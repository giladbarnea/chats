#!/usr/bin/env python3
"""Behavior tests for the fork command across supported session ecosystems."""

from __future__ import annotations

import json
from pathlib import Path

import conversations.cli as cli_module
import conversations.commands as commands_module
import conversations.forking as forking_module
from conversations.model import ConversationFlags
from conversations.tool_filter import ToolFilter


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_cmd_fork_claude_default_creates_thin_main_session_and_updates_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    project_dir = temp_home / ".claude" / "projects" / "demo-project"
    history_file = temp_home / ".claude" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("", encoding="utf-8")

    session_path = project_dir / "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.jsonl"
    sidechain_path = project_dir / "agent-deadbeef.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "assistant",
                "sessionId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "claude thinking should disappear"},
                        {
                            "type": "tool_use",
                            "id": "toolu_task",
                            "name": "Task",
                            "input": {"subagent_type": "Explore", "prompt": "inspect"},
                        },
                        {
                            "type": "tool_use",
                            "id": "toolu_bash",
                            "name": "Bash",
                            "input": {"command": "printf 'hello'\n"},
                        },
                        {"type": "text", "text": "assistant text stays"},
                    ],
                },
                "timestamp": "2026-04-14T09:00:00.000Z",
            },
            {
                "type": "user",
                "sessionId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_bash",
                            "content": "tool output should disappear",
                            "is_error": False,
                        }
                    ],
                },
                "toolUseResult": {
                    "stdout": "tool output should disappear",
                    "stderr": "",
                    "interrupted": False,
                    "isImage": False,
                },
                "timestamp": "2026-04-14T09:00:01.000Z",
            },
        ],
    )
    _write_jsonl(
        sidechain_path,
        [
            {
                "type": "assistant",
                "sessionId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "agentId": "deadbeef",
                "isSidechain": True,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "sidechain content"}],
                },
                "timestamp": "2026-04-14T09:00:02.000Z",
            }
        ],
    )

    monkeypatch.setattr(
        forking_module,
        "_generate_claude_session_id",
        lambda: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    )

    commands_module.cmd_fork(
        str(session_path),
        ConversationFlags(color=False, paging=False),
    )

    forked_path = project_dir / "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb.jsonl"
    assert forked_path.exists(), "Expected fork to create a new Claude session file."
    assert not (project_dir / "agent-bbbbbbbb.jsonl").exists(), (
        "Expected default fork to omit sidechain files unless --agents is requested."
    )

    forked_entries = _read_jsonl(forked_path)
    assistant_content = forked_entries[0]["message"]["content"]
    assert assistant_content == [{"type": "text", "text": "assistant text stays"}], (
        "Expected default fork to strip Claude thinking and tool_use blocks while "
        f"preserving assistant text. Got: {assistant_content!r}"
    )
    assert forked_entries[1]["message"]["content"] == [], (
        "Expected default fork to strip Claude tool_result blocks from user messages."
    )
    assert "toolUseResult" not in forked_entries[1], (
        "Expected default fork to remove Claude toolUseResult payloads when tools are hidden."
    )
    history_entries = _read_jsonl(history_file)
    assert history_entries[-1].get("sessionId") == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", (
        "Expected Claude forks to append the new session id to ~/.claude/history.jsonl. "
        f"Got: {history_entries!r}"
    )


def test_cmd_fork_claude_agents_rewrites_sidechain_linkage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    project_dir = temp_home / ".claude" / "projects" / "demo-project"
    history_file = temp_home / ".claude" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("", encoding="utf-8")

    session_path = project_dir / "claude-session-id.jsonl"
    sidechain_path = project_dir / "agent-deadbeef.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "assistant",
                "sessionId": "claude-session-id",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_task",
                            "name": "Task",
                            "input": {"subagent_type": "Explore", "prompt": "inspect"},
                        }
                    ],
                },
                "timestamp": "2026-04-14T09:00:00.000Z",
            },
            {
                "type": "user",
                "sessionId": "claude-session-id",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_task",
                            "content": [{"type": "text", "text": "agent finished"}],
                            "is_error": False,
                        }
                    ],
                },
                "toolUseResult": {
                    "agentId": "deadbeef",
                    "content": [{"type": "text", "text": "agent finished"}],
                    "status": "completed",
                },
                "timestamp": "2026-04-14T09:00:01.000Z",
            },
        ],
    )
    _write_jsonl(
        sidechain_path,
        [
            {
                "type": "assistant",
                "sessionId": "claude-session-id",
                "agentId": "deadbeef",
                "isSidechain": True,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "sidechain content"}],
                },
                "timestamp": "2026-04-14T09:00:02.000Z",
            }
        ],
    )

    monkeypatch.setattr(
        forking_module,
        "_generate_claude_session_id",
        lambda: "forked-claude-session-id",
    )
    monkeypatch.setattr(
        forking_module,
        "_generate_claude_agent_id",
        lambda: "cafebabe",
    )

    commands_module.cmd_fork(
        str(session_path),
        ConversationFlags(show_agents=True, color=False, paging=False),
    )

    forked_main = _read_jsonl(project_dir / "forked-claude-session-id.jsonl")
    forked_sidechain_path = project_dir / "agent-cafebabe.jsonl"
    assert forked_sidechain_path.exists(), (
        "Expected --agents fork to duplicate Claude sidechains with a renamed agent file."
    )

    nested_agent_id = forked_main[1].get("toolUseResult", {}).get("agentId")
    assert nested_agent_id == "cafebabe", (
        "Expected main-session Task results to point at the new sidechain agent id. "
        f"Got: {nested_agent_id!r}"
    )
    forked_sidechain = _read_jsonl(forked_sidechain_path)
    assert forked_sidechain[0].get("agentId") == "cafebabe", (
        "Expected forked Claude sidechain entries to carry the new short agent id. "
        f"Got: {forked_sidechain!r}"
    )
    assert forked_sidechain[0].get("sessionId") == "forked-claude-session-id", (
        "Expected forked Claude sidechains to belong to the new main session id. "
        f"Got: {forked_sidechain!r}"
    )


