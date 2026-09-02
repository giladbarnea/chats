#!/usr/bin/env -S uv run
"""Record the bytes of a whole conversation panel **with a real message body**.

`views-and-colour`'s panel oracle gates the frame, the title and the facts line
with a stand-in body, deliberately: laying a message out belongs to this seat. This
one puts the real body in and gates the three together — which is the only thing
that proves the sink rather than its parts.

Composition copied from `_render_conversation_panel` rather than approximated:
the facts line and a blank line ahead of the body when metadata is on, the title
built by `_panel_title`, `box.ROUNDED`, `title_align="left"`, `padding=(0, 1)`, and
the border hue cycling on the ordinal.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

_PRIVATE_HOME = tempfile.mkdtemp(prefix="ch-panel-sink-")
os.environ["HOME"] = _PRIVATE_HOME

from rich import box  # noqa: E402
from rich.console import Console, Group  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from chats.commands import search as search_command  # noqa: E402
from chats.formatting import build_messages_group  # noqa: E402
from chats.model import ConversationFlags  # noqa: E402
from chats.session_scan import SessionScan  # noqa: E402
from chats.theme import APP_THEME  # noqa: E402

WIDTHS = (40, 68, 100)
BORDER_CYCLE = ["#5cc8a8", "#9d7cd8", "#d8a657", "#7aa2f7"]
NOW = datetime(2026, 9, 1, 12, 0, 0)
SESSION_ID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaa01"


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
    messages: list
    matches: list
    match_count: int


def entry(index: int, role: str, text: str, minute: int) -> str:
    message: dict = {"role": role, "content": text}
    if role == "assistant":
        message["model"] = "claude-sonnet-4-6"
    return json.dumps(
        {
            "type": "user" if role == "user" else "assistant",
            "uuid": f"u{index}",
            "timestamp": f"2026-08-20T17:{minute:02d}:00",
            "message": message,
            "cwd": "/tmp/panelproj",
        }
    )


def session(*texts: tuple[str, str]) -> str:
    return "\n".join(
        entry(index, role, text, index) for index, (role, text) in enumerate(texts)
    )


CASES: list[dict] = [
    {"id": "one-message", "jsonl": session(("user", "a needle in the body"))},
    {
        "id": "two-messages",
        "jsonl": session(("user", "first with needle"), ("assistant", "second reply")),
    },
    {
        "id": "markdown-body",
        "jsonl": session(("assistant", "A **bold** needle.\n\n- one\n- two\n\n> quoted")),
    },
    {
        "id": "wrapping-body",
        "jsonl": session(("user", "the needle sits in a line long enough to wrap at every recorded width without fail")),
    },
    {
        "id": "plain-fence",
        "jsonl": session(("assistant", "before\n\n```text\na needle in a plain block\n```\n\nafter")),
    },
    {
        "id": "table-body",
        "jsonl": session(("assistant", "| a | needle |\n| - | - |\n| 1 | 2 |")),
    },
    {"id": "wide-characters", "jsonl": session(("user", "你好你好你好你好你好你好 needle"))},
]

HIGHLIGHT = re.compile("needle")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    project = Path(_PRIVATE_HOME) / ".claude" / "projects" / "panelproj"
    project.mkdir(parents=True)
    path = project / f"{SESSION_ID}.jsonl"

    records = []
    ordinal = 0
    for case in CASES:
        path.write_text(case["jsonl"])
        flags = ConversationFlags()
        scan = SessionScan.from_file(path, flags)
        messages = list(scan.messages)
        matches = [
            message
            for message in messages
            if "needle" in (message.text or "")
        ] or messages[:1]
        for width in WIDTHS:
            for emit_metadata in (True, False):
                for full in (False, True):
                    for highlight in (None, HIGHLIGHT):
                        hit = Hit(
                            metadata=Meta(path, NOW, "claude"),
                            cwd="/tmp/panelproj",
                            last_custom_title="a recorded panel",
                            matching_summaries=[],
                            messages=messages,
                            matches=matches,
                            match_count=len(matches),
                        )
                        display = messages if full else matches
                        console = Console(
                            width=width,
                            force_terminal=True,
                            color_system="truecolor",
                            theme=APP_THEME,
                        )
                        body = build_messages_group(
                            display,
                            flags,
                            None,
                            highlight_regex=highlight,
                            conversation_tag=SESSION_ID[:8],
                        )
                        rows = []
                        if emit_metadata:
                            rows.append(search_command._panel_facts_line(hit, width=width))
                            rows.append(Text(""))
                        rows.append(body)
                        with console.capture() as capture:
                            console.print(
                                Panel(
                                    Group(*rows),
                                    title=search_command._panel_title(hit, width=width, now=NOW),
                                    title_align="left",
                                    border_style=BORDER_CYCLE[ordinal % len(BORDER_CYCLE)],
                                    box=box.ROUNDED,
                                    padding=(0, 1),
                                )
                            )
                        lines = capture.get().split("\n")
                        if lines and lines[-1] == "":
                            lines.pop()
                        records.append(
                            {
                                "id": case["id"],
                                "jsonl": case["jsonl"],
                                "width": width,
                                "emit_metadata": emit_metadata,
                                "full": full,
                                "highlight": HIGHLIGHT.pattern if highlight else None,
                                "ordinal": ordinal,
                                "match_indices": [messages.index(m) for m in matches],
                                "lines": lines,
                            }
                        )
                        ordinal += 1

    Path(options.out).write_text(
        json.dumps({"now": NOW.isoformat(), "session_id": SESSION_ID, "cases": records},
                   ensure_ascii=False)
    )
    print(f"{len(records)} records over {len(CASES)} cases -> {options.out}")


if __name__ == "__main__":
    main()
