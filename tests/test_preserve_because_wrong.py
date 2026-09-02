"""Every `preserve-because-wrong` item, as a prohibition rather than a note.

**These are behaviours that are wrong and must stay wrong.** A native implementation that
gets one of them *better* passes every other gate on this mission, because the output
looks correct and no reviewer flags an improvement.

**The list recorded them; nothing asserted them.** A gap and a prohibition look identical
in a passing suite and behave completely differently a month later, when someone reads a
wrong-looking behaviour as an unfinished port and helpfully corrects it. **The only
difference is whether a gate fails when they do.**

**The bytes are frozen, not live.** `tests/data/preserve-because-wrong/legacy-baseline.json`
was captured while `ch-legacy` existed, because the deletion slice is downstream and it
could not be taken afterwards. `CH_NOW` and `TZ` are pinned in it and the file mtimes are
recorded, so item 5's age tokens do not rot overnight.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "data" / "preserve-because-wrong"
BASELINE = FIXTURES / "legacy-baseline.json"


def _load() -> dict:
    assert BASELINE.is_file(), (
        f"The frozen baseline is missing at {BASELINE}. **It cannot be regenerated once "
        "`ch-legacy` is deleted**, which is why it was captured before the cutover."
    )
    return json.loads(BASELINE.read_text())


RECORDED = _load()
CASES = RECORDED["cases"]


@pytest.fixture(scope="module", autouse=True)
def applied_mtimes() -> None:
    """Item 5's ages are measured from file mtimes, so the recording owns them too."""
    for name, pool in RECORDED["pools"].items():
        home = FIXTURES / name / "home"
        for relative, when in pool["mtimes"].items():
            path = home / relative
            assert path.is_file(), f"{path} is missing; the committed pool has moved."
            os.utime(path, (when, when))


def _run(executable: Path, case: dict) -> subprocess.CompletedProcess[bytes]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "COLUMNS", "NO_COLOR", "COLORTERM", "FORCE_COLOR", "CLICOLOR",
            "CLICOLOR_FORCE", "TTY_COMPATIBLE",
        }
    }
    environment.update({
        "HOME": str(FIXTURES / case["pool"] / "home"),
        "COLUMNS": str(case["columns"]),
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "TZ": RECORDED["tz"],
        "CH_NOW": RECORDED["ch_now"],
    })
    return subprocess.run(
        [str(executable), "search", *case["arguments"]],
        env=environment, capture_output=True, check=False,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_a_wrong_behaviour_is_reproduced_exactly(checkout_built_ch: Path, case: dict) -> None:
    result = _run(checkout_built_ch, case)
    assert result.returncode == case["exit_status"], (
        f"{case['id']}: exit {result.returncode} against the recorded {case['exit_status']}."
    )
    assert result.stdout == case["stdout"].encode("latin-1"), (
        f"{case['id']}: stdout differs from `ch-legacy`'s recorded bytes.\n"
        f"  legacy: {case['stdout'].encode('latin-1')[:220]!r}\n"
        f"  native: {result.stdout[:220]!r}\n"
        "**This behaviour is wrong on purpose.** If the change that broke this looks "
        "like a correction, that is the failure mode this gate exists for — read "
        "`preserve-because-wrong.md` before repairing anything."
    )
    assert result.stderr == case["stderr"].encode("latin-1"), (
        f"{case['id']}: stderr differs from `ch-legacy`'s recorded bytes.\n"
        f"  legacy: {case['stderr'].encode('latin-1')[:220]!r}\n"
        f"  native: {result.stderr[:220]!r}"
    )


def test_the_recording_still_carries_the_wrong_answers() -> None:
    """Reach, not just agreement.

    **A recording that stopped containing the wrong behaviour would pass a route that had
    fixed it.** Each check below names the evidence the item is about, so a corpus that
    drifted away from its own subject fails here rather than going quietly green.
    """
    # **Bytes, not text.** The recording stores the exact bytes through latin-1, so a
    # UTF-8 needle like `…` compared against the decoded string never matches — it looks
    # like the corpus lost the behaviour when it has not. Search the bytes.
    by_item: dict[str, bytes] = {}
    for case in CASES:
        item = case["id"].split()[0]
        recorded = (case["stdout"] + case["stderr"]).encode("latin-1")
        by_item[item] = by_item.get(item, b"") + recorded

    assert b"~X/" in by_item["1"], (
        "Item 1's recording no longer shows a mangled sibling path. `collapse_home` "
        "matches a string prefix rather than a path boundary, and `~X/` is that."
    )
    assert "…".encode() in by_item["3"], (
        "Item 3's recording contains no ellipsis, so nothing was elided and the "
        "code-point counter was never exercised."
    )
    assert b"..." in by_item["4"] or "…".encode() in by_item["4"], (
        "Item 4's recording shows no truncation, so NFD never crossed the limit."
    )
    assert b"12mo" in by_item["5"] and b"1y" in by_item["5"], (
        "Item 5's recording no longer spans the 360/365-day boundary, where a 30-day "
        "month and a 365-day year disagree. Both tokens must appear."
    )
    assert by_item["7"].count(b'"2026-10-25 01:30"') >= 2, (
        "Item 7's recording no longer shows two instants an hour apart rendering the "
        "same naive local time. That collapse is the whole item."
    )
    assert b"with the current filters" in by_item["11"] and b"Invalid date format" in by_item["11"], (
        "Item 11's recording no longer shows both readings of an empty string — absent "
        "to the no-results wording, present and invalid to the date filter."
    )