def test_cmd_fork_pi_rewrites_native_session_id_and_filename_suffix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-14T09-00-00-000Z_pi-old-id.jsonl"
    )
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "pi-old-id",
                "timestamp": "2026-04-14T09:00:00.000Z",
                "cwd": "/tmp/pi-project",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": "pi-old-id",
                "timestamp": "2026-04-14T09:00:01.000Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello from pi"}],
                },
            },
        ],
    )

    monkeypatch.setattr(forking_module, "_generate_pi_session_id", lambda: "pi-new-id")

    commands_module.cmd_fork(
        str(session_path),
        ConversationFlags(color=False, paging=False),
    )

    forked_path = session_path.with_name("2026-04-14T09-00-00-000Z_pi-new-id.jsonl")
    assert forked_path.exists(), (
        "Expected PI forks to preserve the native filename prefix and replace only the session id suffix."
    )
    forked_entries = _read_jsonl(forked_path)
    assert forked_entries[0].get("id") == "pi-new-id", (
        "Expected PI fork to rewrite the session entry's native id field. "
        f"Got: {forked_entries[0]!r}"
    )
    assert forked_entries[1].get("parentId") == "pi-new-id", (
        "Expected PI fork to rewrite parentId links that target the root session id. "
        f"Got: {forked_entries[1]!r}"
    )


def test_cmd_fork_codex_rewrites_native_session_id_filename_and_default_visibility(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "14"
        / "rollout-2026-04-14T12-00-00-codex-old-id.jsonl"
    )
    _write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-04-14T09:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "codex-old-id", "cwd": "/tmp/codex-project"},
            },
            {
                "timestamp": "2026-04-14T09:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "reasoning",
                    "summary": [
                        {"type": "summary_text", "text": "codex reasoning should disappear"}
                    ],
                },
            },
            {
                "timestamp": "2026-04-14T09:00:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "call-1",
                    "arguments": json.dumps({"cmd": "echo hi"}),
                },
            },
            {
                "timestamp": "2026-04-14T09:00:03.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "codex tool output should disappear",
                },
            },
            {
                "timestamp": "2026-04-14T09:00:04.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "assistant text stays"}],
                },
            },
        ],
    )

    monkeypatch.setattr(
        forking_module,
        "_generate_codex_session_id",
        lambda: "codex-new-id",
    )

    commands_module.cmd_fork(
        str(session_path),
        ConversationFlags(color=False, paging=False),
    )

    forked_path = session_path.with_name("rollout-2026-04-14T12-00-00-codex-new-id.jsonl")
    assert forked_path.exists(), (
        "Expected Codex forks to preserve the native rollout filename prefix and replace the canonical session id."
    )

    forked_entries = _read_jsonl(forked_path)
    assert forked_entries[0].get("payload", {}).get("id") == "codex-new-id", (
        "Expected Codex fork to rewrite session_meta.payload.id. "
        f"Got: {forked_entries[0]!r}"
    )
    payload_types = [entry.get("payload", {}).get("type") for entry in forked_entries[1:]]
    assert payload_types == ["message"], (
        "Expected default Codex fork to strip reasoning and tool response items, leaving only visible text payloads. "
        f"Got payload types: {payload_types!r}"
    )


