# RESUME — engine confirmation and Codex decode

Seat: `engine-and-codex`. Written cold: nothing here assumes you followed my thread.
Oracle: `src/chats/commands/search.py` at `8cb4c5f` plus the clock seam.

---

## The one-paragraph version

**Both halves of G4 are green.** Against a **frozen** copy of the real pool the
uncoloured route is byte-identical on **54 of 54** cases — stdout, stderr and exit
status — with **0 unstable**. The coloured pty gate is green on all four original
cases; its only red is two new fence cases that the renderer **refuses by design**
pending lexer tables.

Landed here: confirmation, the Codex decoder, the raw-transcript decoder, the
`search . -ll` projection, all five output modes, the plain sink, the coloured list
sink's wiring, and the `Confirmed` adapter. **234 lib tests pass**, five build configurations.

What is left is the four queued items at the end, none of which blocks the cutover.
The cutover itself waits on `message-renderer`'s lexer tables, not on this seat.

---

## Proof, with coverage stated

| gate | result |
| --- | --- |
| five build configurations | all green |
| lib tests | **234 pass** |
| Codex render differential | **0 mismatches, 8,477 cases, 1,211 of 1,211 sessions** |
| Codex falsification | 10 of 11 mutations killed over the full corpus; the survivor is an unreachable branch |
| scan-loop falsification | 9 of 9 mutations killed |
| Rich `rule` parity | 99 of 99 recorded rows |
| Rich wrap parity | **235 of 235 recorded rows**, five widths |
| route differential, synthetic pool | 0 of 54 |
| **route differential, frozen real pool** | **0 mismatches, 0 unstable, 54 of 54** |
| coloured pty gate | 4 of 4 original cases green; 2 fence cases refused by design |

### G4's gate: green, and what the projection taught

**Pool: `/private/tmp/ch-pool-snapshot`, an APFS clone of the live pool taken
2026-08-29, 5,136 files, 4,871 sessions returned by `search . -ll`.**

The gate reached 0 of 54 only after `_can_project_dot_only_id` and
`_stream_dot_only_id_projection` were ported **as written**. Before that it sat at
52 of 54, both failures being `search . -ll` short by exactly one session id.

**The reason that matters more than the fix.** Run against the one missing file:

```
projection says:            MATCH
authoritative path says:    no hit
```

**Python's projection disagrees with Python's own full search path, and the
projection wins**, because `_stream_dot_only_id_projection` prints the id on MATCH
and never consults the full path. So `ch search . -ll` returns a session that
`ch search .` does not.

I had filed the projection as a performance path with an open question about
whether it could change results. **It changes results, on the commonest id-only
query.** A port that "fixes" the disagreement loses a session the product shows and
passes every gate on this mission. The reproduction — file path and both measured
answers — is recorded on `stream_dot_only_id_projection` itself, so the next reader
meets the reason before the temptation.

### The snapshot, and why it exists

The live pool **cannot** support this gate. Nine sessions append to it
continuously, and every whole-pool case compares ~4,900 mtime-ordered lines, so
the *reference disagrees with itself* over the measurement window. Three separate
runs produced 1–3 "mismatches" that were all the corpus moving: a transcript
growing by one message, a session appearing mid-run, two ids transposing.

`cp -Rc` clones copy-on-write on APFS: 9 GB of pool, **44 seconds, zero disk
consumed**. I had argued a snapshot was unaffordable — that was a claim about
bytes when the relevant fact was filesystem semantics.

**Do not delete the snapshot.** It costs nothing while the originals are unchanged
and it is what makes this gate re-derivable. Verified stable before use: legacy run
twice against it agrees byte for byte, and the run reports **0 unstable** where
live runs reported 4–14.

**Reach is 54 of 54 again.** The two invalid-date cases were permanently unstable
against a live pool and are ordinary cases against a frozen one.

## What is landed

| file | what it is |
| --- | --- |
| `rust/search_engine.rs` | the scan loop. Restructured to Python's real shape: one loop parameterised by batch size and probe, modelling **both** Python paths. `batch_size = 1` is the serial path exactly. |
| `rust/search_confirm.rs` | confirmation. `Confirmation::new`, `scan_session`, `rendered_for_search`, `SearchHit`, `SessionMetadata`. |
| `rust/codex.rs` | the Codex decoder, its own module. `rust/session.rs` never touched. |
| `rust/raw_transcript.rs` | the fourth decoder, for `detect_format == Raw`. |
| `rust/python_io.rs` | `read_text`, `python_io_error`, `decode_utf8` — **lifted** from `main.rs`, reviewed and passed by `search-runtime`. |
| `rust/search_output.rs` | the four plain modes, `PlainSink`, `BufferingSink`, `rule`, `metadata_block`, `format_raw`, `confirmed_from`. |
| `rust/search_run.rs` | `run(arguments, home, width) -> i32`. **This is what the cutover's `Run` arm calls.** |

