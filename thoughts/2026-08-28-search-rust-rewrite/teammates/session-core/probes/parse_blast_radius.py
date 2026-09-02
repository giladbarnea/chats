"""Characterize which public `ch parse` bytes move when the inner-tag escaping defect is repaired.

Runs the true public route over the real session corpus: Python renders canonical
JSON, the installed native `ch parse` converts it to XML, and that is compared
byte-for-byte against Python's own `format_to_xml`. Any difference is a byte that
moves. Read-only; prints counts and tag shapes, never message content.

Usage: uv run python thoughts/.../probes/parse_blast_radius.py [session_limit]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from chats.commands.common import _build_tool_id_map
from chats.formatting import format_to_json, format_to_xml
from chats.model import ConversationFlags
from chats.parsing import find_all_supported_session_files, get_jsonl_session_adapter
from chats.session_scan import SessionScan

CH = Path(os.environ.get("CH", str(Path.home() / ".local" / "bin" / "ch")))
INNER_TAGS = ("thinking", "tool-input", "tool-output", "subagent-task")

# Python's authority: a complete opening tag at line start.
PYTHON_OPENING = re.compile(
    rf"^<(?:{'|'.join(re.escape(tag) for tag in INNER_TAGS)})"
    r'(?:\s+[\w-]+="[^"]*")*>',
    re.MULTILINE,
)


def rust_says_inner_tag(line: str) -> bool:
    """Reproduce codecs.rs::has_inner_opening_tag — `<tag` then `>` or a space."""
    if not line.startswith("<"):
        return False
    remainder = line[1:]
    for tag in INNER_TAGS:
        if remainder.startswith(tag):
            suffix = remainder[len(tag) :]
            if suffix.startswith(">") or suffix.startswith(" "):
                return True
    return False


def divergent_lines(text: str) -> list[str]:
    """Lines Rust would escape and Python would not."""
    return [
        line
        for line in text.split("\n")
        if rust_says_inner_tag(line) and PYTHON_OPENING.match(line) is None
    ]


CONFIGURATIONS = {
    "bare": ConversationFlags(),
    "with-tools": ConversationFlags(show_tools=True),
    "tools-and-agents": ConversationFlags(show_tools=True, show_agents=True),
}


def main() -> int:
    argument = sys.argv[1] if len(sys.argv) > 1 else ""
    supported = find_all_supported_session_files()

    if argument and Path(argument).is_file():
        # A candidate list from the raw-text gate, intersected with real sessions.
        wanted = {
            line.strip() for line in Path(argument).read_text().splitlines() if line.strip()
        }
        sessions = [session for session in supported if str(session) in wanted]
        print(f"candidate list: {len(wanted)} paths, {len(sessions)} are supported sessions")
    else:
        sessions = supported[: int(argument)] if argument else supported

    totals = Counter()
    differing_sessions: set[str] = set()
    shapes: Counter = Counter()
    providers_affected: Counter = Counter()

    for session in sessions:
        try:
            provider = get_jsonl_session_adapter(session).name
        except (ValueError, OSError):
            totals["provider_unresolved"] += 1
            continue

        for configuration, flags in CONFIGURATIONS.items():
            totals["comparisons"] += 1
            try:
                scan = SessionScan.from_file(session, flags)
            except (OSError, UnicodeDecodeError, ValueError):
                totals["scan_failed"] += 1
                continue

            messages = list(scan.messages)
            if not messages:
                continue
            tool_id_map = _build_tool_id_map(messages)

            try:
                canonical = format_to_json(messages, flags, tool_id_map)
                expected = format_to_xml(messages, flags, tool_id_map)
            except Exception:
                totals["python_render_failed"] += 1
                continue

            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8"
            ) as handle:
                handle.write(canonical)
                canonical_path = handle.name

            try:
                completed = subprocess.run(
                    [str(CH), "parse", "-f", "xml", canonical_path],
                    capture_output=True,
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                totals["native_timeout"] += 1
                continue
            finally:
                Path(canonical_path).unlink(missing_ok=True)

            if completed.returncode != 0:
                totals["native_error"] += 1
                continue

            # The CLI terminates its output with a newline; `format_to_xml` returns
            # the document without one. That single byte is the CLI's own framing,
            # not a rendering difference, so it is normalized away on both sides.
            if completed.stdout.decode('utf-8').rstrip("\n") == expected.rstrip("\n"):
                totals["identical"] += 1
                continue

            totals["differ"] += 1
            differing_sessions.add(str(session))
            providers_affected[provider] += 1

            # Attribute the difference: is it the known escaping defect?
            for message in messages:
                for payload in (message.text, message.thinking or "", message.plan or ""):
                    for line in divergent_lines(payload):
                        prefix = line[: line.find(" ") if " " in line else len(line)]
                        shapes[prefix[:40]] += 1

    print("=== ch parse public-route differential, real corpus ===")
    print(f"sessions scanned      {len(sessions)}")
    for key in (
        "comparisons",
        "identical",
        "differ",
        "scan_failed",
        "python_render_failed",
        "native_error",
        "native_timeout",
        "provider_unresolved",
    ):
        print(f"{key:22}{totals[key]}")
    print(f"\ndistinct sessions whose bytes move: {len(differing_sessions)}")
    if providers_affected:
        print(f"by provider: {dict(providers_affected)}")
    if shapes:
        print("\ndivergent line prefixes (Rust escapes, Python does not):")
        for shape, count in shapes.most_common(20):
            print(f"  {count:6}  {shape!r}")
    else:
        print("\nno divergent inner-tag line shapes found in the scanned corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
