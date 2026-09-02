#!/usr/bin/env python3
"""Generate the `ch search` contract fixtures from the current-main Python oracle.

Command shapes come from the unmerged cycle-02 branch. Every expectation is
re-derived here by running the shape through the public `ch search` journey on
current `main`, because the branch's own expectations were produced by the
branch's implementation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).parent
PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
SOURCE_FIXTURES = WORK / "wip-fixtures"
TARGET_FIXTURES = PROJECT_ROOT / "tests" / "data" / "search-contract-fixtures"
# The suite's own cargo target, not the shared `target/release` that other
# suites unlink and rebuild. Expectations must come from the same artifact
# the suite measures.
BUILT_CH = PROJECT_ROOT / "target" / "contract-suite" / "release" / "ch"
HOME = WORK / "generate-home"

SOURCE_CASES = json.loads((SOURCE_FIXTURES / "MANIFEST.json").read_text())["cases"]
MTIMES = json.loads((SOURCE_FIXTURES / "MTIMES.json").read_text())

# Colored views render an age token and an age style, both functions of wall
# clock against a fixed fixture timestamp. Both are normalized here, and
# `test_search_age_rendering_*` pins the mapping they hide.
AGE_TOKEN = re.compile(rb"(\x1b\[[0-9;]*m)(\d{1,3}(?:s|m|h|d|w|mo|y)|now|\?)(\x1b\[0m)")
AGE_STYLES = {
    b"\x1b[38;2;169;174;180m": b"\x1b[{AGE_STYLE}m",
    b"\x1b[38;2;135;140;146m": b"\x1b[{AGE_STYLE}m",
    b"\x1b[38;2;107;112;118m": b"\x1b[{AGE_STYLE}m",
    b"\x1b[38;2;86;91;97m": b"\x1b[{AGE_STYLE}m",
}


sys.path.insert(0, str(WORK))
import extra_fixtures  # noqa: E402


def materialize_extra_sessions(root: Path) -> dict[str, float]:
    """Write this contract's own sessions into a fixture home and time-stamp them."""
    mtimes: dict[str, float] = {}
    ordered = [
        *(
            (relative, "\n".join(json.dumps(e, separators=(",", ":")) for e in entries) + "\n")
            for relative, entries in extra_fixtures.EXTRA_SESSIONS.items()
        ),
        *extra_fixtures.RAW_EXTRA_SESSIONS.items(),
    ]
    for offset, (relative, content) in enumerate(ordered):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        mtimes[relative] = extra_fixtures.EXTRA_MTIME_BASE + offset * 100
    return mtimes


ALL_MTIMES = dict(MTIMES)


def _reject_ordering_ties(mtimes: dict[str, float]) -> None:
    """Refuse a corpus where two sessions tie on the ordering key.

    Search orders newest-first by stat mtime with a stable sort, so equal mtimes
    keep discovery order — and discovery is `read_dir`, whose order is not stable
    across directory instances. A tie therefore makes the corpus produce
    different bytes in one copy of the fixture home than in another, and the
    resulting failures land on whichever cases happen to show both tied files.
    """
    grouped: dict[float, list[str]] = {}
    for relative_path, mtime in mtimes.items():
        grouped.setdefault(mtime, []).append(relative_path)
    ties = {mtime: paths for mtime, paths in grouped.items() if len(paths) > 1}
    assert not ties, (
        "Expected every fixture session to have a distinct stat mtime, because "
        f"ties make search order depend on `read_dir`. Tied: {ties}."
    )


def build_home() -> Path:
    if HOME.exists():
        shutil.rmtree(HOME)
    shutil.copytree(SOURCE_FIXTURES / "home", HOME)
    ALL_MTIMES.update(materialize_extra_sessions(HOME))
    _reject_ordering_ties(ALL_MTIMES)
    for relative_path, mtime in ALL_MTIMES.items():
        os.utime(HOME / relative_path, (mtime, mtime))
    return HOME


def environment(*, columns: int, color: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "HOME": str(HOME),
        "TZ": "Asia/Jerusalem",
        "COLUMNS": str(columns),
        "LINES": "40",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "NO_COLOR": "1",
    })
    if color:
        env.pop("NO_COLOR", None)
    return env


def normalize(content: bytes) -> bytes:
    normalized = content.replace(str(HOME).encode(), b"{HOME}").replace(
        str(PROJECT_ROOT).encode(), b"{PROJECT_ROOT}"
    )
    normalized = AGE_TOKEN.sub(rb"\g<1>{AGE}\g<3>", normalized)
    for style, placeholder in AGE_STYLES.items():
        normalized = normalized.replace(style, placeholder)
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", normalized)


