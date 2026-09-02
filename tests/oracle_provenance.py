"""The oracle route the frozen artifacts name, after that route was deleted.

**One authority for a question that changed on 2026-09-02.** Three suites used to
ask `oracle_route_digest() == ORACLE["source_digest"]` — *has the live Python route
moved since these expectations were recorded?* **The Python search authority was
deleted, so the answer is permanently yes and the question stopped being
answerable.**

⚠ **What was lost, said plainly.** The live check caught a source edit that moved
the oracle under a stored expectation. **Nothing can do that any more.** These
artifacts describe a route that no longer runs, so **no gate can tell you that one
of them was wrong when it was recorded.**

**What replaces it is what Ruling 2 bought rather than nothing.** The pre-deletion
tree is committed at `67d60532bb0d`, and the two digest inputs git cannot hold —
`.venv/bin/ch-legacy` and the installed `RECORD` — are stored at
`tests/data/oracle-route-inputs/`. So the question becomes: **is the route these
artifacts name still RECOVERABLE?** That is answered by rebuilding it and
re-deriving the digest, which is a mechanism where a stamp comparison was a check.

***The property that makes a route digest a good pin — it covers more than git can
hold — is the property that makes it unrecoverable from a commit alone.*** The
stored inputs are the answer to that, and this module is what proves they still
work.

**The recipe is imported, never restated.** `oracle_digest.oracle_route_digest`
takes a `root` for exactly this caller; a second copy here would grade the
reconstruction against a drifted definition of the digest.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import oracle_digest

PROJECT_ROOT = Path(__file__).parent.parent
STORED_INPUTS = PROJECT_ROOT / "tests" / "data" / "oracle-route-inputs"

#: The Python search route every frozen artifact on this desk was characterized
#: against. **A constant, not a measurement** — the route it names is deleted.
ORACLE_ROUTE_DIGEST = (
    "sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0"
)
#: The revision that holds that route's `src/chats/`. Not the revision that holds
#: this file: the claim is about that tree, so it stays true as this one moves.
ORACLE_ROUTE_REVISION = "67d60532bb0d"
#: Where the recipe looks for the input git cannot hold. Reproduced from the
#: README beside the stored files, and asserted by the reconstruction below rather
#: than trusted.
RECORD_DESTINATION = ".venv/lib/python3.14/site-packages/chats-0.1.0.dist-info/RECORD"


def assert_artifact_names_the_recorded_oracle(source_digest: str, artifact: str) -> None:
    """One artifact still names the route it was characterized against.

    Cheap, and deliberately separate from the reconstruction: this runs at every
    artifact, the reconstruction runs once in `test_oracle_provenance.py`.
    """
    assert source_digest == ORACLE_ROUTE_DIGEST, (
        f"{artifact} names oracle route {source_digest}, and every frozen artifact "
        f"on this desk was characterized against {ORACLE_ROUTE_DIGEST} — the Python "
        f"search route at revision {ORACLE_ROUTE_REVISION}, deleted on 2026-09-02.\n"
        "**This is not a currency check and cannot be satisfied by re-freezing:** "
        "the route is gone, so an artifact naming a different one describes something "
        "nobody can reproduce. Re-derive it from "
        "`tests/data/oracle-route-inputs/README.md`, or say in the artifact which "
        "route it came from."
    )


def reconstruct_oracle_route_digest() -> str:
    """Rebuild the deleted route from git plus the stored inputs, and digest it.

    The four steps from `tests/data/oracle-route-inputs/README.md`, executed rather
    than described — **`git archive` of the pre-deletion revision, the two stored
    files put where the recipe looks, then the recipe.** Uses the STORED copies
    rather than the live ones, which is what proves the stored copies work.
    """
    archive = subprocess.run(
        ["git", "archive", ORACLE_ROUTE_REVISION, "src/chats"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    scratch = Path(tempfile.mkdtemp(prefix="oracle-route-"))
    try:
        with tempfile.NamedTemporaryFile(suffix=".tar") as bundle:
            bundle.write(archive)
            bundle.flush()
            with tarfile.open(bundle.name) as tar:
                tar.extractall(scratch, filter="data")
        legacy_entry = scratch / ".venv" / "bin" / "ch-legacy"
        legacy_entry.parent.mkdir(parents=True)
        shutil.copy2(STORED_INPUTS / "ch-legacy", legacy_entry)
        record = scratch / RECORD_DESTINATION
        record.parent.mkdir(parents=True)
        shutil.copy2(STORED_INPUTS / "RECORD", record)
        return oracle_digest.oracle_route_digest(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
