# deletion-owner — resume state

**Seat opened 2026-09-02** on `prompts/deletion-owner.md`. Five items, in order, and
no other scope.

**Context: no current reading.** The harness has volunteered no context figure this
session. The last value on this desk is **90% of the context window**, recorded by
`parity-finisher` at close on 2026-09-02 — **the context-window percentage, not a
session token budget.** Not derived.

## Status in one line

**Items 1 and 2 are done and green. Item 3 is handed to `search-firstmate` and is
not this seat's to make. Item 4's list is DERIVED and reported, and nothing has
been deleted.** Two findings and one gap in an inherited document are reported
rather than fixed, per the brief's scope rule.

## Digests, re-derived immediately before every run below

    oracle route digest  sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
    rust tree digest     7b3267a6a22e1f7c54910fcc6d92695cf37b2aad7827ce509998de735a66e10b

Both identical to what `parity-finisher` recorded at close, so **nothing moved
across the seat change.** The recipe is `probes/digests.py` — the oracle half is
imported from `tests/oracle_digest.py`, never restated; the rust half is sha256
over `rust/**/*.rs` in sorted order, and it **reproduces `parity-finisher`'s
`7b3267a6a22e` exactly**, which is what says the recipe is theirs and not a second
one.

## 1 — the gate wiring. Landed.

`tests/test_legacy_selection_frozen.py`'s `posix_class_future_warning` row now
defers to the shared divergence authority instead of asserting byte-parity.

**The authority gained a name; it did not gain a copy.**
`tests/deliberate_divergences.py` now carries:

- `SELECTION_WARNING_DIVERGENCES = ("posix_class_future_warning",)`
- `WARNING_PREFIX` and `WARNING_SOURCE_ECHO`, **moved** out of
  `test_deliberate_divergences.py`, which now imports them.

**Why a separate name rather than an addition to `DELIBERATE`.** These are
`query_pattern_corpus.DEFECT_PATTERNS` keys, not manifest case ids, and
`test_the_set_of_deliberate_divergences_is_exact` compares `DELIBERATE` against
what the two manifests actually produce. A foreign id there fails that assertion as
an allowance pointing at nothing. **The rule is one authority, not one tuple.**

**The exempt row is not skipped.** `_assert_only_the_missing_warning_decoration`
asserts the exit status and stdout still reproduce the recording, that stderr still
differs, **and that the difference is still exactly CPython's warning decoration** —
`recorded == WARNING_PREFIX + native + WARNING_SOURCE_ECHO`. It is the frozen
successor of `test_a_warning_divergence_is_only_the_missing_decoration`, which
asserts the same bound against the live route and dies with it.

### The three falsifiers, RUN rather than asserted

Each was produced by editing the authority, running the row, and restoring the file
— **verified restored byte-identical, sha256 `af37fa6a172d5009…` before and after.**

| falsifier | what was done | it failed saying |
| --- | --- | --- |
| **A** — an id that leaves the authority | `SELECTION_WARNING_DIVERGENCES = ()` | `defect pattern posix_class_future_warning: stderr differs from the recording.` — byte-parity restored **by itself** |
| **B** — an id that stops diverging | added `digit_escape_is_unicode`, which matches today | `…is listed in SELECTION_WARNING_DIVERGENCES but now reproduces the recording exactly. An exempt case that has stopped diverging is not a pass` |
| **C** — the difference stops being the decoration | `WARNING_PREFIX` `:96:` → `:97:` | `…difference is no longer exactly CPython's warning decoration.` |

**A and B are the two directions the brief required. C is the bound**, and it is
there because without it the exemption would only assert that *something* differs.

## 2 — all 94. GREEN.

    tests/test_legacy_selection_frozen.py     94 passed
    tests/test_deliberate_divergences.py      11 passed
    tests/test_search_command_contract.py    827 passed
    whole Python suite (perf excluded)      2,488 passed, 3 skipped, 0 failed

**Digests re-derived immediately before the run and recorded above.** The three
suites beyond the 94 are the blast radius of the authority edit: both other
importers of `tests/deliberate_divergences.py`, plus the whole suite as a control.

## 3 — the checkpoint commit is not this seat's

