#!/usr/bin/env python3
"""
Unit tests for the rm command.

Tests behavior (what rm does), not implementation (how it does it).

The rm command removes a conversation session and all associated files:
- The main .jsonl conversation file
- Any agent-*.jsonl files belonging to this session
- file-history/{session_id}/ directory
- projects/{project_dir}/{session_id}/ directory
- session-env/{session_id}/ directory
- debug/{session_id}.txt file
- todos/{session_id}-agent-{session_id}.json file
- Lines in history.jsonl with matching sessionId
"""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from chats import cmd_rm

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
    temp_home = tmp_path / "home"
    temp_claude = temp_home / ".claude"
    temp_projects = temp_claude / "projects"

    # Copy the fixture project directory
    shutil.copytree(FIXTURES_DIR / "projects", temp_projects)

    # Patch Path.home() to return our temp directory
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    return temp_home


@pytest.fixture
def full_session_setup(temp_claude_home):
    """
    Create a full session with all associated files/directories.

    Returns dict with session info and paths.
    """
    session_id = "test-session-12345678"
    project_dir = "test-project"
    claude_dir = temp_claude_home / ".claude"

    # Create the main conversation file
    projects_dir = claude_dir / "projects" / project_dir
    conv_file = projects_dir / f"{session_id}.jsonl"
    conv_file.write_text(
        json.dumps({
            "type": "summary",
            "summary": "Test session for rm command",
            "leafUuid": "leaf-test",
        })
        + "\n"
        + json.dumps({
            "type": "user",
            "message": {"role": "user", "content": "Hello"},
            "sessionId": session_id,
            "uuid": "msg-1",
        })
        + "\n"
    )

    # Create an agent file
    agent_file = projects_dir / session_id / "subagents" / "agent-abc12345.jsonl"
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    agent_file.write_text(
        json.dumps({
            "type": "user",
            "sessionId": session_id,
            "message": {"role": "user", "content": "Agent hello"},
        })
        + "\n"
    )

    # Create debug file
    debug_dir = claude_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_file = debug_dir / f"{session_id}.txt"
    debug_file.write_text("Debug output")

    # Create todos file
    todos_dir = claude_dir / "todos"
    todos_dir.mkdir(parents=True, exist_ok=True)
    todos_file = todos_dir / f"{session_id}-agent-{session_id}.json"
    todos_file.write_text(json.dumps({"tasks": []}))

    # Create file-history directory
    file_history_dir = claude_dir / "file-history" / session_id
    file_history_dir.mkdir(parents=True, exist_ok=True)
    (file_history_dir / "backup.txt").write_text("backup content")

    # Create project session directory
    project_session_dir = projects_dir / session_id
    project_session_dir.mkdir(parents=True, exist_ok=True)
    (project_session_dir / "data.json").write_text("{}")

    # Create session-env directory
    session_env_dir = claude_dir / "session-env" / session_id
    session_env_dir.mkdir(parents=True, exist_ok=True)
    (session_env_dir / "env.json").write_text("{}")

    # Create history.jsonl with entries for this session and others
    history_file = claude_dir / "history.jsonl"
    history_file.write_text(
        json.dumps({"sessionId": session_id, "event": "start"})
        + "\n"
        + json.dumps({"sessionId": "other-session", "event": "start"})
        + "\n"
        + json.dumps({"sessionId": session_id, "event": "end"})
        + "\n"
        + json.dumps({"sessionId": "another-session", "event": "something"})
        + "\n"
    )

    return {
        "session_id": session_id,
        "project_dir": project_dir,
        "claude_dir": claude_dir,
        "conv_file": conv_file,
        "agent_file": agent_file,
        "debug_file": debug_file,
        "todos_file": todos_file,
        "file_history_dir": file_history_dir,
        "project_session_dir": project_session_dir,
        "session_env_dir": session_env_dir,
        "history_file": history_file,
    }


# =============================================================================
# cmd_rm() tests - Core behavior
# =============================================================================


