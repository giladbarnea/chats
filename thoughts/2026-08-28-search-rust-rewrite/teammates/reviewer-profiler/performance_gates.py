#!/usr/bin/env python3
"""The A2 fixed-corpus performance and memory gates.

Replaces the two live-pool budgets that flapped because they measured a growing
corpus through a moving relative date.

**All six time gates are absolutes on the frozen corpus.** They passed through a
ratio form for one afternoon and came back, and both moves were right for their
moment: ratios while both routes existed and the ceilings in force had been
derived from a *different build*; absolutes once the deletion was next, because
**a ratio needs a live denominator and a stored Python timing is not one.** See
the block above `ABSOLUTE_TIME_GATES` for the digest that makes absolutes
admissible here.

    performance_gates.py SUBJECT

⚠ **`--reference` and `--falsify` were RETIRED on 2026-09-02** and the gate refuses
them by name. They consumed the Python route, which is deleted. **The property
`--falsify` existed to check is asserted instead** — `verify_ceilings_discriminate`
refuses to run if any ceiling sits at or above the Python figure recorded for its
shape, before anything is measured, so the hole cannot open in the first place.
The retirement and its measurement are recorded where `run_memory_parity` was.

**The subject must be a native binary and the gate refuses otherwise.** See
`verify_native_subject`: a launcher that delegates to the Python route would make
every measurement Python's own, and linkage cannot tell the two apart.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CORPUS = Path.home() / ".cache" / "ch-search-corpus" / "v1"
PROBE = Path.home() / ".cache" / "ch-search-corpus" / "pi-bigline"
CORPUS_IDENTITY = "de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965"
REPETITIONS = 5
REPOSITORY = Path(__file__).resolve().parents[4]


def _tests_on_path() -> None:
    """Put the repository's `tests/` on `sys.path`. Two callers, one insert."""
    if str(REPOSITORY / "tests") not in sys.path:
        sys.path.insert(0, str(REPOSITORY / "tests"))


def oracle_stamp() -> str:
    """The route the historical Python column came from — **derived, not written here.**

    ⚠ **This was a hardcoded string and it went stale the moment the route moved:**
    `HEAD 8cb4c5f, oracle route digest sha256:dd6ab701…`, naming a revision that
    predates this whole mission and a route that no longer exists. **The same fault
    was corrected in `frozen_reference.json` the day before by making the
    instrument derive the field, and it survived in this file because nothing
    derived it here.** *A field nobody derives is a field nobody re-derives.*

    `tests/oracle_provenance.py` is the one authority for that route's identity now.
    """
    _tests_on_path()
    import oracle_provenance

    return (
        f"revision {oracle_provenance.ORACLE_ROUTE_REVISION}, "
        f"oracle route digest {oracle_provenance.ORACLE_ROUTE_DIGEST} "
        "(deleted 2026-09-02; re-derivable — see tests/data/oracle-route-inputs/)"
    )

