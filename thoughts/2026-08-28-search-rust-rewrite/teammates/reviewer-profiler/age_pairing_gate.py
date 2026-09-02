#!/usr/bin/env python3
"""Pin the age label-to-colour pairing, which every age normalization hides.

`humanize_age` and `age_style` carry unaligned thresholds. The label switches
unit at 1 minute, 1 hour, 1 day, 7 days, 30 days and 365 days; the colour
switches bucket at 1 day, 7 days and 30 days only. So from one day onward the
colour is exactly one bucket older than the label reads: `3d` is painted week,
`2w` is painted month, `5mo` is painted old.

That is a behaviour to preserve, not a bug to fix, and it is invisible to every
comparator we have — mine and `contract-owner`'s both fold the age colour away
to survive wall-clock drift. A port that drives label and colour from one table,
which is the first simplification any reviewer would suggest, changes the colour
of every coloured row with no gate firing.

The pairing is clock-independent even though the absolute bucket is not, so this
gate keeps working as the corpus ages. Usage:

    age_pairing_gate.py CH_BINARY FIXTURE_HOME
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pty_harness import run_at_width  # noqa: E402

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
BINARY = FIXTURE_HOME = None


def _read_arguments() -> None:
    global BINARY, FIXTURE_HOME
    BINARY, FIXTURE_HOME = sys.argv[1], Path(sys.argv[2])

# The corpus reaches two label units on its own, because every fixture mtime sits in
# one bucket. `CH_NOW` is the approved clock pin and both routes honour it, so the
# instant becomes a swept dimension rather than whatever today happens to be.
# `views-and-colour` found the same thinness from the other end: fixture mtimes
# cluster within 600 seconds, so most instants collapse every row into one bucket.
CLOCK_INSTANTS = [
    "2026-08-20T10:00:30",  # seconds after  -> now
    "2026-08-20T10:40:00",  # minutes after  -> Nm
    "2026-08-20T15:00:00",  # hours after    -> Nh
    "2026-08-23T10:00:00",  # days after     -> Nd
    "2026-09-03T10:00:00",  # weeks after    -> Nw
    "2026-10-20T10:00:00",  # months after   -> Nmo
    "2028-08-20T10:00:00",  # years after    -> Ny
]

NOW, WEEK, MONTH, OLD = "169;174;180", "135;140;146", "107;112;118", "86;91;97"

# label unit -> the colour today's implementation actually paints it.
EXPECTED_COLOUR = {
    "now": NOW,
    "m": NOW,
    "h": NOW,
    "d": WEEK,
    "w": MONTH,
    "mo": OLD,
    "y": OLD,
}
BUCKET_NAME = {NOW: "now", WEEK: "week", MONTH: "month", OLD: "old"}

AGE_TOKEN = re.compile(
    rb"\x1b\[38;2;(169;174;180|135;140;146|107;112;118|86;91;97)m"
    rb"(now|\d+mo|\d+[smhdwy])\x1b\[0m"
)


def unit_of(label: str) -> str:
    if label == "now":
        return "now"
    return label.lstrip("0123456789")


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
    observed = []
    for instant in CLOCK_INSTANTS:
        output = run_at_width(
            [BINARY, "search", ".", "-l", "--color", "always", "--no-paging"],
            columns=100,
            environment=environment | {"CH_NOW": instant},
        )
        observed.extend(AGE_TOKEN.findall(output))
    if not observed:
        print("FAILED  no age tokens found — the gate would pass vacuously")
        return 1

    # Sweeping the clock only widens coverage if the subject honours the pin. A route
    # that ignores CH_NOW returns the same labels for every instant, and the gate then
    # checks two pairings while reporting seven units' worth of confidence.
    units_seen = {unit_of(label.decode()) for _colour, label in observed}
    if len(units_seen) < 5:
        print(
            f"FAILED  only {len(units_seen)} label unit(s) across {len(CLOCK_INSTANTS)} "
            f"CH_NOW instants: {sorted(units_seen)}\n"
            "        The subject is not honouring the clock pin, so this gate's widened\n"
            "        coverage is fictional. Fix the pin before trusting a PASS here."
        )
        return 1

    violations = []
    for colour, label in observed:
        colour, label = colour.decode(), label.decode()
        expected = EXPECTED_COLOUR[unit_of(label)]
        if colour != expected:
            violations.append(
                f"{label!r} painted {BUCKET_NAME.get(colour, colour)}, "
                f"expected {BUCKET_NAME[expected]}"
            )

    pairs = sorted({(label.decode(), BUCKET_NAME.get(c.decode(), "?")) for c, label in observed})
    print(f"{len(observed)} age tokens, {len(pairs)} distinct pairings:")
    for label, bucket in pairs:
        print(f"   {label:>6} -> {bucket}")
    print()
    if violations:
        print(f"FAILED  {len(violations)} pairing violations")
        for violation in violations[:10]:
            print(f"   {violation}")
        return 1
    print("PASS    label-to-colour pairing matches the recorded behaviour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
