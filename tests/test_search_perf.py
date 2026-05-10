#!/usr/bin/env python3
"""Performance budgets for hot-path queries against the real session pool."""

from __future__ import annotations

import os
import subprocess
import time


def _time_ccc(args: list[str]) -> tuple[int, float, bytes]:
    """Run `ccc` end-to-end and return (returncode, elapsed_ms, stderr)."""
    start = time.perf_counter()
    result = subprocess.run(
        ["uv", "run", "ccc", *args],
        check=False,
        capture_output=True,
    )
    return result.returncode, (time.perf_counter() - start) * 1000, result.stderr


def test_search_mafter_4h_list_under_1000ms() -> None:
    """`ccc search . -ma 4h --list` must complete within 1000ms end-to-end."""
    returncode, elapsed_ms, stderr = _time_ccc(["search", ".", "-ma", "4h", "--list"])

    assert returncode in (0, 1), (
        f"`ccc search . -ma 4h --list` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1000, (
        f"`ccc search . -ma 4h --list` took {elapsed_ms:.0f}ms; budget is 1000ms."
    )


def test_recent_index_dir_filter_under_1000ms() -> None:
    """`ccc -1 -d ~/dev/conversations` must complete within 1000ms end-to-end."""
    target_dir = os.path.expanduser("~/dev/conversations")
    returncode, elapsed_ms, stderr = _time_ccc(["-1", "-d", target_dir])

    assert returncode in (0, 1), (
        f"`ccc -1 -d {target_dir}` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1000, (
        f"`ccc -1 -d {target_dir}` took {elapsed_ms:.0f}ms; budget is 1000ms."
    )


def test_recent_index_mafter_4h_under_1000ms() -> None:
    """`ccc -1 -ma 4h` must complete within 1000ms end-to-end."""
    returncode, elapsed_ms, stderr = _time_ccc(["-1", "-ma", "4h"])

    assert returncode in (0, 1), (
        f"`ccc -1 -ma 4h` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1000, (
        f"`ccc -1 -ma 4h` took {elapsed_ms:.0f}ms; budget is 1000ms."
    )


def test_search_dir_filter_list_under_2000ms() -> None:
    """`ccc search . -l -d .` must complete within 2000ms end-to-end."""
    returncode, elapsed_ms, stderr = _time_ccc(["search", ".", "-l", "-d", "."])

    assert returncode in (0, 1), (
        f"`ccc search . -l -d .` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 2000, (
        f"`ccc search . -l -d .` took {elapsed_ms:.0f}ms; budget is 2000ms."
    )
