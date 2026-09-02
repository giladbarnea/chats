# reviewer-profiler — resume state

Kept current as work proceeds. Last updated after the first full A2 gate run.

## Role

Independent reviewer and profiler. Edits no production code and no tests. Owns the gates,
the instruments, and the final G5 verification. Holds the shell-suite token, unused since the
morning baseline.

## Instruments, and how they fit together

All in this directory. **Import them, do not copy them** — a copied tool grades against a stale
probe set and reports `CALIBRATED` while meaning less than the word implies.

| file | what it is |
| --- | --- |
| `calibrate_harness.py` | Grades a capture *and* its comparator against 14 probes. Declared blindness passes, undeclared fails, stale copies fail. `load_by_path` is the safe path-import helper — plain `spec_from_file_location` breaks on any file containing a dataclass. |
| `pty_harness.py` | Runs a command under a real pty at a chosen width. Caller-supplied environments are used **verbatim**; defaults apply only to an inherited one. |
| `calibrate_pty.py` | Grades the width axis, which no byte payload can reach. |
| `colored_width_gate.py` | Colored parity at 60/120/200, with 80 as a demonstration of why 80 must not be the gate. |
| `age_pairing_gate.py` | Pins the age label-to-colour pairing, which every comparator folds away. |
| `colour_capability_sweep.py` | The colour-downgrade divergence matrix across six terminal capabilities. |
| `performance_gates.py` | The A2 gates: six timing shapes, three memory shapes, the oversized-line parity arm, and `--falsify` to prove they can go red. |
| `console_reset_plugin.py` | Diagnostic only. `contract-owner` is landing the real `conftest.py`. |
| `allocation_profile.py` | Fits peak RSS against payload size across five arms. Answers *how many resident copies*, which a single ratio cannot. |
| `ratio_scaling.py` | Runs a ratio across four corpus sizes to decide whether it is a property or a point on a curve. |
| `tool_visibility_oracle.py` | Generates the 7315-case `resolve_tool_visibility` table, with both the Python and Rust input shapes. |
| `width_probe_fixture.py` | Seeds a fixture with width-unstable characters. Delegates the delta derivation to `views-and-colour`'s `differing_between`; my own range scan found 29 of a true 2,350 and is deleted rather than kept beside theirs. |
| `ambient_gate.py` / `ambient_gate_piped.py` | Per-environment-variable rows, asking *does the route respond* and *do the routes agree*. Two conditions, because each is blind to what the other catches. |
| `economy_probe.py` | Times the byte-invisible economies: streaming, early close, filter-before-probe. |

`context-curator`'s `tests/data/search-content-fuzz/fuzz_harness.py` imports `calibrate_harness`
and their `calibrate_width` grades the width axis in both directions. Leave it where it is.

## A snapshot is a correctness requirement, not hygiene

Sessions in this project's own directory belong to agents running now, so a file can grow
between one route's read and the other's. Every correctness comparison must read a snapshot,
and `session-core`'s harness adds the refinement that the *original* path is passed for provider
classification while both sides read the *snapshot* bytes, because Python classifies by
location. Without that, failures are intermittent, plausible and irreproducible.

All my correctness results are on the frozen corpus, so they are unaffected. Two early timing
and memory numbers were taken against the live pool before the corpus existed — both are
superseded by the corpus measurements in the plan and neither is quoted anywhere.

## Corpora

- `~/.cache/ch-search-corpus/v1` — frozen. 695 files, 1,183,541,907 bytes, identity
  `de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965`. `performance_gates.py`
  refuses to run if that digest moves. **Not reproducible** — rebuilding from a grown pool
  gives a different corpus, so if it is lost the budgets get re-baselined, not regenerated.
- `~/.cache/ch-search-corpus/pi-bigline` — four arms for the oversized-line memory probe:
  `large`/`small` carry the agent marker, `claude-large`/`claude-small` and `pi-nomarker-*` are
  the controls that proved the trigger is the marker rather than the provider.

## Done

Branch verdict (promoted), the review-and-profile plan (promoted, and the A2 design), the
instrument-calibration procedure, the ambient-input enumeration, the colour-downgrade sizing,
the age pairing gate, the A2 gates with ratio conversion, the allocation profile, and the
`resolve_tool_visibility` seam review.

