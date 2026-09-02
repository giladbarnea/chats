#!/usr/bin/env -S uv run
"""Freeze what `_read_output_renderable` renders for real `Read` results.

**The `Read` gutter is geometry, not highlighting.** `Syntax(..., line_numbers=True,
start_line=N)` puts a numbered column beside the code whatever lexer it finds, and only
a promoted family changes the colours inside it. So this records the **rendered lines**
rather than the lexer's name: a mis-resolved lexer shows up here as different bytes,
and a lexer that resolves differently without changing bytes is not a divergence.

Pairs are harvested from the frozen pool: a `Read` tool_use carrying `file_path`, and
the `tool_result` that names its id. Paths are ordered by a hash of the path, so a pool
that grows adds cases at the tail.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))
os.environ["HOME"] = tempfile.mkdtemp(prefix="ch-read-gutter-")

from rich.color import ColorType  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.syntax import Syntax  # noqa: E402

from chats.formatting import _read_output_renderable, _strip_read_line_numbers  # noqa: E402
from chats.theme import APP_THEME  # noqa: E402

POOL = Path("/private/tmp/ch-pool-snapshot")
WIDTHS = (40, 100)
# **Bodies are capped so the fixture is committable.** A `Read` result can be thousands
# of lines; the gutter's geometry is settled long before that, and the widest number
# column this reaches is what decides the layout.
MAX_BODY_LINES = 28


def hashed_order(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: hashlib.sha256(str(path).encode()).hexdigest())


def iter_blocks(record: object):
    stack = [record]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            yield item
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(part for part in parts if part)
    return ""


def harvest(limit: int) -> tuple[list[dict], int, collections.Counter]:
    cases: list[dict] = []
    found = 0
    extensions: collections.Counter = collections.Counter()
    seen_extensions: set[str] = set()
    for path in hashed_order(list(POOL.rglob("*.jsonl"))):
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        reads: dict[str, str] = {}
        for line in content.split("\n"):
            if '"Read"' not in line and '"tool_result"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for block in iter_blocks(record):
                if block.get("type") == "tool_use" and block.get("name") == "Read":
                    data = block.get("input")
                    identifier = block.get("id")
                    if isinstance(data, dict) and isinstance(identifier, str):
                        file_path = data.get("file_path")
                        if isinstance(file_path, str) and file_path:
                            reads[identifier] = file_path
                    continue
                if block.get("type") != "tool_result" or block.get("is_error"):
                    continue
                file_path = reads.get(block.get("tool_use_id") or "")
                if not file_path:
                    continue
                body = text_of(block.get("content", ""))
                if not body:
                    continue
                found += 1
                extension = Path(file_path).suffix.lower()
                extensions[extension] += 1
                body = "\n".join(body.split("\n")[:MAX_BODY_LINES])
                # Keep every extension at least once before repeating one, so the
                # corpus is not three thousand `.py` files.
                if extension in seen_extensions and len(cases) >= limit // 2:
                    continue
                seen_extensions.add(extension)
                if len(cases) >= limit:
                    continue
                cases.append({"file_path": file_path, "output_text": body})
    return cases, found, extensions


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=110)
    options = parser.parse_args()

    cases, found, extensions = harvest(options.limit)
    records = []
    for case in cases:
        code, start_line = _strip_read_line_numbers(case["output_text"])
        lexer = Syntax.guess_lexer(case["file_path"], code)
        for width in WIDTHS:
            console = Console(
                theme=APP_THEME, force_terminal=True, color_system="truecolor",
                width=width, legacy_windows=False,
            )
            rail = _read_output_renderable(case["output_text"], case["file_path"], "tool.result")
            lines = console.render_lines(rail, console.options.update_width(width), pad=False)
            records.append(
                {
                    "file_path": case["file_path"],
                    "output_text": case["output_text"],
                    "width": width,
                    "lexer": lexer,
                    "start_line": start_line,
                    "lines": [
                        [{"t": segment.text, "s": style_record(segment.style)} for segment in line]
                        for line in lines
                    ],
                }
            )

    payload = {
        "widths": list(WIDTHS),
        "found_in_pool": found,
        "extensions": dict(extensions.most_common(40)),
        "cases": records,
    }
    Path(options.out).write_text(json.dumps(payload, ensure_ascii=False))
    print(f"{len(records)} records over {len(cases)} cases from {found} real Read results")
    print("top extensions:", dict(extensions.most_common(12)))
    print("lexers:", dict(collections.Counter(r["lexer"] for r in records).most_common(15)))


if __name__ == "__main__":
    main()
