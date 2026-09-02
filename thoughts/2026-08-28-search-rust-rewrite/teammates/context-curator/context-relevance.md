---
date: 2026-08-28
author: context-curator
head: 8cb4c5f
status: accepted
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: NOT ORACLE-DEPENDENT. This document's claims are about commits,
  documents, or teammates' tooling rather than about oracle behaviour, so a digest
  neither strengthens nor dates them. Recorded to say so explicitly: an earlier
  version carried a behaviour stamp, which implied a dependency it does not have.
---

# Historical context relevance for the native search rewrite

## What this document is

The charter says current code, tests, and installed-launcher evidence outrank `thoughts/`, and that historical notes stay untrusted until they are classified. This document is that classification. It covers four directories:

- `thoughts/2026-08-19-rust-rewrite/`
- `thoughts/2026-08-20-search-parse-rust-rewrite/`
- `thoughts/2026-08-20-search-performance/`
- `thoughts/2026-08-25-post-rust-rewrite-project-review/`

Method: full reads of all 59 files in those directories, then verification of their load-bearing claims against `main` at `8cb4c5f`, the current `rust/` and `src/chats/` sources, the current test suite, `ARCHITECTURE.md`, the installed launchers on this machine, and the git history including unmerged branches.

Every claim below states its evidence. Where a directory-level verdict would hide drift, the verdict is per file.

---

## 1. The finding that changes the mission

**A completed native `ch search` rewrite already exists, on an unmerged branch, and no project record explains why it was not merged.**

Branch `wip/cycle-02-native-default-pause-20260821`, commit `0ffde41`, dated 2026-08-25 00:30. Its working copy is checked out at `/Users/giladbarnea/dev/chats-cycle02-ox`.

The branch name says "pause". The branch did not pause. It ran three further cycles past that point, through slices A to G and a repair round, and closed with a final-acceptance document that declares the completion contract satisfied for all three public journeys, `ch search` among them.

### What the branch contains, against `main` at `8cb4c5f`

| | `main` | branch `0ffde41` |
| --- | --- | --- |
| `rust/` source files | 4 | 16 |
| `rust/` hand-written lines | 4,229 | about 17,500 |
| Search modules in Rust | none | `search.rs`, `search_engine.rs`, `search_query.rs`, `search_views.rs` |
| Session modules in Rust | none | `session.rs`, `session_render.rs`, `session_provider.rs`, `inventory.rs`, `scanner.rs` |
| Python search authority | `search_query.py`, `session_scan.py` present | both deleted |
| Search byte-oracle corpus | none | `tests/test_search_command_contract.py` (973 lines) plus `tests/data/search-command-fixtures/` with `MANIFEST.json`, `MTIMES.json`, `build_home.py`, and 704 expected stdout and stderr pairs |

A separate 39,965-line generated Unicode name table supports the native regex engine. It is machine-generated data, not hand-written code.

### The acceptance evidence recorded on that branch

Recorded 2026-08-24 and 2026-08-25 by an independent verifier. **These are their numbers. I did not re-run any of them.**

- The 704-case contract suite passes through both installed launchers.
- `tests/run_all.sh` exits 0: 2,054 passed, 3 skipped, 4 performance tests, 13 of 13 shell suites.
- Loader traces show zero Python entries on all three journeys: 842 dynamic libraries loaded, none of them Python, `_native`, or ABI3.
- Eight performance gates pass. Broad filtered literal miss: 906 ms native against a same-window legacy control of 3,543 ms. Broad regex miss: 1,317 ms against 18,072 ms.
- `cargo test` green in both feature modes, zero warnings.
- A clean-room wheel is byte-identical to both installed launchers.

### Why this may still not be the answer

Three facts argue against adopting the branch unchanged.

1. **`main` has moved since 2026-08-25, and the branch does not have those changes.** `main` gained the post-review fixes at `47b3db9` (honest EPIPE handling, `JsonEscapeValidator` deletion, launcher provenance guard, empty-optionals parity) and the terminal-width fix at `a51f32c` on 2026-08-27. The branch's own list of accepted limitations includes COLUMNS-only width detection, which is exactly the defect `main` fixed two days later.
2. **The branch's scope is wider than our charter.** It also moved default session parse to Rust. Our charter keeps default session parsing on `ch-legacy`.
3. **It carries six accepted deviations from legacy, two of which change search results.** They are listed in section 6. The branch's authors knew about all six and recorded them.

