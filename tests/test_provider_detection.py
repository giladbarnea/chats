#!/usr/bin/env python3
"""Provider selection for session files outside native storage paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import ConversationFlags, cmd_parse
from chats.model import ParseOutputMode
from chats.parsing import get_jsonl_session_adapter


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a test session path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_external_pi_session_is_detected_from_its_first_entry(
    tmp_path: Path,
    capsys,
) -> None:
    """A copied Pi session should parse without living under ~/.pi/."""
    session_path = tmp_path / "avidor" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "0f408325-0d79-4781-bdcd-9dccf4acc2d1",
                "timestamp": "2026-08-04T13:56:02.355Z",
                "cwd": "/opt/avidor/workdir",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": None,
                "timestamp": "2026-08-04T13:56:03.355Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "external Pi prompt"}],
                    "timestamp": 1785851763355,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "external Pi prompt" in captured.out, (
        "Expected the external Pi header signature to select the Pi parser. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_external_codex_session_is_detected_from_its_first_entry(
    tmp_path: Path,
    capsys,
) -> None:
    """A copied Codex session should parse without living under ~/.codex/."""
    session_path = tmp_path / "export" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-08-04T13:56:02.355Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexexternal1",
                    "cwd": "/opt/export/workdir",
                },
            },
            {
                "timestamp": "2026-08-04T13:56:03.355Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "external Codex prompt"}
                    ],
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "external Codex prompt" in captured.out, (
        "Expected the external Codex header signature to select the Codex parser. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_native_path_takes_precedence_over_first_entry_signature(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A recognized provider path should win over a conflicting content signature."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session_path = home / ".claude" / "projects" / "demo" / "session.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "pi-shaped-content",
                "timestamp": "2026-08-04T13:56:02.355Z",
                "cwd": "/tmp/demo",
            }
        ],
    )

    adapter = get_jsonl_session_adapter(session_path)

    assert adapter.name == "claude", (
        "Expected the recognized Claude path to override the conflicting Pi header. "
        f"Got provider: {adapter.name!r}"
    )


def test_pi_signature_requires_an_integer_version(tmp_path: Path) -> None:
    """A Pi-shaped header with a string version should remain unrecognized."""
    session_path = tmp_path / "pi-string-version" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [{"type": "session", "version": "3", "id": "not-an-exact-pi-header"}],
    )

    with pytest.raises(ValueError, match="Cannot determine JSONL session provider"):
        get_jsonl_session_adapter(session_path)


def test_unknown_external_jsonl_exits_instead_of_assuming_claude(
    tmp_path: Path,
    capsys,
) -> None:
    """An unrecognized path and first entry should fail without a Claude fallback."""
    session_path = tmp_path / "unknown" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "user",
                "sessionId": "external-claude-shaped-session",
                "message": {"role": "user", "content": "unknown provider prompt"},
            }
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        cmd_parse(
            ConversationFlags(color="never", paging=False),
            str(session_path),
            slice_str=None,
            output_file=None,
            output_format="xml",
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exit_info.value.code == 1, (
        "Expected an unknown JSONL provider to exit with status 1. "
        f"Got: {exit_info.value.code!r}"
    )
    assert "Cannot determine JSONL session provider" in captured.err, (
        "Expected the error to explain that provider resolution failed. "
        f"Got stderr:\n{captured.err}"
    )
    assert captured.out == "", (
        "Expected unknown JSONL input not to produce transcript output. "
        f"Got stdout:\n{captured.out}"
    )


def test_unknown_external_jsonl_only_id_exits_cleanly(
    tmp_path: Path,
    capsys,
) -> None:
    """Provider rejection should also apply before the id-only fast path returns."""
    session_path = tmp_path / "unknown-id" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [{"type": "user", "sessionId": "unknown", "message": {"role": "user"}}],
    )

    with pytest.raises(SystemExit) as exit_info:
        cmd_parse(
            ConversationFlags(color="never", paging=False),
            str(session_path),
            slice_str=None,
            output_file=None,
            output_format="xml",
            emit_metadata=False,
            output_mode=ParseOutputMode.ONLY_ID,
        )

    captured = capsys.readouterr()
    assert exit_info.value.code == 1, (
        f"Expected unknown id-only JSONL to exit 1. Got: {exit_info.value.code!r}"
    )
    assert "Cannot determine JSONL session provider" in captured.err, (
        "Expected id-only provider rejection without a traceback. "
        f"Got stderr:\n{captured.err}"
    )
