#!/usr/bin/env python3
"""
Tests for granular tool filtering: parsing, matching, and integration.

Covers:
- Spec parsing (lax syntax: order-independent, short/long forms, optional colon)
- Filter matching (criteria AND'd, negation inverts, positive OR'd, negative AND'd as blocklist)
- Integration with Message.iter_visible_parts (direction, name, error, shortening)
"""

import pytest

from conversations import ConversationFlags, Message
from conversations.parts import MessagePartKind
from conversations.tool_filter import ToolFilter, parse_tool_spec
from conversations.utils import truncate_middle

# =============================================================================
# Shared tool dicts
# =============================================================================

BASH_USE = {
    "type": "tool_use",
    "name": "Bash",
    "id": "toolu_01",
    "input": {"command": "ls"},
}
BASH_RESULT = {"type": "tool_result", "tool_use_id": "toolu_01", "content": "file1.txt"}
BASH_ERROR = {
    "type": "tool_result",
    "tool_use_id": "toolu_01",
    "content": "cmd failed",
    "is_error": True,
}
READ_USE = {
    "type": "tool_use",
    "name": "Read",
    "id": "toolu_02",
    "input": {"file_path": "f.txt"},
}
READ_RESULT = {
    "type": "tool_result",
    "tool_use_id": "toolu_02",
    "content": "content of f.txt",
}
SKILL_USE = {
    "type": "tool_use",
    "name": "Skill",
    "id": "toolu_03",
    "input": {"skill": "commit"},
}
SKILL_RESULT = {
    "type": "tool_result",
    "tool_use_id": "toolu_03",
    "content": "skill output",
}

ID_MAP = {"toolu_01": "Bash", "toolu_02": "Read", "toolu_03": "Skill"}


def make_message(*tools):
    """Create an assistant Message with the given tool dicts."""
    return Message(role="assistant", text="text", tools=list(tools))


def tool_parts_from(msg, flags, tool_id_map=None):
    """Return only the TOOL MessageParts from iter_visible_parts."""
    return [
        p
        for p in msg.iter_visible_parts(flags, tool_id_map)
        if p.kind == MessagePartKind.TOOL
    ]


# =============================================================================
# Parsing: spec string -> ToolFilter
# =============================================================================


