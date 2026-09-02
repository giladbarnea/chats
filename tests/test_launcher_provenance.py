"""The launcher-provenance guard, falsified against a real stale artifact.

**A positive freshness proof that has never been shown to fail is green for an unknown
reason.** The guard this file grades was inverted on 2026-09-01: it used to reject a
launcher carrying one forbidden string, and that premise died when the native `search`
arm landed and a legitimately fresh build started carrying it. The replacement asserts
the binary and the working tree **agree** about a set of probe strings, in both
directions.

**The artifact is kept rather than reproduced.** `tests/data/launcher-provenance/`
holds a real `ch` built from `wip/cycle-02-native-default-pause-20260821` @ `0ffde41` on
2026-08-25 — the unmerged branch whose stale binaries are the hazard the guard exists
for. Rebuilding one later to falsify a guard is the expensive version of something that
was nearly free while a copy still existed.
"""

from __future__ import annotations

import pytest

from test_search_command_contract import (
    LAUNCHER_PROVENANCE_PROBES,
    PROJECT_ROOT,
    _reject_foreign_launcher,
    _rust_source_bytes,
)

STALE_LAUNCHER = PROJECT_ROOT / "tests" / "data" / "launcher-provenance" / "ch-0ffde41"


def test_the_kept_stale_launcher_is_still_there() -> None:
    """Without the artifact the falsification below is a claim about one."""
    assert STALE_LAUNCHER.is_file(), (
        f"The kept stale launcher is missing at {STALE_LAUNCHER}. It is the only thing "
        "that shows the provenance guard can fail. Rebuild it with the recipe in "
        "`provenance.json` beside it, or the guard becomes green for an unknown reason."
    )


def test_the_guard_rejects_a_real_stale_launcher() -> None:
    """The falsification: a launcher from the unmerged branch must fail."""
    with pytest.raises(AssertionError) as failure:
        _reject_foreign_launcher(STALE_LAUNCHER)
    message = str(failure.value)
    assert "disagrees with" in message, (
        f"The guard rejected the stale launcher for some other reason: {message}"
    )
    assert "real staleness, not a harness quirk" in message, (
        "The failure message must say what a failure means, or the next person reads a "
        "real staleness as a harness problem and deletes the guard."
    )


def test_the_guard_accepts_the_tree_it_was_built_from() -> None:
    """A guard that rejects everything is not a provenance check.

    Built as a synthetic launcher — the concatenated Rust sources — rather than a real
    binary, because the point here is the *rule*, not the compiler: whatever the tree
    contains, the guard must accept.
    """
    synthetic = PROJECT_ROOT / "target" / "synthetic-fresh-launcher"
    synthetic.parent.mkdir(parents=True, exist_ok=True)
    synthetic.write_bytes(_rust_source_bytes())
    try:
        _reject_foreign_launcher(synthetic)
    finally:
        synthetic.unlink(missing_ok=True)


def test_every_probe_is_still_a_string_the_tree_carries() -> None:
    """The probes must live in the tree, or the guard proves nothing about freshness.

    **Four is the floor the guard itself enforces**; this reports the real number so a
    set drifting toward that floor is visible before it reaches it.
    """
    tree = _rust_source_bytes()
    live = [probe.decode() for probe in LAUNCHER_PROVENANCE_PROBES if probe in tree]
    assert len(live) >= 5, (
        f"Only {len(live)} of {len(LAUNCHER_PROVENANCE_PROBES)} probes are still in "
        f"`rust/`: {live}. The set is one edit from the guard's own floor. Add probes "
        "from current production string literals before it gets there."
    )
