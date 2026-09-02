#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.14.*"
# dependencies = []
# ///
"""Drive the generated adversarial corpus through a real pty and observe it.

Two things make this harness different from a plain subprocess runner:

1. **It runs under a pty with a set window size.** Every existing test pins
   `COLUMNS`, so terminal-width resolution is invisible to all of them. Under a
   pty the product resolves width for real, which is the path `main` changed on
   2026-08-28 and no test reaches.

2. **It refuses to report anything until it has been calibrated.** A harness
   that cannot see a difference reports parity over that dimension whether or
   not parity holds. Calibration is `reviewer-profiler`'s tool, not a local
   reimplementation, and it is a gate rather than advice: `main()` exits
   non-zero and runs nothing if any dimension comes back blind.

**ONLCR warning.** A pty translates `\\n` to `\\r\\n` on the way out. Comparing
pty-captured bytes against pipe-captured bytes therefore diverges on every line
ending, for reasons that have nothing to do with the product. Both sides of any
comparison must come from the same kind of channel. `channel_kind()` labels
captures so a mismatch is caught rather than debugged.

Usage:
    uv run fuzz_harness.py calibrate          # gate: prove the instrument sees
    uv run fuzz_harness.py observe <home>     # run the corpus, report invariants
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import pty
import re
import select
import struct
import subprocess
import sys
import termios
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path("/Users/giladbarnea/dev/chats")
LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"
CALIBRATOR = (
    PROJECT_ROOT
    / "thoughts/2026-08-28-search-rust-rewrite/teammates/reviewer-profiler"
    / "calibrate_harness.py"
)

CHANNEL_PTY = "pty"

# The public output modes, with the invariants that actually apply to each.
# `wraps` is not a detail: raw mode emits stored content verbatim, so asserting
# a wrap rule there would manufacture a finding on any session whose stored line
# is longer than the terminal — which this corpus deliberately contains.
# Colour tiers. Every run before 2026-08-28 held these fixed at truecolor, so
# three of the four rendering states below were never exercised — the L22 failure
# applied to this harness. `expected_width` is not decoration: at TERM=dumb the
# product legitimately ignores the terminal size and uses Rich's default 80, so a
# pty-width assertion there measures the harness's assumption, not the product.
COLOUR_TIERS: list[dict] = [
    {"id": "truecolor", "env": {"TERM": "xterm-256color", "COLORTERM": "truecolor"},
     "expected_width": "pty"},
    {"id": "256-colour", "env": {"TERM": "xterm-256color"}, "expected_width": "pty"},
    {"id": "no-colour", "env": {"TERM": "xterm-256color", "COLORTERM": "truecolor",
                                "NO_COLOR": "1"}, "expected_width": "pty"},
    {"id": "dumb-terminal", "env": {"TERM": "dumb"}, "expected_width": 80},
]

OUTPUT_MODES: list[dict] = [
    {
        "id": "matches",
        "arguments": ["--color", "always", "--no-paging", "--no-metadata"],
        "wraps": True,
    },
    {
        "id": "list",
        "arguments": ["-l", "--color", "always", "--no-paging"],
        "wraps": True,
    },
    {
        "id": "full",
        "arguments": ["-f", "--color", "always", "--no-paging", "--no-metadata"],
        "wraps": True,
    },
    {
        "id": "only-id",
        "arguments": ["-ll", "--color", "always", "--no-paging"],
        "wraps": True,
    },
    {
        "id": "raw",
        "arguments": ["-r", "--no-paging", "--no-metadata"],
        "wraps": False,
    },
]


def run_under_pty(
    argv: list[str],
    *,
    columns: int,
    rows: int = 40,
    home: Path | None = None,
    extra_environment: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> tuple[bytes, int]:
    """Run `argv` attached to a pty of the given size; return bytes and status.

    stdout and stderr share the pty, as they would in a terminal, so this
    measures what a user sees rather than what a redirect captures.
    """
    primary, secondary = pty.openpty()
    fcntl.ioctl(
        secondary, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0)
    )
    environment = os.environ.copy()
    environment.update({
        "TZ": "Asia/Jerusalem",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "LINES": str(rows),
    })
    if home is not None:
        environment["HOME"] = str(home)
    # Let the terminal decide. Setting COLUMNS here would defeat the point.
    environment.pop("COLUMNS", None)
    environment.pop("NO_COLOR", None)
    if extra_environment:
        environment.update(extra_environment)

    process = subprocess.Popen(
        argv,
        stdin=secondary,
        stdout=secondary,
        stderr=secondary,
        cwd=PROJECT_ROOT,
        env=environment,
        close_fds=True,
    )
    os.close(secondary)
    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], timeout)
        if not ready:
            break
        try:
            data = os.read(primary, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    os.close(primary)
    process.wait(timeout=timeout)
    return b"".join(chunks), process.returncode


def capture_through_pty(payload: bytes) -> tuple[str, bytes]:
    """Echo `payload` through a pty and return (channel, bytes).

    This is the calibration adapter: it exercises the same capture path the
    corpus runs use, so grading it grades the real instrument rather than an
    idealized one. The channel label travels with the bytes so a pty capture
    can never be silently compared against a pipe capture.
    """
    # stdin comes through a pipe, not the pty: feeding it through the pty would
    # echo the payload straight back and grade the terminal, not the capture.
    primary, secondary = pty.openpty()
    fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 137, 0, 0))
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
        ],
        stdin=subprocess.PIPE,
        stdout=secondary,
        stderr=secondary,
        close_fds=True,
    )
    os.close(secondary)
    assert process.stdin is not None
    process.stdin.write(payload)
    process.stdin.close()
    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], 30.0)
        if not ready:
            break
        try:
            data = os.read(primary, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    os.close(primary)
    process.wait(timeout=30)
    return (CHANNEL_PTY, b"".join(chunks))


def load_calibrator():
    """Import `reviewer-profiler`'s calibration tool rather than reimplementing it."""
    if not CALIBRATOR.exists():
        raise SystemExit(
            f"calibration tool missing at {CALIBRATOR}. "
            "No harness result may be quoted until calibration passes."
        )
    spec = importlib.util.spec_from_file_location("calibrate_harness", CALIBRATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before executing: `@dataclass` resolves its own module through
    # `sys.modules`, so a module loaded this way must be visible there first.
    sys.modules["calibrate_harness"] = module
    spec.loader.exec_module(module)
    return module


def calibrate() -> int:
    """Gate. Prove this harness's real capture path sees every graded dimension."""
    calibrator = load_calibrator()
    blind = calibrator.calibrate("pty byte capture", capture_through_pty)
    if blind:
        print("BLIND in", len(blind))
        for dimension in blind:
            print(f"  - cannot see: {dimension}")
        print(
            "\nRefusing to observe. Every result over a blind dimension is vacuous."
        )
        return 1
    print(f"CALIBRATED  pty byte capture — all {len(calibrator.PROBES)} dimensions visible")
    print(
        "Note: width and clock are not gradeable by byte payload and are not "
        "covered here; they need a live subject under a pty."
    )
    return 0


def calibrate_width() -> int:
    """Grade the width axis, which the byte-payload calibration cannot reach.

    Two directions, because a width instrument fails in two ways and only one
    of them is obvious:

    * **Sensitivity.** A line planted wider than the terminal must be seen. An
      instrument that misses it reports "fits" over a corpus that does not.
    * **Specificity.** A line built from zero-width and wide characters that
      exactly fills the terminal must NOT be flagged. This direction is the one
      that actually bit: counting U+200B as one column invented a consistent
      off-by-one at every width, which reads exactly like a real product bug.

    A byte-payload probe cannot grade either, because both need a rendered
    line measured in columns rather than a payload compared for equality.
    """
    checks: list[tuple[str, bool, str]] = []

    planted_overflow = "x" * 100
    checks.append((
        "sees a line wider than the terminal",
        display_width(planted_overflow) > 72,
        f"{display_width(planted_overflow)} columns against 72",
    ))

    zero_width_filled = "a" * 72 + "​" * 10
    checks.append((
        "does not flag zero-width padding as overflow",
        display_width(zero_width_filled) == 72,
        f"measured {display_width(zero_width_filled)}, expected 72",
    ))

    wide_filled = "你" * 36  # 36 double-width characters exactly fill 72
    checks.append((
        "counts double-width characters as two columns",
        display_width(wide_filled) == 72,
        f"measured {display_width(wide_filled)}, expected 72",
    ))

    combining = "é" * 10  # e + combining acute renders as one column each
    checks.append((
        "counts combining marks as zero columns",
        display_width(combining) == 10,
        f"measured {display_width(combining)}, expected 10",
    ))

    # Live subject: the product must actually render to the width it is given.
    for columns in (52, 137):
        output, _ = run_under_pty(
            [str(LEGACY), "search", "--help"], columns=columns
        )
        widest = max((display_width(line) for line in visible_lines(output)), default=0)
        checks.append((
            f"live render at {columns} columns stays within {columns}",
            widest <= columns,
            f"widest line {widest}",
        ))

    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name:52} ({detail})")
    return 0 if all(passed for _, passed, _ in checks) else 1


