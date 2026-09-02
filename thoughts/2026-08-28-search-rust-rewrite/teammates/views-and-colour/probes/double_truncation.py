"""Does the product's list row show ONE truncation (elide_to_width, code points)
or TWO (elide_to_width, then Rich's cell-based overflow)?

Driven through the real `_build_search_list_row`, printed the way the product
prints it (a Group), not as a bare Text -- a bare Text loses no_wrap via Text.join.
"""
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "src")
from rich.console import Console
from rich.text import Text
from rich.cells import cell_len

from chats.commands.search import _build_search_list_row
from chats.theme import APP_THEME
from chats.utils import elide_to_width

NOW = datetime(2026, 8, 28, 12, 0, 0)
MTIME = datetime(2026, 8, 25, 12, 0, 0)


@dataclass
class Meta:
    path: Path
    mtime: datetime
    provider: str


@dataclass
class Hit:
    metadata: Meta
    cwd: str
    last_custom_title: str
    matching_summaries: list
    matches: list
    match_count: int


def row(headline: str, width: int) -> str:
    hit = Hit(
        metadata=Meta(Path("/Users/giladbarnea/.claude/projects/-Users-giladbarnea-dev-hist/b4ee3512-020a-41b0-a4fb-a41989a26b73.jsonl"), MTIME, "claude"),
        cwd="/Users/giladbarnea/dev/chats",
        last_custom_title=headline,
        matching_summaries=[],
        matches=[],
        match_count=3,
    )
    console = Console(width=width, force_terminal=False, no_color=True, theme=APP_THEME)
    with console.capture() as capture:
        console.print(_build_search_list_row(hit, now=NOW, width=width, show_provider=False))
    return capture.get()


WIDTH = 40
for name, headline in {
    "ascii": "hello world " * 6,
    "wide-cjk": "你好" * 30,
    "mixed": "ab你好" * 15,
}.items():
    budget = max(8, WIDTH - 2)
    elided = elide_to_width(headline, budget)
    rendered = row(headline, WIDTH)
    first = rendered.split("\n")[0]
    expected_if_single_truncation = "▎ " + elided
    print(f"{name}:")
    print(f"  elide_to_width -> {len(elided)} code points / {cell_len(elided)} cells (budget {budget} code points)")
    print(f"  rendered line  -> {len(first)} code points / {cell_len(first)} cells (console width {WIDTH})")
    print(f"  Rich truncated a second time: {first != expected_if_single_truncation}")
    print(f"  {first!r}")
    print()
