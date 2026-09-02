# Search runtime: authority map, boundaries, falsifiers

Owner: `search-runtime`. Written against HEAD `9bf1e06` plus the working tree.
Evidence is current source, the current test suite, and probes of the installed
binary. No production code has been edited.

---

## 1. The structural fact that shapes everything

`rust/lib.rs` is five lines:

```rust
pub mod codecs;
pub mod model;

#[cfg(any(feature = "python-bindings", feature = "extension-module"))]
include!("python_extension.rs");
```

`pyproject.toml` builds the `ch` binary with `--no-default-features`. So the
`ch` binary today compiles `codecs` and `model` only.

Almost every filesystem, inventory, and candidate-gate helper the native search
route needs is **already ordinary Rust**, but it lives inside
`rust/python_extension.rs` and is therefore invisible to the binary:

| Logic | Location | PyO3 in the body? |
| --- | --- | --- |
| Python-compatible path ordering key | `python_filesystem_path_key` | no |
| canonicalize-allowing-missing, symlink budget | `canonicalize_allow_missing*` | no |
| provider roots + classification | `classify_native_session_path_impl` | no |
| Claude / Codex / Pi traversal rules | `read_claude_jsonl_paths`, `read_recursive_provider_paths` | no |
| stat mtime with `-inf` sentinel | `stat_mtime` | no |
| full inventory | `discover_session_files_impl` | no |
| ASCII literal gate | `file_contains_ascii_impl` | **yes** (`&[Vec<PyBackedBytes>]` in the signature) |
| logical JSON-string gate | `LogicalJsonStringCandidateMatchers` | no |
| batched parallel gate | body of `files_contain_ascii_json_strings` | **yes** (logic lives in the `#[pyfunction]`) |
| backward last-timestamp scan | `find_last_jsonl_timestamp_impl` | **yes** (calls Python per line) |
| resolution-facet scan | `scan_resolution_facets_impl` | **yes** (calls Python per line) |

So the native search route does not need this logic written. It needs it
**lifted**, exactly as the first mate has now ruled.

---

## 2. Is the lift a root of the task DAG?

**Partly. It is a hard root for me and only a namespace event for the other two.**

`include!` splices `python_extension.rs` into the crate root, so its items sit
in the crate root namespace. Turning them into `mod` files moves every path and
rewrites one file end to end. Any parallel edit to that file is a textual
conflict. That part of the first mate's reading is right.

What it does **not** block: session-core's canonical model and codecs already
live in `rust/model.rs` and `rust/codecs.rs`, which the lift does not touch.
Query-semantics is entirely new files. Neither owner needs a single item from
`python_extension.rs`.

The only coupling to them is `rust/lib.rs`, a five-line file where each owner
eventually adds one `pub mod` line.

### Smallest complete lift

One mechanical slice, no behavior change:

1. Create `rust/paths.rs`, `rust/inventory.rs`, `rust/jsonl_scan.rs`,
   `rust/candidate_gate.rs`. Move the PyO3-free bodies in unchanged.
2. Change the two PyO3-typed impl signatures to owned Rust types
   (`&[Vec<Vec<u8>>]` instead of `&[Vec<PyBackedBytes>]`), and move the batch
   loop out of `files_contain_ascii_json_strings` into `candidate_gate`.
3. Extract the backward chunked line walk from `find_last_jsonl_timestamp_impl`
   into a `jsonl_scan` primitive that takes a line handler. The PyO3 wrapper
   passes a handler that calls Python. Nothing else about it changes.
4. Leave `python_extension.rs` holding only `#[pyfunction]` wrappers and PyO3
   glue, importing from the new modules.
5. `lib.rs` declares the four new modules unconditionally.

Falsifier for the lift: `./tests/run_all.sh | cat` is green before and after,
**and** a reviewer reading the diff finds no line that changes logic, only moves
and the signature de-PyO3-ing named above. If any behavior differs, the lift was
not mechanical and must be redone.

### How to keep the other two off the critical path

They are not idle behind it, and no split is needed. Recommended sequencing:

