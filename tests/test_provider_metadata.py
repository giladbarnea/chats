#!/usr/bin/env python3
"""Tests for the `provider` metadata field across parse and search output."""

import json
import os
import shutil
from pathlib import Path

import pytest

from conversations import ConversationFlags, cmd_parse, cmd_search
from conversations.commands import _load_conversation_metadata
from conversations.model import ConversationMetadata


# ---------------------------------------------------------------------------
# Unit: ConversationMetadata carries provider
# ---------------------------------------------------------------------------

def test_conversation_metadata_has_provider_field():
    meta = ConversationMetadata(
        path=Path("/tmp/fake.jsonl"),
        ctime=None,
        mtime=None,
        provider="claude",
    )
    assert meta.provider == "claude", f"Expected provider='claude', got {meta.provider!r}"


# ---------------------------------------------------------------------------
# Unit: _load_conversation_metadata derives provider from adapter
# ---------------------------------------------------------------------------

def test_load_metadata_claude_provider(tmp_path, monkeypatch):
    """A file under ~/.claude/projects/ should have provider='claude'."""
    home = tmp_path / "home"
    projects = home / ".claude" / "projects" / "proj"
    projects.mkdir(parents=True)
    session = projects / "abc.jsonl"
    session.write_text(
        json.dumps({"type": "user", "timestamp": "2025-01-01T00:00:00Z",
                     "message": {"role": "user", "content": "hi"}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    meta = _load_conversation_metadata(session)
    assert meta.provider == "claude", f"Expected provider='claude', got {meta.provider!r}"


def test_load_metadata_pi_provider(tmp_path, monkeypatch):
    """A file under ~/.pi/agent/sessions/ should have provider='pi'."""
    home = tmp_path / "home"
    pi_dir = home / ".pi" / "agent" / "sessions"
    pi_dir.mkdir(parents=True)
    session = pi_dir / "sess.jsonl"
    session.write_text(
        json.dumps({"type": "session", "id": "abc"}) + "\n"
        + json.dumps({"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    meta = _load_conversation_metadata(session)
    assert meta.provider == "pi", f"Expected provider='pi', got {meta.provider!r}"


def test_load_metadata_codex_provider(tmp_path, monkeypatch):
    """A file under ~/.codex/sessions/ should have provider='codex'."""
    home = tmp_path / "home"
    codex_dir = home / ".codex" / "sessions"
    codex_dir.mkdir(parents=True)
    session = codex_dir / "rollout-abc.jsonl"
    session.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}}) + "\n"
        + json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user",
                      "content": [{"type": "input_text", "text": "hi"}]}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    meta = _load_conversation_metadata(session)
    assert meta.provider == "codex", f"Expected provider='codex', got {meta.provider!r}"


# ---------------------------------------------------------------------------
# Integration: cmd_parse emits provider in metadata frontmatter
# ---------------------------------------------------------------------------

def test_cmd_parse_emits_provider_claude(tmp_path, capsys, monkeypatch):
    home = tmp_path / "home"
    projects = home / ".claude" / "projects" / "proj"
    projects.mkdir(parents=True)
    session = projects / "session.jsonl"
    session.write_text(
        json.dumps({"type": "user", "timestamp": "2025-01-01T00:00:00Z",
                     "message": {"role": "user", "content": "hello"}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )
    captured = capsys.readouterr()
    assert "provider: claude" in captured.out, (
        f"Expected 'provider: claude' in metadata frontmatter.\nstdout:\n{captured.out}"
    )


def test_cmd_parse_emits_provider_pi(tmp_path, capsys, monkeypatch):
    home = tmp_path / "home"
    pi_dir = home / ".pi" / "agent" / "sessions"
    pi_dir.mkdir(parents=True)
    session = pi_dir / "1234_abc.jsonl"
    session.write_text(
        json.dumps({"type": "session", "id": "abc"}) + "\n"
        + json.dumps({"type": "message", "timestamp": "2025-01-01T00:00:00Z",
                       "message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )
    captured = capsys.readouterr()
    assert "provider: pi" in captured.out, (
        f"Expected 'provider: pi' in metadata frontmatter.\nstdout:\n{captured.out}"
    )


def test_cmd_parse_emits_provider_codex(tmp_path, capsys, monkeypatch):
    home = tmp_path / "home"
    codex_dir = home / ".codex" / "sessions"
    codex_dir.mkdir(parents=True)
    session = codex_dir / "rollout-abc.jsonl"
    session.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}}) + "\n"
        + json.dumps({"type": "response_item", "timestamp": "2025-01-01T00:00:00Z",
                       "payload": {"type": "message", "role": "user",
                                   "content": [{"type": "input_text", "text": "hi"}]}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)
    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )
    captured = capsys.readouterr()
    assert "provider: codex" in captured.out, (
        f"Expected 'provider: codex' in metadata frontmatter.\nstdout:\n{captured.out}"
    )


# ---------------------------------------------------------------------------
# Integration: cmd_search emits provider in metadata frontmatter
# ---------------------------------------------------------------------------

RENAME_FIXTURES_DIR = Path(__file__).parent / "data" / "rename_fixtures"


@pytest.fixture
def temp_claude_home(tmp_path, monkeypatch):
    """Create a temporary .claude directory structure and patch Path.home()."""
    temp_home = tmp_path / "home"
    temp_projects = temp_home / ".claude" / "projects"
    shutil.copytree(RENAME_FIXTURES_DIR / "projects", temp_projects)
    monkeypatch.setattr(Path, "home", lambda: temp_home)
    return temp_home


def test_cmd_search_emits_provider_claude(temp_claude_home, capsys):
    """Search results for a Claude session should include provider: claude."""
    project_dir = temp_claude_home / ".claude" / "projects" / "test-project"
    session = project_dir / "searchable.jsonl"
    session.write_text(
        json.dumps({"type": "user", "timestamp": "2025-01-01T00:00:00Z",
                     "cwd": "/tmp/proj",
                     "message": {"role": "user", "content": "unique_search_needle_claude"}}) + "\n"
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "unique_search_needle_claude",
            ConversationFlags(color="never", paging=False),
            list_only=True,
            emit_metadata=True,
        )
    assert exc_info.value.code == 0, f"Expected search to find a match; exit code: {exc_info.value.code}"
    captured = capsys.readouterr()
    assert "provider: claude" in captured.out, (
        f"Expected 'provider: claude' in search metadata.\nstdout:\n{captured.out}"
    )


def test_cmd_search_emits_provider_pi(tmp_path, capsys, monkeypatch):
    """Search results for a PI session should include provider: pi."""
    home = tmp_path / "home"
    pi_dir = home / ".pi" / "agent" / "sessions"
    pi_dir.mkdir(parents=True)
    session = pi_dir / "1234_abc.jsonl"
    session.write_text(
        json.dumps({"type": "session", "id": "abc"}) + "\n"
        + json.dumps({"type": "message", "timestamp": "2025-01-01T00:00:00Z",
                       "message": {"role": "user", "content": [{"type": "text", "text": "unique_search_needle_pi"}]}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "unique_search_needle_pi",
            ConversationFlags(color="never", paging=False),
            list_only=True,
            emit_metadata=True,
        )
    assert exc_info.value.code == 0, f"Expected search to find a match; exit code: {exc_info.value.code}"
    captured = capsys.readouterr()
    assert "provider: pi" in captured.out, (
        f"Expected 'provider: pi' in search metadata.\nstdout:\n{captured.out}"
    )


def test_cmd_search_emits_provider_codex(tmp_path, capsys, monkeypatch):
    """Search results for a Codex session should include provider: codex."""
    home = tmp_path / "home"
    codex_dir = home / ".codex" / "sessions"
    codex_dir.mkdir(parents=True)
    session = codex_dir / "rollout-abc.jsonl"
    session.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": "abc"}}) + "\n"
        + json.dumps({"type": "response_item", "timestamp": "2025-01-01T00:00:00Z",
                       "payload": {"type": "message", "role": "user",
                                   "content": [{"type": "input_text", "text": "unique_search_needle_codex"}]}}) + "\n"
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "unique_search_needle_codex",
            ConversationFlags(color="never", paging=False),
            list_only=True,
            emit_metadata=True,
        )
    assert exc_info.value.code == 0, f"Expected search to find a match; exit code: {exc_info.value.code}"
    captured = capsys.readouterr()
    assert "provider: codex" in captured.out, (
        f"Expected 'provider: codex' in search metadata.\nstdout:\n{captured.out}"
    )
