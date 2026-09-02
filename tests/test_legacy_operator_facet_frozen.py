"""Boolean operators evaluated against the session SUMMARY facet, frozen.

**Why this exists, and it is the one gap in the bucket-A ruling.** When the Python
search authority was deleted, `test_search_operators.py` went with it: 20 of its 22
claims have a counterpart in the contract corpora (16 of 260 cases carry
`AND`/`OR`/`NOT`, seven of them error paths) or in
`rust/search_query.rs::boolean_parser_precedence_errors_and_not_paths`, whose own
comment records that three were migrated deliberately.

**Two had no counterpart anywhere.** The corpora cover summary facets
(`facet-summary-match`, `facet-summary-only-session`) and they cover operators.
They never cover them together. So *a term satisfied only by a session's summary
still counting toward `AND`*, and *a negated term found only in a summary still
excluding the session*, were asserted nowhere else in the tree.

**Measured on both live routes before this was built**, rather than frozen as a
mystery: `ch-legacy` and `ch` agreed on both shapes on 2026-09-02. **The port was
right, and nothing would have noticed if it stopped being right.** That is decision
6 in its plainest form — the subject survives, the oracle dies, and there is no
successor — so the consultation was stored while the window was open.

**The fixture builder lives HERE and the capture imports it**, which is the import
rule pointed the only way it can point: the module that defined these shapes is
deleted, so the surviving side owns the definition and the recording is graded
against the same one it was taken with.

**The recording's `degradation` field says what this gate stopped being able to
see, and it is not restated here. Read it.**
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

BASELINE = (
    Path(__file__).parent
    / "data"
    / "legacy-operator-facet-baseline"
    / "legacy-operator-facet-baseline.json"
)

#: One entry per claim, holding the whole case: the sessions to write, the pattern,
#: and the ids the claim is about. **The expected ids are NOT what the gate asserts**
#: — the recording is. They are here because a fixture whose point is invisible gets
#: "simplified" by the next reader.
CLAIMS: dict[str, dict] = {
    "and-term-satisfied-by-summary-facet": {
        "sessions": {
            "summary-carries-term": {
                "messages": ["opname-bravo lives in a message"],
                "summary": "summary mentions opname-alpha",
            },
        },
        "pattern": "opname-alpha AND opname-bravo",
        "claim": "an AND term satisfied only by the summary still counts",
        "ids_when_recorded": ["summary-carries-term"],
    },
    "not-excludes-when-negated-term-in-summary": {
        "sessions": {
            "summary-has-excluded": {
                "messages": ["opname-alpha in message"],
                "summary": "summary mentions opname-bravo",
            },
            "clean-session": {
                "messages": ["opname-alpha in message"],
                "summary": "unrelated summary",
            },
        },
        "pattern": "opname-alpha NOT opname-bravo",
        "claim": "a NOT term satisfied only by the summary still excludes",
        "ids_when_recorded": ["clean-session"],
    },
}
ARGUMENTS = ("-ll", "--color", "never", "--no-paging")


def write_claim_home(home: Path, claim: dict) -> None:
    """Materialise one claim's session pool. **Imported by the capture probe.**"""
    for stem, session in claim["sessions"].items():
        path = home / ".claude" / "projects" / "proj" / f"{stem}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(
                {"type": "summary", "summary": session["summary"], "leafUuid": f"{stem}-leaf"}
            )
        ]
        lines += [
            json.dumps(
                {
                    "type": "user",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "cwd": "/tmp/search-operators",
                    "message": {"role": "user", "content": text},
                }
            )
            for text in session["messages"]
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_claim(executable: Path, claim: dict, home: Path) -> subprocess.CompletedProcess[bytes]:
    """Run one claim's search. **Imported by the capture probe.**"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"NO_COLOR", "FORCE_COLOR", "CLICOLOR", "CLICOLOR_FORCE"}
    }
    environment.update(HOME=str(home), COLUMNS="96", TERM="dumb")
    return subprocess.run(
        [str(executable), "search", claim["pattern"], *ARGUMENTS],
        env=environment,
        capture_output=True,
        check=False,
    )


@pytest.fixture
def claim_home(tmp_path: Path) -> Iterator[Path]:
    """A fresh pool per claim. **`tmp_path` is safe here and it was not for the
    columns sweep**: these shapes emit session ids and no paths, so nothing in the
    recorded bytes moves with the length of the home."""
    home = tmp_path / "home"
    home.mkdir(parents=True)
    yield home


def _baseline() -> dict:
    return json.loads(BASELINE.read_text())


@pytest.mark.parametrize("name", sorted(CLAIMS), ids=lambda name: name)
def test_summary_facet_operator_claim_matches_the_recording(
    checkout_built_ch: Path, claim_home: Path, name: str
) -> None:
    """The port still resolves the claim the way `ch-legacy` resolved it."""
    recorded = _baseline()["claims"]
    assert name in recorded, (
        f"{name!r} is in CLAIMS but not in the recording. The route that could "
        "answer for it is gone; re-recording is impossible. Do not skip it — decide."
    )
    claim = CLAIMS[name]
    write_claim_home(claim_home, claim)
    actual = run_claim(checkout_built_ch, claim, claim_home)
    expected = recorded[name]

    assert actual.returncode == expected["returncode"], (
        f"{name}: exit {actual.returncode} where `ch-legacy` recorded "
        f"{expected['returncode']}."
    )
    for stream in ("stdout", "stderr"):
        want = base64.b64decode(expected[stream])
        got = getattr(actual, stream)
        assert got == want, (
            f"{name}: {stream} differs from the recording.\n"
            f"  claim:    {claim['claim']}\n"
            f"  recorded: {want[:400]!r}\n  native:   {got[:400]!r}"
        )


def test_the_recording_covers_every_claim_and_carries_its_provenance() -> None:
    """**A shrunken recording must fail here rather than pass quietly.**

    The gate above looks each claim up, so a recording that lost one would stay
    green on the rest. Both sides are checked — what `CLAIMS` holds today and what
    the recording holds — so neither a shrunken recording nor a shrunken claim set
    passes.
    """
    baseline = _baseline()
    assert set(baseline["claims"]) == set(CLAIMS), (
        f"the recording and CLAIMS disagree.\n"
        f"  only in the recording: {sorted(set(baseline['claims']) - set(CLAIMS))}\n"
        f"  only in CLAIMS:        {sorted(set(CLAIMS) - set(baseline['claims']))}"
    )
    assert len(CLAIMS) == 2, (
        f"CLAIMS holds {len(CLAIMS)} claims against the two recorded on 2026-09-02. "
        "A third cannot be recorded — the route that would answer is gone."
    )
    for field in ("oracle_route_digest", "revision", "reference_identity", "what_this_is"):
        assert baseline.get(field), f"the recording is missing {field!r}"
    assert "no longer detect" in baseline["degradation"], (
        "the degradation field must say what this gate stopped being able to see, "
        "not merely that it was frozen"
    )


def test_a_claim_that_stopped_discriminating_fails_here() -> None:
    """**A recording whose two sides agree would pass on any port at all.**

    Each claim exists to separate sessions the summary facet includes from ones it
    excludes. If a recorded answer ever holds every session in its pool, or none,
    the case has stopped discriminating and reproducing it proves nothing.
    """
    recorded = _baseline()["claims"]
    for name, claim in CLAIMS.items():
        ids = base64.b64decode(recorded[name]["stdout"]).decode().split()
        pool = set(claim["sessions"])
        assert ids, f"{name} recorded no matching session; a comparison that cannot fail."
        assert set(ids) < pool or len(pool) == 1 and set(ids) == pool, (
            f"{name} recorded every session in its pool as matching: {ids}. "
            "The claim is about which sessions the summary facet decides, and a "
            "case that selects all of them decides nothing."
        )