- The lift lands first as one commit. It is mechanical and reviewable in one
  pass.
- Session-core and query-semantics start immediately in new files and add their
  `pub mod` line to `lib.rs` after the lift lands. `lib.rs` is five lines, so
  serializing edits to it costs minutes, not a slice.

If the first mate prefers zero waiting at all, the alternative is that I land
step 5 (the `pub mod` declarations plus empty modules) in a five-minute
preparatory commit, then fill the modules. I do not recommend it: it creates a
window where `lib.rs` names modules that do not yet hold the logic, and it buys
almost nothing.

---

## 3. Who owns the pure-Rust line decoder

The first mate asked for a ruling input on the two callback-entangled helpers.
They split cleanly, and they are not the same seam:

**`find_last_jsonl_timestamp` — mine.** The Python callback is
`_jsonl_line_timestamp`, which is `json.loads(line)` then
`entry.get("timestamp") or entry.get("created_at")`. That is a one-field JSON
probe, not message parsing. Its only consumers are `PoolFilter.passes_path_for_date`
and `resolve._load_conversation_metadata` — date filtering and hit metadata, both
inside my scope. I will own the pure-Rust decoder in `rust/jsonl_scan.rs`.

**`scan_resolution_facets` — session-core's, and it is not on the native search
route at all.** Its callback extracts `custom-title` / `session_info` /
`thread_name_updated` / `summary`, which the session-core prompt names as
"metadata and facets". Its only consumer is
`resolve.extract_resolution_facets_from_jsonl`, used by identifier resolution
for `parse`, `name`, `rm`, and `info`. `cmd_search` never resolves an
identifier; search reads its facets through `SessionScan`. So the native search
route never calls it, and my lift moves it structurally without giving it a
native decoder.

**No fork of the scanning itself.** Both helpers share one backward/forward
chunked line walk in `jsonl_scan`, parameterized by a line handler. The PyO3
wrapper supplies a handler that calls Python; the native side supplies a Rust
handler. One authority for the scanning, two thin handlers.

---

## 4. Current authority for my scope

| Concern | Current authority | Native today |
| --- | --- | --- |
| Launcher grammar and routing | `rust/main.rs` handles `parse`; everything else `exec`s `ch-legacy` | routing exists, `search` not claimed |
| Search argument grammar and repairs | `cli.py:348-529`, `_repair_short_option_positionals`, `_short_uses_attached_value`, `_resolve_search_output_mode`, `_normalize_role_visibility_args`, `_resolve_message_selection`, `_resolve_thinking_mode`, `_resolve_show_tools`, `_resolve_short_policy` | none |
| Pool filter flags | `pool_filter.add_pool_filter_args`, `PoolFilter` | none |
| Date parsing | `date_filters.parse_date_filter` | none |
| Inventory and provider partition | `parsing._discover_session_file_rows`, `session_pool.SessionPool` | Rust, behind the feature gate |
| Newest-first order | `SessionPool.stat_mtime_sorted` reversed in `cmd_search` | mtime rows are native |
| Date path filters | `PoolFilter.passes_path_for_date` | last-timestamp scan is Rust with a Python callback |
| Directory filter | `PoolFilter.passes_path_for_index`, `passes_cwd` | none |
| Candidate gate policy | `_search_path_candidate_matches`, `_can_use_logical_json_string_gate`, `_term_path_candidate_matches`, `_ascii_literal_needle`, `_term_can_match_generated_marker`, `_term_can_change_under_json_decoding`, `_evaluate_prefilter` | scanners are Rust, policy is Python |
| Batch window (256) | `_iter_batched_ascii_literal_hits` | batch loop is Rust, inside the `#[pyfunction]` |
| `search . -ll` projection | `_can_project_dot_only_id`, `_stream_dot_only_id_projection`, `_project_default_dot_match`, `_entry_has_default_visible_search_facet` | none |
| Semantic confirmation | `_confirm_search_hit`, `_search_conversation_content` | none |
| Hit metadata | `resolve._load_conversation_metadata`, `parsing.get_display_session_id`, `formatting.build_metadata_text` | none |
| Result modes | `_display_hit`, `display_search_result`, `_render_conversation_panel`, `_build_search_list_row`, `_panel_title`, `_panel_facts_line`, `_display_list_summary`, `_list_show_provider` | none |
| Highlight integration | `_build_highlight_regex` into `formatting.build_messages_group` | none |
| Streaming, paging, early close | `_stream_search_results`, `_emit`, `console.StreamingPager` | none |
| Raw buffering | `_format_search_hits_to_raw` | none |
| Per-file errors | `print_error(f"Error processing conversation file {path}: {error}")` | none |
| No-hit and exits | `_emit_no_results`, exits 0 / 1 / 2 | none |

