---
date: 2026-08-20
title: Slice Four decisions
---

# Slice Four decisions

The existing Maturin and PyO3 ABI3 module remains the only native extension. Slice Four adds one forward resolution-facet scanner to that module and adds no Rust dependency.

Rust reads fixed-size byte chunks and assembles each physical line once. It preserves universal newline boundaries and validates UTF-8 before applying the four exact ASCII marker gates.

A small Python callback strips marker-positive lines, checks the leading object shape, runs `json.loads`, and applies `_extract_custom_title_from_entry`. Rust ignores only `JSONDecodeError`. It propagates other callback errors and accumulates the returned title and summary values.

This split keeps Python JSON and provider-title semantics authoritative. It avoids `serde_json` compatibility work for non-finite values, lone surrogates, large integers, and malformed edge inputs.

`extract_resolution_facets_from_jsonl()` delegates directly to the native scanner. The old Python file loop is removed. There is no feature flag, Python fallback, duplicate scanner, cache, index file, batch service, or second provider registry.

Tests use vertical red-green cycles through the existing Python interface. A transient frozen Python reference supplies whole-pool differential evidence without remaining in production.

The exact global launcher uses the editable install that the user established. Acceptance will not run `uv tool install -e .` or change its receipt. It will remove stale native artifacts, run `cargo clean`, rebuild through the project environment, and verify that the exact launcher imports the one new ABI3 artifact.

Cwd extraction, first-timestamp scanning, search case folding, provider parsing, matching precedence, ambiguity handling, and command orchestration remain Python. Moving any of them would start Slice Five.
