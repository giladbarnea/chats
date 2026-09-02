#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pygments==2.19.2"]
# ///
"""Measure held-out Monokai agreement after learning one style per Arborium tag."""

from __future__ import annotations

import collections
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from pygments.styles.monokai import MonokaiStyle
from pygments.token import Token, string_to_tokentype

Style = tuple[str | None, bool, bool, bool, str | None, str | None]


def style_for(path: str) -> Style:
    style = MonokaiStyle.style_for_token(string_to_tokentype(path.removeprefix("Token.")))
    return (
        style["color"],
        style["bold"],
        style["italic"],
        style["underline"],
        style["bgcolor"],
        style["border"],
    )


DEFAULT_STYLE = style_for(str(Token.Text))


def pygments_styles(case: dict[str, object]) -> list[Style]:
    styles: list[Style] = []
    for path, text in case["tokens"]:  # type: ignore[index]
        styles.extend([style_for(path)] * len(text))
    return styles


def byte_to_character_offsets(source: str) -> dict[int, int]:
    offsets = {0: 0}
    byte_offset = 0
    for character_offset, character in enumerate(source, 1):
        byte_offset += len(character.encode())
        offsets[byte_offset] = character_offset
    return offsets


def arborium_tags(source: str, record: dict[str, object]) -> list[str | None]:
    tags: list[str | None] = [None] * len(source)
    offsets = byte_to_character_offsets(source)
    for start, end, tag in record["tokens"]:  # type: ignore[index]
        tags[offsets[start] : offsets[end]] = [tag] * (offsets[end] - offsets[start])
    return tags


def fold(source: str) -> int:
    return hashlib.sha256(source.encode()).digest()[0] % 5


def main() -> None:
    family, oracle_path, binary = sys.argv[1:]
    oracle = json.loads(Path(oracle_path).read_text())
    completed = subprocess.run(
        [binary, family, oracle_path, "--json"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    records = json.loads(completed.stdout)
    cases = oracle["cases"]
    totals = collections.Counter()
    seen_tags: set[str] = set()

    for held_out in range(5):
        votes: dict[str, collections.Counter[Style]] = collections.defaultdict(collections.Counter)
        for case, record in zip(cases, records, strict=True):
            source = case["text"]
            if fold(source) == held_out:
                continue
            for tag, style in zip(
                arborium_tags(source, record), pygments_styles(case), strict=True
            ):
                if tag is not None:
                    seen_tags.add(tag)
                    votes[tag][style] += 1
        mapping = {tag: counts.most_common(1)[0][0] for tag, counts in votes.items()}

        for case, record in zip(cases, records, strict=True):
            source = case["text"]
            if fold(source) != held_out:
                continue
            actual = pygments_styles(case)
            predicted = [
                mapping.get(tag, DEFAULT_STYLE) if tag is not None else DEFAULT_STYLE
                for tag in arborium_tags(source, record)
            ]
            for expected, got in zip(actual, predicted, strict=True):
                expected_painted = expected != DEFAULT_STYLE
                got_painted = got != DEFAULT_STYLE
                totals["characters"] += 1
                totals["correct"] += expected == got
                totals["expected_painted"] += expected_painted
                totals["correct_painted"] += expected_painted and expected == got
                totals["predicted_painted"] += got_painted
                totals["true_predicted_painted"] += got_painted and expected == got

    print(
        f"{family}: characters={totals['characters']} tags={len(seen_tags)} "
        f"all_style_agreement={100 * totals['correct'] / totals['characters']:.1f}% "
        f"painted_recall={100 * totals['correct_painted'] / totals['expected_painted']:.1f}% "
        f"painted_precision={100 * totals['true_predicted_painted'] / totals['predicted_painted']:.1f}%"
    )


if __name__ == "__main__":
    main()
