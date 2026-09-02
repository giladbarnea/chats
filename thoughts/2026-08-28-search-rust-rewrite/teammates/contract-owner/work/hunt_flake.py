#!/usr/bin/env python3
"""Replay the byte lock outside pytest and print the first mismatching bytes.

The failures move between runs and vanish when a case is run alone, so the
report has to show the actual bytes rather than a count. A finding taken from an
aggregate here would be a guess with a number attached.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "tests")
import test_search_command_contract as contract  # noqa: E402

ROOT = Path("tests/data/search-contract-fixtures")


def build_home(destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(ROOT / "home", destination)
    for relative_path, mtime in json.loads((ROOT / "MTIMES.json").read_text()).items():
        os.utime(destination / relative_path, (mtime, mtime))
    return destination


def main() -> int:
    home = build_home(Path(sys.argv[1]) / "home")
    mismatches = 0
    for corpus, case in contract.ALL_CASES:
        if corpus.name != 'contract':
            continue
        completed = contract._run_search(contract.CONTRACT_BUILT_CH, case, home)
        got_out = contract._normalize(completed.stdout, home)
        got_err = contract._normalize(completed.stderr, home)
        want_out = (ROOT / str(case["expected_stdout"])).read_bytes()
        want_err = (ROOT / str(case["expected_stderr"])).read_bytes()
        if completed.returncode == case["exit_status"] and got_out == want_out and got_err == want_err:
            continue
        mismatches += 1
        print(f"\n{'=' * 74}\n### {case['id']}  args={case['arguments']}")
        print(f"exit want={case['exit_status']} got={completed.returncode}")
        for label, want, got in (("stdout", want_out, got_out), ("stderr", want_err, got_err)):
            if want == got:
                continue
            print(f"--- {label}: {len(want)} expected bytes vs {len(got)} actual ---")
            for index, (a, b) in enumerate(zip(want, got)):
                if a != b:
                    start = max(0, index - 60)
                    print(f"first difference at byte {index}")
                    print(f"  expected …{want[start:index + 60]!r}")
                    print(f"  actual   …{got[start:index + 60]!r}")
                    break
            else:
                print(f"  one is a prefix of the other; tail differs by {abs(len(want) - len(got))} bytes")
                print(f"  expected tail {want[-120:]!r}")
                print(f"  actual   tail {got[-120:]!r}")
    print(f"\n{mismatches} mismatched")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