### What no record says

The project's OptMem memory has no entry mentioning cycle 03 or this branch. The 2026-08-25 project review examined `main` only. Its reviewers encountered the branch solely as a nuisance: the binary built from it was installed at `~/.local/bin/ch` and made a contract test fail, and they described it as a "stale wip-cycle02 build".

So the branch is invisible to the project's institutional memory. Whether it was rejected on purpose or simply lost cannot be determined from anything written down.

**This is a decision for the first mate and the admiral, not for this document.** It is recorded here so that no teammate discovers it late.

---

## 2. Directory verdicts

### `thoughts/2026-08-19-rust-rewrite/` — historical only

Six slices, dated 2026-08-19 and 2026-08-20, that moved narrow hot paths into Rust behind PyO3. Provider path classification, backward timestamp scanning, session inventory, resolution-facet scanning, ASCII candidate scanning, and the case-insensitive candidate gate.

Every slice optimizes for a constraint our charter reverses: Rust is called *from* Python, and a small Python callback stays authoritative for JSON semantics. Their design decisions ("keep `json.loads` in Python", "add one more PyO3 function", "do not move Unicode case folding") are correct for their era and wrong for ours.

Read them for one thing only: the behavioral rules they wrote down. Those rules are still true of the product.

**Two files inside are worth real time.**

- `slice-06-native-case-insensitive-candidate-gate/contract.md` lists the 20 Python 3.14 case-fold and regex risk scalars by code point: U+00DF, U+0130, U+0131, U+0149, U+017F, U+01F0, U+1E96 through U+1E9A, U+1E9E, U+212A, and U+FB00 through U+FB06. It also records why U+0131 is in the set. This list is load-bearing for any native gate and is expensive to re-derive.
- `slice-04-native-resolution-facet-scan/contract.md` states the 17 rules of the forward facet scan, including universal-newline handling and the four marker strings.

**One file contains a contradiction a reader hits first.** `slice-01-provider-path-classification/outcome.md` originally claimed that normal project setup made the global launcher work. That was disproved and corrected. The correction is recorded in `review-iter-1-and-2/findings.md`, in a different file. A reader who opens the outcome alone is fine; a reader who skims both may believe the dispute is open. It is not: the global editable install came from the user running `uv tool install -e .`.

### `thoughts/2026-08-20-search-parse-rust-rewrite/` — mixed, per file

This is the fleet that produced the native `ch parse` conversion now on `main`. Its shape is closest to ours.

| File | Verdict |
| --- | --- |
| `approach.md` | Historical. Its completion contract is close to our charter and is worth one read for framing. Its chain of command is not ours. |
| `cycle-01-scout.md`, `cycle-01-profile.md`, `cycle-01-map.md`, `cycle-01-smp.md` | Superseded by their cycle 02 equivalents. Skip. |
| `cycle-01-contract.md`, `cycle-01-implementation.md`, `cycle-01-live-review.md`, `cycle-01-rewrite.md` | Historical. Conversion shipped and is closed. Useful only as a worked example of a red process contract that gated a native cutover. |
| **`cycle-02-map.md`** | **Safe to reuse. The single most valuable file in all four directories.** |
| `cycle-02-scout.md` | Mostly reusable. Its public search contract summary still holds. Its performance numbers do not. |
| `cycle-02-profile.md` | Method reusable, numbers stale. See section 4. |
| `cycle-02-smp.md` | The integration of the three above. Redundant if you read `cycle-02-map.md`. |
| `state.md` | Stale pointer list. It points at cycle 02 as the frontier. Cycle 03 happened on a branch this file never learned about. |

