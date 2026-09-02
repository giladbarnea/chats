#!/usr/bin/env python3
"""Compare CPython's `\\s` / `\\w` against the Rust `regex` crate's, scalar by scalar.

Both sides are dumps, not readings. The Rust half is `drivers/charclass`:

  cd drivers/charclass && CARGO_TARGET_DIR=$PWD/target cargo build --release \\
      && ./target/release/charclass > /tmp/rust_classes.tsv
  uv run -p python3 python character_class_parity.py /tmp/rust_classes.tsv

Prints the symmetric difference for the bare classes and for the two candidate
replacements, so "exact" is a measured claim and not a reading of two documents.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

COLUMNS = ["rust \\s", "rust \\w", "rust [\\s\\x1C-\\x1F]", "rust [\\p{L}\\p{Nd}\\p{Nl}\\p{No}_]"]


def python_set(pattern: str) -> set[int]:
    compiled = re.compile(pattern)
    return {code for code in range(0x110000) if compiled.fullmatch(chr(code))}


def rust_sets(path: Path) -> list[set[int]]:
    sets: list[set[int]] = [set() for _ in COLUMNS]
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        code = int(fields[0])
        for index, flag in enumerate(fields[1:]):
            if flag == "1":
                sets[index].add(code)
    return sets


def show(label: str, codes: set[int], limit: int = 10) -> None:
    print(f"  {label}: {len(codes)}")
    for code in sorted(codes)[:limit]:
        try:
            name = unicodedata.name(chr(code))
        except ValueError:
            name = f"<unnamed, category {unicodedata.category(chr(code))}>"
        print(f"      U+{code:04X}  {name}")
    if len(codes) > limit:
        print(f"      ... {len(codes) - limit} more")


def compare(label: str, python: set[int], rust: set[int]) -> bool:
    only_python = python - rust
    only_rust = rust - python
    print(f"{label}   CPython {len(python)}   Rust {len(rust)}")
    show("CPython only", only_python)
    show("Rust only", only_rust)
    exact = not only_python and not only_rust
    print(f"  EXACT: {exact}\n")
    return exact


def main() -> int:
    rust = rust_sets(Path(sys.argv[1]))
    python_space = python_set(r"\s")
    python_word = python_set(r"\w")

    compare("bare \\s      ", python_space, rust[0])
    compare("bare \\w      ", python_word, rust[1])
    space_exact = compare("candidate \\s ", python_space, rust[2])
    word_exact = compare("candidate \\w ", python_word, rust[3])

    print(f"candidate space class is exact: {space_exact}")
    print(f"candidate word class is exact:  {word_exact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