**Charter: workers do not commit independently.** `search-firstmate` was told the
gates are green and asked for the second checkpoint. **Nothing is committed by this
seat.**

## 4 — THE DELETION LIST, DERIVED. Nothing is deleted yet.

**Derived by reachability from `cli.py`'s dispatch, not by filename.**
`probes/reachability.py` builds the module import graph from the AST, computes one
closure per dispatch arm, and reports what only the `search` arm reaches.

**⚠ The two package `__init__` files are re-export HUBS and had to be excluded as
nodes.** `chats/commands/__init__.py` imports every command module and
`chats/__init__.py` re-exports nearly the whole package, so with them in the graph
**every arm reaches everything and the derivation returns nothing.** They are
handled as explicit edits instead.

### A. Modules reached only by the `search` arm

| path | note |
| --- | --- |
| `src/chats/commands/search.py` | the command |
| `src/chats/search_query.py` | the query grammar |
| `src/chats/session_scan.py` | imported by `commands/search.py` and re-exported by the hub; nothing else |

### B. Symbols that go with them, out of modules that stay

Derived by `probes/symbol_usage.py` — a top-level name in a surviving module that
only the three files above use.

| module | symbol |
| --- | --- |
| `console.py` | `StreamingPager`, `print_hint` |
| `formatting.py` | `build_messages_group` |
| `parsing.py` | `extract_summaries_from_entries`, `extract_latest_custom_title_from_entries` |
| `model.py` | `SearchOutputMode` — used only by `search.py` and by `cli.py`'s search arm |
| `cli.py` | `_resolve_search_output_mode` — the only search-arm-only helper; every other `_helper` the arm calls is shared |

### C. Explicit edits

- `cli.py` — the `search` arm, `main()` lines 348–529, its `cmd_search` /
  `SearchOutputMode` imports, and the `search` line of the default parser's epilog.
- `chats/commands/__init__.py` — the `from . import search` and the five
  `from .search import …` re-exports.
- `chats/__init__.py` — `cmd_search` and `SessionScan` in its re-export block.

### D. ⚠ THE TWO TRAPS, both checked rather than inherited

**`pool_filter.py` stays, and the derivation reaches that on its own.**
`extract_cwd_from_jsonl_file` lives in `parsing.py`, serves
`pool_filter.passes_path_for_index`, and that is called from **`commands/resolve.py:142`**
as well as `commands/search.py:917`. `resolve.py` is on the `-1 -d` index path the
charter keeps. **Both `pool_filter.py` and `parsing.py` are reached by four
surviving arms.**

**`python_extension.rs` and the PyO3 wheel stay.** Nothing in the derived set
touches them, and `ch-legacy` uses `inventory` and `scanner`.

### E. ⚠⚠ THE GAP IN THE INHERITED ENUMERATION — 281 tests nobody has ruled on

`teammates/g5-runner/deletion-enumeration.md` enumerates every instrument that
**consults `ch-legacy search` as an oracle.** It does not enumerate the tests that
**import the Python search module in-process**, and those are the larger half.

Measured by `probes/blast_radius.py`, which derives the vanishing names from the
three modules' own ASTs rather than listing them:

**16 files, 281 collected tests, break at import when the three modules go.**

    test_search_orchestration.py            78    imports chats.commands.search
    test_native_ascii_candidate_scanner.py  59    imports chats.commands.search
    test_colored_rendering.py               36    imports chats.commands.search
    test_search_operators.py                22
    test_provider_filter.py                 14
    test_provider_metadata.py               12
    test_claude_agent_detection.py          10
    test_search_case_sensitivity.py         10
    test_search_cli_args.py                  8
    test_hook_additional_context.py           7
    test_search_visibility.py                 7
    test_session_search_space.py              7
    test_search_output_modes.py               6
    test_metadata_timestamps.py               2
    test_session_scan.py                      2
    test_message_selection.py                 1

**And the live twins, which the enumeration does cover** — 372 comparisons across
three files: contract 289 (260 + 18 + 1 + 10), columns sweep 72, deliberate
divergences 11.

**Together ≈ 653 of the 2,488 collected Python tests.**

