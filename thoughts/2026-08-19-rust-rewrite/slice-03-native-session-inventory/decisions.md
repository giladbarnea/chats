---
date: 2026-08-20
title: Slice three decisions
---

# Slice three decisions

The existing Maturin and PyO3 ABI3 module remains the only native extension. The inventory uses `std::fs` and adds no dependency.

Rust owns the unified root traversal, canonical native-provider classification, and per-path mtime probe. One native call returns the data needed to construct the existing Python `SessionPool`.

Python keeps the public `Path` projection and the `SessionPool` interface. It also keeps first-entry provider detection for inventory paths that have no canonical native match.

`SessionPool.discover()` consumes the labeled native rows directly. It must not classify every path again. Recent-index sidechain removal must reuse the same discovered provider result rather than start another pool-wide classifier pass.

`SessionPool.from_files()` stays because explicit and synthetic path sequences need the existing general constructor. This is a separate caller-supplied boundary, not a Python discovery implementation.

The Python unified `glob` and `rglob` traversal is removed. There is no Python fallback, feature flag, cache, index file, background service, or second provider registry.

Provider classification remains canonical. The inventory does not infer provider ownership only from the lexical root because a symlink can resolve outside that root.

Mtime remains an inventory property because every `SessionPool` needs the stat-sorted sequence. Returning it with each row removes another pool-wide Python filesystem pass while preserving the existing negative-infinity fallback and stable sort.

Tests follow vertical red-green cycles through the public discovery and `SessionPool` interfaces. A transient Python reference supplies differential acceptance without leaving two production implementations.

Acceptance will not run `uv tool install -e .` or change the uv tool receipt. The exact launcher uses the global editable install that the user already established.

Slice Three ends at native session inventory. Timestamp batching, forward scans, cwd scans, and other Slice Four candidates remain unchanged.
