#!/usr/bin/env python3
"""Behavior tests for search output modes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conversations import ConversationFlags, SearchOutputMode, cmd_search


def test_cmd_search_only_id_mode_prints_plain_session_id(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`output_mode=ONLY_ID` should emit only the matching session identifier."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    session_path = home / ".codex" / "sessions" / "rollout-abc.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}}) + "\n"
        + json.dumps(
            {
                "type": "response_item",
                "timestamp": "2025-01-01T00:00:00Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "unique-search-output-mode"}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "unique-search-output-mode",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected search ONLY_ID mode to exit successfully when a session matches. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == "abc", (
        "Expected ONLY_ID search mode to print only the matching session id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "history_path:" not in captured.out, (
        "Expected ONLY_ID search mode to suppress metadata output. "
        f"Got stdout:\n{captured.out}"
    )
