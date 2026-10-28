#!/usr/bin/env python3
"""Claude agent dispatch and delivered results require --agents, not --tools.

Delivered replies remain available even when the separate child file is missing.
"""

import json
from pathlib import Path

from chats import ConversationFlags, Message, parse_jsonl as _parse_jsonl
from chats.formatting import format_to_xml


CLAUDE_SOURCE_PATH = Path.home() / ".claude" / "projects" / "tests" / "session.jsonl"


def parse_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse test content through an explicit Claude session path."""
    return _parse_jsonl(content, flags, source_path=CLAUDE_SOURCE_PATH)


TASK_NOTIFICATION_BODY = (
    "<task-notification>\n"
    "<task-id>a0000000000000001</task-id>\n"
    "<tool-use-id>toolu_dispatch</tool-use-id>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Analyze question 1" completed</summary>\n'
    "<result>NOTIFICATION_RESULT_MARKER</result>\n"
    "</task-notification>"
)


def _conversation_with_agent_plumbing() -> str:
    """A Claude session that dispatches an Agent, gets its result, runs a normal
    Bash tool, and receives a background task-notification."""
    entries = [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Dispatching an agent."},
                    {
                        "type": "tool_use",
                        "id": "toolu_dispatch",
                        "name": "Agent",
                        "input": {"subagent_type": "general-purpose", "prompt": "say hi"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_dispatch",
                        "content": "DISPATCH_RESULT_MARKER\nagentId: abc123",
                    }
                ],
            },
        },
        {
            "type": "assistant",
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
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_bash", "content": "ok"}
                ],
            },
        },
        {"type": "user", "origin": {"kind": "task-notification"}, "message": {"role": "user", "content": TASK_NOTIFICATION_BODY}},
    ]
    return "\n".join(json.dumps(entry) for entry in entries)


def test_agents_keep_dispatch_and_delivered_results_without_a_child_file():
    flags = ConversationFlags(show_agents=True, color="never")
    output = format_to_xml(parse_jsonl(_conversation_with_agent_plumbing(), flags), flags)
    for marker in ('name="Agent"', "DISPATCH_RESULT_MARKER", "NOTIFICATION_RESULT_MARKER"):
        assert marker in output, f"Missing {marker} under --agents: {output}"
    assert 'agent_id="a0000000000000001"' in output, output
    assert "<task-notification>" not in output, output


def test_native_search_finds_delivered_agent_reply_without_child_file(tmp_path: Path):
    import os
    import subprocess
    import sys

    home = tmp_path / "home"
    path = home / ".claude/projects/project/delivered.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(_conversation_with_agent_plumbing() + "\n", encoding="utf-8")
    for marker in ("DISPATCH_RESULT_MARKER", "NOTIFICATION_RESULT_MARKER"):
        result = subprocess.run([str(Path(sys.executable).with_name("ch")), "search", marker, "--agents", "--only-id"],
                                env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)
        assert result.stdout.strip() == "delivered", result


def test_batched_notifications_keep_only_proven_agent_results():
    records = [json.loads(line) for line in _conversation_with_agent_plumbing().splitlines()]
    records[-1]["message"]["content"] = TASK_NOTIFICATION_BODY + "\n" + TASK_NOTIFICATION_BODY.replace(
        "toolu_dispatch", "toolu_bash").replace("NOTIFICATION_RESULT_MARKER", "SHELL_RESULT_MARKER")
    flags = ConversationFlags(show_agents=True, color="never")
    output = format_to_xml(parse_jsonl("\n".join(map(json.dumps, records)), flags), flags)
    assert "NOTIFICATION_RESULT_MARKER" in output, output
    assert "SHELL_RESULT_MARKER" not in output, output


def test_pasted_notification_is_not_agent_delivery():
    records = [json.loads(line) for line in _conversation_with_agent_plumbing().splitlines()]
    records[-1].pop("origin")
    flags = ConversationFlags(show_agents=True, color="never")
    messages = parse_jsonl("\n".join(map(json.dumps, records)), flags)
    assert not any(message.agent_id == "a0000000000000001" for message in messages), messages


def test_user_fork_delivery_survives_missing_child_and_no_agent_tool():
    task = "aresearch-0123456789ab1234"
    records = [
        {"type": "system", "subtype": "local_command", "content": "<command-name>/subtask</command-name>"},
        {"type": "system", "subtype": "local_command", "content": "<local-command-stdout>⑂ forked research (1234)</local-command-stdout>"},
        {"type": "user", "origin": {"kind": "task-notification"}, "message": {"role": "user", "content":
         f"<task-notification><task-id>{task}</task-id><result>USER_FORK_DELIVERED</result></task-notification>"}},
    ]
    flags = ConversationFlags(show_agents=True, color="never")
    output = format_to_xml(parse_jsonl("\n".join(map(json.dumps, records)), flags), flags)
    assert "USER_FORK_DELIVERED" in output and f'agent_id="{task}"' in output, output


def test_agent_dispatch_suppressed_even_with_tools():
    """Tools alone do not expose agent dispatch or its result."""
    flags = ConversationFlags(show_tools=True, color="never")
    output = format_to_xml(parse_jsonl(_conversation_with_agent_plumbing(), flags), flags)

    assert 'name="Agent"' not in output, (
        f"Expected the Agent dispatch tool_use to be abstracted away. Got:\n{output}"
    )
    assert "DISPATCH_RESULT_MARKER" not in output, (
        f"Expected the dispatch tool_result to be abstracted away. Got:\n{output}"
    )


def test_task_notification_suppressed_even_with_tools():
    """Tools alone do not expose delivered agent reports."""
    flags = ConversationFlags(show_tools=True, color="never")
    output = format_to_xml(parse_jsonl(_conversation_with_agent_plumbing(), flags), flags)

    assert "task-notification" not in output, (
        f"Expected the task-notification to be abstracted away. Got:\n{output}"
    )
    assert "NOTIFICATION_RESULT_MARKER" not in output, (
        f"Expected the notification body to be gone. Got:\n{output}"
    )


def test_normal_tools_and_text_survive_suppression():
    """Suppression is surgical: ordinary tools and assistant prose are untouched."""
    flags = ConversationFlags(show_tools=True, color="never")
    output = format_to_xml(parse_jsonl(_conversation_with_agent_plumbing(), flags), flags)

    assert 'name="Bash"' in output, f"Expected normal Bash tool to remain. Got:\n{output}"
    assert "NORMAL_TOOL_MARKER" in output, f"Expected normal tool body to remain. Got:\n{output}"
    assert "Dispatching an agent." in output, (
        f"Expected the assistant's narration to remain. Got:\n{output}"
    )


def test_dispatch_hidden_by_default_too():
    """Default (no --tools) also shows none of the plumbing."""
    flags = ConversationFlags(color="never")
    output = format_to_xml(parse_jsonl(_conversation_with_agent_plumbing(), flags), flags)

    for marker in ('name="Agent"', "DISPATCH_RESULT_MARKER", "task-notification"):
        assert marker not in output, (
            f"Expected '{marker}' hidden by default. Got:\n{output}"
        )
