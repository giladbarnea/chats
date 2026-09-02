#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Falsify the scan loop's gates: break `search_engine.rs` on purpose, prove each test notices.

A test that has never failed is not known to work. This applies one named mutation at a
time and requires `cargo test` to go red. A mutation nothing catches is a blind spot and
the run fails.

The mutation set **is** this harness's parameterization, so each entry names the hazard it
stands for rather than leaving it implied. An unnamed mutation set is an unexamined
assumption.

Two properties, each bought by someone's mistake:

- **It never touches the shared checkout.** It syncs the crate into a private directory
  and mutates that. `query-semantics`'s harness mutates in place and restores in a
  `finally`, which is correct and still left me reading a transiently mutated file and
  drawing a wrong conclusion from it. A private copy removes the class rather than
  narrowing the window.
- **It refuses rather than reporting a number when an anchor does not match exactly
  once.** A mutation that was never applied and a mutation nothing caught both produce
  "no new failures", and only one of them is a finding.

Structure is imported from `teammates/query-semantics/harness/falsify_gates.py`; the
measurement is not, because that harness diffs corpora against recorded Python output and
this one reads a `cargo test` exit status. Different instrument, same discipline.

Usage:  uv run falsify_engine.py [--repo PATH] [--work PATH]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

TARGET = "rust/search_engine.rs"

# Each mutation names the hazard it stands for. Every one is a change a competent
# implementer could plausibly make while believing it equivalent.
MUTATIONS: list[dict[str, str]] = [
    {
        "name": "batch_counts_scanned_files",
        "hazard": "the batch filling with survivors rather than with scanned paths",
        "find": "            Gated::Rejected => {}",
        "replace": "            Gated::Rejected => pending.push(path.clone()),",
    },
    {
        "name": "screen_failure_skips_the_flush",
        "hazard": "a screen failure landing at its own scan position",
        "find": (
            "                if flush(&mut pending, sink, &mut probe, &mut confirm, &mut found) {\n"
            "                    return outcome(found);\n"
            "                }\n"
            "                sink.emit_error(&message);"
        ),
        "replace": "                sink.emit_error(&message);",
    },
    {
        "name": "early_close_ignored_inside_a_batch",
        "hazard": "the scan stopping at the hit, not at the end of the batch",
        "find": (
            "                *found = true;\n"
            "                if sink.closed() {\n"
            "                    pending.clear();\n"
            "                    return true;\n"
            "                }"
        ),
        "replace": "                *found = true;",
    },
    {
        "name": "early_close_ignored_between_files",
        "hazard": "a reader that quits with no hit yet emitted still stopping the scan",
        "find": "        if sink.closed() {\n            return outcome(found);\n        }\n        match screen(path) {",
        "replace": "        match screen(path) {",
    },
    {
        "name": "probe_rejections_ignored",
        "hazard": "a probe rejection skipping confirmation entirely",
        "find": "        if !candidate {\n            continue;\n        }",
        "replace": "        if false {\n            continue;\n        }\n        let _ = candidate;",
    },
    {
        "name": "final_partial_batch_dropped",
        "hazard": "the trailing batch being confirmed after the scan ends",
        "find": "    flush(&mut pending, sink, &mut probe, &mut confirm, &mut found);\n    if !sink.closed() {",
        "replace": "    if !sink.closed() {",
    },
    {
        "name": "probe_decisions_misaligned",
        "hazard": "decisions being positional against their input paths",
        "find": "    for (path, candidate) in pending.iter().zip(decisions) {",
        "replace": "    for (path, candidate) in pending.iter().rev().zip(decisions) {",
    },
    {
        "name": "empty_pool_collapsed_into_no_hits",
        "hazard": "an empty candidate pool exiting 1 silently",
        "find": "        return Outcome::EmptyPool;",
        "replace": "        return Outcome::NoHits;",
    },
    {
        "name": "no_results_hint_on_an_empty_pool",
        "hazard": "the hint distinguishing a fruitless search from an empty pool",
        "find": "        matches!(self, Outcome::NoHits)",
        "replace": "        !matches!(self, Outcome::Hits)",
    },
]

