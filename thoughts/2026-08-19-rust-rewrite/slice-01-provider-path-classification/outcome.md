---
date: 2026-08-19
title: Slice one outcome
---

# Slice one outcome

Slice one is accepted. Rust now owns native Codex, Pi, and Claude path classification through `chats._native`. The three Python path predicates, the adapter path-matcher field, and the separate removal-command classifier are gone. Python still owns external Codex and Pi first-entry detection, and every CLI interface stays unchanged.

The Rust boundary preserves Python 3.13 `Path.resolve(strict=False)` behavior. It covers existing and missing leaves, parent components, roots and later symlinks, dangling absolute and relative targets, and bounded symlink loops. A per-home cache stores only canonical provider roots. Every candidate source path still resolves on each call.

The first acceptance missed the real editable launcher. At that time, the project environment used Python 3.13, while `~/.local/bin/ch` used Python 3.14. Interpreter-specific extensions made the launcher fail after a Python 3.13 project build. Slice One then targeted the Python 3.13 stable ABI so one `_native.abi3.so` could load through both interpreters. The launcher worked only after the user ran `uv tool install -e .`. Normal project setup did not establish that global editable install.

On the live 4,911-file pool, median classification time fell from 281.2 ms for the Python reference to 39.7 ms for Rust. This is an 86% reduction. Warm serial performance runs pass all four budgets without changing their limits.

The final cold full-project run passed 954 Python tests and skipped 3. Three performance budgets passed. `search . -ma 4h --list` took 1,965 ms against 1,750 ms. This improves its 2,089 ms baseline failure but does not close it reliably. All classifier calls together cost only 173 ms, so even removing classification cannot recover the remaining 215 ms. Cold last-timestamp probes cost 1,106 ms, and changing them would start slice two. The earlier full run passed all 13 shell suites, and the updated 10-test CLI seam suite passes after the ABI3 repair.

`cargo test --locked`, `cargo check --locked --all-targets --all-features`, and `cargo build --release --locked` pass.

Editable installation, the existing `ch` entry point, the exact global Python 3.14 launcher, fresh ABI3 wheel and source-distribution builds, isolated Python 3.13 installs, the packaged native extension, the catalog template asset, and installed `ch --help` all pass. Maturin also removes the baseline Hatch build failure on the tracked external skill symlink.

Rustfmt and Clippy could not run because this installed toolchain lacks both components. The verification did not modify global toolchain state.

No timestamp scanner, file discovery, session-pool construction, search gate, or other slice-two work changed.
