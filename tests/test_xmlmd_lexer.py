"""Tests for the XmlmdLexer Pygments lexer.

Verifies:
1. Complete tokenization — concatenating token values reproduces the input exactly.
2. No error tokens emitted for valid xmlmd input.
3. Correct token types for each structural element.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pygments.token import Generic, Literal, Name, Punctuation, Text, Token

from chats.lexer import XmlmdLexer

# ── helpers ──────────────────────────────────────────────────────────────────


def get_tokens(text: str) -> list[tuple[Token, str]]:
    return list(XmlmdLexer().get_tokens(text))


def token_types(text: str) -> list[Token]:
    return [t for t, _ in get_tokens(text)]


def values_for_type(text: str, token_type: Token) -> list[str]:
    return [v for t, v in get_tokens(text) if t is token_type]


def joined(text: str) -> str:
    return "".join(v for _, v in get_tokens(text))


# ── minimal fixtures ──────────────────────────────────────────────────────────

MINIMAL_SINGLE_MESSAGE = """\
---
session_id: abc123
provider: claude
---
<user-message i="1">
## User

Hello world
</user-message>
"""

MINIMAL_TWO_MESSAGES = """\
---
session_id: abc123
---
<user-message i="1">
## User

Hello

</user-message>

---

<assistant-response i="2">
## Assistant

Response here
</assistant-response>
"""

INTERNAL_XML_TAG = """\
---
session_id: abc
---
<user-message i="3" isMeta="true">
## User

<local-command-caveat>Caveat text here.</local-command-caveat>
</user-message>
"""

ATTR_WITH_ANGLE_BRACKETS = """\
---
session_id: abc
---
<assistant-response i="2" model="<synthetic>">
## Assistant

Not logged in
</assistant-response>
"""

LITERAL_LESS_THAN_TEXT = """\
---
session_id: abc
---
<user-message i="4">
## User

