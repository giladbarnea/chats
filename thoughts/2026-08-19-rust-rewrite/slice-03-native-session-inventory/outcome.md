---
date: 2026-08-20
title: Slice three outcome
---

# Slice three outcome

Slice Three is accepted. Rust now owns unified Claude, Codex, and Pi session inventory traversal in the existing PyO3 extension.

The native boundary returns byte-preserving paths, canonical native-provider labels or no match, and mtimes or negative infinity. Python keeps the public `Path` and `SessionPool` interfaces. It runs first-entry provider detection only for canonical no-match rows.

`SessionPool.discover()` consumes the native provider and mtime rows directly. `SessionPool.from_files()` remains the separate constructor for caller-supplied sequences. The production Python unified glob traversal is gone.

## Differential parity

The frozen Python reference and Rust had zero differences on 4,864 main rows and 4,937 sidechain-inclusive rows. Ordered paths, labels, mtimes, public paths, provider groups, stable stat order, and both last-wins identifier maps matched.

The synthetic matrix also had zero differences across 15 main rows, 18 inclusive rows, and missing roots. It covered ordering, depth, hidden names, case-sensitive suffixes, sidechains, symlinks, external provider fallback, stat failures, stable ties, and duplicate identifiers.

The first native version sorted full path strings. Live differential testing found that Python sorts `Path` component tuples instead. Rust now compares byte-preserving filesystem code points component by component. A durable sibling-prefix test covers the failed `agents` versus `agents-plugins` shape.

APFS rejected a raw invalid-byte filename with `EILSEQ`. Rust retains an executable non-UTF-8 `OsString` test. A public Python seam test proves the native bytes row survives `os.fsdecode`, `Path`, and `os.fsencode` without loss.

## Clean rebuild and tests

Acceptance removed every source native artifact and ran `cargo clean`. It confirmed no native artifact remained before `uv sync --dev --reinstall-package chats` built exactly one new 582,944-byte `src/chats/_native.abi3.so`. No interpreter-tagged extension exists.

`cargo test --locked` passed 4 tests. `cargo check --locked --all-targets --all-features` and `cargo build --release --locked` passed.

The full functional run passed 981 Python tests and skipped 3. Its performance stage stopped on the same four cold budget categories that failed at baseline:

1. Search after modification took 2,108 ms against 1,750 ms.
2. Recent directory lookup took 2,828 ms against 2,250 ms.
3. Recent lookup after modification took 2,028 ms against 1,500 ms.
4. Directory-filtered search took 3,727 ms against 2,500 ms.

All 13 shell suites then passed separately, including the real-launcher seam.

Rustfmt and Clippy remain unavailable in the installed toolchain. Acceptance did not change toolchain state.

## Exact-launcher measurements

Every end-to-end sample used the exact `~/.local/bin/ch` launcher. Each unprimed sample was the first fresh process in its pair. A second fresh process ran immediately as the primed sample.

macOS denied `/usr/sbin/purge`, so the unprimed samples do not claim a guaranteed page-cache flush. They are the available operational cold-process measurements. The paired primed samples measure the warm filesystem state.

Five paired samples produced these results in milliseconds:

- `search . -ma 4h --list`
  - Unprimed: 2,831.921, 2,097.547, 2,165.869, 2,085.709, 2,243.257. Median: 2,165.9.
  - Primed: 2,113.898, 1,375.186, 1,417.104, 1,399.128, 1,390.859. Median: 1,399.1.
- `-1 -ma 4h`
  - Unprimed: 1,222.117, 2,148.097, 1,809.971, 1,834.793, 1,925.371. Median: 1,834.8.
  - Primed: 1,837.896, 1,250.135, 1,481.051, 1,446.505, 1,407.112. Median: 1,446.5.
- `-1 -d ~/.claude` control
  - Unprimed: 2,523.348, 2,937.170, 2,806.721, 2,770.488, 2,885.586. Median: 2,806.7.
  - Primed: 2,749.443, 2,937.223, 2,823.003, 2,878.078, 3,092.319. Median: 2,878.1.
- `search . -l -d .` control
  - Unprimed: 3,613.069, 3,847.639, 3,813.612, 3,924.603, 3,871.185. Median: 3,847.6.
  - Primed: 3,835.894, 3,901.251, 3,794.660, 3,818.167, 3,868.591. Median: 3,835.9.

A second five-run warm series used the exact pre-change method. Date-filtered search improved from 2,213.5 to 1,824.2 ms, or 17.6%. Recent date-filtered lookup improved from 1,566.8 to 1,490.0 ms, or 4.9%.

The recent-directory control moved from 2,878.9 to 2,892.4 ms, or 0.5%. The directory-search control improved from 4,062.0 to 3,982.7 ms, or 2.0%. Neither control shows a material warm regression.

The direct `SessionPool.discover(False)` last-five median fell from 562.0 to 261.1 ms, or 53.5%. This microbenchmark supports the real-launcher search gain but does not establish acceptance alone.

Cold filesystem I/O remains variable, and all four cold budgets still fail. All four also failed at the selected baseline. The repeated 17.6% warm real-launcher search gain establishes material end-to-end impact.

## Launcher and packages

The exact launcher still uses its uv-tool Python 3.14.7 shebang. It imports this checkout and the new ABI3 artifact, passes `--help`, parses a Pi fixture, and runs the affected commands.

The uv receipt still records `editable = /Users/giladbarnea/dev/chats`. Its SHA-256 stayed unchanged. The user established this global editable install with `uv tool install -e .`; Slice Three did not run that command or change global tool state.

Fresh builds produced a `cp314-abi3` wheel and source distribution. Both include the native module, catalog asset, and required build sources. Fresh isolated Python 3.14.7 wheel and source installs passed native import, `ch --help`, fixture parsing, and catalog-asset loading.

No timestamp scanner, cwd scanner, parser, search matcher, date filter, renderer, or other Slice Four behavior changed.
