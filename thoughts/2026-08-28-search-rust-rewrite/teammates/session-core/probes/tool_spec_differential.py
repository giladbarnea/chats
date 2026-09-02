"""Differential: native `parse_tool_spec` against Python's, over a generated spec corpus.

Python at oracle revision `8cb4c5f` is the oracle. Specs are generated combinatorially
rather than hand-written, because hand-written expectations for this grammar have
already been wrong twice — the lookahead accepts `s=8` but rejects `s=8:p`, which is
not what the shape suggests.

Point at the driver with TOOLSPEC_BIN=/path/to/toolspec.
Run from the repo root.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

from chats.tool_filter import parse_tool_spec

BIN = os.environ.get("TOOLSPEC_BIN")

NAMES = ["", "Bash", "Read", "apply_patch", "exec_command", "Unknown", "weird-name"]
MODIFIERS = ["", "i", "input", "o", "output", "e", "error", "I", "Error"]
SHORTS = [
    "",
    "s",
    "short",
    "S",
    "s=8",
    "s=500",
    "s=7",
    "s=p",
    "s=progressive",
    "s=p=128",
    "s=p:128",
    "s=8:p",
    "s=8:",
    "s=abc",
    "short=p=64",
]
EXTRAS = ["", "s", "Read", "e"]


def generated_specs() -> list[str]:
    specs: set[str] = set()
    for name, modifier, short in itertools.product(NAMES, MODIFIERS, SHORTS):
        parts = [part for part in (name, modifier, short) if part]
        if not parts:
            continue
        body = ":".join(parts)
        specs.add(body)
        specs.add(f"!{body}")
    # Trailing and repeated separators, and a second bare token after a short.
    for name, extra in itertools.product(NAMES[:4], EXTRAS):
        for template in ("{n}:{e}", "{n}::{e}", "{n}:s:{e}", "{n}:{e}:", ":{n}:{e}"):
            body = template.format(n=name, e=extra)
            if body.strip(":"):
                specs.add(body)
                specs.add(f"!{body}")
    return sorted(specs)


def python_result(spec: str) -> dict:
    try:
        filter_value = parse_tool_spec(spec)
    except ValueError:
        return {"ok": False}
    return {
        "ok": True,
        "name": filter_value.name,
        "negate": filter_value.negate,
        "direction": filter_value.direction,
        "error_only": filter_value.error_only,
        "short": filter_value.short,
        "short_max_chars": filter_value.short_max_chars,
        "short_progressive": filter_value.short_progressive,
    }


def main() -> int:
    if not BIN:
        print("set TOOLSPEC_BIN to the differential driver")
        return 2

    specs = generated_specs()
    payload = "\n".join(json.dumps(spec) for spec in specs) + "\n"
    completed = subprocess.run([BIN], input=payload.encode("utf-8"), capture_output=True)
    if completed.returncode != 0:
        print(completed.stderr.decode("utf-8")[:2000])
        return 1

    native = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line]
    if len(native) != len(specs):
        print(f"driver returned {len(native)} rows for {len(specs)} specs")
        return 1

    mismatches = []
    for spec, actual in zip(specs, native):
        expected = python_result(spec)
        if actual != expected:
            mismatches.append((spec, expected, actual))

    # --emit-table records the run as a stored table: the same (input, expected) pairs
    # this run just compared, in the form that survives the Python authority's deletion.
    # The table is a *recording of a passing live run*, never written by hand, so
    # regenerating it is free and it can never drift from the differential that made it.
    if "--emit-table" in sys.argv:
        if mismatches:
            print("refusing to emit a table from a run with mismatches")
            return 1
        table = {
            "oracle_revision": "8cb4c5f",
            "generated_by": Path(__file__).name,
            "cases": [
                {"spec": spec, "expected": python_result(spec)} for spec in specs
            ],
        }
        out_path = Path(sys.argv[sys.argv.index("--emit-table") + 1])
        out_path.write_text(json.dumps(table, indent=1), encoding="utf-8")
        print(f"emitted {len(table['cases'])} cases to {out_path}")

    accepted = sum(1 for row in native if row["ok"])
    print(f"specs: {len(specs)}  (native accepts {accepted}, rejects {len(specs) - accepted})")
    print(f"mismatches: {len(mismatches)}")
    for spec, expected, actual in mismatches[:10]:
        print(f"  {spec!r}")
        print(f"    python {expected}")
        print(f"    native {actual}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