**Why `cycle-02-map.md` earns its status.** Its two tables enumerate, responsibility by responsibility, exactly what Python still owns in the default-session and search paths and which module owns it. I checked its search table against HEAD line by line. Every row is still accurate: `search_query.py` still owns regex-or-literal fallback and the uppercase boolean grammar; `commands/search.py` still owns candidate planning, result modes, streaming, and exits; `session_scan.py` still owns semantic confirmation; the three native scans are still reached through PyO3.

It also records two facts that shape our dependency cone:

- Search truth is defined by rendered semantic inner XML. A renderer change changes which sessions match. This is why the charter puts rendering inside the cone.
- `rust/lib.rs` includes `rust/python_extension.rs` only under the Python-binding features, and the packaged `ch` binary builds with `--no-default-features`. So the existing Rust scans are **not reachable from the native executable**. I verified this at HEAD: `rust/lib.rs` is five lines and gates the include behind `python-bindings` or `extension-module`, and `pyproject.toml` builds the `ch` binary with `args = ["--no-default-features"]`. Any native route must extract those implementations into ordinary Rust modules first.

### `thoughts/2026-08-20-search-performance/` — largely safe to reuse

Four files, dated 2026-08-20, that diagnosed and fixed one slow search.

`discovery.md` is the best description of *why* search is slow that exists in this repository, and it still describes today's Python product. Its central argument survives at HEAD: the raw candidate gate can only reject, never confirm; a query character that JSON can encode as an escape makes raw absence unsafe, so the whole file defers; and the resulting amplification, not the parser, is the dominant cost. I confirmed the mechanism is unchanged — `_term_can_change_under_json_decoding` still exists at `src/chats/commands/search.py:969` and still governs the bypass.

It also carries a constraint list for candidate parity that our contract owner should treat as a checklist, not as history: raw `/`, escaped `\/`, `/`, escapes in any other query character, invalid UTF-8, Python case-insensitive Unicode risks, default joined Pi-agent evidence, and other generated provider or tool content.

`plan.md`, `scope-01-outcome.md`, and `scope-02-outcome.md` are historical as narrative, but they pin three implementation constants that are live in the code today and were chosen by measurement:

- 256-file candidate windows. Verified at `src/chats/commands/search.py:102`, `ASCII_LITERAL_CANDIDATE_WINDOW_SIZE = 256`. The measured knee: 128, 256, and 512-file windows completed in 1.422, 1.188, and 1.182 seconds; 512 saved 6 ms of completion but added 207 ms to the first barrier.
- A 128 KiB native read buffer, which beat 64 KiB, 256 KiB, and 1 MiB.
- Window-ordered error draining. A mid-window filter error must flush the accumulated window before printing, or output order changes. An independent reviewer found this defect the first time and it was fixed.

Also durable: the two output measures the user actually experiences are separate. Time to first visible ID through a real pipe, and full completion. Do not report one as the other.

### `thoughts/2026-08-25-post-rust-rewrite-project-review/` — safe to reuse, with corrections

Five scope reviews plus a task-criteria file, dated 2026-08-25 and 2026-08-26. This is verified, adversarial, source-grounded work and the quality is high. Four of the six findings it raised as tasks were fixed on `main` at `47b3db9`.

`search-pipeline/review.md` deserves particular weight. It re-derived the soundness argument for both candidate gates from scratch and found no correctness regression. Three of its verified-clean conclusions are worth carrying forward because they are non-obvious and each cost real effort to establish:

