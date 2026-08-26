# Review: legacy-parsing-model (provider parsing + shared model/rendering)

Scope: `src/chats/parsing.py`, `src/chats/model.py` across ac6599cc..3078625, plus the rendering/formatting modules they feed (`formatting.py`, `tools.py`, `theme.py`, `shortening.py`, `parts.py`, `lexer.py`). Method: read both changed files in full before/after, read the unchanged renderers in full for coupling, traced the native seams (`find_last_jsonl_timestamp`, `scan_resolution_facets`, `discover_session_files`, `classify_native_session_path`) down to the Rust implementations, and ran the test suites plus targeted empirical probes.

## Verdict

The legacy parsing/model migration is in good shape. The Python→Rust seams are faithful ports with exact semantic parity where it matters; the model.py reshuffle is a clean deletion with no dangling consumers. Two minor confirmed issues below; no correctness regressions found.

## Findings

### 1. Dead `TOOL_SCHEMAS` import left behind by the migration (minor)

`src/chats/model.py:13` imports `TOOL_SCHEMAS`, whose only consumer was `_append_tool_input` — one of ~260 lines of `-f json` reconstruction deleted when the conversion moved to Rust (`rust/model.rs` ports it as its own `tool_input_needs_wrapper`). The symbol now appears exactly once: on the import line. One-line cleanup.

```python
from .registry import TOOL_SCHEMAS, ContentBlockType  # TOOL_SCHEMAS unused
```

### 2. Native discovery's "Python-compatible" sort key doesn't match pathlib ordering (low severity, fidelity bug)

`read_claude_jsonl_paths` / `read_recursive_provider_paths` sort with `python_filesystem_path_key` — a per-component codepoint vector that even handles surrogate escapes — clearly intended to reproduce the old `sorted(<Path globs>)` order. But pathlib compares paths as **full normcased strings** (`PurePath.__lt__` → `self._str_normcase < other._str_normcase`), not component-wise. The two orders differ whenever paths diverge at a separator-vs-intra-component boundary involving characters below `/`:

```
python pathlib sorted : [.../foo-x/baz.jsonl, .../foo/bar.jsonl]   # '-'(0x2D) < '/'(0x2F)
component-wise sorted : [.../foo/bar.jsonl, .../foo-x/baz.jsonl]
```

Old code sorted Claude/Codex/PI glob results as Path objects (string comparison); the new Rust inventory sorts them component-wise, so cross-project ordering can differ from pre-rewrite behavior (plausible here: Claude project dirs are dash-prefixed like `-Users-...`). Observable impact is near-nil today — recency ordering is mtime-dominated and stems/filenames are unique — so this is a fidelity deviation from the port's own stated intent, not a user-visible bug yet.

### 3. Attribution correction on the failing contract test (cross-scope; deferred to cli-router-commands)

`test_parse_command_contract.py::test_uncompleted_public_journeys_keep_exact_legacy_behavior` fails at HEAD on this machine. My initial attribution — "macOS 26 dyld goes silent across exec" — was wrong; I retract it after peer counter-evidence and controlled re-experiments:

- HEAD-built `.venv/bin/ch` execs ch-legacy on search and default-parse routes and produces 34 python loader-trace hits under a single PID: dyld traces across exec fine on this OS.
- The real cause: `~/.local/bin/ch` is a newer wip-cycle02 build (embeds `"logicalParentUuid"`, absent from HEAD `rust/`, present in `chats-cycle02-ox/rust/session_provider.rs`) that handles those journeys natively without exec.

So the assertion itself is sound against HEAD artifacts; the defect is that the contract suite binds `REAL_INSTALLED_CH` to an external mutable path not built from this repo state. cli-router-commands owns that seam finding; nothing further from my scope.

## What I verified clean

- **Adapter selection**: `_select_jsonl_session_adapter` is byte-identical between base and HEAD (Rust path classifier first, then first-entry signatures, else ValueError). No classifier-fallback regressions.
- **Discovery parity**: group order (claude→codex→pi) matches old enumeration order; sidechain exclusion (`provider==Claude && filename starts "agent-"`) reproduces the old `is_sidechain_session_file` filter exactly, including its raise-on-unclassifiable behavior for provider-None rows; mtime fallback (`-inf`) matches `_safe_stat_mtime`.
- **Backward timestamp scan**: chunked backward reader, fragmented-line reassembly, skip-on-JSONDecodeError/UnicodeDecodeError, abort-on-other-exception all match old semantics. Measured on a ~40 MB worst case: 0.179s vs 0.212s for the old pure-Python loop — the per-line FFI callback design is *faster*, not a regression.
- **Resolution-facet scan**: markers, summary/title extraction, line splitting (`\r\n`/`\n`/`\r`), OSError→(None, []) discard semantics, and even the raise-on-invalid-UTF-8 parity are preserved. The decode-to-raise trick in `accumulate_resolution_line` is convoluted but deliberate; pyo3 has `PyUnicodeDecodeError::new_err` if anyone wants it cleaner someday.
- **model.py reshuffle**: pure deletion of the JSON reconstruction block; no dangling references anywhere (src, tests, or rust); formatting/tools/parts/theme/shortening/lexer all consume the model coherently; `xml_transport.py` deletions removed only functions whose sole consumer (`xmlmd.py`) was deleted in the same range.
- **SHORT_SPEC.md vs shortening.py**: walked every documented accept/reject case through `parse_short_spec`/`looks_like_short_spec` — no contradictions (file untouched in this range).
- **Tests**: `test_timestamp_scanner`, `test_native_session_inventory`, `test_resolution_facet_scanner`, `test_parse_round_trip`, `test_python_runtime` all pass. The only failure in my scope is the cross-scope installed-binary issue above.
