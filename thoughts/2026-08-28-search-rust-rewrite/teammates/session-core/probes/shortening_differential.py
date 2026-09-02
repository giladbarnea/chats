"""Differential: native `truncate_middle` against Python's, over an adversarial corpus.

Python at oracle revision `8cb4c5f` is the oracle. The native side is driven through a
small binary reading one JSON case per line, so the comparison is on bytes rather than
on a reimplementation of either side.

Point at the driver with DIFF_BIN=/path/to/diff.
Run from the repo root: DIFF_BIN=... uv run python thoughts/.../probes/shortening_differential.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

from chats.utils import truncate_middle

sys.path.insert(0, str(Path(__file__).parent))
from emit_table import emit_table

DIFF_BIN = os.environ.get("DIFF_BIN")

# Scripts chosen so code points, bytes and display columns all disagree.
SAMPLES = [
    "",
    "a",
    "abcdefghijklmnopqrstuvwxyz0123456789",
    "אבגדהוזחטיכלמנסעפצקרשת" * 3,
    "日本語のテキストです" * 4,
    "𝔘𝔫𝔦𝔠𝔬𝔡𝔢" * 6,
    "👨‍👩‍👧‍👦" * 8,
    unicodedata.normalize("NFC", "café résumé naïve " * 6),
    unicodedata.normalize("NFD", "café résumé naïve " * 6),
    "line one\nline two\nline three\n" * 4,
    "\t\t\t   spaced   \t\t\t" * 5,
    "mixed אבג 日本 𝔘𝔫 👩‍💻 café" * 5,
    "\x00\x01\x02 control bytes \x1b[31m" * 4,
    "y" * 500,
]

# Every limit that exercises a branch, plus the reachable range.
LIMITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17, 31, 32, 33, 100, 499, 500, 501]


def main() -> int:
    if not DIFF_BIN:
        print("set DIFF_BIN to the differential driver")
        return 2

    # The sample index is part of the key, not the text. Samples 7 and 8 are the
    # NFC and NFD forms of the same visible string and samples 12 and 3 look alike
    # in a listing; keyed by text they would collapse, and they are exactly the
    # cases worth keeping distinct.
    cases = [
        {"sample": index, "text": text, "limit": limit}
        for index, text in enumerate(SAMPLES)
        for limit in LIMITS
    ]
    payload = "\n".join(
        json.dumps({"text": case["text"], "limit": case["limit"]}) for case in cases
    ) + "\n"

    completed = subprocess.run(
        [DIFF_BIN], input=payload.encode("utf-8"), capture_output=True
    )
    if completed.returncode != 0:
        print(completed.stderr.decode("utf-8")[:2000])
        return 1

    native = [
        json.loads(line)
        for line in completed.stdout.decode("utf-8").splitlines()
        if line
    ]
    if len(native) != len(cases):
        print(f"driver returned {len(native)} rows for {len(cases)} cases")
        return 1

    def case_key(case: dict) -> str:
        return f"sample{case['sample']}/limit{case['limit']}"

    actual_by_key = {case_key(case): actual for case, actual in zip(cases, native)}
    mismatches = []
    for case, actual in zip(cases, native):
        expected = truncate_middle(case["text"], max_chars=case["limit"])
        if actual != expected:
            mismatches.append((case, expected, actual))

    if "--emit-table" in sys.argv:
        written, message = emit_table(
            Path(sys.argv[sys.argv.index("--emit-table") + 1]),
            cases=cases,
            expected_for=lambda case: truncate_middle(case["text"], max_chars=case["limit"]),
            mismatched_keys=[case_key(case) for case, _e, _a in mismatches],
            key_for=case_key,
            oracle_revision="8cb4c5f",
            generated_by=Path(__file__).name,
            declared={},
            actual_for=lambda case: actual_by_key[case_key(case)],
        )
        print(message)
        if not written:
            return 1

    print(f"cases: {len(cases)}  ({len(SAMPLES)} samples x {len(LIMITS)} limits)")
    print(f"mismatches: {len(mismatches)}")
    for case, expected, actual in mismatches[:8]:
        print(f"  limit={case['limit']} text={case['text'][:28]!r}")
        print(f"    python {expected!r}")
        print(f"    native {actual!r}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
