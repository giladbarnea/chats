---
date: 2026-08-20
title: Slice three baseline
---

# Slice three baseline

The working tree started clean at commit `8c99c49`.

The project and the exact real launcher both use Python 3.14.7. Package metadata requires `==3.14.*`, and PyO3 uses `abi3-py314`.

The functional baseline passed 971 Python tests and skipped 3 tests. The full runner then stopped because all four live performance budgets failed:

1. `ch search . -ma 4h --list` took 2,130 ms against 1,750 ms.
2. `ch -1 -d ~/.claude` took 3,034 ms against 2,250 ms.
3. `ch -1 -ma 4h` took 1,756 ms against 1,500 ms.
4. `ch search . -l -d .` took 3,229 ms against 2,500 ms.

The exact launcher had these five-run warm medians:

- `search . -ma 4h --list`: 2,213.5 ms.
- `-1 -ma 4h`: 1,566.8 ms.
- `-1 -d ~/.claude`: 2,878.9 ms.
- `search . -l -d .`: 4,062.0 ms.

The stable main-session pool contained 4,863 files. It had 384 Claude, 1,204 Codex, and 3,275 Pi files.

The exact `~/.local/bin/ch` shebang uses the uv tool Python 3.14.7. Its receipt records `/Users/giladbarnea/dev/chats` as editable. Both runtimes import this checkout and `src/chats/_native.abi3.so`.

The user established that global editable install with `uv tool install -e .`. Project setup did not establish it. Slice Three discovery did not change global tool state.

A pre-change differential check found zero provider-classification, raw timestamp, or public timestamp mismatches across 4,862 unchanged live files. One changing file was excluded.
