---
name: negative-index-jsonl-recency-post-implementation
description: Why recent negative selectors now use transcript timestamps instead of filesystem mtime.
date: 2026-06-27
---

# Negative Index JSONL Recency — Post-Implementation Notes

The change moved recent negative selectors back to the semantic meaning users expect: `ch -1` now means the session whose transcript says it was modified last, not the file the filesystem happened to touch last.

The implementation stayed deliberately narrow. `_resolve_recent_conversation_file` now excludes sidechains before any timestamp read, applies the cwd probe before timestamp sorting, and orders the remaining candidates with `get_jsonl_last_timestamp`, which already provides the efficient backward timestamp probe used elsewhere in metadata and date filtering. That preserved the cheap path: no full metadata construction, no full parse, and no timestamp probes for excluded sidechains or non-matching directories.

The main decision was to keep the existing filesystem fallback for sessions with no readable in-band timestamp. That fallback is not the primary truth anymore; it is only the ordering backstop for malformed or legacy files, matching the timestamp helpers already used by metadata display.

The regression coverage in `tests/test_recent_index_orchestration.py` now protects both the direct mismatch case and the directory-filtered short-circuit order. The current docs in `README.md`, `ARCHITECTURE.md`, and `CHANGELOG.md` were updated to remove the old stat-mtime contract while keeping search streaming documented as filesystem-mtime ordered.
