#!/usr/bin/env python3
"""Grade a differential harness before trusting anything it reports.

A harness has two failure directions: reporting a difference that is not there,
and missing one that is. Implausible numbers catch neither reliably — a harness
bug producing a plausible number ships. So the instrument is tested the way the
code is: for every dimension it claims to observe, inject one minimal mutation
in exactly that dimension and require it to be seen.

Two things get graded, not one. The **capture** turns a subject into bytes. The
**comparator** — capture plus whatever normalization runs before the equality
check — is what actually decides parity. Grading only the capture certifies a
component while leaving the decision ungraded.

Blindness in the comparator is sometimes deliberate: a normalization that hides
a wall-clock age bucket is load-bearing until the clock seam lands. Those are
declared by name. Declared blindness passes; undeclared blindness fails. That
makes this a ratchet rather than a report — a normalization added quietly later
cannot pass, and a declaration that has outlived its cause is reported so it
gets deleted.

Scope, stated precisely because overclaiming here is the failure this tool
exists to prevent: it grades the dimensions where this project has already been
wrong. It is not a proof of general correctness, and no probe set can be.

    uv run python calibrate_harness.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

CANONICAL_RELATIVE = Path(
    "thoughts/2026-08-28-search-rust-rewrite/teammates/reviewer-profiler/calibrate_harness.py"
)


def load_by_path(path: Path, name: str = "calibrate_harness"):
    """Import a module from a file path, safely.

    The registration in `sys.modules` before `exec_module` is not optional:
    `dataclasses` resolves a class's own module through `sys.modules`, so a
    module loaded by path without it raises `AttributeError` on the first
    `@dataclass` it reaches. Use this rather than hand-rolling the three-line
    version, which works until the imported file grows a dataclass.
    """
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load a module from {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _repository_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def probe_set_digest(probes: dict[str, tuple[bytes, bytes]]) -> str:
    """Content digest over the probe set, so a stale copy is detectable."""
    joined = b"\n".join(
        name.encode() + b"\x00" + baseline + b"\x00" + mutated
        for name, (baseline, mutated) in sorted(probes.items())
    )
    return hashlib.sha256(joined).hexdigest()[:16]

Capture = Callable[[bytes], object]
Comparator = Callable[[object, object], bool]

AGE_BUCKET_COLOURS = (b"135;140;146", b"107;112;118", b"169;174;180", b"86;91;97")

# Each probe is a pair differing in exactly one observable dimension, so a
# harness that cannot separate the pair is blind in that dimension and nothing
# else. Colour is split into four probes rather than one: a comparator that
# legitimately normalizes age buckets must not be reported as colour-blind.
PROBES: dict[str, tuple[bytes, bytes]] = {
    "visible text": (b"alpha\n", b"alpba\n"),
    "lone carriage return": (b"a\nb\n", b"a\rb\n"),
    "CRLF versus LF": (b"a\nb\n", b"a\r\nb\n"),
    "trailing newline": (b"alpha\n", b"alpha"),
    "trailing whitespace": (b"alpha\n", b"alpha \n"),
    "NUL byte": (b"a\x00b", b"ab"),
    "non-ASCII payload": ("café\n".encode(), "cafe\n".encode()),
    "NFC versus NFD": (
        unicodedata.normalize("NFC", "café résumé\n").encode(),
        unicodedata.normalize("NFD", "café résumé\n").encode(),
    ),
    "zero-width space": ("ab\n".encode(), "a​b\n".encode()),
    "confusable letter": ("data\n".encode(), "datа\n".encode()),
    "SGR arbitrary colour": (b"\x1b[38;2;1;2;3mx\x1b[0m", b"\x1b[38;2;4;5;6mx\x1b[0m"),
    "SGR palette versus truecolor": (b"\x1b[38;5;79mx\x1b[0m", b"\x1b[38;2;92;200;168mx\x1b[0m"),
    "SGR age colour versus non-age grey": (
        b"\x1b[38;2;135;140;146mx\x1b[0m",
        b"\x1b[38;2;120;120;120mx\x1b[0m",
    ),
    "SGR between two age buckets": (
        b"\x1b[38;2;135;140;146mx\x1b[0m",
        b"\x1b[38;2;107;112;118mx\x1b[0m",
    ),
}


def freshness() -> tuple[str, str, str | None]:
    """Compare this file's probe set against the canonical one on disk.

    A copy of this tool goes stale silently: it grades against the probe set it
    was copied with, reports CALIBRATED, and means something weaker than the
    word implies. The probe set grew from 8 dimensions to 14 in one afternoon,
    so this is not hypothetical.

    Returns (verdict, own digest, canonical digest).
    """
    own = probe_set_digest(PROBES)
    here = Path(__file__).resolve()
    root = _repository_root(here)
    if root is None:
        return ("unverifiable (no repository root found)", own, None)
    canonical = (root / CANONICAL_RELATIVE).resolve()
    if canonical == here:
        return ("canonical", own, own)
    if not canonical.exists():
        return ("unverifiable (canonical file not found)", own, None)
    try:
        theirs = probe_set_digest(load_by_path(canonical, "_calibrate_canonical").PROBES)
    except Exception as error:  # a broken canonical must not read as fresh
        return (f"unverifiable ({type(error).__name__})", own, None)
    return ("current" if own == theirs else "STALE", own, theirs)


@dataclass
class Report:
    capture_blind: list[str] = field(default_factory=list)
    comparator_blind: list[str] = field(default_factory=list)
    declared: frozenset[str] = frozenset()
    freshness: str = "unchecked"

    @property
    def undeclared(self) -> list[str]:
        return [name for name in self.comparator_blind if name not in self.declared]

    @property
    def stale_declarations(self) -> list[str]:
        return sorted(self.declared - set(self.comparator_blind))

    @property
    def passed(self) -> bool:
        return (
            not self.capture_blind
            and not self.undeclared
            and not self.freshness.startswith(("STALE", "unverifiable"))
        )

    # A Report stands in for the plain list this returned before the comparator
    # grading landed, so `if report:`, `len(report)` and iteration keep working
    # for callers written against the older shape.
    def _blind(self) -> list[str]:
        return self.capture_blind + self.undeclared

    def __bool__(self) -> bool:
        return bool(self._blind())

    def __len__(self) -> int:
        return len(self._blind())

    def __iter__(self):
        return iter(self._blind())


def _blind_dimensions(
    capture: Capture,
    equal: Comparator,
    probes: Iterable[str],
) -> list[str]:
    """Dimensions this harness cannot observe.

    The equal-payload branch below is **load-bearing beyond its stated purpose**.
    A probe whose two payloads are identical takes it and is reported blind, which
    is what lets this calibrator distinguish *I observed the mutation* from *the
    mutation did nothing* — the distinction all fourteen real probes rest on. That
    is accidental rather than designed: a smarter blindness check could satisfy
    every existing probe and quietly stop reporting a null probe, and nothing here
    would fail. If this function is refactored, keep a null probe in the set.
    """
    blind = []
    for dimension in probes:
        baseline, mutated = PROBES[dimension]
        # Null control first. An unstable harness would pass every sensitivity
        # probe below for the wrong reason.
        if not equal(capture(baseline), capture(baseline)):
            blind.append(f"{dimension} (unstable: identical input compared unequal)")
            continue
        if equal(capture(baseline), capture(mutated)):
            blind.append(dimension)
    return blind


def calibrate(
    capture: Capture | str,
    legacy_capture: Capture | None = None,
    *,
    comparator: Comparator | None = None,
    declared: Iterable[str] = (),
) -> Report:
    """Grade a capture, and the comparator built on it, against every probe.

    An earlier shape of this function took a display name first and returned a
    plain list. Callers written against it keep working: the name is ignored and
    the `Report` behaves like that list.
    """
    if legacy_capture is not None:
        capture = legacy_capture
    if isinstance(capture, str):
        raise TypeError("calibrate() needs a capture callable, not a name alone")

    identity: Comparator = lambda left, right: left == right
    verdict, _own, _canonical = freshness()
    report = Report(declared=frozenset(declared), freshness=verdict)
    report.capture_blind = _blind_dimensions(capture, identity, PROBES)
    if comparator is not None:
        report.comparator_blind = _blind_dimensions(capture, comparator, PROBES)
    return report


def render(name: str, report: Report) -> None:
    verdict = "CALIBRATED" if report.passed else "FAILED"
    print(f"{name:34} {verdict}   [{len(PROBES)} dimensions, probe set {probe_set_digest(PROBES)}]")
    if report.freshness not in ("canonical", "current"):
        print(f"   PROBE SET {report.freshness}: regrade against the canonical tool")
    for dimension in report.capture_blind:
        print(f"   capture cannot see      : {dimension}")
    for dimension in report.undeclared:
        print(f"   comparator hides        : {dimension}  [UNDECLARED]")
    for dimension in sorted(set(report.comparator_blind) & report.declared):
        print(f"   comparator hides        : {dimension}  (declared)")
    for dimension in report.stale_declarations:
        print(f"   declaration now unneeded: {dimension}  (delete it)")


# --------------------------------------------------------------------- subjects

def _echo(payload: bytes, *, text: bool) -> object:
    program = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"
    if text:
        completed = subprocess.run(
            [sys.executable, "-c", program],
            input=payload.decode("utf-8", "surrogateescape"),
            capture_output=True,
            text=True,
        )
        return completed.stdout
    return subprocess.run(
        [sys.executable, "-c", program], input=payload, capture_output=True
    ).stdout


def capture_bytes(payload: bytes) -> object:
    """Capture raw bytes. The correct instrument."""
    return _echo(payload, text=False)


def capture_text(payload: bytes) -> object:
    """Capture with `text=True`, which implies universal newlines."""
    return _echo(payload, text=True)


def age_normalizing_comparator(left: object, right: object) -> bool:
    """Fold the four wall-clock age-bucket colours, as a real byte lock must."""
    import re

    pattern = rb"\x1b\[38;2;(?:" + b"|".join(AGE_BUCKET_COLOURS) + rb")m"
    fold = lambda value: re.sub(pattern, b"\x1b[38;2;{AGE}m", value)
    return fold(left) == fold(right)  # type: ignore[arg-type]


def main() -> int:
    failures = 0

    report = calibrate(capture_bytes)
    render("bytes capture", report)
    failures += 0 if report.passed else 1

    report = calibrate(capture_text)
    render("text=True capture", report)
    failures += 1 if report.passed else 0  # this one is expected to fail

    report = calibrate(
        capture_bytes,
        comparator=age_normalizing_comparator,
        declared={"SGR between two age buckets"},
    )
    render("bytes + age-folding comparator", report)
    failures += 0 if report.passed else 1

    report = calibrate(capture_bytes, comparator=age_normalizing_comparator)
    render("same comparator, undeclared", report)
    failures += 1 if report.passed else 0  # expected to fail: the ratchet

    print()
    print(
        "Graded on the dimensions where this project has already been wrong.\n"
        "Not a proof of general correctness; no probe set can be."
    )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
