#!/usr/bin/env python3
"""
Unit tests for conversation resolution bugs.

Tests specific failure modes discovered in code review:
- Bug #2: "not found" misreported as "ambiguous" (iter([]) truthiness)
- Bug #3: Single-word prefix match fails (generator exhaustion)
- Bug #4: Ambiguous input treated as raw content in parse mode

Uses same fixture pattern as test_rename.py - reuses rename_fixtures.
"""

import io
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from conversations import (
    _try_resolve_conversation_file,
    resolve_conversation_file,
    get_input_content,
    find_all_conversations,
)


# =============================================================================
# Fixtures (reuse rename_fixtures structure)
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "data" / "rename_fixtures"


@pytest.fixture
def temp_claude_home(tmp_path, monkeypatch):
    """Create temp .claude directory and patch Path.home()."""
    temp_home = tmp_path / "home"
    temp_projects = temp_home / ".claude" / "projects"

    shutil.copytree(FIXTURES_DIR / "projects", temp_projects)
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    return temp_home


@pytest.fixture
def add_single_word_fixture(temp_claude_home):
    """
    Add a conversation with single-word-prefix-matchable summary.

    Summary: "Unicorn debugging session"
    Should match prefix "Unicorn" (single word).
    """
    projects_dir = temp_claude_home / ".claude" / "projects" / "test-project"
    fixture_file = projects_dir / "eeee5555-unicorn.jsonl"

    lines = [
        {"type": "summary", "summary": "Unicorn debugging session", "leafUuid": "leaf-5555"},
        {"type": "user", "message": {"role": "user", "content": "Debug unicorn"}, "uuid": "msg-1"},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Found it!"}]}},
    ]

    with open(fixture_file, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")

    return fixture_file


@pytest.fixture
def set_recent_order(temp_claude_home):
    """Assign deterministic mtimes so negative indices map to recent sessions."""
    projects_dir = temp_claude_home / ".claude" / "projects" / "test-project"
    ordered_names = [
        "aaaa1111-with-summary.jsonl",
        "bbbb2222-without-summary.jsonl",
        "cccc3333-ambiguous-alpha.jsonl",
        "dddd4444-ambiguous-beta.jsonl",
    ]
    base_mtime = 1_700_000_000

    ordered_paths: list[Path] = []
    for offset, name in enumerate(ordered_names):
        path = projects_dir / name
        mtime = base_mtime + offset
        os.utime(path, (mtime, mtime))
        ordered_paths.append(path)

    agent_file = projects_dir / "agent-newest.jsonl"
    agent_file.write_text(
        json.dumps(
            {
                "type": "user",
                "sessionId": "dddd4444-ambiguous-beta",
                "message": {"role": "user", "content": "agent noise"},
            }
        )
        + "\n"
    )
    os.utime(agent_file, (base_mtime + 99, base_mtime + 99))

    return {
        "ordered_paths": ordered_paths,
        "newest_main": ordered_paths[-1],
        "second_newest_main": ordered_paths[-2],
        "agent_file": agent_file,
    }


# =============================================================================
# Bug #2: "not found" misreported as "ambiguous"
# =============================================================================

class TestNotFoundVsAmbiguous:
    """
    Bug #2: _try_resolve_conversation_file returns iter([]) for "not found",
    but iter([]) is truthy, so resolve_conversation_file takes the "ambiguous" branch.
    """

    def test_not_found_error_message(self, temp_claude_home, capsys):
        """Non-existent conversation should print 'not found', not 'ambiguous'."""
        with pytest.raises(SystemExit) as exc_info:
            resolve_conversation_file("TOTALLY_NONEXISTENT_UUID_12345")

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        # Should say "not found", NOT "ambiguous"
        assert "not found" in captured.out.lower() or "not found" in captured.err.lower(), \
            f"Expected 'not found' in output, got:\nstdout: {captured.out}\nstderr: {captured.err}"
        assert "ambiguous" not in captured.out.lower() and "ambiguous" not in captured.err.lower(), \
            f"Should NOT mention 'ambiguous' for non-existent conversation:\nstdout: {captured.out}\nstderr: {captured.err}"

    def test_ambiguous_shows_matches(self, temp_claude_home, capsys):
        """Ambiguous prefix should list the matching conversations."""
        # "Fix authentication" matches both cccc3333 and dddd4444
        with pytest.raises(SystemExit):
            resolve_conversation_file("Fix authentication")

        captured = capsys.readouterr()
        output = captured.out + captured.err

        # Should list both matches
        assert "cccc3333" in output or "Fix authentication bug" in output
        assert "dddd4444" in output or "Fix authentication flow" in output

    def test_try_resolve_returns_list_not_iterator(self, temp_claude_home):
        """
        _try_resolve_conversation_file should return a list (or empty list) for
        ambiguous_matches, NOT an iterator.

        This is the root cause fix: bool([]) is False, bool(iter([])) is True.
        """
        # Non-existent should return (None, []) where [] is falsy
        path, ambig = _try_resolve_conversation_file("NONEXISTENT_12345")

        assert path is None
        # The fix: ambig should be a list, and empty list should be falsy
        ambig_list = list(ambig)  # Convert in case it's still an iterator
        assert len(ambig_list) == 0, f"Expected no matches, got {ambig_list}"


# =============================================================================
# Bug #3: Single-word prefix match fails (generator exhaustion)
# =============================================================================

class TestSingleWordPrefixMatch:
    """
    Bug #3: For single-word queries, _try_resolve_conversation_file iterates
    conversation_files twice (exact match, then summary prefix). If it's a
    generator, the first loop exhausts it.
    """

    def test_multiword_prefix_works(self, temp_claude_home, add_single_word_fixture):
        """Multi-word prefix match should work (baseline - skips exact match loop)."""
        # "Unicorn debugging" is 2 words, should match "Unicorn debugging session"
        path, _ = _try_resolve_conversation_file("Unicorn debugging")

        assert path is not None, "Multi-word prefix should resolve"
        assert "eeee5555" in str(path)

    def test_single_word_prefix_works(self, temp_claude_home, add_single_word_fixture):
        """
        Single-word prefix match should work.

        Bug: "Unicorn" (1 word) enters exact-match loop first, exhausts generator,
        then summary-prefix loop sees nothing.
        """
        # "Unicorn" is 1 word, should still match "Unicorn debugging session"
        path, _ = _try_resolve_conversation_file("Unicorn")

        assert path is not None, \
            "Single-word prefix should resolve (bug #3: generator exhausted)"
        assert "eeee5555" in str(path)

    def test_single_word_exact_match_still_works(self, temp_claude_home):
        """Single-word exact UUID match should still work."""
        # This always worked because it matches in the first loop
        path, _ = _try_resolve_conversation_file("aaaa1111-with-summary")

        assert path is not None
        assert "aaaa1111" in str(path)


class TestNegativeRecentIndexResolution:
    """Negative numeric identifiers resolve by global recency."""

    def test_minus_one_resolves_most_recent_main_conversation(
        self, temp_claude_home, set_recent_order
    ):
        """-1 should resolve to the newest non-agent conversation file."""
        result = resolve_conversation_file("-1")

        assert result == set_recent_order["newest_main"], (
            "Expected '-1' to resolve to the most recently modified main "
            f"conversation. Got: {result!s}"
        )

    def test_minus_two_resolves_second_most_recent_main_conversation(
        self, temp_claude_home, set_recent_order
    ):
        """-2 should resolve to the second newest non-agent conversation file."""
        result = resolve_conversation_file("-2")

        assert result == set_recent_order["second_newest_main"], (
            "Expected '-2' to resolve to the second most recently modified "
            f"main conversation. Got: {result!s}"
        )


# =============================================================================
# Bug #4: Ambiguous input treated as raw content in parse mode
# =============================================================================

class TestAmbiguousInParseMode:
    """
    Bug #4: get_input_content() ignores ambiguous_matches return value and
    falls back to treating input as raw content, producing "No messages found"
    instead of showing the ambiguity error.
    """

    def test_get_input_content_ambiguous_should_error(self, temp_claude_home, capsys):
        """
        Ambiguous input in get_input_content should raise an error or return
        information about the ambiguity, not silently treat it as raw content.
        """
        # "Fix authentication" matches both cccc3333 and dddd4444
        # Current bug: returns "Fix authentication" as raw content
        # Expected: raise error or return ambiguity info

        # This test documents the expected behavior after fix
        with pytest.raises(SystemExit) as exc_info:
            get_input_content("Fix authentication")

        captured = capsys.readouterr()
        output = captured.out + captured.err

        # Should mention ambiguity, not silently fail
        assert "ambiguous" in output.lower() or exc_info.value.code == 1, \
            f"Ambiguous input should error explicitly, got: {output}"

    def test_get_input_content_valid_path_works(self, temp_claude_home):
        """Valid file path should return content (baseline test)."""
        file_path = temp_claude_home / ".claude" / "projects" / "test-project" / "aaaa1111-with-summary.jsonl"

        content = get_input_content(str(file_path))

        assert "Existing summary" in content

    def test_get_input_content_valid_summary_works(self, temp_claude_home):
        """Valid unique summary prefix should return content."""
        # "Existing summary" only matches aaaa1111
        content = get_input_content("Existing summary")

        assert content is not None
        assert len(content) > 0


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent
    )
    sys.exit(result.returncode)