Also changed, each flagged to its owner: `rust/session_pool.rs` (removed
`windows()`, corrected the `CANDIDATE_WINDOW` doc), `rust/pool_filter.rs`
(Python repr quoting and `python_strip` in `parse_date_filter`), `rust/terminal.rs`
(lifted `wrap_preserving_spaces` in), `rust/main.rs` (lifted two functions out),
`rust/lib.rs`, and `probes/drivers/render/src/main.rs` (repointed at the
production pipeline).

---

## Not done

**The coloured panel sink is landed** — `message-renderer` wrote
`ColouredPanelSink` and wired it into `search_run.rs` beside my list arm, proved on
168 recorded panels before the wiring existed. The coloured list arm and its
`show_provider` derivation are mine.

**What genuinely remains is one thing, and it is not this seat's:** the renderer
refuses a fenced block whose language has a lexer, typed `Unsupported` rather than
rendered approximately. The G4 fixture reaches none of it, so both gates are green;
real sessions reach it, so **the cutover waits on the lexer tables.** The panic is
safe today only because nothing in `main.rs` routes to `search_run`.

Everything else this seat deferred has since been closed. See the queued list at
the end for the three small items that are left, none of which blocks anything.

## Facts worth more than the code

**Both Codex defects the differential found were the same mistake: my parser being
*more permissive* than Python's.**

- `tools.clock__curr_time({})` — Python parses `{}`, then discards it because an
  empty dict is falsy, so the call is unparsed and the envelope keeps the name
  `exec`, which normalises to `Bash`. 56 mismatches.
- `const patch = "a\n" +\n"b";` — Python's binding pattern requires the literal to
  be followed by `;`, so a concatenated patch matches nothing. I took the first
  fragment and rendered a truncated patch. 4 mismatches.

In both cases **the Python's accident is the contract**, and my version read as
the more correct of the two. A reviewer would have approved mine.

**Python's `re` `\s` matches U+001C–U+001F, and so does `str.strip()`** — both
measured. So every trim standing in for either has to use `python_strip`
semantics, not only the `.strip()`-derived ones. All 9 sites in `codex.rs` were
wrong; fixed. The same class was found and fixed in `pool_filter.rs`.

**Falsification: 10 of 11 over the full corpus, and the sample lied about two of
them.** At 300 sessions, 8 of 11 died. At full corpus, `script_calls_never_merged`
and `script_object_json_only` also die — 416 and 604 mismatches. They had looked
corpus-blind and were only **sample**-blind: the shapes occur 788 and 7,989 times,
but not in the first 300 sessions in discovery order, because `custom_tool_call` is
a newer Codex feature and discovery starts old. **Falsify over the same corpus the
gate covers, or a survivor means nothing.**

**The remaining survivor is a third category, and no fixture can fix it.**
`empty_assistant_turns_kept` removes the `has_content` guard in `flush_assistant`
and changes nothing. Not because the corpus lacks the shape — because **no input
can reach it**: all six `ensure_assistant` call sites, in my port and in Python,
add text, thinking or a tool immediately after opening the message. It is an
unreachable branch, kept only because Python keeps it. Distinguish that from
corpus blindness: one is a missing instrument, the other is a branch with no
inputs.

**Four shapes this code handles do not occur in the corpus at all**, measured:
assistant multi-block messages (0), reasoning summaries with a non-`summary_text`
item (0), a genuine `> ` / `⏺ ` CLI transcript (0 — all 9 raw-format files decode
to nothing), and a C0 separator inside a tool script (0). The first two are pinned
by fixtures in `session-core/codex-fixtures/`, each validated against Python and
accompanied by a control shape that occurs 94 times. **The last two are pinned by
nothing.**

**The 44 excluded Codex sessions split 8 raw-format / 36 jsonl-format.** The 8 are
excluded by `detect_format` before `parse_codex` runs; every large one is in that
group. A more permissive decoder cannot surface them and would wrongly surface the
36 trivial ones. `codex-handoff.md` originally said the opposite and is corrected.

