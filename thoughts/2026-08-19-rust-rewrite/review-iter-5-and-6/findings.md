# Slices One through Six review findings

## 1. High: case-sensitive native candidate rejection drops real search hits

`src/chats/commands/search.py:952-974` applies the strict generated-content bypass and raw `\\u` and joined-Pi evidence only to case-insensitive terms. A case-sensitive plain literal can therefore fail before `SessionScan` even though the rendered Python matcher accepts it.

I reproduced three silent false negatives:

1. Claude visible text stored as `"\\u0042ash"`: `search -s Bash` exits 1, while the equivalent non-literal `search -s 'B[a]sh'` returns the session.
2. A Codex `exec_command` shown under `-t` as canonical `Bash`: the literal exits 1, while `B[a]sh` returns the session.
3. A default-visible joined Pi failure that generates the canonical `Bash` tool name: the literal exits 1, while `B[a]sh` returns the session.

This violates the documented case-sensitive semantics and the candidate gate's conservative contract. Make strict eligibility and raw decode or normalization evidence independent of case mode. Keep the native scan only where raw bytes are a proved semantic superset. Add end-to-end regressions for the three boundaries above.

## 2. Medium: the real editable launcher's installed metadata still claims Python 3.13 support

The exact `~/.local/bin/ch` launcher is functional. Its Python 3.14.7 process imports this checkout and `src/chats/_native.abi3.so`. Its uv receipt still proves the editable install the user established with `uv tool install -e .`.

However, that tool environment's installed `chats-0.1.0.dist-info/METADATA` says `Requires-Python: >=3.13`. The source metadata and a fresh `cp314-abi3` wheel correctly say `==3.14.*`. The editable install's metadata snapshot predates the Python 3.14-only correction.

A project patch cannot update this user-owned installation snapshot. Do not claim that the real launcher's installed metadata is aligned until the same editable tool installation is refreshed. Project setup did not create or refresh that global install.

## Verification

The full runner passed 1,044 tests with 3 skips, all four performance budgets, and all 13 shell suites. Cargo test, check, and release build passed. A fresh wheel and source package built, and an isolated wheel install loaded the ABI3 module, asset, and CLI. I found no other high-confidence issue across the six Rust boundaries, packaging sources, ABI linkage, or integration. Slice Seven did not start.
