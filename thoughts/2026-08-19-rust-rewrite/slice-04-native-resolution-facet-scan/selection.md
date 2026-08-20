---
date: 2026-08-20
title: Slice Four selection
---

# Slice Four selection

Slice Four moves the forward resolution-facet file scan to Rust.

This behavior runs after path, recent-index, exact-identifier, and canonical-UUID lookup miss. It scans every session for the latest current title and ordered summaries. Python keeps title-before-summary resolution, substring and prefix matching, ambiguity handling, and every public interface.

Current evidence selects this behavior rather than a candidate from earlier notes. The exact `~/.local/bin/ch 'slice-four-unmatchable-title-019f'` launcher took 23.78, 23.13, and 23.65 seconds. A later paired reference took 19.99 seconds. Direct Python resolution-facet extraction across all 4,937 sidechain-inclusive live files took 21.243 seconds.

A transient forward-scanner prototype had zero facet mismatches on those 4,937 files. It reduced the paired exact-launcher run from 19.99 to 16.63 seconds. Its direct pool scan took 15.886 seconds. An independent exact-launcher run fell from 21.637 to 18.57 seconds with an equivalent transient byte prefilter, a 14.2% gain. These measurements show end-to-end impact before production code changes. The microbenchmark supports selection but does not accept the slice.

The forward cwd probe is the largest remaining pool-wide metadata probe in directory-filtered flows. Five direct warm samples had a 457.5 ms median. Exact-launcher medians were 2,589 ms for recent directory lookup and 3,184 ms for directory-filtered search. A standalone Rust I/O floor was 126 to 171 ms across 4,863 main files. This behavior is valuable, but its absolute recoverable time ranks below resolution-facet extraction.

First-timestamp and last-timestamp passes had direct medians of 396.8 ms and 356.6 ms. They also rank below resolution facets.

A case-insensitive literal miss took 38.51 seconds, but 30.6 seconds came from whole-content Python case folding after the conservative byte gate deferred on non-ASCII data. Exact Python Unicode and rendered-search parity make that boundary too broad for this bite-sized slice. Moving only the raw byte gate would not address the dominant cost.

Slice Four does not move cwd extraction, first-timestamp scanning, search matching, content case folding, provider parsing, resolution precedence, or command orchestration to Rust.
