#!/usr/bin/env python3
"""Extend `rule-oracle.tsv` with the rows that separate the two `truncate_to_cells`.

F16 is two functions of the same name with different semantics: `cells.rs` models
Rich's `Text.truncate`, which goes through `set_cell_size` and **pads with a space**
when a double-width character cannot fit; `search_output.rs` accumulates to the
budget and appends the ellipsis with no padding. The existing 99-row table does not
tell them apart — it is green against both — so unifying on the recorded table alone
would be a change justified by an instrument that cannot see it.

This script does two things, in this order:

1. **Control.** Regenerate the existing 99 rows from live Rich and diff them against
   the recorded file. If they do not reproduce, this generator is not the same
   instrument that produced the table and its new rows are worthless.
2. **Extend.** Emit rows for wide and mixed-width titles at every width where the
   truncation lands inside a double-width character, which is where the two
   implementations disagree.

    uv run -p python3 python .../probes/rule_oracle_wide.py           # control only
    uv run -p python3 python .../probes/rule_oracle_wide.py --write   # rewrite the table
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from rich.console import Console

RECORDED = (
    Path(__file__).resolve().parents[2]
    / "engine-and-codex"
    / "probes"
    / "rule-oracle.tsv"
)

# Written beside this script rather than into `engine-and-codex`'s recorded table:
# their 99 rows are their evidence, and these rows are a different seat's addition
# for a different question. The Rust gate reads both files.
EXTENSION = Path(__file__).resolve().parent / "rule-oracle-wide.tsv"

# Titles that put a double-width character across every possible truncation
# boundary, plus one that mixes widths so the pad space is not always at the end.
EXTRA_TITLES = [
    "你好你好你好",
    "a你b好c你d",
    "你a好b你c",
]
EXTRA_WIDTHS = list(range(6, 22))


def render(title: str, width: int) -> str:
    buffer = io.StringIO()
    console = Console(file=buffer, width=width, force_terminal=False, no_color=True)
    console.rule(title=title, characters="─", style=None)
    return buffer.getvalue().rstrip("\n")


def recorded_rows() -> list[tuple[int, str, str]]:
    rows = []
    for line in RECORDED.read_text().splitlines()[1:]:
        width, title, expected = line.split("\t")
        rows.append((int(width), unquote(title), unquote(expected)))
    return rows


def unquote(value: str) -> str:
    inner = value.strip()[1:-1]
    return inner.replace("\\'", "'").replace("\\\\", "\\")


def quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    rows = recorded_rows()
    mismatches = [
        (width, title, expected, render(title, width))
        for width, title, expected in rows
        if render(title, width) != expected
    ]
    print(f"CONTROL: {len(rows)} recorded rows, {len(mismatches)} not reproduced by live Rich")
    for width, title, expected, actual in mismatches[:5]:
        print(f"    width {width} title {title!r}\n      recorded {expected!r}\n      live     {actual!r}")
    if mismatches:
        print(
            "CONTROL FAILED - this generator does not reproduce the recorded table, so "
            "any row it adds would be a different instrument's answer. Refusing to write."
        )
        return 1

    extra = [
        (width, title, render(title, width))
        for title in EXTRA_TITLES
        for width in EXTRA_WIDTHS
    ]
    known = {(width, title) for width, title, _ in rows}
    extra = [row for row in extra if (row[0], row[1]) not in known]
    print(f"EXTEND:  {len(extra)} new rows across {len(EXTRA_TITLES)} wide titles")

    if "--write" not in sys.argv:
        for width, title, line in extra[:6]:
            print(f"    {width}\t{quote(title)}\t{quote(line)}")
        print("\n(pass --write to write the extension table)")
        return 0

    header = RECORDED.read_text().splitlines()[0]
    body = [f"{width}\t{quote(title)}\t{quote(line)}" for width, title, line in extra]
    EXTENSION.write_text("\n".join([header, *body]) + "\n")
    print(f"wrote {len(body)} rows to {EXTENSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