**⚠ `test_native_ascii_candidate_scanner.py` is the sharpest of the 281.** It
imports `_file_contains_ascii` from `commands/search.py` to grade the native
scanner against it. **That is an instrument consulting the Python authority, and it
is not in the enumeration** — the enumeration looked for subprocess consultations
and this one is an import.

**This is reported, not acted on.** Deleting 281 tests is a decision, and the desk's
own rule is that a gate with no successor is a deleted gate.

## Findings reported and NOT fixed, per the scope rule

### F1 — the no-results message passes the user's pattern through Rich markup

**Verified live on both routes, 2026-09-02, while both still exist.**

    ch-legacy search '[z-a]+' -l    →  stderr: No sessions match "+".
    ch      search '[z-a]+' -l      →  stderr: No sessions match "[z-a]+".

**Mechanism, confirmed by construction and by running Rich directly:**
`console.print_hint` calls `Console.print`, whose markup is on by default, so a
bracket expression that parses as a style tag is **deleted** from the message.
`[-a]` and `[123]` survive because they do not parse as tags.

**The port prints the pattern, which is the better output** — the direction
`preserve-because-wrong` exists for. **Four recorded rows carry it**:
`generated-15`, `generated-32`, `generated-42`, `generated-59`. **Unruled.**

### F2 — `[a&&b]` loses its whole warning, not only its decoration

    ch-legacy  →  ...search_query.py:96: FutureWarning: Possible set intersection at position 2
    ch         →  (nothing)

**`WARNING_DIVERGENCES` rules against reproducing the *decoration*. This is the
whole warning absent**, so the existing ruling does not cover it. One recorded row,
`generated-51`. **Unruled.**

### How F1 and F2 were found, and it was not by looking for them

`g5-runner` messaged that three generated rows carry the ruled warning divergence
and are invisible because `test_generated_patterns_match_the_recording` compares
`returncode` and `stdout` only. **Re-derived here rather than taken on report**, and
the measurement was widened from that family to the whole group: **7 of 60 rows
differ on stderr, not 3.** Three are the ruled warning; **the other four were F1,
which nobody was looking for.**

*The check that would have found them earlier is the one `g5-runner` named as
missing from their own enumeration: they checked the recording for path
contamination and not for overlap with the ruled divergence sets.*

**The evidence is not perishable** — `legacy-selection-baseline.json` stores
`ch-legacy`'s bytes for all 60 rows including stderr. **What ends at the deletion is
the ability to explore variants live**, which is how the mechanism was pinned.

### Recorded where a reader meets it

`test_generated_patterns_match_the_recording`'s docstring now names all seven rows,
the measurement date and both digests, and says **do not strengthen this gate
without a ruling on those five rows.** The gate itself is unchanged.

## Instruments, all under `probes/`

| probe | what it answers |
| --- | --- |
| `digests.py` | both digests, oracle half imported from `tests/oracle_digest.py` |
| `reachability.py` | which modules only the `search` dispatch arm reaches |
| `symbol_usage.py` | which symbols of a surviving module only the search files use |
| `blast_radius.py` | which test files break, and how many tests, with the vanishing names derived from the three modules' ASTs |
| `stderr_overlap.py` | which recorded rows carry the ruled warning decoration |
| `generated_stderr_gap.py` | how many generated rows would go red if that gate compared stderr. **Run it by copying into `tests/`** — it needs the session fixtures |

## What is not done

1. **The deletion.** Blocked on the checkpoint commit, which is
   `search-firstmate`'s, and on a ruling for the 281 tests in item E.
2. **Nothing is committed by this seat.**
3. **F1 and F2 are reported and deliberately not fixed** — the brief scopes this
   seat to five items and says to report a defect outside them.
4. **`chats/lexer.py` and `chats/murmurs.py` are reached by no dispatch arm at
   all.** They are not the search authority and are **deliberately left**;
   `parity-finisher` already recorded that `XmlmdLexer` has no production import.
   Named so it is not mistaken for something this seat missed.
5. **`README.md` and `ARCHITECTURE.md` document the Python search authority** and go
   stale at the deletion, as do the `//!` provenance headers in seven `rust/`
   files that name `commands/search.py` and `search_query.py`. **The Rust headers
   should stay** — they name where the port came from, and that file lives at
   `67d6053`. The two documents are a `final-change-log.md` item, not this seat's.
