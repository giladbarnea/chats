#!/usr/bin/env python3
"""Tests for parse-mode `--only-metadata` and `--only-id` output modes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conversations import cli
from conversations.commands import cmd_parse
from conversations.model import ConversationFlags, ParseOutputMode


def _write_claude_session(path: Path) -> None:
    """Write a minimal Claude-format session fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "type": "summary",
            "summary": "Parse output mode fixture",
            "leafUuid": "fixture-leaf",
        },
        {
            "type": "user",
            "sessionId": path.stem,
            "cwd": "/tmp/parse-output-modes",
            "timestamp": "2026-04-23T09:00:00.000Z",
            "message": {"role": "user", "content": "first prompt"},
            "uuid": "fixture-user-1",
        },
        {
            "type": "assistant",
            "sessionId": path.stem,
            "cwd": "/tmp/parse-output-modes",
            "timestamp": "2026-04-23T09:00:01.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "first response"}],
            },
            "uuid": "fixture-assistant-1",
        },
        {
            "type": "user",
            "sessionId": path.stem,
            "cwd": "/tmp/parse-output-modes",
            "timestamp": "2026-04-23T09:00:02.000Z",
            "message": {"role": "user", "content": "last prompt"},
            "uuid": "fixture-user-2",
        },
    ]
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_parse_cli_only_id_forces_plain_output(monkeypatch) -> None:
    """`ccc -ll` should force plain output and pass `only_id=True` into parse."""
    captured: dict[str, object] = {}

    def fake_cmd_parse(
        flags,
        input_arg,
        slice_str,
        output_file,
        *,
        output_format="xml",
        emit_metadata=True,
        pool_filter=None,
        output_mode=ParseOutputMode.FULL,
    ) -> None:
        captured["flags"] = flags
        captured["input_arg"] = input_arg
        captured["output_mode"] = output_mode

    session_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    monkeypatch.setattr(cli, "cmd_parse", fake_cmd_parse)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["ccc", "-ll", "--paging", "--color", "always", session_id],
    )

    cli.main()

    flags = captured.get("flags")
    assert flags is not None, (
        "Expected parse CLI seam to reach cmd_parse with built flags."
    )
    assert captured.get("input_arg") == session_id, (
        "Expected parse input to pass through unchanged. "
        f"Got: {captured.get('input_arg')!r}"
    )
    assert captured.get("output_mode") == ParseOutputMode.ONLY_ID, (
        "Expected `-ll` to reach parse as `ParseOutputMode.ONLY_ID`. "
        f"Got: {captured.get('output_mode')!r}"
    )
    assert flags.color is False, (
        "Expected parse `-ll` to force plain output even when `--color always` was passed."
    )
    assert flags.paging is False, (
        "Expected parse `-ll` to force paging off even when `--paging` was passed."
    )


def test_parse_cli_only_metadata_reaches_cmd_parse(monkeypatch) -> None:
    """`ccc -l` should enter parse metadata-only mode."""
    captured: dict[str, object] = {}

    def fake_cmd_parse(
        flags,
        input_arg,
        slice_str,
        output_file,
        *,
        output_format="xml",
        emit_metadata=True,
        pool_filter=None,
        output_mode=ParseOutputMode.FULL,
    ) -> None:
        captured["input_arg"] = input_arg
        captured["output_mode"] = output_mode

    session_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    monkeypatch.setattr(cli, "cmd_parse", fake_cmd_parse)
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "-l", session_id])

    cli.main()

    assert captured.get("input_arg") == session_id, (
        "Expected parse input to pass through unchanged. "
        f"Got: {captured.get('input_arg')!r}"
    )
    assert captured.get("output_mode") == ParseOutputMode.ONLY_METADATA, (
        "Expected `-l` to reach parse as `ParseOutputMode.ONLY_METADATA`. "
        f"Got: {captured.get('output_mode')!r}"
    )


