#!/usr/bin/env -S uv run
"""Freeze `Syntax.guess_lexer`'s answer for real `Read` paths and bodies.

**The render oracle cannot grade the lexer resolution on its own.** It holds whole
rendered blocks, so it is expensive per case and thin in the tail — and the tail is
where the resolution is decided. A `.js` file that Pygments hands to a template
delegate renders **plain** where an extension-only answer would colour it, and a
144-record render corpus happened to contain none.

So this is the cheap, wide half: path, body and the alias Rich returns, with the body
truncated and the expectation computed **on the truncated body**, so the pair is
self-consistent rather than approximately real.
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
os.environ["HOME"] = tempfile.mkdtemp(prefix="ch-read-lexer-")

from rich.syntax import Syntax  # noqa: E402

from chats.formatting import _strip_read_line_numbers  # noqa: E402

POOL = Path("/private/tmp/ch-pool-snapshot")
MAX_BODY_LINES = 60
# Extensions the seven promoted families claim, which is where a wrong answer changes
# what the screen shows.
PROMOTED_EXTENSIONS = {
    ".ts", ".tsx", ".py", ".pyi", ".pyw", ".js", ".mjs", ".cjs", ".jsm",
    ".json", ".jsonl", ".sh", ".bash", ".zsh", ".ksh", ".sql", ".sc",
}


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--per-extension", type=int, default=12)
    options = parser.parse_args()

    cases: list[dict] = []
    per_extension: collections.Counter = collections.Counter()
    aliases: collections.Counter = collections.Counter()
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
                extension = Path(file_path).suffix.lower()
                limit = options.per_extension * (3 if extension in PROMOTED_EXTENSIONS else 1)
                if per_extension[extension] >= limit:
                    continue
                body = "\n".join(body.split("\n")[:MAX_BODY_LINES])
                code, _ = _strip_read_line_numbers(body)
                alias = Syntax.guess_lexer(file_path, code)
                per_extension[extension] += 1
                aliases[alias] += 1
                cases.append({"file_path": file_path, "code": code, "lexer": alias})

    Path(options.out).write_text(
        json.dumps({"cases": cases, "aliases": dict(aliases.most_common())}, ensure_ascii=False)
    )
    print(f"{len(cases)} cases over {len(per_extension)} extensions -> {options.out}")
    print("aliases:", dict(aliases.most_common(20)))


if __name__ == "__main__":
    main()
