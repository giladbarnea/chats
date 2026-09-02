#!/usr/bin/env python3
"""Every test file that stops working when the Python search authority goes.

Two ways a file breaks, measured separately:

1. **It imports a name that disappears.** The names are derived from the three
   search-only modules and from the two hub `__init__` files that re-export them,
   rather than listed by hand.
2. **It executes `ch-legacy search` in a subprocess.** Matched on the command line
   that is actually built, not on a mention of the word.

Reported with each file's collected test count so the size of the loss is a number
rather than an impression.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

PACKAGE = Path("src/chats")
SEARCH_MODULES = {
    "chats.commands.search": PACKAGE / "commands" / "search.py",
    "chats.search_query": PACKAGE / "search_query.py",
    "chats.session_scan": PACKAGE / "session_scan.py",
}


def exported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out.add(target.id)
    return out


VANISHING = set()
for name, path in SEARCH_MODULES.items():
    VANISHING |= exported_names(path)
#: `SearchOutputMode` lives in `model.py`, which survives — but only `search.py` and
#: the search arm of `cli.py` use it, so it goes with them. Named explicitly because
#: no module-level derivation can find it.
VANISHING.add("SearchOutputMode")

LEGACY_SEARCH = re.compile(r"(CHECKOUT_LEGACY|ch-legacy)[^\n]{0,120}?[\"']search[\"']")

rows = []
for path in sorted(Path("tests").rglob("test_*.py")):
    text = path.read_text()
    tree = ast.parse(text)
    hit_names: set[str] = set()
    hit_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module in SEARCH_MODULES:
                hit_modules.add(node.module)
            if node.module in {"chats", "chats.commands", "chats.model"}:
                hit_names |= {a.name for a in node.names} & VANISHING
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in SEARCH_MODULES:
                    hit_modules.add(alias.name)
    runs_legacy_search = bool(LEGACY_SEARCH.search(text))
    if hit_names or hit_modules or runs_legacy_search:
        collected = subprocess.run(
            ["uv", "run", "pytest", str(path), "--collect-only", "-q"],
            capture_output=True, text=True,
        ).stdout.strip().splitlines()
        count = collected[-1].split(":")[-1].strip() if collected else "?"
        rows.append((path, count, sorted(hit_modules), sorted(hit_names), runs_legacy_search))

total = 0
print(f"{'file':46s} {'tests':>6s}  why")
for path, count, modules, names, legacy in rows:
    reasons = []
    if modules:
        reasons.append("imports " + ", ".join(modules))
    if names:
        reasons.append("imports vanishing name(s): " + ", ".join(names))
    if legacy:
        reasons.append("runs `ch-legacy search`")
    print(f"{str(path):46s} {count:>6s}  {'; '.join(reasons)}")
    if count.isdigit():
        total += int(count)
print(f"\n{len(rows)} files, {total} collected tests reach the Python search authority")
