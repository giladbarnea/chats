from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
CH_EXECUTABLE = Path(sys.executable).with_name("ch")
SESSION_ID = "11111111-1111-4111-8111-111111111111"
SOURCE_LENGTH = 240
PLACEHOLDER_LENGTH = len("\n...\n")
PROGRESSIVE_VALUES = (
    ("p", 500),
    ("progressive", 500),
    ("p=32", 32),
    ("progressive=32", 32),
)
INVALID_PROGRESSIVE_VALUES = (
    "",
    "7",
    "p=7",
    "progressive=7",
    "p=",
    "progressive=",
    "unknown",
    "p=p",
    "progressive=progressive",
    "32=p",
    "32=progressive",
    "p=32=extra",
    "progressive=32=extra",
    "32:p",
    "p:32",
    "32:progressive",
    "progressive:32",
    "32:64",
)
GLOBAL_CARRIERS = ("long-attached", "long-detached", "short-detached")
TOOL_CARRIERS = (
    "short-detached",
    "short-attached",
    "long-detached",
    "long-attached",
)
TOOL_SHORT_MODIFIERS = ("s", "short")
LEGACY_DETACHED_SLICE_VALUES = ("7", "32:64")
GLOBAL_VALID_CASES = tuple(
    (value, expected_length, carrier)
    for value, expected_length in PROGRESSIVE_VALUES
    for carrier in GLOBAL_CARRIERS
)
GLOBAL_INVALID_CASES = tuple(
    (value, carrier)
    for value in INVALID_PROGRESSIVE_VALUES
    for carrier in GLOBAL_CARRIERS
    if value not in LEGACY_DETACHED_SLICE_VALUES or carrier == "long-attached"
)
TOOL_VALID_CASES = tuple(
    (value, expected_length, modifier, carrier)
    for value, expected_length in PROGRESSIVE_VALUES
    for modifier in TOOL_SHORT_MODIFIERS
    for carrier in TOOL_CARRIERS
)
TOOL_INVALID_CASES = tuple(
    (value, modifier, carrier)
    for value in INVALID_PROGRESSIVE_VALUES
    for modifier in TOOL_SHORT_MODIFIERS
    for carrier in TOOL_CARRIERS
)


def _timestamp(index: int) -> str:
    hour_offset, minute = divmod(index, 60)
    return f"2026-08-03T{12 + hour_offset:02}:{minute:02}:00.000Z"


def _uuid(index: int) -> str:
    return f"00000000-0000-4000-8000-{index:012d}"


def _assistant_message(
    content: Sequence[dict[str, object]],
    index: int,
    *,
    session_id: str = SESSION_ID,
    cwd: str = "/tmp/progressive-shortening",
) -> dict[str, object]:
    return {
        "parentUuid": None,
        "isSidechain": False,
        "userType": "external",
        "cwd": cwd,
        "sessionId": session_id,
        "version": "1.0.0",
        "gitBranch": "main",
        "type": "assistant",
        "message": {
            "id": f"message-{index}",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-20250514",
            "content": list(content),
            "stop_reason": "end_turn",
        },
        "uuid": _uuid(index),
        "timestamp": _timestamp(index),
    }


def _assistant_text(
    text: str,
    index: int,
    *,
    session_id: str = SESSION_ID,
    cwd: str = "/tmp/progressive-shortening",
) -> dict[str, object]:
    return _assistant_message(
        [{"type": "text", "text": text}],
        index,
        session_id=session_id,
        cwd=cwd,
    )


def _tool_input(
    text: str,
    index: int,
    *,
    name: str = "Bash",
    tool_use_id: str | None = None,
) -> dict[str, object]:
    identifier = tool_use_id or f"tool-{index}"
    input_key = "command" if name == "Bash" else "file_path"
    return _assistant_message(
        [
            {
                "type": "tool_use",
                "id": identifier,
                "name": name,
                "input": {input_key: text},
            }
        ],
        index,
    )


def _tool_inputs(
    tools: Sequence[tuple[str, str]],
    index: int,
) -> dict[str, object]:
    content: list[dict[str, object]] = []
    for tool_index, (name, text) in enumerate(tools):
        input_key = "command" if name == "Bash" else "file_path"
        content.append(
            {
                "type": "tool_use",
                "id": f"tool-{index}-{tool_index}",
                "name": name,
                "input": {input_key: text},
            }
        )
    return _assistant_message(content, index)


