#!/usr/bin/env -S uv run
"""Record what `build_messages_group` renders, as lines of styled runs.

The gate for the message body: badges, part ordering, the rule between messages,
the blank lines, the left rails, and the search highlight painted into a body.

**Timestamps in the corpus are naive on purpose.** `_message_timestamp_datetime`
converts an offset-bearing timestamp to local time, which would make every recorded
date depend on the recorder's `TZ`. Offsets are covered end to end by the pty
differential, which pins `TZ`; this gate stays independent of it.

**The corpus includes a match straddling a style boundary**, because the product
paints the highlight per rendered segment and therefore *misses* it — a behaviour
that is wrong, preserved, and unreachable by a fixture built from unformatted text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

# Provider classification asks whether the path sits under `~/.claude/projects`, so
# the corpus's private pool has to *be* the home while it is being read.
_PRIVATE_HOME = tempfile.mkdtemp(prefix="ch-body-oracle-")
os.environ["HOME"] = _PRIVATE_HOME

from rich.color import ColorType
from rich.console import Console

from chats.commands.common import _build_tool_id_map
from chats.formatting import build_messages_group
from chats.model import ConversationFlags
from chats.session_scan import SessionScan
from chats.theme import APP_THEME
from chats.model import Message

WIDTHS = (24, 40, 68, 100)


def entry(index: int, role: str, text: str, *, model: str | None = None, minute: int = 0) -> str:
    message: dict = {"role": role, "content": text}
    if model is not None:
        message["model"] = model
    return json.dumps(
        {
            "type": "user" if role == "user" else "assistant",
            "uuid": f"u{index}",
            "timestamp": f"2026-08-20T17:{minute:02d}:00",
            "message": message,
            "cwd": "/tmp/bodyproj",
        }
    )


def session(*texts: tuple[str, str]) -> str:
    return "\n".join(
        entry(index, role, text, model="claude-sonnet-4-6" if role == "assistant" else None, minute=index)
        for index, (role, text) in enumerate(texts)
    )


CASES: list[dict] = [
    {"id": "single-text", "jsonl": session(("user", "Codex needle five body"))},
    {
        "id": "two-messages",
        "jsonl": session(("user", "first message"), ("assistant", "second message")),
    },
    {
        "id": "markdown-body",
        "jsonl": session(("assistant", "A **bold** claim and *emphasis*.\n\n- one\n- two\n\n> quoted")),
    },
    {
        "id": "wrapping-body",
        "jsonl": session(("user", "The quick brown fox jumps over the lazy dog again and again and again.")),
    },
    {
        "id": "heading-and-rule",
        "jsonl": session(("assistant", "# Title\n\nbody text\n\n---\n\nafter")),
    },
    {
        "id": "wide-characters",
        "jsonl": session(("user", "你好你好你好你好你好你好你好你好你好你好")),
    },
    {
        "id": "tag-like-text",
        "jsonl": session(("user", "see <SOURCE> and </div> here")),
    },
    {
        "id": "highlight-plain",
        "jsonl": session(("user", "a needle in a haystack, needle again")),
        "highlight": ["needle"],
    },
    {
        "id": "highlight-across-style-boundary",
        "jsonl": session(("user", "the word **hel**lo is split, and hello is not")),
        "highlight": ["hello"],
        "note": "the split occurrence is NOT painted; the whole one is",
    },
    {
        "id": "highlight-case-insensitive",
        "jsonl": session(("user", "Needle and needle and NEEDLE")),
        "highlight": ["needle"],
        "case_sensitive": False,
    },
    {
        "id": "highlight-folding-both-directions",
        "jsonl": session(("user", "İstanbul and ﬀ and iff")),
        "highlight": ["i"],
        "case_sensitive": False,
        "note": "İ folds longer, ﬀ folds shorter; neither may shift a span",
    },
    {
        "id": "highlight-inside-bold",
        "jsonl": session(("user", "**a needle inside bold** and outside")),
        "highlight": ["needle"],
    },
    {
        "id": "thinking",
        "jsonl": "\n".join(
            [
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "a1",
                        "timestamp": "2026-08-20T17:01:00",
                        "message": {
                            "role": "assistant",
                            "model": "claude-sonnet-4-6",
                            "content": [
                                {"type": "thinking", "thinking": "a long private thought that wraps at the narrow widths"},
                                {"type": "text", "text": "the visible answer"},
                            ],
                        },
                        "cwd": "/tmp/bodyproj",
                    }
                )
            ]
        ),
        "flags": {"show_thinking": True},
    },
    {
        "id": "highlight-not-painted-in-a-thinking-rail",
        "jsonl": "{\"type\": \"assistant\", \"uuid\": \"a1\", \"timestamp\": \"2026-08-20T17:01:00\", \"message\": {\"role\": \"assistant\", \"model\": \"claude-sonnet-4-6\", \"content\": [{\"type\": \"thinking\", \"thinking\": \"a needle hides in this private thought\"}, {\"type\": \"text\", \"text\": \"a needle in the visible answer\"}]}, \"cwd\": \"/tmp/bodyproj\"}",
        "flags": {"show_thinking": True},
        "highlight": ["needle"],
        "note": "the visible text is painted and the thinking rail is NOT: no rail carries the regex",
    },    {
        "id": "empty-first-message",
        "jsonl": "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "uuid": "u0",
                        "timestamp": "2026-08-20T17:00:00",
                        "message": {"role": "user", "content": ""},
                        "cwd": "/tmp/bodyproj",
                    }
                ),
                entry(1, "assistant", "the only visible message", model="claude-sonnet-4-6", minute=1),
            ]
        ),
        "note": "the rule still appears above the second message: Python separates on the enumerate index",
    },
    # **Tool parts, added 2026-09-01 to make a vacuously-green assertion fail.** The
    # unsupported check above passed only because no case here carried a tool part,
    # and `Part::Tool` goes straight to `Unsupported("tool")` — so `ch search -t` with
    # colour panicked the panel sink and truncated a scan that had already printed.
    # **These are red until styled tool rendering is built**, which is the point: the
    # gap is visible before it is closed, not after.
    {
        "id": "tool-call-and-result",
        "jsonl": '{"type": "assistant", "uuid": "a1", "timestamp": "2026-08-20T17:01:00", "message": {"role": "assistant", "content": [{"type": "text", "text": "running it"}, {"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "ls -la /tmp", "description": "list the directory"}}], "model": "claude-sonnet-4-6"}, "cwd": "/tmp/bodyproj"}\n{"type": "user", "uuid": "u1", "timestamp": "2026-08-20T17:02:00", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "total 0\\ndrwxr-xr-x  2 a b 64 Aug 20 17:00 .\\n"}]}, "cwd": "/tmp/bodyproj"}',
        "flags": {"show_tools": True},
        "note": "the 87.6% path: a header, a coloured rail, and a fenced markdown body",
    },
    {
        "id": "tool-error-result",
        "jsonl": '{"type": "assistant", "uuid": "a1", "timestamp": "2026-08-20T17:01:00", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_2", "name": "Bash", "input": {"command": "false"}}], "model": "claude-sonnet-4-6"}, "cwd": "/tmp/bodyproj"}\n{"type": "user", "uuid": "u1", "timestamp": "2026-08-20T17:02:00", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_2", "is_error": true, "content": "Error: command failed with exit 1"}]}, "cwd": "/tmp/bodyproj"}',
        "flags": {"show_tools": True},
        "note": "is_error picks the error accent and appends `  ·  error` to the header",
    },
    {
        "id": "tool-read-result-promoted-extension",
        "jsonl": '{"type": "assistant", "uuid": "a1", "timestamp": "2026-08-20T17:01:00", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_3", "name": "Read", "input": {"file_path": "/tmp/bodyproj/example.py"}}], "model": "claude-sonnet-4-6"}, "cwd": "/tmp/bodyproj"}\n{"type": "user", "uuid": "u1", "timestamp": "2026-08-20T17:02:00", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_3", "content": "    12\\tdef add(a, b):\\n    13\\t    return a + b\\n    14\\t"}]}, "cwd": "/tmp/bodyproj"}',
        "flags": {"show_tools": True},
        "note": "the Read gutter: `<n>\\t` stripped, line numbers restored from 12, .py lexed",
    },
    {
        "id": "tool-read-result-unported-extension",
        "jsonl": '{"type": "assistant", "uuid": "a1", "timestamp": "2026-08-20T17:01:00", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_4", "name": "Read", "input": {"file_path": "/tmp/bodyproj/notes.md"}}], "model": "claude-sonnet-4-6"}, "cwd": "/tmp/bodyproj"}\n{"type": "user", "uuid": "u1", "timestamp": "2026-08-20T17:02:00", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_4", "content": "     1\\t# A heading\\n     2\\t\\n     3\\tbody text\\n"}]}, "cwd": "/tmp/bodyproj"}',
        "flags": {"show_tools": True},
        "note": "markdown is the largest real Read extension and is not promoted: gutter, no colour",
    },
    {
        "id": "tool-edit-diff",
        "jsonl": '{"type": "assistant", "uuid": "a1", "timestamp": "2026-08-20T17:01:00", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_5", "name": "Edit", "input": {"file_path": "/tmp/bodyproj/example.py", "old_string": "def add(a, b):\\n    return a + b\\n", "new_string": "def add(a: int, b: int) -> int:\\n    return a + b\\n"}}], "model": "claude-sonnet-4-6"}, "cwd": "/tmp/bodyproj"}',
        "flags": {"show_tools": True},
        "note": "Edit renders a unified diff of old_string against new_string, not its content",
    },
    {
        "id": "tool-header-key-argument-elided",
        "jsonl": '{"type": "assistant", "uuid": "a1", "timestamp": "2026-08-20T17:01:00", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_6", "name": "Read", "input": {"file_path": "/tmp/bodyproj/a-very-long-directory-name/a-very-long-directory-name/a-very-long-directory-name/a-very-long-directory-name/file.py"}}], "model": "claude-sonnet-4-6"}, "cwd": "/tmp/bodyproj"}',
        "flags": {"show_tools": True},
        "note": "the key argument is elided at the width it renders at, inside the panel and rail",
    },
]


def colour(value) -> dict | None:
    if value is None:
        return None
    if value.type in (ColorType.STANDARD, ColorType.EIGHT_BIT):
        return {"palette": value.number}
    if value.type is ColorType.TRUECOLOR:
        triplet = value.triplet
        return {"triplet": [triplet.red, triplet.green, triplet.blue]}
    return None


def style_record(style) -> dict | None:
    if style is None:
        return None
    record: dict = {}
    for name in ("bold", "dim", "italic", "underline", "reverse", "strike"):
        set_value = getattr(style, name)
        if set_value is not None:
            record[name] = set_value
    if (foreground := colour(style.color)) is not None:
        record["fg"] = foreground
    if (background := colour(style.bgcolor)) is not None:
        record["bg"] = background
    if style.link:
        record["link"] = style.link
    return record or None


def highlight_regex(literals: list[str], case_sensitive: bool):
    """`_build_highlight_regex`, over already-chosen literals."""
    ordered = sorted(set(literals), key=len, reverse=True)
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile("|".join(re.escape(literal) for literal in ordered), flags), (
        "|".join(re.escape(literal) for literal in ordered)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    options = parser.parse_args()

    home = Path(_PRIVATE_HOME)
    project = home / ".claude" / "projects" / "bodyproj"
    project.mkdir(parents=True)

    records = []
    for case in CASES:
        path = project / "aaaaaaaa-1111-4111-8111-aaaaaaaaaa01.jsonl"
        path.write_text(case["jsonl"])
        flags = ConversationFlags(**case.get("flags", {}))
        scan = SessionScan.from_file(path, flags)
        messages: tuple[Message, ...] = scan.messages
        pattern = None
        regex = None
        case_sensitive = case.get("case_sensitive", True)
        if "highlight" in case:
            regex, pattern = highlight_regex(case["highlight"], case_sensitive)
        for width in WIDTHS:
            console = Console(
                theme=APP_THEME,
                force_terminal=True,
                color_system="truecolor",
                width=width,
                legacy_windows=False,
            )
            group = build_messages_group(
                list(messages),
                flags,
                # **The product's shape, and passing `None` here was a recorder
                # defect.** `_render_conversation_panel` passes
                # `_build_tool_id_map(hit.messages)`. With `None` no tool result can
                # resolve its name, so every result rendered as `Tool` and four
                # behaviours became unreachable at once: the `Read` gutter, the result
                # header label, `_tool_result_label`'s `output`, and the `Bash` badge
                # on a bash-result message.
                _build_tool_id_map(list(messages)),
                highlight_regex=regex,
                conversation_tag="aaaaaaaa",
            )
            lines = console.render_lines(group, console.options.update_width(width), pad=False)
            records.append(
                {
                    "id": case["id"],
                    "width": width,
                    "jsonl": case["jsonl"],
                    "flags": case.get("flags", {}),
                    "highlight": pattern,
                    "ignorecase": not case_sensitive,
                    "note": case.get("note"),
                    "lines": [
                        [{"t": segment.text, "s": style_record(segment.style)} for segment in line]
                        for line in lines
                    ],
                }
            )

    payload = {"widths": list(WIDTHS), "cases": records}
    Path(options.out).write_text(json.dumps(payload, ensure_ascii=False))
    print(f"{len(records)} records over {len(CASES)} cases -> {options.out}")


if __name__ == "__main__":
    main()
