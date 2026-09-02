"""Emit a stored table as the residue of a passing differential run.

A stored table is the only form that outlives the Python authority, so every
live differential must leave one behind before the deletion slice. The table is
a *recording of a run*, never written by hand, so it cannot drift from the
differential that produced it.

`refuse on any mismatch` is right for accidental divergence and wrong for
deliberate divergence. This mission already has ruled divergences — the
broken-pipe traceback the native route correctly does not reproduce, and the
open ambient-input gaps — and a table that refuses on *any* mismatch drops
exactly the expectations that most need pinning, while looking complete.

So the rule is a ratchet, the same one the harness calibration uses:

  * an **undeclared** mismatch refuses the emit;
  * a **declared** mismatch is recorded with its reason and both values;
  * a declaration that no longer diverges is reported as stale, so it gets
    deleted rather than permanently excusing a mismatch that stopped happening.

Store the output, never the judgement about the output. A table holding bytes
cannot decay into a table about *whether* two things differed; a table holding a
verdict can.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path


def emit_table(
    path: Path,
    *,
    cases: Sequence[dict],
    expected_for: Callable[[dict], object],
    mismatched_keys: Iterable[str],
    key_for: Callable[[dict], str],
    oracle_revision: str,
    generated_by: str,
    declared: dict[str, str] | None = None,
    actual_for: Callable[[dict], object] | None = None,
) -> tuple[bool, str]:
    """Write the table, or refuse. Returns (written, message)."""
    declared = declared or {}
    mismatched = set(mismatched_keys)
    undeclared = sorted(mismatched - declared.keys())
    if undeclared:
        return False, (
            f"refusing to emit: {len(undeclared)} undeclared mismatch(es), "
            f"first {undeclared[:3]}"
        )

    stale = sorted(declared.keys() - mismatched)
    entries = []
    for case in cases:
        key = key_for(case)
        entry: dict[str, object] = {"key": key, "case": case, "expected": expected_for(case)}
        if key in mismatched:
            entry["declared_divergence"] = declared[key]
            if actual_for is not None:
                entry["native_actual"] = actual_for(case)
        entries.append(entry)

    path.write_text(
        json.dumps(
            {
                "oracle_revision": oracle_revision,
                "generated_by": generated_by,
                "declared_divergences": declared,
                "cases": entries,
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    message = f"emitted {len(entries)} cases to {path}"
    if declared:
        message += f"; {len(mismatched & declared.keys())} declared divergence(s) recorded"
    if stale:
        message += f"; STALE declarations no longer diverging, delete them: {stale}"
    return True, message
