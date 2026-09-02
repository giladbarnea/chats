#!/usr/bin/env python3
"""The two operator claims with no counterpart, measured on both live routes.

`test_search_operators.py` holds 22 claims. 20 have a counterpart in the contract
corpus or in `rust/search_query.rs`, whose own comment says three of them were
migrated deliberately. **These two do not: an operator term satisfied by, or
negated against, the SUMMARY FACET.** The corpus covers summary facets and
operators, never together.

**Measured rather than argued, while both routes still exist.** The fixtures are
built the way `_write_session` builds them, so the shape is the claim's own.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"
NATIVE = PROJECT_ROOT / "target" / "release" / "ch"


def write_session(path: Path, texts: list[str], summary: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if summary is not None:
        lines.append(json.dumps(
            {"type": "summary", "summary": summary, "leafUuid": f"{path.stem}-leaf"}
        ))
    lines += [
        json.dumps({
            "type": "user", "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-operators",
            "message": {"role": "user", "content": text},
        })
        for text in texts
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ids(executable: Path, pattern: str, home: Path) -> tuple[int, list[str]]:
    environment = {**os.environ, "HOME": str(home), "COLUMNS": "96", "TERM": "dumb"}
    completed = subprocess.run(
        [str(executable), "search", pattern, "-ll", "--color", "never", "--no-paging"],
        env=environment, capture_output=True, check=False,
    )
    return completed.returncode, completed.stdout.decode().split()


CLAIMS = {
    "and_term_satisfied_by_summary_facet": (
        {"summary-carries-term": (["opname-bravo lives in a message"],
                                  "summary mentions opname-alpha")},
        "opname-alpha AND opname-bravo",
        ["summary-carries-term"],
    ),
    "not_excludes_when_negated_term_in_summary": (
        {"summary-has-excluded": (["opname-alpha in message"],
                                  "summary mentions opname-bravo"),
         "clean-session": (["opname-alpha in message"], "unrelated summary")},
        "opname-alpha NOT opname-bravo",
        ["clean-session"],
    ),
}

for name, (sessions, pattern, expected) in CLAIMS.items():
    with tempfile.TemporaryDirectory() as scratch:
        home = Path(scratch) / "home"
        for stem, (texts, summary) in sessions.items():
            write_session(home / ".claude" / "projects" / "proj" / f"{stem}.jsonl",
                          texts, summary)
        legacy = ids(LEGACY, pattern, home)
        native = ids(NATIVE, pattern, home)
    print(f"{name}")
    print(f"    pattern   {pattern!r}")
    print(f"    claim     exit 0, ids {expected}")
    print(f"    ch-legacy exit {legacy[0]}, ids {legacy[1]}")
    print(f"    ch        exit {native[0]}, ids {native[1]}")
    print(f"    ROUTES AGREE: {legacy == native}    "
          f"CLAIM HOLDS ON THE PORT: {native == (0, expected)}")
