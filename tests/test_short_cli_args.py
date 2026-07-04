#!/usr/bin/env python3
"""CLI seam tests for `--short` character-limit parsing and ambiguity handling."""

from __future__ import annotations

import pytest

from chats import cli


def _run_parse_cli(monkeypatch, *argv: str) -> tuple[int, dict[str, object]]:
    """Run parse-mode CLI and capture the arguments that reach cmd_parse."""
    captured: dict[str, object] = {}

    def fake_cmd_parse(
        flags,
        input_path=None,
        *,
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
        pool_filter=None,
        output_mode=None,
    ) -> None:
        captured["flags"] = flags
        captured["input"] = input_path
        captured["slice_str"] = slice_str

    monkeypatch.setattr(cli, "cmd_parse", fake_cmd_parse)
    monkeypatch.setattr(cli.sys, "argv", ["ch", *argv])

    exit_code = 0
    try:
        cli.main()
    except SystemExit as exc:  # pragma: no cover - argparse seam
        exit_code = exc.code if isinstance(exc.code, int) else 1

    return exit_code, captured


def _run_search_cli(monkeypatch, *argv: str) -> tuple[int, dict[str, object]]:
    """Run search-mode CLI and capture the arguments that reach cmd_search."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode=None,
        output_format="xml",
        emit_metadata=True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["flags"] = flags

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", *argv])

    exit_code = 0
    try:
        cli.main()
    except SystemExit as exc:  # pragma: no cover - argparse seam
        exit_code = exc.code if isinstance(exc.code, int) else 1

    return exit_code, captured


def test_parse_bare_short_keeps_following_input_positional(monkeypatch) -> None:
    """Bare `--short` should leave the following token as parse input."""
    exit_code, captured = _run_parse_cli(monkeypatch, "--short", "session.jsonl")

    assert exit_code == 0, f"Expected success. Got exit_code={exit_code}."
    assert captured["input"] == "session.jsonl", (
        "Expected bare `--short` to keep the following token as parse input. "
        f"Got: {captured.get('input')!r}"
    )
    assert captured["flags"].shorten is True
    assert captured["flags"].shorten_max_chars == 500


def test_parse_short_accepts_attached_numeric_max_chars(monkeypatch) -> None:
    """`--short=NUMBER` should propagate the custom max-chars into ConversationFlags."""
    exit_code, captured = _run_parse_cli(monkeypatch, "--short=120", "session.jsonl")

    assert exit_code == 0
    assert captured["input"] == "session.jsonl"
    assert captured["flags"].shorten is True
    assert captured["flags"].shorten_max_chars == 120, (
        "Expected `--short=120` to propagate max-chars 120. "
        f"Got: {captured['flags'].shorten_max_chars!r}"
    )


@pytest.mark.parametrize(
    ("argv", "expected_input", "expected_slices", "expected_max_chars"),
    [
        (("-1", "-1", "-s", "10"), "-1", ["-1"], 10),
        (("-1", "-1", "-s"), "-1", ["-1"], 500),
        (("-1", "-s", "-1"), "-1", ["-1"], 500),
        (("-1", "-s", "1"), "-1", ["1"], 500),
        (("10", "-s"), "10", [], 500),
        (("10", "-s", "10"), "10", [], 10),
        (("-s", "10", "-1"), "-1", [], 10),
        (("-10", "-s", "10:12", "10"), "-10", ["10:12", "10"], 500),
        (("FILE", "-s", "10"), "FILE", [], 10),
        (("FILE", "-s", "1"), "FILE", ["1"], 500),
        (("FILE", "-s", "1:3"), "FILE", ["1:3"], 500),
    ],
)
def test_parse_short_resolves_ambiguous_numeric_neighbors(
    monkeypatch,
    argv: tuple[str, ...],
    expected_input: str,
    expected_slices: list[str],
    expected_max_chars: int,
) -> None:
    """Detached numeric values after `--short` become the max-chars only when they are digits > 7."""
    exit_code, captured = _run_parse_cli(monkeypatch, *argv)

    assert exit_code == 0, (
        f"Expected success for argv={argv!r}. Got exit_code={exit_code}."
    )
    assert captured["input"] == expected_input, (
        f"Expected input {expected_input!r} for argv={argv!r}. Got: {captured.get('input')!r}"
    )
    assert captured["slice_str"] == expected_slices, (
        f"Expected slices {expected_slices!r} for argv={argv!r}. Got: {captured.get('slice_str')!r}"
    )
    assert captured["flags"].shorten is True
    assert captured["flags"].shorten_max_chars == expected_max_chars, (
        f"Expected shorten max-chars {expected_max_chars} for argv={argv!r}. "
        f"Got: {captured['flags'].shorten_max_chars!r}"
    )


def test_parse_short_can_snatch_the_only_numeric_token(monkeypatch) -> None:
    """`-s 10` should consume 10 as the max-chars and leave no positional input behind."""
    exit_code, captured = _run_parse_cli(monkeypatch, "-s", "10")

    assert exit_code == 0, (
        "Expected the CLI seam to reach cmd_parse after consuming 10 as the max-chars. "
        f"Got exit_code={exit_code} captured={captured!r}"
    )
    assert captured["input"] is None, (
        "Expected `-s 10` to leave no positional input after consuming 10 as the max-chars. "
        f"Got: {captured.get('input')!r}"
    )
    assert captured["slice_str"] == []
    assert captured["flags"].shorten_max_chars == 10


def test_parse_tool_short_accepts_local_attached_max_chars(monkeypatch) -> None:
    """`-t Bash:s=10` should keep its max-chars limit local to that tool spec."""
    exit_code, captured = _run_parse_cli(
        monkeypatch,
        "-t",
        "Bash:s=10",
        "session.jsonl",
    )

    assert exit_code == 0, f"Expected success. Got exit_code={exit_code}."
    assert captured["input"] == "session.jsonl"
    tool_filters = captured["flags"].show_tools
    assert isinstance(tool_filters, list), (
        f"Expected filtered tool specs to reach flags as a list. Got: {tool_filters!r}"
    )
    assert tool_filters[0].name == "Bash", (
        f"Expected `Bash:s=10` to keep name='Bash'. Got: {tool_filters[0]!r}"
    )
    assert tool_filters[0].short is True, (
        f"Expected `Bash:s=10` to enable local shortening. Got: {tool_filters[0]!r}"
    )
    assert tool_filters[0].short_max_chars == 10, (
        "Expected `Bash:s=10` to store local max-chars 10. "
        f"Got: {tool_filters[0].short_max_chars!r}"
    )


def test_search_bare_short_keeps_following_pattern_positional(monkeypatch) -> None:
    """Bare `search --short` should keep the following token as the search pattern."""
    exit_code, captured = _run_search_cli(monkeypatch, "--short", "needle")

    assert exit_code == 0
    assert captured["pattern"] == "needle"
    assert captured["flags"].shorten is True
    assert captured["flags"].shorten_max_chars == 500


def test_search_short_accepts_detached_numeric_max_chars(monkeypatch) -> None:
    """`search --short 120 needle` should propagate max-chars 120 and keep needle as the pattern."""
    exit_code, captured = _run_search_cli(monkeypatch, "--short", "120", "needle")

    assert exit_code == 0
    assert captured["pattern"] == "needle"
    assert captured["flags"].shorten is True
    assert captured["flags"].shorten_max_chars == 120


@pytest.mark.parametrize("invalid_value", ["7", "-1", "1:3"])
def test_parse_invalid_attached_short_value_fails_fast(
    monkeypatch,
    invalid_value: str,
) -> None:
    """Explicit attached `--short=<value>` should fail validation unless the value is digits > 7."""
    exit_code, captured = _run_parse_cli(
        monkeypatch,
        f"--short={invalid_value}",
        "session.jsonl",
    )

    assert exit_code == 2, (
        "Expected invalid attached `--short=<value>` to fail fast before reaching cmd_parse. "
        f"Got exit_code={exit_code} for {invalid_value=!r}"
    )
    assert captured == {}, (
        "Did not expect cmd_parse to run when attached short value validation fails. "
        f"Got: {captured!r}"
    )
