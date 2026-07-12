"""Boolean `and`/`or` search-query parsing for `ch search` patterns.

A pattern with no bare `and`/`or` word tokens (in any letter case) stays one
verbatim regex term (existing behavior). Once an operator appears, every
multi-word or regex-shaped term must be quoted, e.g. `'"hello world" and foo'`.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterator
from typing import Literal

_REGEX_META_CHARACTERS = frozenset(".^$*+?{}[]\\|()")
_QUOTE_CHARACTERS = ('"', "'")

_TokenKind = Literal["term", "and", "or", "lparen", "rparen"]


class SearchQueryError(ValueError):
    """Raised when a pattern contains operators but is not a valid boolean query."""


@dataclasses.dataclass(frozen=True)
class SearchTerm:
    """One leaf pattern compiled with the standard search regex semantics."""

    pattern: str
    regex: re.Pattern[str]
    literal_candidate: str | None

    def evaluate(self, term_matches: Callable[[SearchTerm], bool]) -> bool:
        return term_matches(self)

    def iter_terms(self) -> Iterator[SearchTerm]:
        yield self


@dataclasses.dataclass(frozen=True)
class AndQuery:
    operands: tuple[SearchQuery, ...]

    def evaluate(self, term_matches: Callable[[SearchTerm], bool]) -> bool:
        return all(operand.evaluate(term_matches) for operand in self.operands)

    def iter_terms(self) -> Iterator[SearchTerm]:
        for operand in self.operands:
            yield from operand.iter_terms()


@dataclasses.dataclass(frozen=True)
class OrQuery:
    operands: tuple[SearchQuery, ...]

    def evaluate(self, term_matches: Callable[[SearchTerm], bool]) -> bool:
        return any(operand.evaluate(term_matches) for operand in self.operands)

    def iter_terms(self) -> Iterator[SearchTerm]:
        for operand in self.operands:
            yield from operand.iter_terms()


SearchQuery = SearchTerm | AndQuery | OrQuery


def compile_search_term(pattern: str) -> SearchTerm:
    """Compile one pattern with regex-or-literal fallback search semantics."""
    flags = re.IGNORECASE | re.MULTILINE | re.DOTALL
    try:
        regex = re.compile(pattern, flags)
        literal_candidate = (
            pattern.casefold() if _is_plain_literal_search_pattern(pattern) else None
        )
    except re.error:
        regex = re.compile(re.escape(pattern), flags)
        literal_candidate = pattern.casefold()
    return SearchTerm(
        pattern=pattern, regex=regex, literal_candidate=literal_candidate
    )


def parse_search_query(pattern_arg: str) -> SearchQuery:
    """Parse a search pattern into a boolean query tree.

    Raises SearchQueryError when operators are present but the query is malformed.
    """
    tokens = _tokenize(pattern_arg)
    if tokens is None:
        return compile_search_term(pattern_arg)
    has_operator = any(token.kind in ("and", "or") for token in tokens)
    has_operand = any(token.kind not in ("and", "or") for token in tokens)
    if not (has_operator and has_operand):
        return compile_search_term(pattern_arg)
    return _Parser(tokens).parse()


def _is_plain_literal_search_pattern(pattern: str) -> bool:
    """Return True when a search pattern contains no regex metacharacters.

    >>> _is_plain_literal_search_pattern("hello world")
    True
    >>> _is_plain_literal_search_pattern("implement.*feature")
    False
    """
    return not any(character in _REGEX_META_CHARACTERS for character in pattern)


@dataclasses.dataclass(frozen=True)
class _Token:
    kind: _TokenKind
    text: str


def _tokenize(pattern: str) -> list[_Token] | None:
    """Split a pattern into terms, operators, and parens.

    Quotes only open a term at a token boundary, so mid-word apostrophes
    (`don't panic`) stay plain words. Returns None for unterminated quotes,
    which sends the whole pattern down the single-term path.
    """
    tokens: list[_Token] = []
    position = 0
    while position < len(pattern):
        character = pattern[position]
        if character.isspace():
            position += 1
            continue
        if character in "()":
            kind = "lparen" if character == "(" else "rparen"
            tokens.append(_Token(kind, character))
            position += 1
            continue
        if character in _QUOTE_CHARACTERS:
            closing = pattern.find(character, position + 1)
            if closing == -1:
                return None
            tokens.append(_Token("term", pattern[position + 1 : closing]))
            position = closing + 1
            continue
        start = position
        while (
            position < len(pattern)
            and not pattern[position].isspace()
            and pattern[position] not in "()"
        ):
            position += 1
        word = pattern[start:position]
        normalized_word = word.casefold()
        kind = normalized_word if normalized_word in ("and", "or") else "term"
        tokens.append(_Token(kind, word))
    return tokens


class _Parser:
    """Recursive-descent parser: `or` over `and` over terms and parenthesized groups."""

    def __init__(self, tokens: list[_Token]) -> None:
        self.tokens = tokens
        self.position = 0

    def parse(self) -> SearchQuery:
        query = self._parse_or()
        if self.position != len(self.tokens):
            leftover = self.tokens[self.position]
            if leftover.kind == "term":
                raise SearchQueryError(
                    f"Invalid search query: unexpected term {leftover.text!r}. "
                    "Quote multi-word terms, e.g. '\"hello world\" and foo'."
                )
            raise SearchQueryError(
                f"Invalid search query: unexpected {leftover.text!r}."
            )
        return query

    def _parse_or(self) -> SearchQuery:
        operands = [self._parse_and()]
        while self._peek_kind() == "or":
            self.position += 1
            operands.append(self._parse_and())
        return operands[0] if len(operands) == 1 else OrQuery(tuple(operands))

    def _parse_and(self) -> SearchQuery:
        operands = [self._parse_atom()]
        while self._peek_kind() == "and":
            self.position += 1
            operands.append(self._parse_atom())
        return operands[0] if len(operands) == 1 else AndQuery(tuple(operands))

    def _parse_atom(self) -> SearchQuery:
        token = self.tokens[self.position] if self.position < len(self.tokens) else None
        if token is None:
            raise SearchQueryError(
                "Invalid search query: expected a term, got end of pattern."
            )
        if token.kind == "lparen":
            self.position += 1
            group = self._parse_or()
            if self._peek_kind() != "rparen":
                raise SearchQueryError("Invalid search query: missing closing ')'.")
            self.position += 1
            return group
        if token.kind == "term":
            if not token.text:
                raise SearchQueryError("Invalid search query: empty quoted term.")
            self.position += 1
            return compile_search_term(token.text)
        raise SearchQueryError(
            f"Invalid search query: expected a term, got {token.text!r}."
        )

    def _peek_kind(self) -> _TokenKind | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position].kind