def display_width(text: str) -> int:
    """Terminal columns occupied by `text`.

    Byte length is the wrong measure: a rule filling 72 columns of box drawing
    is 216 bytes, and reporting that as a 216-column line makes a correct
    render look broken.
    """
    columns = 0
    for character in text:
        category = unicodedata.category(character)
        # Zero-width: combining marks (Mn, Me) and format characters (Cf, which
        # covers U+200B ZERO WIDTH SPACE and the bidi controls). Counting Cf as
        # one column produced a clean, consistent, entirely false off-by-one at
        # every width — the most convincing kind of wrong.
        if category in {"Mn", "Me", "Cf"}:
            continue
        columns += 2 if unicodedata.east_asian_width(character) in "WF" else 1
    return columns


def visible_lines(output: bytes) -> list[str]:
    plain = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", output)
    text = plain.decode("utf-8", errors="replace")
    return [line.rstrip("\r") for line in text.split("\n")]


def observe(home: Path, cases_path: Path) -> int:
    """Run every generated session at every width and check width invariants.

    These invariants hold for the Python oracle today, so a violation is a real
    finding rather than a comparison against an absent native route. They are
    the properties that a length-changing fold or a wide character breaks.
    """
    manifest = json.loads(cases_path.read_text(encoding="utf-8"))
    needle = manifest["needle"]
    findings: list[dict] = []
    runs = 0

    for tier in COLOUR_TIERS:
      for mode in OUTPUT_MODES:
        for width in manifest["widths"]:
            arguments = [str(LEGACY), "search", needle, *mode["arguments"]]
            output, status = run_under_pty(
                arguments, columns=width, home=home, extra_environment=tier["env"]
            )
            runs += 1
            limit = width if tier["expected_width"] == "pty" else tier["expected_width"]
            if status != 0:
                findings.append({
                    "tier": tier["id"], "mode": mode["id"], "width": width,
                    "kind": "non-zero exit", "detail": status,
                })
            if b"\xef\xbf\xbd" in output:
                findings.append({
                    "tier": tier["id"], "mode": mode["id"], "width": width,
                    "kind": "replacement character in output",
                    "detail": "output is not valid UTF-8",
                })
            if not mode["wraps"]:
                continue
            overflow = [
                (index, display_width(line))
                for index, line in enumerate(visible_lines(output))
                if display_width(line) > limit
            ]
            if overflow:
                findings.append({
                    "tier": tier["id"], "mode": mode["id"], "width": width,
                    "kind": "line exceeds resolved width",
                    "detail": overflow[:5],
                })

    print(
        f"runs: {runs}   tiers: {len(COLOUR_TIERS)}   modes: {len(OUTPUT_MODES)}   "
        f"widths: {len(manifest['widths'])}   sessions: {len(manifest['cases'])}"
    )
    if not findings:
        print("no invariant violations")
        return 0
    print(f"findings: {len(findings)}")
    for finding in findings:
        print(f"  {finding.get('tier','?'):14} {finding['mode']:8} w{finding['width']:<4} {finding['kind']}: {finding['detail']}")
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    command = sys.argv[1]
    if command == "calibrate":
        status = calibrate()
        print()
        return max(status, calibrate_width())
    if command == "observe":
        if len(sys.argv) != 3:
            print("usage: fuzz_harness.py observe <destination>")
            return 2
        # Gate: never observe with an ungraded instrument, on either axis.
        if calibrate() != 0 or calibrate_width() != 0:
            return 1
        destination = Path(sys.argv[2])
        return observe(destination / "home", destination / "CASES.json")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
