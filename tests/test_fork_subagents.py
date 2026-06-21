#!/usr/bin/env python3
"""Tests for user-initiated `/fork` subagent capture under `--agents`.

A `/fork` is stored as a detached sidechain: the main session keeps only the
`/fork` command and the returning `<task-notification>`, while the fork's
transcript lives in `subagents/agent-{slug}-{taskId}.jsonl` whose leading
`fork-context-ref` links back to the parent (no in-thread `Task` anchor). These
tests pin that such forks are discovered, merged, and labelled `Fork` (distinct
from agent-initiated `Task` subagents, which render as `Agent`).
"""

import json
from pathlib import Path

from chats import ConversationFlags
from chats.commands import _merge_agent_messages, find_agent_files_for_session
from chats.formatting import format_to_xml
from chats.parsing import parse_jsonl

SESSION_ID = "39fbe958-8ccb-4534-a34e-36b0dc6b8dff"
TASK_ID = "ok-so-we-3dcb2cb11fb5b840"


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in entries),
        encoding="utf-8",
    )


def _write_fork(
    project_dir: Path,
    *,
    prompt: str,
    reply: str,
    started_at: str,
    replied_at: str,
) -> Path:
    """Write a `/fork` transcript: leading fork-context-ref, then sidechain messages."""
    fork_file = project_dir / SESSION_ID / "subagents" / f"agent-{TASK_ID}.jsonl"
    _write_jsonl(fork_file, [
        {
            "type": "fork-context-ref",
            "agentId": TASK_ID,
            "parentSessionId": SESSION_ID,
            "parentLastUuid": "2e635c10-b8ac-4653-ad2d-6603c11651c9",
            "contextLength": 64,
        },
        {
            "type": "user",
            "parentUuid": None,
            "isSidechain": True,
            "agentId": TASK_ID,
            "sessionId": SESSION_ID,
            "uuid": "14994b85-f578-4b61-a08b-dcf256f32092",
            "timestamp": started_at,
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "parentUuid": "14994b85-f578-4b61-a08b-dcf256f32092",
            "isSidechain": True,
            "agentId": TASK_ID,
            "sessionId": SESSION_ID,
            "uuid": "25aa5c21-c9bd-5764-be3e-7714d22762a0",
            "timestamp": replied_at,
            "message": {"role": "assistant", "content": [{"type": "text", "text": reply}]},
        },
    ])
    fork_file.with_suffix(".meta.json").write_text(
        json.dumps({
            "agentType": "fork",
            "isFork": True,
            "description": prompt[:60],
            "name": TASK_ID.rsplit("-", 1)[0],
        }),
        encoding="utf-8",
    )
    return fork_file


class TestForkDiscovery:
    """A fork file is anchored to its parent via fork-context-ref.parentSessionId,
    not a first-line sessionId, so discovery must match on it."""

    def test_finds_fork_by_parent_session_id(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{"type": "summary", "summary": "test"}])

        fork_file = _write_fork(
            project_dir,
            prompt="FORK_PROMPT",
            reply="FORK_REPLY",
            started_at="2025-01-01T00:01:00Z",
            replied_at="2025-01-01T00:01:30Z",
        )

        result = find_agent_files_for_session(conv_file, SESSION_ID)
        assert result == [fork_file], (
            "Expected the fork transcript to be discovered by its "
            f"fork-context-ref.parentSessionId. Got: {result}"
        )


class TestForkRendering:
    """A merged fork renders as a `Fork` block (vs a classic agent's `Agent`),
    carrying its content, the prompt as <subagent-task>, and subagent_type="fork"."""

    def _merge_and_format(self, tmp_path: Path, monkeypatch) -> str:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"

        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "message": {"role": "user", "content": "/fork do the thing"},
        }])
        _write_fork(
            project_dir,
            prompt="FORK_PROMPT",
            reply="FORK_REPLY",
            started_at="2025-01-01T00:01:00Z",
            replied_at="2025-01-01T00:01:30Z",
        )

        flags = ConversationFlags(show_agents=True, color="never")
        messages = parse_jsonl(conv_file.read_text(), flags, source_path=conv_file)
        merged = _merge_agent_messages(messages, conv_file, flags)
        return format_to_xml(merged, flags)

    def test_fork_content_is_spliced_in(self, tmp_path: Path, monkeypatch):
        output = self._merge_and_format(tmp_path, monkeypatch)
        assert "FORK_REPLY" in output, (
            f"Expected the fork's reply to be merged into the timeline. Got:\n{output}"
        )
        assert "<subagent-task>" in output and "FORK_PROMPT" in output, (
            f"Expected the fork prompt rendered as <subagent-task>. Got:\n{output}"
        )

    def test_fork_renders_as_fork_not_agent(self, tmp_path: Path, monkeypatch):
        output = self._merge_and_format(tmp_path, monkeypatch)
        assert "## Fork" in output, (
            f"Expected a user-initiated fork to render with a Fork header. Got:\n{output}"
        )
        assert "## Agent" not in output, (
            f"A fork is user-initiated, so it must not render as a classic Agent. Got:\n{output}"
        )
        assert 'subagent_type="fork"' in output, (
            f"Expected subagent_type=\"fork\" as the machine-readable marker. Got:\n{output}"
        )
