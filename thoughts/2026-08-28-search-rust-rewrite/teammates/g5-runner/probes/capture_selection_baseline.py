#!/usr/bin/env python3
"""Record `ch-legacy search`'s answers for the three gates that have NO frozen twin.

**A gate with no successor is not a weakened gate, it is a deleted gate.** Three
live-only gates were about to stop asserting anything at the deletion:
`test_named_defect_patterns_select_the_same_sessions`,
`test_generated_patterns_select_the_same_sessions`, and
`test_columns_sweep_reproduces_legacy`. This records what Python answers so the
port can still be held to it.

**Cheap now, impossible after.** Run while both routes are alive.

The harness is IMPORTED, never copied: a hand copy grades the successor against a
drifted definition of the case and both sides pass while measuring different
things.

    capture_selection_baseline.py <out-dir>
"""
from __future__ import annotations

import base64, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
sys.path.insert(0, str(PROJECT_ROOT / "thoughts/2026-08-28-search-rust-rewrite/teammates/contract-owner/work"))

import oracle_digest  # noqa: E402
import query_pattern_corpus  # noqa: E402
import test_search_command_contract as contract  # noqa: E402
import test_search_columns_sweep as sweep  # noqa: E402

LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"

# ⚠ The `columns-sweep` group is recorded at a FIXED home, not a `tmp_path`, and the
# reason is the whole point of that gate.
#
# The `invalid-date` shape's stderr names session paths. The product wraps that text
# at the sweep width **while the real path is still in it**, and `_normalize` replaces
# the home afterwards — so a plain string replace cannot repair a break that landed
# *inside* a path. Recorded under one temporary home and replayed under another, the
# breaks fall at different offsets and the comparison fails on a byte-perfect product.
#
# The obvious fix is to collapse whitespace inside paths before comparing. **That is
# rejected: it would stop the sweep seeing wrap differences, and the wrap composition
# is the entire reason the gate exists** — `preserve-because-wrong` item 9, two width
# resolvers that must compose correctly at every value. A gate that cannot see
# wrapping is not a weaker version of that gate; it is a different one that passes.
#
# So both the recording and the successor use a home of this exact path and length,
# and the length is stored in the provenance so the successor can assert it.
# **Do not reach for `tmp_path` here** — it is the obvious thing and it is the defect.
SWEEP_HOME = Path("/tmp/ch-columns-sweep-home/home")
EXPECTED = {"defect-patterns": 18, "generated-patterns": 60, "columns-sweep": 72}


def materialize(corpus, root: Path) -> Path:
    """Same recipe the suite uses: copy, then restore the recorded mtimes."""
    home = root / corpus.name / "home"
    shutil.copytree(corpus.root / "home", home)
    for relative_path, mtime in corpus.mtimes.items():
        target = home / relative_path
        if target.exists():
            os.utime(target, (mtime, mtime))
    return home


def build_sweep_home() -> Path:
    """A home at a fixed path, so wrap points are reproducible. See SWEEP_HOME."""
    if SWEEP_HOME.parent.exists():
        shutil.rmtree(SWEEP_HOME.parent)
    corpus = contract.CORPORA[0]
    shutil.copytree(corpus.root / "home", SWEEP_HOME)
    for relative_path, mtime in corpus.mtimes.items():
        target = SWEEP_HOME / relative_path
        if target.exists():
            os.utime(target, (mtime, mtime))
    return SWEEP_HOME


def store(completed, home: Path) -> dict:
    """Both streams and the exit code, with the ephemeral home tokenised."""
    return {
        "returncode": completed.returncode,
        "stdout": base64.b64encode(contract._normalize(completed.stdout, home)).decode(),
        "stderr": base64.b64encode(contract._normalize(completed.stderr, home)).decode(),
    }


