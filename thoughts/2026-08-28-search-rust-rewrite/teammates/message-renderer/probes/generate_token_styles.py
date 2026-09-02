#!/usr/bin/env -S uv run
"""Emit Monokai's resolved style for every Pygments token type, as Rust.

`Syntax.highlight` asks `PygmentsSyntaxTheme.get_style_for_token` for each token a
lexer emits, and that walks the token's ancestry until it finds a style. Recording
the **resolved** answer per token type means the renderer never re-derives the
theme, and the generator is the thing to review.

Every entry carries `bold`, `italic` and `underline` explicitly, including when
false: `PygmentsSyntaxTheme` builds each style from the full Pygments dict, so the
attributes **clear** rather than inherit. That is invisible inside a fence, where
nothing is set above them, and it is the reason a style attribute is three-valued.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pygments.token import STANDARD_TYPES, Token
from rich.color import ColorType
from rich.syntax import PygmentsSyntaxTheme


def colour(value) -> str:
    if value is None:
        return "None"
    if value.type in (ColorType.STANDARD, ColorType.EIGHT_BIT):
        return f"Some(StyleColor::Palette({value.number}))"
    if value.type is ColorType.TRUECOLOR:
        triplet = value.triplet
        return f'Some(StyleColor::Triplet(ColorTriplet::from_hex("#{triplet.hex[1:]}")))'
    return "None"


def flag(value) -> str:
    return "None" if value is None else f"Some({str(value).lower()})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    theme = PygmentsSyntaxTheme("monokai")
    rows = []
    for token in sorted(STANDARD_TYPES, key=str):
        style = theme.get_style_for_token(token)
        rows.append(
            f'    ("{token}", Style {{\n'
            f"        bold: {flag(style.bold)}, dim: {flag(style.dim)},"
            f" italic: {flag(style.italic)},\n"
            f"        underline: {flag(style.underline)},"
            f" reverse: {flag(style.reverse)}, strike: {flag(style.strike)},\n"
            f"        foreground: {colour(style.color)},\n"
            f"        background: {colour(style.bgcolor)},\n"
            f"    }}),"
        )

    from importlib.metadata import version

    Path(options.out).write_text(
        f'''//! Monokai's resolved style for every Pygments token type.
//!
//! Generated from Pygments {version("pygments")} and Rich's `PygmentsSyntaxTheme`
//! by `teammates/message-renderer/probes/generate_token_styles.py`. Do not edit.
//!
//! `Syntax.highlight` asks the theme for each token a lexer emits, and the theme
//! walks the token's ancestry until it finds a style. The **resolved** answer is
//! recorded here so the renderer never re-derives the theme; [`token_style`] walks
//! the same ancestry for a token this table does not name.

use crate::color::{{ColorTriplet, StyleColor}};
use crate::search_views::Style;

/// Every token type Pygments defines, with the style Monokai gives it. Sorted, so
/// a lookup is a binary search.
pub const TOKEN_STYLES: &[(&str, Style)] = &[
{chr(10).join(rows)}
];

/// The style a token path resolves to, walking up its ancestry as the theme does.
///
/// `Token.Name.Function.Magic` falls back to `Token.Name.Function`, then
/// `Token.Name`, then `Token` — which is how a lexer emitting a type the theme does
/// not name still gets a colour.
///
/// ```
/// use _native::syntax_styles::token_style;
/// // A keyword is Monokai's cyan.
/// let keyword = token_style("Token.Keyword");
/// assert!(keyword.foreground.is_some());
/// // An unnamed descendant inherits its nearest named ancestor.
/// assert_eq!(token_style("Token.Name.Function.Invented"), token_style("Token.Name.Function"));
/// ```
pub fn token_style(path: &str) -> Style {{
    let mut candidate = path;
    loop {{
        if let Ok(index) = TOKEN_STYLES.binary_search_by(|(name, _)| (*name).cmp(candidate)) {{
            return TOKEN_STYLES[index].1;
        }}
        match candidate.rfind('.') {{
            Some(cut) => candidate = &candidate[..cut],
            None => return Style::inherit(),
        }}
    }}
}}
''',
        encoding="utf-8",
    )
    print(f"{len(rows)} token types -> {options.out}")


if __name__ == "__main__":
    main()