- The blanket bypass for backslash-containing patterns is **required** for soundness, not defensive. Raw JSON stores `\\` where rendered text has `\`.
- Parsers join adjacent text blocks with `"\n\n"` and rendering joins parts with `"\n\n"`. A needle spanning two JSON strings therefore cannot appear in rendered output without containing control characters, which gate eligibility already excludes. The boundary test is sound, not lucky.
- XML transport entities such as `&amp;` deliberately sit outside search semantics. This is encoded intent with a test that names it, not a blind spot.

`tasks-criteria.md` is a good model of the charter's own falsification discipline. Read it for the shape, not the tasks; those are done.

---

## 3. Still open at HEAD

The fix round covered four findings. These were reviewed, confirmed against source, and **never entered that round**. I verified each is still present at `8cb4c5f`.

1. **`--help` abbreviation divergence.** `rust/main.rs:64` matches only exact `-h` or `--help`, while `is_long_format_option` at line 157 emulates argparse prefix matching for `--format`. So `ch parse --h` errors with exit 2 where the pre-rewrite argparse printed help and exited 0. Same for `--he`, `--hel`, `-hf`, and `--help=foo`. No fixture pins any of them.
2. **`Infinity` passes the integer gate.** `rust/model.rs:327`: `number_is_integer` decides by scanning for `.`, `e`, or `E`. The string `Infinity` contains none, so `original_index: 1e999` renders as `<user-message i="Infinity">` where legacy rejected it. The emitted document then fails the native implementation's own re-parse.
3. **`NaN` is not normalized.** `rust/codecs.rs:1285`: `normalize_python_json_constants` rewrites `Infinity` and `-Infinity` but omits `NaN`, so an unknown-tool body containing bare `NaN` dies where `json.loads` accepted it.
4. **Dead import.** `src/chats/model.py:13` still imports `TOOL_SCHEMAS`, which has no consumer in that file.
5. **Duplicated nine-flag visibility predicate.** `_can_use_logical_json_string_gate` at `src/chats/commands/search.py:1006` and `native_gate_bypassed` at line 1048 spell out the same nine visibility conditions, once negated and once positive. A tenth flag must be added in both places or the gates diverge silently. This one is directly in our path: any native re-implementation inherits the duplication unless it collapses it.
6. **Redundant length guard** before a `zip(..., strict=True)` in `_confirm_ascii_literal_window`.
7. **CHANGELOG contradicts the build system.** `CHANGELOG.md:60` still says builds use Maturin. `pyproject.toml` uses `setuptools-rust`. No changelog entry covers the headline change, that public `ch` became a Rust launcher.

Two further fidelity items were raised by reviewers and remain unresolved. Neither is user-visible today, and both are decisions rather than defects:

- **Sort-key fidelity.** Native discovery sorts paths component-wise; two reviewers disagreed about whether `pathlib` compares component tuples or full normcased strings. They reached opposite conclusions on the same question. If native inventory ordering enters our cone, settle this empirically rather than by citation.
- **Non-UTF-8 session paths.** `classify_native_session_path(path: &str, home: &str)` and `find_last_jsonl_timestamp(path: &str, ...)` take `&str` where every sibling takes bytes, so PyO3 raises `UnicodeEncodeError` on a path containing invalid UTF-8. Such a path is discovered fine and then crashes downstream. Legacy handled it. A fully native route removes the FFI boundary and so removes the defect for free — but only if the native code carries paths as bytes throughout.

---

## 4. Stale enough to mislead

These claims appear in the four directories, read as current, and are false today. Acting on them costs wrong work rather than slow work.

**1. "The installed `~/.local/bin/ch` is a stale wip-cycle02 artifact."** Stated in three separate review files as a live hazard, with a task (T3) built around it.

No longer true. `~/.local/bin/ch` was reinstalled 2026-08-28 at 10:11. It is byte-identical to `target/release/ch` built from HEAD, SHA-256 beginning `661f5ee0`, 2,988,400 bytes. It contains none of the HEAD-absent marker strings the reviewers used to identify the stale build.

**2. The staleness moved to `.venv/bin/ch`.** That binary is dated 2026-08-26 16:34, SHA-256 beginning `00bbdb00`, and does not match HEAD's `661f5ee0`. Measuring or testing through the checkout launcher measures old bytes. This inverts the hazard the reviews describe, so a reader who trusts them will guard the wrong launcher.

**3. "The contract suite binds to `~/.local/bin/ch`."** Fixed at `47b3db9`. `tests/test_parse_command_contract.py` now builds its own launcher with `cargo build --release --bin ch --no-default-features` and rejects any binary embedding HEAD-absent strings, naming the reason in the failure. `REAL_INSTALLED_CH` no longer appears anywhere in `tests/`.

**4. Every absolute performance number in all four directories.** They span 2026-08-19 to 2026-08-25 and were taken on a live corpus that grew throughout: 4,838 files at the first baseline, 4,907 at the cycle 01 profile, 4,915 at cycle 02, and 5,043 by the last measurement window. Corpus bytes went from about 6.0 GB to 6.9 GB. Several documents state plainly that concurrent team work made their own samples noisy, and one records that its whole absolute range drifted upward between cycles while an interleaved control drifted with it.

Use these numbers to order work. Never as budgets. Our own baseline must be measured in one window with interleaved controls, as the charter requires.

**5. `state.md` in the search-parse directory.** It names cycle 02 as the frontier and points at cycle 02 artifacts. Cycle 03 completed on a branch. A reader who trusts this file will conclude that search was never attempted.

**6. The Python 3.13 packaging claims** in `2026-08-19-rust-rewrite/review-iter-1-and-2/findings.md`. Resolved during that same effort. `pyproject.toml` now requires `==3.14.*` and PyO3 targets `abi3-py314`. The finding is history, not a task.

**7. "Rustfmt and Clippy are unavailable in the installed toolchain."** Repeated in six slice outcomes as a standing condition. It was true on 2026-08-19 and 2026-08-20. Nobody has rechecked it since. Treat it as unverified rather than as a constraint.

---

## 5. Safe to reuse, in one list

Facts and fixtures that survived verification and are worth taking as given rather than re-deriving.

**Behavioral rules**

- The 20 Python 3.14 case-fold and regex risk scalars, with U+0131's justification. `2026-08-19-rust-rewrite/slice-06-.../contract.md`.
- The 17 forward facet-scan rules and the four marker strings. `slice-04-.../contract.md`.
- The 10 backward timestamp-scan rules, including Python truthiness on `timestamp or created_at` and the non-string precedence rule. `slice-02-.../contract.md`.
- The 19 session-inventory rules: provider group order Claude, Codex, Pi; symlink behavior differing between fixed-depth Claude globs and recursive Codex and Pi walks; negative infinity as the stat-failure sentinel. `slice-03-.../contract.md`.
- The candidate-parity checklist for JSON-escape forms. `2026-08-20-search-performance/discovery.md`.
- Search truth includes all summaries and the current title, and role filters do not remove them. Stated in several places; still true at HEAD.

**Measured constants now live in the code**

- 256-file candidate windows, `src/chats/commands/search.py:102`.
- 128 KiB native read buffer.
- Window-ordered error draining.
- Evidence markers `b'"pi-user-agents"'` and `b"\\u"`, at `src/chats/commands/search.py:98` and `:99`.

**Method**

- Time to first visible ID and full completion are separate user outcomes. Measure and report both.
- A scanner microbenchmark cannot accept a slice. Every slice in the 2026-08-19 effort states this explicitly, and the discipline held.
- Differential acceptance against a frozen reference implementation, run over the whole live pool plus a synthetic edge matrix, is the pattern that caught real drift repeatedly. It found `serde_json` divergence on non-finite values and lone surrogates, and it found the component-wise versus string sort difference.
- Interleaved old-versus-new runs in one window. Standalone comparison against a previous cycle's wall times is misleading and was recorded as such.

**Current authority map**

`ARCHITECTURE.md` is accurate for HEAD. I checked its native-launcher, native hot-path helper, and search sections against the source. It correctly describes `ch parse` as the one closed native route and every other shape as an `exec` into `ch-legacy`. Prefer it over any `thoughts/` map for present-tense questions. Use `cycle-02-map.md` for the question `ARCHITECTURE.md` does not answer: which Python module owns which responsibility, and what has to happen to it.

---

## 6. The branch, treated as a fifth directory

The first mate ruled on 2026-08-28: the branch is prior art, never an oracle. The Python product on current `main` stays the only source of behavioral truth. This section records what the branch's own authors knew was wrong with their work, because that is the part no re-implementation can rediscover cheaply.

Sources: the branch's independent closure review (`review-03.md`, 2026-08-24), its repair round (`cycle-03-repair-result.md`), and its final acceptance (`cycle-03-final-acceptance.md`). All three live in commit `0ffde41` and are absent from `main`.

### Read the closure review as leads, never as verdicts

The repair round formally overturned four of the closure review's nine findings, each with fresh empirical evidence:

- The age-formatter finding cited legacy outputs (`48d`, `10w`, `14mo`) that the legacy function does not produce. Characterized three ways against the preserved control tree. The real divergence was in the minutes and hours buckets, and it was fixed.
- The provider-column finding had its premise inverted. Both binaries produce byte-identical output; no change was needed.
- A claim that `session_pool.py` was unreferenced dead code was wrong. It is live for the retained `name` and `rm` routes.
- A corrupt-first-line finding was real but backwards. Legacy *aborts* on an invalid-UTF-8, malformed, or non-object first line; the native code had been skipping such lines. It was aligned to abort.

Two independent, careful reviewers reached opposite conclusions on the same questions on this project, twice — this pattern and the `pathlib` sort-key disagreement in section 3. Verify empirically; do not arbitrate by citation.

### Six accepted deviations, still standing at `0ffde41`

**Change search results.**

1. **Regex step-limit exhaustion.** The native regex VM carries a two-million-step budget. When a catastrophic-backtracking pattern trips it, the branch emits a one-time stderr warning and returns "no match", where CPython eventually returns the true answer. Full parity was judged to require an engine-strategy fork and was deliberately not attempted. This is the branch's largest known truth divergence.
2. **Malformed intervals, `{5,x}` and `{, 2}`.** The native validator rejects the pattern, so the whole pattern falls back to a literal. CPython treats that text as literal characters mid-pattern while the rest of the regex still applies. Results coincide for a single-term pattern and can differ inside an alternation. Found late, flagged for a future cycle, never fixed.

**Change bytes, not results.**

3. **COLUMNS-only width detection**, defaulting to 80. Legacy Rich queried the terminal. zsh does not export COLUMNS, so interactive colored rendering on the branch is always 80 columns. This is now a three-way reconciliation: `main` fixed exactly this at `a51f32c` on 2026-08-27 using `ioctl TIOCGWINSZ` across fds 0, 1, and 2. `main` today differs from the branch and from the legacy the branch measured against.
4. **Machine-baked absolute paths in synthesized stderr.** Warning synthesis prints a `CARGO_MANIFEST_DIR`-derived path; a file-write failure embeds absolute interpreter and repository paths. The suite masks both, so the real bytes are machine-specific and unpinned. Same defect class that `main` removed from the parse launcher in T1.
5. **Three stderr line-wrap implementations, kept separate on purpose.** One counts characters and is not width-aware, one is UnicodeWidth-aware, one preserves trailing spaces. Wide-character error text wraps differently depending on the journey. Byte identity was judged unprovable.
6. **Non-UTF-8 argv decodes lossily** to replacement characters instead of Python's surrogateescape. Unpinned, low impact.

### Seven blind spots in the 704-case contract suite

The branch's reviewer enumerated behavior classes that no case in the suite pins. Adopting the command shapes without closing these inherits the holes.

1. Interactive terminal width. Every manifest case sets COLUMNS.
2. Age labels and warning-source paths, both erased by normalization tokens. The reviewer notes this masking hid two genuine parity signals — the age bug was found by hand, not by the suite.
3. The provider-column predicate when the candidate set spans a single provider.
4. Anything beyond exit code, stdout, and stderr: SIGINT during pager streaming, SIGPIPE mid-panel write (only whole-buffer EPIPE is pinned), process groups, and reaping of `less`.
5. Non-UTF-8 argv, unset HOME, and a pool file mutated between discovery and confirmation.
6. Step-limit exhaustion. No test observes any output at all.
7. Nothing pins that the installed launcher matches the repository build between acceptance windows.

### Four CPython regex constructs the branch got wrong before it got them right

Each was verified against CPython 3.14.7 and then fixed. This is a trap list, not history — a fresh implementation will meet all four.

| Construct | CPython truth | The wrong answer |
| --- | --- | --- |
| `a{,2}`, `a{,}` | quantifier with minimum 0; `a{}` stays literal | treated the brace as a literal character |
| `(?x)`, `(?x:…)` | verbose is valid; strip ASCII whitespace and `#` comments between atoms, leave classes and escapes untouched | rejected at compile, falling back to a literal |
| `(?<=ab+)c`, `(?<=a*)b` | invalid; lookbehind requires fixed width | compiled and matched, producing extra hits |
| `(?-m:^two$)` | scoped multiline is honored; `$` without the flag matches at end, or before the final newline only | anchor evaluation hardcoded multiline true |

