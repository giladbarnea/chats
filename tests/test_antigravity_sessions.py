from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from chats import ConversationFlags, SessionPool, ToolFilter, cmd_parse


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _utc_to_local_display(utc_iso: str) -> str:
    timestamp = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    return timestamp.astimezone().replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")



def _antigravity_log_path(home: Path, session_id: str, filename: str) -> Path:
    return (
        home
        / ".gemini"
        / "antigravity-cli"
        / "brain"
        / session_id
        / ".system_generated"
        / "logs"
        / filename
    )


def test_cmd_parse_renders_antigravity_user_request_and_assistant_response(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    session_id = "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
    transcript_path = _antigravity_log_path(home, session_id, "transcript_full.jsonl")
    _write_jsonl(
        transcript_path,
        [
            {
                "step_index": 1,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "status": "DONE",
                "created_at": "2026-06-01T10:00:00Z",
                "content": "<USER_REQUEST>\nBuild the Antigravity adapter.\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\nnoise\n</ADDITIONAL_METADATA>",
            },
            {
                "step_index": 2,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "created_at": "2026-06-01T10:00:03Z",
                "content": "I will add focused support.",
            },
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(transcript_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert "provider: antigravitycli" in captured.err, (
        f"Expected Antigravity provider metadata. stderr:\n{captured.err}"
    )
    assert f"session_id: {session_id}" in captured.err, (
        f"Expected brain-directory session id in metadata. stderr:\n{captured.err}"
    )
    assert "Build the Antigravity adapter." in captured.out, (
        f"Expected USER_REQUEST content to render. stdout:\n{captured.out}"
    )
    assert "I will add focused support." in captured.out, (
        f"Expected PLANNER_RESPONSE content to render. stdout:\n{captured.out}"
    )
    assert "ADDITIONAL_METADATA" not in captured.out, (
        f"Expected Antigravity user metadata wrapper to stay hidden. stdout:\n{captured.out}"
    )


def test_cmd_parse_renders_antigravity_thinking_and_tool_roundtrip(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    session_id = "eeeeeeee-1111-2222-3333-ffffffffffff"
    transcript_path = _antigravity_log_path(home, session_id, "transcript_full.jsonl")
    _write_jsonl(
        transcript_path,
        [
            {
                "step_index": 1,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "created_at": "2026-06-01T10:00:00Z",
                "thinking": "Need to inspect the tree.",
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {"Command": "pwd", "WaitMsBeforeAsync": 500},
                    }
                ],
            },
            {
                "step_index": 2,
                "source": "MODEL",
                "type": "RUN_COMMAND",
                "status": "ERROR",
                "created_at": "2026-06-01T10:00:01Z",
                "content": "command failed loudly",
            },
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    cmd_parse(
        ConversationFlags(
            show_thinking=True,
            show_tools=True,
            color="never",
            paging=False,
        ),
        str(transcript_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "Need to inspect the tree." in captured.out, (
        f"Expected Antigravity thinking to render. stdout:\n{captured.out}"
    )
    assert '<tool-input name="Bash"' in captured.out, (
        f"Expected run_command to normalize to Bash tool input. stdout:\n{captured.out}"
    )
    assert "pwd" in captured.out, (
        f"Expected run_command command text to render. stdout:\n{captured.out}"
    )
    assert '<tool-output name="Bash"' in captured.out, (
        f"Expected following RUN_COMMAND record to pair with Bash tool output. stdout:\n{captured.out}"
    )
    assert 'is_error="true"' in captured.out, (
        f"Expected RUN_COMMAND status=ERROR to render as error tool output. stdout:\n{captured.out}"
    )
    assert "command failed loudly" in captured.out, (
        f"Expected RUN_COMMAND content to render. stdout:\n{captured.out}"
    )


def test_cmd_parse_filters_orphan_antigravity_result_by_record_type(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    session_id = "dddddddd-1111-2222-3333-eeeeeeeeeeee"
    transcript_path = _antigravity_log_path(home, session_id, "transcript_full.jsonl")
    _write_jsonl(
        transcript_path,
        [
            {
                "step_index": 1,
                "source": "MODEL",
                "type": "RUN_COMMAND",
                "status": "DONE",
                "created_at": "2026-06-01T10:00:01Z",
                "content": "orphan Antigravity result content",
            }
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    cmd_parse(
        ConversationFlags(
            show_tools=[ToolFilter(name="Bash")],
            color="never",
            paging=False,
        ),
        str(transcript_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert '<tool-output name="Bash"' in captured.out, (
        "Expected `-t Bash` to include an orphan RUN_COMMAND result. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )
    assert "orphan Antigravity result content" in captured.out, (
        "Expected the filtered orphan Antigravity result to preserve its content. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_cmd_parse_metadata_uses_antigravity_created_at_timestamps(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    session_id = "99999999-1111-2222-3333-888888888888"
    transcript_path = _antigravity_log_path(home, session_id, "transcript_full.jsonl")
    _write_jsonl(
        transcript_path,
        [
            {
                "step_index": 1,
                "type": "USER_INPUT",
                "created_at": "2026-06-01T10:00:00Z",
                "content": "<USER_REQUEST>hello</USER_REQUEST>",
            },
            {
                "step_index": 2,
                "type": "PLANNER_RESPONSE",
                "created_at": "2026-06-01T11:30:00Z",
                "content": "hi",
            },
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(transcript_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    expected_created = _utc_to_local_display("2026-06-01T10:00:00Z")
    expected_modified = _utc_to_local_display("2026-06-01T11:30:00Z")
    assert f'created: "{expected_created}"' in captured.err, (
        f"Expected first Antigravity created_at to drive local-time metadata. stderr:\n{captured.err}"
    )
    assert f'modified: "{expected_modified}"' in captured.err, (
        f"Expected last Antigravity created_at to drive local-time metadata. stderr:\n{captured.err}"
    )


def test_cmd_parse_resolves_antigravity_session_id_to_full_transcript(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    session_id = "77777777-1111-2222-3333-666666666666"
    short_path = _antigravity_log_path(home, session_id, "transcript.jsonl")
    full_path = _antigravity_log_path(home, session_id, "transcript_full.jsonl")
    _write_jsonl(
        short_path,
        [
            {
                "type": "USER_INPUT",
                "created_at": "2026-06-01T10:00:00Z",
                "content": "<USER_REQUEST>short transcript loser</USER_REQUEST>",
            }
        ],
    )
    _write_jsonl(
        full_path,
        [
            {
                "type": "USER_INPUT",
                "created_at": "2026-06-01T10:00:00Z",
                "content": "<USER_REQUEST>full transcript winner</USER_REQUEST>",
            }
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        session_id,
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert "full transcript winner" in captured.out, (
        f"Expected session-id resolution to select transcript_full.jsonl. stdout:\n{captured.out}"
    )
    assert "short transcript loser" not in captured.out, (
        f"Expected compact transcript to be ignored when _full exists. stdout:\n{captured.out}"
    )
    assert "transcript_full.jsonl" in captured.err, (
        f"Expected metadata to show selected full transcript path. stderr:\n{captured.err}"
    )


def test_session_pool_discovers_antigravity_full_transcript_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    session_id = "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
    fallback_session_id = "cccccccc-1111-2222-3333-dddddddddddd"
    short_path = _antigravity_log_path(home, session_id, "transcript.jsonl")
    full_path = _antigravity_log_path(home, session_id, "transcript_full.jsonl")
    fallback_path = _antigravity_log_path(home, fallback_session_id, "transcript.jsonl")

    _write_jsonl(
        short_path,
        [
            {
                "type": "USER_INPUT",
                "created_at": "2026-06-01T10:00:00Z",
                "content": "short",
            }
        ],
    )
    _write_jsonl(
        full_path,
        [
            {
                "type": "USER_INPUT",
                "created_at": "2026-06-01T10:00:00Z",
                "content": "full",
            }
        ],
    )
    _write_jsonl(
        fallback_path,
        [
            {
                "type": "USER_INPUT",
                "created_at": "2026-06-01T11:00:00Z",
                "content": "fallback",
            }
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    pool = SessionPool.discover(include_sidechains=False)

    assert pool.by_provider["antigravitycli"] == (full_path, fallback_path), (
        "Expected Antigravity discovery to prefer transcript_full.jsonl when present "
        f"and fall back to transcript.jsonl otherwise. Got: {pool.by_provider!r}"
    )
