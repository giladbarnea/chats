---
name: claude-read-path-post-implementation
description: Why current Claude Read paths are normalized at the provider boundary.
date: 2026-07-26
---

# Claude Read paths now survive every output mode

Claude Code 2.1.220 records `Read` inputs under `path`, while `ch` renders the shared `Read` contract through canonical `file_path`. Structured JSON retained the native value, but schema-based plain and colored views silently lost it.

The fix normalizes the alias in the Claude adapter rather than widening each renderer. This preserves one downstream tool contract, keeps existing native `file_path` inputs valid, and restores the path consistently in plain/XML, structured, and colored output.

Active synthetic Claude fixtures now use the current provider shape. Historical captured sessions remain truthful records, while provider-free and canonical transport fixtures continue using `file_path` because they exercise the downstream contract rather than Claude ingestion.

Regression coverage in `tests/test_colored_rendering.py`, `tests/test_parse_visibility_flags.py`, and `tests/test_tool_filter.sh` protects the public rendering and visibility paths. `ARCHITECTURE.md` documents the provider-adapter normalization boundary that made this the narrowest fix.
