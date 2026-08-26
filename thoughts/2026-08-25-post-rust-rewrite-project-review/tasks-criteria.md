# Task criteria — post-Rust-rewrite review follow-up (2026-08-26)

One falsification set + one definition-of-done set per task. Authored by scope-matched reviewer personas; ground truth lives in each `<scope>/review.md`.

## T3 — Contract suite validates a checkout-built launcher

**Falsify if:**
1. Stale swap: copy `/Users/giladbarnea/dev/chats-cycle02-ox/target/release/ch` over every launcher path the suite resolves, then run `uv run pytest tests/test_parse_command_contract.py -q`. Exit 0 disproves the fix — `test_uncompleted_public_journeys_keep_exact_legacy_behavior` must fail loudly against that artifact.
2. Missing launcher: remove `target/release/ch .venv/bin/ch`, rerun. Silent skip or pass without a build/provenance error disproves the fail-loudly half.

**Done when:**
1. `rg -n REAL_INSTALLED_CH tests/test_parse_command_contract.py` shows it deleted or confined to one provenance guard; all `_run_ch` targets come from `cargo build --release --bin ch` in this repo; suite green while `~/.local/bin/ch` still symlinks the stale artifact.
2. An explicit guard rejects any binary not matching freshly built `target/release/ch` (sha256 equality, or absence of HEAD-absent strings like `logicalParentUuid`) and names the reason in the failure.

## T2 — Delete JsonEscapeValidator

**Falsify if:**
1. Semantic divergence: file containing `{"content":"bad \x escape"}` plus one valid match, scanned before (baseline) vs after deletion via `file_contains_ascii_json_strings`; any output difference on malformed-escape or invalid-UTF-8 inputs disproves correctness-neutrality.
2. Recall loss: fuzz ~1k random JSON-escaped needle/file pairs comparing native scan against Python semantic-reference search; any missed true match disproves regex completeness.

**Done when:**
1. `rg -n "JsonEscapeValidator" rust/python_extension.rs` returns nothing; `cargo test` passes in `rust/`.
2. `tests/test_native_ascii_candidate_scanner.py::test_logical_json_uncertainty_defers_to_semantic_confirmation` updated to assert no-defer behavior for malformed escapes; `uv run pytest tests/test_native_ascii_candidate_scanner.py` green.

## T1 — Honest EPIPE handling

**Falsify if:**
1. `cargo build --release`, then pipe a large JSON through `target/release/ch parse /dev/stdin | head -c200`. Any stderr containing `Traceback (most recent call last):`, `cli.py`, `parse.py`, or an absolute path under CARGO_MANIFEST_DIR disproves the fix.
2. `rg -n "print_broken_pipe_traceback|CARGO_MANIFEST_DIR" rust/main.rs` still matches after T1.

**Done when:**
1. `rust/main.rs` handles `std::io::ErrorKind::BrokenPipe` at the write site (~line 210) via silent exit 0 or one plain stderr line, no Python-frame text anywhere; probe 1 exits cleanly with clean stderr.
2. Permanent test exists — `#[cfg(test)]` case in `rust/main.rs` asserting the handler's output contract, plus shell regression in `tests/test_basic.sh` piping through `head -c200`; both pass under `cargo test` and `bash tests/run_all.sh`.

## T4 — Empty-string optional-field parity

**Falsify if:**
1. Feed `{"type": "user-message", "branch": "", "status": "", "agent_id": ""}` through native `ch parse`; any of `branch=""`, `status=""`, `agent_id=""` in XML attributes — or those keys with `""` values in the JSON direction (`codecs.rs:557/1405`) — disproves parity.
2. After the change, `tests/run_all.sh` shows any legacy-vs-native golden diff on existing fixtures in `tests/data/parse-command-fixtures/expected/`.

**Done when:**
1. New fixture pair `tests/data/parse-command-fixtures/inputs/empty-optionals.json` + `.xml` with matching `expected/` files showing bare `<user-message i="1">`, registered in `MANIFEST.json`, passes.
2. `bash tests/test_branch_marking.py` and full `tests/run_all.sh` exit 0 with empty-string fields absent from both directions; round-trip JSON→XML→JSON yields no `""` keys.

## Gate G

Full `./tests/run_all.sh | cat` green once T1–T4 land.
