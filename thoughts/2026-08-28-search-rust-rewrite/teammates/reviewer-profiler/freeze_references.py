#!/usr/bin/env python3
"""Freeze the Python side of every comparison gate, while Python still exists.

At cutover the Python authority is deleted and any gate comparing two live
routes stops being runnable. Freezing is cheap now and impossible afterwards.

The stored side is the *reference* output only. Nothing here is derived from the
user's private sessions — every case runs against the checked-in contract
fixture home — because `tests/` is committed and a table must not launder
private conversation content into it to look durable.

    freeze_references.py REFERENCE FIXTURE_HOME [--verify FROZEN.json]
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pty_harness import run_at_width  # noqa: E402
from width_probe_fixture import GENERATOR, seed as seed_width_probe  # noqa: E402

# Read inside main() so the module stays importable. A module-level `sys.argv`
# read blocks `from <module> import CONSTANT`, which forces the other side to keep
# a hand copy — and hand copies drift silently, with both sets of gates passing
# while measuring different things.
REFERENCE = FIXTURE = None


def _read_arguments() -> None:
    global REFERENCE, FIXTURE
    REFERENCE, FIXTURE = sys.argv[1], Path(sys.argv[2])
PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROBE_SESSION_PATH = ".claude/projects/widthprobe/aaaaaaaa-1111-4111-8111-111111111111.jsonl"


def oracle_stamp() -> str:
    """The oracle's identity, derived now rather than transcribed.

    A hardcoded stamp on a freshly generated artifact asserts an oracle state
    nobody checked at generation time. Deriving it is the only form that means
    what it says.
    """
    sys.path.insert(0, str(PROJECT_ROOT / "tests"))
    import oracle_digest

    return oracle_digest.oracle_route_digest()


INSTRUMENT_MODULES = ("freeze_references.py", "pty_harness.py", "width_probe_fixture.py")
PROVENANCE = (
    "Instrument written by `g5-runner`, the seat that also verified it. Disclosed "
    "rather than laundered through another pair of hands: the record here is of "
    "*Python's* answers, and that seat has no stake in them — its stake is in the "
    "Rust port, which this artifact does not measure. The way the instrument could "
    "be wrong is normalisation reaching too far, and that is proved against "
    "separately: a path differing outside the ephemeral home, and one differing "
    "under it past the prefix, both still fail. Re-verify from a separate process "
    "with a fresh temp home; do not trust a second call inside one. "
    "Every stamp here is derived AT generation. `contract-owner`'s "
    "`rebless_oracle.py` used to add them afterwards and no longer does — its "
    "`FOREIGN_RECORDS` is deliberately empty. Stamping a frozen artifact without "
    "re-recording its entries asserts the oracle has not moved since generation, "
    "which a later stamp cannot support: derived-at-generation is the strong form "
    "and asserted-afterwards is a downgrade, not a refresh. If you find both "
    "writers in the history, this one was right. "
    "The reference is `.venv/bin/ch-legacy`, not the pinned `~/.local/bin/ch` these "
    "answers were first frozen against. Both were measured equivalent over all 82 "
    "entries before the move — 0 drifted — so no recorded answer changed. The move "
    "is because installing the wheel overwrites `~/.local/bin/ch` with the NATIVE "
    "route, which would make this gate compare native against native while reporting "
    "drift. `ch-legacy` is the route `oracle_digest.py` actually defines and "
    "installing does not touch it. `--verify` now refuses a reference whose identity "
    "does not match the one recorded here."
)


def instrument_digest() -> str:
    """Digest the code that produced this artifact, not only the oracle it read.

    An artifact stamped with its oracle alone cannot say which of several
    instrument versions made it — which is exactly the position this file was in,
    carrying a hardcoded stamp from a version no longer on disk. A revision alone
    is not enough, one artifact over.
    """
    digest = hashlib.sha256()
    here = Path(__file__).resolve().parent
    for name in sorted(INSTRUMENT_MODULES) + [GENERATOR.name]:
        path = here / name if name in INSTRUMENT_MODULES else GENERATOR
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def refuse_a_swapped_reference(stored: dict) -> None:
    """Refuse to verify against a reference that is not the one frozen.

    **This gate compared entries and never checked which reference produced
    them.** A reference swapped underneath it makes every entry disagree and the
    run reports *drift* — **it fails in the shape of a different problem**, so the
    port looks broken when only the reference moved.

    The cheapest way to cause it is ordinary: installing the wheel over
    `~/.local/bin/ch` turns that path from the Python route into the native one.
    Nobody would think of that as touching a gate.

    **Refusing rather than warning is the point.** A warning here is read after
    the drift list, and by then the drift list has been believed.
    """
    expected = stored["reference_route_identity"]
    actual = hashlib.sha256(Path(REFERENCE).read_bytes()).hexdigest()[:16]
    if actual != expected:
        raise SystemExit(
            "refusing to verify: the reference is not the one these answers were frozen "
            f"against.\n  frozen against  {expected}\n  given           {actual}  "
            f"({REFERENCE})\nEvery entry would disagree and the run would report drift, which "
            "reads as\nthe port breaking. Point at the reference above, or re-freeze "
            "deliberately."
        )


def restore_fixture_mtimes(home: Path) -> None:
    """Apply the fixture's recorded mtimes, as the contract suite already does.

    Session order is `sort_by_modified`. A fixture home carrying whatever mtimes a
    checkout happened to give it therefore orders differently between runs, and 54
    of 82 entries moved that way between two runs of an unchanged oracle.
    """
    for relative, stamp in json.loads((FIXTURE.parent / "MTIMES.json").read_text()).items():
        path = home / relative
        if path.exists():
            os.utime(path, (stamp, stamp))


def stamp_width_probe(home: Path) -> None:
    """Continue the fixture's stamping scheme onto the seeded probe.

    `seed` writes the probe at the wall clock, so its rank against a fixture set
    stamped in 2027 depends on the day this runs. The scheme steps by 100.
    """
    recorded = json.loads((FIXTURE.parent / "MTIMES.json").read_text())
    stamp = max(recorded.values()) + 100
    os.utime(home / PROBE_SESSION_PATH, (stamp, stamp))


COLOURED = ["search", "needle five", "--color", "always", "--no-paging", "--no-metadata"]
# The shapes that write to stderr. Frozen on a pty, because colour on stderr is
# decided by whether *stderr* is a terminal — captured through a pipe it is off by
# construction and the baseline would record the wrong thing.
# The `--color` flag matrix on stdout. `--color never` still emits colour on the
# Python route, because the plain path calls `get_console().rule(style=...)` and the
# rule styles unconditionally — the flag does not reach every console. That is the
# oracle's behaviour, so the charter requires reproducing it, and a port that
# honoured `never` everywhere would be *more* correct and would diverge. Nothing
# pinned it until now.
COLOUR_FLAG_SHAPES = {
    "always": ["search", "needle five", "--color", "always", "--no-paging", "--no-metadata"],
    "never": ["search", "needle five", "--color", "never", "--no-paging", "--no-metadata"],
    "auto": ["search", "needle five", "--color", "auto", "--no-paging", "--no-metadata"],
    "absent": ["search", "needle five", "--no-paging", "--no-metadata"],
}

STDERR_SHAPES = {
    "no-match": ["search", "zqxjvwmkbphfgd", "--no-paging"],
    "no-match-colour-never": ["search", "zqxjvwmkbphfgd", "--no-paging", "--color", "never"],
    "no-match-colour-always": ["search", "zqxjvwmkbphfgd", "--no-paging", "--color", "always"],
    "no-match-filtered": ["search", "zqxjvwmkbphfgd", "--no-paging", "-p", "codex"],
}
PIPED_CASE = ["search", "needle five", "--no-metadata"]
PTY_BASE = {"PATH": "/usr/bin:/bin", "TERM": "xterm-256color", "COLORTERM": "truecolor", "TZ": "Asia/Jerusalem"}
UNSET = object()

AMBIENT = {
    "COLORTERM": ({"COLORTERM": "truecolor"}, {"COLORTERM": UNSET}),
    "NO_COLOR": ({}, {"NO_COLOR": "1"}),
    "FORCE_COLOR": ({}, {"FORCE_COLOR": "1"}),
    "TERM=dumb": ({}, {"TERM": "dumb"}),
    "TTY_COMPATIBLE": ({}, {"TTY_COMPATIBLE": "1"}),
    "TTY_INTERACTIVE": ({}, {"TTY_INTERACTIVE": "1"}),
    "LINES": ({"LINES": "40"}, {"LINES": "200"}),
    "TZ": ({"TZ": "Asia/Jerusalem"}, {"TZ": "Pacific/Kiritimati"}),
    "UNICODE_VERSION": ({"UNICODE_VERSION": "latest"}, {"UNICODE_VERSION": "9.0.0"}),
}
CAPABILITIES = {
    "truecolor": {"TERM": "xterm-256color", "COLORTERM": "truecolor"},
    "256 colour": {"TERM": "xterm-256color", "COLORTERM": UNSET},
    "16 colour": {"TERM": "xterm-16color", "COLORTERM": UNSET},
    "8 colour": {"TERM": "xterm", "COLORTERM": UNSET},
    "dumb terminal": {"TERM": "dumb", "COLORTERM": UNSET},
    "NO_COLOR": {"NO_COLOR": "1"},
}


def environment(home: Path, overrides: dict, base: dict) -> dict[str, str]:
    result = base | {"HOME": str(home)}
    for key, value in overrides.items():
        if value is UNSET:
            result.pop(key, None)
        else:
            result[key] = value
    return result


def record(output: bytes, home: Path) -> dict:
    """Store bytes, with the ephemeral home replaced by a token.

    A per-file error names the offending path, and that path lives under a
    temporary home. Recorded raw, the entry would be the one row nobody could
    ever re-derive — which is the opposite of what a frozen reference is for.

    `home` is required rather than defaulted. It was defaulted, one of nine call
    sites passed it, and the other twenty-one entries froze a `mkdtemp` name that
    is new every run — so `--verify` could not return zero on any fresh run, at 82
    or at 76. A caller cannot omit what it must pass.
    """
    output = output.replace(str(home).encode(), b"{HOME}")
    ephemeral = home.parent.name.encode()
    if ephemeral in output:
        raise SystemExit(
            f"the ephemeral directory name {ephemeral!r} survived normalisation. The home "
            "prefix was probably cut by the render width, so this entry could never be "
            "re-derived. Fix the case; do not freeze it."
        )
    return {"sha256": hashlib.sha256(output).hexdigest(), "bytes": base64.b64encode(output).decode()}


def collect(home: Path) -> dict:
    entries: dict[str, dict] = {}
    for width in (60, 80, 120, 200):
        out = run_at_width([REFERENCE, *COLOURED], columns=width,
                           environment=environment(home, {}, PTY_BASE))
        entries[f"width/{width}"] = record(out, home)
    for name, (a, b) in AMBIENT.items():
        for label, overrides in (("A", a), ("B", b)):
            env = environment(home, overrides, PTY_BASE)
            out = run_at_width([REFERENCE, *COLOURED], columns=80, environment=env,
                               allow_dumb=env.get("TERM") == "dumb")
            entries[f"ambient-pty/{name}/{label}"] = record(out, home)
            piped_env = environment(home, overrides, PTY_BASE | {"COLUMNS": "80"})
            piped = subprocess.run([REFERENCE, *PIPED_CASE], capture_output=True,
                                   check=False, env=piped_env).stdout
            entries[f"ambient-piped/{name}/{label}"] = record(piped, home)
    # stderr is a surface no gate watched until today, and it carries a baseline
    # divergence needing no ambient input at all. Python is deleted at cutover, so
    # this is the only chance to record what it did.
    broken = home / ".claude" / "projects" / "alpha" / "99999999-9999-4999-8999-999999999999.jsonl"
    broken.mkdir(parents=True, exist_ok=True)
    # Both separators: the bold brace, and the width pin. TERM=dumb fixes Rich at 80
    # *before* COLUMNS is read, so at 80 only the attribute separates the two states
    # and at any other width the wrapping does too. Captured at both.
    for width in (80, 120):
        for label, overrides in (("baseline", {}), ("NO_COLOR", {"NO_COLOR": "1"}),
                                 ("TERM=dumb", {"TERM": "dumb"})):
            env = environment(home, overrides, PTY_BASE)
            entries[f"stderr-errno-{width}/{label}"] = record(
                run_at_width([REFERENCE, "search", "needle", "--no-paging"], columns=width,
                             environment=env, allow_dumb=env.get("TERM") == "dumb",
                             stream="stderr"),
                home,
            )

    for shape, arguments in STDERR_SHAPES.items():
        env = environment(home, {}, PTY_BASE)
        entries[f"stderr/{shape}"] = record(
            run_at_width([REFERENCE, *arguments], columns=80, environment=env, stream="stderr"),
            home,
        )
    for name, (a, b) in AMBIENT.items():
        for label, overrides in (("A", a), ("B", b)):
            env = environment(home, overrides, PTY_BASE)
            entries[f"stderr-ambient/{name}/{label}"] = record(
                run_at_width([REFERENCE, *STDERR_SHAPES["no-match"]], columns=80,
                             environment=env, allow_dumb=env.get("TERM") == "dumb",
                             stream="stderr"),
                home,
            )

    # Both conditions, because the isatty cascade makes `auto` and `absent` resolve
    # differently on a pty than on a pipe, and the flag matrix is exactly where that
    # shows.
    for flag, arguments in COLOUR_FLAG_SHAPES.items():
        env = environment(home, {}, PTY_BASE)
        entries[f"colour-flag-pty/{flag}"] = record(
            run_at_width([REFERENCE, *arguments], columns=80, environment=env),
            home,
        )
        entries[f"colour-flag-piped/{flag}"] = record(
            subprocess.run([REFERENCE, *arguments], capture_output=True, check=False,
                           env=env | {"COLUMNS": "80"}).stdout,
            home,
        )

    for tier, overrides in CAPABILITIES.items():
        env = environment(home, overrides, PTY_BASE | {"COLUMNS": "80"})
        out = run_at_width([REFERENCE, *COLOURED], columns=80, environment=env,
                           allow_dumb=env.get("TERM") == "dumb")
        entries[f"capability/{tier}"] = record(out, home)
    return entries


def main() -> int:
    _read_arguments()
    if "--verify" in sys.argv:
        refuse_a_swapped_reference(
            json.loads(Path(sys.argv[sys.argv.index("--verify") + 1]).read_text())
        )
    home = Path(tempfile.mkdtemp()) / "home"
    shutil.copytree(FIXTURE, home)
    restore_fixture_mtimes(home)
    seed_width_probe(home)
    stamp_width_probe(home)
    entries = collect(home)

    if "--verify" in sys.argv:
        stored = json.loads(Path(sys.argv[sys.argv.index("--verify") + 1]).read_text())["entries"]
        drift = [k for k in stored if stored[k]["sha256"] != entries.get(k, {}).get("sha256")]
        missing = [k for k in entries if k not in stored]
        print(f"verify: {len(stored)} stored, {len(drift)} drifted, {len(missing)} new")
        for key in drift[:10]:
            print(f"  drifted: {key}")
        return 1 if drift or missing else 0

    out = Path(__file__).parent / "frozen_reference.json"

    # Every field below is derived here. The carry-forward that used to preserve
    # `contract-owner`'s stamp fields is gone: this instrument now derives
    # `source_digest` and `source_digest_recipe` itself, and `revision` — the only
    # remaining foreign field — has no reader. `responsiveness.py` reads `entries`
    # alone, and the contract suite's `ORACLE["revision"]` is a different artifact,
    # `search-contract-fixtures/ORACLE.json`. An artifact whose point is
    # self-description cannot carry one field nobody re-derives; the next reader
    # would assume the others are un-derived too.
    stamp = oracle_stamp()
    instrument = instrument_digest()
    mine = {
        "oracle_state": f"reference {REFERENCE}, oracle route digest {stamp}",
        "source_digest": stamp,
        "source_digest_recipe": "tests/oracle_digest.py::oracle_route_digest",
        "instrument_digest": instrument,
        "instrument_digest_recipe": (
            "sha256 over name+bytes of "
            + ", ".join(sorted(INSTRUMENT_MODULES) + [GENERATOR.name])
        ),
        "provenance": PROVENANCE,
        "reference_route_identity": hashlib.sha256(Path(REFERENCE).read_bytes()).hexdigest()[:16],
        "note": "Reference-side outputs only. Contract fixture home; no user session content.",
        "entries": entries,
    }
    out.write_text(json.dumps(mine, indent=1))
    total = sum(len(base64.b64decode(e["bytes"])) for e in entries.values())
    print(f"froze {len(entries)} reference outputs, {total:,} bytes of output, file {out.stat().st_size:,} bytes")
    print(f"oracle:     {stamp}")
    print(f"instrument: {instrument}")
    print(f"reference:  {REFERENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