class TestParseToolSpec:
    """Spec string is parsed into correct ToolFilter regardless of syntax form."""

    @pytest.mark.parametrize(
        "spec, expected",
        [
            # --- Bare modifier, short form ---
            ("o", {"direction": "output"}),
            ("i", {"direction": "input"}),
            ("s", {"short": True}),
            ("e", {"error_only": True}),
            # --- Bare modifier, long form ---
            ("output", {"direction": "output"}),
            ("input", {"direction": "input"}),
            ("short", {"short": True}),
            ("error", {"error_only": True}),
            # --- Name + modifier ---
            ("Bash:i", {"name": "Bash", "direction": "input"}),
            ("Read:o", {"name": "Read", "direction": "output"}),
            ("Read:o:s", {"name": "Read", "direction": "output", "short": True}),
            ("Bash:e", {"name": "Bash", "error_only": True}),
            # --- Order independence ---
            ("i:Bash", {"name": "Bash", "direction": "input"}),
            ("short:Bash:i", {"name": "Bash", "direction": "input", "short": True}),
            ("s:o:Read", {"name": "Read", "direction": "output", "short": True}),
            # --- Optional leading colon ---
            (":o", {"direction": "output"}),
            (":o:s", {"direction": "output", "short": True}),
            (":short", {"short": True}),
            # --- Mixed short/long modifiers ---
            ("Read:output:s", {"name": "Read", "direction": "output", "short": True}),
            ("Bash:i:short", {"name": "Bash", "direction": "input", "short": True}),
            # --- Negation ---
            ("!Bash", {"name": "Bash", "negate": True}),
            ("!Bash:o", {"name": "Bash", "direction": "output", "negate": True}),
            ("!o", {"direction": "output", "negate": True}),
            # --- Name only ---
            ("Bash", {"name": "Bash"}),
            ("Read", {"name": "Read"}),
            # --- Empty (bare --tools) ---
            ("", {}),
        ],
        ids=lambda x: repr(x) if isinstance(x, str) else None,
    )
    def test_parse(self, spec, expected):
        tf = parse_tool_spec(spec)
        defaults = {
            "name": None,
            "negate": False,
            "direction": None,
            "error_only": False,
            "short": False,
        }
        for field, default in defaults.items():
            want = expected.get(field, default)
            got = getattr(tf, field)
            assert got == want, (
                f"parse_tool_spec({spec!r}).{field}: expected {want!r}, got {got!r}"
            )


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
        flags = ConversationFlags(
            show_tools=[ToolFilter(name="Bash", direction="input")]
        )
        parts = tool_parts_from(self.msg, flags, self.id_map)
        assert len(parts) == 1
        assert parts[0].data.tag == "tool-input"
        assert dict(parts[0].data.attrs).get("name") == "Bash"

    def test_multiple_filters_ored(self):
        """Read:o + Bash:i → Read output and Bash input (2 parts, in message order)."""
        flags = ConversationFlags(
            show_tools=[
                ToolFilter(name="Read", direction="output"),
                ToolFilter(name="Bash", direction="input"),
            ]
        )
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

    def test_multiple_negated_filters(self):
        """!Skill + !Read:o → exclude Skill tools AND Read outputs, show rest."""
        msg = make_message(
            BASH_USE, BASH_RESULT, READ_USE, READ_RESULT, SKILL_USE, SKILL_RESULT
        )
        id_map = {**ID_MAP}
        flags = ConversationFlags(
            show_tools=[
                ToolFilter(name="Skill", negate=True),
                ToolFilter(name="Read", direction="output", negate=True),
            ]
        )
        parts = tool_parts_from(msg, flags, id_map)
        # Should show: Bash use, Bash result, Read use (input only)
        # Should NOT show: Skill use, Skill result, Read result
        names = [dict(p.data.attrs).get("name") for p in parts]
        assert len(parts) == 3, (
            f"Expected 3 parts (Bash in+out, Read in), got {len(parts)}: {names}"
        )
        assert "Skill" not in names, f"Skill should be excluded, got {names}"

    def test_mixed_positive_and_negative(self):
        """Bash + !Read:o → only Bash (positive allowlist), minus Read outputs (irrelevant here)."""
        msg = make_message(
            BASH_USE, BASH_RESULT, READ_USE, READ_RESULT, SKILL_USE, SKILL_RESULT
        )
        id_map = {**ID_MAP}
        flags = ConversationFlags(
            show_tools=[
                ToolFilter(name="Bash"),
                ToolFilter(name="Read", direction="output", negate=True),
            ]
        )
        parts = tool_parts_from(msg, flags, id_map)
        # Positive allowlist: only Bash. Negative: also blocks Read output (but Bash already excludes it).
        names = [dict(p.data.attrs).get("name") for p in parts]
        assert len(parts) == 2, f"Expected 2 Bash parts, got {len(parts)}: {names}"
        assert all(n in ("Bash", None) for n in names), (
            f"Only Bash expected, got {names}"
        )

    def test_error_filter(self):
        """error_only → only tool_results with is_error=True."""
        msg = make_message(BASH_USE, BASH_ERROR, READ_USE, READ_RESULT)
        flags = ConversationFlags(show_tools=[ToolFilter(error_only=True)])
        parts = tool_parts_from(msg, flags, self.id_map)
        assert len(parts) == 1
        assert dict(parts[0].data.attrs).get("is_error") == "true"