Three results worth not re-deriving:

- **Memory mechanism named.** Native peak = `9.00 x payload + 21 MB`; Python = `7.01 x payload
  + 82 MB`. Two extra resident copies, not "29% more". The fit predicts the lines cross at
  30.5 MB and they measure level at 32 MB, which is the model validating itself. Native wins
  below the crossover and loses above it, so the gate only sees the losing half.
- **Ratio gates are properties above ~200 files.** 0.127 / 0.153 / 0.147 / 0.145 across 70 /
  174 / 348 / 695 files. Below roughly 200 the ratio flatters the native route, because
  Python's interpreter startup is a fixed cost it does not pay.
- **`resolve_tool_visibility` has no PyO3 exposure**, which is why its differential stopped at
  `parse_tool_spec`. The oracle table closes it: 7315 cases, 696 spec lists carrying a
  specificity tie, and it catches the two plausible wrong ports at 558 and 634 cases.
- **Nothing new is reachable from Python *in-process*.** `python_extension.rs` exports twelve
  functions, all older helpers; of the twenty-five public items in `tool_filter`, `visibility`,
  `terminal` and `pager`, zero are exposed. The boundary is real. **The consequence I first drew
  from it was too strong** — I said every proof on new code must be a table oracle, an
  end-to-end case, or absent. There is a third method and `session-core` is already running it:
  an out-of-process differential, a small binary linking the crate as a path dependency and
  speaking a line protocol over stdin, so both sides compute fresh. Four live today —
  `truncate_middle` 308 cases, `parse_tool_spec` 2006, `branch_map` 355, the full Claude route
  2436. It costs a subprocess and widens no production surface. So the ordering is: prefer the
  out-of-process differential where both sides can compute, fall back to a table oracle where
  they cannot, and end-to-end for the route.
- **Early close is lost on the native route.** Reader closes after one line: native saves −4%
  and −1% at two shapes, Python saves 87% and 95%. Confirmed by a second path through
  `head -1`, and the whole output is 20,831 bytes against a 64 KB pipe buffer, so it is not
  back-pressure. Streaming and filter-before-probe both survive and the native side is better.
- **`ch search . -ll | head` prints a 1399-byte traceback and exits 120** on the shipping
  launcher. `search.py:350`. Ruled a product defect, not a parity target — the native route is
  correct as it stands.
- **`UNICODE_VERSION` is a sixth ambient input**, found by `views-and-colour` porting
  `rich.cells`, verified by me at both levels: `load("auto")` gives 464 spans at latest against
  371 at 9.0.0, and rendered bytes go 2513 against 2492 on the Python route while the branch
  binary does not move. Their `rust/cells.rs` already reproduces it, so this is about the branch.

  **The bound is the lesson.** My sweep is organised around colour inputs and width resolvers;
  `UNICODE_VERSION` is neither, because it decides how wide a *character* is — the layer between
  them. A sweep is bounded by its inputs, its conditions, **and its categories**, and the
  categories are invisible from inside it. Conditions I found by suspecting them; this one I
  could not have suspected, because naming the category requires knowing the layer exists.

  Three of my own instrument failures nearly made this a false negative: a fixture with zero
  non-ASCII characters, probe codepoints chosen by intuition rather than derived from the table
  delta, and `rg` silently skipping `.venv` because it honours `.gitignore` — **pass `-u`**.

- **Five ambient-input gaps, across two conditions.** `COLORTERM`, `NO_COLOR`, `TERM=dumb` are
  visible only under a pty; `FORCE_COLOR` and `TTY_COMPATIBLE` only when piped. `LINES` and
  `TTY_INTERACTIVE` are inert in both, `TZ` agrees in both. An environment sweep must enumerate
  the conditions as well as the inputs — a condition can make an input inert and the row then
  reads as a clear.

## Half-done, and the state to pick up from