def _tool_output_messages(
    text: str,
    index: int,
    *,
    name: str = "Read",
) -> list[dict[str, object]]:
    tool_use_id = f"tool-{index}"
    assistant = _assistant_message(
        [
            {
                "type": "tool_use",
                "id": tool_use_id,
                "name": name,
                "input": {"file_path": "/tmp/example.txt"},
            }
        ],
        index,
    )
    user = {
        "parentUuid": _uuid(index),
        "isSidechain": False,
        "userType": "external",
        "cwd": "/tmp/progressive-shortening",
        "sessionId": SESSION_ID,
        "version": "1.0.0",
        "gitBranch": "main",
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": text,
                }
            ],
        },
        "uuid": _uuid(index + 1),
        "timestamp": _timestamp(index + 1),
    }
    return [assistant, user]


def _write_claude_session(
    home: Path,
    entries: Iterable[dict[str, object]],
    *,
    session_id: str = SESSION_ID,
) -> Path:
    session_directory = home / ".claude" / "projects" / "progressive-shortening"
    session_directory.mkdir(parents=True)
    session_path = session_directory / f"{session_id}.jsonl"
    session_path.write_text(
        "".join(f"{json.dumps(entry, ensure_ascii=False)}\n" for entry in entries),
        encoding="utf-8",
    )
    return session_path


def _run_ch(
    home: Path,
    *arguments: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "COLUMNS": "500",
            "LINES": "100",
            "TZ": "UTC",
        }
    )
    return subprocess.run(
        [str(CH_EXECUTABLE), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def _global_short_arguments(carrier: str, value: str) -> tuple[str, ...]:
    return {
        "long-attached": (f"--short={value}",),
        "long-detached": ("--short", value),
        "short-detached": ("-s", value),
    }[carrier]


def _tool_arguments(carrier: str, specification: str) -> tuple[str, ...]:
    return {
        "short-detached": ("-t", specification),
        "short-attached": (f"-t:{specification}",),
        "long-detached": ("--tools", specification),
        "long-attached": (f"--tools={specification}",),
    }[carrier]


def _assert_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr


def _expected_symbol_count(effective_length: int, source_length: int = SOURCE_LENGTH) -> int:
    return source_length if effective_length >= source_length else effective_length - PLACEHOLDER_LENGTH


def _assert_symbol_lengths(
    output: str,
    symbols_and_lengths: Sequence[tuple[str, int]],
    *,
    source_length: int = SOURCE_LENGTH,
) -> None:
    for symbol, effective_length in symbols_and_lengths:
        expected_count = _expected_symbol_count(effective_length, source_length)
        assert output.count(symbol) == expected_count, (
            f"Expected {expected_count} instances of {symbol!r} for a "
            f"{effective_length}-character limit. Got: {output.count(symbol)}."
        )


def _assistant_bodies(output: str) -> list[str]:
    return re.findall(
        r"<assistant-response\b[^>]*>\n## Assistant\n\n(.*?)\n</assistant-response>",
        output,
        flags=re.DOTALL,
    )


@pytest.mark.parametrize(("value", "expected_length", "carrier"), GLOBAL_VALID_CASES)
def test_global_progressive_values_accept_every_cli_carrier(
    tmp_path: Path,
    value: str,
    expected_length: int,
    carrier: str,
) -> None:
    symbol = "¤"
    session = _write_claude_session(tmp_path, [_assistant_text(symbol * 800, 1)])

    result = _run_ch(
        tmp_path,
        str(session),
        *_global_short_arguments(carrier, value),
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbol, expected_length)], source_length=800)


def test_global_progressive_aliases_and_carriers_are_byte_identical(
    tmp_path: Path,
) -> None:
    symbol = "§"
    session = _write_claude_session(tmp_path, [_assistant_text(symbol * 800, 1)])

    arguments = [
        _global_short_arguments("long-attached", value)
        for value in ("p=32", "progressive=32")
    ] + [
        _global_short_arguments(carrier, "p=32")
        for carrier in ("long-detached", "short-detached")
    ]
    outputs = [
        _run_ch(
            tmp_path,
            str(session),
            *short_arguments,
            "--color=never",
            "--no-metadata",
        )
        for short_arguments in arguments
    ]

    for result in outputs:
        _assert_success(result)
    assert len({result.stdout for result in outputs}) == 1
    _assert_symbol_lengths(outputs[0].stdout, [(symbol, 32)], source_length=800)


