#!/usr/bin/env -S uv run
"""Reachability of four Codex script-parser divergences found by reading.

1. Duplicate `const <name> = "...";` bindings. Python builds a DICT (last wins);
   the Rust builds a Vec and `.find()`s (FIRST wins). 22t's max-first/max-last
   hazard in a new place.
2. An object item with an EMPTY value, `{a: }`. Python's property regex needs
   `.+` so the whole object is unparsed and the envelope stays `exec` -> `Bash`;
   the Rust's `split_once(':')` yields `""` and the call parses.
3. A lone backtick as a scalar. Python's startswith/endswith both match one
   character and yield `""`; the Rust guards on `len() >= 2` and yields "`".
4. Two or more `exec_command` calls sharing an explicitly NULL `workdir` /
   `yield_time_ms` / `max_output_tokens`. Python's `values[0] is not None` drops
   it; the Rust's `Some(&Value::Null)` keeps it.

Read-only.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from chats.parsing import (
    _CODEX_SCRIPT_STRING_BINDING_PATTERN,
    _CODEX_SCRIPT_TOOL_CALL_PATTERN,
    _discover_session_file_rows,
)

stats = Counter()
samples = []


def scripts_in(entry: dict):
    """Every generated exec script an entry carries."""
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        return
    if payload.get("type") not in {"custom_tool_call", "function_call"}:
        return
    for key in ("input", "arguments"):
        value = payload.get(key)
        if isinstance(value, str) and "tools." in value:
            yield value


for path, provider, _mtime in _discover_session_file_rows(include_sidechains=True):
    if provider != "codex":
        continue
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in content.split("\n"):
        line = line.strip()
        if not line or "tools." not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict):
            continue
        for script in scripts_in(entry):
            stats["generated scripts seen"] += 1
            names = [b.group("name") for b in _CODEX_SCRIPT_STRING_BINDING_PATTERN.finditer(script)]
            if len(names) != len(set(names)):
                stats["*** duplicate const binding name — first/last differ ***"] += 1
                if len(samples) < 3:
                    samples.append((Path(path).name, script[:200]))
            calls = list(_CODEX_SCRIPT_TOOL_CALL_PATTERN.finditer(script))
            if len(calls) > 1:
                stats["scripts with more than one tools.* call"] += 1
            if re.search(r"\{[^{}]*[A-Za-z_]\w*\s*:\s*[,}]", script):
                stats["*** object item with an empty value ***"] += 1
            if re.search(r"[A-Za-z_]\w*\s*:\s*`[^`]*$", script):
                stats["scalar opening a backtick without closing it"] += 1
            if re.search(r"\b(workdir|yield_time_ms|max_output_tokens)\s*:\s*null", script):
                stats["*** explicitly null shared key ***"] += 1

for key, value in stats.most_common():
    print(f"{value:8d}  {key}")
for name, sample in samples:
    print(f"\n  {name}\n     {sample!r}")
