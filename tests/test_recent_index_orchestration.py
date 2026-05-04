#!/usr/bin/env python3
"""Behavior tests for recent negative-index orchestration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from conversations import PoolFilter, SessionPool, _try_resolve_conversation_file, commands



def _write_claude_session(path: Path, *, cwd: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([
            json.dumps({
                "type": "summary",
                "summary": text,
                "leafUuid": f"{path.stem}-leaf",
            }),
            json.dumps({
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": cwd,
                "message": {"role": "user", "content": text},
            }),
        ])
        + "\n",
        encoding="utf-8",
    )



def test_recent_index_dir_filter_skips_eager_metadata_loading(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-1 --dir` should not preload per-file metadata when no date filters are active."""
    home = tmp_path / "home"
    target_dir = tmp_path / "target-project"
    other_dir = tmp_path / "other-project"
    monkeypatch.setattr(Path, "home", lambda: home)

    matching_path = home / ".claude" / "projects" / "proj" / "matching.jsonl"
    other_path = home / ".claude" / "projects" / "proj" / "other.jsonl"
    _write_claude_session(matching_path, cwd=str(target_dir), text="matching cwd")
    _write_claude_session(other_path, cwd=str(other_dir), text="other cwd")

    os.utime(matching_path, (1_700_001_000, 1_700_001_000))
    os.utime(other_path, (1_700_000_000, 1_700_000_000))

    def fail_on_metadata_load(_session_file: Path):
        raise AssertionError(
            "Expected dir-filtered recent-index resolution without date filters to "
            "avoid eager _load_conversation_metadata() calls."
        )

    monkeypatch.setattr(commands, "_load_conversation_metadata", fail_on_metadata_load)

    resolved_path, ambiguous = _try_resolve_conversation_file(
        "-1",
        pool_filter=PoolFilter(dir=str(target_dir)),
    )

    assert ambiguous == [], f"Expected no ambiguity for exact cwd match. Got: {ambiguous!r}"
    assert resolved_path == matching_path, (
        "Expected `-1` with an exact dir filter to resolve to the newest matching "
        f"session. Got: {resolved_path!r}"
    )



def test_recent_index_dir_filter_uses_newest_first_stat_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-1 --dir` should use newest-first stat mtime ordering, not discovery order."""
    home = tmp_path / "home"
    target_dir = tmp_path / "target-project"
    other_dir = tmp_path / "other-project"
    monkeypatch.setattr(Path, "home", lambda: home)

    older_matching_path = home / ".claude" / "projects" / "proj" / "older-match.jsonl"
    newer_nonmatching_path = home / ".claude" / "projects" / "proj" / "newer-other.jsonl"
    newest_matching_path = home / ".claude" / "projects" / "proj" / "newest-match.jsonl"

    _write_claude_session(older_matching_path, cwd=str(target_dir), text="older match")
    _write_claude_session(
        newer_nonmatching_path,
        cwd=str(other_dir),
        text="newer non-match",
    )
    _write_claude_session(newest_matching_path, cwd=str(target_dir), text="newest match")

    os.utime(older_matching_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_nonmatching_path, (1_700_002_000, 1_700_002_000))
    os.utime(newest_matching_path, (1_700_001_000, 1_700_001_000))

    original_passes_path_for_index = PoolFilter.passes_path_for_index
    inspected_paths: list[Path] = []
    candidate_paths = [newest_matching_path, newer_nonmatching_path, older_matching_path]

    def tracked_passes_path_for_index(self: PoolFilter, path: Path) -> bool:
        inspected_paths.append(path)
        return original_passes_path_for_index(self, path)

    with (
        patch.object(
            PoolFilter,
            "passes_path_for_index",
            tracked_passes_path_for_index,
        ),
        patch.object(SessionPool, "discover", return_value=SessionPool.from_files(candidate_paths)),
    ):
        resolved_path, ambiguous = _try_resolve_conversation_file(
            "-1",
            pool_filter=PoolFilter(dir=str(target_dir)),
        )

    assert ambiguous == [], f"Expected no ambiguity for exact cwd match. Got: {ambiguous!r}"
    assert resolved_path == newest_matching_path, (
        "Expected `-1` with an exact dir filter to resolve to the newest matching "
        f"session by stat mtime. Got: {resolved_path!r}"
    )
    assert inspected_paths == [newer_nonmatching_path, newest_matching_path], (
        "Expected dir-filtered `-1` resolution to inspect candidates in newest-first "
        f"stat order and stop after the first match. Got inspected paths: {inspected_paths!r}"
    )
