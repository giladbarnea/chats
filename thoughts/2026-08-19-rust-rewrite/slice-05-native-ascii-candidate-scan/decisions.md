---
date: 2026-08-20
title: Slice Five decisions
---

# Slice Five decisions

The existing Maturin and PyO3 ABI3 module remains the only native extension. Slice Five adds one raw candidate scanner and no Rust dependency.

Python keeps `_file_contains_ascii()` as the search module boundary and delegates it directly to Rust with byte-preserving path, needle, and evidence-group values. Search callers and tests do not gain a second interface.

Rust keeps the current raw overlap algorithm and 1 MiB read size. It also tracks incremental UTF-8 validity for case-sensitive scans. This lets valid non-ASCII text continue without moving Unicode case folding into Rust. Invalid UTF-8 still defers to Python's decoded path.

Case-insensitive behavior deliberately stays conservative. Moving Unicode case folding would require exact Python 3.14 Unicode semantics and wider decoded and rendered search parity. That is not part of this slice.

Python continues to decide when the raw scan is safe. `_ascii_literal_needle()`, generated-marker rules, boolean prefilter evaluation, and Pi normalization evidence remain unchanged. Rust receives only an already-approved ASCII needle and its raw evidence groups.

There is no feature flag, Python fallback, duplicate file loop, cache, index, or batch service. Tests use vertical red-green cycles through the existing Python search boundary. A transient Python reference supplies differential acceptance without remaining in production.

Acceptance will not run `uv tool install -e .` or change the uv tool receipt. The exact launcher uses the global editable install that the user already established. Acceptance removes stale native artifacts, runs `cargo clean`, rebuilds through the project environment, and verifies that the exact launcher imports the one new ABI3 artifact.

Native cwd scanning, first-timestamp scanning, Unicode case folding, semantic search confirmation, parsing, rendering, and pool orchestration remain outside Slice Five.
