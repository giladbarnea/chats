---
updated: 2026-07-12
---
# Bash result panels use semantic presentation labels

Colored parse and search views now label a user-role envelope containing only visible Bash results as `Bash`, using the existing tool-result hue. Within that already-identified panel, the result marker reads `⎿ output` rather than redundantly repeating `⎿ Bash`. This removes misleading transport detail without changing the underlying conversation model.

The change is deliberately narrow. Mixed messages containing genuine user text remain `User`, and output from other tools remains unchanged. Classification happens from visible rendered parts and requires the ordinary user wrapper, so explicit wrappers such as agent and compaction messages retain their identity.

Plain XML, raw, and JSON continue to expose the provider-native user role. This preserves the machine-readable contract described in `README.md` and the colored-versus-plain boundary documented in `thoughts/26-06-18-colored-view-panels-and-tool-blocks/post-implementation.md`.

Public-command tests in `tests/test_colored_rendering.py` cover colored parse, colored search, mixed user text, non-Bash results, and unchanged XML semantics. The real Claude session that prompted the change now renders message 549 as a `Bash` panel.

All 581 Python tests and every shell integration test pass. The previously environment-sensitive search and recent-index performance budgets are now 1200 ms, with explicit warnings against raising them further.
