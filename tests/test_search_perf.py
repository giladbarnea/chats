#!/usr/bin/env python3
"""Performance budgets for hot-path queries against the real session pool."""

from __future__ import annotations

import subprocess
import time


def test_search_mafter_4h_list_under_1200ms() -> None:
    """`ccc search . -ma 4h --list` must complete within 1200ms end-to-end."""
    start = time.perf_counter()
    result = subprocess.run(
        ["uv", "run", "ccc", "search", ".", "-ma", "4h", "--list"],
        check=False,
        capture_output=True,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result.returncode in (0, 1), (
        f"`ccc search . -ma 4h --list` exited with {result.returncode}. "
        f"stderr: {result.stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1200, (
        f"`ccc search . -ma 4h --list` took {elapsed_ms:.0f}ms; budget is 1200ms."
    )