# The six time gates, as ABSOLUTES on the frozen corpus.
# Measured by `g5-runner` 2026-09-01T19:28-19:31Z **while both routes still
# existed**; landed by `parity-finisher`. Spec:
# `teammates/g5-runner/perf-gate-absolutes.md`.
#
#   shape                        native med   worst   spread  margin  CEILING   python
#   help                            5.3ms     8.2ms   2.02x   2.00x     20ms     199ms
#   broad literal miss, id-only   253.5ms   256.1ms   1.02x   1.25x    325ms     464ms
#   broad list, absolute date     967.7ms   990.0ms   1.03x   1.25x   1240ms    2410ms
#   colored matches              2300.4ms  2343.3ms   1.02x   1.25x   2930ms   21539ms
#   selective literal, id-only    904.8ms   985.2ms   1.10x   1.25x   1235ms    2080ms
#   broad regex miss, id-only    1628.1ms  1649.5ms   1.02x   1.25x   2065ms    3782ms
#
# CEILING = worst observed x margin, ROUNDED UP to 5 ms. Both inputs are here so
# the arithmetic is checkable rather than trusted. Margin covers the measured
# noise band: 1.25x where spread is <= 1.20x, and 2.00x for `help`, whose spread
# is 2.02x because it is a 5 ms measurement dominated by process startup.
#
# --- Why absolutes are admissible here, and it is NOT a reversal -------------
# Absolutes were retired because the LIVE POOL grew: every widening was locally
# reasonable, none was recorded, and that is how they reached 1750 ms and 2500 ms.
# **These do not run on a live pool.** They run on the corpus check 2 pins -
# 695 files, 1,183,541,907 bytes, digest
# de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965 - and
# `verify_corpus` below refuses to run if it moves. **A frozen, digest-pinned
# corpus cannot rot from growth, which is the only thing that killed the old
# absolutes.** Without that digest named here, a reader sees absolutes restored
# and reads a reversal.
#
# **And ratios could not survive the deletion.** A stored Python timing satisfies
# none of same-query / same-corpus / same-window / same-machine. A frozen
# denominator is not a denominator.
#
# --- The correction TIGHTENS more than it loosens ----------------------------
#   help                  25ms -> 20ms     tighter
#   broad literal miss   750ms -> 325ms    tighter, 2.3x
#   colored matches     4000ms -> 2930ms   tighter
#   broad list           650ms -> 1240ms   LOOSER - the only one
#   selective literal    ratio -> 1235ms
#   broad regex miss     ratio -> 2065ms
# Three of the four surviving absolutes get tighter. The one that loosens is the
# shape the port takes 968 ms on against an old 650 ms budget **derived from the
# branch build** - the shape that was failing. A correction that tightens three
# ceilings is not a relaxation, and the table is the argument.
#
# --- The live ratios, recorded because they can never be retaken -------------
#   help 0.033   literal miss 0.552   broad list 0.397
#   colored 0.108   selective literal 0.435   regex miss 0.433
# Every shape 1.8x to 33x faster than the route it replaces, measured interleaved
# on 2026-09-01 at oracle digest sha256:dd6ab701...
#
# ⚠ **The python column is HISTORICAL EVIDENCE and explicitly NOT a denominator.**
# It records what the replaced route cost on this corpus on this day.
# **Do not compute a ratio from it.**
#
# --- Why every repetition is printed, and it is not decoration ---------------
# The first derivation was wrong twice, and one fault would have shipped a gate
# that proves nothing.
#   1. Rounding to NEAREST put `help`'s ceiling at 5 ms, BELOW its own worst run
#      of 5.8 ms. The gate would have failed on a working product. Ceilings round
#      up.
#   2. One contended run of 490 ms against a 260 ms median drove `broad literal
#      miss` to a 980 ms ceiling - **above Python's 464 ms**. Nine repetitions
#      show 251-256 ms at 1.02x spread; the 490 ms was the machine. A 3x
#      difference in the ceiling from one run nobody would have seen.
#
# --- Standing rules ----------------------------------------------------------
# A flapping row is widened WITH A RECORDED MEASUREMENT, never quietly - that is
# how the live-pool budgets reached 1750 and 2500. And `broad literal miss` is the
# thinnest at 1.43x headroom: most likely to catch a real regression, least room
# to do it in. As an absolute it once proved nothing at 750 ms; at 325 ms it is
# the sharpest of the six.
#
# --- TIME ONLY ---------------------------------------------------------------
# On memory the port is worse and was measured so the same day: +576 MB against
# +451 MB, slope 9.00 against 6.99, two extra resident copies, unattributed
# (checks 12 and 13). "No user-visible regression" is true of time and false in
# general.
#
# (shape: arguments, ceiling_ms, python_ms_historical)
ABSOLUTE_TIME_GATES = {
    "help": (["search", "--help"], 20, 199),
    "broad literal miss, id-only": (["search", "zqxjvwmkbphfgd", "-ll"], 325, 464),
    "broad list, absolute date": (
        ["search", ".", "-ma", "2026-08-01", "-l", "--no-paging"], 1240, 2410,
    ),
    "colored matches": (
        ["search", "the", "--color", "always", "--no-paging", "--no-metadata"], 2930, 21539,
    ),
    "selective literal, id-only": (["search", "needle", "-ll"], 1235, 2080),
    "broad regex miss, id-only": (["search", "zq[xj]{2}vwmk", "-ll"], 2065, 3782),
}


