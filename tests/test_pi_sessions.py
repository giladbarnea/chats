#!/usr/bin/env python3
"""Integration tests for parsing PI session JSONL files."""

from __future__ import annotations

import json
from pathlib import Path

from conversations import ConversationFlags, cmd_parse


def _write_pi_session(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a PI session fixture path."""
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
    assert "<user-message i=\"1\">" in captured.out, (
        "Expected a PI user message to render through the standard XML wrapper. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hello from pi" in captured.out, (
        "Expected PI user text content to be preserved in XML output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<assistant-response i=\"2\"" in captured.out, (
        "Expected a PI assistant message to render through the standard XML wrapper. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "hi from pi" in captured.out, (
        "Expected PI assistant text content to be preserved in XML output. "
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
                        {"type": "thinking", "thinking": "I should inspect the shell output."},
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
    assert "session_id: 2026-04-04T12-24-33-963Z_session-metadata" in captured.out, (
        "Expected PI session metadata to include the standard session_id field. "
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