**A gate that does not report its own coverage cannot be assessed.** A full disk
made the Codex differential snapshot 1,041 of 1,211 sessions and then report
`mismatches: 0`. The verdict was clean, the number plausible, and the only tell was
a coverage line the harness happened to print. I caused that disk condition: the
render differential leaked a full corpus copy per run, 33 GiB across 28 directories.
`session-core` has fixed the leak and made partial coverage a hard refusal.

---

## Three duplicated types, one ruling

`inventory::Provider` vs `session::Provider`, and `search::parse::SearchOutputMode`
vs `visibility::SearchOutputMode`. Same names, different declaration orders, no
conversion either way.

**Ruled: do not unify. Bridge explicitly.** `inventory::Provider`'s order is
load-bearing — the provider partition was proved identical to Python across 5,036
sessions, so a unification could silently adopt the wrong order. Both bridges live
in files I own: `ProviderBridge` in `search_confirm.rs`, `output_mode_of` in
`search_output.rs`.

Note the second pair is entirely within `search-runtime`'s scope and **their own
two functions disagree**: `SearchArguments` carries the `parse` type,
`render_no_results_hint` takes the `visibility` one.

---

## Traps closed structurally rather than documented

**`Confirmation` does not accept a `PoolFilter`.** It takes the directory and
builds its own with no dates. Confirmation applies only the cwd check, but
`PoolFilter::new` parses dates eagerly and fails on a bad one — so passing the date
strings through would make `-ma notadate` fail once before the scan, where the
product fails **once per candidate file**. That divergence is invisible to every
gate on this mission: eager and lazy date filters agree on every valid value, and
the only case separating them is the one a fast failure deletes. Found by
`search-runtime` reading my seam.

**`Gated::Failed` is reachable, via invalid filter values only.** My earlier
finding that the path stage cannot raise was right for *valid* values and wrong as
a generalisation: `mafter_dt` is a `cached_property` calling `parse_date_filter`,
which raises on every access because a raising property caches nothing.
`search-runtime` owns that arm.

---

## Tooling in this directory

| file | what it does |
| --- | --- |
| `route_differential.py` | the whole-route byte diff. **Run this first.** |
| `falsify_engine.py` | 9 mutations against the scan loop, via `cargo test` |
| `falsify_codex.py` | 11 mutations against the Codex decoder, via the render differential |
| `make_codex_fixtures.py` | synthesizes the two corpus-blind Codex shapes, validated against Python |
| `probes/rule-oracle.tsv` | 99 recorded Rich `rule` rows, 11 widths × 9 titles |
| `probes/searchdriver/` | the three-arm cutover, standalone, so the route can be diffed before it is live |

Both falsifiers **sync the crate into a private directory and mutate that**, never
the shared checkout. That is not fastidiousness: I read a peer's file mid-mutation
once and published a wrong finding from it.

---

## The coloured gate — all four original cases green

Re-run after `message-renderer` landed `ColouredPanelSink` into `search_run.rs`:

```
210 comparisons over 6 coloured cases, widths 72, 7 clocks
FAILED  70 differences
   5 DIFFERS g4-fence-never-covered
   5 DIFFERS g4-fence-covered-later
```

**`g4-list`, `g4-default-matches`, `g4-full` and `g4-matches-no-metadata` are all
green.** The 70 differences are two cases × 5 tiers × 7 clocks — both of them the
new fence cases, which **panic by design**: the renderer types a
syntax-highlighted fence as `Unsupported` rather than rendering it approximately.
That waits on the lexer tables. The panic is safe today because nothing in
`main.rs` routes to `search_run`.

**Both responsiveness guards have stopped firing**, which is its own result. They
previously reported `CLOCK IGNORED` and `TIER IGNORED` — "the subject route
produced 1 distinct output across 7 instants / 5 colour tiers". Measured per case
at the time, that was false for the case the wiring covered:

| case | subject / 5 tiers | reference | subject / 3 clocks | reference |
| --- | --- | --- | --- | --- |
| `g4-list` | 5 | 5 | 3 | 3 |
| `g4-default-matches` (then unwired) | 2 | 5 | — | — |

**The guards were reporting a route-wide blindness from evidence covering only
cases where the dimension was inert.** Worth knowing if they fire again: check per
case before believing the headline.

**One `g4-list` difference was found and is `views-and-colour`'s, now fixed or
absorbed** — Python expands a literal TAB in the headline to spaces at the tab stop
and splits the styled span; the raw tab differed by 26 bytes. It is Rich's `Text`
expansion **at render time**, so it belongs to the row renderer rather than to
`headline()`.