def verify_ceilings_discriminate() -> None:
    """**Every ceiling must be below the Python figure for its shape.**

    Not in `g5-runner`'s spec; added on `search-firstmate`'s ruling because it
    closes a risk that returning to absolutes reintroduces.

    **A ceiling above the reference discriminates nothing** - both routes pass it,
    so the row proves the port is not slower than a budget no one could exceed.
    That is the exact hole ratio gates were adopted to close, and it walks back
    the moment absolutes return.

    **It nearly shipped.** The first derivation put `broad literal miss` at
    **980 ms against Python's 464 ms**, driven by a single contended run of 490 ms
    against a 260 ms median. `g5-runner` caught it by hand. **The next person
    widening a row after a flaky night will not**, and the
    widen-with-a-recorded-measurement rule does not stop a *correctly measured*
    widening that happens to cross the reference.

    The python column is already in the table as evidence, **so this assertion is
    free - it converts a discipline into a mechanism.**

    ⚠ **It used to be described as *restoring `--falsify`'s meaning*. `--falsify` was
    retired on 2026-09-02 with the route it consumed, so this is no longer a
    companion to that arm — it is the whole of it.** The property is asserted here,
    before anything is measured, rather than demonstrated afterwards against a
    reference that no longer exists.
    """
    indiscriminate = [
        f"  {name}: ceiling {ceiling}ms is not below Python's {python}ms"
        for name, (_, ceiling, python) in ABSOLUTE_TIME_GATES.items()
        if ceiling >= python
    ]
    if indiscriminate:
        raise SystemExit(
            "REFUSING: a ceiling at or above the route it replaces proves nothing.\n"
            + "\n".join(indiscriminate)
            + "\nBoth routes would pass that row. Re-derive it; do not widen it."
        )


MEMORY_GATES = {
    "selective literal, id-only": (["search", "needle", "-ll"], 700),
    "broad list, absolute date": (["search", ".", "-ma", "2026-08-01", "-l", "--no-paging"], 900),
    "colored matches": (["search", "the", "--color", "always", "--no-paging", "--no-metadata"], 900),
}

# **`MEMORY_PARITY_TOLERANCE` was deleted with the comparison it parameterised.** A
# threshold with no consumer is a number a reader will try to interpret.
ABSENT_LITERAL = ["search", "zqxjvwmkbphfgd", "-ll"]
ARMS = {"agent-bearing": ("large", "small"), "control (claude)": ("claude-large", "claude-small")}


def environment_for(home: Path) -> dict[str, str]:
    return os.environ | {"HOME": str(home), "NO_COLOR": "1", "COLUMNS": "96"}


def verify_corpus() -> None:
    """Refuse to measure against a corpus that is not the one the budgets came from."""
    manifest = json.loads((CORPUS / "MANIFEST.json").read_text())
    identity = hashlib.sha256(
        "\n".join(
            f"{entry['path']} {entry['bytes']} {entry['sha256']}" for entry in manifest["entries"]
        ).encode()
    ).hexdigest()
    if identity != CORPUS_IDENTITY:
        raise SystemExit(
            f"corpus identity mismatch.\n  expected {CORPUS_IDENTITY}\n  found    {identity}\n"
            "The budgets came from a different corpus; re-baseline before trusting them."
        )
    print(f"corpus  {manifest['files']} files, {manifest['bytes']:,} bytes, identity verified")
    print(f"oracle  {oracle_stamp()}\n")


