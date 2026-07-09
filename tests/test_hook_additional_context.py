#!/usr/bin/env python3
"""A Claude hook's injected additional-context attachment is represented as an
`AdditionalContext` tool, so it obeys the same `-t/--tools` visibility policy as
any other tool across parse, JSON, search, and fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import chats.commands as commands_module
import chats.forking as forking_module
from chats import (
    ConversationFlags,
    SearchOutputMode,
    cmd_search,
    parse_jsonl,
)
from chats.formatting import format_to_json, format_to_xml
from chats.tool_filter import ToolFilter

HOOK_MARKER = "HOOK_CONTEXT_MARKER"


def _session_with_hook_context(
    *,
    hook_name: str = "UserPromptSubmit",
    content: list[str] | None = None,
) -> str:
    """A Claude session: a user prompt, an injected hook additional-context
    attachment, and an ordinary Bash tool call/result."""
    entries = [
        {
            "type": "user",
            "uuid": "u1",
            "message": {"role": "user", "content": "go"},
            "timestamp": "2026-07-09T09:37:00.000Z",
        },
        {
            "type": "attachment",
            "uuid": "att1",
            "parentUuid": "u1",
            "attachment": {
                "type": "hook_additional_context",
                "content": content or [f"{HOOK_MARKER} injected context body"],
                "hookName": hook_name,
                "toolUseID": "hook-abc123",
                "hookEvent": hook_name,
            },
            "timestamp": "2026-07-09T09:37:10.000Z",
        },
        {
            "type": "assistant",
            "uuid": "a1",
            "parentUuid": "att1",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_bash",
                        "name": "Bash",
                        "input": {"command": "echo NORMAL_TOOL_MARKER"},
                    }
                ],
            },
            "timestamp": "2026-07-09T09:37:20.000Z",
        },
    ]
    return "\n".join(json.dumps(entry) for entry in entries)


def test_hidden_by_default_and_shown_with_tools() -> None:
    """No `--tools`: the hook context is hidden. Bare `--tools`: it renders as an
    `AdditionalContext` tool carrying its `hook_name` and injected body."""
    content = _session_with_hook_context()

    hidden = format_to_xml(
        parse_jsonl(content, ConversationFlags(color="never")),
        ConversationFlags(color="never"),
    )
    assert HOOK_MARKER not in hidden, (
        f"Expected hook additional-context hidden without --tools. Got:\n{hidden}"
    )
    assert "AdditionalContext" not in hidden, (
        f"Expected no AdditionalContext tool without --tools. Got:\n{hidden}"
    )

    flags = ConversationFlags(show_tools=True, color="never")
    shown = format_to_xml(parse_jsonl(content, flags), flags)
    assert 'name="AdditionalContext"' in shown, (
        f"Expected an AdditionalContext tool with --tools. Got:\n{shown}"
    )
    assert 'hook_name="UserPromptSubmit"' in shown, (
        f"Expected the hook_name attribute on the tool. Got:\n{shown}"
    )
    assert HOOK_MARKER in shown, (
        f"Expected the injected context body to render. Got:\n{shown}"
    )


def test_obeys_name_filters_like_any_tool() -> None:
    """`AdditionalContext` participates in positive and negated `-t` name filters."""
    content = _session_with_hook_context()

    only = ConversationFlags(
        show_tools=[ToolFilter(name="AdditionalContext")], color="never"
    )
    only_output = format_to_xml(parse_jsonl(content, only), only)
    assert HOOK_MARKER in only_output, (
        f"Expected `-t AdditionalContext` to keep the hook context. Got:\n{only_output}"
    )
    assert "NORMAL_TOOL_MARKER" not in only_output, (
        f"Expected `-t AdditionalContext` to hide the Bash tool. Got:\n{only_output}"
    )

    without = ConversationFlags(
        show_tools=[ToolFilter(name="AdditionalContext", negate=True)], color="never"
    )
    without_output = format_to_xml(parse_jsonl(content, without), without)
    assert HOOK_MARKER not in without_output, (
        f"Expected `-t !AdditionalContext` to hide the hook context. Got:\n{without_output}"
    )
    assert "NORMAL_TOOL_MARKER" in without_output, (
        f"Expected `-t !AdditionalContext` to keep the Bash tool. Got:\n{without_output}"
    )


def test_hook_name_with_event_qualifier_renders_verbatim() -> None:
    """Hook names can carry a `:tool` qualifier (e.g. `PostToolUse:Edit`)."""
    content = _session_with_hook_context(hook_name="PostToolUse:Edit")
    flags = ConversationFlags(show_tools=True, color="never")
    output = format_to_xml(parse_jsonl(content, flags), flags)
    assert 'hook_name="PostToolUse:Edit"' in output, (
        f"Expected the qualified hook name to render verbatim. Got:\n{output}"
    )


def test_multiple_content_blocks_join_with_blank_line() -> None:
    """A hook's `content` list is joined into one body, blocks separated by a blank line."""
    content = _session_with_hook_context(content=["FIRST_BLOCK", "SECOND_BLOCK"])
    flags = ConversationFlags(show_tools=True, color="never")
    output = format_to_xml(parse_jsonl(content, flags), flags)
    assert "FIRST_BLOCK\n\nSECOND_BLOCK" in output, (
        f"Expected the hook content blocks joined by a blank line. Got:\n{output}"
    )


