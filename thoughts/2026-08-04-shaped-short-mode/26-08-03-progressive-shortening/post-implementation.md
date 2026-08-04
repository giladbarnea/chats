---
date: 2026-08-03
task: progressive-shortening
---

# Progressive shortening

[SHORT_SPEC.md](../../SHORT_SPEC.md) owns the shortening grammar and sequence. [TOOL_SPEC.md](../../TOOL_SPEC.md) still owns tool matching, specificity, and tie-breaking.

Global and local progressive policies share one message union sequence. This avoids independent ramps that would assign different conversation positions to related payloads.

Parse assigns the sequence after message slicing. Search assigns it before match filtering, so matches-only output keeps the same positions as full output.

The detached-slice follow-up preserved `-s 7` and `-s 32:64` after an input as bare fixed-500 shortening plus selectors. Attached invalid short values remain strict.
