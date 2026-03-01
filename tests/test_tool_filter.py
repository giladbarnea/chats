#!/usr/bin/env python3
"""
Tests for granular tool filtering: parsing, matching, and integration.

Covers:
- Spec parsing (lax syntax: order-independent, short/long forms, optional colon)
- Filter matching (criteria AND'd, negation inverts, multiple filters OR'd)
- Integration with Message.iter_visible_parts (direction, name, error, shortening)
"""

import pytest

from conversations import ConversationFlags, Message
from conversations.parts import MessagePartKind
from conversations.tool_filter import ToolFilter, parse_tool_spec


# =============================================================================
# Shared tool dicts
# =============================================================================

BASH_USE = {"type": "tool_use", "name": "Bash", "id": "toolu_01", "input": {"command": "ls"}}
BASH_RESULT = {"type": "tool_result", "tool_use_id": "toolu_01", "content": "file1.txt"}
BASH_ERROR = {"type": "tool_result", "tool_use_id": "toolu_01", "content": "cmd failed", "is_error": True}
READ_USE = {"type": "tool_use", "name": "Read", "id": "toolu_02", "input": {"file_path": "f.txt"}}
READ_RESULT = {"type": "tool_result", "tool_use_id": "toolu_02", "content": "content of f.txt"}

ID_MAP = {"toolu_01": "Bash", "toolu_02": "Read"}


def make_message(*tools):
    """Create an assistant Message with the given tool dicts."""
    return Message(role="assistant", text="text", tools=list(tools))


def tool_parts_from(msg, flags, tool_id_map=None):
    """Return only the TOOL MessageParts from iter_visible_parts."""
    return [p for p in msg.iter_visible_parts(flags, tool_id_map) if p.kind == MessagePartKind.TOOL]


# =============================================================================
# Parsing: spec string -> ToolFilter
# =============================================================================

class TestParseToolSpec:
    """Spec string is parsed into correct ToolFilter regardless of syntax form."""

    @pytest.mark.parametrize("spec, expected", [
        # --- Bare modifier, short form ---
        ("o",       dict(direction="output")),
        ("i",       dict(direction="input")),
        ("s",       dict(short=True)),
        ("e",       dict(error_only=True)),
        # --- Bare modifier, long form ---
        ("output",  dict(direction="output")),
        ("input",   dict(direction="input")),
        ("short",   dict(short=True)),
        ("error",   dict(error_only=True)),
        # --- Name + modifier ---
        ("Bash:i",  dict(name="Bash", direction="input")),
        ("Read:o",  dict(name="Read", direction="output")),
        ("Read:o:s", dict(name="Read", direction="output", short=True)),
        ("Bash:e",  dict(name="Bash", error_only=True)),
        # --- Order independence ---
        ("i:Bash",          dict(name="Bash", direction="input")),
        ("short:Bash:i",    dict(name="Bash", direction="input", short=True)),
        ("s:o:Read",        dict(name="Read", direction="output", short=True)),
        # --- Optional leading colon ---
        (":o",      dict(direction="output")),
        (":o:s",    dict(direction="output", short=True)),
        (":short",  dict(short=True)),
        # --- Mixed short/long modifiers ---
        ("Read:output:s",   dict(name="Read", direction="output", short=True)),
        ("Bash:i:short",    dict(name="Bash", direction="input", short=True)),
        # --- Negation ---
        ("!Bash",   dict(name="Bash", negate=True)),
        ("!Bash:o", dict(name="Bash", direction="output", negate=True)),
        ("!o",      dict(direction="output", negate=True)),
        # --- Name only ---
        ("Bash",    dict(name="Bash")),
        ("Read",    dict(name="Read")),
        # --- Empty (bare --tools) ---
        ("",        dict()),
    ], ids=lambda x: repr(x) if isinstance(x, str) else None)
    def test_parse(self, spec, expected):
        tf = parse_tool_spec(spec)
        defaults = dict(name=None, negate=False, direction=None, error_only=False, short=False)
        for field, default in defaults.items():
            want = expected.get(field, default)
            got = getattr(tf, field)
            assert got == want, f"parse_tool_spec({spec!r}).{field}: expected {want!r}, got {got!r}"


