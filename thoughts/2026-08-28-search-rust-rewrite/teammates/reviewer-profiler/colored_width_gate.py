#!/usr/bin/env python3
"""Colored parity across terminal widths, under a real pty.

Usage: colored_width_gate.py NATIVE_CH PYTHON_CH FIXTURE_HOME

80 is included only to demonstrate why it must not be the gate: a
`COLUMNS`-only implementation and one that follows the terminal both produce 80
columns there, so a diff at 80 certifies the exact width where the defect hides.
The gate widths are the others.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pty_harness import observed_width, run_at_width  # noqa: E402

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
NATIVE = PYTHON = FIXTURE_HOME = None


def _read_arguments() -> None:
    global NATIVE, PYTHON, FIXTURE_HOME
    NATIVE, PYTHON, FIXTURE_HOME = sys.argv[1], sys.argv[2], Path(sys.argv[3])
GATE_WIDTHS = (60, 120, 200)
DEMONSTRATION_WIDTH = 80
CASE = ["search", "needle five", "--color", "always", "--no-paging", "--no-metadata"]

AGE_BUCKETS = rb"(?:169;174;180|135;140;146|107;112;118|86;91;97)"


def normalize(content: bytes) -> bytes:
    """Neutralize the wall-clock age bucket, which is not a width property."""
    return re.sub(rb"\x1b\[38;2;" + AGE_BUCKETS + rb"m", b"\x1b[38;2;{AGE}m", content)


def main() -> int:
    _read_arguments()
    home = Path(tempfile.mkdtemp()) / "home"
    shutil.copytree(FIXTURE_HOME, home)
    environment = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TZ": "Asia/Jerusalem",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
    }

    print(f"{'width':>6}  {'native':>8}  {'python':>8}  verdict")
    failures = 0
    for width in (DEMONSTRATION_WIDTH, *GATE_WIDTHS):
        native = run_at_width([NATIVE, *CASE], columns=width, environment=environment)
        python = run_at_width([PYTHON, *CASE], columns=width, environment=environment)
        identical = normalize(native) == normalize(python)
        label = "demo" if width == DEMONSTRATION_WIDTH else ("PASS" if identical else "FAIL")
        if width in GATE_WIDTHS and not identical:
            failures += 1
        print(
            f"{width:>6}  {observed_width(native):>8}  {observed_width(python):>8}  "
            f"{label}{'  (identical)' if identical else '  (differ)'}"
        )

    print()
    if failures:
        print(
            f"{failures}/{len(GATE_WIDTHS)} gate widths differ. Columns above are the widest\n"
            "visible line each route actually produced."
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
