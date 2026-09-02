#!/usr/bin/env -S uv run
"""Pi `toolResult` entries with no `content` key.

Python injects a default: `"content": message_data.get("content", [])`, so the key is
ALWAYS present and `shorten_data`'s `"content" in tool` test always fires.
rust/session.rs:1567-1568 sets `content: None, has_content: false` when the key is
absent, which models a state Python's Pi path cannot produce.

The Claude path is faithful — Python keeps `{**item}` there, so presence is genuine.
Only the Pi path injects. Read-only.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

stats = Counter()
samples = []

for path, provider, _mtime in _discover_session_file_rows(include_sidechains=True):
    if provider != "pi":
        continue
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in content.split("\n"):
        line = line.strip()
        if not line or '"toolResult"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "message":
            continue
        message = entry.get("message")
        if not isinstance(message, dict) or message.get("role") != "toolResult":
            continue
        stats["pi toolResult entries"] += 1
        if "content" not in message:
            stats["*** no `content` key — Python defaults to [], Rust has_content=false ***"] += 1
            if len(samples) < 5:
                samples.append((Path(path).name, sorted(message)))
        elif message.get("content") is None:
            stats["`content` present and null"] += 1
        elif message.get("content") == []:
            stats["`content` present and empty"] += 1

for key, value in stats.most_common():
    print(f"{value:8d}  {key}")
if samples:
    print("\ninstances (22c) — the keys each such message_data actually carries:")
    for name, keys in samples:
        print(f"  {name}: {keys}")
