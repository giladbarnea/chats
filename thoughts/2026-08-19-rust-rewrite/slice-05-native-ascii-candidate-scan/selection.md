---
date: 2026-08-20
title: Slice Five selection
---

# Slice Five selection

Slice Five moves the raw ASCII search candidate scan to Rust and sharpens its case-sensitive path.

This choice comes from current evidence, not the earlier slice notes. Repeated exact-launcher trials found that case-sensitive literal misses spend several seconds in avoidable full-file decoding after the Python byte gate sees valid non-ASCII text. A transient equivalent gate kept scanning valid UTF-8 under case-sensitive search. It reduced three real no-hit command series by about 5 to 6 seconds. A real-hit `PyO3` search kept identical ID output and improved by about 4.7 seconds.

Native cwd scanning was the strongest alternative. The current 4,870-file pool takes about 0.3 to 0.4 seconds for one warm cwd pass. A transient result-preserving prototype found only about 0.1 to 0.3 seconds of exact-launcher headroom. First-timestamp scanning ranked slightly below cwd and serves fewer pool-wide product paths.

A default case-insensitive literal miss is still slower than the selected path. It was rejected because exact Python 3.14 Unicode case folding, decoded JSON, renderer-generated text, and Pi normalization evidence form a broader semantic boundary. Slice Five keeps that conservative Unicode defer unchanged.

The selected boundary keeps search query parsing, boolean evaluation, generated-marker handling, semantic confirmation, JSON decoding, rendering, and output in Python. Rust owns only raw file reads, overlap-aware ASCII matching, evidence-group accumulation, and incremental UTF-8 validity needed by the case-sensitive gate.