The governing invariant: **the native validity gate must accept exactly what CPython accepts.** Search falls back to a literal on an invalid pattern, so any disagreement about validity silently changes which sessions match, in either direction.

Their own map stated this before any code was written, and the four constructs above are what happened anyway: do not port query truth onto Rust `regex` naively, because `re` accepts lookarounds and backreferences that Rust `regex` rejects, and the literal fallback turns every validity disagreement into a silent result change. Pin both sides — patterns Python rejects, and patterns Rust accepts that Python treats differently.

### The regex model rule that matters more than the four constructs

**`re.IGNORECASE` is not `casefold()`.** They implemented sre's actual model: single-codepoint `tolower` plus an exact 50-entry fixes table. The pin that separates the two models is that **`ss` does not match `ß`** under `re.IGNORECASE`, both directions, where `casefold()` makes them equal.

Today's Python search normalizes needles with `casefold()` behind an `.isascii()` guard, and that guard is the only thing keeping the two models from diverging. Drop the guard and keep the casefold, or keep the guard and assume casefold generalizes, and search truth moves.

Their verified folding pins, probed against CPython 3.14.7: `i` matches `İ` both ways; `İ` matches `i` followed by U+0307; `s` matches `ſ` both ways; `k` matches U+212A both ways; `ss` does not match `ß`.

