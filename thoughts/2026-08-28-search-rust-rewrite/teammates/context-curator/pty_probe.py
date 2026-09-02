#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.14.*"
# dependencies = []
# ///
"""Falsification probe: does a pty winsize actually change what the oracle renders?

The whole generated-content-plus-width plan rests on one assumption — that
running `ch-legacy search` under a real pty with a set window size makes Rich
resolve that width, so the harness exercises the resolution path that every
existing test bypasses by pinning COLUMNS.

If output at two widths is identical, the assumption is false and the plan
needs rethinking before anything is generated.

Run with no arguments. Prints PASS or FAIL per check.
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

PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"
HOME = Path(
    "/private/tmp/claude-501/-Users-giladbarnea-dev-chats"
    "/34993643-8a40-408e-be63-a5ecaf66fe03/scratchpad/repro/home"
)


def run_under_pty(
    arguments: list[str],
    *,
    columns: int,
    rows: int = 40,
    home: Path = HOME,
    strip_columns_env: bool = True,
    timeout: float = 60.0,
) -> tuple[bytes, int]:
    """Run `ch-legacy search ...` attached to a pty of the given size.

    Returns combined output bytes and the exit status. stdout and stderr share
    the pty, exactly as they would in a terminal, so this measures what a user
    sees rather than what a redirect captures.
    """
    primary, secondary = pty.openpty()
    fcntl.ioctl(
        secondary, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0)
    )

    environment = os.environ.copy()
    environment.update({
        "HOME": str(home),
        "TZ": "Asia/Jerusalem",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "LINES": str(rows),
    })
    # The point of the probe: let the terminal, not the variable, decide.
    if strip_columns_env:
        environment.pop("COLUMNS", None)
    environment.pop("NO_COLOR", None)

    process = subprocess.Popen(
        [str(LEGACY), "search", *arguments],
        stdin=secondary,
        stdout=secondary,
        stderr=secondary,
        cwd=PROJECT_ROOT,
        env=environment,
        close_fds=True,
    )
    os.close(secondary)

    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], timeout)
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
    process.wait(timeout=timeout)
    return b"".join(chunks), process.returncode


def display_width(text: str) -> int:
    """Terminal columns occupied by `text`.

    Byte length is the wrong measure here: a box-drawing rule filling 72
    columns is 216 bytes, and reporting that as a 216-column line makes a
    correctly wrapped render look broken.
    """
    import unicodedata

    columns = 0
    for character in text:
        if unicodedata.combining(character):
            continue
        columns += 2 if unicodedata.east_asian_width(character) in "WF" else 1
    return columns


def longest_line(output: bytes) -> int:
    """Longest visible line in terminal columns, ignoring escape sequences."""
    import re

    plain = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", output)
    text = plain.decode("utf-8", errors="replace")
    return max(
        (display_width(line.rstrip("\r")) for line in text.split("\n")), default=0
    )


def main() -> int:
    if not LEGACY.exists():
        print(f"FAIL: no oracle launcher at {LEGACY}")
        return 1
    if not HOME.exists():
        print(f"FAIL: no fixture home at {HOME}")
        return 1

    arguments = ["needle five", "--color", "always", "--no-paging", "--no-metadata"]
    narrow, wide = 72, 137  # neither is 80, neither is the corpus default 96

    narrow_output, narrow_status = run_under_pty(arguments, columns=narrow)
    wide_output, wide_status = run_under_pty(arguments, columns=wide)

    checks: list[tuple[str, bool, str]] = []

    checks.append((
        "both runs succeed",
        narrow_status == 0 and wide_status == 0,
        f"exit {narrow_status} / {wide_status}",
    ))
    checks.append((
        "output differs between widths",
        narrow_output != wide_output,
        f"{len(narrow_output)} vs {len(wide_output)} bytes",
    ))
    checks.append((
        f"narrow output fits {narrow} columns",
        longest_line(narrow_output) <= narrow,
        f"longest visible line {longest_line(narrow_output)}",
    ))
    checks.append((
        f"wide output uses more than {narrow} columns",
        longest_line(wide_output) > narrow,
        f"longest visible line {longest_line(wide_output)}",
    ))

    # COLUMNS must still win when set, or the override contract is broken.
    os.environ["COLUMNS"] = str(narrow)
    forced_output, _ = run_under_pty(
        arguments, columns=wide, strip_columns_env=False
    )
    del os.environ["COLUMNS"]
    checks.append((
        "COLUMNS overrides a wider pty",
        longest_line(forced_output) <= narrow,
        f"pty {wide}, COLUMNS {narrow}, longest line {longest_line(forced_output)}",
    ))

    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name:44} ({detail})")

    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
