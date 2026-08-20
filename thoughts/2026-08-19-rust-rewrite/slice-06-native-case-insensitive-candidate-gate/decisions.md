---
date: 2026-08-20
title: Slice Six decisions
---

# Slice Six decisions

The existing Maturin and PyO3 ABI3 extension remains the only native module. Slice Six adds no Rust dependency and changes no public function signature.

Rust owns UTF-8 framing and the 20-scalar Python 3.14 risk table. The package supports only Python 3.14, so the table targets its Unicode and regex behavior directly. Rust does not implement Python case folding or regex matching.

Python keeps query parsing, strict eligibility, visibility rules, boolean evaluation, JSON escape and Pi evidence construction, JSON decoding, provider normalization, `SessionScan`, rendered regex confirmation, ordering, and output.

The optimized gate is deliberately strict. Non-default visible content and shortening can generate text that raw JSON does not contain. Those modes bypass native rejection rather than duplicating renderer semantics in Rust.

The decoded-content candidate gate is removed. Keeping it would require a second Python risk table for U+0131 and future semantic exceptions. One native conservative gate followed by one semantic `SessionScan` authority is smaller and safer.

Raw `\\u` evidence handles Unicode escapes without a JSON parser in Rust. Default Pi joined-agent evidence handles the one default-visible provider normalization that can generate text absent from raw values.

Tests follow vertical red-green cycles through the existing Python scanner interface and public search command. Transient Python references provide broad differential evidence without remaining in production.

Acceptance will not run `uv tool install -e .` or change the uv tool receipt. The exact launcher uses the global editable install that the user already established. Acceptance will remove stale native artifacts, run `cargo clean`, rebuild through the project environment, and verify the one Python 3.14 ABI3 artifact.

Cwd scanning, first-timestamp scanning, Unicode semantic matching, parser logic, renderer logic, and batch orchestration remain outside Slice Six.
