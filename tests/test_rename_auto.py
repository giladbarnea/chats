#!/usr/bin/env python3
"""
Tests for the --auto flag on the rename command.

The auto-naming flow:
1. Read the session content as readable text
2. Derive the cwd name from session metadata
3. Call `pi` subprocess to generate a name from the transcript
4. Parse the output with the same logic as auto-session-name.ts
5. Apply the generated name via the existing rename logic

Tested units:
- _clean_line()               pure function, no mocking
- _parse_auto_session_name()  pure function, no mocking
- _generate_auto_name()       mocks subprocess.run + cmd_parse capture
- cmd_rename(..., auto=True)  integration: fixture + subprocess mock
"""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from conversations import cmd_rename
from conversations.commands import (
    _clean_line,
    _generate_auto_name,
    _parse_auto_session_name,
)

# =============================================================================
# Fixtures (reuse rename_fixtures data)
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "data" / "rename_fixtures"


@pytest.fixture
def temp_claude_home(tmp_path, monkeypatch):
    temp_home = tmp_path / "home"
    temp_claude = temp_home / ".claude"
    shutil.copytree(FIXTURES_DIR / "projects", temp_claude / "projects")
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    return temp_home


@pytest.fixture
def session_file(temp_claude_home):
    return (
        temp_claude_home
        / ".claude"
        / "projects"
        / "test-project"
        / "aaaa1111-with-summary.jsonl"
    )


def get_last_line_json(path: Path, offset: int = -1) -> dict:
    with open(path) as f:
        lines = f.readlines()
        return json.loads(lines[offset])


# =============================================================================
# _clean_line
# =============================================================================


class TestCleanLine:
    def test_strips_whitespace(self):
        assert _clean_line("  hello  ") == "hello"

    def test_strips_double_quotes(self):
        assert _clean_line('"hello"') == "hello"

    def test_strips_single_quotes(self):
        assert _clean_line("'hello'") == "hello"

    def test_strips_backticks(self):
        assert _clean_line("`hello`") == "hello"

    def test_strips_multiple_surrounding_quotes(self):
        assert _clean_line('"""hello"""') == "hello"

    def test_strips_mixed_surrounding(self):
        # Only strips same-kind from start/end via regex, leaves inner alone
        result = _clean_line('"hello"')
        assert result == "hello"

    def test_truncates_to_max_length(self):
        long = "a" * 200
        result = _clean_line(long)
        assert len(result) == 150

    def test_preserves_internal_content(self):
        assert _clean_line("foo bar baz") == "foo bar baz"

    def test_empty_string(self):
        assert _clean_line("") == ""

    def test_whitespace_only(self):
        assert _clean_line("   ") == ""


# =============================================================================
# _parse_auto_session_name
# =============================================================================


class TestParseAutoSessionName:
    def test_single_line_returns_name(self):
        result = _parse_auto_session_name("conversations implement auto-rename feature", "conversations")
        assert result == "conversations implement auto-rename feature"

    def test_two_lines_first_ends_with_colon_returns_second(self):
        output = "Session name:\nconversations implement auto-rename feature"
        result = _parse_auto_session_name(output, "conversations")
        assert result == "conversations implement auto-rename feature"

    def test_empty_output_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _parse_auto_session_name("", "conversations")

    def test_whitespace_only_output_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _parse_auto_session_name("   \n\n  ", "conversations")

    def test_multiline_no_colon_pattern_raises(self):
        output = "line one\nline two\nline three"
        with pytest.raises(ValueError, match="could not pick"):
            _parse_auto_session_name(output, "conversations")

    def test_two_lines_neither_ends_with_colon_raises(self):
        output = "line one\nline two"
        with pytest.raises(ValueError, match="could not pick"):
            _parse_auto_session_name(output, "conversations")

    def test_name_same_as_cwd_raises(self):
        with pytest.raises(ValueError, match="useless"):
            _parse_auto_session_name("conversations", "conversations")

    def test_name_same_as_cwd_case_insensitive_raises(self):
        with pytest.raises(ValueError, match="useless"):
            _parse_auto_session_name("CONVERSATIONS", "conversations")

    def test_strips_quotes_from_output(self):
        result = _parse_auto_session_name('"conversations fix bug"', "conversations")
        assert result == "conversations fix bug"

    def test_strips_backticks_from_output(self):
        result = _parse_auto_session_name("`conversations fix bug`", "conversations")
        assert result == "conversations fix bug"

    def test_trailing_blank_lines_ignored(self):
        result = _parse_auto_session_name("conversations fix bug\n\n\n", "conversations")
        assert result == "conversations fix bug"


