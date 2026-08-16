---
date: 2026-08-16
commits: [509ed1e, d71b04e, 48f3050, 0b5f191]
---

# Tool name filters now follow user-facing names

The tool name filter now treats an explicit parsed name as authoritative. It uses the tool ID map only when a result lacks a name.

Provider-native names and canonical names match symmetrically. This avoids making a valid parsed name unreachable because another provider uses it as an alias.

PI now preserves `toolName` on results. Antigravity now pairs results by record type instead of assuming every call receives a result.

Antigravity orphan results needed special care because some result types represent several possible calls. Candidate names preserve discoverability without inventing a false call identity.

# Repeated reviews exposed cross-provider assumptions

The first design normalized only the requested name. Reviews showed that provider-specific parsed names could then become impossible to query.

Later reviews found positional Antigravity pairing drift and missing provider aliases. Focused red tests drove each correction through public parse and filter paths.

The functional suite finished with 955 passing tests and 3 skips. Existing timing-budget failures remained outside this work.

A final review flagged unsupported Antigravity `INVOKE_SUBAGENT` results. The user intentionally left that follow-up outside this branch.

Useful context came from [README.md](../../README.md) and [ARCHITECTURE.md](../../ARCHITECTURE.md), especially the tool-filter contract and tool ID map lifecycle.
