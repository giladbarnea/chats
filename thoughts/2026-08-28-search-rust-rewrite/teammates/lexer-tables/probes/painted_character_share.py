#!/usr/bin/env -S uv run
"""What share of the colour a promoted set actually delivers.

**Blocks are the wrong unit for a colour decision and characters are only half
right.** Sixty per cent of the characters inside a fence carry Monokai's default
foreground whatever lexer runs, so the quantity that decides whether a language is
worth porting is the characters a lexer paints **away** from that default.

This counts them per lexer, so a bounded language list can be chosen on what it
delivers rather than on how often its tag appears.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd() / "src"))

from harvest_family_corpus import fences
from pygments.util import ClassNotFound
from rich.syntax import Syntax

MONOKAI_DEFAULT = "#f8f8f2"

PROMOTED = {"TypeScript", "TSX", "Bash", "Python", "JavaScript", "JSON", "SQL"}


def painted(tag: str, body: str) -> tuple[int, int, str | None]:
    """Characters painted away from the default, total characters, and the lexer."""
    syntax = Syntax(body.rstrip(), tag, theme="monokai", word_wrap=True)
    try:
        lexer = syntax.lexer
    except ClassNotFound:
        lexer = None
    if lexer is None:
        return 0, len(body), None
    text = syntax.highlight(body.rstrip())
    count = 0
    for span in text.spans:
        colour = getattr(span.style, "color", None)
        if colour is None or colour.triplet is None:
            continue
        if f"#{colour.triplet.hex[1:]}".lower() != MONOKAI_DEFAULT:
            count += span.end - span.start
    return count, len(text.plain), lexer.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=23)
    options = parser.parse_args()

    blocks = fences(options.files, options.seed, None)
    by_lexer_painted: collections.Counter[str] = collections.Counter()
    by_lexer_blocks: collections.Counter[str] = collections.Counter()
    total_characters = 0
    for tag, body in blocks:
        count, characters, name = painted(tag, body)
        total_characters += characters
        key = name or "«no lexer»"
        by_lexer_painted[key] += count
        by_lexer_blocks[key] += 1

    total_painted = sum(by_lexer_painted.values())
    print(f"blocks {sum(by_lexer_blocks.values())}   characters {total_characters}")
    print(
        f"painted away from Monokai's default: {total_painted} "
        f"({100 * total_painted / max(1, total_characters):.1f}% of all fenced characters)\n"
    )
    print(f"{'lexer':26} {'blocks':>7} {'painted':>10} {'share of painted':>17}")
    running = 0
    for name, count in by_lexer_painted.most_common(24):
        share = 100 * count / max(1, total_painted)
        marker = "*" if name in PROMOTED else " "
        print(f"{marker}{name[:25]:25} {by_lexer_blocks[name]:7} {count:10} {share:16.1f}%")

    promoted = sum(by_lexer_painted[name] for name in PROMOTED)
    print(
        f"\n* the {len(PROMOTED)} promoted families: {promoted} painted characters, "
        f"{100 * promoted / max(1, total_painted):.1f}% of all painted characters"
    )
    for candidate in ("XML", "Markdown", "HTML", "YAML", "Diff", "TOML", "CSS", "JSX"):
        count = by_lexer_painted[candidate]
        print(
            f"  + {candidate:10} would add {count:8} "
            f"({100 * count / max(1, total_painted):5.1f}%), running total "
            f"{100 * (promoted + count) / max(1, total_painted):5.1f}%"
        )


if __name__ == "__main__":
    main()
