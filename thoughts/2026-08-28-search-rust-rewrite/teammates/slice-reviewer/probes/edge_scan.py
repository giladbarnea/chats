"""Two questions, separately.

Q1 (the strip question, L47's premise): does a decoded string value carry one of the
    ten separators AT AN EDGE?
Q2 (the splitlines question, unasked so far): does a decoded string value carry one
    ANYWHERE -- and what do those strings actually look like?
Read-only. Instances dumped, per 22c.
"""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

SEPS = "".join(chr(c) for c in (0x0A,0x0B,0x0C,0x0D,0x1C,0x1D,0x1E,0x85,0x2028,0x2029))
NONLF = "".join(c for c in SEPS if c != "\n")
C0STRIP = "".join(chr(c) for c in range(0x1C, 0x20))   # what L47 measured

edge_any = Counter(); edge_files = set()
edge_c0 = 0; edge_c0_files = set()
samples = []
seen_kinds = set()

rows = list(_discover_session_file_rows(include_sidechains=True))
for p, *_ in rows:
    try:
        content = Path(p).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        stack = [entry]
        while stack:
            v = stack.pop()
            if isinstance(v, dict):
                stack.extend(v.values()); continue
            if isinstance(v, list):
                stack.extend(v); continue
            if not isinstance(v, str) or not v:
                continue
            if v[0] in NONLF or v[-1] in NONLF:
                edge_any[v[0] if v[0] in NONLF else v[-1]] += 1
                edge_files.add(p)
            if v[0] in C0STRIP or v[-1] in C0STRIP:
                edge_c0 += 1; edge_c0_files.add(p)
            for ch in NONLF:
                if ch in v and ch not in seen_kinds and len(samples) < 12:
                    seen_kinds.add(ch)
                    i = v.index(ch)
                    samples.append((f"U+{ord(ch):04X}", Path(p).name, repr(v[max(0,i-45):i+45])))

print("Q1  string values with a non-LF splitlines separator AT AN EDGE :", sum(edge_any.values()),
      f"({len(edge_files)} files)")
for ch, n in sorted(edge_any.items(), key=lambda kv: -kv[1]):
    print(f"      U+{ord(ch):04X}: {n}")
print("Q1b string values with U+001C-001F at an edge (L47's measure)   :", edge_c0,
      f"({len(edge_c0_files)} files)")
print()
print("Q2  instances, one per character (22c: read them, do not report the aggregate):")
for kind, fname, sample in sorted(samples):
    print(f"  {kind}  {fname}")
    print(f"        {sample}")
