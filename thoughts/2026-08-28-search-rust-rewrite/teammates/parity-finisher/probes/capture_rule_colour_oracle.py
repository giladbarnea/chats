#!/usr/bin/env python3
"""Record what `ch-legacy` writes to stdout across every colour environment.

**Capture first, fix second, gate third.** This recording is the irreversible
half: it comes from `ch-legacy`, and the deletion slice removes `ch-legacy`. Once
it is gone this table cannot be re-derived at any cost.

**What it records, and why the plain route is the interesting one.** Measured:
`FORCE_COLOR` and `TTY_COMPATIBLE` do **not** flip `flags.color`. `cli.py:343`
computes it from a plain `sys.stdout.isatty()`, so piped output always takes the
plain `console.rule()` route. What the variables reach is the *console*, which
Rich then decides is a terminal — so the rule's filler and title gain colour while
every other byte stays exactly as it was.

**Refusals, because a recording that comes out empty looks identical to a corpus.**
This is the failure the first version of the sibling probe would have produced: it
cleared only the two variables under test, so the parent shell's `COLORTERM`
leaked into every tier and the three colour depths recorded identical bytes.

1. The control must contain **zero** escapes.
2. At least one tier must contain escapes.
3. **Truecolor, eight-bit and standard must differ from one another.** This is the
   one that catches an ambient leak, because a leak makes them agree.
4. `TERM=dumb` must contain no escapes.
5. Every tier's child environment must carry only the variables that tier sets.

Any failure refuses to write.

    uv run -p python3 python .../probes/capture_rule_colour_oracle.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LEGACY = Path(".venv/bin/ch-legacy").resolve()
TARGET = Path(__file__).resolve().parent / "rule-colour-oracle.json"
ESCAPE = re.compile(rb"\x1b\[[0-9;:]*[A-Za-z]")

# Every variable Rich consults when deciding terminal-ness and colour depth.
AMBIENT = ("FORCE_COLOR", "TTY_COMPATIBLE", "COLORTERM", "NO_COLOR", "TERM")

ENVIRONMENTS = {
    "control": {},
    "truecolor": {"FORCE_COLOR": "1", "COLORTERM": "truecolor", "TERM": "xterm-256color"},
    "eight-bit": {"FORCE_COLOR": "1", "TERM": "xterm-256color"},
    "standard": {"FORCE_COLOR": "1", "TERM": "xterm"},
    "no-term": {"FORCE_COLOR": "1"},
    "dumb": {"FORCE_COLOR": "1", "TERM": "dumb"},
    "no-color": {"FORCE_COLOR": "1", "TERM": "xterm-256color", "NO_COLOR": "1"},
    "tty-compatible": {"TTY_COMPATIBLE": "1", "COLORTERM": "truecolor", "TERM": "xterm-256color"},
    # Presence, not truth: Rich reads `FORCE_COLOR=0` as a terminal.
    "force-color-zero": {"FORCE_COLOR": "0", "COLORTERM": "truecolor", "TERM": "xterm-256color"},
    # `TTY_COMPATIBLE=0` is checked before `FORCE_COLOR` and wins.
    "tty-compatible-zero": {"TTY_COMPATIBLE": "0", "FORCE_COLOR": "1", "COLORTERM": "truecolor"},
}

SHAPES = {
    "list": ["search", "forcecolourneedle", "--list"],
    "matches": ["search", "forcecolourneedle"],
}

SESSION_ID = "00000000-0000-0000-0000-000000000001"


def build_home(root: Path) -> Path:
    """A two-message session with fixed in-band timestamps.

    **No age token reaches the plain route** — it prints `created:` and
    `modified:` as absolute times taken from these stamps — so the recording does
    not rot and needs no clock override. The temporary home collapses to `~` in
    the rendered paths, so the varying part of the path never reaches the bytes.
    """
    directory = root / ".claude" / "projects" / "-tmp-force-colour"
    directory.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "type": "user",
            "uuid": "u1",
            "parentUuid": None,
            "cwd": str(root),
            "timestamp": "2026-08-20T10:00:00.000Z",
            "message": {"role": "user", "content": "forcecolourneedle in a haystack"},
        },
        {
            "type": "assistant",
            "uuid": "a1",
            "parentUuid": "u1",
            "timestamp": "2026-08-20T10:00:01.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "an answer worth rendering"}],
            },
        },
    ]
    body = "\n".join(json.dumps(entry) for entry in entries) + "\n"
    (directory / f"{SESSION_ID}.jsonl").write_text(body)
    return root


def run(home: Path, extra: dict[str, str], arguments: list[str]) -> bytes:
    environment = dict(os.environ, HOME=str(home), COLUMNS="100")
    for name in AMBIENT:
        environment.pop(name, None)
    environment.update(extra)
    leaked = [
        name
        for name in AMBIENT
        if name in environment and name not in extra
    ]
    if leaked:
        raise SystemExit(f"REFUSING: {leaked} leaked into the child environment")
    completed = subprocess.run(
        [str(LEGACY), *arguments], capture_output=True, env=environment, cwd=str(home)
    )
    return completed.stdout


def main() -> int:
    if not LEGACY.exists():
        print(f"REFUSING: {LEGACY} does not exist. This table can only come from ch-legacy.")
        return 2

    root = Path(tempfile.mkdtemp(prefix="rule-colour-"))
    try:
        home = build_home(root)
        recorded: dict[str, dict[str, str]] = {}
        for shape, arguments in SHAPES.items():
            recorded[shape] = {
                name: base64.b64encode(run(home, extra, arguments)).decode("ascii")
                for name, extra in ENVIRONMENTS.items()
            }
    finally:
        shutil.rmtree(root, ignore_errors=True)

    def raw(shape: str, name: str) -> bytes:
        return base64.b64decode(recorded[shape][name])

    problems: list[str] = []
    for shape in SHAPES:
        if ESCAPE.search(raw(shape, "control")):
            problems.append(f"{shape}: the control carries escapes; it must not")
        if not any(ESCAPE.search(raw(shape, name)) for name in ENVIRONMENTS):
            problems.append(f"{shape}: no tier carries an escape — this is not a corpus")
        if ESCAPE.search(raw(shape, "dumb")):
            problems.append(f"{shape}: TERM=dumb carries escapes; Rich returns no colour there")
        depths = {name: raw(shape, name) for name in ("truecolor", "eight-bit", "standard")}
        if len(set(depths.values())) != 3:
            problems.append(
                f"{shape}: truecolor, eight-bit and standard did not all differ. "
                "That is the signature of an ambient COLORTERM leak, not of a product "
                "that renders them alike."
            )

    if problems:
        print("REFUSING TO WRITE:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    TARGET.write_text(
        json.dumps(
            {
                "oracle": "ch-legacy",
                "captured": "2026-09-01",
                "note": (
                    "stdout bytes, base64. flags.color is FALSE in every row: piped "
                    "output always takes the plain console.rule() route, and these "
                    "variables reach the console rather than the flag."
                ),
                "columns": "100",
                "session_id": SESSION_ID,
                "environments": ENVIRONMENTS,
                "recorded": recorded,
            },
            indent=2,
        )
        + "\n"
    )
    for shape in SHAPES:
        print(f"--- {shape}")
        for name in ENVIRONMENTS:
            data = raw(shape, name)
            codes = [m.group().decode("latin1") for m in ESCAPE.finditer(data.split(b"\n")[0])]
            print(f"  {name:20} {len(data):5}B  {len(codes)} rule codes")
    print(f"\nwrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
