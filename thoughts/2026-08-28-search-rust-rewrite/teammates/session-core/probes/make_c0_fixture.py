"""Author a session carrying C0 separators at string edges, where `.strip()` and `.trim()` disagree.

Measured: not one file in the 5,046-session corpus contains U+001C-001F at all, so
every differential is blind to this. Zero occurrences here is an instrument limit, not
a property of the world — transcripts carry arbitrary tool output, and a dump or a
pasted terminal trace produces exactly these bytes.

Python's `str.strip()` removes U+001C-001F; Rust's `str::trim` does not, because the
Unicode `White_Space` property excludes them. Every site in `session.rs` that ports a
`.strip()` with a bare `.trim()` diverges here and nowhere else.

Validated against Python, never against the port.

Run from the repo root:
  uv run python thoughts/.../probes/make_c0_fixture.py [out_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chats.model import ConversationFlags
from chats.parsing import _iter_jsonl_entries, _parse_default_jsonl_entries

FS = ""  # file separator
US = ""  # unit separator

STAMP = "2026-08-20T{:02d}:00:00.000Z"


def user(uuid: str, parent: str | None, text: str, minute: int) -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "parentUuid": parent,
        "timestamp": STAMP.format(minute),
        "message": {"role": "user", "content": text},
    }


def assistant(uuid: str, parent: str, text: str, minute: int) -> dict:
    return {
        "type": "assistant",
        "uuid": uuid,
        "parentUuid": parent,
        "timestamp": STAMP.format(minute),
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


ENTRIES = [
    user("u1", None, "a question", 0),
    # The assistant text block is trimmed by `.strip()` in Python at
    # `_parse_assistant_entry`, so the separators vanish there and survive a bare
    # `.trim()` in Rust. Both ends, because leading and trailing are separate calls.
    assistant("a1", "u1", f"{FS}answer with separators at both ends{US}", 1),
    # A second one where the separator is the *only* thing outside real text, so the
    # divergence is a leading character rather than a whole-string difference.
    assistant("a2", "a1", f"{US}{FS}second answer", 2),
]


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("claude-fixtures")
    out_dir.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(entry) for entry in ENTRIES) + "\n"
    target = out_dir / "c0-separators-at-string-edges.jsonl"
    target.write_text(content, encoding="utf-8")

    messages = _parse_default_jsonl_entries(_iter_jsonl_entries(content), ConversationFlags())
    texts = [message.text for message in messages]

    # Python must have removed every separator. If any survives, the fixture does not
    # reach the behaviour it names and must not be landed.
    survives = [text for text in texts if FS in text or US in text]
    reaches = len(messages) == 3 and not survives

    print(f"[{'OK ' if reaches else 'FAIL'}] c0-separators-at-string-edges")
    print(f"        python yields {len(messages)} message(s)")
    for text in texts:
        print(f"          {text!r}")
    if survives:
        print(f"        SEPARATORS SURVIVED PYTHON: {survives!r} — fixture is wrong, not the port")
    print(f"\nwrote {target}")
    return 0 if reaches else 1


if __name__ == "__main__":
    raise SystemExit(main())
