#!/usr/bin/env python3
"""Which top-level symbols of the SURVIVING modules only `commands/search.py` uses.

The module-level reachability answers which files go. This answers the second
question the same rule implies: **a symbol any surviving path uses survives.**
Reported rather than acted on, so the list is on the record before anything moves.

The two package `__init__` hubs re-export nearly everything, so their references are
counted separately: a name that only a hub and `search.py` mention is search-only,
and the hub line goes with the deletion.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[5] / "src" / "chats"
HUBS = {PACKAGE / "__init__.py", PACKAGE / "commands" / "__init__.py"}
SEARCH_ONLY_FILES = {
    PACKAGE / "commands" / "search.py",
    PACKAGE / "search_query.py",
    PACKAGE / "session_scan.py",
}
SURVIVORS = sorted(
    p for p in PACKAGE.rglob("*.py") if p not in SEARCH_ONLY_FILES and p not in HUBS
)


def top_level_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    out.append(target.id)
    return out


ALL = sorted(PACKAGE.rglob("*.py"))
TEXT = {p: p.read_text() for p in ALL}

for path in SURVIVORS:
    findings = []
    for name in top_level_names(path):
        word = re.compile(rf"\b{re.escape(name)}\b")
        users = {
            other
            for other in ALL
            if other != path and word.search(TEXT[other])
        }
        # A symbol its own module uses internally is not search-only.
        own_internal = len(word.findall(TEXT[path])) > 1
        search_users = users & SEARCH_ONLY_FILES
        other_users = users - SEARCH_ONLY_FILES - HUBS - {PACKAGE / "cli.py"}
        if search_users and not other_users and not own_internal:
            hub = " (+hub re-export)" if users & HUBS else ""
            cli = " (+cli.py — CHECK the arm)" if (PACKAGE / "cli.py") in users else ""
            findings.append(f"{name}{hub}{cli}")
    if findings:
        print(f"{path.relative_to(PACKAGE.parent.parent)}")
        for finding in findings:
            print(f"    only search uses: {finding}")
