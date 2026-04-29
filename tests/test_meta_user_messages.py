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


def test_string_command_input_user_message_renders_as_yaml_block():
    """Claude command input strings should render as indentation-driven pseudo-YAML."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-name>/model</command-name>\\n"
        "            <command-message>model</command-message>\\n"
        '            <command-args>opus</command-args>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '<user-command-input i="1">' in output, (
        "Expected command-tag user string to switch from <user-message> to "
        f"<user-command-input>. Got:\n{output}"
    )
    assert (
        '```yaml\nname: "/model"\n  message: "model"\n  args: "opus"\n```' in output
    ), (
        "Expected command-tag user string to render as indentation-driven YAML-like "
        f"XML-like command tags. Got:\n{output}"
    )


def test_string_command_output_user_message_strips_stdout_wrapper():
    """Claude local command stdout strings should render as bare command output."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        '<local-command-stdout>Set model to \\u001b[1mOpus 4.7\\u001b[22m</local-command-stdout>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '<user-command-output i="1">' in output, (
        "Expected local-command stdout user string to switch from <user-message> "
        f"to <user-command-output>. Got:\n{output}"
    )
    assert "Set model to \u001b[1mOpus 4.7\u001b[22m" in output, (
        "Expected command output wrapper tags to be stripped while preserving the "
        f"stdout body. Got:\n{output}"
    )
    assert "local-command-stdout" not in output, (
        "Expected local-command-stdout XML tags to be removed from rendered output. "
        f"Got:\n{output}"
    )


def test_string_command_input_preserves_source_order_for_same_indent_level():
    """Command input output should preserve source order when lines share an indent level."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-message>export is running…</command-message>\\n"
        '<command-name>/export</command-name>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert '```yaml\nmessage: "export is running…"\nname: "/export"\n```' in output, (
        "Expected command input YAML-like output to preserve source line order when "
        f"source tags arrive in a different order. Got:\n{output}"
    )


def test_string_command_input_supports_multiple_indentation_levels():
    """Deeper indentation should produce deeper rendered hierarchy levels."""
    content = (
        '{"type":"user","message":{"role":"user","content":"'
        "<command-name>/agent</command-name>\\n"
        "  <command-message>run</command-message>\\n"
        '    <command-args>full</command-args>"}}'
    )
    flags = ConversationFlags(color="never")

    messages = parse_jsonl(content, flags)
    output = format_to_xml(messages, flags)

    assert (
        '```yaml\nname: "/agent"\n  message: "run"\n    args: "full"\n```' in output
    ), (
        "Expected indentation depth in command-tag input to carry through into the "
        f"rendered YAML-like hierarchy. Got:\n{output}"
    )


def test_string_command_input_leaves_numeric_and_boolean_scalars_unquoted():
    """Numeric and lowercase boolean command values should stay as bare YAML scalars."""
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

    assert (
        '```yaml\nname: "/config"\ncount: -42\nenabled: true\nnote: "alpha"\n```'
        in output
    ), (
        "Expected command input scalars to quote by default while leaving numeric "
        f"and lowercase boolean values bare. Got:\n{output}"
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