def verify_native_subject(path: str) -> None:
    """Refuse a subject that delegates to the Python route. Never fall back.

    **The whole point of a ratio gate is the numerator.** `.venv/bin/ch` is a
    launcher that `exec`s a `ch-legacy` sibling, so pointing these gates at it
    measures Python against Python - about 1.0 against ceilings near 0.1, and six
    rows red for a reason that has nothing to do with the port. `target/release/ch`
    is the shipped artifact; check 14 has it byte-identical to the `ch` in the
    wheel.

    **Linkage cannot tell them apart, and that was measured rather than assumed.**
    Both binaries carry zero undefined `Py_` symbols and three dylibs - the
    delegating launcher holds no interpreter either, because it `exec`s. So
    `nm`/`otool`, and check 1's entire no-PyO3 test, pass on the binary that
    measures Python.

    **The only discriminator is behavioural**, and it is check 10's shape: copy the
    candidate alone into an empty directory with no `ch-legacy` sibling, strip
    `PATH`, run one search. A native binary exits 0 with output; a delegating one
    exits 1 with "Cannot start the private ch legacy entry". Two processes, and
    decisive.

    **The probe query must MATCH.** The first version of this guard used the
    absent literal the gates measure, and refused the native binary: a successful
    `search zqxjvwmkbphfgd -ll` finds nothing, so it exits 1 with no output -
    byte-for-byte the verdict a delegating binary gives, for the opposite reason.
    `search . -ll` matches every session in the corpus, so exit 0 with output means
    the binary served the search itself.

    **It refuses rather than warning.** A fallback to the launcher makes the gate
    pass by measuring the wrong route, which is the same defect this repo already
    carries on its record - "the contract suite binds the wrong installed ch
    binary" - wearing a stopwatch instead. And a tool that printed a warning was
    ignored for hours on this desk; one that refused was obeyed in seconds.
    """
    candidate = Path(path)
    if not candidate.is_file():
        raise SystemExit(f"subject is not a file: {path}")
    with tempfile.TemporaryDirectory(prefix="perf-gate-subject-") as isolated:
        alone = Path(isolated) / candidate.name
        shutil.copy2(candidate, alone)
        alone.chmod(0o755)
        probe = subprocess.run(
            [str(alone), "search", ".", "-ll"],
            capture_output=True,
            check=False,
            env=environment_for(CORPUS) | {"PATH": ""},
        )
    if probe.returncode != 0 or not probe.stdout:
        raise SystemExit(
            f"REFUSING: {path} does not serve a search on its own.\n"
            f"  exit {probe.returncode}, {len(probe.stdout)} bytes of stdout\n"
            f"  stderr: {probe.stderr.decode(errors='replace')[:200]!r}\n"
            "It delegates to the Python route, so every ratio below would measure\n"
            "Python against Python. Point these gates at `target/release/ch`."
        )


def verify_subject_freshness(path: str) -> None:
    """Reject a stale or foreign subject, **by importing the existing guard**.

    `_reject_foreign_launcher` is a tree-relative positive proof: for every probe
    the binary must carry it if and only if the working tree does, so a stale
    artifact fails for what it lacks and a foreign one for what it carries.

    **Imported, never copied. A second, drifted copy of exactly this function
    caused 21 errors on the morning of 2026-09-01**, and a third copy would be the
    same fault queued up.

    ⚠ **THIS DOES NOT PROVE THE BINARY IS CURRENT, and the sentence above is only
    true under a precondition it does not name.** It is a **probe-string agreement
    test**. It proves the binary is neither foreign nor from a different feature
    set. **A change that touches no probe string is invisible to it**, so "a stale
    artifact fails for what it lacks" holds only for staleness that removed or
    added a probe.

    **Measured here, not relayed.** `target/release/ch` linked at 21:00:10 on
    2026-09-01; `rust/search_output.rs` was edited at 21:01:19 and
    `rust/terminal.rs` at 21:04:03 — both **after** the link — and this function
    **accepted that binary**. `g5-runner` reproduced it independently.

    **So check 11's subject can be stale while every guard is green**, and
    `verify_native_subject` above cannot see it either: a stale native binary still
    serves a search on its own.

    **That is a limit of the instrument, not a fault in it** — the same distinction
    as a loader trace being meaningful on one side and not the other. It is written
    here because otherwise someone finds it next month and reads it as a defect.

    **What actually closes it is build order, not a check**: rebuild, then measure,
    in that order and in one window. If a cheap positive proof of currency is ever
    wanted, it is a comparison of the binary's mtime against the newest `rust/**`
    mtime — deliberately not added here, because a mtime test fails for reasons
    that have nothing to do with content and this file refuses rather than warns.
    """
    _tests_on_path()
    from test_search_command_contract import _reject_foreign_launcher

    _reject_foreign_launcher(Path(path))