a<b
git add <file>...
1 <= 2
</user-message>
"""

# ── tracer bullet: completeness ───────────────────────────────────────────────


def test_tokenizes_single_message_completely() -> None:
    """Concatenating all token values must reproduce the input exactly."""
    result = joined(MINIMAL_SINGLE_MESSAGE)
    assert result == MINIMAL_SINGLE_MESSAGE, (
        f"Token values do not reproduce input.\n"
        f"Expected: {MINIMAL_SINGLE_MESSAGE!r}\n"
        f"Got:      {result!r}"
    )


# ── no error tokens ───────────────────────────────────────────────────────────


def test_no_error_tokens_single_message() -> None:
    errors = [(t, v) for t, v in get_tokens(MINIMAL_SINGLE_MESSAGE) if t is Token.Error]
    assert not errors, f"Unexpected error tokens: {errors}"


def test_no_error_tokens_two_messages() -> None:
    errors = [(t, v) for t, v in get_tokens(MINIMAL_TWO_MESSAGES) if t is Token.Error]
    assert not errors, f"Unexpected error tokens: {errors}"


def test_no_error_tokens_internal_xml() -> None:
    errors = [(t, v) for t, v in get_tokens(INTERNAL_XML_TAG) if t is Token.Error]
    assert not errors, f"Unexpected error tokens: {errors}"


def test_no_error_tokens_attr_angle_brackets() -> None:
    errors = [(t, v) for t, v in get_tokens(ATTR_WITH_ANGLE_BRACKETS) if t is Token.Error]
    assert not errors, f"Unexpected error tokens: {errors}"


def test_no_error_tokens_literal_less_than_text() -> None:
    errors = [(t, v) for t, v in get_tokens(LITERAL_LESS_THAN_TEXT) if t is Token.Error]
    assert not errors, f"Unexpected error tokens: {errors}"


# ── frontmatter ───────────────────────────────────────────────────────────────


def test_frontmatter_fence_is_punctuation() -> None:
    types = token_types(MINIMAL_SINGLE_MESSAGE)
    assert types[0] is Punctuation, (
        f"Expected opening frontmatter '---' to be Punctuation, got {types[0]}"
    )


def test_frontmatter_keys_are_name_attribute() -> None:
    keys = values_for_type(MINIMAL_SINGLE_MESSAGE, Name.Attribute)
    assert "session_id" in keys, (
        f"Expected 'session_id' to be tokenized as Name.Attribute. Got: {keys}"
    )
    assert "provider" in keys, (
        f"Expected 'provider' to be tokenized as Name.Attribute. Got: {keys}"
    )


def test_frontmatter_values_are_literal_string() -> None:
    values = values_for_type(MINIMAL_SINGLE_MESSAGE, Literal.String)
    assert "abc123" in values, (
        f"Expected 'abc123' to be tokenized as Literal.String. Got: {values}"
    )
    assert "claude" in values, (
        f"Expected 'claude' to be tokenized as Literal.String. Got: {values}"
    )


# ── outer wrapper tags ────────────────────────────────────────────────────────


def test_outer_tag_name_is_name_tag() -> None:
    tag_names = values_for_type(MINIMAL_SINGLE_MESSAGE, Name.Tag)
    assert "user-message" in tag_names, (
        f"Expected 'user-message' to be tokenized as Name.Tag. Got: {tag_names}"
    )


def test_outer_tag_attr_name_is_name_attribute() -> None:
    attr_names = values_for_type(MINIMAL_SINGLE_MESSAGE, Name.Attribute)
    assert "i" in attr_names, (
        f"Expected 'i' to be tokenized as Name.Attribute. Got: {attr_names}"
    )


def test_outer_tag_attr_value_is_literal_string() -> None:
    values = values_for_type(MINIMAL_SINGLE_MESSAGE, Literal.String)
    assert "1" in values, (
        f"Expected attribute value '1' (from i=\"1\") to be Literal.String. Got: {values}"
    )


def test_closing_outer_tag_name_is_name_tag() -> None:
    tag_names = values_for_type(MINIMAL_SINGLE_MESSAGE, Name.Tag)
    count = tag_names.count("user-message")
    assert count == 2, (
        f"Expected 'user-message' to appear twice (open+close). Got {count} times in {tag_names}"
    )


# ── role header ───────────────────────────────────────────────────────────────


def test_role_header_is_generic_heading() -> None:
    headings = values_for_type(MINIMAL_SINGLE_MESSAGE, Generic.Heading)
    assert any("User" in h for h in headings), (
        f"Expected '## User' line to be tokenized as Generic.Heading. Got: {headings}"
    )


def test_assistant_role_header_is_generic_heading() -> None:
    headings = values_for_type(MINIMAL_TWO_MESSAGES, Generic.Heading)
    assert any("Assistant" in h for h in headings), (
        f"Expected '## Assistant' line to be Generic.Heading. Got: {headings}"
    )


# ── message separator ─────────────────────────────────────────────────────────


def test_two_messages_tokenize_completely() -> None:
    result = joined(MINIMAL_TWO_MESSAGES)
    assert result == MINIMAL_TWO_MESSAGES, (
        f"Token values do not reproduce two-message input.\n"
        f"Expected: {MINIMAL_TWO_MESSAGES!r}\n"
        f"Got:      {result!r}"
    )


# ── internal xml tags ─────────────────────────────────────────────────────────


def test_internal_xml_tag_name_is_name_tag() -> None:
    tag_names = values_for_type(INTERNAL_XML_TAG, Name.Tag)
    assert "local-command-caveat" in tag_names, (
        f"Expected 'local-command-caveat' to be Name.Tag. Got: {tag_names}"
    )


def test_internal_xml_content_is_text() -> None:
    text_values = values_for_type(INTERNAL_XML_TAG, Text)
    all_text = "".join(text_values)
    assert "Caveat text here." in all_text, (
        f"Expected tag content to be Text. All text tokens: {all_text!r}"
    )


def test_internal_xml_tokenizes_completely() -> None:
    result = joined(INTERNAL_XML_TAG)
    assert result == INTERNAL_XML_TAG, (
        f"Token values do not reproduce internal-XML input.\n"
        f"Expected: {INTERNAL_XML_TAG!r}\n"
        f"Got:      {result!r}"
    )


# ── attribute value containing angle brackets ─────────────────────────────────


def test_attr_value_with_angle_brackets_is_literal_string() -> None:
    values = values_for_type(ATTR_WITH_ANGLE_BRACKETS, Literal.String)
    assert "<synthetic>" in values, (
        f"Expected '<synthetic>' to be Literal.String. Got: {values}"
    )


def test_attr_with_angle_brackets_tokenizes_completely() -> None:
    result = joined(ATTR_WITH_ANGLE_BRACKETS)
    assert result == ATTR_WITH_ANGLE_BRACKETS, (
        f"Token values do not reproduce angle-bracket-attr input.\n"
        f"Expected: {ATTR_WITH_ANGLE_BRACKETS!r}\n"
        f"Got:      {result!r}"
    )


def test_literal_less_than_text_tokenizes_completely() -> None:
    result = joined(LITERAL_LESS_THAN_TEXT)
    assert result == LITERAL_LESS_THAN_TEXT, (
        f"Token values do not reproduce literal-less-than input.\n"
        f"Expected: {LITERAL_LESS_THAN_TEXT!r}\n"
        f"Got:      {result!r}"
    )


def test_literal_less_than_text_stays_text() -> None:
    text_values = values_for_type(LITERAL_LESS_THAN_TEXT, Text)
    all_text = "".join(text_values)
    assert "a<b" in all_text, f"Expected 'a<b' to remain Text. Got: {all_text!r}"
    assert "git add <file>..." in all_text, (
        f"Expected 'git add <file>...' to remain Text. Got: {all_text!r}"
    )
    assert "1 <= 2" in all_text, f"Expected '1 <= 2' to remain Text. Got: {all_text!r}"


# ── baseline file parity ──────────────────────────────────────────────────────

BASELINE_DIR = Path("/tmp/convsyntax/baseline")
BASELINE_FILES = list(BASELINE_DIR.glob("*.colorless.xmd")) if BASELINE_DIR.exists() else []


@pytest.mark.parametrize("path", BASELINE_FILES, ids=[p.name for p in BASELINE_FILES])
def test_baseline_tokenizes_completely(path: Path) -> None:
    """Tokenizing any captured baseline file must reproduce the text exactly."""
    text = path.read_text()
    result = joined(text)
    assert result == text, (
        f"Token values do not reproduce baseline {path.name}.\n"
        f"First diff index: {next((i for i, (a, b) in enumerate(zip(result, text)) if a != b), len(result))}\n"
        f"Expected snippet: {text[:200]!r}\n"
        f"Got snippet:      {result[:200]!r}"
    )


@pytest.mark.parametrize("path", BASELINE_FILES, ids=[p.name for p in BASELINE_FILES])
def test_baseline_no_error_tokens(path: Path) -> None:
    """No error tokens should be emitted for any captured baseline file."""
    text = path.read_text()
    errors = [(t, v) for t, v in get_tokens(text) if t is Token.Error]
    assert not errors, f"Error tokens in {path.name}: {errors[:5]}"
