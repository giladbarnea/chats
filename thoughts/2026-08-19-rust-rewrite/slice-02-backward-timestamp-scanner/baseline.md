---
date: 2026-08-19
title: Slice two baseline
---

# Slice two baseline

The working tree started clean at commit `ac6599c`.

The required functional baseline passed 954 Python tests and skipped 3 tests in 67.50 seconds.

The serial performance baseline had one failure. `ch search . -ma 4h --list` took 2,443 ms against its 1,750 ms budget. The other three performance budgets passed. The failure stopped `tests/run_all.sh` before its 13 shell suites.

The live main-session pool contained 4,851 files and 6.036 GB. It had 383 Claude, 1,202 Codex, and 3,266 Pi files.

Direct repeated measurements gave these costs:

- File discovery took 112 to 124 ms.
- `SessionPool` construction took 91 to 98 ms warm.
- The raw Python backward scanner took 832 to 847 ms warm.
- A process-cold raw scan took 1,198 to 1,445 ms.

A pre-change differential manifest captured the raw and public Python results, file sizes, and modification times for all 4,851 files. Acceptance will compare Rust only on unchanged files and will add a synthetic edge corpus.

Project Python is 3.13.15. The exact `~/.local/bin/ch` launcher points to a uv tool script. Its shebang interpreter is `~/.local/share/uv/tools/chats/bin/python3`, which is Python 3.14.7. The uv receipt marks `/Users/giladbarnea/dev/chats` as editable. Both interpreters import this checkout and `src/chats/_native.abi3.so`.

The exact launcher had these five-run pre-change medians:

- `search . -ma 4h --list` took 2,359 ms fresh and 2,033 ms primed.
- `-1 -ma 4h` took 1,537 ms fresh and 1,387 ms primed.
- `-1 -d ~/.claude` took 871 ms fresh and 782 ms primed.
- `search . -l -d .` took 1,662 ms fresh and 1,494 ms primed.

The real launcher worked after Slice One only when the user ran `uv tool install -e .`. Normal project setup did not establish that working state. This is the authoritative installation baseline. No Slice Two discovery changed global tool state.
