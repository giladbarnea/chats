#!/usr/bin/env python3
"""Tests for meta user messages linked to tool input/output chains."""

import json
from datetime import datetime

from chats import ConversationFlags, ToolFilter, cmd_parse, parse_jsonl
from chats.formatting import format_to_xml


def _utc_to_local_display(utc_iso: str) -> str:
    """Convert a UTC ISO timestamp to the local-time display string used in date attrs."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    local = dt.astimezone().replace(tzinfo=None)
    return local.strftime("%Y-%m-%d %H:%M")


def _build_tool_id_map(messages):
    """Build tool id map exactly like parse/search command flows."""
    tool_id_map = {}
    for msg in messages:
        for tool in msg.tools:
            if tool.get("type") == "tool_use" and "id" in tool:
                tool_id_map[tool["id"]] = tool.get("name", "Unknown")
    return tool_id_map


def test_meta_user_message_with_tools_includes_wrapper_attrs_and_tool_chain_link():
    """A meta user message becomes visible with tools and keeps chain-link attrs."""
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


def test_meta_user_message_hidden_by_default_without_tools():
    """Claude isMeta user messages should stay hidden unless tools are requested."""
    content = """{"type":"user","message":{"role":"user","content":[{"type":"text","text":"hello"}]}}
{"type":"user","isMeta":true,"sourceToolUseId":"toolu_0abc11111111111111111111111","message":{"role":"user","content":[{"type":"text","text":"meta"}]}}"""
    flags = ConversationFlags(color="never")
    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '<user-message i="1">' in output, (
        "Expected regular user message wrapper to remain unchanged."
    )
    assert '>\n## User\n\nhello\n</user-message>' in output, (
        "Expected the regular user message to remain visible."
    )
    assert 'sourceToolUserId="0abc"' not in output, (
        "Expected isMeta user messages to stay hidden without `--tools`."
    )
    assert '>\n## User\n\nmeta\n</user-message>' not in output, (
        "Expected isMeta user text to stay hidden without `--tools`."
    )


def test_skill_payload_meta_user_message_counts_as_tool_output():
    """Claude skill payloads linked to Skill calls should obey output tool filters."""
    skill_tool_id = "toolu_018FPXcYEL6XtjceAPCLAfd7"
    entries = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": skill_tool_id,
                        "name": "Skill",
                        "input": {"skill": "instruct-another-ai"},
                    }
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
                        "tool_use_id": skill_tool_id,
                        "content": "Launching skill: instruct-another-ai",
                    }
                ],
            },
        },
        {
            "type": "user",
            "isMeta": True,
            "sourceToolUseID": skill_tool_id,
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Base directory for this skill: /Users/giladbarnea/.claude/skills/instruct-another-ai\n\nSkill body content.",
                    }
                ],
            },
        },
    ]
    content = "\n".join(json.dumps(entry) for entry in entries)
    input_flags = ConversationFlags(
        show_tools=[ToolFilter(direction="input")],
        color="never",
    )
    messages = parse_jsonl(content, input_flags)
    tool_id_map = _build_tool_id_map(messages)
    input_output = format_to_xml(messages, input_flags, tool_id_map)

    assert '<tool-input name="Skill" id="018F">' in input_output, (
        f"Expected the Skill invocation to remain visible under input-only tool filtering. Got:\n{input_output}"
    )
    assert "Base directory for this skill" not in input_output, (
        "Expected the skill payload to be hidden by `-t:i` because it is a tool output. "
        f"Got:\n{input_output}"
    )

    output_flags = ConversationFlags(
        show_tools=[ToolFilter(direction="output")],
        color="never",
    )
    output_output = format_to_xml(messages, output_flags, tool_id_map)
    assert '<tool-output name="Skill" id="018F">' in output_output, (
        f"Expected the skill payload to render as a Skill tool output. Got:\n{output_output}"
    )
    assert "Base directory for this skill" in output_output, (
        f"Expected the skill payload body to be present under output tool filtering. Got:\n{output_output}"
    )


def test_assistant_and_agent_messages_include_model_attribute():
    """Assistant messages (regular and agent) render model attr with claude- prefix stripped."""
    content = '{"type":"user","message":{"role":"user","content":"hello"}}\n{"type":"assistant","message":{"role":"assistant","model":"claude-opus-4-6","content":[{"type":"text","text":"hi"}]}}\n{"type":"assistant","agentId":"agent-abc123","message":{"role":"assistant","model":"claude-sonnet-4-5-20250929","content":[{"type":"text","text":"agent reply"}]}}'
    flags = ConversationFlags(show_agents=True, color="never")
    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert 'model="opus-4-6"' in output, (
        f"Expected assistant message to include model attr with 'claude-' stripped. Got:\n{output}"
    )
    assert 'agent_id="agent-abc123"' in output, (
        f"Expected agent message to retain agent_id attr. Got:\n{output}"
    )
    assert 'model="sonnet-4-5-20250929"' in output, (
        f"Expected agent message to include model attr with 'claude-' stripped. Got:\n{output}"
    )


def test_user_messages_have_no_model_attribute():
    """User messages never render a model attr, even when adjacent to assistant with model."""
    content = '{"type":"user","message":{"role":"user","content":"hello"}}\n{"type":"assistant","message":{"role":"assistant","model":"claude-opus-4-6","content":[{"type":"text","text":"reply"}]}}'
    flags = ConversationFlags(color="never")
    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    user_tag_line = [line for line in output.splitlines() if "<user-message" in line]
    assert len(user_tag_line) == 1, (
        f"Expected exactly 1 user-message tag. Got:\n{output}"
    )
    assert "model=" not in user_tag_line[0], (
        f"User message must not have a model attribute. Got tag: {user_tag_line[0]}"
    )


def test_message_wrappers_include_date_attribute_from_timestamp():
    """Plain XML message wrappers should expose the message's calendar date."""
    content = (
        '{"type":"user","timestamp":"2026-06-21T09:30:00Z",'
        '"message":{"role":"user","content":"hello"}}\n'
        '{"type":"assistant","timestamp":"2026-06-21T09:31:00Z",'
        '"message":{"role":"assistant","model":"claude-opus-4-8",'
        '"content":[{"type":"text","text":"reply"}]}}'
    )
    flags = ConversationFlags(color="never")
    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    user_date = _utc_to_local_display("2026-06-21T09:30:00Z")
    assistant_date = _utc_to_local_display("2026-06-21T09:31:00Z")
    assert f'<user-message i="1" date="{user_date}">' in output, (
        f"Expected user wrapper to include date attr. Got:\n{output}"
    )
    assert (
        f'<assistant-response i="2" model="opus-4-8" date="{assistant_date}">' in output
    ), f"Expected assistant wrapper to include model then date attrs. Got:\n{output}"


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


