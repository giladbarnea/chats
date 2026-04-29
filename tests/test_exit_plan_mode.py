#!/usr/bin/env python3
"""
Unit tests for ExitPlanMode handling.

Tests that:
- Plans are shown by default
- Plans are hidden with --no-plans
- Plans are shown with --all
- Plans are hidden with --all --no-plans (--no-plans takes precedence)
"""

from pathlib import Path

from conversations import (
    ConversationFlags,
    Message,
    parse_jsonl,
    render_message_inner_xml,
)

# Path to test fixture
FIXTURE_PATH = Path(__file__).parent / "data" / "exit-plan-mode-full-message.jsonl"


def load_fixture() -> str:
    """Load the ExitPlanMode test fixture."""
    return FIXTURE_PATH.read_text(encoding="utf-8")


class TestExitPlanModeVisibility:
    """Test plan visibility based on flags."""

    def test_plan_shown_by_default(self):
        """Plans are shown by default (no flags)."""
        content = load_fixture()
        flags = ConversationFlags()

        messages = parse_jsonl(content, flags)

        assert len(messages) == 1, f"Expected 1 message, got {len(messages)}"
        msg = messages[0]
        assert msg.plan is not None, "Plan should be extracted"
        assert "# Plan: Fix SonarCloud Issues" in msg.plan

        # Verify it appears in visible content
        visible = render_message_inner_xml(msg, flags)
        assert '<tool-input name="ExitPlanMode">' in visible
        assert "# Plan: Fix SonarCloud Issues" in visible

    def test_plan_hidden_with_no_plans(self):
        """Plans are hidden when show_plans=False."""
        content = load_fixture()
        flags = ConversationFlags(show_plans=False)

        messages = parse_jsonl(content, flags)

        assert len(messages) == 1
        msg = messages[0]
        # Plan is still extracted (for potential later use)
        assert msg.plan is not None

        # But NOT in visible content
        visible = render_message_inner_xml(msg, flags)
        assert '<tool-input name="ExitPlanMode">' not in visible
        assert "# Plan: Fix SonarCloud Issues" not in visible

    def test_plan_shown_with_all(self):
        """Plans are shown with --all flag."""
        content = load_fixture()
        flags = ConversationFlags(
            show_thinking=True,
            show_tools=True,
            show_agents=True,
            show_plans=True,  # Explicit, but default anyway
        )

        messages = parse_jsonl(content, flags)

        assert len(messages) == 1
        msg = messages[0]

        visible = render_message_inner_xml(msg, flags)
        assert '<tool-input name="ExitPlanMode">' in visible

    def test_plan_hidden_with_all_and_no_plans(self):
        """--no-plans takes precedence over --all."""
        content = load_fixture()
        flags = ConversationFlags(
            show_thinking=True,
            show_tools=True,
            show_agents=True,
            show_plans=False,  # --no-plans takes precedence
        )

        messages = parse_jsonl(content, flags)

        assert len(messages) == 1
        msg = messages[0]

        visible = render_message_inner_xml(msg, flags)
        assert '<tool-input name="ExitPlanMode">' not in visible


class TestExitPlanModeExtraction:
    """Test that ExitPlanMode is extracted correctly and not mixed with tools."""

    def test_plan_not_in_tools_list(self):
        """ExitPlanMode should be extracted to msg.plan, not msg.tools."""
        content = load_fixture()
        flags = ConversationFlags(show_tools=True)

        messages = parse_jsonl(content, flags)

        assert len(messages) == 1
        msg = messages[0]

        # Plan extracted separately
        assert msg.plan is not None

        # Not in tools list
        for tool in msg.tools:
            assert tool.get("name") != "ExitPlanMode", (
                "ExitPlanMode should not be in tools list"
            )

    def test_plan_content_extracted_correctly(self):
        """Plan content should be the full markdown plan text."""
        content = load_fixture()
        flags = ConversationFlags()

        messages = parse_jsonl(content, flags)
        msg = messages[0]

        # Check key sections are present
        assert "## Issue Clarification" in msg.plan
        assert "## Actual Issues" in msg.plan
        assert "## Solution" in msg.plan
        assert "## Files to Modify" in msg.plan
        assert "## Order of Changes" in msg.plan


class TestMessageHasContent:
    """Test that has_content() correctly considers plans."""

    def test_message_with_only_plan_has_content(self):
        """A message with only a plan should be considered to have content."""
        msg = Message(role="assistant", plan="# My Plan")
        assert msg.has_content() is True

    def test_empty_message_has_no_content(self):
        """A message with nothing should not have content."""
        msg = Message(role="assistant")
        assert msg.has_content() is False


if __name__ == "__main__":
    import subprocess

    # Run with pytest if available
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
    )
    sys.exit(result.returncode)
