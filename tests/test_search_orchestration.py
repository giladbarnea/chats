#!/usr/bin/env python3
"""Behavior tests for search orchestration across the session pool."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from chats import (
    ConversationFlags,
    MessageSelection,
    PoolFilter,
    SearchOutputMode,
    commands,
)
import chats.commands.resolve as resolve_commands
import chats.commands.search as search_commands
import chats.parsing as parsing


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


def _write_hidden_thinking_session(path: Path, hidden_text: str) -> None:
    """Write a session whose only needle is hidden thinking content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "assistant",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-orchestration",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": hidden_text},
                    {"type": "text", "text": "visible answer"},
                ],
            },
        })
        + "\n",
        encoding="utf-8",
    )


def _write_hidden_only_thinking_session(path: Path) -> None:
    """Write a session with no default-visible searchable content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "assistant",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-orchestration",
            "message": {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": "hidden only"}],
            },
        })
        + "\n",
        encoding="utf-8",
    )


def _write_pi_visible_session(path: Path, session_id: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(entry, separators=(",", ":")) + "\n"
            for entry in [
                {"type": "session", "id": session_id, "cwd": "/tmp/pi"},
                {
                    "type": "message",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": text}],
                    },
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_codex_visible_session(path: Path, session_id: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(entry, separators=(",", ":")) + "\n"
            for entry in [
                {"type": "session_meta", "payload": {"id": session_id, "cwd": "/tmp/codex"}},
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    },
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_title_only_session(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "custom-title", "customTitle": "title only"}) + "\n",
        encoding="utf-8",
    )


def _write_tool_only_session(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "assistant",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-orchestration",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "pwd"}}
                ],
            },
        })
        + "\n",
        encoding="utf-8",
    )


def _write_task_notification_only_session(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-orchestration",
            "message": {
                "role": "user",
                "content": (
                    "<task-notification>"
                    "<tool-use-id>toolu_projection</tool-use-id>"
                    "<status>completed</status>"
                    "<summary>projection task finished</summary>"
                    "<result>projection task body</result>"
                    "</task-notification>"
                ),
            },
        })
        + "\n",
        encoding="utf-8",
    )


def test_dot_only_id_projection_outputs_ids_without_full_scan_or_metadata(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Eligible `search . -ll` should stream ids from projection, not full SessionScan."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    pi_path = home / ".pi" / "agent" / "sessions" / "proj" / "pi-visible.jsonl"
    codex_path = home / ".codex" / "sessions" / "2026" / "01" / "01" / "codex-visible.jsonl"
    _write_pi_visible_session(pi_path, "pi-visible-id", "visible pi")
    _write_codex_visible_session(codex_path, "codex-visible-id", "visible codex")
    os.utime(pi_path, (1_700_000_001, 1_700_000_001))
    os.utime(codex_path, (1_700_000_002, 1_700_000_002))

    def fail_session_scan(*_args, **_kwargs):
        raise AssertionError("Expected eligible dot/id search to skip SessionScan.")

    def fail_metadata_load(*_args, **_kwargs):
        raise AssertionError("Expected dot/id projection to avoid metadata loading.")

    monkeypatch.setattr(search_commands.SessionScan, "from_content", fail_session_scan)
    monkeypatch.setattr(
        resolve_commands,
        "_load_conversation_metadata",
        fail_metadata_load,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected dot/id search to find all visible sessions through projection. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.splitlines() == [
        "codex-visible-id",
        "pi-visible-id",
    ], (
        "Expected projection to preserve newest-first id output across providers. "
        f"Got stdout:\n{captured.out}"
    )


def test_dot_only_id_projection_does_not_match_hidden_or_protocol_only_sessions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Projection for `.` should not treat hidden-only raw content as visible content."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    hidden_path = home / ".claude" / "projects" / "proj" / "hidden-only.jsonl"
    protocol_path = home / ".claude" / "projects" / "proj" / "protocol-only.jsonl"
    tool_path = home / ".claude" / "projects" / "proj" / "tool-only.jsonl"
    task_notification_path = home / ".claude" / "projects" / "proj" / "task-notification-only.jsonl"
    _write_hidden_only_thinking_session(hidden_path)
    _write_tool_only_session(tool_path)
    _write_task_notification_only_session(task_notification_path)
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.write_text(
        json.dumps({
            "type": "user",
            "message": {
                "role": "user",
                "content": "<command-name>/status</command-name>",
            },
        })
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected hidden/protocol-only sessions not to match default dot search. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out == "", (
        "Expected no ids for hidden/protocol-only sessions. "
        f"Got stdout:\n{captured.out}"
    )


def test_dot_only_id_projection_matches_summary_and_title_only_sessions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Summary/title facets remain searchable even when no messages are visible."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    summary_path = home / ".claude" / "projects" / "proj" / "summary-only.jsonl"
    title_path = home / ".claude" / "projects" / "proj" / "title-only.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps({"type": "summary", "summary": "summary only"}) + "\n",
        encoding="utf-8",
    )
    _write_title_only_session(title_path)
    os.utime(summary_path, (1_700_000_000, 1_700_000_000))
    os.utime(title_path, (1_700_000_001, 1_700_000_001))

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected summary/title facets to match dot search. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.splitlines() == ["title-only", "summary-only"], (
        "Expected title-only and summary-only sessions to be projected as matches. "
        f"Got stdout:\n{captured.out}"
    )


def test_dot_only_id_ineligible_flags_fall_back_to_current_search_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Projection v1 is disabled for extra visibility flags such as thinking."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    hidden_path = home / ".claude" / "projects" / "proj" / "hidden-thinking.jsonl"
    _write_hidden_only_thinking_session(hidden_path)

    fallback_paths: list[Path] = []
    real_search_hit_for_file = search_commands._search_hit_for_file

    def tracked_search_hit_for_file(conv_file, query, flags, pool_filter):
        fallback_paths.append(conv_file)
        return real_search_hit_for_file(conv_file, query, flags, pool_filter)

    monkeypatch.setattr(
        search_commands,
        "_search_hit_for_file",
        tracked_search_hit_for_file,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(color="never", paging=False, show_thinking=True),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected fallback path with --thinking to find hidden thinking content. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert fallback_paths == [hidden_path], (
        "Expected ineligible flags to use the existing per-file search path. "
        f"Got fallback paths: {fallback_paths!r}"
    )


def test_dot_only_id_role_filters_fall_back_to_current_search_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Projection v1 is disabled for role-filtered dot searches."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    user_path = home / ".claude" / "projects" / "proj" / "user-visible.jsonl"
    _write_session(user_path, "visible user text")

    fallback_paths: list[Path] = []
    real_search_hit_for_file = search_commands._search_hit_for_file

    def tracked_search_hit_for_file(conv_file, query, flags, pool_filter):
        fallback_paths.append(conv_file)
        return real_search_hit_for_file(conv_file, query, flags, pool_filter)

    monkeypatch.setattr(
        search_commands,
        "_search_hit_for_file",
        tracked_search_hit_for_file,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(
                color="never",
                paging=False,
                message_selection=MessageSelection.ONLY_USER,
            ),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected fallback path with --only-user semantics to find visible user content. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert fallback_paths == [user_path], (
        "Expected role-filtered dot search to use the existing per-file search path. "
        f"Got fallback paths: {fallback_paths!r}"
    )


def test_dot_only_id_branchable_claude_files_fall_back(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Branchable Claude transcripts should fall back rather than guessing branch visibility."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    branch_path = home / ".claude" / "projects" / "proj" / "branch.jsonl"
    branch_path.parent.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).parent / "data" / "claude-branch-root-rewind.jsonl"
    branch_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    fallback_paths: list[Path] = []
    real_search_hit_for_file = search_commands._search_hit_for_file

    def tracked_search_hit_for_file(conv_file, query, flags, pool_filter):
        fallback_paths.append(conv_file)
        return real_search_hit_for_file(conv_file, query, flags, pool_filter)

    monkeypatch.setattr(
        search_commands,
        "_search_hit_for_file",
        tracked_search_hit_for_file,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected branchable file fallback to preserve current dot search behavior. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert fallback_paths == [branch_path], (
        "Expected branchable Claude file to use the existing per-file search path. "
        f"Got fallback paths: {fallback_paths!r}"
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


def test_ascii_literal_no_hit_prefilter_skips_text_reads_and_confirmation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """ASCII literal no-hit searches should reject files before text reads/parsing."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    first_path = home / ".claude" / "projects" / "proj" / "first.jsonl"
    second_path = home / ".claude" / "projects" / "proj" / "second.jsonl"
    _write_session(first_path, "ordinary first text")
    _write_session(second_path, "ordinary second text")

    session_paths = {first_path, second_path}
    real_read_text = Path.read_text

    def fail_if_session_text_read(path: Path, *args, **kwargs):
        if path in session_paths:
            raise AssertionError(
                "Expected ASCII literal no-hit prefilter to skip session text reads."
            )
        return real_read_text(path, *args, **kwargs)

    def fail_if_confirmed(*_args, **_kwargs):
        raise AssertionError(
            "Expected ASCII literal no-hit prefilter to skip semantic confirmation."
        )

    monkeypatch.setattr(Path, "read_text", fail_if_session_text_read)
    monkeypatch.setattr(
        search_commands,
        "_search_conversation_content",
        fail_if_confirmed,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "absent-ascii-byte-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected no-hit search to exit 1 after cleanly rejecting every file. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Error processing conversation file" not in captured.err, (
        "Expected prefilter misses to be clean skips, not caught read errors. "
        f"Got stderr:\n{captured.err}"
    )


def test_ascii_literal_prefilter_skips_text_read_for_noncandidate_files(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """ASCII literal noncandidates should be rejected before full text reads/parsing."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    matching_path = home / ".claude" / "projects" / "proj" / "match.jsonl"
    noncandidate_path = home / ".claude" / "projects" / "proj" / "other.jsonl"
    _write_session(matching_path, "ascii-byte-prefilter-needle")
    _write_session(noncandidate_path, "unrelated ascii text")

    real_read_text = Path.read_text

    def fail_if_noncandidate_text_read(path: Path, *args, **kwargs):
        if path == noncandidate_path:
            raise AssertionError(
                "Expected ASCII literal prefilter to skip text reads for noncandidate files."
            )
        return real_read_text(path, *args, **kwargs)

    real_search_conversation_content = search_commands._search_conversation_content
    confirmed_paths: list[Path] = []

    def tracked_search_conversation_content(
        conv_file: Path,
        content: str,
        query,
        flags: ConversationFlags,
        pool_filter: PoolFilter,
    ):
        confirmed_paths.append(conv_file)
        return real_search_conversation_content(
            conv_file, content, query, flags, pool_filter
        )

    monkeypatch.setattr(Path, "read_text", fail_if_noncandidate_text_read)
    monkeypatch.setattr(
        search_commands,
        "_search_conversation_content",
        tracked_search_conversation_content,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "ascii-byte-prefilter-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected the matching file to still be reported after prefiltering. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "match" in captured.out, (
        "Expected the matching session to remain visible. "
        f"Got stdout:\n{captured.out}"
    )
    assert "Error processing conversation file" not in captured.err, (
        "Expected noncandidate rejection to be a clean skip, not a caught read error. "
        f"Got stderr:\n{captured.err}"
    )
    assert confirmed_paths == [matching_path], (
        "Expected semantic confirmation only for byte-prefilter survivors. "
        f"Got confirmed paths: {confirmed_paths!r}"
    )


def test_ascii_literal_prefilter_survivor_still_requires_visible_confirmation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A raw byte candidate must not become a hit when the term is hidden by flags."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "hidden.jsonl"
    _write_hidden_thinking_session(session_path, "hidden-ascii-byte-needle")

    confirmed_paths: list[Path] = []
    real_search_conversation_content = search_commands._search_conversation_content

    def tracked_search_conversation_content(
        conv_file: Path,
        content: str,
        query,
        flags: ConversationFlags,
        pool_filter: PoolFilter,
    ):
        confirmed_paths.append(conv_file)
        return real_search_conversation_content(
            conv_file, content, query, flags, pool_filter
        )

    monkeypatch.setattr(
        search_commands,
        "_search_conversation_content",
        tracked_search_conversation_content,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "hidden-ascii-byte-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected a term present only in hidden thinking to remain hidden by default. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert confirmed_paths == [session_path], (
        "Expected byte candidates to continue through semantic visibility confirmation. "
        f"Got confirmed paths: {confirmed_paths!r}"
    )
    assert captured.out == "", (
        "Expected no id output for a hidden-only match. "
        f"Got stdout:\n{captured.out}"
    )


def test_non_ascii_literal_search_falls_back_and_remains_case_insensitive(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Non-ASCII literals should not use the ASCII byte gate and must keep regex semantics."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "accent.jsonl"
    _write_session(session_path, "CAFÉ-token")

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "café-token",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected non-ASCII literal search to preserve case-insensitive matching. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "accent" in captured.out, (
        "Expected the session containing CAFÉ-token to match query café-token. "
        f"Got stdout:\n{captured.out}"
    )


def test_regex_search_falls_back_to_full_confirmation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Regex searches are not optimized by the ASCII byte literal gate in this slice."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "regex.jsonl"
    _write_session(session_path, "regex-token-42")

    confirmed_paths: list[Path] = []
    real_search_conversation_content = search_commands._search_conversation_content

    def tracked_search_conversation_content(
        conv_file: Path,
        content: str,
        query,
        flags: ConversationFlags,
        pool_filter: PoolFilter,
    ):
        confirmed_paths.append(conv_file)
        return real_search_conversation_content(
            conv_file, content, query, flags, pool_filter
        )

    monkeypatch.setattr(
        search_commands,
        "_search_conversation_content",
        tracked_search_conversation_content,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            r"regex-token-\d+",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected regex search to keep matching through the full confirmation path. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert confirmed_paths == [session_path], (
        "Expected regex search to fall back to semantic confirmation. "
        f"Got confirmed paths: {confirmed_paths!r}"
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
        query,
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
        query,
        flags: ConversationFlags,
        pool_filter: PoolFilter,
    ):
        parsed_paths.append(conv_file)
        return real_search_conversation_content(
            conv_file, content, query, flags, pool_filter
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


def test_cmd_search_skips_first_timestamp_probe_when_only_mafter_is_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-ma` alone should never probe first-timestamp for files outside the window."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    fresh_path = home / ".claude" / "projects" / "proj" / "fresh.jsonl"
    stale_path = home / ".claude" / "projects" / "proj" / "stale.jsonl"

    fresh_iso = (
        (datetime.now(UTC) - timedelta(minutes=5))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    _write_session(fresh_path, "shared-needle-mafter-probe", timestamp=fresh_iso)
    _write_session(
        stale_path, "shared-needle-mafter-probe", timestamp="2020-01-01T00:00:00Z"
    )

    first_ts_calls: list[Path] = []
    real_find_first_timestamp = parsing._find_first_timestamp

    def tracked_find_first_timestamp(path: Path):
        first_ts_calls.append(path)
        return real_find_first_timestamp(path)

    monkeypatch.setattr(
        parsing, "_find_first_timestamp", tracked_find_first_timestamp
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "shared-needle-mafter-probe",
            ConversationFlags(color="never", paging=False),
            pool_filter=PoolFilter(mafter="1h"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected the in-window file to be reported. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert stale_path not in first_ts_calls, (
        "Expected mafter-only filtering to skip first-timestamp probing for files "
        f"outside the date window. Got first-timestamp probes for: {first_ts_calls!r}"
    )


def test_cmd_search_skips_last_timestamp_probe_when_only_cafter_is_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`-ca` alone should never probe last-timestamp for files outside the window."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    fresh_path = home / ".claude" / "projects" / "proj" / "fresh.jsonl"
    stale_path = home / ".claude" / "projects" / "proj" / "stale.jsonl"

    fresh_iso = (
        (datetime.now(UTC) - timedelta(minutes=5))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    _write_session(fresh_path, "shared-needle-cafter-probe", timestamp=fresh_iso)
    _write_session(
        stale_path, "shared-needle-cafter-probe", timestamp="2020-01-01T00:00:00Z"
    )

    last_ts_calls: list[Path] = []
    real_find_last_timestamp = parsing.find_last_jsonl_timestamp

    def tracked_find_last_timestamp(path: str, *parser_args: object) -> str | None:
        last_ts_calls.append(Path(path))
        return real_find_last_timestamp(path, *parser_args)

    monkeypatch.setattr(
        parsing, "find_last_jsonl_timestamp", tracked_find_last_timestamp
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "shared-needle-cafter-probe",
            ConversationFlags(color="never", paging=False),
            pool_filter=PoolFilter(cafter="1h"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected the in-window file to be reported. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert stale_path not in last_ts_calls, (
        "Expected cafter-only filtering to skip last-timestamp probing for files "
        f"outside the date window. Got last-timestamp probes for: {last_ts_calls!r}"
    )


# U+212A KELVIN SIGN: casefolds to 'k' but is not ASCII 'k'. Written as an escape
# so an editor normalizing the glyph cannot silently turn this into ASCII and hide
# the bug under test.
_KELVIN_SIGN = "\u212a"


def _write_unicode_session(
    path: Path,
    text: str,
    *,
    ensure_ascii: bool = False,
) -> None:
    """Write a Claude session with literal Unicode or JSON Unicode escapes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join([
            json.dumps(
                {"type": "summary", "summary": text, "leafUuid": f"{path.stem}-leaf"},
                ensure_ascii=ensure_ascii,
            ),
            json.dumps(
                {
                    "type": "user",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "cwd": "/tmp/search-orchestration",
                    "message": {"role": "user", "content": text},
                },
                ensure_ascii=ensure_ascii,
            ),
        ])
        + "\n",
        encoding="utf-8",
    )


def _write_compact_meta_session(path: Path) -> None:
    """Write a Claude entry the projection counts visible but the parser drops.

    `isCompactSummary` + `isMeta`: the real parser yields no visible message (meta
    suppresses the user text), so default `search .` must not list it. The current
    projection shortcuts on `isCompactSummary` and wrongly lists it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-orchestration",
            "isCompactSummary": True,
            "isMeta": True,
            "message": {"role": "user", "content": "compaction recap text"},
        })
        + "\n",
        encoding="utf-8",
    )


def test_case_sensitive_ascii_miss_skips_decoded_read_for_valid_unicode(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A valid non-ASCII character cannot create a case-sensitive ASCII match."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "unicode-miss.jsonl"
    _write_unicode_session(path, "unrelated café text")

    real_read_text = Path.read_text

    def fail_if_session_text_read(candidate: Path, *args, **kwargs):
        if candidate == path:
            raise AssertionError(
                "Expected the case-sensitive byte gate to reject valid Unicode "
                "content without a decoded file read."
            )
        return real_read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_session_text_read)

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "absent-ascii-needle",
            ConversationFlags(color="never", paging=False),
            case_sensitive=True,
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected the case-sensitive miss to exit 1 after the byte gate rejected it. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert "Error processing conversation file" not in captured.err, (
        "Expected a clean byte-gate miss without a decoded file read. "
        f"Got stderr:\n{captured.err}"
    )


def test_case_sensitive_ascii_miss_accepts_unicode_split_across_read_boundary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Incremental UTF-8 validation must carry a split code point between reads."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "split-unicode.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = b'{"type":"summary","summary":"'
    padding = b"x" * (1024 * 1024 - len(prefix) - 1)
    path.write_bytes(prefix + padding + "é unrelated".encode() + b'"}\n')

    real_read_text = Path.read_text

    def fail_if_session_text_read(candidate: Path, *args, **kwargs):
        if candidate == path:
            raise AssertionError(
                "Expected split valid UTF-8 to remain a clean case-sensitive miss."
            )
        return real_read_text(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_session_text_read)

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "absent-ascii-needle",
            ConversationFlags(color="never", paging=False),
            case_sensitive=True,
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected the case-sensitive miss to exit 1. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert "Error processing conversation file" not in captured.err, (
        "Expected the byte gate to accept a code point split at its read boundary. "
        f"Got stderr:\n{captured.err}"
    )


def test_ascii_literal_search_finds_unicode_casefold_match(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """An ASCII literal must match content that equals it only under Unicode case folding.

    The native candidate gate folds ASCII only. It must defer U+212A KELVIN SIGN
    so the authoritative `re.IGNORECASE` confirmation can match it to ASCII `k`.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "kelvin.jsonl"
    _write_unicode_session(path, f"the {_KELVIN_SIGN}town status report")

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "ktown",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "ASCII query 'ktown' must match U+212A content through the authoritative "
        f"regex. Got exit {exc_info.value.code}, "
        f"stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == path.stem, (
        "Expected the Unicode-folding session id to be reported. "
        f"Got stdout:\n{captured.out}"
    )


