#!/usr/bin/env python3
"""Byte differential: the native `ch search` route against `ch-legacy search`.

Compares **stdout bytes, stderr bytes and exit status** for every command shape, on
a fixed pool under a pinned clock. This is the gate the whole mission turns on: the
Python route is deliberately still alive precisely so this diff can exist.

Four properties, each bought with someone's mistake on this mission:

1. **Bytes, never text.** `subprocess` with `text=True` applies universal newlines
   and rewrites `\\r\\n` and lone `\\r` to `\\n`. Real transcripts carry carriage
   returns constantly, so a text-mode harness agrees where the routes differ.
2. **The clock is pinned** with `CH_NOW`. Age appears in list rows and panel
   titles, so any age-bearing diff is meaningless without it.
3. **Environment is set directly, never through a shell.** A shell mangled
   `COLUMNS="９６"` to ASCII before the binary saw it, and the probe measured the
   shell.
4. **It prints what it covered**, not only whether it passed. A gate reporting
   pass/fail hides its own scope, which is the property that lets it silently
   cover less than it claims — measured on this mission when a full disk shrank a
   corpus by 170 sessions under a clean verdict.
5. **Every mismatch is checked against the corpus moving, by running the
   *legacy* route twice and diffing it against itself.** Reproducing the mismatch
   is not enough: the pool is under active write, the two binaries run one after
   the other, and the file that moves most is this session's own transcript —
   which is the newest file, and therefore the first one a newest-first scan
   reads. That artefact is **systematic rather than random**, so it reproduces
   perfectly and a re-run control passes it straight through. Measured: it
   produced 2 apparent mismatches whose file *sets* were identical, 4,937 against
   4,937, differing only in the position of the transcript being appended to.

   Comparing legacy against itself removes the native route from the question
   entirely. If legacy cannot agree with itself, nothing measured in that window
   means anything.

**Scale changes what this instrument is, and the change is not only size.** Against
the real pool it reaches at least two branches a small pool cannot: the 256-file
batching path, which needs 256 survivors before a batch ever forms, and the
provider column, which only appears when the pool spans more than one provider. It
also acquires the instability above, which a fixed synthetic pool does not have. So
the two runs are complementary rather than one being a bigger version of the other
— and the synthetic one stays worth running because it is reproducible.

Usage:  ./route_differential.py NATIVE_BIN [--home DIR] [--real]
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

CH_NOW = "2026-08-28T12:00:00"

# Each case is the argv after the subcommand. Chosen to cross every axis the route
# has: output mode, format, metadata, filters, boolean grammar, and the failure
# modes that print rather than match.
CASES: list[list[str]] = [
    ["skill"],
    ["skill", "-l"],
    ["skill", "-ll"],
    ["skill", "--full"],
    ["skill", "-f", "raw"],
    ["."],
    [".", "-ll"],
    ["nonexistentneedlexyz"],
    ["nonexistentneedlexyz", "-ll"],
    ["skill", "-t"],
    ["skill", "--thinking"],
    ["skill", "-s"],
    ["skill AND toolkit"],
    ["skill OR nothingmatchesthis"],
    ["NOT skill"],
    ["skill", "-p", "claude"],
    ["skill", "-p", "codex"],
    ["skill", "-ma", "2020-01-01"],
    ["skill", "-ca", "2020-01-01"],
    ["skill", "-ma", "notadate"],
    ["skill", "-ca", "bogus-date"],
    ["skill", "-d", "/nonexistent-directory"],
    ["(unclosed"],
    ["skill AND"],
    ["[a-z", "-ll"],
    ["s=8:", "-ll"],
    ["\\N{LATIN SMALL LETTER A}", "-ll"],
]

WIDTHS = [60, 100]


def capture(command: list[str], environment: dict[str, str]) -> tuple[bytes, bytes, int]:
    """Run and capture raw bytes. Never `text=True`; see the module docstring."""
    completed = subprocess.run(command, capture_output=True, env=environment)
    return completed.stdout, completed.stderr, completed.returncode


def show(label: str, value: bytes) -> str:
    body = value.decode("utf-8", "replace")
    if len(body) > 400:
        body = body[:400] + f"… ({len(value)} bytes total)"
    return f"      {label}: {body!r}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("native")
    parser.add_argument("--home", default=None, help="pool root; defaults to the real $HOME")
    parser.add_argument("--legacy", default=".venv/bin/ch-legacy")
    arguments = parser.parse_args()

    native_bin = str(pathlib.Path(arguments.native).resolve())
    legacy_bin = str(pathlib.Path(arguments.legacy).resolve())
    home = arguments.home or os.environ["HOME"]

    compared = 0
    unstable = 0
    mismatches: list[str] = []
    for width in WIDTHS:
        for case in CASES:
            environment = {
                **os.environ,
                "HOME": home,
                "CH_NOW": CH_NOW,
                "COLUMNS": str(width),
                # Colour off: the coloured sink is `views-and-colour`'s and is not
                # wired yet. Saying so here stops a later reader reading a green
                # run as covering more than it does.
                "NO_COLOR": "1",
            }
            native = capture([native_bin, *case], environment)
            legacy = capture([legacy_bin, "search", *case], environment)
            compared += 1
            if native == legacy:
                continue
            # Ask whether the corpus moved, not whether the mismatch repeats.
            # A systematic artefact repeats perfectly; legacy disagreeing with
            # itself over the same window is the thing that proves the pool moved.
            if capture([legacy_bin, "search", *case], environment) != legacy:
                unstable += 1
                continue
            native_again = capture([native_bin, *case], environment)
            if native_again == legacy:
                unstable += 1
                continue
            native_out, native_err, native_code = native
            legacy_out, legacy_err, legacy_code = legacy
            report = [f"  width={width} argv={case}"]
            if native_code != legacy_code:
                report.append(f"      exit: legacy {legacy_code}, native {native_code}")
            if native_out != legacy_out:
                report.append(show("stdout legacy", legacy_out))
                report.append(show("stdout native", native_out))
            if native_err != legacy_err:
                report.append(show("stderr legacy", legacy_err))
                report.append(show("stderr native", native_err))
            mismatches.append("\n".join(report))

    print(f"pool: {home}")
    print(f"compared {compared} cases ({len(CASES)} shapes x {len(WIDTHS)} widths), colour off")
    print(f"mismatches: {len(mismatches)}   unstable (did not reproduce): {unstable}")
    for report in mismatches[:12]:
        print()
        print(report)
    if len(mismatches) > 12:
        print(f"\n… and {len(mismatches) - 12} more")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
