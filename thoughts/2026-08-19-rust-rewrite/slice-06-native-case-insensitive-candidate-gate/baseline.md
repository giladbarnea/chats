---
date: 2026-08-20
title: Slice Six baseline
---

# Slice Six baseline

The working tree started clean at commit `6ac378c`.

`./tests/run_all.sh | cat` passed 1,006 Python tests and skipped 3 in 60.23 seconds. All four serial performance budgets passed together in 3.26 seconds. All 13 shell suites passed, including the exact real-launcher seam. The baseline had zero performance failures.

The stable main inventory contained 4,883 files.

Project Python and the uv-tool Python are both 3.14.7. The exact launcher is `~/.local/bin/ch`. It links to `~/.local/share/uv/tools/chats/bin/ch`, whose shebang uses the uv-tool Python.

The uv receipt SHA-256 was `675c53b8ffb0c04557fcc9af60ca88f43b87c783ebcccd2a42708bbec81168f7`. It records the editable checkout that the user established with `uv tool install -e .`. Project setup did not create that global install. Slice Six discovery did not change global tool state.

The sole source native artifact was `src/chats/_native.abi3.so`. It was 636,864 bytes with SHA-256 `19f8a5b05c22ac7e613d44f7977cf8bfb9cf634dcde5c460eac4d63fe016f4e9`. It exported only the five Slice One through Five functions.

## Exact-launcher candidate ranking

Each entry below gives the unprimed and primed median from five fresh-process pairs. The harness alternated implementation order.

1. The selected conservative native-I/O prototype:
   - Impossible Claude literal: current 1,646.9/1,659.2 ms; refined 895.4/887.9 ms.
   - Real Claude `Rust` hit: current 2,693.7/2,703.9 ms; refined 1,643.2/1,632.3 ms.
   - The miss saved 751.6/771.3 ms. The real hit saved 1,050.5/1,071.6 ms.
   - All miss runs exited 1 with empty output.
   - All hit runs exited 0 with byte-identical 4,662-byte stdout containing 126 IDs. Its SHA-256 was `5bb3d83a1d689e9f14af47f7cbba1613021c4060d819f7a977998b60e03dd2df`.
2. Cwd cached ceiling:
   - Recent directory lookup fell from 621.4/609.1 to 413.8/423.0 ms.
   - A case-sensitive directory no-hit search fell from 656.7/649.0 to 433.1/446.8 ms.
   - Its best saving was 223.7/202.2 ms.
3. First-timestamp cached ceiling:
   - A created-after no-hit search fell from 2,278.2/2,238.4 to 2,073.9/2,067.3 ms.
   - A recent created-after lookup fell from 641.7/642.0 to 463.6/465.1 ms.
   - Its best saving was 204.3/176.9 ms.

The selected semantic oracle retained 79 miss candidates and 288 real-hit candidates among the 381 Claude files.