# =============================================================================
# Matching: ToolFilter.matches() against tool dicts
# =============================================================================

class TestToolFilterMatching:
    """ToolFilter.matches() selects tools based on criteria (AND'd), negation inverts."""

    def test_no_criteria_matches_everything(self):
        tf = ToolFilter()
        for tool in [BASH_USE, BASH_RESULT, READ_USE, READ_RESULT, BASH_ERROR]:
            assert tf.matches(tool, ID_MAP), (
                f"ToolFilter() should match {tool.get('type')}/{tool.get('name', tool.get('tool_use_id'))}"
            )

    def test_name_only(self):
        tf = ToolFilter(name="Bash")
        assert tf.matches(BASH_USE, ID_MAP)
        assert tf.matches(BASH_RESULT, ID_MAP)
        assert not tf.matches(READ_USE, ID_MAP)
        assert not tf.matches(READ_RESULT, ID_MAP)

    def test_direction_input(self):
        tf = ToolFilter(direction="input")
        assert tf.matches(BASH_USE, ID_MAP)
        assert tf.matches(READ_USE, ID_MAP)
        assert not tf.matches(BASH_RESULT, ID_MAP)
        assert not tf.matches(READ_RESULT, ID_MAP)

    def test_direction_output(self):
        tf = ToolFilter(direction="output")
        assert not tf.matches(BASH_USE, ID_MAP)
        assert tf.matches(BASH_RESULT, ID_MAP)
        assert tf.matches(READ_RESULT, ID_MAP)
        assert tf.matches(BASH_ERROR, ID_MAP)

    def test_error_only(self):
        tf = ToolFilter(error_only=True)
        assert tf.matches(BASH_ERROR, ID_MAP)
        assert not tf.matches(BASH_RESULT, ID_MAP), "Non-error result should not match"
        assert not tf.matches(BASH_USE, ID_MAP), "tool_use should not match"

    def test_criteria_anded(self):
        """name + direction: only Bash inputs, not Bash outputs or Read inputs."""
        tf = ToolFilter(name="Bash", direction="input")
        assert tf.matches(BASH_USE, ID_MAP)
        assert not tf.matches(BASH_RESULT, ID_MAP)
        assert not tf.matches(READ_USE, ID_MAP)

    def test_negation(self):
        """!Bash:o matches everything EXCEPT Bash outputs."""
        tf = ToolFilter(name="Bash", direction="output", negate=True)
        assert tf.matches(BASH_USE, ID_MAP), "Bash input should still match"
        assert not tf.matches(BASH_RESULT, ID_MAP), "Bash output should not match"
        assert not tf.matches(BASH_ERROR, ID_MAP), "Bash error output should not match"
        assert tf.matches(READ_USE, ID_MAP), "Read input should match"
        assert tf.matches(READ_RESULT, ID_MAP), "Read output should match"


# =============================================================================
# Integration: filters in Message.iter_visible_parts
# =============================================================================

