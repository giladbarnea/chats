---
updated: 2026-07-12
---
# Bash result panels use semantic presentation labels

Colored parse and search views now label a user-role envelope containing only visible Bash results as `Bash`, using the existing tool-result hue. This removes a misleading transport-level `User` label without changing the underlying conversation model.

The change is deliberately narrow. Mixed messages containing genuine user text remain `User`, and output from other tools remains unchanged. Classification happens from visible rendered parts and requires the ordinary user wrapper, so explicit wrappers such as agent and compaction messages retain their identity.

Plain XML, raw, and JSON continue to expose the provider-native user role. This preserves the machine-readable contract described in `README.md` and the colored-versus-plain boundary documented in `thoughts/26-06-18-colored-view-panels-and-tool-blocks/post-implementation.md`.

Public-command tests in `tests/test_colored_rendering.py` cover colored parse, colored search, mixed user text, non-Bash results, and unchanged XML semantics. The real Claude session that prompted the change now renders message 549 as a `Bash` panel.

All rendering tests, 577 non-performance Python tests, and every shell integration test pass. The full suite retains a pre-existing environment-sensitive failure in `tests/test_search_perf.py`: 1000 ms search/recent-index budgets currently measure roughly 1100–1130 ms, both before and after this unrelated presentation change.
