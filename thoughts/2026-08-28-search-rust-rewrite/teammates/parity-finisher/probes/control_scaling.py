#!/usr/bin/env python3
"""Does a candidate control command actually grow with the session pool?

**The question this answers, and why it is not optional.** Two performance
budgets are being converted from absolute milliseconds to a ratio against a
control, because an absolute budget on a growing pool rots — the test's own
comment records it being pushed from 1,000 to 1,200 to 1,750 ms. The ratio only
removes that rot **if the control grows with the pool at the same rate the
subject does.** A control picked for cheapness that turns out to be flat
silently reintroduces exactly the rot it was chosen to remove, and nothing in
the gate would ever say so.

So: build synthetic pools of several sizes, point HOME at each, and time every
candidate. A control is admissible when its time grows roughly linearly in the
number of sessions.

    uv run -p python3 python .../probes/control_scaling.py [sizes...]

Default sizes are 500 1000 2000 4000. The pools are written under the system
temporary directory and removed afterwards.
"""

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPEATS = 3

CANDIDATES: dict[str, list[str]] = {
    "search . --list": ["search", ".", "--list"],
    "search zzzznomatchzzz --list": ["search", "zzzznomatchzzz", "--list"],
    "-1": ["-1"],
    "search . -ma 4h --list": ["search", ".", "-ma", "4h", "--list"],
    "search . -l -d .": ["search", ".", "-l", "-d", "."],
}


RECENT_FRACTION = 0.05


def write_pool(root: Path, count: int) -> None:
    """One small, valid Claude session per file, all in one project directory.

    **A fixed fraction of the pool is recent, and that is not decoration.** The
    first version stamped every session with one old timestamp, so `-ma 4h`
    matched nothing and measured a short-circuit rather than a scan — it read as
    growth 0.09 where the same shape on the real pool grows with it. A held
    parameter nobody chose. Keeping the recent share fixed makes the `-ma` subject
    grow with the pool the way it does in production.
    """
    directory = root / ".claude" / "projects" / "-synthetic-pool"
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    recent = max(1, int(count * RECENT_FRACTION))
    for index in range(count):
        stamp = (
            now - timedelta(minutes=index % 60)
            if index < recent
            else now - timedelta(days=30 + (index % 300))
        )
        stamped = stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        entries = [
            {
                "type": "user",
                "uuid": f"u{index}",
                "parentUuid": None,
                "cwd": str(root),
                "timestamp": stamped,
                "message": {"role": "user", "content": f"synthetic question {index}"},
            },
            {
                "type": "assistant",
                "uuid": f"a{index}",
                "parentUuid": f"u{index}",
                "timestamp": stamped,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"synthetic answer {index}"}],
                },
            },
        ]
        body = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        (directory / f"{index:08d}-0000-0000-0000-000000000000.jsonl").write_text(body)


def time_command(args: list[str], home: Path) -> float:
    import os

    environment = dict(os.environ, HOME=str(home))
    start = time.perf_counter()
    subprocess.run(
        ["uv", "run", "ch", *args],
        check=False,
        capture_output=True,
        env=environment,
        cwd=str(home),
    )
    return (time.perf_counter() - start) * 1000


def main() -> int:
    sizes = [int(value) for value in sys.argv[1:]] or [500, 1000, 2000, 4000]
    measurements: dict[str, list[float]] = {name: [] for name in CANDIDATES}

    root = Path(tempfile.mkdtemp(prefix="control-scaling-"))
    try:
        for size in sizes:
            home = root / f"pool-{size}"
            write_pool(home, size)
            for name, args in CANDIDATES.items():
                times = [time_command(args, home) for _ in range(REPEATS)]
                measurements[name].append(statistics.median(times))
            print(f"pool {size:5} sessions done", flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    header = "command".ljust(32) + "".join(f"{size:>10}" for size in sizes)
    print(header + "     growth")
    print("-" * len(header) + "  ----------")
    for name, medians in measurements.items():
        # Growth is the observed time ratio divided by the session-count ratio.
        # 1.0 means the command grows exactly in step with the pool; near 0 means
        # it does not grow with the pool at all and is inadmissible as a control.
        size_ratio = sizes[-1] / sizes[0]
        time_ratio = medians[-1] / medians[0] if medians[0] else float("nan")
        growth = (time_ratio - 1) / (size_ratio - 1)
        row = name.ljust(32) + "".join(f"{value:10.0f}" for value in medians)
        print(f"{row}  {growth:9.2f}")
    print()
    print("growth 1.00 = grows exactly in step with the pool; 0.00 = flat.")
    print("A control is admissible only if its growth is close to the subject's.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
