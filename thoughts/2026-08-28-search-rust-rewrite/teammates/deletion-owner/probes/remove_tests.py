#!/usr/bin/env python3
"""Remove named test functions from a file, decorators and all.

Line ranges come from the AST rather than from a regex, so a decorator stack or a
multi-line signature cannot be half-removed. Blank lines left behind are collapsed
to the two-line separation the files already use.

    remove_tests.py <file> <test name> [<test name> ...]
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


def main() -> None:
    path = Path(sys.argv[1])
    wanted = set(sys.argv[2:])
    source = path.read_text()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    spans: list[tuple[int, int]] = []
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in wanted:
            continue
        found.add(node.name)
        start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
        spans.append((start, node.end_lineno))

    missing = wanted - found
    if missing:
        raise SystemExit(f"REFUSING: {path} holds no {sorted(missing)}")

    keep = [line for index, line in enumerate(lines)
            if not any(start <= index < end for start, end in spans)]
    text = re.sub(r"\n{4,}", "\n\n\n", "".join(keep)).rstrip("\n") + "\n"
    path.write_text(text)
    print(f"{path}: removed {len(found)} tests")


if __name__ == "__main__":
    main()
