#!/usr/bin/env python3
"""Both timestamp probes, both routes, on the two sessions the corpus already had.

**Why this exists rather than a fixture assertion.** The corpus already contained
sessions named *"Render nan first line"* and *"Render ctrl separator line"* — built
for exactly these cases — and both passed the 260-case comparison, because **no
recorded case renders their metadata block. The corpus had the inputs and not the
assertion.** This probe is the assertion.

**The class has four Rust sites and three different correct answers**, which is why
"make them all use `python_strip`" is wrong:

- `pool_filter::first_in_band_timestamp` ports `_find_first_timestamp`, which is
  **pure CPython**: `line.strip()` then stdlib `json.loads`. Both halves diverge —
  the byte trim misses U+001C..U+001F and every non-ASCII space, and `serde_json`
  rejects `NaN`.
- `inventory::cwd_from_path` ports `extract_cwd_from_jsonl_file`, same pair, same
  two divergences.
- `inventory::last_timestamp` must match **the accelerator**, not pure Python:
  `get_jsonl_last_timestamp` calls the Rust `find_last_jsonl_timestamp`, so the
  **trim is already Rust's** and only the parse is Python's. Its one divergence is
  `NaN`.
- `python_extension::timestamp_from_line` **is the oracle** for that path. Changing
  its trim moves the oracle rather than matching it. Leave it.

    uv run -p python3 python .../probes/first_timestamp_parity.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

STAMP_FIRST = "2026-08-20T10:00:00.000Z"
STAMP_SECOND = "2026-08-27T10:00:00.000Z"

FILE_SEPARATOR = "\u001c"  # U+001C FILE SEPARATOR


def entry(uuid: str, parent: str | None, stamp: str, text: str, extra: dict | None = None) -> dict:
    payload = {
        "type": "user",
        "uuid": uuid,
        "parentUuid": parent,
        "cwd": "/tmp/timestamp-parity",
        "timestamp": stamp,
        "message": {"role": "user", "content": text},
    }
    if extra:
        payload.update(extra)
    return payload


def nan_first_line() -> str:
    """Line one carries `NaN`. `json.loads` takes it; `serde_json` does not."""
    first = json.dumps(entry("u1", None, STAMP_FIRST, "nan first line"))
    first = first[:-1] + ', "score": NaN}'
    second = json.dumps(entry("u2", "u1", STAMP_SECOND, "ordinary second line"))
    return f"{first}\n{second}\n"


def control_separator_line() -> str:
    """Every line is prefixed with U+001C. `str.strip()` removes it; a byte trim
    over the ASCII whitespace set does not."""
    first = json.dumps(entry("u1", None, STAMP_FIRST, "ctrl separator line"))
    second = json.dumps(entry("u2", "u1", STAMP_SECOND, "ordinary second line"))
    return f"{FILE_SEPARATOR}{first}\n{FILE_SEPARATOR}{second}\n"


def nan_last_line() -> str:
    """`NaN` on the LAST line, which is the only place `inventory::last_timestamp`
    can see it. The two fixtures the corpus already had both put it on line one,
    so the backward scan's half of the divergence was invisible to them."""
    first = json.dumps(entry("u1", None, STAMP_FIRST, "ordinary first line"))
    last = json.dumps(entry("u2", "u1", STAMP_SECOND, "nan last line"))
    last = last[:-1] + ', "score": NaN}'
    return f"{first}\n{last}\n"


CASES = {
    "nan-first-line": nan_first_line,
    "nan-last-line": nan_last_line,
    "ctrl-separator-line": control_separator_line,
}


def python_answers(path: Path) -> dict[str, str]:
    sys.path.insert(0, str(Path.cwd() / "src"))
    from chats.parsing import (
        extract_cwd_from_jsonl_file,
        get_jsonl_first_timestamp,
        get_jsonl_last_timestamp,
    )

    return {
        "first_timestamp": str(get_jsonl_first_timestamp(path)),
        "last_timestamp": str(get_jsonl_last_timestamp(path)),
        "cwd": str(extract_cwd_from_jsonl_file(path)),
    }


def native_answers(binary: str, path: Path) -> dict[str, str]:
    completed = subprocess.run(
        [binary, str(path)],
        capture_output=True,
        env=dict(os.environ),
    )
    if completed.returncode != 0:
        return {"error": completed.stderr.decode()[:300]}
    return json.loads(completed.stdout.decode())


def main() -> int:
    binary = os.environ.get("TIMESTAMP_BIN")
    root = Path(tempfile.mkdtemp(prefix="timestamp-parity-"))
    directory = root / ".claude" / "projects" / "-tmp-timestamp-parity"
    directory.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name, build in CASES.items():
        path = directory / f"{name}.jsonl"
        path.write_text(build(), encoding="utf-8")
        expected = python_answers(path)
        print(f"--- {name}")
        print(f"  python : {expected}")
        if binary:
            actual = native_answers(binary, path)
            print(f"  native : {actual}")
            for key, value in expected.items():
                if actual.get(key) != value:
                    failures += 1
                    print(f"    MISMATCH {key}: python {value!r}  native {actual.get(key)!r}")
        else:
            print("  native : set TIMESTAMP_BIN to compare")
    if binary:
        print(f"\nmismatches: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
