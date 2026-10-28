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
import re
from pathlib import Path

from chats import ConversationFlags
from chats.commands import _merge_agent_messages, find_agent_files_for_session
from chats.formatting import format_to_xml
from chats.parsing import parse_jsonl

SESSION_ID = "40000000-0000-4000-8000-000000000001"
TASK_ID = "example-fork-0000000000000001"


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
            "parentLastUuid": "40000000-0000-4000-8000-000000000100",
            "contextLength": 64,
        },
        {
            "type": "user",
            "parentUuid": None,
            "isSidechain": True,
            "agentId": TASK_ID,
            "sessionId": SESSION_ID,
            "uuid": "40000000-0000-4000-8000-000000000200",
            "timestamp": started_at,
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "assistant",
            "parentUuid": "40000000-0000-4000-8000-000000000200",
            "isSidechain": True,
            "agentId": TASK_ID,
            "sessionId": SESSION_ID,
            "uuid": "40000000-0000-4000-8000-000000000300",
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


FORK_BOILERPLATE = (
    "<fork-boilerplate>\n"
    "You are a worker fork. The transcript above is the parent's history — inherited "
    "reference, not your situation. Execute ONE directive, then stop.\n"
    "</fork-boilerplate>\n\n"
)


class TestForkTaskAndName:
    """A fork's task is its directive, not Claude Code's worker boilerplate, and its
    header carries the name Claude Code gave it."""

    def _merge(self, tmp_path: Path, monkeypatch, prompt: str) -> str:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        project_dir = tmp_path / ".claude" / "projects" / "proj"
        conv_file = project_dir / f"{SESSION_ID}.jsonl"
        _write_jsonl(conv_file, [{
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "message": {"role": "user", "content": "start"},
        }])
        _write_fork(
            project_dir,
            prompt=prompt,
            reply="FORK_REPLY",
            started_at="2025-01-01T00:01:00Z",
            replied_at="2025-01-01T00:01:30Z",
        )
        flags = ConversationFlags(show_agents=True, color="never")
        messages = parse_jsonl(conv_file.read_text(), flags, source_path=conv_file)
        return format_to_xml(_merge_agent_messages(messages, conv_file, flags), flags)

    def test_task_is_the_directive_without_boilerplate(self, tmp_path: Path, monkeypatch):
        output = self._merge(tmp_path, monkeypatch, FORK_BOILERPLATE + "Your directive: DIRECTIVE_MARKER")

        assert re.search(r"<subagent-task>\n\s*Your directive: DIRECTIVE_MARKER\n\s*</subagent-task>", output), (
            f"Expected the directive alone as the subagent task. Got:\n{output}"
        )
        assert "worker fork" not in output and "fork-boilerplate" not in output, (
            f"Expected Claude Code's fork boilerplate dropped. Got:\n{output}"
        )

    def test_header_carries_the_fork_name(self, tmp_path: Path, monkeypatch):
        output = self._merge(tmp_path, monkeypatch, "FORK_PROMPT")

        assert "## Fork 'example-fork'" in output and 'name="example-fork"' in output, (
            f"Expected the fork's meta name in its header and attributes. Got:\n{output}"
        )


def test_search_ignores_fork_boilerplate(tmp_path: Path):
    """Search reads a fork transcript the way parse does: the directive, not the boilerplate."""
    import os
    import subprocess
    import sys

    home = tmp_path / "home"
    project_dir = home / ".claude" / "projects" / "proj"
    _write_jsonl(project_dir / f"{SESSION_ID}.jsonl", [{
        "type": "user",
        "timestamp": "2025-01-01T00:00:00Z",
        "message": {"role": "user", "content": "start"},
    }])
    _write_fork(
        project_dir,
        prompt=FORK_BOILERPLATE + "Your directive: DIRECTIVE_SEARCH_MARKER",
        reply="FORK_REPLY",
        started_at="2025-01-01T00:01:00Z",
        replied_at="2025-01-01T00:01:30Z",
    )

    def search(pattern: str) -> str:
        return subprocess.run(
            [str(Path(sys.executable).with_name("ch")), "search", pattern, "--agents", "--only-id"],
            env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()

    assert set(search("DIRECTIVE_SEARCH_MARKER").split()) == {SESSION_ID, f"agent-{TASK_ID}"}, "Expected parent and child matches."
    assert search("worker fork") == "", "Expected the fork boilerplate not to match."
