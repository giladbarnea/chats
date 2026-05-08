#!/usr/bin/env python3
"""Integration tests for cross-ecosystem session discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conversations import (
    ConversationFlags,
    MessageSelection,
    PoolFilter,
    SearchOutputMode,
    SessionPool,
    cmd_parse,
    cmd_rename,
    cmd_search,
)


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


def test_session_pool_discovers_one_unified_inventory_and_resolves_exact_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """SessionPool should treat Claude, PI, and Codex sessions as one provider-neutral pool."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    paths = _build_supported_session_space(temp_home)

    pool = SessionPool.discover()

    assert set(pool.files) == set(paths.values()), (
        "Expected SessionPool.files to include the full supported-session inventory. "
        f"Got: {pool.files!r}"
    )
    assert pool.by_provider["claude"] == (paths["claude"],), (
        "Expected SessionPool to group Claude sessions under the 'claude' provider. "
        f"Got: {pool.by_provider['claude']!r}"
    )
    assert pool.by_provider["pi"] == (paths["pi"],), (
        "Expected SessionPool to group PI sessions under the 'pi' provider. "
        f"Got: {pool.by_provider['pi']!r}"
    )
    assert pool.by_provider["codex"] == (paths["codex"],), (
        "Expected SessionPool to group Codex sessions under the 'codex' provider. "
        f"Got: {pool.by_provider['codex']!r}"
    )
    assert (
        pool.resolve_exact_identifier("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        == paths["claude"]
    ), (
        "Expected exact Claude ids to resolve from the unified pool. "
        f"Got: {pool.resolve_exact_identifier('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')!r}"
    )
    assert pool.resolve_exact_identifier("pi-session-id") == paths["pi"], (
        "Expected exact PI native ids to resolve from the unified pool. "
        f"Got: {pool.resolve_exact_identifier('pi-session-id')!r}"
    )
    assert (
        pool.resolve_exact_identifier("019d7b61-53d7-7891-9033-ad646f9d2ce7")
        == paths["codex"]
    ), (
        "Expected exact Codex native ids to resolve from the unified pool. "
        f"Got: {pool.resolve_exact_identifier('019d7b61-53d7-7891-9033-ad646f9d2ce7')!r}"
    )


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


def test_cmd_parse_provider_filter_limits_recent_negative_index_resolution(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`-p/--provider` should narrow parse's recent index only, matching search routing."""
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
        pool_filter=PoolFilter(provider="claude"),
    )

    captured = capsys.readouterr()
    assert (
        "history_path: ~/.claude/projects/demo-project/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
        in captured.out
    ), (
        "Expected provider='claude' filter to make parse resolve '-1' against "
        f"only Claude sessions. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "claude assistant response" in captured.out, (
        "Expected the newest Claude session's last message to render after filtering. "
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
            output_mode=SearchOutputMode.LIST,
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


def test_cmd_parse_resolves_latest_title_substring_across_ecosystems(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Parse-mode resolution by latest title substring should work for non-Claude native title shapes too."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    paths = _build_supported_session_space(temp_home)

    cmd_rename(str(paths["codex"]), "cross-ecosystem-current-title-token")
    capsys.readouterr()

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        "current-title-token",
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert (
        "history_path: ~/.codex/sessions/2026/04/11/"
        "rollout-2026-04-11T10-11-09-019d7b61-53d7-7891-9033-ad646f9d2ce7.jsonl"
    ) in captured.out, (
        "Expected latest-title substring resolution to work for Codex native thread names too. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "cross-ecosystem-current-title-token" in captured.out, (
        "Expected metadata to surface the current resolved title after name-based resolution. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_search_matches_only_latest_custom_title_across_ecosystems(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Search should acknowledge only the latest title, even across native provider title shapes."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    paths = _build_supported_session_space(temp_home)

    cmd_rename(str(paths["pi"]), "historic-title-token")
    cmd_rename(str(paths["pi"]), "xyzzy-current-title-token")

    with pytest.raises(SystemExit) as old_exc_info:
        cmd_search(
            "historic-title-token",
            ConversationFlags(
                color="never",
                paging=False,
                message_selection=MessageSelection.NO_ASSISTANT,
            ),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    old_captured = capsys.readouterr()
    assert old_exc_info.value.code == 1, (
        "Expected search not to acknowledge renamed-away historical titles. "
        f"Got exit code: {old_exc_info.value.code}\nstdout:\n{old_captured.out}\nstderr:\n{old_captured.err}"
    )

    with pytest.raises(SystemExit) as current_exc_info:
        cmd_search(
            "current-title-token",
            ConversationFlags(
                color="never",
                paging=False,
                message_selection=MessageSelection.NO_ASSISTANT,
            ),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    current_captured = capsys.readouterr()
    assert current_exc_info.value.code == 0, (
        "Expected search to find the session via its latest title substring. "
        f"Got exit code: {current_exc_info.value.code}\nstdout:\n{current_captured.out}\nstderr:\n{current_captured.err}"
    )
    assert "pi" in current_captured.out.lower(), (
        f"Expected PI session path in output. Got stdout:\n{current_captured.out}"
    )
    assert "historic-title-token" not in current_captured.out, (
        "Expected search output not to acknowledge the historical title once a newer title exists. "
        f"Got stdout:\n{current_captured.out}"
    )


def test_cmd_search_only_id_prints_plain_session_id(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--only-id` should emit just the matching session identifier."""
    temp_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    _build_supported_session_space(temp_home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "codex-search-token",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 0, (
        "Expected `search --only-id` to exit successfully when a Codex session matches. "
        f"Got exit code: {exc_info.value.code}\nstdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert captured.out.strip() == "019d7b61-53d7-7891-9033-ad646f9d2ce7", (
        "Expected `--only-id` to print only the matching session id, with no "
        f"metadata or content. Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "history_path:" not in captured.out, (
        f"Expected `--only-id` to suppress search metadata. Got stdout:\n{captured.out}"
    )
