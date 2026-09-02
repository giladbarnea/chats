#!/usr/bin/env python3
"""Which recorded rows carry the ruled warning decoration, and which gate looks.

`g5-runner` reported four rows in one family and three of them invisible. This
re-derives that from the recording rather than taking it on report, and prints
every row whose recorded stderr is non-empty so the answer is not confined to the
family that was asked about.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

BASELINE = Path("tests/data/legacy-selection-baseline/legacy-selection-baseline.json")
DECORATION = b"{SEARCH_QUERY_SOURCE}:96: FutureWarning:"

baseline = json.loads(BASELINE.read_text())
for group, rows in baseline["groups"].items():
    carrying = []
    non_empty = []
    for key, row in rows.items():
        stderr = base64.b64decode(row["stderr"])
        if stderr:
            non_empty.append((key, stderr))
        if DECORATION in stderr:
            carrying.append(key)
    print(f"{group}: {len(rows)} rows, {len(non_empty)} with stderr, "
          f"{len(carrying)} carrying the decoration")
    for key in sorted(carrying):
        pattern = rows[key].get("pattern") or rows[key].get("arguments")
        print(f"    decoration  {key}  {pattern!r}")
    for key, stderr in sorted(non_empty):
        if key not in carrying:
            print(f"    other       {key}  {stderr[:120]!r}")
