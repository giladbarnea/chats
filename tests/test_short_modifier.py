#!/usr/bin/env python3
"""Integration tests for short modifiers across different session ecosystems."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chats import ConversationFlags, cmd_parse
from chats.tool_filter import ToolFilter


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries),
        encoding="utf-8",
    )


def _extract_tool_input_body(output: str, tool_name: str) -> str:
    pattern = re.compile(
        rf'<tool-input[^>]*name="{re.escape(tool_name)}"[^>]*>\n(?P<body>.*?)\n</tool-input>',
        re.DOTALL,
    )
    match = pattern.search(output)
    assert match is not None, (
        f"Expected output to contain a tool-input block for {tool_name!r}. Got:\n{output}"
    )
    return match.group("body")


def _extract_thinking_body(output: str) -> str:
    match = re.search(r"<thinking>\n(?P<body>.*?)\n</thinking>", output, re.DOTALL)
    assert match is not None, (
        f"Expected output to contain a thinking block. Got:\n{output}"
    )
    return match.group("body")


def _assert_shortened_tool_body(body: str, start_marker: str, end_marker: str) -> None:
    assert len(body) == 500, (
        f"Expected shortened tool body to be exactly 500 chars. Got {len(body)}.\nBody:\n{body}"
    )
    assert body.count("\n...\n") == 1, (
        f"Expected exactly one line-broken ellipsis placeholder. Got body:\n{body}"
    )
    assert start_marker in body[:260], (
        f"Expected the preserved prefix to contain {start_marker!r}. Got:\n{body[:260]}"
    )
    assert end_marker in body[-260:], (
        f"Expected the preserved suffix to contain {end_marker!r}. Got:\n{body[-260:]}"
    )


def _assert_shortened_thinking_body(
    body: str,
    start_marker: str,
    end_marker: str,
) -> None:
    assert len(body) == 500, (
        f"Expected shortened thinking body to be exactly 500 chars. Got {len(body)}.\nBody:\n{body}"
    )
    assert body.count("\n...\n") == 1, (
        f"Expected exactly one line-broken ellipsis placeholder in thinking body. Got:\n{body}"
    )
    assert start_marker in body[:260], (
        f"Expected the preserved thinking prefix to contain {start_marker!r}. Got:\n{body[:260]}"
    )
    assert end_marker in body[-260:], (
        f"Expected the preserved thinking suffix to contain {end_marker!r}. Got:\n{body[-260:]}"
    )


def test_short_modifier_claude_session(tmp_path: Path, monkeypatch, capsys) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    session_path = (
        temp_home
        / ".claude"
        / "projects"
        / "p1"
        / "1e446a9f-08fd-43ac-be72-8ce337d01dcd.jsonl"
    )

    long_text = "CLAUDE_START-" + ("A" * 1000) + "-CLAUDE_END"
    _write_jsonl(
        session_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "Bash",
                            "input": {"command": long_text},
                        }
                    ],
                },
            }
        ],
    )

    cmd_parse(
        ConversationFlags(
            color="never",
            paging=False,
            show_tools=[ToolFilter(short=True)],
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )
    out = capsys.readouterr().out
    body = _extract_tool_input_body(out, "Bash")
    _assert_shortened_tool_body(body, "CLAUDE_START-", "CLAUDE_END")


def test_short_modifier_codex_session(tmp_path: Path, monkeypatch, capsys) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "rollout-session001.jsonl"
    )

    long_text = "CODEX_START-" + ("B" * 1000) + "-CODEX_END"
    _write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:15:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "session001",
                    "timestamp": "2026-04-10T06:15:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:15:01.300Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "call_exec_1",
                    "arguments": json.dumps({"cmd": long_text, "workdir": "/tmp"}),
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(
            color="never",
            paging=False,
            show_tools=[ToolFilter(short=True)],
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )
    out = capsys.readouterr().out
    body = _extract_tool_input_body(out, "Bash")
    _assert_shortened_tool_body(body, "CODEX_START-", "CODEX_END")


def test_short_modifier_pi_session(tmp_path: Path, monkeypatch, capsys) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_session-short.jsonl"
    )

    long_text = "PI_START-" + ("C" * 1000) + "-PI_END"
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-short",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "assistant-1",
                "parentId": "session-short",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "toolCall",
                            "id": "call_1234567890",
                            "name": "bash",
                            "arguments": {"command": long_text, "timeout": 300},
                        }
                    ],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "toolUse",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(
            color="never",
            paging=False,
            show_tools=[ToolFilter(short=True)],
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )
    out = capsys.readouterr().out
    body = _extract_tool_input_body(out, "Bash")
    _assert_shortened_tool_body(body, "PI_START-", "PI_END")


def test_thinking_short_modifier_claude_session(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    session_path = (
        temp_home / ".claude" / "projects" / "p1" / "thinking-short-claude.jsonl"
    )

    long_thinking = "CLAUDE_THINK_START-" + ("A" * 1000) + "-CLAUDE_THINK_END"
    _write_jsonl(
        session_path,
        [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "thinking", "thinking": long_thinking}],
                },
            }
        ],
    )

    cmd_parse(
        ConversationFlags(
            color="never",
            paging=False,
            show_thinking=True,
            shorten_thinking=True,
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )
    out = capsys.readouterr().out
    body = _extract_thinking_body(out)
    _assert_shortened_thinking_body(body, "CLAUDE_THINK_START-", "CLAUDE_THINK_END")


def test_thinking_short_modifier_codex_session(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    session_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "10"
        / "thinking-short-codex.jsonl"
    )

    long_thinking = "CODEX_THINK_START-" + ("B" * 1000) + "-CODEX_THINK_END"
    _write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-04-10T06:15:00.000Z",
                "type": "session_meta",
                "payload": {
                    "id": "session-thinking-short-codex",
                    "timestamp": "2026-04-10T06:15:00.000Z",
                    "cwd": "/tmp/codex-project",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "timestamp": "2026-04-10T06:15:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": long_thinking}],
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(
            color="never",
            paging=False,
            show_thinking=True,
            shorten_thinking=True,
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )
    out = capsys.readouterr().out
    body = _extract_thinking_body(out)
    _assert_shortened_thinking_body(body, "CODEX_THINK_START-", "CODEX_THINK_END")


def test_thinking_short_modifier_pi_session(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-04-04T12-24-33-963Z_thinking-short-pi.jsonl"
    )

    long_thinking = "PI_THINK_START-" + ("C" * 1000) + "-PI_THINK_END"
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "session-thinking-short-pi",
                "timestamp": "2026-04-04T12:24:33.963Z",
                "cwd": "/tmp/project",
            },
            {
                "type": "message",
                "id": "assistant-thinking-1",
                "parentId": "session-thinking-short-pi",
                "timestamp": "2026-04-04T12:25:48.467Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "thinking", "thinking": long_thinking}],
                    "provider": "openrouter",
                    "model": "z-ai/glm-5",
                    "stopReason": "done",
                    "timestamp": 1775305547188,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(
            color="never",
            paging=False,
            show_thinking=True,
            shorten_thinking=True,
        ),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )
    out = capsys.readouterr().out
    body = _extract_thinking_body(out)
    _assert_shortened_thinking_body(body, "PI_THINK_START-", "PI_THINK_END")
