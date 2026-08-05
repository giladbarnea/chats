#!/usr/bin/env python3
"""Claude agent plumbing is abstracted away by the merged agent block.

The dispatch (`Agent`/`Task` tool_use + its tool_result) and the background-task
`<task-notification>` no longer render: their content lives in the agent block
(and its `<subagent-task>`). They stay hidden even with `--tools`, mirroring how
Codex's spawn/wait/close + subagent_notification are suppressed.
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
    "<task-id>afffad81cb99d3ae1</task-id>\n"
    "<tool-use-id>toolu_015Rn3jxAaywYknHrxdKHfmZ</tool-use-id>\n"
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
        {"type": "user", "message": {"role": "user", "content": TASK_NOTIFICATION_BODY}},
    ]
    return "\n".join(json.dumps(entry) for entry in entries)


def test_agent_dispatch_suppressed_even_with_tools():
    """The Agent/Task dispatch tool_use and its tool_result never render."""
    flags = ConversationFlags(show_tools=True, color="never")
    output = format_to_xml(parse_jsonl(_conversation_with_agent_plumbing(), flags), flags)

    assert 'name="Agent"' not in output, (
        f"Expected the Agent dispatch tool_use to be abstracted away. Got:\n{output}"
    )
    assert "DISPATCH_RESULT_MARKER" not in output, (
        f"Expected the dispatch tool_result to be abstracted away. Got:\n{output}"
    )


def test_task_notification_suppressed_even_with_tools():
    """The background-task notification never renders."""
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