@pytest.mark.parametrize(
    "arguments",
    [("--short", "progressive"), ("-s", "p")],
)
def test_detached_progressive_value_is_consumed_before_stdin_resolution(
    tmp_path: Path,
    arguments: tuple[str, str],
) -> None:
    symbol = "¶"
    input_text = "".join(
        f"{json.dumps(entry, ensure_ascii=False)}\n"
        for entry in (
            {
                "type": "session_meta",
                "payload": {"id": SESSION_ID, "cwd": "/tmp/progressive-shortening"},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": symbol * 800}],
                },
            },
        )
    )

    result = _run_ch(
        tmp_path,
        *arguments,
        "--color=never",
        "--no-metadata",
        input_text=input_text,
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbol, 500)], source_length=800)


@pytest.mark.parametrize(("value", "carrier"), GLOBAL_INVALID_CASES)
def test_invalid_global_progressive_value_fails_before_input_resolution(
    tmp_path: Path,
    value: str,
    carrier: str,
) -> None:
    missing_session = tmp_path / "does-not-exist.jsonl"

    result = _run_ch(
        tmp_path,
        str(missing_session),
        *_global_short_arguments(carrier, value),
        "--color=never",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "short" in result.stderr.lower()
    assert "error reading input" not in result.stderr.lower()


@pytest.mark.parametrize(
    ("selector", "expected_indices"),
    [
        pytest.param("7", [7], id="single-message"),
        pytest.param("32:64", list(range(32, 64)), id="range"),
    ],
)
def test_detached_short_after_file_preserves_legacy_slice(
    tmp_path: Path,
    selector: str,
    expected_indices: list[int],
) -> None:
    session = _write_claude_session(
        tmp_path,
        [
            _assistant_text(f"MESSAGE {index} {'¤' * 800}", index)
            for index in range(1, 65)
        ],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "-s",
        selector,
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    rendered_indices = re.findall(r'<assistant-response i="(\d+)"', result.stdout)
    expected_index_strings = [str(index) for index in expected_indices]
    assert rendered_indices == expected_index_strings, (
        f"Expected `{selector}` to select {expected_indices!r}. Got: {rendered_indices!r}."
    )
    rendered_lengths = [len(body) for body in _assistant_bodies(result.stdout)]
    assert rendered_lengths == [500] * len(expected_indices), (
        "Expected bare `-s` to keep its fixed 500-character limit while slicing. "
        f"Got: {rendered_lengths!r}."
    )


@pytest.mark.parametrize(
    ("value", "expected_length", "modifier", "carrier"),
    TOOL_VALID_CASES,
)
def test_tool_progressive_values_accept_every_modifier_and_cli_carrier(
    tmp_path: Path,
    value: str,
    expected_length: int,
    modifier: str,
    carrier: str,
) -> None:
    symbol = "∆"
    session = _write_claude_session(tmp_path, [_tool_input(symbol * 800, 1)])
    specification = f"Bash:{modifier}={value}"

    result = _run_ch(
        tmp_path,
        str(session),
        *_tool_arguments(carrier, specification),
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbol, expected_length)], source_length=800)


