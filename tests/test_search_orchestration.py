#!/usr/bin/env python3
"""Behavior tests for search orchestration across the session pool."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from conversations import ConversationFlags, PoolFilter, SearchOutputMode, commands
import conversations.commands.resolve as resolve_commands
import conversations.commands.search as search_commands


def _write_session(
    path: Path,
    text: str,
    *,
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
                "cwd": "/tmp/search-orchestration",
                "message": {"role": "user", "content": text},
            }),
        ])
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

    real_load_conversation_metadata = resolve_commands._load_conversation_metadata

    def load_conversation_metadata(session_file: Path):
        if session_file == nonmatching_path:
            raise AssertionError(
                "Expected cmd_search to avoid loading metadata for unrelated "
                f"nonmatching sessions. Got metadata load for: {session_file}"
            )
        return real_load_conversation_metadata(session_file)

    monkeypatch.setattr(
        resolve_commands,
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

    real_render_message_inner_xml = search_commands.render_message_inner_xml
    rendered_texts: list[str] = []

    def render_message_inner_xml(message, flags, tool_id_map=None):
        rendered_texts.append(message.text)
        return real_render_message_inner_xml(message, flags, tool_id_map)

    monkeypatch.setattr(
        search_commands,
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


def test_cmd_search_scans_candidate_sessions_newest_first(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Search should scan candidate sessions newest-first instead of discovery order."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    older_path = home / ".claude" / "projects" / "proj" / "a-older.jsonl"
    newer_path = home / ".claude" / "projects" / "proj" / "z-newer.jsonl"
    _write_session(older_path, "scan-order-shared-needle")
    _write_session(newer_path, "scan-order-shared-needle")

    import os

    os.utime(older_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_path, (1_700_001_000, 1_700_001_000))

    scanned_paths: list[Path] = []

    def search_hit_for_file(
        conv_file: Path,
        regex,
        pattern_arg: str,
        literal_candidate: str | None,
        flags: ConversationFlags,
        pool_filter,
    ):
        scanned_paths.append(conv_file)

    monkeypatch.setattr(search_commands, "_search_hit_for_file", search_hit_for_file)

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "scan-order-shared-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 1, (
        "Expected the patched search to exit with 1 because no fake hits were returned. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert scanned_paths == [newer_path, older_path], (
        "Expected search to scan newer candidate sessions before older ones, even when "
        f"the filenames would sort the other way. Got scan order: {scanned_paths!r}"
    )


def test_cmd_search_skips_full_parse_for_files_outside_date_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-ma 1h` should not full-parse files whose in-band mtime is older than the cutoff."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    fresh_path = home / ".claude" / "projects" / "proj" / "fresh.jsonl"
    stale_path = home / ".claude" / "projects" / "proj" / "stale.jsonl"

    fresh_iso = (
        (datetime.now(UTC) - timedelta(minutes=5))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    _write_session(fresh_path, "shared-needle-date-skip", timestamp=fresh_iso)
    _write_session(stale_path, "shared-needle-date-skip", timestamp="2020-01-01T00:00:00Z")

    parsed_paths: list[Path] = []
    real_search_conversation_content = search_commands._search_conversation_content

    def tracked_search_conversation_content(
        conv_file: Path,
        content: str,
        regex,
        flags: ConversationFlags,
        pool_filter: PoolFilter,
    ):
        parsed_paths.append(conv_file)
        return real_search_conversation_content(
            conv_file, content, regex, flags, pool_filter
        )

    monkeypatch.setattr(
        search_commands,
        "_search_conversation_content",
        tracked_search_conversation_content,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "shared-needle-date-skip",
            ConversationFlags(color="never", paging=False),
            pool_filter=PoolFilter(mafter="1h"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected the in-window file to be reported. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert stale_path not in parsed_paths, (
        "Expected `cmd_search` with -ma 1h to skip parsing files whose in-band mtime "
        f"is older than the cutoff. Got parsed files: {parsed_paths!r}"
    )
    assert fresh_path in parsed_paths, (
        "Expected the in-window file to still be parsed. "
        f"Got parsed files: {parsed_paths!r}"
    )
