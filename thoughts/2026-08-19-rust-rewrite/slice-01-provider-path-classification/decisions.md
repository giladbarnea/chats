---
date: 2026-08-19
title: Slice one decisions
---

# Slice one decisions

Maturin and PyO3 provide the one native extension. PyO3 targets the stable ABI from the project’s Python 3.13 floor, so one editable artifact works under Python 3.13 and 3.14. The project keeps its mixed Python package and the existing `ch` entry point.

The slice replaces one cohesive behavior. It does not add a feature flag, Python fallback, or second provider registry.

Python keeps provider adapters and first-entry detection because those rules parse external content. Rust owns only native filesystem containment.

The classifier must use the active Python home directory. This keeps temporary-home tests and callers consistent with the existing `Path.home()` behavior.

Rust resolves the three provider roots once per active home during a CLI process. It still resolves each source path per call. This removes repeated root work without caching session results, and distinct temporary homes stay isolated.

The normal setup force-reinstalls the editable project. This rebuilds the shared stable-ABI artifact when Rust or build metadata changes, without reinstalling the global tool.

The backward timestamp scanner remains Python. Its measured Rust gain was smaller, and changing it would start slice two.

File discovery and `SessionPool` construction also remain Python. Their broader orchestration is outside this stable classifier boundary.