@pytest.mark.parametrize(("value", "modifier", "carrier"), TOOL_INVALID_CASES)
def test_invalid_tool_progressive_value_fails_before_input_resolution(
    tmp_path: Path,
    value: str,
    modifier: str,
    carrier: str,
) -> None:
    missing_session = tmp_path / "does-not-exist.jsonl"
    specification = f"Bash:{modifier}={value}"

    result = _run_ch(
        tmp_path,
        str(missing_session),
        *_tool_arguments(carrier, specification),
        "--color=never",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert value in result.stderr or "short" in result.stderr.lower()
    assert "error reading input" not in result.stderr.lower()


def test_tool_progressive_modifiers_are_order_independent_and_directional(
    tmp_path: Path,
) -> None:
    symbol = "Ω"
    session = _write_claude_session(
        tmp_path,
        _tool_output_messages(symbol * SOURCE_LENGTH, 1, name="Read"),
    )

    first = _run_ch(
        tmp_path,
        str(session),
        "-t",
        "Read:o:s=progressive=32",
        "--color=never",
        "--no-metadata",
    )
    second = _run_ch(
        tmp_path,
        str(session),
        "-t:s=p=32:o:Read",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(first)
    _assert_success(second)
    assert first.stdout == second.stdout
    _assert_symbol_lengths(first.stdout, [(symbol, 32)])


def test_search_long_short_option_accepts_progressive_attached_and_detached(
    tmp_path: Path,
) -> None:
    first_symbol = "Ж"
    second_symbol = "Ф"
    session = _write_claude_session(
        tmp_path,
        [
            _assistant_text(f"MATCH {first_symbol * 800}", 1),
            _assistant_text(f"MATCH {second_symbol * 800}", 2),
        ],
    )

    attached = _run_ch(
        tmp_path,
        "search",
        "MATCH",
        "--short=progressive",
        "--full",
        "--color=never",
        "--no-metadata",
    )
    detached = _run_ch(
        tmp_path,
        "search",
        "MATCH",
        "--short",
        "p",
        "--full",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(attached)
    _assert_success(detached)
    assert attached.stdout == detached.stdout
    bodies = _assistant_bodies(attached.stdout)
    assert [len(body) for body in bodies] == [8, 500]
    assert str(session) not in attached.stderr


def test_search_short_s_remains_case_sensitive_instead_of_shortening(
    tmp_path: Path,
) -> None:
    _write_claude_session(tmp_path, [_assistant_text("lowercase needle", 1)])

    sensitive = _run_ch(tmp_path, "search", "Needle", "-s", "--only-id")
    insensitive = _run_ch(tmp_path, "search", "Needle", "--only-id")

    assert sensitive.returncode == 1
    assert sensitive.stdout == ""
    _assert_success(insensitive)
    assert SESSION_ID in insensitive.stdout


def test_search_invalid_progressive_value_fails_with_status_two(tmp_path: Path) -> None:
    result = _run_ch(tmp_path, "search", "needle", "--short=progressive:")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "short" in result.stderr.lower()


def test_search_detached_progressive_value_does_not_replace_missing_pattern(
    tmp_path: Path,
) -> None:
    result = _run_ch(tmp_path, "search", "--short", "p")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "pattern" in result.stderr.lower()


def test_search_local_tool_progressive_modifier_reaches_rendering(tmp_path: Path) -> None:
    symbol = "Ψ"
    _write_claude_session(
        tmp_path,
        [_tool_input(f"MATCH {symbol * 800}", 1)],
    )

    result = _run_ch(
        tmp_path,
        "search",
        "MATCH",
        "--full",
        "--tools",
        "Bash:s=p",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    assert result.stdout.count(symbol) == 500 - PLACEHOLDER_LENGTH - len("MATCH ")


def test_global_progressive_shortening_uses_one_sequence_for_visible_messages(
    tmp_path: Path,
) -> None:
    symbols = ("¤", "§", "¶", "∆")
    session = _write_claude_session(
        tmp_path,
        [_assistant_text(symbol * SOURCE_LENGTH, index) for index, symbol in enumerate(symbols, 1)],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=128",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, list(zip(symbols, (8, 48, 88, 128), strict=True)))


def test_global_progressive_singleton_receives_the_full_limit(tmp_path: Path) -> None:
    symbol = "Ж"
    session = _write_claude_session(tmp_path, [_assistant_text(symbol * SOURCE_LENGTH, 1)])

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=128",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbol, 128)])


def test_short_qualifying_message_advances_the_progressive_sequence(tmp_path: Path) -> None:
    symbols = ("¤", "§", "¶", "∆")
    entries = [
        _assistant_text(symbols[0] * SOURCE_LENGTH, 1),
        _assistant_text("tiny", 2),
        _assistant_text(symbols[1] * SOURCE_LENGTH, 3),
        _assistant_text(symbols[2] * SOURCE_LENGTH, 4),
        _assistant_text(symbols[3] * SOURCE_LENGTH, 5),
    ]
    session = _write_claude_session(tmp_path, entries)

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=128",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, list(zip(symbols, (8, 68, 98, 128), strict=True)))
    assert "tiny" in result.stdout


def test_slice_recomputes_progressive_positions_after_message_selection(tmp_path: Path) -> None:
    symbols = ("¤", "§", "¶", "∆")
    session = _write_claude_session(
        tmp_path,
        [_assistant_text(symbol * SOURCE_LENGTH, index) for index, symbol in enumerate(symbols, 1)],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "2:4",
        "--short=p=128",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    assert result.stdout.count(symbols[0]) == 0
    assert result.stdout.count(symbols[3]) == 0
    _assert_symbol_lengths(result.stdout, [(symbols[1], 8), (symbols[2], 128)])


def test_progressive_limit_eight_shortens_every_qualifier_to_eight(tmp_path: Path) -> None:
    symbols = ("¤", "§", "¶")
    session = _write_claude_session(
        tmp_path,
        [_assistant_text(symbol * SOURCE_LENGTH, index) for index, symbol in enumerate(symbols, 1)],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=8",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbol, 8) for symbol in symbols])


def test_local_progressive_sequence_excludes_plain_fixed_and_hidden_messages(
    tmp_path: Path,
) -> None:
    progressive_symbols = ("¤", "§", "¶")
    fixed_symbol = "Ω"
    hidden_symbol = "Ψ"
    entries = [
        _tool_input(progressive_symbols[0] * SOURCE_LENGTH, 1),
        _assistant_text("plain assistant text", 2),
        _tool_input("tiny", 3),
        _tool_input(fixed_symbol * SOURCE_LENGTH, 4, name="Read"),
        _tool_input(hidden_symbol * SOURCE_LENGTH, 5, name="Write"),
        _tool_input(progressive_symbols[1] * SOURCE_LENGTH, 6),
        _tool_input(progressive_symbols[2] * SOURCE_LENGTH, 7),
    ]
    session = _write_claude_session(tmp_path, entries)

    result = _run_ch(
        tmp_path,
        str(session),
        "-t",
        "Bash:s=p=128",
        "-t",
        "Read",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(
        result.stdout,
        list(zip(progressive_symbols, (8, 88, 128), strict=True)),
    )
    assert result.stdout.count(fixed_symbol) == SOURCE_LENGTH
    assert result.stdout.count(hidden_symbol) == 0
    assert "plain assistant text" in result.stdout
    assert "tiny" in result.stdout


def test_multiple_progressive_tools_in_one_message_share_one_factor(tmp_path: Path) -> None:
    first_symbol = "¤"
    second_symbol = "§"
    fixed_symbol = "Ω"
    final_symbol = "¶"
    entries = [
        _tool_inputs(
            [
                ("Bash", first_symbol * SOURCE_LENGTH),
                ("Bash", second_symbol * SOURCE_LENGTH),
                ("Read", fixed_symbol * SOURCE_LENGTH),
            ],
            1,
        ),
        _tool_input(final_symbol * SOURCE_LENGTH, 2),
    ]
    session = _write_claude_session(tmp_path, entries)

    result = _run_ch(
        tmp_path,
        str(session),
        "-t",
        "Bash:s=p=128",
        "-t",
        "Read",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(
        result.stdout,
        [(first_symbol, 8), (second_symbol, 8), (final_symbol, 128)],
    )
    assert result.stdout.count(fixed_symbol) == SOURCE_LENGTH


def test_progressive_tool_limit_applies_to_each_string_leaf(tmp_path: Path) -> None:
    first_symbol = "Q"
    second_symbol = "Z"
    session = _write_claude_session(
        tmp_path,
        [
            _assistant_message(
                [
                    {
                        "type": "tool_use",
                        "id": "tool-custom",
                        "name": "Custom",
                        "input": {
                            "first": first_symbol * SOURCE_LENGTH,
                            "second": second_symbol * SOURCE_LENGTH,
                        },
                    }
                ],
                1,
            )
        ],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "-t",
        "Custom:s=p=32",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(first_symbol, 32), (second_symbol, 32)])


def test_bare_local_short_inherits_the_complete_global_progressive_policy(
    tmp_path: Path,
) -> None:
    symbols = ("¤", "§")
    session = _write_claude_session(
        tmp_path,
        [_tool_input(symbol * 800, index) for index, symbol in enumerate(symbols, 1)],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=64",
        "-t",
        "Bash:s",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbols[0], 8), (symbols[1], 64)], source_length=800)


def test_bare_local_short_without_global_short_remains_fixed_at_500(tmp_path: Path) -> None:
    symbols = ("¤", "§")
    session = _write_claude_session(
        tmp_path,
        [_tool_input(symbol * 800, index) for index, symbol in enumerate(symbols, 1)],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "-t",
        "Bash:s",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(result.stdout, [(symbol, 500) for symbol in symbols], source_length=800)


@pytest.mark.parametrize(
    ("global_short", "local_short", "expected_lengths"),
    [
        ("64", "s=progressive", (8, 64)),
        (None, "short=progressive", (8, 500)),
        ("p=128", "s=p=32", (8, 32)),
    ],
)
def test_local_progressive_policy_inherits_only_unspecified_global_fields(
    tmp_path: Path,
    global_short: str | None,
    local_short: str,
    expected_lengths: tuple[int, int],
) -> None:
    symbols = ("Ж", "Ф")
    session = _write_claude_session(
        tmp_path,
        [_tool_input(symbol * 800, index) for index, symbol in enumerate(symbols, 1)],
    )
    global_arguments = () if global_short is None else (f"--short={global_short}",)

    result = _run_ch(
        tmp_path,
        str(session),
        *global_arguments,
        "-t",
        f"Bash:{local_short}",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(
        result.stdout,
        list(zip(symbols, expected_lengths, strict=True)),
        source_length=800,
    )


def test_global_and_local_progressive_policies_share_a_message_union_sequence(
    tmp_path: Path,
) -> None:
    global_first = "¤"
    local_middle = "§"
    fixed_only = "Ω"
    global_last = "¶"
    local_last = "∆"
    entries = [
        _assistant_text(global_first * SOURCE_LENGTH, 1),
        _tool_input(local_middle * SOURCE_LENGTH, 2, name="Read"),
        _tool_input(fixed_only * SOURCE_LENGTH, 3),
        _assistant_message(
            [
                {"type": "text", "text": global_last * SOURCE_LENGTH},
                {
                    "type": "tool_use",
                    "id": "tool-last",
                    "name": "Read",
                    "input": {"file_path": local_last * SOURCE_LENGTH},
                },
            ],
            4,
        ),
    ]
    session = _write_claude_session(tmp_path, entries)

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=128",
        "-t",
        "s=p=64",
        "-t",
        "Bash:s=32",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(result)
    _assert_symbol_lengths(
        result.stdout,
        [
            (global_first, 8),
            (local_middle, 36),
            (fixed_only, 32),
            (global_last, 128),
            (local_last, 64),
        ],
    )


def test_all_renderers_use_the_same_progressive_lengths(tmp_path: Path) -> None:
    symbols = ("¤", "§", "¶", "∆")
    session = _write_claude_session(
        tmp_path,
        [_assistant_text(symbol * SOURCE_LENGTH, index) for index, symbol in enumerate(symbols, 1)],
    )
    renderer_arguments = (
        ("--format=xml", "--color=never"),
        ("--format=json", "--color=never"),
        ("--format=raw", "--color=never"),
        ("--format=xml", "--color=always", "--no-paging"),
    )

    results = [
        _run_ch(
            tmp_path,
            str(session),
            "--short=p=128",
            *arguments,
            "--no-metadata",
        )
        for arguments in renderer_arguments
    ]

    for result in results:
        _assert_success(result)
        _assert_symbol_lengths(
            result.stdout,
            list(zip(symbols, (8, 48, 88, 128), strict=True)),
        )


def test_progressive_shortening_does_not_shorten_metadata(tmp_path: Path) -> None:
    long_cwd = f"/tmp/{'metadata' * 40}"
    session = _write_claude_session(
        tmp_path,
        [_assistant_text("¤" * SOURCE_LENGTH, 1, cwd=long_cwd)],
    )

    result = _run_ch(
        tmp_path,
        str(session),
        "--short=p=32",
        "--color=never",
    )

    _assert_success(result)
    assert long_cwd in result.stderr


def test_search_assigns_positions_before_match_filtering_and_preserves_them_in_full_mode(
    tmp_path: Path,
) -> None:
    entries = [
        _assistant_text("first " + "¤" * SOURCE_LENGTH, 1),
        _assistant_text("MATCH " + "§" * SOURCE_LENGTH, 2),
        _assistant_text("third " + "¶" * SOURCE_LENGTH, 3),
        _assistant_text("MATCH " + "∆" * SOURCE_LENGTH, 4),
    ]
    _write_claude_session(tmp_path, entries)

    matches = _run_ch(
        tmp_path,
        "search",
        "MATCH",
        "--short=p=128",
        "--color=never",
        "--no-metadata",
    )
    full = _run_ch(
        tmp_path,
        "search",
        "MATCH",
        "--short=p=128",
        "--full",
        "--color=never",
        "--no-metadata",
    )

    _assert_success(matches)
    _assert_success(full)
    assert [len(body) for body in _assistant_bodies(matches.stdout)] == [48, 128]
    assert [len(body) for body in _assistant_bodies(full.stdout)] == [8, 48, 88, 128]
