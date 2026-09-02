#!/usr/bin/env python3
"""Extend the wrap oracle with the rows where the two `chop_cells` disagree.

`engine-and-codex`'s `wrap-oracle.tsv` is 235 rows of ASCII error messages across
five widths, built so the wrap boundary lands in every position relative to a
space. It cannot see F17: the two `chop_cells` in this tree differ only when a
single grapheme is wider than the whole line, which needs a double-width character
and a narrow width.

Order matters here, as with the rule table:

1. **Control.** Regenerate all 235 recorded rows from live Rich and diff. If they
   do not reproduce, this generator is not the same instrument that produced the
   recorded table and its new rows are worthless.
2. **Extend.** Emit wide-character rows at widths 1 to 6, where a CJK grapheme
   does not fit the line.

    uv run -p python3 python .../probes/wrap_oracle_cjk.py           # control only
    uv run -p python3 python .../probes/wrap_oracle_cjk.py --write   # write the table
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.text import Text

RECORDED = (
    Path(__file__).resolve().parents[2]
    / "engine-and-codex"
    / "probes"
    / "wrap-oracle.tsv"
)
EXTENSION = Path(__file__).resolve().parent / "wrap-oracle-cjk.tsv"

WIDE_MESSAGES = [
    "你好世界",
    "a 你好 b",
    "你好 世界",
    "ab 你 cd",
    "你a好b世c",
]
WIDE_WIDTHS = [1, 2, 3, 4, 5, 6]


def wrap(message: str, width: int) -> str:
    lines = Text(message).wrap(_console(), width)
    return "\n".join(line.plain for line in lines)


_CONSOLE = None


def _console():
    global _CONSOLE
    if _CONSOLE is None:
        from rich.console import Console

        _CONSOLE = Console(width=200)
    return _CONSOLE


def unquote(value: str) -> str:
    return eval(value)  # noqa: S307 - the tables carry Python reprs of str literals


def quote(value: str) -> str:
    return repr(value)


def recorded_rows() -> list[tuple[int, str, str]]:
    rows = []
    for line in RECORDED.read_text().splitlines()[1:]:
        if not line:
            continue
        width, message, wrapped = line.split("\t")
        rows.append((int(width), unquote(message), unquote(wrapped)))
    return rows


def main() -> int:
    rows = recorded_rows()
    mismatches = [
        (width, message, expected, wrap(message, width))
        for width, message, expected in rows
        if wrap(message, width) != expected
    ]
    print(f"CONTROL: {len(rows)} recorded rows, {len(mismatches)} not reproduced by live Rich")
    for width, message, expected, actual in mismatches[:4]:
        print(f"    width {width} {message!r}\n      recorded {expected!r}\n      live     {actual!r}")
    if mismatches:
        print(
            "CONTROL FAILED - this generator does not reproduce the recorded table, so "
            "any row it adds would be a different instrument's answer. Refusing to write."
        )
        return 1

    extra = [
        (width, message, wrap(message, width))
        for message in WIDE_MESSAGES
        for width in WIDE_WIDTHS
    ]
    print(f"EXTEND:  {len(extra)} wide-character rows")
    if "--write" not in sys.argv:
        for width, message, wrapped in extra[:6]:
            print(f"    {width}\t{quote(message)}\t{quote(wrapped)}")
        print("\n(pass --write to write the extension table)")
        return 0

    header = RECORDED.read_text().splitlines()[0]
    body = [f"{width}\t{quote(message)}\t{quote(wrapped)}" for width, message, wrapped in extra]
    EXTENSION.write_text("\n".join([header, *body]) + "\n")
    print(f"wrote {len(body)} rows to {EXTENSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
