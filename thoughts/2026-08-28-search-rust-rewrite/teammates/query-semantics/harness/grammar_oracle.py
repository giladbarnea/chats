"""Record CPython's argument-grammar behavior for `ch search`, byte for byte.

Runs under a pty at a fixed width because argparse rewraps usage and help to the
terminal, so a width-blind capture would hide a whole class of defect. Neither
width is 80: that is argparse's own fallback and also the native side's, so a
diff at 80 hides both a width defect and a total failure to measure.

Usage:
    uv run python grammar_oracle.py <out.json> [--binary ch-legacy] [--widths 96,60]
"""

from __future__ import annotations

import argparse
import json
import os
import pty
import select
import subprocess
import sys

# Argument shapes whose output is pure grammar — usage, help, and errors — with
# no dependency on the session corpus. The rest of the command's surface belongs
# to the engine's own gate, not here.
GRAMMAR_CASES: list[list[str]] = [
    [],
    ["--help"],
    ["-h"],
    ["needle", "extra"],
    ["needle", "--bogus"],
    ["-s", "-i", "needle"],
    ["--color", "bogus", "needle"],
    ["-p", "bogus", "needle"],
    ["--short", "7", "needle"],
    ["-t", "needle"],
    ["-T", "needle"],
    ["-T", "bogus", "needle"],
    ["--"],
]


def run_at_width(binary: str, args: list[str], columns: int) -> dict:
    """Run one invocation under a pty sized to `columns`, capturing raw bytes."""
    primary, secondary = pty.openpty()
    import fcntl
    import struct
    import termios

    fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columns, 0, 0))

    environment = dict(os.environ)
    environment.pop("COLUMNS", None)
    environment["TERM"] = "dumb"

    process = subprocess.Popen(
        [binary, "search", *args],
        stdout=secondary,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        env=environment,
        text=False,
    )
    os.close(secondary)

    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], 10.0)
        if not ready:
            break
        try:
            chunk = os.read(primary, 65536)
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    os.close(primary)
    stderr = process.communicate()[1]
    return {
        "columns": str(columns),
        "args": args,
        "exit": process.returncode,
        # A pty turns \n into \r\n, and emits \r\r\n when a line exactly fills
        # the terminal. Replacing "\r\n" once leaves the stray \r behind and
        # invents a mismatch at precisely the widths worth testing, so strip
        # every carriage return instead.
        "stdout": b"".join(chunks).decode("utf-8", "replace").replace("\r", ""),
        "stderr": stderr.decode("utf-8", "replace").replace("\r", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--binary", default="ch-legacy")
    parser.add_argument("--widths", default="96,60")
    options = parser.parse_args()

    widths = [int(width) for width in options.widths.split(",")]
    assert 80 not in widths, "80 is argparse's own fallback and hides width defects"

    results = [
        run_at_width(options.binary, case, width)
        for width in widths
        for case in GRAMMAR_CASES
    ]
    with open(options.out, "w") as handle:
        json.dump(results, handle, indent=1)
    print(f"{len(results)} cases at widths {widths} -> {options.out}")


if __name__ == "__main__":
    main()
