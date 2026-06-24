---
name: performance-fast-paths-plan
description: Red-team-approved plan for worst-case `ch` performance improvements.
date: 2026-06-24
post_implementation: post-implementation.md
---

# Performance Fast Paths — Plan

The team plan targeted worst-case waste across `ch` without introducing a persistent index, parallel scanner, or Rust rewrite. The recurring root cause was that commands needing only a small fact were paying for whole-file reads, JSONL decoding, message construction, or rendered XML confirmation.

Approved slices:

- Parse/resolve should skip global session discovery for explicit stdin/content and should print `--only-id` after resolving the path, without reading the session body.
- Resolver misses should fail fast for canonical UUIDs after exact-id lookup, and title/summary fallback should JSON-parse only lines that can carry resolution facets.
- Plain ASCII literal search should use a chunked byte candidate gate before `read_text`, while preserving semantic confirmation for survivors and falling back for non-ASCII, regex, and render-dependent terms.
- `search . -ll` may use a narrow projection only for `ONLY_ID`, exact dot, default visibility, no dir/date filters, and no role/extra visibility flags. Every uncertain case must fall back to the existing `SessionScan` path.

The explicit non-goal was a general projection/indexing framework. The work was meant to remove current Python algorithmic waste while keeping the implementation small enough to audit.
