---
date: 2026-08-20
title: Slice Four outcome
---

# Slice Four outcome

Slice Four is accepted. Rust now owns the forward file scan used by title and summary fallback resolution.

The native scanner reads fixed-size chunks, frames LF, CRLF, and lone-CR lines, validates UTF-8, applies the four raw facet-marker gates, and accumulates the latest title plus ordered summaries. A small Python callback keeps `json.loads` and the shared Claude, Pi, and Codex title rules authoritative.

`extract_resolution_facets_from_jsonl(Path) -> tuple[str | None, list[str]]` stays unchanged. Python still owns exact-identifier lookup, title substring matching, summary prefix matching, title precedence, ambiguity handling, and miss fallback. The replaced Python forward loop and marker helper are absent. No fallback or dual production implementation remains.

## Differential parity

An independent frozen pre-change Python reference and the production Rust path had zero mismatches across all 4,938 current sidechain-inclusive live files. Every compared file stayed stable by device, inode, size, and nanosecond mtime during the comparison.

The committed public-interface matrix covers universal newlines, a missing final newline, all provider title envelopes, later valid and blank titles, ordered duplicate summaries, malformed and non-object JSON, false marker candidates, non-finite values, lone surrogates, UTF-8 validation before filtering, Python's integer-string limit, chunk-split markers and CRLF, oversized lines, and file and path errors.

The 25 focused scanner and resolution tests pass. Independent review found no semantic drift, duplicate implementation, scope leak, or simpler repair.

## Clean native rebuild

Acceptance removed every source native binary and ran `cargo clean`, which removed 2,331 files and 335.7 MiB. It then proved that no source or target native binary remained before `uv sync --dev --reinstall-package chats` rebuilt the project.

The rebuild created exactly one 585,184-byte `src/chats/_native.abi3.so`. It created no `_native.cpython-*` artifact.

`cargo test --locked` passed 4 tests. `cargo check --locked --all-targets --all-features` and `cargo build --release --locked` passed.

Rustfmt and Clippy remain unavailable in the installed toolchain. Acceptance did not change global toolchain state.

## Exact-launcher measurements

The accepted A/B harness invoked the exact `~/.local/bin/ch` launcher for a guaranteed resolution-fallback miss. It compared a transient frozen Python reference with production Rust in five unprimed and five immediately repeated primed samples for each implementation.

The first harness attempt patched only the parsing module and missed the resolver's bound import. Acceptance discarded those samples and restarted with the corrected bound call path.

The corrected medians were:

- Frozen Python reference:
  - Unprimed: 22,007.1 ms.
  - Primed: 22,742.8 ms.
- Production Rust:
  - Unprimed: 12,264.0 ms.
  - Primed: 12,288.8 ms.

Rust saved 9,743.1 ms, or 44.3%, on the unprimed median. It saved 10,454.0 ms, or 46.0%, on the primed median. All 20 affected invocations returned 0.

The canonical-UUID control bypasses resolution facets. Its five-pair medians were 1,168.6 ms unprimed and 771.8 ms primed.

macOS denies `/usr/sbin/purge`. The unprimed samples are fresh processes but do not claim guaranteed page-cache eviction. Each primed sample ran immediately after its paired unprimed process and measures the available warm filesystem state.

These repeated end-to-end results establish material user impact. The direct scanner benchmark did not accept the slice by itself.

## Functional and package verification

The full Python stage passed 987 tests and skipped 3. Its performance stage had one failure: cold `search . -ma 4h --list` took 2,747 ms against 1,750 ms. This category failed at baseline, and Slice Four does not touch its path. The other three budgets passed.

All 13 shell suites passed separately, including the exact real-launcher seam.

Fresh builds produced `chats-0.1.0-cp314-abi3-macosx_11_0_arm64.whl` and the source distribution. The wheel contains the ABI3 module, Python scanner callback, command entry point, and catalog asset. The source distribution contains the Cargo files, Rust source, Python source, and asset.

Fresh temporary Python 3.14.7 wheel and no-cache source installs passed native import, scanner export, asset loading, installed `ch --help`, and fixture parsing.

## Launcher and scope

The exact launcher still resolves from `~/.local/bin/ch` to `~/.local/share/uv/tools/chats/bin/ch`. Its shebang uses Python 3.14.7. It imports this checkout and the single rebuilt ABI3 artifact, exposes `scan_resolution_facets`, passes `--help`, and parses a temporary Pi fixture.

The uv receipt SHA-256 stayed `675c53b8ffb0c04557fcc9af60ca88f43b87c783ebcccd2a42708bbec81168f7`. It still records the editable checkout that the user established with `uv tool install -e .`. Slice Four did not run that command, change the receipt, or create the global editable install through project setup.

No cwd scanner, timestamp scanner, search matcher, case-fold path, provider parser, resolution precedence, ambiguity logic, or other Slice Five behavior changed.