Five further characterizations from the same source, each worth taking rather than re-deriving:

1. Default flags are always MULTILINE plus DOTALL. `$` matches at end of string or before one final newline; `\Z` is absolute end.
2. Digit escapes take up to three digits. A leading `0` or the full three-digit form means octal, maximum `0o377`. Otherwise it is a group reference, and an undefined group is an error.
3. The POSIX-class FutureWarning fires if and only if `[` immediately follows a class's opening bracket. The reported position is the inner bracket index, and the stderr bytes carry a source path plus a two-space-indented source line, once per process per distinct message. This warning is user-visible search output.
4. The empty alternation `zznope|` matches every session.
5. `[[:alpha:]]` hits the literal text `:]`, while `[[:alpha:]] class` misses because of the doubled `]]`.

### Two negative results worth inheriting

**Do not pre-filter dates on stat mtime.** The branch tried it and withdrew it. Legacy consults content timestamps only, and the pool contains files that break the assumption that creation precedes modification precedes mtime — imports and copies carrying foreign clocks, `touch -t`, restore tools. It silently dropped hits. Worse, the colored-and-paged arm used a different predicate, so the binary disagreed with itself on one query. The guarded variant was analyzed and permanently closed: for `-ca` the content probe *is* the cheap first-timestamp read, and `-ma` already reads only 4 KB tail chunks backward, so guarding reinstates the same I/O plus extra stat calls and cannot win on speed.

