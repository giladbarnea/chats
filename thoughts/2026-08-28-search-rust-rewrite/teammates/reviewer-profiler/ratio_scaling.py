#!/usr/bin/env python3
"""Is a ratio gate a property of the implementation, or a point on a curve?

Both routes plausibly have a fixed cost plus a per-file cost. If so a ratio
measured at one corpus size is not a property: Python's interpreter startup is
a large constant the native route does not pay, so the ratio should rise toward
the true per-file work ratio as the corpus grows, and understate it below.

The gates stay sound either way, because the corpus is frozen and the gate
measures that corpus. What this decides is whether the *sentence* "native is
0.18x Python" travels.

    ratio_scaling.py SUBJECT REFERENCE
"""

from __future__ import annotations

import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

CORPUS = Path.home() / ".cache" / "ch-search-corpus" / "v1"
ROOT = Path.home() / ".cache" / "ch-search-corpus" / "scaling"
STRIDES = {10: 70, 4: 174, 2: 348, 1: 695}
SHAPES = {
    "selective literal": ["search", "needle", "-ll"],
    "broad regex miss": ["search", "zq[xj]{2}vwmk", "-ll"],
}
REPETITIONS = 3


def build_subset(stride: int) -> Path:
    home = ROOT / f"stride{stride}"
    if home.exists():
        return home
    sessions = sorted(CORPUS.rglob("*.jsonl"))[::stride]
    for source in sessions:
        destination = home / source.relative_to(CORPUS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return home


def timed(binary: str, arguments: list[str], home: Path) -> float:
    start = time.perf_counter()
    subprocess.run(
        [binary, *arguments],
        capture_output=True,
        check=False,
        env=os.environ | {"HOME": str(home), "NO_COLOR": "1", "COLUMNS": "96"},
    )
    return (time.perf_counter() - start) * 1000


def interleaved(subject: str, reference: str, arguments: list[str], home: Path) -> tuple[float, float]:
    timed(subject, arguments, home)
    timed(reference, arguments, home)
    s, r = [], []
    for _ in range(REPETITIONS):
        s.append(timed(subject, arguments, home))
        r.append(timed(reference, arguments, home))
    return statistics.median(s), statistics.median(r)


def main() -> int:
    subject, reference = sys.argv[1], sys.argv[2]
    homes = {count: build_subset(stride) for stride, count in STRIDES.items()}

    for shape, arguments in SHAPES.items():
        print(f"\n{shape}")
        print(f"  {'files':>6}  {'subject':>10}  {'reference':>11}  {'ratio':>7}")
        for count in sorted(homes):
            s, r = interleaved(subject, reference, arguments, homes[count])
            print(f"  {count:6}  {s:9.1f}ms  {r:10.1f}ms  {s / r:7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
