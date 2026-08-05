#!/usr/bin/env python3
"""
Unit tests for the name command.

Tests behavior (what the name command does), not implementation (how it does it).

For Claude sessions, the rename command appends exactly two entries to the end of the session file:
1. {"type":"custom-title","customTitle":"<name>","sessionId":"<session_id>"}
2. {"type":"agent-name","agentName":"<name>","sessionId":"<session_id>"}

It writes nothing else, in the session file or anywhere else.

Resolution tests:
- Direct file path
- UUID match
- Summary prefix match
- Ambiguous match (error)
- Not found (error)
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

from chats import cmd_name, resolve_conversation_file

# =============================================================================
# Fixtures
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "data" / "rename_fixtures"


@pytest.fixture
def temp_claude_home(tmp_path, monkeypatch):
    """
    Create a temporary .claude directory structure and patch Path.home().

    Returns the path to the temp home directory.
    """
    # Copy fixtures to temp directory
    temp_home = tmp_path / "home"
    temp_claude = temp_home / ".claude"
    temp_projects = temp_claude / "projects"

    # Copy the fixture project directory
    shutil.copytree(FIXTURES_DIR / "projects", temp_projects)

    # Patch Path.home() to return our temp directory
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    return temp_home


@pytest.fixture
def session_with_summary(temp_claude_home):
    """Return path to session file that has existing summary."""
    return (
        temp_claude_home
        / ".claude"
        / "projects"
        / "test-project"
        / "aaaa1111-with-summary.jsonl"
    )


@pytest.fixture
def session_without_summary(temp_claude_home):
    """Return path to session file that has no summary."""
    return (
        temp_claude_home
        / ".claude"
        / "projects"
        / "test-project"
        / "bbbb2222-without-summary.jsonl"
    )


def get_last_line_json(path: Path, offset: int = -1) -> dict:
    """Read and parse a line from the end of a JSONL file.

    offset=-1 is last line, -2 is second-to-last, etc.
    """
    with open(path, "r") as f:
        lines = f.readlines()
        return json.loads(lines[offset])


def count_lines(path: Path) -> int:
    """Count lines in a file."""
    with open(path, "r") as f:
        return sum(1 for _ in f)


# =============================================================================
# resolve_conversation_file() tests
# =============================================================================


class TestResolveConversationFile:
    """Test the resolve_conversation_file function."""

    def test_resolve_by_direct_path(self, session_with_summary):
        """Direct file path resolves to itself."""
        result = resolve_conversation_file(str(session_with_summary))
        assert result == session_with_summary

    def test_resolve_by_uuid_stem(self, temp_claude_home):
        """UUID (filename stem) resolves to matching file."""
        result = resolve_conversation_file("aaaa1111-with-summary")
        expected = (
            temp_claude_home
            / ".claude"
            / "projects"
            / "test-project"
            / "aaaa1111-with-summary.jsonl"
        )
        assert result == expected

    def test_resolve_by_uuid_with_extension(self, temp_claude_home):
        """UUID with .jsonl extension resolves to matching file."""
        result = resolve_conversation_file("aaaa1111-with-summary.jsonl")
        expected = (
            temp_claude_home
            / ".claude"
            / "projects"
            / "test-project"
            / "aaaa1111-with-summary.jsonl"
        )
        assert result == expected

    def test_resolve_by_summary_prefix(self, temp_claude_home):
        """Summary prefix (case-insensitive) resolves to matching file."""
        result = resolve_conversation_file("Existing summary")
        expected = (
            temp_claude_home
            / ".claude"
            / "projects"
            / "test-project"
            / "aaaa1111-with-summary.jsonl"
        )
        assert result == expected

    def test_resolve_by_summary_prefix_case_insensitive(self, temp_claude_home):
        """Summary prefix match is case-insensitive."""
        result = resolve_conversation_file("EXISTING SUMMARY")
        expected = (
            temp_claude_home
            / ".claude"
            / "projects"
            / "test-project"
            / "aaaa1111-with-summary.jsonl"
        )
        assert result == expected

    def test_resolve_ambiguous_exits(self, temp_claude_home):
        """Ambiguous prefix match exits with error."""
        # "Fix authentication" matches both cccc3333 and dddd4444
        with pytest.raises(SystemExit) as exc_info:
            resolve_conversation_file("Fix authentication")
        assert exc_info.value.code == 1

    def test_resolve_not_found_exits(self, temp_claude_home):
        """Non-existent conversation exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_conversation_file("nonexistent-uuid-12345")
        assert exc_info.value.code == 1

    def test_resolve_not_found_by_summary_exits(self, temp_claude_home):
        """Non-matching summary prefix exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_conversation_file("This summary does not exist anywhere")
        assert exc_info.value.code == 1


# =============================================================================
# cmd_name() tests - Custom title entry
# =============================================================================


class TestRenameAppendsCustomTitle:
    """Test that rename appends a custom-title entry to the file."""

    def test_appends_custom_title_entry(self, session_with_summary):
        """Rename appends a custom-title entry as the second-to-last line."""
        cmd_name(str(session_with_summary), "New Name Here")

        custom_title = get_last_line_json(session_with_summary, -2)
        assert custom_title["type"] == "custom-title"
        assert custom_title["customTitle"] == "New Name Here"

    def test_session_id_from_filename(self, session_with_summary):
        """Session ID is extracted from the filename stem."""
        cmd_name(str(session_with_summary), "Test Name")

        custom_title = get_last_line_json(session_with_summary, -2)
        assert custom_title["sessionId"] == "aaaa1111-with-summary"

    def test_adds_two_lines(self, session_with_summary):
        """Rename adds exactly two lines to the session file (custom-title + agent-name)."""
        original_count = count_lines(session_with_summary)

        cmd_name(str(session_with_summary), "Another Name")

        new_count = count_lines(session_with_summary)
        assert new_count == original_count + 2, (
            f"Expected {original_count + 2} lines (original {original_count} + custom-title + agent-name), got {new_count}"
        )

    def test_preserves_existing_content(self, session_with_summary):
        """Rename preserves all existing lines in the file."""
        with open(session_with_summary, "r") as f:
            original_lines = f.readlines()

        cmd_name(str(session_with_summary), "Changed Name")

        with open(session_with_summary, "r") as f:
            new_lines = f.readlines()

        # All original lines should still be there
        assert new_lines[:-2] == original_lines

    def test_works_without_summary(self, session_without_summary):
        """Rename works on files without an existing summary."""
        original_count = count_lines(session_without_summary)

        cmd_name(str(session_without_summary), "Brand New Title")

        custom_title = get_last_line_json(session_without_summary, -2)
        assert custom_title["type"] == "custom-title"
        assert custom_title["customTitle"] == "Brand New Title"
        assert custom_title["sessionId"] == "bbbb2222-without-summary"
        assert count_lines(session_without_summary) == original_count + 2


# =============================================================================
# cmd_name() tests - Agent name entry
# =============================================================================


class TestRenameAppendsAgentName:
    """Test that rename appends an agent-name entry after custom-title."""

    def test_appends_agent_name_entry(self, session_with_summary):
        """Rename appends an agent-name entry as the last line."""
        cmd_name(str(session_with_summary), "My Agent Name")

        last_line = get_last_line_json(session_with_summary)
        assert last_line["type"] == "agent-name"
        assert last_line["agentName"] == "My Agent Name"

    def test_agent_name_session_id(self, session_with_summary):
        """Agent-name entry has the correct sessionId."""
        cmd_name(str(session_with_summary), "Test Name")

        last_line = get_last_line_json(session_with_summary)
        assert last_line["sessionId"] == "aaaa1111-with-summary"

    def test_agent_name_follows_custom_title(self, session_with_summary):
        """Agent-name entry immediately follows custom-title entry."""
        cmd_name(str(session_with_summary), "Ordered Test")

        custom_title = get_last_line_json(session_with_summary, -2)
        agent_name = get_last_line_json(session_with_summary)

        assert custom_title["type"] == "custom-title"
        assert agent_name["type"] == "agent-name"
        assert custom_title["customTitle"] == agent_name["agentName"] == "Ordered Test"


# =============================================================================
# cmd_name() tests - Nothing else is appended
# =============================================================================


class TestRenameAppendsNothingElse:
    """Test that rename appends the two title entries and no other record."""

    def test_no_system_command_entry(self, session_with_summary):
        """Rename does not fabricate a /rename system local_command record."""
        with open(session_with_summary, "r") as f:
            original_count = sum(1 for _ in f)

        cmd_name(str(session_with_summary), "System Test")

        with open(session_with_summary, "r") as f:
            appended = [json.loads(line) for line in f.readlines()[original_count:]]

        assert [entry["type"] for entry in appended] == ["custom-title", "agent-name"]

    def test_does_not_touch_claude_history(
        self, temp_claude_home, session_with_summary
    ):
        """Rename leaves ~/.claude/history.jsonl alone."""
        history_file = temp_claude_home / ".claude" / "history.jsonl"
        history_file.write_text(json.dumps({"display": "existing"}) + "\n")

        cmd_name(str(session_with_summary), "History Test")

        assert history_file.read_text() == json.dumps({"display": "existing"}) + "\n"

    def test_does_not_create_claude_history(
        self, temp_claude_home, session_with_summary
    ):
        """Rename does not create ~/.claude/history.jsonl."""
        cmd_name(str(session_with_summary), "No History")

        assert not (temp_claude_home / ".claude" / "history.jsonl").exists()


# =============================================================================
# cmd_name() error cases
# =============================================================================


class TestRenameErrors:
    """Test error handling in rename command."""

    def test_empty_name_exits(self, session_with_summary):
        """Empty name exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            cmd_name(str(session_with_summary), "")
        assert exc_info.value.code == 1

    def test_whitespace_only_name_exits(self, session_with_summary):
        """Whitespace-only name exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            cmd_name(str(session_with_summary), "   ")
        assert exc_info.value.code == 1

    def test_nonexistent_file_exits(self, temp_claude_home):
        """Non-existent file path exits with error."""
        fake_path = temp_claude_home / "nonexistent.jsonl"
        with pytest.raises(SystemExit) as exc_info:
            cmd_name(str(fake_path), "Some Name")
        assert exc_info.value.code == 1

    def test_unknown_external_jsonl_exits_cleanly(self, tmp_path, capsys):
        """Unknown JSONL should report a user error without changing the file."""
        session_path = tmp_path / "external" / "transcript.jsonl"
        session_path.parent.mkdir(parents=True)
        original_content = json.dumps({
            "type": "user",
            "sessionId": "unknown-provider",
            "message": {"role": "user", "content": "hello"},
        }) + "\n"
        session_path.write_text(original_content, encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cmd_name(str(session_path), "New name")

        captured = capsys.readouterr()
        assert exc_info.value.code == 1, (
            f"Expected unknown JSONL to exit 1. Got: {exc_info.value.code!r}"
        )
        assert "Cannot determine JSONL session provider" in captured.err, (
            "Expected a clear provider-resolution error. "
            f"Got stderr:\n{captured.err}"
        )
        assert session_path.read_text(encoding="utf-8") == original_content, (
            "Expected failed naming not to modify the unknown session file."
        )

    def test_empty_name_does_not_modify_file(self, session_with_summary):
        """Failed rename due to empty name leaves file unchanged."""
        with open(session_with_summary, "r") as f:
            original_content = f.read()

        with pytest.raises(SystemExit):
            cmd_name(str(session_with_summary), "")

        with open(session_with_summary, "r") as f:
            new_content = f.read()

        assert new_content == original_content


# =============================================================================
# Edge cases
# =============================================================================


class TestRenameEdgeCases:
    """Test edge cases and special inputs."""

    def test_special_characters_preserved(self, session_with_summary):
        """Special characters in name are preserved correctly."""
        special_name = 'Test with "quotes", émojis: 🎉, and\nnewlines'

        cmd_name(str(session_with_summary), special_name)

        custom_title = get_last_line_json(session_with_summary, -2)
        assert custom_title["customTitle"] == special_name
        agent_name = get_last_line_json(session_with_summary)
        assert agent_name["agentName"] == special_name

    def test_very_long_name(self, session_with_summary):
        """Very long names are handled correctly."""
        long_name = "A" * 1000

        cmd_name(str(session_with_summary), long_name)

        custom_title = get_last_line_json(session_with_summary, -2)
        assert custom_title["customTitle"] == long_name

    def test_unicode_name(self, session_with_summary):
        """Unicode characters are preserved."""
        unicode_name = "日本語テスト 中文测试 한국어테스트"

        cmd_name(str(session_with_summary), unicode_name)

        custom_title = get_last_line_json(session_with_summary, -2)
        assert custom_title["customTitle"] == unicode_name

    def test_json_special_chars_escaped(self, session_with_summary):
        """JSON special characters are properly escaped."""
        tricky_name = '{"type":"malicious","customTitle":"injected"}'

        cmd_name(str(session_with_summary), tricky_name)

        custom_title = get_last_line_json(session_with_summary, -2)
        # The name should be stored as a string value, not parsed as JSON
        assert custom_title["customTitle"] == tricky_name
        assert custom_title["type"] == "custom-title"  # Not overwritten

    def test_multiple_renames_append(self, session_with_summary):
        """Multiple renames append multiple entry pairs."""
        original_count = count_lines(session_with_summary)

        cmd_name(str(session_with_summary), "First rename")
        cmd_name(str(session_with_summary), "Second rename")
        cmd_name(str(session_with_summary), "Third rename")

        assert count_lines(session_with_summary) == original_count + 6, (
            f"Expected {original_count + 6} lines (original {original_count} + 3 renames * 2 entries each)"
        )

        last_agent_name = get_last_line_json(session_with_summary)
        assert last_agent_name["agentName"] == "Third rename"


if __name__ == "__main__":
    import subprocess

    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    sys.exit(result.returncode)
