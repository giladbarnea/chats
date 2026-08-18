---
date: 2026-08-16
commits: [509ed1e, d71b04e, 48f3050, 0b5f191]
---

# Tool name filters now follow user-facing names

The tool name filter now treats an explicit parsed name as authoritative. It uses the tool ID map only when a result lacks a name.

Provider-native names and canonical names match symmetrically. This avoids making a valid parsed name unreachable because another provider uses it as an alias.

PI now preserves `toolName` on results.

# Repeated reviews exposed cross-provider assumptions

The first design normalized only the requested name. Reviews showed that provider-specific parsed names could then become impossible to query.

The functional suite finished with 955 passing tests and 3 skips. Existing timing-budget failures remained outside this work.

Useful context came from [README.md](../../README.md) and [ARCHITECTURE.md](../../ARCHITECTURE.md), especially the tool-filter contract and tool ID map lifecycle.
