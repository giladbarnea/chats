"""Differential: the whole native Claude route against Python, per rendered message.

Decode, visibility, shortening and the semantic inner-XML render, compared as the one
string search actually matches against. Python at oracle revision `8cb4c5f` is the
oracle. This is the F1 gate.

Point at the driver with RENDER_BIN=/path/to/branchcheck.
Run from the repo root; pass a session limit as argv[1] to sample.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from chats.commands.common import _build_tool_id_map
from chats.formatting import render_message_inner_xml
from chats.model import ConversationFlags, assign_progressive_shortening
from chats.parsing import find_all_supported_session_files, get_jsonl_session_adapter
from chats.session_scan import SessionScan

BIN = os.environ.get("RENDER_BIN")

CONFIGURATIONS = {
    "bare": ConversationFlags(),
    "with-tools": ConversationFlags(show_tools=True),
    "tools-and-agents": ConversationFlags(show_tools=True, show_agents=True),
    "thinking": ConversationFlags(show_thinking=True),
    "branches": ConversationFlags(show_branches=True),
    "shortened": ConversationFlags(show_tools=True, shorten=True, shorten_max_chars=120),
    "progressive": ConversationFlags(
        show_tools=True, shorten=True, shorten_max_chars=128, shorten_progressive=True
    ),
}


PROVIDER = os.environ.get("PROVIDER", "claude")


def claude_sessions(limit: int) -> list[Path]:
    found = []
    for session in find_all_supported_session_files():
        try:
            if get_jsonl_session_adapter(session).name == PROVIDER:
                found.append(session)
        except (ValueError, OSError):
            continue
        if limit and len(found) >= limit:
            break
    return found


def digest(value: str) -> str:
    """FNV-1a 64, matching the driver. Only equality matters; this keeps rows small
    so a megabyte-wide rendered message cannot truncate the protocol."""
    hashed = 0xCBF29CE484222325
    for byte in value.encode("utf-8"):
        hashed ^= byte
        hashed = (hashed * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{hashed:016x}"


def python_rendered(snapshot: Path, origin: Path, flags: ConversationFlags) -> list[str]:
    # Content from the snapshot so both sides see identical bytes; path from the
    # original so Python's provider classification, which is path-based, still works.
    content = snapshot.read_text(encoding="utf-8")
    scan = SessionScan.from_content(content, flags, source_path=origin)
    messages = list(scan.messages)
    tool_id_map = _build_tool_id_map(messages)
    assign_progressive_shortening(messages, flags, tool_id_map)
    rendered = [render_message_inner_xml(message, flags, tool_id_map) for message in messages]
    return rendered if os.environ.get("DETAIL") else [digest(text) for text in rendered]


def main() -> int:
    snapshot_root: Path | None = None
    try:
        return _run()
    finally:
        # ~1.2 GiB per run leaked before this existed; 28 orphaned snapshot
        # directories reached 33 GiB and took every gate on the mission down with
        # the volume. The copy is scratch, not evidence — nothing reads it after.
        if _SNAPSHOT_ROOT[0] is not None:
            shutil.rmtree(_SNAPSHOT_ROOT[0], ignore_errors=True)


_SNAPSHOT_ROOT: list[Path | None] = [None]


def _run() -> int:
    if not BIN:
        print("set RENDER_BIN to the differential driver")
        return 2
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    live = claude_sessions(limit)

    # Synthesized fixtures first: they carry shapes the real corpus does not contain.
    # All 477 user-agent envelopes in the corpus have <duration_ms>; Python's grammar
    # makes it optional, so without these the prior team's exact defect is invisible.
    fixture_dir = Path(__file__).resolve().parent.parent / f"{PROVIDER}-fixtures"
    fixtures = sorted(fixture_dir.glob("*.jsonl")) if fixture_dir.is_dir() else []
    live = fixtures + live
    if fixtures:
        print(f"including {len(fixtures)} synthesized {PROVIDER} fixture(s)")

    # Snapshot before comparing. Several of these sessions belong to agents working
    # right now, so the file grows between the driver's read and Python's. That
    # produces message-count differences that are the instrument's, not the product's.
    snapshot_root = Path(tempfile.mkdtemp(prefix="claude-render-snapshot-"))
    _SNAPSHOT_ROOT[0] = snapshot_root
    sessions: list[tuple[Path, Path]] = []
    for index, source in enumerate(live):
        target = snapshot_root / f"{index:04d}-{source.name}"
        try:
            target.write_bytes(source.read_bytes())
        except OSError:
            continue
        sessions.append((target, source))
    # A precondition, not a caveat. A run that snapshots fewer sessions than the pool
    # holds did not happen: it reports `mismatches: 0` over a smaller corpus, and the
    # verdict alone cannot show it. One run under a full disk covered 170 fewer
    # sessions and still read as clean.
    if len(sessions) != len(live):
        print(
            f"PRECONDITION FAILED: snapshotted {len(sessions)} of {len(live)} sessions. "
            "A partial corpus cannot produce a verdict; refusing to compare."
        )
        return 1
    print(f"snapshotted {len(sessions)} of {len(live)} sessions to a stable copy")

    cases = [
        {"path": str(snapshot), "origin": str(origin), "flags": name, "provider": PROVIDER}
        for snapshot, origin in sessions
        for name in CONFIGURATIONS
    ]
    payload = "\n".join(json.dumps(case) for case in cases) + "\n"
    completed = subprocess.run([BIN], input=payload.encode("utf-8"), capture_output=True)
    if completed.returncode != 0:
        print(completed.stderr.decode("utf-8")[:3000])
        return 1
    lines = [line for line in completed.stdout.decode("utf-8").splitlines() if line]
    native = [json.loads(line) for line in lines]
    # A gate must report what it covered. Silent row loss misaligns every later case
    # and reads as hundreds of product defects.
    if len(native) != len(cases):
        print(
            f"PROTOCOL ERROR: driver returned {len(native)} rows for {len(cases)} cases. "
            "Results would be misaligned; refusing to compare."
        )
        return 1

    mismatches: list[tuple] = []
    by_configuration: Counter = Counter()
    count_mismatch = 0
    for case, actual in zip(cases, native):
        flags = CONFIGURATIONS[case["flags"]]
        try:
            expected = python_rendered(Path(case["path"]), Path(case["origin"]), flags)
        except Exception as error:  # a decode failure is itself a divergence
            mismatches.append((case, f"python raised {type(error).__name__}: {error}", ""))
            by_configuration[case["flags"]] += 1
            continue
        if expected != actual:
            mismatches.append((case, expected, actual))
            by_configuration[case["flags"]] += 1
            if len(expected) != len(actual):
                count_mismatch += 1

    print(f"sessions: {len(sessions)}  configurations: {len(CONFIGURATIONS)}  cases: {len(cases)}")
    print(f"mismatches: {len(mismatches)}  (of which differ in message count: {count_mismatch})")
    if by_configuration:
        print(f"by configuration: {dict(by_configuration)}")
    for case, expected, actual in mismatches[:4]:
        print(f"\n  {Path(case['path']).name} [{case['flags']}]")
        if isinstance(expected, str):
            print(f"    {expected}")
            continue
        print(f"    python {len(expected)} messages, native {len(actual)}")
        for position, (left, right) in enumerate(zip(expected, actual)):
            if left != right:
                print(f"    first differing message at {position}")
                print(f"      python {left[:220]!r}")
                print(f"      native {right[:220]!r}")
                break
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