def route_identity(path: str) -> str:
    """Hash the whole route, not the launcher.

    Bracketing only the launcher protects a self-contained artifact and says
    nothing about a route made of a launcher, a sibling script, an interpreter
    and a site-packages tree. A run once reported "unchanged" while the Python
    route underneath it was being reinstalled, and recorded the resulting
    never-ran process as a PASS.
    """
    target = Path(path)
    if target.is_file():
        return hashlib.sha256(target.read_bytes()).hexdigest()[:16]
    digest = hashlib.sha256()
    for member in sorted(target.rglob("*")):
        if member.is_file() and not member.is_symlink():
            digest.update(str(member.relative_to(target)).encode())
            digest.update(hashlib.sha256(member.read_bytes()).digest())
    return digest.hexdigest()[:16]


def timed(binary: str, arguments: list[str], home: Path) -> float:
    start = time.perf_counter()
    subprocess.run([binary, *arguments], capture_output=True, check=False, env=environment_for(home))
    return (time.perf_counter() - start) * 1000


def peak_megabytes(binary: str, arguments: list[str], home: Path) -> float:
    """Peak RSS of exactly one child.

    `getrusage(RUSAGE_CHILDREN)` is a running maximum over every child this
    process has reaped, so it reports one identical figure for every shape.
    `os.wait4` returns the rusage of the child that just exited.
    """
    if not home.exists():
        raise SystemExit(f"probe arm missing: {home}")
    pid = os.fork()
    if pid == 0:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
        os.execve(binary, [binary, *arguments], environment_for(home))
        os._exit(127)
    _pid, status, usage = os.wait4(pid, 0)
    if os.waitstatus_to_exitcode(status) == 127:
        raise SystemExit(f"probe failed to exec {binary}")
    return usage.ru_maxrss / (1 << 20)


def median_time(binary: str, arguments: list[str], home: Path) -> float:
    timed(binary, arguments, home)
    return statistics.median(timed(binary, arguments, home) for _ in range(REPETITIONS))


# **Retained deliberately, and it can no longer run after the deletion.** It
# consumes two live routes, which is exactly the shape decision 6 says dies at
# cutover. It produced the recorded ratios in the block above - 0.033 / 0.552 /
# 0.397 / 0.108 / 0.435 / 0.433 - and those can never be retaken, so the function
# that took them stays beside them rather than being tidied away.
def interleaved_medians(
    subject: str, reference: str, arguments: list[str], home: Path
) -> tuple[float, float]:
    """Medians of both routes, strictly alternating so each pair sees one machine."""
    timed(subject, arguments, home)
    timed(reference, arguments, home)
    subject_times, reference_times = [], []
    for _ in range(REPETITIONS):
        subject_times.append(timed(subject, arguments, home))
        reference_times.append(timed(reference, arguments, home))
    return statistics.median(subject_times), statistics.median(reference_times)


# **Unreachable and KEPT, for the same reason as `interleaved_medians` above.** It
# produced the +576 MB / +451 MB figures cited in the TIME ONLY block, and those
# were taken while both routes existed. **It stays beside the numbers it produced.**
# ⚠ **Do not wire it back to a reference route** — `ch-legacy` cannot search, so a
# second arm would measure session resolution. **And do not read it as the successor
# to the memory question:** the oversized-line probe is retired as the primary
# instrument, and the named follow-up is per-session accumulation on the real corpus.
def memory_delta(binary: str, arm: str) -> float:
    large_dir, small_dir = ARMS[arm]
    large = max(peak_megabytes(binary, ABSENT_LITERAL, PROBE / large_dir) for _ in range(2))
    small = max(peak_megabytes(binary, ABSENT_LITERAL, PROBE / small_dir) for _ in range(2))
    return large - small


