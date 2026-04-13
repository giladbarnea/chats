#!/usr/bin/env python3
"""Integration tests for cross-ecosystem session discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conversations import ConversationFlags, cmd_parse, cmd_rename, cmd_search


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _write_claude_session(
    path: Path,
    *,
    summary: str,
    user_text: str,
    assistant_text: str,
    session_id: str,
    cwd: str,
    timestamp_prefix: str,
) -> None:
    """Write a minimal Claude-format session fixture."""
    _write_jsonl(
        path,
        [
            {"type": "summary", "summary": summary, "leafUuid": f"{session_id}-leaf"},
            {
                "type": "user",
                "sessionId": session_id,
                "cwd": cwd,
                "timestamp": f"{timestamp_prefix}:00.000Z",
                "message": {"role": "user", "content": user_text},
                "uuid": f"{session_id}-user",
            },
            {
                "type": "assistant",
                "sessionId": session_id,
                "cwd": cwd,
                "timestamp": f"{timestamp_prefix}:01.000Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": assistant_text}],
                },
                "uuid": f"{session_id}-assistant",
            },
        ],
    )


def _write_pi_session(
    path: Path,
    *,
    session_id: str,
    user_text: str,
    assistant_text: str,
    cwd: str,
    timestamp_prefix: str,
) -> None:
    """Write a minimal PI-format session fixture."""
    _write_jsonl(
        path,
        [
            {
                "type": "session",
                "id": session_id,
                "cwd": cwd,
                "timestamp": f"{timestamp_prefix}:00.000Z",
                "version": 3,
            },
            {
                "type": "message",
                "id": f"{session_id}-user",
                "parentId": session_id,
                "timestamp": f"{timestamp_prefix}:01.000Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": user_text}],
                },
            },
            {
                "type": "message",
                "id": f"{session_id}-assistant",
                "parentId": f"{session_id}-user",
                "timestamp": f"{timestamp_prefix}:02.000Z",
                "message": {
                    "role": "assistant",
                    "model": "z-ai/glm-5",
                    "content": [{"type": "text", "text": assistant_text}],
                },
            },
        ],
    )


def _write_codex_session(
    path: Path,
    *,
    session_id: str,
    user_text: str,
    assistant_text: str,
    cwd: str,
    timestamp_prefix: str,
) -> None:
    """Write a minimal Codex-format session fixture."""
    _write_jsonl(
        path,
        [
            {
                "type": "session_meta",
                "timestamp": f"{timestamp_prefix}:00.000Z",
                "payload": {
                    "id": session_id,
                    "cwd": cwd,
                    "timestamp": f"{timestamp_prefix}:00.000Z",
                    "originator": "codex_cli_rs",
                    "cli_version": "0.99.0",
                    "source": "cli",
                    "model_provider": "openai",
                },
            },
            {
                "type": "response_item",
                "timestamp": f"{timestamp_prefix}:01.000Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_text}],
                },
            },
            {
                "type": "response_item",
                "timestamp": f"{timestamp_prefix}:02.000Z",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": assistant_text}],
                },
            },
        ],
    )


def _build_supported_session_space(temp_home: Path) -> dict[str, Path]:
    """Create one Claude, PI, and Codex session with deliberate modified times."""
    claude_path = (
        temp_home
        / ".claude"
        / "projects"
        / "demo-project"
        / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    )
    _write_claude_session(
        claude_path,
        summary="Claude mid session",
        user_text="claude newest claude-only candidate",
        assistant_text="claude assistant response",
        session_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cwd="/tmp/claude-project",
        timestamp_prefix="2026-04-11T07:09",
    )

    pi_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-pi-project--"
        / "2026-04-11T10-08-00-000Z_pi-session.jsonl"
    )
    _write_pi_session(
        pi_path,
        session_id="pi-session-id",
        user_text="pi older session prompt",
        assistant_text="pi assistant response",
        cwd="/tmp/pi-project",
        timestamp_prefix="2026-04-11T07:08",
    )

    codex_path = (
        temp_home
        / ".codex"
        / "sessions"
        / "2026"
        / "04"
        / "11"
        / "rollout-2026-04-11T10-11-09-019d7b61-53d7-7891-9033-ad646f9d2ce7.jsonl"
    )
    _write_codex_session(
        codex_path,
        session_id="019d7b61-53d7-7891-9033-ad646f9d2ce7",
        user_text="codex newest session prompt",
        assistant_text="codex assistant response with codex-search-token",
        cwd="/tmp/codex-project",
        timestamp_prefix="2026-04-11T07:11",
    )

    os.utime(pi_path, (1_700_000_001, 1_700_000_001))
    os.utime(claude_path, (1_700_000_002, 1_700_000_002))
    os.utime(codex_path, (1_700_000_003, 1_700_000_003))

    return {"claude": claude_path, "pi": pi_path, "codex": codex_path}


def test_cmd_parse_recent_negative_index_uses_all_supported_sessions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`-1` should resolve against the newest Claude, PI, and Codex session together."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    _build_supported_session_space(temp_home)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        "-1",
        slice_str="-1",
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert (
        "history_path: ~/.codex/sessions/2026/04/11/"
        "rollout-2026-04-11T10-11-09-019d7b61-53d7-7891-9033-ad646f9d2ce7.jsonl"
    ) in captured.out, (
        "Expected `-1` to resolve within the unified supported-session search space, "
        "so the newest Codex session should win over newer-than-PI Claude sessions. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "codex assistant response" in captured.out, (
        "Expected the last message from the newest supported session to be rendered. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_search_uses_all_supported_sessions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`search` should match content from non-Claude supported sessions too."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    _build_supported_session_space(temp_home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "codex-search-token",
            ConversationFlags(color="never", paging=False),
            list_only=True,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected `search` to exit successfully when a Codex session matches. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "history_path: ~/.codex/sessions/2026/04/11/"
        "rollout-2026-04-11T10-11-09-019d7b61-53d7-7891-9033-ad646f9d2ce7.jsonl"
    ) in captured.out, (
        "Expected `search` to include matching Codex sessions in the unified search space. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_search_matches_custom_title_across_ecosystems(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Search should find a session whose custom title matches the query, even
    when assistant messages are hidden (so custom-title entries aren't parsed
    as messages).  Custom titles should be a first-class search dimension like
    summaries, not matched incidentally through message content."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    paths = _build_supported_session_space(temp_home)

    # Rename the PI session with a unique custom title
    cmd_rename(str(paths["pi"]), "xyzzy-unique-title-token")

    # Search with show_assistant_messages=False — custom-title entries won't
    # be parsed as messages, so matching must happen via the dedicated
    # custom-title extraction path.
    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "xyzzy-unique-title-token",
            ConversationFlags(color="never", paging=False, show_assistant_messages=False),
            list_only=True,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected search to find the PI session via its custom title. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "pi" in captured.out.lower(), (
        "Expected PI session path in output. "
        f"Got stdout:\n{captured.out}"
    )


def test_cmd_search_only_id_prints_plain_session_id(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--only-id` should emit just the matching session identifier."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    paths = _build_supported_session_space(temp_home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "codex-search-token",
            ConversationFlags(color="never", paging=False),
            list_only=False,
            emit_metadata=True,
            only_id=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected `search --only-id` to exit successfully when a Codex session matches. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == paths["codex"].stem, (
        "Expected `--only-id` to print only the matching session id, with no "
        f"metadata or content. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "history_path:" not in captured.out, (
        "Expected `--only-id` to suppress search metadata. "
        f"Got stdout:\n{captured.out}"
    )
