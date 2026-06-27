#!/usr/bin/env python3
"""Behavior tests for recent negative-index orchestration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from chats import PoolFilter, SessionPool, _try_resolve_conversation_file
import chats.commands.resolve as resolve_commands



def _write_claude_session(
    path: Path,
    *,
    cwd: str,
    text: str,
    timestamp: str = "2025-01-01T00:00:00Z",
) -> None:
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
                "timestamp": timestamp,
                "cwd": cwd,
                "message": {"role": "user", "content": text},
            }),
        ])
        + "\n",
        encoding="utf-8",
    )



def _write_pi_session(
    path: Path,
    *,
    session_id: str,
    cwd: str,
    text: str,
    timestamp: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([
            json.dumps({
                "type": "session",
                "id": session_id,
                "timestamp": timestamp,
                "cwd": cwd,
                "version": 3,
            }),
            json.dumps({
                "type": "message",
                "id": f"{session_id}-message",
                "timestamp": timestamp,
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )



def _write_codex_session(
    path: Path,
    *,
    session_id: str,
    cwd: str,
    text: str,
    timestamp: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([
            json.dumps({
                "type": "session_meta",
                "timestamp": timestamp,
                "payload": {"id": session_id, "cwd": cwd},
            }),
            json.dumps({
                "type": "response_item",
                "timestamp": timestamp,
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )



def test_recent_index_uses_jsonl_last_timestamp_instead_of_filesystem_mtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-1` should resolve by the session's last in-band timestamp, not file mtime."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    semantically_newer_path = (
        home / ".claude" / "projects" / "proj" / "semantic-new.jsonl"
    )
    filesystem_newer_path = home / ".claude" / "projects" / "proj" / "fs-new.jsonl"
    _write_claude_session(
        semantically_newer_path,
        cwd="/tmp/project",
        text="new by jsonl timestamp",
        timestamp="2025-05-01T00:00:00Z",
    )
    _write_claude_session(
        filesystem_newer_path,
        cwd="/tmp/project",
        text="new by filesystem mtime only",
        timestamp="2025-01-01T00:00:00Z",
    )

    os.utime(semantically_newer_path, (1_700_000_000, 1_700_000_000))
    os.utime(filesystem_newer_path, (1_700_001_000, 1_700_001_000))

    resolved_path, ambiguous = _try_resolve_conversation_file("-1")

    assert ambiguous == [], (
        f"Expected no ambiguity for recent-index lookup. Got: {ambiguous!r}"
    )
    assert resolved_path == semantically_newer_path, (
        "Expected `-1` to resolve by the newest JSONL timestamp, even when another "
        f"file has a newer filesystem mtime. Got: {resolved_path!r}"
    )



def test_recent_index_jsonl_timestamp_order_spans_claude_pi_and_codex(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Recent-index JSONL recency should work across the unified provider pool."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    claude_path = home / ".claude" / "projects" / "proj" / "claude-old.jsonl"
    pi_path = home / ".pi" / "agent" / "sessions" / "proj" / "pi-middle.jsonl"
    codex_path = home / ".codex" / "sessions" / "2026" / "01" / "codex-new.jsonl"
    _write_claude_session(
        claude_path,
        cwd="/tmp/claude",
        text="claude old",
        timestamp="2025-01-01T00:00:00Z",
    )
    _write_pi_session(
        pi_path,
        session_id="pi-middle-id",
        cwd="/tmp/pi",
        text="pi middle",
        timestamp="2025-03-01T00:00:00Z",
    )
    _write_codex_session(
        codex_path,
        session_id="codex-new-id",
        cwd="/tmp/codex",
        text="codex new",
        timestamp="2025-05-01T00:00:00Z",
    )

    os.utime(claude_path, (1_700_003_000, 1_700_003_000))
    os.utime(pi_path, (1_700_002_000, 1_700_002_000))
    os.utime(codex_path, (1_700_001_000, 1_700_001_000))

    resolved_newest, newest_ambiguous = _try_resolve_conversation_file("-1")
    resolved_middle, middle_ambiguous = _try_resolve_conversation_file("-2")
    resolved_oldest, oldest_ambiguous = _try_resolve_conversation_file("-3")

    assert newest_ambiguous == [], (
        f"Expected no ambiguity for newest lookup. Got: {newest_ambiguous!r}"
    )
    assert middle_ambiguous == [], (
        f"Expected no ambiguity for middle lookup. Got: {middle_ambiguous!r}"
    )
    assert oldest_ambiguous == [], (
        f"Expected no ambiguity for oldest lookup. Got: {oldest_ambiguous!r}"
    )
    assert resolved_newest == codex_path, (
        "Expected Codex to win by the newest JSONL timestamp despite oldest fs mtime. "
        f"Got: {resolved_newest!r}"
    )
    assert resolved_middle == pi_path, (
        "Expected PI to resolve as the middle JSONL timestamp. "
        f"Got: {resolved_middle!r}"
    )
    assert resolved_oldest == claude_path, (
        "Expected Claude to resolve as the oldest JSONL timestamp despite newest fs mtime. "
        f"Got: {resolved_oldest!r}"
    )



def test_recent_index_excludes_sidechains_before_timestamp_probe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Recent-index ordering should not read timestamps from excluded sidechains."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    main_path = home / ".claude" / "projects" / "proj" / "main.jsonl"
    sidechain_path = (
        home
        / ".claude"
        / "projects"
        / "proj"
        / "main"
        / "subagents"
        / "agent-side.jsonl"
    )
    _write_claude_session(
        main_path,
        cwd="/tmp/project",
        text="main session",
        timestamp="2025-01-01T00:00:00Z",
    )
    _write_claude_session(
        sidechain_path,
        cwd="/tmp/project",
        text="sidechain session",
        timestamp="2025-05-01T00:00:00Z",
    )

    real_get_jsonl_last_timestamp = resolve_commands.get_jsonl_last_timestamp
    probed_paths: list[Path] = []

    def tracked_get_jsonl_last_timestamp(path: Path):
        probed_paths.append(path)
        if path == sidechain_path:
            raise AssertionError(
                "Expected recent-index resolution to exclude sidechains before "
                "probing JSONL timestamps."
            )
        return real_get_jsonl_last_timestamp(path)

    monkeypatch.setattr(
        resolve_commands,
        "get_jsonl_last_timestamp",
        tracked_get_jsonl_last_timestamp,
    )

    resolved_path, ambiguous = _try_resolve_conversation_file(
        "-1",
        [sidechain_path, main_path],
    )

    assert ambiguous == [], (
        f"Expected no ambiguity for recent-index lookup. Got: {ambiguous!r}"
    )
    assert resolved_path == main_path, (
        "Expected sidechains to stay excluded from recent-index resolution. "
        f"Got: {resolved_path!r}"
    )
    assert sidechain_path not in probed_paths, (
        "Expected sidechain timestamp not to be probed. "
        f"Probed paths: {probed_paths!r}"
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

    monkeypatch.setattr(
        resolve_commands,
        "_load_conversation_metadata",
        fail_on_metadata_load,
    )

    resolved_path, ambiguous = _try_resolve_conversation_file(
        "-1",
        pool_filter=PoolFilter(dir=str(target_dir)),
    )

    assert ambiguous == [], f"Expected no ambiguity for exact cwd match. Got: {ambiguous!r}"
    assert resolved_path == matching_path, (
        "Expected `-1` with an exact dir filter to resolve to the newest matching "
        f"session. Got: {resolved_path!r}"
    )



def test_recent_index_dir_filter_uses_newest_first_jsonl_timestamp_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-1 --dir` should use newest-first JSONL timestamp ordering, not discovery order."""
    home = tmp_path / "home"
    target_dir = tmp_path / "target-project"
    other_dir = tmp_path / "other-project"
    monkeypatch.setattr(Path, "home", lambda: home)

    older_matching_path = home / ".claude" / "projects" / "proj" / "older-match.jsonl"
    newer_nonmatching_path = home / ".claude" / "projects" / "proj" / "newer-other.jsonl"
    newest_matching_path = home / ".claude" / "projects" / "proj" / "newest-match.jsonl"

    _write_claude_session(
        older_matching_path,
        cwd=str(target_dir),
        text="older match",
        timestamp="2025-01-01T00:00:00Z",
    )
    _write_claude_session(
        newer_nonmatching_path,
        cwd=str(other_dir),
        text="newer non-match",
        timestamp="2025-03-01T00:00:00Z",
    )
    _write_claude_session(
        newest_matching_path,
        cwd=str(target_dir),
        text="newest match",
        timestamp="2025-02-01T00:00:00Z",
    )

    os.utime(older_matching_path, (1_700_002_000, 1_700_002_000))
    os.utime(newer_nonmatching_path, (1_700_000_000, 1_700_000_000))
    os.utime(newest_matching_path, (1_700_001_000, 1_700_001_000))

    original_passes_path_for_index = PoolFilter.passes_path_for_index
    real_get_jsonl_last_timestamp = resolve_commands.get_jsonl_last_timestamp
    inspected_paths: list[Path] = []
    timestamp_probed_paths: list[Path] = []
    candidate_paths = [
        older_matching_path,
        newest_matching_path,
        newer_nonmatching_path,
    ]

    def tracked_passes_path_for_index(self: PoolFilter, path: Path) -> bool:
        inspected_paths.append(path)
        return original_passes_path_for_index(self, path)

    def tracked_get_jsonl_last_timestamp(path: Path):
        timestamp_probed_paths.append(path)
        return real_get_jsonl_last_timestamp(path)

    monkeypatch.setattr(
        resolve_commands,
        "get_jsonl_last_timestamp",
        tracked_get_jsonl_last_timestamp,
    )

    with (
        patch.object(
            PoolFilter,
            "passes_path_for_index",
            tracked_passes_path_for_index,
        ),
        patch.object(
            SessionPool,
            "discover",
            return_value=SessionPool.from_files(candidate_paths),
        ),
    ):
        resolved_path, ambiguous = _try_resolve_conversation_file(
            "-1",
            pool_filter=PoolFilter(dir=str(target_dir)),
        )

    assert ambiguous == [], (
        f"Expected no ambiguity for exact cwd match. Got: {ambiguous!r}"
    )
    assert resolved_path == newest_matching_path, (
        "Expected `-1` with an exact dir filter to resolve to the newest matching "
        f"session by JSONL timestamp. Got: {resolved_path!r}"
    )
    assert inspected_paths == candidate_paths, (
        "Expected dir-filtered recent-index resolution to inspect cwd before "
        f"timestamp sorting. Got inspected paths: {inspected_paths!r}"
    )
    assert timestamp_probed_paths == [older_matching_path, newest_matching_path], (
        "Expected timestamp sorting to run only after cwd filtering, while still "
        "choosing the newest matching JSONL timestamp. Got timestamp probes: "
        f"{timestamp_probed_paths!r}"
    )
