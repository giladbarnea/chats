---
date: 2026-08-20
title: Slice Six outcome
---

# Slice Six outcome

Slice Six is accepted. Rust now keeps scanning eligible case-insensitive ASCII candidates through valid Unicode that is safe under Python 3.14 semantics.

The scanner defers on the 20 casefold or regex risk scalars and on invalid or incomplete UTF-8. Python limits native rejection to default unshortened visibility. JSON-decode-unstable queries and generated-content modes bypass it. Eligible searches add raw `\\u` evidence, and eligible Pi searches add joined-agent evidence.

The decoded-content candidate gate and its re-export are gone. Every native survivor goes directly to `SessionScan` and rendered Python regex confirmation. No second risk table or semantic matcher remains in production. Case-sensitive behavior and the public PyO3 interface stay unchanged.

Independent review found no contract gap, semantic drift, duplicate implementation, or scope leak.

## Differential parity

The production gate had zero mismatches against the proved reference on all 4,888 stable live main files. It sent 1,000 conservative survivors to semantic confirmation.

The independent corpus covered all 20 risk scalars and one aggregate containing every other valid non-ASCII scalar. It also covered 10,000 seeded refined cases, 2,000 Slice Five case-sensitive cases, UTF-8 boundaries, chunk boundaries, evidence groups, errors, JSON controls, Pi evidence, every bypass, and boolean forms. Every comparison passed.

Production search matched a no-gate `SessionScan` semantic reference byte-for-byte. The impossible literal exited 1 with empty output. The current real `Rust` hit exited 0 with 127 IDs and 4,699-byte stdout whose SHA-256 starts `b4a3dba5`. Live content changed after the 126-ID baseline, and the semantic reference confirmed the added hit.

## Clean native rebuild

Acceptance removed the source ABI3 module and every target dylib. `cargo clean` removed 2,185 files and 340.8 MiB. No native binary remained before the rebuild.

`uv sync --dev --reinstall-package chats` created exactly one 653,376-byte `src/chats/_native.abi3.so`. Its SHA-256 starts `fd1aae1b`. No CPython-tagged source module exists.

`cargo test --locked`, `cargo check --locked --all-targets --all-features`, and `cargo build --release --locked` passed. Rustfmt and Clippy remain unavailable in the installed toolchain. Acceptance did not change toolchain state.

## Exact-launcher measurements

Every measurement invoked the exact `~/.local/bin/ch` launcher. Each implementation received five unprimed fresh-process samples and five immediate primed samples. Unprimed means the first fresh process in its pair. It does not claim guaranteed page-cache eviction.

For `search slice-six-unmatchable-literal-019f -ll -p claude --color never --no-paging`:

- The pre-slice medians were 1,646.9 ms unprimed and 1,659.2 ms primed.
- The final medians were 1,392.3 ms unprimed and 1,384.8 ms primed.
- Slice Six saved 254.6 ms, or 15.5%, unprimed.
- Slice Six saved 274.4 ms, or 16.5%, primed.

For the real `search Rust -ll -p claude --color never --no-paging` hit:

- The pre-slice medians were 2,693.7 ms unprimed and 2,703.9 ms primed.
- The final medians were 1,767.0 ms unprimed and 1,790.3 ms primed.
- Slice Six saved 926.7 ms, or 34.4%, unprimed.
- Slice Six saved 913.6 ms, or 33.8%, primed.

The control moved from 480.6 to 462.5 ms unprimed and from 478.9 to 464.7 ms primed. It shows no regression.

These repeated end-to-end results establish material user impact. A direct scanner benchmark did not accept the slice.

## Functional and package verification

The full runner passed 1,044 Python tests and skipped 3. All four serial performance budgets passed. All 13 shell suites passed, including the exact real-launcher seam.

The exact launcher, project Python, and uv-tool Python all use Python 3.14.7 and import the same rebuilt artifact. The launcher passed `--help` and parsed a Pi fixture.

The uv receipt SHA-256 remains `675c53b8ffb0c04557fcc9af60ca88f43b87c783ebcccd2a42708bbec81168f7`. It still records the editable checkout that the user established with `uv tool install -e .`. Slice Six did not create or change that global install.

Fresh builds produced a `cp314-abi3` wheel and a source package. Fresh isolated Python 3.14 installs passed site-package origin, identical native hash and exports, catalog-asset loading, installed `ch --help`, and fixture parsing. Package metadata still requires `==3.14.*`.

No decoded candidate gate, duplicate risk table, dependency change, Slice Seven work, or second Slice Six directory remains.
