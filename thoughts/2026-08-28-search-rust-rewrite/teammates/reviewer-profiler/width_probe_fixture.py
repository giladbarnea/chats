"""Seed a fixture home with content that can express a cell-width difference.

Adding `UNICODE_VERSION` as a sweep row against an all-ASCII fixture produces a
row that reads "neither route responds" — a false clear, and exactly the trap
of a measurement narrower than the claim it supports. The contract fixture home
holds 12,572 characters and not one of them is non-ASCII.

The probe characters are *derived* from the table delta rather than chosen for
looking exotic. Picking by intuition already produced one false negative here:
arrows, stars and circled digits are all width-stable across the tables.
"""

from __future__ import annotations

import json
import pathlib
import sys
from pathlib import Path

PROBE_SESSION = "aaaaaaaa-1111-4111-8111-111111111111"


GENERATOR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "views-and-colour" / "probes" / "generate_cell_oracle.py"
)


def differing_codepoints(limit: int = 24) -> str:
    """Characters whose cell width differs between the newest and oldest tables.

    Delegates to `views-and-colour`'s `differing_between`, which sweeps 0..0x1FB00
    for an arbitrary pair. My own version scanned U+2000..U+32FF and found 29 of a
    true 2,350 — about 1.2% of the delta, and the part it missed is mostly outside
    the BMP symbol ranges. Deleted rather than kept beside theirs.
    """
    import importlib.util

    specification = importlib.util.spec_from_file_location("generate_cell_oracle", GENERATOR)
    module = importlib.util.module_from_spec(specification)
    sys.modules["generate_cell_oracle"] = module
    specification.loader.exec_module(module)
    return "".join(module.differing_between("9.0.0", "latest", limit=limit))


def seed(home: Path) -> str:
    """Add one session whose headline carries width-unstable characters."""
    sample = differing_codepoints()
    directory = home / ".claude" / "projects" / "widthprobe"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{PROBE_SESSION}.jsonl").write_text(
        json.dumps({
            "type": "user",
            "uuid": "u1",
            "parentUuid": None,
            "timestamp": "2026-08-20T10:00:00.000Z",
            "cwd": "/tmp",
            "message": {"role": "user", "content": "needle five " + sample * 3},
        }) + "\n",
        encoding="utf-8",
    )
    return sample