def test_string_command_input_user_message_hidden_by_default():
    """Claude command input strings should stay hidden in default parse output."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-name>/model</command-name>\\n"
        "            <command-message>model</command-message>\\n"
        '            <command-args>opus</command-args>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert output == "", (
        "Expected default parse output to hide command-tag user strings entirely. "
        f"Got:\n{output}"
    )


def test_string_command_output_user_message_hidden_by_default():
    """Claude local command stdout strings should stay hidden in default parse output."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        '<local-command-stdout>Set model to \\u001b[1mOpus 4.7\\u001b[22m</local-command-stdout>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert output == "", (
        "Expected default parse output to hide local-command stdout user strings entirely. "
        f"Got:\n{output}"
    )


def test_string_command_input_with_reordered_tags_hidden_by_default():
    """Command-tag user strings should stay hidden even when tag order varies."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-message>export is running…</command-message>\\n"
        '<command-name>/export</command-name>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert output == "", (
        "Expected reordered command-tag user strings to stay hidden by default. "
        f"Got:\n{output}"
    )


def test_string_command_input_with_multiple_indentation_levels_hidden_by_default():
    """Nested command-tag user strings should stay hidden by default."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-name>/agent</command-name>\\n"
        "  <command-message>run</command-message>\\n"
        '    <command-args>full</command-args>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert output == "", (
        "Expected nested command-tag user strings to stay hidden by default. "
        f"Got:\n{output}"
    )


def test_string_command_input_with_scalar_variants_hidden_by_default():
    """Scalar-shaped command-tag user strings should stay hidden by default."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-name>/config</command-name>\\n"
        "<command-count>-42</command-count>\\n"
        "<command-enabled>true</command-enabled>\\n"
        '<command-note>alpha</command-note>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert output == "", (
        "Expected scalar-shaped command-tag user strings to stay hidden by default. "
        f"Got:\n{output}"
    )


def test_away_summary_system_message_renders_as_recap_without_disable_suffix():
    """Claude away-summary system entries should render as Recap blocks."""
    content = (
        '{"type":"system","subtype":"away_summary","content":"'
        "Fixing the Elaborate-on-selected-text feature in the mobile web client. "
        "The overlay-closing bug is patched; next step is running a fresh "
        'end-to-end test to confirm the fix works. (disable recaps in /config)"}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '<recap i="1">' in output, (
        f"Expected away_summary system messages to render as <recap>. Got:\n{output}"
    )
    assert "## Recap" in output, f"Expected recap header in output. Got:\n{output}"
    assert "disable recaps in /config" not in output, (
        f"Expected recap suffix to be stripped from visible output. Got:\n{output}"
    )
    assert (
        "Fixing the Elaborate-on-selected-text feature in the mobile web client."
        in output
    ), f"Expected recap body to be preserved. Got:\n{output}"


def test_compaction_user_message_renders_as_compaction_block_by_default():
    """Claude isCompactSummary user entries render as a Compaction block by default."""
    content = (
        '{"type":"user","isCompactSummary":true,"message":{"role":"user","content":"'
        "This session is being continued from a previous conversation that ran out "
        "of context.\\n\\nSummary:\\n1. Primary Request and Intent."
        '"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '<compaction i="1">' in output, (
        f"Expected isCompactSummary user entries to render as <compaction>. Got:\n{output}"
    )
    assert "## Compaction" in output, (
        f"Expected the Compaction header in output. Got:\n{output}"
    )
    assert "<user-message" not in output, (
        f"A compaction entry must not render as a plain user message. Got:\n{output}"
    )
    assert "Primary Request and Intent." in output, (
        f"Expected the compaction body to be preserved. Got:\n{output}"
    )
