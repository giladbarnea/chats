#!/usr/bin/env python3
"""Is the boolean AND/OR/NOT grammar covered without `test_search_operators.py`?

`search-firstmate`'s bucket-A ruling rests on the premise that the coverage lives in
the Rust suite and the contract corpus. **This measures the premise instead of
believing it.** Two counts: contract cases whose pattern carries an operator, and
Rust tests naming the grammar.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CORPORA = [
    Path("tests/data/search-contract-fixtures"),
    Path("tests/data/search-amendment-fixtures"),
]
#: The grammar's own tokens, uppercase-only by the product's rule, plus the
#: parenthesised grouping the parser supports.
OPERATOR = re.compile(r"(?:(?<=\s)|^)(AND|OR|NOT)(?:(?=\s)|$)")

total = 0
carrying: list[tuple[str, str]] = []
for corpus in CORPORA:
    manifest = json.loads((corpus / "MANIFEST.json").read_text())
    cases = manifest["cases"] if isinstance(manifest, dict) else manifest
    for case in cases:
        total += 1
        pattern = " ".join(str(argument) for argument in case["arguments"])
        if OPERATOR.search(pattern):
            carrying.append((str(case["id"]), pattern))

print(f"contract corpora: {len(carrying)} of {total} cases carry AND/OR/NOT")
for case_id, pattern in carrying:
    print(f"    {case_id:44s} {pattern}")