---

## 5. Proposed ordinary-Rust boundary

Feature-independent modules, compiled into both the binary and the extension.

Lifted from `python_extension.rs`:

- `rust/paths.rs` — OS-byte helpers, Python-compatible path ordering key,
  canonicalize-allowing-missing, provider roots, path classification, stat mtime.
- `rust/inventory.rs` — session discovery, sidechain rules, and the pool
  projections (`files`, `by_provider`, `by_stem`, `by_filename`,
  `stat_mtime_sorted`).
- `rust/jsonl_scan.rs` — forward and backward chunked line walks plus the
  pure-Rust first/last timestamp decoders and cwd probe.
- `rust/candidate_gate.rs` — `CandidateMatcher`, `EscapedRiskScalarTracker`,
  `logical_ascii_regex`, `LogicalJsonStringCandidateMatchers`, the single-file
  gates, and the parallel batch driver.

New, mine:

- `rust/search/mod.rs` — the `ch search` entry point.
- `rust/search/cli.rs` — search grammar, argparse-compatible errors and help,
  the positional repairs, output-mode resolution, role-visibility normalization.
- `rust/search/filters.rs` — `PoolFilter` equivalent and date parsing.
- `rust/search/plan.rs` — candidate planning, gate eligibility policy, the
  256-file window, conservative boolean prefilter.
- `rust/search/projection.rs` — the `search . -ll` projection.
- `rust/search/hit.rs` — `SearchHit`, hit metadata, YAML frontmatter.
- `rust/search/render.rs` — result modes, list rows, panels, rules, highlight
  integration.
- `rust/search/stream.rs` — streaming, `less -r` paging, early close.
- `rust/search/raw.rs` — raw buffering and the single-message special case.

---

## 6. Files: own, create, do not touch

**Own (existing):**

- `rust/main.rs` — the routing seam and the cutover point.
- `rust/python_extension.rs` — for the lift only, as one mechanical slice.
- `rust/lib.rs` — I add the lift's module declarations. Session-core and
  query-semantics add one `pub mod` line each, after the lift lands.

**Create:** the nine `rust/search/*` files and the four lifted modules listed
above.

**Do not touch:** everything under `src/chats/`. My scope needs zero Python
edits, including at cutover. `tests/` and fixtures belong to contract-owner.

---

## 7. The cutover, in file terms

Today `rust/main.rs` routes only `parse` natively:

```rust
if arguments.first().is_some_and(|argument| argument == "parse") {
    return run_parse(&arguments[1..]);
}
run_legacy(&arguments)
```

`ch search` therefore `exec`s `ch-legacy`, which is the Python entry point.

**The cutover is adding one branch to `rust/main.rs` for `search`.** Nothing
else changes. No Python is edited, added, or deleted. Consequences worth
planning around:

1. Production search stays fully Python until that branch exists, which is
   exactly what the charter requires, with no intermediate hybrid.
2. Reverting the cutover is deleting the branch.
3. `ch-legacy search` remains a working oracle right through the cutover, so
   differential proof can run `ch-legacy search ARGS` against `ch search ARGS`
   on the same corpus, in the same process tree, at any time. That is the
   strongest parity harness available to us and it costs nothing to keep.
4. The no-Python proof is process-level: `ch search` must not `exec` anything
   and must not load a Python runtime. Provable by running `ch search` with the
   `ch-legacy` executable removed from the launcher directory.

