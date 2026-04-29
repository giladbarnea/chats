#!/usr/bin/env python3
"""CLI seam tests for search-specific argument normalization."""

from __future__ import annotations

from conversations import SearchOutputMode, cli


def test_search_only_id_forces_plain_output(monkeypatch) -> None:
    """`search --only-id` should force plain output regardless of color/paging flags."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["flags"] = flags
        captured["output_mode"] = output_mode
        captured["emit_metadata"] = emit_metadata

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["ccc", "search", "--only-id", "--paging", "--color", "always", "needle"],
    )

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["output_mode"] == SearchOutputMode.ONLY_ID
    flags = captured["flags"]
    assert flags.color is False, (
        "Expected --only-id to force plain output even when --color always was passed."
    )
    assert flags.paging is False, (
        "Expected --only-id to force paging off even if --paging was also passed."
    )


def test_search_full_flag_reaches_cmd_search(monkeypatch) -> None:
    """`search -f/--full` should request full-conversation rendering."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["output_mode"] = output_mode

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "search", "-f", "needle"])

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["output_mode"] == SearchOutputMode.FULL, (
        "Expected `ccc search -f needle` to request full-conversation output. "
        f"Got: {captured.get('output_mode')!r}"
    )


def test_search_default_output_mode_is_matching_messages(monkeypatch) -> None:
    """Bare `search` should keep showing only matching messages."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["output_mode"] = output_mode

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ccc", "search", "needle"])

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["output_mode"] == SearchOutputMode.MATCHES, (
        "Expected bare search to keep rendering only matching messages. "
        f"Got: {captured.get('output_mode')!r}"
    )
