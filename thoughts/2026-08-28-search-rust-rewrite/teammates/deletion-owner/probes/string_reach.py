#!/usr/bin/env python3
"""Tests that reach the search arm by STRING, which a name-based scan cannot see.

`classify_tests.py` marks a test by the identifiers it names. **A test that does
`monkeypatch.setattr(cli, "cmd_search", …)` or drives `cli.sys.argv` with
`["ch", "search", …]` names nothing** — the symbol is a string literal, and the
whole class was invisible to the first classifier.

Found when the residue of a bucket-B removal still mentioned `cmd_search`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PATTERNS = (
    re.compile(r'setattr\(\s*cli\s*,\s*["\']cmd_search["\']'),
    re.compile(r'["\']ch["\']\s*,\s*["\']search["\']'),
    re.compile(r'["\']chats\.commands\.search["\']|["\']chats\.search_query["\']'
               r'|["\']chats\.session_scan["\']'),
)


def reaches(text: str) -> bool:
    return any(pattern.search(text) for pattern in PATTERNS)


for path in sorted(Path("tests").rglob("test_*.py")):
    source = path.read_text()
    if not reaches(source):
        continue
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    def body(node) -> str:
        return "".join(lines[node.lineno - 1 : node.end_lineno])

    tainted_helpers = {
        node.name for node in functions
        if not node.name.startswith("test") and reaches(body(node))
    }
    hits = [
        node.name for node in functions
        if node.name.startswith("test")
        and (reaches(body(node))
             or (set(re.findall(r"\b\w+\b", body(node))) & tainted_helpers))
    ]
    module_level = reaches("".join(
        line for index, line in enumerate(lines)
        if not any(f.lineno - 1 <= index < f.end_lineno for f in functions)
    ))
    print(f"{path}")
    if module_level:
        print("    module level reaches the search arm by string")
    for name in hits:
        print(f"    {name}")
