from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

import chats.parsing as parsing


def test_last_jsonl_timestamp_returns_the_newest_in_band_time_in_local_time(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        "".join(
            json.dumps({"timestamp": timestamp}) + "\n"
            for timestamp in (
                "2026-08-19T08:00:00Z",
                "2026-08-19T09:00:00+00:00",
            )
        ),
        encoding="utf-8",
    )
    expected = (
        datetime.fromisoformat("2026-08-19T09:00:00+00:00")
        .astimezone()
        .replace(tzinfo=None)
    )

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == expected, (
        "Expected the newest in-band timestamp converted to naive local time. "
        f"Got: {actual!r}"
    )


def test_lone_escaped_surrogate_in_unrelated_data_keeps_the_line_parseable(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        "".join([
            '{"timestamp":"2026-08-19T08:00:00Z"}\n',
            '{"payload":"\\ud800","timestamp":"2026-08-19T17:00:00Z"}\n',
        ]),
        encoding="utf-8",
    )
    expected = (
        datetime.fromisoformat("2026-08-19T17:00:00+00:00")
        .astimezone()
        .replace(tzinfo=None)
    )

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == expected, (
        "Expected a lone escaped surrogate in unrelated data to remain parseable. "
        f"Got: {actual!r}"
    )


def test_lone_surrogate_timestamp_remains_the_raw_winner(tmp_path: Path) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        "".join([
            '{"timestamp":"2026-08-19T08:00:00Z"}\n',
            '{"timestamp":"\\ud800"}\n',
        ]),
        encoding="utf-8",
    )
    mtime = 1_700_000_000
    os.utime(session_path, (mtime, mtime))

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == datetime.fromtimestamp(mtime), (
        "Expected the lone surrogate timestamp to win raw scanning, then use mtime. "
        f"Got: {actual!r}"
    )


def test_active_python_integer_digit_limit_aborts_to_file_mtime(tmp_path: Path) -> None:
    digit_limit = sys.get_int_max_str_digits()
    assert digit_limit > 0, "Expected the project interpreter integer limit to be active."
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        "".join([
            '{"timestamp":"2026-08-19T08:00:00Z"}\n',
            '{"metric":'
            + "1" * (digit_limit + 1)
            + ',"timestamp":"2026-08-19T18:00:00Z"}\n',
        ]),
        encoding="utf-8",
    )
    mtime = 1_700_000_000
    os.utime(session_path, (mtime, mtime))

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == datetime.fromtimestamp(mtime), (
        "Expected Python's active integer digit limit to abort scanning to mtime. "
        f"Got: {actual!r}"
    )


def test_malformed_non_finite_substring_does_not_hide_an_older_timestamp(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        "".join([
            '{"timestamp":"2026-08-19T08:00:00Z"}\n',
            '{"metric":2NaN,"timestamp":"2026-08-19T15:00:00Z"}\n',
        ]),
        encoding="utf-8",
    )
    expected = (
        datetime.fromisoformat("2026-08-19T08:00:00+00:00")
        .astimezone()
        .replace(tzinfo=None)
    )

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == expected, (
        "Expected malformed 2NaN to be skipped without hiding the older timestamp. "
        f"Got: {actual!r}"
    )


@pytest.mark.parametrize(
    "tail",
    [
        '{"timestamp":"not-iso"}',
        '["valid JSON but not an object"]',
    ],
)
def test_last_jsonl_timestamp_falls_back_to_file_mtime(
    tmp_path: Path,
    tail: str,
) -> None:
    session_path = tmp_path / "session.jsonl"
    session_path.write_text(
        '{"timestamp":"2026-08-19T08:00:00Z"}\n' + tail + "\n",
        encoding="utf-8",
    )
    mtime = 1_700_000_000
    os.utime(session_path, (mtime, mtime))

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == datetime.fromtimestamp(mtime), (
        "Expected an invalid raw winner or a non-object entry to use file mtime. "
        f"Got: {actual!r}"
    )


def test_last_jsonl_timestamp_handles_a_multi_megabyte_whitespace_wrapped_line(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "session.jsonl"
    newest_entry = json.dumps({
        "payload": "x" * 3_752_303,
        "timestamp": "2026-08-19T19:00:00Z",
    })
    session_path.write_text(
        '{"timestamp":"2026-08-19T08:00:00Z"}\n'
        + "\v\f"
        + newest_entry
        + "\v\f\n",
        encoding="utf-8",
    )
    expected = (
        datetime.fromisoformat("2026-08-19T19:00:00+00:00")
        .astimezone()
        .replace(tzinfo=None)
    )

    actual = parsing.get_jsonl_last_timestamp(session_path)

    assert actual == expected, (
        "Expected linear cross-chunk assembly and Python byte-whitespace trimming. "
        f"Got: {actual!r}"
    )


def test_last_jsonl_timestamp_returns_none_for_a_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"

    actual = parsing.get_jsonl_last_timestamp(missing_path)

    assert actual is None, f"Expected no timestamp for a missing file. Got: {actual!r}"
