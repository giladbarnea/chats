#!/usr/bin/env python3
"""Size the streaming corpus so time-to-first-id and total time separate.

The gate is a ratio, not a budget: the first id must arrive in a small fraction
of the total run. That only means anything if the scan genuinely continues after
the first hit, so this measures how many decoy sessions are needed before the
total is long enough for the ratio to discriminate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
BUILT_CH = PROJECT_ROOT / "target" / "release" / "ch"
MARKER = "streammarker"
# `|` is a regex metacharacter, so this pattern has no literal candidate and the
# fast byte gate is bypassed: every file gets a full semantic scan. That makes
# the scan long enough to separate from interpreter startup.
SLOW_PATTERN = "streammarker|zzznope"
DECOY_BODY = "unrelated filler content " * 400


def build(home: Path, decoys: int, *, match_newest: bool) -> str:
    if home.exists():
        shutil.rmtree(home)
    projects = home / ".claude" / "projects" / "stream"
    projects.mkdir(parents=True)
    base = 1_800_030_000.0

    for index in range(decoys):
        path = projects / f"decoy-{index:04d}.jsonl"
        path.write_text(
            json.dumps({
                "type": "user",
                "timestamp": "2026-08-20T10:00:00.000Z",
                "cwd": "/tmp/stream",
                "message": {"role": "user", "content": f"{DECOY_BODY} {index}"},
            }, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.utime(path, (base + index, base + index))

    match = projects / "match-newest.jsonl"
    match.write_text(
        json.dumps({
            "type": "user",
            "timestamp": "2026-08-20T11:00:00.000Z",
            "cwd": "/tmp/stream",
            "message": {"role": "user", "content": f"{MARKER} lives here"},
        }, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    stamp = base + decoys + 1 if match_newest else base - 1
    os.utime(match, (stamp, stamp))
    return match.stem


def measure(home: Path) -> tuple[float, float, bytes]:
    environment = os.environ.copy()
    environment.update({"HOME": str(home), "TZ": "Asia/Jerusalem", "COLUMNS": "96", "NO_COLOR": "1"})
    start = time.perf_counter()
    process = subprocess.Popen(
        [str(BUILT_CH), "search", SLOW_PATTERN, "-ll"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        cwd=str(PROJECT_ROOT),
    )
    first = process.stdout.readline()
    first_at = time.perf_counter() - start
    process.stdout.read()
    process.wait()
    return first_at, time.perf_counter() - start, first


def main() -> None:
    home = Path(sys.argv[1]) / "home"
    for decoys in (300, 800):
        for match_newest in (True, False):
            build(home, decoys, match_newest=match_newest)
            first_at, total, first = measure(home)
            where = "newest" if match_newest else "oldest"
            print(
                f"decoys={decoys:5d} match={where:6s}  first_id={first_at * 1000:7.1f}ms  "
                f"total={total * 1000:7.1f}ms  first_line={first.decode().strip()!r}"
            )


if __name__ == "__main__":
    main()