FAILED_TEST = re.compile(r"^test (\S+) \.\.\. FAILED$", re.MULTILINE)


def cargo_test(work: pathlib.Path) -> tuple[bool, set[str]]:
    """Run the engine tests in `work`. Returns (all passed, names that FAILED)."""
    result = subprocess.run(
        ["cargo", "test", "--no-default-features", "--lib", "search_engine"],
        cwd=work,
        capture_output=True,
        env={**_env(), "CARGO_TARGET_DIR": str(work / "target")},
    )
    output = result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
    if "error[" in output or "error: could not compile" in output:
        return False, {"<build failed>"}
    return result.returncode == 0, set(FAILED_TEST.findall(output))


def _env() -> dict[str, str]:
    import os

    return dict(os.environ)


def sync(repo: pathlib.Path, work: pathlib.Path) -> None:
    """Refresh the private crate from the real tree, so the gate grades today's artifact."""
    work.mkdir(parents=True, exist_ok=True)
    for name in ("Cargo.toml", "Cargo.lock", "build.rs"):
        source = repo / name
        if source.exists():
            shutil.copy2(source, work / name)
    if (work / "rust").exists():
        shutil.rmtree(work / "rust")
    shutil.copytree(repo / "rust", work / "rust")
    # The recorded oracle tables are `include_str!`d by tests in `search_output.rs`
    # and `terminal.rs`, so a crate copy without them does not compile.
    probes = "thoughts/2026-08-28-search-rust-rewrite/teammates/engine-and-codex/probes"
    (work / probes).mkdir(parents=True, exist_ok=True)
    for table in (repo / probes).glob("*.tsv"):
        shutil.copy2(table, work / probes / table.name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", type=pathlib.Path)
    parser.add_argument(
        "--work",
        type=pathlib.Path,
        default=pathlib.Path("/private/tmp/ch-falsify-engine"),
        help="Private crate copy. Never the shared checkout.",
    )
    arguments = parser.parse_args()
    repo = arguments.repo.resolve()
    work = arguments.work.resolve()

    if work == repo or repo in work.parents:
        return _fail(f"--work {work} is inside the checkout; refusing to mutate shared source")

    sync(repo, work)
    target = work / TARGET
    pristine = target.read_text()

    passed, failures = cargo_test(work)
    if not passed:
        return _fail(
            "baseline is not green, so nothing below would mean anything. "
            f"Failing: {sorted(failures) or '<build>'}"
        )
    print(f"baseline: green against {repo}/{TARGET}\n")

    print(f"{'mutation':<38} {'verdict':<9} caught by")
    survivors: list[str] = []
    for mutation in MUTATIONS:
        occurrences = pristine.count(mutation["find"])
        if occurrences != 1:
            print(
                f"{mutation['name']:<38} {'REFUSED':<9} "
                f"ANCHOR MATCHES {occurrences} TIMES, EXPECTED 1 — "
                f"mutation not applied, result meaningless"
            )
            survivors.append(mutation["name"])
            continue

        target.write_text(pristine.replace(mutation["find"], mutation["replace"], 1))
        try:
            still_green, failures = cargo_test(work)
        finally:
            target.write_text(pristine)

        if still_green:
            survivors.append(mutation["name"])
            print(f"{mutation['name']:<38} {'SURVIVED':<9} nothing — the gate is blind to: {mutation['hazard']}")
            continue
        names = sorted(name.split("::")[-1] for name in failures)
        print(f"{mutation['name']:<38} {'killed':<9} {', '.join(names)}")

    print()
    if survivors:
        return _fail(f"{len(survivors)} mutation(s) nothing caught: {', '.join(survivors)}")
    print(f"PASS: all {len(MUTATIONS)} mutations were caught, each by a named test")
    return 0


def _fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
