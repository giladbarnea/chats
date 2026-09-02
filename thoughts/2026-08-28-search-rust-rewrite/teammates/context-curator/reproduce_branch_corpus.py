#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.14.*"
# dependencies = []
# ///
"""Replay the branch's 704-case search contract corpus against today's `main` Python.

Mirrors the branch harness (`tests/test_search_command_contract.py` @ 0ffde41):
same fixture home, same MTIMES, same environment pinning, same normalization.
The only substitution is the executable: `ch-legacy` on current `main` instead
of the branch's native launcher.

Answers one question: how many of the 173 manifest cases' expected bytes
reproduce against the product our charter names as the sole behavioral oracle.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
CORPUS = Path(
    "/private/tmp/claude-501/-Users-giladbarnea-dev-chats"
    "/34993643-8a40-408e-be63-a5ecaf66fe03/scratchpad/branch-corpus"
    "/tests/data/search-command-fixtures"
)
LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"


def build_home(destination: Path) -> Path:
    home = destination / "home"
    if home.exists():
        shutil.rmtree(home)
    shutil.copytree(CORPUS / "home", home)
    mtimes = json.loads((CORPUS / "MTIMES.json").read_text(encoding="utf-8"))
    for relative_path, mtime in mtimes.items():
        os.utime(home / relative_path, (mtime, mtime))
    return home


def environment(home: Path, *, columns: int, color: bool) -> dict[str, str]:
    result = os.environ.copy()
    result.update({
        "HOME": str(home),
        "TZ": "Asia/Jerusalem",
        "COLUMNS": str(columns),
        "LINES": "40",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "NO_COLOR": "1",
    })
    if color:
        result.pop("NO_COLOR", None)
    return result


def normalize(content: bytes, home: Path) -> bytes:
    """Byte-for-byte the branch harness's `_normalize`."""
    normalized = content.replace(str(home).encode(), b"{HOME}").replace(
        str(PROJECT_ROOT).encode(), b"{PROJECT_ROOT}"
    )
    normalized = re.sub(
        rb"(\x1b\[[0-9;]*m)(\d{1,3}[smhdw]|\?)(\x1b\[0m)",
        rb"\g<1>{AGE}\g<3>",
        normalized,
    )
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", normalized)


def run_case(case: dict, home: Path) -> subprocess.CompletedProcess[bytes]:
    arguments = [
        str(argument).replace("{HOME}", str(home)) for argument in case["arguments"]
    ]
    try:
        return subprocess.run(
            [str(LEGACY), "search", *arguments],
            cwd=PROJECT_ROOT,
            env=environment(
                home,
                columns=int(case.get("columns", 96)),
                color=bool(case.get("color")),
            ),
            input=b"",
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args=arguments, returncode=-1, stdout=b"", stderr=b"{TIMEOUT}")


def classify(case_id: str, expected: bytes, actual: bytes) -> str:
    """Coarse reason label so failures group instead of listing individually."""
    if expected == actual:
        return "match"
    if not expected and actual:
        return "output-where-none-expected"
    if expected and not actual:
        return "no-output-where-expected"
    if expected.split() == actual.split():
        return "whitespace-only"
    if b"FutureWarning" in expected or b"FutureWarning" in actual:
        return "futurewarning-text"
    if b"\x1b[" in expected or b"\x1b[" in actual:
        return "colored-bytes"
    return "content"


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    scratch = Path(
        "/private/tmp/claude-501/-Users-giladbarnea-dev-chats"
        "/34993643-8a40-408e-be63-a5ecaf66fe03/scratchpad/repro"
    )
    scratch.mkdir(parents=True, exist_ok=True)
    home = build_home(scratch)

    cases = json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))["cases"]
    if only:
        cases = [case for case in cases if case["id"] == only]

    results = []
    for case in cases:
        expected_stdout = (CORPUS / case["expected_stdout"]).read_bytes()
        expected_stderr = (CORPUS / case["expected_stderr"]).read_bytes()
        completed = run_case(case, home)
        actual_stdout = normalize(completed.stdout, home)
        actual_stderr = normalize(completed.stderr, home)
        results.append({
            "id": case["id"],
            "arguments": case["arguments"],
            "exit_expected": case["exit_status"],
            "exit_actual": completed.returncode,
            "exit_match": completed.returncode == case["exit_status"],
            "stdout_match": actual_stdout == expected_stdout,
            "stderr_match": actual_stderr == expected_stderr,
            "stdout_reason": classify(case["id"], expected_stdout, actual_stdout),
            "stderr_reason": classify(case["id"], expected_stderr, actual_stderr),
            "expected_stdout_len": len(expected_stdout),
            "actual_stdout_len": len(actual_stdout),
            "expected_stderr_len": len(expected_stderr),
            "actual_stderr_len": len(actual_stderr),
        })

    (scratch / "results.json").write_text(json.dumps(results, indent=1))

    full = [r for r in results if r["exit_match"] and r["stdout_match"] and r["stderr_match"]]
    print(f"cases: {len(results)}")
    print(f"fully reproducing: {len(full)}")
    print(f"exit mismatches: {sum(1 for r in results if not r['exit_match'])}")
    print(f"stdout mismatches: {sum(1 for r in results if not r['stdout_match'])}")
    print(f"stderr mismatches: {sum(1 for r in results if not r['stderr_match'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
