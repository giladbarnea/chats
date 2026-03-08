#!/usr/bin/env python3
"""Tests for meta user messages linked to tool input/output chains."""

from conversations import ConversationFlags, cmd_parse, parse_jsonl
from conversations.formatting import format_to_xml


def _build_tool_id_map(messages):
    """Build tool id map exactly like parse/search command flows."""
    tool_id_map = {}
    for msg in messages:
        for tool in msg.tools:
            if tool.get("type") == "tool_use" and "id" in tool:
                tool_id_map[tool["id"]] = tool.get("name", "Unknown")
    return tool_id_map


def test_meta_user_message_includes_wrapper_attrs_and_tool_chain_link():
    """A meta user message gets isMeta + sourceToolUserId wrapper attrs."""
    content = """{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"toolu_013cAqxRaJroBvWdutKHWm47","name":"Skill","input":{"prompt":"go"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_013cAqxRaJroBvWdutKHWm47","content":"ok"}]}}
{"type":"user","isMeta":true,"sourceToolUseID":"toolu_013cAqxRaJroBvWdutKHWm47","message":{"role":"user","content":[{"type":"text","text":"follow up meta note"}]}}"""
    flags = ConversationFlags(show_tools=True, color="never")
    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags, _build_tool_id_map(messages))

    assert '<tool-input name="Skill" id="013c">' in output, (
        "Expected tool input to render with short id='013c' for chain linkage."
    )
    assert '<tool-output name="Skill" id="013c">' in output, (
        "Expected tool output to render with name='Skill' and short id='013c' for chain linkage."
    )
    assert '<user-message i="3" isMeta="true" sourceToolUserId="013c">' in output, (
        "Expected meta user wrapper attrs with short sourceToolUserId."
    )


def test_non_meta_user_message_has_no_meta_wrapper_attrs():
    """Regular user messages should keep existing wrapper shape."""
    content = """{"type":"user","message":{"role":"user","content":[{"type":"text","text":"hello"}]}}
{"type":"user","isMeta":true,"sourceToolUseId":"toolu_0abc11111111111111111111111","message":{"role":"user","content":[{"type":"text","text":"meta"}]}}"""
    flags = ConversationFlags(color="never")
    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '<user-message i="1">' in output, (
        "Expected regular user message wrapper to remain unchanged."
    )
    assert 'sourceToolUserId="0abc"' in output, (
        "Expected sourceToolUseId variant to map to sourceToolUserId short id."
    )


def test_cmd_parse_slice_preserves_tool_name_on_tool_output(tmp_path, capsys):
    """Sliced parse output should still know the originating tool name."""
    content = """{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"toolu_013cAqxRaJroBvWdutKHWm47","name":"Skill","input":{"prompt":"go"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_013cAqxRaJroBvWdutKHWm47","content":"ok"}]}}"""
    conversation_path = tmp_path / "tool-chain.jsonl"
    conversation_path.write_text(content, encoding="utf-8")

    cmd_parse(
        ConversationFlags(show_tools=True, color="never"),
        str(conversation_path),
        "2",
        None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert '<tool-output name="Skill" id="013c">' in captured.out, (
        "Expected sliced parse output to preserve the originating tool name on "
        f"tool-output tags. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
