#!/usr/bin/env python3
"""Measure the colour-downgrade divergence surface, so it can be sized.

Rich picks a colour system from the terminal's declared capability. The native
route emits hard-coded truecolor. This measures where that actually diverges on
supported environments, and how many distinct colours a mapping would have to
cover, rather than leaving either to estimate.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pty_harness import run_at_width

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
NATIVE = PYTHON = FIXTURE = None


def _read_arguments() -> None:
    global NATIVE, PYTHON, FIXTURE
    NATIVE, PYTHON, FIXTURE = sys.argv[1], sys.argv[2], Path(sys.argv[3])
CASE = ["search", "needle five", "--color", "always", "--no-paging", "--no-metadata"]

ENVIRONMENTS = {
    "truecolor":     {"TERM": "xterm-256color", "COLORTERM": "truecolor"},
    "256 colour":    {"TERM": "xterm-256color"},
    "16 colour":     {"TERM": "xterm-16color"},
    "8 colour":      {"TERM": "xterm"},
    "dumb terminal": {"TERM": "dumb"},
    "NO_COLOR set":  {"TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "1"},
}

TRUECOLOR = re.compile(rb"\x1b\[[0-9;]*?38;2;(\d+;\d+;\d+)")
PALETTE = re.compile(rb"\x1b\[[0-9;]*?38;5;(\d+)")


def profile(output: bytes) -> str:
    truecolor = set(TRUECOLOR.findall(output))
    palette = set(PALETTE.findall(output))
    if not truecolor and not palette:
        return "no colour"
    parts = []
    if truecolor:
        parts.append(f"{len(truecolor)} truecolor")
    if palette:
        parts.append(f"{len(palette)} palette")
    return " + ".join(parts)


def main() -> int:
    _read_arguments()
    home = Path(tempfile.mkdtemp()) / "home"
    shutil.copytree(FIXTURE, home)
    base = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TZ": "Asia/Jerusalem", "COLUMNS": "80"}

    print(f"{'environment':16} {'native':22} {'python':22} verdict")
    native_palettes = set()
    for label, overrides in ENVIRONMENTS.items():
        environment = base | overrides
        kwargs = {"columns": 80, "environment": environment, "allow_dumb": True}
        native = run_at_width([NATIVE, *CASE], **kwargs)
        python = run_at_width([PYTHON, *CASE], **kwargs)
        native_palettes |= set(TRUECOLOR.findall(native))
        verdict = "identical" if native == python else "DIVERGES"
        print(f"{label:16} {profile(native):22} {profile(python):22} {verdict}")

    print()
    print(f"distinct truecolor values the native route emits: {len(native_palettes)}")
    print("that set is the size of any downgrade mapping it would need.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
