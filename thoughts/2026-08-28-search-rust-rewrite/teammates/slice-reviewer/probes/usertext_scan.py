"""Narrow the measurement to the surface the site actually consumes.

`_parse_command_tag_lines` runs only on USER message text blocks. Counting every
string value in the corpus would overstate it by orders of magnitude -- most of the
hits are binary tool OUTPUT, which never reaches this site.

Also separates this team's own sessions from ordinary usage, because several of the
richest hits are transcripts of this very mission discussing these characters.
Read-only.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

NONLF = "".join(chr(c) for c in (0x0B,0x0C,0x0D,0x1C,0x1D,0x1E,0x85,0x2028,0x2029))
MISSION = ("search-rust-rewrite", "slice-reviewer", "preserve-because-wrong",
           "context-curator", "search-firstmate")

def user_text_blocks(entry):
    if entry.get("type") != "user":
        return
    message = entry.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return
    content = message.get("content")
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                yield item["text"]

hits = Counter(); files = {}
lone_cr = 0
mission_files = set(); ordinary_files = set()
blocks = 0

for p, *_ in _discover_session_file_rows(include_sidechains=True):
    try:
        content = Path(p).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    is_mission = any(marker in content for marker in MISSION)
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if not isinstance(entry, dict):
            continue
        for text in user_text_blocks(entry):
            blocks += 1
            for ch in NONLF:
                n = text.count(ch)
                if not n:
                    continue
                hits[ch] += n
                files.setdefault(ch, set()).add(p)
                (mission_files if is_mission else ordinary_files).add(p)

print("user text blocks scanned:", blocks)
print()
print(f"{'char':8s} {'occurrences':>12s} {'files':>7s}")
for ch in NONLF:
    if hits[ch]:
        print(f"U+{ord(ch):04X}  {hits[ch]:12d} {len(files.get(ch,())):7d}")
print()
print("files with a hit that are THIS MISSION's own transcripts:", len(mission_files))
print("files with a hit that are ordinary usage            :", len(ordinary_files - mission_files))
for p in sorted(ordinary_files - mission_files)[:10]:
    print("   ", Path(p).name)
