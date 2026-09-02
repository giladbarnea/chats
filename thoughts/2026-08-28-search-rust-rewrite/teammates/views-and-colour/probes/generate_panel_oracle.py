#!/usr/bin/env -S uv run
"""Record the exact bytes Rich's `Panel` emits for the conversation frame.

Only the frame. Body lines are plain text chosen to fit the interior, because
laying a message out into lines belongs to the session renderer, and a body line
that wraps would make this an oracle for two things at once.

Titles include one that overflows the box, which is the branch Rich truncates to
`width - 5` and closes with an ellipsis before the corner.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")
os.environ["HOME"] = "/Users/ada"

from rich import box  # noqa: E402
from rich.console import Console, Group  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from chats.theme import APP_THEME  # noqa: E402

OUTPUT = Path(__file__).with_name("panel-oracle.json")

BORDER_CYCLE = ["#5cc8a8", "#9d7cd8", "#d8a657", "#7aa2f7"]
WIDTHS = [24, 30, 40, 60, 96, 100, 120]

# (segment text, theme token) pairs, mirroring what `_panel_title` assembles.
TITLES = {
    "short": [("▎ ", "search.tick"), ("a title", "search.title")],
    "full": [
        ("▎ ", "search.tick"),
        ("a reasonable session title", "search.title"),
        ("  ·  ", "search.sep"),
        ("01234567", "search.id.head"),
        ("89abcdef", "search.id.tail"),
        ("  ·  ", "search.sep"),
        ("3d", "search.age.week"),
    ],
    "overflowing": [
        ("▎ ", "search.tick"),
        ("a session title far too long to fit inside any of these boxes", "search.title"),
        ("  ·  ", "search.sep"),
        ("01234567", "search.id.head"),
    ],
    "wide": [("▎ ", "search.tick"), ("你好你好你好你好你好", "search.title")],
    "fallback": [("▎ ", "search.tick"), ("(untitled session)", "search.title.fallback")],
}

BODIES = {
    "one": ["body line one"],
    # A body line **shorter than the interior and carrying a style**. Without it,
    # "the frame pads with unstyled spaces" is indistinguishable from "the padding
    # inherits the body's style" — every other body here is plain, so the corpus
    # proved the padding by luck. Found by `message-renderer` asking.
    "styled-short": ["\x00styled body"],
    "empty": [""],
    "several": ["first", "", "third line"],
    "none": [],
}


def main() -> None:
    rows = []
    for width in WIDTHS:
        for title_name, title_parts in TITLES.items():
            for body_name, body in BODIES.items():
                for ordinal in range(len(BORDER_CYCLE) + 1):
                    title = Text(no_wrap=True, overflow="ellipsis")
                    for text, token in title_parts:
                        title.append(text, style=token)
                    console = Console(
                        width=width,
                        force_terminal=True,
                        color_system="truecolor",
                        theme=APP_THEME,
                    )
                    with console.capture() as capture:
                        console.print(
                            Panel(
                                Group(*[Text(line[1:], style="search.title") if line.startswith("\x00") else Text(line) for line in body]),
                                title=title,
                                title_align="left",
                                border_style=BORDER_CYCLE[ordinal % len(BORDER_CYCLE)],
                                box=box.ROUNDED,
                                padding=(0, 1),
                            )
                        )
                    lines = capture.get().split("\n")
                    if lines and lines[-1] == "":
                        lines.pop()
                    rows.append(
                        {
                            "width": width,
                            "title": title_name,
                            "title_parts": title_parts,
                            "body": body,
                            "body_name": body_name,
                            "ordinal": ordinal,
                            "lines": lines,
                        }
                    )

    payload = {"border_cycle": BORDER_CYCLE, "widths": WIDTHS, "rows": rows}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=True, indent=1))
    print(
        f"wrote {OUTPUT.name} - {len(rows)} panels, "
        f"{sum(len(row['lines']) for row in rows)} rendered lines"
    )


if __name__ == "__main__":
    main()
