#!/usr/bin/env python3
"""Tests for `--provider` (and other pool-filter) wiring through PoolFilter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import cli
from chats.commands import _try_resolve_conversation_file, cmd_search
from chats.model import ConversationFlags, SearchOutputMode
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
# Integration: cmd_search with PoolFilter(provider=...)
# ---------------------------------------------------------------------------


def test_provider_filter_claude_includes_only_claude(tmp_path, monkeypatch, capsys):
    """With PoolFilter(provider='claude'), only Claude sessions are returned."""
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            NEEDLE,
            FLAGS,
            PoolFilter(provider="claude"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        f"Expected exit 0 (found match), got {exc_info.value.code}"
    )
    out = capsys.readouterr().out
    assert "provider: claude" in out, (
        f"Expected 'provider: claude' in output.\nstdout:\n{out}"
    )
    assert "provider: pi" not in out, (
        f"Expected no 'provider: pi' when filtering for claude.\nstdout:\n{out}"
    )
    assert "provider: codex" not in out, (
        f"Expected no 'provider: codex' when filtering for claude.\nstdout:\n{out}"
    )


def test_provider_filter_pi_includes_only_pi(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            NEEDLE,
            FLAGS,
            PoolFilter(provider="pi"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        f"Expected exit 0 (found match), got {exc_info.value.code}"
    )
    out = capsys.readouterr().out
    assert "provider: pi" in out, f"Expected 'provider: pi' in output.\nstdout:\n{out}"
    assert "provider: claude" not in out, f"Got unexpected claude.\nstdout:\n{out}"
    assert "provider: codex" not in out, f"Got unexpected codex.\nstdout:\n{out}"


def test_provider_filter_codex_includes_only_codex(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            NEEDLE,
            FLAGS,
            PoolFilter(provider="codex"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        f"Expected exit 0 (found match), got {exc_info.value.code}"
    )
    out = capsys.readouterr().out
    assert "provider: codex" in out, f"Expected codex in output.\nstdout:\n{out}"
    assert "provider: claude" not in out, f"Got unexpected claude.\nstdout:\n{out}"
    assert "provider: pi" not in out, f"Got unexpected pi.\nstdout:\n{out}"


def test_provider_filter_no_match_exits_1(tmp_path, monkeypatch):
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            NEEDLE,
            FLAGS,
            PoolFilter(provider="codex"),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 1, (
        f"Expected exit 1 (no match after provider filter), got {exc_info.value.code}"
    )


def test_provider_filter_none_includes_all(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    _write_claude_session(home / ".claude" / "projects" / "proj" / "s.jsonl", NEEDLE)
    _write_pi_session(home / ".pi" / "agent" / "sessions" / "s.jsonl", NEEDLE)
    _write_codex_session(home / ".codex" / "sessions" / "rollout-s.jsonl", NEEDLE)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            NEEDLE,
            FLAGS,
            PoolFilter(),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, f"Expected exit 0, got {exc_info.value.code}"
    out = capsys.readouterr().out
    assert "provider: claude" in out, (
        f"Expected claude in unfiltered search.\nstdout:\n{out}"
    )
    assert "provider: pi" in out, f"Expected pi in unfiltered search.\nstdout:\n{out}"
    assert "provider: codex" in out, (
        f"Expected codex in unfiltered search.\nstdout:\n{out}"
    )


# ---------------------------------------------------------------------------
# CLI seam: -p / --provider args reach cmd_search via PoolFilter
# ---------------------------------------------------------------------------


def _make_fake_cmd_search(captured: dict):
    def fake_cmd_search(
        pattern_arg,
        flags,
        pool_filter=None,
        *,
        output_mode=SearchOutputMode.MATCHES,
        output_format="xml",
        emit_metadata=True,
    ):
        captured["pool_filter"] = pool_filter

    return fake_cmd_search


def test_cli_short_provider_flag(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "-p", "claude", "needle"])
    cli.main()
    pf = captured.get("pool_filter")
    assert pf == PoolFilter(provider="claude"), (
        f"Expected PoolFilter(provider='claude'), got {pf!r}"
    )


def test_cli_long_provider_flag(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(
        cli.sys, "argv", ["ch", "search", "--provider", "pi", "needle"]
    )
    cli.main()
    pf = captured.get("pool_filter")
    assert pf == PoolFilter(provider="pi"), (
        f"Expected PoolFilter(provider='pi'), got {pf!r}"
    )


def test_cli_provider_codex(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "-p", "codex", "needle"])
    cli.main()
    pf = captured.get("pool_filter")
    assert pf == PoolFilter(provider="codex"), (
        f"Expected PoolFilter(provider='codex'), got {pf!r}"
    )


def test_cli_no_provider_flag_defaults_to_empty(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(cli, "cmd_search", _make_fake_cmd_search(captured))
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "needle"])
    cli.main()
    pf = captured.get("pool_filter")
    assert pf == PoolFilter(), f"Expected empty PoolFilter, got {pf!r}"
    assert pf is not None and pf.is_empty(), (
        f"Expected pool_filter to be empty, got {pf!r}"
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


def test_search_dir_filter_requires_exact_cwd_match(tmp_path, monkeypatch, capsys):
    """Search `--dir` should exclude child-directory sessions that only share a parent."""
    home = tmp_path / "home"
    target_dir = tmp_path / "target_proj"
    child_dir = target_dir / "nested" / "child"
    target_dir.mkdir(parents=True)
    child_dir.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    exact_path = home / ".claude" / "projects" / "proj" / "exact.jsonl"
    child_path = home / ".claude" / "projects" / "proj" / "child.jsonl"
    _write_claude_session(exact_path, "exact-dir-needle")
    _write_claude_session(child_path, "child-dir-needle")

    exact_payload = json.loads(exact_path.read_text().strip())
    exact_payload["cwd"] = str(target_dir)
    exact_payload["message"]["content"] = "shared-dir-search-needle exact"
    exact_path.write_text(json.dumps(exact_payload) + "\n")

    child_payload = json.loads(child_path.read_text().strip())
    child_payload["cwd"] = str(child_dir)
    child_payload["message"]["content"] = "shared-dir-search-needle child"
    child_path.write_text(json.dumps(child_payload) + "\n")

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "shared-dir-search-needle",
            FLAGS,
            PoolFilter(dir=str(target_dir)),
            output_mode=SearchOutputMode.LIST,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        f"Expected exit 0 when the exact cwd matches. Got {exc_info.value.code}"
    )
    out = capsys.readouterr().out
    assert "shared-dir-search-needle exact" not in out, (
        "List mode should not print message bodies; this assert guards the test shape."
    )
    assert "exact.jsonl" in out, (
        f"Expected the exact-cwd session to match --dir={target_dir!s}.\nstdout:\n{out}"
    )
    assert "child.jsonl" not in out, (
        f"Expected child-directory sessions to be excluded by exact-dir matching.\nstdout:\n{out}"
    )
