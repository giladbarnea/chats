#!/usr/bin/env python3
"""Write the authored newline fixtures and record what Python does with each.

The real pool cannot grade F1: 0 of 5,061 `.jsonl` files carry a literal CR byte
(measured 2026-09-01, every root under ~/.claude, ~/.pi and ~/.codex). So these
four files are authored, and this script is what makes them trustworthy — it
writes them and then states what Python does with each, so the Rust expectations
are transcribed from a run rather than from a belief about `Path.read_text`.

The fixtures live under a fake HOME because both routes classify a session's
provider by its location, not by its content.

Run from the repo root:
  uv run -p python3 python thoughts/.../probes/make_newline_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAKE_HOME = ROOT / "fixtures" / "home"
SESSION_DIR = FAKE_HOME / ".claude" / "projects" / "-tmp-newline"

CLAUDE_ENTRIES = [
    {"type": "user", "uuid": "u1", "parentUuid": None, "cwd": "/tmp/newline",
     "message": {"role": "user", "content": "alpha question"}},
    {"type": "assistant", "uuid": "a1", "parentUuid": "u1",
     "message": {"role": "assistant", "content": [{"type": "text", "text": "beta answer"}]}},
]

TRANSCRIPT_LINES = ["> alpha question", "⏺ beta answer", "gamma continuation"]

CASES = [
    ("jsonl-crlf.jsonl", "jsonl", "\r\n"),
    ("jsonl-lone-cr.jsonl", "jsonl", "\r"),
    ("raw-transcript-crlf.jsonl", "raw", "\r\n"),
    ("raw-transcript-lone-cr.jsonl", "raw", "\r"),
]


def body(kind: str) -> str:
    if kind == "jsonl":
        return "\n".join(json.dumps(entry, ensure_ascii=False) for entry in CLAUDE_ENTRIES)
    return "\n".join(TRANSCRIPT_LINES)


def main() -> int:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(FAKE_HOME)

    sys.path.insert(0, str(Path.cwd() / "src"))
    from chats.model import ConversationFlags
    from chats.parsing import detect_format
    from chats.session_scan import SessionScan

    flags = ConversationFlags()
    rows = []
    for name, kind, terminator in CASES:
        path = SESSION_DIR / name
        path.write_bytes(body(kind).replace("\n", terminator).encode("utf-8"))
        text = path.read_text(encoding="utf-8")
        scan = SessionScan.from_file(path, flags)
        messages = [(message.role, message.text) for message in scan.messages]
        rows.append((name, messages))
        print(f"--- {name}")
        print(f"  bytes on disk     : {path.read_bytes()!r}")
        print(f"  read_text() gives : {text!r}")
        print(f"  detect_format     : {detect_format(text)}")
        print(f"  provider          : {scan.provider}")
        print(f"  messages          : {messages}")
        print()

    print("expected rows, JSON, for transcription into the Rust gate:")
    print(json.dumps({name: messages for name, messages in rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
