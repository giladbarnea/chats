"""The frozen successors to three gates that ran both routes live.

**Why these exist.** `test_named_defect_patterns_select_the_same_sessions`,
`test_generated_patterns_select_the_same_sessions` and
`test_columns_sweep_reproduces_legacy` each ran `ch` and `ch-legacy` and asserted
they agreed. After the Python search authority is deleted there is no `ch-legacy`,
so all three would assert **nothing** while continuing to pass. Freezing them is
what stops them lapsing into decoration.

**The recording is `g5-runner`'s and the assertions are this seat's**, deliberately
— *"the runner wrote the gate he then verified"* is the one sentence that would
undo that separation. Same split as the performance ceilings.

**The degradation is stated in the recording itself**, as a `degradation` field a
reader meets before the data, and is not restated here. Read it. Its last sentence
is the true shape of every frozen successor built today:

    it can no longer detect that this recording was itself wrong, because the
    route that would have said so is gone.

**The harness is imported, never copied.** Every case identifier, pattern, width
and shape comes from the live modules that defined them, so a successor cannot
grade the port against a *drifted* definition of the case while both sides pass.
A second, hand-copied definition of one helper cost 21 errors on the morning of
2026-09-01, one file over.

**All three streams are compared** — stdout, stderr and the exit code — because
two of these gates assert on stderr, and a stdout-only comparison silently drops
half of what was recorded.
"""

from __future__ import annotations

import base64
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

import query_pattern_corpus

# **Imported, never restated.** `tests/deliberate_divergences.py` is the single
# authority for the cases no suite may assert byte-parity on, and for the shape of
# each difference. A second copy of either is the defect that module exists to
# prevent — the launcher guard was fixed in one of two files that held it, and 21
# errors followed.
from deliberate_divergences import (
    SELECTION_WARNING_DIVERGENCES,
    WARNING_PREFIX,
    WARNING_SOURCE_ECHO,
)
from test_search_columns_sweep import COLUMNS_VALUES, SHAPES, _run
from test_search_command_contract import (
    GENERATED_PATTERN_COUNT,
    GENERATED_PATTERN_SEED,
    GENERATED_PATTERN_WIDTHS,
    _normalize,
    _run_search,
)

# The two homes are module-level fixtures rather than conftest ones, so they are
# imported here to register them. **Imported for the same reason as everything
# else in this file**: `contract_home` and `sweep_home` each pick a specific
# corpus for a specific reason — an empty pool makes the no-results shape print
# nothing on both sides, which is a comparison that cannot fail — and a local
# redefinition would grade the port against a different pool than the recording
# was taken on.
from test_search_columns_sweep import sweep_home  # noqa: F401
from test_search_command_contract import contract_home  # noqa: F401

BASELINE = (
    Path(__file__).parent / "data" / "legacy-selection-baseline" / "legacy-selection-baseline.json"
)


def _baseline() -> dict:
    return json.loads(BASELINE.read_text())


def _recorded(group: str) -> dict[str, dict]:
    """One group's rows, with the stored streams decoded back to bytes."""
    rows = _baseline()["groups"][group]
    return {
        key: {
            **row,
            "stdout": base64.b64decode(row["stdout"]),
            "stderr": base64.b64decode(row["stderr"]),
        }
        for key, row in rows.items()
    }


def _compare(actual, expected: dict, home: Path, what: str) -> None:
    """All three streams, in one place, so no caller can compare half of them.

    **Both sides go through `_normalize`, because the recording stores normalised
    bytes.** Paths, the launcher directory, wall-clock age and the
    `search_query.py` location are replaced with placeholders at capture time —
    `posix_class_future_warning`'s stderr is stored as
    `{SEARCH_QUERY_SOURCE}:96: FutureWarning: …`. Comparing raw output against it
    fails on a byte-perfect route.

    Normalising the recorded side too is a no-op — it holds no home path to
    replace — and it is done anyway so the two sides are visibly treated alike.
    **The first version normalised neither and failed on the one row that carries
    a placeholder; the fault predates the re-recording, and the previous recording
    in git carries the identical bytes.**
    """
    assert actual.returncode == expected["returncode"], (
        f"{what}: exit {actual.returncode} where `ch-legacy` recorded "
        f"{expected['returncode']}."
    )
    for stream in ("stdout", "stderr"):
        got = _normalize(getattr(actual, stream), home)
        want = _normalize(expected[stream], home)
        assert got == want, (
            f"{what}: {stream} differs from the recording.\n"
            f"  recorded: {want[:400]!r}\n  native:   {got[:400]!r}"
        )


