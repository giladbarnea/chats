---
date: 2026-08-20
title: Slice Four baseline
---

# Slice Four baseline

The working tree started clean at commit `10dd6e2`.

The functional baseline passed 981 Python tests and skipped 3 tests. The full runner then stopped because all four live performance budgets failed:

1. `ch search . -ma 4h --list` took 3,192 ms against 1,750 ms.
2. `ch -1 -d ~/.claude` took 2,574 ms against 2,250 ms.
3. `ch -1 -ma 4h` took 1,994 ms against 1,500 ms.
4. `ch search . -l -d .` took 3,161 ms against 2,500 ms.

The stopped runner did not reach the 13 shell suites. Slice Three passed all 13 suites before this clean baseline.

The live inventory contained 4,863 main rows and 4,937 sidechain-inclusive rows. The main rows comprised 380 Claude, 1,204 Codex, and 3,279 Pi sessions.

The exact launcher is `~/.local/bin/ch`. It resolves to `~/.local/share/uv/tools/chats/bin/ch`. Its shebang uses `~/.local/share/uv/tools/chats/bin/python3`, which is Python 3.14.7. It imports this checkout and `src/chats/_native.abi3.so`. `--help` and a temporary Pi fixture parse passed.

The uv receipt records `editable = /Users/giladbarnea/dev/chats`. Its pre-slice SHA-256 is `675c53b8ffb0c04557fcc9af60ca88f43b87c783ebcccd2a42708bbec81168f7`. The user established this global editable install with `uv tool install -e .`. Project setup did not create it, and Slice Four discovery did not change global tool state.

Concurrent work made the first five paired launcher samples noisy. Their unprimed and primed medians were 2,924 and 2,991 ms for date-filtered search, 1,748 and 1,670 ms for recent date lookup, 2,380 and 1,957 ms for recent directory lookup, and 2,945 and 2,977 ms for directory-filtered search. These samples establish the operational baseline but cannot accept impact alone.

macOS denies `/usr/sbin/purge`. Final measurements will call each first fresh process in a pair `unprimed`, not guaranteed filesystem-cold. The immediate second process is the `primed` sample. Acceptance requires at least five quiet exact-launcher pairs for the affected resolution fallback and a control.
