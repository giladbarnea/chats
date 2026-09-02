#!/usr/bin/env python3
"""Derive the deletion set by reachability, not by filename.

Builds the module-level import graph of `src/chats` from the AST, then reports,
for every module, which `cli.main()` dispatch arms reach it. **What goes is what
only the `search` arm reaches.** Anything a surviving command imports survives.

Module granularity is the first cut and is deliberately reported as such: a module
reached by two arms may still hold functions only one of them calls, which is the
`pool_filter.py` trap, and that is checked separately by caller.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[5] / "src" / "chats"


def module_name(path: Path) -> str:
    relative = path.relative_to(PACKAGE).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["chats", *parts])


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out: set[str] = set()
    own = module_name(path).split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = own[: len(own) - node.level + (1 if path.name == "__init__.py" else 0)]
                prefix = ".".join(base)
                out.add(f"{prefix}.{node.module}" if node.module else prefix)
                for alias in node.names:
                    out.add(f"{prefix}.{node.module}.{alias.name}" if node.module
                            else f"{prefix}.{alias.name}")
            elif node.module:
                out.add(node.module)
                for alias in node.names:
                    out.add(f"{node.module}.{alias.name}")
    return out


#: The two package `__init__` modules are re-export HUBS, not dependencies: they
#: import every command module and every shared module, so leaving them in the graph
#: makes every arm reach everything. They are excluded as nodes and handled as an
#: explicit edit of the deletion instead.
HUBS = {"chats", "chats.commands"}
MODULES = {
    module_name(p): p
    for p in sorted(PACKAGE.rglob("*.py"))
    if module_name(p) not in HUBS
}
GRAPH: dict[str, set[str]] = {}
for name, path in MODULES.items():
    GRAPH[name] = {i for i in imports_of(path) if i in MODULES and i != name}


def closure(roots: set[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        current = stack.pop()
        if current in seen or current not in GRAPH:
            continue
        seen.add(current)
        stack.extend(GRAPH[current])
    return seen


#: One root per `cli.main()` dispatch arm, taken from the handler each arm calls.
ARMS = {
    "search": {"chats.commands.search"},
    "name": {"chats.commands.name"},
    "rm": {"chats.commands.rm"},
    "catalog": {"chats.catalog"},
    "info": {"chats.commands.info"},
    "parse-default": {"chats.commands.parse"},
}

reached = {arm: closure(roots) for arm, roots in ARMS.items()}
survivors: set[str] = set()
for arm, modules in reached.items():
    if arm != "search":
        survivors |= modules

print(f"{len(MODULES)} modules in the package\n")
print("REACHED ONLY BY `search` — the candidate deletion set")
for name in sorted(reached["search"] - survivors):
    print(f"    {name:40s} {MODULES[name].relative_to(PACKAGE.parent.parent)}")

print("\nREACHED BY `search` AND AT LEAST ONE SURVIVOR — these stay")
for name in sorted(reached["search"] & survivors):
    arms = sorted(a for a, m in reached.items() if a != "search" and name in m)
    print(f"    {name:40s} also: {', '.join(arms)}")

unreached = set(MODULES) - closure(set().union(*ARMS.values())) - {"chats.cli", "chats"}
print("\nREACHED BY NO ARM (cli.py and the package root excluded)")
for name in sorted(unreached):
    print(f"    {name}")
