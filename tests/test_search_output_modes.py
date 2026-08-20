#!/usr/bin/env python3
"""Behavior tests for search output modes."""

from __future__ import annotations

import json
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from chats import ConversationFlags, SearchOutputMode, cmd_search


class _FlushRecordingStream:
    def __init__(self) -> None:
        self.content = ""
        self.flush_snapshots: list[str] = []

    def write(self, content: str) -> int:
        self.content += content
        return len(content)

    def flush(self) -> None:
        self.flush_snapshots.append(self.content)


def test_cmd_search_only_id_flushes_each_id_as_it_streams(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Each matching ID must become visible before the remaining scan completes."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    older_path = home / ".codex" / "sessions" / "older.jsonl"
    newer_path = home / ".codex" / "sessions" / "newer.jsonl"
    for path, session_id in (
        (older_path, "older-id"),
        (newer_path, "newer-id"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"type": "session_meta", "payload": {"id": session_id}})
            + "\n"
            + json.dumps({
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "flush-streamed-id"}
                    ],
                },
            })
            + "\n",
            encoding="utf-8",
        )
    os.utime(older_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_path, (1_700_001_000, 1_700_001_000))

    stream = _FlushRecordingStream()
    with redirect_stdout(stream), pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "flush-streamed-id",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    assert exc_info.value.code == 0, (
        "Expected the streamed ID search to succeed. "
        f"Got exit code: {exc_info.value.code}, stdout: {stream.content!r}"
    )
    assert stream.content == "newer-id\nolder-id\n", (
        "Expected flushing to preserve the exact newest-first stdout bytes. "
        f"Got: {stream.content!r}"
    )
    assert stream.flush_snapshots == [
        "newer-id\n",
        "newer-id\nolder-id\n",
    ], (
        "Expected stdout to flush after each ID, not only after the full scan. "
        f"Got flush snapshots: {stream.flush_snapshots!r}"
    )


def test_dot_projection_flushes_each_id_as_it_streams(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The narrow dot projection must use the same flushed ID output contract."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".pi" / "agent" / "sessions" / "project" / "pi.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({
            "type": "session",
            "version": 3,
            "id": "pi-projection-id",
            "cwd": "/tmp/pi",
        })
        + "\n"
        + json.dumps({
            "type": "message",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "visible projection text"}],
            },
        })
        + "\n",
        encoding="utf-8",
    )

    stream = _FlushRecordingStream()
    with redirect_stdout(stream), pytest.raises(SystemExit) as exc_info:
        cmd_search(
            ".",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    assert exc_info.value.code == 0, (
        "Expected the dot projection to find the visible Pi session. "
        f"Got exit code: {exc_info.value.code}, stdout: {stream.content!r}"
    )
    assert stream.content == "pi-projection-id\n", (
        "Expected dot projection flushing to preserve exact stdout bytes. "
        f"Got: {stream.content!r}"
    )
    assert stream.flush_snapshots == ["pi-projection-id\n"], (
        "Expected the dot projection to flush its ID immediately. "
        f"Got flush snapshots: {stream.flush_snapshots!r}"
    )


def test_cmd_search_only_id_mode_prints_plain_session_id(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`output_mode=ONLY_ID` should emit only the matching session identifier."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".codex" / "sessions" / "rollout-abc.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}})
        + "\n"
        + json.dumps({
            "type": "response_item",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "unique-search-output-mode"}
                ],
            },
        })
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "unique-search-output-mode",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected search ONLY_ID mode to exit successfully when a session matches. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == "abc", (
        "Expected ONLY_ID search mode to print only the matching session id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "history_path:" not in captured.out, (
        "Expected ONLY_ID search mode to suppress metadata output. "
        f"Got stdout:\n{captured.out}"
    )


def test_cmd_search_full_mode_prints_entire_matching_conversation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Full search output should render every visible message from a matching session."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "full-search.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "\n".join([
            json.dumps({
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp/search-full-mode",
                "message": {
                    "role": "user",
                    "content": "context that did not match directly",
                },
            }),
            json.dumps({
                "type": "assistant",
                "timestamp": "2025-01-01T00:00:01Z",
                "cwd": "/tmp/search-full-mode",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "answer with unique-full-mode-needle",
                        }
                    ],
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "unique-full-mode-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.FULL,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected FULL search mode to exit successfully when a session matches. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "context that did not match directly" in captured.out, (
        "Expected FULL search mode to render nonmatching messages from the same "
        f"matching conversation. Got stdout:\n{captured.out}"
    )
    assert "answer with unique-full-mode-needle" in captured.out, (
        "Expected FULL search mode to keep rendering the matched message. "
        f"Got stdout:\n{captured.out}"
    )


def test_cmd_search_full_mode_prints_conversation_for_summary_match(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A summary-only match is still a matching conversation, so full mode renders it."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "summary-full.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "\n".join([
            json.dumps({
                "type": "summary",
                "summary": "summary-only-full-mode-needle",
                "leafUuid": "summary-full-leaf",
            }),
            json.dumps({
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp/search-full-mode",
                "message": {
                    "role": "user",
                    "content": "message body without the summary token",
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "summary-only-full-mode-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.FULL,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected FULL search mode to succeed for a summary-only match. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "matched_summary" in captured.out, (
        "Expected summary matches to remain visible in metadata. "
        f"Got stdout:\n{captured.out}"
    )
    assert "message body without the summary token" in captured.out, (
        "Expected FULL search mode to render the conversation body even when "
        f"only the summary matched. Got stdout:\n{captured.out}"
    )


def test_cmd_search_lists_newest_match_first(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """List search should display newer matching sessions before older ones."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    older_path = home / ".claude" / "projects" / "proj" / "older.jsonl"
    newer_path = home / ".claude" / "projects" / "proj" / "newer.jsonl"
    older_path.parent.mkdir(parents=True, exist_ok=True)

    older_path.write_text(
        "\n".join([
            json.dumps({
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp/search-order",
                "message": {
                    "role": "user",
                    "content": "shared-ordering-needle older",
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )
    newer_path.write_text(
        "\n".join([
            json.dumps({
                "type": "user",
                "timestamp": "2025-01-02T00:00:00Z",
                "cwd": "/tmp/search-order",
                "message": {
                    "role": "user",
                    "content": "shared-ordering-needle newer",
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )

    # Streaming display emits in scan order (newest first by filesystem mtime),
    # so pin the mtimes instead of relying on sub-tick write timing.
    import os

    os.utime(older_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_path, (1_700_001_000, 1_700_001_000))

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "shared-ordering-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected list search to succeed when both sessions match. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    newer_index = captured.out.index(
        "history_path: ~/.claude/projects/proj/newer.jsonl"
    )
    older_index = captured.out.index(
        "history_path: ~/.claude/projects/proj/older.jsonl"
    )
    assert newer_index < older_index, (
        "Expected search results to be displayed newest-first. "
        f"Got stdout:\n{captured.out}"
    )
    assert "---" not in captured.out, (
        "Expected search list mode to omit metadata separators. "
        f"Got stdout:\n{captured.out}"
    )
