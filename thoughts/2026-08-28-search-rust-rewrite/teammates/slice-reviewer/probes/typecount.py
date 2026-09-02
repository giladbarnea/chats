import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

types = Counter(); roles = Counter(); provider_files = Counter()
for p, prov, _m in _discover_session_file_rows(include_sidechains=True):
    provider_files[prov] += 1
    try:
        content = Path(p).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in content.split("\n"):
        line = line.strip()
        if not line: continue
        try: e = json.loads(line)
        except Exception: continue
        if not isinstance(e, dict): continue
        types[e.get("type")] += 1
        if e.get("type") == "user":
            m = e.get("message")
            roles[(type(m).__name__, m.get("role") if isinstance(m, dict) else None,
                   type(m.get("content")).__name__ if isinstance(m, dict) else None)] += 1
print("provider file counts:", dict(provider_files))
print()
print("top entry types:")
for t, n in types.most_common(15):
    print(f"  {t!r:28s} {n}")
print()
print("shape of type=='user' entries:")
for k, n in roles.most_common(10):
    print("  ", k, n)
