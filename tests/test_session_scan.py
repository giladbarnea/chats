#!/usr/bin/env python3
"""Behavior tests for SessionScan."""

from __future__ import annotations

import json
from pathlib import Path

from chats import ConversationFlags, MessageSelection, SessionScan


def test_session_scan_extracts_search_facets_independently_of_visible_messages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """SessionScan should preserve summary/current-title/cwd even when message visibility hides assistant text."""
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
                    "type": "summary",
                    "summary": "scan-summary-token",
                    "leafUuid": "leaf-1",
                },
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
                {
                    "type": "custom-title",
                    "customTitle": "scan-title-token",
                    "sessionId": "scan-session",
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

    assert scan.provider == "claude", (
        "Expected SessionScan to expose the owning provider for the scanned session. "
        f"Got: {scan.provider!r}"
    )
    assert scan.cwd == "/tmp/session-scan", (
        "Expected SessionScan to preserve cwd for directory-filtered search. "
        f"Got: {scan.cwd!r}"
    )
    assert scan.summaries == ("scan-summary-token",), (
        "Expected SessionScan to preserve summary search text independently of message visibility. "
        f"Got: {scan.summaries!r}"
    )
    assert scan.custom_title == "scan-title-token", (
        "Expected SessionScan to preserve only the current title, not historical title lists. "
        f"Got: {scan.custom_title!r}"
    )
    assert [message.role for message in scan.messages] == ["user"], (
        "Expected SessionScan.messages to respect the supplied visibility flags while keeping "
        f"summary/title search facets intact. Got roles: {[message.role for message in scan.messages]!r}"
    )


def test_session_scan_acknowledges_only_latest_custom_title(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """SessionScan should expose only the latest title when a session was renamed multiple times."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    session_path = (
        temp_home
        / ".claude"
        / "projects"
        / "demo-project"
        / "scan-latest-title-session.jsonl"
    )
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "".join(
            json.dumps(entry, separators=(",", ":")) + "\n"
            for entry in [
                {
                    "type": "summary",
                    "summary": "scan-summary-token",
                    "leafUuid": "leaf-2",
                },
                {
                    "type": "user",
                    "sessionId": "scan-latest-title-session",
                    "cwd": "/tmp/session-scan",
                    "timestamp": "2026-04-16T10:00:00.000Z",
                    "message": {"role": "user", "content": "scan-user-token"},
                    "uuid": "user-1",
                },
                {
                    "type": "custom-title",
                    "customTitle": "historic-title-token",
                    "sessionId": "scan-latest-title-session",
                },
                {
                    "type": "custom-title",
                    "customTitle": "current-title-token",
                    "sessionId": "scan-latest-title-session",
                },
            ]
        ),
        encoding="utf-8",
    )

    scan = SessionScan.from_file(
        session_path,
        ConversationFlags(color="never", paging=False),
    )

    assert scan.custom_title == "current-title-token", (
        "Expected SessionScan to acknowledge only the latest title after multiple renames. "
        f"Got: {scan.custom_title!r}"
    )