---

## 8. Falsifiers and definitions of done

Two disprovable falsifiers and two provable definitions of done per slice.

### Slice 0 — the lift

- **F0.1** A reviewer finds a diff line that changes logic rather than moving
  it or de-PyO3-ing the two named signatures. Disproves "mechanical".
- **F0.2** `./tests/run_all.sh | cat` differs before and after.
- **D0.1** `cargo build --no-default-features` succeeds and the binary links
  `inventory`, `paths`, `jsonl_scan`, `candidate_gate`.
- **D0.2** The full suite is green and `git diff --stat` shows
  `python_extension.rs` shrinking by roughly the moved volume with no net logic
  added anywhere.

### Slice 1 — launcher grammar and routing

- **F1.1** Any of a fixed argv corpus produces different stdout, stderr, or exit
  status under `ch search` than under `ch-legacy search`. Includes the missing
  positional (exit 2), unknown flags (exit 2), `--help`, `-ll` / `--only-id`
  forcing `--color never --no-paging`, `-r` implying `--no-metadata`, and the
  `--short` and `-t` positional repairs.
- **F1.2** `ch search --help` differs from `ch-legacy search --help` at any
  terminal width in a fixed set.
- **D1.1** A differential runner over the argv corpus reports zero diffs on all
  three streams.
- **D1.2** With `ch-legacy` absent from the launcher directory, `ch search`
  still answers, proving no `exec` on the search path.

### Slice 2 — inventory, filters, ordering

- **F2.1** Native inventory rows differ from `discover_session_files` rows on
  the fixtures already pinned in `tests/test_native_session_inventory.py`:
  hidden names, case-sensitive `.jsonl`, surrogate-escaped bytes, symlink rules,
  stat failures sorting first, equal mtimes stable.
- **F2.2** For a corpus with `-ma`, `-ca`, `-d`, and `-p` combinations, the
  native scan order or the filtered set differs from Python's.
- **D2.1** Native and Python produce identical ordered id lists for every filter
  combination on a recorded corpus.
- **D2.2** The probe-avoidance guarantees hold: `-ma` alone never reads a first
  timestamp, `-ca` alone never reads a last timestamp.

### Slice 3 — candidate planning and gates

- **F3.1** Any file the native gate rejects is one the semantic path would have
  matched. This is the safety-critical direction: the gate must be conservative.
  Probed with the parity trick the suite already uses — comparing a literal
  query against its regex twin, for example `error-order-probe` against
  `error-order-prob[e]`, which forces the semantic path.
- **F3.2** Native batching changes the interleaving of stdout hits and stderr
  per-file errors relative to the serial path.
- **D3.1** On the pinned adversarial corpus — U+212A, U+0131, JSON `\u` escapes,
  escaped slashes, control characters, split UTF-8 at a read boundary, Pi joined
  agent evidence, Codex tool-name normalization — native and Python emit
  identical ids and exit codes.
- **D3.2** Batches are exactly 256 files wide and confirmation is newest-first
  in input order, matching `test_eligible_ascii_literal_scans_fixed_windows_before_ordered_confirmation`.

### Slice 4 — result modes, streaming, paging, exits

- **F4.1** Byte-diff of `ch search` against `ch-legacy search` on a fixed corpus
  is non-empty for any of: plain `MATCHES`, `FULL`, `LIST`, `--only-id`, `--raw`,
  with and without `--no-metadata`.
- **F4.2** Ids do not appear on stdout before the scan completes, or `less`
  quitting early does not stop the scan.
- **D4.1** Byte parity on all five modes, plain output, on the recorded corpus.
- **D4.2** Streaming is observable: each id flushes before the next file is
  scanned, and early pager close halts the scan, matching
  `test_cmd_search_only_id_flushes_each_id_as_it_streams`.

### Slice 5 — colored output

Held deliberately separate. See the risk below.

---

## 9. Interface needs

**From session-core:**

