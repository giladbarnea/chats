#!/usr/bin/env python3
"""Does `FORCE_COLOR` flip `flags.color`, or only the console's colour?

**The question decides the fix, and guessing it wrong changes two visible
behaviours instead of one.** `cli.py:343` computes
`color = (value == "always") or (value == "auto" and sys.stdout.isatty())` — plain
`isatty()`, no Rich cascade — and `paging` defaults to `color` one line down.
`_display_hit` then branches on `flags.color`: true picks a coloured list row or a
conversation panel, false picks `console.rule()` plus a plain body.

Meanwhile `init_module_console` builds a `Console`, and **Rich consults
`FORCE_COLOR` and `TTY_COMPATIBLE` itself** when deciding whether it is writing to
a terminal.

So there are two candidate stories and they need different fixes:

1. **`flags.color` flipped.** Then the native parser must resolve `--color auto`
   through `terminal::resolve_color`, and the sink and paging move with it.
2. **Only the console's colour flipped.** Then `flags.color` is still false, the
   product still takes the plain route, and the fix is at the console rather than
   at the flag — touching the parser would change the output *shape* where the
   product only changes its colour.

**The discriminator is the shape, not the byte count.** Strip the ANSI escapes
from the `FORCE_COLOR=1` output: if what remains is byte-identical to the control,
the route did not change and only the paint did.

    uv run -p python3 python .../probes/force_color_shape.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

LEGACY = Path(".venv/bin/ch-legacy").resolve()
ESCAPE = re.compile(rb"\x1b\[[0-9;:]*[A-Za-z]")

VARIANTS = {
    "control (unset)": {},
    "FORCE_COLOR=1": {"FORCE_COLOR": "1"},
    "TTY_COMPATIBLE=1": {"TTY_COMPATIBLE": "1"},
}


def build_home(root: Path) -> Path:
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
    (directory / "00000000-0000-0000-0000-000000000001.jsonl").write_text(body)
    return root


# **Every variable Rich consults, cleared before each run.** The first version of
# this probe popped only `FORCE_COLOR` and `TTY_COMPATIBLE`, so the parent shell's
# `COLORTERM` leaked into every tier and an "eight-bit" run reported truecolor
# bytes. A held parameter nobody chose, inside the instrument built to find them.
AMBIENT = ("FORCE_COLOR", "TTY_COMPATIBLE", "COLORTERM", "NO_COLOR", "TERM")


def run(home: Path, extra: dict[str, str], arguments: list[str]) -> bytes:
    environment = dict(os.environ, HOME=str(home), COLUMNS="100")
    for name in AMBIENT:
        environment.pop(name, None)
    environment.update(extra)
    completed = subprocess.run(
        [str(LEGACY), *arguments],
        capture_output=True,
        env=environment,
        cwd=str(home),
    )
    return completed.stdout


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="force-colour-"))
    try:
        home = build_home(root)
        for shape, arguments in (
            ("list", ["search", "forcecolourneedle", "--list"]),
            ("matches", ["search", "forcecolourneedle"]),
        ):
            print(f"=== {shape}: {' '.join(arguments)}")
            control = run(home, {}, arguments)
            for label, extra in VARIANTS.items():
                output = run(home, extra, arguments)
                stripped = ESCAPE.sub(b"", output)
                verdict = (
                    "SAME SHAPE, colour only"
                    if stripped == control
                    else "SHAPE CHANGED - flags.color flipped"
                )
                print(
                    f"  {label:18} {len(output):5} bytes  "
                    f"{len(ESCAPE.findall(output)):3} escapes  "
                    f"stripped {len(stripped):5}  -> {verdict}"
                )
            print()
        print("If every row says 'SAME SHAPE', `flags.color` never flipped and the")
        print("fix belongs at the console, not at the parser's --color resolution.")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