def test_cmd_fork_claude_can_keep_shortened_thinking_and_tool_payloads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    long_thinking = "CLAUDE_THINK_START-" + ("A" * 1000) + "-CLAUDE_THINK_END"
    long_command = "CLAUDE_TOOL_START-" + ("B" * 1000) + "-CLAUDE_TOOL_END"
    long_output = "CLAUDE_OUTPUT_START-" + ("C" * 1000) + "-CLAUDE_OUTPUT_END"

    session_path = temp_home / ".claude" / "projects" / "demo-project" / "short-claude-session.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "assistant",
                "sessionId": "short-claude-session",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": long_thinking},
                        {
                            "type": "tool_use",
                            "id": "toolu_bash",
                            "name": "Bash",
                            "input": {"command": long_command},
                        },
                    ],
                },
            },
            {
                "type": "user",
                "sessionId": "short-claude-session",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_bash",
                            "content": long_output,
                            "is_error": False,
                        }
                    ],
                },
                "toolUseResult": {
                    "stdout": long_output,
                    "stderr": "",
                    "interrupted": False,
                    "isImage": False,
                },
            },
        ],
    )

    monkeypatch.setattr(
        forking_module,
        "_generate_claude_session_id",
        lambda: "shortened-claude-fork",
    )

    commands_module.cmd_fork(
        str(session_path),
        ConversationFlags(
            show_thinking=True,
            shorten_thinking=True,
            show_tools=[ToolFilter(short=True)],
            color=False,
            paging=False,
        ),
    )

    forked_entries = _read_jsonl(session_path.with_name("shortened-claude-fork.jsonl"))
    thinking_text = forked_entries[0]["message"]["content"][0]["thinking"]
    command_text = forked_entries[0]["message"]["content"][1]["input"]["command"]
    output_text = forked_entries[1]["message"]["content"][0]["content"]
    tool_use_result_stdout = forked_entries[1]["toolUseResult"]["stdout"]

    assert "\n...\n" in thinking_text and len(thinking_text) == 500, (
        "Expected `--thinking short` semantics to persist a shortened Claude thinking block."
    )
    assert "\n...\n" in command_text and len(command_text) == 500, (
        "Expected `--tools:s` semantics to shorten Claude tool input payloads."
    )
    assert "\n...\n" in output_text and len(output_text) == 500, (
        "Expected `--tools:s` semantics to shorten Claude tool result content."
    )
    assert "\n...\n" in tool_use_result_stdout and len(tool_use_result_stdout) == 500, (
        "Expected Claude toolUseResult payloads to stay in sync with shortened tool result content."
    )


def test_cmd_fork_codex_can_keep_shortened_thinking_and_tool_payloads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    long_thinking = "CODEX_THINK_START-" + ("A" * 1000) + "-CODEX_THINK_END"
    long_command = "CODEX_TOOL_START-" + ("B" * 1000) + "-CODEX_TOOL_END"
    long_output = "CODEX_OUTPUT_START-" + ("C" * 1000) + "-CODEX_OUTPUT_END"

    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "14"
        / "rollout-2026-04-14T12-00-00-codex-short-id.jsonl"
    )
    _write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-04-14T09:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "codex-short-id", "cwd": "/tmp/codex-project"},
            },
            {
                "timestamp": "2026-04-14T09:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": long_thinking}],
                    "encrypted_content": "opaque",
                },
            },
            {
                "timestamp": "2026-04-14T09:00:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "call-1",
                    "arguments": json.dumps({"cmd": long_command}),
                },
            },
            {
                "timestamp": "2026-04-14T09:00:03.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": long_output,
                },
            },
        ],
    )

    monkeypatch.setattr(
        forking_module,
        "_generate_codex_session_id",
        lambda: "codex-short-fork",
    )

    commands_module.cmd_fork(
        str(session_path),
        ConversationFlags(
            show_thinking=True,
            shorten_thinking=True,
            show_tools=[ToolFilter(short=True)],
            color=False,
            paging=False,
        ),
    )

    forked_entries = _read_jsonl(
        session_path.with_name("rollout-2026-04-14T12-00-00-codex-short-fork.jsonl")
    )
    reasoning_text = forked_entries[1]["payload"]["summary"][0]["text"]
    arguments = json.loads(forked_entries[2]["payload"]["arguments"])
    output_text = forked_entries[3]["payload"]["output"]

    assert "\n...\n" in reasoning_text and len(reasoning_text) == 500, (
        "Expected `--thinking short` semantics to persist shortened Codex reasoning summaries."
    )
    assert "\n...\n" in arguments["cmd"] and len(arguments["cmd"]) == 500, (
        "Expected `--tools:s` semantics to shorten serialized Codex tool inputs."
    )
    assert "\n...\n" in output_text and len(output_text) == 500, (
        "Expected `--tools:s` semantics to shorten Codex tool outputs."
    )


def test_fork_cli_treats_bare_tools_flag_like_parse_for_following_session_argument(
    tmp_path: Path,
    monkeypatch,
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = temp_home / ".claude" / "projects" / "demo" / "cli-session.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_cmd_fork(session_arg: str, flags: ConversationFlags) -> None:
        captured["session_arg"] = session_arg
        captured["flags"] = flags

    monkeypatch.setattr(commands_module, "cmd_fork", fake_cmd_fork)
    monkeypatch.setattr(
        cli_module.sys,
        "argv",
        ["ccc", "fork", "-t", str(session_path)],
    )

    cli_module.main()

    assert captured.get("session_arg") == str(session_path), (
        "Expected `ccc fork -t <session>` to resolve the following path as the session positional, "
        f"matching parse-mode argument handling. Got: {captured!r}"
    )
    flags = captured.get("flags")
    assert isinstance(flags, ConversationFlags), f"Expected CLI to pass ConversationFlags. Got: {flags!r}"
    assert flags.show_tools is True, (
        "Expected bare `-t` in fork mode to preserve parse-mode behavior and enable all tools. "
        f"Got: {flags!r}"
    )
