# Search Pipeline Review — post-Rust-rewrite (`ac6599cc..3078625`)

Scope: Python search orchestration over the native gate — `commands/search.py`, `search_query.py`, `session_scan.py`, `session_pool.py`, `pool_filter.py`, `date_filters.py`, `ordering.py`, plus their FFI seams into `chats._native`.

## Verdict

This is the best-covered area of the rewrite, and it holds up. I traced every seam between the Python orchestration and the three native scanners (`file_contains_ascii`, `file_contains_ascii_json_strings`, batched variant), re-derived the soundness argument for both gates, and ran two empirical probes. No correctness regressions found. Two simplification/maintenance findings below; both low severity.

## Findings

### 1. Nine-flag visibility predicate duplicated between the two gate paths

`_can_use_logical_json_string_gate` (gate *eligibility*) and `native_gate_bypassed` inside `_term_path_candidate_matches` (~line 1048) each spell out the identical nine visibility conditions (`show_thinking`, `show_tools`, `show_agents`, `show_custom`, `show_branches`, `show_plans`, `shorten`, `shorten_progressive`, `shorten_thinking`) — once negated, once positive. Adding a tenth visibility flag requires touching both sites or the gates diverge silently.

Two asymmetries already invite misreading: `message_selection == ALL` appears only in the eligibility check (justified — raw-byte presence is selection-independent, but nothing documents why the lists differ), and only `show_tools` gets `bool()` wrapping (required — it can be a non-empty `ToolFilter` list). A single shared predicate, e.g. `flags.searches_default_visibility()`, collapses both sites and makes the `message_selection` exception explicit at its own site.

### 2. Redundant double-check in `_confirm_ascii_literal_window`

```python
if len(decisions) != len(window):
    raise RuntimeError("native candidate decision count differs from input count")
for (conv_file, _pi_session), candidate_matches in zip(window, decisions, strict=True):
```

`zip(..., strict=True)` already raises on length mismatch. One guard suffices; keep whichever fails louder.

### Observation: multi-term queries lost the cheap post-read rejection layer

At base, a second content-level gate (`_search_candidate_matches(content, …)`) rejected files after `read_text` but before `SessionScan` parse+render. The rewrite removed it. For eligible single literal terms the new decoded-JSON-string native gate more than compensates. But boolean queries take the serial path where each term opens/scans the file separately, and any surviving file goes straight from read into full parse + XML render of every message. Files where term A passes but term B never existed now pay full parse+render cost instead of a cheap casefold-substring miss. Correctness-neutral; magnitude unclear since common-word terms pass anyway. Worth revisiting only if perf budgets creep again.

## Verified clean (checked explicitly, not just by tests)

- **Native-gate bypass logic (~1048)**: every bypass branch returns `True` (conservative direction only). Traced each visibility flag against rendering: `AdditionalContext` synthesis, `ExitPlanMode` markers, progressive-shortening elision, and backslash-containing patterns (raw JSON stores `\\`, rendered text has `\` — blanket bypass is *required* here for soundness). No false-negative path found.
- **Case sensitivity ↔ Rust scanner**: needle normalization is consistent end-to-end (`casefold()` ≡ ASCII lower given `.isascii()` guards); KELVIN SIGN / U+0131 risk scalars defer to semantic confirmation on both Python and Rust sides; split UTF-8 code points carry across 128 KiB read boundaries; escape-form matching covers upper/lower hex variants and `\/`. Differential-oracle tests (`optimized == semantic_reference`) cover all of these.
- **Batched windowing**: fixed windows of 256 scanned in parallel via rayon, survivors confirmed strictly in input order; mid-window filter errors flush the accumulated window *before* printing the error, preserving output order. Native IO errors map to `true` (`unwrap_or(true)`), matching the single-file wrapper's `except OSError → True`.
- **Gate-vs-rendering concatenation**: parsers join adjacent text blocks with `"\n\n"` and rendering joins parts with `"\n\n"`, so a needle spanning two JSON strings can never appear in rendered output without containing control characters — which are excluded from gate eligibility. The `test_logical_match_does_not_cross_json_string_boundaries` assertion is therefore sound, not lucky.
- **XML-entity literals** (`&amp;`, `&lt;` …): probed empirically — they miss sessions whose visible text contains bare `&`/`<`. This is *encoded intent* (`test_cmd_search_xml_transport_entity_reaches_semantic_confirmation`: "XML-only transport entities stay outside search semantics"), not a blindspot.
- **Pool discovery**: native rows preserve old ordering semantics (claude → codex → pi groups, Python-comparable sort key, stable mtime sort); sidechain filtering change is semantics-preserving because only the claude adapter defines a real `is_sidechain_path` and Rust excludes `agent-*` under the same flag.
- **Timestamp/date-filter plumbing**: backward last-timestamp scan moved to Rust faithfully; `-ma`/`-ca` lazily probe only the timestamp each needs (tests assert zero wasted probes).
- **Tests**: substantial throughout — differential oracles against regex-forced serial search, falsifying guardrails (projection must return UNKNOWN for claude files; equivalence corpus includes a live-divergence trap entry), boundary-crossing fixtures at exactly 1 MiB. 162 scope tests + 4 perf budgets pass at HEAD.

No regressions, contradictions with specs, or over-engineering found beyond the above.