def run_case(case: dict) -> tuple[int, bytes, bytes]:
    arguments = [str(a).replace("{HOME}", str(HOME)) for a in case["arguments"]]
    completed = subprocess.run(
        [str(BUILT_CH), "search", *arguments],
        cwd=str(PROJECT_ROOT),
        env=environment(columns=int(case.get("columns", 96)), color=bool(case.get("color"))),
        capture_output=True,
    )
    return completed.returncode, normalize(completed.stdout), normalize(completed.stderr)


def record_oracle_identity() -> dict[str, str]:
    """Record which oracle these expectations were derived from.

    A revision alone is not enough. `.venv/bin/ch-legacy` reaches `src/chats/`
    through the editable install, so it delivers the working tree rather than a
    commit. An artifact naming a revision while the tree beneath it has moved
    claims something the launcher does not deliver.
    """
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    identity = {
        "revision": revision,
        "source_digest": contract_source_digest(PROJECT_ROOT / "src" / "chats"),
    }
    (TARGET_FIXTURES / "ORACLE.json").write_text(
        json.dumps(identity, indent=2) + "\n", encoding="utf-8"
    )
    return identity


def contract_source_digest(root: Path) -> str:
    """The oracle's identity, defined once in `tests/oracle_digest.py`."""
    sys.path.insert(0, str(PROJECT_ROOT / "tests"))
    import oracle_digest

    return oracle_digest.oracle_route_digest()


def _derive(source_case: dict, expected_dir: Path) -> dict:
    case_id = source_case["id"]
    code, out, err = run_case(source_case)
    (expected_dir / f"{case_id}.stdout").write_bytes(out)
    (expected_dir / f"{case_id}.stderr").write_bytes(err)
    return {
        "id": case_id,
        "arguments": source_case["arguments"],
        "columns": source_case.get("columns", 96),
        "color": bool(source_case.get("color")),
        "exit_status": code,
        "expected_stdout": f"expected/{case_id}.stdout",
        "expected_stderr": f"expected/{case_id}.stderr",
    }


def amend(case_ids: list[str]) -> None:
    """Derive only the named cases, leaving every other expectation untouched.

    The corpus is frozen: a post-freeze finding adds a case and regenerates that
    case. Regenerating the whole corpus to add one shape would silently re-derive
    220 expectations against whatever the product does today, which is how a
    parity net turns into a mirror.
    """
    build_home()
    manifest_path = TARGET_FIXTURES / "MANIFEST.json"
    cases = json.loads(manifest_path.read_text())["cases"]
    by_id = {case["id"]: index for index, case in enumerate(cases)}
    source_by_id = {
        case["id"]: case for case in [*SOURCE_CASES, *extra_fixtures.EXTRA_CASES]
    }

    for relative, _mtime in ALL_MTIMES.items():
        target = TARGET_FIXTURES / "home" / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HOME / relative, target)
    (TARGET_FIXTURES / "MTIMES.json").write_text(
        json.dumps(ALL_MTIMES, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for case_id in case_ids:
        derived = _derive(source_by_id[case_id], TARGET_FIXTURES / "expected")
        if case_id in by_id:
            cases[by_id[case_id]] = derived
        else:
            cases.append(derived)
    manifest_path.write_text(json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8")
    record_oracle_identity()
    print(f"amended {len(case_ids)} cases; corpus now {len(cases)}")


def main() -> None:
    assert BUILT_CH.is_file(), f"Expected a freshly built launcher at {BUILT_CH}."
    if len(sys.argv) > 1 and sys.argv[1] == "--amend":
        amend(sys.argv[2:])
        return

    build_home()

    if TARGET_FIXTURES.exists():
        shutil.rmtree(TARGET_FIXTURES)
    shutil.copytree(HOME, TARGET_FIXTURES / "home")
    (TARGET_FIXTURES / "MTIMES.json").write_text(
        json.dumps(ALL_MTIMES, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    expected_dir = TARGET_FIXTURES / "expected"
    expected_dir.mkdir(parents=True)

    cases = [
        _derive(source_case, expected_dir)
        for source_case in [*SOURCE_CASES, *extra_fixtures.EXTRA_CASES]
    ]

    (TARGET_FIXTURES / "MANIFEST.json").write_text(
        json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8"
    )
    identity = record_oracle_identity()
    print(f"wrote {len(cases)} cases to {TARGET_FIXTURES}")
    print(f"oracle revision {identity['revision'][:9]} {identity['source_digest'][:23]}…")


if __name__ == "__main__":
    main()
