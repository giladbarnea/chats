#!/usr/bin/env python3
"""Calibrate the search contract harness against `reviewer-profiler`'s probes.

Two instruments are graded, not one, because they can be blind in different
places:

* the capture — how the suite reads a process's output;
* the comparator — capture plus `_normalize`, which is what the byte lock and
  the live differential actually compare.

A normalization is a deliberate blindness. Grading only the capture would hide
it, which is the same mistake the normalizations exist to be honest about.

The one accepted blindness is identified by what it *is* rather than by the
probe's name: a pair whose two payloads differ only in which of the four
age-bucket colours they use. Matching on a name couples this gate to a label
owned upstream, and a rename then reads as a parity failure — which is exactly
what happened the first time this ran after the probe table was refactored.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).parent
PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
sys.path.insert(
    0, str(PROJECT_ROOT / "thoughts/2026-08-28-search-rust-rewrite/teammates/reviewer-profiler")
)

import calibrate_harness  # noqa: E402
import test_search_command_contract as contract  # noqa: E402

FIXTURE_HOME = Path("/nonexistent-home-for-calibration")
_SGR = re.compile(rb"\x1b\[[0-9;]*m")


def capture_like_the_suite(payload: bytes) -> object:
    """Read a process's stdout exactly as the contract suite reads it."""
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        input=payload,
        capture_output=True,
        check=False,
    )
    return completed.stdout


def compare_like_the_suite(payload: bytes) -> object:
    """Read and normalize exactly as the byte lock and live differential do."""
    return contract._normalize(capture_like_the_suite(payload), FIXTURE_HOME)


def _is_age_bucket_only(dimension: str) -> bool:
    """Whether a probe's two payloads differ only among the four age colours.

    That is the whole of the declared normalization. Any other blindness — a
    different colour pair, or anything that is not colour at all — is undeclared
    and fails this gate regardless of what the probe is called.
    """
    probe = calibrate_harness.PROBES.get(dimension)
    if probe is None:
        return False
    baseline, mutated = probe
    if _SGR.sub(b"", baseline) != _SGR.sub(b"", mutated):
        return False
    sequences = set(_SGR.findall(baseline)) | set(_SGR.findall(mutated))
    age_sequences = set(contract.AGE_STYLE_SEQUENCES) | {b"\x1b[0m"}
    return bool(sequences) and sequences <= age_sequences


def _classifier_discriminates() -> None:
    """Prove the accepted-blindness rule can still say no.

    `_is_age_bucket_only` is a rule this file reimplements, and a gate aimed by a
    reimplemented rule can degrade silently: if this one drifted permissive, every
    blindness would be "declared" and the gate would pass forever while measuring
    nothing. So it has to reject something known, not merely accept something
    known.
    """
    accepted = {name for name in calibrate_harness.PROBES if _is_age_bucket_only(name)}
    rejected = set(calibrate_harness.PROBES) - accepted
    assert accepted, (
        "The accepted-blindness rule matches no probe at all, so it can no longer "
        "recognise the declared normalization. The probe table has moved out from "
        "under it."
    )
    assert len(accepted) == 1, (
        f"Expected exactly one probe to be age-bucket-only. Got: {sorted(accepted)}. "
        "More than one means the rule has drifted permissive."
    )
    assert any("SGR" in name for name in rejected), (
        "The rule accepts every SGR probe, so it cannot distinguish the declared "
        "age normalization from colour blindness in general."
    )


def main() -> int:
    _classifier_discriminates()
    results = {
        "capture": calibrate_harness.calibrate("capture", capture_like_the_suite),
        "comparator (capture + _normalize)": calibrate_harness.calibrate(
            "comparator", compare_like_the_suite
        ),
    }
    for name, blind in results.items():
        status = "CALIBRATED" if not blind else f"BLIND in {len(blind)}"
        print(f"{name:36} {status}")
        for dimension in blind:
            print(f"{'':36} - cannot see: {dimension}")

    capture_blind = set(results["capture"])
    comparator_blind = set(results["comparator (capture + _normalize)"])
    undeclared = {d for d in comparator_blind if not _is_age_bucket_only(d)}

    print()
    print(f"probes graded: {len(calibrate_harness.PROBES)}")
    if capture_blind:
        print(f"FAIL: the capture is blind in {sorted(capture_blind)}.")
        return 1
    if undeclared:
        print(f"FAIL: the comparator has undeclared blindness in {sorted(undeclared)}.")
        return 1
    print(
        "PASS. The capture sees every probed dimension. The comparator is blind\n"
        "only where a probe's two payloads differ solely in which age-bucket\n"
        "colour they carry — the declared normalization, pinned separately by\n"
        "`test_search_age_token_and_style_track_the_clock`, and deleted when the\n"
        "clock injection point lands."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
