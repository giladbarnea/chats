---
date: 2026-08-19
title: Slice two outcome
---

# Slice two outcome

Slice two is accepted. Rust now owns backward file reads, bounded linear line assembly, UTF-8 validation, and scan control for last-timestamp probes. Python keeps its existing JSON parser, timestamp selection, local datetime conversion, and filesystem fallback. The replaced Python backward loop and its repeated growing-buffer copies are gone.

The first Rust version used `serde_json`. Differential tests found drift for non-finite values, escaped lone surrogates, malformed non-finite token boundaries, and Python's active integer-string digit limit. The final smaller design calls one Python line callback from the Rust I/O loop. This removed serde, its dependency graph, and all JSON compatibility emulation.

Differential acceptance found zero raw or public-result differences across 4,852 stable live main-session files. It also found zero differences across a 36-case edge matrix. The matrix covered multi-megabyte and chunk-boundary lines, malformed JSON, invalid UTF-8, byte whitespace, timestamp truthiness and precedence, invalid raw winners, non-object aborts, non-finite values, lone surrogates, and the active integer digit limit.

The exact real launcher shows material end-to-end impact across five fresh-process and five primed samples:

- `search . -ma 4h --list` improved from a 2,359 ms fresh median to 1,621 ms. This is 31.3% faster.
- The same search improved from a 2,033 ms primed median to 1,397 ms. This is 31.3% faster.
- `-1 -ma 4h` improved from a 1,537 ms fresh median to 761 ms. This is 50.5% faster.
- The same recent lookup improved from a 1,387 ms primed median to 704 ms. This is 49.2% faster.

Four of five fresh search samples and all five primed samples passed the 1,750 ms budget. All ten recent-index samples passed its 1,500 ms budget.

The controls had no material regression. Fresh `-1 -d ~/.claude` improved from 871 to 712 ms, while its primed median moved from 782 to 786 ms. Fresh `search . -l -d .` improved from 1,662 to 1,395 ms, while its primed median moved from 1,494 to 1,496 ms.

Cold random I/O remains variable. The full runner stopped on the same search budget that failed before this slice. Its final cold result was 2,464 ms, compared with the 2,443 ms baseline. Across nine independent serial budget runs, two passed and seven failed at 1,846 to 2,464 ms. A cold pool-wide native scan still costs about 826 ms, while a warm scan costs 156 to 197 ms.

This cold failure does not add a baseline failure. Slice One was accepted with the same cold search failure. Slice two meets the explicit acceptance gates through zero differential mismatches and repeated fresh and primed end-to-end gains. Parallel or batch orchestration could reduce cold random I/O, but it would widen this slice. That work remains outside Slice Two.

The final project tests passed 963 Python tests and skipped 3. All 13 shell suites passed separately. `cargo test --locked`, `cargo check --locked --all-targets --all-features`, and `cargo build --release --locked` passed. The installed toolchain still lacks `cargo-fmt`, and verification did not change global toolchain state.

Acceptance removed every source and target native artifact and ran `cargo clean` before `uv sync --dev --reinstall-package chats`. The rebuild created exactly one new `src/chats/_native.abi3.so` and no interpreter-tagged extension. Project Python 3.13.15 and the exact `~/.local/bin/ch` Python 3.14.7 both imported this checkout and the same new artifact. The launcher parsed a fixture and ran both affected commands.

The global uv receipt and launcher did not change. They still record the editable install that the user established with `uv tool install -e .` after Slice One. Slice Two did not run that command and does not claim project setup created the global editable state.

Fresh ABI3 wheel and source packages built. Isolated wheel installs passed under Python 3.13 and 3.14. An isolated source install passed under Python 3.13. Native imports, the catalog asset, fixture parsing, and installed `ch --help` all passed.

No forward scanner, file discovery, session-pool construction, batch scan, parallel scan, search gate, or other Slice Three work changed.
