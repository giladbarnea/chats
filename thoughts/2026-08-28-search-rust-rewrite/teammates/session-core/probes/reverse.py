import json
import subprocess
from pathlib import Path

from chats.formatting import format_to_xml
from chats.model import ConversationFlags, Message

CH = Path.home() / ".local" / "bin" / "ch"

CASES = {
    "tab_attr": "<thinking\tname=\"x\">",
    "space_attr": '<thinking name="x">',
    "bare_close": "<thinking>",
    "space_no_close": "<thinking is my hobby",
    "newline_attr": '<thinking\nname="x">',
}

flags = ConversationFlags()
for name, text in CASES.items():
    message = Message(role="user", index=1, text=text)
    python_out = format_to_xml([message], flags)
    canonical = json.dumps(
        [
            {
                "type": "user-message",
                "role": "user",
                "original_index": 1,
                "content": [text],
            }
        ]
    )
    path = Path(f"/tmp/rev_{name}.json")
    path.write_text(canonical, encoding="utf-8")
    rust_out = subprocess.run(
        [str(CH), "parse", "-f", "xml", str(path)],
        capture_output=True,
    ).stdout.decode("utf-8")
    path.unlink(missing_ok=True)

    python_escapes = 'text_encoding="html"' in python_out
    rust_escapes = 'text_encoding="html"' in rust_out
    verdict = "AGREE" if python_escapes == rust_escapes else "DIVERGE"
    print(f"{name:16} python_escapes={python_escapes!s:5} rust_escapes={rust_escapes!s:5} {verdict}")
