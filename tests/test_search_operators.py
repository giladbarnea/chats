#!/usr/bin/env python3
"""Behavior tests for boolean `and`/`or` operators in search patterns."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import ConversationFlags, SearchOutputMode, commands


def _write_session(
    path: Path,
    message_texts: list[str],
    *,
    summary: str | None = None,
    timestamp: str = "2025-01-01T00:00:00Z",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if summary is not None:
        lines.append(
            json.dumps({
                "type": "summary",
                "summary": summary,
                "leafUuid": f"{path.stem}-leaf",
            })
        )
    lines.extend(
        json.dumps({
            "type": "user",
            "timestamp": timestamp,
            "cwd": "/tmp/search-operators",
            "message": {"role": "user", "content": text},
        })
        for text in message_texts
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _claude_session_path(home: Path, stem: str) -> Path:
    return home / ".claude" / "projects" / "proj" / f"{stem}.jsonl"


def _run_search_ids(pattern: str, capsys) -> tuple[int, list[str]]:
    """Run an only-id search and return (exit_code, matched session ids)."""
    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            pattern,
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )
    stdout = capsys.readouterr().out
    return exc_info.value.code, stdout.split()


def test_and_requires_both_terms_in_same_session(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A and B` matches sessions containing both terms, even in different messages."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "has-both"),
        ["first message with opname-alpha", "second message with opname-bravo"],
    )
    _write_session(
        _claude_session_path(home, "has-alpha-only"),
        ["only opname-alpha appears here"],
    )

    exit_code, matched_ids = _run_search_ids("opname-alpha and opname-bravo", capsys)

    assert exit_code == 0, (
        f"Expected `A and B` search to find the session with both terms. Got exit code: {exit_code}"
    )
    assert "has-both" in matched_ids, (
        "Expected the session containing both terms (across different messages) to match. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "has-alpha-only" not in matched_ids, (
        "Expected the session containing only one of the `and` terms not to match. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_or_matches_sessions_with_either_term(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A or B` matches sessions containing either term, and skips sessions with neither."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "has-alpha"), ["opname-alpha here"])
    _write_session(_claude_session_path(home, "has-bravo"), ["opname-bravo here"])
    _write_session(_claude_session_path(home, "has-neither"), ["nothing relevant"])

    exit_code, matched_ids = _run_search_ids("opname-alpha or opname-bravo", capsys)

    assert exit_code == 0, f"Expected `A or B` search to find matches. Got exit code: {exit_code}"
    assert "has-alpha" in matched_ids and "has-bravo" in matched_ids, (
        "Expected `A or B` to match sessions containing either term. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "has-neither" not in matched_ids, (
        f"Expected sessions with neither term not to match. Got matched ids: {matched_ids!r}"
    )


def test_and_displays_matching_messages_for_all_terms(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Default search output for `A and B` renders the messages matching each term."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "spread-terms"),
        [
            "alpha-needle lives in the first message",
            "an unrelated middle message",
            "bravo-needle lives in the last message",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "alpha-needle and bravo-needle",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.MATCHES,
            emit_metadata=False,
        )
    stdout = capsys.readouterr().out

    assert exc_info.value.code == 0, (
        f"Expected the search to succeed. Got exit code: {exc_info.value.code}"
    )
    assert "alpha-needle" in stdout and "bravo-needle" in stdout, (
        "Expected both terms' matching messages to be rendered for an `and` hit. "
        f"Got stdout:\n{stdout}"
    )
    assert "unrelated middle message" not in stdout, (
        "Expected non-matching messages to stay hidden in default matches output. "
        f"Got stdout:\n{stdout}"
    )


def test_quoted_multi_word_term_is_one_term(tmp_path: Path, monkeypatch, capsys) -> None:
    """`'"hello world" and foo'` treats the quoted phrase as one term."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "phrase-and-foo"),
        ["hello world appears here", "foo-needle appears here"],
    )
    _write_session(
        _claude_session_path(home, "words-split"),
        ["hello there", "world of foo-needle"],
    )

    exit_code, matched_ids = _run_search_ids('"hello world" and foo-needle', capsys)

    assert exit_code == 0, f"Expected the quoted-phrase search to succeed. Got exit code: {exit_code}"
    assert "phrase-and-foo" in matched_ids, (
        "Expected the session containing the exact phrase plus the second term to match. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "words-split" not in matched_ids, (
        "Expected the quoted phrase to match as one contiguous term, not as separate words. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_unquoted_multi_word_term_next_to_operator_is_invalid(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`hello world and foo` must error: operations require quoting multi-word terms."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(_claude_session_path(home, "any-session"), ["hello world and foo"])

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "hello world and foo",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )
    stderr = capsys.readouterr().err

    assert exc_info.value.code == 2, (
        "Expected an invalid boolean query to exit with code 2. "
        f"Got exit code: {exc_info.value.code}"
    )
    assert "quote" in stderr.casefold(), (
        f"Expected the error to tell the user to quote multi-word terms. Got stderr:\n{stderr}"
    )


