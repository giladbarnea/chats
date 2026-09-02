"""How often do the ten `str.splitlines()` separators appear in DECODED string values?

session-core measured U+001C-001F over raw file bytes and found zero. That covers
four of the ten characters `str.splitlines()` splits on, and it measures raw bytes
rather than decoded JSON strings -- where U+000C arrives as the standard JSON
escape \f and U+2028 as  , neither of which is a raw byte in the file.
Read-only.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

SEPS = [0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029]
NON_LF = [c for c in SEPS if c not in (0x0A,)]

counts = Counter()
files_with = {c: set() for c in SEPS}

def walk(value, path):
    if isinstance(value, str):
        for cp in NON_LF:
            n = value.count(chr(cp))
            if n:
                counts[cp] += n
                files_with[cp].add(path)
    elif isinstance(value, dict):
        for v in value.values():
            walk(v, path)
    elif isinstance(value, list):
        for v in value:
            walk(v, path)

rows = list(_discover_session_file_rows(include_sidechains=True))
scanned = 0
for p, *_ in rows:
    try:
        content = Path(p).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    scanned += 1
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        walk(entry, p)

print("files scanned:", scanned)
print()
print(f"{'char':10s} {'occurrences':>12s} {'files':>8s}")
for cp in NON_LF:
    print(f"U+{cp:04X}    {counts[cp]:12d} {len(files_with[cp]):8d}")
