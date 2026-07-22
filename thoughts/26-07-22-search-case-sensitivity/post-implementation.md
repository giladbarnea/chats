---
name: search-case-sensitivity-post-implementation
description: Decisions behind explicit case-sensitive and case-insensitive search modes.
date: 2026-07-22
related:
  - ../26-07-12-search-case-insensitive-operators/post-implementation.md
  - ../26-07-15-not-search-operator/post-implementation.md
---

# Search Case-Sensitivity Modes

The default remains case-insensitive, preserving existing searches, while `-s` opts into exact-case matching and `-i` makes the default explicit. Because `search -s` previously meant `--short`, search shortening now requires its unambiguous long form; parse-mode `-s` is unchanged.

Case sensitivity is carried by each compiled `SearchTerm`, making the query the single source of truth for regex evaluation, literal candidate gates, and highlighting. This avoids a split mode where a fast prefilter could reject a result that the final matcher would accept.

Boolean operator recognition remains case-insensitive. The new mode controls term matching only, including positive and negated terms in `NotQuery`.

`tests/test_search_case_sensitivity.py` drove the implementation red-to-green across CLI wiring, mutual exclusion, default compatibility, literals, regexes, and negation. The complete Python and shell suites remained green. `README.md`, `ARCHITECTURE.md`, and `CHANGELOG.md` record the public contract and the `-s` compatibility decision.
