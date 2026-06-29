---
date: 2026-06-29
feature: search-role-only-filters
---
# Search role-only filters

`ch search` now exposes `--only-user` and `--only-assistant`, but the important decision was not to reinterpret the whole search index as role-scoped.

The existing search model has three facets: rendered visible messages, summaries, and the current title. Historical tests in `tests/test_session_scan.py` and `tests/test_session_search_space.py` already protect the invariant that summaries and current titles remain searchable even when message visibility hides assistant text. I kept that invariant. The new flags narrow regular message matches and rendered matching-message output; they do not suppress title or summary hits. `tests/test_search_visibility.py` now pins that behavior directly with summary-only and title-only role-filtered hits.

The other decision was to reuse the parse-mode normalization semantics. An `--only-*` search disables contradictory extras such as thinking, tools, agents, plans, and all, with the same warning shape parse already uses. That keeps downstream code receiving one clean `ConversationFlags.message_selection` value instead of spreading CLI contradiction handling into search.

A post-implementation `claudeox` review found no correctness bugs and agreed that leaving `search.py` untouched was the simplest shape. The one smell it noted was the explicit search-side defaults for unsupported `--no-user` / `--no-assistant`; I left them at the call site because they make the parse/search difference visible without changing shared helper semantics.

Useful context came from `README.md`, `ARCHITECTURE.md`, the original parse-mode role visibility commit `52f4b760`, and the later `MessageSelection` refactor `ba79de50`.
