"""Minimal repro: native `ch parse` normalizes carriage returns inside content, Python does not.

Run from the repo root: uv run python thoughts/.../probes/carriage_return.py
"""

import json
import subprocess
import tempfile
from pathlib import Path

from chats.formatting import format_to_xml
from chats.model import ConversationFlags, Message

CH = Path.home() / ".local" / "bin" / "ch"

CASES = {
    "crlf": "alpha\r\nbeta",
    "lone_cr": "alpha\rbeta",
    "cr_in_tool_output": None,  # filled below
}

for name, text in list(CASES.items()):
    if text is None:
        continue
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

    literal_cr = b"\r" in Path(path).read_bytes()
    native = subprocess.run(
        [str(CH), "parse", "-f", "xml", path], capture_output=True
    ).stdout.decode("utf-8").rstrip("\n")
    Path(path).unlink(missing_ok=True)

    python = format_to_xml(
        [Message(role="user", index=1, text=text)], ConversationFlags()
    ).rstrip("\n")

    verdict = "MATCH" if native == python else "DIVERGE"
    print(f"--- {name}  (file contains literal CR byte: {literal_cr})")
    print(f"  native: {native!r}")
    print(f"  python: {python!r}")
    print(f"  {verdict}\n")