1. **Two budgets in `performance_gates.py` are still provisional and were not re-taken.**
   `selective literal, id-only` (750 ms) and `broad regex miss, id-only` (1000 ms).
   **Do not relax either budget to make it pass** — that is exactly how the live-pool budgets we
   retired reached 1750 ms and 2500 ms.

   The diagnosis is done even though the re-take is not. Seven repetitions in a clean window,
   route-bracketed, oracle state `8cb4c5f` + oracle route digest `sha256:dd6ab701…`:

   | shape | native min / median / max | spread | native÷python |
   | --- | --- | ---: | ---: |
   | selective literal, id-only | 360.3 / 372.8 / 568.0 ms | **56%** | 0.142 |
   | broad regex miss, id-only | 467.4 / 498.5 / 538.7 ms | 14% | 0.105 |

   So neither earlier window was contaminated — `selective literal` genuinely swings 56% run to
   run, which is why it read 360 ms once and 833 ms later. **An absolute budget on that shape
   will flap no matter where it is set**, which is the same defect as the budgets we retired.

   **The fix, when work resumes: convert these two to interleaved ratio gates** against the
   Python route measured in the same window. The ratios are stable where the absolutes are not
   — 0.142 and 0.105 — and §3 rule 4 and §12 already call for ratios alongside absolutes. Keep
   the four well-behaved shapes on absolute budgets; they pass with real headroom.

2. **The Python column of the run before that is void.** See the interference note below. The
   later route-bracketed run is sound: all six timing and all three memory shapes passed
   natively, and all nine went red against Python, so the set is sensitive.
3. **The age pairing gate needs `contract-owner`'s clock-relative fixture source** to reach all
   seven pairings. It covers two today and says PASS, which overstates it.
4. **Ambient-input gate rows are enumerated but not all built.** §8a lists thirteen inputs and
   seven gaps; only width and colour capability have gates.

## The interference the private copies did not stop

A private copy of the launcher **is not private**. `ch` is self-contained, but the Python route
is a launcher plus a sibling `ch-legacy` script plus an interpreter plus a site-packages tree.
Copying the first two leaves the run depending on a shared, mutable install.

That is not theoretical: during the last gate run `session-core` reinstalled the uv tool, and
`~/.local/bin/ch` did not exist at all for part of it. The private `ch-python` failed instantly
with "Cannot start the private ch legacy entry", 6 MB resident, and the memory-parity row
recorded Python at +0 MB — a clean-looking PASS produced by a route that never ran. The native
column of that run is sound and independently reproduced at 597 MB against 20 MB.

**To measure the Python route privately, the interpreter and site-packages must be inside the
copy**, or the measurement must wait for an exclusive window.

## Conversions and freezes — exact state

**Done.**
- `freeze_references.py` + `frozen_reference.json` — 42 reference outputs (4 widths, 16 ambient
  pty, 16 ambient piped, 6 capability tiers), oracle-stamped, all verified to contain a real
  search hit. Proved not-weakened: verifying against the native route drifts 13 of 42, every
  drift a known defect, and `width/80` and `capability/truecolor` correctly agree.
- `probes/emit_table.py` — the shared declared/undeclared ratchet, falsified in all four states
  (clean emits, undeclared refuses, declared records with reason, stale declaration reported).
- `probes/shortening_differential.py` — wired to it and run end to end: 308 cases, 0 mismatches,
  table emitted. Staged at `shortening_frozen_table.json` (101 KB) for `contract-owner` to place
  beside `tests/data/search-frozen-differentials/`. Verified to carry no home paths, no session
  ids, authored inputs only. Keyed by sample index, which matters: the NFC and NFD samples agree
  on only 10 of 22 limits, and a text-keyed table would have deduplicated the other 12 away.

**Done — the driver reappeared and the conversion completed.**
- `branch_map_differential.py --emit-table` run green: **360 sessions compared, 227 carrying at
  least one branch, 0 mismatches, 7 fixture cases emitted** to
  `branch_fixtures_frozen_table.json`. Verified: no home paths, no session ids, fixture names
  only. **Re-run against the tree driver** at `probes/drivers/branchmap`, built from its README
  recipe — same result. My first run used a stale scratchpad binary that happened to agree;
  agreeing is not the same as being quotable, and I had no way to know it agreed.

