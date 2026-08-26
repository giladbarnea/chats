# Review: native hot-path helpers (`chats._native`)

Scope: `rust/python_extension.rs` (1,451 lines), thin re-export in `rust/lib.rs`, across `ac6599cc..3078625`. Reviewed every Python call site it feeds (`parsing.py`, `commands/search.py`, `pool_filter.py`, `session_pool.py`, `session_scan.py`, `info.py`, `resolve.py`, `name.py`) and the legacy pre-rewrite implementations for parity. Ran all four dedicated suites (92 passed) plus the Rust unit tests; verified several subtle behaviors empirically.

## Findings

### 1. Mixed path-parameter conventions at the FFI boundary break non-UTF-8 session paths

The module's convention is byte-level paths: `discover_session_files` takes and returns raw bytes (`PyBytes`), `scan_resolution_facets` and the three ASCII scanners take `PyBackedBytes`. Two functions deviate by taking `&str`:

- `find_last_jsonl_timestamp(path: &str, ...)` — **new in this range** (`e068be0`). PyO3 rejects surrogate-containing Python strings during `&str` extraction, so it raises `UnicodeEncodeError` on any path containing invalid UTF-8 bytes (verified empirically). The legacy `_find_last_timestamp` opened files in binary mode and handled such paths fine.
- `classify_native_session_path(path: &str, home: &str)` — same flaw, but it predates the range (baseline `ac6599cc`); the rewrite perpetuated it instead of normalizing while its new siblings all moved to bytes.

This is reachable in production: a session file whose name contains non-UTF-8 bytes is *discovered* fine (native inventory returns raw bytes; `os.fsdecode` round-trips them — pinned by tests), but then crashes downstream:

- `pool_filter.passes_path_for_date` → `get_jsonl_last_timestamp(str(path))` → crash on date-filtered searches.
- `_select_jsonl_session_adapter(str(source_path))` → `classify_native_session_path` → crash from `SessionPool.discover`'s re-classification of unclassified rows, `name.py`, `rm.py`, etc.

Note the asymmetry inside one pair: `get_jsonl_first_timestamp` (pure Python) still works on such paths while `get_jsonl_last_timestamp` now crashes. Legacy behavior was graceful end-to-end.

Fix shape is mechanical: accept bytes like every sibling (`path_from_python_bytes` already exists) and let callers pass `os.fsencode(...)`.

### 2. `JsonEscapeValidator` (~130 lines + state machine + tests) is additive-only conservatism — removable without correctness change

In `LogicalJsonStringCandidateMatchers::file_contains`, every validator failure path (malformed escape, bad hex digit, unpaired surrogate, escape truncated at EOF) returns `Ok(true)` — i.e., *defer* to semantic confirmation. It can never flip a decision toward rejection.

Meanwhile the logical ASCII regex already models exactly how JSON escapes can encode ASCII bytes: raw byte, `\/` for slash, and `\uXXXX` with hex-case variants per byte. Completeness holds because the authoritative parse is per-line `orjson.loads` with drop-on-error (`_iter_jsonl_entries`), so only validly-encoded lines contribute decoded content, and each ASCII char of a parsed string has one contiguous raw encoding covered by the regex alternatives. A malformed-escape region can never produce semantic content, so deferring on it converts a would-be fast reject into a slower full read+parse+render — pure performance cost, no correctness save.

That contradicts the project's own tenets ("no defensive programming", "complexity is the enemy") and the module contract's "no parsing semantics" stance — this state machine *is* JSON parsing semantics. Caveat: current tests pin defer-on-malformed outputs, so removal requires deliberate expectation updates (the updated expectations would be semantically correct).

### 3. Measured opportunity: eager per-path canonicalization dominates native discovery (perf, not regression)

On this machine (~5,011 real session rows): native `discover_session_files` ≈ 78 ms/call, of which ~43 ms is `classify_native_session_path_impl` canonicalizing each discovered path independently — even though each path's provider root was just canonicalized into the cache. Incremental component-wise resolution reusing cached canonical roots would reclaim most of that. For fairness: legacy full-pool discovery (glob + per-file adapter sniffing) measured ≈ 78 ms too, so this is not a regression vs what consumers needed anyway — but discovery sits on the startup path of every inventory-consuming command, and halving it aligns with why this rewrite exists.

## Verified parity-correct (no action needed)

These were checked because they looked suspicious and survived scrutiny:

- **Sort order**: Rust's component-wise code-point key matches Python 3.14 `Path` comparison (verified empirically — pathlib compares part tuples, not raw strings); group order [claude, codex, pi] matches legacy claude-glob + adapter-list order; surrogate-escape ordering (`é` < U+DC80) exact.
- **Backward timestamp scanner**: fragment assembly across 3+ chunk boundaries, boundary-aligned newlines, final unterminated line, whitespace trimming set, invalid-UTF-8 lines skipped, non-JSONDecodeError callback errors → `None`/mtime fallback — all match legacy `except Exception: pass`.
- **Facet scanner**: universal-newline splitting (\r, \n, \r\n incl. \r\n spanning chunks), UTF-8 validation *before* the marker gate (pins UnicodeDecodeError propagation parity with text-mode iteration), OSError→(None, []) discarding accumulated facets — all legacy-exact.
- **Candidate matcher**: Horspool shift-table construction and boundary-window coverage are correct; case-insensitive needles are pre-casefolded callers-side; risk-character deferral list matches CPython IGNORECASE fold targets (Kelvin sign, ß, İ, ligatures…).
- **Symlink rules**: fixed-depth Claude traversal follows directory symlinks (matching glob semantics), recursive Codex/Pi traversal does not (`DirEntry::file_type` is lstat-based) — pinned by tests and legacy-consistent.
- **mtime**: float bit-parity with `st_mtime`; NEG_INFINITY sentinel coherent with `session_pool._safe_stat_mtime`.
- ARCHITECTURE.md's description of this module is accurate; no doc/code contradictions found.

Tests across all four dedicated files are substantive: they pin real product-derived behavior (chunk-boundary straddles, multi-MB lines, int-digit-limit aborts, surrogate round-trips, 1 MiB read boundaries), not implementation echoes.
