#!/usr/bin/env -S uv run
"""Every `preserve-because-wrong` item, asked of the **live route** rather than of a fixture.

**The point is that the route has flipped.** Before the arm landed, `ch search` was
`ch-legacy` and every one of these questions answered itself. Now the two are different
programs, and each item is a behaviour a competent port would silently *improve* — which
is the direction no comparator on this mission can see.

Each case builds its own session pool, runs the shape on both binaries, and compares
stdout, stderr and exit status byte for byte. **A difference here is a divergence in the
direction nobody reports**, because the native answer looks better.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

NATIVE = Path("target/release/ch").resolve()
LEGACY = Path(".venv/bin/ch-legacy").resolve()


def session(home: Path, name: str, entries: list[dict]) -> Path:
    directory = home / ".claude" / "projects" / "pbw"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
    return path


def entry(index: int, text: str, *, timestamp: str, cwd: str, thinking: str | None = None) -> dict:
    content: list | str = text
    if thinking is not None:
        content = [
            {"type": "thinking", "thinking": thinking},
            {"type": "text", "text": text},
        ]
    return {
        "type": "user" if index % 2 == 0 else "assistant",
        "uuid": f"u{index}",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "user" if index % 2 == 0 else "assistant", "content": content},
    }


def compare(label: str, home: Path, arguments: list[str], *, tz: str | None = None) -> bool:
    environment = {k: v for k, v in os.environ.items() if k not in {"COLUMNS", "NO_COLOR"}}
    environment["HOME"] = str(home)
    environment["COLUMNS"] = "96"
    environment["TERM"] = "dumb"
    if tz:
        environment["TZ"] = tz
    a = subprocess.run([str(NATIVE), "search", *arguments], env=environment, capture_output=True)
    b = subprocess.run([str(LEGACY), "search", *arguments], env=environment, capture_output=True)
    same = (a.stdout, a.stderr, a.returncode) == (b.stdout, b.stderr, b.returncode)
    # **A probe that reaches nothing agrees vacuously.** Every SAME here is reported with
    # the bytes behind it, because "both printed nothing" and "both printed the same
    # wrong-on-purpose answer" look identical in a pass/fail column.
    reach = f"{len(b.stdout)}B out, {len(b.stderr)}B err, exit {b.returncode}"
    print(f"{'SAME    ' if same else 'DIFFERS '} {label}  [{reach}]")
    if same and len(b.stdout) + len(b.stderr) < 40:
        print("    ⚠ VACUOUS: the routes agree on almost no output. This probe proves nothing.")
    if not same:
        for stream in ("stdout", "stderr"):
            an, bn = getattr(a, stream), getattr(b, stream)
            if an != bn:
                index = next((i for i in range(min(len(an), len(bn))) if an[i] != bn[i]), min(len(an), len(bn)))
                print(f"    {stream} first differs at {index}")
                print(f"      legacy {bn[max(0,index-70):index+70]!r}")
                print(f"      native {an[max(0,index-70):index+70]!r}")
        if a.returncode != b.returncode:
            print(f"    exit legacy={b.returncode} native={a.returncode}")
    return same


def item_1_collapse_home() -> None:
    """`collapse_home` matches a string prefix, not a path boundary."""
    root = Path(tempfile.mkdtemp())
    home = root / "giladbarnea"
    home.mkdir()
    # A sibling whose name *starts with* the home directory's name.
    sibling = f"{home}X/dev/chats"
    session(home, "aaaaaaaa-0001-4000-8000-000000000001",
            [entry(0, "pbw collapse needle", timestamp="2026-08-20T13:00:00.000Z", cwd=sibling)])
    compare("1  collapse_home renders a mangled sibling path", home, ["pbw", "-l"])


def item_3_elide_to_width() -> None:
    """`elide_to_width` counts code points, so wide text overshoots its budget."""
    root = Path(tempfile.mkdtemp()); home = root / "h"; home.mkdir()
    wide = "你好" * 60
    session(home, "aaaaaaaa-0003-4000-8000-000000000003",
            [entry(0, f"{wide} pbw wide needle", timestamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw")])
    # **`--color always`, because `elide_to_width` is only reached from the coloured
    # list row and the panel title.** The plain list mode never elides, so the first
    # version of this probe compared two un-elided outputs and agreed about nothing.
    for width in ("40", "72", "96"):
        environment = dict(os.environ, HOME=str(home), COLUMNS=width, TERM="xterm-256color")
        environment.pop("NO_COLOR", None)
        shape = ["search", "pbw", "-l", "--color", "always", "--no-paging"]
        a = subprocess.run([str(NATIVE), *shape], env=environment, capture_output=True)
        b = subprocess.run([str(LEGACY), *shape], env=environment, capture_output=True)
        marker = "…" in b.stdout.decode(errors="replace")
        print(f"{'SAME    ' if a.stdout == b.stdout else 'DIFFERS '} 3  elide_to_width on wide "
              f"text at COLUMNS={width}  [{len(b.stdout)}B, elided={marker}]")


def item_4_truncate_middle() -> None:
    """`truncate_middle` counts code points, so shortening is normalization-sensitive."""
    root = Path(tempfile.mkdtemp()); home = root / "h"; home.mkdir()
    visible = "é" * 400
    nfd = unicodedata.normalize("NFD", visible)
    session(home, "aaaaaaaa-0004-4000-8000-000000000004",
            [entry(1, "pbw nfd needle", timestamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw", thinking=nfd)])
    compare("4  truncate_middle over NFD thinking, --short", home, ["pbw", "-T", "--short", "-f"])


def item_5_age_units() -> None:
    """`humanize_age` uses 30-day months and 365-day years."""
    import time
    root = Path(tempfile.mkdtemp()); home = root / "h"; home.mkdir()
    now = time.time()
    for index, days in enumerate((359, 360, 364, 365, 366)):
        path = session(home, f"aaaaaaaa-0005-4000-8000-00000000000{index}",
                       [entry(0, "pbw age needle", timestamp="2026-01-01T13:00:00.000Z", cwd="/tmp/pbw")])
        when = now - days * 86400
        os.utime(path, (when, when))
    compare("5  humanize_age at the 360/365-day boundaries", home, ["pbw", "-l"])


def item_7_dst_fold() -> None:
    """Naive local time collapses two instants across a DST fold."""
    root = Path(tempfile.mkdtemp()); home = root / "h"; home.mkdir()
    for index, stamp in enumerate(("2026-10-24T22:30:00.000Z", "2026-10-24T23:30:00.000Z")):
        session(home, f"aaaaaaaa-0007-4000-8000-00000000000{index}",
                [entry(0, "pbw fold needle", timestamp=stamp, cwd="/tmp/pbw")])
    compare("7  DST fold ordering and rendered dates", home, ["pbw", "-l"], tz="Asia/Jerusalem")
    compare("7b DST fold under -ma", home, ["pbw", "-ll", "-ma", "2026-10-24"], tz="Asia/Jerusalem")


def item_8_trailing_space() -> None:
    """Exactly one trailing space, on exactly the last line, is deleted."""
    root = Path(tempfile.mkdtemp()); home = root / "h"; home.mkdir()
    bodies = {
        "one-on-last": "pbw trailing needle\nlast line ",
        "two-on-last": "pbw trailing needle\nlast line  ",
        "one-not-last": "pbw trailing needle \nlast line",
    }
    for index, body in enumerate(bodies.values()):
        session(home, f"aaaaaaaa-0008-4000-8000-00000000000{index}",
                [entry(0, body, timestamp="2026-08-20T13:00:00.000Z", cwd="/tmp/pbw")])
    compare("8  trailing-space rule, three shapes", home, ["pbw", "-f"])
    compare("8b trailing-space rule, raw", home, ["pbw", "-r"])


def main() -> None:
    for probe in (item_1_collapse_home, item_3_elide_to_width, item_4_truncate_middle,
                  item_5_age_units, item_7_dst_fold, item_8_trailing_space):
        try:
            probe()
        except Exception as error:  # a probe that cannot run is not a pass
            print(f"ERROR    {probe.__name__}: {error}")


if __name__ == "__main__":
    main()
