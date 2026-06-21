#!/usr/bin/env python3
"""Tests for the `info` command's session statistics aggregation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats.commands import build_session_info, cmd_info, render_session_info


def _write_session(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a session fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _pi_session_path(home: Path) -> Path:
    return (
        home
        / ".pi"
        / "agent"
        / "sessions"
        / "--tmp-project--"
        / "2026-06-21T18-45-29-010Z_pi-session.jsonl"
    )


def _pi_entries() -> list[dict]:
    """A minimal PI session: header, title, user, assistant (usage+cost+tool), result."""
    return [
        {
            "type": "session",
            "id": "pi-session",
            "timestamp": "2026-06-21T18:45:29.010Z",
            "cwd": "/tmp/project",
        },
        {"type": "session_info", "name": "fill rate report"},
        {
            "type": "message",
            "id": "m1",
            "timestamp": "2026-06-21T18:45:30.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "hello"}],
            },
        },
        {
            "type": "message",
            "id": "m2",
            "timestamp": "2026-06-21T18:50:29.010Z",
            "message": {
                "role": "assistant",
                "model": "anthropic/claude-sonnet-4.6",
                "provider": "openrouter",
                "content": [
                    {"type": "text", "text": "on it"},
                    {"type": "toolCall", "id": "tc1", "name": "bash"},
                ],
                "usage": {
                    "input": 571,
                    "output": 179,
                    "cacheRead": 10240,
                    "cacheWrite": 0,
                    "totalTokens": 10990,
                    "cost": {
                        "input": 0.0014275,
                        "output": 0.002685,
                        "cacheRead": 0.00256,
                        "cacheWrite": 0,
                        "total": 0.0066725,
                    },
                },
            },
        },
        {
            "type": "message",
            "id": "m3",
            "timestamp": "2026-06-21T18:50:30.000Z",
            "message": {
                "role": "toolResult",
                "toolCallId": "tc1",
                "toolName": "bash",
                "content": "done",
            },
        },
    ]


def _claude_entries() -> list[dict]:
    """A Claude session: human user, one assistant response split across two lines
    (repeating message.id + usage), a tool result, a synthetic line, and a
    turn_duration system entry."""
    usage = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 200,
    }
    return [
        {
            "type": "user",
            "timestamp": "2026-06-21T18:45:29.010Z",
            "message": {"role": "user", "content": "hello"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-06-21T18:45:31.000Z",
            "requestId": "req_1",
            "message": {
                "id": "msg_1",
                "model": "claude-opus-4-8",
                "usage": usage,
                "content": [{"type": "thinking", "thinking": "hmm"}],
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-06-21T18:45:32.000Z",
            "requestId": "req_1",
            "message": {
                "id": "msg_1",
                "model": "claude-opus-4-8",
                "usage": usage,
                "content": [
                    {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {}}
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-06-21T18:45:33.000Z",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_1", "content": "out"}
                ],
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-06-21T18:45:34.000Z",
            "message": {
                "id": "msg_syn",
                "model": "<synthetic>",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "content": [{"type": "text", "text": "placeholder"}],
            },
        },
        {
            "type": "system",
            "subtype": "turn_duration",
            "durationMs": 5000,
            "timestamp": "2026-06-21T18:50:29.010Z",
        },
    ]


# ---------------------------------------------------------------------------
# PI: cost and tokens come straight from the stored usage object
# ---------------------------------------------------------------------------


def test_pi_aggregation_uses_stored_cost_and_tokens(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = _pi_session_path(home)
    _write_session(path, _pi_entries())

    info = build_session_info(path)

    assert info.provider == "pi", f"Expected pi provider, got {info.provider!r}"
    assert info.name == "fill rate report", f"Got name {info.name!r}"
    assert info.user_messages == 1, f"Got {info.user_messages} user messages"
    assert info.assistant_messages == 1, f"Got {info.assistant_messages} assistant"
    assert info.tool_calls == 1, f"Got {info.tool_calls} tool calls"
    assert info.tool_results == 1, f"Got {info.tool_results} tool results"
    assert info.total_messages == 3, f"Got total {info.total_messages}"

    usage = info.usage_by_model["anthropic/claude-sonnet-4.6"]
    assert usage.input_tokens == 571, f"Got input {usage.input_tokens}"
    assert usage.cache_read_tokens == 10240, f"Got cache read {usage.cache_read_tokens}"
    assert info.totals.cost == pytest.approx(0.0066725), (
        f"Expected stored PI cost summed, got {info.totals.cost}"
    )


def test_pi_wall_duration_spans_first_to_last_timestamp(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = _pi_session_path(home)
    _write_session(path, _pi_entries())

    info = build_session_info(path)

    assert info.wall_duration is not None, "Expected a wall duration"
    assert info.wall_duration.total_seconds() == pytest.approx(300.99, abs=0.01), (
        f"Expected ~301s span (first to last timestamp), got {info.wall_duration.total_seconds()}"
    )
    assert info.api_duration is None, "PI has no in-band API duration to report"


# ---------------------------------------------------------------------------
# Claude: usage deduplicated by message.id, cost computed from a pricing table
# ---------------------------------------------------------------------------


def test_claude_deduplicates_usage_across_repeated_message_lines(tmp_path):
    path = tmp_path / "claude-session.jsonl"
    _write_session(path, _claude_entries())

    info = build_session_info(path)

    assert info.provider == "claude", f"Got provider {info.provider!r}"
    usage = info.usage_by_model["claude-opus-4-8"]
    assert usage.input_tokens == 100, (
        f"Two lines share message.id msg_1; usage must count once, got {usage.input_tokens}"
    )
    assert usage.output_tokens == 50, f"Got output {usage.output_tokens}"
    assert usage.cache_write_tokens == 200, f"Got cache write {usage.cache_write_tokens}"
    assert "<synthetic>" not in info.usage_by_model, (
        "Synthetic placeholder lines must not appear as a model"
    )


def test_claude_dedup_keeps_final_output_tokens_not_thinking_partial(tmp_path):
    """When a response opens with a thinking block, the first line's output_tokens
    is a partial; the final total is on a later line. Dedup must keep the last."""
    path = tmp_path / "claude-thinking-first.jsonl"
    _write_session(
        path,
        [
            {
                "type": "assistant",
                "timestamp": "2026-06-21T18:45:31.000Z",
                "message": {
                    "id": "msg_x",
                    "model": "claude-opus-4-8",
                    "usage": {"input_tokens": 10, "output_tokens": 49},
                    "content": [{"type": "thinking", "thinking": "..."}],
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-06-21T18:45:33.000Z",
                "message": {
                    "id": "msg_x",
                    "model": "claude-opus-4-8",
                    "usage": {"input_tokens": 10, "output_tokens": 5942},
                    "content": [{"type": "text", "text": "answer"}],
                },
            },
        ],
    )

    info = build_session_info(path)

    assert info.usage_by_model["claude-opus-4-8"].output_tokens == 5942, (
        "Dedup must keep the final output_tokens (5942), not the thinking-only "
        f"partial (49); got {info.usage_by_model['claude-opus-4-8'].output_tokens}"
    )


def test_claude_computes_cost_from_pricing_table(tmp_path):
    path = tmp_path / "claude-session.jsonl"
    _write_session(path, _claude_entries())

    info = build_session_info(path)

    # opus-4-8, no TTL breakdown -> cache writes at the 5-minute rate (1.25x input):
    # 100*$5 + 50*$25 + 1000*$0.5 + 200*$6.25, per million tokens.
    expected = (100 * 5 + 50 * 25 + 1000 * 0.5 + 200 * 6.25) / 1_000_000
    assert info.totals.cost == pytest.approx(expected), (
        f"Expected computed cost {expected}, got {info.totals.cost}"
    )


def test_claude_prices_one_hour_cache_writes_at_double_input(tmp_path):
    """A 1-hour cache write bills at 2x input, not the 1.25x 5-minute rate."""
    path = tmp_path / "claude-1h.jsonl"
    _write_session(
        path,
        [
            {
                "type": "assistant",
                "timestamp": "2026-06-21T18:45:31.000Z",
                "message": {
                    "id": "msg_1h",
                    "model": "claude-opus-4-8",
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 1000,
                        "cache_creation": {
                            "ephemeral_1h_input_tokens": 1000,
                            "ephemeral_5m_input_tokens": 0,
                        },
                    },
                    "content": [{"type": "text", "text": "hi"}],
                },
            }
        ],
    )

    info = build_session_info(path)

    # 1000 cache-write tokens at 2x opus input ($5) -> $10/Mtok -> $0.01.
    assert info.totals.cost == pytest.approx(1000 * 10 / 1_000_000), (
        f"1-hour writes must bill at 2x input; got {info.totals.cost}"
    )


def test_pi_total_tokens_is_read_not_recomputed(tmp_path, monkeypatch):
    """The PI report trusts the stored `totalTokens` field over a fresh sum."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    path = _pi_session_path(home)
    _write_session(
        path,
        [
            {
                "type": "session",
                "id": "pi-session",
                "timestamp": "2026-06-21T18:45:29.010Z",
            },
            {
                "type": "message",
                "id": "m1",
                "timestamp": "2026-06-21T18:45:30.000Z",
                "message": {
                    "role": "assistant",
                    "model": "gpt-5.4",
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {
                        "input": 1,
                        "output": 1,
                        "cacheRead": 1,
                        "cacheWrite": 1,
                        # Deliberately not equal to 1+1+1+1; the report must trust this.
                        "totalTokens": 99999,
                        "cost": {"total": 0.5},
                    },
                },
            },
        ],
    )

    info = build_session_info(path)

    assert info.total_tokens == 99999, (
        f"Expected stored totalTokens (99999) to be used, got {info.total_tokens}"
    )


