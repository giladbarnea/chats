#!/usr/bin/env python3
"""Generate an oracle table for `resolve_tool_visibility`.

`session-core` flagged this seam themselves: the 2006-case differential covers
`parse_tool_spec` only. The reason is structural rather than an oversight —
`resolve_tool_visibility` is not exposed through PyO3, so there is no way to
call both implementations from one process and compare. The only half reachable
from Python is the half that was tested.

A table oracle closes it without exposing production surface. Python computes
the answer for every case here; a Rust test asserts against the same table. The
untested behaviour is specificity ties going to the later filter, so the space is
built to produce ties in quantity rather than to look broad.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/giladbarnea/dev/chats/src")
from chats.tool_filter import (  # noqa: E402
    DEFAULT_SHORT_MAX_CHARS,
    parse_tool_spec,
    resolve_tool_visibility,
)

SPECS = [
    "Bash", "o", "!Bash", "Bash:s=100", "Bash:s=200", "s=300",
    "o:s=400", "Bash:o:s=500", "e:s=600", "Bash:o:e:s=700", "Read:s=800",
]

TOOLS = {
    "bash_use": {"type": "tool_use", "name": "Bash", "id": "t1"},
    "bash_result_ok": {"type": "tool_result", "tool_use_id": "t1", "is_error": False},
    "bash_result_error": {"type": "tool_result", "tool_use_id": "t1", "is_error": True},
    "read_use": {"type": "tool_use", "name": "Read", "id": "t2"},
    "read_result_error": {"type": "tool_result", "tool_use_id": "t2", "is_error": True},
}
ID_MAP = {"t1": "Bash", "t2": "Read"}


def native_tool(name: str, tool: dict) -> dict:
    """The same tool in the Rust FilterableTool shape."""
    return {
        "is_input": tool["type"] == "tool_use",
        "name": tool.get("name"),
        "tool_use_id": tool.get("tool_use_id"),
        "is_error": tool.get("is_error", False),
    }


def main() -> int:
    cases = []
    ties = 0
    for length in (1, 2, 3):
        for combination in itertools.product(SPECS, repeat=length):
            filters = [parse_tool_spec(spec) for spec in combination]
            for tool_name, tool in TOOLS.items():
                show, policy = resolve_tool_visibility(tool, filters, ID_MAP)
                cases.append({
                    "specs": list(combination),
                    "tool": tool_name,
                    "native_tool": native_tool(tool_name, tool),
                    "show": show,
                    "max_chars": policy.max_chars if policy else None,
                    "progressive": policy.progressive if policy else None,
                })
            # A tie is two matching short filters of equal specificity.
            shorts = [f for f in filters if f.short]
            specificities = [
                sum([f.name is not None, f.direction is not None, f.error_only]) for f in shorts
            ]
            if len(specificities) > 1 and len(set(specificities)) < len(specificities):
                ties += 1

    payload = {
        "oracle": "resolve_tool_visibility",
        "oracle_state": "HEAD 8cb4c5f, oracle route digest sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (tests/oracle_digest.py::oracle_route_digest)",
        "default_short_max_chars": DEFAULT_SHORT_MAX_CHARS,
        "id_map": ID_MAP,
        "cases": cases,
    }
    out = Path(__file__).parent / "tool_visibility_oracle.json"
    out.write_text(json.dumps(payload, indent=1))

    shown = sum(1 for c in cases if c["show"])
    with_policy = sum(1 for c in cases if c["max_chars"] is not None)
    limits = sorted({c["max_chars"] for c in cases if c["max_chars"] is not None})
    print(f"cases          : {len(cases)}")
    print(f"spec lists      : {len(cases) // len(TOOLS)}  (of which {ties} contain a specificity tie)")
    print(f"visible / hidden: {shown} / {len(cases) - shown}")
    print(f"carry a policy  : {with_policy}")
    print(f"distinct limits : {limits}")
    print(f"written         : {out.name} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
