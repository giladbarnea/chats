#!/usr/bin/env python3
"""Behavior tests for search visibility semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import ConversationFlags, SearchOutputMode, cmd_search


def _write_claude_session(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_cmd_search_agent_only_content_is_hidden_by_default_and_found_with_agents(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Agent sidechains should enter the search space only when --agents is enabled."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    project_dir = home / ".claude" / "projects" / "proj"
    _write_claude_session(
        project_dir / "main.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp/search-visibility",
                "message": {"role": "user", "content": "main session text"},
            }
        ],
    )
    _write_claude_session(
        project_dir / "agent-sidechain.jsonl",
        [
            {
                "type": "assistant",
                "agentId": "agent-1",
                "timestamp": "2025-01-01T00:00:01Z",
                "cwd": "/tmp/search-visibility",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "slice-4-agent-only-needle"}],
                },
            }
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "slice-4-agent-only-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 1, (
        "Expected agent-only content to stay out of the default search space. "
        f"Got exit code: {exc_info.value.code}"
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "slice-4-agent-only-needle",
            ConversationFlags(color="never", paging=False, show_agents=True),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected --agents search to include sidechain agent content. "
        f"Got exit code: {exc_info.value.code}"
    )
    stdout = capsys.readouterr().out
    assert "agent-sidechain" in stdout, (
        "Expected the agent sidechain file to appear once --agents is enabled. "
        f"Got stdout:\n{stdout}"
    )


def test_cmd_search_plan_text_is_hidden_by_default_and_found_with_plans(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Plan text should stay out of search unless plans are explicitly enabled."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "plan.jsonl"
    _write_claude_session(
        session_path,
        [
            {
                "type": "assistant",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp/search-visibility",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "ExitPlanMode",
                            "input": {"plan": "slice-4-plan-needle"},
                        }
                    ],
                },
            }
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "slice-4-plan-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 1, (
        "Expected plan text to stay out of default search results. "
        f"Got exit code: {exc_info.value.code}"
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "slice-4-plan-needle",
            ConversationFlags(color="never", paging=False, show_plans=True),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected plan text to become searchable when plans are enabled. "
        f"Got exit code: {exc_info.value.code}"
    )
    stdout = capsys.readouterr().out
    assert "plan" in stdout, (
        "Expected the plan-bearing session to appear once plans are enabled. "
        f"Got stdout:\n{stdout}"
    )


def test_cmd_search_render_dependent_plan_tag_query_still_works(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Render-dependent queries should still reach full confirmation instead of being skipped."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".claude" / "projects" / "proj" / "plan-tag.jsonl"
    _write_claude_session(
        session_path,
        [
            {
                "type": "assistant",
                "timestamp": "2025-01-01T00:00:00Z",
                "cwd": "/tmp/search-visibility",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "ExitPlanMode",
                            "input": {"plan": "slice-4-plan-tag-needle"},
                        }
                    ],
                },
            }
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "<tool-input",
            ConversationFlags(color="never", paging=False, show_plans=True),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        "Expected render-dependent tag queries to keep working after adding "
        f"candidate/confirm search. Got exit code: {exc_info.value.code}"
    )
    stdout = capsys.readouterr().out
    assert "plan-tag" in stdout, (
        "Expected the plan-tag session to appear for a render-dependent query. "
        f"Got stdout:\n{stdout}"
    )
