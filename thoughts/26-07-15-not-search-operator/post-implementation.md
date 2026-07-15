---
name: not-search-operator-post-implementation
description: How the NOT search operator was added, key decisions and trade-offs.
date: 2026-07-15
related: ../26-06-10-search-boolean-operators/post-implementation.md
---

# NOT Search Operator — Post-Implementation Notes

Added `NotQuery` node to the existing `search_query.py` AST alongside `SearchTerm`,
`AndQuery`, `OrQuery`. Parsed by a flat `_parse_not_query` function, deliberately
separate from the recursive-descent `_Parser` that handles `and`/`or`. Pinned by 7
new tests in `test_search_operators.py` (TDD), total now 22.

Decisions and the whys:

- **Separate flat parser instead of extending `_Parser`.** The user scope is `term
  [NOT term ...]` — no parens, no mixing with `and`/`or`. A flat loop is ~30 lines
  and matches exactly this grammar; threading NOT into the recursive-descent precedence
  chain would add complexity for a shape the feature deliberately doesn't support yet.
  When mixed operators are added later, `_parse_not_query` can be retired and NOT
  folded into `_Parser` as a unary prefix at the atom level.

- **Mixed-operator rejection lives in `parse_search_query`, not the parsers.** One
  early guard (`has_and_or and has_not → error`) routes cleanly to the right parser
  and gives a clear error. No parser ever sees tokens from the other operator family.

- **`NotQuery.iter_terms()` yields nothing.** `iter_terms()` feeds two downstream
  consumers: highlight regex and display-match selection. Negated terms should
  contribute to neither — you want to see *what matched*, not what was excluded.
  The real evaluation (session exclusion) goes through `evaluate()`, which correctly
  negates.

- **Prefilter conservatism via `_evaluate_prefilter`.** The byte and raw-content
  candidate gates (`_search_path_candidate_matches`, `_search_candidate_matches`)
  are sound because their `term_matches` callbacks return True conservatively ("could
  match"). `NotQuery.evaluate` inverts this: `not True → False`, which would falsely
  reject files. Rather than making `evaluate` context-aware, a separate
  `_evaluate_prefilter` in `commands/search.py` short-circuits `NotQuery → True`.
  This keeps the AST nodes clean and the prefilter/real-match split explicit.

- **`SearchQuery` type union updated** to include `NotQuery`. The `_evaluate_prefilter`
  function uses `isinstance` dispatch rather than the polymorphic `evaluate`, which is
  the one place where the concrete types are inspected outside the AST — acceptable
  for a prefilter optimization that's inherently type-aware.
