---
date: 2026-08-20
title: Slice three selection
---

# Slice three selection

Slice Three moves unified native session inventory discovery to Rust.

This is the highest-impact bite-sized remaining behavior found from current evidence. The live pool contains 4,863 main sessions and 4,936 sessions with Claude sidechains. It holds about 6.2 GB.

`SessionPool.discover(include_sidechains=False)` took 552 to 788 ms in repeated warm measurements. Its last-five median was 562 ms. The current path walks the roots in Python, classifies paths to remove sidechains, and classifies them again to build provider groups.

A transient single-classification inventory preserved every live `SessionPool` field. It reduced the median from 659 ms to 459 ms in one interleaved series.

The exact real launcher supplied end-to-end selection evidence. A transient equivalent inventory reduced `search . -ma 4h --list` from a 2,162 ms median to 1,672 ms. This is 490 ms, or 22.7%.

Concurrent team work made these four-sample series noisy. The samples ranged from 1,475 to 2,497 ms before and 1,327 to 2,169 ms with the prototype. Final acceptance requires quiet repeated cold and warm measurements.

A separate Rust prototype reproduced all 4,936 live paths byte-for-byte. It took 64.9 ms on its first pass and 40.9 to 43.9 ms after that. This prototype is impact evidence only because it did not yet apply canonical provider classification.

Forward timestamp scanning ranks below this behavior because it affects only `--cafter`. Forward cwd scanning affects only directory filters. Parallel last-timestamp probing changes wider orchestration and is not bite-sized.

This slice does not move timestamp scanning, cwd extraction, session parsing, search matching, date filtering, or command rendering to Rust.
