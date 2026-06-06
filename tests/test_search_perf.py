#!/usr/bin/env python3
"""Performance budgets for hot-path queries against the real session pool."""

from __future__ import annotations

import os
import subprocess
import time


def _time_ch(args: list[str]) -> tuple[int, float, bytes]:
    """Run `ch` end-to-end and return (returncode, elapsed_ms, stderr)."""
    start = time.perf_counter()
    result = subprocess.run(
        ["uv", "run", "ch", *args],
        check=False,
        capture_output=True,
    )
    return result.returncode, (time.perf_counter() - start) * 1000, result.stderr


def test_search_mafter_4h_list_under_1000ms() -> None:
    """`ch search . -ma 4h --list` must complete within 1000ms end-to-end."""
    returncode, elapsed_ms, stderr = _time_ch(["search", ".", "-ma", "4h", "--list"])

    assert returncode in (0, 1), (
        f"`ch search . -ma 4h --list` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1000, (
        f"`ch search . -ma 4h --list` took {elapsed_ms:.0f}ms; budget is 1000ms."
    )


def test_recent_index_dir_filter_under_1000ms() -> None:
    """`ch -1 -d ~/.claude` must complete within 1000ms end-to-end.

    `~/.claude` is a stable, always-present directory that is itself a recent
    session cwd (config edits), so the newest-first cwd probe short-circuits
    near the top of the pool instead of relying on a project checkout existing.
    """
    # This stays fast only as long as the most recent ~/.claude session sits near the top of the pool
    target_dir = os.path.expanduser("~/.claude")
    returncode, elapsed_ms, stderr = _time_ch(["-1", "-d", target_dir])

    assert returncode in (0, 1), (
        f"`ch -1 -d {target_dir}` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1000, (
        f"`ch -1 -d {target_dir}` took {elapsed_ms:.0f}ms; budget is 1000ms."
    )


def test_recent_index_mafter_4h_under_1000ms() -> None:
    """`ch -1 -ma 4h` must complete within 1000ms end-to-end."""
    returncode, elapsed_ms, stderr = _time_ch(["-1", "-ma", "4h"])

    assert returncode in (0, 1), (
        f"`ch -1 -ma 4h` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 1000, (
        f"`ch -1 -ma 4h` took {elapsed_ms:.0f}ms; budget is 1000ms."
    )


def test_search_dir_filter_list_under_2000ms() -> None:
    """`ch search . -l -d .` must complete within 2000ms end-to-end."""
    returncode, elapsed_ms, stderr = _time_ch(["search", ".", "-l", "-d", "."])

    assert returncode in (0, 1), (
        f"`ch search . -l -d .` exited with {returncode}. "
        f"stderr: {stderr.decode(errors='replace')!r}"
    )
    assert elapsed_ms < 2000, (
        f"`ch search . -l -d .` took {elapsed_ms:.0f}ms; budget is 2000ms."
    )
