#!/usr/bin/env -S uv run
"""Compare the Rust `markdown-it` crate's parse against `markdown-it-py`'s.

The first mate's condition on adopting the crate: two ports of one reference can
drift by version, and the whole argument for a crate over a hand-written parser is
that the drift is **measurable**. This measures it.

Both sides emit the *flattened* token stream `rich.markdown` actually consumes —
`_flatten_tokens` drops the `inline` wrapper and yields its children, except for
`image` and `fence` — because that stream, not the parser's internal shape, is what
decides a rendered byte.

Fields compared are the ones Rich reads: `type`, `tag`, `content`, `info`, and the
attributes it looks up (`href` on a link, `start` on an ordered list, `src`/`title`
on an image). `nesting` is implied by the type suffix and is not compared twice.
"""

from __future__ import annotations

import argparse
import collections
import re
import json
import os
import random
import subprocess
from pathlib import Path

from markdown_it import MarkdownIt

RICH_ATTRS = {"href", "start", "src", "title", "style"}


# `formatting._message_content_renderables` escapes tag-like text before handing a
# TEXT part to Markdown, so `<SOURCE>` never reaches the parser as markup on that
# path. Copied from there rather than approximated, because the exposure of any
# HTML-shaped parser divergence depends on exactly which inputs survive it.
XML_TAG_PATTERN = re.compile(r"<[a-zA-Z][a-zA-Z0-9-]*[>\s]")


def escape_tag_like(text: str) -> str:
    if XML_TAG_PATTERN.search(text):
        return re.sub(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)(\s+[^>]*?)?>", r"\\<\1\2\3>", text)
    return text


def comparable_content(kind: str, content: str) -> str:
    """The part of a token's content that reaches a rendered byte.

    An `html_block`'s content reaches `UnknownElement`, whose `on_text` is a no-op
    and whose render yields nothing. A fence's or an indented block's reaches
    `CodeBlock.__rich_console__`, which does `str(self.text).rstrip()` before
    handing it to `Syntax`. Both are read from the Rich source, not assumed.
    """
    if kind == "html_block":
        return ""
    if kind in ("fence", "code_block"):
        return content.rstrip()
    return content


def flatten(tokens):
    """`rich.markdown.Markdown._flatten_tokens`, copied so the comparison uses it."""
    for token in tokens:
        is_fence = token.type == "fence"
        is_image = token.tag == "img"
        if token.children and not (is_image or is_fence):
            yield from flatten(token.children)
        else:
            yield token


def python_tokens(markdown: MarkdownIt, markup: str) -> list[dict]:
    records = []
    for token in flatten(markdown.parse(markup)):
        if token.type == "text" and not token.content:
            # A no-op for `Text.append`, and the Rust side drops it too, so the
            # comparison is over what renders rather than over token bookkeeping.
            continue
        attrs = {
            key: str(value)
            for key, value in (token.attrs or {}).items()
            if key in RICH_ATTRS
        }
        records.append(
            {
                "type": token.type,
                "tag": token.tag,
                # An `html_block`'s content reaches `UnknownElement`, whose
                # `on_text` is a no-op and whose render yields nothing, so the
                # trailing newline the two parsers disagree about is unread.
                "content": comparable_content(token.type, token.content),
                # `info` is read by Rich only on a fence; on `list_item_open` it
                # carries the list marker and reaches nothing.
                "info": token.info if token.type == "fence" else "",
                "attrs": attrs,
            }
        )
    return records


def rust_tokens(binary: str, markups: list[str]) -> list[list[dict]]:
    payload = "\n".join(json.dumps(markup) for markup in markups)
    completed = subprocess.run(
        [binary], input=payload.encode(), stdout=subprocess.PIPE, check=True
    )
    documents = json.loads(completed.stdout)
    out = []
    for document in documents:
        records = []
        for token in document:
            attrs = {
                key: str(value)
                for key, value in (token["attrs"] or {}).items()
                if key in RICH_ATTRS
            }
            records.append(
                {
                    "type": token["type"],
                    "tag": token["tag"],
                    "content": comparable_content(token["type"], token["content"]),
                    "info": token["info"],
                    "attrs": attrs,
                }
            )
        out.append(records)
    return out


