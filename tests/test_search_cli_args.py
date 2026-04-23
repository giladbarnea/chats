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
        dir_filter: str | None = None,
        mafter: str | None = None,
        cafter: str | None = None,
        *,
        output_mode: SearchOutputMode = SearchOutputMode.FULL,
        emit_metadata: bool = True,
        provider_filter=None,
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
