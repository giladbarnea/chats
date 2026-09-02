#!/usr/bin/env -S uv run
"""What is left to port, counted and classified rather than estimated.

Every fence tag in the real corpora that reaches a Pygments lexer and is not already
promoted, with the three things that decide the plan:

1. **How often it occurs**, so the set can be ordered.
2. **What kind of lexer it is.** A pure `RegexLexer` is batch work on machinery used
   five times. One carrying a hand-written callback, or one that nests a *different*
   lexer, needs an engine addition first. One that is not a `RegexLexer` at all — as
   JSON is — is an imperative port with none of it.
3. **Whether real content exists to gate it.** A family with fourteen blocks cannot
   have the gate bash has, and the precedent is that the gate must say so.

And the question the count cannot answer on its own: **Pygments has hundreds of
lexers and any fence can name one.** The residue is reported as a number rather than
left to be discovered.
"""

from __future__ import annotations

import argparse
import collections
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harvest_family_corpus import fences, session_files
from pygments.lexer import Lexer, RegexLexer, this
from pygments.lexers import get_all_lexers, get_lexer_by_name
from pygments.token import _TokenType
from pygments.util import ClassNotFound

# Display names with a table or a port already landed.
PROMOTED = {"TypeScript", "TSX", "Bash", "Python", "JavaScript", "JSON"}

CARRIED_FLAGS = re.MULTILINE | re.DOTALL | re.IGNORECASE


def classify(lexer) -> tuple[str, str]:
    """The lexer's kind, and what makes it that kind."""
    if not isinstance(lexer, RegexLexer):
        base = type(lexer).__mro__[1].__name__
        return "scanner", f"not a RegexLexer ({type(lexer).__name__} over {base})"

    if lexer.flags & ~CARRIED_FLAGS:
        return "flags", f"declares {re.RegexFlag(lexer.flags)!r}, which LexerFlags cannot carry"

    callbacks: list[str] = []
    foreign: list[str] = []
    for state, rules in lexer._tokens.items():
        for index, rule in enumerate(rules):
            action = rule[1]
            if action is None or isinstance(action, _TokenType):
                continue
            variables = inspect.getclosurevars(action).nonlocals
            if "args" not in variables:
                callbacks.append(f"{state}[{index}]:{getattr(action, '__name__', '?')}")
                continue
            for slot in variables["args"]:
                if slot is None or isinstance(slot, _TokenType):
                    continue
                inner = inspect.getclosurevars(slot).nonlocals
                if "args" in inner:
                    callbacks.append(f"{state}[{index}]:nested-bygroups")
                elif "_other" in inner:
                    foreign.append(f"{state}[{index}]:using({inner['_other']})")
    if foreign:
        return "foreign-lexer", foreign[0]
    if callbacks:
        return "callback", callbacks[0]
    return "table", f"{sum(len(r) for r in lexer._tokens.values())} rules, {len(lexer._tokens)} states"


def _known(tag: str) -> bool:
    try:
        get_lexer_by_name(tag)
    except ClassNotFound:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=23)
    options = parser.parse_args()

    # No tag filter: a tag Pygments does not know is exactly what the ruling calls
    # the plain-fallback case, so it has to be counted rather than filtered away.
    blocks = fences(options.files, options.seed, None)

    counts: collections.Counter[str] = collections.Counter()
    characters: collections.Counter[str] = collections.Counter()
    for tag, body in blocks:
        counts[tag] += 1
        characters[tag] += len(body)

    rows = []
    unknown_blocks = 0
    for tag, count in counts.items():
        try:
            lexer = get_lexer_by_name(tag, stripnl=False, ensurenl=True, tabsize=4)
        except ClassNotFound:
            unknown_blocks += count
            continue
        if lexer.name in PROMOTED or lexer.name == "Text only":
            continue
        kind, why = classify(lexer)
        rows.append((count, characters[tag], tag, lexer.name, kind, why))

    by_lexer: dict[str, list] = {}
    for count, chars, tag, name, kind, why in rows:
        entry = by_lexer.setdefault(name, [0, 0, [], kind, why])
        entry[0] += count
        entry[1] += chars
        entry[2].append(tag)

    total_blocks = sum(counts.values())
    unknown_tags = sorted(
        (count, tag)
        for tag, count in counts.items()
        if not _known(tag)
    )
    print(f"fenced blocks scanned: {total_blocks} over {options.files} files")
    print(
        f"tags reaching NO Pygments lexer — the plain-fallback case: {unknown_blocks} "
        f"blocks ({100 * unknown_blocks / max(1, total_blocks):.1f}%) across "
        f"{len(unknown_tags)} tags"
    )
    print("  commonest: " + ", ".join(f"{tag}({count})" for count, tag in sorted(unknown_tags, reverse=True)[:12]))
    print()
    print(f"{'lexer':26} {'blocks':>7} {'chars':>9}  {'kind':14} tags")
    remaining = 0
    for name, (count, chars, tags, kind, why) in sorted(
        by_lexer.items(), key=lambda item: -item[1][0]
    ):
        remaining += count
        print(f"{name[:26]:26} {count:7} {chars:9}  {kind:14} {','.join(sorted(tags))}")
    print(f"\nunpromoted-but-known: {remaining} blocks "
          f"({100 * remaining / max(1, total_blocks):.1f}%) across {len(by_lexer)} lexers")

    print("\nwhy, per lexer:")
    for name, (_count, _chars, _tags, kind, why) in sorted(by_lexer.items()):
        print(f"  {name[:26]:26} {kind:14} {why[:90]}")

    every_lexer = {name for name, _a, _f, _m in get_all_lexers()}
    print(
        f"\nresidue: Pygments defines {len(every_lexer)} lexers; this corpus names "
        f"{len(by_lexer) + len(PROMOTED)} of them. A fence may name any of the rest."
    )


if __name__ == "__main__":
    main()
