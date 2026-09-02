"""The durable successors to the three differentials that die at deletion.

Three instruments in `test_search_command_contract.py` compare `ch search`
against `ch-legacy search` with nothing stored. The day the Python search
authority is deleted they stop being runnable — not broken, over. Their expected
answers exist only as "whatever Python said a moment ago".

This file holds Python's side, recorded once from `ch-legacy` explicitly rather
than from `ch`. Today those are the same bytes because `ch` execs its sibling,
but a record has to name the oracle it came from, not the route that reaches it.

**These do not replace the live differentials while Python is alive.** A live
comparison is the proof that the cutover preserved behaviour; a record is the
proof that survives it. Both run until the deletion slice, which removes the
live three and leaves these.

Re-posing test, applied: *what answer does the re-posed question give if the new
subject is wrong?* These compare exit status and bytes, so a wrong native route
produces different bytes and fails. Sound — the failure mode to avoid is an
instrument that asks whether native *responds* rather than whether it responds
*correctly*, and none of these does.

But see `test_frozen_pattern_set_can_still_discriminate`: the pattern set's
coverage is much narrower than its case count suggests, and that is recorded
rather than hidden.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import oracle_provenance
import test_search_command_contract as contract


FIXTURE_ROOT = Path(__file__).parent / "data" / "search-frozen-differentials"
FROZEN = json.loads((FIXTURE_ROOT / "frozen.json").read_text(encoding="utf-8"))
ORACLE = json.loads((FIXTURE_ROOT / "ORACLE.json").read_text(encoding="utf-8"))


def test_frozen_records_name_the_oracle_they_came_from() -> None:
    """A record with no machine-checkable stamp cannot be traced to its source.

    ⚠ **Not a currency check any more.** It compared this stamp against the live
    Python route until that route was deleted on 2026-09-02. **Re-freezing is no
    longer possible and no longer the remedy** — `work/freeze_differentials.py`
    has nothing to run.
    """
    oracle_provenance.assert_artifact_names_the_recorded_oracle(
        ORACLE["source_digest"], "the frozen differentials"
    )


@pytest.mark.parametrize("row", FROZEN["patterns"], ids=lambda row: row["id"])
def test_pattern_selects_the_frozen_sessions(
    checkout_built_ch: Path,
    corpus_homes: dict[str, Path],
    row: dict,
) -> None:
    """Each pattern must still select exactly the sessions Python selected."""
    home = corpus_homes[contract.CORPORA[0].name]
    completed = contract._run_search(checkout_built_ch, row, home)
    actual = contract._normalize(completed.stdout, home).decode("utf-8", "surrogateescape")

    assert completed.returncode == row["exit_status"], (
        f"Expected exit {row['exit_status']} for {row['id']} "
        f"({row['arguments'][0]!r}). Got {completed.returncode}."
    )
    assert actual == row["stdout"], (
        f"Expected the frozen session selection for {row['id']} "
        f"({row['arguments'][0]!r}). A validity disagreement flips a pattern "
        "between regex and literal with no error on either side, and a different "
        "session set is its only visible trace."
    )


@pytest.mark.parametrize("row", FROZEN["terminal"], ids=lambda row: row["id"])
def test_terminal_rendering_matches_the_frozen_bytes(
    checkout_built_ch: Path,
    corpus_homes: dict[str, Path],
    row: dict,
) -> None:
    """Colored output on a real terminal must still render the frozen bytes."""
    home = corpus_homes[contract.CORPORA[0].name]
    status, output = contract._run_search_on_terminal(
        checkout_built_ch, row["arguments"], home, columns=row["columns"]
    )
    actual = contract._normalize(output, home).decode("utf-8", "surrogateescape")

    assert status == row["exit_status"], (
        f"Expected exit {row['exit_status']} for {row['id']}. Got {status}."
    )
    assert actual == row["output"], (
        f"Expected the frozen terminal rendering for {row['id']} at "
        f"{row['columns']} columns."
    )


def test_frozen_pattern_set_can_still_discriminate() -> None:
    """Record how much the pattern set actually distinguishes, and refuse decay.

    **The case count overstates the coverage and that is worth knowing.** Of 78
    frozen pattern rows, 45 record empty output and the whole set collapses onto
    18 distinct answers, because the generated patterns mostly match everything
    or nothing against this corpus. The set still discriminates in both
    directions — an under-matching route fails the non-empty rows, an
    over-matching route fails the empty ones — but "78 cases" is not 78
    independent assertions.

    The known improvement is `query_pattern_corpus.adversarial_haystacks`, which
    biases fixture text toward what each pattern could touch. Not funded at the
    time of writing; recorded so the choice stays visible.

    This asserts the current discriminating power as a floor, so a future change
    that flattens the set further fails here rather than silently.
    """
    rows = FROZEN["patterns"]
    non_empty = [row for row in rows if row["stdout"].strip()]
    distinct = {(row["exit_status"], row["stdout"]) for row in rows}

    assert len(non_empty) >= 33, (
        f"Only {len(non_empty)} of {len(rows)} pattern rows record any output. "
        "A route that found nothing for everything would pass the rest."
    )
    assert len(distinct) >= 18, (
        f"The pattern set collapses onto {len(distinct)} distinct answers, down "
        "from 18. It distinguishes less than it did."
    )