1. A parse entry that takes file content plus flags and returns visible
   messages, cwd, summaries, and the latest custom title — the `SessionScan`
   equivalent. My confirmation step calls exactly this.
2. `render_message_inner_xml` equivalent. This defines search truth: a term
   matches a message if and only if it matches that rendered string.
3. `format_to_xml` and `format_to_raw` equivalents for `MATCHES`, `FULL`, and
   `--raw`.
4. The tool-id map, and `assign_progressive_shortening`, applied before
   rendering.
5. Display session id and forked-from per provider, for hit metadata.
6. **The colored renderable pipeline** — see the risk below.

**From query-semantics:**

1. A parsed query value with `evaluate(term_matches) -> bool`, and iteration
   over its terms.
2. Per term: the compiled matcher, `case_sensitive`, `pattern`, and
   `literal_candidate`. My gate policy reads all four; `literal_candidate` being
   `None` is what makes a term unprobeable.
3. A conservative prefilter evaluation where `NOT` always passes.
4. The parse-error type, so I can emit the error and exit 2.

The gate policy stays mine. Query-semantics owns what a term *means*; I own
whether a term may be probed against raw bytes.

---

## 10. Contract gaps for contract-owner

1. **Per-file error text is Python's.** `test_native_candidate_read_errors_keep_semantic_error_text`
   pins `[Errno 21] Is a directory:` reaching stderr. The native route must
   reproduce Python `OSError` message text, including the `[Errno N]` prefix and
   the `repr`-quoted path. `rust/main.rs` already has `python_io_error` for this
   on the parse path; the contract should state whether that is the required
   authority for search too.
2. **`--help` and usage text are argparse's,** including option ordering, the
   `session pool filters` group, and wrapping at terminal width. Needs an
   explicit width policy in the contract.
3. **The `MATCHES` plain-mode rule.** `get_console().rule(...)` prints a
   width-dependent `──── id ────` banner even with `--color never`. Its exact
   rendering needs pinning.
4. **Metadata frontmatter format.** `build_metadata_text` field order,
   `created` / `modified` as `"%Y-%m-%d %H:%M"` in local time,
   `matched_summary` repetition, and the `---` separator rules that differ
   between `LIST` and the other modes.
5. **Exit-status matrix.** 2 for a grammar or query error, 1 for no hits *and*
   for an empty candidate pool, 0 otherwise. Note that an empty pool exits 1
   with no hint text, while a no-hit search prints a hint unless `--only-id`.
6. **`--raw` single-message special case.** One session with exactly one visible
   message prints the bare body; anything else gets `Session <id>` headers and
   `\n\n---\n\n` joins. This is the one mode that must buffer.
7. **Relative date filters are evaluated against wall-clock now,** with months
   at 30 days and years at 365. Fixtures must not be time-fragile.
8. **`-d` resolves both sides of the comparison** via `Path.resolve()`, so
   symlinked cwds compare equal. Native must match.

---

## 11. Risks

**R1 — the colored path is the mission's largest unpriced item, and it is not in
my scope.** Colored `MATCHES` and `FULL` render a Rich `Panel` whose body comes
from `formatting.build_messages_group`. That body contains Rich `Markdown`
rendering of message text, a custom `LeftRail` renderable, `difflib` unified
diffs for `Edit`, and Pygments-backed `Syntax` highlighting for `Read` results.
Reproducing Rich's Markdown renderer and Pygments natively is a project in its
own right, comparable in size to everything else on this mission.

Three tests in `tests/test_colored_rendering.py` pin colored search, and they
assert substrings and SGR codes rather than byte-exact output, which is a real
mitigation. But the colored view is what a user actually sees, so a native
renderer that wraps differently or draws a different box is a visible regression
even with those tests green.

This belongs to session-core's rendering surface, not mine. I integrate with it;
I do not own it. I am raising it to the first mate and to session-core now
rather than at G4. My recommendation is that colored output be scoped as its own
slice with its own accept-or-escalate gate, and that the parity harness for it
be a byte diff of `ch-legacy search --color always` against `ch search --color
always` on a fixed corpus, with any diff treated as a falsifier.

