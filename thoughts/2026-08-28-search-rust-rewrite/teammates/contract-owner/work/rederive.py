#!/usr/bin/env python3
"""Re-derive every wip-branch search case from the current-main Python oracle.

The branch's command shapes are trusted. Its expected outputs are not: they came
from that branch's own implementation. This runs each shape against current main
and reports where the two disagree.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRATCH = Path(__file__).parent
FIXTURE_ROOT = SCRATCH / "wip-fixtures"
PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
CH = PROJECT_ROOT / ".venv" / "bin" / "ch"
HOME = SCRATCH / "wip-home"

MANIFEST = json.loads((FIXTURE_ROOT / "MANIFEST.json").read_text())["cases"]
MTIMES = json.loads((FIXTURE_ROOT / "MTIMES.json").read_text())


def build_home() -> Path:
    if HOME.exists():
        shutil.rmtree(HOME)
    shutil.copytree(FIXTURE_ROOT / "home", HOME)
    for relative_path, mtime in MTIMES.items():
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
    normalized = re.sub(
        rb"(\x1b\[[0-9;]*m)(\d{1,3}[smhdw]|\?)(\x1b\[0m)",
        rb"\g<1>{AGE}\g<3>",
        normalized,
    )
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", normalized)


def run_case(case: dict) -> tuple[int, bytes, bytes]:
    arguments = [str(a).replace("{HOME}", str(HOME)) for a in case["arguments"]]
    completed = subprocess.run(
        [str(CH), "search", *arguments],
        cwd=str(PROJECT_ROOT),
        env=environment(columns=int(case.get("columns", 96)), color=bool(case.get("color"))),
        capture_output=True,
    )
    return completed.returncode, normalize(completed.stdout), normalize(completed.stderr)


def main() -> None:
    build_home()
    disagreements = []
    for case in MANIFEST:
        code, out, err = run_case(case)
        want_code = case["exit_status"]
        want_out = (FIXTURE_ROOT / case["expected_stdout"]).read_bytes()
        want_err = (FIXTURE_ROOT / case["expected_stderr"]).read_bytes()
        problems = []
        if code != want_code:
            problems.append(f"exit: branch={want_code} main={code}")
        if out != want_out:
            problems.append("stdout differs")
        if err != want_err:
            problems.append("stderr differs")
        if problems:
            disagreements.append((case, problems, code, out, err, want_code, want_out, want_err))

    print(f"cases: {len(MANIFEST)}  agreeing: {len(MANIFEST) - len(disagreements)}  disagreeing: {len(disagreements)}")
    for case, problems, code, out, err, want_code, want_out, want_err in disagreements:
        print(f"\n{'=' * 78}\n### {case['id']}  args={case['arguments']}\n    {'; '.join(problems)}")
        if out != want_out:
            print("--- branch stdout ---")
            print(want_out.decode(errors="replace")[:1200])
            print("--- main stdout ---")
            print(out.decode(errors="replace")[:1200])
        if err != want_err:
            print("--- branch stderr ---")
            print(want_err.decode(errors="replace")[:1200])
            print("--- main stderr ---")
            print(err.decode(errors="replace")[:1200])


if __name__ == "__main__":
    main()
