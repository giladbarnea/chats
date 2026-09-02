#!/usr/bin/env python3
"""Calibrate the pty harness before any width result it produces is quoted.

Byte-level calibration cannot grade width, because width is a property of the
subject's environment rather than of the captured bytes. This grades it against
a subject whose behaviour is known: a Python one-liner that asks the terminal
its own size. If the harness cannot move that number, it is not setting the
width and every width verdict it reports is vacuous.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pty_harness import run_at_width  # noqa: E402

REPORTER = [
    sys.executable,
    "-c",
    "import shutil,sys; sys.stdout.write(str(shutil.get_terminal_size().columns))",
]
ECHO = [sys.executable, "-c", "import os,sys; sys.stdout.write(os.environ.get('COLUMNS','<unset>'))"]


def reported_width(columns: int, environment: dict[str, str] | None = None) -> int:
    return int(run_at_width(REPORTER, columns=columns, environment=environment).strip())


def main() -> int:
    failures: list[str] = []

    # Null control first. A harness that is unstable would pass every sensitivity
    # probe below for the wrong reason.
    if reported_width(120) != reported_width(120):
        failures.append("unstable: same width reported differently across runs")

    # Sensitivity: the subject must actually see each width we ask for.
    for requested in (60, 100, 120, 200):
        seen = reported_width(requested)
        if seen != requested:
            failures.append(f"asked for {requested} columns, subject saw {seen}")

    # The trap that made a teammate's first width probe measure their shell:
    # an inherited COLUMNS must not reach the child and must not win over the pty.
    polluted = dict(os.environ) | {"COLUMNS": "999"}
    if (leaked := run_at_width(ECHO, columns=120, environment=polluted).strip()) != b"<unset>":
        failures.append(f"COLUMNS leaked into the child as {leaked!r}")
    if (seen := reported_width(120, polluted)) != 120:
        failures.append(f"inherited COLUMNS overrode the pty: subject saw {seen}")

    print("pty harness        " + ("CALIBRATED" if not failures else f"FAILED {len(failures)}"))
    for failure in failures:
        print(f"                   - {failure}")
    if not failures:
        print("                   - width is settable and observed at 60/100/120/200")
        print("                   - inherited COLUMNS neither leaks nor overrides")
    return 1 if failures else 0


if __name__ == "__main__":
    import os

    raise SystemExit(main())
