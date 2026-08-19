---
date: 2026-08-19
title: Slice two decisions
---

# Slice two decisions

The existing Maturin and PyO3 ABI3 extension remains the only native module. Slice two adds one raw scanner to that module. It does not add another extension, a feature flag, or a Python fallback.

The scanner uses a linear backward byte walk. This choice fixes the measured repeated-copy cost on multi-megabyte lines. It also keeps memory bounded by one physical line plus one fixed read chunk.

Rust owns backward file reads, UTF-8 validation, linear line assembly, and scan control. A small Python line callback keeps `json.loads` and `_entry_timestamp` authoritative. `JSONDecodeError` continues the scan. Other parser errors abort to filesystem fallback.

The first Rust version used `serde_json`. Differential tests found drift for Python non-finite numbers, escaped lone surrogates, and the active integer-string digit limit. The final design removes serde and its compatibility emulation. It also returns the original Python string object, so a lone-surrogate timestamp reaches the unchanged Python fallback path.

Python keeps JSON semantics, datetime parsing, and stat fallback. Moving those parts would widen the compatibility matrix without helping the measured backward I/O cost.

The slice keeps one-path calls instead of adding batch or parallel orchestration. The measured standalone Rust scanner already predicts sufficient impact. Batch filtering would change search streaming and recent-index ownership.

Tests follow vertical red-green cycles through the existing public Python datetime wrapper. These tests exercise the native I/O loop and the Python line callback together. A transient Python reference provides whole-pool differential evidence without leaving two production implementations.

The real `~/.local/bin/ch` installation worked only after the user ran `uv tool install -e .`. Acceptance will not repeat that global operation without authorization. It will remove local stale native artifacts, rebuild through a named project path, inspect both interpreters, and run the exact launcher. The outcome must not claim project setup originally established the editable global tool.

File discovery, forward timestamp scanning, provider parsing, session-pool construction, filters, ordering, and command orchestration remain candidates for later work. Slice two does not start that work.
