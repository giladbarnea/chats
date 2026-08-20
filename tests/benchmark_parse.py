#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import time


EXPECTED_FIXTURES = {
    "json": (552_693, "be0bfacf29e2d0fdc29a27bd55c713ca6dd3d121987b18578fd453967223e76e"),
    "xml": (327_099, "9ed12ce8c2d02ce05985d0a053f58fab17f1fc94027872bff427ed2f2f79d47f"),
    "canonical_json": (
        412_168,
        "b5435c7ef3bc385ea23f529ef434da9e35d43aca0493549ff2685f7266c7d823",
    ),
}
BUDGET_MILLISECONDS = 60.0
RUNS_PER_DIRECTION = 7


@dataclass(frozen=True)
class Direction:
    name: str
    arguments: list[str]
    expected_stdout: bytes


def _fixture_bytes(path: Path, fixture_name: str) -> bytes:
    content = path.read_bytes()
    expected_size, expected_sha256 = EXPECTED_FIXTURES[fixture_name]
    actual_sha256 = hashlib.sha256(content).hexdigest()
    assert len(content) == expected_size, (
        f"Expected {fixture_name} fixture size {expected_size}. Got: {len(content)}."
    )
    assert actual_sha256 == expected_sha256, (
        f"Expected {fixture_name} fixture SHA-256 {expected_sha256}. "
        f"Got: {actual_sha256}."
    )
    return content


def _run_conversion(
    executable: Path,
    direction: Direction,
    *,
    measured: bool,
) -> float:
    environment = os.environ.copy()
    environment["TZ"] = "Asia/Jerusalem"
    started = time.perf_counter()
    completed = subprocess.run(
        [str(executable), *direction.arguments],
        env=environment,
        capture_output=True,
        check=False,
    )
    elapsed_milliseconds = (time.perf_counter() - started) * 1_000
    assert completed.returncode == 0, (
        f"Expected {direction.name} to succeed. Exit status: {completed.returncode}; "
        f"stderr: {completed.stderr[:500]!r}."
    )
    assert completed.stdout == direction.expected_stdout, (
        f"Expected exact {direction.name} stdout. "
        f"Expected {len(direction.expected_stdout)} bytes; got {len(completed.stdout)}."
    )
    assert completed.stderr == b"", (
        f"Expected {direction.name} stderr to stay empty. Got: {completed.stderr[:500]!r}."
    )
    return elapsed_milliseconds if measured else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--executable",
        type=Path,
        default=Path.home() / ".local" / "bin" / "ch",
    )
    parser.add_argument(
        "--fixture-directory",
        type=Path,
        default=Path("/tmp/ch-cycle-01-profile"),
    )
    arguments = parser.parse_args()

    source_json = _fixture_bytes(arguments.fixture_directory / "large.json", "json")
    expected_xml = _fixture_bytes(arguments.fixture_directory / "large.xml", "xml")
    expected_json = _fixture_bytes(
        arguments.fixture_directory / "large.canonical.json",
        "canonical_json",
    )
    directions = [
        Direction(
            name="json-to-xml",
            arguments=["parse", str(arguments.fixture_directory / "large.json")],
            expected_stdout=expected_xml,
        ),
        Direction(
            name="xml-to-json",
            arguments=[
                "parse",
                "-f",
                "json",
                str(arguments.fixture_directory / "large.xml"),
            ],
            expected_stdout=expected_json,
        ),
    ]
    assert source_json, "Expected the accepted large structured JSON fixture to be non-empty."

    for direction in directions:
        _run_conversion(arguments.executable, direction, measured=False)

    timings = {direction.name: [] for direction in directions}
    for run_index in range(RUNS_PER_DIRECTION):
        run_order = directions if run_index % 2 == 0 else list(reversed(directions))
        for direction in run_order:
            timings[direction.name].append(
                _run_conversion(arguments.executable, direction, measured=True)
            )

    medians = {
        direction_name: statistics.median(direction_timings)
        for direction_name, direction_timings in timings.items()
    }
    print(json.dumps({"timings_ms": timings, "medians_ms": medians}, indent=2))
    for direction_name, median_milliseconds in medians.items():
        assert median_milliseconds <= BUDGET_MILLISECONDS, (
            f"Expected {direction_name} warm median at most {BUDGET_MILLISECONDS:.0f} ms. "
            f"Got: {median_milliseconds:.1f} ms."
        )


if __name__ == "__main__":
    main()
