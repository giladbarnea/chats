#!/usr/bin/env -S uv run
"""Does the body oracle's recorder call `build_messages_group` the way the product does?

`_render_conversation_panel` passes `_build_tool_id_map(hit.messages)`.
`generate_body_oracle.py` passes `None`. This renders every tool case both ways and
prints the first differing line, so the answer is measured rather than argued.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

_PRIVATE_HOME = tempfile.mkdtemp(prefix="ch-tool-id-map-")
os.environ["HOME"] = _PRIVATE_HOME

from rich.console import Console

from chats.commands.common import _build_tool_id_map
from chats.formatting import build_messages_group
from chats.model import ConversationFlags
from chats.session_scan import SessionScan
from chats.theme import APP_THEME

sys.path.insert(0, str(Path.cwd() / "thoughts/2026-08-28-search-rust-rewrite/teammates/message-renderer/probes"))
from generate_body_oracle import CASES  # noqa: E402

# Importing the generator runs its module body, which points HOME at its own
# temporary pool. Take it back, or provider classification fails.
os.environ["HOME"] = _PRIVATE_HOME

WIDTH = 68


def render(messages, flags, tool_id_map) -> list[str]:
    console = Console(
        theme=APP_THEME, force_terminal=True, color_system="truecolor",
        width=WIDTH, legacy_windows=False,
    )
    group = build_messages_group(
        list(messages), flags, tool_id_map, highlight_regex=None, conversation_tag="aaaaaaaa"
    )
    lines = console.render_lines(group, console.options.update_width(WIDTH), pad=False)
    return ["".join(segment.text for segment in line).rstrip() for line in lines]


def main() -> None:
    home = Path(_PRIVATE_HOME)
    project = home / ".claude" / "projects" / "bodyproj"
    project.mkdir(parents=True)
    path = project / "aaaaaaaa-1111-4111-8111-aaaaaaaaaa01.jsonl"

    for case in CASES:
        if not case.get("flags", {}).get("show_tools"):
            continue
        path.write_text(case["jsonl"])
        flags = ConversationFlags(**case.get("flags", {}))
        messages = list(SessionScan.from_file(path, flags).messages)
        without = render(messages, flags, None)
        with_map = render(messages, flags, _build_tool_id_map(messages))
        verdict = "SAME" if without == with_map else "DIFFERS"
        print(f"\n=== {case['id']}  {verdict}  (map={_build_tool_id_map(messages)})")
        if verdict == "SAME":
            continue
        for index in range(max(len(without), len(with_map))):
            left = without[index] if index < len(without) else ""
            right = with_map[index] if index < len(with_map) else ""
            marker = "  " if left == right else "->"
            print(f"  {marker} none: {left!r}")
            print(f"     map : {right!r}")


if __name__ == "__main__":
    main()
