#!/usr/bin/env python3
"""Behavior tests for message role selection."""

from __future__ import annotations

import json
from pathlib import Path

from chats import ConversationFlags, MessageSelection, SessionScan


def test_session_scan_hides_assistant_messages_with_message_selection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`message_selection=NO_ASSISTANT` should hide regular assistant messages in downstream scans."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home / ".claude" / "projects" / "demo-project" / "scan-session.jsonl"
    )
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "".join(
            json.dumps(entry, separators=(",", ":")) + "\n"
            for entry in [
                {
                    "type": "user",
                    "sessionId": "scan-session",
                    "cwd": "/tmp/session-scan",
                    "timestamp": "2026-04-16T10:00:00.000Z",
                    "message": {"role": "user", "content": "scan-user-token"},
                    "uuid": "user-1",
                },
                {
                    "type": "assistant",
                    "sessionId": "scan-session",
                    "cwd": "/tmp/session-scan",
                    "timestamp": "2026-04-16T10:00:01.000Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "scan-assistant-token"}],
                    },
                    "uuid": "assistant-1",
                },
            ]
        ),
        encoding="utf-8",
    )

    scan = SessionScan.from_file(
        session_path,
        ConversationFlags(
            color="never",
            paging=False,
            message_selection=MessageSelection.NO_ASSISTANT,
        ),
    )

    assert [message.role for message in scan.messages] == ["user"], (
        "Expected NO_ASSISTANT message selection to hide regular assistant messages "
        f"while preserving user messages. Got roles: {[message.role for message in scan.messages]!r}"
    )
