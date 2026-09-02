#!/usr/bin/env -S uv run
"""Harvest real fenced blocks of one family, and measure which rules they reach.

Two questions a table's gate cannot be built without:

1. **How much real content exists** for the family, and what it costs to store.
2. **Which of the table's rules that content actually reaches.** A table gated
   against content that exercises half of it looks identical to a complete one, so
   the corpus is chosen by coverage rather than by volume alone.

Coverage is measured by wrapping each rule's matcher in `_tokens`, which records a
rule the moment Pygments' own driver matches it. Nothing about the lexing changes:
the proxy returns the reference's own match object.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

from pygments.lexers import get_lexer_by_name

FENCE = re.compile(r"^```([^\n`]*)\n(.*?)(?:^```\s*$|\Z)", re.MULTILINE | re.DOTALL)


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


def session_files() -> list[Path]:
    home = Path(os.environ["HOME"])
    roots = [
        home / ".claude" / "projects",
        home / ".pi" / "agent" / "sessions",
        home / ".codex" / "sessions",
    ]
    return [path for root in roots if root.exists() for path in root.rglob("*.jsonl")]


def fences(files: int, seed: int, tags: set[str] | None) -> list[tuple[str, str]]:
    """Real fenced blocks of the given tags, in an order that survives the
    directory growing under it.

    **The session directory is live**, and a prefix of a seeded shuffle is not
    stable against it: adding files reshuffles every position, and one harvest here
    moved from 589 blocks to 465 in half an hour. Ordering by a hash of the path
    instead means a new file lands in one place rather than moving everything, so a
    regenerated corpus grows at its tail instead of churning. `seed` salts that
    hash, so it still selects a different sample.
    """
    paths = sorted(
        session_files(),
        key=lambda path: hashlib.blake2b(
            f"{seed}:{path}".encode(), digest_size=8
        ).digest(),
    )
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
                    tag = (info.split(" ")[0] or "text").lower()
                    if tags is None or tag in tags:
                        found.append((tag, body))
    return found


def instrument(lexer) -> set[tuple[str, int]]:
    """Record every rule Pygments' own driver matches. Returns the live set."""
    reached: set[tuple[str, int]] = set()
    instrumented = {}
    for state, rules in lexer._tokens.items():
        replaced = []
        for index, rule in enumerate(rules):
            def matcher(text, position, state=state, index=index, inner=rule[0]):
                found = inner(text, position)
                if found is not None:
                    reached.add((state, index))
                return found

            replaced.append((matcher, *rule[1:]))
        instrumented[state] = replaced
    lexer._tokens = instrumented
    return reached


def preprocess(lexer, code: str) -> str:
    """What `Syntax` hands the lexer: `_process_code` then `Lexer.get_tokens`'s own
    preprocessing, which is what the token offsets are measured against."""
    processed = (code if code.endswith("\n") else code + "\n").expandtabs(4)
    return lexer._preprocess_lexer_input(processed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alias", default="typescript")
    parser.add_argument("--tags", default="typescript,ts,tsx")
    parser.add_argument("--files", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=23)
    options = parser.parse_args()

    lexer = get_lexer_by_name(options.alias, stripnl=False, ensurenl=True, tabsize=4)
    declared = {
        (state, index): rule[0].__self__.pattern
        for state, rules in lexer._tokens.items()
        for index, rule in enumerate(rules)
    }
    reached = instrument(lexer)

    tags = {tag.strip() for tag in options.tags.split(",")}
    blocks = fences(options.files, options.seed, tags)
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for tag, body in blocks:
        text = preprocess(lexer, body.rstrip())
        if text in seen:
            continue
        seen.add(text)
        unique.append((tag, text))

    by_tag = collections.Counter(tag for tag, _ in unique)
    characters = sum(len(text) for _, text in unique)
    for _, text in unique:
        list(lexer.get_tokens(text))

    missed = [entry for entry in declared if entry not in reached]
    print(f"files scanned {options.files}  blocks {len(blocks)}  unique {len(unique)}")
    print(f"characters {characters}  by tag {dict(by_tag)}")
    print(f"rules declared {len(declared)}  reached {len(reached)}  unreached {len(missed)}")
    for state, index in missed:
        print(f"  unreached {state}[{index}]  {declared[(state, index)][:110]!r}")


if __name__ == "__main__":
    main()
