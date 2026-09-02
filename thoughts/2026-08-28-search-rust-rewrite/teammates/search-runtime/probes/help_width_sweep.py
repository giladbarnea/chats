#!/usr/bin/env -S uv run
"""Differential gate: native `ch search --help` against CPython argparse.

Sweeps every terminal width from 20 to 200 and compares raw bytes. argparse
rewraps help to the terminal, so a single-width check cannot see a width-blind
implementation — which is exactly the defect the abandoned branch shipped, with
static USAGE and HELP constants that passed its own 704-case corpus because
every case in it pinned COLUMNS=96.

Capture goes through a plain pipe rather than a pty, because nothing here needs
colour and a pipe has no line discipline to reason about.

Do **not** read that as "a pty corrupts narrow output". I proposed that rule and
`query-semantics` refuted it by measurement: at width 27 the pty and pipe
captures have identical line counts, 132 and 132, so no hard-wrapping occurred,
and the artifact also appears at width 48 where nothing overflows at all. The
real defect was a single stray carriage return per capture — raw bytes of
`\r\r\n`, where a `.replace("\r\n", "\n")` consumes one pair and leaves the odd
`\r` behind. Stripping every `\r` gives 181 of 181.

That matters because the colour gates *need* a pty, and narrow widths are where
elision in list rows and panel titles gets interesting. A "no pty below 47
columns" rule would delete exactly the coverage the two-widths requirement exists
to get.

Still true and unrelated to the above: argparse emits lines longer than the
terminal at narrow widths. At COLUMNS=27 the longest help line is 46 columns,
because the usage continuation indent plus an unbreakable token like
`[--color {always,never,auto}]` overflows and argparse will not break inside it.

Falsification: `--falsify` pins one width for the native side regardless of the
requested one, simulating a width-blind implementation. The sweep must fail. A
gate that has never been observed to fail is not yet evidence.

    uv run help_width_sweep.py [--falsify]
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

FIRST_WIDTH = 20
LAST_WIDTH = 200
FALSIFY_WIDTH = 96

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
ORACLE = PROJECT_ROOT / ".venv/bin/ch-legacy"
NATIVE = PROJECT_ROOT / "target/debug/ch"


def isolated_home() -> str:
    """A home with an empty session pool, so help never depends on the corpus."""
    home = tempfile.mkdtemp()
    pathlib.Path(home, ".claude/projects/empty").mkdir(parents=True)
    return home


def help_bytes(binary: pathlib.Path, home: str, columns: int) -> bytes:
    result = subprocess.run(
        [str(binary), "search", "--help"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "HOME": home, "COLUMNS": str(columns)},
    )
    return result.stdout


def main() -> int:
    falsify = "--falsify" in sys.argv
    if not ORACLE.exists():
        print(f"oracle missing: {ORACLE}")
        return 2
    if not NATIVE.exists():
        print(f"native binary missing: {NATIVE} (cargo build --no-default-features)")
        return 2

    home = isolated_home()
    mismatched: list[int] = []
    for columns in range(FIRST_WIDTH, LAST_WIDTH + 1):
        expected = help_bytes(ORACLE, home, columns)
        actual = help_bytes(NATIVE, home, FALSIFY_WIDTH if falsify else columns)
        if expected != actual:
            mismatched.append(columns)

    swept = LAST_WIDTH - FIRST_WIDTH + 1
    print(f"widths swept: {swept}   mismatches: {len(mismatched)}")
    if mismatched:
        print(f"failing widths: {mismatched[:20]}")

    if falsify:
        if mismatched:
            print("FALSIFIED as expected: a width-blind implementation fails the sweep.")
            return 0
        print("GATE IS INERT: a width-blind implementation passed. Fix the gate.")
        return 1
    return 1 if mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
