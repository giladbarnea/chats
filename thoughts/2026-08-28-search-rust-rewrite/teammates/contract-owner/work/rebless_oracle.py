#!/usr/bin/env python3
"""Re-bless the oracle record after proving the product's bytes did not move.

The ruling is that any change to `src/chats/` is an oracle event requiring
either re-characterization or a proof that behaviour is unchanged. This is the
second branch, and it refuses to be the first: it replays every case in every
corpus against the recorded expectations and updates `ORACLE.json` only when
nothing differs.

Re-characterizing instead would silently accept whatever the product does today,
which is how a parity net turns into a mirror.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).parent))

import generate_fixtures as base  # noqa: E402
import test_search_command_contract as contract  # noqa: E402


def materialize(corpus: contract.Corpus, root: Path) -> Path:
    home = root / corpus.name / "home"
    shutil.copytree(corpus.root / "home", home)
    for relative_path, mtime in corpus.mtimes.items():
        os.utime(home / relative_path, (mtime, mtime))
    return home


# Artifacts owned by other teammates that hold recorded Python answers, stamped
# here because they go stale on the same oracle events as ours. **Deliberately
# empty, not an oversight** — 2026-09-01, `g5-runner`, with `search-firstmate`'s
# ruling.
#
# `reviewer-profiler/frozen_reference.json` was the only member and was removed
# because **it now derives the machine-checkable half itself**, at generation, in
# `freeze_references.py`. The reason for stamping it was removed rather than
# worked around.
#
# Removing the writer matters in one direction specifically. **Stamping a frozen
# artifact without re-recording its entries is decision 3's rejected restamp: a
# new digest on an artifact previously carrying a blind one asserts the oracle has
# not moved since generation.** That artifact now carries a stamp derived AT
# generation, which is the strong form; stamping it here would replace that with
# an asserted-afterwards one. **A downgrade, not a refresh.**
#
# The hazard was live rather than latent: `_refuse_if_the_launcher_is_native`
# does not fire for the pinned `~/.local/bin/ch`, which hands search to Python.
#
# Re-add a member only if it holds recorded Python answers and cannot stamp
# itself.
FOREIGN_RECORDS: tuple[Path, ...] = ()


def _stamp_foreign_records(digest: str, revision: str) -> None:
    """Add a machine-checkable digest beside another owner's prose stamp.

    Additive: their `oracle_state` string stays, because it is their provenance
    record. It quotes a working-diff digest, which cannot see the venv entry
    script or the installed RECORD, so it reads unchanged while a reinstall
    replaces the route — which is the failure a stamp exists to detect.
    """
    for path in FOREIGN_RECORDS:
        if not path.is_file():
            continue
        record = json.loads(path.read_text())
        record["source_digest"] = digest
        record["source_digest_recipe"] = "tests/oracle_digest.py::oracle_route_digest"
        record["revision"] = revision
        path.write_text(json.dumps(record, indent=1) + "\n")
        print(f"stamped {path.name} ({len(record.get('entries', {}))} entries)")


def _refuse_if_the_launcher_is_native() -> None:
    """Refuse once `ch search` is the Rust route, because the verdict goes circular.

    This tool replays cases through the built launcher and re-blesses when the
    bytes still match. That is sound only while the launcher *is* the oracle —
    while `ch` execs `ch-legacy` and the bytes it produces are Python's. After
    cutover it stamps records as current because the **new** implementation
    agrees with them, which is the port grading its own homework.

    Detected by behaviour rather than by reading source: a copy of the launcher
    alone in a directory, with no `ch-legacy` sibling. If it can still serve a
    search, the route is native.

    It refuses rather than warning. The next person to reach for this will have
    thirty reds and a deadline, and a printed warning does not survive that.
    """
    with tempfile.TemporaryDirectory() as solitary:
        alone = Path(solitary) / "ch"
        shutil.copy2(contract.CONTRACT_BUILT_CH, alone)
        completed = subprocess.run(
            [str(alone), "search", ".", "-ll"],
            capture_output=True,
            env={**os.environ, "HOME": solitary, "PATH": "/usr/bin:/bin"},
            check=False,
        )
    delegated = b"Cannot start the private ch legacy entry" in completed.stderr
    if not delegated:
        raise SystemExit(
            "REFUSED: the launcher serves search natively, so this tool's verdict "
            "is circular.\n\n"
            "It re-blesses when replayed bytes match the record. Those records hold "
            "Python's answers. A native launcher matching them proves parity, not "
            "that the oracle is unchanged — so re-blessing here would stamp the "
            "record current on the strength of the port agreeing with it.\n\n"
            "Parity is what the contract suite measures. If the oracle has genuinely "
            "moved, re-characterize from `ch-legacy` with `generate_fixtures.py`."
        )


def main() -> int:
    _refuse_if_the_launcher_is_native()

    digest = base.contract_source_digest(PROJECT_ROOT / "src" / "chats")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # The launcher resolves `ch-legacy` as its own sibling, and the suite's
    # private cargo target has none. Without this every case dies at the
    # handoff and the tool would report 251 behaviour changes.
    contract._place_legacy_sibling(contract.CONTRACT_BUILT_CH.parent)

    mismatches: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        homes = {c.name: materialize(c, Path(scratch)) for c in contract.CORPORA}
        for corpus, case in contract.ALL_CASES:
            home = homes[corpus.name]
            completed = contract._run_search(contract.CONTRACT_BUILT_CH, case, home)
            want_out = (corpus.root / str(case["expected_stdout"])).read_bytes()
            want_err = (corpus.root / str(case["expected_stderr"])).read_bytes()
            if (
                completed.returncode != case["exit_status"]
                or contract._normalize(completed.stdout, home) != want_out
                or contract._normalize(completed.stderr, home) != want_err
            ):
                mismatches.append(f"{corpus.name}:{case['id']}")

    if mismatches:
        print(f"REFUSED. {len(mismatches)} of {len(contract.ALL_CASES)} cases moved:")
        for name in mismatches[:20]:
            print(f"  {name}")
        print(
            "\nThe oracle changed behaviour. Re-characterize deliberately with\n"
            "`generate_fixtures.py`, and say in the change log what moved and why."
        )
        return 1

    # Declared, not discovered. Every artifact holding recorded Python answers
    # goes stale on the same events, so each needs the same stamp — but which
    # artifacts those are is a decision, and a decision belongs in a list
    # somebody can read rather than in a directory walk that quietly picks up
    # whatever appears.
    stamped = [corpus.root for corpus in contract.CORPORA]
    frozen = PROJECT_ROOT / "tests" / "data" / "search-frozen-differentials"
    if frozen.is_dir():
        stamped.append(frozen)
    for root in stamped:
        (root / "ORACLE.json").write_text(
            json.dumps({"revision": revision, "source_digest": digest}, indent=2) + "\n",
            encoding="utf-8",
        )
    _stamp_foreign_records(digest, revision)
    print(
        f"Re-blessed {len(stamped)} stamped artifacts at revision {revision[:9]}.\n"
        f"{len(contract.ALL_CASES)} of {len(contract.ALL_CASES)} cases reproduce their "
        "recorded bytes, so the oracle moved without moving behaviour."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
