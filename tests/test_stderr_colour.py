"""The three stderr consoles, against bytes frozen from `ch-legacy` while it lived.

**`--color` reaches none of these consoles.** `cli.py` hands the choice to
`init_module_console`, which builds the *stdout* console; `print_error`, `print_warning`
and `print_hint` each build a bare `Console(stderr=True)`, so their colour follows
stderr's own tty-ness — `ch search nomatch --color never 2>/dev/tty` is coloured.
**Preserved, not repaired.** Preserve-because-wrong item 10.

**Why a pty on stderr and a pipe on stdout.** Every coloured gate on this mission puts
its pty on *stdout*, so this whole surface had never been measured — and when it finally
was, all eight shapes diverged. **A held parameter in the harness hid an entire surface
rather than a single case.**

**The baseline is frozen, not live.** `tests/data/stderr-colour/legacy-stderr-baseline.json`
holds 240 recorded answers across six shapes, four `--color` settings, five terminal
tiers and two widths — captured while `ch-legacy` still existed, because the deletion
slice is downstream and this could not be recorded afterwards.
"""

from __future__ import annotations

import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import termios
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE = PROJECT_ROOT / "tests" / "data" / "stderr-colour" / "legacy-stderr-baseline.json"
POOL = PROJECT_ROOT / "tests" / "data" / "stderr-colour" / "home"


def _load() -> dict:
    assert BASELINE.is_file(), (
        f"The frozen stderr baseline is missing at {BASELINE}. **It cannot be "
        "regenerated once `ch-legacy` is deleted** — that is why it was captured before "
        "the cutover rather than after."
    )
    return json.loads(BASELINE.read_text())


BASELINE_CASES = _load()["cases"]


def _run(executable: Path, case: dict) -> tuple[bytes, int]:
    """Run with **stderr** on a pty and stdout on a pipe, as the recording did."""
    primary, secondary = pty.openpty()
    fcntl.ioctl(
        secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 40, case["columns"], 0, 0)
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "COLUMNS", "NO_COLOR", "COLORTERM", "FORCE_COLOR", "CLICOLOR",
            "CLICOLOR_FORCE", "TTY_COMPATIBLE",
        }
    }
    environment["HOME"] = str(POOL)
    environment["COLUMNS"] = str(case["columns"])
    environment["TZ"] = "Asia/Jerusalem"
    environment.update(case["environment"])
    process = subprocess.Popen(
        [str(executable), "search", *case["arguments"]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=secondary,
        env=environment,
        close_fds=True,
    )
    os.close(secondary)
    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], 60.0)
        if not ready:
            break
        try:
            data = os.read(primary, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    os.close(primary)
    return b"".join(chunks), process.wait()


#: Shapes whose difference is already ruled and pinned elsewhere, so a byte compare here
#: would re-litigate a settled decision.
#:
#: **`warning-posix-class` is CPython's `warnings` decoration.** Reproducing it means
#: emitting a path to `search_query.py:96` and echoing a line of Python the cutover
#: deletes — the fabricated-traceback pattern this project already removed once. Ruled
#: against reproduction; `test_deliberate_divergences.py` pins the shape of the
#: difference. Here it is pinned again in the *coloured* form, because a decoration that
#: moves the fold points cannot be compared byte for byte through a wrap.
RULED_DIVERGENCES = ("warning-posix-class",)
SGR = __import__("re").compile(rb"\x1b\[[0-9;]*m")


def _shape(case: dict) -> str:
    return case["id"].split("/", 1)[0]


@pytest.mark.parametrize(
    "case", [c for c in BASELINE_CASES if _shape(c) in RULED_DIVERGENCES],
    ids=lambda case: case["id"],
)
def test_a_ruled_divergence_differs_only_by_the_warning_decoration(
    checkout_built_ch: Path, case: dict
) -> None:
    stderr, _ = _run(checkout_built_ch, case)
    expected = case["stderr"].encode("latin-1")
    ours = SGR.sub(b"", stderr).replace(b"\r\n", b"").replace(b"\n", b"")
    theirs = SGR.sub(b"", expected).replace(b"\r\n", b"").replace(b"\n", b"")
    assert b"FutureWarning: Possible nested set at position 1" in ours, (
        f"{case['id']}: the warning text itself is gone. **Only its decoration is "
        f"forgiven.** Got {stderr[:200]!r}"
    )
    assert b"search_query.py:96:" in theirs and b"re.compile(pattern, flags)" in theirs, (
        f"{case['id']}: the recorded legacy bytes no longer carry the decoration this "
        "allowance exists for, so the allowance is allowing nothing."
    )
    assert b"search_query.py:96:" not in ours, (
        f"{case['id']}: the native route has started emitting a path to a Python source "
        "file the cutover deletes. **That is the fabricated-traceback pattern this "
        "project removed once**, and it is ruled against."
    )


@pytest.mark.parametrize(
    "case", [c for c in BASELINE_CASES if _shape(c) not in RULED_DIVERGENCES],
    ids=lambda case: case["id"],
)
def test_stderr_reproduces_the_frozen_legacy_bytes(checkout_built_ch: Path, case: dict) -> None:
    stderr, status = _run(checkout_built_ch, case)
    expected = case["stderr"].encode("latin-1")
    assert status == case["exit_status"], (
        f"{case['id']} exits {status} where `ch-legacy` exited {case['exit_status']}."
    )
    assert stderr == expected, (
        f"{case['id']} differs from the frozen `ch-legacy` bytes.\n"
        f"  legacy: {expected[:200]!r}\n"
        f"  native: {stderr[:200]!r}\n"
        "**The colour choice must not reach a stderr console.** These three follow "
        "stderr's tty-ness alone, `--color never` included, and a route that resolves "
        "the choice once and applies it everywhere is *more correct* and diverges on "
        "every no-results search run in a terminal."
    )


def test_the_baseline_actually_records_colour() -> None:
    """A baseline with no escapes in it would pass a route that emits none.

    **This is the assertion that keeps the 240 honest.** The whole point of the capture
    is the colour; a recording taken through a pipe by mistake would look like a corpus
    and prove the opposite of what it claims.
    """
    coloured = [case["id"] for case in BASELINE_CASES if "\x1b[" in case["stderr"]]
    assert len(coloured) >= 100, (
        f"Only {len(coloured)} of {len(BASELINE_CASES)} recorded cases carry an escape "
        "sequence. The capture was taken without a tty on stderr and records the wrong "
        "behaviour."
    )
    tiers = {case["id"].rsplit("/", 2)[1] for case in BASELINE_CASES}
    assert {"truecolor", "eight-bit", "standard", "no-colour", "dumb"} <= tiers, (
        f"The capture is missing terminal tiers: {sorted(tiers)}. A theme colour "
        "downgrades differently at each, and `print_hint`'s grey is an RGB triple where "
        "`print_error`'s red is a palette index that never downgrades."
    )
