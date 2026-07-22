#!/usr/bin/env python3
"""Behavior and CLI seam tests for search case sensitivity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import ConversationFlags, SearchOutputMode, cli, commands


def _write_session(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2025-01-01T00:00:00Z",
            "cwd": "/tmp/search-case-sensitivity",
            "message": {"role": "user", "content": text},
        })
        + "\n",
        encoding="utf-8",
    )


def _run_search_ids(
    pattern: str,
    capsys,
    *,
    case_sensitive: bool = False,
) -> tuple[int, list[str]]:
    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            pattern,
            ConversationFlags(color="never", paging=False),
            case_sensitive=case_sensitive,
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=False,
        )
    return exc_info.value.code, capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    ("case_flag", "expected_case_sensitive"),
    [
        ([], False),
        (["-i"], False),
        (["--case-insensitive"], False),
        (["-s"], True),
        (["--case-sensitive"], True),
    ],
)
def test_search_case_flag_reaches_command(
    monkeypatch,
    case_flag: list[str],
    expected_case_sensitive: bool,
) -> None:
    captured: dict[str, object] = {}

    def fake_cmd_search(
        pattern_arg: str,
        flags: ConversationFlags,
        pool_filter=None,
        *,
        case_sensitive: bool = False,
        output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
        output_format: str = "xml",
        emit_metadata: bool = True,
    ) -> None:
        captured["pattern"] = pattern_arg
        captured["case_sensitive"] = case_sensitive

    monkeypatch.setattr(cli, "cmd_search", fake_cmd_search)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["ch", "search", *case_flag, "CaseNeedle"],
    )

    cli.main()

    assert captured == {
        "pattern": "CaseNeedle",
        "case_sensitive": expected_case_sensitive,
    }


def test_search_case_flags_are_mutually_exclusive(monkeypatch, capsys) -> None:
    def fail_cmd_search(*_args, **_kwargs) -> None:
        raise AssertionError("cmd_search must not run for contradictory case flags")

    monkeypatch.setattr(cli, "cmd_search", fail_cmd_search)
    monkeypatch.setattr(
        cli.sys,
        "argv",
        ["ch", "search", "-s", "-i", "CaseNeedle"],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_search_is_case_insensitive_by_default(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(
        home / ".claude" / "projects" / "proj" / "default-match.jsonl",
        "CaseNeedle",
    )

    exit_code, matched_ids = _run_search_ids("caseneedle", capsys)

    assert exit_code == 0
    assert matched_ids == ["default-match"]


def test_case_sensitive_search_requires_exact_literal_case(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(
        home / ".claude" / "projects" / "proj" / "exact-match.jsonl",
        "CaseNeedle",
    )

    exact_exit_code, exact_ids = _run_search_ids(
        "CaseNeedle", capsys, case_sensitive=True
    )
    mismatch_exit_code, mismatch_ids = _run_search_ids(
        "caseneedle", capsys, case_sensitive=True
    )

    assert exact_exit_code == 0
    assert exact_ids == ["exact-match"]
    assert mismatch_exit_code == 1
    assert mismatch_ids == []


def test_case_sensitive_search_applies_to_regex_terms(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(
        home / ".claude" / "projects" / "proj" / "regex-case.jsonl",
        "token-abc",
    )

    exit_code, matched_ids = _run_search_ids(
        r"Token-[A-Z]+", capsys, case_sensitive=True
    )

    assert exit_code == 1
    assert matched_ids == []


def test_case_sensitive_search_applies_to_negated_terms(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(
        home / ".claude" / "projects" / "proj" / "not-case.jsonl",
        "CaseNeedle blocked",
    )

    exit_code, matched_ids = _run_search_ids(
        "CaseNeedle NOT BLOCKED",
        capsys,
        case_sensitive=True,
    )

    assert exit_code == 0
    assert matched_ids == ["not-case"]
