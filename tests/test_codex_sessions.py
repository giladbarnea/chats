#!/usr/bin/env python3
"""Integration tests for parsing Codex session JSONL files."""

from __future__ import annotations

import json
from pathlib import Path

from conversations import ConversationFlags, ToolFilter, cmd_parse, cmd_rename


def _write_codex_session(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a Codex session fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_cmd_parse_supports_basic_text_from_codex_session_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A direct ~/.codex session path should render only the real user and assistant turns."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T09-15-00-01961abc-def0-7123-89ab-codexsession0001.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:15:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexsession0001",
                    "timestamp": "2026-04-10T06:15:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:15:00.100Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "<permissions instructions>\nworkspace-write\n</permissions instructions>",
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-04-10T06:15:00.200Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "# AGENTS.md instructions for /tmp/codex-project\n\n<INSTRUCTIONS>\nAlways read the docs.\n</INSTRUCTIONS>",
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-04-10T06:15:00.300Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "<environment_context>\n  <cwd>/tmp/codex-project</cwd>\n  <shell>zsh</shell>\n</environment_context>",
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-04-10T06:15:00.350Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": None,
                    "rate_limits": {},
                },
            },
            {
                "timestamp": "2026-04-10T06:15:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Summarize the last deployment issue.",
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-04-10T06:15:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "The last deployment failed because the database migration timed out.",
                        }
                    ],
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
        "Expected the first visible Codex turn to render as a standard user message. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Summarize the last deployment issue." in captured.out, (
        "Expected the real Codex user prompt to be preserved in XML output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<assistant-response i=\"2\"" in captured.out, (
        "Expected the Codex assistant reply to render as a standard assistant message. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "The last deployment failed because the database migration timed out." in captured.out, (
        "Expected the Codex assistant text to be preserved in XML output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "AGENTS.md instructions" not in captured.out, (
        "Expected Codex session preamble instructions to stay hidden by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<environment_context>" not in captured.out, (
        "Expected Codex environment context preamble to stay hidden by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "permissions instructions" not in captured.out, (
        "Expected Codex developer protocol preamble to stay hidden by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_supports_codex_session_id_after_claude_and_pi_lookup_fail(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A Codex session id should resolve through adapter fallback after other ecosystems miss."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_id = "01961abc-def0-7123-89ab-codexsession0002"
    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / f"rollout-2026-04-10T09-18-00-{session_id}.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:18:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "timestamp": "2026-04-10T06:18:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:18:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Explain the timeout regression."}],
                },
            },
            {
                "timestamp": "2026-04-10T06:18:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "The regression came from a slower startup path in the migration worker."}],
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
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "Explain the timeout regression." in captured.out, (
        "Expected the bare Codex session id to resolve through adapter fallback and "
        f"render the Codex user message. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "The regression came from a slower startup path in the migration worker." in captured.out, (
        "Expected the bare Codex session id to resolve through adapter fallback and "
        f"render the Codex assistant message. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_supports_reasoning_and_both_tool_shapes_from_codex_session_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A Codex assistant turn should merge reasoning, regular tools, custom tools, and final text."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T09-21-00-01961abc-def0-7123-89ab-codexsession0003.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:21:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexsession0003",
                    "timestamp": "2026-04-10T06:21:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Fix the deployment timeout issue."}],
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.100Z",
                "type": "event_msg",
                "payload": {
                    "type": "agent_reasoning",
                    "text": "agent-only reasoning that should stay hidden",
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.200Z",
                "type": "response_item",
                "payload": {
                    "type": "reasoning",
                    "summary": [
                        {
                            "type": "summary_text",
                            "text": "Inspecting deployment failure logs.",
                        }
                    ],
                    "content": None,
                    "encrypted_content": "opaque",
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.300Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "call_exec_1",
                    "arguments": json.dumps({"cmd": "uv run pytest -q", "workdir": "/tmp/codex-project"}),
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.400Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call_exec_1",
                    "output": "Chunk ID: 123\nProcess exited with code 1\nOutput:\n1 failed\n",
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.500Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "status": "completed",
                    "call_id": "call_patch_1",
                    "name": "apply_patch",
                    "input": "*** Begin Patch\n*** Update File: app.py\n@@\n-print('old')\n+print('new')\n*** End Patch",
                },
            },
            {
                "timestamp": "2026-04-10T06:21:01.600Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "call_patch_1",
                    "output": "{\"output\":\"Success. Updated the following files:\\nM app.py\\n\"}",
                },
            },
            {
                "timestamp": "2026-04-10T06:21:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "I updated the timeout handling and the failing test should pass now.",
                        }
                    ],
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
    assert "<assistant-response i=\"2\"" in captured.out, (
        "Expected the Codex assistant turn to normalize into a single assistant response. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<assistant-response i=\"3\"" not in captured.out, (
        "Expected contiguous Codex assistant-side events to stay grouped in one response. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<thinking>" in captured.out, (
        "Expected Codex reasoning summaries to render through the shared thinking block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Inspecting deployment failure logs." in captured.out, (
        "Expected Codex reasoning summary text to be preserved. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "agent-only reasoning that should stay hidden" not in captured.out, (
        "Expected Codex agent_reasoning event messages to remain hidden. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<tool-input name="Bash"' in captured.out, (
        "Expected a regular Codex function_call to normalize into a tool-input block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<tool-output name="Bash"' in captured.out, (
        "Expected a regular Codex function_call_output to normalize into a named tool-output block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<tool-input name="Patch"' in captured.out, (
        "Expected a Codex custom_tool_call to normalize into a tool-input block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '<tool-output name="Patch"' in captured.out, (
        "Expected a Codex custom_tool_call_output to normalize into a named tool-output block. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "I updated the timeout handling and the failing test should pass now." in captured.out, (
        "Expected the final Codex assistant text to be preserved alongside reasoning and tools. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_codex_exec_command_input_renders_through_tool_schema(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Codex exec_command arguments should render as canonical Bash tool input."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T09-24-00-01961abc-def0-7123-89ab-codextoolschema01.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:24:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codextoolschema01",
                    "timestamp": "2026-04-10T06:24:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:24:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "call_exec_1",
                    "arguments": json.dumps({
                        "cmd": "uv run pytest tests/test_codex_sessions.py -q",
                        "workdir": "/tmp/codex-project",
                        "yield_time_ms": 1000,
                        "max_output_tokens": 12000,
                    }),
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(
            show_tools=[ToolFilter(name="Bash")],
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
    assert (
        '<tool-input name="Bash" id="call" '
        'workdir="/tmp/codex-project" yield_time_ms="1000" max_output_tokens="12000">'
        in captured.out
    ), (
        "Expected Codex exec_command to normalize to Bash and render options as attributes. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "```sh\nuv run pytest tests/test_codex_sessions.py -q\n```" in captured.out
    ), (
        "Expected Codex exec_command cmd to render as a shell fenced body. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '"cmd":' not in captured.out, (
        "Expected Codex exec_command input not to fall back to raw JSON. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_codex_apply_patch_input_aliases_to_patch_and_renders_pretty(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Codex apply_patch payloads should render the patch and unwrapped tool output."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T09-25-00-01961abc-def0-7123-89ab-codextoolschema02.jsonl"
    )
    patch_text = (
        "*** Begin Patch\n"
        "*** Update File: app.py\n"
        "@@\n"
        "-print('old')\n"
        "+print('new')\n"
        "*** End Patch"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:25:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codextoolschema02",
                    "timestamp": "2026-04-10T06:25:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:25:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "call_id": "call_patch_1",
                    "input": patch_text,
                },
            },
            {
                "timestamp": "2026-04-10T06:25:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "call_patch_1",
                    "output": json.dumps({
                        "output": "Success. Updated the following files:\nM app.py\n"
                    }),
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
    assert '<tool-input name="Patch" id="call">' in captured.out, (
        "Expected Codex apply_patch input to render as canonical Patch. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert f"```diff\n{patch_text}\n```" in captured.out, (
        "Expected Codex apply_patch input to render as a diff fenced body. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Success. Updated the following files:\nM app.py" in captured.out, (
        "Expected Codex JSON-wrapped apply_patch output to render as its contained text. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '"input":' not in captured.out, (
        "Expected Codex apply_patch input not to fall back to raw JSON. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert '{"output":' not in captured.out, (
        "Expected Codex apply_patch output not to expose the JSON wrapper. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_emits_metadata_for_codex_session_path(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A direct Codex session path should expose cwd-backed metadata like other adapters."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T09-27-00-01961abc-def0-7123-89ab-codexsession0004.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:27:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexsession0004",
                    "timestamp": "2026-04-10T06:27:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:27:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Show me metadata for this session."}],
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
    assert "session_id: 01961abc-def0-7123-89ab-codexsession0004" in captured.out, (
        "Expected Codex metadata to include the canonical Codex session id from session_meta.payload.id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "directory: /tmp/codex-project" in captured.out, (
        "Expected Codex metadata to use session_meta.cwd for the directory field. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "history_path: ~/.codex/sessions/2026/04/10/"
        "rollout-2026-04-10T09-27-00-01961abc-def0-7123-89ab-codexsession0004.jsonl"
    ) in captured.out, (
        "Expected Codex metadata to include the direct ~/.codex history path. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "messages: 1" in captured.out, (
        "Expected Codex metadata to report the normalized message count. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_rename_persists_canonical_codex_session_id_in_appended_entries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Codex rename metadata should keep the canonical short session id, not the rollout-prefixed filename stem."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_id = "01961abc-def0-7123-89ab-codexrename002"
    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / f"rollout-2026-04-10T10-05-00-{session_id}.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T07:05:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "timestamp": "2026-04-10T07:05:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T07:05:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Rename this codex session."}],
                },
            },
        ],
    )

    cmd_rename(str(session_path), "Canonical Codex Title")

    appended_entries = [
        json.loads(line)
        for line in session_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-2:]
    assert [entry["sessionId"] for entry in appended_entries] == [session_id, session_id], (
        "Expected cmd_rename to append custom-title and agent-name entries that use the "
        "canonical Codex session id rather than the rollout-prefixed filename stem. "
        f"Got entries: {appended_entries}"
    )


def test_codex_skill_payloads_hidden_by_default(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Codex user messages containing <skill> protocol payloads should be filtered out."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T10-30-00-01961abc-def0-7123-89ab-codexskill0001.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T07:30:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexskill0001",
                    "timestamp": "2026-04-10T07:30:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T07:30:00.100Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "<skill>\n<name>tdd</name>\n<path>/some/path/SKILL.md</path>\nTest-driven development skill content.\n</skill>",
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-04-10T07:30:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Real user prompt."}],
                },
            },
            {
                "timestamp": "2026-04-10T07:30:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Real assistant reply."}],
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
    assert "Real user prompt." in captured.out, (
        "Expected the real user prompt to remain visible. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Real assistant reply." in captured.out, (
        "Expected the assistant reply to remain visible. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<skill>" not in captured.out, (
        "Expected Codex skill protocol payloads to be hidden by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "Test-driven development skill content." not in captured.out, (
        "Expected skill content to be hidden by default. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_rename_makes_title_visible_in_codex_parse_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """After renaming a Codex session, the custom title should render as a session-rename block."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-2026-04-10T10-00-00-01961abc-def0-7123-89ab-codexrename001.jsonl"
    )
    _write_codex_session(
        session_path,
        [
            {
                "timestamp": "2026-04-10T07:00:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexrename001",
                    "timestamp": "2026-04-10T07:00:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T07:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello from codex rename test."}],
                },
            },
            {
                "timestamp": "2026-04-10T07:00:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Codex assistant reply."}],
                },
            },
        ],
    )

    cmd_rename(str(session_path), "My Codex Title")

    # Now parse — the title should be visible
    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "My Codex Title" in captured.out, (
        "Expected the custom title written by cmd_rename to render as visible content "
        "when parsing a Codex session. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "<session-rename" in captured.out, (
        "Expected the custom title to render through the standard session-rename XML tag. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
