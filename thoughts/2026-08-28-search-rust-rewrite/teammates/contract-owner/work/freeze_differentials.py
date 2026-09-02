#!/usr/bin/env python3
"""Freeze the three live differentials that would not survive the deletion slice.

Three instruments compare two live routes with nothing stored, so the day the
Python search authority is deleted they stop being runnable — not broken, over.
Their expected answers exist only as "whatever Python said a moment ago".

This records Python's side once, from `ch-legacy` explicitly rather than from
`ch` — today they are the same bytes because `ch` execs its sibling, but the
record has to name the oracle it came from, not the route that happens to reach
it.

The frozen sets are stamped like the corpora and re-bless through the same path,
so freezing early costs nothing when the oracle next moves.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).parent
sys.path.insert(0, str(WORK))
sys.path.insert(0, "/Users/giladbarnea/dev/chats/tests")

import oracle_digest  # noqa: E402
import test_search_command_contract as contract  # noqa: E402

TARGET = contract.PROJECT_ROOT / "tests" / "data" / "search-frozen-differentials"


def materialize(corpus: contract.Corpus, root: Path) -> Path:
    home = root / corpus.name / "home"
    shutil.copytree(corpus.root / "home", home)
    for relative_path, mtime in corpus.mtimes.items():
        os.utime(home / relative_path, (mtime, mtime))
    return home


def record(home: Path) -> dict:
    """Record the Python route's answer for every case the three tests compare."""
    patterns = []
    for name in sorted(contract.query_pattern_corpus.DEFECT_PATTERNS):
        case = {
            "id": f"defect:{name}",
            "arguments": [contract.query_pattern_corpus.DEFECT_PATTERNS[name], "-ll"],
            "columns": 96,
            "color": False,
        }
        completed = contract._run_search(contract.CHECKOUT_LEGACY, case, home)
        patterns.append({
            "id": case["id"],
            "arguments": case["arguments"],
            "columns": case["columns"],
            "color": case["color"],
            "exit_status": completed.returncode,
            "stdout": contract._normalize(completed.stdout, home).decode("utf-8", "surrogateescape"),
        })

    generated = contract.query_pattern_corpus.generate_patterns(
        contract.GENERATED_PATTERN_SEED, contract.GENERATED_PATTERN_COUNT
    )
    for index, pattern in enumerate(generated):
        columns = contract.GENERATED_PATTERN_WIDTHS[index % len(contract.GENERATED_PATTERN_WIDTHS)]
        case = {
            "id": f"generated:{index}",
            "arguments": [pattern, "-l", "--color", "always", "--no-paging"],
            "columns": columns,
            "color": True,
        }
        completed = contract._run_search(contract.CHECKOUT_LEGACY, case, home)
        patterns.append({
            "id": case["id"],
            "arguments": case["arguments"],
            "columns": columns,
            "color": True,
            "exit_status": completed.returncode,
            "stdout": contract._normalize(completed.stdout, home).decode("utf-8", "surrogateescape"),
        })

    terminal = []
    for name, arguments in contract.TERMINAL_SHAPES:
        for columns in contract.TERMINAL_WIDTHS:
            status, output = contract._run_search_on_terminal(
                contract.CHECKOUT_LEGACY, arguments, home, columns=columns
            )
            terminal.append({
                "id": f"{name}:{columns}",
                "arguments": arguments,
                "columns": columns,
                "exit_status": status,
                "output": contract._normalize(output, home).decode("utf-8", "surrogateescape"),
            })

    return {"patterns": patterns, "terminal": terminal}


def main() -> None:
    contract_corpus = contract.CORPORA[0]
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.mkdir(parents=True)

    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        home = materialize(contract_corpus, Path(scratch))
        recorded = record(home)

    (TARGET / "frozen.json").write_text(json.dumps(recorded, indent=1) + "\n", encoding="utf-8")
    (TARGET / "ORACLE.json").write_text(
        json.dumps(
            {
                "revision": subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(contract.PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip(),
                "source_digest": oracle_digest.oracle_route_digest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"froze {len(recorded['patterns'])} pattern cases and "
        f"{len(recorded['terminal'])} terminal cases"
    )


if __name__ == "__main__":
    main()
