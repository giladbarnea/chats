#!/usr/bin/env -S uv run
"""Record the bytes of a whole conversation panel built from the real
`_panel_title` and `_panel_facts_line`.

The frame is already gated against Rich separately. This gates the two segment
lists that go into it, and the three of them together, against Python.

The body is plain text rather than a rendered message group: laying a message out
belongs to the session renderer, and including it would make this an oracle for
two owners at once. `emit_metadata` is modelled by placing the facts line and a
blank line ahead of the body, which is what `_render_conversation_panel` does.
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

from rich import box  # noqa: E402
from rich.console import Console, Group  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from chats.commands import search as search_command  # noqa: E402
from chats.theme import APP_THEME  # noqa: E402

OUTPUT = Path(__file__).with_name("panel-view-oracle.json")

NOW = datetime(2026, 6, 15, 12, 0, 0)
DAY = 86400
BORDER_CYCLE = ["#5cc8a8", "#9d7cd8", "#d8a657", "#7aa2f7"]

WIDTHS = [24, 30, 40, 60, 96, 100, 120]
HEADLINES = [
    "a short title",
    "a considerably longer session title that will not fit inside a narrow panel",
    "你好你好你好你好你好你好你好你好",
    "café",
    "",
]
DIRECTORIES = [
    "/Users/ada/dev/chats",
    "/Users/adaX/dev/chats",
    "/Users/ada-backup/some/deeply/nested/project/directory/tree",
    None,
]
AGES = [30, 3 * DAY, 45 * DAY, 400 * DAY, None]
SESSION_IDS = ["0123456789abcdef-0000-1111", "short-id"]


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
    ordinal = 0
    for width in WIDTHS:
        for headline in HEADLINES:
            for directory in DIRECTORIES:
                for age in AGES:
                    for session_id in SESSION_IDS:
                        for emit_metadata in (False, True):
                            mtime = None if age is None else NOW - timedelta(seconds=age)
                            hit = Hit(
                                metadata=Meta(Path(session_id), mtime, "claude"),
                                cwd=directory,
                                last_custom_title=headline,
                                matching_summaries=[],
                                matches=[],
                                match_count=3,
                            )
                            console = Console(
                                width=width,
                                force_terminal=True,
                                color_system="truecolor",
                                theme=APP_THEME,
                            )
                            body = [Text("body line")]
                            panel_rows = []
                            if emit_metadata:
                                panel_rows.append(
                                    search_command._panel_facts_line(hit, width=width)
                                )
                                panel_rows.append(Text(""))
                            panel_rows.extend(body)
                            with console.capture() as capture:
                                console.print(
                                    Panel(
                                        Group(*panel_rows),
                                        title=search_command._panel_title(
                                            hit, width=width, now=NOW
                                        ),
                                        title_align="left",
                                        border_style=BORDER_CYCLE[
                                            ordinal % len(BORDER_CYCLE)
                                        ],
                                        box=box.ROUNDED,
                                        padding=(0, 1),
                                    )
                                )
                            lines = capture.get().split("\n")
                            if lines and lines[-1] == "":
                                lines.pop()
                            derived, is_fallback = search_command._headline(hit)
                            rows.append(
                                {
                                    "width": width,
                                    "session_id": session_id,
                                    "headline": derived,
                                    "headline_is_fallback": is_fallback,
                                    "directory": directory,
                                    "provider": "claude",
                                    "match_count": 3,
                                    "age_seconds": age,
                                    "emit_metadata": emit_metadata,
                                    "ordinal": ordinal,
                                    "lines": lines,
                                }
                            )
                            ordinal += 1

    payload = {"home": HOME, "border_cycle": BORDER_CYCLE, "rows": rows}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=True, indent=1))
    print(
        f"wrote {OUTPUT.name} - {len(rows)} panels, "
        f"{sum(len(row['lines']) for row in rows)} rendered lines"
    )


if __name__ == "__main__":
    main()
