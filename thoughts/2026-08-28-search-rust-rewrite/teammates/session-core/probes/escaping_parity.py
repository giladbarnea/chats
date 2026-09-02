"""Differential for the inner-tag escaping grammar, both directions.

Python's `_INNER_XML_BLOCK_OPENING_PATTERN` is the oracle. The native codec must
agree on every shape, including the two where Python escapes and a per-line prefix
check does not.

Point at a specific binary with CH=/path/to/ch; defaults to the installed one.
Run from the repo root: CH=... uv run python thoughts/.../probes/escaping_parity.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from chats.formatting import format_to_xml
from chats.model import ConversationFlags, Message

CH = Path(os.environ.get("CH", str(Path.home() / ".local" / "bin" / "ch")))

CASES = {
    "space_no_close": "<thinking is my hobby",
    "tab_attr": '<thinking\tname="x">',
    "newline_attr": '<thinking\nname="x">',
    "space_attr": '<thinking name="x">',
    "bare_close": "<thinking>",
    "mid_line": 'not at line start <thinking name="x">',
    "tool_input_space": "<tool-input is a phrase",
    "tool_output_tab": '<tool-output\tname="Bash">',
    "subagent_task_bare": "<subagent-task>",
    "second_line": 'ordinary first line\n<thinking name="x">',
    "unknown_tag": '<thinkingx name="x">',
}


def native(text: str) -> str:
    canonical = json.dumps(
        [
            {
                "type": "user-message",
                "role": "user",
                "original_index": 1,
                "content": [text],
            }
        ],
        ensure_ascii=False,
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8", newline=""
    ) as handle:
        handle.write(canonical)
        path = handle.name
    try:
        completed = subprocess.run(
            [str(CH), "parse", "-f", "xml", path], capture_output=True
        )
        return completed.stdout.decode("utf-8").rstrip("\n")
    finally:
        Path(path).unlink(missing_ok=True)


def main() -> int:
    print(f"binary under test: {CH}")
    flags = ConversationFlags()
    failures = 0
    for name, text in CASES.items():
        expected = format_to_xml(
            [Message(role="user", index=1, text=text)], flags
        ).rstrip("\n")
        actual = native(text)
        agree = actual == expected
        python_escapes = 'text_encoding="html"' in expected
        native_escapes = 'text_encoding="html"' in actual
        if not agree:
            failures += 1
        print(
            f"  {name:20} python_escapes={str(python_escapes):5} "
            f"native_escapes={str(native_escapes):5} "
            f"{'AGREE' if agree else 'DIVERGE'}"
        )
        if not agree:
            print(f"      expected {expected!r}")
            print(f"      actual   {actual!r}")

    print(f"\n{len(CASES) - failures}/{len(CASES)} shapes agree")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
