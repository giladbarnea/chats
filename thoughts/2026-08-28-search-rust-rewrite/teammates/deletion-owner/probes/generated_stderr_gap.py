#!/usr/bin/env python3
"""How many generated rows would go red if that gate compared stderr.

`g5-runner` reported three rows carrying the ruled warning divergence and
invisible because `test_generated_patterns_match_the_recording` compares
`returncode` and `stdout` only. This measures the whole group rather than the
family that was asked about: a strengthening is only cheap if the rows it turns
red are exactly the ruled ones.

Run as a pytest module so the session fixtures build and place the launcher.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

import query_pattern_corpus
from test_search_command_contract import (
    GENERATED_PATTERN_COUNT,
    GENERATED_PATTERN_SEED,
    GENERATED_PATTERN_WIDTHS,
    _normalize,
    _run_search,
)
from test_search_command_contract import contract_home  # noqa: F401

BASELINE = (
    Path(__file__).resolve().parents[5]
    / "tests" / "data" / "legacy-selection-baseline" / "legacy-selection-baseline.json"
)


def test_report_the_generated_stderr_gap(checkout_built_ch: Path, contract_home: Path) -> None:
    rows = json.loads(BASELINE.read_text())["groups"]["generated-patterns"]
    patterns = query_pattern_corpus.generate_patterns(
        GENERATED_PATTERN_SEED, GENERATED_PATTERN_COUNT
    )
    differing = []
    for index, pattern in enumerate(patterns):
        columns = GENERATED_PATTERN_WIDTHS[index % len(GENERATED_PATTERN_WIDTHS)]
        key = f"generated-{index}"
        case = {
            "id": key,
            "arguments": [pattern, "-l", "--color", "always", "--no-paging"],
            "columns": columns,
            "color": True,
        }
        actual = _run_search(checkout_built_ch, case, contract_home)
        got = _normalize(actual.stderr, contract_home)
        want = _normalize(base64.b64decode(rows[key]["stderr"]), contract_home)
        if got != want:
            differing.append((key, pattern, want, got))
    print(f"\n{len(differing)} of {len(patterns)} generated rows differ on stderr")
    for key, pattern, want, got in differing:
        print(f"  {key}  {pattern!r}")
        print(f"    recorded: {want[:160]!r}")
        print(f"    native:   {got[:160]!r}")
