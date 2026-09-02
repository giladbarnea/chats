#!/usr/bin/env python3
"""The piped half of the ambient sweep, which the pty half could not reach.

`ambient_gate.py` runs under a pty with `--color always`. Several ambient
inputs only take effect when output is *not* a terminal or colour is not
forced, so four of its rows read "no divergence" when they mean "not under
these conditions". This is the other condition: output on a pipe, colour left
at its default so the isatty cascade is live.

That cascade is the reason this half matters. `ConversationFlags` resolves
`color` from `sys.stdout.isatty()`, and `paging` then defaults to whatever
`color` resolved to. One input decides two visible behaviours, so a sweep that
forces colour cannot see either.

    ambient_gate_piped.py SUBJECT REFERENCE FIXTURE_HOME
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from width_probe_fixture import seed as seed_width_probe  # noqa: E402

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
SUBJECT = REFERENCE = FIXTURE = None


def _read_arguments() -> None:
    global SUBJECT, REFERENCE, FIXTURE
    SUBJECT, REFERENCE, FIXTURE = sys.argv[1], sys.argv[2], Path(sys.argv[3])
CASE = ["search", "needle five", "--no-metadata"]

BASE = {"PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "TZ": "Asia/Jerusalem", "COLUMNS": "80"}
UNSET = object()

INPUTS = {
    "COLORTERM":       ({"COLORTERM": "truecolor"}, {"COLORTERM": UNSET}),
    "NO_COLOR":        ({},                          {"NO_COLOR": "1"}),
    "FORCE_COLOR":     ({},                          {"FORCE_COLOR": "1"}),
    "TERM=dumb":       ({},                          {"TERM": "dumb"}),
    "TTY_COMPATIBLE":  ({},                          {"TTY_COMPATIBLE": "1"}),
    "TTY_INTERACTIVE": ({},                          {"TTY_INTERACTIVE": "1"}),
    "LINES":           ({"LINES": "40"},             {"LINES": "200"}),
    "TZ":              ({"TZ": "Asia/Jerusalem"},    {"TZ": "Pacific/Kiritimati"}),
    "UNICODE_VERSION": ({"UNICODE_VERSION": "latest"}, {"UNICODE_VERSION": "9.0.0"}),
}


def run_piped(binary: str, environment: dict[str, str]) -> bytes:
    return subprocess.run(
        [binary, *CASE], capture_output=True, check=False, env=environment
    ).stdout


def main() -> int:
    _read_arguments()
    home = Path(tempfile.mkdtemp()) / "home"
    shutil.copytree(FIXTURE, home)
    seed_width_probe(home)

    print(f"{'ambient input':17} {'subject':>9} {'reference':>10}  {'agree A':>8} {'agree B':>8}")
    gaps = []
    reverse_gaps = []
    for name, (setting_a, setting_b) in INPUTS.items():
        results = {}
        for label, overrides in (("A", setting_a), ("B", setting_b)):
            environment = BASE | {"HOME": str(home)}
            for key, value in overrides.items():
                if value is UNSET:
                    environment.pop(key, None)
                else:
                    environment[key] = value
            for role, binary in (("subject", SUBJECT), ("reference", REFERENCE)):
                results[(role, label)] = run_piped(binary, environment)
        subject_responds = results[("subject", "A")] != results[("subject", "B")]
        reference_responds = results[("reference", "A")] != results[("reference", "B")]
        agree_a = results[("subject", "A")] == results[("reference", "A")]
        agree_b = results[("subject", "B")] == results[("reference", "B")]
        if reference_responds and not subject_responds:
            gaps.append(name)
        # The reverse direction. A parameterization of "inputs the reference honours
        # that the subject ignores" cannot contain an input only the *subject*
        # honours — it falls outside by construction, however exhaustively swept.
        # That divergence has no failing comparison anywhere, because the oracle
        # does not vary along the axis at all, so nothing disagrees with it.
        if subject_responds and not reference_responds:
            reverse_gaps.append(name)
        print(
            f"{name:17} {'yes' if subject_responds else 'NO':>9} "
            f"{'yes' if reference_responds else 'no':>10}  "
            f"{'yes' if agree_a else 'NO':>8} {'yes' if agree_b else 'NO':>8}"
        )

    # The cascade itself: one input, two visible behaviours.
    print("\nisatty cascade (pipe vs pty is covered by the two sweeps together)")
    plain = BASE | {"HOME": str(home)}
    for role, binary in (("subject", SUBJECT), ("reference", REFERENCE)):
        piped = run_piped(binary, plain)
        coloured = b"\x1b[" in piped
        print(f"  {role:10} piped output carries colour: {'yes' if coloured else 'no'}  ({len(piped)} bytes)")

    print()
    if gaps:
        print(f"{len(gaps)} input(s) the reference honours and the subject ignores: {', '.join(gaps)}")
    else:
        print("no input is honoured by the reference and ignored by the subject")
    if reverse_gaps:
        print(
            f"{len(reverse_gaps)} input(s) the SUBJECT honours and the reference ignores: "
            f"{', '.join(reverse_gaps)}  <- no comparison anywhere would fail on these"
        )
    else:
        print("no input is honoured by the subject and ignored by the reference")
    return len(gaps) + len(reverse_gaps)


if __name__ == "__main__":
    raise SystemExit(main())
