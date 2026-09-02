#!/usr/bin/env python3
"""Measure the "byte-invisible" economies, which are not all invisible.

`context-curator` lists four documented economies as reviewable only by reading
the diff, because they produce identical bytes and no gate costs them. Three of
the four leave a timing signature that an instrument can see:

  streaming          time to first byte against time to exit. If streaming is
                     lost the first byte arrives with the last.
  early close        exit time when the reader closes after one line. If the
                     scan does not stop, a closed pager costs a full scan.
  filter-before-probe a filter matching nothing should cost far less than an
                     unfiltered scan. If the probe runs first, it costs the same.

The fourth, lazy short-circuiting inside a probe, stays a reading job.

Measurement does not replace the structural review; it gives it a second and
independent witness, which is the pairing that has held up all day.

    economy_probe.py SUBJECT REFERENCE CORPUS_HOME
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
SUBJECT = REFERENCE = CORPUS = None


def _read_arguments() -> None:
    global SUBJECT, REFERENCE, CORPUS
    SUBJECT, REFERENCE, CORPUS = sys.argv[1], sys.argv[2], Path(sys.argv[3])
ENVIRONMENT = os.environ | {"HOME": str(CORPUS), "NO_COLOR": "1", "COLUMNS": "96"}
BROAD = ["search", ".", "-ll"]


def first_byte_and_total(binary: str, arguments: list[str]) -> tuple[float, float]:
    """Milliseconds to the first output byte, and to process exit."""
    start = time.perf_counter()
    process = subprocess.Popen(
        [binary, *arguments], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ENVIRONMENT
    )
    first = None
    assert process.stdout is not None
    while True:
        chunk = process.stdout.read(1)
        if chunk:
            first = (time.perf_counter() - start) * 1000
            break
        if process.poll() is not None:
            break
    process.stdout.read()
    process.wait()
    return (first if first is not None else float("nan"), (time.perf_counter() - start) * 1000)


def early_close(binary: str, arguments: list[str]) -> float:
    """Exit time when the reader closes the pipe after one line."""
    start = time.perf_counter()
    process = subprocess.Popen(
        [binary, *arguments], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ENVIRONMENT
    )
    assert process.stdout is not None
    process.stdout.readline()
    process.stdout.close()
    process.wait()
    return (time.perf_counter() - start) * 1000


def elapsed(binary: str, arguments: list[str]) -> float:
    start = time.perf_counter()
    subprocess.run([binary, *arguments], capture_output=True, check=False, env=ENVIRONMENT)
    return (time.perf_counter() - start) * 1000


def main() -> int:
    _read_arguments()
    routes = (("subject", SUBJECT), ("reference", REFERENCE))
    for _, binary in routes:
        elapsed(binary, BROAD)

    print("streaming — first byte against total, broad id-only scan")
    for label, binary in routes:
        first, total = first_byte_and_total(binary, BROAD)
        share = first / total if total else float("nan")
        print(f"  {label:10} first {first:8.1f}ms   total {total:8.1f}ms   first/total {share:5.2f}")

    print("\nearly close — reader closes after one line")
    for label, binary in routes:
        closed = early_close(binary, BROAD)
        full = elapsed(binary, BROAD)
        print(f"  {label:10} closed {closed:8.1f}ms   full {full:8.1f}ms   saved {1 - closed / full:5.0%}")

    print("\nfilter-before-probe — a dir filter matching nothing")
    filtered = ["search", "needle", "-ll", "-d", "/nonexistent-directory"]
    unfiltered = ["search", "needle", "-ll"]
    for label, binary in routes:
        with_filter = elapsed(binary, filtered)
        without = elapsed(binary, unfiltered)
        print(
            f"  {label:10} filtered {with_filter:8.1f}ms   unfiltered {without:8.1f}ms   "
            f"ratio {with_filter / without:5.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
