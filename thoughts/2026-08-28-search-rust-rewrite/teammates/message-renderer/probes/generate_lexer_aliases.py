#!/usr/bin/env -S uv run
"""Emit Pygments' alias table as Rust.

A fence's language tag decides which lexer Rich finds, and **whether it finds one
at all** decides whether the block renders plain. That question cannot be answered
without the alias set, so the set is generated from the reference rather than
guessed at, the way the cell tables are.

Generated data is trusted by construction; the generator is the thing to review.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pygments.lexers import get_all_lexers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    pairs: dict[str, str] = {}
    for name, aliases, _filenames, _mimetypes in get_all_lexers():
        for alias in aliases:
            key = alias.lower()
            if key in pairs and pairs[key] != name:
                raise SystemExit(f"alias {key!r} is claimed by two lexers")
            pairs[key] = name

    # Two escaping traps, both hit: `repr` plus a quote swap breaks on a name
    # carrying an apostrophe (`Cap'n Proto` closed its own literal), and JSON
    # escaping breaks on a non-BMP alias (Mojo's is an emoji, which JSON writes as
    # a surrogate pair that Rust rejects). The file is UTF-8, so the character goes
    # in literally and only the two Rust delimiters are escaped.
    def rust_string(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        escaped = "".join(
            character if character >= " " else f"\\u{{{ord(character):x}}}"
            for character in escaped
        )
        return f'"{escaped}"'

    rows = "\n".join(
        f"    ({rust_string(alias)}, {rust_string(pairs[alias])}),"
        for alias in sorted(pairs)
    )
    from importlib.metadata import version

    Path(options.out).write_text(
        f'''//! Which Pygments lexer a fence's language tag resolves to.
//!
//! Generated from Pygments {version("pygments")} by
//! `teammates/message-renderer/probes/generate_lexer_aliases.py`. Do not edit.
//!
//! `CodeBlock.create` takes the first word of a fence's info string, or `text`,
//! and `Syntax` looks that name up. **A tag with no entry here finds no lexer**,
//! and Rich then falls back to its plain-text lexer — which is the same rendering
//! as the `text` tag, and is exactly reproducible with no lexer at all.

/// Every Pygments alias, lowercased, paired with its lexer's display name.
/// Sorted, so a lookup is a binary search.
pub const LEXER_ALIASES: &[(&str, &str)] = &[
{rows}
];

/// The lexer a fence tag resolves to, or `None` when Pygments knows no such name.
///
/// Case-insensitive, because `get_lexer_by_name` compares lowercased aliases.
///
/// ```
/// use _native::syntax_lexers::lexer_for_tag;
/// assert_eq!(lexer_for_tag("typescript"), Some("TypeScript"));
/// assert_eq!(lexer_for_tag("TS"), Some("TypeScript"));
/// assert_eq!(lexer_for_tag("text"), Some("Text only"));
/// // No lexer at all — the product renders these plain.
/// assert_eq!(lexer_for_tag("mermaid"), None);
/// assert_eq!(lexer_for_tag(""), None);
/// ```
pub fn lexer_for_tag(tag: &str) -> Option<&'static str> {{
    let lowered = tag.to_lowercase();
    LEXER_ALIASES
        .binary_search_by(|(alias, _)| alias.cmp(&lowered.as_str()))
        .ok()
        .map(|index| LEXER_ALIASES[index].1)
}}
''',
        encoding="utf-8",
    )
    print(f"{len(pairs)} aliases -> {options.out}")


if __name__ == "__main__":
    main()
