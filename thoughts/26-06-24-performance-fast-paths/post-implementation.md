---
name: performance-fast-paths-post-implementation
description: Why the parse/resolve/search performance pass stayed fallback-first and what should not be refactored away.
date: 2026-06-24
plan: plan.md
---

# Performance Fast Paths — Post-Implementation Notes

This effort landed as four narrow fast paths rather than a new indexing layer. That was deliberate: the slow cases were not fundamentally blocked on Python, they were paying for rich parsing/rendering when the command only needed an identity, a marker facet, or a raw literal absence check.

The most important decision was **fallback-first optimization**. `src/chats/commands/search.py` now rejects safe ASCII literal noncandidates before `read_text`, but survivors still pass through the existing semantic confirmation path. Likewise, the `search . -ll` projection is intentionally tiny: exact dot, `ONLY_ID`, default visibility, no date/dir filters, no role filters, no extra visibility flags. Branchable Claude files and any uncertain projection result fall back to `SessionScan`.

The fragile part was projection semantics. Vega caught that a Claude `<task-notification>`-only session was hidden by the real parser but emitted by the projection. The final projection therefore mirrors the parser’s hidden-content rules for command protocol text, task notifications, tool-only/thinking-only sessions, branch uncertainty, and provider-specific visible text. The real-pool equivalence check compared projected `search . -ll` against the full fallback path: both returned the same 2,132 ids in the same order.

Parse and resolver speedups followed the same principle. `cmd_parse --only-id` resolves identity and stops before reading the body. Explicit JSONL/raw stdin bypasses session lookup entirely, while a single piped id still resolves. Canonical UUID misses now stop after exact-id lookup, and resolution fallback parses only lines that can carry summaries or current titles.

Mechanisms worth preserving:

- `_search_path_candidate_matches` is a conservative byte gate, not a substitute for `_search_conversation_content`.
- `_can_project_dot_only_id` is the safety boundary for projection; broadening it should require new equivalence tests, not confidence.
- `_project_default_dot_match` must stay tri-state so uncertain files can fall back.
- `_looks_like_explicit_content` protects stdin/raw-content performance without breaking one-line id resolution.
- `extract_resolution_facets_from_jsonl` is a marker-line scan; do not turn it back into whole-file JSON decoding for ordinary messages.

Useful context: `ARCHITECTURE.md` search notes and state machines, `README.md` command semantics, and `thoughts/26-05-05-optimize-lookup-performance/initial-context.md`, which framed this as projection-like facet probing rather than a cache.
