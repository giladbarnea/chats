#!/usr/bin/env python3
"""Tests for `--provider` (and other pool-filter) wiring through PoolFilter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import cli
from chats.commands import _try_resolve_conversation_file
from chats.model import ConversationFlags
from chats.pool_filter import PoolFilter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_claude_session(path: Path, needle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/proj",
            "message": {"role": "user", "content": needle},
        })
        + "\n"
    )


def _write_pi_session(path: Path, needle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session", "id": "abc"})
        + "\n"
        + json.dumps({
            "type": "message",
            "timestamp": "2025-01-01T00:00:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": needle}]},
        })
        + "\n"
    )


def _write_codex_session(path: Path, needle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}})
        + "\n"
        + json.dumps({
            "type": "response_item",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": needle}],
            },
        })
        + "\n"
    )


FLAGS = ConversationFlags(color="never", paging=False)
NEEDLE = "provider_filter_test_needle_xyzzy"


# ---------------------------------------------------------------------------
# CLI seam: parse -p / --provider applies only to recent index inputs
# ---------------------------------------------------------------------------


def _make_fake_cmd_parse(captured: dict):
    def fake_cmd_parse(
        flags,
        input_arg,
        slice_str,
        output_file,
        *,
        output_format="xml",
        emit_metadata=True,
        pool_filter=None,
        output_mode=None,
    ):
        captured["input_arg"] = input_arg
        captured["pool_filter"] = pool_filter

    return fake_cmd_parse


def test_parse_cli_provider_filter_reaches_cmd_parse_for_recent_index(monkeypatch):
    """`ch -p codex -1` passes PoolFilter(provider='codex') to parse."""
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_parse", _make_fake_cmd_parse(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ch", "-p", "codex", "-1"])
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    cli.main()

    assert captured.get("input_arg") == "-1", (
        f"Expected '-1' to remain the parse input, got {captured.get('input_arg')!r}"
    )
    pf = captured.get("pool_filter")
    assert pf == PoolFilter(provider="codex"), (
        f"Expected PoolFilter(provider='codex'), got {pf!r}"
    )


def test_parse_cli_provider_filter_warns_and_ignores_session_id(monkeypatch, capsys):
    """`ch -p codex session-id` should warn and disable the pool filter."""
    captured: dict = {}
    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    monkeypatch.setattr(cli, "cmd_parse", _make_fake_cmd_parse(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ch", "-p", "codex", session_id])

    cli.main()

    stderr = capsys.readouterr().err
    assert captured.get("input_arg") == session_id, (
        f"Expected parse input to stay as the session id, got {captured.get('input_arg')!r}"
    )
    pf = captured.get("pool_filter")
    assert pf == PoolFilter(), (
        f"Expected pool filter to be ignored for session ids, got {pf!r}"
    )
    assert (
        "Warning:" in stderr and "--provider" in stderr and "recent index" in stderr
    ), (
        "Expected a warning explaining that pool filters only apply to recent index inputs. "
        f"Got stderr:\n{stderr}"
    )


# ---------------------------------------------------------------------------
# Parse-index resolution: pool filters narrow the candidate set for `-N`
# ---------------------------------------------------------------------------


def test_parse_index_provider_filter_narrows_candidate_pool(tmp_path, monkeypatch):
    """`-1` with provider=codex resolves to the most recent codex session, skipping newer claude/pi ones."""
    home = tmp_path / "home"
    claude_path = home / ".claude" / "projects" / "proj" / "c.jsonl"
    pi_path = home / ".pi" / "agent" / "sessions" / "p.jsonl"
    codex_path = home / ".codex" / "sessions" / "rollout-x.jsonl"
    _write_claude_session(claude_path, NEEDLE)
    _write_pi_session(pi_path, NEEDLE)
    _write_codex_session(codex_path, NEEDLE)
    # Make claude newest, codex oldest — so `-1` without filter would pick claude.
    import os

    os.utime(codex_path, (1_700_000_000, 1_700_000_000))
    os.utime(pi_path, (1_700_000_500, 1_700_000_500))
    os.utime(claude_path, (1_700_001_000, 1_700_001_000))
    monkeypatch.setattr(Path, "home", lambda: home)

    resolved_codex, _ = _try_resolve_conversation_file(
        "-1", pool_filter=PoolFilter(provider="codex")
    )
    assert resolved_codex == codex_path, (
        f"Expected `-1` with provider=codex to resolve to the codex session. Got: {resolved_codex!r}"
    )

    resolved_pi, _ = _try_resolve_conversation_file(
        "-1", pool_filter=PoolFilter(provider="pi")
    )
    assert resolved_pi == pi_path, (
        f"Expected `-1` with provider=pi to resolve to the pi session. Got: {resolved_pi!r}"
    )

    resolved_claude, _ = _try_resolve_conversation_file(
        "-1", pool_filter=PoolFilter(provider="claude")
    )
    assert resolved_claude == claude_path, (
        f"Expected `-1` with provider=claude to resolve to the claude session. Got: {resolved_claude!r}"
    )


def test_parse_index_dir_filter_requires_exact_cwd_match(tmp_path, monkeypatch):
    """`-1` with --dir should exclude newer child directories and match only the exact cwd."""
    home = tmp_path / "home"
    target_dir = tmp_path / "target_proj"
    child_dir = target_dir / "nested" / "child"
    target_dir.mkdir(parents=True)
    child_dir.mkdir(parents=True)

    older_path = home / ".claude" / "projects" / "a" / "older.jsonl"
    newer_path = home / ".claude" / "projects" / "b" / "newer.jsonl"
    older_path.parent.mkdir(parents=True, exist_ok=True)
    newer_path.parent.mkdir(parents=True, exist_ok=True)
    older_path.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": str(target_dir),
            "message": {"role": "user", "content": "hello from exact dir"},
        })
        + "\n"
    )
    newer_path.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2025-02-01T00:00:00Z",
            "cwd": str(child_dir),
            "message": {"role": "user", "content": "hello from child dir"},
        })
        + "\n"
    )
    import os

    os.utime(older_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_path, (1_700_001_000, 1_700_001_000))
    monkeypatch.setattr(Path, "home", lambda: home)

    resolved, _ = _try_resolve_conversation_file(
        "-1", pool_filter=PoolFilter(dir=str(target_dir))
    )
    assert resolved == older_path, (
        f"Expected `-1` with --dir={target_dir!s} to ignore newer sessions from child directories "
        f"and resolve to the exact-cwd match. Got: {resolved!r}"
    )