**Never index a string with byte offsets measured on its lowercased copy.** This was the branch's one blocker, reaching exit 101 mid-render. `İ` grows from 2 bytes to 3 when lowercased; the ligatures `ﬀﬁﬂﬃﬄ` shrink from 3 to 2. Below the abort threshold it silently paints the wrong span. Fold per character over the original string, using the same equivalence that defines search truth. Selection rule: earliest start wins, longest needle on ties.

### Their deviation list is itself incomplete

A sixth-and-a-half deviation exists that never reached the final record. At slice C they noted that `\N{...}` resolves through a generated canonical-name table, and that **algorithmic CJK and Hangul names are excluded** — flagged as a documented divergence risk with no fixture coverage. It does not appear in the closure record's accepted-limitations list. It fell off their own books between slice C and acceptance.

Treat the six as a floor, not a census.

### Three defects their process did not catch

Each passed cargo tests in both feature modes, the 704-case contract suite, acceptance gates, and an independent review.

**1. The extraction of the two scanners left a live fork, and the fork already disagrees.** Found by `search-runtime` during mapping; I verified it at source on `0ffde41`. `rust/python_extension.rs` keeps `find_last_jsonl_timestamp_impl` and `scan_resolution_facets_impl` with their own bodies, trimming with `trim_python_byte_whitespace` — Python's four-byte JSON whitespace set. `rust/inventory.rs` separately grew `last_timestamp` and `resolution_facets`, trimming with bare `.trim()` — Rust's full Unicode `White_Space` property — and reading facets with `std::fs::read_to_string`.