def test_and_with_parenthesized_or_group(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A and (B or C)` requires A plus at least one of B/C in the session."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "alpha-and-charlie"),
        ["opname-alpha is here", "opname-charlie is here"],
    )
    _write_session(_claude_session_path(home, "alpha-alone"), ["opname-alpha is here"])
    _write_session(
        _claude_session_path(home, "bravo-and-charlie"),
        ["opname-bravo is here", "opname-charlie is here"],
    )

    exit_code, matched_ids = _run_search_ids(
        "opname-alpha and (opname-bravo or opname-charlie)", capsys
    )

    assert exit_code == 0, f"Expected the compound search to succeed. Got exit code: {exit_code}"
    assert "alpha-and-charlie" in matched_ids, (
        "Expected `A and (B or C)` to match a session containing A and C. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "alpha-alone" not in matched_ids, (
        "Expected a session with only A not to satisfy `A and (B or C)`. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "bravo-and-charlie" not in matched_ids, (
        "Expected a session without A not to satisfy `A and (B or C)`. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_three_term_and_chain(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A and B and C` requires all three terms in the session."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "all-three"),
        ["opname-alpha", "opname-bravo", "opname-charlie"],
    )
    _write_session(
        _claude_session_path(home, "two-of-three"),
        ["opname-alpha", "opname-bravo"],
    )

    exit_code, matched_ids = _run_search_ids(
        "opname-alpha and opname-bravo and opname-charlie", capsys
    )

    assert exit_code == 0, f"Expected the three-term search to succeed. Got exit code: {exit_code}"
    assert matched_ids == ["all-three"], (
        "Expected only the session containing all three `and` terms to match. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_three_term_or_chain(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A or B or C` matches a session containing any one term."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "charlie-only"), ["opname-charlie"])
    _write_session(_claude_session_path(home, "none-of-them"), ["something else"])

    exit_code, matched_ids = _run_search_ids(
        "opname-alpha or opname-bravo or opname-charlie", capsys
    )

    assert exit_code == 0, f"Expected the three-term or search to succeed. Got exit code: {exit_code}"
    assert matched_ids == ["charlie-only"], (
        "Expected `A or B or C` to match exactly the session containing one of the terms. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_or_and_precedence(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A or B and C` parses as `A or (B and C)`: and binds tighter than or."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "alpha-only"), ["opname-alpha"])
    _write_session(_claude_session_path(home, "bravo-only"), ["opname-bravo"])
    _write_session(
        _claude_session_path(home, "bravo-and-charlie"),
        ["opname-bravo", "opname-charlie"],
    )

    exit_code, matched_ids = _run_search_ids(
        "opname-alpha or opname-bravo and opname-charlie", capsys
    )

    assert exit_code == 0, f"Expected the precedence search to succeed. Got exit code: {exit_code}"
    assert "alpha-only" in matched_ids, (
        "Expected `A or B and C` to match a session containing only A. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "bravo-and-charlie" in matched_ids, (
        "Expected `A or B and C` to match a session containing B and C. "
        f"Got matched ids: {matched_ids!r}"
    )
    assert "bravo-only" not in matched_ids, (
        "Expected `A or B and C` not to match a session with only B (and binds tighter). "
        f"Got matched ids: {matched_ids!r}"
    )


