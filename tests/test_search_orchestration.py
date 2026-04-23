#!/usr/bin/env python3
"""Behavior tests for search orchestration across the session pool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import conversations.commands as commands
from conversations import ConversationFlags, SearchOutputMode


def _write_session(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "summary",
                        "summary": text,
                        "leafUuid": f"{path.stem}-leaf",
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "cwd": "/tmp/search-orchestration",
                        "message": {"role": "user", "content": text},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_cmd_search_succeeds_when_unrelated_nonmatch_metadata_would_fail(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A no-date search should not preload metadata for unrelated nonmatching sessions."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    matching_path = home / ".claude" / "projects" / "proj" / "match.jsonl"
    nonmatching_path = home / ".claude" / "projects" / "proj" / "other.jsonl"
    _write_session(matching_path, "slice-3-lazy-metadata-needle")
    _write_session(nonmatching_path, "totally different content")

    real_load_conversation_metadata = commands._load_conversation_metadata

    def load_conversation_metadata(session_file: Path):
        if session_file == nonmatching_path:
            raise AssertionError(
                "Expected cmd_search to avoid loading metadata for unrelated "
                f"nonmatching sessions. Got metadata load for: {session_file}"
            )
        return real_load_conversation_metadata(session_file)

    monkeypatch.setattr(
        commands,
        "_load_conversation_metadata",
        load_conversation_metadata,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "slice-3-lazy-metadata-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected list search to succeed even when metadata loading would fail for "
        f"an unrelated nonmatch. Got exit code: {exc_info.value.code}"
    )
    stdout = capsys.readouterr().out
    assert "match" in stdout, (
        "Expected the matching session to still be reported after the lazy metadata "
        f"change. Got stdout:\n{stdout}"
    )
    assert "other" not in stdout, (
        "Expected the unrelated nonmatching session not to appear in output. "
        f"Got stdout:\n{stdout}"
    )


def test_cmd_search_does_not_render_noncandidate_sessions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A rare-token search should skip expensive render confirmation for noncandidate files."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    matching_path = home / ".claude" / "projects" / "proj" / "match.jsonl"
    noncandidate_path = home / ".claude" / "projects" / "proj" / "other.jsonl"
    _write_session(matching_path, "slice-4-render-skip-needle")
    _write_session(noncandidate_path, "slice-4-render-skip-noncandidate")

    real_render_message_inner_xml = commands.render_message_inner_xml
    rendered_texts: list[str] = []

    def render_message_inner_xml(message, flags, tool_id_map=None):
        rendered_texts.append(message.text)
        return real_render_message_inner_xml(message, flags, tool_id_map)

    monkeypatch.setattr(
        commands,
        "render_message_inner_xml",
        render_message_inner_xml,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "slice-4-render-skip-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected search to succeed while avoiding render confirmation for "
        f"noncandidate files. Got exit code: {exc_info.value.code}"
    )
    stdout = capsys.readouterr().out
    assert "match" in stdout, (
        "Expected the matching session to remain visible after introducing "
        f"candidate/confirm search. Got stdout:\n{stdout}"
    )
    assert "slice-4-render-skip-noncandidate" not in rendered_texts, (
        "Expected cmd_search not to XML-render messages from files whose raw "
        f"content cannot match the query. Got rendered texts: {rendered_texts!r}"
    )
