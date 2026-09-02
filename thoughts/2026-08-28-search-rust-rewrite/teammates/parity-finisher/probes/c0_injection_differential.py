#!/usr/bin/env python3
"""The C0 gate: the real corpus with C0 separators injected, both routes fresh.

**Why the corpus has to be mutated rather than sampled.** Not one of the 5,046
session files contains U+001C..U+001F anywhere, so every existing differential is
blind to the 23 sites in `rust/session.rs` where Python's `str.strip()` removes
those characters and Rust's `str::trim` leaves them. Authoring one fixture per
site is 23 chances to author a fixture that does not fire. Injecting a separator
at the edge of every content-bearing string in the *real* corpus instead reaches
every site the corpus reaches, and Python stays the oracle.

**The control arm is not optional.** Injection re-serializes each entry, and
re-serializing alone can move bytes. The first run re-serializes without
injecting and must report zero. A non-zero control means the instrument is
contaminated and the injected run's number says nothing.

Imports `claude_render_differential` rather than copying it, so both runs use the
same oracle, the same digest and the same seven flag configurations.

    cd .../session-core/probes/drivers/render
    CARGO_TARGET_DIR=$PWD/target cargo build --release
    RENDER_BIN=$PWD/target/release/branchcheck \\
      uv run -p python3 python .../probes/c0_injection_differential.py [limit]

`PROVIDER=pi` / `PROVIDER=codex` select the other two routes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SESSION_CORE_PROBES = Path(__file__).resolve().parents[2] / "session-core" / "probes"
sys.path.insert(0, str(SESSION_CORE_PROBES))

import claude_render_differential as base  # noqa: E402

FILE_SEPARATOR = "\u001c"  # U+001C FILE SEPARATOR
UNIT_SEPARATOR = "\u001f"  # U+001F UNIT SEPARATOR

# The content-bearing keys the ported `.strip()` sites read. Structural keys
# (`type`, `uuid`, `role`) are deliberately left alone: mutating those changes
# which decoder runs, which is a different experiment.
INJECTED_KEYS = frozenset(
    {"text", "thinking", "content", "customTitle", "summary", "task", "thread_name"}
)


def inject(value: object) -> object:
    """Wrap every content-bearing string in a leading and a trailing separator."""
    if isinstance(value, dict):
        return {
            key: (
                f"{FILE_SEPARATOR}{item}{UNIT_SEPARATOR}"
                if key in INJECTED_KEYS and isinstance(item, str) and item
                else inject(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [inject(item) for item in value]
    return value


def rewrite(content: str, *, injecting: bool) -> str | None:
    """Re-serialize every entry, optionally injecting.

    Returns `None` when a line will not round-trip, which disqualifies the file
    from both arms rather than from one.
    """
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue
        try:
            entry = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return None
        lines.append(json.dumps(inject(entry) if injecting else entry, ensure_ascii=False))
    return "\n".join(lines)


def snapshot(sessions: list[Path], root: Path, *, injecting: bool) -> list[tuple[Path, Path]]:
    pairs = []
    for index, source in enumerate(sessions):
        try:
            rewritten = rewrite(source.read_text(encoding="utf-8"), injecting=injecting)
        except (OSError, UnicodeDecodeError):
            continue
        if rewritten is None:
            continue
        target = root / f"{index:04d}-{source.name}"
        target.write_text(rewritten, encoding="utf-8")
        pairs.append((target, source))
    return pairs


def run(binary: str, sessions: list[Path], *, injecting: bool) -> tuple[int, int, list[str]]:
    """Return (cases compared, mismatches, first few explanations)."""
    root = Path(tempfile.mkdtemp(prefix="c0-injection-"))
    try:
        pairs = snapshot(sessions, root, injecting=injecting)
        cases = [
            {"path": str(path), "origin": str(origin), "flags": name, "provider": base.PROVIDER}
            for path, origin in pairs
            for name in base.CONFIGURATIONS
        ]
        payload = "\n".join(json.dumps(case) for case in cases) + "\n"
        completed = subprocess.run([binary], input=payload.encode("utf-8"), capture_output=True)
        if completed.returncode != 0:
            raise SystemExit(completed.stderr.decode("utf-8")[:2000])
        rows = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line]
        if len(rows) != len(cases):
            raise SystemExit(
                f"PROTOCOL ERROR: driver returned {len(rows)} rows for {len(cases)} cases."
            )

        mismatches = 0
        explanations: list[str] = []
        for case, actual in zip(cases, rows):
            flags = base.CONFIGURATIONS[case["flags"]]
            try:
                expected = base.python_rendered(Path(case["path"]), Path(case["origin"]), flags)
            except Exception as error:
                mismatches += 1
                if len(explanations) < 3:
                    explanations.append(
                        f"{Path(case['path']).name}: python raised {error!r}"
                    )
                continue
            if expected != actual:
                mismatches += 1
                if len(explanations) < 3:
                    explanations.append(
                        f"{Path(case['path']).name} [{case['flags']}]: "
                        f"python {len(expected)} rows, native {len(actual)} rows"
                    )
        return len(cases), mismatches, explanations
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    binary = os.environ.get("RENDER_BIN")
    if not binary:
        print("set RENDER_BIN to session-core's render driver")
        return 2
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    sessions = base.claude_sessions(limit)
    if not sessions:
        print(f"no {base.PROVIDER} sessions found")
        return 2
    print(f"provider: {base.PROVIDER}   sessions: {len(sessions)}")

    control_cases, control_mismatches, control_notes = run(binary, sessions, injecting=False)
    print(
        f"CONTROL  (re-serialized, no injection): {control_cases} cases, "
        f"{control_mismatches} mismatches"
    )
    for note in control_notes:
        print(f"    {note}")
    if control_mismatches:
        print(
            "CONTROL FAILED - re-serialization alone moves output, so the injected "
            "run below measures the instrument rather than the port. Refusing a verdict."
        )
        return 1

    cases, mismatches, notes = run(binary, sessions, injecting=True)
    print(
        f"INJECTED (U+001C/U+001F at every content-string edge): {cases} cases, "
        f"{mismatches} mismatches"
    )
    for note in notes:
        print(f"    {note}")
    if mismatches == 0:
        print("\nPASS - and read the next line before believing it.")
        print(
            "Zero here is evidence only if the injection reached a stripped site. "
            "Revert `python_is_space` to exclude U+001C..U+001F and re-run: a run "
            "that stays at zero is a statement about this corpus, not about the port."
        )
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
