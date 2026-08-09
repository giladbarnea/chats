---
name: search-boolean-operators-post-implementation
description: How `and`/`or` search operators were added, key decisions and trade-offs.
date: 2026-06-10
status: historical
follow_up: ../26-07-12-search-case-insensitive-operators/post-implementation.md
---

# Search `and`/`or` Operators — Post-Implementation Notes

> Historical record. Since 2026-08-09, only exact uppercase `AND`, `OR`, and `NOT` tokens are operators. See [README.md](../../README.md#boolean-operators).

New module `src/chats/search_query.py` (tokenizer + recursive-descent parser producing
`SearchTerm`/`AndQuery`/`OrQuery`) plugged into `commands/search.py`. Behavior pinned by
`tests/test_search_operators.py` (15 tests, TDD).

Decisions and the whys:

- **Boolean interpretation triggers only when a bare lowercase `and`/`or` word token AND at
  least one operand token are present.** Everything else — including unterminated quotes,
  regex parens like `deploy-(prod|staging)`, uppercase `AND`, and a bare `and` pattern —
  falls back to the existing single-regex semantics. Recall was the priority: previously-valid
  plain patterns must not start erroring.
- **Quotes open a term only at a token boundary**, so mid-word apostrophes (`don't panic`)
  stay plain words instead of tripping the tokenizer.
- **General grammar instead of enumerating the spec's allowed shapes.** A tiny `or`-over-`and`
  recursive descent with parens is less code than form whitelisting, and naturally covers
  `A and (B or C)`, three-term chains, and standard precedence (`and` binds tighter).
- **Session-scoped evaluation**: a term is satisfied by a match anywhere in the session
  (summaries, current title, or any rendered message), so `and` terms may match in different
  messages. Displayed matches are the union of messages matching any term.
- **The literal candidate prefilter generalized per-term** by evaluating the same query tree
  over per-term raw-content plausibility. One gotcha: an eager `content.casefold()` per
  candidate file regressed `test_search_mafter_4h_list_under_1000ms` (pattern `.` never needed
  it before); fixed by making the casefold lazy via `functools.cache(content.casefold)`.
- **Invalid boolean queries (unquoted multi-word terms, dangling operators, unbalanced parens)
  exit 2** with a quoting hint, distinct from exit 1 for "no matches".

Drift/cleanup along the way: `_is_plain_literal_search_pattern` moved into `search_query.py`;
the private seams `_search_hit_for_file` and `_search_conversation_content` now take a
`SearchQuery` instead of `(regex, pattern_arg, literal_candidate)`, which required updating two
fakes in `tests/test_search_orchestration.py`. Contrary to the task brief, no test hardcoded
`~/dev/chats`; the only repo-path-ish dependency is `~/.claude` in `test_search_perf.py`, which
is intentional (commit c42ec4b).