def test_plain_multi_word_pattern_without_operators_stays_one_regex(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """`hello world` with no operators keeps matching as one contiguous pattern."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "contiguous"), ["say hello world today"])
    _write_session(
        _claude_session_path(home, "split-words"),
        ["hello there", "world over there"],
    )

    exit_code, matched_ids = _run_search_ids("hello world", capsys)

    assert exit_code == 0, f"Expected the plain search to succeed. Got exit code: {exit_code}"
    assert matched_ids == ["contiguous"], (
        "Expected a no-operator multi-word pattern to keep its existing single-regex "
        f"semantics. Got matched ids: {matched_ids!r}"
    )


def test_regex_pattern_with_parens_and_no_operators_stays_regex(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Parens without `and`/`or` keywords keep their regex meaning."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "regex-target"), ["deploy-prod happened"])

    exit_code, matched_ids = _run_search_ids("deploy-(prod|staging)", capsys)

    assert exit_code == 0, f"Expected the regex search to succeed. Got exit code: {exit_code}"
    assert matched_ids == ["regex-target"], (
        "Expected a parenthesized regex with no boolean operators to be treated as one "
        f"regex pattern. Got matched ids: {matched_ids!r}"
    )


def test_and_term_satisfied_by_summary_facet(tmp_path: Path, monkeypatch, capsys) -> None:
    """An `and` term satisfied only by the session summary still counts."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "summary-carries-term"),
        ["opname-bravo lives in a message"],
        summary="summary mentions opname-alpha",
    )

    exit_code, matched_ids = _run_search_ids("opname-alpha and opname-bravo", capsys)

    assert exit_code == 0, (
        f"Expected the summary facet to satisfy one `and` term. Got exit code: {exit_code}"
    )
    assert matched_ids == ["summary-carries-term"], (
        "Expected a session whose summary satisfies one term and whose message satisfies "
        f"the other to match `A and B`. Got matched ids: {matched_ids!r}"
    )


