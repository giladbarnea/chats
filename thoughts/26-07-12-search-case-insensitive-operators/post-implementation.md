---
name: search-case-insensitive-operators-post-implementation
description: Why boolean search operators became case-insensitive.
date: 2026-07-12
supersedes: ../26-06-10-search-boolean-operators/post-implementation.md
---

# Case-Insensitive Search Operators

The reported false negative looked quote-related, but reproduction isolated uppercase `OR` as the cause: both supported quote delimiters already behaved identically.

Operator recognition now normalizes each token before classifying it while preserving the original term text. This keeps the parser, precedence, candidate filtering, and matching pipeline unchanged.

`tests/test_search_operators.py::test_all_operators_are_case_insensitive` drove the change red-to-green and covers lowercase and uppercase forms of both operators. Existing quoted-term and precedence coverage remained green.

The public contract in `README.md` and the current invariant in `ARCHITECTURE.md` now describe operators as case-insensitive. The original implementation notes remain useful historical context and link here for the follow-up.