**R2 — the gate policy is safety-critical and asymmetric.** A false positive
costs a wasted parse. A false negative silently loses a user's search result.
Every gate change must be probed in the losing direction, not merely tested.

**R3 — `python_extension.rs` is textually included,** so the lift is one
all-or-nothing edit to a file three owners depend on. Mitigated by landing it
first and by its being mechanical.

---

## 12. Judgment calls recorded

Per the team rule, decisions I took rather than stalling on:

1. **Dilemma:** whether the pure-Rust line decoders for the two callback
   helpers are one seam or two. **Chosen:** two — timestamps mine, resolution
   facets session-core's — with a single shared line-walk primitive.
   **Rejected:** one decoder owned by session-core, because the timestamp probe
   is a single-field date read with no message semantics, and routing it through
   session-core would couple my date filters to their parse model for no gain.
2. **Dilemma:** whether to split the lift so peers are never blocked.
   **Chosen:** do not split; land it whole and first. **Rejected:** a
   preparatory empty-module commit, because it creates a window where `lib.rs`
   names modules that do not hold their logic, and it saves only minutes.
3. **Dilemma:** whether to claim `src/chats/` files for the cutover.
   **Chosen:** claim none. The cutover is one branch in `rust/main.rs`.
   **Rejected:** deleting or shimming `cmd_search` at cutover, because keeping
   it intact preserves `ch-legacy search` as a live differential oracle and
   makes the cutover trivially reversible.

---

## 13. Inherited constraints (from `context-curator`, 2026-08-28)

Hard-won results from the earlier team's cycle on branch `0ffde41`. None is
discoverable by reading current code. All bind the native runtime design. I have
checked each against `main`'s source; agreements and one refinement noted.

**C1 — Date filters read content timestamps only. Never stat mtime.**
An mtime short circuit is unsound: imports, copies preserving foreign clocks,
`touch -t`, and restore tools all produce files whose mtime precedes their
content timestamp, so a pure-mtime negative drops real hits. The guarded variant
is closed too, and the reason is the useful part: `-ca`'s content probe *is* the
cheap first-timestamp read, and `-ma`'s last-timestamp scan already reads only
4 KB tail chunks backward, so guarding reinstates identical I/O plus extra stat
calls. It cannot win on speed. My section 8 D2.2 already forbids the extra
probes; this closes the idea permanently rather than leaving it as an
optimization to rediscover.

**C2 — Never index a string with offsets measured on a lowercased copy.**
`İ` grows 2→3 bytes when lowercased and the ligatures `ﬀﬁﬂﬃﬄ` shrink 3→2. The
earlier team hit a mid-render abort (exit 101, out-of-bounds slice, stdout
truncated mid-panel) and, below the abort threshold, silently painted wrong
spans. Correct shape: walk the original characters and fold each comparison
through the same equivalence the search truth uses, so painted spans and matched
spans are defined identically. Selection rule: earliest start wins, longest
needle on ties. The case-sensitive path needs its own check — folding the
haystack while keeping an original-case needle paints nothing at all. An
ASCII-only fixture corpus cannot see any of this.

**C3 — A mid-window filter error flushes the accumulated window before it
prints.** Otherwise a later directory-filter decode error can print ahead of an
earlier semantic read error, changing observable output order. `main` already
does this in `_iter_batched_ascii_literal_hits`. My F3.2 is the falsifier.

**C4 — The provider-column predicate reads discovery rows, not gate survivors.**
`_list_show_provider` receives the candidate set built from the pool's provider
partitions — every file, or the single `-p` provider — before any gate runs.
Easy to get backwards; getting it backwards changes whether the provider column
appears.

**C5 — Windows scan in parallel, confirm serially in input order.** The gate may
scan a window in parallel but returns decisions in input order, and confirmation
runs serially before the next window opens. That is what preserves newest-first
streaming. Two measured constants: 256-file windows
(`ASCII_LITERAL_CANDIDATE_WINDOW_SIZE`, `commands/search.py:102`) and a 128 KiB
native read buffer. The 256 knee was measured — 128 / 256 / 512 completed in
1.422 / 1.188 / 1.182 s, and 512 bought 6 ms of completion while adding 207 ms
to the first barrier. Treat 256 as evidence-backed, not arbitrary.