def _assert_only_the_missing_warning_decoration(
    actual, expected: dict, home: Path, name: str
) -> None:
    """A ruled divergence is exempt from byte-parity here — and must still be a divergence.

    The frozen successor of `test_a_warning_divergence_is_only_the_missing_decoration`,
    which asserts this bound against the live route and dies with it. **Not a skip.**
    Stdout and the exit status still have to reproduce the recording, the difference still
    has to be exactly CPython's `warnings` decoration, and a row that stops diverging fails
    below as an inert allowance.

    **Both directions run off the authority's membership, so neither can go quiet.**
    Removing the name from `deliberate_divergences.SELECTION_WARNING_DIVERGENCES` puts this
    row back on byte-parity by itself; a name that stops diverging fails here.
    """
    assert actual.returncode == expected["returncode"], (
        f"defect pattern {name}: exit {actual.returncode} where `ch-legacy` recorded "
        f"{expected['returncode']}. The ruled divergence is CPython's warning decoration "
        "on stderr and nothing else."
    )
    assert _normalize(actual.stdout, home) == _normalize(expected["stdout"], home), (
        f"defect pattern {name}: stdout differs from the recording. The ruled divergence "
        "is CPython's warning decoration on stderr and nothing else."
    )
    native = _normalize(actual.stderr, home)
    recorded = _normalize(expected["stderr"], home)
    assert native != recorded, (
        f"{name} is listed in `SELECTION_WARNING_DIVERGENCES` but now reproduces the "
        "recording exactly. **An exempt case that has stopped diverging is not a pass** — "
        "drop it from `tests/deliberate_divergences.py` and this gate asserts byte-parity "
        "on it again on its own."
    )
    assert recorded == WARNING_PREFIX + native + WARNING_SOURCE_ECHO, (
        f"{name}'s difference is no longer exactly CPython's warning decoration.\n"
        f"  recorded: {recorded!r}\n  native:   {native!r}\n"
        "Reproducing the decoration is ruled against — it means emitting a path to a "
        "`search_query.py` the cutover deletes and echoing a line of Python that will not "
        "exist. The warning **text**, its stream and its ordering are not covered by that "
        "ruling, and this says one of them has moved."
    )


# ── The three frozen gates ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name", sorted(query_pattern_corpus.DEFECT_PATTERNS), ids=lambda name: name
)
def test_named_defect_patterns_match_the_recording(
    checkout_built_ch: Path, contract_home: Path, name: str
) -> None:
    """Patterns behind known defect classes still select what Python selected.

    Held by name rather than by seed, exactly as the live gate was: these came
    from enumerating Unicode and from reading engines, not from generation, so a
    seed change must not be able to drop them.

    One row is a **ruled** divergence and defers to the shared authority rather
    than asserting byte-parity. See `_assert_only_the_missing_warning_decoration`.
    """
    recorded = _recorded("defect-patterns")
    assert name in recorded, (
        f"{name!r} is in DEFECT_PATTERNS but not in the recording. The corpus grew "
        "after the recording was taken and the route that could answer for the new "
        "case is gone; re-recording is impossible. Do not skip it — decide."
    )
    case = {
        "id": name,
        "arguments": [query_pattern_corpus.DEFECT_PATTERNS[name], "-ll"],
        "columns": 96,
        "color": False,
    }
    actual = _run_search(checkout_built_ch, case, contract_home)
    if name in SELECTION_WARNING_DIVERGENCES:
        _assert_only_the_missing_warning_decoration(
            actual, recorded[name], contract_home, name
        )
        return
    _compare(actual, recorded[name], contract_home, f"defect pattern {name}")


