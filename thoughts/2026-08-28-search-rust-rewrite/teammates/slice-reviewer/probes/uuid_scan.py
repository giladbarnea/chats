"""Measure the reachability of three branch_map key-shape divergences.

(a) an entry carrying a `uuid` key whose value is not a string
(b) an entry carrying a `leafUuid` whose value is not a string
(c) an empty-string uuid / leafUuid (the truthiness sites)
Read-only over the real pool.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

rows = list(_discover_session_file_rows(include_sidechains=True))
print("files:", len(rows))

non_str_uuid = 0
empty_uuid = 0
non_str_leaf = 0
empty_leaf = 0
null_uuid = 0
files_hit = set()
entries_seen = 0
files_scanned = 0

for path, *_ in rows:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    files_scanned += 1
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
        entries_seen += 1
        if "uuid" in entry:
            v = entry["uuid"]
            if v is None:
                null_uuid += 1; files_hit.add(path)
            elif not isinstance(v, str):
                non_str_uuid += 1; files_hit.add(path)
            elif v == "":
                empty_uuid += 1; files_hit.add(path)
        if "leafUuid" in entry:
            v = entry["leafUuid"]
            if not isinstance(v, str):
                non_str_leaf += 1; files_hit.add(path)
            elif v == "":
                empty_leaf += 1; files_hit.add(path)

print("files scanned:", files_scanned, "entries:", entries_seen)
print("uuid present but null      :", null_uuid)
print("uuid present, non-str non-null:", non_str_uuid)
print("uuid empty string          :", empty_uuid)
print("leafUuid non-str           :", non_str_leaf)
print("leafUuid empty string      :", empty_leaf)
print("files affected             :", len(files_hit))