**C6 — Collapse the duplicated gate predicate.** `_can_use_logical_json_string_gate`
(`commands/search.py:1006`) and `native_gate_bypassed` (line 1048) spell the same
nine visibility conditions, once negated and once positive, so a tenth flag has
to be added twice or the gates diverge silently. The native port must collapse
them into one predicate. Two asymmetries are real and must survive the collapse:
`message_selection == ALL` belongs only to eligibility, because raw-byte presence
is selection-independent; and `show_tools` needs an explicit truthiness test,
since it can be a tool-filter list rather than a bool.

**C7 — Decide the stderr wrapper early.** The earlier branch deliberately kept
three stderr line-wrap implementations: one character-counting and not
width-aware, one UnicodeWidth-aware, one preserving trailing spaces. Wide
characters therefore wrap differently per journey, and that team judged byte
identity across journeys unprovable. My scope emits per-file errors and the
no-hit hint to stderr, so this is on my acceptance path. It wants a decision
before implementation, not a discovery at acceptance.

---

## 14. Rulings (from `search-firstmate`, 2026-08-28)

Settled decisions. Where these conflict with an earlier section, these win.

**R-1 — Scope: the search route only.** The branch's `main.rs` routing is
adopted for `search` and rejected for the default session journey. The
`run_legacy` fallthrough stays, so default session parsing remains on
`ch-legacy` per the charter. Supersedes the open question in
`branch-boundary-comparison.md` section 3.1.

**R-2 — The differential oracle is not deleted.** The Python search
implementation stays until the byte harness is green. Deleting it becomes its
own final slice, gated on that harness. The branch's commit order — which stubs
`commands/search.py` and removes `search_query.py` and `session_scan.py` — is
explicitly not inherited. Binding on the whole team. Confirms section 7 and
`branch-boundary-comparison.md` section 3.2.

**R-3 — One stderr wrapper, not three.** The branch kept three line-wrap
implementations because byte identity across three journeys was judged
unprovable. This mission is search alone, so the question collapses: the search
route reproduces exactly the bytes `ch-legacy search` produces, proven by diff.
Closes C7 in section 13, which asked for this decision.

**R-4 — The shared line-walk primitive is the accepted fix** for the two
duplicated authorities found in the branch's lift (`last_timestamp`,
`resolution_facets`). Confirms section 2 and section 3.

**Consequence for the lift.** Under R-1 through R-4, adopting the branch is a
reconciliation rather than a merge. The lift's shape is unchanged from section
2, but its target is now the branch's `inventory.rs` and `scanner.rs` rather
than four new modules of my own, and its first job is collapsing the fork rather
than creating the split.

---

## 15. The `.isascii()` guard is a correctness invariant, not a filter

From `query-semantics`, measured, and it changes how I must treat one line of my
own eligibility policy.

`search_query.py` carries **two case models that genuinely disagree**. Matching
uses `re.IGNORECASE`, which is single-codepoint lowering plus a fifty-entry
fixes table. `literal_candidate` uses `str.casefold()`, which is full case
folding. For the pattern `ß`, `literal_candidate` is `'ss'` while the compiled
regex does not match `ss`.

So **`literal_candidate` is not a sound lower bound for the regex in general.**
What makes every byte-gate path in `commands/search.py` sound today is the
`.isascii()` guard, because the two case models coincide on ASCII and only on
ASCII.

Consequence for my gate policy: `.isascii()` is load-bearing for correctness. It
is not one performance condition among the others in
`_can_use_logical_json_string_gate` and `_ascii_literal_needle`, and it must not
be relaxed to admit non-ASCII literals to a byte gate as an optimization. Doing
so lets the gate reject a file the authoritative matcher would have matched —
the silent-loss direction. It gets a pinned test of its own, phrased against the
`ß` case.

