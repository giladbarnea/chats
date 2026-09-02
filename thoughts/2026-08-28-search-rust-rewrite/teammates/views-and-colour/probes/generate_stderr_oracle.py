#!/usr/bin/env -S uv run
"""Record the exact bytes the product's stderr consoles emit.

Four consoles, three of them defective in the same way: `--color` reaches
`init_module_console` and none of the stderr ones, so stderr colour follows
**stderr's own tty-ness** alone. `ch search nomatch --color never 2>/dev/tty` is
coloured. That is preserved, not repaired.

Two further things a reading of `console.py` does not predict, both measured:

- `print_error` and `print_warning` build `Console(stderr=True)` with **no theme**,
  so their `"red"` and `"yellow"` resolve to the standard 16-colour codes 31 and 33
  rather than to truecolor. `print_hint` has the theme and resolves `search.empty`
  to a truecolor triple.
- Rich's `ReprHighlighter` paints these messages **on top of** the base style —
  `repr.str` green on the quoted search term, `repr.path` and `repr.filename` on a
  file path, `repr.number` and `repr.brace` inside `[Errno 21]`. So a port that
  applies a style and stops produces the wrong bytes on every message that
  contains a quoted term, which is every no-results hint.

Each case runs in its own process with **stderr on a pty and stdout discarded**.
The inversion matters: `pty_harness.run_at_width` sends stderr to `DEVNULL`, which
is why no gate on this desk could see any of this.
"""

import base64
import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import sys
import termios
from pathlib import Path

OUTPUT = Path(__file__).with_name("stderr-oracle.json")

# (kind, message). The messages are the shapes the product actually emits, plus
# two chosen to exercise highlighter rules the others do not reach.
CASES = [
    ("hint", 'No sessions match "needle five".'),
    ("hint", 'No sessions match "needle five" with the current filters.'),
    ("hint", 'No sessions match "a AND b" with the current filters.'),
    ("hint", 'No sessions match "-".'),
    ("hint", 'No sessions match "你好你好你好你好你好你好你好你好".'),
    ("error", "Error processing conversation file /Users/ada/.claude/projects/x/1.jsonl: [Errno 21] Is a directory"),
    ("error", "[Errno 21] Is a directory: '/Users/ada/.claude/projects/x'"),
    ("error", "Invalid search query: expected a term, got end of pattern."),
    ("warning", "Search pattern exceeded its step budget: (a+)+b"),
]

TIERS = {
    "truecolor": {"TERM": "xterm-256color", "COLORTERM": "truecolor"},
    "eight-bit": {"TERM": "xterm-256color"},
    "standard": {"TERM": "xterm-16color"},
    "no-color": {"TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "1"},
    "dumb": {"TERM": "dumb"},
}
WIDTHS = [40, 72, 120]

DRIVER = """
import sys
sys.path.insert(0, "src")
from chats.console import print_error, print_hint, print_warning
{"hint": print_hint, "error": print_error, "warning": print_warning}[sys.argv[1]](sys.argv[2])
"""


def stderr_on_pty(arguments, environment, columns):
    controller, follower = pty.openpty()
    fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", 40, columns, 0, 0))
    process = subprocess.Popen(
        arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=follower, env=environment, close_fds=True)
    os.close(follower)
    chunks = []
    while True:
        ready, _, _ = select.select([controller], [], [], 30)
        if not ready:
            break
        try:
            chunk = os.read(controller, 65536)
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    os.close(controller)
    process.wait(timeout=30)
    # Every `\\r`, never `\\r\\n` pairs: a line that exactly fills the terminal
    # emits `\\r\\r\\n` and pair-replacement leaves a stray carriage return.
    return b"".join(chunks).replace(b"\r", b"")


def main() -> None:
    rows = []
    for tier, overrides in TIERS.items():
        for columns in WIDTHS:
            for kind, message in CASES:
                environment = {
                    "PATH": "/usr/bin:/bin:/usr/local/bin",
                    "HOME": "/Users/ada",
                    "TZ": "Asia/Jerusalem",
                    "LC_ALL": "en_US.UTF-8",
                    **overrides,
                }
                captured = stderr_on_pty(
                    [sys.executable, "-c", DRIVER, kind, message], environment, columns)
                rows.append({
                    "tier": tier,
                    "columns": columns,
                    "kind": kind,
                    "message": message,
                    "bytes": base64.b64encode(captured).decode(),
                })
    OUTPUT.write_text(json.dumps({"rows": rows}, indent=1))
    print(f"wrote {OUTPUT.name} - {len(rows)} cases "
          f"({len(TIERS)} tiers x {len(WIDTHS)} widths x {len(CASES)} messages)")


if __name__ == "__main__":
    main()