def test_dangling_operator_is_invalid(tmp_path: Path, monkeypatch, capsys) -> None:
    """`foo and` must error instead of silently degrading."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(_claude_session_path(home, "any-session"), ["foo and"])

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "foo and",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )
    capsys.readouterr()

    assert exc_info.value.code == 2, (
        f"Expected a dangling operator to exit with code 2. Got exit code: {exc_info.value.code}"
    )


def test_bare_operator_word_is_a_plain_pattern(tmp_path: Path, monkeypatch, capsys) -> None:
    """Searching for just `and` has no operands, so it stays a literal search."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "contains-word"), ["bread and butter"])

    exit_code, matched_ids = _run_search_ids("and", capsys)

    assert exit_code == 0, (
        f"Expected a bare `and` pattern to behave as a literal search. Got exit code: {exit_code}"
    )
    assert matched_ids == ["contains-word"], (
        "Expected `and` with no operand terms to match sessions containing the word. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_not_excludes_sessions_matching_negated_term(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A NOT B` matches sessions containing A that do not contain B anywhere."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "has-alpha-only"),
        ["opname-alpha lives here"],
    )
    _write_session(
        _claude_session_path(home, "has-both"),
        ["opname-alpha here", "opname-bravo here"],
    )
    _write_session(
        _claude_session_path(home, "has-neither"),
        ["nothing relevant"],
    )

    exit_code, matched_ids = _run_search_ids("opname-alpha NOT opname-bravo", capsys)

    assert exit_code == 0, (
        f"Expected `A NOT B` search to find the session with A but not B. Got exit code: {exit_code}"
    )
    assert matched_ids == ["has-alpha-only"], (
        "Expected only the session containing A but not B to match `A NOT B`. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_multiple_nots_exclude_all_negated_terms(tmp_path: Path, monkeypatch, capsys) -> None:
    """`A NOT B NOT C` matches sessions with A that contain neither B nor C."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "alpha-only"),
        ["opname-alpha here"],
    )
    _write_session(
        _claude_session_path(home, "alpha-and-bravo"),
        ["opname-alpha", "opname-bravo"],
    )
    _write_session(
        _claude_session_path(home, "alpha-and-charlie"),
        ["opname-alpha", "opname-charlie"],
    )

    exit_code, matched_ids = _run_search_ids(
        "opname-alpha NOT opname-bravo NOT opname-charlie", capsys
    )

    assert exit_code == 0, (
        f"Expected `A NOT B NOT C` to find the session with only A. Got exit code: {exit_code}"
    )
    assert matched_ids == ["alpha-only"], (
        "Expected only the session containing A without B or C to match. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_not_with_quoted_multi_word_terms(tmp_path: Path, monkeypatch, capsys) -> None:
    """`'"hello world" NOT "goodbye earth"'` treats quoted phrases as terms."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "has-hello-only"),
        ["hello world is great"],
    )
    _write_session(
        _claude_session_path(home, "has-both-phrases"),
        ["hello world", "goodbye earth"],
    )

    exit_code, matched_ids = _run_search_ids(
        '"hello world" NOT "goodbye earth"', capsys
    )

    assert exit_code == 0, (
        f"Expected quoted-phrase NOT to find a match. Got exit code: {exit_code}"
    )
    assert matched_ids == ["has-hello-only"], (
        "Expected only the session with the positive phrase but not the negated phrase. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_mixing_not_with_and_or_is_invalid(tmp_path: Path, monkeypatch, capsys) -> None:
    """Queries combining NOT with AND or OR must error with exit code 2."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(_claude_session_path(home, "any-session"), ["alpha bravo charlie"])

    mixed_patterns = [
        "alpha AND bravo NOT charlie",
        "alpha NOT bravo OR charlie",
        "alpha OR bravo NOT charlie",
        "alpha NOT bravo AND charlie",
    ]
    for pattern in mixed_patterns:
        with pytest.raises(SystemExit) as exc_info:
            commands.cmd_search(
                pattern,
                ConversationFlags(color="never", paging=False),
                output_mode=SearchOutputMode.ONLY_ID,
                emit_metadata=True,
            )
        stderr = capsys.readouterr().err
        assert exc_info.value.code == 2, (
            f"Expected {pattern!r} to exit with code 2 (mixed operators). "
            f"Got exit code: {exc_info.value.code}"
        )
        assert "not" in stderr.casefold(), (
            f"Expected the error for {pattern!r} to mention NOT. Got stderr:\n{stderr}"
        )


def test_not_excludes_when_negated_term_in_summary(tmp_path: Path, monkeypatch, capsys) -> None:
    """A NOT term satisfied only by the session summary still causes exclusion."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "summary-has-excluded"),
        ["opname-alpha in message"],
        summary="summary mentions opname-bravo",
    )
    _write_session(
        _claude_session_path(home, "clean-session"),
        ["opname-alpha in message"],
        summary="unrelated summary",
    )

    exit_code, matched_ids = _run_search_ids("opname-alpha NOT opname-bravo", capsys)

    assert exit_code == 0, (
        f"Expected the clean session to match. Got exit code: {exit_code}"
    )
    assert matched_ids == ["clean-session"], (
        "Expected the session whose summary contains the negated term to be excluded. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_bare_not_is_a_plain_pattern(tmp_path: Path, monkeypatch, capsys) -> None:
    """Searching for just `not` has no operands, so it stays a literal search."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(_claude_session_path(home, "contains-word"), ["this is not working"])

    exit_code, matched_ids = _run_search_ids("not", capsys)

    assert exit_code == 0, (
        f"Expected a bare `not` pattern to behave as a literal search. Got exit code: {exit_code}"
    )
    assert matched_ids == ["contains-word"], (
        "Expected `not` with no operand terms to match sessions containing the word. "
        f"Got matched ids: {matched_ids!r}"
    )


def test_dangling_not_is_invalid(tmp_path: Path, monkeypatch, capsys) -> None:
    """`foo NOT` must error instead of silently degrading."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    _write_session(_claude_session_path(home, "any-session"), ["foo bar"])

    with pytest.raises(SystemExit) as exc_info:
        commands.cmd_search(
            "foo NOT",
            ConversationFlags(color="never", paging=False),
            output_mode=SearchOutputMode.ONLY_ID,
            emit_metadata=True,
        )
    capsys.readouterr()

    assert exc_info.value.code == 2, (
        f"Expected a dangling NOT to exit with code 2. Got exit code: {exc_info.value.code}"
    )


def test_all_operators_are_case_insensitive(tmp_path: Path, monkeypatch, capsys) -> None:
    """`and`/`or` operators have identical lowercase and uppercase semantics."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)

    _write_session(
        _claude_session_path(home, "has-both"),
        ["case-alpha", "case-bravo"],
    )
    _write_session(
        _claude_session_path(home, "has-alpha-only"),
        ["case-alpha"],
    )

    expectations = {
        "case-alpha and case-bravo": {"has-both"},
        "case-alpha AND case-bravo": {"has-both"},
        "case-alpha or case-bravo": {"has-both", "has-alpha-only"},
        "case-alpha OR case-bravo": {"has-both", "has-alpha-only"},
        "case-alpha not case-bravo": {"has-alpha-only"},
        "case-alpha NOT case-bravo": {"has-alpha-only"},
    }
    for pattern, expected_ids in expectations.items():
        exit_code, matched_ids = _run_search_ids(pattern, capsys)
        assert exit_code == 0, (
            f"Expected {pattern!r} to use boolean operator semantics. "
            f"Got exit code: {exit_code}"
        )
        assert set(matched_ids) == expected_ids, (
            f"Expected {pattern!r} to match {expected_ids!r}. "
            f"Got matched ids: {matched_ids!r}"
        )