class TestRmRemovesFiles:
    """Test that rm removes all associated files."""

    def test_removes_main_conversation_file(self, full_session_setup):
        """rm removes the main conversation .jsonl file."""
        setup = full_session_setup
        assert setup["conv_file"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["conv_file"].exists()

    def test_removes_agent_files(self, full_session_setup):
        """rm removes agent files belonging to this session."""
        setup = full_session_setup
        assert setup["agent_file"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["agent_file"].exists()

    def test_removes_debug_file(self, full_session_setup):
        """rm removes debug/{session_id}.txt file."""
        setup = full_session_setup
        assert setup["debug_file"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["debug_file"].exists()

    def test_removes_todos_file(self, full_session_setup):
        """rm removes todos/{session_id}-agent-{session_id}.json file."""
        setup = full_session_setup
        assert setup["todos_file"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["todos_file"].exists()


class TestRmRemovesDirectories:
    """Test that rm removes all associated directories."""

    def test_removes_file_history_dir(self, full_session_setup):
        """rm removes file-history/{session_id}/ directory."""
        setup = full_session_setup
        assert setup["file_history_dir"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["file_history_dir"].exists()

    def test_removes_project_session_dir(self, full_session_setup):
        """rm removes projects/{project}/{session_id}/ directory."""
        setup = full_session_setup
        assert setup["project_session_dir"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["project_session_dir"].exists()

    def test_removes_session_env_dir(self, full_session_setup):
        """rm removes session-env/{session_id}/ directory."""
        setup = full_session_setup
        assert setup["session_env_dir"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["session_env_dir"].exists()


class TestRmUpdatesHistory:
    """Test that rm updates history.jsonl correctly."""

    def test_removes_history_entries(self, full_session_setup):
        """rm removes matching entries from history.jsonl."""
        setup = full_session_setup
        assert setup["history_file"].exists()

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        # Read remaining history
        with open(setup["history_file"], "r") as f:
            remaining_lines = f.readlines()

        # Should have 2 lines (the other sessions), not 4
        assert len(remaining_lines) == 2

        # None should have our session ID
        for line in remaining_lines:
            entry = json.loads(line)
            assert entry.get("sessionId") != setup["session_id"]

    def test_preserves_other_history_entries(self, full_session_setup):
        """rm preserves history entries from other sessions."""
        setup = full_session_setup

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        with open(setup["history_file"], "r") as f:
            remaining_lines = f.readlines()

        session_ids = [json.loads(line).get("sessionId") for line in remaining_lines]
        assert "other-session" in session_ids
        assert "another-session" in session_ids


class TestRmDryRun:
    """Test dry run mode."""

    def test_dry_run_does_not_remove_files(self, full_session_setup):
        """Dry run doesn't actually remove anything."""
        setup = full_session_setup

        cmd_rm(str(setup["conv_file"]), dry_run=True)

        # Everything should still exist
        assert setup["conv_file"].exists()
        assert setup["agent_file"].exists()
        assert setup["debug_file"].exists()
        assert setup["todos_file"].exists()
        assert setup["file_history_dir"].exists()
        assert setup["project_session_dir"].exists()
        assert setup["session_env_dir"].exists()

        # History should be unchanged
        with open(setup["history_file"], "r") as f:
            lines = f.readlines()
        assert len(lines) == 4


class TestRmMissingFiles:
    """Test handling of missing files/directories."""

    def test_handles_missing_optional_files(self, temp_claude_home):
        """rm succeeds even if optional files don't exist."""
        session_id = "minimal-session"
        project_dir = "test-project"
        claude_dir = temp_claude_home / ".claude"
        projects_dir = claude_dir / "projects" / project_dir

        # Only create the main conversation file
        conv_file = projects_dir / f"{session_id}.jsonl"
        conv_file.write_text(
            json.dumps({
                "type": "summary",
                "summary": "Minimal test session",
                "leafUuid": "leaf-minimal",
            })
            + "\n"
        )

        # Should not raise
        with patch("builtins.input", return_value="y"):
            cmd_rm(str(conv_file), dry_run=False)

        assert not conv_file.exists()

    def test_nonexistent_session_exits(self, temp_claude_home):
        """rm exits with error for non-existent session."""
        with (
            pytest.raises(SystemExit) as exc_info,
            patch("builtins.input", return_value="y"),
        ):
            cmd_rm("nonexistent-session-uuid-12345", dry_run=False)
        assert exc_info.value.code == 1


class TestRmResolution:
    """Test session resolution for rm command."""

    def test_resolve_by_direct_path(self, full_session_setup):
        """rm works with direct file path."""
        setup = full_session_setup

        with patch("builtins.input", return_value="y"):
            cmd_rm(str(setup["conv_file"]), dry_run=False)

        assert not setup["conv_file"].exists()

    def test_resolve_by_uuid(self, full_session_setup):
        """rm works with session UUID."""
        setup = full_session_setup

        with patch("builtins.input", return_value="y"):
            cmd_rm(setup["session_id"], dry_run=False)

        assert not setup["conv_file"].exists()


class TestRmConfirmation:
    """Test confirmation prompt behavior."""

    def test_confirms_before_removal(self, full_session_setup):
        """rm prompts for confirmation before removing files."""
        setup = full_session_setup

        with patch("builtins.input", return_value="y") as mock_input:
            cmd_rm(str(setup["conv_file"]), dry_run=False)
            mock_input.assert_called_once_with("Proceed with removal? [y/n]: ")

    def test_cancels_on_n_response(self, full_session_setup):
        """rm cancels removal when user responds with 'n'."""
        setup = full_session_setup
        assert setup["conv_file"].exists()

        with patch("builtins.input", return_value="n"):
            with pytest.raises(SystemExit) as exc_info:
                cmd_rm(str(setup["conv_file"]), dry_run=False)
            assert exc_info.value.code == 0

        # File should still exist
        assert setup["conv_file"].exists()

    def test_cancels_on_invalid_response(self, full_session_setup):
        """rm cancels removal when user responds with anything other than 'y'."""
        setup = full_session_setup
        assert setup["conv_file"].exists()

        with patch("builtins.input", return_value="maybe"):
            with pytest.raises(SystemExit) as exc_info:
                cmd_rm(str(setup["conv_file"]), dry_run=False)
            assert exc_info.value.code == 0

        # File should still exist
        assert setup["conv_file"].exists()

    def test_handles_keyboard_interrupt(self, full_session_setup):
        """rm handles KeyboardInterrupt gracefully during confirmation."""
        setup = full_session_setup
        assert setup["conv_file"].exists()

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                cmd_rm(str(setup["conv_file"]), dry_run=False)
            assert exc_info.value.code == 0

        # File should still exist
        assert setup["conv_file"].exists()


class TestRmNonClaude:
    """Test rm with PI and Codex session paths."""

    def test_dry_run_codex_session_by_direct_path(self, tmp_path, monkeypatch, capsys):
        """rm --dry-run on a Codex session path should not crash."""
        temp_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: temp_home)

        session_path = (
            temp_home
            / ".codex"
            / "sessions"
            / "2026"
            / "04"
            / "10"
            / "rollout-2026-04-10T10-00-00-01961abc-rm-codex.jsonl"
        )
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            json.dumps({
                "timestamp": "2026-04-10T07:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "01961abc-rm-codex", "cwd": "/tmp/codex"},
            })
            + "\n"
            + json.dumps({
                "timestamp": "2026-04-10T07:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            })
            + "\n",
            encoding="utf-8",
        )

        cmd_rm(str(session_path), dry_run=True)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out, (
            "Expected dry-run message for Codex session. "
            f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
        )
        assert "01961abc-rm-codex" in captured.out, (
            "Expected Codex rm preview to display the canonical short session id. "
            f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
        )
        assert (
            "Session: rollout-2026-04-10T10-00-00-01961abc-rm-codex" not in captured.out
        ), (
            "Expected Codex rm preview not to present the rollout-prefixed filename stem in the session label. "
            f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
        )

    def test_dry_run_pi_session_by_direct_path(self, tmp_path, monkeypatch, capsys):
        """rm --dry-run on a PI session path should not crash."""
        temp_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: temp_home)

        session_path = (
            temp_home
            / ".pi"
            / "agent"
            / "sessions"
            / "--tmp--"
            / "2026-04-04T12-00-00_rm-pi-test.jsonl"
        )
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            json.dumps({
                "type": "session",
                "version": 3,
                "id": "rm-pi-test",
                "timestamp": "2026-04-04T12:00:00.000Z",
                "cwd": "/tmp/pi",
            })
            + "\n"
            + json.dumps({
                "type": "message",
                "id": "user-1",
                "parentId": "rm-pi-test",
                "timestamp": "2026-04-04T12:00:01.000Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hi"}],
                },
            })
            + "\n",
            encoding="utf-8",
        )

        cmd_rm(str(session_path), dry_run=True)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out, (
            "Expected dry-run message for PI session. "
            f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
        )

    def test_dry_run_codex_session_by_adapter_id(self, tmp_path, monkeypatch, capsys):
        """rm --dry-run should resolve a Codex session via adapter ID fallback."""
        temp_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: temp_home)

        session_id = "01961abc-def0-7123-89ab-codexrm0005"
        session_path = (
            temp_home
            / ".codex"
            / "sessions"
            / "2026"
            / "04"
            / "10"
            / f"rollout-2026-04-10T10-00-00-{session_id}.jsonl"
        )
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            json.dumps({
                "timestamp": "2026-04-10T07:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": session_id, "cwd": "/tmp/codex"},
            })
            + "\n"
            + json.dumps({
                "timestamp": "2026-04-10T07:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            })
            + "\n",
            encoding="utf-8",
        )

        cmd_rm(session_id, dry_run=True)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out, (
            "Expected dry-run to succeed when resolving Codex session by adapter ID. "
            f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
        )

    def test_rm_codex_session_removes_file(self, tmp_path, monkeypatch, capsys):
        """rm on a Codex session path should delete the session file."""
        temp_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: temp_home)

        session_path = (
            temp_home
            / ".codex"
            / "sessions"
            / "2026"
            / "04"
            / "10"
            / "rollout-2026-04-10T10-00-00-01961abc-rm-codex2.jsonl"
        )
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            json.dumps({
                "timestamp": "2026-04-10T07:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "01961abc-rm-codex2", "cwd": "/tmp/codex"},
            })
            + "\n",
            encoding="utf-8",
        )

        assert session_path.exists()
        with patch("builtins.input", return_value="y"):
            cmd_rm(str(session_path), dry_run=False)

        assert not session_path.exists(), (
            "Expected Codex session file to be removed after rm"
        )


if __name__ == "__main__":
    import subprocess

    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    sys.exit(result.returncode)
