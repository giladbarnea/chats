#!/usr/bin/env python3
"""CLI seam tests for search-specific argument normalization."""

from __future__ import annotations

from conversations import cli


def test_search_only_id_disables_paging_but_keeps_color(monkeypatch) -> None:
    """`search --only-id` should force paging off without changing color selection."""
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags,
        list_only: bool,
        only_id: bool = False,
        dir_filter: str | None = None,
        mafter: str | None = None,
        cafter: str | None = None,
        *,
        emit_metadata: bool = True,
        provider_filter=None,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["flags"] = flags
        captured["list_only"] = list_only
        captured["only_id"] = only_id
        captured["emit_metadata"] = emit_metadata

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["ccc", "search", "--only-id", "--paging", "--color", "always", "needle"],
    )

    cli.main()

    assert captured["pattern"] == "needle"
    assert captured["only_id"] is True
    flags = captured["flags"]
    assert flags.color is True, "Expected --color always to keep Rich color enabled."
    assert flags.paging is False, (
        "Expected --only-id to force paging off even if --paging was also passed."
    )
