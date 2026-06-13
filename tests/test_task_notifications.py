#!/usr/bin/env python3
"""Tests for Claude background-task notification messages (TaskNotification tool)."""

import json

from chats import ConversationFlags, parse_jsonl, tool_filter
from chats.formatting import format_to_json, format_to_xml

TASK_NOTIFICATION_BODY = (
    "<task-notification>\n"
    "<task-id>afffad81cb99d3ae1</task-id>\n"
    "<tool-use-id>toolu_015Rn3jxAaywYknHrxdKHfmZ</tool-use-id>\n"
    "<output-file>/tmp/tasks/afffad81cb99d3ae1.output</output-file>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Analyze question 1" completed</summary>\n'
    "<result>Done. Findings written to `findings.md`.\n\n"
    "**Highlights** follow.</result>\n"
    "<usage><subagent_tokens>120889</subagent_tokens><tool_uses>41</tool_uses>"
    "<duration_ms>519544</duration_ms></usage>\n"
    "</task-notification>"
)


def _conversation_with_notification() -> str:
    entries = [
        {"type": "user", "message": {"role": "user", "content": "hello"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "hi"}],
            },
        },
        {
            "type": "queue-operation",
            "operation": "enqueue",
            "content": TASK_NOTIFICATION_BODY,
        },
        {
            "type": "user",
            "message": {"role": "user", "content": TASK_NOTIFICATION_BODY},
            "origin": {"kind": "task-notification"},
            "promptSource": "system",
        },
    ]
    return "\n".join(json.dumps(entry) for entry in entries)


def test_task_notification_hidden_by_default():
    """Task notifications are tool-class content, not user prose: hidden without --tools."""
    flags = ConversationFlags(color="never")
    messages = parse_jsonl(_conversation_with_notification(), flags)
    output = format_to_xml(messages, flags)

    assert len(messages) == 2, (
        f"Expected only the regular user+assistant messages to survive default "
        f"parsing; the task notification must not become a message. Got "
        f"{len(messages)} messages:\n{output}"
    )
    assert "task-notification" not in output, (
        f"Expected the raw task-notification payload to stay hidden by default. "
        f"Got:\n{output}"
    )


def test_task_notification_renders_as_tool_with_structured_attributes():
    """With --tools, the notification renders as a TaskNotification tool-input
    whose structured fields become XML attributes and whose result is the body."""
    flags = ConversationFlags(show_tools=True, color="never")
    messages = parse_jsonl(_conversation_with_notification(), flags)
    output = format_to_xml(messages, flags)

    tool_lines = [line for line in output.splitlines() if "<tool-input" in line]
    assert len(tool_lines) == 1, (
        f"Expected exactly one TaskNotification tool-input tag. Got:\n{output}"
    )
    tag_line = tool_lines[0]

    assert 'name="TaskNotification"' in tag_line, (
        f"Expected the notification to classify as tool TaskNotification. "
        f"Got tag: {tag_line}"
    )
    for expected_attribute in (
        'tool_use_id="015R"',
        'status="completed"',
        "summary=\"Agent 'Analyze question 1' completed\"",
    ):
        assert expected_attribute in tag_line, (
            f"Expected structured attribute {expected_attribute} on the "
            f"TaskNotification tag. Got tag: {tag_line}"
        )

    for dropped_attribute in (
        "task_id=",
        "output_file=",
        "subagent_tokens=",
        "tool_uses=",
        "duration_ms=",
    ):
        assert dropped_attribute not in tag_line, (
            f"Expected attribute {dropped_attribute} to be dropped from the "
            f"TaskNotification tag. Got tag: {tag_line}"
        )

    assert "Done. Findings written to `findings.md`." in output, (
        f"Expected the result markdown to render as the tool body. Got:\n{output}"
    )
    assert "<result>" not in output, (
        f"Expected the raw <result> wrapper tags to be stripped from the body. "
        f"Got:\n{output}"
    )


def test_task_notification_attribute_double_quotes_become_single():
    """Embedded double quotes in attribute values are downgraded to single
    quotes (not escaped), keeping the unescaped-attribute convention valid."""
    flags = ConversationFlags(show_tools=True, color="never")
    messages = parse_jsonl(_conversation_with_notification(), flags)
    output = format_to_xml(messages, flags)

    tag_line = next(line for line in output.splitlines() if "<tool-input" in line)
    assert '"Analyze question 1"' not in tag_line, (
        f"Expected embedded double quotes to be gone from the attribute value. "
        f"Got tag: {tag_line}"
    )
    assert "'Analyze question 1'" in tag_line, (
        f"Expected embedded double quotes downgraded to single quotes. "
        f"Got tag: {tag_line}"
    )


def test_task_notification_matches_name_tool_filter():
    """`-t TaskNotification` selects the notification like any named tool."""
    flags = ConversationFlags(
        show_tools=[tool_filter.parse_tool_spec("TaskNotification")], color="never"
    )
    messages = parse_jsonl(_conversation_with_notification(), flags)
    output = format_to_xml(messages, flags)

    assert 'name="TaskNotification"' in output, (
        f"Expected `-t TaskNotification` to show the notification tool. "
        f"Got:\n{output}"
    )


def test_task_notification_excluded_by_other_name_tool_filter():
    """`-t Bash` must not leak task notifications into the output."""
    flags = ConversationFlags(
        show_tools=[tool_filter.parse_tool_spec("Bash")], color="never"
    )
    messages = parse_jsonl(_conversation_with_notification(), flags)
    output = format_to_xml(messages, flags)

    assert "TaskNotification" not in output, (
        f"Expected `-t Bash` to exclude the TaskNotification tool. Got:\n{output}"
    )


def test_task_notification_json_output_is_structured():
    """`-f json` exposes the notification as a typed tool block with its fields."""
    flags = ConversationFlags(show_tools=True, color="never")
    messages = parse_jsonl(_conversation_with_notification(), flags)
    output = json.loads(format_to_json(messages, flags))

    tool_blocks = [
        block
        for message in output
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("name") == "TaskNotification"
    ]
    assert len(tool_blocks) == 1, (
        f"Expected exactly one TaskNotification tool block in JSON output. "
        f"Got:\n{json.dumps(output, indent=2)}"
    )
    block = tool_blocks[0]
    assert block.get("type") == "tool-input", (
        f"Expected the notification block to be typed tool-input. Got: {block}"
    )
    assert block.get("tool_use_id") == "015R", (
        f"Expected structured tool_use_id linkage field. Got: {block}"
    )
    assert block.get("status") == "completed", (
        f"Expected structured status field. Got: {block}"
    )
    assert block.get("result", "").startswith("Done. Findings written"), (
        f"Expected the result markdown as a structured field. Got: {block}"
    )
    assert "task_id" not in block, (
        f"Expected the dropped task_id field to be absent from JSON. Got: {block}"
    )
    assert "duration_ms" not in block, (
        f"Expected the dropped duration_ms field to be absent from JSON. Got: {block}"
    )
