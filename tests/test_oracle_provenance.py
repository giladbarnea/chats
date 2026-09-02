"""The deleted oracle route is still recoverable — proved, not asserted.

**Run once, here, rather than at every stamped artifact.** The stamp comparison is
cheap and lives beside each artifact; the reconstruction costs a `git archive` and
belongs in one place.

**This is the gate that replaces three live-currency checks** that the deletion of
the Python search authority made permanently unanswerable. Its degradation is in
`oracle_provenance`'s docstring, where a reader meets the module: it can prove the
route is reachable, and it can never again prove that an expectation recorded
against that route was right.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import oracle_provenance

STORED_IDENTITIES = {
    "ch-legacy": "c1821a3a86ee9a88",
    "RECORD": "863d603b8e2c49ed",
}


def test_the_deleted_oracle_route_still_re_derives_to_its_recorded_digest() -> None:
    """**Cheap now, impossible after — and this is what says it is still cheap.**

    A `git archive` of `67d6053`, the two stored non-git inputs put where the
    recipe looks, and the recipe itself. If this fails, every artifact stamped
    `dd6ab701` has become unverifiable and the stored inputs no longer buy what
    they were stored for.
    """
    reconstructed = oracle_provenance.reconstruct_oracle_route_digest()
    assert reconstructed == oracle_provenance.ORACLE_ROUTE_DIGEST, (
        "The pre-deletion Python search route no longer re-derives to the digest "
        "every frozen artifact names.\n"
        f"  reconstructed: {reconstructed}\n"
        f"  recorded:      {oracle_provenance.ORACLE_ROUTE_DIGEST}\n"
        f"Rebuilt from revision {oracle_provenance.ORACLE_ROUTE_REVISION} plus "
        "`tests/data/oracle-route-inputs/`. Either the revision no longer holds that "
        "`src/chats/`, or a stored input moved. **Do not restamp anything** — the "
        "route is deleted, so a new digest would name nothing."
    )


@pytest.mark.parametrize("name", sorted(STORED_IDENTITIES))
def test_the_stored_inputs_are_the_ones_the_digest_was_taken_with(name: str) -> None:
    """**The two files that look like stray virtualenv artifacts.**

    Named individually so a report says *which* one moved. The reconstruction above
    would also fail, but it would fail saying the digest is wrong rather than saying
    a file was replaced.
    """
    path = oracle_provenance.STORED_INPUTS / name
    assert path.is_file(), (
        f"{path} is missing. It is one of two inputs to `dd6ab701` that git cannot "
        "hold, and without it the deleted oracle route stops being re-derivable. "
        "See the README beside it — it opens 'DO NOT DELETE'."
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    assert digest == STORED_IDENTITIES[name], (
        f"{name} digests to {digest} against the recorded {STORED_IDENTITIES[name]}. "
        "These are frozen inputs, not a copy of the live venv; a refresh replaces the "
        "evidence with something that no longer reproduces the recorded route."
    )


def test_the_readme_survives_beside_them() -> None:
    """**The files without the procedure are not enough and that is measured.**

    `oracle_digest.py` reads the live venv, so a reader holding the two files and no
    instructions still cannot re-derive anything. The README carries the four steps
    and the reason they exist.
    """
    readme = Path(oracle_provenance.STORED_INPUTS) / "README.md"
    assert readme.is_file(), "the re-derivation procedure is gone from beside its inputs"
    text = readme.read_text()
    assert "DO NOT DELETE" in text, "the README no longer says the files are not strays"
    assert oracle_provenance.ORACLE_ROUTE_REVISION[:7] in text, (
        "the README no longer names the revision the reconstruction uses, so the two "
        "would drift apart with nothing to notice"
    )
