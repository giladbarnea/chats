"""Count lone CR (a \r not followed by \n) across the real session pool.

Read-only. Mirrors session-core's C0 measurement method for a different byte class.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, "src")
from chats.parsing import _discover_session_file_rows

files = [row[0] for row in _discover_session_file_rows(include_sidechains=True)]
print("files discovered:", len(files))

lone_cr_files = []
crlf_files = []
any_cr_files = []
unreadable = 0
for p in files:
    try:
        raw = Path(p).read_bytes()
    except OSError:
        unreadable += 1
        continue
    if b"\r" not in raw:
        continue
    any_cr_files.append(p)
    crlf = raw.count(b"\r\n")
    total_cr = raw.count(b"\r")
    if crlf:
        crlf_files.append(p)
    if total_cr > crlf:
        lone_cr_files.append((p, total_cr - crlf))

print("files containing any raw CR byte:", len(any_cr_files))
print("files containing CRLF:", len(crlf_files))
print("files containing a LONE CR:", len(lone_cr_files))
for p, n in lone_cr_files[:10]:
    print("   ", n, p)
print("unreadable:", unreadable)