def test_ascii_literal_search_finds_json_escaped_unicode_casefold_match(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """JSON Unicode escapes must reach the decoded semantic confirmation path."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "escaped-kelvin.jsonl"
    _write_unicode_session(
        path,
        f"the {_KELVIN_SIGN}town status report",
        ensure_ascii=True,
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "ktown",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected JSON-escaped Unicode to reach semantic search confirmation. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == path.stem, (
        "Expected the escaped Unicode session id. "
        f"Got stdout:\n{captured.out}"
    )


def test_case_sensitive_ascii_search_finds_json_escaped_visible_text(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """JSON Unicode escapes must not hide case-sensitive ASCII matches."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "escaped-ascii.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"type":"user","timestamp":"2025-01-01T00:00:00Z",'
        '"cwd":"/tmp/search-orchestration","message":{"role":"user",'
        '"content":"\\u0042ash"}}\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "Bash",
            ConversationFlags(color="never", paging=False),
            case_sensitive=True,
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected a case-sensitive search to confirm JSON-escaped visible text. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == path.stem, (
        f"Expected the JSON-escaped session id. Got stdout:\n{captured.out}"
    )


@pytest.mark.parametrize(
    "flag_kwargs",
    [
        pytest.param({"show_thinking": True}, id="thinking"),
        pytest.param({"show_tools": True}, id="tools"),
        pytest.param({"show_agents": True}, id="agents"),
        pytest.param({"show_custom": True}, id="custom"),
        pytest.param({"show_branches": True}, id="branches"),
        pytest.param({"show_plans": True}, id="plans"),
        pytest.param({"shorten": True}, id="fixed-shortening"),
        pytest.param(
            {"shorten": True, "shorten_progressive": True},
            id="progressive-shortening",
        ),
        pytest.param(
            {"show_thinking": True, "shorten_thinking": True},
            id="thinking-shortening",
        ),
    ],
)
def test_case_insensitive_native_rejection_requires_default_unshortened_visibility(
    tmp_path: Path,
    monkeypatch,
    flag_kwargs: dict[str, bool],
) -> None:
    """Generated or shortened content must bypass the raw native rejection gate."""
    path = tmp_path / "candidate.jsonl"
    path.write_text("unrelated café text", encoding="utf-8")
    query = search_commands.parse_search_query("absent-ascii-needle")

    def fail_native_scan(*_args, **_kwargs) -> bool:
        raise AssertionError(
            "Expected non-default or shortened visibility to bypass native rejection."
        )

    monkeypatch.setattr(search_commands, "_file_contains_ascii", fail_native_scan)

    actual = search_commands._search_path_candidate_matches(
        path,
        query,
        ConversationFlags(color="never", paging=False, **flag_kwargs),
    )

    assert actual is True, (
        "Expected uncertain generated content to require semantic confirmation. "
        f"Got: {actual=!r}, {flag_kwargs=!r}"
    )


@pytest.mark.parametrize(
    "control_character",
    [chr(codepoint) for codepoint in range(0x20)],
    ids=lambda character: f"U+{ord(character):04X}",
)
def test_control_character_literals_bypass_native_candidate_rejection(
    tmp_path: Path,
    monkeypatch,
    control_character: str,
) -> None:
    """Every JSON control character stays on the full semantic fallback path."""
    path = tmp_path / "missing.jsonl"
    query = search_commands.parse_search_query(f"alpha{control_character}beta")

    def fail_native_scan(*_args, **_kwargs) -> bool:
        raise AssertionError(
            "Expected a control-character query to bypass both native gates."
        )

    monkeypatch.setattr(
        search_commands,
        "_file_contains_ascii_json_strings",
        fail_native_scan,
    )
    monkeypatch.setattr(search_commands, "_file_contains_ascii", fail_native_scan)

    actual = search_commands._search_path_candidate_matches(
        path,
        query,
        ConversationFlags(color="never", paging=False),
    )

    assert actual is True, (
        "Expected every U+0000 through U+001F query to require semantic "
        f"confirmation. Got: {actual=!r}, U+{ord(control_character):04X}"
    )


def test_ascii_literal_search_preserves_python_dotless_i_regex_match(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Python `re.IGNORECASE` treats U+0131 as an ASCII `i` equivalent."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "dotless-i.jsonl"
    _write_unicode_session(path, "the \u0131town status report")

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "itown",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected U+0131 to reach Python regex confirmation. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == path.stem, (
        f"Expected the dotless-i session id. Got stdout:\n{captured.out}"
    )


def test_native_candidate_read_errors_keep_semantic_error_text(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A native read failure must defer to the existing Python read error path."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    directory_path = (
        home / ".claude" / "projects" / "proj" / "directory-session.jsonl"
    )
    directory_path.mkdir(parents=True)

    def run_search(pattern: str) -> tuple[int, str, str]:
        with pytest.raises(SystemExit) as exc_info:
            commands.cmd_search(
                pattern,
                ConversationFlags(color="never", paging=False),
                output_mode=SearchOutputMode.ONLY_ID,
                emit_metadata=False,
            )
        captured = capsys.readouterr()
        return exc_info.value.code, captured.out, captured.err

    optimized = run_search("directory-error-probe")
    semantic_reference = run_search("directory-error-prob[e]")

    assert optimized == semantic_reference, (
        "Expected native candidate read uncertainty to preserve the full semantic "
        f"stdout, exit status, and stderr. Got {optimized=!r}, {semantic_reference=!r}"
    )
    assert optimized[0] == 1 and optimized[1] == "", (
        "Expected the unreadable-only search to remain a no-hit exit. "
        f"Got: {optimized=!r}"
    )
    assert "[Errno 21] Is a directory:" in optimized[2], (
        "Expected Python Path.read_text to remain the public error authority. "
        f"Got stderr:\n{optimized[2]}"
    )


def test_slash_literal_gate_decodes_json_escapes_without_deferring_unrelated_unicode_escapes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """An escaped slash can match while unrelated Unicode escapes reject cheaply."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    matching_path = home / ".claude" / "projects" / "proj" / "matching.jsonl"
    unrelated_path = home / ".claude" / "projects" / "proj" / "unrelated.jsonl"
    matching_path.parent.mkdir(parents=True, exist_ok=True)
    matching_path.write_text(
        '{"type":"user","timestamp":"2025-01-01T00:00:00Z",'
        '"cwd":"/tmp/search-orchestration","message":{"role":"user",'
        '"content":"CLIENT_ID\\/CARD"}}\n',
        encoding="utf-8",
    )
    unrelated_path.write_text(
        '{"type":"user","timestamp":"2025-01-01T00:00:00Z",'
        '"cwd":"/tmp/search-orchestration","message":{"role":"user",'
        '"content":"unrelated \\u263A text"}}\n',
        encoding="utf-8",
    )

    real_read_text = Path.read_text

    def fail_if_unrelated_text_is_read(path: Path, *args, **kwargs):
        if path == unrelated_path:
            raise AssertionError(
                "Expected local JSON escape matching to reject an unrelated "
                "Unicode escape without semantic parsing."
            )
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_unrelated_text_is_read)

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "CLIENT_ID/CARD",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected the escaped-slash session to remain a semantic hit. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}stderr:\n{captured.err}"
    )
    assert captured.out.strip() == matching_path.stem, (
        "Expected the logical JSON string match to preserve the visible session ID. "
        f"Got stdout:\n{captured.out}"
    )
    assert "Error processing conversation file" not in captured.err, (
        "Expected the unrelated Unicode escape to be a clean candidate rejection. "
        f"Got stderr:\n{captured.err}"
    )


def test_logical_gate_ids_match_full_semantic_scan_across_providers(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Candidate rejection must not change cross-provider IDs or newest-first order."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    claude_path = home / ".claude" / "projects" / "proj" / "claude.jsonl"
    pi_path = home / ".pi" / "agent" / "sessions" / "proj" / "pi.jsonl"
    codex_path = home / ".codex" / "sessions" / "2026" / "codex.jsonl"
    hidden_path = home / ".claude" / "projects" / "proj" / "hidden.jsonl"
    claude_path.parent.mkdir(parents=True, exist_ok=True)
    claude_path.write_text(
        '{"type":"user","message":{"role":"user",'
        '"content":"CLIENT_ID\\/CARD"}}\n',
        encoding="utf-8",
    )
    _write_pi_visible_session(pi_path, "pi-logical-id", "client_id/card")
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        '{"type":"session_meta","payload":{"id":"codex-logical-id",'
        '"cwd":"/tmp/codex"}}\n'
        '{"type":"response_item","payload":{"type":"message",'
        '"role":"assistant","content":[{"type":"output_text",'
        '"text":"CL\\u0049ENT_ID\\u002fCARD"}]}}\n',
        encoding="utf-8",
    )
    _write_hidden_thinking_session(hidden_path, "CLIENT_ID/CARD")
    for modified_time, path in enumerate(
        (hidden_path, claude_path, pi_path, codex_path),
        start=1_700_000_000,
    ):
        os.utime(path, (modified_time, modified_time))

    def search_ids() -> list[str]:
        with pytest.raises(SystemExit) as exc_info:
            commands.cmd_search(
                "CLIENT_ID/CARD",
                ConversationFlags(color="never", paging=False),
                output_mode=SearchOutputMode.ONLY_ID,
                emit_metadata=False,
            )
        captured = capsys.readouterr()
        assert exc_info.value.code == 0, (
            "Expected the parity corpus to contain visible matches. "
            f"Got exit {exc_info.value.code}, stdout:\n{captured.out}stderr:\n{captured.err}"
        )
        return captured.out.splitlines()

    optimized_ids = search_ids()
    monkeypatch.setattr(
        search_commands,
        "_can_use_logical_json_string_gate",
        lambda *_args, **_kwargs: False,
    )
    semantic_ids = search_ids()

    assert optimized_ids == semantic_ids == [
        "codex-logical-id",
        "pi-logical-id",
        "claude",
    ], (
        "Expected the logical gate to preserve full semantic IDs and order while "
        f"excluding the hidden-only session. Got {optimized_ids=!r}, {semantic_ids=!r}"
    )


def test_json_decode_unstable_query_bypasses_native_rejection(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A query containing a decoded newline must not be searched as raw JSON bytes."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "escaped-newline.jsonl"
    _write_unicode_session(path, "alpha\nbeta")

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "alpha\nbeta",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected a JSON-decode-unstable query to reach semantic confirmation. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == path.stem, (
        f"Expected the escaped-newline session id. Got stdout:\n{captured.out}"
    )


@pytest.mark.parametrize(
    "case_sensitive", [False, True], ids=["insensitive", "sensitive"]
)
def test_nondefault_tool_visibility_bypasses_native_rejection(
    tmp_path: Path, monkeypatch, capsys, case_sensitive: bool
) -> None:
    """Codex tool normalization may create the visible name `Bash` absent raw."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".codex" / "sessions" / "2026" / "01" / "codex-tools.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join([
            json.dumps({
                "type": "session_meta",
                "payload": {"id": "codex-tools-id", "cwd": "/tmp/codex"},
            }),
            json.dumps({
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": "pwd"}),
                    "call_id": "call-1",
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "Bash",
            ConversationFlags(show_tools=True, color="never", paging=False),
            case_sensitive=case_sensitive,
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected non-default tool visibility to bypass native rejection. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == "codex-tools-id", (
        f"Expected the Codex tool session id. Got stdout:\n{captured.out}"
    )


@pytest.mark.parametrize(
    "case_sensitive", [False, True], ids=["insensitive", "sensitive"]
)
def test_default_pi_joined_agent_evidence_reaches_semantic_confirmation(
    tmp_path: Path, monkeypatch, capsys, case_sensitive: bool
) -> None:
    """A joined Pi failure generates visible `Bash` text absent from raw values."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".pi" / "agent" / "sessions" / "project" / "pi-agent.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join([
            json.dumps({
                "type": "session",
                "version": 3,
                "id": "pi-agent-id",
                "cwd": "/tmp/pi",
            }),
            json.dumps({
                "type": "custom_message",
                "customType": "pi-user-agents",
                "display": False,
                "content": "<user_agent_error></user_agent_error>",
                "details": {
                    "mainContextState": "joined",
                    "ok": False,
                    "task": "inspect the failure",
                    "error": "native failure text",
                },
            }),
        ])
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "Bash",
            ConversationFlags(color="never", paging=False),
            case_sensitive=case_sensitive,
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected default Pi joined-agent evidence to reach semantic confirmation. "
        f"Got exit {exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == "pi-agent-id", (
        f"Expected the joined Pi agent session id. Got stdout:\n{captured.out}"
    )


def test_escaped_joined_pi_evidence_matches_full_semantic_search(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """JSON escapes in the Pi marker must not hide generated visible content."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".pi" / "agent" / "sessions" / "project" / "escaped-marker.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "type": "session",
            "version": 3,
            "id": "escaped-marker-id",
            "cwd": "/tmp/pi",
        })
        + "\n"
        + '{"type":"custom_message","customType":"pi-user-\\u0061gents",'
        '"display":false,"content":"<user_agent_error></user_agent_error>",'
        '"details":{"mainContextState":"joined","ok":false,'
        '"task":"inspect the failure","error":"native failure text"}}\n',
        encoding="utf-8",
    )

    def search_id(pattern: str) -> tuple[int, str]:
        with pytest.raises(SystemExit) as exc_info:
            commands.cmd_search(
                pattern,
                ConversationFlags(color="never", paging=False),
                output_mode=SearchOutputMode.ONLY_ID,
                emit_metadata=False,
            )
        return exc_info.value.code, capsys.readouterr().out.strip()

    optimized = search_id("Bash")
    semantic_reference = search_id("B[a]sh")

    assert optimized == semantic_reference == (0, "escaped-marker-id"), (
        "Expected escaped joined-Pi evidence to preserve generated-content parity. "
        f"Got {optimized=!r}, {semantic_reference=!r}"
    )


def test_dot_only_id_claude_files_route_through_fallback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Claude transcripts must defer to the full search path, never the projection.

    Claude default visibility depends on branch resolution the projection cannot
    cheaply replicate, so every Claude file (marker or not) must fall back to
    `_search_hit_for_file`.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    claude_path = home / ".claude" / "projects" / "proj" / "claude-visible.jsonl"
    _write_session(claude_path, "visible claude")  # no "last-prompt" marker

    fallback_paths: list[Path] = []
    real_search_hit_for_file = search_commands._search_hit_for_file

    def tracked_search_hit_for_file(conv_file, query, flags, pool_filter):
        fallback_paths.append(conv_file)
        return real_search_hit_for_file(conv_file, query, flags, pool_filter)

    monkeypatch.setattr(
        search_commands, "_search_hit_for_file", tracked_search_hit_for_file
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            ".",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        f"Expected the visible Claude session to be found. Got exit "
        f"{exc_info.value.code}, stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert fallback_paths == [claude_path], (
        "Claude files must route through the full search path, not the projection. "
        f"Got fallback paths: {fallback_paths!r}"
    )


def test_projection_never_decides_claude_files(
    tmp_path: Path, monkeypatch
) -> None:
    """Falsifying guardrail: the projection must not return a verdict for Claude files.

    A non-UNKNOWN result means the projection judged a Claude transcript's
    visibility itself instead of deferring — the duplication this refactor removes.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = home / ".claude" / "projects" / "proj" / "claude-visible.jsonl"
    _write_session(path, "visible claude")  # no "last-prompt" marker

    result = search_commands._project_default_dot_match(path)
    assert result is search_commands._ProjectionResult.UNKNOWN, (
        "Projection produced a verdict for a Claude file instead of deferring to "
        f"the full search path. Got: {result!r}"
    )


def test_dot_only_id_projection_ids_match_full_scan_ids(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Falsifying guardrail: `search . -ll` projection must equal the full search path.

    The corpus includes an `isCompactSummary`+`isMeta` Claude entry the parser
    drops but the current projection lists — a live divergence the equivalence
    guard must catch.
    """
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(
        home / ".claude" / "projects" / "proj" / "claude-visible.jsonl", "visible claude"
    )
    _write_compact_meta_session(
        home / ".claude" / "projects" / "proj" / "compact-meta.jsonl"
    )
    _write_pi_visible_session(
        home / ".pi" / "agent" / "sessions" / "proj" / "pi.jsonl", "pi-id", "visible pi"
    )
    _write_codex_visible_session(
        home / ".codex" / "sessions" / "2026" / "01" / "01" / "codex.jsonl",
        "codex-id",
        "visible codex",
    )

    def dot_search_ids() -> list[str]:
        with pytest.raises(SystemExit):
            commands.cmd_search(
                ".",
                ConversationFlags(color="never", paging=False),
                output_mode=SearchOutputMode.ONLY_ID,
                emit_metadata=False,
            )
        return capsys.readouterr().out.splitlines()

    projected_ids = dot_search_ids()
    monkeypatch.setattr(
        search_commands, "_can_project_dot_only_id", lambda *args, **kwargs: False
    )
    full_scan_ids = dot_search_ids()

    assert projected_ids == full_scan_ids, (
        "`search . -ll` projection must return exactly the full-scan ids. "
        f"projection={projected_ids!r} full_scan={full_scan_ids!r}"
    )
