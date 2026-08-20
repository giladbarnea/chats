---
date: 2026-08-20
title: Slice three contract
---

# Slice three contract

`find_all_supported_session_files(*, include_sidechains: bool = True) -> list[Path]` stays the public Python interface. Every existing `SessionPool` field and lookup behavior stays unchanged.

Rust receives the active home directory and `include_sidechains`. It returns ordered inventory rows with the path, canonical native-provider match or no match, and stat mtime or the oldest-value sentinel.

The inventory must preserve these rules:

1. Provider groups appear in Claude, Codex, then Pi order.
2. Paths stay lexically sorted inside each provider group.
3. Claude main discovery matches `~/.claude/projects/*/*.jsonl`.
4. Claude sidechain discovery matches `~/.claude/projects/*/*/subagents/agent-*.jsonl`.
5. Codex recursively discovers `*.jsonl` below `~/.codex/sessions`.
6. Pi recursively discovers `*.jsonl` below `~/.pi/agent/sessions`.
7. Recursive Codex and Pi walks do not enter descendant directory symlinks.
8. Fixed-depth Claude discovery follows symlinked directory segments like the current glob path.
9. Matching symlink entries remain inventory entries.
10. Hidden names match, while the `*.jsonl` suffix stays case-sensitive.
11. Paths with surrogate-escaped non-UTF-8 bytes remain representable.
12. Missing roots contribute no files, and subtree scan errors stay non-fatal.
13. `include_sidechains=False` applies the current adapter sidechain rule, including provider selection and Claude `agent-` filenames.
14. Native-provider labels use the existing canonical classifier, not lexical-root assumptions.
15. A path without a native match still uses Python first-entry provider detection.
16. Stat failures map to negative infinity without removing the path.
17. Equal-mtime sorting stays stable in original inventory order.
18. Duplicate stems and filenames keep the current last-entry-wins behavior.
19. The active home argument controls all roots, including temporary-home tests.

Rust becomes the only production implementation of unified inventory traversal. The replaced Python glob and recursive-glob inventory must be absent. `SessionPool.from_files()` remains for callers and tests that supply an explicit sequence. It is not a discovery fallback.

Success requires differential Rust-versus-Python parity on every unchanged live path and a synthetic edge matrix. The comparison must cover ordered paths, provider groups, stat ordering, sidechains, symlinks, missing roots, duplicate identifiers, and stat failures.

Acceptance also requires a stale-artifact-free native rebuild, the exact real launcher, and repeated cold and warm end-to-end measurements. A discovery microbenchmark cannot accept the slice.

All CLI arguments, output, provider parsing, filtering, sorting semantics, and public lookup behavior stay unchanged.
