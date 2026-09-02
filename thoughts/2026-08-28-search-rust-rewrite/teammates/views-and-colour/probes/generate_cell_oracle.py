#!/usr/bin/env -S uv run
"""Record Rich's own cell measurements for an adversarial corpus.

`rust/cells.rs` is a hand port of `rich.cells`, including the grapheme walk with
its zero-width-joiner and variation-selector rules. Unit tests cannot cover that;
only Rich's own answers can. The corpus is biased toward the shapes that make the
two implementations disagree rather than the shapes that occur most often.

Every character above ASCII is written as an escape on purpose. A literal joiner
in this source is unreviewable, a reader cannot tell it from a typo, and it does
not survive a round trip through every tool that touches the file.

Run once per `UNICODE_VERSION`; Rich caches the table per process.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")

from importlib.metadata import version as package_version
from rich.cells import cell_len, chop_cells, set_cell_size, split_text

ZWJ = "\u200d"
VS16 = "\ufe0f"
TICK = "▎"

BASE_CASES = [
    "",
    "a",
    "hello world",
    "╭─ hello ─╮",
    TICK + " untitled session",
    "你好",
    "你好" * 4,
    "ab你好" * 4,
    "café",
    "café",
    "́",
    "İstanbul",
    "ﬀﬁﬂﬃﬄ",
    ZWJ,
    VS16,
    ZWJ + ZWJ,
    "a" + ZWJ + "b",
    "❤" + VS16,
    "❤",
    "❤" + VS16 + ZWJ + "\U0001f525",
    "\U0001f468" + ZWJ + "\U0001f4bb",
    "\U0001f468" + ZWJ + "\U0001f469" + ZWJ + "\U0001f466" + ZWJ + "\U0001f466",
    "\U0001f1ee\U0001f1f1",
    "⌚▶❤" + VS16,
    "A߽B",
    " ",
    "abc\x00",
    "\x07",
    "tab\tseparated",
    "mixed 你好 café \U0001f468" + ZWJ + "\U0001f4bb end",
    "　",
    "ｆｕｌｌｗｉｄｔｈ",
    "한국어 텍스트",
    "العربية",
    "กำ",
]

WIDTHS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 20, 39, 40, 41, 60, 96]

# The versions this corpus is recorded under. `latest` and `13.0.0` produced
# byte-identical oracles until the derived cases below were added, which meant one
# of the four proved nothing a single hardcoded table would not also pass.
VERSIONS_UNDER_TEST = ["latest", "13.0.0", "9.0.0", "4.1.0"]


def differing_between(older: str, newer: str, limit: int = 12) -> list[str]:
    """Codepoints whose cell width differs between two tables.

    Derived, never chosen. `reviewer-profiler` established the need for this the
    expensive way: arrows, stars, circled digits and box drawing are all
    width-stable, so a sample picked for looking exotic produces a clean false
    negative. Their `width_probe_fixture.differing_codepoints` does this for one
    fixed pair; this is the same technique over an arbitrary pair, and the two
    should not drift.
    """
    from rich.cells import get_character_cell_size

    found = [
        chr(codepoint)
        for codepoint in range(0x0, 0x1FB00)
        if get_character_cell_size(chr(codepoint), newer)
        != get_character_cell_size(chr(codepoint), older)
    ]
    return found[:limit]


def derived_cases() -> list[str]:
    """One case per adjacent version pair, so no recorded oracle is redundant."""
    cases = []
    for older, newer in zip(VERSIONS_UNDER_TEST[1:], VERSIONS_UNDER_TEST[:-1]):
        sample = differing_between(older, newer)
        if sample:
            cases.append("".join(sample))
            cases.append("A" + "B".join(sample) + "Z")
    return cases


def main() -> None:
    unicode_version = os.environ.get("UNICODE_VERSION", "latest")
    output = Path(__file__).with_name(f"cell-oracle-{unicode_version}.json")

    cases = list(BASE_CASES) + derived_cases()
    cases += [text * 3 for text in BASE_CASES if text]
    cases += [TICK + " " + text for text in BASE_CASES]

    rows = [
        {
            "text": text,
            "cell_len": cell_len(text),
            "set_cell_size": {str(width): set_cell_size(text, width) for width in WIDTHS},
            # `split_text` has no contract above the string's own width: Rich's own
            # offset guess indexes past its span list and raises. Recording it there
            # would test a mode that is not the contract, and `set_cell_size` -- the
            # only caller -- never reaches it.
            # `chop_cells` folds a word too long for the line. Its fast path slices
            # by code points rather than cells, so ASCII and wide text take
            # structurally different routes and both need recording.
            "chop_cells": {
                str(width): chop_cells(text, width)
                for width in WIDTHS
                if width > 0
            },
            "split_text": {
                str(width): list(split_text(text, width))
                for width in WIDTHS
                if width <= cell_len(text)
            },
        }
        for text in cases
    ]

    payload = {
        "rich_version": package_version("rich"),
        "unicode_version": unicode_version,
        "widths": WIDTHS,
        "rows": rows,
    }
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=1))
    print(
        f"wrote {output.name} - {len(rows)} strings, "
        f"{len(rows)} cell_len + {len(rows) * len(WIDTHS)} set_cell_size + "
        f"{len(rows) * len(WIDTHS)} split_text cases, unicode {unicode_version}"
    )


if __name__ == "__main__":
    main()
