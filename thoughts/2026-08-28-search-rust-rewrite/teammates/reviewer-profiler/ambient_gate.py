#!/usr/bin/env python3
"""Gate rows for every ambient input the Python route reads.

Width, the clock and COLORTERM were each found only after they had corrupted a
measurement. The enumeration in plan section 8a lists thirteen such inputs. This
builds a row per input and asks two separate questions, because they fail
differently:

  RESPONDS  - does the route's output change at all when the input changes?
              A route that ignores an input has no way to agree by accident.
  AGREES    - do the two routes produce the same output for the same setting?

An input where the reference responds and the subject does not is the width and
COLORTERM shape: a divergence on a supported environment.

    ambient_gate.py SUBJECT REFERENCE FIXTURE_HOME
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pty_harness import run_at_width  # noqa: E402
from width_probe_fixture import seed as seed_width_probe  # noqa: E402

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
SUBJECT = REFERENCE = FIXTURE = None


def _read_arguments() -> None:
    global SUBJECT, REFERENCE, FIXTURE
    SUBJECT, REFERENCE, FIXTURE = sys.argv[1], sys.argv[2], Path(sys.argv[3])
CASE = ["search", "needle five", "--color", "always", "--no-paging", "--no-metadata"]
PLAIN = ["search", "needle five", "--no-paging", "--no-metadata"]

BASE = {"PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "COLORTERM": "truecolor", "TZ": "Asia/Jerusalem"}

# Width is pinned at 80 for every row. It is the one width where the known width
# defect is invisible, which is wrong for a width gate and exactly right here:
# it removes width as a variable so the row measures the input it names.
GATE_COLUMNS = 80
UNSET = object()  # an override of UNSET removes the variable; {} would keep BASE's value

# name -> (arguments, setting A, setting B)
INPUTS = {
    "COLORTERM":       (CASE,  {"COLORTERM": "truecolor"}, {"COLORTERM": UNSET}),
    "NO_COLOR":        (CASE,  {},                          {"NO_COLOR": "1"}),
    "FORCE_COLOR":     (PLAIN, {},                          {"FORCE_COLOR": "1"}),
    "TERM=dumb":       (CASE,  {},                          {"TERM": "dumb"}),
    "TTY_COMPATIBLE":  (CASE,  {},                          {"TTY_COMPATIBLE": "0"}),
    "TTY_INTERACTIVE": (CASE,  {},                          {"TTY_INTERACTIVE": "0"}),
    "LINES":           (CASE,  {"LINES": "40"},             {"LINES": "200"}),
    "TZ":              (PLAIN, {"TZ": "Asia/Jerusalem"},    {"TZ": "Pacific/Kiritimati"}),
    "UNICODE_VERSION": (CASE,  {"UNICODE_VERSION": "latest"}, {"UNICODE_VERSION": "9.0.0"}),
}

AGE = rb"(?:169;174;180|135;140;146|107;112;118|86;91;97)"


def normalise(content: bytes) -> bytes:
    return re.sub(rb"\x1b\[38;2;" + AGE + rb"m", b"\x1b[38;2;{AGE}m", content)


def main() -> int:
    _read_arguments()
    home = Path(tempfile.mkdtemp()) / "home"
    shutil.copytree(FIXTURE, home)
    seed_width_probe(home)

    print(f"{'ambient input':17} {'subject':>9} {'reference':>10}  {'agree A':>8} {'agree B':>8}")
    gaps = []
    reverse_gaps = []
    for name, (arguments, setting_a, setting_b) in INPUTS.items():
        results = {}
        for label, overrides in (("A", setting_a), ("B", setting_b)):
            environment = BASE | {"HOME": str(home)}
            for key, value in overrides.items():
                if value is UNSET:
                    environment.pop(key, None)
                else:
                    environment[key] = value
            allow_dumb = environment.get("TERM") == "dumb"
            for role, binary in (("subject", SUBJECT), ("reference", REFERENCE)):
                results[(role, label)] = normalise(
                    run_at_width([binary, *arguments], columns=GATE_COLUMNS,
                                 environment=environment, allow_dumb=allow_dumb)
                )
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