class TestFilterIntegration:
    """ToolFilter list controls what iter_visible_parts yields."""

    def setup_method(self):
        self.msg = make_message(BASH_USE, BASH_RESULT, READ_USE, READ_RESULT)
        # Global id_map (as cmd_parse builds it)
        self.id_map = ID_MAP

    def test_show_tools_false_hides_all(self):
        flags = ConversationFlags(show_tools=False)
        assert tool_parts_from(self.msg, flags) == []

    def test_show_tools_true_shows_all(self):
        flags = ConversationFlags(show_tools=True)
        assert len(tool_parts_from(self.msg, flags, self.id_map)) == 4

    def test_bare_filter_shows_all(self):
        """[ToolFilter()] (bare --tools) shows everything."""
        flags = ConversationFlags(show_tools=[ToolFilter()])
        assert len(tool_parts_from(self.msg, flags, self.id_map)) == 4

    def test_direction_output_only(self):
        flags = ConversationFlags(show_tools=[ToolFilter(direction="output")])
        parts = tool_parts_from(self.msg, flags, self.id_map)
        assert len(parts) == 2, f"Expected 2 outputs, got {len(parts)}"
        assert all(p.data.tag == "tool-output" for p in parts)

    def test_name_and_direction(self):
        """Bash:i → only Bash tool-input."""
        flags = ConversationFlags(show_tools=[ToolFilter(name="Bash", direction="input")])
        parts = tool_parts_from(self.msg, flags, self.id_map)
        assert len(parts) == 1
        assert parts[0].data.tag == "tool-input"
        assert dict(parts[0].data.attrs).get("name") == "Bash"

    def test_multiple_filters_ored(self):
        """Read:o + Bash:i → Read output and Bash input (2 parts, in message order)."""
        flags = ConversationFlags(show_tools=[
            ToolFilter(name="Read", direction="output"),
            ToolFilter(name="Bash", direction="input"),
        ])
        parts = tool_parts_from(self.msg, flags, self.id_map)
        assert len(parts) == 2
        # Message order: Bash use comes before Read result
        assert parts[0].data.tag == "tool-input"
        assert dict(parts[0].data.attrs).get("name") == "Bash"
        assert parts[1].data.tag == "tool-output"

    def test_negation_excludes_targeted(self):
        """!Bash → everything except Bash (Read use + Read result)."""
        flags = ConversationFlags(show_tools=[ToolFilter(name="Bash", negate=True)])
        parts = tool_parts_from(self.msg, flags, self.id_map)
        assert len(parts) == 2
        assert parts[0].data.tag == "tool-input"
        assert dict(parts[0].data.attrs).get("name") == "Read"

    def test_error_filter(self):
        """error_only → only tool_results with is_error=True."""
        msg = make_message(BASH_USE, BASH_ERROR, READ_USE, READ_RESULT)
        flags = ConversationFlags(show_tools=[ToolFilter(error_only=True)])
        parts = tool_parts_from(msg, flags, self.id_map)
        assert len(parts) == 1
        assert dict(parts[0].data.attrs).get("is_error") == "true"


class TestPerToolShortening:
    """The :s modifier shortens only matching tools, not others."""

    def test_short_flag_truncates(self):
        long_content = "A" * 500
        msg = make_message(
            {"type": "tool_use", "name": "Read", "id": "toolu_02", "input": {"file_path": "f.txt"}},
            {"type": "tool_result", "tool_use_id": "toolu_02", "content": long_content},
        )

        parts_short = tool_parts_from(
            msg,
            ConversationFlags(show_tools=[ToolFilter(name="Read", short=True)]),
            ID_MAP,
        )
        parts_full = tool_parts_from(
            msg,
            ConversationFlags(show_tools=[ToolFilter(name="Read")]),
            ID_MAP,
        )

        short_result = parts_short[1].data.content
        full_result = parts_full[1].data.content
        assert len(short_result) < len(full_result), (
            f"short ({len(short_result)} chars) should be < full ({len(full_result)} chars)"
        )

    def test_global_short_overrides(self):
        """Global --short shortens everything; per-tool :s is redundant but harmless."""
        long_content = "B" * 500
        msg = make_message(
            {"type": "tool_use", "name": "Bash", "id": "toolu_01", "input": {"command": "echo " + long_content}},
            {"type": "tool_result", "tool_use_id": "toolu_01", "content": long_content},
        )

        # Global short + per-tool short
        flags = ConversationFlags(show_tools=[ToolFilter(name="Bash", short=True)], shorten=True)
        parts = tool_parts_from(msg, flags, ID_MAP)

        result_content = parts[1].data.content
        assert "[...]" in result_content or len(result_content) < len(long_content), (
            f"Global --short should truncate; got {len(result_content)} chars"
        )