**Superseded, kept because the finding stands.**
- `branch_map_differential.py` now takes `--emit-table`, emitting **only** the seven authored
  fixtures (`combined-eras`, `compaction-boundary`, `equal-depth-fork`, `no-recorded-leaf`,
  `numbering-order`, `rewind-to-first`, `truncated-head`) and never the real sessions. It parses
  and is correct by inspection, but **it has never run**, because its driver binary does not
  exist on disk. `branchcheck` in the scratchpads is the *render* driver — it takes `path`,
  `flags`, `provider` — and the only other candidate is a regex probe. Its docstring also says
  six fixtures where there are seven.

  **A driver is as perishable as the oracle, and nobody priced that.** These drivers live in
  per-session scratchpads under `/private/tmp`, which are session-scoped. The conversion plan
  assumed "run it once more before cutover" is always available; for `branch_map` it already is
  not, so `session-core`'s 355-case branch result is currently unreproducible. The shortening
  driver survives — I used it — and the render driver survives as `branchcheck`.

  **Consequence:** either rebuild the branch driver from `session-core`'s map before cutover, or
  record the 355-case result as a dated point-in-time proof that cannot be re-run. The second is
  honest; the first is better if the recipe is in their map.

**Remaining.**
- `allocation_profile` — freeze Python's `7.01x + 82` as one constant, folded in when the slope
  prediction runs.
- `ratio_scaling` retires rather than converting.
- Registering the frozen set with the oracle guard — `contract-owner`'s, asked, may land in
  their handoff instead.
- Add `UNICODE_VERSION` as a row to both ambient sweeps and re-freeze (42 entries becomes 44).

**Deliberately not converted, and must not be.** `branch_map_differential` and
`claude_render_differential` are keyed by paths into the user's live private sessions. A stored
table would be unportable, unstable, and would commit conversation content to a tracked
directory. Run once more before cutover and record as dated point-in-time proofs.

## Two things that exist nowhere else

**1. The reverse gate is built, not pending.** It was finished and falsified before the
retraction of its approval arrived, so there is no half-started work. Both ambient sweeps now
report both directions. Falsified by swapping subject and reference: the four forward gaps move
to the reverse list and the forward list empties. Against the branch the reverse list is empty.

**Its open design question, which is the part with no home outside this file.** The gate compares
bytes under two settings, so it asks *does the native route **respond** to this input today*. It
does **not** ask *is this input **consulted** at all*. Those differ on exactly one known case:
`search_run.rs:108` threads `CellMetrics::from_environment()` into `PlainSink`, which reads
`UNICODE_VERSION` and cannot move the bytes while the product's elision counts code points. My
gate reports that clean, correctly, and it arms the day anyone repairs `elide_to_width` to count
columns.

**My position: it should not try to answer the stronger question.** "Consulted at all" is not
observable from outside the process — it needs a source read or instrumentation, which is
structural review. A byte gate attempting it would produce a measurement-shaped answer to a
question measurement cannot reach. So the split is: this gate owns *responds*, `slice-reviewer`
owns *consulted*. The limit is in the gate's own docstring, not only here.

**2. All of G5 is mine, alone.** Independent final verification — the complete route, the full
suite, the installed launcher, package ownership, no Python or PyO3, fixed-corpus performance,
and scoped diff cleanliness. It is the one role that cannot be done at the end by whoever has
capacity left, and cannot be done at all by someone who helped build the thing. No second owner
exists. If this session does not return, that gap is the mission's largest.

## Session of 2026-08-29

**G5 skeleton written and promoted** as `g5-runbook.md`: 15 checks, 8 runnable now, 7 blocked on
the cutover with the reason named. Three proved against the current tree — no PyO3 on the
artifact, the frozen set at 0 drift, the scoped diff enumerated.

**Frozen set 68 → 82.** Added the `--color` flag matrix (8) and per-file-error stderr shapes at
two widths (6). The flag matrix pins a preserve-because-wrong behaviour nothing had recorded:
**`--color never` on a pty still emits colour**, 841 bytes, because the plain path styles its
rule unconditionally. A port implementing `never` as "the plain path" produces 721 bytes and
diverges.

