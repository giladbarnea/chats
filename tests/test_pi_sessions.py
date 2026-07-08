#!/usr/bin/env python3
"""Integration tests for parsing PI session JSONL files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from chats import ConversationFlags, cmd_parse, cmd_name


def _utc_to_local_display(utc_iso: str) -> str:
    """Convert a UTC ISO timestamp to the local-time display string used in date attrs."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    local = dt.astimezone().replace(tzinfo=None)
    return local.strftime("%Y-%m-%d %H:%M")


def _write_pi_session(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a PI session fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _write_claude_session(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a Claude session fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_cmd_parse_supports_basic_text_from_pi_session_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A direct ~/.pi session path should render user and assistant text messages."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-123",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-123",
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello from pi"}],
                    "timestamp": 1775305547146,
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hi from pi"}],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "stop",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    user_date = _utc_to_local_display("2026-04-04T12:25:47.187Z")
    assert f'<user-message i="1" date="{user_date}">' in captured.out, (
        "Expected a PI user message to render through the standard XML wrapper. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hello from pi" in captured.out, (
        "Expected PI user text content to be preserved in XML output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<assistant-response i="2"' in captured.out, (
        "Expected a PI assistant message to render through the standard XML wrapper. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hi from pi" in captured.out, (
        "Expected PI assistant text content to be preserved in XML output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_renders_pi_compaction_entries_as_compaction_blocks(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A native PI compaction entry should render as the shared compaction block."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-07-07T11-19-51-210Z_session-compaction.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-compaction",
                "timestamp": "2026-07-07T11:19:51.210Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "compaction",
                "id": "0d16eb25",
                "parentId": "87ec96ee",
                "timestamp": "2026-07-07T11:51:02.552Z",
                "summary": "Summary of the prior PI conversation.",
                "tokensBefore": 446281,
                "firstKeptEntryId": "87ec96ee",
                "fromHook": False,
                "details": {"modifiedFiles": [], "readFiles": []},
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    compaction_date = _utc_to_local_display("2026-07-07T11:51:02.552Z")
    assert f'<compaction i="1" date="{compaction_date}">' in captured.out, (
        "Expected a native PI compaction entry to render through the shared "
        f"compaction XML wrapper. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "## Compaction" in captured.out, (
        "Expected the PI compaction block to use the Compaction header, not User. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Summary of the prior PI conversation." in captured.out, (
        "Expected the native PI compaction summary text to be preserved. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<user-message" not in captured.out, (
        "Expected a native PI compaction entry not to render as a user message. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_supports_pi_session_id_after_claude_lookup_is_exhausted(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A PI session id should resolve only after Claude Code lookup finds no match."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    _write_claude_session(
        temp_home
        / ".claude"
        / "projects"
        / "demo-project"
        / "unrelated-claude-session.jsonl",
        [
            {
                "type": "summary",
                "summary": "Unrelated Claude session",
                "leafUuid": "leaf-1",
            },
            {
                "type": "user",
                "message": {"role": "user", "content": "claude user"},
                "uuid": "claude-user-1",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "claude assistant"}],
                },
            },
        ],
    )

    session_id = "9a27c7d8-d58f-4179-bf0a-a4657c7dca64"
    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / f"2026-04-04T12-24-33-963Z_{session_id}.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": session_id,
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": session_id,
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello from pi by id"}],
                    "timestamp": 1775305547146,
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hi from pi by id"}],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "stop",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        session_id,
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert "hello from pi by id" in captured.out, (
        "Expected the PI session id to resolve through fallback lookup and render the "
        f"PI user message. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hi from pi by id" in captured.out, (
        "Expected the PI session id to resolve through fallback lookup and render the "
        f"PI assistant message. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "history_path: ~/.pi/agent/sessions/--tmp-project--/"
        f"2026-04-04T12-24-33-963Z_{session_id}.jsonl"
    ) in captured.out, (
        "Expected metadata to prove the session id resolved to the PI session file. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_prefers_claude_session_before_pi_fallback_for_same_identifier(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Claude session ids should win before adapter fallback is tried."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_id = "9a27c7d8-d58f-4179-bf0a-a4657c7dca64"
    _write_claude_session(
        temp_home / ".claude" / "projects" / "demo-project" / f"{session_id}.jsonl",
        [
            {
                "type": "summary",
                "summary": "Claude should win",
                "leafUuid": "leaf-1",
            },
            {
                "type": "user",
                "message": {"role": "user", "content": "hello from claude by id"},
                "uuid": "claude-user-1",
                "timestamp": "2026-04-04T12:25:47.187Z",
                "cwd": "/tmp/claude-project",
                "sessionId": session_id,
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hi from claude by id"}],
                },
                "timestamp": "2026-04-04T12:25:48.467Z",
                "cwd": "/tmp/claude-project",
                "sessionId": session_id,
            },
        ],
    )

    _write_pi_session(
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / f"2026-04-04T12-24-33-963Z_{session_id}.jsonl",
        [
            {
                "type": "session",
                "version": 3,
                "id": session_id,
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/pi-project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": session_id,
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello from pi by id"}],
                    "timestamp": 1775305547146,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        session_id,
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert "hello from claude by id" in captured.out, (
        "Expected Claude's exact session id match to win before PI fallback. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hi from claude by id" in captured.out, (
        "Expected Claude assistant content when the same identifier exists in both "
        f"ecosystems. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hello from pi by id" not in captured.out, (
        "Expected PI fallback not to run once Claude already matched the session id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        f"history_path: ~/.claude/projects/demo-project/{session_id}.jsonl"
    ) in captured.out, (
        "Expected metadata to prove the identifier resolved to the Claude session file. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_hides_command_like_pi_user_messages_by_default(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """PI user messages carrying Claude-style command protocol text should stay hidden by default."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session-command-hidden.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-command-hidden",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-command-hidden",
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "<command-name>/model</command-name>\n<command-args>opus</command-args>",
                        }
                    ],
                    "timestamp": 1775305547146,
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "real pi reply"}],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "stop",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "real pi reply" in captured.out, (
        "Expected the real PI assistant reply to remain visible. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<command-name>" not in captured.out, (
        "Expected command-like PI user messages to stay hidden by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "user-command-input" not in captured.out, (
        "Expected command-like PI user messages not to render through user-command wrappers by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_supports_thinking_and_tools_from_pi_session_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A direct ~/.pi session path should normalize thinking and tools too."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session-tools.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-456",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-456",
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "run a command"}],
                    "timestamp": 1775305547146,
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "I should inspect the shell output.",
                        },
                        {"type": "text", "text": "Running the command now."},
                        {
                            "type": "toolCall",
                            "id": "call_1234567890",
                            "name": "bash",
                            "arguments": {"command": "echo hi", "timeout": 300},
                        },
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "toolUse",
                    "timestamp": 1775305547188,
                },
            },
            {
                "type": "message",
                "id": "tool-result-1",
                "parentId": "assistant-1",
                "timestamp": "2026-04-04T12:25:49.467Z",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "call_1234567890",
                    "toolName": "bash",
                    "content": [{"type": "text", "text": "hi"}],
                    "isError": False,
                    "timestamp": 1775305548188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(
            show_thinking=True,
            show_tools=True,
            color="never",
            paging=False,
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "<thinking>" in captured.out, (
        "Expected PI assistant thinking content to render through the shared thinking block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "I should inspect the shell output." in captured.out, (
        "Expected PI assistant thinking text to be preserved. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<tool-input name="Bash"' in captured.out, (
        "Expected a PI toolCall to normalize into the standard tool-input XML block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "echo hi" in captured.out, (
        "Expected PI toolCall arguments to render through the standard tool formatter. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<tool-output name="Bash"' in captured.out, (
        "Expected a PI toolResult to normalize into the standard tool-output XML block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hi" in captured.out, (
        "Expected PI toolResult content to be preserved in XML output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_emits_metadata_for_pi_session_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """PI session paths should flow through the standard metadata frontmatter."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session-metadata.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-789",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-789",
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello from pi metadata"}],
                    "timestamp": 1775305547146,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert "session_id: session-789" in captured.out, (
        "Expected PI session metadata to include the native PI session id, not the timestamp-prefixed filename stem. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "directory: /tmp/project" in captured.out, (
        "Expected PI session metadata to use the session cwd for the directory field. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "history_path: ~/.pi/agent/sessions/--tmp-project--/"
        "2026-04-04T12-24-33-963Z_session-metadata.jsonl"
    ) in captured.out, (
        "Expected PI session metadata to include the direct ~/.pi history path. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "messages: 1" in captured.out, (
        "Expected PI session metadata to report the normalized message count. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_name_keeps_title_out_of_default_pi_parse_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """After renaming a PI session, the title should stay out of default parse output."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session-rename.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-rename-test",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-rename-test",
                "timestamp": "2026-04-04T12:25:47.187Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello from pi rename test"}],
                    "timestamp": 1775305547146,
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "pi assistant reply"}],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "stop",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_name(str(session_path), "My PI Title")
    capsys.readouterr()

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "My PI Title" not in captured.out, (
        "Expected the custom title written by cmd_name to stay out of default PI parse output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<session-rename" not in captured.out, (
        "Expected default PI parse output not to render the session-rename wrapper. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_name_appends_native_pi_session_info_entry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """PI rename should append one native session_info entry chained to the previous entry."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session-native-rename.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-native-rename",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "session-native-rename",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "pi assistant reply"}],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "stop",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_name(str(session_path), "Native PI Title")

    entries = [
        json.loads(line)
        for line in session_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rename_entry = entries[-1]
    assert rename_entry.get("type") == "session_info", (
        "Expected PI rename to append a native session_info entry. "
        f"Got entry: {rename_entry}"
    )
    assert rename_entry.get("name") == "Native PI Title", (
        "Expected PI rename to preserve the requested title in session_info.name. "
        f"Got entry: {rename_entry}"
    )
    assert rename_entry.get("parentId") == "assistant-1", (
        "Expected PI rename to chain off the previous entry id. "
        f"Got entry: {rename_entry}"
    )
    assert isinstance(rename_entry.get("id"), str) and len(rename_entry["id"]) == 8, (
        "Expected PI rename to synthesize an 8-character entry id. "
        f"Got entry: {rename_entry}"
    )
    assert all(character in "0123456789abcdef" for character in rename_entry["id"]), (
        "Expected PI rename ids to use lowercase hexadecimal characters. "
        f"Got entry: {rename_entry}"
    )
    assert isinstance(rename_entry.get("timestamp"), str) and rename_entry[
        "timestamp"
    ].endswith("Z"), (
        "Expected PI rename to stamp the native entry with a UTC JSONL timestamp. "
        f"Got entry: {rename_entry}"
    )
    assert not (temp_home / ".claude" / "history.jsonl").exists(), (
        "Expected PI rename not to create Claude's global history.jsonl side effect."
    )


def test_cmd_parse_treats_native_pi_session_name_as_custom_title(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Native PI session_info names should flow through the shared custom-title surface."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    native_title = "research session name aspect in conversations"
    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-26T09-34-26-042Z_019dc923-e4f9-738a-af74-ed184e7a4adf.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "019dc923-e4f9-738a-af74-ed184e7a4adf",
                "timestamp": "2026-04-26T09:34:26.042Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "019dc923-e4f9-738a-af74-ed184e7a4adf",
                "timestamp": "2026-04-26T09:35:47.187Z",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Show the native PI session name."}
                    ],
                    "timestamp": 1775305547146,
                },
            },
            {
                "type": "session_info",
                "id": "c7b92652",
                "parentId": "51820569",
                "timestamp": "2026-04-26T09:46:06.122Z",
                "name": native_title,
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-04-26T09:46:08.467Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Native PI rename acknowledged."}
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "stop",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert f'custom_title: "{native_title}"' in captured.out, (
        "Expected native PI session names to populate the shared metadata custom_title field. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.count(native_title) == 1, (
        "Expected the native PI session name to appear only in metadata, not as rendered message content. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<session-rename" not in captured.out, (
        "Expected native PI session names not to render through the session-rename XML tag anymore. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_tool_error_isError_false_details_error_absent(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """isError=False without details.error: tool output should NOT be marked as error."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-05-12T08-34-34-538Z_no-error.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-no-error",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-no-error",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "read a file"}],
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-05-12T08:34:35.538Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "toolCall",
                            "id": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                            "name": "read",
                            "arguments": {"file_path": "/tmp/plan.md"},
                        },
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                },
            },
            {
                "type": "message",
                "id": "tool-result-1",
                "parentId": "assistant-1",
                "timestamp": "2026-05-12T08:34:36.538Z",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                    "toolName": "read",
                    "content": [
                        {
                            "type": "text",
                            "text": "# Plan\n\nHello world.",
                        }
                    ],
                    "isError": False,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(show_tools=True, color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert 'is_error="true"' not in captured.out, (
        "Expected PI tool output without isError and without details.error NOT to carry "
        f"is_error=true. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_tool_error_isError_true_details_error_absent(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """isError=True without details.error: tool output should be marked as error."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-05-12T08-34-34-538Z_iserror-true-no-details.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-iserror-true",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-iserror-true",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "read a nonexistent file"}],
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-05-12T08:34:35.538Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "toolCall",
                            "id": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                            "name": "read",
                            "arguments": {
                                "file_path": "/nonexistent/path/to/nowhere.md"
                            },
                        },
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                },
            },
            {
                "type": "message",
                "id": "tool-result-1",
                "parentId": "assistant-1",
                "timestamp": "2026-05-12T08:34:36.538Z",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                    "toolName": "read",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error reading file: ENOENT",
                        }
                    ],
                    "isError": True,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(show_tools=True, color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert 'is_error="true"' in captured.out, (
        "Expected PI tool output with isError=true to carry is_error=true. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_tool_error_isError_true_details_error_present(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """isError=True with details.error: tool output should be marked as error."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-05-12T08-34-34-538Z_both-error.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-both-error",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-both-error",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "read a nonexistent file"}],
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-05-12T08:34:35.538Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "toolCall",
                            "id": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                            "name": "read",
                            "arguments": {
                                "file_path": "/nonexistent/path/to/nowhere.md"
                            },
                        },
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                },
            },
            {
                "type": "message",
                "id": "tool-result-1",
                "parentId": "assistant-1",
                "timestamp": "2026-05-12T08:34:36.538Z",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                    "toolName": "read",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error reading file: ENOENT",
                        }
                    ],
                    "isError": True,
                    "details": {
                        "path": "/nonexistent/path/to/nowhere.md",
                        "error": "ENOENT: no such file or directory",
                    },
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(show_tools=True, color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert 'is_error="true"' in captured.out, (
        "Expected PI tool output with both isError=true and details.error to carry "
        f"is_error=true. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_tool_error_isError_false_details_error_present(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """isError=False WITH details.error: tool output should STILL be marked as error."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-05-12T08-34-34-538Z_details-error.jsonl"
    )
    _write_pi_session(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-details-error",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "session-details-error",
                "timestamp": "2026-05-12T08:34:34.538Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "read a nonexistent file"}],
                },
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "user-1",
                "timestamp": "2026-05-12T08:34:35.538Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "toolCall",
                            "id": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                            "name": "read",
                            "arguments": {
                                "file_path": "/nonexistent/path/to/nowhere.md"
                            },
                        },
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                },
            },
            {
                "type": "message",
                "id": "tool-result-1",
                "parentId": "assistant-1",
                "timestamp": "2026-05-12T08:34:36.538Z",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "call_00_pZnGyhqtwR73Ww7oyx9Y6251",
                    "toolName": "read",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error reading file \"/nonexistent/path/to/nowhere.md\": ENOENT: no such file or directory, access '/nonexistent/path/to/nowhere.md'",
                        }
                    ],
                    "isError": False,
                    "details": {
                        "path": "/nonexistent/path/to/nowhere.md",
                        "error": "ENOENT: no such file or directory, access '/nonexistent/path/to/nowhere.md'",
                    },
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(show_tools=True, color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert 'is_error="true"' in captured.out, (
        "Expected PI tool output with details.error to carry is_error=true even when "
        f"isError=False. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


@pytest.mark.skip(reason="Out of scope as of May 16")
def test_rich_rendering_of_recursive_xml_matches_expected_colored_output(
    capsys,
) -> None:
    """Rich-rendered output must match expected colored text when a user message embeds
    a full ch transcript (itself containing XML tags) wrapped in XML tags."""
    session_path = Path(__file__).parent / "data" / "recursive_xml_rich_rendering.jsonl"

    cmd_parse(
        ConversationFlags(color="always", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    expected = ""  # TODO: fill in expected colored output string once bug is fixed
    assert captured.out == expected, (
        f"Rich rendering of session 019e2a43 with recursively embedded XML does not "
        f"match expected colored output. Got:\n{captured.out[:500]!r}"
    )
