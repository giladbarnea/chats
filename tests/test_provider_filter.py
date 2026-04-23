#!/usr/bin/env python3
"""Tests for `ccc search -p/--provider` filtering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conversations import cli
from conversations.commands import cmd_search
from conversations.model import ConversationFlags


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
        }) + "\n"
    )


def _write_pi_session(path: Path, needle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session", "id": "abc"}) + "\n"
        + json.dumps({
            "type": "message",
            "timestamp": "2025-01-01T00:00:00Z",
            "message": {"role": "user", "content": [{"type": "text", "text": needle}]},
        }) + "\n"
    )


def _write_codex_session(path: Path, needle: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}}) + "\n"
        + json.dumps({
            "type": "response_item",
            "timestamp": "2025-01-01T00:00:00Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": needle}],
            },
        }) + "\n"
    )


FLAGS = ConversationFlags(color="never", paging=False)
NEEDLE = "provider_filter_test_needle_xyzzy"


# ---------------------------------------------------------------------------
# Integration: cmd_search with provider_filter
# ---------------------------------------------------------------------------

def test_provider_filter_claude_includes_only_claude(tmp_path, monkeypatch, capsys):
    """With provider_filter='claude', only Claude sessions are returned."""
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(NEEDLE, FLAGS, list_only=True, emit_metadata=True, provider_filter="claude")

    assert exc_info.value.code == 0, f"Expected exit 0 (found match), got {exc_info.value.code}"
    out = capsys.readouterr().out
    assert "provider: claude" in out, f"Expected 'provider: claude' in output.\nstdout:\n{out}"
    assert "provider: pi" not in out, f"Expected no 'provider: pi' when filtering for claude.\nstdout:\n{out}"
    assert "provider: codex" not in out, f"Expected no 'provider: codex' when filtering for claude.\nstdout:\n{out}"


def test_provider_filter_pi_includes_only_pi(tmp_path, monkeypatch, capsys):
    """With provider_filter='pi', only PI sessions are returned."""
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(NEEDLE, FLAGS, list_only=True, emit_metadata=True, provider_filter="pi")

    assert exc_info.value.code == 0, f"Expected exit 0 (found match), got {exc_info.value.code}"
    out = capsys.readouterr().out
    assert "provider: pi" in out, f"Expected 'provider: pi' in output.\nstdout:\n{out}"
    assert "provider: claude" not in out, f"Expected no 'provider: claude' when filtering for pi.\nstdout:\n{out}"
    assert "provider: codex" not in out, f"Expected no 'provider: codex' when filtering for pi.\nstdout:\n{out}"


def test_provider_filter_codex_includes_only_codex(tmp_path, monkeypatch, capsys):
    """With provider_filter='codex', only Codex sessions are returned."""
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(NEEDLE, FLAGS, list_only=True, emit_metadata=True, provider_filter="codex")

    assert exc_info.value.code == 0, f"Expected exit 0 (found match), got {exc_info.value.code}"
    out = capsys.readouterr().out
    assert "provider: codex" in out, f"Expected 'provider: codex' in output.\nstdout:\n{out}"
    assert "provider: claude" not in out, f"Expected no 'provider: claude' when filtering for codex.\nstdout:\n{out}"
    assert "provider: pi" not in out, f"Expected no 'provider: pi' when filtering for codex.\nstdout:\n{out}"


def test_provider_filter_no_match_exits_1(tmp_path, monkeypatch):
    """With provider_filter='codex' but only Claude sessions exist, exit code is 1."""
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(NEEDLE, FLAGS, list_only=True, emit_metadata=True, provider_filter="codex")

    assert exc_info.value.code == 1, (
        f"Expected exit 1 (no match after provider filter), got {exc_info.value.code}"
    )


def test_provider_filter_none_includes_all(tmp_path, monkeypatch, capsys):
    """With provider_filter=None (default), sessions from all providers are searched."""
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(NEEDLE, FLAGS, list_only=True, emit_metadata=True, provider_filter=None)

    assert exc_info.value.code == 0, f"Expected exit 0 (found matches), got {exc_info.value.code}"
    out = capsys.readouterr().out
    assert "provider: claude" in out, f"Expected claude in unfiltered search.\nstdout:\n{out}"
    assert "provider: pi" in out, f"Expected pi in unfiltered search.\nstdout:\n{out}"
    assert "provider: codex" in out, f"Expected codex in unfiltered search.\nstdout:\n{out}"


# ---------------------------------------------------------------------------
# CLI seam: -p / --provider args reach cmd_search
# ---------------------------------------------------------------------------

def _make_fake_cmd_search(captured: dict):
    def fake_cmd_search(
        pattern_arg,
        flags,
        list_only,
        only_id=False,
        dir_filter=None,
        mafter=None,
        cafter=None,
        *,
        emit_metadata=True,
        provider_filter=None,
    ):
        captured["provider_filter"] = provider_filter

    return fake_cmd_search


def test_cli_short_provider_flag(monkeypatch):
    """`ccc search -p claude pattern` passes provider_filter='claude' to cmd_search."""
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "search", "-p", "claude", "needle"])
    cli.main()
    assert captured.get("provider_filter") == "claude", (
        f"Expected provider_filter='claude', got {captured.get('provider_filter')!r}"
    )


def test_cli_long_provider_flag(monkeypatch):
    """`ccc search --provider pi pattern` passes provider_filter='pi' to cmd_search."""
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "search", "--provider", "pi", "needle"])
    cli.main()
    assert captured.get("provider_filter") == "pi", (
        f"Expected provider_filter='pi', got {captured.get('provider_filter')!r}"
    )


def test_cli_provider_codex(monkeypatch):
    """`ccc search -p codex pattern` passes provider_filter='codex' to cmd_search."""
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "search", "-p", "codex", "needle"])
    cli.main()
    assert captured.get("provider_filter") == "codex", (
        f"Expected provider_filter='codex', got {captured.get('provider_filter')!r}"
    )


def test_cli_no_provider_flag_defaults_to_none(monkeypatch):
    """`ccc search pattern` (no -p) passes provider_filter=None to cmd_search."""
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "search", "needle"])
    cli.main()
    assert captured.get("provider_filter") is None, (
        f"Expected provider_filter=None when -p is omitted, got {captured.get('provider_filter')!r}"
    )


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
        provider_filter=None,
        output_mode=None,
    ):
        captured["input_arg"] = input_arg
        captured["provider_filter"] = provider_filter

    return fake_cmd_parse


def test_parse_cli_provider_filter_reaches_cmd_parse_for_recent_index(monkeypatch):
    """`ccc -p codex -1` passes provider_filter='codex' to parse."""
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_parse", _make_fake_cmd_parse(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "-p", "codex", "-1"])
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)

    cli.main()

    assert captured.get("input_arg") == "-1", (
        f"Expected '-1' to remain the parse input, got {captured.get('input_arg')!r}"
    )
    assert captured.get("provider_filter") == "codex", (
        f"Expected provider_filter='codex', got {captured.get('provider_filter')!r}"
    )


def test_parse_cli_provider_filter_warns_and_ignores_session_id(monkeypatch, capsys):
    """`ccc -p codex session-id` should warn and keep session-id resolution provider-neutral."""
    captured: dict = {}
    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    monkeypatch.setattr(cli, "cmd_parse", _make_fake_cmd_parse(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "-p", "codex", session_id])

    cli.main()

    stderr = capsys.readouterr().err
    assert captured.get("input_arg") == session_id, (
        f"Expected parse input to stay as the session id, got {captured.get('input_arg')!r}"
    )
    assert captured.get("provider_filter") is None, (
        f"Expected provider_filter to be ignored for session ids, got {captured.get('provider_filter')!r}"
    )
    assert "Warning:" in stderr and "--provider" in stderr and "recent index" in stderr, (
        "Expected a warning explaining that --provider only applies to recent index inputs. "
        f"Got stderr:\n{stderr}"
    )
