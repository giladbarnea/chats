#!/usr/bin/env python3
"""Tests for Claude agent file discovery in the subagents/ directory layout."""

import json
from pathlib import Path

import pytest

from chats import cmd_search, ConversationFlags, SearchOutputMode
from chats.commands import _merge_agent_messages, find_agent_files_for_session
from chats.formatting import format_to_xml
from chats.parsing import find_all_supported_session_files, parse_jsonl


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries),
        encoding="utf-8",
    )


SESSION_ID = "aaaa-bbbb-cccc-dddd"


# =============================================================================
# find_agent_files_for_session
# =============================================================================


class TestFindAgentFilesNewLayout:
    """Agent files in <session_id>/subagents/ (new Claude layout)."""

    def test_finds_agent_in_subagents_dir(self, tmp_path: Path, monkeypatch):
        project_dir = tmp_path / ".claude" / "projects" / "proj"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{"type": "summary", "summary": "test"}])

        agent_file = project_dir / SESSION_ID / "subagents" / "agent-deadbeef.jsonl"
        _write_jsonl(agent_file, [
            {"type": "assistant", "sessionId": SESSION_ID, "agentId": "deadbeef"}
        ])

        result = find_agent_files_for_session(conv_file, SESSION_ID)
        assert len(result) == 1, (
            f"Expected to find 1 agent file in subagents/ dir. Got: {result}"
        )
        assert result[0] == agent_file

    def test_finds_multiple_agents_in_subagents_dir(self, tmp_path: Path, monkeypatch):
        project_dir = tmp_path / ".claude" / "projects" / "proj"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{"type": "summary", "summary": "test"}])

        subagents_dir = project_dir / SESSION_ID / "subagents"
        for agent_id in ("aaa", "bbb"):
            _write_jsonl(subagents_dir / f"agent-{agent_id}.jsonl", [
                {"type": "assistant", "sessionId": SESSION_ID, "agentId": agent_id}
            ])

        result = find_agent_files_for_session(conv_file, SESSION_ID)
        assert len(result) == 2, (
            f"Expected 2 agent files. Got: {result}"
        )

    def test_ignores_agents_from_other_sessions(self, tmp_path: Path, monkeypatch):
        project_dir = tmp_path / ".claude" / "projects" / "proj"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{"type": "summary", "summary": "test"}])

        other_session = "other-session-id"
        _write_jsonl(project_dir / SESSION_ID / "subagents" / "agent-ours.jsonl", [
            {"type": "assistant", "sessionId": SESSION_ID, "agentId": "ours"}
        ])
        _write_jsonl(project_dir / other_session / "subagents" / "agent-theirs.jsonl", [
            {"type": "assistant", "sessionId": other_session, "agentId": "theirs"}
        ])

        result = find_agent_files_for_session(conv_file, SESSION_ID)
        assert len(result) == 1, (
            f"Expected 1 agent file (ours only). Got: {result}"
        )
        assert result[0].name == "agent-ours.jsonl"

    def test_no_session_dir_returns_empty(self, tmp_path: Path, monkeypatch):
        """When the session has no subagents/ dir, return empty list."""
        project_dir = tmp_path / ".claude" / "projects" / "proj"
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{"type": "summary", "summary": "test"}])

        result = find_agent_files_for_session(conv_file, SESSION_ID)
        assert result == [], (
            f"Expected empty list when no subagents/ dir. Got: {result}"
        )


class TestClaudeAgentBlockRendering:
    """Merged Claude subagents render like Codex: ## Agent + <subagent-task>, indented,
    but with no nickname."""

    def test_claude_agent_block_has_task_and_indent_no_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "message": {"role": "user", "content": "spawn an agent"},
        }])

        agent_file = project_dir / SESSION_ID / "subagents" / "agent-beef.jsonl"
        _write_jsonl(agent_file, [
            {
                "type": "user",
                "sessionId": SESSION_ID,
                "agentId": "beef",
                "timestamp": "2025-01-01T00:01:00Z",
                "message": {"role": "user", "content": "CLAUDE_TASK_PROMPT"},
            },
            {
                "type": "assistant",
                "sessionId": SESSION_ID,
                "agentId": "beef",
                "timestamp": "2025-01-01T00:01:01Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "CLAUDE_AGENT_REPLY"}],
                },
            },
        ])
        agent_file.with_suffix(".meta.json").write_text(
            json.dumps({"agentType": "general-purpose", "toolUseId": "toolu_x"}),
            encoding="utf-8",
        )

        flags = ConversationFlags(show_agents=True, color="never")
        messages = parse_jsonl(conv_file.read_text(), flags, source_path=conv_file)
        merged = _merge_agent_messages(messages, conv_file, flags)
        output = format_to_xml(merged, flags)

        assert "## Agent" in output, f"Expected an agent block. Got:\n{output}"
        assert "name=" not in output, (
            f"Claude subagents have no nickname, so no name attribute. Got:\n{output}"
        )
        assert "<subagent-task>" in output and "CLAUDE_TASK_PROMPT" in output, (
            f"Expected the prompt rendered as <subagent-task>. Got:\n{output}"
        )
        assert output.count("CLAUDE_TASK_PROMPT") == 1, (
            f"Expected the prompt only inside <subagent-task>, not duplicated. Got:\n{output}"
        )
        assert "\n  <subagent-task>" in output and "\n  CLAUDE_AGENT_REPLY" in output, (
            f"Expected agent inner content indented 2 spaces. Got:\n{output}"
        )


