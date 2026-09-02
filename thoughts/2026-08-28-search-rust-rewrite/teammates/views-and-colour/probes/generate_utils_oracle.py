#!/usr/bin/env -S uv run
"""Record `src/chats/utils.py`'s answers for the four display helpers views uses.

Three of the four are preserved *because* they are wrong, so this oracle is the
only thing standing between a helpful repair and a silent divergence on every
coloured row. The age sweep is dense around each bucket edge, in both functions,
because the whole point is that their edges do not line up.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "src")

from chats.utils import age_style, collapse_home, elide_to_width, humanize_age

OUTPUT = Path(__file__).with_name("utils-oracle.json")

DAY = 86400
BUCKET_EDGES = [60, 3600, DAY, 7 * DAY, 30 * DAY, 365 * DAY]
AGE_SECONDS = sorted(
    {0, 1, 30, 59, 59.9}
    | {edge + offset for edge in BUCKET_EDGES for offset in (-2, -1, -0.5, 0, 0.5, 1, 2)}
    | {n * DAY for n in range(0, 400, 7)}
    | {n * DAY + 0.5 for n in (359, 360, 361, 364, 365, 366)}
    | {n * 60 for n in range(0, 60, 7)}
    | {n * 3600 for n in range(0, 24)}
)

ELISION_TEXTS = [
    "",
    "a",
    "hello world",
    "/a/very/long/path/here",
    "/Users/ada/dev/chats/thoughts/2026-08-28",
    "你好你好你好你好",
    "ab你好" * 4,
    "café",
    "café",
    "İstanbul is a long headline that will not fit",
    "\U0001f468‍\U0001f4bb technologist headline",
    "(untitled session)",
]
ELISION_WIDTHS = [0, 1, 2, 3, 4, 5, 8, 11, 12, 16, 20, 40, 100]

HOME = "/Users/ada"
PATHS = [
    "/Users/ada",
    "/Users/ada/",
    "/Users/ada/dev/chats",
    "/Users/adaX/dev",
    "/Users/ada-backup/x",
    "/Users/adam/dev",
    "/Users/ad/dev",
    "/Users/adaada/dev",
    "/opt/tools",
    "",
    "/Users/ada/你好",
]


def main() -> None:
    base = datetime(2026, 6, 15, 12, 0, 0)
    ages = []
    for seconds in AGE_SECONDS:
        then = base - timedelta(seconds=seconds)
        ages.append(
            {
                "seconds": seconds,
                "label": humanize_age(then, base),
                "style": age_style(then, base),
            }
        )

    elisions = [
        {
            "text": text,
            "width": width,
            "where": where,
            "result": elide_to_width(text, width, where=where),
        }
        for text in ELISION_TEXTS
        for width in ELISION_WIDTHS
        for where in ("tail", "middle")
    ]

    # `collapse_home` reads `Path.home()`, so the oracle is recorded under a
    # pinned HOME rather than this machine's.
    os.environ["HOME"] = HOME
    homes = [{"path": path, "home": HOME, "result": collapse_home(path)} for path in PATHS]

    payload = {"ages": ages, "elisions": elisions, "collapse_home": homes}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=True, indent=1))
    print(
        f"wrote {OUTPUT.name} - {len(ages)} ages, {len(elisions)} elisions, "
        f"{len(homes)} paths"
    )


if __name__ == "__main__":
    main()
