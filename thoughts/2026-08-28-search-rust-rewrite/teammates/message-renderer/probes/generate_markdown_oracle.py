#!/usr/bin/env -S uv run
"""Record what Rich's `Markdown` renders, as lines of styled runs, at several widths.

The gate for the markdown half of the message renderer. Rendered through the
product's own console theme and the product's own `Markdown` subclass, so the
inline-code padding and the `dim` and `markdown.code` overrides are in the answer
rather than approximated.

**Widths are a swept dimension.** Three width defects on this mission hid behind a
corpus that pinned one width. None of these is 80 (Rich's fallback) or 96 (what
every recorded coloured case pins).

**The style is recorded structurally, not as SGR bytes.** A palette colour and a
truecolor triple that happen to emit the same parameters at truecolor are different
things, and the difference is only visible on a 16-colour terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

from rich.color import ColorType
from rich.console import Console

from chats.formatting import Markdown
from chats.theme import APP_THEME

WIDTHS = (13, 20, 40, 72, 120)


def colour(value) -> dict | None:
    """A Rich colour as the kind it is: an authored triple or a palette index."""
    if value is None:
        return None
    if value.type in (ColorType.STANDARD, ColorType.EIGHT_BIT):
        return {"palette": value.number}
    if value.type is ColorType.TRUECOLOR:
        triplet = value.triplet
        return {"triplet": [triplet.red, triplet.green, triplet.blue]}
    if value.type is ColorType.DEFAULT:
        return None
    raise SystemExit(f"unrecorded colour type {value.type!r}")


def style_record(style) -> dict | None:
    if style is None:
        return None
    record: dict = {}
    for name in ("bold", "dim", "italic", "underline", "reverse", "strike"):
        set_value = getattr(style, name)
        if set_value is not None:
            record[name] = set_value
    foreground = colour(style.color)
    background = colour(style.bgcolor)
    if foreground is not None:
        record["fg"] = foreground
    if background is not None:
        record["bg"] = background
    if style.link:
        record["link"] = style.link
    return record or None


def render(markup: str, width: int) -> list[list[dict]]:
    console = Console(
        theme=APP_THEME,
        force_terminal=True,
        color_system="truecolor",
        width=width,
        legacy_windows=False,
    )
    options = console.options.update_width(width)
    lines = console.render_lines(Markdown(markup), options, pad=False)
    return [
        [{"t": segment.text, "s": style_record(segment.style)} for segment in line]
        for line in lines
    ]


CURATED: list[tuple[str, str]] = [
    ("empty", ""),
    ("plain", "hello world"),
    ("wrap", "The quick brown fox jumps over the lazy dog again and again and again."),
    ("two-paragraphs", "first paragraph\n\nsecond paragraph"),
    ("strong", "Some **bold** text."),
    ("emph", "Some *italic* text."),
    ("strong-emph", "Some ***both*** text."),
    ("strike", "Some ~~gone~~ text."),
    ("code-inline", "Some `code` text."),
    ("code-inline-empty", "Some `` text."),
    ("code-inline-wrap", "aaa `bbbbbbbbbbbbbbbbbbbbbbbbbbbb` ccc"),
    ("nested-strong-emph", "**bold with *inner* rest**"),
    ("hr", "---"),
    ("hr-between", "before\n\n---\n\nafter"),
    ("h1", "# Heading one"),
    ("h2", "## Heading two"),
    ("h3", "### Heading three"),
    ("h4", "#### Heading four"),
    ("h1-long", "# " + "a heading that is long enough to wrap at every width " * 2),
    ("h1-empty", "#"),
    ("setext", "Heading\n======="),
    ("bullets", "- alpha\n- beta\n- gamma"),
    ("bullets-loose", "- alpha\n\n- beta"),
    ("bullets-nested", "- alpha\n  - inner\n- beta"),
    ("bullets-wrap", "- " + "a list item long enough to wrap at every width " * 2),
    ("ordered", "1. one\n2. two"),
    ("ordered-start", "5. five\n6. six"),
    ("ordered-wide", "8. eight\n9. nine\n10. ten\n11. eleven"),
    ("list-empty-item", "- alpha\n-\n- gamma"),
    ("list-then-nested", "- alpha\n  - inner"),
    ("quote", "> quoted text"),
    ("quote-bold", "> quoted **bold** text"),
    ("quote-wrap", "> " + "a quotation long enough to wrap at every width " * 2),
    ("quote-multi", "> first\n>\n> second"),
    ("link", "see [label](https://example.com) here"),
    ("autolink", "see <https://example.com> here"),
    ("image", "![alt text](https://example.com/a.png)"),
    ("table", "| a | b |\n| - | - |\n| 1 | 2 |"),
    ("table-aligned", "| a | b | c |\n| :- | :-: | -: |\n| 1 | 2 | 3 |"),
    # The width algorithms — `_collapse_widths` and `ratio_reduce` — are only
    # reached by a table wider than its console. A corpus of small tables gates the
    # box drawing and nothing else.
    (
        "table-overwide",
        "| alpha column | beta column | gamma column |\n| - | - | - |\n"
        "| a fairly long first cell | another long cell here | and a third one |",
    ),
    (
        "table-one-huge-column",
        "| short | a single enormously long heading that dwarfs its neighbour |\n"
        "| - | - |\n| x | y |",
    ),
    (
        "table-wrapping-cell",
        "| head | other |\n| - | - |\n"
        "| a cell whose text is long enough to wrap onto several lines at every width | z |",
    ),
    ("table-empty-cell", "| a | b |\n| - | - |\n|  | 2 |\n| 3 |  |"),
    ("table-four-columns", "| a | b | c | d |\n| - | - | - | - |\n| 1 | 2 | 3 | 4 |"),
    ("table-multiline-header", "| a very long heading indeed | b |\n| - | - |\n| 1 | 2 |"),
    ("table-wide-characters", "| 名前 | 説明 |\n| - | - |\n| 你好你好 | 世界 |"),
    ("hardbreak", "line one  \nline two"),
    ("softbreak", "line one\nline two"),
    ("entity", "a &amp; b"),
    ("escape", "a \\* b"),
    ("wide-chars", "你好你好你好你好你好你好你好你好你好你好你好你好"),
    ("wide-in-bold", "**你好你好你好你好你好你好你好你好**"),
    ("emoji-zwj", "family \U0001f468‍\U0001f4bb here"),
    ("long-word", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
    ("tabs", "a\tb\tc"),
    ("fence-python", "```python\ndef f(x):\n    return x + 1\n```"),
    ("fence-untagged", "```\nplain fenced text\n```"),
    ("indented-code", "    indented code line\n    second line"),
    # The geometry half: every one of these reaches the plain-text lexer, so the
    # block is exact with no lexer written. They stress padding, wrapping, the
    # character-counted tab expansion and the trailing rstrip.
    ("fence-text-tag", "```text\nan explicitly tagged plain block\n```"),
    ("fence-unknown-tag", "```mermaid\ngraph TD\n  A --> B\n```"),
    ("fence-tag-with-argument", "```text title=example\ntagged with an argument\n```"),
    ("fence-empty", "```text\n```"),
    ("fence-blank-lines-inside", "```text\nfirst\n\nthird\n```"),
    ("fence-trailing-blank-lines", "```text\ncontent\n\n\n```"),
    ("fence-long-line", "```text\n" + "a line long enough to wrap at every recorded width " * 3 + "\n```"),
    ("fence-long-word", "```text\n" + "x" * 130 + "\n```"),
    ("fence-tabs", "```text\na\tb\tc\nab\tcd\n```"),
    ("fence-wide-characters", "```text\n你好你好你好你好你好你好你好你好你好你好\n```"),
    ("fence-leading-indent", "```text\n    indented\n        deeper\n```"),
    # **A control code inside a fence survives**, because `Syntax.highlight` appends
    # through `Text._text.append` and never `Text.append`, so Rich's control-code
    # strip is unreachable there. Markdown normalises newlines, so a form feed and a
    # vertical tab are the only ways in — and the port dropped them until this case
    # existed.
    ("fence-control-codes", "```text\nbefore\x0cafter\x0bmore\n```"),
    ("indented-code-blank-line", "    first\n\n    third"),
    ("indented-code-tabs", "    a\tb\n    cd\tef"),
    ("html-block", "<div>\nraw\n</div>"),
    ("html-inline", "a <span> b"),
]


def sampled(files: int, seed: int, count: int) -> list[tuple[str, str]]:
    """Real message text, so the corpus is not only what a fixture author imagined."""
    home = Path(os.environ["HOME"])
    roots = [
        home / ".claude" / "projects",
        home / ".pi" / "agent" / "sessions",
        home / ".codex" / "sessions",
    ]
    paths = [path for root in roots if root.exists() for path in root.rglob("*.jsonl")]
    random.Random(seed).shuffle(paths)
    blocks: list[str] = []

    def walk(item, found):
        stack = [item]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                if current.get("type") == "text" and isinstance(current.get("text"), str):
                    found.append(current["text"])
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)

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
            walk(entry, blocks)
            if len(blocks) >= count * 6:
                break
        if len(blocks) >= count * 6:
            break

    chosen = random.Random(seed).sample(blocks, min(count, len(blocks)))
    # Long blocks make a failure unreadable and add little: the shapes repeat.
    return [(f"real-{index}", text[:1500]) for index, text in enumerate(chosen)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--from-existing",
        help="re-render the markup already recorded in this oracle instead of "
        "sampling the live pool. **This is how the corpus is regenerated.**",
    )
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--files", type=int, default=300)
    parser.add_argument("--seed", type=int, default=41)
    options = parser.parse_args()

    # **The sampled half re-reads the live session directory, so the same seed does
    # not give the same corpus.** An oracle that looks regenerable and is not is the
    # worse form of a perishable instrument: it runs, succeeds, and returns a
    # different corpus wearing the old one's authority.
    #
    # So a regeneration re-renders the markup **already recorded**, and only the
    # curated list may grow. Sampling happens once, when a corpus is first built.
    if options.from_existing:
        recorded = json.loads(Path(options.from_existing).read_text())
        seen: dict[str, str] = {}
        for case in recorded["cases"]:
            seen.setdefault(case["id"], case["markup"])
        curated = dict(CURATED)
        cases = [
            (identifier, curated.get(identifier, markup))
            for identifier, markup in seen.items()
        ]
        cases += [item for item in CURATED if item[0] not in seen]
    else:
        cases = CURATED + sampled(options.files, options.seed, options.samples)
    records = []
    for identifier, markup in cases:
        for width in WIDTHS:
            records.append(
                {
                    "id": identifier,
                    "width": width,
                    "markup": markup,
                    "lines": render(markup, width),
                }
            )

    from importlib.metadata import version

    payload = {
        "rich_version": version("rich"),
        "widths": list(WIDTHS),
        "curated": len(CURATED),
        "sampled": len(cases) - len(CURATED),
        "cases": records,
    }
    Path(options.out).write_text(json.dumps(payload, ensure_ascii=False))
    print(f"{len(records)} records over {len(cases)} cases -> {options.out}")


if __name__ == "__main__":
    main()