class TestPerToolShortening:
    """The :s modifier shortens only matching tools, not others."""

    def test_short_flag_truncates_rendered_tool_output_to_500_chars(self):
        long_content = "READ_START-" + ("A" * 1000) + "-READ_END"
        msg = make_message(
            {
                "type": "tool_use",
                "name": "Read",
                "id": "toolu_02",
                "input": {"file_path": "f.txt"},
            },
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
        assert short_result is not None, (
            "Expected shortened tool output content to be present."
        )
        assert full_result is not None, (
            "Expected full tool output content to be present."
        )
        assert len(short_result) == 500, (
            f"Expected :s to truncate the rendered tool body to 500 chars. Got {len(short_result)}."
        )
        assert len(full_result) > len(short_result), (
            f"Expected shortened content to be smaller than full content. "
            f"Got short={len(short_result)} full={len(full_result)}."
        )
        assert "\n...\n" in short_result, (
            "Expected shortened tool output to use the line-broken ellipsis placeholder."
        )
        assert "READ_START-" in short_result[:260], (
            f"Expected the start of the rendered tool body to be preserved. Got: {short_result[:260]!r}"
        )
        assert "READ_END" in short_result[-260:], (
            f"Expected the end of the rendered tool body to be preserved. Got: {short_result[-260:]!r}"
        )

    def test_global_short_overrides(self):
        """Global --short shortens everything; per-tool :s is redundant but harmless."""
        long_content = "BASH_START-" + ("B" * 1000) + "-BASH_END"
        msg = make_message(
            {
                "type": "tool_use",
                "name": "Bash",
                "id": "toolu_01",
                "input": {"command": "echo " + long_content},
            },
            {"type": "tool_result", "tool_use_id": "toolu_01", "content": long_content},
        )

        # Global short + per-tool short
        flags = ConversationFlags(
            show_tools=[ToolFilter(name="Bash", short=True)], shorten=True
        )
        parts = tool_parts_from(msg, flags, ID_MAP)

        input_content = parts[0].data.content
        result_content = parts[1].data.content
        assert input_content is not None, (
            "Expected Bash tool-input content to be present."
        )
        assert result_content is not None, (
            "Expected Bash tool-output content to be present."
        )
        assert len(input_content) == 500, (
            f"Expected global --short to truncate tool-input content to 500 chars. Got {len(input_content)}."
        )
        assert len(result_content) == 500, (
            f"Expected global --short to truncate tool-output content to 500 chars. Got {len(result_content)}."
        )
        assert "BASH_START-" in input_content[:260], (
            f"Expected shortened tool-input content to preserve the start. Got: {input_content[:260]!r}"
        )
        assert "BASH_END" in result_content[-260:], (
            f"Expected shortened tool-output content to preserve the end. Got: {result_content[-260:]!r}"
        )


# =============================================================================
# truncate_middle: unit tests
# =============================================================================


class TestTruncateMiddle:
    """truncate_middle truncates exactly to max_len, replacing the middle with a placeholder."""

    def test_short_string_unchanged(self):
        assert truncate_middle("hello", max_len=100) == "hello"

    def test_length_at_threshold_unchanged(self):
        s = "a" * 115
        assert truncate_middle(s, max_len=120) == s

    def test_length_above_threshold_truncates_to_exact_max_len(self):
        result = truncate_middle("a" * 116, max_len=120)
        assert len(result) == 120, f"Expected 120 chars exactly, got {len(result)}"
        assert "\n...\n" in result, (
            f"Expected the line-broken ellipsis placeholder in truncated output. Got: {result!r}"
        )

    def test_long_string_keeps_start_and_end(self):
        s = "A" * 40 + "B" * 40 + "C" * 40 + "D" * 40  # 160 chars
        result = truncate_middle(s, max_len=100)
        assert result.startswith("A" * 40), (
            f"Should start with first quarter. Got: {result[:50]}"
        )
        assert result.endswith("D" * 40), (
            f"Should end with last quarter. Got: {result[-50:]}"
        )
        assert "..." in result
        assert len(result) == 100, f"Expected 100 chars exactly, got {len(result)}"

    def test_default_500_char_behavior_uses_248_ellipsis_247_split(self):
        source = ("S" * 248) + ("M" * 1000) + ("E" * 247)
        result = truncate_middle(source)
        assert result == ("S" * 248) + "\n...\n" + ("E" * 247), (
            "Expected default truncation to keep 248 leading chars, then '\\n...\\n', "
            "then 247 trailing chars."
        )

    def test_placeholder_is_ellipsis_not_bracket(self):
        result = truncate_middle("x" * 200, max_len=100)
        assert "..." in result
        assert "[...]" not in result


# =============================================================================
# Message-level shortening: --short uses middle truncation
# =============================================================================


class TestMessageMiddleTruncation:
    """--short flag middle-truncates message text, preserving both start and end."""

    def test_text_preserves_start_and_end(self):
        start = "START_MARKER "
        end = " END_MARKER"
        middle = "m" * 1000
        long_text = start + middle + end

        msg = Message(role="assistant", text=long_text)
        flags = ConversationFlags(shorten=True)
        parts = msg.iter_visible_parts(flags)

        text_parts = [p for p in parts if p.kind == MessagePartKind.TEXT]
        assert len(text_parts) == 1, f"Expected 1 text part, got {len(text_parts)}"
        shortened = text_parts[0].data

        assert "START_MARKER" in shortened, (
            f"Start should be preserved. Got: {shortened[:60]}"
        )
        assert "END_MARKER" in shortened, (
            f"End should be preserved. Got: {shortened[-60:]}"
        )
        assert "..." in shortened, "Should contain ellipsis placeholder"

    def test_thinking_preserves_start_and_end(self):
        start = "FIRST_THOUGHT "
        end = " FINAL_THOUGHT"
        middle = "t" * 1000
        long_thinking = start + middle + end

        msg = Message(role="assistant", text="x", thinking=long_thinking)
        flags = ConversationFlags(shorten=True, show_thinking=True)
        parts = msg.iter_visible_parts(flags)

        thinking_parts = [p for p in parts if p.kind == MessagePartKind.THINKING]
        assert len(thinking_parts) == 1
        shortened = thinking_parts[0].data

        assert "FIRST_THOUGHT" in shortened, (
            f"Start should be preserved. Got: {shortened[:60]}"
        )
        assert "FINAL_THOUGHT" in shortened, (
            f"End should be preserved. Got: {shortened[-60:]}"
        )
