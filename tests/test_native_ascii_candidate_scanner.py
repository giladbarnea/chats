from __future__ import annotations

import os
from pathlib import Path

import pytest

from chats.commands.search import _file_contains_ascii


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