def test_generated_patterns_match_the_recording(
    checkout_built_ch: Path, contract_home: Path
) -> None:
    """Generated patterns still select what Python selected, at varying widths.

    Reported as one collected list rather than one case per pattern, as the live
    gate was, because a validity disagreement is almost never singular: the useful
    output is the whole disagreeing set.

    **The width is regenerated from the same constants, not read from the
    recording.** Reading it back would make the gate agree with itself about which
    width each pattern was taken at, which is the one thing it must not do.

    ⚠ **This gate compares `returncode` and `stdout` only**, faithfully reproducing
    the live gate it replaced. Strengthening it to compare stderr is a genuine
    improvement and **it turns rows red for reasons that are already known**, so
    they are named here rather than rediscovered. Measured 2026-09-02 at oracle
    `sha256:dd6ab701…`, rust tree `7b3267a6a22e1f7c`, with both routes alive:
    **7 of 60 rows differ on stderr.**

    - `generated-17` and `generated-58` carry the **ruled** warning divergence —
      the same one `deliberate_divergences.SELECTION_WARNING_DIVERGENCES` names for
      `posix_class_future_warning`, arrived at by generation rather than by name.
    - `generated-51` (`[a&&b]`) is **not** covered by that ruling: `ch-legacy`
      warns `Possible set intersection`, and the port emits **nothing at all**, so
      the whole warning is absent rather than only its decoration.
    - `generated-15`, `generated-32`, `generated-42` and `generated-59` differ for
      an **unruled** reason, reported to `search-firstmate` on 2026-09-02 and
      **verified live rather than read off the recording**: `console.print_hint`
      passes the user's pattern through Rich console markup, so a bracket
      expression that parses as a style tag is **deleted** from
      `No sessions match "…"`. `ch-legacy` prints `No sessions match "+".` for the
      pattern `[z-a]+`; the port prints the pattern. `[-a]` and `[123]` survive
      because they do not parse as tags. **The port is the better output, which is
      the direction `preserve-because-wrong` exists for.**

    **Do not strengthen this gate without a ruling on those five rows.**
    """
    recorded = _recorded("generated-patterns")
    patterns = query_pattern_corpus.generate_patterns(
        GENERATED_PATTERN_SEED, GENERATED_PATTERN_COUNT
    )
    assert len(patterns) == GENERATED_PATTERN_COUNT, (
        f"Expected {GENERATED_PATTERN_COUNT} distinct generated patterns. "
        f"Got {len(patterns)}."
    )

    divergences: list[str] = []
    for index, pattern in enumerate(patterns):
        columns = GENERATED_PATTERN_WIDTHS[index % len(GENERATED_PATTERN_WIDTHS)]
        key = f"generated-{index}"
        expected = recorded[key]
        assert expected["pattern"] == pattern, (
            f"{key} was recorded for {expected['pattern']!r} and the corpus now "
            f"generates {pattern!r}. The seed or the generator moved; the recording "
            "cannot be re-taken."
        )
        assert expected["columns"] == columns, (
            f"{key} was recorded at {expected['columns']} columns and is now "
            f"generated at {columns}."
        )
        case = {
            "id": key,
            "arguments": [pattern, "-l", "--color", "always", "--no-paging"],
            "columns": columns,
            "color": True,
        }
        actual = _run_search(checkout_built_ch, case, contract_home)
        if actual.returncode != expected["returncode"] or _normalize(
            actual.stdout, contract_home
        ) != _normalize(expected["stdout"], contract_home):
            # (already normalised both sides here; `_compare` now does the same
            # for the other two gates.)
            divergences.append(f"{pattern!r} at {columns} columns")

    assert not divergences, (
        "Expected `ch search` to reproduce the recording for every generated "
        f"pattern. {len(divergences)} of {len(patterns)} diverged: {divergences[:10]}."
    )


