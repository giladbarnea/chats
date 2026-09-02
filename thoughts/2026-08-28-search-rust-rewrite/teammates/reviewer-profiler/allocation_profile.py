#!/usr/bin/env python3
"""Name the mechanism behind the memory gap by reading the slope, not the total.

The agent-bearing arm shows the native route holding about 29% more than Python
through the same confirmation. A single pair of totals cannot say why. Varying
the oversized line and fitting peak RSS against it can: the slope is how many
resident copies of the payload each route keeps, and the intercept is its fixed
cost. "Nine copies against seven" is actionable where "29% more" is not.

Needs no privileged tooling, which matters because DTrace is SIP-restricted here
and `/usr/sbin/purge` is denied.

    allocation_profile.py SUBJECT REFERENCE
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
from pathlib import Path

SOURCE = Path("/Users/giladbarnea/dev/chats/tests/data/pi-custom-message.jsonl")
ROOT = Path.home() / ".cache" / "ch-search-corpus" / "allocation-profile"
SIZES_MB = (8, 16, 32, 64, 96)

# Python's measured model, frozen so this instrument outlives the oracle. Taken at
# oracle 8cb4c5f on corpus arms 8..96 MB: peak = 7.01 x payload + 82 MB fixed.
# After cutover there is no reference route to interleave against, so the gate
# becomes "the subject must not hold more resident copies than Python did".
REFERENCE_SLOPE = 7.01
REFERENCE_INTERCEPT_MB = 82.0
SLOPE_TOLERANCE = 1.05
ABSENT_LITERAL = ["search", "zqxjvwmkbphfgd", "-ll"]
FILLER = "abcdefghijklmnopqrstuvwxyz0123456789 "


def build_arm(payload_bytes: int) -> Path:
    home = ROOT / f"mb{payload_bytes >> 20}"
    sessions = home / ".pi" / "agent" / "sessions"
    if (sessions / "arm.jsonl").exists():
        return home
    sessions.mkdir(parents=True, exist_ok=True)
    body = (FILLER * (payload_bytes // len(FILLER) + 1))[:payload_bytes]
    final = json.dumps(
        {
            "type": "message",
            "id": "final",
            "parentId": None,
            "message": {"role": "assistant", "content": [{"type": "text", "text": body}]},
        },
        separators=(",", ":"),
    )
    prefix = SOURCE.read_text(encoding="utf-8").rstrip("\n")
    (sessions / "arm.jsonl").write_text(f"{prefix}\n{final}\n", encoding="utf-8")
    return home


def peak_megabytes(binary: str, home: Path) -> float:
    pid = os.fork()
    if pid == 0:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        os.execve(binary, [binary, *ABSENT_LITERAL], os.environ | {"HOME": str(home), "NO_COLOR": "1"})
        os._exit(127)
    _pid, status, usage = os.wait4(pid, 0)
    if os.waitstatus_to_exitcode(status) == 127:
        raise SystemExit(f"probe failed to exec {binary}")
    return usage.ru_maxrss / (1 << 20)


def slope_and_intercept(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    variance = sum((x - mean_x) ** 2 for x in xs)
    slope = covariance / variance
    return slope, mean_y - slope * mean_x


def main() -> int:
    subject, reference = sys.argv[1], sys.argv[2]
    homes = {size: build_arm(size << 20) for size in SIZES_MB}

    print(f"{'payload':>9}  {'subject':>10}  {'reference':>10}")
    measurements: dict[str, list[float]] = {"subject": [], "reference": []}
    for size in SIZES_MB:
        subject_peak = max(peak_megabytes(subject, homes[size]) for _ in range(2))
        reference_peak = max(peak_megabytes(reference, homes[size]) for _ in range(2))
        measurements["subject"].append(subject_peak)
        measurements["reference"].append(reference_peak)
        print(f"{size:6} MB  {subject_peak:8.0f}MB  {reference_peak:8.0f}MB")

    xs = [float(size) for size in SIZES_MB]
    print()
    for role in ("subject", "reference"):
        slope, intercept = slope_and_intercept(xs, measurements[role])
        print(f"{role:10} peak = {slope:.2f} x payload + {intercept:.0f} MB fixed")
    subject_slope, _ = slope_and_intercept(xs, measurements["subject"])
    reference_slope, _ = slope_and_intercept(xs, measurements["reference"])
    print()
    print(
        f"resident copies of the payload: subject {subject_slope:.2f}, reference "
        f"{reference_slope:.2f}, difference {subject_slope - reference_slope:+.2f}"
    )

    # The durable form. A live reference disappears at cutover; the frozen model
    # does not, and it asks the same question rather than a weaker one.
    ceiling = REFERENCE_SLOPE * SLOPE_TOLERANCE
    ok = subject_slope <= ceiling
    print(
        f"\nfrozen gate: subject slope {subject_slope:.2f} against Python's recorded "
        f"{REFERENCE_SLOPE} x{SLOPE_TOLERANCE} = {ceiling:.2f}  {'PASS' if ok else 'FAIL'}"
    )
    drift = abs(reference_slope - REFERENCE_SLOPE) / REFERENCE_SLOPE
    if drift > 0.05:
        print(
            f"  NOTE: the live reference measured {reference_slope:.2f}, {drift:.0%} from the "
            f"frozen {REFERENCE_SLOPE}. Re-freeze before trusting the constant."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