def test_json_output_carries_name_hook_and_body() -> None:
    """Structured JSON output represents the hook context as a named tool block."""
    content = _session_with_hook_context()
    flags = ConversationFlags(show_tools=True, color="never")
    payload = json.loads(format_to_json(parse_jsonl(content, flags), flags))

    tool_blocks = [
        block
        for message in payload
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("name") == "AdditionalContext"
    ]
    assert len(tool_blocks) == 1, (
        f"Expected exactly one AdditionalContext block in JSON. Got:\n{payload}"
    )
    block = tool_blocks[0]
    assert block.get("hook_name") == "UserPromptSubmit", (
        f"Expected the hook_name field in JSON. Got:\n{block}"
    )
    assert HOOK_MARKER in json.dumps(block), (
        f"Expected the injected body in the JSON block. Got:\n{block}"
    )


def _write_claude_session(project_dir: Path, session_id: str) -> Path:
    session_path = project_dir / f"{session_id}.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "type": "user",
            "uuid": "u1",
            "sessionId": session_id,
            "message": {"role": "user", "content": "go"},
        },
        {
            "type": "attachment",
            "uuid": "att1",
            "parentUuid": "u1",
            "sessionId": session_id,
            "attachment": {
                "type": "hook_additional_context",
                "content": [f"{HOOK_MARKER} injected context body"],
                "hookName": "UserPromptSubmit",
                "toolUseID": "hook-abc123",
                "hookEvent": "UserPromptSubmit",
            },
        },
    ]
    session_path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return session_path


def test_fork_obeys_tool_visibility_for_hook_context(tmp_path, monkeypatch) -> None:
    """Fork mirrors the display policy: hook context stays only when tools are kept."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    project_dir = temp_home / ".claude" / "projects" / "demo-project"
    history_file = temp_home / ".claude" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("", encoding="utf-8")

    generated = iter(["thin-fork", "with-tools-fork"])
    monkeypatch.setattr(
        forking_module, "_generate_claude_session_id", lambda: next(generated)
    )

    source = _write_claude_session(project_dir, "hook-fork-source")

    commands_module.cmd_fork(str(source), ConversationFlags(color=False, paging=False))
    thin = (project_dir / "thin-fork.jsonl").read_text(encoding="utf-8")
    assert HOOK_MARKER not in thin, (
        f"Expected a default (no --tools) fork to drop hook additional-context. Got:\n{thin}"
    )

    commands_module.cmd_fork(
        str(source), ConversationFlags(show_tools=True, color=False, paging=False)
    )
    with_tools = (project_dir / "with-tools-fork.jsonl").read_text(encoding="utf-8")
    assert HOOK_MARKER in with_tools, (
        f"Expected a `--tools` fork to keep hook additional-context. Got:\n{with_tools}"
    )


def test_search_finds_hook_body_only_with_tools(tmp_path, monkeypatch) -> None:
    """A needle living only inside a hook body is searchable only when tools are on."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "hook-search.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "".join(
            json.dumps(entry, separators=(",", ":")) + "\n"
            for entry in [
                {
                    "type": "user",
                    "uuid": "u1",
                    "cwd": "/tmp/hook-search",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "message": {"role": "user", "content": "unrelated prompt"},
                },
                {
                    "type": "attachment",
                    "uuid": "att1",
                    "parentUuid": "u1",
                    "cwd": "/tmp/hook-search",
                    "timestamp": "2025-01-01T00:00:01Z",
                    "attachment": {
                        "type": "hook_additional_context",
                        "content": ["slice-hook-body-needle"],
                        "hookName": "SessionStart",
                        "toolUseID": "SessionStart",
                        "hookEvent": "SessionStart",
                    },
                },
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as hidden:
        cmd_search(
            "slice-hook-body-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )
    assert hidden.value.code == 1, (
        "Expected a hook-body needle to stay out of the default search space. "
        f"Got exit code: {hidden.value.code}"
    )

    with pytest.raises(SystemExit) as shown:
        cmd_search(
            "slice-hook-body-needle",
            ConversationFlags(show_tools=True, color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )
    assert shown.value.code == 0, (
        "Expected `--tools` search to reach hook additional-context bodies. "
        f"Got exit code: {shown.value.code}"
    )


def test_search_finds_generated_tool_name_with_tools(tmp_path, monkeypatch) -> None:
    """`AdditionalContext` is a rendered name absent from the raw JSONL, yet a
    `-t` search for it must still confirm the session (search parity with tools)."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "hook-name-search.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "".join(
            json.dumps(entry, separators=(",", ":")) + "\n"
            for entry in [
                {
                    "type": "user",
                    "uuid": "u1",
                    "cwd": "/tmp/hook-name-search",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "message": {"role": "user", "content": "unrelated prompt"},
                },
                {
                    "type": "attachment",
                    "uuid": "att1",
                    "parentUuid": "u1",
                    "cwd": "/tmp/hook-name-search",
                    "timestamp": "2025-01-01T00:00:01Z",
                    "attachment": {
                        "type": "hook_additional_context",
                        "content": ["some injected body"],
                        "hookName": "SessionStart",
                        "toolUseID": "SessionStart",
                        "hookEvent": "SessionStart",
                    },
                },
            ]
        ),
        encoding="utf-8",
    )
    assert "AdditionalContext" not in session_path.read_text(encoding="utf-8"), (
        "Test premise: the raw JSONL must not contain the literal 'AdditionalContext'."
    )

    with pytest.raises(SystemExit) as hidden:
        cmd_search(
            "AdditionalContext",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )
    assert hidden.value.code == 1, (
        "Expected the generated tool name to be unsearchable without --tools. "
        f"Got exit code: {hidden.value.code}"
    )

    with pytest.raises(SystemExit) as shown:
        cmd_search(
            "AdditionalContext",
            ConversationFlags(show_tools=True, color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )
    assert shown.value.code == 0, (
        "Expected `--tools` search for the generated tool name to confirm the session. "
        f"Got exit code: {shown.value.code}"
    )
