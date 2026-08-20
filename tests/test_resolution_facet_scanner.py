from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import chats.parsing as parsing


def test_resolution_facets_preserve_universal_newlines_and_missing_final_newline(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_bytes(
        b' {"type":"summary","summary":"lf"}\n'
        b'{"type":"custom-title","customTitle":" old "}\r\n'
        b'{"type":"summary","summary":"crlf"}\r'
        b'{"type":"session_info","name":" new pi "}\r'
        b'{"type":"summary","summary":"final"}'
    )

    actual = parsing.extract_resolution_facets_from_jsonl(session_path)

    assert actual == ("new pi", ["lf", "crlf", "final"]), (
        "Expected LF, CRLF, lone CR, and an unterminated final line to preserve "
        f"file-order facets. Got: {actual!r}"
    )


def test_resolution_facets_preserve_title_and_summary_semantics(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    entries = [
        '{"type":"summary","summary":"  keep exactly  "}',
        '{"type":"message","payload":"\\\"summary\\\" marker only"}',
        '{"type":"summary","summary":"duplicate"}',
        '{"type":"summary","summary":"duplicate"}',
        '{"type":"summary","summary":""}',
        '{"type":"summary","summary":7}',
        '{"type":"summary","summary":"malformed"',
        '{"type":"custom-title","customTitle":" claude title "}',
        '{"type":"session_info","name":" pi title "}',
        (
            '{"type":"event_msg","payload":'
            '{"type":"thread_name_updated","thread_name":" codex title "}}'
        ),
        '{"type":"custom-title","customTitle":"   "}',
        '{"type":"summary","summary":"\\ud800"}',
        '{"type":"summary","metric":NaN,"summary":"non-finite"}',
        '["summary", "valid non-object"]',
    ]
    session_path.write_text("\n".join(entries), encoding="utf-8")

    actual = parsing.extract_resolution_facets_from_jsonl(session_path)

    assert actual == (
        "codex title",
        ["  keep exactly  ", "duplicate", "duplicate", "\ud800", "non-finite"],
    ), (
        "Expected provider title rules, later-title replacement, preserved summary "
        f"text and duplicates, and Python JSON edge semantics. Got: {actual!r}"
    )


def test_resolution_facets_validate_utf8_before_the_marker_gate(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_bytes(
        b'{"type":"summary","summary":"before invalid bytes"}\n'
        b'{"type":"message","payload":"\xff"}\n'
    )

    with pytest.raises(UnicodeDecodeError):
        parsing.extract_resolution_facets_from_jsonl(session_path)


def test_resolution_facets_propagate_non_json_callback_errors(
    tmp_path: Path,
) -> None:
    digit_limit = sys.get_int_max_str_digits()
    assert digit_limit > 0, "Expected the Python integer-string limit to be active."
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        '{"type":"summary","metric":'
        + "1" * (digit_limit + 1)
        + ',"summary":"blocked"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="limit"):
        parsing.extract_resolution_facets_from_jsonl(session_path)


def test_resolution_facets_handle_chunk_boundaries_and_oversized_lines(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    summary_line = b'{"type":"summary","summary":"boundary summary"}'
    summary_line += b" " * (4095 - len(summary_line))
    marker_start = 4 * 4096 - 5
    payload_prefix = b'{"payload":"'
    type_prefix = b'","type":'
    payload_length = marker_start - len(payload_prefix) - len(type_prefix)
    large_prefix = payload_prefix + b"x" * payload_length + type_prefix
    assert len(large_prefix) == marker_start, (
        "Expected the title marker to start at the intended chunk boundary. "
        f"Got: {len(large_prefix)}"
    )
    title_line = large_prefix + b'"custom-title","customTitle":"large title"}'
    session_path.write_bytes(summary_line + b"\r\n" + title_line)

    actual = parsing.extract_resolution_facets_from_jsonl(session_path)

    assert actual == ("large title", ["boundary summary"]), (
        "Expected CRLF and a facet marker split across fixed chunks to preserve "
        f"an oversized physical line. Got: {actual!r}"
    )


def test_resolution_facets_return_empty_for_open_and_read_errors(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.jsonl"
    directory_path = tmp_path / "directory.jsonl"
    directory_path.mkdir()
    surrogate_path = Path(os.fsdecode(os.fsencode(tmp_path) + b"/missing-\xff.jsonl"))

    actual = [
        parsing.extract_resolution_facets_from_jsonl(path)
        for path in (missing_path, directory_path, surrogate_path)
    ]

    assert actual == [(None, []), (None, []), (None, [])], (
        "Expected open failures, read failures, and surrogate-escaped missing paths "
        f"to return empty facets. Got: {actual!r}"
    )
