#!/usr/bin/env python3
"""Size the early-close corpus and measure the economy it is meant to protect.

When the consumer stops reading, the scan must stop. Measured as a pair on one
corpus — close the reader after one line, versus read to the end — so both runs
pay identical interpreter startup and the difference is scan time alone.

Every session matches, deliberately. With a single match there is nothing left to
write after the first line, so no write ever hits the closed pipe and the process
runs to completion whether or not it handles early close. A corpus that cannot
distinguish the two is worse than no gate.
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
BUILT_CH = PROJECT_ROOT / "target" / "contract-suite" / "release" / "ch"
MARKER = "closemarker"
# No literal candidate, so the fast byte gate is bypassed and every file gets a
# full semantic scan — long enough for an early exit to be visible.
PATTERN = f"{MARKER}|zzznope"
BODY = "unrelated filler content " * 400


def build(home: Path, sessions: int) -> None:
    if home.exists():
        shutil.rmtree(home)
    projects = home / ".claude" / "projects" / "close"
    projects.mkdir(parents=True)
    base = 1_800_040_000.0
    for index in range(sessions):
        path = projects / f"match-{index:04d}.jsonl"
        path.write_text(
            json.dumps({
                "type": "user",
                "timestamp": "2026-08-20T10:00:00.000Z",
                "cwd": "/tmp/close",
                "message": {"role": "user", "content": f"{MARKER} {BODY} {index}"},
            }, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.utime(path, (base + index, base + index))


def run(home: Path, *, close_early: bool) -> tuple[float, int]:
    environment = os.environ.copy()
    environment.update({"HOME": str(home), "TZ": "Asia/Jerusalem", "COLUMNS": "96", "NO_COLOR": "1"})
    start = time.perf_counter()
    process = subprocess.Popen(
        [str(BUILT_CH), "search", PATTERN, "-ll"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        cwd=str(PROJECT_ROOT),
    )
    lines = 0
    process.stdout.readline()
    lines += 1
    if close_early:
        process.stdout.close()
    else:
        while process.stdout.readline():
            lines += 1
        process.stdout.close()
    process.wait()
    return time.perf_counter() - start, lines


def main() -> None:
    home = Path(sys.argv[1]) / "home"
    for sessions in (300, 800):
        build(home, sessions)
        full, full_lines = run(home, close_early=False)
        closed, _ = run(home, close_early=True)
        print(
            f"sessions={sessions:5d}  full={full * 1000:7.1f}ms ({full_lines} ids)  "
            f"closed={closed * 1000:7.1f}ms  saved={(1 - closed / full) * 100:5.1f}%"
        )


if __name__ == "__main__":
    main()
