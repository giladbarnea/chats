#!/usr/bin/env python3
"""Behavior tests for search output modes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conversations import ConversationFlags, SearchOutputMode, cmd_search


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