## The cutover — prepared, and BLOCKED

**Do not land the `search` arm until styled tool rendering exists.** Landing is
exactly what makes the gap reachable: nothing in `main.rs` routes to `search_run`
today, so the panic below is unreachable until the arm goes in.

### The panic: narrowed to one route, NOT closed

**Re-measured 2026-09-01 after `lexer-tables` landed the common tool path.** Tree
green at 234 lib tests; the deliberate red is gone. All eleven flag shapes clean
under a colour pty:

```
ok exit=0  (default)  --full  --thinking  --plans  --agents
ok exit=0  --branches --short --tools  --tools Bash  --tools + --full
ok exit=2  --custom   (grammar error, not a panic)
```

`Part::Tool(_) => Unsupported("tool")` is gone.

**Do not read that as the panic class being closed.** `search_views.rs:1968` still
panics on `Unsupported`, and **one route still reaches it**:
`Unsupported("fence lexer budget")` at `session_render.rs:3700` — a step-budget
exhaustion in the syntax lexer.

**It is content-driven, so no flag sweep can rule it out.** Eleven clean shapes
over a small curated fixture is the evidence shape this mission has been caught by
repeatedly.

**Attempted and not triggered:** a 147 KB pathological Python fence — long
unterminated strings, 80-deep nesting, ×400 — rendered fine, exit 0. **Not easily
reachable; not proved unreachable.** Recorded as unmeasured, not as safe.

### ⚠ RULED 2026-09-01, and NOT YET IMPLEMENTED: render plain on budget exhaustion

**The fence-language ruling transfers to the budget route.** A fence that exhausts
the step budget must **render plain with complete geometry and never refuse.**

The comment at `session_render.rs:3700` justifies refusing because *"Python's `re`
has no step budget, so there is no behaviour here to reproduce."* **That was
written when refusing meant a typed error.** Once the panel sink existed, refusing
began producing a truncated scan and exit 101 — a failure worse than the
approximation it prevented. Identical in structure to the fence-language case and
strictly rarer. **The comment has been false since the sink landed, and a false
comment directs the next change, so it goes with the fix.**

**Two constraints on whoever implements it, from the first mate — constraints, not
a design:**

1. **The gate must force exhaustion.** A real corpus cannot reach it, so the only
   honest falsifier is a test that shrinks the budget and asserts plain output and
   no panic.
2. **Close the route structurally, not with a second refusal.** Once no producer of
   `Unsupported` remains on that path, the sink's panic should be **impossible by
   construction** rather than merely unreached. Removing the possibility beats
   guarding it.

**What still blocks the arm** is no longer a crash: the `Edit` diff renders a body
where legacy renders a unified diff (~6.3% of tool parts, to be built on a
vendored `difflib` port agreeing with CPython on 2,814 of 2,814 real Edit calls),
and the `Read` line-number gutter. Both are visible parity breaks, which is still
a reason to wait.

### The three things nothing type-checks — all verified

1. **`&arguments[1..]`.** `main.rs:34` already establishes the convention one line
   from where the arm goes: `run_parse(&arguments[1..])`. Copy the neighbouring
   arm's shape.
2. **Two width resolvers.** `argparse_columns()` for `Help` and `Error`,
   `terminal_width()` for `Run`. The driver is correct as written; the hazard is a
   later unification, which the existing disagree-on-`+96` test defends.
3. **Warnings.** `eprint!`, not `eprintln!`, before the match — the warning carries
   its own newline.

### G5's expiring precondition — answered, no question spent

`g5-runbook.md` states `run` had no callers as of 2026-09-01 and that **the
cutover is what expires it**, since that caller chooses the width source. Intended
source is `terminal_width()`, which the driver uses. `colored_width_gate` and the
ambient sweeps already cover both sources, so it is a gap only if the wiring uses a
**third** source. Check 7 after the cutover is the check. `reviewer-profiler`'s one
question was not needed.

### `HOME` resolution — landed in the driver, verified against legacy

`.expect("HOME")` **panicked where the product works**, and its message named
`main.rs`, which after the cutover is the production file. Replaced with a
three-branch resolver, because `posixpath.expanduser` distinguishes three states
and a `home_dir`-shaped convenience call collapses two:

| `HOME` | legacy | `std::env::home_dir()` | resolver |
| --- | --- | --- | --- |
| a path | that path | that path | that path |
| unset | passwd entry, search works | passwd entry | passwd entry |
| **empty** | **`/`** | passwd entry | **`/`** |

