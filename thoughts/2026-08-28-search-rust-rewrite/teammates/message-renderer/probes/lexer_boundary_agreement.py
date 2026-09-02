#!/usr/bin/env -S uv run
"""Do Pygments and syntect put their token boundaries in the same places?

Prices the highlighting-crate option. The two cannot be compared by colour —
syntect maps TextMate **scopes** through a theme, Pygments maps its own **token
types** through a style map, and no mapping between them exists to borrow. Where
each puts a run boundary can be compared with nothing invented, and **a boundary
in the wrong place is a divergence no theme can repair**, so the agreement measured
here is an upper bound on what any theme mapping could achieve.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fence_lexer_census import fences  # noqa: E402

from rich.syntax import Syntax  # noqa: E402


def pygments_boundaries(tag: str, body: str) -> tuple[list[int], int] | None:
    syntax = Syntax(body, tag, theme="monokai", word_wrap=True)
    if syntax.lexer is None:
        return None
    text = syntax.highlight(body)
    offsets = sorted({span.start for span in text.spans} | {0})
    return offsets, len(text.plain)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--files", type=int, default=600)
    parser.add_argument("--blocks", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=23)
    options = parser.parse_args()

    blocks = [
        (tag, body)
        for tag, body in fences(options.files, options.seed, options.blocks)
        if body.strip()
    ]
    payload = "\n".join(
        json.dumps({"tag": tag, "body": body}) for tag, body in blocks
    )
    completed = subprocess.run(
        [options.binary], input=payload.encode(), stdout=subprocess.PIPE, check=True
    )
    theirs = json.loads(completed.stdout)

    missing: collections.Counter[str] = collections.Counter()
    agreement: dict[str, list[float]] = collections.defaultdict(list)
    compared = 0

    for (tag, body), record in zip(blocks, theirs):
        if not record.get("found"):
            missing[tag] += 1
            continue
        ours = pygments_boundaries(tag, body)
        if ours is None:
            continue
        pygments_offsets, length = ours
        if length == 0:
            continue
        theirs_offsets = set(record["boundaries"])
        mine = set(pygments_offsets)
        union = mine | theirs_offsets
        if not union:
            continue
        shared = len(mine & theirs_offsets)
        agreement[tag].append(shared / len(union))
        compared += 1

    print(f"blocks compared {compared}")
    print("\nno syntect syntax for the tag at all:")
    for tag, count in missing.most_common(12):
        print(f"  {tag:14} {count}")

    print("\ntag             blocks   boundary agreement (Jaccard)")
    ordered = sorted(agreement.items(), key=lambda item: -len(item[1]))
    for tag, scores in ordered[:14]:
        mean = sum(scores) / len(scores)
        print(f"  {tag:14} {len(scores):6}   {100 * mean:5.1f}%")
    every = [score for scores in agreement.values() for score in scores]
    if every:
        print(f"\n  {'overall':14} {len(every):6}   {100 * sum(every) / len(every):5.1f}%")


if __name__ == "__main__":
    main()
