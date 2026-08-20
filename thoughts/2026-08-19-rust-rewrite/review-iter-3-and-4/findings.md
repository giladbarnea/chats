# Slices One through Four review findings

## Findings

I found no high-confidence, high-impact issue in the complete Rust rewrite through Slice Four.

The four native boundaries preserve their Python contracts and stay cohesive. Python still owns JSON semantics, datetime conversion, external provider detection, resolution precedence, and public interfaces. The Rust code has no duplicate production fallback or Slice Five scope leak.

The earlier at-large findings are resolved. The package now targets Python 3.14 only, the timestamp parity cases remain in durable tests, and the Slice One outcome records the launcher history accurately.

Packaging and launcher integration are correct. The real `~/.local/bin/ch` launcher imports this checkout and `src/chats/_native.abi3.so` through the editable install the user established with `uv tool install -e .`. Project setup does not claim to create that global install.

## Verification

The functional suite passed 987 tests with 3 skips. All 13 shell suites passed separately, including the real launcher seam. Focused cross-boundary integration tests also passed.

`cargo test --locked`, `cargo check --locked --all-targets --all-features`, and the release build passed. Rustfmt and Clippy remain unavailable in the installed toolchain.

Fresh Python 3.14 wheel and source packages built. Isolated installs loaded the ABI3 module, the catalog asset, and the installed CLI.

The live performance stage failed two existing baseline categories. Date-filtered search took 2,946 ms against 1,750 ms. Recent date-filtered lookup took 3,358 ms against 1,500 ms. Both categories already failed the Slice Four baseline, so they are not regressions from this reviewed work. Addressing them would start the explicitly excluded Slice Five.
