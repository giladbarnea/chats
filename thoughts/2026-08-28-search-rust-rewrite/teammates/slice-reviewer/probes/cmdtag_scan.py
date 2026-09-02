"""Reachability of the two command-tag divergences, over the surface that consumes them.

A. `expand_tabs`: a flat 4 per tab vs Python's `expandtabs(4)` tab stops. They differ
   only when a space precedes a tab in the indent.
B. `dedent`: only runs when a tag value contains a newline.
Read-only.
"""
import json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows, _COMMAND_TAG_LINE_PATTERN

def user_text_blocks(entry):
    if entry.get("type") != "user": return
    m = entry.get("message")
    if not isinstance(m, dict) or m.get("role") != "user": return
    c = m.get("content")
    if isinstance(c, str): yield c
    elif isinstance(c, list):
        for item in c:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                yield item["text"]

stats = Counter()
indent_shapes = Counter()
multiline_examples = []

for p, *_ in _discover_session_file_rows(include_sidechains=True):
    try: content = Path(p).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError): continue
    for line in content.split("\n"):
        line = line.strip()
        if not line: continue
        try: entry = json.loads(line)
        except Exception: continue
        if not isinstance(entry, dict): continue
        for text in user_text_blocks(entry):
            if "<command-" not in text: continue
            stats["blocks mentioning <command-"] += 1
            ok = True
            rows = []
            for raw in text.splitlines():
                if not raw.strip(): continue
                mt = _COMMAND_TAG_LINE_PATTERN.fullmatch(raw)
                if mt is None:
                    ok = False; break
                rows.append(mt)
            if not ok or not rows:
                stats["not a pure command-tag block"] += 1
                continue
            stats["pure command-tag blocks"] += 1
            for mt in rows:
                ind = mt.group("indent")
                indent_shapes[repr(ind)] += 1
                if "\t" in ind:
                    stats["indent contains a tab"] += 1
                    if len(ind.expandtabs(4)) != sum(4 if ch=="\t" else 1 for ch in ind):
                        stats["*** expandtabs DIVERGES ***"] += 1
                val = mt.group("value")
                if "\n" in val.strip():
                    stats["multi-line value (dedent runs)"] += 1
                    if len(multiline_examples) < 3:
                        multiline_examples.append((Path(p).name, val[:160]))
                    lines = [l for l in val.strip().split("\n") if l and not l.isspace()]
                    leads = {re.match(r"[ \t]*", l).group(0) for l in lines}
                    if any("\t" in l for l in leads) and any(l.startswith(" ") for l in leads):
                        stats["*** dedent tab/space mix ***"] += 1
                    if any(l.isspace() for l in val.strip().split("\n") if l):
                        stats["*** dedent whitespace-only interior line ***"] += 1

for k, v in stats.most_common():
    print(f"{v:8d}  {k}")
print()
print("indent shapes seen:", dict(indent_shapes.most_common(8)))
print()
for name, sample in multiline_examples:
    print(f"  multi-line value in {name}: {sample!r}")
