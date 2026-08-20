---
date: 2026-08-20
title: Slice Five outcome
---

# Slice Five outcome

Slice Five is accepted. Rust now owns the raw file scan used to reject impossible plain ASCII literal search candidates before full decoding.

The Python `_file_contains_ascii()` interface stays unchanged and delegates directly to the existing PyO3 extension with byte-preserving paths. Rust owns 1 MiB reads, overlap-aware needle and evidence matching, ASCII haystack lowering, and incremental UTF-8 validity. Python still owns query parsing, boolean evaluation, generated-marker rules, Pi evidence construction, decoded-content confirmation, semantic matching, ordering, and output.

Case-sensitive scans now continue across valid non-ASCII UTF-8 because those bytes cannot create an ASCII match. Invalid or incomplete UTF-8 still defers to the decoded path. Case-insensitive scans keep the prior conservative defer on every non-ASCII byte. The production Python file loop and scan constant are gone. No fallback or dual scanner remains.

## Differential parity

The refined Python oracle and production Rust had zero mismatches across 20,000 seeded random cases and 8 explicit boundary cases. An independent whole-pool comparison made 24,720 comparisons across all 4,944 stable sidechain-inclusive files with five query and evidence shapes. It found zero mismatches.

Public `cmd_search` results also matched the reference. An independent case-sensitive miss returned exit 1 with no IDs in both paths. The real `PyO3` hit returned exit 0 with one identical ID. Stdout and stderr matched byte-for-byte.

The committed contract and orchestration tests cover both case modes, valid, invalid, incomplete, and boundary-split UTF-8, cross-chunk needles and evidence, complete and incomplete evidence groups, empty needles, file errors, surrogate-escaped paths, and mandatory semantic confirmation.

## Clean native rebuild

Acceptance removed every source native binary and ran `cargo clean`, which removed 2,795 files and 359.5 MiB. It proved no source or target native binary remained before `uv sync --dev --reinstall-package chats` rebuilt the project.

The rebuild created exactly one 636,864-byte `src/chats/_native.abi3.so` and no `_native.cpython-*` artifact.

`cargo test --locked` passed 4 tests. `cargo check --locked --all-targets --all-features` and `cargo build --release --locked` passed. Rustfmt and Clippy remain unavailable in the installed toolchain. Acceptance did not change toolchain state.

## Exact-launcher measurements

Every end-to-end sample invoked the exact `~/.local/bin/ch` launcher. A transient frozen pre-change Python scanner replaced only the bound raw scan for the reference series. Each implementation received five unprimed fresh-process samples and five immediate primed samples. The acceptance environment denied `/usr/sbin/purge`, so unprimed does not claim page-cache eviction.

For `search -s slice-five-unmatchable-literal-019f -ll --color never --no-paging`:

- Python reference median: 9,433.2 ms unprimed and 8,959.3 ms primed.
- Production Rust median: 3,050.1 ms unprimed and 3,043.1 ms primed.
- Rust saved 6,383.0 ms, or 67.7%, unprimed.
- Rust saved 5,916.1 ms, or 66.0%, primed.

All 20 no-hit invocations exited 1 with byte-identical empty output.

For real-hit `search -s PyO3 -ll --color never --no-paging`:

- Python reference median: 19,799.2 ms unprimed and 19,869.5 ms primed.
- Production Rust median: 17,918.1 ms unprimed and 17,868.1 ms primed.
- Rust saved 1,881.1 ms, or 9.5%, unprimed.
- Rust saved 2,001.4 ms, or 10.1%, primed.

All 20 real-hit invocations exited 0 with the same one-ID stdout byte-for-byte.

The recent-index control showed no material regression. `-ll -1 --color never --no-paging` moved from 682.2 to 683.0 ms unprimed and from 686.6 to 682.5 ms primed. All outputs and exit codes matched.

These repeated real-launcher results establish material user impact. A scanner microbenchmark did not accept the slice.

## Functional and package verification

The full functional stage passed 1,006 Python tests and skipped 3. Its performance stage had the same existing failure as the baseline. The fresh-process `search . -ma 4h --list` took 2,658 ms against 1,750 ms, compared with baseline runs of 2,568 and 2,465 ms. The dot query bypasses the changed literal scanner. The other three budgets passed.

All 13 shell suites passed separately after the clean rebuild, including the real-launcher seam.

Fresh builds produced `chats-0.1.0-cp314-abi3-macosx_11_0_arm64.whl` and the source package. Fresh isolated Python 3.14.7 wheel and no-cache source installs passed native import and export, site-package origin, catalog-asset loading, installed `ch --help`, and fixture parsing. Package metadata still requires `==3.14.*`.

## Launcher and scope

The exact launcher still resolves through the uv tool Python 3.14.7 environment. It imports this checkout and the single rebuilt ABI3 artifact, which exports `file_contains_ascii`.

The uv receipt SHA-256 stayed `675c53b8ffb0c04557fcc9af60ca88f43b87c783ebcccd2a42708bbec81168f7`. It still records the global editable checkout that the user established with `uv tool install -e .`. Slice Five did not run that command, change the receipt, or claim project setup created the global install.

No cwd scanner, first-timestamp scanner, Unicode case-fold implementation, semantic search matcher, parser, renderer, pool orchestration, or Slice Six behavior changed.
