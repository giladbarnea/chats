#!/usr/bin/env python3
"""Per test function: does it reach the Python search authority?

The file-level blast radius says which files break. **The ruling is per subject,
and a file can hold both** — `test_colored_rendering.py` pins `cmd_parse` and
`cmd_search` in one place. This splits every affected file test by test.

A test counts as reaching the authority when its own source, or the source of a
module-level helper it calls, names one of the vanishing symbols.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PACKAGE = Path("src/chats")
SEARCH_FILES = [
    PACKAGE / "commands" / "search.py",
    PACKAGE / "search_query.py",
    PACKAGE / "session_scan.py",
]

VANISHING: set[str] = {"SearchOutputMode"}
for path in SEARCH_FILES:
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            VANISHING.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    VANISHING.add(target.id)

FILES = [
    "test_search_orchestration", "test_native_ascii_candidate_scanner",
    "test_colored_rendering", "test_search_operators", "test_provider_filter",
    "test_provider_metadata", "test_claude_agent_detection",
    "test_search_case_sensitivity", "test_search_cli_args",
    "test_hook_additional_context", "test_search_visibility",
    "test_session_search_space", "test_search_output_modes",
    "test_metadata_timestamps", "test_session_scan", "test_message_selection",
]


def names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
    }


for stem in FILES:
    path = Path("tests") / f"{stem}.py"
    tree = ast.parse(path.read_text())
    # `ast.walk`, not `tree.body`: one of these files nests its tests in a class,
    # and a top-level-only scan reported it as holding no tests at all.
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    helpers = {
        node.name: node for node in functions if not node.name.startswith("test")
    }
    tainted_helpers = {
        name for name, node in helpers.items() if names_in(node) & VANISHING
    }
    reaching, clean = [], []
    for node in functions:
        if not node.name.startswith("test"):
            continue
        used = names_in(node)
        if (used & VANISHING) or (used & tainted_helpers):
            reaching.append(node.name)
        else:
            clean.append(node.name)
    verdict = ("WHOLE FILE" if not clean else "MIXED" if reaching else "clean")
    print(f"{stem:42s} {len(reaching):>3} reach / {len(clean):>3} clean   {verdict}")
    if reaching and clean:
        for name in reaching:
            print(f"        REMOVE: {name}")
