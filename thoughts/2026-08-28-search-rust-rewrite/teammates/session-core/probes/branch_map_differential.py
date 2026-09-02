"""Differential: native `branch_map` against Python's `_resolve_branch_map`.

Runs over the seven synthesized fixtures *and* every real Claude session, because the
fixtures cover the structural shapes and the corpus covers the boring accidents no
one writes a fixture for. Python at oracle revision `8cb4c5f` is the oracle.

Point at the driver with BRANCH_BIN=/path/to/branchcheck.
Run from the repo root.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from emit_table import emit_table

from chats.parsing import (
    _iter_jsonl_entries,
    _resolve_branch_map,
    find_all_supported_session_files,
    get_jsonl_session_adapter,
)

BIN = os.environ.get("BRANCH_BIN")
FIXTURES = (
    Path(__file__).resolve().parent.parent / "branch-fixtures"
)


def claude_sessions() -> list[Path]:
    found = []
    for session in find_all_supported_session_files():
        try:
            if get_jsonl_session_adapter(session).name == "claude":
                found.append(session)
        except (ValueError, OSError):
            continue
    return found


def main() -> int:
    if not BIN:
        print("set BRANCH_BIN to the differential driver")
        return 2

    paths = sorted(FIXTURES.glob("*.jsonl")) + claude_sessions()
    payload = "\n".join(json.dumps(str(path)) for path in paths) + "\n"
    completed = subprocess.run([BIN], input=payload.encode("utf-8"), capture_output=True)
    if completed.returncode != 0:
        print(completed.stderr.decode("utf-8")[:2000])
        return 1

    native = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line]
    if len(native) != len(paths):
        print(f"driver returned {len(native)} rows for {len(paths)} paths")
        return 1

    mismatches = []
    with_branches = 0
    for path, actual in zip(paths, native):
        try:
            entries = _iter_jsonl_entries(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        expected = _resolve_branch_map(entries)
        if expected:
            with_branches += 1
        if actual != expected:
            mismatches.append((path, expected, actual))

    # Only the authored fixtures convert. The real Claude sessions are keyed by paths
    # into the user's live pool: a stored table of them would be unportable, unstable
    # under active writes, and would commit conversation content to a tracked
    # directory. Those stay a dated point-in-time proof.
    if "--emit-table" in sys.argv:
        fixture_paths = sorted(FIXTURES.glob("*.jsonl"))
        expected_by_name = {
            path.name: _resolve_branch_map(_iter_jsonl_entries(path.read_text(encoding="utf-8")))
            for path in fixture_paths
        }
        written, message = emit_table(
            Path(sys.argv[sys.argv.index("--emit-table") + 1]),
            cases=[{"fixture": path.name} for path in fixture_paths],
            expected_for=lambda case: expected_by_name[case["fixture"]],
            mismatched_keys=[p.name for p, _e, _a in mismatches],
            key_for=lambda case: case["fixture"],
            oracle_revision="8cb4c5f",
            generated_by=Path(__file__).name,
            declared={},
        )
        print(message)
        if not written:
            return 1

    print(f"sessions compared: {len(paths)}  ({len(list(FIXTURES.glob('*.jsonl')))} fixtures)")
    print(f"sessions with at least one branch: {with_branches}")
    print(f"mismatches: {len(mismatches)}")
    for path, expected, actual in mismatches[:5]:
        only_expected = {k: v for k, v in expected.items() if actual.get(k) != v}
        only_actual = {k: v for k, v in actual.items() if expected.get(k) != v}
        print(f"  {path.name}")
        print(f"    python-only/differing: {dict(list(only_expected.items())[:6])}")
        print(f"    native-only/differing: {dict(list(only_actual.items())[:6])}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
