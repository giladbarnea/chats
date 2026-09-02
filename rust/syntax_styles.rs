//! Monokai's resolved style for every Pygments token type.
//!
//! Generated from Pygments 2.19.2 and Rich's `PygmentsSyntaxTheme`
//! by `teammates/message-renderer/probes/generate_token_styles.py`. Do not edit.
//!
//! `Syntax.highlight` asks the theme for each token a lexer emits, and the theme
//! walks the token's ancestry until it finds a style. The **resolved** answer is
//! recorded here so the renderer never re-derives the theme; [`token_style`] walks
//! the same ancestry for a token this table does not name.

use crate::color::{ColorTriplet, StyleColor};
use crate::search_views::Style;

/// Every token type Pygments defines, with the style Monokai gives it. Sorted, so
/// a lookup is a binary search.
pub const TOKEN_STYLES: &[(&str, Style)] = &[
    ("Token", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment.Hashbang", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment.Multiline", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment.Preproc", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment.PreprocFile", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment.Single", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Comment.Special", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Error", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ed007e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#1e0010"))),
    }),
    ("Token.Escape", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Deleted", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ff4689"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Emph", Style {
        bold: Some(false), dim: None, italic: Some(true),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.EmphStrong", Style {
        bold: Some(true), dim: None, italic: Some(true),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Error", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Heading", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Inserted", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Output", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Prompt", Style {
        bold: Some(true), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ff4689"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Strong", Style {
        bold: Some(true), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Subheading", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#959077"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Generic.Traceback", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword.Constant", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword.Declaration", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword.Namespace", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ff4689"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword.Pseudo", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword.Reserved", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Keyword.Type", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Date", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number.Bin", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number.Float", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number.Hex", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number.Integer", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number.Integer.Long", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.Number.Oct", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Affix", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Backtick", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Char", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Delimiter", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Doc", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Double", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Escape", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ae81ff"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Heredoc", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Interpol", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Other", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Regex", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Single", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Literal.String.Symbol", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6db74"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Attribute", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Builtin", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Builtin.Pseudo", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Class", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Constant", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#66d9ef"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Decorator", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Entity", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Exception", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Function", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Function.Magic", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Label", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Namespace", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Other", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#a6e22e"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Property", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Tag", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ff4689"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Variable", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Variable.Class", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Variable.Global", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Variable.Instance", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Name.Variable.Magic", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Operator", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ff4689"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Operator.Word", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#ff4689"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Other", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Punctuation", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Punctuation.Marker", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Text", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
    ("Token.Text.Whitespace", Style {
        bold: Some(false), dim: None, italic: Some(false),
        underline: Some(false), reverse: None, strike: None,
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
    }),
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
pub fn token_style(path: &str) -> Style {
    let mut candidate = path;
    loop {
        if let Ok(index) = TOKEN_STYLES.binary_search_by(|(name, _)| (*name).cmp(candidate)) {
            return TOKEN_STYLES[index].1;
        }
        match candidate.rfind('.') {
            Some(cut) => candidate = &candidate[..cut],
            None => return Style::inherit(),
        }
    }
}