def capture(home: Path) -> dict[str, dict]:
    out: dict[str, dict] = {"defect-patterns": {}, "generated-patterns": {}, "columns-sweep": {}}

    for name in sorted(query_pattern_corpus.DEFECT_PATTERNS):
        case = {"id": name, "arguments": [query_pattern_corpus.DEFECT_PATTERNS[name], "-ll"],
                "columns": 96, "color": False}
        out["defect-patterns"][name] = store(contract._run_search(LEGACY, case, home), home)

    patterns = query_pattern_corpus.generate_patterns(
        contract.GENERATED_PATTERN_SEED, contract.GENERATED_PATTERN_COUNT)
    for index, pattern in enumerate(patterns):
        columns = contract.GENERATED_PATTERN_WIDTHS[index % len(contract.GENERATED_PATTERN_WIDTHS)]
        case = {"id": f"generated-{index}", "columns": columns, "color": True,
                "arguments": [pattern, "-l", "--color", "always", "--no-paging"]}
        entry = store(contract._run_search(LEGACY, case, home), home)
        entry["pattern"] = pattern
        entry["columns"] = columns
        out["generated-patterns"][f"generated-{index}"] = entry

    sweep_home = build_sweep_home()
    for shape in sweep.SHAPES:
        arguments = shape.values[0]
        for columns in sweep.COLUMNS_VALUES:
            key = f"{shape.id}|{columns!r}"
            out["columns-sweep"][key] = store(
                sweep._run(LEGACY, arguments, columns, sweep_home), sweep_home)
            out["columns-sweep"][key]["arguments"] = arguments
            out["columns-sweep"][key]["columns"] = columns
    return out


def refuse_unless_complete(captured: dict[str, dict]) -> None:
    """Refuse rather than write. **A recording that came out empty must not look
    like a corpus** — a successor built on it would pass over nothing at all."""
    for group, expected in EXPECTED.items():
        got = len(captured.get(group, {}))
        if got != expected:
            raise SystemExit(
                f"refusing to write: {group} captured {got} cases, expected {expected}. "
                "A short or empty recording is indistinguishable from a corpus once "
                "written, and the route it recorded is about to be deleted."
            )
        for key, entry in captured[group].items():
            for stream in ("stdout", "stderr"):
                raw = base64.b64decode(entry[stream])
                if b"/var/folders" in raw or b"/tmp/ch-columns-sweep-home" in raw:
                    raise SystemExit(
                        f"refusing to write: {group}/{key} {stream} still carries a raw "
                        "home path after normalisation. A line break landed inside the "
                        "path, so `_normalize` could not match it, and this row could "
                        "never be reproduced at another home. Fix the case; do not "
                        "freeze it."
                    )
            if entry["returncode"] == 0 and not base64.b64decode(entry["stdout"]) \
               and not base64.b64decode(entry["stderr"]):
                raise SystemExit(
                    f"refusing to write: {group}/{key} exited 0 with both streams empty. "
                    "That is a case that cannot fail, recorded as if it could."
                )


def main() -> int:
    out_dir = Path(sys.argv[1])
    root = Path(tempfile.mkdtemp())
    home = materialize(contract.CORPORA[0], root)
    captured = capture(home)
    refuse_unless_complete(captured)

    digest = oracle_digest.oracle_route_digest()
    record = {
        "what_this_is": (
            "`ch-legacy search`'s answers for three gates that had no frozen twin. "
            "Recorded 2026-09-01 by g5-runner, immediately before the Python search "
            "authority was deleted."
        ),
        "degradation": (
            "BEFORE: each of these gates ran BOTH routes and asserted they agreed, so "
            "it could see the port drift away from Python. AFTER: it asserts the port "
            "still produces what Python produced on 2026-09-01 at oracle route digest "
            f"{digest}. It can no longer detect that this recording was itself wrong, "
            "because the route that would have said so is gone."
        ),
        "oracle_route_digest": digest,
        "oracle_route_digest_recipe": "tests/oracle_digest.py::oracle_route_digest",
        "reference": str(LEGACY),
        "reference_identity": hashlib.sha256(LEGACY.read_bytes()).hexdigest()[:16],
        "revision": subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                                   capture_output=True, text=True).stdout.strip(),
        "columns_sweep_home": str(SWEEP_HOME),
        "columns_sweep_home_length": len(str(SWEEP_HOME)),
        "columns_sweep_home_note": (
            "The columns-sweep group was recorded at this exact path. The successor "
            "MUST replay it at a home of this exact length, or the product's wrap "
            "points move and a byte-perfect route fails. Do not use tmp_path here."
        ),
        "counts": {group: len(cases) for group, cases in captured.items()},
        "groups": captured,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "legacy-selection-baseline.json"
    target.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(f"recorded {sum(record['counts'].values())} answers "
          f"({', '.join(f'{k} {v}' for k, v in record['counts'].items())})")
    print(f"oracle    {digest}")
    print(f"reference {record['reference_identity']}")
    print(f"file      {target} ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
