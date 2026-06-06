#!/usr/bin/env python3
"""CLI seam tests for search-specific argument normalization."""

from __future__ import annotations

from chats import SearchOutputMode, cli


def test_search_only_id_forces_plain_output(monkeypatch) -> None:
    """`search --only-id` should force plain output regardless of color/paging flags."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        output_format: str = "xml",
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
        ["ch", "search", "--only-id", "--paging", "--color", "always", "needle"],
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
        output_format: str = "xml",
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["output_mode"] = output_mode

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "-f", "needle"])

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["output_mode"] == SearchOutputMode.FULL, (
        "Expected `ch search -f needle` to request full-conversation output. "
        f"Got: {captured.get('output_mode')!r}"
    )


def test_search_raw_forces_plain_output_and_disables_metadata(monkeypatch) -> None:
    """`search -r/--raw` should mirror parse raw behavior on the display path."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        output_format: str = "xml",
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["flags"] = flags
        captured["output_mode"] = output_mode
        captured["output_format"] = output_format
        captured["emit_metadata"] = emit_metadata

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["ch", "search", "--raw", "--paging", "--color", "always", "needle"],
    )

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["output_mode"] == SearchOutputMode.MATCHES, (
        "Expected raw search to keep the default matching-messages breadth unless "
        f"`--full` was requested. Got: {captured.get('output_mode')!r}"
    )
    assert captured["output_format"] == "raw", (
        "Expected `search --raw` to request raw output formatting. "
        f"Got: {captured.get('output_format')!r}"
    )
    assert captured["emit_metadata"] is False, (
        "Expected `search --raw` to imply `--no-metadata`. "
        f"Got: {captured.get('emit_metadata')!r}"
    )
    flags = captured["flags"]
    assert flags.color is False, (
        "Expected `search --raw` to force plain output even when `--color always` "
        f"was passed. Got: {flags!r}"
    )
    assert flags.paging is False, (
        "Expected `search --raw` to bypass paging just like parse raw output. "
        f"Got: {flags!r}"
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
        output_format: str = "xml",
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["output_mode"] = output_mode

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "needle"])

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["output_mode"] == SearchOutputMode.MATCHES, (
        "Expected bare search to keep rendering only matching messages. "
        f"Got: {captured.get('output_mode')!r}"
    )


def test_search_plans_flag_reaches_cmd_search(monkeypatch) -> None:
    """`search --plans` should opt plan visibility back in."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        output_format: str = "xml",
        emit_metadata: bool = True,
    ) -> None:
        captured["flags"] = flags

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "--plans", "needle"])

    cli.main()

    assert captured["flags"].show_plans is True, (
        "Expected `search --plans` to enable plan visibility in ConversationFlags."
    )



def test_search_all_includes_plans(monkeypatch) -> None:
    """`search --all` should include plans along with the other extras."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        pool_filter=None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        output_format: str = "xml",
        emit_metadata: bool = True,
    ) -> None:
        captured["flags"] = flags

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(cli.sys, "argv", ["ch", "search", "--all", "needle"])

    cli.main()

    assert captured["flags"].show_plans is True, (
        "Expected `search --all` to include plans now that they are hidden by default."
    )
