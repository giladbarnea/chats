#!/usr/bin/env python3
"""Build the amendment corpus: post-freeze shapes in their own session pool."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).parent
sys.path.insert(0, str(WORK))

import amendment_fixtures  # noqa: E402
import generate_fixtures as base  # noqa: E402

TARGET = base.PROJECT_ROOT / "tests" / "data" / "search-amendment-fixtures"
HOME = WORK / "amendment-home"


def build_home() -> dict[str, float]:
    if HOME.exists():
        shutil.rmtree(HOME)
    mtimes: dict[str, float] = {}
    ordered: list[tuple[str, str]] = [
        (relative, "\n".join(json.dumps(e, separators=(",", ":")) for e in entries) + "\n")
        for relative, entries in amendment_fixtures.AMENDMENT_SESSIONS.items()
    ]
    for name in amendment_fixtures.BRANCH_FIXTURE_NAMES:
        source = amendment_fixtures.BRANCH_FIXTURE_SOURCE / f"{name}.jsonl"
        ordered.append((f".claude/projects/branch/{name}.jsonl", source.read_text()))

    for offset, (relative, content) in enumerate(ordered):
        path = HOME / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        mtimes[relative] = amendment_fixtures.MTIME_OVERRIDES.get(
            relative, amendment_fixtures.BASE_MTIME + offset * 100
        )

    base._reject_ordering_ties(mtimes)
    for relative, mtime in mtimes.items():
        os.utime(HOME / relative, (mtime, mtime))
    return mtimes


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
        str(base.PROJECT_ROOT).encode(), b"{PROJECT_ROOT}"
    )
    normalized = base.AGE_TOKEN.sub(rb"\g<1>{AGE}\g<3>", normalized)
    for style, placeholder in base.AGE_STYLES.items():
        normalized = normalized.replace(style, placeholder)
    return normalized


def main() -> None:
    assert base.BUILT_CH.is_file(), f"Expected a freshly built launcher at {base.BUILT_CH}."
    mtimes = build_home()

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(HOME, TARGET / "home")
    (TARGET / "MTIMES.json").write_text(
        json.dumps(mtimes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    expected = TARGET / "expected"
    expected.mkdir(parents=True)

    cases = []
    for case in amendment_fixtures.AMENDMENT_CASES:
        arguments = [str(a).replace("{HOME}", str(HOME)) for a in case["arguments"]]
        completed = subprocess.run(
            [str(base.BUILT_CH), "search", *arguments],
            cwd=str(base.PROJECT_ROOT),
            env=environment(columns=int(case["columns"]), color=bool(case["color"])),
            capture_output=True,
        )
        (expected / f"{case['id']}.stdout").write_bytes(normalize(completed.stdout))
        (expected / f"{case['id']}.stderr").write_bytes(normalize(completed.stderr))
        cases.append({
            **case,
            "exit_status": completed.returncode,
            "expected_stdout": f"expected/{case['id']}.stdout",
            "expected_stderr": f"expected/{case['id']}.stderr",
        })

    (TARGET / "MANIFEST.json").write_text(
        json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8"
    )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(base.PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (TARGET / "ORACLE.json").write_text(
        json.dumps(
            {
                "revision": revision,
                "source_digest": base.contract_source_digest(
                    base.PROJECT_ROOT / "src" / "chats"
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(cases)} amendment cases to {TARGET}")


if __name__ == "__main__":
    main()