Related, and closed: the twenty-scalar case-fold risk list in the existing gates
answers *rejection safety* — which non-ASCII scalars fold onto ASCII so the gate
must defer. That question is settled and should not be re-funded. What stays
open is authoritative matching, which the gates never touch. The two must not be
conflated at G2.

Also settled with `query-semantics`: an invalid regex is not an error. It falls
back to a literal search at `search_query.py:102-104`, so the set of patterns
CPython *accepts* is itself part of the public contract, and a native validator
that accepts a different set silently flips a pattern between regex and literal
with no error anywhere. Only a malformed boolean query raises and exits 2.

---

## 16. Age rendering has no clock seam, and that breaks the harness

Found while checking `reviewer-profiler`'s seven age-bucket contract failures.
They were reported as fixture rot. They are not — the fixtures are correct, and
they will fail again after any regeneration.

The colored list fixture pins `38;2;135;140;146` on the age field. That is
`#878c92`, which `age_style` returns for the 1-to-7-day bucket. The corpus
normalizes the age *label* to a `{AGE}` placeholder and leaves the age *style*
baked, though both derive from the same clock. The fixture therefore asserts
"this session is between one and seven days old", which was true when it was
generated and becomes false at 30 days and again at 365.

Age comes from wall-clock now with no injection point on either side:
`datetime.now()` at `commands/search.py:721`, `chrono::Local::now()` at the
branch's `search_engine.rs:7`. So the corpus cannot freeze the clock, and this
recurs on a timer rather than once.

Normalizing the label without the style is worse than normalizing neither,
because the field then looks handled.

**The consequence reaches past the fixtures.** A byte diff between two binaries
is meaningless for any age-bearing output unless both agree on now, and that is
every list row and every panel title. Any differential harness has to settle
this before it is built.

Two options are with `search-firstmate`: normalize the style token too, which is
free but deletes all coverage of `age_style`'s four buckets and their
boundaries; or add a clock injection point read once at startup so the harness
can pin now for both binaries. I recommended the second and named the objection
myself — it is production surface added for testability. Age rendering is one of
the few places where identical inputs legitimately differ by day, which is why I
think a seam is warranted rather than merely convenient. The ruling is not mine.

---

## 17. Wrong behaviours in my views that must be preserved

From `search-firstmate`, via `contract-owner`'s characterization. These are
defects, and a port that fixes them diverges. Both reach code I own.

**The age label and the age colour disagree by one bucket.** `humanize_age` and
`age_style` carry separate, unaligned thresholds, so a row reading `3d` is
painted with the *week* colour, `2w` with *month*, and `1mo` with *old* —
consistently one bucket older than its own label, at every age. Driving both
from one table is the obvious simplification and the one a reviewer would ask
for, and it silently repaints every coloured result row.

`humanize_age` also uses 30-day months and 365-day years, so twelve months is
360 days and an age between 360 and 365 days renders `12mo` before jumping to
`1y`.

**This is the highest-risk item on the mission right now** because
`contract-owner`'s comparator normalizes the age SGR away, so it is the one
dimension where a regression fires no gate and looks correct. It is being pinned
at unit level rather than waiting for the clock seam. That is the same hole I
described in section 16 from the other side: there, the label was normalized and
the style was not; here, the style is normalized and so nothing checks it.

**`collapse_home` matches a string prefix, not a path boundary.** So
`/Users/giladbarneaX/dev/chats` renders as `~X/dev/chats`, and any sibling
directory whose name starts with the home directory's name is mangled. It
reaches both the list row and the panel title. A port that compares path
components produces the *correct* answer and therefore diverges.

Two more are `session-core`'s and reach my views: `elide_to_width` counts code
points, so wide text overflows its own budget — `你好你好你好你好` at a budget
of 8 returns unchanged at 16 columns — and `truncate_middle` is
normalization-sensitive for the same reason. `elide_to_width` has four call
sites in `commands/search.py`, across both the list and panel views. The
codebase already counts in three different units, including UTF-16 code units in
Pi `responsePreview` truncation, so any port that unifies them changes
behaviour.
