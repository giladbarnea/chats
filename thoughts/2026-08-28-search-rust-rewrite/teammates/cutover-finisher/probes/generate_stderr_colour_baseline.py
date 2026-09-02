#!/usr/bin/env -S uv run
"""Freeze what `ch-legacy` writes to a **tty stderr**, before `ch-legacy` goes away.

**This capture is the irreversible half and it is not contingent on the fix.** Legacy's
coloured stderr can only be recorded while the Python route lives, and the deletion slice
is downstream. Even a decision to ship the divergence would still need this taken today.

**Why a pty on stderr and a pipe on stdout.** The `--color` choice reaches stdout's
console and none of the three stderr ones — `print_error`, `print_warning` and
`print_hint` each build a bare `Console(stderr=True)` — so their colour is decided solely
by whether stderr is a tty. **Every coloured gate on this mission puts its pty on
stdout**, which is why this surface has never been recorded.

The matrix crosses four `--color` settings with five terminal tiers and two widths,
because the tier decides how a truecolor theme colour is downgraded and the width decides
where the message folds.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import sys
import termios
from pathlib import Path

#: Walked rather than counted. A hard-coded `parents[n]` was off by one on the first
#: run and the capture refused instead of recording nothing, which is the only reason
#: that mistake cost a minute rather than a fixture full of empty bytes.
def _project_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".venv" / "bin" / "ch-legacy").is_file():
            return candidate
    raise SystemExit(
        "No ancestor of this probe owns `.venv/bin/ch-legacy`. **This baseline can only "
        "be captured while the Python route lives**, which is the whole reason it exists."
    )


PROJECT_ROOT = _project_root()
LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "data" / "stderr-colour"

#: Every stderr-writing shape a public `ch search` reaches.
SHAPES = [
    ("hint-no-results", ["zzzz-no-such-term"]),
    ("hint-no-results-filtered", ["zzzz-no-such-term", "-d", "/nowhere"]),
    ("warning-role-contradiction", ["needle", "--only-user", "--only-assistant"]),
    ("warning-posix-class", ["[[:alpha:]]", "-ll"]),
    ("error-invalid-date", ["needle", "-ma", "notadate"]),
    ("error-grammar", ["needle AND", "-ll"]),
]
COLOURS = [None, "never", "auto", "always"]
#: `(label, environment overrides)`. The tier decides how a truecolor theme colour is
#: downgraded, and `NO_COLOR` and a dumb terminal are the two ways colour disappears.
TIERS = [
    ("truecolor", {"TERM": "xterm-256color", "COLORTERM": "truecolor"}),
    ("eight-bit", {"TERM": "xterm-256color"}),
    ("standard", {"TERM": "xterm"}),
    ("no-colour", {"TERM": "xterm-256color", "NO_COLOR": "1"}),
    ("dumb", {"TERM": "dumb"}),
]
WIDTHS = (40, 96)


def build_pool(home: Path) -> None:
    directory = home / ".claude" / "projects" / "stderrcolour"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "aaaaaaaa-0010-4000-8000-000000000010.jsonl").write_text(
        json.dumps({
            "type": "user", "uuid": "u0", "timestamp": "2026-08-20T13:00:00.000Z",
            "cwd": "/tmp/stderrcolour",
            "message": {"role": "user", "content": "a needle in the only session"},
        }) + "\n"
    )


def run(arguments: list[str], home: Path, overrides: dict, columns: int) -> tuple[bytes, int]:
    primary, secondary = pty.openpty()
    fcntl.ioctl(secondary, termios.TIOCSWINSZ, struct.pack("HHHH", 40, columns, 0, 0))
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"COLUMNS", "NO_COLOR", "COLORTERM", "FORCE_COLOR", "CLICOLOR",
                       "CLICOLOR_FORCE", "TTY_COMPATIBLE"}
    }
    environment["HOME"] = str(home)
    environment["COLUMNS"] = str(columns)
    environment["TZ"] = "Asia/Jerusalem"
    environment.update(overrides)
    process = subprocess.Popen(
        [str(LEGACY), "search", *arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=secondary,
        env=environment, close_fds=True,
    )
    os.close(secondary)
    chunks: list[bytes] = []
    while True:
        ready, _, _ = select.select([primary], [], [], 60.0)
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
    return b"".join(chunks), process.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(FIXTURE_ROOT / "legacy-stderr-baseline.json"))
    options = parser.parse_args()

    assert LEGACY.is_file(), (
        f"{LEGACY} is gone. **This baseline can only be captured while the Python route "
        "lives**, which is the whole reason it exists."
    )
    home = FIXTURE_ROOT / "home"
    build_pool(home)

    cases = []
    coloured = 0
    for shape_name, arguments in SHAPES:
        for colour in COLOURS:
            for tier_name, overrides in TIERS:
                for width in WIDTHS:
                    argv = list(arguments) + ([] if colour is None else ["--color", colour])
                    stderr, status = run(argv, home, overrides, width)
                    if b"\x1b[" in stderr:
                        coloured += 1
                    cases.append({
                        "id": f"{shape_name}/{colour or 'bare'}/{tier_name}/{width}",
                        "arguments": argv,
                        "environment": overrides,
                        "columns": width,
                        "exit_status": status,
                        # Latin-1 keeps every byte, including the SGR introducers, and
                        # round-trips exactly. `errors="replace"` would not.
                        "stderr": stderr.decode("latin-1"),
                    })
    payload = {
        "captured": "2026-09-01",
        "oracle": str(LEGACY),
        "why": (
            "Legacy's coloured stderr can only be recorded while ch-legacy lives. The "
            "colour choice reaches stdout's console and none of the three stderr ones, "
            "so their colour follows the tty alone -- including under `--color never`. "
            "That is preserve-because-wrong item 10."
        ),
        "cases": cases,
    }
    Path(options.out).write_text(json.dumps(payload, ensure_ascii=False))
    print(f"{len(cases)} cases, {coloured} carrying colour -> {options.out}")
    if coloured == 0:
        print("⚠ VACUOUS: nothing in this capture is coloured, so it records the wrong thing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
