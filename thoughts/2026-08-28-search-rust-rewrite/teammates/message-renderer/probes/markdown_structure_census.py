#!/usr/bin/env -S uv run
"""How much markdown structure real transcript text actually carries.

Prices parser fidelity. A hand-written block parser is cheap if real content is
paragraphs and fences and expensive if it is nested lists, tables and quotes, so
the question is answered by counting rather than by judgement.

Parses with the exact parser Rich uses — `MarkdownIt().enable("strikethrough")
.enable("table")` — so the token names are the ones `rich.markdown` dispatches on.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
from pathlib import Path

from markdown_it import MarkdownIt


def text_blocks(entry: dict) -> list[str]:
    """Every assistant/user text block in one JSONL entry, provider-agnostic."""
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=400)
    parser.add_argument("--seed", type=int, default=17)
    options = parser.parse_args()

    home = Path(os.environ["HOME"])
    roots = [home / ".claude" / "projects", home / ".pi" / "agent" / "sessions", home / ".codex" / "sessions"]
    paths = [path for root in roots if root.exists() for path in root.rglob("*.jsonl")]
    random.Random(options.seed).shuffle(paths)
    paths = paths[: options.files]

    markdown = MarkdownIt().enable("strikethrough").enable("table")
    block_counts: collections.Counter[str] = collections.Counter()
    inline_counts: collections.Counter[str] = collections.Counter()
    blocks_seen = 0
    files_read = 0

    for path in paths:
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        files_read += 1
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            for text in text_blocks(entry):
                blocks_seen += 1
                try:
                    tokens = markdown.parse(text)
                except Exception:
                    block_counts["PARSE-FAILED"] += 1
                    continue
                kinds = set()
                for token in tokens:
                    if token.type.endswith("_close"):
                        continue
                    kinds.add(token.type)
                    for child in token.children or []:
                        if child.type not in ("text", "softbreak"):
                            inline_counts[child.type] += 1
                for kind in kinds:
                    block_counts[kind] += 1

    print(f"files {files_read}  text blocks {blocks_seen}")
    print("\nblock tokens, share of text blocks containing at least one:")
    for kind, count in block_counts.most_common(30):
        print(f"  {kind:24} {count:8}  {100 * count / max(1, blocks_seen):6.2f}%")
    print("\ninline tokens, total occurrences:")
    for kind, count in inline_counts.most_common(20):
        print(f"  {kind:24} {count:8}")


if __name__ == "__main__":
    main()
