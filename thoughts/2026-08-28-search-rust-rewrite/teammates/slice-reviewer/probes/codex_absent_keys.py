#!/usr/bin/env -S uv run
"""Three Codex decoder divergences that all turn on an ABSENT key.

Python supplies a default at each site; the Rust models absence instead.

1. `payload.get("output", "")` -> Python content is "", Rust is Value::Null.
2. `agent_lifecycle_call_ids.add(payload.get("call_id"))` -> Python adds None when
   the key is absent, so a later output with no call_id matches and is SUPPRESSED.
   The Rust only records string ids, so that output RENDERS.
3. `payload.get("call_id") in agent_lifecycle_call_ids` -> the None match above.

Read-only.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

LIFECYCLE = {"spawn_agent", "wait_agent", "close_agent"}
stats = Counter()

for path, provider, _mtime in _discover_session_file_rows(include_sidechains=True):
    if provider != "codex":
        continue
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in content.split("\n"):
        line = line.strip()
        if not line or '"response_item"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "response_item":
            continue
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            continue
        kind = payload.get("type")
        if kind in {"function_call_output", "custom_tool_call_output"}:
            stats[f"{kind} entries"] += 1
            if "output" not in payload:
                stats[f"*** {kind} with NO output key ***"] += 1
            if "call_id" not in payload:
                stats[f"*** {kind} with NO call_id ***"] += 1
            elif not isinstance(payload.get("call_id"), str):
                stats[f"*** {kind} call_id not a string ***"] += 1
        if kind == "function_call":
            stats["function_call entries"] += 1
            if payload.get("name") in LIFECYCLE:
                stats["lifecycle function_call"] += 1
                if "call_id" not in payload:
                    stats["*** lifecycle function_call with NO call_id ***"] += 1
                elif not isinstance(payload.get("call_id"), str):
                    stats["*** lifecycle call_id not a string ***"] += 1
            if "arguments" not in payload:
                stats["function_call with NO arguments key"] += 1

for key, value in stats.most_common():
    print(f"{value:9d}  {key}")