**A blind spot in the stderr baseline, found by `slice-reviewer` from the file alone.**
`NO_COLOR` and `TERM=dumb` were byte-identical there. I ruled the fix unavailable — wrong, and
the error was expensive because an unavailability ruling closes a fix. The attribute comes from
the *message content*, not the console style: Rich's `repr.brace` is `Style(bold=True)`, and the
product emits `[Errno 21]` on any unreadable session file. **Closed and verified: 244 B with the
bold brace under `NO_COLOR`, 220 B with no SGR under `TERM=dumb`.** Entries are `{HOME}`-
normalised, or they would be the one row nobody could re-derive.

**Still open on that surface:** the second separator. `TERM=dumb` pins width to 80 before
`COLUMNS` is read, so the two states also diverge on wrapping — but my errno shape is byte-
identical at 80 and 120, so it does not wrap and the brace carries the discrimination alone.

**Engine measurement is held.** Only the plain sink is reachable through
`engine-and-codex/probes/searchdriver`; every colour mode collapses to one uncoloured output, so
the coloured sink is exercised by nothing. The frozen set reports 50 of 68 drift against it and
**that number is an artefact of an unfinished surface, not a quality signal.** `id only` matches
Python byte for byte at 76 B, which is the one comparison that means anything today.

**Three of `slice-reviewer`'s designed mutations answered.** The calibrator passes its null-probe
test — a probe whose mutation changes nothing is reported blind and the run fails — but
**accidentally**, via the equal-payload branch in `_blind_dimensions`, now documented as
load-bearing because a smarter check would satisfy every probe and quietly stop meaning
anything. The `tool_visibility_oracle` alphabet is **1 of 4**: it has the equal-specificity tie
and lacks a prefix pair, a case pair, and — demonstrated observable — the alias/canonical pair,
where `['exec_command:s=100','Bash:s=200']` gives 200 and the reverse gives 100.

**M3′ is unanswerable with the width gate**, proved on the input rather than the output: the
gate's query returns one session whose longest body line is 36 characters against a ~116-column
interior. **Capacity in the corpus and capacity in the cases a gate runs are different
quantities** — the corpus has a 617-character line; the query selects only short bodies.
Requirement: a case whose *visible* body has a line of 117–196 characters.

## Next

1. **Queued prediction test.** When `session` lands, re-run `allocation_profile.py`. If the
   native slope falls from 9.00 toward 7.00, `session-core`'s clone-versus-move hypothesis was
   the mechanism and the memory row closes. If it does not move, the hypothesis is dead cheaply
   and the next step is measuring allocations directly. A prediction that can fail.
2. G3 reviews as slices land, split with `context-curator`.
3. Ambient-input gate rows: seven of thirteen inputs still have no gate.

## Oracle stamp

Every number in `review-profile-plan.md` and in this file was taken at HEAD `8cb4c5f`, oracle route digest `sha256:dd6ab701…`, via
`tests/oracle_digest.py::oracle_route_digest`. The earlier `a99c3302d0f852ba` was withdrawn:
it digested `src/` only, so it read unchanged while a `uv sync` replaced the Python route.
A digest, never "clean". Re-verify or re-stamp on the next oracle event.

## What each instrument refuses to do

- `calibrate_harness.py` — refuses to pass a stale copy, or an undeclared comparator blindness.
  It does **not** grade width or clock; those need a live subject.
- `pty_harness.py` — refuses `TERM=dumb` unless asked, and refuses to complete a caller's
  environment. It does **not** decide what a correct width is.
- `colored_width_gate.py` — refuses to treat 80 columns as a gate width.
- `age_pairing_gate.py` — refuses absolute colour as evidence; pins the label-to-colour pairing.
  Sweeps `CH_NOW` across seven instants, so it now covers **all seven label units** (12 distinct
  pairings on the Python route) rather than the two the corpus reaches on its own. Refuses to
  report a PASS when the subject returns fewer than five units across those instants — a route
  ignoring the clock pin would otherwise be checked on two pairings while the gate reported
  seven units' worth of confidence. The branch binary fails that guard, correctly: it predates
  the clock seam.
- `performance_gates.py` — refuses to run against a corpus whose digest moved, and voids its own
  run if the route changes underneath it. `--falsify` refuses to accept a budget the Python
  route could meet.
- `colour_capability_sweep.py` — refuses inherited environment defaults; each tier is set.

Launcher window: **released.**