def text_blocks(entry) -> list[str]:
    found: list[str] = []
    stack = [entry]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                found.append(item["text"])
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def corpus(files: int, seed: int, cap: int) -> list[str]:
    home = Path(os.environ["HOME"])
    roots = [
        home / ".claude" / "projects",
        home / ".pi" / "agent" / "sessions",
        home / ".codex" / "sessions",
    ]
    paths = [path for root in roots if root.exists() for path in root.rglob("*.jsonl")]
    random.Random(seed).shuffle(paths)
    blocks: list[str] = []
    for path in paths[:files]:
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            blocks.extend(text_blocks(entry))
            if len(blocks) >= cap:
                return blocks[:cap]
    return blocks[:cap]


def brief(token: dict) -> str:
    """One token in one line: what it is, plus whatever of it carries meaning."""
    parts = [token["type"]]
    if token["content"]:
        parts.append(repr(token["content"])[:44])
    if token["info"]:
        parts.append(f"info={token['info']!r}")
    if token["attrs"]:
        parts.append(str(token["attrs"]))
    return " ".join(parts)


def first_difference(left: list[dict], right: list[dict], window: int = 4) -> str:
    """Both streams around the first disagreement.

    A single token names the symptom and hides the cause: a stream that gains or
    loses one token reports every later token as different. The window is what
    separates one real divergence from its shadow.
    """
    limit = min(len(left), len(right))
    position = next((index for index in range(limit) if left[index] != right[index]), limit)
    if position == limit and len(left) == len(right):
        return ""
    low = max(0, position - window)
    high = position + window + 1
    lines = [f"at token {position} of py {len(left)} / rs {len(right)}"]
    for index in range(low, high):
        py = brief(left[index]) if index < len(left) else "-"
        rs = brief(right[index]) if index < len(right) else "-"
        marker = "  " if py == rs else "->"
        lines.append(f"    {marker} {index:>4}  py {py:<58.58} rs {rs:.58}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--files", type=int, default=200)
    parser.add_argument("--blocks", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--show", type=int, default=12)
    parser.add_argument(
        "--dump", type=int, default=None,
        help="print the first differing token pair of this block in full")
    parser.add_argument(
        "--escape-tags", action="store_true",
        help="apply the product's TEXT-part tag escaping before parsing")
    parser.add_argument(
        "--falsify",
        action="store_true",
        help="prove the comparison can fail, by perturbing the Python side",
    )
    options = parser.parse_args()

    markups = corpus(options.files, options.seed, options.blocks)
    if options.escape_tags:
        markups = [escape_tag_like(markup) for markup in markups]
    markdown = MarkdownIt().enable("strikethrough").enable("table")
    expected = [python_tokens(markdown, markup) for markup in markups]
    if options.falsify:
        for record in expected:
            for token in record:
                if token["type"] == "text":
                    token["content"] += "!"
                    break
    actual = rust_tokens(options.binary, markups)

    mismatched: list[tuple[int, str]] = []
    kinds: collections.Counter[str] = collections.Counter()
    for index, (left, right) in enumerate(zip(expected, actual)):
        if left != right:
            difference = first_difference(left, right)
            mismatched.append((index, difference))
            kinds[difference.splitlines()[1].split("py ")[1][:20] if len(difference.splitlines()) > 1 else "?"] += 1

    if options.dump is not None:
        left, right = expected[options.dump], actual[options.dump]
        limit = min(len(left), len(right))
        position = next(
            (index for index in range(limit) if left[index] != right[index]), limit
        )
        print(f"block {options.dump}, first differing token {position}")
        for side, stream in (("py", left), ("rs", right)):
            if position < len(stream):
                print(f"  {side}: {stream[position]!r}")
        return

    print(f"blocks compared {len(markups)}")
    print(f"identical       {len(markups) - len(mismatched)}")
    print(f"differing       {len(mismatched)}")
    print("\nfirst-difference shapes:")
    for kind, count in kinds.most_common(12):
        print(f"  {count:5}  {kind}")
    for index, difference in mismatched[: options.show]:
        print(f"\n--- block {index}\n{markups[index]!r:.200}\n{difference}")
    if options.falsify and not mismatched:
        raise SystemExit("FALSIFICATION FAILED: a perturbed Python side compared equal")


if __name__ == "__main__":
    main()