Two real consequences. A JSONL line beginning with U+00A0, U+2028, or U+3000 is trimmed to a bare `{` by the native path and parses, while the legacy path leaves the byte and `json.loads` rejects the line: one route returns a timestamp, the other falls back to filesystem mtime, on the same file. And `read_to_string` discards the bounded-memory property that the streaming facet scanner was built for — a property bought because one real Pi session has a 3,752,303-byte final line that cost 773 ms, 67% of a whole-pool scan, in the original Python implementation.

So the branch's "one authority per journey" claim holds per journey but not per behavior. **The lesson: delete the original in the same change as the extraction, or prove the two are byte-identical. A copy that compiles is not an extraction.**

**2. A latent provider bug from their default-session cycle surfaced only during their search cycle.** Their native Pi agent parser required an unconditional `<duration_ms>` terminator where Python's envelope grammar makes it optional, so joined pi-user-agent responses silently vanished from parse output. Their default journey had already passed its own byte contract, its own gates, and an independent review with this inside it, because no fixture contained the shape. The fix needed the whole grammar — prefix and ending envelope regexes, producer-boundary candidates, a single-candidate rule, and a `responsePreview` fallback modeling Python's 500-UTF-16-code-unit truncation — not the one terminator.

This shape matters beyond Pi: joined Pi agent records are one of the two known cases where provider normalization generates visible text that the raw JSON does not contain. That is why `b'"pi-user-agents"'` is an unconditional evidence marker in today's gate.

**3. The corpus was uniform along the axis each bug lived on.** The highlight-painting blocker survived because every fixture was ASCII. The width-detection gap survives because every manifest case sets COLUMNS. In both cases the suite was large and the axis was invisible.

### A cheap technique worth reusing

`search-runtime` settled "faithful port or look-alike?" for a 3,749-line renderer in one command, by finding the artifact a re-implementer would never guess: Rich renders `Markdown("---")` as a dim ASCII hyphen run, not a box-drawing rule. The branch emits exactly that, escape codes included. Look for the one output detail that only a faithful port would reproduce, rather than diffing broadly.

### What is durable and what is a hypothesis

Durable: the 704 command shapes, the fixture home builder, the `MTIMES.json` pinning, the trap lists above, and the negative results. These describe the problem.

A hypothesis: the 704 expected output files. They were generated by an implementation with six known deviations and seven unpinned behavior classes. They are a well-informed guess at legacy truth, not legacy truth.

## 7. A dilemma, recorded

The team communication rule says that when peers cannot resolve an ambiguity, I take the simplest sound path and record the decision.

**The dilemma.** The branch in section 1 makes the charter's premise questionable. The charter says to build the native search route; a built one may already exist. I could have paused this document until that was resolved.

**Chosen path.** Deliver the classification in full, on the charter as written, and escalate the branch to the first mate as a decision rather than treating it as an answer. The classification is useful under either outcome: if the branch is adopted, this document says which historical claims would mislead a porting effort; if it is rejected, the document does the job it was commissioned for.

**Rejected alternative.** Reading the branch's Rust source and reporting on its quality. That is a review, it belongs to whoever owns the decision's follow-through, and doing it now would spend the whole team's Phase 1 on work that a single answer from the admiral could make irrelevant.

**Why.** The charter's own rule is to follow evidence and change the plan when a falsifier disproves it. The branch is a candidate falsifier of the plan's premise. Surfacing it early costs one message. Discovering it in Phase 3 costs the cycle.
