#!/usr/bin/env -S uv run
"""Item 10: `--color never` still colours stderr when **stderr** is a tty.

**A pty on stdout does not answer this.** The colour choice reaches stdout's console and
none of the stderr ones, so the question is whether the *stderr* console colours — and
that is decided solely by whether stderr is a tty. Every coloured gate on this mission
puts the pty on stdout, which is why this behaviour has never been measured through the
native route.

**`script` failing here is a fact about `script`.** `pty.openpty()` works, and the
follower can be attached to stderr alone while stdout goes to a pipe.
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
from pathlib import Path

NATIVE = Path("target/release/ch").resolve()
LEGACY = Path(".venv/bin/ch-legacy").resolve()


def run_with_pty_stderr(executable: Path, arguments: list[str], home: Path,
                        *, columns: int = 96) -> tuple[bytes, int]:
    """Run the binary with **stderr** on a pty and stdout on a pipe."""
    primary, secondary = pty.openpty()
    fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 40, columns, 0, 0))
    environment = {k: v for k, v in os.environ.items() if k not in {"COLUMNS", "NO_COLOR"}}
    environment.update({
        "HOME": str(home), "TERM": "xterm-256color", "COLORTERM": "truecolor",
    })
    process = subprocess.Popen(
        [str(executable), "search", *arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=secondary,
        env=environment, close_fds=True,
    )
    os.close(secondary)
    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], 60.0)
        if not ready:
            break
        try:
            data = os.read(primary, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    os.close(primary)
    return b"".join(chunks), process.wait()


def main() -> None:
    import json, tempfile
    root = Path(tempfile.mkdtemp()); home = root / "h"
    directory = home / ".claude" / "projects" / "tty"
    directory.mkdir(parents=True)
    (directory / "aaaaaaaa-0010-4000-8000-000000000010.jsonl").write_text(
        json.dumps({
            "type": "user", "uuid": "u0", "timestamp": "2026-08-20T13:00:00.000Z",
            "cwd": "/tmp/tty", "message": {"role": "user", "content": "a present session"},
        }) + "\n"
    )

    print("stderr on a pty, stdout on a pipe — the shape item 10 is about\n")
    shapes = [
        (["zzzz-no-such-term"], "hint, bare"),
        (["zzzz-no-such-term", "--color", "never"], "hint, never"),
        (["zzzz-no-such-term", "--color", "always"], "hint, always"),
        (["zzzz-no-such-term", "--color", "auto"], "hint, auto"),
        # `print_warning` and `print_error` build their own bare `Console(stderr=True)`
        # too, so the same question is asked of all three stderr consoles.
        (["needle", "--only-user", "--only-assistant"], "warning, bare"),
        (["needle", "--only-user", "--only-assistant", "--color", "never"], "warning, never"),
        (["needle", "-ma", "notadate"], "error, bare"),
        (["needle", "-ma", "notadate", "--color", "never"], "error, never"),
    ]
    failures = 0
    for arguments, label in shapes:
        native, native_code = run_with_pty_stderr(NATIVE, arguments, home)
        legacy, legacy_code = run_with_pty_stderr(LEGACY, arguments, home)
        same = (native, native_code) == (legacy, legacy_code)
        coloured = b"\x1b[" in legacy
        print(f"{'SAME    ' if same else 'DIFFERS '} {label:16} "
              f"[legacy {len(legacy)}B, coloured={coloured}, exit {legacy_code}]")
        if not same:
            failures += 1
            print(f"      legacy {legacy[:160]!r}")
            print(f"      native {native[:160]!r}")
    if not any(b"\x1b[" in run_with_pty_stderr(LEGACY, a, home)[0] for a, _ in shapes):
        print("\n⚠ VACUOUS: `ch-legacy` emitted no colour on stderr under any shape, so "
              "this probe never reached the behaviour it exists for.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
