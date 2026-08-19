---
date: 2026-08-19
title: Slice one contract
---

# Slice one contract

The native classifier receives a session path and the active home directory. It returns the provider for these canonical containment roots:

- `~/.codex/sessions` returns `codex`.
- `~/.pi` returns `pi`.
- `~/.claude/projects` returns `claude`.
- A path outside these roots returns no native match.

Canonical containment must preserve `Path.resolve(strict=False)` behavior. It follows symlinks through the longest existing ancestor and keeps a missing path tail. Provider precedence stays Codex, then Pi, then Claude.

`get_jsonl_session_adapter()` remains the Python interface. A native-path match takes precedence over conflicting file content. If no native path matches, Python still detects Codex and Pi from the first JSONL entry. Unknown external JSONL still fails clearly.

Rust is the only native-path classifier after this slice. The replaced Python classifier functions and any fallback implementation must be absent.

Success requires unchanged provider behavior, a measurable classification speedup, passing Rust and Python builds, installable wheel and source packages, and no new full-baseline failure.