@pytest.fixture(scope="module")
def fixed_length_sweep_home(sweep_home: Path) -> Iterator[Path]:
    """The sweep corpus at a home of **exactly** the recorded length.

    **The length is the contract; the path is not.** `g5-runner` falsified that
    directly — replaying at a different path of the same length reproduced all 72
    rows byte for byte on stdout, stderr and exit code.

    **Why it cannot be `tmp_path`.** These rows carry session paths in wrapped
    stderr, so the product's wrap points move with the length of the home. A
    variable-length home makes a byte-perfect route fail, which is the defect this
    recording was re-taken to remove — and the recording says *"do not use
    tmp_path here"* in as many words, because `tmp_path` is the obvious thing.

    The corpus content is copied from the live `sweep_home` fixture rather than
    rebuilt, so this differs from the gate it replaces in path only.
    """
    baseline = _baseline()
    target = Path(baseline["columns_sweep_home"])
    if target.exists():
        shutil.rmtree(target.parent, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(sweep_home, target)
    try:
        yield target
    finally:
        shutil.rmtree(target.parent, ignore_errors=True)


def test_the_sweep_home_is_the_recorded_length() -> None:
    """**Fail loudly rather than compare wrongly.**

    `g5-runner`'s recommendation, and the reason is that the alternative is silent:
    a future change to the home fixture would move the product's wrap points and
    produce wrong comparisons rather than a red row — which reads as a port defect
    and is not one.
    """
    baseline = _baseline()
    recorded = baseline["columns_sweep_home"]
    assert len(recorded) == baseline["columns_sweep_home_length"], (
        "the recording disagrees with itself about the home length"
    )
    assert len(recorded) == 31, (
        f"the columns-sweep home length moved to {len(recorded)}. Every row in that "
        "group was recorded at 31 and cannot be re-taken; the route that would "
        "answer is gone."
    )


@pytest.mark.parametrize("columns", COLUMNS_VALUES, ids=lambda value: repr(value))
@pytest.mark.parametrize("arguments", SHAPES)
def test_columns_sweep_matches_the_recording(
    checkout_built_ch: Path,
    fixed_length_sweep_home: Path,
    arguments: list[str],
    columns: str | None,
) -> None:
    """The two width resolvers still compose the way Python composed them.

    `preserve-because-wrong` item 9: argparse reads `COLUMNS` through
    `shutil.get_terminal_size` and Rich through `str.isdigit()`, so they disagree
    on a leading sign, surrounding whitespace and fullwidth digits. Keeping both
    is the correct port; this asserts the *composition* still reproduces what
    `ch-legacy` produced at every swept value.
    """
    # **Indexed on the recording's own `arguments` and `columns` fields, not on its
    # key string.** Reproducing someone else's key format is a second definition of
    # the case that can drift from theirs silently; the fields are the case.
    recorded = {
        (tuple(row["arguments"]), row["columns"]): row
        for row in _recorded("columns-sweep").values()
    }
    key = (tuple(arguments), columns)
    assert key in recorded, (
        f"`ch {' '.join(arguments)}` at COLUMNS={columns!r} is swept but was not "
        "recorded. SHAPES or COLUMNS_VALUES grew after the recording; the route "
        "that could answer is gone."
    )
    assert len(str(fixed_length_sweep_home)) == _baseline()["columns_sweep_home_length"], (
        f"replaying at a home of length {len(str(fixed_length_sweep_home))} against "
        f"rows recorded at {_baseline()['columns_sweep_home_length']}. The wrap "
        "points move with it, so a byte-perfect route would fail here."
    )
    actual = _run(checkout_built_ch, arguments, columns, fixed_length_sweep_home)
    _compare(
        actual,
        recorded[key],
        fixed_length_sweep_home,
        f"`ch {' '.join(arguments)}` at COLUMNS={columns!r}",
    )


# ── The falsifiers ───────────────────────────────────────────────────────────


def test_the_recording_covers_every_case_the_live_gates_ran() -> None:
    """**A shrunken comparison must fail here rather than pass quietly.**

    Each of the three gates above iterates a corpus and looks its cases up in the
    recording. If the recording lost rows, or a corpus shrank, every remaining row
    would still match and all three would stay green while measuring less. This is
    the assertion that cannot.

    The counts are the recording's own, checked against what the live modules
    generate today — **both sides, so neither a shrunken recording nor a shrunken
    corpus passes.**
    """
    baseline = _baseline()
    counts = baseline["counts"]
    groups = baseline["groups"]

    expected = {
        "defect-patterns": len(query_pattern_corpus.DEFECT_PATTERNS),
        "generated-patterns": GENERATED_PATTERN_COUNT,
        "columns-sweep": len(SHAPES) * len(COLUMNS_VALUES),
    }
    assert expected == {"defect-patterns": 18, "generated-patterns": 60, "columns-sweep": 72}, (
        f"The live corpora no longer produce the sizes recorded on 2026-09-01: "
        f"{expected}. The recording cannot be re-taken, so this is a decision, not "
        "a re-baseline."
    )
    assert counts == expected, (
        f"The recording's own counts {counts} disagree with what the live modules "
        f"generate {expected}."
    )
    for group, size in expected.items():
        assert len(groups[group]) == size, (
            f"group {group!r} holds {len(groups[group])} rows against {size} cases. "
            "A gate that looks its cases up would still pass on every row it kept."
        )


def test_the_recording_carries_its_provenance_and_its_degradation() -> None:
    """A frozen successor whose provenance is missing cannot be audited later.

    The oracle digest and revision say **what** was recorded; the `degradation`
    field says what the gate stopped being able to see. Without the second, a
    reader finds a passing gate and no way to know it is weaker than the one it
    replaced.
    """
    baseline = _baseline()
    for field in ("oracle_route_digest", "revision", "reference_identity", "what_this_is"):
        assert baseline.get(field), f"the recording is missing {field!r}"
    assert "no longer detect" in baseline["degradation"], (
        "the degradation field must say what this gate stopped being able to see, "
        "not merely that it was frozen"
    )