def run_gates(subject: str) -> int:
    """Every shape must pass. **`expect_failure` is gone with the reference arm.**"""
    failures = 0
    print(f"{'shape':32} {'measured':>10} {'gate':>11}  verdict")

    for name, (arguments, ceiling, python) in ABSOLUTE_TIME_GATES.items():
        measured = median_time(subject, arguments, CORPUS)
        ok = measured < ceiling
        failures += 0 if ok else 1
        print(
            f"{name:32} {measured:9.1f}ms {ceiling:8}ms  {'PASS' if ok else 'FAIL'}"
            f"   (python was {python}ms, historical evidence, not a denominator)"
        )

    print()
    for name, (arguments, budget) in MEMORY_GATES.items():
        measured = max(peak_megabytes(subject, arguments, CORPUS) for _ in range(2))
        ok = measured < budget
        failures += 0 if ok else 1
        print(f"{name:32} {measured:9.0f}MB {budget:8}MB  {'PASS' if ok else 'FAIL'}")

    print()
    print("GATE: every shape had to pass")
    if failures:
        print(f"  {failures} shape(s) did not behave as required")
    return failures


# ── ⚠ RETIRED 2026-09-02: both arms that consumed a reference route ──────────
#
# `run_memory_parity` and the `--falsify` arm are gone. **They compared the subject
# against `ch-legacy`, and `ch-legacy` can no longer search.** What it does with
# `search zqxjvwmkbphfgd -ll` now was measured rather than assumed:
#
#   .venv/bin/ch-legacy search zqxjvwmkbphfgd -ll
#     -> "Error: Ambiguous conversation/session identifier 'search' matches
#        multiple sessions", exit 0, **14.9 seconds**
#
# It resolves the word `search` as a session identifier and scans the whole pool.
# **So a reference arm measures session resolution, not a search route.**
#
# ⚠ **THE TWO ARMS FAILED IN OPPOSITE AND UNEQUALLY VISIBLE WAYS, and that is the
# finding.** The memory parity arm went RED — its control caught the invalid
# measurement, which is why nobody filed a 576-vs-65 MB regression. **The
# `--falsify` arm would have gone GREEN:** it requires every shape to exceed its
# ceiling against the reference, and a 14.9-second session resolution exceeds all
# six. ***A gate passing for a reason unrelated to what it measures is worse than
# one going red, because nothing draws anyone to it.***
#
# **Nothing was lost by removing `--falsify`.** `verify_ceilings_discriminate`
# already asserts the property it existed to catch — every ceiling below the
# recorded Python figure — and it does so BEFORE anything is measured. L354: a
# mechanism where there was a check.
#
# **What survives is native-only and still meaningful:** the six absolute time
# ceilings and the three `MEMORY_GATES` budgets, all on the digest-pinned corpus.
#
# ▶ **THE SUCCESSOR TO THE MEMORY PARITY QUESTION IS A NAMED FOLLOW-UP, not this
# file:** *scan-memory per-session accumulation.* On id-only scanning Python's peak
# was FLAT at 56 MB across sessions from 34.6 MB to 83.3 MB while the native
# route's grew with the session — so the extra memory is a per-session
# accumulation, not a constant overhead. **Streaming versus materialising is the
# obvious reading and has never been measured.** The oversized-line probe that
# these two arms used is retired as the primary instrument: it is a pathological
# shape nobody has, and it sent two checks after a mechanism the real corpus
# describes better.


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        raise SystemExit(__doc__)
    subject = sys.argv[1]
    if "--reference" in sys.argv or "--falsify" in sys.argv:
        raise SystemExit(
            "REFUSING: `--reference` and `--falsify` are retired. They compared the\n"
            "subject against `ch-legacy`, which can no longer search — it resolves the\n"
            "word `search` as a session identifier and takes 14.9 seconds to say so.\n"
            "`--falsify` would have PASSED on that, for a reason unrelated to search.\n"
            "The property it checked is asserted by `verify_ceilings_discriminate`\n"
            "before anything is measured. Run with the subject alone."
        )

    verify_corpus()
    verify_ceilings_discriminate()
    verify_native_subject(subject)
    verify_subject_freshness(subject)
    identity = route_identity(subject)
    print(f"route   {identity}  {subject}\n")

    unexpected = run_gates(subject)

    if route_identity(subject) != identity:
        raise SystemExit(f"VOID: {subject} changed mid-run; every number above is unusable")
    print("\nroute identity unchanged across the run")
    return unexpected


if __name__ == "__main__":
    raise SystemExit(main())
