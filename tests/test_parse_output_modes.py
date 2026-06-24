#!/usr/bin/env python3
"""Tests for parse-mode `--only-metadata` and `--only-id` output modes."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from chats import cli
from chats.commands import cmd_parse
from chats.model import ConversationFlags, ParseOutputMode
import chats.commands.resolve as resolve_commands


def _claude_session_content(session_id: str) -> str:
    """Return a minimal Claude-format JSONL session fixture."""
    entries = [
        {
            "type": "summary",
            "summary": "Parse output mode fixture",
            "leafUuid": "fixture-leaf",
        },
        {
            "type": "user",
            "sessionId": session_id,
            "cwd": "/tmp/parse-output-modes",
            "timestamp": "2026-04-23T09:00:00.000Z",
            "message": {"role": "user", "content": "first prompt"},
            "uuid": "fixture-user-1",
        },
        {
            "type": "assistant",
            "sessionId": session_id,
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
            "sessionId": session_id,
            "cwd": "/tmp/parse-output-modes",
            "timestamp": "2026-04-23T09:00:02.000Z",
            "message": {"role": "user", "content": "last prompt"},
            "uuid": "fixture-user-2",
        },
    ]
    return "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries)


def _write_claude_session(path: Path) -> None:
    """Write a minimal Claude-format session fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_claude_session_content(path.stem), encoding="utf-8")


def test_cmd_parse_stdin_jsonl_content_skips_global_session_resolution(
    monkeypatch,
    capsys,
) -> None:
    """Clearly-JSONL stdin should parse directly instead of scanning the session pool."""
    content = _claude_session_content("stdin-content-session")
    monkeypatch.setattr(resolve_commands.sys, "stdin", io.StringIO(content))

    def fail_discover(*_args, **_kwargs):
        raise AssertionError(
            "Expected stdin JSONL content to bypass global SessionPool discovery."
        )

    monkeypatch.setattr(resolve_commands.SessionPool, "discover", fail_discover)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        None,
        slice_str="1",
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "first prompt" in captured.out, (
        "Expected stdin JSONL content to be parsed through the real parse path. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_explicit_multiline_jsonl_content_skips_identifier_resolution(
    monkeypatch,
    capsys,
) -> None:
    """Explicit multiline JSONL content should not be treated as a session identifier."""
    content = _claude_session_content("explicit-content-session")

    def fail_resolution(*_args, **_kwargs):
        raise AssertionError(
            "Expected explicit multiline JSONL content to bypass identifier resolution."
        )

    monkeypatch.setattr(
        resolve_commands,
        "_try_resolve_conversation_file",
        fail_resolution,
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        content,
        slice_str="2",
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "first response" in captured.out, (
        "Expected explicit multiline JSONL content to be parsed through the real parse path. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_explicit_one_line_jsonl_content_skips_identifier_resolution(
    monkeypatch,
    capsys,
) -> None:
    """An explicit one-line JSONL entry should parse as content, not an identifier."""
    content = json.dumps({
        "type": "user",
        "message": {"role": "user", "content": "one-line prompt"},
        "uuid": "one-line-user",
    })

    def fail_resolution(*_args, **_kwargs):
        raise AssertionError(
            "Expected explicit one-line JSONL content to bypass identifier resolution."
        )

    monkeypatch.setattr(
        resolve_commands,
        "_try_resolve_conversation_file",
        fail_resolution,
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        content,
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "one-line prompt" in captured.out, (
        "Expected explicit one-line JSONL content to be parsed through the real parse path. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_stdin_single_line_identifier_still_resolves(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """A piped one-line session id should keep the existing identifier-resolution behavior."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session = (
        home
        / ".claude"
        / "projects"
        / "demo-project"
        / "dddddddd-dddd-dddd-dddd-dddddddddddd.jsonl"
    )
    _write_claude_session(session)
    monkeypatch.setattr(resolve_commands.sys, "stdin", io.StringIO(session.stem + "\n"))

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        None,
        slice_str="1",
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "first prompt" in captured.out, (
        "Expected piped one-line identifiers to keep resolving as sessions. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_only_id_does_not_read_resolved_session_body(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Id-only parse should resolve identity without reading the session body."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session = (
        home
        / ".claude"
        / "projects"
        / "demo-project"
        / "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee.jsonl"
    )
    _write_claude_session(session)
    real_read_text = Path.read_text

    def fail_if_session_body_read(path: Path, *args, **kwargs):
        if path == session:
            raise AssertionError(
                "Expected parse --only-id to avoid reading resolved session content."
            )
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_session_body_read)

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
    assert captured.out.strip() == session.stem, (
        "Expected parse id-only mode to print only the resolved session id. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_parse_cli_only_id_forces_plain_output(monkeypatch) -> None:
    """`ch -ll` should force plain output and pass `only_id=True` into parse."""
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
        ["ch", "-ll", "--paging", "--color", "always", session_id],
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
    """`ch -l` should enter parse metadata-only mode."""
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
    monkeypatch.setattr(cli.sys, "argv", ["ch", "-l", session_id])

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