def test_claude_counts_messages_tools_and_api_duration(tmp_path):
    path = tmp_path / "claude-session.jsonl"
    _write_session(path, _claude_entries())

    info = build_session_info(path)

    assert info.user_messages == 1, f"Got {info.user_messages} user messages"
    assert info.assistant_messages == 1, (
        f"Synthetic excluded, one real response; got {info.assistant_messages}"
    )
    assert info.tool_calls == 1, f"Got {info.tool_calls} tool calls"
    assert info.tool_results == 1, f"Got {info.tool_results} tool results"
    assert info.total_messages == 3, f"Got total {info.total_messages}"
    assert info.api_duration is not None, "turn_duration entry should yield API duration"
    assert info.api_duration.total_seconds() == pytest.approx(5.0), (
        f"Expected 5s API duration, got {info.api_duration.total_seconds()}"
    )


# ---------------------------------------------------------------------------
# Provider gate and rendering
# ---------------------------------------------------------------------------


def test_unsupported_provider_is_rejected(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    codex_path = (
        home / ".codex" / "sessions" / "2026" / "rollout-2026-codex.jsonl"
    )
    _write_session(
        codex_path,
        [{"type": "session_meta", "payload": {"id": "codex"}}],
    )

    with pytest.raises(ValueError, match="claude and pi"):
        build_session_info(codex_path)


def test_render_contains_all_sections(tmp_path):
    path = tmp_path / "claude-session.jsonl"
    _write_session(path, _claude_entries())

    rendered = render_session_info(build_session_info(path))

    for marker in ("Session Info", "Messages", "Tokens", "Cost", "claude-opus-4-8"):
        assert marker in rendered, f"Expected {marker!r} in rendered report"
    assert " Total: 1,350" in rendered, (
        f"Total tokens should include cache write; report was:\n{rendered}"
    )


def test_cmd_info_preserves_bracketed_session_name(tmp_path, capsys):
    """Square brackets in a name must survive printing, not be eaten as Rich markup."""
    path = tmp_path / "claude-bracket.jsonl"
    _write_session(
        path,
        [
            {
                "type": "custom-title",
                "customTitle": "[06-21][avidor-run] dormant-insole 00",
                "sessionId": "s",
            },
            {
                "type": "user",
                "timestamp": "2026-06-21T18:45:29.010Z",
                "message": {"role": "user", "content": "hi"},
            },
            {
                "type": "assistant",
                "timestamp": "2026-06-21T18:45:31.000Z",
                "message": {
                    "id": "m",
                    "model": "claude-opus-4-8",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                    "content": [{"type": "text", "text": "ok"}],
                },
            },
        ],
    )

    cmd_info(str(path))

    out = capsys.readouterr().out
    assert "[06-21][avidor-run] dormant-insole 00" in out, (
        f"Bracketed name must print verbatim, not be consumed as markup; got:\n{out}"
    )


def test_cmd_info_prints_report_for_resolved_path(tmp_path, capsys):
    path = tmp_path / "claude-session.jsonl"
    _write_session(path, _claude_entries())

    cmd_info(str(path))

    out = capsys.readouterr().out
    assert "Session Info" in out, f"Expected report on stdout, got:\n{out}"
    assert "claude-opus-4-8" in out, f"Expected model line, got:\n{out}"