def test_cmd_parse_only_id_prints_plain_session_id(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`cmd_parse(..., only_id=True)` should emit only the resolved session id."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session = (
        home
        / ".claude"
        / "projects"
        / "demo-project"
        / "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl"
    )
    _write_claude_session(session)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
        output_mode=ParseOutputMode.ONLY_ID,
    )

    captured = capsys.readouterr()
    assert captured.out.strip() == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", (
        "Expected parse id-only mode to print only the resolved session id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "history_path:" not in captured.out, (
        f"Expected parse id-only mode to suppress metadata. Got stdout:\n{captured.out}"
    )
    assert (
        "first prompt" not in captured.out and "first response" not in captured.out
    ), (
        "Expected parse id-only mode to suppress rendered conversation content. "
        f"Got stdout:\n{captured.out}"
    )


def test_cmd_parse_only_metadata_hides_messages_and_respects_slice(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Metadata-only mode should emit frontmatter only, with post-slice message counts."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session = (
        home
        / ".claude"
        / "projects"
        / "demo-project"
        / "cccccccc-cccc-cccc-cccc-cccccccccccc.jsonl"
    )
    _write_claude_session(session)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session),
        slice_str="-1",
        output_file=None,
        output_format="xml",
        emit_metadata=True,
        output_mode=ParseOutputMode.ONLY_METADATA,
    )

    captured = capsys.readouterr()
    assert "session_id: cccccccc-cccc-cccc-cccc-cccccccccccc" in captured.out, (
        "Expected metadata-only mode to include the resolved session id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "history_path: ~/.claude/projects/demo-project/cccccccc-cccc-cccc-cccc-cccccccccccc.jsonl"
        in captured.out
    ), (
        "Expected metadata-only mode to include the session history path. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "messages: 1" in captured.out, (
        "Expected metadata-only mode to preserve parse's post-slice message count semantics. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "---" not in captured.out, (
        "Expected metadata-only mode to omit YAML frontmatter separators in list output. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert (
        "<user-message" not in captured.out
        and "<assistant-response" not in captured.out
    ), (
        "Expected metadata-only mode to suppress XML message wrappers. "
        f"Got stdout:\n{captured.out}"
    )
    assert (
        "first prompt" not in captured.out
        and "first response" not in captured.out
        and "last prompt" not in captured.out
    ), (
        "Expected metadata-only mode to suppress rendered message content. "
        f"Got stdout:\n{captured.out}"
    )


def test_cmd_parse_only_id_rejects_raw_content(capsys) -> None:
    """`--only-id` should fail for raw content with no stable session identity."""
    with pytest.raises(SystemExit) as exc_info:
        cmd_parse(
            ConversationFlags(color="never", paging=False),
            "raw pasted content",
            slice_str=None,
            output_file=None,
            output_format="xml",
            emit_metadata=True,
            output_mode=ParseOutputMode.ONLY_ID,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected id-only mode to exit 1 for raw non-file-backed input. "
        f"Got exit code: {exc_info.value.code!r}"
    )
    assert (
        "`--only-id` requires a resolved session or file-backed input" in captured.err
    ), (
        "Expected id-only mode to explain why raw input is unsupported. "
        f"Got stderr:\n{captured.err}"
    )
    assert captured.out == "", (
        "Expected id-only mode to avoid writing stdout on this error path. "
        f"Got stdout:\n{captured.out}"
    )


def test_cmd_parse_only_metadata_rejects_raw_content(capsys) -> None:
    """`--only-metadata` should fail for raw content with no stable session identity."""
    with pytest.raises(SystemExit) as exc_info:
        cmd_parse(
            ConversationFlags(color="never", paging=False),
            "raw pasted content",
            slice_str=None,
            output_file=None,
            output_format="xml",
            emit_metadata=True,
            output_mode=ParseOutputMode.ONLY_METADATA,
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1, (
        "Expected metadata-only mode to exit 1 for raw non-file-backed input. "
        f"Got exit code: {exc_info.value.code!r}"
    )
    assert (
        "`--only-metadata` requires a resolved session or file-backed input"
        in captured.err
    ), (
        "Expected metadata-only mode to explain why raw input is unsupported. "
        f"Got stderr:\n{captured.err}"
    )
    assert captured.out == "", (
        "Expected metadata-only mode to avoid writing stdout on this error path. "
        f"Got stdout:\n{captured.out}"
    )
