#!/usr/bin/env -S uv run
"""Freeze `ch-legacy`'s answer for every `preserve-because-wrong` item.

**Every item on that list is an accepted difference with no prohibition behind it.** A
gap and a prohibition look identical in a passing suite and behave completely differently
a month later, when someone reads a wrong-looking behaviour as an unfinished port and
helpfully corrects it. **The only difference is whether a gate fails when they do.**

**The sweep already asserted every prohibition; what it lacked was a schedule.** A probe
run once protects nothing after the run. So this captures legacy's bytes and
`tests/test_preserve_because_wrong.py` compares against them — **prohibitions that
outlive the oracle.**

**The capture is the irreversible half and the gate is not.** It compares against
`ch-legacy`, so it cannot be taken after the deletion slice.

**Everything wall-clock is pinned.** `CH_NOW` fixes the clock the age tokens are measured
from, `TZ` fixes the fold, and the file mtimes are recorded here and re-applied by the
gate — otherwise item 5's recorded ages rot in a day.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

CH_NOW = "2026-09-01T12:00:00"
TZ = "Asia/Jerusalem"


def project_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".venv" / "bin" / "ch-legacy").is_file():
            return candidate
    raise SystemExit(
        "No ancestor owns `.venv/bin/ch-legacy`. **This baseline can only be captured "
        "while the Python route lives.**"
    )


ROOT = project_root()
LEGACY = ROOT / ".venv" / "bin" / "ch-legacy"
FIXTURES = ROOT / "tests" / "data" / "preserve-because-wrong"


def write_session(home: Path, name: str, entries: list[dict]) -> Path:
    directory = home / ".claude" / "projects" / "pbw"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
    return path


def entry(index: int, text: str, *, stamp: str, cwd: str, thinking: str | None = None) -> dict:
    content: list | str = text
    if thinking is not None:
        content = [{"type": "thinking", "thinking": thinking}, {"type": "text", "text": text}]
    role = "user" if index % 2 == 0 else "assistant"
    return {
        "type": role, "uuid": f"u{index}", "timestamp": stamp, "cwd": cwd,
        "message": {"role": role, "content": content},
    }


def build_pools() -> dict[str, dict]:
    """One committed pool per item, plus the mtimes the gate must re-apply."""
    if FIXTURES.exists():
        for child in FIXTURES.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
    pools: dict[str, dict] = {}

    # 1 — `collapse_home` matches a string prefix, so a sibling starting with the home
    # directory's name renders mangled. The sibling has to be a real path beside HOME.
    home = FIXTURES / "item1" / "home"
    write_session(home, "aaaaaaaa-0001-4000-8000-000000000001",
                  [entry(0, "pbw collapse needle", stamp="2026-08-20T13:00:00.000Z",
                         cwd=str(FIXTURES / "item1" / "homeX" / "dev" / "chats"))])
    pools["item1"] = {"home": str(home), "mtimes": {}}

    # 3 — `elide_to_width` counts code points, so wide text overshoots. Only the
    # **coloured** list row and panel title reach it; plain list mode never elides.
    home = FIXTURES / "item3" / "home"
    write_session(home, "aaaaaaaa-0003-4000-8000-000000000003",
                  [entry(0, "你好" * 60 + " pbw wide needle",
                         stamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw")])
    pools["item3"] = {"home": str(home), "mtimes": {}}

    # 4 — `truncate_middle` counts code points, so NFD loses visible characters.
    home = FIXTURES / "item4" / "home"
    write_session(home, "aaaaaaaa-0004-4000-8000-000000000004",
                  [entry(1, "pbw nfd needle", stamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw",
                         thinking=unicodedata.normalize("NFD", "é" * 400))])
    pools["item4"] = {"home": str(home), "mtimes": {}}

    # 5 — 30-day months and 365-day years, sampled either side of both boundaries.
    #
    # **The age comes from the last *in-band* timestamp, not the file mtime.**
    # `last_timestamp` prefers the content and only falls back to the filesystem, so a
    # fixture that set mtimes and left every entry at one timestamp measured nothing —
    # the first attempt did exactly that and recorded five ages in *minutes* where the
    # item is about months and years.
    import datetime as _datetime
    import time as _time
    os.environ["TZ"] = TZ
    _time.tzset()
    pinned = _datetime.datetime.strptime(CH_NOW, "%Y-%m-%dT%H:%M:%S")
    home = FIXTURES / "item5" / "home"
    for index, days in enumerate((359, 360, 364, 365, 366)):
        when = pinned - _datetime.timedelta(days=days)
        write_session(home, f"aaaaaaaa-0005-4000-8000-00000000000{index}",
                      [entry(0, "pbw age needle",
                             stamp=when.strftime("%Y-%m-%dT%H:%M:%S.000"),
                             cwd="/tmp/pbw")])
    pools["item5"] = {"home": str(home), "mtimes": {}}

    # 7 — naive local time collapses two instants inside a DST fold.
    home = FIXTURES / "item7" / "home"
    for index, stamp in enumerate(("2026-10-24T22:30:00.000Z", "2026-10-24T23:30:00.000Z")):
        write_session(home, f"aaaaaaaa-0007-4000-8000-00000000000{index}",
                      [entry(0, "pbw fold needle", stamp=stamp, cwd="/tmp/pbw")])
    pools["item7"] = {"home": str(home), "mtimes": {}}

    # 8 — exactly one trailing space, on exactly the last line, is deleted.
    home = FIXTURES / "item8" / "home"
    for index, body in enumerate((
        "pbw trailing needle\nlast line ",
        "pbw trailing needle\nlast line  ",
        "pbw trailing needle \nlast line",
    )):
        write_session(home, f"aaaaaaaa-0008-4000-8000-00000000000{index}",
                      [entry(0, body, stamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw")])
    pools["item8"] = {"home": str(home), "mtimes": {}}

    # 11 — an empty string is *absent* to the no-results wording and *present and
    # invalid* to the date filter, from the same struct.
    home = FIXTURES / "item11" / "home"
    write_session(home, "aaaaaaaa-0011-4000-8000-000000000011",
                  [entry(0, "pbw empty needle", stamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw")])
    pools["item11"] = {"home": str(home), "mtimes": {}}
    return pools


CASES: list[tuple[str, str, list[str], int]] = [
    ("1  collapse_home renders a mangled sibling", "item1", ["pbw", "-l"], 96),
    ("3  elide_to_width, coloured, narrow", "item3",
     ["pbw", "-l", "--color", "always", "--no-paging"], 40),
    ("3  elide_to_width, coloured, wide", "item3",
     ["pbw", "-l", "--color", "always", "--no-paging"], 96),
    ("4  truncate_middle over NFD thinking", "item4", ["pbw", "-T", "--short", "-f"], 96),
    ("5  humanize_age at both boundaries", "item5", ["pbw", "-l"], 96),
    ("5  humanize_age, coloured", "item5",
     ["pbw", "-l", "--color", "always", "--no-paging"], 96),
    ("7  DST fold ordering and dates", "item7", ["pbw", "-l"], 96),
    ("7  DST fold under -ma", "item7", ["pbw", "-ll", "-ma", "2026-10-24"], 96),
    ("8  trailing space, fenced", "item8", ["pbw", "-f"], 96),
    ("8  trailing space, raw", "item8", ["pbw", "-r"], 96),
    ("11 empty -d is absent", "item11", ["-d", "", "zzz"], 96),
    ("11 no filter at all", "item11", ["zzz"], 96),
    ("11 a real -d is present", "item11", ["-d", "/tmp/nowhere", "zzz"], 96),
    ("11 empty -ma is present and invalid", "item11", ["-ma", "", "zzz"], 96),
]


def run(pool: dict, arguments: list[str], columns: int):
    environment = {
        key: value for key, value in os.environ.items()
        if key not in {"COLUMNS", "NO_COLOR", "COLORTERM", "FORCE_COLOR", "CLICOLOR",
                       "CLICOLOR_FORCE", "TTY_COMPATIBLE"}
    }
    environment.update({
        "HOME": pool["home"], "COLUMNS": str(columns), "TERM": "xterm-256color",
        "COLORTERM": "truecolor", "TZ": TZ, "CH_NOW": CH_NOW,
    })
    return subprocess.run([str(LEGACY), "search", *arguments],
                          env=environment, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(FIXTURES / "legacy-baseline.json"))
    options = parser.parse_args()

    pools = build_pools()
    cases = []
    for label, pool_name, arguments, columns in CASES:
        result = run(pools[pool_name], arguments, columns)
        cases.append({
            "id": label, "pool": pool_name, "arguments": arguments, "columns": columns,
            "exit_status": result.returncode,
            "stdout": result.stdout.decode("latin-1"),
            "stderr": result.stderr.decode("latin-1"),
        })

    # **Refusals, not warnings.** A recording that came out empty or missing an item
    # looks exactly like a corpus and proves the opposite of what it claims.
    empty = [case["id"] for case in cases if not case["stdout"] and not case["stderr"]]
    if empty:
        raise SystemExit(f"These cases recorded nothing at all: {empty}. Refusing to write.")
    items = {case["id"].split()[0] for case in cases}
    missing = {"1", "3", "4", "5", "7", "8", "11"} - items
    if missing:
        raise SystemExit(f"Items {sorted(missing)} are absent from the capture. Refusing.")
    if len(cases) < len(CASES):
        raise SystemExit("Fewer cases than shapes. Refusing.")

    Path(options.out).write_text(json.dumps({
        "captured": "2026-09-01", "ch_now": CH_NOW, "tz": TZ,
        "why": (
            "Every item on preserve-because-wrong.md is an accepted difference with no "
            "prohibition behind it. A gap and a prohibition look identical in a passing "
            "suite and behave differently a month later, when someone reads a "
            "wrong-looking behaviour as an unfinished port and corrects it."
        ),
        "pools": {name: {"mtimes": pool["mtimes"]} for name, pool in pools.items()},
        "cases": cases,
    }, ensure_ascii=False))
    total = sum(len(case["stdout"]) + len(case["stderr"]) for case in cases)
    print(f"{len(cases)} cases over {len(pools)} pools, {total} bytes -> {options.out}")


if __name__ == "__main__":
    main()
