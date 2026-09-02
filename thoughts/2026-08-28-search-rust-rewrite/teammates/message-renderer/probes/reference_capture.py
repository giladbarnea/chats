#!/usr/bin/env -S uv run
"""Capture the oracle's coloured panel bytes for one G4 case, escaped for reading.

The gate reports a byte difference; this prints what the reference actually emits,
which is the thing being reproduced. Imports the differential's own capture path
rather than re-deriving it, so the two cannot drift.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
VIEWS_PROBES = HERE.parents[2] / "views-and-colour" / "probes"
sys.path.insert(0, str(VIEWS_PROBES))

import pty_differential as differential  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="g4-default-matches")
    parser.add_argument("--columns", type=int, default=72)
    parser.add_argument("--tier", default="truecolor")
    parser.add_argument("--now", default=differential.DEFAULT_NOW)
    parser.add_argument("--raw", action="store_true", help="write bytes to stdout")
    options = parser.parse_args()

    case = next(
        item for item in differential.G4_COLOURED_CASES if item["id"] == options.case
    )
    home = differential.fixture_home()
    captured = differential.capture(
        str(Path.cwd() / ".venv" / "bin" / "ch-legacy"),
        case,
        options.columns,
        home,
        options.now,
        options.tier,
    )
    if options.raw:
        sys.stdout.buffer.write(captured)
        return
    for line in captured.split(b"\n"):
        print(line.decode("utf-8").replace("\x1b", "\\e"))


if __name__ == "__main__":
    main()
