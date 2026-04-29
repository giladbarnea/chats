"""Tests for PaddedInlineCodeMarkdown — inline code rendered with 1-space padding."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from conversations.formatting import PaddedInlineCodeMarkdown


def _render(markup: str) -> str:
    """Render PaddedInlineCodeMarkdown to plain text, no color, wide enough to avoid wrapping."""
    buf = StringIO()
    console = Console(file=buf, no_color=True, highlight=False, width=500)
    console.print(PaddedInlineCodeMarkdown(markup))
    return buf.getvalue()


def test_inline_code_padded_with_one_space_each_side() -> None:
    """Single inline code span should have 1 space prepended and appended."""
    output = _render("use `foo` here")
    assert " foo " in output, (
        f"Expected inline code to be rendered as ' foo ' (1-space padding each side). "
        f"Got: {output!r}"
    )


def test_multiple_inline_code_spans_all_padded() -> None:
    """All inline code spans in the same paragraph are padded."""
    output = _render("try `alpha` and `beta`")
    assert " alpha " in output, (
        f"Expected first inline code to be rendered as ' alpha '. Got: {output!r}"
    )
    assert " beta " in output, (
        f"Expected second inline code to be rendered as ' beta '. Got: {output!r}"
    )


def test_non_code_text_not_affected() -> None:
    """Bold and italic inlines should not gain extra spaces."""
    output = _render("**bold** and _italic_ text")
    assert "bold" in output, f"Expected 'bold' to appear in output. Got: {output!r}"
    assert "  bold  " not in output, (
        f"Expected bold text to not be padded. Got: {output!r}"
    )
    assert "italic" in output, f"Expected 'italic' to appear in output. Got: {output!r}"
    assert "  italic  " not in output, (
        f"Expected italic text to not be padded. Got: {output!r}"
    )


def test_code_content_preserved() -> None:
    """The code content itself must not be mutated — only spaces added around it."""
    output = _render("run `my_func(arg)` now")
    assert "my_func(arg)" in output, (
        f"Expected original code content to be preserved. Got: {output!r}"
    )
