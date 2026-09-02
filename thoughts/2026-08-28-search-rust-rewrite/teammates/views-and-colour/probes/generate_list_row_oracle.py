#!/usr/bin/env -S uv run
"""Record the exact bytes Python's `_build_search_list_row` emits.

Drives the real function in `src/chats/commands/search.py`, printed the way the
product prints it -- as a `Group`, which is the only mode where the `Text`'s own
`no_wrap` and `overflow` survive `Console.print`. Printing a bare `Text` routes
through `Text.join` and silently drops both.

`resolve.get_display_session_id` is stubbed because it resolves an id from a real
session file on disk. It belongs to parsing, not to views, and stubbing it is what
lets the grid vary the id freely.

Widths deliberately exclude 80: it is Rich's fallback constant, so a comparison
there cannot tell a correct width from no measurement at all.
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, "src")

HOME = "/Users/ada"
os.environ["HOME"] = HOME

from rich.console import Console  # noqa: E402

from chats.commands import search as search_command  # noqa: E402
from chats.theme import APP_THEME  # noqa: E402

OUTPUT = Path(__file__).with_name("list-row-oracle.json")

NOW = datetime(2026, 6, 15, 12, 0, 0)
DAY = 86400

WIDTHS = [4, 8, 9, 10, 11, 12, 20, 30, 40, 60, 96, 100, 120]

HEADLINES = [
    "a short title",
    "(untitled session)",
    "a considerably longer session title that will not fit inside a narrow row",
    "你好你好你好你好你好你好你好你好你好你好",
    "ab你好 mixed width headline that runs on and on and on",
    "café",
    "",
]

DIRECTORIES = [
    "/Users/ada/dev/chats",
    "/Users/adaX/dev/chats",
    "/Users/ada-backup/some/deeply/nested/project/directory/tree/here",
    "/opt/tools",
    None,
]

AGES = [30, 3600 * 3, 3 * DAY, 10 * DAY, 45 * DAY, 200 * DAY, 400 * DAY, None]


@dataclass
class Meta:
    path: Path
    mtime: datetime | None
    provider: str


@dataclass
class Hit:
    metadata: Meta
    cwd: str | None
    last_custom_title: str
    matching_summaries: list
    matches: list
    match_count: int


def main() -> None:
    search_command.resolve.get_display_session_id = lambda path: path.name

    rows = []
    for width in WIDTHS:
        for headline in HEADLINES:
            for directory in DIRECTORIES:
                for age in AGES:
                    for show_provider in (False, True):
                        for match_count in (1, 3, 128):
                            session_id = "0123456789abcdef-0000-1111"
                            mtime = None if age is None else NOW - timedelta(seconds=age)
                            hit = Hit(
                                metadata=Meta(Path(session_id), mtime, "claude"),
                                cwd=directory,
                                last_custom_title=headline,
                                matching_summaries=[],
                                matches=[],
                                match_count=match_count,
                            )
                            console = Console(
                                width=width,
                                force_terminal=True,
                                color_system="truecolor",
                                theme=APP_THEME,
                            )
                            with console.capture() as capture:
                                console.print(
                                    search_command._build_search_list_row(
                                        hit,
                                        now=NOW,
                                        width=width,
                                        show_provider=show_provider,
                                    )
                                )
                            lines = capture.get().split("\n")
                            # `_headline` derives both the string and the
                            # fallback flag from the hit. Recording the input
                            # instead of its answer records a different case
                            # than the one that was rendered: an empty custom
                            # title is falsy, so it falls through to
                            # "(untitled session)" in the italic fallback style.
                            derived, is_fallback = search_command._headline(hit)
                            rows.append(
                                {
                                    "width": width,
                                    "session_id": session_id,
                                    "headline": derived,
                                    "headline_is_fallback": is_fallback,
                                    "directory": directory,
                                    "provider": "claude",
                                    "show_provider": show_provider,
                                    "match_count": match_count,
                                    "age_seconds": age,
                                    "title_line": lines[0],
                                    "facts_line": lines[1],
                                }
                            )

    payload = {"home": HOME, "widths": WIDTHS, "rows": rows}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=True, indent=1))
    print(f"wrote {OUTPUT.name} - {len(rows)} rendered rows across {len(WIDTHS)} widths")


if __name__ == "__main__":
    main()