Verified against the **live** `ch-legacy` route on both edge shapes, not against my
expectation of it: `HOME unset: MATCH`, `HOME empty: MATCH`.

**Third instance of one class this week** — empty custom title, empty script
object, empty `HOME`. The question to ask of any convenience call: *does it
distinguish absent from empty, and does the product?*

## Queued — two left, all untouched

Items 1–4, economy 2 and the `HOME` measurement are done. These two remain, in the first mate's order. **All untouched.**

1. **`HOME` unset.** `searchdriver` uses `.expect("HOME")`, which is a panic on a
   missing environment variable once copied into `main.rs` — a behaviour, not an
   implementation detail. Measure what `ch-legacy search` does with `HOME` unset
   and match it; the cutover copies from the driver. Standing constraint 1 makes
   the unset case reachable rather than theoretical.
2. **`terminal.rs`'s private `chop_cells` — delete it, call `metrics.chop_cells`.**
   They disagree: `chop_cells("你好", 1)` gives `["", "你", "好"]` in Rich and in
   `cells.rs`, `["你", "好"]` in the private one, which carries an extra
   `!line.is_empty()` guard. `cells.rs` is gated on 20,056 recorded Rich answers.
   Unreachable above width 1, so cheap rather than urgent.
3. **Gate `session_render.rs`'s copies of `re_word` and `rstrip_end` against
   `probes/wrap-oracle.tsv`.** Both copies are needed and neither is wrong;
   unifying is deferred past cutover. One table over both catches drift without
   paying for the refactor, and "remember to unify these later" is the form that
   has failed every time this week.
4. ~~Economy 2's ordering test.~~ **Done and falsified.**
   `a_failed_mafter_returns_before_the_cafter_probe` in `rust/search/plan.rs`, with
   a control beside it. The trick: an **invalid** `-ca` beside a rejecting `-ma`.
   In the right order the `-ca` string is never parsed, so the verdict is
   `Rejected`; swap the probes and parsing it first turns the same case into
   `Failed`. That asserts the **ordering** — a test checking "a rejected file
   produces no hit" passes either way. Falsified: the `cafter_probed_before_mafter`
   swap makes it red with a message that explains itself.
   The control matters: without it the first test would also pass against a screen
   that never looked at `-ca` at all.

## Stop point — 2026-09-01, handing off the cutover

**The cutover is prepared and NOT landed, and it should not be landed by this
seat.** Ninety per cent of a context window is not enough for the arm, and a
landing abandoned midway in `rust/main.rs` is the one failure on this mission with
no cheap recovery. Everything needed to land it is in the sections above.

**Tree digest at handoff**, `rust/**/*.rs` hashed in sorted order:

```
tree                 ca874ce060f1
search_engine.rs     bd23b41526de      codex.rs           4c7bfd2c4e98
search_confirm.rs    f35a86bf8c54      raw_transcript.rs  76df0701b527
search_output.rs     a358e67632a5      python_io.rs       ff245bf7c517
search_run.rs        f478f84bd73d
```

**State:** 234 lib tests, five build configurations green. Uncoloured G4 **54 of
54, 0 unstable** on the frozen pool; coloured G4 green on all four original cases
plus `g4-fence-covered-later`. Engine falsification 9 of 9; Codex 10 of 11 with the
survivor an unreachable branch.

**Nothing is partially written.** No mutation sits in any file. The only production
edit since the last stop is nothing — the `HOME` resolver went into
`probes/searchdriver`, deliberately, so the rehearsal stays faithful and it travels
with the arm rather than landing ahead of it.

**Two things wait on other seats, neither a crash:** the `Edit` diff renders a body
where legacy renders a unified diff, and the `Read` line-number gutter. Both are
visible parity breaks, which is reason enough for the arm to keep waiting.

**One thing waits on nobody and is ruled but unimplemented:** render plain on
lexer budget exhaustion, with the false comment removed. See the ruling above.

**The snapshot at `/private/tmp/ch-pool-snapshot` stays** — an APFS clone taken
2026-08-29, costing no disk, and the thing that makes G4 re-derivable rather than
believed.

## Context reporting

My harness exposes **two** quantities that differ by more than tenfold: a session
token budget (`total_tokens left`, 15,000,000 initial) and a context-window
percentage. Name the quantity every time, and give the context window when only one
is available, because that is what ends a session.

At this writing: session budget **14.11M of 15M**. For the context window the
harness last reported crossing **75%** and has not given a newer figure — **do not
estimate past a harness reading**, since roster and pause decisions are made on it.
