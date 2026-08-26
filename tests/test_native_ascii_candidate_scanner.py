from __future__ import annotations

import os
from pathlib import Path

import pytest

import chats.commands.search as search_commands
from chats.commands.search import (
    _file_contains_ascii,
    _file_contains_ascii_json_strings,
)


@pytest.mark.parametrize(
    ("content", "needle", "case_sensitive", "evidence_groups", "expected"),
    [
        pytest.param(b"prefix Exact suffix", b"Exact", True, (), True, id="exact"),
        pytest.param(b"prefix Exact suffix", b"exact", True, (), False, id="case-sensitive-miss"),
        pytest.param(b"prefix EXACT suffix", b"exact", False, (), True, id="ascii-lowercase"),
        pytest.param("unrelated café".encode(), b"absent", True, (), False, id="valid-unicode"),
        pytest.param(
            "unrelated café".encode(),
            b"absent",
            False,
            (),
            False,
            id="safe-unicode-continues",
        ),
        pytest.param(b"unrelated \xff bytes", b"absent", True, (), True, id="invalid-utf8"),
        pytest.param(b"unrelated \xff bytes", b"absent", False, (), True, id="invalid-utf8-insensitive"),
        pytest.param(b"incomplete \xf0\x9f\x98", b"absent", True, (), True, id="incomplete-utf8"),
        pytest.param(
            b"incomplete \xf0\x9f\x98",
            b"absent",
            False,
            (),
            True,
            id="incomplete-utf8-insensitive",
        ),
        pytest.param(
            b"first marker and later second marker",
            b"absent",
            True,
            ((b"first", b"second"),),
            True,
            id="complete-evidence-group",
        ),
        pytest.param(
            b"first marker only",
            b"absent",
            True,
            ((b"first", b"second"),),
            False,
            id="incomplete-evidence-group",
        ),
        pytest.param(
            b"UPPERCASE EVIDENCE",
            b"absent",
            False,
            ((b"uppercase", b"evidence"),),
            False,
            id="evidence-remains-exact",
        ),
        pytest.param(
            b"alternate marker",
            b"absent",
            True,
            ((b"missing",), (b"alternate",)),
            True,
            id="any-complete-evidence-group",
        ),
    ],
)
def test_native_ascii_candidate_scan_contract(
    tmp_path: Path,
    content: bytes,
    needle: bytes,
    case_sensitive: bool,
    evidence_groups: tuple[tuple[bytes, ...], ...],
    expected: bool,
) -> None:
    path = tmp_path / "candidate.bin"
    path.write_bytes(content)

    actual = _file_contains_ascii(
        path,
        needle,
        case_sensitive=case_sensitive,
        evidence_groups=evidence_groups,
    )

    assert actual is expected, (
        "Expected the native ASCII candidate scan to preserve the locked contract. "
        f"Got: {actual=!r}, {expected=!r}, {case_sensitive=!r}, "
        f"{needle=!r}, {evidence_groups=!r}"
    )


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b'{"content":"CLIENT_ID/CARD"}\n', id="raw-solidus"),
        pytest.param(b'{"content":"CLIENT_ID\\/CARD"}\n', id="short-escaped-solidus"),
        pytest.param(b'{"content":"CLIENT_ID\\u002fCARD"}\n', id="unicode-escaped-solidus"),
        pytest.param(
            b'{"content":"CL\\u0049ENT_ID\\u002fCA\\u0052D"}\n',
            id="mixed-query-character-escapes",
        ),
    ],
)
def test_logical_json_string_scan_matches_raw_and_escaped_characters(
    tmp_path: Path,
    content: bytes,
) -> None:
    path = tmp_path / "logical-match.jsonl"
    path.write_bytes(content)

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is True, (
        "Expected raw and escaped query characters to form one logical JSON "
        f"string match. Got: {actual=!r}, {content=!r}"
    )


def test_logical_json_string_batch_returns_decisions_in_input_order(
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"candidate-{index}.jsonl" for index in range(4)]
    contents = [
        b'{"content":"CLIENT_ID/CARD"}\n',
        b'{"content":"unrelated text"}\n',
        b'{"content":"CLIENT_ID\\u002fCARD"}\n',
        b'{"content":"invalid \xff bytes"}\n',
    ]
    for path, content in zip(paths, contents, strict=True):
        path.write_bytes(content)

    actual = search_commands._files_contain_ascii_json_strings(
        paths,
        b"client_id/card",
        pi_sessions=[False, False, False, False],
    )

    assert actual == [True, False, True, True], (
        "Expected one native batch decision per input path in input order, with "
        f"encoding uncertainty preserved as a survivor. Got: {actual=!r}"
    )


