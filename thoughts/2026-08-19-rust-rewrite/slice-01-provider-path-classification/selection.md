---
date: 2026-08-19
title: Slice one selection
---

# Slice one selection

Slice one replaces native provider-path classification with Rust.

The stable boundary takes a session source path and returns `claude`, `pi`, `codex`, or no native match. `get_jsonl_session_adapter()` keeps its current interface and its first-entry fallback for external JSONL files.

This is the highest-impact small boundary found in the current runtime. The live pool contains 4,838 session files. One Python classification pass costs about 350 ms, and the failing date flows make about two passes. A standalone Rust prototype classified and statted the pool in 68–73 ms. The expected saving is about 550–600 ms per affected command.

The backward timestamp scanner is the next-largest isolated cost. It was rejected for slice one because its Rust prototype saved only 120–220 ms. That gain would not close either current performance gap.

Slice one does not change file discovery, timestamp scanning, JSONL parsing, provider behavior, or any CLI output.
