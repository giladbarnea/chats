#!/usr/bin/env python3
"""Re-derive both digests immediately before a run, printed together.

The oracle route digest is `tests/oracle_digest.py`'s, imported rather than
restated. The rust tree digest is sha256 over `rust/**/*.rs` in sorted order,
which is the recipe `parity-finisher` recorded as `7b3267a6a22e`.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import oracle_digest  # noqa: E402


def rust_tree_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted((PROJECT_ROOT / "rust").rglob("*.rs")):
        digest.update(path.read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    print(f"oracle route digest  {oracle_digest.oracle_route_digest()}")
    print(f"rust tree digest     {rust_tree_digest()}")