def test_logical_json_string_batch_keeps_pi_evidence_exact_and_per_path(
    tmp_path: Path,
) -> None:
    paths = [tmp_path / f"pi-evidence-{index}.jsonl" for index in range(3)]
    contents = [
        b'{"customType":"not-pi-user-agents"}\n',
        b'{"customType":"pi-user-agents"}\n',
        b'{"customType":"pi-user-agents"}\n',
    ]
    for path, content in zip(paths, contents, strict=True):
        path.write_bytes(content)

    actual = search_commands._files_contain_ascii_json_strings(
        paths,
        b"absent-query",
        pi_sessions=[True, True, False],
    )

    assert actual == [False, True, False], (
        "Expected the exact joined-Pi marker to defer only its aligned Pi path. "
        f"Got: {actual=!r}"
    )


def test_logical_json_escape_may_cross_the_one_mibibyte_read_boundary(
    tmp_path: Path,
) -> None:
    path = tmp_path / "split-logical-escape.jsonl"
    prefix = b'{"content":"'
    padding = b"x" * (1024 * 1024 - len(prefix) - 1)
    path.write_bytes(prefix + padding + b"\\u0043LIENT_ID/CARD\"}\n")

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is True, (
        "Expected an escape split after its backslash at the native read boundary "
        f"to remain one logical match. Got: {actual=!r}"
    )


def test_valid_surrogate_pair_may_cross_the_one_mibibyte_read_boundary(
    tmp_path: Path,
) -> None:
    path = tmp_path / "split-surrogate-pair.jsonl"
    prefix = b'{"content":"'
    padding = b"x" * (1024 * 1024 - len(prefix) - len(b"\\ud83d"))
    path.write_bytes(prefix + padding + b"\\ud83d\\ude00\"}\n")

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is False, (
        "Expected a valid surrogate pair split between native reads to remain "
        f"safe and unrelated. Got: {actual=!r}"
    )


def test_logical_match_does_not_cross_json_string_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "separate-strings.jsonl"
    path.write_text(
        '{"first":"CLIENT_ID/","second":"CARD"}\n',
        encoding="utf-8",
    )

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is False, (
        "Expected the logical matcher to reset between JSON strings. "
        f"Got: {actual=!r}"
    )


def test_valid_surrogate_pair_does_not_defer_an_unrelated_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "valid-surrogate-pair.jsonl"
    path.write_text('{"content":"unrelated \\ud83d\\ude00 text"}\n', encoding="utf-8")

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is False, (
        "Expected a valid surrogate pair to decode as one safe non-ASCII scalar, "
        f"not force semantic confirmation. Got: {actual=!r}"
    )


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b'{"content":"bad \\x escape"}\n', id="malformed-escape"),
        pytest.param(
            b'{"content":"bad \\ud83d scalar"}\n', id="unpaired-high-surrogate"
        ),
        pytest.param(
            b'{"content":"bad \\ude00 scalar"}\n', id="unpaired-low-surrogate"
        ),
    ],
)
def test_logical_json_malformed_escapes_reject_without_deferring(
    tmp_path: Path,
    content: bytes,
) -> None:
    path = tmp_path / "malformed-escape.jsonl"
    path.write_bytes(content)

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is False, (
        "Expected structurally invalid JSON-string escapes, whose lines cannot "
        f"parse into content, to fast-reject instead of deferring. Got: {actual=!r}, {content=!r}"
    )


def test_logical_json_invalid_utf8_still_defers_to_semantic_confirmation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid-utf8.jsonl"
    path.write_bytes(b'{"content":"invalid \xff bytes"}\n')

    actual = _file_contains_ascii_json_strings(path, b"client_id/card")

    assert actual is True, (
        "Expected undecodable byte sequences to preserve encoding uncertainty for "
        f"semantic confirmation. Got: {actual=!r}"
    )


@pytest.mark.parametrize(
    "content",
    [
        pytest.param('{"content":"unrelated K text"}\n'.encode(), id="raw"),
        pytest.param(b'{"content":"unrelated \\u212A text"}\n', id="unicode-escape"),
    ],
)
def test_logical_json_scan_defers_python_case_insensitive_risk_scalars(
    tmp_path: Path,
    content: bytes,
) -> None:
    path = tmp_path / "unicode-risk.jsonl"
    path.write_bytes(content)

    actual = _file_contains_ascii_json_strings(path, b"absent-ascii-needle")

    assert actual is True, (
        "Expected raw and escaped Python 3.14 case-insensitive risk scalars "
        f"to defer safely. Got: {actual=!r}, {content=!r}"
    )


_PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS = (
    "\u00df\u0130\u0131\u0149\u017f\u01f0"
    "\u1e96\u1e97\u1e98\u1e99\u1e9a\u1e9e\u212a"
    "\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06"
)


@pytest.mark.parametrize(
    "risk_character",
    _PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS,
    ids=lambda character: f"U+{ord(character):04X}",
)
def test_case_insensitive_scan_defers_python_ascii_match_risk_characters(
    tmp_path: Path,
    risk_character: str,
) -> None:
    path = tmp_path / "risk-character.jsonl"
    path.write_text(f"unrelated {risk_character} text", encoding="utf-8")

    actual = _file_contains_ascii(
        path,
        b"absent",
        case_sensitive=False,
    )

    assert actual is True, (
        "Expected Python 3.14 casefold or regex risk characters to require "
        f"semantic confirmation. Got: {actual=!r}, U+{ord(risk_character):04X}"
    )


@pytest.mark.parametrize(
    ("character", "expected"),
    [
        pytest.param("é", False, id="safe-unicode"),
        pytest.param("\u212a", True, id="casefold-risk"),
        pytest.param("\u0131", True, id="regex-risk"),
    ],
)
def test_unicode_risk_decision_survives_a_split_utf8_code_point(
    tmp_path: Path,
    character: str,
    expected: bool,
) -> None:
    path = tmp_path / "split-unicode.jsonl"
    path.write_bytes(b"x" * (1024 * 1024 - 1) + character.encode("utf-8"))

    actual = _file_contains_ascii(
        path,
        b"absent",
        case_sensitive=False,
    )

    assert actual is expected, (
        "Expected incremental UTF-8 classification to preserve the Python risk "
        f"decision across a read boundary. Got: {actual=!r}, {expected=!r}, "
        f"U+{ord(character):04X}"
    )


@pytest.mark.parametrize(
    ("content", "needle", "case_sensitive", "evidence_groups"),
    [
        pytest.param(
            b"x" * (1024 * 1024 - 3) + b"boundary",
            b"boundary",
            True,
            (),
            id="exact-needle",
        ),
        pytest.param(
            b"x" * (1024 * 1024 - 3) + b"BOUNDARY",
            b"boundary",
            False,
            (),
            id="lowercased-haystack",
        ),
        pytest.param(
            b"x" * (1024 * 1024 - 3) + b"evidence and later companion",
            b"absent",
            True,
            ((b"evidence", b"companion"),),
            id="evidence-member",
        ),
    ],
)
def test_candidate_matches_may_cross_the_one_mibibyte_read_boundary(
    tmp_path: Path,
    content: bytes,
    needle: bytes,
    case_sensitive: bool,
    evidence_groups: tuple[tuple[bytes, ...], ...],
) -> None:
    path = tmp_path / "boundary.bin"
    path.write_bytes(content)

    actual = _file_contains_ascii(
        path,
        needle,
        case_sensitive=case_sensitive,
        evidence_groups=evidence_groups,
    )

    assert actual is True, (
        "Expected a candidate split across the 1 MiB read boundary to match. "
        f"Got: {actual=!r}, {case_sensitive=!r}, {needle=!r}, "
        f"{evidence_groups=!r}"
    )


def test_empty_needle_does_not_open_the_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.bin"

    actual = _file_contains_ascii(
        missing_path,
        b"",
        case_sensitive=True,
    )

    assert actual is True, (
        "Expected an empty needle to pass without opening a missing path. "
        f"Got: {actual=!r}"
    )


def test_logical_json_candidate_file_errors_defer_to_semantic_reads(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.jsonl"

    actual = _file_contains_ascii_json_strings(missing_path, b"needle")

    assert actual is True, (
        "Expected native read errors to remain candidates so Path.read_text keeps "
        f"the public error contract. Got: {actual=!r}"
    )


def test_candidate_file_errors_propagate_as_os_errors(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.bin"
    with pytest.raises(OSError):
        _file_contains_ascii(
            missing_path,
            b"needle",
            case_sensitive=True,
        )

    unreadable_file = tmp_path / "directory"
    unreadable_file.mkdir()
    with pytest.raises(OSError):
        _file_contains_ascii(
            unreadable_file,
            b"needle",
            case_sensitive=True,
        )


@pytest.mark.skipif(
    os.name != "posix", reason="surrogate-escaped paths are POSIX-specific"
)
def test_surrogate_escaped_path_bytes_reach_the_native_boundary(tmp_path: Path) -> None:
    raw_path = os.fsencode(tmp_path) + b"/missing-\xff.bin"
    surrogate_path = Path(os.fsdecode(raw_path))

    with pytest.raises(OSError):
        _file_contains_ascii(
            surrogate_path,
            b"needle",
            case_sensitive=True,
        )
