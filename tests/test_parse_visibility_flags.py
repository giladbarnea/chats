#!/usr/bin/env python3
"""CLI integration tests for parse-mode user/assistant visibility flags."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from conversations.cli import main


def _write_session(path: Path) -> None:
    """Write a compact fixture that exercises text, thinking, tools, plans, and agents."""
    entries = [
        {
            "type": "user",
            "timestamp": "2026-04-05T09:00:00.000Z",
            "message": {"role": "user", "content": "plain user"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-04-05T09:00:01.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "private thought"},
                    {"type": "text", "text": "plain assistant"},
                    {
                        "type": "tool_use",
                        "id": "toolu_read_1",
                        "name": "Read",
                        "input": {"file_path": "notes.txt"},
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_plan_1",
                        "name": "ExitPlanMode",
                        "input": {"plan": "# Plan\nstay calm"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-04-05T09:00:02.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_read_1",
                        "content": "notes body",
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "agentId": "agent-007",
            "timestamp": "2026-04-05T09:00:03.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "agent assistant"}],
            },
        },
    ]
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _write_session_with_custom_title(path: Path) -> None:
    """Write a fixture that includes a hidden-by-default rename record."""
    entries = [
        {
            "type": "user",
            "timestamp": "2026-04-05T09:00:00.000Z",
            "message": {"role": "user", "content": "plain user"},
        },
        {
            "type": "custom-title",
            "timestamp": "2026-04-05T09:00:01.000Z",
            "customTitle": "renamed session",
        },
    ]
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _run_cli(monkeypatch, capsys, *argv: str) -> tuple[int, str, str]:
    """Execute the real CLI entrypoint and capture exit code + stdio."""
    monkeypatch.setattr(sys, "argv", ["ccc", *argv])
    exit_code = 0

    try:
        main()
    except SystemExit as exc:  # pragma: no cover - exercised by CLI behavior
        exit_code = exc.code if isinstance(exc.code, int) else 1

    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def test_only_assistant_overrides_thinking_with_warning(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--only-assistant` should disable contradictory extras upstream and keep assistant-only output."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--only-assistant",
        "--thinking",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "warning" in stderr.lower(), (
        "Expected a warning when `--only-assistant` overrides `--thinking`. "
        f"Got stderr:\n{stderr}"
    )
    assert "plain assistant" in stdout, (
        "Expected regular assistant text to remain visible. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "plain user" not in stdout, (
        "Expected user text to be hidden by `--only-assistant`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "<thinking>" not in stdout, (
        "Expected contradictory thinking output to be disabled upstream. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert 'name="Read"' not in stdout, (
        "Expected tool visibility to remain off for `--only-assistant`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "agent assistant" not in stdout, (
        "Expected agent messages to remain hidden unless `--agents` survives normalization. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_only_assistant_overrides_plans_with_warning(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--only-assistant` should disable contradictory plan visibility upstream."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--only-assistant",
        "--plans",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "warning" in stderr.lower(), (
        "Expected a warning when `--only-assistant` overrides `--plans`. "
        f"Got stderr:\n{stderr}"
    )
    assert "plain assistant" in stdout, (
        "Expected regular assistant text to remain visible. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert 'name="ExitPlanMode"' not in stdout, (
        "Expected contradictory plan output to be disabled upstream. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_only_user_and_only_assistant_warn_but_end_with_empty_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Contradictory `--only-*` flags should warn, then fall through to empty output without a no-messages error."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--only-user",
        "--only-assistant",
        str(session_path),
    )

    assert exit_code == 0, (
        "Expected the contradictory `--only-*` combination to stay a successful no-op. "
        f"Got exit_code={exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert stdout == "", (
        "Expected the contradictory `--only-*` filters to match nothing and print nothing. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "warning" in stderr.lower(), (
        "Expected a warning for contradictory `--only-user` + `--only-assistant`. "
        f"Got stderr:\n{stderr}"
    )
    assert "No messages found in input." not in stderr, (
        "Expected the flow to end organically without a no-messages error. "
        f"Got stderr:\n{stderr}"
    )


def test_only_user_overrides_tools_and_agents_with_warning(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--only-user` should disable contradictory extras and leave only regular user output."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--only-user",
        "--tools",
        "--agents",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "warning" in stderr.lower(), (
        "Expected a warning when `--only-user` overrides extra visibility options. "
        f"Got stderr:\n{stderr}"
    )
    assert "plain user" in stdout, (
        "Expected regular user text to remain visible. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "plain assistant" not in stdout, (
        "Expected assistant text to be hidden by `--only-user`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert 'name="Read"' not in stdout, (
        "Expected tool visibility to be disabled upstream by `--only-user`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "agent assistant" not in stdout, (
        "Expected agent visibility to be disabled upstream by `--only-user`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_default_parse_hides_session_rename_blocks(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Default parse output should ignore session-rename records."""
    session_path = tmp_path / "rename-fixture.jsonl"
    _write_session_with_custom_title(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "plain user" in stdout, (
        "Expected regular user text to remain visible. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "renamed session" not in stdout, (
        "Expected session-rename records to stay out of default parse output. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "<session-rename" not in stdout, (
        "Expected default parse output not to render the session-rename wrapper. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_plans_hidden_by_default_and_shown_with_explicit_flag(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """Plans should require `--plans` in parse mode."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert 'name="ExitPlanMode"' not in stdout, (
        "Expected plans to stay hidden by default. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--plans",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert 'name="ExitPlanMode"' in stdout, (
        "Expected `--plans` to make plan content visible. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_all_now_includes_plans(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--all` should include plans now that they are otherwise hidden by default."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--all",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert 'name="ExitPlanMode"' in stdout, (
        "Expected `--all` to include plan content. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_no_assistant_still_shows_agents_when_requested(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--no-assistant` should hide regular assistant output without disabling explicit agent visibility."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--no-assistant",
        "--agents",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "plain assistant" not in stdout, (
        "Expected regular assistant text to be hidden by `--no-assistant`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "agent assistant" in stdout, (
        "Expected `--agents` to keep agent messages visible even when regular assistant text is hidden. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_no_user_hides_regular_user_text_but_keeps_tool_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--no-user` should hide normal user text without suppressing explicitly requested tools."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--no-user",
        "--tools",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "plain user" not in stdout, (
        "Expected regular user text to be hidden by `--no-user`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "plain assistant" in stdout, (
        "Expected regular assistant text to remain visible. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert '<tool-input name="Read"' in stdout, (
        "Expected assistant tool input to remain visible when `--tools` is enabled. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert '<tool-output name="Read"' in stdout, (
        "Expected user-side tool output to remain visible even when regular user text is hidden. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_no_assistant_can_show_thinking_tools_and_agents_together(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--no-assistant` should hide regular assistant text while preserving explicitly requested extras."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--no-assistant",
        "--thinking",
        "--tools",
        "--agents",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert stderr == "", (
        f"Expected no warning for a valid combination. Got stderr:\n{stderr}"
    )
    assert "plain assistant" not in stdout, (
        "Expected regular assistant text to be hidden by `--no-assistant`. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "<thinking>" in stdout, (
        "Expected thinking blocks to remain visible when explicitly enabled. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert '<tool-input name="Read"' in stdout, (
        "Expected tool inputs to remain visible when explicitly enabled. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert "agent assistant" in stdout, (
        "Expected agent messages to remain visible when `--agents` is enabled. "
        f"Got stdout:\n{stdout}\nstderr:\n{stderr}"
    )


def test_thinking_short_modifier_truncates_only_thinking_blocks(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--thinking=short` should truncate thinking blocks while keeping the block visible."""
    session_path = tmp_path / "thinking-short-fixture.jsonl"
    long_thinking = "THINK_START-" + ("x" * 1000) + "-THINK_END"
    entries = [
        {
            "type": "assistant",
            "timestamp": "2026-04-05T09:00:01.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": long_thinking},
                    {"type": "text", "text": "assistant text"},
                ],
            },
        }
    ]
    session_path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--thinking=short",
        str(session_path),
    )

    assert exit_code == 0, (
        f"Expected success exit code. Got: {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert stderr == "", (
        f"Expected no warning for valid --thinking=short usage. Got stderr:\n{stderr}"
    )
    assert "<thinking>" in stdout, (
        "Expected thinking blocks to be shown when `--thinking=short` is enabled. "
        f"Got stdout:\n{stdout}"
    )
    assert stdout.count("\n...\n") == 1, (
        "Expected shortened thinking output to contain one line-broken ellipsis placeholder. "
        f"Got stdout:\n{stdout}"
    )
    assert "THINK_START-" in stdout and "THINK_END" in stdout, (
        "Expected shortened thinking output to preserve both prefix and suffix. "
        f"Got stdout:\n{stdout}"
    )


def test_bare_thinking_flag_keeps_following_slice_positional(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """`--thinking` should not consume a following numeric slice argument."""
    session_path = tmp_path / "visibility-fixture.jsonl"
    _write_session(session_path)

    exit_code, stdout, stderr = _run_cli(
        monkeypatch,
        capsys,
        "--color=never",
        "--no-metadata",
        "--thinking",
        "2",
        str(session_path),
    )

    assert exit_code == 0, (
        "Expected `--thinking 2 <file>` to treat `2` as the positional slice, "
        f"not as an invalid thinking mode. Got exit_code={exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )
    assert stderr == "", (
        "Expected no CLI error when a slice follows bare `--thinking`. "
        f"Got stderr:\n{stderr}"
    )
    assert "plain assistant" in stdout, (
        f"Expected slice `2` to select the assistant turn. Got stdout:\n{stdout}"
    )
    assert "<thinking>" in stdout, (
        "Expected the selected assistant turn to keep its thinking block visible. "
        f"Got stdout:\n{stdout}"
    )
    assert "plain user" not in stdout, (
        f"Expected slice `2` to exclude the first user turn. Got stdout:\n{stdout}"
    )