# =============================================================================
# find_all_supported_session_files (search mode sidechain discovery)
# =============================================================================


class TestFindAllSupportedSessionFilesNewLayout:
    """find_all_supported_session_files discovers agents in subagents/."""

    def test_discovers_agent_files_in_subagents_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"

        # Main session
        _write_jsonl(project_dir / "main.jsonl", [
            {"type": "summary", "summary": "main"}
        ])
        # Agent in new layout
        _write_jsonl(project_dir / "main" / "subagents" / "agent-beef.jsonl", [
            {"type": "assistant", "sessionId": "main", "agentId": "beef"}
        ])

        all_files = find_all_supported_session_files(include_sidechains=True)
        agent_files = [f for f in all_files if "agent-" in f.name]
        assert len(agent_files) >= 1, (
            f"Expected agent files in subagents/ to be discovered. "
            f"Got {len(agent_files)} agent files in: {all_files}"
        )

    def test_excludes_subagents_when_sidechains_disabled(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"

        _write_jsonl(project_dir / "main.jsonl", [
            {"type": "summary", "summary": "main"}
        ])
        _write_jsonl(project_dir / "main" / "subagents" / "agent-beef.jsonl", [
            {"type": "assistant", "sessionId": "main", "agentId": "beef"}
        ])

        all_files = find_all_supported_session_files(include_sidechains=False)
        agent_files = [f for f in all_files if "agent-" in f.name]
        assert agent_files == [], (
            f"Expected no agent files when sidechains disabled. Got: {agent_files}"
        )

    def test_ignores_non_agent_jsonl_files_in_subagents_dir(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"

        _write_jsonl(project_dir / "main.jsonl", [
            {"type": "summary", "summary": "main"}
        ])
        _write_jsonl(project_dir / "main" / "subagents" / "agent-beef.jsonl", [
            {"type": "assistant", "sessionId": "main", "agentId": "beef"}
        ])
        _write_jsonl(project_dir / "main" / "subagents" / "not-an-agent.jsonl", [
            {"type": "summary", "summary": "should stay hidden"}
        ])

        all_files = find_all_supported_session_files(include_sidechains=True)
        assert project_dir / "main" / "subagents" / "agent-beef.jsonl" in all_files
        assert project_dir / "main" / "subagents" / "not-an-agent.jsonl" not in all_files


# =============================================================================
# Search integration: agents in subagents/ found by cmd_search
# =============================================================================


class TestSearchFindsAgentsInSubagents:
    """cmd_search should find content in agent files stored in subagents/."""

    def test_search_finds_agent_content_in_subagents_dir(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: home)
        project_dir = home / ".claude" / "projects" / "proj"

        _write_jsonl(project_dir / "main.jsonl", [
            {
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp",
                "message": {"role": "user", "content": "hello"},
            }
        ])
        _write_jsonl(
            project_dir / "main" / "subagents" / "agent-deadbeef.jsonl",
            [
                {
                    "type": "assistant",
                    "agentId": "deadbeef",
                    "timestamp": "2025-01-01T00:00:01Z",
                    "cwd": "/tmp",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "subagent-needle-xyz"}],
                    },
                }
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            cmd_search(
                "subagent-needle-xyz",
                ConversationFlags(color="never", paging=False, show_agents=True),
                output_mode=SearchOutputMode.LIST,
                emit_metadata=True,
            )
        assert exc_info.value.code == 0, (
            "Expected --agents search to find content in subagents/ agent files. "
            f"Got exit code: {exc_info.value.code}"
        )
