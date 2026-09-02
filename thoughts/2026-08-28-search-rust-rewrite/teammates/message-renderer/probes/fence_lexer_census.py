#!/usr/bin/env -S uv run
"""What a fence lexer would actually have to do, over real fenced blocks.

Prices stage two. Three questions, each answered by counting rather than by
judgement:

1. **Which fence tags reach a lexer at all.** `CodeBlock.create` takes the first
   word of the info string, or `text`; `Syntax` then looks that name up in
   Pygments. **A tag Pygments does not know renders plain** — no lexer needed, and
   exactly reproducible today.
2. **How much colour a lexer actually adds.** The share of characters a real lexer
   paints away from Monokai's default foreground. A language whose blocks are
   mostly default-coloured is cheap to be wrong about.
3. **Which languages carry the weight**, by block and by character.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

from rich.syntax import Syntax

FENCE = re.compile(r"^```([^\n`]*)\n(.*?)(?:^```\s*$|\Z)", re.MULTILINE | re.DOTALL)
MONOKAI_DEFAULT = "#f8f8f2"


def text_blocks(entry) -> list[str]:
    found: list[str] = []
    stack = [entry]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                found.append(item["text"])
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def fences(files: int, seed: int, cap: int) -> list[tuple[str, str]]:
    home = Path(os.environ["HOME"])
    roots = [
        home / ".claude" / "projects",
        home / ".pi" / "agent" / "sessions",
        home / ".codex" / "sessions",
    ]
    paths = [path for root in roots if root.exists() for path in root.rglob("*.jsonl")]
    random.Random(seed).shuffle(paths)
    found: list[tuple[str, str]] = []
    for path in paths[:files]:
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            for text in text_blocks(entry):
                if "```" not in text:
                    continue
                for info, body in FENCE.findall(text):
                    found.append((info.split(" ")[0] or "text", body))
                    if len(found) >= cap:
                        return found
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=600)
    parser.add_argument("--blocks", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=23)
    options = parser.parse_args()

    blocks = fences(options.files, options.seed, options.blocks)
    by_tag: collections.Counter[str] = collections.Counter()
    characters_by_tag: collections.Counter[str] = collections.Counter()
    coloured_by_tag: collections.Counter[str] = collections.Counter()
    plain_tags: set[str] = set()
    lexed_tags: set[str] = set()

    for tag, body in blocks:
        by_tag[tag] += 1
        syntax = Syntax(body.rstrip(), tag, theme="monokai", word_wrap=True)
        lexer = syntax.lexer
        if lexer is None:
            plain_tags.add(tag)
            characters_by_tag[tag] += len(body)
            continue
        lexed_tags.add(tag)
        text = syntax.highlight(body.rstrip())
        # Every character carries Monokai's default foreground unless a token
        # painted it something else.
        painted = 0
        for span in text.spans:
            style = span.style
            colour = getattr(style, "color", None)
            if colour is None or colour.triplet is None:
                continue
            if f"#{colour.triplet.hex[1:]}".lower() != MONOKAI_DEFAULT:
                painted += span.end - span.start
        characters_by_tag[tag] += len(text.plain)
        coloured_by_tag[tag] += painted

    total_blocks = sum(by_tag.values())
    total_characters = sum(characters_by_tag.values())
    plain_blocks = sum(count for tag, count in by_tag.items() if tag in plain_tags)
    plain_characters = sum(
        count for tag, count in characters_by_tag.items() if tag in plain_tags
    )

    print(f"fenced blocks {total_blocks}   characters {total_characters}")
    print(
        f"\nno Pygments lexer -> renders plain, needs no lexer at all:"
        f"  {plain_blocks} blocks ({100 * plain_blocks / max(1, total_blocks):.1f}%),"
        f"  {plain_characters} chars ({100 * plain_characters / max(1, total_characters):.1f}%)"
    )
    print(f"distinct tags: {len(lexed_tags)} lexed, {len(plain_tags)} plain")

    total_painted = sum(coloured_by_tag.values())
    print(
        f"\ncharacters a lexer paints away from Monokai's default:"
        f"  {total_painted} of {total_characters}"
        f"  ({100 * total_painted / max(1, total_characters):.1f}%)"
    )
    family = {"typescript", "ts", "tsx"}
    family_blocks = sum(by_tag[tag] for tag in family)
    family_chars = sum(characters_by_tag[tag] for tag in family)
    family_painted = sum(coloured_by_tag[tag] for tag in family)
    print(
        f"typescript family: {family_blocks} blocks"
        f" ({100 * family_blocks / max(1, total_blocks):.1f}%),"
        f" {family_chars} chars ({100 * family_chars / max(1, total_characters):.1f}%),"
        f" {family_painted} of all painted characters"
        f" ({100 * family_painted / max(1, total_painted):.1f}%)"
    )
    text_chars = characters_by_tag.get("text", 0)
    print(
        f"`text` fences: {by_tag.get('text', 0)} blocks"
        f" ({100 * by_tag.get('text', 0) / max(1, total_blocks):.1f}%),"
        f" {text_chars} chars ({100 * text_chars / max(1, total_characters):.1f}%),"
        f" 0 painted — correct today with no lexer"
    )

    print("\ntag                 blocks   share    chars     painted%  lexer")
    for tag, count in by_tag.most_common(22):
        chars = characters_by_tag[tag]
        painted = coloured_by_tag[tag]
        share = 100 * count / max(1, total_blocks)
        density = 100 * painted / chars if chars and tag in lexed_tags else 0.0
        kind = "plain" if tag in plain_tags else "pygments"
        print(
            f"{tag[:18]:18} {count:7} {share:6.1f}% {chars:8}  "
            f"{density:7.1f}%  {kind}"
        )


if __name__ == "__main__":
    main()
