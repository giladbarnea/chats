#!/usr/bin/env -S uv run
"""F5 reachability: does a real user text block make the two command-tag patterns disagree?

Python requires the closing tag to match the opening one, via a backreference:
    (?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</(?P=tag)>[ \t]*
The `regex` crate has no backreferences, so rust/session.rs:758 widened it:
    ^(?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</command-[a-z0-9-]+>[ \t]*$

`is_hidden_user_command_text` decides whether a user text block renders at all, so a
block the wide pattern accepts and the narrow one rejects is a message that shows in
Python and DISAPPEARS natively.

The wide pattern accepts a superset of the narrow one, so disagreement is
one-directional: never Python hiding what the native route shows.

Method note (22j): the Rust half is transcribed here, so this measures the CORPUS
against two patterns, not the artifact. The subject is the transcript pool; the
patterns are inputs. Both are applied with identical line splitting, so this isolates
the backreference from F4's `lines()`-vs-`splitlines()` gap, which measured zero.

`--falsify` runs the instrument against synthetic shapes instead of the pool, per
L48: a probe that catches zero may be broken rather than the world being flat, and
the two look identical. The pool result below is only quotable because `--falsify`
fires on four shapes and stays silent on three controls.

Read-only. `main` is guarded so importing WIDE/NARROW/verdict does not rescan.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from chats.parsing import _COMMAND_TAG_LINE_PATTERN, _discover_session_file_rows

# rust/session.rs:758, verbatim minus the ^ $ anchors, which `re.fullmatch` supplies.
WIDE = re.compile(
    r"(?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</command-[a-z0-9-]+>[ \t]*",
    re.DOTALL,
)
NARROW = _COMMAND_TAG_LINE_PATTERN

FALSIFIERS = [
    ("mismatched pair, single line", "<command-name>x</command-args>", True),
    ("mismatched pair, indented", "    <command-name>x</command-args>", True),
    ("three tags, outer mismatch", "<command-a>x</command-b>y</command-c>", True),
    ("mixed: one line mismatched", "<command-name>a</command-name>\n<command-message>b</command-args>", True),
    ("matched pair (control)", "<command-name>x</command-name>", False),
    ("two matched lines (control)", "<command-name>a</command-name>\n<command-args>b</command-args>", False),
    ("not a command tag (control)", "hello world", False),
]


def verdict(pattern: re.Pattern, text: str) -> bool:
    """True when the whole block parses as pure command-tag lines."""
    rows = 0
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if pattern.fullmatch(raw) is None:
            return False
        rows += 1
    return rows > 0


def user_text_blocks(entry: dict):
    if entry.get("type") != "user":
        return
    message = entry.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return
    content = message.get("content")
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                yield item["text"]


def falsify() -> None:
    print(f"{'case':32s} {'python(narrow)':>15s} {'rust(wide)':>12s}   expected")
    failures = 0
    for label, text, should_disagree in FALSIFIERS:
        narrow, wide = verdict(NARROW, text), verdict(WIDE, text)
        disagreed = narrow != wide
        state = "ok" if disagreed == should_disagree else "*** INSTRUMENT BROKEN ***"
        failures += disagreed != should_disagree
        print(f"{label:32s} {str(narrow):>15s} {str(wide):>12s}   {state}")
    print()
    print("instrument is able to fire" if not failures else f"{failures} falsifier(s) failed")


def scan() -> None:
    stats = Counter()
    disagreements = []
    mismatched_lines = []

    for path, *_ in _discover_session_file_rows(include_sidechains=True):
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if not isinstance(entry, dict):
                continue
            for text in user_text_blocks(entry):
                stats["user text blocks"] += 1
                if "<command-" not in text:
                    continue
                stats["blocks mentioning <command-"] += 1
                wide, narrow = verdict(WIDE, text), verdict(NARROW, text)
                if wide != narrow:
                    stats["*** DISAGREE — renders in Python, vanishes natively ***"] += 1
                    if len(disagreements) < 10:
                        disagreements.append((Path(path).name, text[:400]))
                    continue
                for raw in text.splitlines():
                    opens = set(re.findall(r"<(command-[a-z0-9-]+)>", raw))
                    closes = set(re.findall(r"</(command-[a-z0-9-]+)>", raw))
                    if opens and closes and opens != closes:
                        stats["line carrying a MISMATCHED tag pair"] += 1
                        if len(mismatched_lines) < 10:
                            mismatched_lines.append((Path(path).name, raw[:200]))

    for key, value in stats.most_common():
        print(f"{value:8d}  {key}")
    print()
    if disagreements:
        print("DISAGREEMENTS (22c: read them, never report the count alone):")
        for name, sample in disagreements:
            print(f"  {name}\n        {sample!r}\n")
    else:
        print("No block in the pool makes the two patterns disagree.")
    if mismatched_lines:
        print("Lines carrying a mismatched command-tag pair:")
        for name, sample in mismatched_lines:
            print(f"  {name}\n        {sample!r}")
    print()
    print("The pool is written by live sessions while this runs. Three runs on")
    print("2026-08-28/29 gave 4129, 4124 and 4126 blocks. Quote the count with its date.")


if __name__ == "__main__":
    falsify() if "--falsify" in sys.argv else scan()
