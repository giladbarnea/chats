"""The oracle guard, applied to a table oracle rather than to a fixture corpus.

`resolve_tool_visibility` is not exposed through PyO3 — nothing in the new native
surface is — so no in-process differential can compare the two implementations
directly. The available method is a table: Python's answers recorded once, the
Rust side compared against them later. `reviewer-profiler` built it, 7315 cases
from 1463 ordered spec lists, 696 of them carrying a specificity tie.

**A table oracle is only as good as the Python it was generated against, and it
was generated once.** If the oracle moves, the table silently describes a Python
that no longer exists — and unlike the fixture corpora, nothing was checking it.
This file is that check.

Two wrong ports were falsified against this table when it was built, and they are
the reason the tie cases exist:

* *Ties go to the earlier filter* — same specificity ranking, but on a tie the
  first matching short spec wins instead of the last. **558 of 7315 differ.**
  The natural mistake: "first match wins" is the intuitive reading of an
  allowlist, and the correct rule is the opposite.
* *Specificity ignored entirely* — the last short declaration wins regardless of
  how specific it is. **634 of 7315 differ.** What you get from reading "later
  wins" out of the tie rule and generalising it into the whole rule.

Both are mistakes a careful person writes. Do not prune the 696 tie cases as
repetitive: they are the only cases those two ports fail.

The Rust side of this comparison belongs to `session-core`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import oracle_provenance

from chats.tool_filter import parse_tool_spec, resolve_tool_visibility


FIXTURE_ROOT = Path(__file__).parent / "data" / "tool-visibility-oracle"
TABLE = json.loads((FIXTURE_ROOT / "table.json").read_text(encoding="utf-8"))
ORACLE = json.loads((FIXTURE_ROOT / "ORACLE.json").read_text(encoding="utf-8"))


def test_table_oracle_records_the_oracle_it_was_generated_against() -> None:
    """A table with no machine-checkable stamp cannot be traced to its source.

    ⚠ **Not a currency check any more**, since the Python search route it named was
    deleted on 2026-09-02. **The table's subject survives** — `resolve_tool_visibility`
    is still live Python, and `test_table_oracle_still_describes_the_python_product`
    below still runs it against every row. **That test is the currency check now**;
    this one only says which route the table came from.
    """
    oracle_provenance.assert_artifact_names_the_recorded_oracle(
        ORACLE["source_digest"], f"the tool-visibility table ({ORACLE['human_stamp']})"
    )


def test_table_oracle_still_describes_the_python_product() -> None:
    """Every recorded answer must still be the answer Python gives.

    The stamp above says the oracle has not moved; this says the table agrees
    with it. Both are needed — a stamp can be re-blessed by hand, and a table
    generated against the right revision can still have been generated wrongly.

    This does not make the table redundant. The parity comparison it exists for
    is Rust against these recorded values, which is a comparison this file
    cannot make: the Rust side is not reachable from here. All this proves is
    that the values are still the Python product's own.
    """
    tools = TABLE["tools"]
    id_map = TABLE["id_map"]
    default_short_max_chars = TABLE["default_short_max_chars"]

    divergences = []
    for case in TABLE["cases"]:
        filters = [parse_tool_spec(spec) for spec in case["specs"]]
        show, policy = resolve_tool_visibility(
            tools[case["tool"]],
            filters,
            id_map,
            default_short_max_chars=default_short_max_chars,
        )
        recorded = (case["show"], case["max_chars"], case["progressive"])
        actual = (
            show,
            policy.max_chars if policy is not None else None,
            policy.progressive if policy is not None else None,
        )
        if recorded != actual:
            divergences.append((case["specs"], case["tool"], recorded, actual))

    assert not divergences, (
        f"{len(divergences)} of {len(TABLE['cases'])} recorded answers no longer "
        f"match the Python product. First few: {divergences[:5]}."
    )


def test_table_oracle_still_contains_its_discriminating_cases() -> None:
    """The specificity ties must survive, since they are what the table is for.

    Everything else in the table passes against both falsified wrong ports. A
    trim that removed the ties would leave 6619 cases, a green suite, and no
    ability to fail.
    """
    ties = [
        case
        for case in TABLE["cases"]
        if sum(1 for spec in case["specs"] if "s=" in spec) > 1
    ]
    assert len(ties) >= 696, (
        f"Expected at least 696 cases carrying more than one short declaration, "
        f"which are the only ones the two falsified ports fail. Found {len(ties)}."
    )
