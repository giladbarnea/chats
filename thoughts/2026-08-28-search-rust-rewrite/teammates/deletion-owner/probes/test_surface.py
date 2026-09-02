#!/usr/bin/env python3
"""Which test files reach the Python search authority, and how.

Two questions, kept apart because they have different answers at the deletion:
**which files IMPORT one of the three search-only modules** (they stop importing),
and **which files EXECUTE `ch-legacy search`** (they lose their reference route).
A file can do one, both or neither, and a mention in a comment is neither.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

TESTS = Path("tests")
SEARCH_MODULES = {
    "chats.commands.search",
    "chats.search_query",
    "chats.session_scan",
}
RUNS_LEGACY_SEARCH = re.compile(r"""["'](search|-ll?)["']|\bsearch\b""")

for path in sorted(TESTS.rglob("*.py")):
    text = path.read_text()
    imports: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in SEARCH_MODULES:
            imports.append(f"from {node.module} import "
                           + ", ".join(a.name for a in node.names))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in SEARCH_MODULES:
                    imports.append(f"import {alias.name}")
    legacy = "ch-legacy" in text or "CHECKOUT_LEGACY" in text
    legacy_search = legacy and bool(re.search(r"ch-legacy[^\n]*search|"
                                              r"CHECKOUT_LEGACY[^\n]*", text))
    if imports or legacy:
        print(f"{path}")
        for line in imports:
            print(f"    IMPORT   {line}")
        if legacy:
            print(f"    LEGACY   mentions ch-legacy; search use: "
                  f"{'likely' if legacy_search else 'check'}")