# =============================================================================
# _generate_auto_name
# =============================================================================


class TestGenerateAutoName:
    def test_returns_parsed_name_on_success(self, session_file):
        mock_result = MagicMock()
        mock_result.stdout = "conversations implement auto-rename\n"
        with patch("conversations.commands.rename.subprocess.run", return_value=mock_result):
            name = _generate_auto_name(session_file, session_file.read_text())
        assert name == "conversations implement auto-rename"

    def test_raises_on_pi_not_found(self, session_file):
        with patch(
            "conversations.commands.rename.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(RuntimeError, match="not found"):
                _generate_auto_name(session_file, session_file.read_text())

    def test_raises_on_pi_nonzero_exit(self, session_file):
        with patch(
            "conversations.commands.rename.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "pi"),
        ):
            with pytest.raises(RuntimeError, match="failed"):
                _generate_auto_name(session_file, session_file.read_text())

    def test_raises_on_unparseable_output(self, session_file):
        mock_result = MagicMock()
        mock_result.stdout = "line one\nline two\nline three\n"
        with patch("conversations.commands.rename.subprocess.run", return_value=mock_result):
            with pytest.raises(ValueError, match="could not pick"):
                _generate_auto_name(session_file, session_file.read_text())

    def test_calls_pi_with_print_flag(self, session_file):
        mock_result = MagicMock()
        mock_result.stdout = "conversations fix thing\n"
        with patch("conversations.commands.rename.subprocess.run", return_value=mock_result) as mock_run:
            _generate_auto_name(session_file, session_file.read_text())
        args = mock_run.call_args[0][0]
        assert args[0] == "pi"
        assert "--print" in args

    def test_uses_capture_output(self, session_file):
        mock_result = MagicMock()
        mock_result.stdout = "conversations fix thing\n"
        with patch("conversations.commands.rename.subprocess.run", return_value=mock_result) as mock_run:
            _generate_auto_name(session_file, session_file.read_text())
        kwargs = mock_run.call_args[1]
        assert kwargs.get("capture_output") is True


# =============================================================================
# cmd_rename with auto=True
# =============================================================================


class TestCmdRenameAuto:
    def test_auto_renames_session(self, session_file):
        mock_result = MagicMock()
        mock_result.stdout = "conversations implement auto-rename\n"
        with patch("conversations.commands.rename.subprocess.run", return_value=mock_result):
            cmd_rename(str(session_file), None, auto=True)

        last = get_last_line_json(session_file)
        assert last["type"] == "agent-name"
        assert last["agentName"] == "conversations implement auto-rename"

    def test_auto_and_name_raises(self, session_file):
        with pytest.raises(SystemExit) as exc_info:
            cmd_rename(str(session_file), "Explicit Name", auto=True)
        assert exc_info.value.code == 1

    def test_no_name_no_auto_raises(self, session_file):
        with pytest.raises(SystemExit) as exc_info:
            cmd_rename(str(session_file), None, auto=False)
        assert exc_info.value.code == 1

    def test_auto_pi_not_found_exits(self, session_file):
        with patch(
            "conversations.commands.rename.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(SystemExit) as exc_info:
                cmd_rename(str(session_file), None, auto=True)
        assert exc_info.value.code == 1

    def test_auto_bad_output_exits(self, session_file):
        mock_result = MagicMock()
        mock_result.stdout = "line one\nline two\nline three\n"
        with patch("conversations.commands.rename.subprocess.run", return_value=mock_result):
            with pytest.raises(SystemExit) as exc_info:
                cmd_rename(str(session_file), None, auto=True)
        assert exc_info.value.code == 1


if __name__ == "__main__":
    import subprocess as sp
    import sys

    result = sp.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    sys.exit(result.returncode)
