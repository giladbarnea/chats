#!/usr/bin/env -S uv run
"""Claude assistant entries whose ONLY content is an empty or whitespace thinking block.

`codex.rs:278`'s `has_content` tests `thinking.is_some()`; `session.rs:1137`'s tests
`is_some_and(|v| !v.is_empty())`, which is what Python's `bool(self.thinking)` means.
The codex.rs doc comment calls them "the same predicate" and proposes promoting the
codex.rs one to `model.rs` as a five-line change.

If that promotion lands, every entry counted here starts rendering as an empty
assistant message that Python drops. This measures the blast radius of a refactor
that is currently documented as safe. Read-only.
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
    if provider != "claude":
        continue
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in content.split("\n"):
        line = line.strip()
        if not line or '"thinking"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        items = message.get("content")
        if not isinstance(items, list):
            continue
        thinking_values = [
            item.get("thinking", "")
            for item in items
            if isinstance(item, dict) and item.get("type") == "thinking"
        ]
        if not thinking_values:
            continue
        stats["assistant entries carrying a thinking block"] += 1
        # Python and session.rs keep only the LAST thinking block.
        last = thinking_values[-1]
        if not isinstance(last, str) or last.strip():
            continue
        stats["last thinking block is empty or whitespace"] += 1
        others = [
            item for item in items
            if isinstance(item, dict) and item.get("type") in {"text", "tool_use"}
        ]
        texts = [i for i in others if i.get("type") == "text" and str(i.get("text", "")).strip()]
        if not texts and not [i for i in others if i.get("type") == "tool_use"]:
            stats["*** and nothing else — Python drops it, the promoted predicate keeps it ***"] += 1
            if len(samples) < 5:
                samples.append((Path(path).name, repr(last)[:60], sorted({i.get("type") for i in items if isinstance(i, dict)})))

for key, value in stats.most_common():
    print(f"{value:8d}  {key}")
if samples:
    print("\ninstances (22c):")
    for name, value, kinds in samples:
        print(f"  {name}: last thinking={value} block types={kinds}")
