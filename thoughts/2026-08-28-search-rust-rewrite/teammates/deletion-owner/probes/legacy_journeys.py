#!/usr/bin/env python3
"""`ch-legacy`'s surviving journeys, captured before the deletion and replayed after.

**A deletion is falsified by what still has to pass.** The charter keeps `ch-legacy`
for default session parsing and the unscoped commands, so the proof that the right
thing was deleted is that every one of those journeys produces the same bytes
afterwards.

Every journey is run through **both** binaries: `.venv/bin/ch-legacy` directly, and
the public `ch` launcher, which routes these arms to its sibling. A capture of only
one side would miss a routing change.

Refusals, because a recording that came out empty must not look like a corpus:
a short journey list, and any journey that exits 0 with both streams empty — a
comparison that cannot fail.

    --capture   write evidence/legacy-journeys.json
    --verify    replay and diff against it
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence" / "legacy-journeys.json"
FIXTURE_HOME = PROJECT_ROOT / "tests" / "data" / "search-contract-fixtures" / "home"
LEGACY = PROJECT_ROOT / ".venv" / "bin" / "ch-legacy"
LAUNCHER = PROJECT_ROOT / "target" / "release" / "ch"

SESSION = "a1a1a1a1-1111-4111-8111-aaaaaaaaaa09"
#: The cwd recorded inside the fixture sessions, so `-d` exercises
#: `pool_filter.passes_path_for_index` — the `-1 -d` index path the charter keeps
#: and the one trap that would be broken by deleting `pool_filter.py` by name.
SESSION_CWD = "/tmp/search-contract"

#: One entry per surviving `cli.main()` dispatch arm, plus the shapes inside the
#: default parse arm that reach different renderers.
JOURNEYS: dict[str, list[str]] = {
    "help": ["--help"],
    "parse-default": [SESSION],
    "parse-raw": [SESSION, "--raw"],
    "parse-json": [SESSION, "-f", "json"],
    "parse-thinking": [SESSION, "-T"],
    "parse-short": [SESSION, "--short"],
    "parse-slice": [SESSION, "1:2"],
    "parse-no-metadata": [SESSION, "--no-metadata"],
    "parse-subcommand-help": ["parse", "--help"],
    "index-recent": ["-1"],
    "index-recent-dir-filter": ["-1", "-d", SESSION_CWD],
    "index-recent-dir-miss": ["-1", "-d", "/tmp/no-such-directory-here"],
    "info-text": ["info", SESSION],
    "info-json": ["info", SESSION, "-f", "json"],
    "name-dry-run": ["name", SESSION, "a new display name", "--dry-run"],
    "rm-dry-run": ["rm", SESSION, "--dry-run"],
    "unknown-option": [SESSION, "--no-such-option"],
    "missing-session": ["00000000-0000-4000-8000-000000000000"],
}
MINIMUM_JOURNEYS = 18


def _normalize(content: bytes, home: Path) -> bytes:
    return (
        content.replace(str(home).encode(), b"{HOME}")
        .replace(str(PROJECT_ROOT).encode(), b"{PROJECT_ROOT}")
    )


def _run(executable: Path, arguments: list[str], home: Path) -> dict:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"NO_COLOR", "FORCE_COLOR", "CLICOLOR", "CLICOLOR_FORCE"}
    }
    environment.update(HOME=str(home), COLUMNS="96", TERM="dumb")
    completed = subprocess.run(
        [str(executable), *arguments],
        cwd=PROJECT_ROOT, env=environment, capture_output=True, check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": base64.b64encode(_normalize(completed.stdout, home)).decode(),
        "stderr": base64.b64encode(_normalize(completed.stderr, home)).decode(),
    }


def collect() -> dict:
    out: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as scratch:
        home = Path(scratch) / "home"
        shutil.copytree(FIXTURE_HOME, home)
        for name, arguments in JOURNEYS.items():
            for binary, path in (("ch-legacy", LEGACY), ("ch", LAUNCHER)):
                out[f"{name}|{binary}"] = {"arguments": arguments, **_run(path, arguments, home)}
    return out


def refuse(rows: dict) -> None:
    if len(JOURNEYS) < MINIMUM_JOURNEYS:
        raise SystemExit(
            f"REFUSING: {len(JOURNEYS)} journeys against a floor of {MINIMUM_JOURNEYS}. "
            "A shortened list records less while looking like a corpus."
        )
    inert = [
        key for key, row in rows.items()
        if row["returncode"] == 0 and not row["stdout"] and not row["stderr"]
    ]
    if inert:
        raise SystemExit(
            f"REFUSING: {len(inert)} journeys exit 0 with both streams empty: {inert}. "
            "A comparison that cannot fail must not be recorded as if it could."
        )


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--verify"
    rows = collect()
    refuse(rows)
    if mode == "--capture":
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps({
            "what_this_is": (
                "`ch-legacy`'s surviving journeys, recorded before the Python search "
                "authority was deleted. The falsifier for the deletion: these must "
                "reproduce byte for byte afterwards, through both binaries."
            ),
            "journeys": rows,
        }, indent=2, sort_keys=True))
        print(f"captured {len(rows)} journey runs to {EVIDENCE}")
        return

    recorded = json.loads(EVIDENCE.read_text())["journeys"]
    assert set(recorded) == set(rows), (
        f"the journey set moved.\n  joined: {sorted(set(rows) - set(recorded))}\n"
        f"  left:   {sorted(set(recorded) - set(rows))}"
    )
    differing = []
    for key, row in sorted(rows.items()):
        for field in ("returncode", "stdout", "stderr"):
            if row[field] != recorded[key][field]:
                differing.append((key, field, recorded[key][field], row[field]))
    for key, field, want, got in differing:
        print(f"DIFFERS  {key}  {field}")
        if field != "returncode":
            print(f"    before: {base64.b64decode(want)[:300]!r}")
            print(f"    after:  {base64.b64decode(got)[:300]!r}")
        else:
            print(f"    before: {want}   after: {got}")
    print(f"\n{len(rows) - len({k for k, *_ in differing})} of {len(rows)} journey runs "
          f"reproduce; {len({k for k, *_ in differing})} differ")
    raise SystemExit(1 if differing else 0)


if __name__ == "__main__":
    main()
