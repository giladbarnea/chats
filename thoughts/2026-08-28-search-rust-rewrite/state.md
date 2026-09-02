# State — fully native `ch search`

Decision record. Owned by `search-firstmate`. **Last update: 2026-08-29.**

> ## ⚠ HOW TO READ THIS FILE
>
> **It is append-only and later entries supersede earlier ones.** The
> **`L`-numbered section at the end is newer than everything above it**, and the
> most recent `L` entry on a subject is the current one. Earlier text is left in
> place, with a `⚠` marker where it was superseded, **because the reasoning that
> was overturned is often the useful part.**
>
> **Do not quote anything above the `L` section without checking for a later
> entry on the same subject.** This header itself was stale for a day and said
> *"Phase 1 closing, G2 blocked on one measurement"* while both G4 gates were
> green — the exact failure L194 describes, in the first four lines a reader
> sees.
>
> **Current state, 2026-08-29:** **both G4 gates are green** — uncoloured 54 of
> 54 on a frozen pool, coloured green on all four original cases, **red only on
> two fence cases that are red by design.** **The cutover has not landed and
> waits on the lexer tables** (L182, L184). G5's runbook is written, 15 checks,
> 7 blocked on the cutover.

## ▶ RESUMED — 2026-08-28, admiral lifted the pause

A new 5-hour window opened. All seven sessions restarted with prior ownership and
sequencing intact. The pause cost nothing: nothing was committed, reverted, or
left half-applied, and every teammate had a current brief.

**Live assignments on resume.** `search-runtime` moves the pager into the engine
— the critical path, because it is the structural condition before the engine
package can start. `session-core` runs the `truncate_middle` doctest inside the
crate now that `cargo test` is unblocked, then compiles `tool_filter.rs` for the
first time. `query-semantics` closes the last two diagnosed divergences, then
takes the engine. `contract-owner` holds the launcher window for a re-bless and
clean re-run. `reviewer-profiler` converts the two flapping shapes to interleaved
ratio gates. `context-curator` waits for the first G3 slice.

*The no-recovery rule applies only when the current window is actually
exhausted.*

### The pause record, kept because it is the resume baseline

The 5h allowance fell to 6–11% remaining. All seven sessions stopped cleanly. No
models switched, no replacements spawned, no recovery attempted. **Read this
section, then `teammates/<name>/RESUME.md` for the scope you are taking.**

### Gates completed

| Gate | State |
| --- | --- |
| G1 — Phase 1 | **done.** All six documents written and promoted. |
| G2 — boundaries and DAG | **done.** Ownership map and task DAG published below. |
| A1 — oracle and contract | **done.** 5 proof classes, 227-case corpus + 25-case amendment corpus, oracle guard live. |
| A2 — performance gates | **done, two budgets provisional.** See blockers. |
| A3 — `terminal_width` | **done.** `rust/terminal.rs`, 12,096 rows against Rich, zero differences. |
| Clock seam | **done and proved three ways.** 252/252 cases reproduce; the oracle moved without moving behaviour. |
| B1 — inventory and scanner lift | **done and green.** One substantive diff line, the documented de-PyO3-ing. Full Python suite exit 0. |
| B2 | **2 of ~5 slices.** `codecs.rs` escaping repair and `rust/shortening.rs` both proved. |
| B3 | **~95%.** 15 defects fixed, hand-written gates at zero, generated divergences 994 → **2**, and both remaining causes are already diagnosed — see their `RESUME.md`. |
| G3, G4, G5 | not started. |

### Working tree at pause

Nothing is committed. `src/chats/` digest `a99c3302d0f852ba` — HEAD `8cb4c5f`
plus the clock seam only.

- **Modified:** `rust/codecs.rs`, `lib.rs`, `main.rs`, `model.rs`,
  `python_extension.rs`; `src/chats/commands/search.py`; `tests/lib.sh`.
- **New:** `rust/clock.rs`, `inventory.rs`, `scanner.rs`, `search_query.rs`,
  `search_query_unicode_names.rs`, `shortening.rs`, `terminal.rs`,
  `tool_filter.rs`; `tests/conftest.py`, `test_search_command_contract.py`,
  `query_pattern_corpus.py`, and three fixture directories.

### Blockers to clear first

1. **`rust/shortening.rs` doctest is red, and there are three candidate causes.
   Do not change an expected value before ruling them out.**
   `truncate_middle` expects `"abc\n...\nij"`, gets `"abc\n...\nab"`.
   *(a)* `contract-owner` believes the **expectation** is the transcription error
   and the implementation right, because `"abc\n...\nab"` looks like the `s[-0:]`
   whole-string behaviour we ruled must be reproduced verbatim.
   *(b)* `session-core` notes their doctests **have never run inside the crate**,
   because `cargo test` was red from `search_query.rs` at the time. In their
   standalone harness the doctests failed only because they name the real crate
   `_native`, which that harness is not. So the failure may be about the harness
   rather than about either the expectation or the code.
   *(c)* The implementation is genuinely wrong.
   `query-semantics` has since unblocked `cargo test`, so **running the doctest
   inside the crate is the first step and may resolve it outright.**

2. **`rust/tool_filter.rs` is written and has NEVER been compiled.** It is not
   declared in `lib.rs`, so it is inert and the tree builds green without it. It
   is not landed work. Whoever resumes declares the module, builds, and should
   expect real errors.
3. **Two performance budgets are provisional — and the cause is now known.**
   **Neither earlier window was contaminated.** Seven repetitions in a clean,
   route-bracketed window gave `selective literal, id-only` at 360.3 / 372.8 /
   568.0 ms — a **56% run-to-run spread**. That is why it read 360 ms once and
   833 ms later. `broad regex miss` spreads 14%.
   So an absolute budget on `selective literal` will flap wherever it is set,
   which is the same defect as the live-pool budgets we retired. **The ratios are
   stable where the absolutes are not** — 0.142 and 0.105 against the Python
   route in the same window.
   **The fix on resume: convert those two shapes to interleaved ratio gates and
   leave the other four on absolutes.** Sections 3 and 12 of the plan already
   call for it.
   Until then both stay marked provisional, and **they must not be relaxed to
   make them pass** — that is how the retired live-pool budgets reached 1750 ms
   and 2500 ms.
3. **The memory parity gate's 1.29×** awaits an allocation profile. Not part of
   B1.

### Resume order

1. `search-runtime`: **move the pager from views into the engine.** That unblocks
   the engine owner, so it is the critical path.
   *`risk_character_pattern()` is closed as a rejection, not a to-do.* It was
   benchmarked rather than adopted: over a 128 KiB realistic non-ASCII chunk, the
   current `binary_search` runs 18.4–18.9 ms against the branch's regex at
   39.3–40.6 ms. **The branch's "optimization" is 2.1× slower**, because the
   current code short-circuits on `is_ascii()` and searches only 20 entries for
   non-ASCII characters while the regex must scan every byte. It was the one
   thing the branch had earned in that module, and measuring it showed it had
   not. Do not re-litigate.
2. `session-core`: resolve blocker 1, then `tool_filter.rs`, visibility,
   `rust/color.rs`, then provider decode.
3. `query-semantics`: finish B3's last 18 divergences and its re-run, **then**
   take the search engine. Strictly sequential, by their own judgment.
4. `reviewer-profiler`: re-take the two budgets in a genuinely quiet window,
   with the whole route bracketed, not just the launcher.
5. `contract-owner`: re-bless and re-run clean. Their last run's two failures are
   explained — a concurrent reinstall — so do not chase them again.
6. `context-curator`: G3 review as slices land. Criteria already promoted.

### Ownership, unchanged

`search-runtime` — `main.rs`, `lib.rs`, `python_extension.rs`, `terminal.rs`,
`clock.rs`, inventory/scanner/gates, engine and views until reassigned.
`session-core` — `model.rs`, `codecs.rs`, `shortening.rs`, `tool_filter.rs`,
`color.rs`, rendering, provider decode.
`query-semantics` — `search_query.rs` and its tables; the search engine on
resume. `contract-owner` — `tests/` and all fixtures. `reviewer-profiler` and
`context-curator` — no production files, and **do not convert either to an
implementer**; the reason is in decision 7's discussion and their briefs.

## ⚠ `search-runtime` is down — 2026-08-28

Their session ended without warning while a ruling was in transit. **Nothing was
lost**, which is the entire return on the resume-brief discipline:
`rust/pager.rs`, `terminal.rs`, `clock.rs`, `inventory.rs` and `scanner.rs` are
all in the tree, `cargo check --no-default-features` is green, and
`teammates/search-runtime/` holds a current `RESUME.md`, the promoted handoff,
the 76-case `probes/grammar-oracle.json` and the 12,096-row `color-oracle.tsv`.

**Unowned as a result: the argument grammar (`rust/search.rs`), `rust/main.rs`
routing, and the G4 cutover.** The engine went to `query-semantics` before the
loss. Views were already waiting on `session-core`.

### The ruling they never received — apply it to the grammar

Their last message reported **the seventh branch defect and a sharper finding
underneath it.**

*The seventh defect.* The branch's help text is a static string constant in
`search_help_consts.rs`, asserted against a single fixture. But argparse rewraps
the whole help body at terminal width: **42 lines at 96 columns, 68 at 60**,
differing from the first line. The branch emits identical bytes at every width
and is wrong at all but one. That is the third width defect sharing one blind
spot — every case in the branch's corpus pins `COLUMNS=96`, so a static help
constant, a `COLUMNS`-only helper and a fixed-44 elision all passed 704 of 704
for the same reason. **One unexamined dimension, three defects.**

*The sharper finding.* **The product resolves terminal width two different ways
and they disagree.** argparse goes through `shutil.get_terminal_size`, which is
`int(COLUMNS)` in a try/except and accepts a leading `+`, surrounding whitespace
and fullwidth digits. Rich uses `str.isdigit()` then `int()`. They differ on
`+96`, `0` and `' 96'`. Verified end to end on the real launcher: `--help` at
`COLUMNS=+96` resolves 96 while error wrapping resolves 80, same binary.

**Rulings, recorded here because they never reached their author:**

1. **Two resolvers, and this is not duplication.** `terminal.rs::columns_override`
   stays as Rich's rule for rendered output. The grammar gets its own with
   `shutil` semantics. A single resolver would be the helpful unification this
   team has now caught four times. Name each for what it models.
2. **Split the grammar into two slices.** Slice one is parsing, repairs, mode
   forcing, role normalisation and error bytes — everything except `--help` and
   `-h` — driven straight off the captured 76-case oracle. Slice two is the help
   formatter with its own width-sweep gate at several widths. This keeps the part
   most likely to overrun off the critical path.
3. **No divergence on help output.** It is public surface and legacy produces a
   correct answer at every width, so the line holds: we preserve. Fixtures cannot
   cover a continuous dimension and shelling to Python violates the charter.
4. **Test the narrowing before accepting the 400–600 line estimate.** That figure
   assumed reproducing argparse's general `HelpFormatter`. The parser's content
   is fixed and known — only the wrapping varies with width. If the usage
   assembler does not need the general part-splitting logic, the work may be much
   smaller. Unverified; the first mate has not read that code.

## Where we are

The team moves every public `ch search` shape into the package-owned Rust
executable. The finished route must keep public behavior exactly. It must not
start, import, embed, call, or fall back to Python or PyO3. The charter is
[`charter.md`](charter.md). Role prompts are in [`prompts/`](prompts/).

**The mission changed shape on day one.** A finished native `ch search` rewrite
already exists on an unmerged branch. The job is probably reconciliation, not
construction. One measurement decides it. See decision 8.

## Baseline

- Clean `main` at `9bf1e06`. Post-review fixes are committed at `47b3db9`.
- The shipped `ch` binary is one commit behind the Rust sources. Two teammates
  proved this independently. See decision 10.

## Roster

| Teammate | Owns |
| --- | --- |
| `search-firstmate` | The whole mission. Edits no production source or tests. |
| `context-curator` | Which historical material is safe, historical, or stale. |
| `contract-owner` | The red acceptance contract. Owns `tests/` and fixtures. |
| `session-core` | Provider decoding, normalization, visibility, facets, rendering. |
| `query-semantics` | Regex and literal behavior, boolean grammar, match truth. |
| `search-runtime` | Launcher routing, inventory, filters, ordering, output, exits. |
| `reviewer-profiler` | Independent review, baseline, corpus, performance gates. |
| `views-and-colour` | **Added 2026-08-28.** Views chrome and the colour seam. `prompts/views-and-colour.md`. |
| `engine-and-codex` | **Added 2026-08-28.** The engine's confirmation half plus Codex decode. `prompts/engine-and-codex.md`. |

## Gates

1. **G1 — exit Phase 1.** Every teammate's Phase 1 document is written and
   promoted. Mostly done.
2. **G2 — accepted boundaries.** The first mate publishes the ownership map, the
   file ownership table, and the task DAG. Production implementation starts only
   after G2. **Blocked** on the branch reproduction in decision 8.
3. **G3 — slice review.** Every accepted slice gets an independent review before
   the next slice opens. **A slice is not accepted while any harness feeding its
   evidence is uncalibrated.** No harness result is quoted in a review, a gate,
   or a promoted document until its calibration passes. The tool is
   `teammates/reviewer-profiler/calibrate_harness.py`: inject one minimal
   mutation per observed dimension and require the harness to see it. A blind
   dimension makes every result over that dimension vacuous. The null control
   runs first, because a harness that reports spurious differences would
   otherwise fake a pass on every sensitivity probe. Width and clock are not
   gradeable this way — they need a live subject under a pty and stay in the
   falsifier set.
4. **G4 — one cutover.** One `search` branch added to the routing in
   `rust/main.rs`. No Python is edited, added, or deleted. Reverting is deleting
   that branch. `ch-legacy search` stays a live oracle through the cutover.
   **⚠ Superseded on scope, not on shape — the cutover is NOT near.** This entry
   and several messages described G4 as "short, proved on `search-runtime`'s
   side, blocked only on the engine." That was true when written and is now
   wrong. `search-runtime` found it by checking rather than assuming.
   `rust/search_engine.rs` has landed and it is **the scheduler, not the engine
   entry point**: `stream_search<S: HitSink>(scan_order, sink, batch_size,
   screen, probe, confirm) -> Outcome` — ordering, batching, the
   window-flush-on-error rule, early close, and nothing more. **There is no
   `run(SearchArguments) -> ExitCode`; the only `ExitCode` in the crate is in
   `main.rs`.** The `Run` arm still needs six things, none landed:
   (1) the scan order, (2) the `screen` closure, (3) the `probe` closure,
   (4) **`confirm`** — parse, render, evaluate, the confirmation half, currently
   `engine-and-codex`'s step 2 and unstarted, (5) a `HitSink` across all five
   output modes routing through the pager, and (6) `Outcome` mapped to exit
   status including the empty-pool-exits-1 case.
   Items 1–3 have their machinery landed and need assembling. Item 4 is
   unstarted. Item 5 spans views and the plain modes. **The cutover is still one
   branch in `main.rs` and still `search-runtime`'s. It is just not near.**
5. **G5 — final proof.** Full suite, package and installed-launcher proof,
   no-Python proof, fixed-corpus performance, scoped diff check, and
   `final-change-log.md`.

## Decisions

1. **Collision rule until G2.** Every existing file under `src/chats/` and
   `rust/` is shared and unowned. No teammate edits any of them before G2.
   `tests/` and fixtures belong to `contract-owner`.
2. **File ownership is declared, not assumed.** Each technical owner names the
   files it needs to own and to create. The first mate resolves overlaps at G2.
3. **Commits.** No teammate commits. The first mate creates accepted checkpoint
   commits only.
4. **Performance gates are a Phase 1 deliverable.** The corpus identity and the
   numbers are fixed before any implementation exists. A gate agreed after the
   implementation exists is a negotiation, not a gate.
5. **Historical material is untrusted until classified.** `context-curator`
   rules on it. A coarse early verdict beats a complete late one.
6. **One authority. Lift, do not fork.** The PyO3-free logic in
   `rust/python_extension.rs` moves into feature-independent modules that both
   the `ch` binary and the Python extension use. No second copy.
   *Why:* `rust/lib.rs` includes that file only under the `python-bindings` or
   `extension-module` features, and `pyproject.toml` builds the `ch` binary with
   `--no-default-features`. Session discovery, provider classification, the
   candidate gates, and the file scans are ordinary Rust the binary cannot see.
   *Status:* on hold. Decision 8 may supersede the module split.
7. **No upward escalation. The first mate decides and records.** Nobody messages
   the Pi captain. Resolve a question with the teammate whose scope owns it. If
   no peer can resolve it, take the simplest sound path and record it below.
8. **The branch is prior art, never an oracle. Reconcile, do not rebuild —
   pending one measurement.** See the dilemma record.
9. **Desk and memory policy (captain).** Only `search-firstmate` writes
   team-level files under this desk, and only `search-firstmate` runs `memo` or
   writes under `.optmem/`. Teammates work inside `teammates/<name>/` and ask for
   promotion. Recorded in the charter and appended to every role prompt.
10. **`tests/run_all.sh` asserts binary provenance. It does not rebuild.**
    The suite refuses to run when the binary under test is older than the Rust
    sources, and names `uv sync --dev --reinstall-package chats`.
    *Why:* the suite stays a test runner rather than becoming a build tool, and
    an implementer who never rebuilds must not be able to reach a green.
11. **Colored output is its own slice with its own gate.** Its parity harness is
    a byte diff of `ch-legacy search --color always` against `ch search --color
    always` on a fixed corpus.
    *Why:* the three colored tests in `test_colored_rendering.py` assert
    substrings and SGR codes, not bytes, so they can stay green through a
    visible regression. This project has already been bitten by exactly that.

12. **Adopt the search route only. Keep the `run_legacy` fallthrough.** The
    branch's `main.rs` also routes the default session journey natively. The
    charter keeps default session parsing on `ch-legacy`, so that half is
    rejected. The reconciliation is narrow and lives in launcher routing.
13. **Do not delete the differential oracle.** The Python search implementation
    stays alive until the byte harness is green. Deletion is its own final
    slice. The branch deleted `search_query.py` and `session_scan.py` and
    stubbed `commands/search.py`, which destroys the one property that makes
    this mission provable: `ch-legacy search ARGS` and `ch search ARGS` can be
    diffed on the same corpus at any moment.
14. **One stderr line-wrap behavior, not three.** The branch carries three,
    because byte identity across its three journeys was judged unprovable. This
    mission is search alone, so the question collapses. The search route
    reproduces exactly the bytes `ch-legacy search` produces, proven by diff.

15. **The Rust `regex` crate cannot carry `ch search` semantics.** Measured: 39
    divergences in 50 probes against CPython 3.14.7. The dangerous ones compile
    cleanly in both engines and mean different things, including POSIX classes,
    class intersection, and class difference. Sharpest case: the crate reads
    `(?R)` as its CRLF flag, so the pattern becomes empty and `ch search '(?R)'`
    would match every session where legacy matches none. Any plan that assumes
    the crate is the query engine is unsound.
16. **Colored parity is best-effort, behind a two-part gate.** Provable colored
    parity needs Rich and Pygments, which needs Python, which fails the charter.
    So the gate is a fixed-corpus byte diff **plus** a differential fuzz against
    the live Python oracle, on an adversarially extended corpus. The change log
    states plainly that the highlighting is a reimplementation whose fidelity is
    corpus-bounded.
17. **Partial file ownership, granted early.** `rust/codecs.rs` and
    `rust/model.rs` to `session-core`. `rust/search_query.rs` and its generated
    Unicode tables to `query-semantics`. `rust/main.rs`, `rust/lib.rs`, and
    `rust/python_extension.rs` to `search-runtime`. The visibility, shortening,
    and tool-filter layer inside the branch's `session.rs` is `session-core`'s to
    extract. Nobody lifts `session.rs` wholesale. Agent transcript merging stays
    out of scope: `_merge_agent_messages` is parse-only and search never calls
    it.

18. **The branch is stale, not merely unproven. `main` wins by default.** The
    branch forked on 2026-08-25 and predates `main`'s repairs. For any file both
    sides touched, `main`'s version is the base and the branch must earn each
    individual difference. A difference is evidence of a missing fix until shown
    otherwise, never evidence of a design choice. Adopted branch code is rebased
    onto `main`, not merged with it.
    *Why:* `session-core` and `search-runtime` reached this independently, from
    opposite evidence. Four correctness questions `main` litigated after the fork
    still carry the losing answer on the branch: the fabricated BrokenPipe
    traceback with build paths baked in, the `JsonEscapeValidator`, the
    `COLUMNS`-or-80 width helper, and the tool key elided at a hard-coded 44
    columns.
    **⚠ The first mate propagated a lazy form of this and it must not be
    inherited.** "Eight for eight, the branch always carries the losing answer,
    assume the ninth" went into a handoff, a role prompt and several messages.
    **The rule is that a difference must be *earned*, in both directions** — not
    that the branch is wrong. A reader who inherits the lazy form rejects a
    branch difference without measuring it.
    *Current count in one scope: seven examined, six losing, **one won**.* The
    branch's hand-rolled panel frame matches Rich's `Panel` at widths 40, 60, 96
    and 100, including its `title_box = width - 5` and its `…─╮` truncation of an
    over-long title. Verified by measurement and adopted. The same person who
    rejected `risk_character_pattern()` on a benchmark promoted this win into
    `views-handoff.md`'s body rather than footnoting it, because a win in a
    footnote reads as an exception to the rule rather than as the rule working.
    **⚠ The win is WITHDRAWN. The count is seven examined, seven losing, zero
    won.** `views-and-colour` withdrew it themselves: the outcomes agree with
    Rich at the four sampled widths, **the mechanism does not**. Rich has no
    fits-or-truncates branch — it assembles the whole strip between the corners
    and clips *that* in one pass, so a title of exactly `width - 5` overflows.
    Their 11,200-line panel corpus caught it at precisely that boundary. The
    branch carries a latent boundary defect of the same shape.
    **The rule correction above survives and must not be withdrawn with the
    example.** A difference must be earned in both directions, because a
    benchmark could as easily have accepted `risk_character_pattern()` as
    rejected it. The panel is simply no longer the example — it was never one.
    See 22as for the general lesson, which is worth more than the example was.
19. **The `JsonEscapeValidator` question is a re-decision, and `main` wins.**
    `main` has `EscapedRiskScalarTracker` after a fuzz campaign disproved full
    deletion, because case-fold risk scalars keep the defer path load-bearing.
    The branch carries the pre-litigation answer. Reconcile its `scanner.rs` to
    `main`.
20. **The no-Python proof is the empty-directory proof.** `ch` alone, no
    `ch-legacy` sibling, stripped `PATH`. Search renders real hits and `-ll`
    lists ids. `ch info --help` fails with the private-entry error.
    *Why the loader trace is dead:* it reports "842 libraries, 0 python" for
    `ch info --help` too, which stays on the Python route by design. `run_legacy`
    uses `exec`, and macOS purges `DYLD_*` for a hardened-runtime interpreter, so
    the trace stops at the handoff. The branch applies that empty check to all
    173 of its manifest cases.
21. **Two flapping live-pool performance budgets are retired.**
    `tests/run_all.sh` is red on clean `main` today because of them. They are
    replaced by `reviewer-profiler`'s deterministic fixed-corpus gates. G5's
    green bar means green including the fixed-corpus gates and excluding the two
    retired budgets.

22. **Every gate is checked against the claim it supports.** A green result that
    measures something narrower than the claim is worse than no result, because
    it buys false confidence. Four instances appeared on day one:
    round-trip fidelity mistaken for cross-implementation parity; a line count
    mistaken for a diff; a loader trace that reports the same clean output for a
    command that does use Python; and a colored byte diff at 80 columns, which is
    the exact width where the known width defect is invisible.
    **The method, owned by `reviewer-profiler`.** For every gate a slice adds,
    name the claim the gate supports, then try to name an implementation that
    passes the gate and violates the claim. If one can be named, the gate is
    insufficient and it is said before the slice is accepted.
    **Concrete requirement:** the colored harness drives both binaries under a
    pty at two or more widths, neither of them 80, and one narrow enough to force
    elision in list rows and panel titles. The differential fuzz varies width as
    a generated dimension. 80 is both the branch's default and `main`'s fallback
    constant, so a diff at 80 hides the width defect and a total failure to
    measure alike.
    *A fifth instance surfaced later the same day:* the branch's character-range
    folding arm ends in `&& false`, so the whole clause is dead. It shipped
    through a green suite and an independent review.
22b. **Constraint 22 covers the instrument, not only the code under test.**
    Byte-diff harnesses capture bytes and compare bytes. `subprocess.run(...,
    text=True)` implies universal newlines and silently rewrites `\r\n` and lone
    `\r` to `\n` in captured output. Real transcripts carry carriage returns
    constantly, so such a harness agrees where the implementations differ and
    differs where they agree. Set environment variables directly rather than
    through a shell: a shell mangled `COLUMNS="９６"` to ASCII before the binary
    saw it, and the probe measured the shell.
    **Before trusting a comparison, prove the harness detects a difference
    planted deliberately, including one that is only a carriage return.**
    *Why:* both instrument bugs were caught only because their numbers were
    implausible in opposite directions. A harness bug producing a plausible
    number would have shipped. That is luck, not a method.
22c. **No finding is reported from an aggregate alone.** Print the specific
    instances that produced it and inspect them before writing anything down.
    *Why this is not covered by 22b:* `session-core` concluded that a harness bug
    producing a plausible number would have shipped. `context-curator` then
    produced exactly that — a consistent off-by-one at four independent widths,
    which is what a genuine wrapping bug looks like. Nothing in the aggregate
    would have prompted a second look. The cause was U+200B ZERO WIDTH SPACE:
    they had zeroed combining characters but not format characters. Calibration
    is necessary and not sufficient. Auditing instances is what caught it.
    *Also:* a width instrument fails in two directions. It must see a planted
    overflow, **and** it must not flag a line of zero-width and double-width
    characters that exactly fills the terminal. The second is the one that bit.
22e. **An invariant is only evidence over the modes where it is actually the
    contract.** Applying one uniformly across modes looks like more coverage and
    is actually less. Raw mode emits stored content verbatim rather than
    wrapping, so a width assertion there would have manufactured a confident
    false finding against a 131,070-character line. `OUTPUT_MODES` carries a
    `wraps` flag: exit status and UTF-8 validity are checked everywhere, the
    width check only where wrapping is the contract.
22g. **A gate must not name what it accepts by an identifier it does not own.**
    `contract-owner`'s comparator accepted one blindness by matching a probe's
    name. `reviewer-profiler` split that probe into four, the accepted name
    stopped matching, and a rename upstream read as a parity failure downstream.
    The verdict had been right the whole time. Identify an accepted exemption by
    what it *is* — here, two payloads differing solely in which age-bucket colour
    they carry — so a rename cannot break it and a new probe reusing the old name
    cannot slip through.
22h. **A harness must not silently complete its caller's environment.**
    `reviewer-profiler`'s colour sweep stripped `NO_COLOR` because the caller had
    set it, and defaulted `COLORTERM=truecolor` into the very rows meant to test
    lower tiers. Both confounded runs produced coherent, readable tables, and a
    retraction of a correct finding was half-written before the per-row profiles
    were read against the verdict column. **A wrong retraction is worse than the
    original error**, because work had already been commissioned on it.
    Defaults apply only to an inherited environment; a caller who passes one owns
    it verbatim.
22f. **Import shared tooling, do not copy it.** `reviewer-profiler`'s probe set
    grew from 8 dimensions to 14 within an hour. An importer inherited all 14
    with no change. A copier is now graded against a stale probe set, reports
    `CALIBRATED`, and means something weaker than the word implies. The tool must
    announce its own staleness rather than relying on a teammate noticing.
    *Mechanism note:* `dataclasses` resolves a class's own module through
    `sys.modules`, so a module loaded by path must be registered there before
    execution.
22d. **The native route resolves every ambient input the way Python does.**
    Enumerated rather than discovered one at a time: **13 ambient inputs, 7
    gaps.** Beyond width, the clock and `COLORTERM`, the native route also does
    not read `LINES`, `FORCE_COLOR`, `TTY_COMPATIBLE` or `TTY_INTERACTIVE`, all
    of which Rich honors. The `isatty` cascade needs its own row: `color`
    resolves from `sys.stdout.isatty()`, then `paging` defaults to whatever
    `color` resolved to, so one input drives two visible behaviors.
    **One gap is structural and is being sized before anyone builds.**
    `session_render.rs` has no colour-system decision anywhere — colours are
    hard-coded truecolor literals throughout, so the route cannot downgrade for a
    256-colour, 16-colour or dumb terminal, and `NO_COLOR` is its only off
    switch. It does not ignore `COLORTERM`; it has nothing to ignore with. This
    closes rather than becoming a documented divergence, because Python produces
    a correct downgraded render on those terminals.
    **Seam:** resolution is `search-runtime`'s, in `rust/terminal.rs`.
    Application is `session-core`'s, in the renderer.
    **Sized and approved 2026-08-28. Not a material cost increase.** Python
    downgrades on five supported environments plus two off switches; the native
    route emits identical truecolor on all six. But the resolution logic already
    exists in `stderr_color_enabled()` and is simply not wired to the render
    path, and application is one chokepoint — `Segment::ansi` emits every
    coloured byte through a single `format!`, so downgrading is an SGR parameter
    rewrite at one call site. 150–200 lines across about four sites. The 79
    truecolor literals do not change; they all flow through the funnel. Twelve
    raw emissions bypass `Segment`: six need only the off switch, two carry
    truecolor in the syntax-highlighting path and need routing.
    **The gate is exhaustive enumeration, not sampling.** The emittable colour
    set is fixed — theme, Monokai palette, border hue cycle — so the ported
    `Color.downgrade` is verified over its complete input set. Three exact-match
    hazards: `rgb_to_hls` must match `colorsys` branch for branch; **Python's
    `round` is banker's rounding while Rust's `f64::round` is half-away-from-
    zero, diverging at channel bytes 155 and 235**; and the STANDARD downgrade
    must stay integer arithmetic or nearest-match ties flip. The current palette
    dodges the rounding trap by luck rather than design, which is exactly why the
    gate cannot be the palette as it stands.
22u. **A normalization that silently no-ops is invisible in exactly the same way
    as one that is unnecessary.** A placeholder that never appears looks
    identical to a placeholder that is not needed.
    **Therefore: every substitution asserts that it fired.** Not that its output
    is right — just that it did something.
    *Earned:* the contract suite normalized the age *colour* first, which
    rewrites the SGR introducer the *token* pattern anchors on, so the token
    substitution matched nothing and never once fired. `{AGE}` appeared in zero
    files across both corpora while `{AGE_STYLE}` appeared in 15, and **17 files
    carried a live wall-clock `1w`** that would have rotted within days. That is
    the branch's defect exactly, with the two halves swapped — and section 4 of
    the contract states the correct rule while the code implemented its inverse.
    The calibration could not see it: it probes SGR *pairs*, proving the
    comparator is blind to age colour, which is true and declared. Nothing probed
    whether the substitution ran at all.
22v. **Accepting a correct explanation without looking is harder to resist than
    accepting a wrong one.** Four cases moved: two expected, two *explainable* —
    and the explanation was right, a provider column appearing because the pool
    now spanned two providers. Opening the bytes anyway is what put the raw `1w`
    in front of its author. There is nothing to be suspicious of in a correct
    explanation, which is precisely the danger.
22w. **Growing a shared pool changes which branches the existing cases take.** It
    does not only add cases. New Codex sessions activated a provider-column path
    the pool had never exercised, moving two unrelated expectations. A shared
    pool makes every existing expectation a function of every future addition —
    the real argument for the two-corpora split.
22p. **A tool that refuses is only useful if its refusal is legible.**
    `rebless_oracle.py` refused once before succeeding, reporting **all 251 cases
    moved**. That count told its author the *harness* was broken; "3 of 251"
    would have told them the *product* had. The number carried the diagnosis, and
    a 100% move rate is implausible enough to be its own alarm. Design refusals
    so the shape of the refusal names the cause.
22q. **A ratio gate falsifies itself.** The reference measured against itself is
    1.0, so a ratio ceiling below 1.0 cannot be met by an implementation no
    faster than the oracle. It cannot pass vacuously by construction, rather than
    by our remembering to check — a stronger property than any falsification
    bolted on afterwards, and a second reason to prefer ratios wherever the
    absolute is not measurable.
22r. **A suite is not isolated until every tool it invokes has its own output
    directory.** Isolating the obvious tool feels like completion and is not. For
    the contract suite, cargo was the obvious tool and also the last one; for the
    wheel test, cargo was obvious and `uv build` still wrote setuptools' shared
    `build/`.
    *And isolation breaks relationships:* moving the suite to a private cargo
    target killed every case at the launcher handoff, because `ch` resolves
    `ch-legacy` as its own sibling. The private-copy fix keeps producing new
    instances because the thing copied has neighbours.
22s. **Import-not-copy is for tools, and a small enough thing is not a tool.**
    `reviewer-profiler` declined a shared timing runner: eight lines, and taking
    it from `tests/` would make their ratios depend on a path `contract-owner`
    maintains for byte-differential purposes, so a later reordering — correct on
    its own terms — would move a gate with nobody touching a gate. Sharing has a
    cost duplication does not. Knowing which side of the line a thing falls on is
    the judgment.
22t. **Four instruments, and they are complements rather than alternatives.**
    - A **generated** corpus finds what its grammar can express.
    - A **curated** fixture finds what someone thought to write.
    - A **real** corpus finds what usage actually produces.
    - A **synthesized adversarial** fixture finds what the code can do that usage
      never asks for.
    *Both ends, on one function.* Claude branch resolution needed a real corpus
    to find that Python builds its graph from the node map rather than from the
    entries, so a repeated uuid contributes edges once — two duplicates in 2,919
    entries moved the whole map, and nobody writes that fixture. And it needed a
    synthesized fixture to find that Python's `max` keeps the first maximal
    element where Rust's `max_by_key` keeps the last, because **nothing in 347
    real sessions makes that observable**.
    *Also real-corpus-only:* three all-preamble Codex sessions are why the branch
    returns 563 ids where the oracle returns 560.
    **⚠ Corrected twice, and the second correction inverts the risk.** The count
    is **44**, not 3 and not 39 — 3 was correct only for a 695-file subset.
    And the *mechanism* recorded in `codex-handoff.md` is wrong: all six named
    files are excluded **before the decoder ever runs**. Their first line is a
    JSON object with no `type` field, so `detect_format` routes them to the
    raw-transcript parser, which also zeroes cwd, summaries and title.
    Measured: 1,208 Codex files, `search . -ll -p codex` returns 1,164, so 44
    excluded — **8 raw-format, 36 jsonl-format**. Every jsonl exclusion has 2–4
    entries; every large one (612, 449, 253, 179, 87, 37 entries) is raw-format.
    **So a permissive `parse_codex` cannot surface the large sessions and would
    wrongly surface the small ones.** Anyone building a guard from the handoff's
    framing would have built the wrong one.
    **And the fourth instrument needs an anchor: a synthesized fixture is
    validated against the real specimen it was synthesized from, and where they
    disagree the fixture is the suspect.** It reaches what usage never produces,
    which is exactly why nothing else can check it.
22aa. **A limit of your instruments is never a property of the world.** Say
    "nothing we have can see this", never "this cannot be seen". Two people —
    `context-curator` and the first mate — described four timing economies as
    *unmeasurable* when what either could support was that our instruments at the
    time could not see them. `reviewer-profiler` built the instrument anyway and
    found a real defect: the native route does not stop scanning when the reader
    stops, costing a 92% saving. **Had they believed us, it reaches G5.**
    Worse than a dropped qualifier, because it does not merely mislead — it stops
    people trying.
22ab. **Coverage that stops where the bindings stop looks identical to coverage
    that stops where the risk stops.** Only one of those is a decision.
    `resolve_tool_visibility` was uncovered because it is not exposed through
    PyO3, not because anyone judged it low risk. Every per-module differential on
    this mission — 2006 tool-spec cases, 308 shortening, 4000 patterns, 355
    branch resolutions — exists because the function happened to be reachable.
    *`contract-owner` is enumerating what else sits behind that boundary.*
22ac. **A fixture's justification travels with the fixture**, or someone removes
    it for looking unnecessary. 696 specificity-tie cases with no stated reason
    get pruned as redundant. So do the timing economies, the `visited` set, and
    the three counting units. A comment is the cheapest defence and the only one
    that survives a reader who was not here.
22ad. **A table that re-derives its own answers is not a fixture.** It is the
    implementation wearing a fixture's clothes, and it passes against any port
    that shares the derivation. Store expected values per case.
22ae. **A caveat attached to a result does not protect the result.** The number
    travels and the qualifier does not.
    **The operational form, from `reviewer-profiler`: the test is not whether the
    caveat is present, it is whether the *shortest quotable unit* is true on its
    own.** A row is quotable. A table header is quotable. A paragraph two lines
    below the table is not — and that is exactly where the conditions that matter
    most end up, because there they feel like context rather than content.
    *Earned:* they applied it to their own plan and found four failures. The
    clearest was an age-pairing result stated as "both routes pass it today and
    agree exactly", with the two-of-seven coverage limit sitting three lines
    below under its own heading. The sentence was **true**, would have been quoted
    as a seven-pairing result, and anyone lifting it would have been reading the
    document correctly.
22af. **An enumeration must cover the conditions as well as the inputs.** A
    condition can render an input inert, and the row then reads as a *clear*
    rather than as untested.
    *Earned:* the ambient-input sweep under a pty found three gaps. Under a pipe
    it found a different set. **Five real gaps in total**, and the two sweeps see
    disjoint subsets — colour-depth inputs cannot show under a pipe because
    colour is already off, and tty-negotiation inputs cannot show under a pty
    because colour is already forced. **Neither sweep alone could have found more
    than three of five, however carefully it was run.**
    *Supersedes the "7 gaps" figure in 22d:* source reading proposed seven, one
    condition measured three, both conditions confirm **five**. `LINES` and
    `TTY_INTERACTIVE` are genuinely inert under either condition and are not gaps.
    The five are `COLORTERM`, `NO_COLOR`, `TERM=dumb`, `FORCE_COLOR` and
    `TTY_COMPATIBLE` — one seam, the native route not consulting terminal
    capability when it renders.
22ag. **Three distinct questions about a recorded oracle, and all three are
    needed.**
    - The **stamp** answers *was this generated against the current oracle*.
    - **Re-verification** answers *does it still describe that oracle* — a stamp
      can be re-blessed by hand, and a table generated against the right revision
      can still have been generated wrongly.
    - **Re-derivation** answers *was the measurement reproducible at all*.
    *Earned on the third:* `search-runtime`'s grammar oracle contained recorded
    stderr embedding the capture run's temporary `HOME` path — bytes that could
    never reproduce, because every run gets a new temp directory. **A correct
    digest would have passed**, because the route had not moved. Only re-deriving
    the table found it, and they very nearly filed it as a route change.
    *Fix:* capture twice and diff to prove determinism, then stamp. Normalising
    the path repairs the instance; the double capture repairs the class.
22ah. **A restamp alone upgrades "unknown" to "verified".** An artifact whose old
    stamp was blind to a class of change cannot support the claim that no such
    change happened *before* the restamp — which is precisely what the new stamp
    silently asserts.
    **So: re-derive first where possible. Where impossible, the honest stamp
    records the pre-restamp window as unverified** rather than implying it was
    checked.
22ai. **A stamp that does not apply dilutes the ones that do.** Two artifacts
    carrying claims about commits, documents and teammates' tooling — not about
    oracle behaviour — were stamped for uniformity, implying a dependency they do
    not have and dating them for nothing. They now say `NOT ORACLE-DEPENDENT`
    explicitly, **including that an earlier version implied otherwise**.
22aj. **Five build configurations, not three.** Supersedes the count in standing
    constraint 4. `cargo check`, `cargo check --no-default-features`, `cargo test
    --no-run`, the release build under `--no-default-features`, and **`cargo test
    --doc`** — which is the only one that compiles doctests.
    *Earned:* three broken doctests sat in the tree unnoticed because every other
    configuration passed over them. Same shape as the `--no-default-features`
    finding: **a configuration nothing routinely exercises accumulates defects
    precisely because nothing exercises it.** Two instances now, and both were
    found by someone tripping over them rather than by looking.
22ak. **Re-posing a question buys free durability only when the re-posed question
    is the same question.** It can buy durability by asking *less*.
    *The distinction:* a pty differential asks "do both routes render
    identically". A self-comparison at two widths asks "does the renderer read the
    terminal at all" — durable, and strictly weaker. Keep both; the cheap one is
    not a replacement.
    **The test, from `context-curator`: ask what answer the re-posed question
    gives if the new subject is wrong. If the answer is still "pass", the question
    got weaker.** Checkable per instrument without knowing what it measures.
    *Their own NFC probe failed it.* It asks whether an implementation diverges on
    normalization form. Against the oracle, yes. **After cutover the native route
    must diverge too, in order to preserve behaviour** — so re-pointed, the probe
    passes a route that diverges by nine visible characters or by ninety. It
    survives perfectly and means nothing, and nothing in its shape signals that.
    *Narrows the "cheaper to re-pose than to freeze" line in the E section.*
22al. **A recorded disagreement must store both sides.** If a finding says X
    differs from Y and only Y is on disk, the finding dies the moment X becomes
    unavailable.
    Generalises past cutover to any comparison against something transient — a
    live corpus that grows, a render that depends on wall-clock time, a path
    specific to one machine. In each case the finding survives and the evidence
    does not.
    *This is the age-colour fixture rot seen from the other end.* There the stored
    side was frozen and the live side moved, so the comparison failed for the
    wrong reason. Here the stored side is frozen and the live side is about to
    vanish, so the comparison stops being checkable at all. **Both are one-sided
    records of a two-sided claim.**
    *And it pairs with 22ak rather than duplicating it.* 22ak asks whether a
    re-posed question is still the same question; this asks whether the evidence
    for an already-recorded finding will still exist. An instrument can pass the
    first while a document fails the second — which is what happened with
    `reproduce_branch_corpus`, sound only because a document-level freeze had
    already happened for an unrelated reason.
22am. **A test can defend a decision rather than a behaviour.**
    `search-runtime` landed a test asserting that `argparse_columns` and
    `python_int` **disagree** on `+96` and `' 96'`, so anyone who later unifies the
    two width resolvers gets a failure that explains itself.
    Most tests defend a behaviour. This one defends a decision against the
    specific tempting simplification that would undo it. This team has spent the
    mission catching "helpful unifications" by hand; that test makes one of them
    catch itself.
22an. **An enumeration is bounded by its categories as well as its conditions,
    and the categories are invisible from inside.** Extends 22af, which covered
    conditions only.
    A **sixth** ambient input exists: `UNICODE_VERSION`, which selects Rich's
    cell-width table and therefore decides how wide a character *is* — so it
    decides where every line elides and how much padding a panel body gets. The
    ambient sweep missed it because that sweep was organised around two
    categories, colour inputs and width resolvers, and this is **neither**. It
    was found by porting `rich.cells`, not by sweeping for it.
    Measured: the same headline at the same console width renders **31
    characters unset and 20 under `UNICODE_VERSION=9.0.0`**; 2,350 codepoints
    differ in width between Unicode 9.0.0 and 17.0.0. Reproduced rather than
    diverged — the charter preserves wherever legacy produces a usable answer,
    and an older table produces one.
22ao. **A third class, beside preserve-because-wrong and timing-shaped:
    observably neither.** A line with no consequence at any input.
    `max(8, width - 2)` against `max(8, width)` for the headline budget produces
    identical bytes at **every width from 2 to 129 over seven headline shapes**,
    because the outer cell clip subsumes the inner elision — tail elision only
    shortens, and both budgets sit at or above `width - 2`.
    **The danger is not that someone changes it. It is that someone spends an
    afternoon building a gate for it.** Recording *why* there is nothing to gate
    is worth more than the line. Keep it, because Python has it and simplifying
    is pointless, and pin the non-observability so the test fires if the outer
    clip ever makes the budget load-bearing — a test guarding the *reason* there
    is no behaviour.
22ap. **Counterweight to 22aa: neither is every null result a limit of your
    instruments.** Three successive explanations of "my corpus is too thin" were
    wrong; the fourth measurement showed the corpus was fine and the world was
    flat there.
    Without both halves the rule becomes a different bias with better manners.
    This is the **second** correction today to the "suspect your instrument
    first" prior — the first was a surviving mutation that meant the *code* was
    wrong rather than the test weak, and holding that prior would have shipped
    inert code behind seven green tests.
22aq. **A single-case discrimination is luck with a witness, not coverage.** One
    row of 1,499 distinguished a particular wrong implementation — enough to
    fail, and one row deep. Pin such a case separately so the guard does not
    depend on the oracle's coverage there. A single-row discrimination quietly
    becomes zero.
22ar. **Measure the cost before arguing the scope.** Deciding whether to
    reproduce an expensive-looking legacy behaviour: 21 Unicode versions, 20
    distinct tables, 7,045 ranges came to **163 KB generated**, against a 1.7 MB
    table the tree already carries for `\N{...}` names. The expensive-looking
    option was the cheap one, and the two questions are usually asked in the
    wrong order.
22as. **An outcome that matches at every sampled point is not evidence that the
    mechanism matches.** Distinct from every other rule here: those are about
    gates that cannot fail, corpora blind to a shape, or enumerations bounded by
    their categories. This is a **correct result obtained from a wrong model**,
    and it is invisible to any amount of sampling — because the sampling is the
    thing that agrees.
    *Earned:* a hand-rolled panel frame agreed with Rich at four widths. Rich has
    no fits-or-truncates branch at all; it assembles the whole strip between the
    corners and clips *that* in one pass, so a title of exactly `width - 5`
    overflows. Two implementations, four agreeing samples, incompatible models.
    An 11,200-line corpus found the boundary.
    **Two tells.** Agreement across a small sample. And a rewrite that **removes**
    a branch rather than adding one — the single-pass version is usually the real
    one, so if your port needs a decision the oracle does not appear to make, you
    have probably not found the oracle's actual shape yet.
22z. **The first mate compresses findings and the compression drops
    qualifiers.** Three instances today, same shape:
    - "Python does not flush **at this site**" → relayed as a general rule.
    - "Five files **in `src/` and `rust/`**" → relayed as the whole
      reconciliation surface, understating it fivefold while three owners sized
      on it.
    - "cost-**unmeasured**" → relayed as "unmeasur**able**", which filed four
      timing economies as reading-only. Three of them turned out to leave a
      timing signature, and one of those is a real defect.
    **Therefore: findings reach owners from the person who made them.** The first
    mate routes and rules; it does not paraphrase evidence. Where a relay is
    unavoidable, quote rather than summarise.
22y. **A claim confirmed only by reading is a lead, not a result.** Source
    reading tells you which inputs a route *reads*. It does not tell you which
    ones change *this* output. An ambient-input enumeration built by reading gave
    seven gaps; measured, three were real and four were inputs Rich genuinely
    consults that do not move the search render.
    **Enforced at the point of use, not by audit:** when an owner builds on a map
    claim, they confirm it by execution or flag it as unconfirmed, and G3 checks
    which stage a claim reached. A sweep would find only the claims already
    marked, and the unmarked ones are the exposure — the same reason the oracle
    grep found only the compliant.
    *Applies to this desk's own maps.* They were written against a tree that has
    moved several times; the engine handoff's blocked table was stale within the
    hour.

### G3 review split — three evidence types, not two

| Reviewer | Evidence type |
| --- | --- |
| `reviewer-profiler` | **Measurement.** Memory and timing gates, colour, width, ambient inputs, the slope prediction when `session` lands. |
| `context-curator` | **Corpus sweep.** Content fuzz, NFC/NFD, provider decode against real transcripts, preserve-because-wrong. |
| `context-curator` | **Structural review of the diff.** Reading the change and checking a property survived. |

The third type was nearly orphaned. A measurement-versus-corpus split leaves it
unclaimed — and **all four timing economies fall there and nowhere else**, since
they are byte-invisible and cost-unmeasured by design. The only possible review
is reading whether the economy survived the port. Each slice is named explicitly
by whoever takes it, so nothing is doubly assumed.

22x. **A gate should print what it covered, not only whether it passed.**
    Twice the *number* carried the diagnosis where the verdict did not. A
    differential printing "6 fixtures" where 7 were expected caught an insertion
    script that had matched a nonexistent anchor and reported success anyway. And
    "251 of 251 moved" told its author the harness was broken where "3 of 251"
    would have told them the product was.
    A gate reporting only pass/fail hides its own scope — the property that lets
    it silently cover less than it claims.
    *Corollary:* a script that reports success without checking its own effect is
    the same defect as a gate that cannot fail. Assert the anchor; assert the
    result is present in the file you wrote.
22n. **For anything with a parser in it, intuition about the expected value is
    not evidence.** `session-core` wrote two hand-typed expectations wrong in one
    hour, both caught by running the oracle rather than by review, and in both
    cases the generated differential was right throughout. Generate expectations;
    do not write them.
22o. **Code that suggests something false about itself is a defect with no
    instrument.** The short-modifier lookahead's shape suggests it accepts a
    joined value; it exists only to name that value in an error message. The
    flush comment read as a general rule while all three call sites were
    correct — and that comment is the vector by which an over-general claim
    reached three teammates through the first mate. Nothing we have detects this
    class.
22k. **A fixture must be asymmetric in the dimension it is checking.**
    `truncate_middle("xxxxxx", 10) == "xxx\n...\nxx"` is uniform, so head and
    tail are indistinguishable and swapping them still passes. The sample's own
    symmetry hides the property under test — a gate that cannot fail, one level
    down. Found when a hand-typed doctest expectation put the first two
    characters where the last two belong, and the generated 308-case differential
    caught what the unit test could not.
22l. **A discovery command that finds only the compliant reports clean forever.**
    `rg oracle_tree_state` answers "which stamps might be stale". The live
    question is "which characterizations have no stamp", and the artifacts at
    risk are invisible to that grep. Coverage was **5 of 19**, all five belonging
    to the rule's author, while the sweep reported clean. The real sweep cannot
    be a grep, because it needs judgment about what counts as a
    characterization.
22m. **A stale figure is worse than a stale stamp.** A stale stamp says "this may
    be out of date". A stale figure says something false with confidence. The
    reconciliation surface was corrected from "five files, 185 insertions" to 26
    files and 913 insertions in a message and in a later artifact — but not in
    the two documents owners were most likely to read it from, where it survived
    for hours. **A correction that lives only in a message thread has not been
    made.**
22j. **A gate that reimplements the thing it grades is grading itself.**
    `query-semantics`'s `predicates.rs` had copied the engine's `\w` predicate
    into itself, so it compared a transcription against CPython rather than the
    artifact. A mutation rewriting the real predicate moved it by **zero** — it
    could never have failed. Rewired through the live engine, the same mutation
    moves it by 136,710. **It had produced the correct number, 6,167**: right,
    quotable, and inert. Nothing was visibly wrong.
    *Pairs with 22f.* A copied **tool** goes stale and grades less than it
    claims. A copied **implementation inside a gate** goes inert and grades
    nothing. The second never reports a problem, so it is worse.
    *Technique:* name each mutation for the hazard it stands for. The mutation
    set **is** the harness's parameterization, so an unnamed mutation set is an
    unexamined assumption.
22i. **Exhaustive is always exhaustive over a parameterization, and the
    parameterization is the assumption.** The capstone rule; every other
    constraint here is an instance of it.
    *Earned:* `session-core` built a colour oracle on two principles that both
    sounded complete — every colour the product emits, and every value in each
    channel — and it was blind to one of three hazards, because a nearest-match
    argmin is stressed by neither. The float-versus-integer distance disagrees
    with Rich 56 times in 636,056 triples, about one in eleven thousand, and when
    it disagrees it picks an **entirely different** colour rather than an
    adjacent one. Rare enough to survive any sampling, loud enough to be
    unmissable in the wild.
    **Therefore: every gate guarding a ported algorithm ships with an automated
    falsification** — a deliberately wrong implementation, run as part of the
    gate, failing the build if the gate ever stops catching it. Not a check
    performed once. Scope: the colour downgrade, the query engine, the candidate
    gates, and the width and colour-system resolution.
    *The technique:* a parameterization chosen from the problem finds what the
    problem suggests. One chosen from the **failure mode** finds what you would
    otherwise miss.
23b. **Enumerate when the domain is enumerable.** A suspicion a 4,000-pattern
    corpus could not settle was closed by sweeping all 1,114,112 codepoints:
    defect 10 found at 6,167 codepoints, and the `tolower` question closed
    permanently rather than left as a residual worry.
24. **Silence from a test is not evidence when the test cannot express the case.**
    `query-semantics` stated it as "a generator only finds what its grammar can
    express", and applied it against their own result: 4,000 generated patterns
    showed no divergence in `tolower` multi-scalar truncation or in the `\w`
    predicate, but the corpus was not built to stress either. Both get measured
    before they are carried across.

23. **A clock injection point is approved.** Read once at startup, one source, no
    branching, no fallback, the same mechanism on both binaries. It does not
    change behavior when unset.
    *Why:* age comes from wall-clock `now` on both sides, so the corpus can never
    freeze the clock and the age fixtures rot on a timer. Normalizing the age
    label was a half-fix that hid the problem. This is the same class of decision
    as standing constraint 1, the `$HOME` override: an ambient input made
    explicit so a differential harness can function. Age appears in every list
    row and every panel title, so refusing it would make a large share of output
    unprovable. `age_style` therefore stays under test at all four buckets.

## Deliberate divergences from legacy

**The line.** Preserve legacy behavior, including behavior we think is poor,
whenever legacy produces a usable answer. Diverge only where legacy fails to
produce an answer at all. A hang and a crash cost the user the result.
Verbosity does not.

Every item here goes in `final-change-log.md`.

| Divergence | Reason |
| --- | --- |
| Catastrophic patterns fail loud instead of hanging | Measured: `ch search '(a+)+b'` against 40 consecutive `a` characters does not terminate in CPython within 10 seconds. No timeout, no warning, no interrupt short of killing the process. The guard is a **repair**, not a regression. No golden fixture can own this case, because the oracle produces no answer to record. |
| `COLUMNS="²"` renders instead of crashing | It passes Rich's `isdigit()` and then raises in `int()`. Reproducing a crash on an input where the crash is the bug serves nobody. |
| `isdigit()`-then-`int()` inputs are rejected rather than crashing | Python's `str.isdigit()` accepts digits with no decimal value, so `"²"` passes the guard and raises an uncaught `ValueError` in `int()`. Three independent sightings — Rich's width detection, shortening spec parsing, and `src/chats/cli.py:73` and `:78`, which are unguarded and reachable. One class, not three entries. The native route accepts Unicode decimal digits (`"５００"` → 500) and rejects the rest cleanly. |
| Warning text keeps its category, drops the source location | A Python warning's `file:line` names a location in the interpreter's source that does not exist in a native binary. Any value is invented. The branch invented one from `CARGO_MANIFEST_DIR`, naming a Python file it deletes — the fabricated-provenance anti-pattern this project already removed once. |
| Colored highlighting is corpus-bounded | Provable parity needs Rich and Pygments, which needs Python, which fails the charter. Stated plainly rather than discovered later. |
| ~~A fence in a known-but-unported or unknown language renders with complete geometry and plain unstyled code~~ **⚠ RETRACTED 2026-08-30 — see L239. Plain rendering is correct ONLY where legacy also rendered plain because the tag was genuinely unrecognised.** *Original text follows for its reasoning:* **Captain's ruling, 2026-08-30.** Pygments ships 500+ lexers; six are ported. **The alternative is a route that truncates and exits 101 on about one interactive coloured search in three.** Measured residue after all planned families: **2.56% of all fences, 3.11% of tagged**, top items SQL, CSS, XML, JSX, HTML, YAML — **and block exposure is a property of whose sessions, so the honest figure is a range of 2.6%–11%.** Geometry, background and padding are byte-identical; only token colours are absent. **Long-tail lexer coverage is explicitly not expanded in this cutover.** |
| `display_session_id` reads entries already decoded during confirmation; Python's `get_display_session_id` reopens the file | Both extraction rules agree — first parseable line, `session_meta`/`session` type, non-empty string id, else the stem. The native form is more consistent and does one fewer read. **Observable only if the file is rewritten between confirmation and rendering, which a live pool can do.** Added 2026-08-29 from G3; it had been documented in code and nowhere a change log is assembled from. |

## Preserved because they are wrong

The most dangerous class on this mission: a native implementation looks correct,
diverges, and no reviewer objects because the output looks *better*. Full list in
[`preserve-because-wrong.md`](preserve-because-wrong.md), all confirmed by
running the oracle at `8cb4c5f`.

Every fixture pinning these **carries a comment saying the expectation is wrong
on purpose.** Without it the next reader helpfully repairs the fixture and we
ship the divergence through our own contract.

1. **The age label and the age colour disagree by one bucket.** `humanize_age`
   and `age_style` carry separate, unaligned thresholds: `3d` is painted with the
   *week* colour, `2w` gets *month*, `1mo` gets *old*. Driving both from one
   table — the obvious simplification — repaints every coloured result row.
   **Highest risk on the mission**, because `contract-owner`'s comparator
   normalizes the age SGR away, so this is the one dimension where a regression
   fires no gate. Pinned at unit level immediately rather than waiting for the
   clock seam. `humanize_age` also uses 30-day months and 365-day years, so
   360–365 days renders `12mo` before jumping to `1y`.
2. **`collapse_home` matches a string prefix, not a path boundary.**
   `/Users/giladbarneaX/dev/chats` renders `~X/dev/chats`. Reaches the list row
   and the panel title.
3. **`elide_to_width` counts code points**, so wide text overflows its budget:
   `你好你好你好你好` at a budget of 8 comes back unchanged, at 16 columns.
4. **`truncate_middle` counts code points**, so shortening is
   normalization-sensitive: 400 characters survive as NFC, come back as 253 as
   NFD.
5. **Title elision counts code points**, so NFD truncates about nine visible
   characters early against NFC at the same width.
6. **A bool `color=true` resolves colour OFF and metadata colour ON.** Python
   compares `color` against the strings `"always"` and `"auto"`, and a bool
   matches neither — while `metadata_color = color != "never"` is true. There is
   a test named for it.
7. **An empty tool filter list is falsy, so it does not mean "all".**
   `ToolVisibility::Filters(vec![])` reproduces Python's empty-list semantics.
8. **`s=p:128`, `s=8:p` and `s=8:` all raise.** The short-modifier lookahead
   joins the next token and the spec parser then rejects the colon form. The
   lookahead exists to name the whole value **in the error message**, not to
   accept it — which is not what its shape suggests. The valid spelling is
   `s=p=128`.

**Scope is wider than titles.** `elide_to_width` has four call sites in
`commands/search.py` across both views plus `formatting.py:152`.
`truncate_middle` reaches `model.py` directly and `shorten_data` at six more
sites, so it surfaces in every `--short` mode. **The codebase already counts in
three different units** — code points here, UTF-16 code units in Pi
`responsePreview` truncation. Any port that unifies them changes behaviour.

## Right behaviours whose absence looks identical

The mirror of the class above, and invisible to the same instruments for the
opposite reason. A byte oracle cannot see a *timing* property: the output is
identical, the order is identical, the exit code is identical, and the product is
seconds slower.

1. **`commands/search.py:350` flushes every streamed session ID individually.**
   Not incidental — it is the entire deliverable of a measured scope from
   2026-08-20. The first ID of `ch search 'CLIENT_ID/CARD' -ca 2m -ll | cat` went
   from **15.995 s to 0.38 s**, completion time unchanged. The whole gain was
   Python block-buffering three short lines into a pipe. A native engine that
   buffers them regresses the product's most visible latency by 15.6 seconds and
   passes every byte gate we have.
   *Covered by:* a commissioned timing assertion — time to first ID through a
   real pipe — which is the only shape of test that can fail on it.

**Related correction.** "Python does not flush stdout" is **not** a general rule.
`search.py:350` and `console.py:64–73` both flush. It is true only at the pager's
missing-`less` fallback, where the native port correctly matches it. The first
mate relayed the general form twice; do not let it into a fixture.

`context-curator` is sweeping for other timing-shaped behaviours, biased toward
ones some earlier effort deliberately introduced — those leave a measurement
behind, which is what makes them findable.

**Preserved deliberately, though poor.** `-ma notadate` keeps printing one error
per candidate file and exiting 1. It works. Changing it is a product improvement
outside this mission, and smuggling an improvement into a parity rewrite is the
failure this team spent the day guarding against. It goes to the captain as a
separate proposal.

24. **Trust the harness's context figure over your own accounting.** An agent
    cannot see its own token count directly and self-estimates have been wrong in
    both directions today — `session-core` over-reported by 10–15 points,
    `reviewer-profiler` under-reported by a similar margin against their
    harness. Report the harness number, flag the discrepancy, and do not talk
    yourself out of it on the strength of your own count.
    ~~*Open:* whether the harness reports the context window or a session token
    budget.~~ **✅ ANSWERED 2026-08-28, and it explains a day of confusion.**
    Some harnesses report a **session token budget** — named `total_tokens left`,
    starting at 15,000,000 — which is **not** a context-window percentage. Herdr
    reports something else. So teammates have been reporting **two different
    quantities under one word** all day, and discrepancies attributed to poor
    self-estimation were partly this.
    **Report which quantity you are naming**, as `engine-and-codex` did: "14.81M
    left, about 1.3% used — a session budget, not a window."
    The rest of the constraint stands: still report the harness figure rather
    than your own count.

## Standing constraints

These bind every implementer and enter the task DAG at G2.

1. **Session roots stay `$HOME`-derived and `$HOME`-overridable.** No absolute
   path, no compiled-in default, no cache outside `$HOME`. The fixed-corpus
   performance gate is unmeasurable otherwise.
2. **Any suite that measures a build artifact copies it to a private path
   first.** The shared checkout guarantees someone else is rebuilding it. Under
   `--dist=loadfile`, `test_parse_command_contract.py` unlinks and rebuilds the
   very binary the search contract cases measure, on a different worker. That was
   the cause of a full afternoon of apparent nondeterminism: a different failing
   set every run, no standalone reproduction, none outside pytest.
   **This applies to every suite that measures the binary**, not only the
   contract suite — the shell suite and the performance gates too. It is not a
   convenience: any teammate who needs the installed binary to reflect their own
   change must rebuild it, so without private copies, individual verification and
   trustworthy suite runs are mutually exclusive.
   *Interim, until it lands everywhere:* `target/release/` is contended, so
   announce before rebuilding — **and a run records the binary identity at start
   and at end, with any change voiding the run.** Announcement lowers the odds; it
   does not make a completed run checkable after the fact.
   *Note:* this is the second cross-teammate collision produced by the
   one-checkout decision, after `tests/lib.sh`. Serialization is a workaround;
   a private copy removes the class.
3. **Bracket the whole route, not the launcher.** A private copy of `ch` is
   genuinely private; a private copy of the *Python* route is not. That route is
   a launcher, a sibling `ch-legacy` script, an interpreter, and a site-packages
   tree. Copying the first two leaves the rest shared and mutable. During a
   concurrent reinstall, a private `ch-python` failed instantly and the memory
   row recorded **Python at +0 MB and printed PASS** — a clean pass from a route
   that never ran. Binary-identity bracketing said "unchanged" and was telling
   the truth about the wrong object.
4. **Three configurations, not two.** A slice is landed only when the release
   build passes under `--no-default-features` **and** the test target is green.
   `cargo check --no-default-features` green implies neither — check skips test
   targets entirely, so a lib and binary can be green while `cargo test` is red.
   Nobody installs into `~/.local/bin/ch` from a tree that has not passed the
   release build. That is the configuration `pyproject.toml` uses for
   the binary, and the one no editor, `cargo check`, or local test run
   exercises. `uv tool install --force` deletes the existing install *before*
   building the replacement, so a failing build leaves no binary at all — which
   happened, for a few minutes, to the launcher two teammates were measuring
   against.
   *Corollary:* a tree red under `--no-default-features` blocks every install
   for everyone. Anyone editing Rust keeps it green or announces it is knowingly
   red.
   **⚠ The count is superseded by 22aj: five configurations, not three.**
   `cargo test --doc` is the only one that compiles doctests, and three broken
   ones sat in the tree while every other configuration passed.
5. **An oracle event triggers a re-blessing sweep across every artifact carrying
   an oracle stamp**, not only the corpora obviously affected. `rg
   oracle_tree_state` over the desk gives the list — currently nineteen files.
   *Why:* the clock seam was the first oracle event, and it caught the rule's own
   author. Every one of `context-curator`'s eight findings still claimed
   `src/chats clean at 8cb4c5f`. Three are reached through the file that changed.
   All eight re-verified and all eight hold — but the belief that carried them,
   "they live in files nobody touched", was true and still not a proof. **The
   artifacts that quietly rot are the ones whose authors were confident they were
   unaffected.**
   *Current state:* HEAD `8cb4c5f`, `src/chats/commands/search.py` modified,
   working-diff digest `a99c3302d0f852ba`. A digest, never "clean".
6. **The installed launcher is an exclusive resource.** Ask the first mate for
   the window, announce release.
6. **Shell-suite runs are serialized.** `tests/lib.sh` uses one fixed path,
   `${TMPDIR}/ch-shell-tests-${USER}`, and deletes it on start. Two concurrent
   runs corrupt each other and produce failures that look like real regressions.
   `reviewer-profiler` holds the token. `contract-owner` is asked whether
   parameterizing that path is cheap, which would dissolve this rule.
3. **The Python product on current `main` is the only oracle.** Not the branch,
   and not the branch's recorded expectations.
4. **A copy that compiles is not an extraction.** When lifting logic, delete the
   original in the same change, or prove the two byte-identical. The branch broke
   this and shipped a live fork: `python_extension.rs` trims on Python's
   four-byte JSON whitespace set while `inventory.rs` trims on Rust's full
   Unicode whitespace property. A JSONL line starting with U+00A0 therefore
   parses on one path and is rejected on the other, so one route returns a
   timestamp and the other falls back to filesystem mtime for the same file. The
   same extraction also replaced a streaming read with `read_to_string`, which
   discards the bounded-memory property it was built for. One real Pi session has
   a 3.75 MB final line that cost 773 ms, two thirds of a whole-pool scan.
   *Why a standing rule:* this fork passed `cargo` in both feature modes, a
   704-case suite, and an independent review. Every gate this team has would
   have missed it too.
5. **`re.IGNORECASE` is not `casefold()`.** Python's `re` uses single-codepoint
   `tolower` plus a fixes table. `ss` does not match `ß`. Today's Python search
   only avoids the divergence because of an `.isascii()` guard. A native
   implementation that drops the guard, or assumes `casefold` generalizes, moves
   search truth with no diff showing it.
6. **The branch's accepted-limitations list is a floor, not a census.** A seventh
   deviation exists that never reached its closure record: `\N{...}` resolves
   through a generated table with algorithmic CJK and Hangul names excluded,
   flagged at slice C and then absent from the final list.

## G2 — ownership map and task DAG

**Open as of 2026-08-28.** Both halves of the branch question are answered.
Production work may start on the tasks below, inside the named ownership only.

### File ownership

| Owner | Files |
| --- | --- |
| `session-core` | `rust/model.rs`, `rust/codecs.rs`, session rendering and provider modules, and the visibility, shortening, and tool-filter layer extracted from the branch's `session.rs` |
| `query-semantics` | `rust/search_query.rs` and its generated Unicode tables |
| `search-runtime` | `rust/main.rs`, `rust/lib.rs`, `rust/python_extension.rs`, `rust/terminal.rs`, `rust/clock.rs`, `rust/pager.rs`, the lifted inventory and scanner modules, the whole argument grammar (`rust/search/`), and the G4 cutover. **Views withdrawn — see below.** |
| `contract-owner` | `tests/` and all fixtures |
| `reviewer-profiler` | No production files. Gates, harnesses, and review. |
| `views-and-colour` | **Added 2026-08-28.** `rust/color.rs` and `rust/cells.rs` — both landed, gated and falsified — plus the views chrome and the five-input colour seam. |
| `engine-and-codex` | **Added 2026-08-28.** The engine's confirmation half (`gate` and `confirm` in `rust/search_engine.rs`, the output modes) and Codex decode in **its own module, `rust/codex.rs`**. |

Nobody lifts the branch's `session.rs` wholesale. Agent transcript merging stays
out of scope.

**`rust/session.rs` stays `session-core`'s.** Its Claude and Pi decoders are
landed and proved at 2,436 and 24,367 cases and are frozen. Codex decode goes in
`rust/codex.rs`; `session-core` adds the one-line dispatch arm, coordinated
directly.

### Live status — 2026-08-28

**The argument grammar is complete, both halves.** Parsing, formatting and
rendering. 87 lib tests, 1 bin test, 18 doctests, release build green in the
shipping configuration. Four permanent gates compare live against `ch-legacy`,
including one that proves the twelve-width help comparison is **not inert** by
showing a width-pinned formatter must disagree with argparse at every other
width.

**Routing is blocked on the engine, and deliberately so.** The cutover branch's
third arm calls the engine. A `search` branch handling only help and errors would
be the intermediate hybrid the charter forbids — production search half native
and half Python, with no single moment of cutover. Everything the route needs
from the grammar side is landed and proved, so the cutover is a short three-arm
function the moment the engine exists:

```
parse_search_arguments -> Help  : print render_help(argparse_columns()), exit 0
                          Error : eprint render_error(msg, argparse_columns()), exit 2
                          Run   : engine
```

**Standing commitment from `search-runtime`: the moment the engine lands, they
drop whatever they are doing and land the cutover.** It is short, proved on their
side, and the only thing in the mission with no second owner. Nothing takes
priority over it.

**⚠ "Short three-arm function" is superseded — see gate 4 above.** The `Run` arm
does not call a finished engine. `search_engine.rs` is the scheduler;
`stream_search` takes `scan_order`, `sink`, `batch_size`, `screen`, `probe` and
`confirm` as parameters and returns `Outcome`. There is no
`run(SearchArguments) -> ExitCode` anywhere in the crate. Six pieces are still
needed and only the machinery for three of them is landed. **Anyone planning
around "short function when the engine arrives" must read the six items in gate 4
first.** The commitment and the ownership stand; the timeline does not.

**Views and colour, `views-and-colour` — landed since.** `rust/color.rs`, gated
on all 1,499 oracle rows with hand-written falsifying mutations (naive rounding
fails 51 rows, float redmean fails 1). `rust/cells.rs`, Rich's cell measurement,
gated on **11,410 recorded measurements across four Unicode versions**, five
mutations caught including cropping by code points instead of cells at 1,082.
The list view is **byte-identical to Python across 43,680 rendered lines**, 13
widths from 4 to 120 and never 80. The conversation panel body waits on
`session-core`'s renderer; its frame is gateable separately.

**Newly discovered scope, not previously listed: `parse_raw_cli_transcript` is
not ported.** `SessionFormat::Raw` exists in `session.rs` with no parser behind
it. Nine files in the 5,039-file pool take that branch and **every one produces
zero messages, so the real corpus cannot grade it** — the same blindness
`session-core` measured for Pi, found in a second place by the same method. A
confirmation half that skips the format check surfaces 8 large sessions the
product hides. `engine-and-codex` is treating it as a small port rather than an
argument.

**A transient test failure, observed once and recorded as observed-once.**
`query-semantics` saw `cargo test --lib --no-default-features` report `123
passed; 1 failed` a single time, **could not reproduce it in 11 subsequent
runs**, and never captured the failing test's name. It passes now. Two
unconfirmed candidates: the suite touches the live session pool, which mutates
under measurement, and other sessions were building concurrently.
**Not called a defect on one observation** — recorded so a successor who sees it
knows it was observed before rather than assuming it is new, since a suite that
fails once in twelve is the shape that cost this team an hour earlier today. It
also qualifies every "all five configurations green" claim on this desk: those
were true when run and are not universally true.

### ⚠ Three unowned packages, no roster capacity

> **✅ SUPERSEDED 2026-08-28 — this table is now empty. Every remaining package
> has an owner.** The captain approved two seats. `views-and-colour` took views
> **and** the colour seam; `engine-and-codex` took the engine's confirmation half
> **and** Codex decode, as one seat because confirmation feeds on decode.
> The section below is kept as the record of the constraint and the reasoning
> that produced the two prompts — in particular the sizing correction, which is
> still binding on whoever holds views.

Escalated upward and **unanswered**.

| Package | Why unowned |
| --- | --- |
| **Codex decode** | `session-core` is at ~80%. Seam ruled: finish Pi, hand off Codex and the colour seam together. Codex has a named case waiting — ~~the three all-scaffolding sessions~~ **44 sessions, and the mechanism below is not what this said.** |
| **The colour seam** | Same handoff. Well specified: `session-core`'s 1,459-row oracle exists and is proved able to fail; five ambient inputs, one mechanism. |
| **Views** | **Withdrawn from `search-runtime` on their own recommendation.** Giving the largest remaining package to the person holding the irreplaceable small one inverted the priority — if they run out mid-views, the mission loses the cutover too, and loses it exactly when the engine lands. They are writing a views handoff instead, while they still have room to write it well. |

*A sizing correction that belongs with the views entry.* The chrome half is
independent of the colour **downgrade algorithm** but **not** of the colour
**decision** — every chrome surface emits truecolor SGR literals today, so each
must route through whatever `session-core` lands as the downgrade entry point.
That is a wiring dependency across the whole package rather than a single seam,
which is why "start it and stop" is the worst shape for this module.

**Both reviewers must stay independent.** Both have offered capacity; both were
declined. Verification cannot be done at the end by whoever has window left, and
cannot be done at all by someone who helped build the thing. `contract-owner` is
the only other free capacity and is the worst candidate — the cutover is the
moment their suite stops being a formality and starts being the gate.

### Task DAG

**A. Foundation. Runs in parallel. The oracle is established before anything is
measured against it.**

- A1 `contract-owner`: adopt the 173-case corpus, pin fixture times against a
  frozen clock rather than masking what moves, and replace the loader trace with
  the empty-directory proof.
- A2 `reviewer-profiler`: build the fixed-corpus performance gates that replace
  the two retired live-pool budgets.
- A3 `search-runtime`: `terminal_width()` only. Relocate it out of
  `rust/main.rs` into `rust/terminal.rs` so the library can see it, and repair
  the two divergent inputs.
  **Corrected 2026-08-28.** A3 first said "the four repairs". Three of the four
  have no target in the working tree, because the defective code lives in branch
  files that do not exist on `main`. Those three are now landing conditions on
  B1, not work performed after it: **the branch modules land already reconciled,
  so the defective forms never enter the tree at all.** B1's definition of done
  includes proving each is absent from what landed, rather than fixed after
  landing. The rejected alternative was to import first and repair second, which
  creates a window where the tree holds four known defects and a green build.

**The complete reconciliation surface, measured.** `main` and the branch forked
at `a7e89eb` on 2026-08-21. Since then `main` has exactly two commits touching
`src/` or `rust/`: `47b3db9` and `a51f32c`. **26 files, 913 insertions against
178 deletions**, of which 364 insertions are the `tests/` guards. Porting from
the branch means replaying those two commits onto it, or shipping five
regressions.
*Corrected: an earlier version of this line said "five files, 185 insertions",
which was the `src/` and `rust/` slice only. The omitted `tests/` half is the
part that keeps the fixes from regressing — replaying source hunks alone restores
the behaviours and none of their proofs. Three owners sized on the wrong figure
for a while.*

**The five landing conditions.** Each lands already reconciled. The defective
form never enters the tree.

| # | Defect on the branch | Owner |
| --- | --- | --- |
| T1 | Fabricated Python traceback at `main.rs:347`, built from `env!("CARGO_MANIFEST_DIR")` and citing three files that do not exist | `search-runtime` |
| T2 | `JsonEscapeValidator` at `scanner.rs:134` | `search-runtime` |
| T4 | `model.rs:298` returns `Ok(Some(value.clone()))`, no attribute guard, so `{"branch": ""}` renders `branch=""` where legacy renders nothing | `session-core` |
| — | `terminal_width()` as `COLUMNS`-or-80 | `search-runtime` (A3, done) |
| — | Tool key argument elided at a hard-coded 44 columns | `session-core` |

**B. Port. Starts after A1. The three owners run in parallel, each in its own
files.**

- B1 `search-runtime`: reconcile inventory and scanner onto `main`, with one
  shared line-walk primitive whose trim lives in the handler, not the walk.
  Discard `validate_chunk_encoding`. Take `risk_character_pattern()` on its
  merits.
- B2 `session-core`: rebase `model.rs` and `codecs.rs` onto `main`, extract the
  visibility and shortening layer, and repair the inner-tag escaping defect once
  in the shared renderer.
- B3 `query-semantics`: rebase the query engine onto `main` and close the nine
  defects, cost model first.

**B4 `context-curator`: the content generator.** Reading cannot reach provider
decoding, visibility, shortening, or the renderer's tokenizers. Generated
*session content*, driven through both routes and compared, is the missing half.
`query-semantics` has a pattern generator, `contract-owner` owns the live
differential, `reviewer-profiler` owns the corpus. This is the gap. It varies
width as a generated dimension and runs under a pty. Fixtures land with
`contract-owner`.

**Memory gate: parity, not boundedness.** The native large-arm delta must not
exceed `main`'s. Measured on a 64 MB amplified final message, peak RSS:

| Arm | Reference native | `main` Python |
| --- | --- | --- |
| Pi, small → large | 20 → 596 MB (+576) | 82 → 530 MB (+448) |
| Claude, small → large | 10 → 10 MB (+0) | 54 → 54 MB (+0) |

The gate compares the two deltas in the same window rather than a stored
constant, so it is self-calibrating and never needs re-baselining — the failure
mode that retired the two live-pool budgets. The 5% tolerance is measured: across
three runs the native delta spread 0.3 MB against Python's 11 MB, about 2.4%.
The reference branch **fails it today at 1.29×**.

**RESOLVED — the mechanism is two copies, not a percentage.** Profiled across
five payload arms from 8 MB to 96 MB:

    subject    peak = 9.00 × payload + 21 MB fixed
    reference  peak = 7.01 × payload + 82 MB fixed

**The native route holds two additional resident copies of the payload.** The
1.29× was an artefact of reading two lines at one payload size — it is what a
difference of +1.98 in slope happens to equal at 64 MB, and nothing in particular
anywhere else.

*The fit validates itself:* it predicts the lines cross at 30.5 MB, and the
measurements show them level at 32 MB — 308 against 307. A prediction made by the
model and then observed independently.

*A shape nobody had named:* the native route **wins** on small sessions, because
its fixed cost is 21 MB against 82. The gate only ever sees the losing half, so a
red row there does not mean the native route is uniformly heavier. This belongs
in the change log.

*Which two copies is deliberately unattributed.* `search-runtime` established
from source it is not `read_to_string` and not a double read; `reviewer-profiler`
stopped at the slope rather than guessing at serde buffers. Two refusals to
speculate are why the question is clean for whoever opens that code.

**Standing measurement principle from it: a single ratio cannot distinguish a
proportional cost from a fixed offset plus a slope, and the cure is the same
either way — vary the input rather than measure harder at one point.** No amount
of reasoning gets from the percentage to the mechanism, because the percentage
does not contain it.

*The same move answered a second, unrelated question.* Applied to the timing
ratios: they climb off the smallest corpus and flatten from about 174 files
upward, so the gate corpus at 695 sits well inside the plateau and the ratios
**are** properties of the implementation rather than points on a curve. Below
roughly 200 files the ratio *understates* the work, because Python's interpreter
startup is a fixed cost the native route does not pay and it dominates a small
scan. **Change-log wording: "native is 0.145× Python for corpora of this order
and larger."** Without the qualifier, someone runs it on 50 files and concludes
the number is wrong.

*A principle that answers two unrelated questions with the same move is a
principle. One that answers only the question it came from is a description.*

**Corrected twice, and the second correction matters.** A third arm falsified
"Pi sessions are expensive". Strip the `"pi-user-agents"` marker from the same Pi
session and it becomes exactly as cheap as a Claude one: +576 MB native with the
marker, −1 MB without. The true statement is that **agent-bearing sessions defer
to confirmation.**

And this is **not a defect**. It is the price of a correctness deferral. Joined
agent records synthesize visible text absent from the raw bytes, so the gate must
defer or produce false negatives, and two existing tests pin that. The first mate
recorded a bounded version of this gate as "a product improvement for the captain
to consider". That was wrong. Narrowing the evidence group to save memory would
buy a silent-loss bug. The number is recorded with its cause and its
justification, not proposed as a fix.

The residual 1.29× — the Rust side holding 29% more than Python through the same
confirmation — is unexplained from source and awaits an allocation profile. It is
its own task, not part of B1.

**C. Integration.** `search-runtime` wires the engine and views.
`terminal_width()` moves out of `rust/main.rs`. The colored slice runs under a
pty at two or more widths, neither of them 80.

**D. Cutover.** One `search` branch added to the routing in `rust/main.rs`. No
Python is edited. Reverting is deleting the branch.

**E. Deletion, and only after the byte harness is green.**

**Prerequisite, wider than first ruled: before the oracle is deleted, every
instrument that consults it must have its last consultation stored.** An
instrument not converted by then has silently become a script that cannot run.
I first ruled this as "freeze the fuzz-discovered cases into fixtures" — one
corpus, when it is a property of the whole instrument set.

`reviewer-profiler` audited their eleven: **five die unless converted, two
partly.** Ratio gates become absolute budgets from frozen Python medians; width,
ambient and colour-tier gates freeze Python's bytes as fixtures; the memory
comparison freezes `7.01x + 82` as a constant. `ratio_scaling` **retires** rather
than converting — it exists to prove the ratio gates are properties, and once
they are absolutes the question is moot. An instrument that has answered its
question should be retired, not preserved.

`contract-owner`'s live differential has the same property: it compares `ch
search` against `ch-legacy search`, so the class stops being runnable — **not
broken, over.** Two consequences for whoever runs this slice: do not let it land
while the differential is the only thing that has verified a recent change, and
expect the class's removal to be part of the slice rather than read as a
regression. *That reads as a broken suite six weeks later if nobody wrote down
that it was supposed to expire.*

**The design lesson, from the two instruments that survive by accident.** One
compares a binary against *itself* — closed against full, first byte against
total. One asserts a *stored rule* rather than another route. Neither was
designed for durability; both got it from the shape of the question. **An
instrument that compares against a stored rule, or against itself, is durable by
construction. One that compares against a live peer is not.** Cheaper to re-pose
the question than to freeze the comparison — **but see 22ak: re-posing is free
durability only when the re-posed question is the *same* question.** It can buy
durability by asking less, and a weakened instrument survives perfectly while
meaning nothing.

**The ordering:** the live differential is the proof that the cutover preserved
behaviour; the byte lock is the proof that survives it.

## Dilemma record

Judgment calls taken because no peer scope could resolve them.

### D1 — A finished native `ch search` already exists, unmerged

**The dilemma.** `context-curator` found branch
`wip/cycle-02-native-default-pause-20260821` at commit `0ffde41`, dated
2026-08-25. The first mate verified it: 16 files under `rust/`, the Python search
authority deleted, and a 704-case byte-oracle fixture corpus. Its records claim a
green full suite, zero-Python loader traces, and eight passing performance gates.
Its commit history shows slices A through G, a closure review, a repair round,
and captain-level gate rulings. That was a managed campaign. `memo recall` finds
no record of it anywhere in project memory. So it is unclear whether the branch
was rejected on purpose or simply left behind. The curator recommended asking the
captain. Decision 7 had just closed that route.

**Chosen path.** Neither adopt nor ignore. Buy the choice with one cheap
measurement. `reviewer-profiler` runs a time-boxed reproduction in a separate
worktree, never in the shared checkout. Meanwhile the branch is prior art and the
Python product on `main` stays the only oracle. `contract-owner` mines the 704
command shapes now and re-derives every expectation from Python.

**Rejected alternatives.** Building from scratch was rejected: it re-implements
about 17,500 verified lines and contradicts the charter's own rule against
re-implementation. Adopting the branch on its recorded evidence was rejected:
nobody has re-run it, `main` has moved past it, and its scope is wider than this
charter.

**Why.** Every outcome of the measurement leaves the team better placed than an
argument would. A fast negative is a complete success.

**Correction on the record.** The first mate first justified "prior art, not
oracle" by citing a deviation in the branch's age formatter. That was wrong. The
branch fixed it, and the original reviewer's legacy examples were fabricated.
`context-curator` caught this. The ruling stands on stronger grounds, in D2.

### D2 — Two branch deviations change search results

**The dilemma.** Two accepted deviations on that branch change what a user gets
back, not merely how it looks. Its regex engine has a 2-million-step budget, and
on a backtracking pattern it returns "no match" with a warning where CPython
returns the true answer. And malformed intervals such as `{5,x}` make its
validator reject the whole pattern and fall back to a literal, where CPython
treats that text as literal characters mid-pattern while the rest of the regex
still applies. The two diverge inside an alternation.

**Chosen path. RESOLVED 2026-08-28 by measurement.** `query-semantics` built a
differential harness and ran three engines against CPython 3.14.7 as oracle.
The ruling, in order:

1. Fix the cost model first. Prescan for the required literal. Stop restarting
   the backtracking VM at every start offset.
2. Then keep a step budget only as a pathological-pattern guard, and fail loud
   on exhaustion.
3. Never silently return no-match.
4. On genuinely catastrophic patterns, the loud failure is a deliberate
   divergence and goes in the change log as one.
5. Malformed intervals get fixed, not accepted. It is a parser bug. The branch
   already applies CPython's rule to `a{}`, so the machinery exists and is
   simply not reached.

**The first mate's framing was wrong.** "Wrong and fast against correct and
unusable" holds only for genuinely catastrophic patterns. It is false for the
population that actually trips the budget. A step counter cannot tell a
pathological pattern from a large haystack. `[a-z ]*NEEDLE` over a
20,000-character message that contains `NEEDLE` returns no match, where CPython
answers correctly in 5.9 ms. That is a bug, not a trade-off. Failing loud on
today's engine would turn ordinary searches into hard errors, which is why the
cost-model fix has to come first.

**Also measured:** the warning fires once per process, so a real run prints one
line and then returns wrong answers silently for everything after it.

## Do not re-derive these

Hard-won negative results from the branch. They cost real time once.

1. **Do not add a stat-mtime short circuit *in front of* the content probe.**
   The pool holds files that violate "created ≤ modified ≤ mtime" through
   imports, copies, `touch -t`, and restore tools. It silently dropped hits, and
   the colored-plus-pager arm used a different predicate, so the binary
   disagreed with itself on the same query. The guarded variant was analyzed and
   permanently closed. For `-ca` the content probe is already the cheap first
   read, and `-ma` already reads only 4 KB tail chunks backward, so guarding adds
   stat calls and cannot win.
   **⚠ Corrected. An earlier version of this line said "legacy consults content
   timestamps only", which is false and dangerous.** That is true of the
   *probe* and not of the *fallback*: both `get_jsonl_first_timestamp` and
   `get_jsonl_last_timestamp` **do** fall back to filesystem birth time and
   mtime when a file carries no in-band timestamp. A port that read the earlier
   wording literally and removed the fallback would **drop every timestamp-less
   file from the pool**. The withdrawn defect was a short circuit *replacing* the
   content read — a different thing from the fallback beneath it.
2. **Never index a string with offsets measured on its lowercased copy.** `İ`
   grows from 2 bytes to 3 when lowercased. The ligatures `ﬀﬁﬂﬃﬄ` shrink from 3
   to 2. Enough drift aborts the process mid-render with exit 101. Below that
   threshold it silently paints the wrong span. This was the branch's one
   blocker. Fold per character over the original string, using the same
   equivalence the search truth uses.
3. **The branch's closure review is unreliable.** Its own repair round formally
   overturned four of its nine findings. Read it as leads to verify, never as
   verdicts.

## Open questions

1. ~~Does the branch build and run, and does it hold its timing claims?~~
   **Answered 2026-08-28. Yes. Reconciling beats building fresh.** Release build
   in 16 seconds with no warnings, no libpython, zero undefined `Py_` symbols.
   `cargo test` matches its records: 54 pass no-default-features, 58 pass
   default. Contract suite gave 9 failures, all explained: 2 were method
   artifacts, and 7 were age-bucket fixture rot that pass byte for byte once the
   bucket color is neutralized. The colored cases — Rich panels, hue cycling,
   the 80-column layout, highlight painting, and real `less` streaming —
   reproduce byte for byte. Timing on a 1,600-file, 2.86 GB window: 2.2× to 35×
   faster than the Python route. Peak memory 653 MB against 1,920 MB, treated as
   a floor because that corpus holds one small Pi session. No cross-window claim
   is made. Not measured: the real-install half, the wheel identity test, the
   eight-gate battery, and the two accepted behavior deviations.
2. Do the 704 expected outputs reproduce against today's `main` Python? This
   decides how much of that corpus we adopt as-is. `context-curator`. Blocks G2.
3. ~~The two result-changing deviations.~~ **Resolved.** See D2 and decision 15.
4. ~~Three-way terminal-width reconciliation.~~ **Smaller than reported.**
   `session-core` measured it. `main`'s helper and Rich agree on every ordinary
   input and diverge on exactly two: `COLUMNS="+80"`, which Rust honors and Rich
   ignores, and fullwidth `COLUMNS="８０"`, which Rich honors and Rust ignores. It
   is a two-line repair to `main`'s existing helper. The native renderer calls
   that helper rather than re-deriving width, so `terminal_width()` moves out of
   `rust/main.rs`. Seam between `session-core` and `search-runtime`.
5. Whether parameterizing the shared shell-test path is cheap. Dissolves
   standing constraint 2. `contract-owner`.
6. Seven behavior classes that the branch's 704-case suite pins nowhere.
   `contract-owner` treats them as contract requirements, not background.

## Pointers

Teammate material lives in `teammates/<name>/`. Promotion to the shared desk is
the first mate's call.

| Material | Location | Status |
| --- | --- | --- |
| `context-relevance.md` | shared desk | **promoted** |
| `branch-boundary-comparison.md` | shared desk | **promoted** |
| `session-core-map.md` | shared desk | **promoted** |
| `session-core-branch-reconciliation.md` | shared desk | **promoted** |
| `query-semantics-map.md` | shared desk | **promoted** |
| differential regex harness | `teammates/query-semantics/harness/` | reuse it, do not rebuild |
| `search-runtime-map.md` | `teammates/search-runtime/` | landed, accepted in substance |
| branch reconciliation draft | `teammates/search-runtime/` | commissioned, becomes the G2 task DAG |
| `session-core-map.md` | `teammates/session-core/` | landed, promotion pending |
| contract corpus and sweeps | `teammates/contract-owner/work/` | in progress |
| baseline and corpus evidence | `teammates/reviewer-profiler/evidence/` | in progress |
| `query-semantics-map.md` | `teammates/query-semantics/` | pending |
| `final-change-log.md` | shared desk | pending, G5 |

---

## Late additions (2026-08-28, first mate, written at handover)

Numbered separately from the standing constraints so nothing collides; treat
them as standing.

**Seat note.** A successor first-mate pane was launched and then intentionally
retired. `search-firstmate` retains the seat through a server-side compaction,
with the same ownership and the same rules. `prompts/search-firstmate-successor.md`
stays on the desk as the cold-entry brief for whoever takes the seat next; it is
current except that it lists the seat as being handed over.

### L1. A differential is convertible only while its oracle **and its driver** both exist

`reviewer-profiler` found this and it is the sharpest correction to the
conversion plan. We priced the oracle's death at cutover and never priced the
driver's. Drivers live in per-session scratchpads under `/private/tmp` and die
with the session that built them — **not at cutover, but at any session exit.**

Measured inventory: shortening driver present, render driver present,
**branch-map driver gone.** `branch_map_differential.py` parses, is correct by
inspection, and **has never run**, because nothing on disk produces a branch
map. `session-core`'s 355-case branch result is therefore unreproducible *now*,
not at cutover.

**✅ RESOLVED the same day. Option 1: rebuilt, in the tree, and re-run.**
`session-core` had repurposed the branch-map crate into the render driver by
overwriting its `main.rs`, so the 355-case result was **correct and
unreproducible at the same time**, and had been for hours. Rebuilt at
`probes/drivers/branchmap/` and re-run: **360 sessions, 227 with branches, 0
mismatches.** Rebuilt by its author rather than by the auditor, on the reasoning
below. All five drivers are now present with a README naming which need their
modules copied in first.

**The count moved from 355 to 360 between runs and nothing regressed** — the
Claude corpus grows while the team works. These counts are only meaningful with
the date they were taken, and that is now in the driver README so nobody reads a
moved count as a defect. Same live-corpus property as 22al, from a third
direction.

**`session-core`'s one-word sharpening, which is the part that generalises:
preserving *some* drivers is not preserving them.** They had copied drivers to
the desk an hour earlier and it felt like discharging the obligation. They had
checked that the files they copied worked, rather than checking which files the
probes needed. **The audit that caught it asked the second question.**

**Ruling.** Move every driver a gate depends on into the repository tree, or the
gate's result is a dated point-in-time proof and must say so in its own output.
A scratchpad is not storage. For the branch map specifically: `session-core`
owns the recipe and is on call — the rebuild is theirs, not the reviewer's,
because rebuilding another person's driver from their map is how a
reconstruction acquires the reconstructor's assumptions. If the recipe did not
survive in `session-core-map.md`, the 355-case result is recorded as dated and
we stop claiming it is re-runnable. Both outcomes are acceptable. Only the
silent third one — assuming it can be re-run — is not.

### L2. A shared generated file can be silently emptied by the other owner's generator

`reviewer-profiler`'s generator rebuilds `frozen_reference.json` from scratch.
`contract-owner` had written `source_digest` into it. The fields survived only
because of run ordering; the next regeneration would have deleted them with no
diff anyone would read. Fixed by carrying foreign fields forward.

**Generalise:** any file with two writers where one regenerates wholesale is a
silent-deletion site. Carry unknown fields forward rather than rebuilding.

### L3. The oracle-as-precondition pattern now has four sites and three owners

An assertion that is true for the right implementation **and** true for a
completely different situation. `width_parity` accused the formatter when the
oracle had crashed; fixed and falsified by `search-runtime` (shadowing the
package with a failing `__init__.py`).

**✅ All three closed.** `width_parity` at `rust/search.rs:333`,
`render_parity::oracle` via `assert_oracle_did_not_crash` at `rust/search.rs:435`,
and `parse::argparse_parity::argparse` at `rust/search/parse.rs:841`. 135 lib, 1
bin, 36 doctests, release build green. `query-semantics` wrote the last two on
`search-runtime`'s yes; `search-runtime` reviewed and passed the diff, the same
arrangement as the `python_io` lift.

**The discriminator is not `success()`, and that is the load-bearing detail.** A
rejected argv legitimately exits 2 and a fruitless search exits 1, so a
success-check would have broken correct tests. The precondition is instead that
stderr carries no `Traceback (most recent call last):`, while the status is still
returned for the caller to compare. Verified underneath rather than assumed:
**zero of the 76 recorded oracle cases carry that marker**, and exits 0, 1 and 2
all appear.

**One residual, documented rather than silently accepted.** The check catches a
crash that prints a traceback — the mid-save case. It does not catch a *clean*
non-zero exit from a broken import, and there is no better instrument:
`success()` is unusable where 1 and 2 are legitimate, and enumerating valid
statuses would accept a clean `SystemExit(1)` anyway. The comments claim only
"did the oracle run at all", which is what the gate actually supports.

Three owners in one day makes this a property of how this team writes tests, not
three accidents. It is worse than a missed defect: a missed defect is silent,
this one is confidently wrong. **Every gate that shells out to `ch-legacy` must
assert the oracle ran before it compares anything.**

### L4. The pty differential harness: what it proves and what it does not

`probes/pty_differential.py`, `views-and-colour`. 28 coloured cases under a real
pty at widths **40, 60, 120**. It *refuses* 80 and 96 with an error rather than a
comment — 80 is Rich's fallback and **96 is what every coloured contract case
pins**, so a diff at either proves nothing. Clock pinned, all `\r` stripped,
temp home normalised, and the reference captured **twice per case with
nondeterminism failing before any comparison**, so a route differing from itself
can never read as a difference from the other route. Six perturbations caught.

**The green run is instrument calibration, not parity** — `ch search` still falls
through to `ch-legacy`, so both sides are the same Python and 84 agreeing
comparisons could not have failed. The tool prints that caveat in its own output
rather than in a document, which is the right place for it. What it does
establish: the Python route is byte-deterministic under a pty at these widths
with the clock pinned, and the launcher's hand-off to `ch-legacy` is
byte-transparent.

**Sensitivity is a property of the whole sweep, not of any width in it.** At
width 40 the list row is clipped before its age token, so a self-test at one
width reports the harness blind to a dimension it sees perfectly at 120.

**`CH_NOW=2027-01-16` is a load-bearing constant.** The fixture mtimes cluster
within 600 seconds, so almost every instant puts every row in one age bucket.
That instant spans three (`1d`→week, `22h`→now, `4mo`→old) and is the only
reason the sweep reaches the label-to-colour disagreement — the highest-risk
preserve-because-wrong item. The age colour is caught on 4 of 84 captures: by
far the thinnest dimension, and the one every other comparator normalises away.
**Re-check it first if the fixture corpus moves.**

### L5. Ownership settled at handover

`HitSink::emit` takes `&SearchHit` rather than a pre-rendered string
(`engine-and-codex` proposed, `views-and-colour` approved). The `finish`
condition is `views-and-colour`'s, **except the not-closed half, which stays with
the pager.** The installed-launcher window is **free** — `views-and-colour` only
ever read `.venv/bin/ch` and `ch-legacy`, never rebuilt or reinstalled.

### L6. G3 is open, and it was late

G3 sat unstarted while eight slices landed. Commissioned 2026-08-28 to
`context-curator`, structural half first: `rust/color.rs`, `rust/cells.rs`, the
whole argument grammar under `rust/search/` including the help formatter,
`rust/search/plan.rs`, the `python_io` lift, `terminal.rs`, `inventory.rs`,
`scanner.rs`. Start where the reconciliation is thickest — a replayed source hunk
restores a behaviour and silently drops its proof, and 364 of the 913 insertions
are exactly those proofs.

**The timing-economy review waits.** Three of the four economies live in the
engine being wired now, so the review that reaches them cannot run yet. The
landed slices do not wait for it. This is the one review half that cannot be
replaced by anyone else on the roster — see `decision-record.md` entry 2.

### L7. Live ownership at this point

| Who | State |
| --- | --- |
| `engine-and-codex` | **Critical path.** Confirmation, then Codex in `rust/codex.rs`. Everything downstream is staged. |
| `views-and-colour` | pty harness landed and self-falsified. Highlight painting waits on confirmation; the panel frame is gateable separately. |
| `search-runtime` | Grammar complete; `Run`-arm items **1–3 and 6 done**, all three oracle preconditions closed and green. Idle by choice at 75%. Owns the G4 cutover — still the only thing with no second owner. |
| `reviewer-profiler` | Conversions done but one. Holds the driver-perishability finding. |
| `context-curator` | G3 structural review, opened above. |
| `session-core` | Branch-map driver rebuilt in the tree and re-run clean. List empty, on call for `engine-and-codex`. |
| `contract-owner` | On call for the route flip. Everything delivered. |
| `query-semantics` | **Stopped clean at 10%.** 139 lib tests green, `RESUME.md` written as the complement of the two live documents. `session-core` holds confirmation questions now. |

### L8. The item that has not moved

**`parse_raw_cli_transcript` is still unported**, and it is the one gap no
instrument on this desk can grade: the nine files taking `SessionFormat::Raw`
all produce zero messages, so a green real-corpus run says nothing about it. It
needs a synthesized fixture written from its first line of code, anchored against
a real specimen per 22t. It is in `engine-and-codex`'s scope and it is the
likeliest thing to be finished-looking and untested at G5.

### L9. A falsifier proves a gate fires. It does not prove the gate fires for the modelled cause.

Sharpens 22i, which is the most-cited rule on this desk and is incomplete as
written. "Every gate ships with an automated falsification" makes the gate prove
it can go red. It does not make the gate prove it goes red **for the reason the
falsifier claims to model** — and a falsifier that trips the wrong mechanism is
indistinguishable from one that works, because both produce a red.

**Therefore: read the failure message, not the exit status of the falsifier.**
The verdict tells you the gate is alive. Only the message tells you what it saw.

*Earned, twice over, in one exchange.* `query-semantics`' first falsification for
the oracle precondition raised `SystemExit` — which exits **without** printing a
traceback, so it modelled a clean exit rather than a crash. The test went red
anyway, on the old exit-status comparison, and the mismatch was caught only by
reading what the red said. And `search-runtime` applied the same reading to their
own `width_parity` falsification and found it carries the identical limitation:
it is safe today only because the assertion it trips is broader than the one it
models, so a later narrowing would have left it passing while real crashes went
through. **Both authors found the flaw in their own falsifier by reading a
message they had already been given a green light by.**

This is the same shape as 22j — a gate that grades itself produces a correct,
quotable, inert number — one level up. There the gate could not fail. Here the
gate fails for the wrong reason and the failure looks exactly right.

### L10. G3 first structural pass — clean

`g3-structural-review-01.md`, promoted. Reconciliation-thickest surfaces first.
**No structural defects.** Both criteria the branch demonstrably failed now pass:
the forked scan is not reproduced (`python_extension.rs` fell 1,399 → 301 lines,
three of four scans are thin wrappers over one `inventory.rs` implementation),
and the two trim layers are one function on the right semantics
(`trim_python_byte_whitespace`, defined once at `inventory.rs:349`), so a line
beginning `\u{00A0}` behaves identically on both routes. The mtime short circuit
is absent in every arm of `pool_filter.rs`, **and lines 189–191 carry a comment
recording why, citing the prior team's withdrawal** — the argument now meets a
future reader at the point of temptation, which is the only place it works.
`terminal_width` is imported rather than redefined, so the original was deleted
in the same change.

**Watch item, a shape rather than a bug.** `scan_resolution_facets_impl` is the
one scan not extracted, still carrying its own body at `python_extension.rs:95`.
There is no second copy, so it is not a fork — but resolution fallback needs
facets, so that is exactly where a second implementation gets written when the
native route reaches them, and the branch's defect reproduces. **Cheapest guard:
extract it in the same change that first needs it natively, rather than writing a
native one beside it.**

**Do not fix, and this is the point of recording it.** Two PyO3 functions still
take `&str` where siblings take bytes — the non-UTF-8 path defect. It is not a
port defect: the native side takes `&Path` and is byte-safe, and the lossy
conversion lives only in the legacy wrapper, which dies at cutover and removes it
for free. It reads like an unfixed bug in a diff. Fixing it is work on code
scheduled for deletion.

**Timing economy 2 survives**, both the laziness and the short-circuit — it lives
in `pool_filter.rs` rather than the engine, so it was reviewable now. The other
three wait for the engine.

Next pass: `color.rs`, `cells.rs`, the `rust/search/` grammar, `plan.rs`,
`python_io`, `codex.rs`.

**A ninth preserve-because-wrong behaviour was found by this review** and is
added to `preserve-because-wrong.md` as an attributed addendum: the two width
resolvers disagreeing inside one invocation. It was absent from items 1–8
because the sweep read for naive implementations a porter would correct, and this
is two *correct* implementations of two different specifications sharing a
process.

### L11. The same lesson, one level up: an unrun recipe is not a recipe

`session-core` tested their own driver README instead of trusting it. **It was
wrong** — off by one directory, and the driver it described did not compile.
Identical failure to the lost branch driver: instructions written and not run.

Fixed and verified end to end. All five drivers now build **and reproduce their
numbers**: `branchmap` 360 sessions / 0 mismatches, `toolspec` 2,006 specs / 0
mismatches, `shortening` 308 cases / 0 mismatches, `render` builds from the tree.
The copy path now derives from `git rev-parse --show-toplevel` so it cannot be
off by one.

**The chain in full, three levels, all found today: the oracle is perishable, the
driver is perishable, and the recipe for rebuilding the driver is perishable.**
Each level looked like it discharged the obligation of the one below it. Only
execution ever did.

### L12. "Promoted" meant "was correct once". The desk was stale in 17 of 20 documents.

`context-curator` found it in their own file and inverted my reading of it: the
**desk** copy carried the withdrawn digest, their copy had been re-derived hours
earlier. Promotion had copied, and the copy never tracked the corrections.

I measured the rest rather than fixing the instance. **Seventeen of twenty
promoted documents were behind their sources.** Not marginally:
`review-profile-plan.md` was 230 lines against 780, `session-core-map.md` 432
against 1,405, `contract.md` 426 against 981. The desk — the thing this whole
mission exists to produce, because the last rewrite finished and was never
recorded — was the least current copy of almost everything on it.

**Ruling: promotion is by reference, not by copy.** Every promoted document is
now a symlink into `teammates/<name>/`. One byte-stream, so divergence is not
possible rather than merely detected. The editorial gate is unchanged — I still
decide what appears on the desk — but a document stops being frozen at the moment
it becomes visible.

**Rejected: a mechanism that notices.** A stamp comparing source and desk digests
would have found this and does not remove it, and 22l applies to the sweep that
would have to find the unstamped ones. Removing the second copy beats detecting
divergence between two copies.

**Rejected: re-promote on every correction.** It depends on the author
remembering, and this document's author corrected it three times today without
anyone noticing. A rule that failed three times in one file is not the fix.

**The lesson, not the schedule** — `context-curator`'s framing, and it is the
part that transfers. **The failure was not copying. It was copying *early*,
while the source was still moving.** The right time to freeze is when the thing
stops changing, and not one moment before. That is the same shape as the deletion
slice and as both of their oracle freezes. So: live by reference while the
mission runs, **frozen to copies at G5**, when the record stops being worked on
and starts being history.

**Why it outranks every other finding today, including the eight on the
preserve list.** It degrades all of them at once, and it does so silently — a
stale document does not announce itself, it answers your question with last
hour's answer. I read the stale `decision-record.md` as my authoritative cold
entry this morning and could not have told.

`state.md`, `charter.md`, `herdr-team.md` and `prompts/` are first-mate originals
and stay plain files.

**Consequence every teammate must know: your `teammates/<name>/` copy of a
promoted document is now what the team reads.** Keep it correct. There is no
second copy to fall behind, and no promotion request needed to publish a
correction to something already promoted.

### L13. My own staleness sweep was blind to renames — 22l, on the rule's author, again

The scan that found 17 of 20 matched on **identical basename**. One promoted
document had been renamed at promotion — `session-core-branch-reconciliation.md`
on the desk, `branch-reconciliation.md` at source — and was therefore invisible
to the instrument that was looking for exactly its failure. It was 161 lines
against 184.

**And what it was missing was the worst possible content.** The stale copy still
framed the branch and `main` as peers with competing fixes for `optional_string`.
The correction — `main` changed it at `47b3db9`, the branch is simply stale — is
what produced standing decision 18, *`main` wins by default and the branch must
earn each difference.* **So the desk contradicted a rule the desk also carried**,
in the one document a porter would read while deciding whether to take a branch
hunk.

Found by `session-core` reading their own promotions rather than by the sweep.
Now symlinked. **All 20 promoted documents are references; `state.md`,
`charter.md` and `herdr-team.md` are first-mate originals and stay plain files.**

22l has now caught its author twice in one day: a discovery command that finds
only the compliant reports clean forever, and "same basename" is a compliance
condition wearing the clothes of an identity check.

### L14. `contract-owner`'s fixtures are structurally immune to a wrong document, and that is worth more than the check

Asked whether any fixture was written from preserve item 3's pre-correction
wording. Answer: **none, and none could be.** Every fixture they hold records
**what the product actually rendered** — the generator runs the real command and
stores the bytes. A document entry only ever decided *which shape to include*; it
never supplied an expectation. **So a wrong document entry costs them a useless
case, never a false one.**

That is the structural form of 22ad — a table that re-derives its own answers is
not a fixture — reached from the opposite direction: a fixture whose expected
value comes from a *claim* is the thing to fear, and this corpus has none.

They checked the specific case anyway rather than resting on the argument. The
NFC/NFD title pair pins a real difference, nine visible characters apart at 52
columns. **And it surfaced a fact worth keeping: at 72 columns the two render
identically**, so that row pins nothing about normalisation. Left in place and
now written down, because a width at which two implementations agree is itself a
fact — but it is no longer assumed to be pulling weight it does not pull.

### L15. The confirmation fallback is real, not nominal

`session-core` read `e1-confirmation-handoff.md` through §7 **before** being
needed, rather than accepting the title of fallback. They can answer on the
`stream_search` seam, positional emission, why `Gated` is three-way, the three
search sources, `NOT` contributing no display terms, invalid-regex-becomes-
literal, `StepBudgetExceeded` never collapsing to "no match", `--raw` as the one
buffering mode, and the exit-status split.

**A useful accident: `confirm` calls their decoders and their renderer**, so they
answer both halves of most confirmation questions without a relay. That is a
stronger fallback than the person it replaces, for this particular seam.

They also ran a consistency check between the two handoffs — §4's "three sources,
session-wide" matches what they gave `engine-and-codex` directly, no
contradiction. **Checking two documents against each other before either is
needed is the cheapest form of the staleness audit**, and it is the first time
anyone has done it proactively rather than after a divergence bit.

### L16. `query-semantics` stopped clean, and the handoff shape is worth copying

Stopped at 10% with 139 lib tests green, nothing unfinished, unproven or
mid-flight, and both promoted documents verified byte for byte against their
symlinks. `teammates/query-semantics/RESUME.md`, 107 lines. **`session-core` is
the owner for confirmation questions from here**, having read
`e1-confirmation-handoff.md` through §7 before being needed.

**The shape of that handoff is the transferable part, and every teammate who
hands off should copy it.** It holds *only what is in neither other document* —
the answers to questions nobody asked — and phrases each as the question a
successor would actually put, not as a statement. Seven of them: why
`CANDIDATE_WINDOW` should not be widened and the measurement that says so; why
`PoolFilter`'s date state is private; why the provider partition is a list rather
than a map and when that could change; why any date differential must pin
`CH_NOW` on **both** sides; why chrono's `%Y` cannot be used directly; whether
the birthtime fallback is safe where unsupported; and the one that would bite
hardest — **that "date filters never read stat mtime" is true of the *probe* and
false of the *fallback***, so a port following the handoff literally drops every
timestamp-less file from the pool.

That last one independently reproduces the correction already carried in "Do not
re-derive these" item 1. **Two people arrived at it from different directions and
the desk now says it in two places** — which is the correct amount for a claim
whose literal reading silently loses data.

**A handoff that repeats what two live documents already say buys nothing and
costs the reader's attention.** This one is 107 lines because it is the
complement, not a summary.

### L17. `--color` does not reach stderr — measured, confirmed, owned

**Preserve-because-wrong, second member of the two-parsers class.** Measured by
`views-and-colour` over six runs of the no-results hint:

    stderr on a pty    bare / never / always  ->  103B truecolor, all three IDENTICAL
    stderr on a pipe   bare / never / always  ->   38B plain,     all three IDENTICAL

`--color` reaches stdout's console and **none of the three stderr consoles**.
Stderr colour follows stderr's own tty-ness alone, so `ch search nomatch --color
never 2>/dev/tty` emits truecolor. `search-runtime`'s source reading needed no
correction. It is on the preserve list and it has an owner already — the four
stderr consoles are `views-and-colour`'s, so it lands inside their port rather
than needing an assignment.

### L18. Every pty instrument on this mission is blind to stderr, and for two different reasons

The reason `search-runtime` could not measure their own lead is not local to
their probe. I checked both harnesses.

- **`reviewer-profiler/pty_harness.py::run_at_width` passes
  `stderr=subprocess.DEVNULL`.** Its docstring says "returning raw stdout bytes",
  so it is honest — but it is imported by **six gates**: `ambient_gate.py`,
  `colour_capability_sweep.py`, `colored_width_gate.py`, `age_pairing_gate.py`,
  `freeze_references.py`, `calibrate_pty.py`, **and** `views-and-colour`'s
  `pty_differential.py`.
- **`query-semantics/harness/grammar_oracle.py::run_at_width` passes
  `stderr=subprocess.PIPE`** — captured, but on a **pipe** while stdout is on a
  pty. That is exactly the condition under which stderr colour is off, so its
  recorded stderr is plain *by construction*. Correct for byte-comparing error
  text; incapable of observing stderr colour.

**So the defect in L17 lived in the blind spot of every instrument built to find
that class**, and needed a purpose-built inverted probe to see. None of these
gates is wrong: each is correct for the question it was built for. **What is
wrong is a completeness claim made over them.**

**⚠ This bounds 22af.** That constraint says five ambient gaps in total, that the
pty and pipe sweeps see disjoint subsets, and that "neither sweep alone could
have found more than three of five". That parameterization varied the
**condition** — pty against pipe — while silently holding the **observed stream**
fixed at stdout. This is 22an exactly, one category deeper: *an enumeration is
bounded by its categories, and the categories are invisible from inside.* The
invisible category here is **which stream you are looking at**, and there is now
a measured behaviour that no member of the enumeration could have reached.

**The five-gap figure is not withdrawn. Its scope is narrowed to stdout**, and
whether stderr adds gaps is unmeasured rather than answered.

### L19. A third way a probe can be wrong: pointed at the wrong stream

L9 gave two — a gate that does not fire, and a gate that fires for a cause other
than the one modelled. `search-runtime` names the third: **a probe pointed at the
wrong stream entirely.** It fires correctly, reports honestly, and answers a
question about output nobody asked. Distinct from the first two because nothing
in its behaviour is anomalous — the instrument is working.

**And a parameterization whose members were *chosen* can contain duplicates you
cannot see.** `views-and-colour` found one of their four Unicode oracles
byte-identical to another, so one arm of four proved nothing. Found only because
`reviewer-profiler` asked whether the probe characters were **chosen or derived**.
They were chosen. Now derived per version pair, all four distinct, and a
hardcoded-table mutation fails the corpus gate itself. **Derive the members of a
parameterization from the difference they are meant to expose; a chosen set
cannot tell you it collapsed.**

Related guard, same origin: `clock_responsiveness()` in the pty harness — a route
that ignores `CH_NOW` produces one outcome across seven instants, so the sweep
would silently check a seventh of what it reports. Falsified against a wrapper
that unsets the variable.

### L20. The cutover recipe found two gaps. One is ruled by an existing decision; one needs an owner.

Writing the cutover as a recipe someone else could follow surfaced two things
invisible while it lived in one person's head. **That is the return on writing
it, and it arrived before the branch landed rather than during it.**

**Gap 1 — a missing conversion between two filter types, and it looked ownerless.**
`parse::SearchPoolFilter` carries `{ directory, modified_after, created_after,
provider: Option<Provider> }` with the dates as **unparsed strings**;
`pool_filter::PoolFilter` carries parsed `NaiveDateTime`s and
`provider: Option<String>`. `rg SearchPoolFilter` finds nothing outside the
grammar, so no conversion exists.

**Ruled: it is `search-runtime`'s, on both sides.** The G2 ownership table gives
them the whole argument grammar *and* filters. It reads as a seam because the
two types were written weeks apart for different purposes, not because the
ownership is split.

**Gap 2 — a real divergence, and it is already decided.** `PoolFilter::new`
returns `Result`, so converting at the cutover would fail **fast**, before any
scanning. Python does not: a bad `-ca` value raises **per file** inside the path
filter, is caught, prints `Error processing conversation file <path>: Invalid
date format: 'bogus-date'` once per file, then the ordinary no-results hint, and
exits 1. Recorded in `probes/grammar-oracle.json` under
`["-ca","bogus-date","needle"]`.

**Ruled: preserve the per-file shape. No new judgment was needed** — this desk
already decided it, under "Preserved deliberately, though poor": *`-ma notadate`
keeps printing one error per candidate file and exiting 1. It works. Changing it
is a product improvement outside this mission, and smuggling an improvement into
a parity rewrite is the failure this team spent the day guarding against.* The
`-ca` case is the same behaviour through the same path. It goes to the captain as
a separate proposal, not into the port.

**The reason this entry exists at all** is that failing fast is *arguably better*,
and a conversion writer who had not read that ruling would have chosen it
silently and correctly-looking. A divergence must be ruled, never arrived at by
whoever writes the glue noticing or not noticing.

**Recipe status, honest about itself.** Steps 1–4 checked: all three arms exist
and are byte-proved; the two width resolvers exist with a test asserting they
disagree, so the wrong one cannot be swapped in silently; `plan::{scan_order,
screen, probe}` match `stream_search`'s parameter shapes and `Outcome`'s two
methods exist; and `search` still falls through to `run_legacy`, so the branch is
purely additive and reverting is deleting it. Steps 5–7 **marked unrun** and only
checkable after the branch lands: the suites against a rebuilt binary, the
differential under a pty at two widths, and the no-Python proof. **That last is
the mission's bottom line and nobody can check it early.**

### L21. stderr swept. No new inputs — and one divergence that needs no input at all.

`reviewer-profiler` measured rather than accepting the unmeasured scope note.
`pty_harness.py::run_at_width` now takes `stream="stdout" | "stderr" | "both"`,
defaulting to stdout so **none of the seven importers changes behaviour**.

**Part one: no new input names.** On the no-match shape, the same three
colour-resolution inputs act on stderr — `COLORTERM`, `NO_COLOR`, `TERM=dumb`. So
the gap count stands as a count of *inputs*, scoped to stdout and now confirmed
not to grow on stderr. **Scope corrected, not withdrawn.**

**Part two, and it is a live defect nobody was watching.** At baseline, with no
ambient input set at all:

    subject     37B  'No sessions match "zqxjvwmkbphfgd".'
    reference   92B  grey text, green-highlighted query, coloured throughout

**The native route emits a plain hint where Python emits a coloured one.** Every
`agree` cell in the stderr sweep reads NO at every setting — not because the
inputs diverge but because **the surface does**. Python produces a usable answer,
so the charter line is preserve: this is unported behaviour, not a
preserve-because-wrong item and not a divergence to accept.

**Owner: `views-and-colour`**, with L17. Both live in the same four stderr
consoles, and they are opposite halves of one surface — L17 is `--color` failing
to reach those consoles, this is the consoles never being coloured natively at
all.

### L22. A shared harness's defaults are a parameterization every caller inherits silently

`reviewer-profiler`'s rule, and the sharpest form of the bound this mission keeps
re-deriving. Inputs, conditions, categories — and now **which stream you are
observing**.

**That last one is worse than the others, because it was not a parameter anyone
chose to hold fixed.** It was a default in a helper, inherited by six gates and
by `views-and-colour`'s differential, and **nothing in any of their outputs would
ever have hinted at it.** The harness's own docstring was accurate the whole
time. The finding came from the *product* side, via a purpose-built inverted
probe; it was not reachable from the harness side without being told.

**So: each owner checks what their shared helpers hold *fixed*, not what they
vary.** `run_at_width` held the stream. It could as easily have held the width or
the environment.

**And the corollary, which argues against this desk's own import-not-copy rule at
one point:** a shared harness propagates its blind spots to everything
downstream, and the blind spot is invisible in precisely the artifacts built to
find that class. 22f says import tools rather than copy them, and that stands —
but `views-and-colour` building a purpose-made probe instead of extending the
shared one is what found this, and it was the right call. **The exception to
import-not-copy is when the shared tool's defaults are the thing under
suspicion.**

### L23. Conversion set closed — and a durable replacement does not remove the perishable original

**Closed:** shortening 308 cases / 0 mismatches; 7 branch fixtures from a
360-session green run, 922 bytes, verified free of home paths and session ids;
`allocation_profile` frozen at `7.01x + 82`; 46 frozen ambient/width/colour
reference outputs; `claude_render` not convertible (private session content);
`ratio_scaling` retired, its question answered.

**⚠ A correction to the reading, not to the work.** `reviewer-profiler` concluded
the branch-map differential is still non-durable because the driver they ran
lives in a scratchpad. **It is durable. They ran the wrong binary.**
`session-core` rebuilt it hours earlier at
`teammates/session-core/probes/drivers/branchmap/`, beside `render`,
`shortening`, `toolspec` and a README, then tested the README recipe, found it
wrong, and fixed it. **L1 did not resolve by luck — the rule took effect
deliberately and was verified by execution.**

**The real finding is underneath the mistake.** A stale scratchpad binary was
still on disk, still took exactly the input shape the probe sends, and produced a
clean green run from an artifact nobody intended to be used. **A durable
replacement does not delete the perishable original, and the original is what a
probe finds first** — by path, by habit, or by an environment variable still
pointing at it.

Third clause on the prerequisite: it is not enough that the driver is in the tree
and its recipe has been run. **The scratchpad copy must be gone**, or a probe
keeps succeeding against it right up until the day it does not — the exact
failure L1 exists to prevent, arriving through the fix rather than the gap.

### L24. Freeze the stderr baseline. Ruled yes, execution deferred.

The freeze stores *Python's* bytes, and Python is deleted at the end of this
mission. Without a frozen stderr baseline the only thing that could prove the
stderr port matched is a live differential that dies at cutover — so
`views-and-colour`'s port would land with no durable evidence on the one surface
we now know carries a baseline divergence (L21), and where nothing was looking at
all until today. **The active port is the reason to do it, not a reason to skip
it: a frozen baseline is what the port gets measured against.**

**Execution held** by the disk incident below. A freeze written under a full disk
can be silently truncated, and a truncated frozen reference is the worst artifact
this mission could produce: it outlives the oracle, it looks authoritative, and
nothing downstream can distinguish it from a real one.

### L25. Disk exhaustion, 2026-08-28 — an environment failure that impersonates a code failure

The volume reached **100% with 127 MiB free**. Nine sessions, a 2.7 GiB shared
build directory, private binary copies mandated by standing constraint 2, and
active fixture writes.

**Why it was called before anything else was done: at that free space, builds and
captures do not fail cleanly.** Truncated objects, mysterious link failures, an
empty pty capture, a partial private binary copy. Every one reads as a real
finding in the code. It is the same class as the oracle-precondition defect
closed earlier today — a failure that points confidently at the wrong file — but
arriving simultaneously for every owner.

**Halted:** the cutover (its steps 5–7 all build and write, and a red cutover for
disk reasons is the worst possible first impression of the branch), the contract
suites, the stderr freeze, and any driver rebuild.

**Deliberately not done: deleting scratch to reclaim space.** Constraint 2 has
every teammate holding private copies right now, and three instruments died today
because a scratch directory went away. Deletion is the move most likely to cost
real work, and L23 had just been written about it.

**Cleared to 655 MiB / 95% by `contract-owner`**, entirely from artifacts they
own and all regenerable: their private cargo target (137 MiB, rebuilds in about
six seconds from the shared cache) and pre-regeneration corpus backups whose
purpose — proving the age-token diff — is closed and recorded. They touched
nothing outside their scope and said so.

**Still available if pressure returns: `target/debug` at 2.2 GiB**, which no
release-profile gate needs. **Not to be deleted while anyone is mid-build** — the
cost is a full debug recompile for whoever next runs `cargo test`, and that is
currently the person on the critical path.

**Results taken during the window are unverified rather than wrong.**
`contract-owner` declined to quote their last full run even though it finished
before the volume filled, because they cannot separate it from a partial write.
That is the correct treatment.

### L26. A harness that writes without checking free space cannot tell a short write from a regression

`contract-owner`'s own finding, and it outlives the incident. Their private
binary copy and their fixture writes both happen with no free-space
precondition, so **a short write produces a diff indistinguishable from a real
regression** — in the suite whose red is supposed to mean something.

Same principle as the launcher-staleness check and the oracle-ran precondition:
**assert the conditions the comparison depends on before comparing, not
after.** Named and owned by `contract-owner`, deferred rather than dropped —
unlike instrument conversion this is buildable at any time, so it does not
compete with the cutover.

### L27. Disk resolved to 4.6 GiB — and the sweep found more than space

**127 MiB → 4.6 GiB.** Every byte from a teammate deleting inside their own
scope, with each one stating what they kept and why. `contract-owner` 478 MiB,
`search-runtime` 338 MiB, `reviewer-profiler` 3.0 GB, `session-core` 1.0 GiB.
Nobody touched the shared `target/` (2.7 GiB) and nobody touched another
teammate's scratch. **The rule that made this safe was refusing to reclaim space
centrally**; four owners each knew which of their artifacts were dead, and no
central sweep could have.

**`search-runtime`'s reason for holding is better than mine and replaces it.** I
held the cutover partly on the risk of a bad first impression. The real reason:
steps 5–7 do not merely fail under a full disk, they fail **plausibly** — a build
that cannot write, a differential whose captures truncate, a pty harness that
cannot spawn. Each looks like a parity regression. **Under a full disk every gate
on this mission is simultaneously in the L9/L19 state**, reporting a failure
honestly while pointing at the wrong cause. That is the argument.

**A live defect the sweep surfaced, and it is L23's third instance — the sharpest
one.** `probes/mutate_pi.py`, an **in-tree** file, had `session-core`'s scratchpad
path hardcoded for its driver. The falsification harness would have pointed at a
copy that no longer exists, or worse, one that still did. Repointed at
`drivers/render` relative to its own location, and no scratchpad references
remain in their in-tree artifacts. **Here the probe named the perishable original
explicitly**, so this was not a search order accident — it was written down. The
two stale driver crates, `branchcheck` and `shortcheck`, are now deleted, after
verifying all four in-tree drivers carry complete sources rather than binaries.

**A retired instrument's corpus is not retired with it.** `reviewer-profiler`'s
2.2 GB was the corpus of `ratio_scaling`, retired hours earlier because its
question was answered. **Every owner has probably left one behind.** Retiring an
instrument means retiring its data.

**Sequencing constraint for G5, from `search-runtime`.** The no-Python proof
needs headroom for a full rebuild **and** it perturbs the shared install everyone
else measures against — it removes `ch-legacy` from the launcher directory. It is
scheduled deliberately with the launcher window held, never squeezed in beside
other work.

`target/debug` at 2.2 GiB remains the largest reclaimable item, needed by no
release-profile gate. Unowned, and **not to be deleted while anyone is
mid-build** — the cost is a full debug recompile for whoever next runs `cargo
test`, currently the person on the critical path.

### L28. The stderr freeze ran before the hold, and it is accepted

**Accepted on self-verification rather than re-run.** It executed minutes before
my hold arrived. `reviewer-profiler` verified the artifact rather than assuming:
valid JSON, 68 entries, all seven top-level keys, and **every entry's bytes match
its own recorded sha256**. A short write fails its own hash, so truncation is
detectable rather than a matter of judgement.

**Their argument for accepting is the right one and I am recording it as the
rule: self-verification tests the artifact, a re-run tests the conditions.** When
an artifact can prove its own integrity, re-taking it on a quieter machine
substitutes weaker evidence for stronger — and would produce a *different*
baseline if anything moved in between.

22 stderr entries, none empty. Against the native route: 68 stored, **34 drifted,
up from 14 of 46** — so roughly 20 of the 22 new entries diverge, which is the
L21 baseline stderr divergence appearing exactly where predicted. **The baseline
is Python's behaviour recorded before `views-and-colour`'s port lands**, which
was the whole point of the urgency.

### L29. `reviewer-profiler` at 75%, and the irreplaceable half is ahead of them

Flagged at 75% rather than at 90%, per the standing rule. Materially more than a
quarter of their work remains: G3 measurement reviews across three owners'
slices, the slope prediction test, and **G5 verification, which is the part that
cannot be compressed.**

**This is the second single-owner risk on the mission, after the cutover**, and
`decision-record.md` entry 2 forecloses the obvious fix — converting
`context-curator` would cost the structural review, which is the only one that
reaches the timing economies.

**Ruling: protect the irreplaceable half by spending nothing on the compressible
one while blocked.** Most of their queue is gated on the critical path — the
slope test needs `session`, the measurement reviews need slices — so the real
risk is burning context *waiting*. Delegating file-writing to forks is endorsed
and is the right instinct. `RESUME.md` is current.

### L30. Disk hold released — 22 GiB, and the resume order

Cleared at root cause by the captain: completed `query-semantics` scratch and
cargo debug incremental data only. Active scratch, sources and handoffs
untouched. Verified 22 GiB free before releasing.

**Resume order as issued.**

1. **`engine-and-codex` — confirmation.** First and alone on the critical path.
2. **`contract-owner` — re-run the suites.** They declined to quote their last
   full run because they could not separate it from a partial write, so **there
   is currently no quotable suite result on this desk.**
3. **`reviewer-profiler`** — stderr freeze accepted as it stands, not re-run.
   Re-run the branchmap conversion against the in-tree driver before quoting it.
4. **`search-runtime`** — cutover gate returns to confirmation alone; disk clause
   dropped from the recipe.
5. **`views-and-colour`** — the two stderr items now have a frozen Python
   baseline to be measured against; panel frame still gateable ahead of
   confirmation.
6. **`session-core`** — driver rebuilds safe; fallback for the confirmation seam.
7. **`context-curator`** — G3 pass two, never blocked.

**Standing instruction issued with the release: discard anything measured during
the window rather than reading it as a finding.** A result taken under a full
disk is unverified, not wrong — the distinction `contract-owner` drew and the
right one.

### L31. "Zero warnings" is true of one build mode. The library build reports two the binary build hides.

`reviewer-profiler` found it incidentally while rebuilding the branchmap driver,
which links the crate **as a library**:

    field `usage` is never read                   rust/search.rs:20
    associated function `term_dot` is never used  rust/search_query.rs:1802

`cargo build --release --no-default-features --bin ch` reports **zero**. So the
two modes disagree, and every "zero warnings" claim on this desk is a statement
about the mode we happen to check. **Same shape as the stderr stream default: a
held parameter nobody chose.** Extends 22aj — five configurations, and now the
warning criterion must **name its build mode** or it certifies the mode that
hides them.

**Neither warning is called a defect, and one of them must still be checked.**
Dead code in a work-in-progress module is ordinary. But this desk has already
recorded the branch's character-range folding arm ending in `&& false` — a whole
clause dead, shipped through a green suite **and** an independent review
(constraint 22, fifth instance). **A never-used function in the query engine is
that shape exactly**, and `term_dot` names the regex dot term. If `.` handling is
scaffolded but unwired, it moves search truth and no byte gate would show it,
because nothing calls it.

**Ownership, and it needed a ruling because one owner has stopped.**
`rust/search.rs:20` is `search-runtime`'s with the grammar.
`rust/search_query.rs` was `query-semantics`', who stopped clean at 10%.

**Ruled: `rust/search_query.rs` transfers to `search-runtime`.** They are idle
with the cutover recipe written, they already own the adjacent grammar, and
`engine-and-codex` must not be pulled off the critical path for this.
`session-core` is held as the confirmation fallback. The task is to establish
whether `term_dot` is unfinished scaffolding or an unwired feature — **against
the `&& false` precedent, not by reading it as obviously harmless.**

### L32. Codex decode landed. 0 mismatches, 8,477 cases, 1,211 sessions, full coverage.

`rust/codex.rs`, its own module. `session.rs` untouched and frozen. **The
one-line dispatch arm `session-core` was holding never existed** — dispatch lives
in `search_confirm.rs` — and they have dropped it.

**Both defects the differential found were the same mistake: the parser being
*more permissive* than Python's.**

- `const t = await tools.clock__curr_time({});` — Python parses `{}` and discards
  it, because an empty dict is falsy, so the call is "unparsed", the envelope
  keeps the name `exec`, and `exec` normalises to `Bash`. Returning
  `Some(empty)`, which is truthy, rendered `clock__curr_time`. **56 mismatches,
  14 sessions.**
- `const patch = "line one\n" +\n"line two\n";` — Python's binding pattern
  requires the string literal to be followed immediately by `;`, so a
  concatenated patch matches **nothing** and `apply_patch` stays unparsed.
  Accepting the first fragment rendered a tool named `Patch` carrying a patch
  truncated to one line. **4 mismatches.**

**Both came from implementing what the Python appears to *intend* rather than
what it literally *accepts*.** That is the general form and it belongs beside
preserve-because-wrong: the divergence is invisible to review, because the port
reads as the more correct of the two.

**Corpus blindness, two more instances, measured rather than assumed.** An
assistant `message` payload with more than one visible text block occurs **0**
times in the corpus; a `reasoning` summary carrying a non-`summary_text` item
occurs **0** times. Mutations breaking either caught nothing, **and a corpus of
any size would have been as blind** — `session-core`'s 477-of-477 Pi result in
two more places. Both now pinned by synthesized fixtures in `codex-fixtures/`,
each validated **against Python** rather than against the port, plus a control
shape occurring 94 times so the fixture route is shown to agree with the corpus
route. That is 22t's fourth instrument with its anchor, done correctly.

### L33. `Gated::Failed` is load-bearing after all — and it closes the L20 gap-2 loop

`engine-and-codex` corrected their own earlier finding, caught by
`search-runtime`. "Nothing in the path stage can raise" is true for **valid**
filter values and false for invalid ones: `mafter_dt` is a `cached_property`
calling `parse_date_filter`, **which raises on every access, once per candidate
file.** The discriminator is valid-versus-invalid filter value, not
directory-versus-file.

**This supplies the mechanism for the L20 gap-2 ruling and confirms it.** Python
raising per file is exactly why a bad `-ca` prints one error per candidate and
exits 1, and why converting at the cutover to fail fast would have been a
divergence. The `Failed` arm — recorded on this desk for hours as *deliberately
unused pending evidence* — now has its evidence. `search-runtime` is taking it.
The comment is being corrected to say the measurement covered valid values only.

### L34. The disk incident had a root cause, it is in a harness, and it will recur

**`claude_render_differential.py` calls `tempfile.mkdtemp`, copies the entire
matching corpus into it, and never removes it.** About **1.2 GiB leaked per
run**. 28 leaked `claude-render-snapshot-*` directories were found in `TMPDIR`,
**33 GiB**, most from repeated Codex runs today. Removed after checking no run
held them: 654 MiB → 21 GiB.

**It needs `finally: shutil.rmtree(...)`. It is `session-core`'s file.** Until
that lands, anyone running the render differential refills the disk.

**⚠ And the disk-full condition silently *shrank a gate* rather than failing it.**
One run reported `snapshotted 1041 of 1211` and then `mismatches: 0`. **That zero
was over 170 fewer sessions.** The verdict was clean, the count was plausible,
and the only tell was the coverage line — which exists solely because 22x
requires a gate to print what it covered rather than only whether it passed.
**A gate reporting pass/fail alone would have handed out a false green.**

**Consequence stronger than the guidance I issued at the time.** I told the team a
result taken during the window is *unverified rather than wrong*. The mechanism is
now known and it is narrower and worse: **a gate that does not report its own
coverage cannot be assessed at all, and must be re-run rather than judged.** One
that does report coverage can be checked against its expected total.

### L35. L22 applied to a second harness: the colour tier was held fixed across every result it ever reported

`context-curator` audited their own harness rather than assuming it was fine. It
held `TERM=xterm-256color`, `COLORTERM=truecolor`, `NO_COLOR` popped, `LINES=40`
and `cwd` fixed **across all 20 runs and every result they have reported.**

**`rust/color.rs` documents three distinct rendering states, not two.** `TERM=dumb`
and a redirected stream emit no SGR at all, while **`NO_COLOR` strips colour and
keeps attributes.** The corpus exercised exactly one of them. So every "no
invariant violations" they reported was true and **bounded to the highest colour
tier, a bound never stated** — and a highlight-painting defect appearing only
when attributes survive but colour is stripped was invisible to all 169 sessions.

**One accidental strength worth recording:** their harness merges `stderr` into
the pty rather than sending it to `DEVNULL`, so stderr was captured throughout.
Not foresight — they merged the streams because that is what a terminal does.
The instrument that avoided L18's blind spot did so by modelling the world rather
than the question.

**The near-miss, and the aggregate rule earns its keep for the fourth time.**
Running the missing tiers reported **8,529 overflow lines** at `TERM=dumb` where
every other tier reported zero. Before writing it down they dumped the instances:
**every one is exactly 80 columns.** At `TERM=dumb` the product legitimately
ignores terminal size and uses Rich's default width. **The product is right and
the invariant was wrong for that tier.** Reported as an aggregate it would have
been the largest false finding of the day by two orders of magnitude.

**Fixed:** colour tier is now a generated dimension alongside width, with
`expected_width` per tier so the assertion follows the contract. **80 runs — four
tiers, five modes, four widths — no invariant violations**, and every finding now
carries its tier.

### L36. Widening a dimension can invalidate the invariant. The flood is more convincing than the single false positive.

`context-curator`'s addition to L22, and it is the half that bites at the moment
of fixing. L22 says check what your helpers hold fixed. **This says: when you
widen a dimension, the invariant may not survive the widening.** Their width
assertion was correct across every value of every dimension they had varied, and
became wrong the instant they added one they had not.

**A harness that gains a dimension and keeps its old assertions produces a flood
of false findings that reads as a discovery — and a flood is more convincing than
a single false positive, not less.** That is the trap: the fix is the moment of
maximum risk, and the reward for widening looks identical to the failure.

**And the deepest form of L22, in their words: the three tiers never run were not
chosen. They were the defaults of the environment the author happened to develop
in.** A held parameter nobody chose, twice over — first in a shared helper, now
in an ambient environment.

### L37. A quotable clean suite run — and exactly what it does not say

**First quotable suite result on this desk since the disk incident.**

    unintended failures:  0
    intended red:        260 of 260  (needs_no_private_legacy_entry)

All three suites: the contract, the 88 frozen successors, and the 7,315-case
table with its three guards.

**Preconditions verified before starting rather than after** — 22 GiB free,
oracle digest unchanged against the record, route still Python — and disk held at
19 GiB *throughout*, so no write came near short. That is L26 practised before it
is built, and checking during as well as before is stronger than the rule asks.

**⚠ What this result does not say, restated because it is the sentence most
likely to be misread from a clean run.** The 260 intended reds are 260 assertions
that **the route is still Python**. And the greens are not evidence about new code
either: **the byte lock could not have failed on any new Rust module, because
none is reachable from the route it measures.**

This is the concrete form of the warning that has been on this desk all day —
every gate green today is a formality, and it becomes the gate the day the route
flips. A reader arriving later sees an unbroken run of green across a day of
heavy landing and draws exactly the wrong conclusion. **The number that will mean
something is the first run after G4, when those 260 intended reds must all turn
green and the byte lock becomes capable of failing for the first time.**

### L38. `term_dot` closed by proof. Both build modes at zero. The check was still worth making.

**Redundant scaffolding, not unwired behaviour** — and proved rather than argued.
A test compared `Query::term_dot()` against `parse_search_query(".", false)`
field by field over four probes including the empty string, CJK and an embedded
newline. Identical on `pattern`, `case_sensitive`, match behaviour, and — the one
that mattered — on `literal_candidate`, `None` on both sides because `.` is in
the metacharacter set. `reviewer-profiler` reached the same conclusion
independently from the other direction, with no contact between them.

**Why it was worth checking, and this is the part to keep.** `literal_candidate`
drives the ASCII prefilter. Had `term_dot` set `Some(".")` where the general path
sets `None`, a dot query would have gone to the byte gate as a literal and
rejected files it should have confirmed — **fewer results, no error**, and no
gate compares counts as such. **The function being unused is what made it safe,
not what made it uninteresting.** That is the distinction that justifies the class
of check, independent of this instance coming back negative.

**Deleted, with the property kept.** Dead code plus a test about dead code is
worse than either. What replaced it asserts the invariant that made the
constructor look dangerous — **`.` must never carry a `literal_candidate`** —
with the consequence spelled out, so a later widening of
`is_plain_literal_search_pattern` fails with an explanation. That is 22am again:
a test defending a decision rather than a behaviour.

**The second warning was a genuine duplication, and its failure mode was
scheduled rather than possible.** `Action.usage` held each option's usage
fragment while `format_usage` built the usage line from a separate `USAGE_ORDER`
list — two copies of the same fragments, one unread. Nothing could break today,
**and adding an option would naturally touch the Action and not the list**,
producing a help body carrying the option and a usage line without it. The unread
copy is removed and `USAGE_ORDER` is the single authority; the 12-width help
parity test passes unchanged, which is what says the output did not move.

**A false alarm recorded so nobody re-chases it.** Four `never used` warnings on
Pi inline-skill functions in `rust/session.rs` came from a **stale build** and are
absent from a clean one. `split_pi_inline_skills` is called from
`parse_pi_message_entry` on the production path; Pi inline skills are wired.
**A warning from a stale build is indistinguishable from a warning about real
dead code** — the same family as L23, where the perishable artifact is what a
probe finds first, arriving through the compiler instead.

**Tree: 142 lib, 1 bin, 42 doctests, both build modes warning-free, release build
green.**

### L39. The leak is closed. And a harness that honestly reported its own failure was read as noise.

**Closed and verified by diffing the `TMPDIR` listing across a run** rather than
by reading the code — runs now leave nothing behind. The 13 directories present
were **deliberately not deleted**: all 0–7 minutes old, so they are live runs
rather than orphans, and removing one mid-run corrupts the measurement reading
from it. They clear themselves on the fixed probe.

**Snapshot completeness is now a precondition rather than a printed number.** A
partial corpus refuses to produce a verdict instead of producing one over fewer
sessions.

**⚠ The finding underneath, and it is a failure mode this desk has not recorded.**
`mutate_pi.py` carried a mutation anchor that had been **silently wrong since it
was written**. The harness had been honestly reporting `ANCHOR MISSING` the whole
time — **and that was read as noise.**

22x says a gate should print what it covered rather than only whether it passed.
That stands, and this is its limit: **printing is necessary and not sufficient.
A diagnostic that appears routinely becomes invisible, and an instrument being
ignored looks exactly like an instrument being fine.** Distinct from L9 and L19 —
there the instrument was wrong or misaimed; here it was correct, honest, and
unheard. The cure is the one applied above: make it a **precondition that
refuses**, not a line that reports.

### L40. Third confirmed corpus blind spot — Pi user-agent ambiguity. Ruled: build the fixture now.

With the anchor corrected the mutation applies and **catches zero.** The hazard is
**ambiguity resolution in the Pi user-agent envelope**: Python returns nothing
when candidates cannot be disambiguated, and **a port that takes the first
candidate is a guess where Python declines.** That changes rendered content, and
rendered content is search truth.

Third instance of the class, after `<duration_ms>` at 477-of-477 and the branch
tie-break — and `engine-and-codex` found two more in Codex the same day. **Five
confirmed blind spots means the class is a property of this corpus, not a series
of accidents.**

**Ruled: `session-core` builds it now, ahead of staying purely on call.** The
deciding reason is not scope, it is timing: **a synthesized fixture is validated
against the live oracle, and the oracle dies at cutover.** This is the E-section
prerequisite in a new place — cheap now, impossible after — and being on call is
interruptible work while this has a deadline nobody set.

**Built to `engine-and-codex`'s pattern, which is 22t's fourth instrument done
properly:** validate the synthesized fixture **against Python**, never against
the port, and add a **control shape that does occur** in the corpus so the
fixture route is shown to agree with the corpus route.

### L41. Rehearsing the recipe found a cutover that would have failed. And gap 1 dissolved.

**The recipe had gone stale within hours of being written** — not wrong when
written, stale since. It still described gap 1 as an open seam needing a
`SearchPoolFilter → PoolFilter` conversion. **That conversion no longer exists by
design:** `plan::lazy_screen` takes the **raw** filter and never builds a
`PoolFilter`, because the L20 gap-2 ruling requires per-path date parsing.

**So the preserve ruling removed the work rather than adding to it.** Preserving
Python's per-file raising meant there was nothing to convert. Both gaps are now
marked closed in the recipe with how.

**It also called a method that did not exist.** `args.pool_filter.is_empty()`,
where `SearchPoolFilter` had no `impl` block at all. **Found by checking a line
they had written rather than trusting it** — the third time today that discipline
has caught something.

**And the fix was not the obvious one.** Python is `not (provider or dir or
mafter or cafter)` — **truthiness, not presence.** Measured against `ch-legacy`:

    -d ""        -> No sessions match "zzz".                        (unfiltered)
    -d /tmp/g    -> No sessions match "zzz" with the current filters.

An `is_none()` check — the natural port — would have given an empty `-d` the
filtered wording. Implemented as truthiness with both measured cases pinned.

**L11's third form, and the sharpest.** An unrun recipe is not a recipe; a
recipe whose *instructions* were never executed is not one either; and now: **a
recipe correct when written goes stale against a moving tree, so rehearsal is
what makes it a procedure rather than a plan.** The first two were about writing.
This one is about decay.

### L42. The two-readings class widens: one field, two readings, no second library

**Recorded as a widening rather than a third example, because "look for two
libraries" would not find it.**

The same empty string reads two ways inside `SearchPoolFilter` alone:

- `-d ""` and `-ma ""` are **absent** for the no-results wording, via truthiness.
- `-ma ""` is **present and invalid** to the date path, which parses it and raises
  `Invalid date format` once per candidate file. Measured.

One value, two readings, both deliberate, inside a single object.

The first two instances needed a second library — `COLUMNS` through
`shutil`'s `int()` versus Rich's `isdigit()`, and `--color` reaching one console
constructor and not three others. **The signature was "one user-facing option
name read by two libraries where one parser is stricter."** That signature is now
too narrow. The general form: **one value consumed by two code paths that
disagree about what counts as supplied** — whether the paths live in different
libraries, or in one struct.

Neither instance is reachable by reading for naive implementations, because every
individual reading is correct. The defect is only ever in the composition.

Both readings are documented in the code where someone would change them, not
only on this desk.

**Tree: 143 lib, 1 bin, 42 doctests, both build modes at zero warnings, release
green. `search-runtime` is ready for the cutover and the recipe matches the
tree.**

### L43. A negative result is only as strong as the shape you searched for

`context-curator` withdrew a stated negative. They had reported the hunt for a
third two-readings instance **exhausted**, on evidence that still holds — one env
var read directly, every `Console()` site enumerated. The conclusion was wrong
because the shape they were searching for was too narrow: they had written the
class as *one option read by two libraries*, and mistook the library boundary for
the mechanism.

**A stated negative closes a line of enquiry, and unlike a false positive nobody
goes back to check it.** A false positive gets investigated and dies. A false
negative is quoted, relied on, and ends the search.

Recorded as a **withdrawal in the document rather than a quiet edit**, which is
the only form that tells a later reader the line was closed on bad grounds.

Pairs with 22aa and 22ap: those say do not mistake your instrument's limit for
the world's, and do not mistake every null for an instrument limit either. **This
adds the third: do not mistake the shape you searched for for the shape that
exists.**

### L44. ⚠ Both reviewers at 75%, with the whole proof phase ahead. The largest open risk.

| Reviewer | Remaining | Gated on |
| --- | --- | --- |
| `reviewer-profiler` | G3 measurement reviews, slope prediction test, **G5 verification** | engine, `session` |
| `context-curator` | G3 pass two (**6 landed slices**), the four timing economies | timing economies only |

Both report **75% of context window**, both name the quantity, and the session
token budget is untouched at ~14.98M of 15M — the window binds, not the budget.

**`decision-record.md` entry 2 forecloses the obvious fix**: converting either
reviewer costs the review that cannot be replaced, and the structural half is the
only one that reaches the timing economies.

**What was available without a roster decision, and is now done: decoupling.**
`context-curator` had been treating pass two and the timing economies as one
gated queue. **Pass two is not gated — all six slices are landed.** Ordered to
start it immediately and take nothing else.

**The displacement was the first mate's fault and is recorded as such.** Four
findings were routed to `context-curator` after pass two was commissioned — the
harness audit, item 11, the class widening, the stale-desk correction. Each was
individually right to send. **Together they spent the window pass two needed.**
Routing findings to the person with the scarcest context is a cost that is
invisible per message and only visible in aggregate.

**Escalated upward as a roster question**, since it is the captain's: a third
reviewer seat, fresh, taking G3 measurement or structural. Against it: G5
verification rests on accumulated understanding. For it: `decision-record.md`
entry 2's own argument is that review value comes from having **no stake**, and a
fresh session has the most of that — and both `timing-shaped-behaviours.md` and
`g3-review-criteria.md` exist precisely so the knowledge transfers.

### L45. G3 pass two: no defects, one open question, and the coverage stated at the top

`g3-structural-review-02.md`. **No defects.** Coverage is thinner than pass one
and **the document says so at the top rather than the bottom** — 22ae applied by
its own advocate, since a limitation below the result is not quotable and the
result is.

**Grammar passes on all four properties a hand-written argparse emulation gets
wrong:** the `LONG_OPTIONS` table, prefix matching, the ambiguity error in table
order, and the `ch search: error: ` envelope. **Exact-match-beats-prefix is
present at `parse.rs:661–663`**, which is the one that matters — without it
`--list` is ambiguous against itself in any table holding a longer option sharing
its prefix.

**The strip divergence is handled, and its test is the standard for this
mission.** Python's `str.strip()` and Rust's `str::trim()` differ on the C0
separators U+001C–U+001F: Python strips them, Rust does not. All nine candidates
measured. `session.rs:131` defines `python_strip`, applied at **10 sites**, and
`session.rs:356` carries `python_strip_removes_the_c0_separators_rust_trim_leaves`
— which pins the correct behaviour **and asserts the incorrect one beside it**,
`assert!(content.trim().starts_with('\u{1c}'))`. A reader who "simplifies" to
`.trim()` gets a failure that explains what they broke rather than a diff. Third
instance of 22am on this mission.

**The open question, and it is stated as a question rather than a finding.** Bare
`.trim()` remains at **9 sites in `codex.rs` and 23 in `session.rs`** — the file
that *defines* `python_strip`. **Does the Python counterpart at each site use
`.strip()`?** If yes they diverge on C0 separators; if it uses a regex, `shlex`
or a split, bare `.trim()` is correct and there is nothing there. The sampled
`codex.rs` sites are all inside tool-script parsing, a different domain from JSONL
message text.

**Why it is worth asking rather than assuming, in their words: same configuration
as the stderr consoles — the correct helper sitting immediately beside code that
does not use it.** Not evidence of a defect, but exactly where one hides, because
a reviewer sees the correct pattern nearby and assumes it was applied wherever
needed.

**Split rather than routed whole**, to keep it off the critical path: the 23
`session.rs` sites go to `session-core`, who defined `python_strip`; the 9
`codex.rs` sites go to `engine-and-codex`, **queued behind the output modes.**

### L46. ⚠ Four files are unreviewed, and that is recorded rather than papered over

**`color.rs`, `cells.rs`, `plan.rs` and `python_io` were not read.** `codex.rs`
and `session.rs` were queried against strip semantics and grammar only — their
decode logic, ordering and error paths are **unreviewed**.

`context-curator` named this in the document instead of letting the absence pass
as coverage, applying their own L43: a stated negative is only as strong as the
shape searched for, and nobody goes back to check a negative.

**Offered and declined: four thin passes to call the surface covered.** That
would have been worse than the gap, because the gap is visible and a thin pass is
not. **Declining to produce coverage they could not stand behind is the correct
call and is recorded as a decision, not an omission.**

Partial mitigation, stated as such rather than as a substitute: `python_io` was
reviewed by `search-runtime` as a peer, and `color.rs` and `cells.rs` carry heavy
falsified gates — 1,499 oracle rows with hand-written failing mutations, 11,410
cell measurements across four Unicode versions, five mutations caught. **Gates are
not structural review**; they answer a different question.

**This is the concrete scope of the third-reviewer-seat question** now with the
captain: four files to pass-one depth, plus the decode logic and error paths of
two more.

### L47. The C0 strip divergence is real at ~20 sites and invisible to every differential. Ruled: fix it, fixture first.

**Audited by `session-core`.** Roughly 20 of the 23 bare `.trim()` sites in
`session.rs` port a Python `.strip()` or `.lstrip()` and therefore **diverge on
U+001C–U+001F**: custom titles, Codex cwd and its `<cwd>` group, command-tag line
skipping and value normalisation, assistant text blocks, thinking blocks, the
system recap, hook content, Pi skill bodies, Pi compaction summaries, the
user-agent content, its response candidates and its task, and Pi thinking. Two
port `.lstrip()`. **Three are correctly bare:** the `dedent` helper's internals,
which port `textwrap.dedent` and its own whitespace notion, and the assertion
inside the C0 test, which is deliberate.

**Measured before anything was proposed:**

    files scanned:                              5046
    files containing U+001C-001F anywhere:         0
    string values with a C0 separator at an edge:  0

So the divergence is real and **invisible to all 2,436 Claude and 24,367 Pi
differential cases.** Sixth instance of the corpus-blindness class.

**Ruled: option 1 — build the fixture, prove it red, then fix.** Three reasons,
in order of weight.

1. **Zero occurrences in this corpus is an instrument limit, not a property of
   the world** — 22aa, and the fifth time today it has decided something.
   Transcripts carry arbitrary tool output; C0 separators are exactly the bytes a
   dump, a protocol trace or pasted terminal output produces. **This corpus
   belongs to one user. The product does not.**
2. **The charter's line is parity**, and a known divergence at 20 sites is a
   parity break whether or not our corpus reaches it. `python_strip` exists
   precisely because someone already decided this mattered.
3. **The differentials cannot verify the fix, but they can verify it breaks
   nothing else.** That inverts the risk of 20 mechanical edits to a proved file:
   the thing the corpus is blind to is the *behaviour under change*, not the
   26,803 cases guarding everything around it.

**Fixture first, and it must be shown to fail against the current code**, per the
charter's red-before-green rule and per the lesson immediately below. A fixture
built after the fix proves only that the fix is self-consistent.

**The honest counter, recorded because it is right:** `<duration_ms>` was a
defect the prior team actually shipped, and this one is hypothetical. That
lowers the priority — it does not sit ahead of confirmation or the cutover — but
it does not change the ruling, because the cost of finding out later is that the
oracle is gone and the fixture can no longer be validated.

### L48. All three Pi hazards now discriminate — and the first fixture caught zero

**The Pi ambiguity fixture is done and discriminates: the mutation catches 7.**

**Its first version caught zero**, because it omitted the preview — which
short-circuits *before* the check the mutation removes. With both candidates
sharing an opening line, the preview matches equally and the ambiguity path is
actually reached.

**A synthesized fixture can miss the shape it was written for by reaching a
short-circuit first**, and the symptom is identical to the shape not existing —
which is the thing the fixture was built to fix. Same trap as L9 one level over:
there a falsifier fired for the wrong cause; here a fixture fails to fire and the
zero looks like the corpus answer it was meant to replace.

**So a synthesized fixture is not done when it exists. It is done when its
mutation catches something.**

### L49. Third reviewer seat approved: `slice-reviewer`. And a deadline I got wrong.

**`prompts/slice-reviewer.md`.** Scope is exactly the gap `context-curator` named
in L46: `color.rs`, `cells.rs`, `plan.rs`, `python_io.rs` unread, plus the decode
logic, ordering and error paths of `session.rs` and `codex.rs`. Reviewer rules
unchanged — **edits no production source and no tests**, and
`decision-record.md` entry 2 applies to this seat as it does to the other two.

**Roster on the admiral's context figures.** `session-core` **87%** — stopped at
its present seam with a cold-entry handoff, no new scope. `search-runtime` **89%**
and `contract-owner` **87%** — both done, held idle, and only to be woken for a
narrow question inside their own ownership.

**⚠ A correction to my own L47 ruling, and it changed who does the work.** I told
`session-core` the C0 fixture had to be validated before the oracle died at
cutover. **That deadline is wrong.** Decision 13 keeps `ch-legacy search` alive as
a live oracle **through** the cutover, and deletion is its own final slice
afterwards. **The real deadline is the deletion slice, not G4.**

The ruling itself stands: build the fixture, prove it red, then make the ~20
edits. But the urgency I attached to it was manufactured by my own error, and it
nearly put new scope on a session at 87% under an admiral stop order.

**The enumeration is the asset, not the edit.** `session-core`'s handoff carries
which of the 23 sites port `.strip()`, which port `.lstrip()`, and the three
correctly bare — the `dedent` internals and their own C0 test assertion. Rebuilt
from scratch it costs an hour and the three exceptions are the part a rebuilder
gets wrong.

**Owner: unassigned, deliberately.** It is production editing in `session.rs`,
which the new seat cannot do, and every other owner is either on the critical
path or held idle above 87%. It waits for capacity, and it has until the deletion
slice to find it.

### L50. `session-core` stopped clean at 87%, with the C0 fixture proved red

`teammates/session-core/RESUME.md`, 166 lines, cold-entry. Build green, nothing
half-written.

**The fixture landed before the withdrawal reached them, and it landed in the
right half.** Built, validated against Python, and **proved red — 7 mismatches,
one per flag configuration.** So the next owner inherits the step L48 says is the
easy one to get wrong, already done. The 20 edits are untouched, which is the
correct seam to stop at: the hard part is proving the fixture discriminates, and
the mechanical part is what a fresh owner can do safely.

**The handoff carries what exists nowhere else:**

- **The site enumeration by function name rather than line number**, so it
  survives drift — which ports `.strip()`, the two that port `.lstrip()` and need
  a leading-only variant, and the **three that are correctly bare**: the two
  inside `dedent`, which ports `textwrap.dedent` and has its own whitespace
  notion, and their own test assertion that asserts the wrong behaviour on
  purpose. **Those three exceptions are what a rebuilder would get wrong.**
- The corpus measurement with its caveat attached — 5,046 files, zero
  occurrences, **an instrument limit rather than a property of the world**.
- That the differentials cannot verify the fix but **can** verify it breaks
  nothing else.
- The corrected deadline: the deletion slice, not G4.

**Also current in it:** Pi at 24,367 cases with three fixtures and all three
hazards discriminating; the four instrument properties; and the constraints —
including **keeping the `visited` set that this project's own
anti-defensive-programming rules argue for deleting.** That last is a
preserve-because-wrong of a different kind: a guard our house style would remove
on sight.

### L51. `held-parameters.md` — a reviewer writing the input to the question they cannot ask about themselves

Promoted. `reviewer-profiler` wrote it unprompted on learning the new seat would
ask whether their parameterizations were the right ones. For each of their eleven
gates: **what it varies, what it holds fixed, and what it is known to be blind
to.**

**"Every held parameter in that table was found by something escaping through it.
The ones still unlisted are the ones that matter."** That sentence is the honest
form of every coverage document on this desk, and it is the reason the table is
useful rather than reassuring.

**Two questions they state they cannot answer about their own work**, now written
into `prompts/slice-reviewer.md` as the new seat's named task:

1. **Is each parameterization derived or chosen?** Their tool-spec alphabet is
   chosen; their width codepoints became derived only after two false negatives
   from choosing them. A chosen set cannot tell you it collapsed — one of
   `views-and-colour`'s four Unicode oracles was byte-identical to another.
2. **Does the subject actually respond to each swept dimension?**
   `age_pairing_gate` guards this; the other ten do not. A route ignoring an
   input yields one outcome across every value of it, and the sweep then checks a
   fraction of what it reports.

**And where to look first for a fifth bound, in their words: a held parameter
someone *chose* is usually documented; one *inherited from a shared helper's
default* is invisible in every downstream artifact, and the helper's docstring
can be accurate the whole time.** That is how `stderr=DEVNULL` reached six gates
and one differential.

**This is the first time on this mission that someone has prepared the evidence
for a review of their own work before being asked for it.** It is also the
strongest available answer to `decision-record.md` entry 2's worry about an
implementer wanting their own numbers to hold — a reviewer who documents their
own blind spots has given up the ability to be quietly right.

### L52. One harness, two quantities, seventeen-fold apart. Supersedes constraint 24's answer.

`engine-and-codex` corrected the rule this desk adopted from them. Earlier they
reported their harness emits a **session token budget** and not a context-window
percentage. True and incomplete — **it emits both**, and they had only ever seen
one:

    session token budget:  14.49M of 15M left  -  about 3% used
    context window:                              50% used

**Same session, same moment.** Anyone reporting 3% and anyone reporting 50% would
both be quoting their harness honestly and describing different resources.

**This is almost certainly the source of the ten-to-fifteen point discrepancies
across four teammates**, and it is worse than previously recorded: not two
harnesses disagreeing, but **one harness with two quantities**.

**The rule, replacing theirs and superseding constraint 24's open answer: name
the quantity every time, and report the *context window* when only one is
available, because that is the resource that ends a session.** Roster decisions
and admiral pause decisions are made on these numbers, so a 17× ambiguity in them
is a mission-level hazard rather than a reporting nicety.

### L53. ⚠ `re`'s `\s` also matches U+001C–U+001F — which widens the C0 question and corrects a stopped teammate's enumeration

**All nine `codex.rs` sites were wrong**, and the reason is bigger than the fix.
`engine-and-codex` measured **both halves rather than assuming**: Python's
`str.strip()` matches U+001C–U+001F **and so does `re`'s `\s`**. So the
**regex-derived sites diverged too**, not only the `.strip()`-derived ones.

Fixed; Codex differential re-run at **0 mismatches over 8,477 cases, 1,211 of
1,211 sessions.**

**⚠ Consequence for the unowned C0 work in `session.rs`.** `session-core`'s
enumeration — the asset their handoff exists to carry — classified the 23 sites
by asking **"does the Python counterpart use `.strip()` or `.lstrip()`?"** That
question is too narrow. The correct criterion is **"does the Python use any
whitespace notion that includes the C0 separators"**, which includes every
regex-derived site using `\s`. **Their three "correctly bare" exceptions and any
site they cleared as regex-based must be re-checked against the wider
criterion** before the 20 edits are made.

Their audit was not wrong; **it answered the question that was asked of it**, and
the question came from `context-curator` framed around `.strip()`. This is L43 in
production: **a stated negative is only as strong as the shape searched for**, and
here the shape came from the person who raised it rather than from the person who
answered.

**Fourth corpus-blind correctness item.** No script in the corpus contains a C0
separator, so the fix changes nothing on real data — right, and ungradeable by any
amount of it.

### L54. The seam trap is closed structurally rather than documented

`Confirmation` **no longer accepts a `PoolFilter` at all.** It takes the directory
and builds its own, so there is no parameter through which a caller could pass
date strings and turn `-ma notadate` into one fast failure where the product
produces one error per candidate file.

`search-runtime` caught the trap; `engine-and-codex` removed the class rather than
warning about it. **A documented hazard depends on the next reader reading; a
removed parameter does not.** That is the same move as making snapshot
completeness a precondition instead of a printed number (L39), from a different
owner an hour later.

**Last of the engine scope before the cutover:** the four plain output modes, the
plain `HitSink`, and the `Result<Option<SearchHit>, ConfirmError>` → `Confirmed`
adapter that `search-runtime` noticed does not exist. `--raw` last.

### L55. The day's capstone: a short form is true only under a disambiguation that travels separately from it

`reviewer-profiler` assembled five instances and proposed one shape. **The shape
is real and I have tightened its boundary rather than adopting it as stated** —
see below for why, because the looser version would itself be an instance of the
problem.

| Short form | What it denoted |
| --- | --- |
| "zero warnings" | two build modes that disagree (L31) |
| "stdout" | a stream default held by a helper, inherited by seven gates (L18, L22) |
| a table's number | a conditional result quoted without its condition (22ae) |
| "cost-unmeasured" | relayed as "unmeasur**able**" (22aa, 22z) |
| "context %" | two quantities, seventeen-fold apart (L52) |

**Two distinct mechanisms, one cure.** Rows 1, 2 and 5 are *one label, two
referents* — the word is ambiguous and both readings exist simultaneously. Rows 3
and 4 are *qualifier loss* — the claim was unambiguous where it was written and
shed its condition in transit. **Calling all five "one label over two things"
would be a label covering more than it should**, which is the failure it
describes.

**The honest common core, and it holds for all five: a short form is true only
under a disambiguation, and the disambiguation travels separately from it.**
Ambiguity travels by having two referents; qualifier loss travels by being
detachable. Both end with a confident, readable, wrong claim.

**The cure is identical and that is what makes it one rule: the shortest quotable
unit must carry the disambiguation.** Not a note nearby, not a paragraph below.
That is why L52 is phrased "name the quantity every time" rather than "be careful
about context reporting" — an instruction to be careful is itself a short form
that sheds its condition.

**The operational test, applicable before the next number anyone quotes: could
this label denote two things, and does the reading survive being quoted alone?**

**One caveat that strengthens rather than weakens it.** "Five times out of five
when anyone checked" is a selection effect: nobody enumerated the labels that
turned out unambiguous, so the base rate is unknown. The rule stands on the cost
of each instance, not on a hit rate — three of the five produced a wrong claim
that reached another teammate, and one of those nearly buried a real defect.

### L56. An estimate labelled as a measurement — and the hole it exposes in constraint 24

`views-and-colour` corrected themselves unprompted: **the only harness reading
they have received this session was a single automatic notice at 50% context
window.** Their subsequent "48%", "55%", "59%" and "63%" were their own
extrapolation, **reported with the words "harness figure, not an estimate" beside
them.**

**This is worse than the error constraint 24 was written against.** Three
teammates reported estimates *as* estimates and were wrong in both directions —
recoverable, because the label was honest. **An estimate wearing a
measurement's label is unfalsifiable from outside**, and I had been making roster
judgements on those numbers.

**The hole: constraint 24 says report the harness figure rather than your own
count. It assumes you can always obtain one.** Some harnesses volunteer a figure
occasionally and cannot be queried on demand, which leaves a third state the rule
does not name — **no current reading** — and the natural thing to do in that state
is derive one, which is exactly what happened.

**Rule, extending 24 and L52: if the harness has not volunteered a figure since
your last report, say "no current reading" and give the last measured value with
its age.** Never derive. **"Past 50%, unknown by how much" is a usable input to a
roster decision; "63%" that is actually unknown is not.**

**Consequence for the roster: `views-and-colour`'s position is UNKNOWN**, not
63%. They hold views, the coloured sink, highlight painting and the two stderr
items — the largest package that unblocks at confirmation. **Ruled: under an
unknown figure, act at the pessimistic end.** Handoff refreshed now, while there
is certainly room, rather than at a threshold nobody can see.

**Note on the shape:** this is L55's mechanism from the inside. "63%" is a short
form whose disambiguation — *derived, not measured* — was written beside it and
then travelled separately, arriving at me as a measurement. They labelled it
correctly nowhere and incorrectly once.

### L57. `views-and-colour`'s handoff, and three things in it a successor could not rediscover cheaply

Cold-entry, eight sections, written to be taken from without reading anything
else of theirs.

**The two look-alike budgets.** The list row's `width - 2` is **inert** — 22ao,
identical bytes at every width from 2 to 129 over seven headline shapes. **The
panel's title budget looks like the same expression and is load-bearing.**
Reasoning from one to the other is wrong in both directions and **only
measurement separates them.** That is the most dangerous pair on their surface,
because the safe one is documented as safe and the resemblance invites the
transfer.

**The preserve argument for the stderr consoles has to answer a specific
objection.** The **correct** pattern already exists in-tree at
`formatting.py:698`, one file from the three wrong ones. So the case for
preserving is not that the right shape is unknown — a porter can point straight
at it. **Whatever comment survives must say why the wrong shape stays anyway**,
or the next reader fixes it in good faith with the correct version visible from
where they stand. Same configuration as the `python_strip` sites: the right
helper beside the code that does not use it.

**Two constants kept in sync by hand between two owners, which will drift
silently** — see L58.

### L58. Two hand-synced constants across an owner boundary. Close it while both are alive.

`views-and-colour` maintains, by hand, copies of `reviewer-profiler`'s **seven
clock instants** and their `differing_between()`. **The clock instants cannot be
imported because the defining module reads `sys.argv` at import time.**

**This is 22f — import shared tooling, do not copy it — blocked by a mechanical
obstacle rather than by a judgement.** And the failure mode is the worst
available: the copies agree today, they drift on any future edit to either side,
and **nothing fails when they do** — the gates keep passing while measuring
different instants.

**Ruled: fix the obstacle, not the symptom.** Guard the `sys.argv` read behind an
entry-point check so the module is importable, then import. It is small, both
owners are alive to verify it, and **once either stops, the hand-sync becomes
permanent and undocumented.**

Timing is the whole argument: this is cheap now and impossible to close later
without one owner reverse-engineering the other's constants. Same class as
instrument conversion and the C0 fixture — **work whose cost is set by when it is
done rather than by what it is.**

### L59. The third-seat ask rested on an unmeasured bound. The bound was wrong.

`context-curator` corrected themselves: they told me the remaining structural
surface was larger than their window **and never measured it.** The four unread
files are **1,314 lines** — `color.rs` 482, `cells.rs` 513, `plan.rs` 238,
`python_io.rs` 81 — which is about what pass one covered at full depth. They are
at ~78% context window with the session budget untouched. **That is enough.**

**In their words: they asserted a bound without measuring the thing bounded,**
which is the exact failure this desk has spent the day correcting. It caught the
author of L43 — *a stated negative is only as strong as the shape you searched
for* — one rung up: a stated **limit** is only as strong as the measurement
behind it, and an unmeasured limit is the same error wearing a modest face.

**First-mate share of it, recorded because it is the reusable part.** I took
their coverage statement and told the captain it was *"what makes the third-seat
ask concrete rather than a worry."* **A number becomes load-bearing when it is
relayed upward, and relaying is what should have prompted the check.** I asked
nobody how large the surface was; I asked for a seat. The ask was granted on it.

**The seat itself is not withdrawn** — see L60 for why the case survives on
better evidence, and for the split that prevents two reviewers doing the same
1,314 lines.

### L60. Reviewer split, disjoint and by what each knows

`slice-reviewer` is live and was briefed on all six surfaces. **Re-scoped rather
than stood down**, because the case for the seat was always better than the
number I used to make it.

| Reviewer | Takes | Why them |
| --- | --- | --- |
| `context-curator` | `plan.rs`, `cells.rs` | **Accumulated criteria are load-bearing here.** `plan.rs` is where *the native gate stays conservative* lives — `True` must mean semantic confirmation is required, never that the session matches. `cells.rs` is where preserve-because-wrong items 3 and 4 live, and where `views-and-colour`'s second-truncation correction must be honoured. A fresh reader would have to load all of that first. |
| `slice-reviewer` | `color.rs`, `python_io.rs`, **and the decode logic, ordering and error paths of `session.rs` and `codex.rs`** | The larger surface, and the one where fresh eyes are worth most. `context-curator` queried those two files on strip semantics and grammar only — everything else in them is unread by anyone. |

**No overlap, and the reason for the boundary is which knowledge is expensive to
transfer, not which files are convenient.**

**The seat's real case, now stated on evidence that holds:** the timing economies
that arrive with the engine, and G5. Both are ahead of both reviewers, and
`reviewer-profiler` holds all of G5 alone at 75%.

### L61. G3 pass three: `plan.rs` passes, `cells.rs` has a finding

`g3-structural-review-03.md`, both files at full depth.

**`plan.rs` — pass, and it documents its own economies.** The conservative-gate
criterion is met in the strongest available form: **the type is named for it**,
`Gated::Survives` rather than `Gated::Match`. The Pi deferral carries the sentence
a future optimiser has to meet **at the point they would reach for the
optimisation** — *"Deferring is a correctness requirement, not a missed
optimisation."* Timing economy 2 is in the module header: lazy per filter and
short-circuiting, so a file rejected by `-ma` is never opened for `-ca`.

One resolution worth copying: Python had both a length check and a `strict=True`
zip, called redundant by an earlier reviewer. The port has **one assertion with a
stated reason** — a mismatch would misalign every decision in the batch rather
than failing loudly. **Redundancy removed in the direction that keeps the
reason.**

**`cells.rs` — the double-truncation correction is encoded where the next reader
meets it**, in the module header, ending *"a port carrying only the first is
correct at every ASCII width and wrong on the first wide character."*

**⚠ The finding: `cells.rs` reads an ambient input on the live render path.**
Verified three ways by `context-curator`: `CellMetrics::from_environment()` reads
**`UNICODE_VERSION`** and selects a width table from it, with its own doctest
showing `'߽'` at one cell under Unicode 9 and zero from Unicode 14; it is
constructed at `search_run.rs:108` for the `PlainSink` that `stream_search` writes
through, so **not a test path**; and **nothing in the Python route reads it** — no
match in the installed `rich`, in `src/`, or in site-packages.

**Not adjudicated here, and deliberately.** `reviewer-profiler` **has** already
swept `UNICODE_VERSION` — they added it to both sweeps with a probe session whose
characters are *derived* from the table delta, and reported it live under a pty
and inert under a pipe. And `views-and-colour` built `cells.rs` against four
Unicode version tables on purpose. **So the claim "no gate varies it" is wrong,
and the two accounts point in opposite directions** — one describes an input the
native route consults that Python does not, the other was recorded in a sweep
built to find inputs Python consults that the native route ignores. **Direction is
the whole question**, and it is settled by the two people who measured it, not by
me from summaries. Routed to both.

### L62. The 7,384-line generated table is unreviewed, and generated data is trusted by construction

`cell_tables.rs` was **not covered** — `context-curator` checked its consumers,
not its contents. **A wrong entry there is invisible to this review and to any
reader who assumes generated data is correct by construction.**

That assumption is the point. 22ad says a table that re-derives its own answers is
not a fixture; this is the neighbouring hazard — **generated data gets a pass
nobody decided to give it**, because reviewing 7,384 lines by eye is obviously
futile and the alternative is never named. The alternative is to review the
**generator** and its source, which nobody has been asked to do.

Recorded as an open gap with no owner rather than closed by assumption.

### L63. `UNICODE_VERSION` is parity, not divergence. The premise was an `rg` default — third time today.

**Both routes read it.** `views-and-colour` and `reviewer-profiler` reached this
independently.

    rg -n  "UNICODE_VERSION" .venv/.../rich/  ->  0 matches
    rg -un "UNICODE_VERSION" .venv/.../rich/  ->  _unicode_data/__init__.py:67

**`rg` honours `.gitignore`, `.venv` is ignored, and the search silently skipped
the entire directory.** Measured end to end: `cell_len` returns 40 unset and 60 at
`9.0.0`; the same headline renders 31 characters against 20.

**⚠ Standing rule, and it has produced three confident negatives today.** **Any
search that must reach installed dependencies uses `rg -u`.** A `.gitignore`-aware
search over a tree whose dependencies are gitignored returns *zero matches*, which
is indistinguishable from *the thing does not exist*. `reviewer-profiler` hit it,
recorded it, warned `views-and-colour` about it, **and it still caught the next
person** — so a warning in a document is not sufficient protection against a tool
default. It is L55 in a search tool: "no matches" is a short form whose
disambiguation — *within the files I was willing to look at* — travels separately.

**The seam is deliberate and belongs on the live path.** The worry underneath the
question does not apply: **Rich does not use the interpreter's `unicodedata` for
cell width at all.** It ships twenty-one of its own tables and selects one from
that variable. `rust/cell_tables.rs` is those same tables generated from the
installed Rich, so there is no second source of truth that could silently
disagree. **That also closes L62's gap in principle** — the generated table's
correctness reduces to the generator plus the installed Rich, rather than to
7,384 lines nobody read.

**First-mate share, and it is the sixth relay compression.** The two accounts
never conflicted — **they had different subjects.** `reviewer-profiler`'s "the
native route ignores it" was about **the abandoned branch binary**, which predates
`rust/cells.rs`. They labelled it correctly. **I relayed "live under a pty and
inert under a pipe" to two people without the subject**, and the missing word was
which binary.

**What saved it was routing rather than relaying.** I sent both parties to each
other instead of adjudicating from summaries, and that is what surfaced the
dropped qualifier within the hour. **Routing is the backstop for relay error, and
it worked exactly as designed on a relay error of my own.**

### L64. The reverse gate: our sweeps cannot see an input only the native route honours

`reviewer-profiler` found a structural hole in their own sweep and is closing it.
**Its parameterization is "inputs Python honours that the native route ignores",
so an input only the *native* route honours cannot appear in it, however
exhaustively it runs.**

**That is a direction rather than a dimension, and it is the class our gates are
worst at.** A native route consulting something Python does not produces a
divergence with **nothing to disagree with** — the oracle is silent, so a
differential sees agreement. Every instrument on this mission compares two routes
against one another; none asks whether the new one has grown an input.

Building the reverse gate is approved. `views-and-colour` concurred.

### L65. A live wire that is inert today: `search_run.rs:108`

`CellMetrics::from_environment()` is threaded into `PlainSink`. **Harmless and
inert** — cell measurement is reached on the plain routes but cannot change their
bytes, **because the product's own elision counts code points** (preserve items 3
and 4).

**It becomes load-bearing the day anyone repairs `elide_to_width` to count
columns.** That is a coupling between a **preserved-because-wrong behaviour** and
a **threading decision**, and it is invisible from either end: a reader of
`elide_to_width` sees a counting bug with a comment saying keep it, and a reader
of `search_run.rs:108` sees an unused parameter. **Neither can see that fixing the
first arms the second.**

Recorded here because it is exactly the shape 22ao warns about — a line with no
observable consequence today — with the addition that **this one has a named
future trigger.**

### L66. Stop-point findings from `reviewer-profiler` (recorded at the soft-pause)

**A correction inside a live document, made sixty seconds after the error.**
`held-parameters.md` claimed no gate exercises `-d`. **False, with the evidence in
the same command output** — `economy_probe.py` passes `-d /nonexistent-directory`.
The summary was written from expectation rather than from what the search
returned, in a document `slice-reviewer` is reading from.

Corrected to the true and narrower claim: **`-d` is exercised on its no-match
branch only** — the filter excludes everything and the scan short-circuits.
**Directory *matching*, where `-d` resolves against cwd and selects real sessions,
is exercised by no gate at all.** That is the branch where an inherited rather
than chosen `cwd` would bite, so the gap is real; it was described wrongly.
Because promoted documents are symlinks, the correction was live to its reader
immediately (L12).

**The reverse gate's boundary, settled.** The gate as designed asks **"does the
native route respond to this input"** — a byte comparison under two settings. It
**cannot** see a read whose result is discarded, so `search_run.rs:108` reports
clean, correctly.

**Ruled with them: it should not try.** *"Is this input consulted at all"* is not
measurable from outside the process — it needs source reading or instrumentation,
which is **structural review, not measurement.** Answering it from a byte gate
would produce the worst combination available: **a measurement-shaped result
answering a question measurement cannot reach.**

So the split is: **`reviewer-profiler`'s reverse gate covers inputs the native
route *responds to* and Python does not; `slice-reviewer` owns inputs the native
route *consults at all*.** `search_run.rs:108` belongs to the reviewer. The limit
is written into the gate's own docstring rather than only on this desk, so the
next reader meets it at the tool.

### L67. Documentation does not compete with a default

Sharpened by the author of the warning that failed. They hit the `rg`/`.gitignore`
trap, recorded it, **told `views-and-colour` explicitly — and it still caught
`context-curator` twice, once while they were verifying a correction to the first
instance.**

**The only fixes that held today are the ones that changed a mechanism:** the
entry-point guard that made the clock module importable, the generator carrying
foreign stamp fields forward, the `stream=` parameter, the removed `PoolFilter`
parameter, snapshot completeness as a precondition. **Every fix that was a note,
a comment, or a warning was defeated by a default or by a reader in a hurry.**

This is the operative form of the whole day: where a hazard has a mechanism,
change the mechanism. Documentation is for the hazards that do not.

## ▶ SOFT-PAUSE — 2026-08-28, 5h window at 91%

Admiral soft-pause. No hard aborts, no new gates, no spawning, no recovery.
Teammates land safe edits, refresh `RESUME.md`, report an exact stop point, idle.

### Stop points as reported

**`reviewer-profiler` — idle, clean.** `RESUME.md` 280 lines, cold entry.
**The reverse gate is FINISHED, not pending** — built, run and falsified before
the retraction arrived, same as the stderr freeze. **Ruled: keep it, do not
revert.** The order was to start no new work in this window, not that the gate is
unwanted; reverting would be additional work destroying proved work.
*Falsified by swapping subject and reference*, which moves the four forward gaps
to the reverse list and empties the forward list; against the branch the reverse
list is empty. Both ambient sweeps now report both directions.

Their `held-parameters.md` at pause: **the fourth bound is direction**, and two
held parameters are common to all eleven gates — **`cwd`, inherited by every
subprocess and never set**, and **directory *matching* under `-d`, exercised by
no gate.**

**⚠ `reviewer-profiler` holds all of G5 alone, with no second owner.** Their own
statement of why it is the mission's largest gap is the sharpest available and is
recorded verbatim in substance: **not because the work is large, but because it is
the one role that cannot be done by anyone who built the thing — and everyone
else has.**

**`context-curator`** — pass three delivered and accepted, at a clean seam.
**`views-and-colour`** — five-tier differential allowed to land or time out at 40
minutes, being read-only and 29 minutes in; nothing new started. Context position
unknown, past 50%, last measured 50% and stale.
**`engine-and-codex`** — critical path; stop point awaited. Four plain output
modes, plain `HitSink`, and the `Confirmed` adapter were in flight.
**`slice-reviewer`** — about one hour in on `color.rs`, `python_io.rs`, and the
decode/ordering/error paths of `session.rs` and `codex.rs`; stop point awaited.
**Idle before the pause:** `search-runtime` (89%), `contract-owner` (87%),
`session-core` (87%), `query-semantics` (stopped clean).

**Resume order when the window reopens:** `engine-and-codex` first and alone on
the critical path — four plain modes, plain sink, `Confirmed` adapter, `--raw`
last. Then the two sinks, then `search-runtime`'s cutover, which is rehearsed
against the current tree.

### L68. `slice-reviewer`: five confirmed port divergences in `session.rs`, and a correction to a measurement L47 rests on

**Coverage limit, stated first as required.** Read in full: `python_io.rs`,
`search/plan.rs`, `color.rs`, `cells.rs`, and `session.rs` through the Claude
decoder (~line 1180). **Pi decoding and all of `codex.rs` are unread.** Every
verdict is from reading Rust against Python at `8cb4c5f` plus execution of the
**Python** half; **no Rust was run**, so nothing is confirmed against the built
artifact.

**⚠ THE CORRECTION. `session-core`'s "0 files contain U+001C–001F" was over raw
file bytes.** These characters reach a transcript as **JSON escapes**, so they are
not raw bytes. Over **decoded string values** the same pool carries U+001C
**8,044 times in 27 files**, U+001D 7,552, U+001E 8,344 — and also U+000B 8,870,
U+000C 9,367, U+0085 63, U+2028 29, U+2029 7. Instances dumped: mostly binary tool
output (Mach-O dumps, protocol traces), and three of the rarer files are this
mission's own transcripts discussing these characters.

**L47's ruling stands and only its premise sentence is wrong.** The measurement
the strip ruling actually depends on — a separator at a string **edge** —
re-reproduces at **0**. So the `.strip()` sites remain corpus-invisible. **What
the "anywhere" number changes is the other half, which nobody had looked at.**

| # | Divergence | Live? |
| --- | --- | --- |
| **F1** | **`python_io::read_text` drops universal-newline translation.** `session_scan.py:32` is `read_text(encoding="utf-8")` — text mode, so `\r\n` **and lone `\r`** become `\n` before `detect_format` or `decode_jsonl_entries` see anything. `python_io.rs:26` is `fs::read` + UTF-8 decode, fed straight to `session::decode_entries` at `search_confirm.rs:247`. **Executed both sides:** a file holding `{"type":"user"}\r{"type":"summary","summary":"FINDME"}` gives Python **two entries** and the native route **zero** — one unparseable line. Worse for raw transcripts, needing no lone CR: **plain CRLF leaves a trailing `\r` on every line of every message**, and `raw_transcript.rs` is the one module the real corpus provably cannot grade. **One root cause, one fix site, two consequences.** The module's docstring says it models `Path.read_text` and enumerates "exactly two ways it fails" — **the newline behaviour is what it does when it succeeds.** | Corpus has 0 raw CR bytes in 5,047 files |
| **F5** | **`command_tag_regex` lost Python's backreference.** Python: `<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</(?P=tag)>`. Rust: `...</command-[a-z0-9-]+>`. The `regex` crate has no backreferences, **so the port widened the pattern rather than failing.** `<command-name>x</command-args>` fails Python's `fullmatch`, so the block is **not** hidden and the text renders; the Rust matches, so `is_hidden_user_command_text` returns true and **the message disappears.** **Needs no exotic input.** | Reachability **not measured** |
| **F4** | **`str::lines()` is not `str.splitlines()`.** Python splits on **ten** characters — U+000A, 000B, 000C, 000D, 001C, 001D, 001E, 0085, 2028, 2029. Rust splits on one. `session.rs:710` (`command_tag_lines`) ports `parsing.py:572`. A hidden `<command-*>` block containing any of the nine renders as **visible user text** natively and nothing in Python — a byte difference in **search truth**, not chrome. | 0 of 4,129 user text blocks |
| **F4b** | **Four `\s` regexes outside `session-core`'s enumeration entirely** — `session.rs` 766, 790, 1186, 1360. Python's `re` `\s` matches U+001C–001F; the crate's `\s` is `\p{White_Space}`, which does not. **This is exactly the widening `engine-and-codex` applied to `codex.rs`, in a file nobody applied it to.** `session-core` enumerated **`.trim()` sites**, so no `\s` site appears in their handoff. **Four sites to add to the L47 work list.** By specification, not execution. | — |
| **F6** | **`expand_tabs` is a flat 4 per tab; Python advances to the next tab stop.** `session.rs:729` vs `parsing.py:580`. Measured: `"\t"` agrees at 4; `" \t"` is Python 4, Rust 5; `"  \t"` is Python 4, Rust 6. Drives `indent_levels` (`parsing.py:618-625`) — the rendered YAML nesting level, **byte-visible**. | 127 blocks, indents only `''` and 12 spaces, no tabs |
| **F7** | **`dedent` is not `textwrap.dedent`.** `session.rs:741`. Python computes a common **prefix** over `[ \t]` only and blanks whitespace-only lines to `""`; the Rust computes a **byte count** of leading Unicode whitespace and leaves such lines in place. Three divergences **and a panic**: mixed tab/space indentation dedents natively and not in Python; an interior whitespace-only line keeps a residue; and a line indented with a three-byte whitespace character beside a two-space line makes `&line[common..]` **slice mid-codepoint and panic.** | — |
| **F3** | **`branch_map` builds maps by "is a non-empty string" where Python uses key presence and truthiness.** Three sites: `nodes` (Python `if "uuid" in entry` admits a null or integer uuid; Rust requires a string), `leaves` (same for `leafUuid`), and `era_roots`/`active_leaf` (Python truthiness, so an empty-string uuid takes the other branch; Rust `Some`/`None` does not). **The L41/L42 `is_empty`-versus-`is_none` family again.** | 0 over 731,847 entries in 5,047 files |

**⚠ F7 directly corrects `session-core`'s classification, which their handoff
carries as its main asset.** They listed the two `dedent` internals among the
three "correctly bare" `.trim()` sites. **Under the widened criterion both are
wrong, in opposite directions:** `line.trim().is_empty()` ports `l.isspace()` and
is **too narrow**; `line.trim_start()` ports a `[ \t]` margin walk and is **too
wide**. Their third exception — their own C0 test assertion — is correct.

**Clean, and checked rather than assumed.** `color.rs` reproduces `rich/color.py`
including `min_by_key` first-minimal matching Python's `min`, integer redmean,
ties-to-even, and the post-gh-106498 saturation denominator. `cells.rs`
reproduces `rich/cells.py` function by function; its one model-level collapse — a
single global `NARROW_TO_WIDE` where Rich carries one per version — is guarded by
an assertion in `generate_cell_tables.py`, and **all 21 versions verified
byte-identical.** `decode_utf8` reproduces CPython over 20 shapes including large
files.

**F2, `context-curator`'s rather than mine:** `plan.rs`'s
`the_lazy_screen_agrees_with_the_eager_filter_on_valid_dates` is **a drift guard
that cannot fail.** Its only subject is `/definitely/not/here.jsonl`, which yields
no timestamps, so all four filter combinations agree trivially and never reach
`stamp >= threshold`. **Swapping `last_timestamp` for `first_timestamp`, or `>=`
for `>`, leaves it green.** 22i, in a test written by this team.

### L69. The universal-newline mechanism, from both ends in one day

**22b says: never `text=True` on a capture**, because universal newlines rewrite
`\r\n` and lone `\r` and a harness that does so agrees where the implementations
differ. **F1 is the same mechanism from the opposite end: the *product* depends on
universal-newline translation, and the port dropped it.**

One team, one day, one behaviour — recorded once as a hazard to avoid in an
instrument and once as a behaviour that must be preserved in the product. **A
mechanism is not good or bad; it is a fact you must model on whichever side it
sits.** Nothing on this desk connected the two until they arrived a few hours
apart.

### Stop points, continued

**`views-and-colour` — idle, clean, launcher window released.**
Five-tier differential **landed clean**: 140 comparisons over 28 coloured cases
across truecolor, 256-colour, 16-colour, `NO_COLOR` and `TERM=dumb`, **both
streams on separate ptys**, three captures each. **Zero differences**, exit 0 at
~33 minutes inside a 40-minute timeout. **This is the instrument L18 said did not
exist this morning** — every pty instrument on the mission was stderr-blind, and
this one measures both streams across five tiers.

*What it establishes:* the Python route is byte-deterministic under a pty across
all five tiers on both streams, and the launcher's hand-off to `ch-legacy` is
byte-transparent in all of them. *What it does not:* both sides were the same
Python. **The tool prints that caveat in its own output**, so the number cannot be
quoted later as parity.

*Landed, gated, falsified, uncommitted:* `rust/color.rs`, `rust/cells.rs`,
`rust/cell_tables.rs` (generated), `rust/search_views.rs`, four lines of
`rust/lib.rs`. **Half-written: nothing**, verified rather than asserted — three
build configurations green, **148 lib + 1 bin + 43 doctests, zero failures**,
`search_views.rs` byte-matching its pre-mutation backup and the mutation anchors
intact, so **no falsification edit was left behind**. Not started: the coloured
sink, highlight painting, the stderr consoles.

**`context-curator` — idle, clean.** Pass three delivered, nothing in progress.
Finding 3 **retracted in place** with both instrument errors recorded, after
reproducing the `rg` behaviour themselves. `held-parameters.md` written for their
own harness: **six held parameters inherited, three chosen**, with `cwd` and
stdin-always-a-tty named as the two to close first — the piped-stdin input path is
**unreachable from their harness entirely**.

*Their own correction, which supersedes an earlier line on this desk:* their first
stop was reported as a capacity boundary and **was not** — nothing had been
measured and the surface was one pass. Recorded so a successor does not conclude
that a reviewer at 78% can do less than one pass.

*What they would put in front of whoever resumes:* **three confident false
negatives from one tool default in a single day.** Not the finding — the default.

### ⚠ RESUME PRIORITY CHANGED BY L68

The first item on resume is no longer only the critical path. **F5 makes a message
disappear on ordinary input** — `<command-name>x</command-args>` renders in Python
and is hidden natively, because the port replaced a backreference the `regex`
crate does not support with a wider pattern rather than failing. **Reachability
unmeasured.** **F1 is one root cause with one fix site and two consequences**, one
of which lands on `raw_transcript.rs`, the single module the real corpus provably
cannot grade.

Neither is corpus-visible, so **no gate on this mission will go red for either**,
and both are in code that has already landed and been reviewed.

**`slice-reviewer` — idle, clean.** Write-up, cold-entry `RESUME.md`, and **six
read-only probes moved out of the session scratchpad into
`teammates/slice-reviewer/probes/`** — L1 and L23 applied without being asked,
each probe printing what it covered rather than only its verdict.

| File | Reached |
| --- | --- |
| `python_io.rs` | **Complete**, 81 of 81 |
| `color.rs` | **Complete**, 482 of 482, against `rich/color.py` and `colorsys` |
| `session.rs` | **Line ~1180 of 1692** — format detection, entry decoding, provider selection, facets, Claude branch resolution, the whole Claude decoder |
| `session.rs` Pi half | **Not started**, ~1176–1692 |
| `codex.rs` | **Not started**, 0 of 792 |

**Promotion note, recorded because L13 says a rename at promotion made my own
staleness scan blind.** Two reviewers independently numbered a document
`g3-structural-review-03.md`. Desk names: `g3-structural-review-01/02/03.md` are
`context-curator`'s; **`g3-review-slice-reviewer-01.md` is `slice-reviewer`'s
`g3-structural-review-03.md`** — 389 lines, the largest review on the desk.

### L70. The cheapest open task, and a reviewer naming their own failure mode

**F5's reachability is unmeasured and is the cheapest task on the list** — one
scan of user text blocks for a mismatched command-tag pair. Reachability was
measured for F1, F3, F4, F6 and F7; the window ran out at F5, **which is the one
finding severe enough to interrupt a pause for.** Its severity currently rests on
reading two regexes, not on a count. **First item on resume.**

**And the reviewer named the shape of their own output rather than repeating
it.** All seven findings are corpus-invisible on this pool. That is a real result
— and **it is also the shape a reviewer can produce indefinitely without ever
reaching a live defect.** Volume that looks like productivity.

`decision-record.md` entry 4 records that nobody has read the three provider
adapters' normalization rules line by line, and names that as where to look first
if the port surfaces surprises in provider decoding. **That is `codex.rs` and the
Pi half — exactly what they stopped in front of.** It is at the top of their
resume order, with a commitment to say so if the next stretch produces only more
of the same class rather than adding volume.

**The general rule: a method that keeps returning findings of one class is
evidence about the method as well as about the code.** Six instances of
corpus-invisibility is a strong result. A seventh is a weaker one, and a
twentieth would be a statement about the reviewer's search rather than about the
port.

### L71. The basename scan is retired, not repaired

`slice-reviewer` caught that resolving the desk collision created a **source**
collision: two teammate directories each held a `g3-structural-review-03.md`, and
**a scan matching on identical basename finds *a* match and cannot tell you it
found the wrong file.** That is L13 one layer down, in the instrument L13 caught.

**Fixed for their file by renaming the source to match the desk name** —
`teammates/slice-reviewer/g3-review-slice-reviewer-01.md`, symlink repointed,
every desk link verified resolving.

**One mismatch remains and is deliberate.**
`session-core-branch-reconciliation.md` points at
`teammates/session-core/branch-reconciliation.md`. **Renaming the source would
break a live cross-reference inside `session-core-map.md`**, which is promoted,
live, and belongs to a stopped teammate. Recorded here as the mapping rather than
repaired, because the repair costs more than the mismatch.

**And the instrument itself is retired rather than fixed.** The basename scan
existed to find desk copies that had drifted from their sources. **Since
promotion is by symlink there is one byte-stream and drift cannot occur**, so the
scan answers a question that no longer exists. What remains — *are there teammate
documents that should be promoted and are not?* — is a different question that a
basename match cannot answer either, and it needs the first mate's judgement
rather than a command.

**This is L67 applied to my own tooling: where a hazard has a mechanism, change
the mechanism.** The mechanism changed at L12, and the scan is a leftover from
before it. Keeping a repaired version of it would be a documented workaround for a
problem that has already been removed — and would report clean forever, which is
exactly 22l.

### L72. ▶ THE ENGINE IS COMPLETE. The native route runs end to end.

**`run(arguments, home, width) -> i32` exists in `rust/search_run.rs`.** That is
what the cutover's third arm calls. Everything G4 needs now exists.

- **All five output modes done**, not partial: `--only-id`, `--list`, `matches`,
  `--full`, and `--raw` **including its buffering and the single-session
  single-message bare-body case.**
- **`PlainSink` and `BufferingSink`** in `rust/search_output.rs`.
- **`confirmed_from`** — the `Result<Option<SearchHit>, ConfirmError>` →
  `Confirmed` adapter — keeping the two error arms distinct: **a per-file failure
  prints and scanning continues; an undecidable pattern ends the run** rather than
  reporting "no match" to a question the engine could not answer.
- **`probes/searchdriver/`** — the three-arm function standalone, outside
  `main.rs`, **so the route could be diffed before it is live.** That is how the
  charter's ban on an intermediate hybrid was honoured without waiting for the
  cutover to get evidence. `search-runtime` can copy it into `main.rs` almost
  verbatim.

**Proof:** five build configurations green, 148 lib tests, Codex differential **0
mismatches over 8,477 cases at full 1,211-session coverage**, scan-loop
falsification 9 of 9, and the whole-route byte differential at **0 of 54** — 27
command shapes across two widths, comparing stdout, stderr **and exit status**.

### L73. ⚠ THE CUTOVER GATE CHANGES: the 54-case zero is against a 5-file synthetic pool

**The route has never been diffed against real data.** The same differential was
started against the real ~5,000-file pool, exceeded a ten-minute limit, and **was
killed with no output.**

**Ruled: the cutover does not land on the synthetic result.** Cutting over on a
5-file pool would be constraint 22 exactly — a green gate measuring something
narrower than the claim it supports, and this is the claim the whole mission
rests on. **G4's gate is now: the whole-route differential green against the real
pool.** The synthetic zero is real evidence that the route *works*; it is not
evidence that it *matches*.

**The cause of the slowness is known, which is why this is a scheduling item
rather than a risk.** When a query is not eligible for the batched byte gate the
probe returns all-true and confirms every survivor — **correct, because the gate
may only ever reject** — but much slower. **Porting `_term_path_candidate_matches`
closes it.** The run needs an hour rather than ten minutes.

**First on resume**, ahead of the cutover and ahead of everything except F5's
one-scan reachability measurement.

### L74. Two deliberate deferrals and a third duplicated enum

**The coloured sink is unwritten and there is no stub to find.**
`views-and-colour`'s five functions are landed and the trait they build against is
agreed and in the tree. **Start clean** — stated so nobody hunts for a
half-written one.

**`_can_project_dot_only_id` is not ported**; the native route always takes the
authoritative path. **This is not purely a performance item:** if Python's
projection ever disagrees with its own full path, the two routes differ. Open
question, worth measuring rather than assuming.

**Third duplicated enum: `search::parse::SearchOutputMode` and
`visibility::SearchOutputMode`** — same four modes, different order, no
conversion. **Both are `search-runtime`'s, and their own two functions disagree
about which**: `SearchArguments` carries the `parse` type while
`render_no_results_hint` takes the `visibility` one. **Bridged, not unified**, per
the standing `Provider` ruling — `output_mode_of`.

### L75. The route differential's first run found two real defects, both on stderr

**Third and fourth stderr defects of the day**, on the surface every instrument
was blind to until this afternoon.

1. **The native route was not wrapping error text at terminal width**, where
   Rich's stderr console does — **breaking every message longer than the
   terminal.** And a per-file error always carries a full path, so long messages
   are the normal case rather than the exotic one.
2. **`parse_date_filter` rendered its value with Rust's `Debug` quoting where
   Python uses `repr`** — `'notadate'` came out as `"notadate"`.

That file also carried **the same `trim` versus `python_strip` divergence** fixed
in `codex.rs`. Five mismatches to zero.

**The pattern is now unmistakable: every defect found on stderr today was found
in the first hour anyone looked at stderr.** It was not a hard surface. It was an
unexamined one, and it stayed unexamined because a shared helper's default sent it
to `/dev/null` (L18, L22).

### RESUME ORDER — superseding the one recorded at the soft-pause

The engine landing changes it. **The critical path is no longer "build the
engine"; it is "prove the route against real data".**

1. **Whole-route differential against the real ~5,000-file pool.** Needs an hour,
   not ten minutes. **This is now G4's gate.** Optionally port
   `_term_path_candidate_matches` first to make the run affordable.
   `engine-and-codex`'s scope; `probes/searchdriver/` runs it without the cutover.
2. **F5 reachability** — one scan of user text blocks for a mismatched
   command-tag pair. Cheapest open task, and the severity of the mission's most
   serious known defect currently rests on reading two regexes.
   `slice-reviewer`, who holds the most context on the team.
3. **The coloured sink** — `views-and-colour`, clean start, no stub exists.
4. **G4 cutover** — `search-runtime`, rehearsed, recipe matches the tree, and
   `probes/searchdriver/` is nearly copy-verbatim. **Gated on item 1, not on the
   engine.**
5. **F1 and the C0/`splitlines`/`\s` work list** — L47 as widened by L68's F4b
   and F7. Unowned; needs production edits in `session.rs`.
6. G3 review of the Pi half and `codex.rs`; G5.

**What the finish still needs that nobody holds:** G5 verification, which
`reviewer-profiler` holds **alone**, and which by their own statement cannot be
done by anyone who built the thing — and everyone else has.

### L76. Credit correction: the constraint produced the architecture, not foresight

I praised `probes/searchdriver/` as finding a third option against the charter's
ban on an intermediate hybrid. **Their correction: it was not foresight.** They
built it because they **could not test `run` any other way** — the cutover is not
theirs and `main.rs` is not their file, so a standalone three-arm binary was the
only available route to evidence. **The charter constraint and the practical one
happened to point the same way.**

Recorded because it changes how the next reader weighs the rest of their work,
which is their reason for raising it.

**And the observation underneath is worth more than the correction.** The desk's
ownership rule — *coordinate before touching a file you do not own* — exists to
prevent collisions in one shared checkout. Here it **forced a standalone,
independently testable artifact** that also satisfied a charter constraint nobody
was thinking about at the time. A boundary drawn for one reason produced the right
shape for another.

That is the counterweight to every entry on this desk about constraints costing
something. It is also why it should not be read as a general argument: **it worked
here and nobody designed it.**

### L77. G4's new gate is in the owner's brief, not only in a thread

`engine-and-codex` recorded the ruling verbatim in `RESUME.md`: the cutover does
not land on the synthetic result; **G4's gate is the whole-route differential
green against the real pool**; resume order is port
`_term_path_candidate_matches`, run the differential, then cut over.

**And they placed the distinction where it survives quoting** — *the 54-case zero
is evidence the route works, not evidence it matches* — **directly under the
coverage table**, because that is the shortest quotable unit on the page and it is
only true with its pool attached.

That is 22ae and L55 applied by the person whose number it is, to their own
number, unprompted. **A correction that lives only in a message thread has not
been made** (22m); this one is in the document the next owner opens.

## ▶ RESUMED — 2026-08-29, new 5h window at 0%

Five owners dispatched on the critical path. Four held idle or on call.

| Owner | Assignment | Gate |
| --- | --- | --- |
| `engine-and-codex` | Port `_term_path_candidate_matches`, then the whole-route differential against the real ~5,000-file pool. | **G4's gate** |
| `slice-reviewer` | F5 reachability (one scan), then the Pi half of `session.rs` and `codex.rs`. | G3 |
| `views-and-colour` | Coloured sink (clean start, no stub), highlight painting, then the two stderr items. | G4 surface |
| `context-curator` | Timing economies 1, 3 and 4 — unblocked by the engine. Plus folding in `slice-reviewer`'s F2. | G3 |
| `reviewer-profiler` | G3 measurement across the landed slices, then G5. | G3, G5 |

**On call, not woken:** `search-runtime` (89%) — the cutover, gated on the
real-pool differential, not on the engine. `contract-owner` (87%) — the route
flip. `session-core` (87%) and `query-semantics` — stopped clean.

**Unowned and required before G5, not before G4.** The parity work list: F1's
universal-newline fix in `python_io.rs`, and the C0 set — L47's ~20 `.strip()`
sites as widened by F4b's four `\s` sites and corrected by F7's two `dedent`
misclassifications. All corpus-invisible, so **no gate will go red for them and
the real-pool differential will not surface them.** They are parity defects and
the definition of done is exact parity. **First owner to free capacity takes
them.**

**Standing for this window: no side quests unless the work blocks a required gate
or a falsifier disproves the path.**

### L78. ⚠ The 5h window resets the session budget. It does NOT reset anyone's context window.

**First time L52's two quantities have pointed in opposite directions in a way
that matters.** The new window restores the **session token budget** to 0% used.
**The context window is the conversation and carries the whole of yesterday.**

So the true roster capacity on resume is *unchanged from the pause*:
`reviewer-profiler` 75%+ and growing, `context-curator` ~78%, `views-and-colour`
unknown past 50%, `search-runtime` 89%, `contract-owner` 87%, `session-core` 87%.
**Only `slice-reviewer` at 32% and `engine-and-codex` at ~50% have real room.**

**A fresh 5h window buys the team permission to work, not the capacity to.**

### L79. Ruled: G5 skeleton before G3 measurement. `reviewer-profiler`'s reversal accepted.

They proposed reversing the order I gave — G5 first, or at minimum its skeleton —
and the argument is one I took upward myself yesterday. **G3 measurement review is
valuable and replaceable: `slice-reviewer` is live with the most context on the
team, and a missed measurement finding costs a defect. G5 is irreplaceable and
cannot be delegated to anyone who built the thing, which is now everyone else.**
Spending an irreplaceable resource on the replaceable half first is the wrong
order.

**Accepted, with the refinement that makes it not a priority inversion at all.**
**G5 cannot run to completion before the cutover** — the full suite, the package
and installed-launcher proof, and the no-Python proof all require the route
flipped. So "G5 first" can only mean the **skeleton**: the exact command list, the
corpus and route identities pinned, and **each gate run once against the current
tree so its shape is proved.** That is not competing with G3; it is doing the part
of G5 whose cost is set by *when* it is done — the same argument as instrument
conversion, driver preservation and the C0 fixture.

**The deliverable, stated so it survives their session:** a G5 that a successor
can *run*, not one they must reconstruct. If they stop after the skeleton, the
mission has a runnable final proof. If they stop having done G3 measurement
instead, it does not.

**Fallback named rather than left implicit:** if context runs out before G3
measurement, it goes to `slice-reviewer`, who holds the most context and is
already reading the same slices — with the standing caution that measurement and
structural review are different evidence types and the criteria are in
`g3-review-criteria.md`.

**Their two gate-shape questions fold into the skeleton rather than competing with
it**, because G5 runs the gates. One is a real gap: `run(arguments, home, width)`
**takes width as a parameter**, and their ambient gates set width through the pty
— so the engine now accepts width by a path their sweeps do not exercise. To be
measured, not reasoned about. The other — that `search_run.rs:108`'s split still
holds against a real engine rather than a hypothetical one — is a ten-minute
confirmation.

### L80. ▶ G3's timing-economy review is COMPLETE. All four economies preserved.

`g3-structural-review-04.md`, promoted. **This is the review nobody else on the
mission could do** — the four economies are byte-invisible, so no gate reaches
them, and `decision-record.md` entry 2 exists to protect this half specifically.

**Economy 1, per-ID flush — preserved and correctly *scoped*.**
`search_output.rs:308` flushes when the mode is `OnlyId`. The scoping is the part
that needed checking and it is right: Python flushes explicitly in exactly one
place, `_print_session_id` on the `-ll` path, and nowhere else in the streamed
modes. **Flushing everywhere would be defensible and would not match.** `--raw`
buffers through `BufferingSink`, named in the code as "the one mode that could not
stream."

**Economy 3 — preserved, and earlier than required.** Sidechain exclusion happens
during discovery at `inventory.rs:336–339`, so an excluded sidechain never becomes
an inventory row. The economy asked for exclusion before the timestamp probe;
this is stronger.

**⚠ QUALIFIED by L130: all four economies are preserved *in the code*. That says
nothing about whether anything would notice if one stopped — and economy 2's
ordering turns out to be guarded by nothing at all.**

**Economy 4 — preserved, and its test is the standard for this mission.** The one
measured **lost** on the branch. `early_close_stops_scanning` asserts `visited ==
1` **exactly**, with the reason in the code: a bound of `< files.len()` would pass
an implementation that stopped only at the next batch boundary, confirming 256
files. **And it carries a negative control** — `without_early_close_the_whole_
pool_is_scanned` — so the first test is measuring the close rather than an
unrelated stop. **Sensitivity and specificity as a pair, unprompted.**

### L81. A hole in the structural-review method, found by its own author

`slice-reviewer`'s cannot-fail guard in `plan.rs` is confirmed. **`context-curator`
passed `plan.rs` in pass three and did not catch it** — and they diagnosed it as a
hole in the method rather than an oversight.

**Their criteria ask *does the code preserve the property?* They never ask *would
the test notice if the code stopped?*** Those are different questions and only the
first was written down. **A file can pass a structural review with every guard
inert**, because the reviewer reads the implementation against the behaviour and
never the test against the implementation.

**The contrast is inside one pass:** economy 4's test asserts an exact count and
carries a negative control; the `plan.rs` guard has neither **and looks equally
reassuring in a diff.**

**Criterion added to `g3-review-criteria.md` for every remaining pass: for each
preserved property, does a test exist that *fails when the property is removed*?**
Not "is there a test" — **would it go red.** Applies to `slice-reviewer` too.

This is 22i turned on the review rather than on a gate, and it is the third time a
member of this team has found the flaw in their own method by applying someone
else's finding to their own work.

**Coverage stated, as required.** Read at depth: sink selection and the flush
path, the scan loop and early-close handling, and the two named tests. **Not
read:** ~600 lines of `search_engine.rs` outside the scan loop, and
`search_output.rs` beyond the sinks — **unreviewed against non-timing criteria.**

### L82. The serial gate is ported. G4's gate is running.

`_term_path_candidate_matches`, `_evaluate_prefilter`, `_ascii_literal_needle`,
`_term_can_change_under_json_decoding` and `_term_can_match_generated_marker`
ported and wired as the serial probe. **A boolean query over the real pool now
completes in 20 seconds** instead of confirming every survivor. Synthetic
differential still 0 of 54, 148 lib tests, five configurations green.

**Two porting details recorded because they are easy to get wrong:**

- **The two byte gates handle a failed read differently in Python** — the
  JSON-string one swallows `OSError` and answers `true`, the plain one does not.
  **Deliberately converged to both answering `true`**, with the reasoning that
  they converge anyway: a file the probe cannot open is one confirmation cannot
  open either, so it produces the same `[Errno N]` line at the same scan
  position. **Same output, one less branch.** A divergence removed by argument
  rather than preserved by reflex — and the argument is the reason it is safe.
- **`_term_can_match_generated_marker` tests the candidate as a substring of the
  marker, not the reverse.** So searching `too` must **defer** when `--tools` is
  on, because `tool-output` is synthesized text the file's bytes do not contain.
  **Getting that backwards would silently reject real hits.**

### L83. Scale adds branches, not just data — and the real-pool run is not reproducible

**The answer to whether the real-pool differential is the same instrument at
larger scale: it is not, and it was hardened before launching rather than after.**

**Two of the things scale adds are branches the synthetic zero never touched.**
The **256-file batching path** — the structure the whole loop was built around —
**needs 256 survivors before a batch ever forms, so a five-file pool has never
once exercised it.** And the **provider column only appears when the pool spans
more than one provider**, which a Claude-only synthetic pool never does.

**Scale also adds a failure mode the synthetic run does not have.** The real pool
is under active write by this team's own sessions, and the differential runs the
two binaries **one after the other** — so a file changing between the two reads
produces a difference that is **the corpus moving, not the routes disagreeing.**

**⚠ A standing instruction was deliberately not followed, and the substitute is
sound.** This desk's rule is *snapshot, and pass the original path for provider
classification while both sides read the snapshot bytes.* **They did not
snapshot** — the pool is gigabytes and copying it is what filled the disk
yesterday. **Substituted control: every mismatch is re-run before it is reported,
and a difference that does not reproduce is counted as `unstable` and printed as
its own number** rather than dropped silently, because a corpus that moved forty
times is telling you something about the run even when the route is clean.

That is 22x applied to an instability rather than to coverage: the number carries
the diagnosis.

### L84. Keep both differentials. Neither retires the other.

**The real-pool run reaches more branches and is not reproducible. The synthetic
run reaches fewer and is.** They are complementary.

**Ruled: the synthetic differential is not retired as redundant once the real one
is green.** It is **the only one of the two that can be re-run to confirm a
finding** — which is precisely the property L23 and L1 spent yesterday
establishing as the thing that dies first and is missed last.

**The general form, which this desk did not have:** a high-reach instrument that
cannot be repeated and a low-reach one that can are **not** ranked. Retiring the
reproducible one because the other has better coverage leaves every future
question answerable only by a run nobody can trust twice.

### L85. F5 measured: zero, with a falsifier that fires and a permanent one-directional bound

**4,128 user text blocks, 150 mentioning `<command-`, and no block makes the two
patterns disagree.** Both patterns applied with identical line splitting, so this
isolates the backreference from F4's `lines()`/`splitlines()` gap rather than
conflating them.

**The zero is quotable only because the falsifier fires** — L48. `--falsify`
disagrees on four synthetic shapes (a mismatched pair bare and indented, a
three-tag line with an outer mismatch, a two-line block where only one line is
bad) and agrees on three controls. **A probe that catches nothing looks exactly
like a world that is flat.**

**A structural fact that bounds the defect permanently: the wide pattern accepts
a superset of the narrow one, so disagreement is one-directional.** The native
route can only ever hide **more** than Python, never less. **There is no shape
where Python hides a message and the native route shows it.** That bound does not
depend on any corpus and survives every future measurement.

**What the zero does not say, and why F5 stays on the fix list.** These tags are
emitted by the Claude CLI itself, so a mismatched pair cannot come from the
machine. It arises only from a user **pasting** protocol-shaped text — **which is
exactly the input `is_hidden_user_command_text` exists to distinguish from real
protocol**, and exactly what one person's history is least likely to hold. **The
corpus is one user's; the product is not.**

**Ruled: F5 stays on the fix list and comes off the wake-people-up list.** The
severity claim is now bounded rather than unmeasured.

### L86. Seven of seven corpus-invisible — and the reviewer's reading of why

**`slice-reviewer` named the shape of their own output rather than adding to it**,
as they committed to. Two readings, which they cannot yet separate:

1. The port is genuinely sound everywhere the corpus reaches, and the residue is
   all in the tails.
2. **Their search shape — Python built-in versus Rust counterpart, truthiness
   versus type, regex feature the crate lacks — only ever *finds* tail defects,
   because a defect on the common path would already have shown in a
   differential.**

**They judge it mostly the second, which means the class is close to exhausted and
further instances are worth less than the first six.**

**The general rule, and it is the sharpest thing said about method on this
mission: a method's null result is informative only if the method could have found
a non-null one by a route the existing gates do not already cover.** Pattern-
matching for built-in mismatches cannot surface a common-path defect, because the
differentials would have caught it first — **so its zeros say nothing about the
common path, however many of them there are.**

**Which is why the provider decoders are the real test.**
`decision-record.md` entry 4 records that nobody has read their normalization
rules line by line. **A live defect there would be found by reading rather than by
pattern-matching, so its absence would be evidence rather than a property of the
method.** That is the next assignment and it is correctly ordered.

**Criterion 5 landed on the reviewer's own instrument as well as on tests:**
`--falsify` **is** that criterion applied to a probe. Two owners have now arrived
at the same discipline from opposite directions without connecting them until
prompted.

### L87. ▶ G5 is written and partly proved. It is now transferable.

`g5-runbook.md`, promoted. **Fifteen numbered checks, each a command, what it
proves, and its status. Eight runnable now, seven blocked on the cutover with the
reason named.**

**The load-bearing result: check 3 verifies the 68 frozen reference answers
against today's install at 0 drifted, 0 new** — while **31 Rust files and one
`src/` file have changed since the freeze.** So the baseline is still a baseline,
and **the divergences it shows after the cutover will be the port's rather than
drift nobody noticed.** That is the freeze doing exactly the job it was built for,
confirmed rather than assumed.

Check 1 passes on the current artifact: `target/release/ch` links libiconv,
CoreFoundation and libSystem only, **zero undefined `Py_` symbols.** Check 8
enumerates the production diff: 31 rust, 12 tests, 1 src, `Cargo.toml` and lock;
`thoughts` and `.optmem` outside production scope. **And `rust/main.rs` does not
route `search`** — the cutover has not happened, which is what the charter
requires and what makes a skeleton the right deliverable rather than a compromise.

**The runbook carries a "things that will be got wrong without being told"
section** — purge `build/` before the wheel; `exec` replaces the process so the
absence of a Python child is not evidence; the loader trace is void and why; `rg`
needs `-u`; drivers die with their session and a stale one gets found first; name
the subject on every number. **That section is the judgement transfer, and it is
what turns a command list into something a successor can run.**

**⚠ This changes the risk picture that produced L79.** G5 was ruled first because
it was irreplaceable. **It is now substantially transferable** — which was the
point of building it. The single-owner exposure on G5 is materially reduced, and
`reviewer-profiler` spending context on G3 measurement no longer risks the
mission's only unreplaceable asset.

### L88. The width question: the shape change was real, the gap was not

**Answered by measurement rather than reasoning. `search_run::run` has no
callers** — the only occurrence in the tree is its own definition, so **nothing
yet chooses what to pass.** The intended source is `terminal_width()`, which reads
`COLUMNS` then falls back to `ioctl`, **and the existing gates already vary
both**: `colored_width_gate` varies the pty, the ambient sweeps vary `COLUMNS`.

**It becomes a gap only if the wiring passes width from a third source** — and
`colored_width_gate` catches the failure that enables, because a route pinned to a
constant renders identically at 60, 120 and 200, which is exactly what it caught
on the branch. **So the risk lives in wiring that has not happened, and the check
on it is runbook check 7 after the cutover, not a new gate.**

**`search_run::run` having no callers is a fact the cutover owner needs**: the
third arm is the first caller, and it chooses the width source.

### L89. Criterion 5 found a hole on its first trial: two hand-maintained lists with nothing guarding their agreement

`g3-structural-review-05.md`, promoted. Measured before committing this time —
1,343 lines across two files, only ~554 production, and the scan loop and sinks
already read. **That is why it fit, and it was a measurement rather than a
guess.**

**The finding.** `can_use_json_string_gate` at `search_output.rs:397` lists nine
visibility flags **negated**; `gate_bypassed` at `:573` lists the same nine
**positive**. Two hand-maintained lists, **and nothing guards their agreement.**

**The behaviour is faithful today**, including both asymmetries that had to
survive: `message_selection == All` appears only in the eligibility check, and
`tools_requested()` handles both `ToolVisibility` variants — the Rust form of
Python needing `bool()` on a filter list. **Nothing is wrong.**

**But no test names the gate, the bypass, visibility, or the flags.** The named
mutation that should break something and does not: **add a tenth flag to one list
and not the other.** Nothing goes red, the gates diverge silently, and **the
losing direction is invisible to every byte gate** — a search that should have
deferred instead rejects the file, and the output is a missing result.

**Cheapest guard: one table test over the 2⁹ combinations asserting the two are
exact complements.** Queued for `engine-and-codex` after the real-pool
differential; `search_output.rs` is theirs. **Required before G5, not before G4.**

**Why four passes missed it, and it is the clearest possible case for the
criterion.** They ask *does the code preserve the property?* **Here the answer is
yes** — which is why this surface passed unremarked when the same reviewer read it
for economy 1. **Criterion 5 asks the second question and the answers differ: the
property holds, and nothing would notice if it stopped.** Same shape as the
`plan.rs` guard one level up — there a test existed and could not fail, here no
test exists at all. **From a green diff the two are indistinguishable.**

### L90. The criterion has a cheaper inverse, and that is the form to use

**From using it: applying criterion 5 as *"audit every test for falsifiability"*
over 789 lines of tests is a far larger job than the pass that found this.**

**What actually found the hole was the inverse: ask which invariants have no test
at all. Start from the invariant list, not the test list.**

Both questions catch the same class. **The second is far cheaper**, and it is the
form given to `slice-reviewer` for the decoders. The expensive direction audits
what exists; the cheap direction enumerates what should exist and looks for
absences — and an absence is quicker to spot than an inert presence.

**Coverage stated:** read `stream_search`, `flush`, `Gated`, `Confirmed`,
`Outcome`, `confirmed_from`, `truncate_to_cells`, `display_session_id`,
`metadata_block`, `path_candidate_matches`, both bypasses, `format_raw`, both
sinks. **The conservative-gate criterion holds throughout — every bypass returns
`true`, never `false`.** Not covered: the 789 lines of tests, assessed only where
they bear on the criteria.

### L91. ⚠ G4 BLOCKER: there is no session renderer, and the gap is on the commonest command

**`views-and-colour` searched for it rather than assuming: nothing in the tree
turns one message into styled lines.** No function anywhere returns styled lines;
the only renderer, `codecs::render_message_inner_xml`, produces XML **text**.

**Why it is a cutover blocker rather than a scheduling item.**
`SearchOutputMode::Matches` is the **default**, and colour is on by default in a
terminal. Python's `_display_hit` routes `color && (Matches | Full)` to the
conversation panel. **So `ch search foo` typed in a terminal — the single most
common invocation of the product — renders panels, and the native route cannot
produce them.**

**Three options, and one is ruled out immediately.** Ship the coloured default
rendering **plainly** is a visible divergence on the commonest command; the
charter preserves public behaviour, and that is the worst possible place to accept
a divergence. **So the choice is build it or wait — and building it is waiting.**

**Ruled: G4 additionally gates on the session renderer.** Sizing commissioned from
`views-and-colour`, who have just searched the tree and are cheapest to ask.
**Measured, not estimated** — L59.

**Ownership open.** `session-core` owns rendering and is at 87%, so a substantial
new module is very likely beyond them; **their value is specifying what the panel
must do, not building it.** `views-and-colour`'s position is unknown after a
compaction. `engine-and-codex` is on G4's gate.

**⚠ The question this raises about G4's gate itself, routed urgently: does the
whole-route differential cover coloured `Matches` and coloured `--full`?** Either
it does not — **and G4's gate has a hole on the most common invocation** — or it
does and passes, in which case someone has the mechanism wrong, which is worth
knowing before the cutover more than anything else on the board. **If the harness
runs with colour off or captures through a pipe, that is the stderr blindness
again: an instrument that could not see the surface while describing itself
accurately.**

### L92. `ColouredListSink` landed — and its name is why the gap was found now

`rust/search_views.rs`. Renders a hit, owns the pager, counts its own `found`,
emits the summary through `render_summary()`. **Gated on 21,840 rendered hits
driven from real `SearchHit` values rather than pre-built rows, so it gates the
projection — which the row oracle structurally could not.** Six mutations caught:
the falsy-headline shortcut, match count dropping summaries, the provider column
in both directions, an absent age painted as zero, and a summary emitted at zero
hits. Five configurations green; 151 lib + 1 bin + 43 doctests.

**Named `ColouredListSink` rather than `ColouredSink` because it covers only
`--list`.** A name claiming the whole surface would have hidden the missing
renderer until `search-runtime` wired the cutover — **the gap was found by a
naming decision, days before the thing that would have exposed it.**

That is the counter-example to this desk's own L55: usually a short form hides its
disambiguation. Here a name that **refused** to claim more than it covered
surfaced a defect nothing else was looking for.

### L93. The renderer priced: ~3,749 lines on the branch, ~2,500 of them library reimplementation

`session-core`'s day-one analysis, carried by `views-and-colour` because
`session-core` is stopped under an admiral order. **Their numbers, uncompressed.**

The branch's `session_render.rs` is **3,749 lines**, of which roughly **2,500 are
a hand-written reimplementation of two third-party libraries**: Rich's Markdown
renderer, and Pygments — per-language lexers including Python with f-string
expansion and shell with heredoc and arithmetic handling, plus HTML, CSS,
JavaScript, JSON and Markdown, emitting hard-coded Monokai. Map §5 and
`branch-reconciliation.md`.

**⚠ The reframing, and it is theirs: decision 16 already ruled on this surface and
it assumed the renderer would exist.** That ruling accepted colour parity here as
**statistical, not provable** — arbitrary user code pasted into transcripts, in any
language and often malformed, so a fixed-corpus byte diff shows parity on that
corpus and cannot bound divergence off it. The accepted trade was **best-effort
corpus-bounded fidelity behind a byte-diff gate plus a differential fuzz**, with
the change log saying so plainly.

**"That is the thing to re-open now, not to re-argue. The trade accepted was
about the fidelity of a renderer that would be written. The open question is
whether it gets written at all."**

**⚠ What materially changes the cost, and I am flagging it rather than assuming
it: this is prior art that exists, not construction from zero.** Decision 8 rules
the branch is prior art to **reconcile, not rebuild**, and open question 1 records
that on the branch build **the coloured cases — Rich panels, hue cycling, the
80-column layout, highlight painting, and real `less` streaming — reproduce byte
for byte** against `main`'s Python. So the renderer has been observed working.
**Every difference must still be earned in both directions** (decision 18), and
the branch's prose is unreliable while its code is not.

**Correction from `views-and-colour` to their own earlier message: highlight
painting is not a separate item following the renderer — it is inside it.** The
matched-term span is painted into message body lines. **One blocked item, not two,
and its cost is the renderer's.**

**Two interface facts confirmed by `session-core`, recorded so a builder does not
rediscover them:** the sink takes **tokens rather than SGR literals**; and
**`cells.rs` is a dependency of any renderer rather than an optimisation**,
because a per-character width sum cannot reproduce Rich's grapheme walk.

### L94. The cutover arm rehearsed against the finished engine — three corrections

**The `Run` arm is one call, not a composition.** The earlier sketch built
`stream_search` by hand; that is all inside `search_run::run` now, which already
calls `plan::scan_order`, `plan::lazy_screen`, `plan::probe`,
`render_no_results_hint` and `SearchPoolFilter::is_empty`. **Verified by reading
`search_run.rs`, not assumed.**

**The width trap is pinned as a table**, because nothing catches it until runbook
check 7. **Three sources in scope, one correct:** `terminal_width()` is Rich's
rule and belongs to the `Run` arm; `argparse_columns()` is argparse's and belongs
to help and error text; anything else is wrong. **Everything the search renders is
Rich-rendered, so it takes Rich's rule. Passing the other compiles and looks
right.** Independently, `probes/searchdriver/src/main.rs` makes exactly that
split — **so the reference and the recipe agree, which is worth more than either
alone.**

**The eager-filter trap is closed structurally and better than proposed.**
`Confirmation::new` now takes the directory itself, so no date can reach it and
**the wrong call cannot be written.** The recipe's section was kept but reworded
to explain *why the API has that shape* rather than to instruct — **a rule that
cannot be violated does not need restating, but the reason does**, or someone
later simplifies it back to taking a filter.

**Second time today a documented rule was replaced by a structural one**, after
`pager::closed()` becoming a method rather than a public field. L67 in practice.

**And the second time rehearsal caught staleness that reading would not.**

### L95. Measurement confirms the renderer gap — and G4's gate does have the hole

`reviewer-profiler` ran G3 measurement against the real engine through
`engine-and-codex`'s `searchdriver` rather than building a second driver.
**Independent confirmation of L91 from the measurement side, arriving before the
question I routed had been answered.**

    case             engine              python
    colour always    735B  colour=no     2535B colour=yes   DIFFERS
    colour default   735B  colour=no     2535B colour=yes   DIFFERS
    colour never     735B  colour=no      841B colour=yes   DIFFERS
    list mode        898B  colour=no     1057B colour=yes   DIFFERS
    id only           76B  colour=no       76B colour=no    same

**Identical bytes across `always`, `default` and `never` means the flag is not
reaching a colour decision at all** — consistent with `search_run.rs:108`
constructing `CellMetrics::from_environment()` for the **PlainSink**, the sink
this path uses. **So the coloured sink is not exercised by any measurement
runnable today, and G4's gate has the hole on the commonest invocation.**

**Answered for them: it is deliberately not wired yet, and partly not built.**
`ColouredListSink` landed an hour ago in `search_views.rs` and nothing wires it —
`search_run.rs` still constructs `PlainSink`. The conversation-panel renderer does
not exist at all (L91, L93).

**The 50-of-68 drift against 34 for the branch is not a quality signal and was
not reported as one.** The recorded answers are Python's **coloured** output and
the engine is not producing coloured output through this route. **Two of four
`width/*` entries would be meaningless even after the sink lands, because they
compare against colour.** Measuring work in progress and reporting drift counts is
how a reviewer manufactures noise; holding instead was correct.

**What is real from the run: `id only` matches Python byte for byte at 76B** —
the one mode plain by construction. **The plain path produces correct output
wherever the comparison is meaningful.**

### L96. A fifth console ignores `--color`, and this one is Python's own behaviour

**Python emits colour under `--color never`** — 841B with escape sequences.
`flags.color` is False, but the plain path calls
`get_console().rule(title=…, style="#00ffba")` and **the rule styles
unconditionally.**

**Same family as the four stderr consoles**: a `--color` decision that does not
reach every console. **But the consequence is the opposite of the earlier ones** —
this is not a native-route gap, it is **the oracle's behaviour**, so the charter
requires reproducing it. **A native route that honours `--color never` everywhere
would be *more correct* and would diverge.** Preserve-because-wrong, candidate
item, and exactly the class where a competent port silently improves on the
oracle.

Routed to `views-and-colour`, who own the colour seam and found the first four.
Flagged rather than pursued by its finder, correctly — it is not their scope.

### L97. The renderer gap, measured from two sides — and a middle option nobody had

**`search-runtime`: the hole is narrower than "no session renderer" and it has a
defined interface.** `search_views.rs` has the frame and the list rows done with
their own oracle tests. `conversation_panel(body: &[Vec<Segment>], …)` **takes
already-styled lines** and its own comment says it "owns only the frame".
**What is missing is exactly the body** — turning one message into styled lines.
**Produce `Vec<Segment>` per line and the panel closes around it.**

**And the branch's renderer is byte-faithful, not a look-alike — proved rather
than assumed.** They went looking for the sharpest tell: Rich renders a Markdown
`---` as a **dim ASCII hyphen run**, not a box-drawing rule. Measured against live
Rich at width 96: `\x1b[2m` + 96 hyphens + `\x1b[0m\n\n`. **The branch emits
exactly that.** Its `humanize_age` tests cite byte-parity pins from the legacy
function. So the option is **transplant known-faithful lines and reconcile**, the
same shape as B1 — one substantive diff line across 510 moved lines of scanner.

**`views-and-colour`, counting the artifact:** `0ffde41:rust/session_render.rs` is
**3,749 lines in 89 functions with no `#[cfg(test)]` at all — zero tests**, so a
port needs the code **and** its gates. **2,482 lines (66%) are markdown, lexing
and highlighting**, corroborating `session-core`'s "roughly 2,500" independently.
Those reimplement Rich's `markdown.py` (793) and `syntax.py` (985) — 1,778 lines
of library — plus Pygments, **112,447 lines across 259 lexer files**, against
which the branch hand-wrote about eight lexers.

**⚠ THE FINDING, and it creates an option nobody had.** Scanned **1,173 real
session files: 64,013 fenced code blocks, 65 distinct language tags.**

    bash 17.7%  python 15.6%  text 15.1%  typescript 14.8%  sh 14.0%  json 13.1%
    ts 2.0%  yaml 0.9%  tsx 0.9%  js 0.7%  sql 0.7%  html 0.6%
    top 6 = 90.3%   top 15 = 97.8%

**The branch lexes bash/sh/zsh, python, markdown, javascript, css, html, json,
diff and text. It has no TypeScript lexer. TypeScript + `ts` + `tsx` = 17.7%** —
the second-largest family, larger than python. **So adopting the branch's lexer
set buys ~78% of real content, not the ~98% the top-15 figure suggests.**

**That reframes decision 16.** The accepted trade was about **fidelity within
covered languages**. The measurement says the larger exposure is **coverage**:
nearly a fifth of real code blocks fall to the plain-text path — **a visible
difference on content users actually paste.**

**What already exists, so 3,749 is not the remaining work.** The panel body has
exactly **four part kinds** — text, thinking, subagent-task, tool — and
`codecs::render_message_inner_xml` **already walks all four in the same order**.
Part iteration and ordering are ported; what is missing is styling each part
rather than emitting XML. Also landed and gated: frame, title, facts line;
`cells.rs`, which any renderer needs and cannot substitute `unicode-width` for;
`color.rs` for the downgrade. **The hit-to-title and hit-to-facts projection
transfers from `ColouredListSink` at roughly twenty lines. The body projection
does not benefit from it.**

**Nobody gave a duration, correctly.** The artifact and the corpus are
measurable; how long someone takes to write 2,500 lines of library
reimplementation is not, and **an estimate dressed as a measurement is the error
this desk has already recorded twice.** The **fidelity** half is unbounded by
construction; the **coverage** half is now measured at 78%.

### L98. The four options, with the middle one named

| | Route | Consequence |
| --- | --- | --- |
| **A** | Transplant, reconcile, **and add a TypeScript lexer** plus gates | Full parity. Largest single work item on the mission. |
| **B** | Transplant and reconcile, **accept 78% coverage** | **Knowingly ships a visible divergence on ~1 in 6 code blocks.** The tempting option, and it did not exist before the measurement. |
| **C** | Cut over with the coloured default rendering plainly | Visible divergence on **every** panel, on the commonest command. |
| **D** | Hold the cutover | No divergence, no finish. |

**The captain's stated definition of done — every public shape, exact parity —
rules out B and C.** B is the one that most needs an explicit decision, because it
looks like a compromise and is a divergence with a measured size.

**⚠ And nobody is available to do A.** `search-runtime` **90%** and explicitly not
volunteering — *"at 90% I would be starting something I cannot finish"*.
`session-core` 87%, `contract-owner` 87%, `context-curator` 78%,
`reviewer-profiler` 75%+, `views-and-colour` unknown after a compaction. **Only
`slice-reviewer` (~34%) and `engine-and-codex` (~50%) have room, and both are on
required gates.** A needs a new seat.

### L99. Pi decoder: three latent divergences — a new class, and the cheap criterion found the best one in ten minutes

**L90 validated on first real use.** Starting from the invariant list rather than
the test list, on a decoder, took about ten minutes — because **a decoder is
mostly invariants about shapes that must and must not be accepted, and those
enumerate without opening a test file.**

**These are latent — no trigger today — rather than live-but-corpus-invisible.**
Different class from the seat's first seven.

**F10 — the Claude tool-name normalisation happens at a different stage from
Python's.** Python passes the **raw** tool name into
`normalize_tool_input_keys("claude", item.get("name"), …)`; the Rust passes the
**canonical** one, because it normalises first. **They agree today for one reason
only: `TOOL_NAME_ALIASES` has no `"claude"` entry, so the two names are the same
string.** Named mutation: **add one alias under `"claude"`.** Python then looks up
the input-key table by the *native* name and finds nothing; the native route looks
it up by the *canonical* name and renames the keys. **Nothing goes red.** No test
asserts which name reaches that call, and **no corpus can, because it needs a
table entry that does not exist.**

**⚠ The general form, and it is new to this desk: a correct neighbour hides an
incorrect one.** The **Pi path passes the canonical name on both sides**, which is
right — **and sitting next to it, that is exactly what makes the Claude asymmetry
invisible.** A reader comparing the two paths sees consistency and stops. Same
family as *the right helper beside the code that does not use it*, one level up:
there the correct pattern was in a neighbouring file, here it is in the
neighbouring branch of the same function.

**F8 — one expression, two operands, two different notions of truth.** Python is
`message_data.get("isError", False) or bool(details.get("error"))` — truthiness on
both. The Rust is strict `as_bool() == Some(true)` on the first and
`value_is_truthy` on the second. **The tell is that the porter reached for
`value_is_truthy` for one operand and not the other, not the reachability.**
Measured unreachable: across **129,157 Pi toolResult entries** `isError` is a real
bool every time, and `details.error` is a string 306 times and null 148 — both of
which the truthy helper handles correctly.

**F9 — the Pi `toolResult` content default models a state Python cannot
produce.** Python injects `"content": message_data.get("content", [])`, so the key
is **always present**; the Rust sets `has_content: false` when absent. **The
Claude path is faithful** — Python keeps `{**item}` there, so presence is genuine
— **which is what makes this Pi-specific rather than a general modelling
choice.** Measured: all 129,157 entries carry the key.

**Add to the parity work list beside `\s`: `\w` differs between the two engines in
both directions.** Python's is `isalnum()` plus `_`, so it carries `\p{No}` and
`\p{Nl}`; the crate's is UTS#18, so it carries `\p{M}`, `\p{Pc}` and
`\p{Join_Control}`. **One site.** The desk had only ever recorded `\s`.

### L100. What the Pi port gets right, and the first gate that was sufficient

**Recorded as the counterweight, because a review that only lists faults is not
calibrated.** Three things a port normally loses and this one keeps: the synthetic
Skill tool id hashes `f"{id}:{ordinal}"` where Python's f-string renders a missing
id as the literal `"None"` — **the Rust writes `unwrap_or("None")`**. The
index-reassignment asymmetry is exact: **Python's Pi loop reassigns `msg.index`
after parsing and its Claude loop never does**, mirrored by `original_index`
written on keep in `parse_pi` and not in `parse_claude`. And thinking blocks
**overwrite** on the Claude path and **join with `\n\n`** on the Pi path, both
preserved.

**⚠ A data point on the other side of L86, and the reviewer volunteered it.**
`tool_from_json` keeps only `name`, `input` and `id` where Python keeps the whole
item dict — **which reads as dropped keys, and was not reported**, because the
2,436-case Claude differential exercises exactly that path on real tool-use items,
so a renderer consulting any other key would already have failed it.

**That is the first time on this seat that an existing gate was sufficient for
something the reviewer found.** L86 offered two readings of seven-of-seven
corpus-invisibility — a sound port, or a search shape that can only reach tails.
**This is evidence for the first reading**: the corpus does cover the common path,
and the reviewer's method correctly declined to report where it does.

**Two non-findings, recorded so nobody re-chases them.**
`extract_pi_user_agent_response` compiles a regex per call where Python's
`re.compile` is cached — **byte-invisible, so timing-shaped rather than a
divergence**; and the corpus's longest task is 13,894 characters, well inside the
crate's 10 MB limit, so the `Regex::new(...).ok()?` that would silently drop a
message is **not reachable**.

### L101. G4's gate confirmed blind to colour — two independent causes, so one fix cannot close it

**Reported from the harness rather than from memory.** (1) Every case sets
`NO_COLOR=1`, put there deliberately when the coloured sink was unwritten.
(2) Every case captures through `subprocess.run(capture_output=True)`, **so stdout
is a pipe, not a tty.** (3) **No case passes `--color` at all** — zero of 27
shapes mention colour.

**Point 2 is why removing the environment variable would not fix it:** with stdout
a pipe, `flags.color` resolves false through the isatty cascade regardless. **Two
independent reasons colour is off**, so the hole cannot be closed by editing an
environment variable. **It needs both binaries driven under a pty.**

**⚠ What the real-pool green will mean when it lands: "the uncoloured route
matches on 54 shapes over the real pool."** True and useful. **It is not the claim
G4 needs and must not be quoted as one.**

**The stderr shape again, and the accurate self-description makes it worse.** The
harness's own comment reads *"Colour off: the coloured sink is
`views-and-colour`'s and is not wired yet."* **Honest, correct when written, and
exactly the sentence that stops a reader asking whether the gate covers the
default invocation. A harness that describes its blindness accurately still cannot
see.** Third instance today, after `stderr=DEVNULL` and the colour tier held fixed.

**One consequence only the engine owner could supply:** the native route today
would not render the panel *wrongly*, it would render the **uncoloured** form —
`PlainSink` is the only sink wired, so `ch search foo` in a terminal emits a rule
and XML where the product emits a panel. **A whole-output divergence on the
default command, not a styling difference — so a coloured differential fails on
its first case rather than subtly.**

### L102. Ruled: G4's gate is two instruments, and the coloured one is built NOW

**Accepted as proposed.** The coloured half of G4's gate is **`views-and-colour`'s
pty harness pointed at the native route**, not an extension of the pipe-based one.
**Mine covers the modes that pipe; theirs covers the modes that need a terminal.**
Same reasoning as the synthetic-versus-real split in L84: two instruments with
different reach, neither retiring the other.

**And the addition that is mine: build the coloured gate now, before the renderer
exists.** It will fail on its first case, loudly, because the divergence is
whole-output rather than stylistic. **That converts a silent absence into a red
test** — the gap stops depending on three people remembering it and starts
depending on a build going red.

That is L67 applied to the gap itself: **where a hazard has a mechanism, change
the mechanism.** A missing renderer that nothing tests is a fact in a document; a
missing renderer that fails a gate is a fact in the build.

**Sequencing: gate now (red) → renderer → coloured sink wired → gate green.** The
gate's red is the specification.

### L103. ⚠ F12 — a false comment scheduling a wrong refactor. The first finding with a live, measured blast radius.

**Not a defect in shipped behaviour. A defect in a comment — and the comment is
the artifact the next person will act on.**

`codex.rs:278` and `session.rs:1137` are **not** the same predicate, and the Codex
comment says they are:

    codex.rs    thinking.is_some()
    session.rs  thinking.is_some_and(|v| !v.is_empty())

Python is `bool(text or thinking or tools or plan or subagent_task)` —
**truthiness, so an empty string is falsy. `session.rs` is right and `codex.rs` is
wrong.**

**Inside `codex.rs` the difference cannot fire**, which is why the 8,477-case
differential is green: `reasoning()` returns early on empty text so `thinking` is
never `Some("")`, and `plan` and `subagent_task` are never set on that path.
**The trigger is not an input. It is the refactor the comment schedules.** The
comment names `Message::has_content()` in `model.rs` as its real home, says
"matching Python", and calls it **"a five-line change pending its owner's
ruling."**

**Promote that version and `session.rs`'s Claude path inherits it** — and there
`parse_assistant_entry` **does** produce `thinking: Some("")`, from
`item.get("thinking").and_then(as_str).unwrap_or_default().trim()`.

**Measured: 12,911 Claude assistant entries** in the real pool whose only content
is an empty or whitespace thinking block. **Today Python and `session.rs` both
drop every one. Under the promoted predicate every one is kept.**

**And the damage is not 12,911 empty blocks — it is every index after the first
one.** `parse_claude` increments `index` only for a kept message, so **each
resurrected entry shifts the `i` attribute of every message following it in that
transcript.**

**Bounded honestly by its finder:** this needs `show_thinking`, which defaults to
`False`. So the count is the **population**, not the per-invocation impact, and it
reaches only invocations that ask for thinking.

**Fix is smaller than the finding: `session.rs`'s version is already correct and
already matches Python. Promote that one.** Queued for `engine-and-codex`
(`codex.rs` is theirs) after the differential. **`model.rs`'s owner
(`session-core`, stopped at 87%) must be told before anyone acts on the comment.**

**⚠ The transferable rule, and it inverts criterion 5.** The `plan.rs` finding was
a test that existed and could not fail. **This is a comment that exists and is
false, and it carries a scheduled change.** Criterion 5 asks whether a test would
go red; **this asks whether a claim in the code is true.** From a green diff the
two are equally invisible — **and the comment is more dangerous, because a test at
worst fails to catch something, while a false comment actively directs the next
change.**

### L104. F13, F11, and a third instance of the correct-neighbour rule

**F13 — three absent-key defaults on the Codex path, all measured unreachable.**
Python defaults `payload.get("output", "")` where the Rust yields `Value::Null`;
and **Python's `agent_lifecycle_call_ids.add(payload.get("call_id"))` adds
`None`** when the key is absent, so a later output with no `call_id` matches and
is suppressed where the native route renders it. Measured zero across 31,393
`function_call`, 31,385 `function_call_output`, 19,244 `custom_tool_call_output`
and 2,186 lifecycle calls — **every one carries both `output` and a string
`call_id`.**

**F11 — `color.rs` grew a `StyleColor` enum with no caller and no test.** The
palette-versus-triplet distinction is **correct**, verified against Rich: `green`
emits `32` at all three colour systems and `#878c92` becomes `37` at STANDARD.
But `rg StyleColor` finds no caller outside `color.rs`. **Named mutation: collapse
the two arms so a palette colour downgrades with the tier. Nothing goes red — and
that collapse is the exact simplification the enum exists to prevent.**
`views-and-colour`'s file; queued behind their stderr items and the coloured gate.

**Third instance of the correct-neighbour rule (L99), and it demotes F9.**
`tool_result` in `codex.rs` sets `has_content: true` unconditionally with a
comment saying Python always sets the key — **that is F9's fix, applied there and
missed on the Pi path.** Same reasoning, one path away. **It makes F9 a local miss
rather than a modelling disagreement.**

**Coverage, stated as a choice rather than an oversight:** the `codex.rs` script
parser below line 500 is **not read** — it was re-differentialled at 0 mismatches
after its `.trim()` fixes and judged lower value than the decoder. **In the
coverage table as a decision.**

### L105. G4's coloured gate is built and red for the right reason — and the red splits in two

**21 failures.** The reference emits a coloured panel; the subject emits a plain
rule and XML frontmatter. Whole-output divergence, as predicted.

| Failure | Goes green when |
| --- | --- |
| `TIER IGNORED` — **one** output across five colour tiers | the route makes any colour decision at all |
| `g4-list` | **`ColouredListSink` is wired.** It exists, is gated on 21,840 hits, and `search_run.rs` wires only `PlainSink`. **No renderer needed.** |
| `g4-default-matches`, `g4-full`, `g4-matches-no-metadata` | the styled renderer exists |

**⚠ A third of the red is a wiring job against a sink that is already built and
proved.** That half can go green today **without touching the renderer decision**,
and it is the half that proves the sink works end to end rather than only against
an oracle. **It shrinks G4's gate to exactly the renderer**, which sharpens the
captain's decision rather than waiting on it. `search_run.rs` is the engine side;
queued for `engine-and-codex` after the differential.

**The guard fired before the comparison did, and that is the sharper half.**
`tier_responsiveness` reported **one distinct output across truecolor,
256-colour, 16-colour, `NO_COLOR` and `TERM=dumb`** — which proves the native
route **has no colour decision at all**, not that it makes a different one. Same
shape as identical output across `always`/`default`/`never`. **A byte diff alone
would not have said that.**

**An instrument change worth generalising: a guard that aborts hides what it was
guarding.** The responsiveness guards used to abort the run before comparing.
They exist to stop a vacuous *pass* — **and when one fires, the run fails either
way, so aborting only hid the divergence underneath.** They now report and
continue, which is why the gate yields **both** the blindness and the bytes.

**Reproducible, in the brief:**

    probes/pty_differential.py --g4 --subject <searchdriver> \
      --subject-takes-search-token no --widths 72

Subject is `engine-and-codex`'s `searchdriver` — **using theirs rather than
building a second one keeps the charter's single-cutover rule intact**, since
`rust/main.rs` still routes only `parse`.

### L106. Stderr items landed at 120 of 135 — and the remaining 15 are shared-code parity defects

Gated across five tiers and three widths. **The 15 are not `views-and-colour`'s:**

1. **`terminal::wrap_preserving_spaces` counts code points where Rich counts
   cells.**
2. **`terminal_width()` does not return 80 for a dumb terminal**, which Rich does
   **before it even reads `COLUMNS`.**

**Both measured, both in shared code that `ch parse` and `PlainSink` use too** —
so these are parity defects with reach beyond the search route. `terminal.rs` is
`search-runtime`'s, **who are at ~90% and reserved for the cutover arm.**

**Ruled: not assigned now.** The wide-character cases are pinned in an
`#[ignore]`d test **naming the function and the reason**, so the gap is visible in
the build and **turns green on its own** when the fix lands. That is the correct
holding pattern for a parity defect with no available owner — better than a
document entry, because it is in the tree where the fixer will be.

**Added to the unowned parity work list** beside F1's universal-newline fix, the
C0/`splitlines`/`\s`/`\w` set, and F5.

152 lib + 1 bin + 43 doctests, one ignored, all configurations green.

### L107. ⚠ F14 — live today, needs no unusual content, and the fix inverts "faithful"

**The same unreadable file produces two different error lines, and a comment four
lines away says it produces one.** Both halves executed on a `chmod 000` file:

    Python, at the SERIAL gate
      Error processing conversation file /p: Permission denied (os error 13)

    native route, at CONFIRMATION
      Error processing conversation file /p: [Errno 13] Permission denied: '/p'

**⚠ The inversion, and it is why nobody would guess it. Python's gate message
comes from Rust** — `file_contains_ascii_impl` returns an `io::Error`, PyO3 turns
it into a `PermissionError` whose `str()` is Rust's `"Permission denied (os error
13)"`. **The native route's message comes from `python_io_error`, which models
`OSError.__str__` faithfully.** So **Python prints the Rust-shaped line and the
native route prints the Python-shaped one**, for the same file, on the same
stream.

**Ruling: the native route must emit the Rust-shaped string at that call site.**
The charter preserves the legacy route's observable behaviour, and legacy prints
Rust's form there. **`python_io_error` is not wrong — it is too faithful for this
site**, because at this call site Python is not producing an `OSError` of its own;
it is surfacing a PyO3-wrapped Rust error. **Preserve-because-wrong in a new
place: the correct model of the wrong thing.** `search_output.rs` is
`engine-and-codex`'s; queued.

**Second instance of L103, in a second file, and this one fires without a
refactor.** `search_output.rs:591–593` says answering `true` "reaches the same
place: confirmation opens the same file, fails the same way, and **prints the same
line**." It reaches the same place and **prints a different line**. **The batched
arm's comment four lines away is correct** — `_file_contains_ascii_json_strings`
really does `except OSError: return True`. **One file, two comments about the same
swallow decision, one right and one wrong.**

**Fourth class for the tally, and it is live rather than latent.** Not
corpus-invisible in the F1–F13 sense — **a transcript corpus cannot represent it
at all.** It needs a permission change, a `.jsonl` path that is a directory, or
**a file removed between discovery and scan — which is ordinary while nine
sessions write the pool.**

**The gate-conservatism criterion holds, arm by arm:** `Not` always passes so a
negated term can never reject a file; `ascii_literal_needle` defers on all three
of Python's conditions; `term_can_match_generated_marker` tests containment in the
right direction, so `too` defers under `--tools`; and the `.isascii()` clause is
intact with its `ß`-folds-to-`ss` reasoning.

**Third case where the oracle covered something the reviewer found**, continuing
the L86 counterweight. The batched gate excludes `"` and `\`; the serial one
excludes `"`, `\` **and `/`** — read as a false-negative source, **and Python has
exactly the same split**, `frozenset('"\\')` against `frozenset('"\\/')`, because
the batched gate decodes JSON strings itself and does not need the `/` guard.
Faithful.

**And a strengthening of `context-curator`'s two-flag-list finding.** The batched
list at `:397` carries `message_selection == All` and the serial `gate_bypassed`
at `:573` does not. **That asymmetry is faithful to Python** and is safe in the
correctness direction, because `message_selection` makes the render carry *less*
text rather than synthesizing more. **Their finding stands on the unguarded
agreement of the two lists, not on today's contents — which is the stronger
form.**

**Coverage:** read `search_output.rs` 390–650, the gate half. **Not read: the
sinks, `rule`, `metadata_block`, `displayed_messages`, and all of
`search_engine.rs` outside the scan loop.**

### L108. The stderr gate is complete at 135 of 135 — and the holding-pattern test I praised was itself broken

**`search-runtime` fixed both shared-code defects.** `wrap_preserving_spaces` now
measures cells via `CellMetrics`; `terminal_width()` short-circuits to 80 for a
dumb terminal. **`views-and-colour`'s gate covers all 135 recorded cases across
five colour tiers and three widths, zero mismatches.** Off the unowned parity
list.

**⚠ Correction to L106, and it lands on something I recorded as good practice.**
The `#[ignore]`d holding-pattern test — praised as better than a document entry
because it sits in the tree and turns green on its own — **was itself broken. Its
first assertion claimed 37 code points where the real value is 53**, so it
panicked on its own premise and **never reached the behavioural assertion.** It
would have stayed red for a reason unrelated to the defect it named — **precisely
the shape it was written to avoid.** Deleted.

**The replacement is stronger than the original**: `search-runtime`'s test proves
not merely that a wide message breaks, but that **every wrapped line fits the
width in cells** — because `contains('\n')` passes for a wrongly-placed break.

**⚠ Second instance of a shape this desk now has twice: the rule survives, the
example does not.** The first was the hand-rolled panel frame, adopted as the
branch's one earned win, then withdrawn when its *mechanism* proved
incompatible — while the rule it produced (a difference must be earned in both
directions) stood. **Here the pinned-`#[ignore]`d-test pattern is sound and this
instance of it was wrong.** Recording it that way round is the discipline: an
example is evidence for a rule, not the rule, and withdrawing one does not
withdraw the other.

**A gate tightened against a regression nobody had named.** The corpus floor moved
from "more than 100" to "more than 130", with the reason in the failure message:
**nothing is excluded any more, so a lower count means a filter crept back in.**
The old floor would have silently accepted the exclusion returning. 22x — the
number carries the diagnosis.

**`StyleColor::Palette` versus `Triplet` has its reason on the record**, which
partly answers F11: `print_error`'s red is a palette index that stays `31` at
every tier, while the themed hint's grey downgrades. **Collapsing them makes the
highlighter drift with the terminal.** Whether a *test* now guards that
distinction is still open — F11's named mutation was that collapsing the arms
turns nothing red.

**Final state for the seat.** All five configurations green. **155 lib + 1 bin +
43 doctests, zero ignored.** Landed this window: `ColouredListSink` (21,840
hits), the four stderr consoles (135 cases), G4's coloured gate (red by design,
split into a wiring third and a renderer two-thirds), and `StyleColor`. Nothing
half-written; `RESUME.md` cold-entry and current. **All remaining scope depends on
the renderer decision.**

### L109. Ruled: land the arm, and its proof is G5 — the overlap was already there

**`search-runtime` is past 90% context window, self-reported without inventing a
finer figure, and made the distinction that resolves it: landing the arm is cheap,
proving it is not.**

**Landing** is a match with three arms over functions that all exist, with
`probes/searchdriver` as a reference to copy from. One diff. **Steps 5–7 are the
expensive half** — the full suite against a rebuilt binary, the pty differential
at two widths, and the no-Python proof, which needs a full rebuild and perturbs
the shared install. Each is a rebuild plus large output plus iteration.

**Ruled: land the arm; the verification is G5.** They proposed splitting to
"someone with room". **The better answer is that steps 5–7 are a subset of the G5
runbook, which `reviewer-profiler` already owns and has already written** — full
suite, package and installed-launcher proof, no-Python proof, fixed-corpus
performance, scoped diff, with **seven of its fifteen checks explicitly blocked on
the cutover.** The overlap has existed since the runbook was written and nobody
noticed it, because the cutover recipe and the G5 runbook were authored
independently.

**So the cutover does not land unproved and does not need a third party.** It
lands, and the gate that was always going to prove it proves it.

**Their self-assessment, recorded because the reasoning is the reusable part.**
They took two fixes against my ruling and were right that the fixes were right —
measured, small, in their file, blocking a teammate's gate, and leaving parity
defects in shared code reaching `ch parse` and `PlainSink`. **What they名 as
mis-weighed: "idle was not the alternative; the alternative was arriving at the
cutover with more room."** That is the correct form of the error — not *should I
do this work* but *what does doing it cost the thing only I can do*.

**And "a cutover that lands unproved is worse than one that has not landed" is the
right instinct**, which is why the ruling removes the premise rather than
accepting the trade.

**Their remaining bounded task, self-selected and approved:** one more rehearsal
pass over the arm's recipe, targeting the `width` argument — **the last unrehearsed
thing in it**, and now diffable against `probes/searchdriver` rather than reasoned
about. Touches nothing.

### L110. F15 — the provider rule is unported, and its fixtures take the answer as an input

**Routed to `engine-and-codex` before the wiring, which is what makes it guidance
rather than a defect.**

`rg show_provider` over `rust/` finds a struct field and test literals; **no
derivation exists.** Python's `_list_show_provider` returns `False` when `-p`
pinned a provider, otherwise whether the **candidate set** spans more than one —
**hoisted out of the per-hit loop, by its own docstring, so rows can stream
without collecting every hit first.**

**The trap is the natural implementation.** Inside a streaming sink holding hits,
computing the span **from the hits** is the obvious move, **gives a different
answer**, and matching the candidate-pool answer from hits would require
**buffering every hit before the first row** — destroying the economy the hoist
protects. The wrong version is both wrong and more expensive to correct later.

**⚠ And it cannot be caught: `search_views.rs:794` and `:1282` read
`show_provider` out of the recorded oracle as an input.** The fixtures grade the
rendering *given* the flag and never the flag's derivation, so **any wrong rule
leaves all of them green.**

**Third shape, beside the inert guard and the two unguarded flag lists: a fixture
that takes the thing under test as a parameter.** 22ad says a table that
re-derives its own answers is not a fixture. **This is its mirror — a table that
is handed the answer.**

**Highlight painting is absent**, and the only `highlight_spans` in the tree
paints the quoted term in the **no-results hint**, not query matches in message
bodies. **This was the branch's one blocker.** Its guard, specified now because it
lands after this review: **fold per character over the original string using
search truth's own equivalence, and assert on a case where folded and original
lengths differ in both directions — `İ` for growth (2→3 bytes), `ﬀ` for shrinkage
(3→2). A fixture built from ASCII cannot fail, and ASCII is what a first fixture
uses.**

**Checked and correct on the rest of the engine surface:** empty pool exits 1
silently before any scanning, with `search_run.rs:44` stating why it is checked
there; `Outcome::EmptyPool` carries `wants_no_results_hint() == false` against
`NoHits`'s `true`, guarded by comment and test because the collapse changes
observable output; the no-results hint is suppressed in `--list-ids` mode,
matching `_emit_no_results`; and **the mid-window flush-then-error rule holds** —
`Gated::Failed` flushes the accumulated batch and only then emits, with the
comment stating why holding to the end of the batch is *not* equivalent, and with
`batch_size = 1` the flush is a no-op so the error prints immediately, as Python's
serial arm does.

### L111. F11 closes by measurement — and the type arrived before its evidence

Both collapse mutations run against the tree:

    M1  Palette resolved through the triplet downgrade  ->  54 of 135 stderr cases differ
    M2  Triplet resolved through the palette path        ->  30 of 135 differ
    restored                                             ->  155 passed

**The guard is the 135-case stderr corpus, not a unit test — and that is the right
shape**, because the distinction is only observable **across colour tiers**, so a
unit test asserting one tier would have passed both mutations.

**`slice-reviewer` was right when they looked.** At that point the stderr corpus
did not exist and `StyleColor` had been introduced an hour earlier with nothing
exercising it below truecolor. **The type arrived before its evidence**, and the
corpus closed it as a **side effect of gating something else** — F11 was not
closed by writing the test it asked for.

### L112. Why the withdrawn-example shape is cheap: the rule was stated separately

`views-and-colour`'s addition, and it is the mechanism behind both instances.
**In each case withdrawal was possible only because the rule was stated separately
from the example.** "A difference must be earned in both directions" survived the
panel frame because it was written as a rule. "A holding-pattern test names the
function and the reason" survived their broken test for the same reason.

**Had either been written as *"the branch's frame is correct, therefore…"* or
*"this test proves…"*, withdrawing the example would have taken the rule with
it.** The separation is what makes withdrawal cheap — and it is why this desk
writes the rule above the evidence rather than as its conclusion.

### L113. The cutover arm, rehearsed against `searchdriver` — three corrections, one fatal

**1. ⚠ The argument slice is off by one, and nothing type-checks it.** The driver
is its own binary and parses `args_os().skip(1)` entire. **The arm sits after
`main.rs` has already matched the `search` token, so it must parse
`&arguments[1..]`** — where `arguments` is itself already `args_os().skip(1)`.
**Two skips, not one.**

**Both are `&[OsString]`, so the type system cannot distinguish them.** Passing
the whole slice makes `search` the pattern and shifts every real argument into a
positional: **`ch search needle` searches for `search` and reports `unrecognized
arguments: needle`.** It fails loudly and immediately — the good case — **but it
fails at the cutover, which is the moment its owner has least room to debug.**

**2. Warnings print before the match, not before the `Run` arm**, and with
`eprint!` — they carry their own newline. The recipe's wording would have dropped
a warning on any other outcome that carries one.

**3. `home` is `std::env::var("HOME")`** — not `dirs`, not a constant. The driver
uses `.expect("HOME")`, which in `main.rs` is **a panic on a missing variable**.
**That needs deciding rather than copying**, and it is a parity question: what
does `ch-legacy` do with `HOME` unset? Measurable in one command. Queued for
`engine-and-codex`, who own `searchdriver`.

**The width split was already right** — `argparse_columns()` for both text arms,
`terminal_width()` for `run` — **and it was the thing the rehearsal set out to
check.** The value came from the diff catching what nobody was looking for.

### L114. Rehearsal has now beaten reading three times, and the pattern is specific

**A stale gap-1 conversion. A method that did not exist. An off-by-one invisible
to the type system.**

**In each case the prose was written by someone who understood the code and was
wrong anyway.** That is the precise form — not carelessness, not
misunderstanding. **Understanding the code is what produces prose confident
enough to be trusted, and it does not make the prose correct.**

The three failures are also three different mechanisms: **the tree moved**, **the
author assumed an interface that was never built**, and **the type system gave
false assurance because both values had the same type.** No single check catches
all three. **Executing the instructions does.**

This is L11's family — an unrun recipe is not a recipe — arriving at its sharpest
form: **the recipe was rehearsed twice before and still had a fatal error, because
each rehearsal was against a different version of the tree.** Rehearsal is not a
one-time gate.

### L115. F16 — two `truncate_to_cells`, same name, different semantics, one module importing the correct one

`cells.rs:304` is public and models Rich: above the limit it goes through
`set_cell_size`, **which pads with a space when a double-width character cannot
fit**. `search_output.rs:115` is private and accumulates characters to the budget
then appends the ellipsis — **no padding**. `"你好你好"` at limit 6 gives
`"你好 …"` (six cells) from one and `"你好…"` (five) from the other.

**Measured unreachable: all 4,693 native session ids in the pool are ASCII and no
filename stem is non-ASCII**, and `rule()`'s only title is a session id.

**Recorded for what it is rather than what it does.** Standing constraint 4 is *a
copy that compiles is not an extraction*. **This is the harder version — not a
copy but a divergent reimplementation under the same name, in a module that
already imports the correct one.** And the `rule` oracle cannot separate them,
because **a recorded corpus of ASCII session ids never reaches the padding
branch.**

### L116. A deliberate divergence that was documented only in code

`display_session_id` takes the native id from entries **already decoded during
confirmation**; Python's `get_display_session_id` **reopens the file**. Both
extraction rules agree and the Rust comment says why the choice was made.

**It is still a divergence in the direction this mission watches most closely** —
more consistent, one fewer read, **observable only if the file is rewritten
between confirmation and rendering, which a live pool can do.**

**Added to the deliberate-divergences table above.** It had been documented in the
code, which is where a porter meets it, **and nowhere a change log is assembled
from.** `final-change-log.md` is a G5 deliverable and does not exist yet; the
table in this document is what it gets assembled from. **A divergence recorded
only at its call site does not reach the change log** — the same shape as a
correction that lives only in a message thread (22m).

### L117. Fourth oracle-covers-it case, and two instrument slips worth more than they cost

**Checked before reporting: `metadata_block` interpolates summaries and titles
into `"..."` unescaped — and Python does exactly the same**,
`f'matched_summary: "{summary}"'`. **69 summaries in the pool contain a double
quote and both routes produce the same broken YAML.** Fourth case where the oracle
covered something this seat found, continuing L86's counterweight.

**Two instrument slips, both caught because the result was absurd rather than
because of care.** `\\w` written inside a heredoc made a probe report that `é` is
not a word character. And `rg -rn` typed twice — **`rg` reads that as `--replace
n`**, so a source listing came back with every match rewritten to the letter `n`.

**The generalisation, and it is 22b turned on the reviewer's own tooling: a
mistyped flag produces a plausible wrong result as readily as an absurd one, and
only the absurd ones announce themselves.** Both of these were obvious. **A
subtler flag error would have produced a plausible listing and been quoted.**
That is the standing argument for the `--falsify` habit on probes, and it now has
two instances from the person applying it.

**Coverage correction, volunteered:** `search_engine.rs` outside the scan loop was
reported unread and then read in the same pass — `Outcome`, `exit_status`,
`wants_no_results_hint`, `stream_search` and `flush` are covered. **Genuinely
unread: only the `HitSink` trait's own tests.**

### L118. ▶ RENDERER RULING: Option A. New seat `message-renderer`.

**Captain's ruling, 2026-08-29: transplant and reconcile the prior styled message
renderer, add TypeScript-family lexer coverage, and build its gates.** Exact
parity and one Rust authority control. **Option B knowingly diverges on about one
in six code blocks, C diverges on every panel, D cannot finish.**

**This is the critical path.** `prompts/message-renderer.md`.

**Scope:** turning one message into styled lines, and **highlight painting, which
is inside that package rather than after it.** Everything around the body is
landed and gated. `conversation_panel` already takes `&[Vec<Segment>]` and owns
only the frame; `render_message_inner_xml` already walks all four part kinds in
order. **The seat produces `Vec<Segment>` per line.**

**Its gate exists and is already red** — `g4-default-matches`, `g4-full` and
`g4-matches-no-metadata` go green when it lands. `g4-list` and `TIER IGNORED`
belong to the wiring job queued for `engine-and-codex`.

**Unchanged by this ruling:** `engine-and-codex` stays on the real-pool
differential and its queue; `slice-reviewer` stays on G3.

**What the ruling changed about decision 16, stated in the prompt so it is not
re-argued:** that decision settled **fidelity** within covered languages as
statistical and corpus-bounded. **Coverage is now a requirement** — the 78%
lexer set was explicitly rejected.

### L119. `message-renderer` is live. Ownership split: oracle/interface versus implementation.

**Captain's boundary, and it holds in both directions.**

| | `views-and-colour` | `message-renderer` |
| --- | --- | --- |
| Owns | `cells.rs`, `color.rs`, `ColouredListSink`, the pty differential, the 135-case stderr corpus. **The interface** — `Vec<Segment>`, tokens rather than SGR literals, what `conversation_panel` expects. **Gate interpretation.** | **`rust/session_render.rs` exclusively.** The styled body, highlight painting, the TypeScript-family lexer, and the gates for all of it. |
| Does not | write the renderer | touch those modules without asking |

**This is the right shape for `views-and-colour`'s position**, which is unknown
and two windows stale: answering interface questions and reading gate output costs
a fraction of implementing, and the role degrades gracefully if they hand it on.

**The most valuable thing handed to the new seat is a red gate.** They arrive to a
specification that is a **build result rather than a document** — three named
cases that go green when they land. `views-and-colour` built it knowing it would
fail, **before the thing it tests existed.**

**Roster reality passed to the new seat, since most of the team cannot help
them:** `search-runtime` past 90% and reserved for the cutover arm;
`session-core`, `contract-owner` and `context-curator` stopped or on call with
cold-entry `RESUME.md` files to read rather than ask; `engine-and-codex` on the
critical-path differential and not to be interrupted; **`views-and-colour` and
`slice-reviewer` are the two they may talk to freely.**

**And the shape of their evidence, stated because it is easy to get backwards:**
nothing they are porting has ever failed a test, because the branch has none. **A
green suite tells them only that they have not broken what exists.** Their
evidence is the coloured gate turning green and the mutations they write for what
they land.

### L120. `renderer-options.md` promoted — and B's stage 1 is a subset of A, not an alternative

Two measurements that post-date the captain's Option A ruling, both material:

**Only 3.6% of session entries reach a highlighter at all** — 3.0% carry a fenced
block, 0.6% are `Read` results, over 750 files and 248,672 entries. **Markdown is
the opposite: it applies to every text part**, since Rich renders all body content
through it.

**And the styling divides cleanly.** Outside a fence, markdown output is
**attribute-only** — no colour. Inside, Rich paints a Monokai background per cell
plus a per-token foreground. **Geometry and background are separable from token
colours.**

**Ruling: Option A stands and the seat sequences markdown and structure first.**
B's stage 1 is a **subset** of A rather than an alternative, so sequencing costs
nothing and gains the provable half landing against a live oracle while
`ch-legacy` still exists. **The only question B actually raises is what stage 2
is**, and that does not need answering yet.

**⚠ One consequence the captain has not weighed, and it changes A's cost by an
order of magnitude.** If fence-interior parity is statistical by construction —
already conceded in decision 16 — **a Rust highlighting crate reaches the same
*class* of result for a fraction of 2,482 lines.** It buys no parity the
reimplementation buys. Worth deciding deliberately rather than by default,
**and it is a decision about stage 2 only.**

**One cheap verification before relying on the staging**, unverified by its
author: **that omitting token foregrounds leaves the fence's line count, padding
and background byte-identical.** The structure was measured to separate; a
no-highlighting variant has not been rendered end to end.

**Also on the record from the brief: option C is more expensive than it looks.**
The charter forbids an intermediate hybrid, so holding the cutover means holding
the sink, grammar, engine and stderr work too — not only panels.

### L121. ⚠ The stderr freeze cannot tell `NO_COLOR` from `TERM=dumb` — and L17 was already in the data

**Computed from `frozen_reference.json` alone, no re-run:** both settings produce
**byte-identical output on stderr**, because the no-results hint carries colour
and no attributes, so *attributes-only* and *suppressed* coincide there.

**`rust/color.rs` documents those as two of three distinct rendering states**, and
its own comment says why: `TERM=dumb` emits no SGR at all while **`NO_COLOR`
strips colour and keeps the attributes**, and *"a renderer that collapses them
drops the bold from every styled span of every `NO_COLOR` invocation."*

**Named mutation: collapse `AttributesOnly` into `Suppressed` in the stderr
console. The stderr baseline stays green.** The pty stdout sweep catches it; the
freeze does not.

**Time-sensitive rather than a G5 note.** L28 froze that baseline **specifically
so the stderr port would have something durable to measure against**, on the one
surface with a known baseline divergence. **It is sound for what it covers and
blind to the exact distinction the module exists to preserve.** Cheapest fix is a
**fixture** change, not a code change: **one stderr shape carrying a bold or
italic span separates the two states.** Routed to `views-and-colour` before they
finish.

**⚠ And the sharpest observation of the day: L17's defect was already in the
frozen data.** The `stderr` dimension's four shapes collapse to two —
`no-match == no-match-colour-always == no-match-colour-never`. **L18 says that
defect lived in the blind spot of every instrument and needed a purpose-built
inverted probe. `freeze_references.py` had recorded the evidence; nobody asked the
data that question.** L39 one level over — **there a diagnostic was printed and
read as noise; here a result was stored and never queried.**

**The method needs no mutation and no re-run: for each swept input, compare the
recorded bytes at its two settings. Identical bytes mean the input moved nothing,
so every row the sweep reports for it could not have failed.** It **reproduces
three of this desk's existing conclusions from frozen data alone** — 22af's
disjoint pty/pipe subsets, its ruling that `LINES` and `TTY_INTERACTIVE` are
genuinely inert, and L21's exactly-three-inputs-on-stderr. **That agreement is why
the two new results are trustworthy, rather than the other way round.**

**A chosen set that demonstrably collapsed** — the empirical proof
`reviewer-profiler` said a chosen parameterization cannot give itself: **two of
their six capability tiers, `16 colour` and `8 colour`, are byte-identical**,
because Rich maps both to `ColorSystem.STANDARD`. **One of six tiers proves
nothing the other does not.**

**And 22c caught on their own aggregate before it reached anyone:** a first cut
counting distinct outputs *per dimension* gave "13 of 18 identical", which reads
as a finding — and the collapsed group is every input's **unset** setting, which
should match the baseline.

**Stated limits:** covers only gates whose outputs are recorded bytes; **six gates
whose outputs are numbers or verdicts still need a designed mutation** for
question 2, and none was designed. And the frozen file records the **reference**
route, so **nothing here is a statement about the port.**

### L122. Oracle-role succession named before it is needed

**`views-and-colour` reported a current harness reading: 75% of the context
window, volunteered rather than extrapolated.** Their own assessment: a quarter is
plenty of *questions*, and **not enough to absorb a surprise** — if a question
needs a **new instrument** rather than a run of an existing one, that is the
handover point.

**Trigger made explicit so it is not decided under pressure**, and **successor
named: `slice-reviewer`**, at 60%, who have just spent a pass inside
`frozen_reference.json` and the capability tiers and therefore **already hold the
instruments' shape rather than needing to learn it.** They message each other
directly.

**What makes the handover cheap is that it was prepared before it was needed:**
`RESUME.md` names the role and the boundary, and **the five hard-won facts reached
`message-renderer` in full with their numbers** — tokens rather than SGR literals
and why the branch cannot downgrade, `cells.rs` as a dependency with its 238-case
figure, the `StyleColor` collapse at 54 and 30 of 135, the five renderings, the
two look-alike budgets, and the stderr pattern sitting one file from the wrong
ones. Plus the two scoping facts: no TypeScript lexer at 17.7% of real fenced
blocks, and `Read` results lexed **by file extension** rather than fence tag.

**Two tasks, and only one was assigned.** The **fixture change** — one stderr
shape carrying a bold or italic span, separating `NO_COLOR` from `TERM=dumb` —
protects the baseline the port is measured against and the blindness is live now.
**The end-to-end no-highlighting verification is deferred**, because it matters
only for stage two, stage two is unstarted, **and its shape is an open
captain-level question** — if a Rust highlighting crate wins, the verified thing
is not the thing that ships.

### L123. Correction: the freeze is blind, the stderr corpus is not — and the fix needs no synthetic fixture

**I routed the fixture to the wrong owner.** `views-and-colour` ran the named
mutation rather than assuming: **collapsing `AttributesOnly` into `Suppressed`
turns 9 of 135 of their stderr cases red.** Their corpus catches it. **The
blindness is in `frozen_reference.json`, which is `reviewer-profiler`'s
artifact.**

**The mechanism, which makes the fix concrete rather than a search for a shape.**
Rich's `repr.brace` is `Style(bold=True)` — **bold with no colour.** So **any
message containing a brace carries an attribute that survives `NO_COLOR` and
disappears under `TERM=dumb`.** Three of their nine messages contain one, and
those three produce the nine.

**And no synthetic fixture is needed.** `[Errno N]` is emitted by the real product
on **every** per-file error, so a directory in the pool or `-ma notadate` produces
one naturally — **the baseline stays made of things the product actually says.**

**⚠ A second separator that is also invisible if the freeze captures at 80 only.**
The two states diverge on **width** independently: **`TERM=dumb` pins Rich to 80
columns before `COLUMNS` is read**, so at any width other than 80 they differ on
wrapping **even with no attribute present.** If the freeze is single-width, the
brace fixture carries the whole load alone.

**Their own tiers did not collapse, and they had to compute it to know.** No two
of their five are identical anywhere — every pair separates on at least **13 of
27** case-slots; the three coloured tiers separate on 15 of 27, and the 12 that do
not are messages whose only colour is a **palette index**, since Rich's `"red"`
and `"yellow"` emit `31` and `33` at every depth while a themed triple
downgrades. **A negative result, computed rather than assumed** — which is
`reviewer-profiler`'s own point arriving in someone else's instrument.

**Deferral accepted with a better reason than the one I gave.** They had called
the no-highlighting verification cheap; **the objection is that its *subject* is
undecided.** If the crate answer wins for stage two, the verified artifact never
ships. **Verifying an artifact whose shape is an open question is how you get a
measurement nobody can use.**

### L124. Two careful readers, opposite conclusions, one wrong shared premise

**The chain, and it is worth more than the finding.** `slice-reviewer` found the
freeze cannot separate `NO_COLOR` from `TERM=dumb` on stderr — holds, 37B vs 37B.
They proposed adding a stderr shape carrying an attribute. **`reviewer-profiler`
ruled that impossible** from the three stderr consoles' styles, none of which
carries an attribute, and **reclassified the defect as undetectable in the
product.** **`views-and-colour` ran the mutation: 9 of 135 red.**

**The mechanism both missed: the attribute does not come from the console style,
it comes from the message content.** Rich's `repr.brace` is bold with no colour,
so **any message containing `[ ] { } ( )` carries an attribute** that survives
`NO_COLOR` and vanishes under `TERM=dumb`.

**⚠ The rule: when two careful people reason to opposite conclusions from the same
reading, suspect the shared premise rather than one of the readers.** Both were
looking one layer too high. That is 22y — a claim confirmed only by reading is a
lead, not a result — **costing two rounds among people who all know the rule, and
settled by the oracle owner in a single measurement.**

**Net:** the gap is in the freeze, not in the product; **the original proposed fix
was available all along** through output the product already emits. **Actionable
form is two things, both natural product output:** an entry whose message carries
a brace, **and stderr capture at a width other than 80** — because `TERM=dumb`
pins Rich to 80 *before `COLUMNS` is read*, separating the states on wrapping at
**13 of 27 case-slots**. `reviewer-profiler` has both.

**And they corrected their own unfalsified list from six to five.** `economy_probe`
**is** falsified — in both directions, **by two real subjects rather than a
designed mutation**: branch binary −4%/−1%, Python route 87%/95%. **Their point,
carried: two real subjects differing in the property are better evidence than a
mutation, because neither was built to be caught.** New first pick:
`colored_width_gate`.

### L125. A single-digit count is the dangerous size

**A false finding killed before it was reported.** The empty-value scan over the
Codex script corpus returned **1** — *"exactly the count that gets written
down."* The hit was `'{(j:,'` inside a **backtick-quoted shell string**,
`${(j:,:)enabled_tool_names}` — zsh parameter expansion. **The regex ignored
quoting; the parser does not.** True count zero.

**Third time 22c has turned one of this seat's aggregates into nothing, and all
three were single-digit counts.** That is the shape to distrust: **large enough to
look like a real finding, small enough not to trigger the suspicion a big number
would.** A zero invites a check of the instrument; a thousand invites a check of
the method; **a one invites a write-up.**

**Codex script parser: four divergences, all measured zero** over 17,106 generated
scripts, 800 multi-call. Duplicate `const` bindings (Python's dict keeps the last,
`Vec::find` keeps the first — 22t in a third place); an object item with an empty
value (Python's regex needs `.+` so the object goes unparsed and the envelope
stays `Bash`, the Rust yields `{"a": ""}` — **the more-permissive class again**);
a lone backtick; and an explicitly `null` shared key surviving the merge.

**Correct in that file, checked rather than assumed:**
`parse_exec_script_tool` aborts the whole parse when any call site fails, matching
Python's `if tool_call is None: return None`; the merge rules match branch for
branch; and `parse_script_object` returning `None` for `{}` where Python returns a
falsy `{}` **reaches the identical outcome**, because Python's caller tests with
`if input_data :=`.

### L126. ⚠ A reproducibility check cannot distinguish a systematic artefact from a real defect

**G4's first real-pool run: 2 mismatches, 14 unstable. Both mismatches are the
corpus moving, not the route.**

Both are the invalid-date cases, which print one error per candidate file, so
their stderr is the whole pool in scan order. Measured rather than eyeballed:

    legacy files: 4937    native files: 4937
    only in legacy: 0     only in native: 0
    same set: True        same order: False
    first order difference at index 0

**Index 0 is the engine owner's own live transcript** — the file being appended to
as they work. Legacy read it first, native second, its mtime advanced between the
two subprocess launches, and newest-first put it elsewhere. **Identical sets, one
adjacent transposition, at the very top.** The desk's documented artefact exactly:
the instability concentrates in the newest files, which is where a newest-first
scan looks first, **so it lands at the top of every diff and is maximally
convincing.**

**⚠ THE RULE. Their control was "re-run each mismatch and require it to
reproduce". It reproduced perfectly — because the artefact is systematic, not
random.** Legacy always runs first and native always second, **so the same file
always advances in the same gap.** A reproducibility check **passes a systematic
artefact and a real defect identically.** It answers "is this noise?" and cannot
answer "is this mine?"

**The control that works removes the subject from the question entirely: run the
reference twice and diff it against itself.** On the failing case:

> **legacy DISAGREES WITH ITSELF**

**If the reference cannot agree with itself over the measurement window, nothing
measured in that window is meaningful and no claim about the subject is even
well-formed.** That is now the control.

**Generalised: the question is not "does my result reproduce" but "does the
reference agree with itself".** The first is about noise; only the second
separates the instrument's world from the thing under test.

**⚠ And the snapshot waiver I granted was wrong. Recorded against my own ruling
and their own argument.** They declined snapshotting because the pool is gigabytes
and copying it filled the disk; I accepted it. **That reasoning holds for the
bytes — and the artefact here is not content, it is mtime *ordering*, which the
desk's snapshot rule would have removed.** Neither of us separated those two
things. **Their substitute caught 14 random instabilities and missed the two
systematic ones**, which is exactly the direction that matters. **Had they not
measured the file sets, two route defects would have been filed.**

**The waiver now stands for a different reason than it was granted for:** the
legacy self-comparison closes the artefact without a copy, so a snapshot is no
longer needed — **but it was not the reason at the time.**

### L127. G4's gate has a reduced reach, priced rather than discovered

**The two invalid-date cases enumerate all 4,937 files, so under a live pool they
will always be unstable.** They will be counted honestly as unstable rather than
as passes — **and they contribute no coverage.**

**So the gate's real reach is 52 of 54, not 54.** Stated by its author before the
green rather than found afterwards, **so a green cannot imply the larger number.**

### L128. M1 — the oracle is not byte-deterministic on markdown links

**Proved end to end.** Three consecutive `ch-legacy search --color always` runs
over one fixture, clock pinned, private HOME: `id=472252`, `id=435269`,
`id=120321`. **Rich sets `Style._link_id = randint(0, 999999)` per Style
instance, and it reaches the shipped OSC-8 sequence.**

**Census over 400 real files and 12,963 text blocks, with the exact parser Rich
uses: `link_open` 9,165 occurrences. Ordinary content, not a tail.**

**Why every determinism check on this desk passed anyway: no G4 case and none of
the 25 recorded contract cases contains a link.** The capture-twice check is the
right check and **cannot reach the defect** — the same shape as the stderr
blindness and the colour-tier hold, arriving in the one instrument built
specifically to catch nondeterminism.

**Three consequences, all accepted:**

1. **A byte comparator over real content must normalise `id=<digits>` in OSC-8 on
   both sides**, beside the `\r` strip and the `$HOME` substitution. This applies
   to every comparator that will ever run over real message bodies.
2. **The native route emits an id of the same shape.** Terminals use it to join a
   hyperlink split across lines, so **dropping it changes terminal behaviour, not
   only bytes.** Uniqueness per link instance is the property; randomness is not.
3. **"Markdown is deterministic and provable" holds with that one stated
   exception.** Not an argument against the sequencing — everything else measured
   is deterministic and stage one still diffs against a live oracle today.

### L129. Ruled: use the `markdown-it` crate. Do not hand-roll the block parser.

**The argument, which is the seat's and is correct: Rich parses with
`MarkdownIt().enable("strikethrough").enable("table")` — CommonMark. The branch
hand-wrote a block parser instead.** The `markdown-it` crate (0.6.1, crates.io) is
a Rust port of **the same reference implementation** that `markdown-it-py` ports.
**So it makes the parse half provable rather than statistical — the exact property
that justified sequencing stage one first.** Hand-rolling forfeits that property
on the half chosen *because* it has it.

**What the parser has to survive, measured:** 13.6% of text blocks carry list
items, 11.8% headings, 5.7% `hr`, **5.3% indented `code_block`**, 4.5% `fence`,
2.5% `html_block`, 1.9% blockquote, 1.7% tables; inline `code_inline` **104,933**,
`hardbreak` 25,705, `strong` 25,510, `html_inline` 15,770.

**Ruled yes**, and it is the charter's own ordering: *leverage existing logic; do
not re-implement anything*. One dependency against ~793 lines of library
reimplementation, on the surface where provability is the whole argument.

**One condition, and it is the falsification this desk would require anyway:
verify the crate's token stream against `markdown-it-py`'s on the census shapes
before building on it.** Two ports of one reference can still drift by version.
**That is measurable, which is the point — a hand-rolled parser's equivalence is
not.** If they diverge, the divergence is enumerable and can be handled; a
hand-rolled parser gives no such list.

**Thin `Cargo.toml` is the cost, and it is the right trade here.** Twelve
dependencies already; this one removes the largest hand-written approximation in
the package.

**Interface change requested and correctly routed:** `Segment.style` must carry a
**composed** style rather than only a theme-token name — markdown styles compose
(`bold`+`italic`, heading+`strong`, highlight over any of them) and `theme_style`
**panics on an unknown token**. `views-and-colour`'s call as interface owner;
raised with them directly.

### L130. Designed mutations delivered — and a timing economy guarded by nothing

`designed-mutations.md`, written **against L9 rather than 22i**: every entry names
**what the failure message must say**, not only that a failure is expected.
**"It went red" is not the acceptance condition**, because a falsifier that trips
the wrong mechanism is indistinguishable from one that works. **None were run** —
running one means editing a subject, which the reviewer seat does not do.

**The best design, and it is nearly free: `calibrate_harness` needs a probe whose
mutation changes nothing at all.** It must report **inert or BLIND, never
CALIBRATED**. If it reports *caught*, the harness cannot distinguish *"I observed
the mutation"* from *"the mutation did nothing"* — **and all fourteen probes rest
on that distinction.** **The tool that grades every other instrument is not graded
in that direction by anything.** Criterion 5 turned on the calibrator.

**`tool_visibility_oracle`: the right move is not a mutation, it is deriving the
alphabet.** A chosen set cannot tell you it collapsed, and this one has never been
asked. Three members derived from the difference they must expose: a name that is
a **prefix** of another, two differing only in **case**, and two filters matching
one tool at **equal specificity**. Its docstring says the space is built to
produce ties in quantity — **built for quantity is not built to contain the
discriminating pair.**

**⚠ `colored_width_gate` — WITHDRAWN, and it is the first time this move failed.**
See L132. The widths *are* distinct, for a reason that makes the number useless.

**⚠ THE FINDING: timing economy 2's ordering is guarded by nothing.**
`plan.rs::screen` returns on a failed `mafter` check **before** the `cafter`
probe, so a rejected file is never opened twice. **The economy is stated only in a
doc comment.** `plan.rs`'s tests cover the cwd probe, the directory rejection and
an empty filter; **none touches the ordering. Named mutation: swap the two probes.
Nothing goes red.**

**Second inert-guard finding in the same file — and this one is an absence rather
than an inert presence**, found by the cheaper form of criterion 5.

**Why it matters more than an ordinary missing test: `economy_probe` cannot reach
this economy.** Its cost is **one file open**, not measurable time, and the tools
that count opens are **SIP-restricted on this machine**. **So a stored-rule unit
test is the only instrument available for it** — and it is durable past cutover,
for the same reason `economy_probe` survives: it compares against a **rule**
rather than a live peer.

**This qualifies L80.** G3's timing-economy review reported all four preserved.
**That is true of the code and says nothing about whether anything would notice if
one stopped.** Queued for `engine-and-codex`.

### L131. F11 was true when made and is not now — the type arrived before its caller

`StyleColor` now has **ten call sites**, and the named mutation goes red on **54
of 135** stderr cases. **`views-and-colour` checked rather than closing it from
memory.**

**The reviewer's pass caught the window between a type landing and its callers
landing.** The finding was correct when made and is false now, **and the review
says so in place** rather than being quietly dropped.

They wrote the local test anyway **and verified it fails on its own**, because the
54 cases catch the collapse only **in composition** — a distinction that would
have been lost if the finding had simply been marked stale.

### L132. ⚠ The "already recorded the answer" move failed for the first time — an aggregate dominated by the term that cannot fail

**I recorded and relayed this as a third win. It is the first failure, and the
reviewer corrected it against their own instinct.**

The proposal: if `colored_width_gate`'s `observed_width` is equal at 120 and 200,
those are two rows and one test. **`reviewer-profiler` checked. The widths are
distinct — and for a reason that makes the number useless.**

**The coloured panel's border spans the full terminal, so `observed_width` — the
widest visible line — tracks the width unconditionally, whatever the content
does.**

**So the gate measures that the frame follows the terminal. It does not measure
that the text inside reflows.** Two properties, one gated, **and the proposed
check could not tell them apart.** The designed mutation would have failed at both
widths **for the border alone**, met its stated expectation, and proved less than
it appeared to.

**⚠ THE RULE, and it is 22c one level up: an aggregate can be dominated by the
single term that cannot fail, so reading a recorded number is not the same as
reading the instances behind it.** The frozen-reference analysis and the stderr
collapse both worked because their recorded values were **per-case bytes**. This
one is a **maximum**, and a maximum over a set containing one element that tracks
the dimension by construction tells you only about that element.

**The move keeps its three wins and gains its qualifier**: recorded data answers a
question only when the recorded quantity can vary with the property under test.

**Corrected design.** M3′ clamps only the **content** budget and leaves the frame
at terminal width — then it fails at 120 and 200 **only if the fixture content is
naturally wider than 100 columns**, and passing is still the finding. The
no-mutation version: **strip the border lines from both captures and compare the
remainder.**

### L133. Two designs came back — and one passes for a reason worth less than passing

**`calibrate_harness` passes the null probe.** A probe whose two payloads are
identical is reported **blind**, and the run fails. **The mechanism:
`_blind_dimensions` marks a dimension blind when baseline and mutated compare
equal, and identical payloads take that branch by construction.**

**`reviewer-profiler`'s framing is the honest one and it is kept: it was not
designed for that, it happens to be right, which is worth less than being designed
for it.** A property held by construction can be lost by a refactor that nobody
would think to check, because no test names it.

**`tool_visibility_oracle` has one of three discriminators — and it is the one it
was built for.** The alphabet is `['Bash', 'Read']`. **Two names is not an
alphabet, it is a pair.** Prefix pair absent, case pair absent, **equal-specificity
tie present** — and the set was chosen to produce ties in bulk, yielding 696
tie-bearing spec lists.

**Both absences are live behaviours, not hypotheticals.** `_tool_names_match`
normalises through `normalize_tool_filter_name`, **which lowercases for the alias
lookup** — so a lowercase `bash` filter should match `Bash`, and `Read` should
**not** match a hypothetical `ReadFile`. **7,315 cases test neither.**

### L134. Preserve-because-wrong item 10 — the class's defining shape, in the renderer

**A search term split across a style boundary is not highlighted.**
`HighlightedMarkdown` renders to a **segment stream** and re-applies the highlight
**per segment**. Its own docstring states it: *a term split across a style
boundary is left untouched.*

Searching `hello` against source `**hel**lo` gives two segments — `hel` bold, `lo`
plain. **The regex matches neither and nothing is highlighted**, though the
rendered line plainly reads `hello`.

**⚠ The most likely of the ten to be silently fixed.** Highlighting the assembled
plain text and mapping offsets back is the obvious implementation, it is genuinely
more useful, and **nobody reviews a search term being highlighted as a defect.**
**And it composes badly with the branch's one blocker: the natural way to build
the better version is exactly the lower-then-index pattern that aborts mid-render
on `İ`.**

**Named mutation: highlight over concatenated plain text rather than per segment;
a fixture whose match straddles a bold boundary must go red.** A fixture built
from unformatted text cannot fail, and unformatted text is what a first fixture
uses.

**`renderer-review-criteria.md` promoted — nine entries, written before the code
exists**, each naming the mutation that should break it. The charter's
red-before-green rule applied to the *review* rather than to the implementation,
as `g3-review-criteria.md` did.

### L135. Three scope facts for the renderer, and a fourth counting unit

**`chop_cells` is unported and the renderer is its first consumer.** `cells.rs`
ports everything else in `rich.cells`, **correctly** — the search views are
`no_wrap=True, overflow="ellipsis"` and never wrap. **The message body is a
Markdown inside a Panel, which wraps, and Rich's wrap path goes through
`chop_cells`.** Its rules are not the ellipsis rules: it returns a **list of
lines**, splits on **grapheme spans**, and its single-cell fast path slices by
**code points** — **a fourth counting unit, in the file that already holds the
other three.**

**`LeftRail` renders its child at reduced width**, so every tool block's wrap
width differs from the panel's. **An off-by-one moves every wrapped line in every
tool block**, and it is invisible on short content.

**Inline code is padded with one space each side by a Rich subclass.** A port that
reimplements Markdown rather than porting the subclass **loses it silently** — a
second argument for the `markdown-it` ruling, on the styling side.

### L136. ⚠ Two instruments in a row dominated by a term that cannot fail

**`reviewer-profiler`'s reflow separator — built to fix the L132 aggregate
problem — hit the same defect, and they reported it open rather than answered.**

**The panel *title* line is a hybrid: content and frame padding on one line**, so
a **line-level** filter cannot separate them, and what it reported as a difference
is width-dependent rule padding.

**That is the second instrument in a row dominated by a term that cannot fail**,
and the second was built specifically to escape the first. **L132 is therefore not
an incident but a property of this surface**: the frame tracks the terminal by
construction, so any measurement that includes frame bytes inherits a term that
varies with width regardless of content. **Separating them requires measuring the
fixture rather than the output** — `slice-reviewer` has sent them a way round.

**Also from `reviewer-profiler`: the tool alphabet gained a fourth derived member
and they demonstrated it is observable**, which had been flagged as unchecked.
`['exec_command:s=100', 'Bash:s=200']` gives **200**; the reverse order gives
**100**. **So the alias collapses onto the canonical name before the positional
tie-break** — and a port collapsing *after* computing specificity would differ
with nothing noticing. One of four now present.

### L137. The last G4 mismatch was a real defect — in shared code, reaching `ch parse`

**Told apart from the corpus artefact by the control that replaced the failed
one.** Run 2 left one mismatch; measuring the file sets gave **identical sets,
identical order, 4,937 each** — so not the pool moving. 46 lines differed, all one
shape.

**The defect: `wrap_preserving_spaces` dropped a space when a line filled
exactly, where Rich carries it.** That function is `terminal.rs`'s, lifted from
`main.rs`, and it wraps **every stderr message on both routes** — **so this was a
live parity defect in `ch parse`'s errors too**, not only in search.

**⚠ The fix was got wrong twice before anyone read the source, and that is the
part worth recording.** First attempt dropped the space (46 lines short); second
carried it always (57 lines long). **Only then was Rich's `_wrap.py` actually
read.** Three details, none reachable by reasoning:

- **A "word" is `\s*\S+\s*`** — it carries leading *and* trailing whitespace, and
  the break is inserted at the **start** of the match, so whitespace travels with
  the word to the next line.
- **The fit test uses the word without its trailing space; the advance uses it
  with.** A line may legitimately end past `width`.
- **`rstrip_end` removes only the *excess*** — `min(trailing whitespace, length −
  width)` — not all trailing whitespace. **A line one space over keeps every space
  but one.**

**Now a faithful port of `divide_line`, `chop_cells` and `rstrip_end`, gated on
`probes/wrap-oracle.tsv` — 235 rows, five widths.** The corpus is **deliberately
one message with a path of every length from 0 to 39, so the wrap boundary lands
in every position relative to a space** — a **derived** parameterization, built
from the difference it must expose, which is exactly the property a chosen set
cannot give itself. It is also precisely the dimension all three hand-reasoned
attempts got wrong, each in a different place.

Verified end to end: the failing command is **byte-identical at both widths**. 158
lib tests pass.

**Ownership flagged rather than assumed: `terminal.rs` is `search-runtime`'s**, its
wrapping changed and a test module added. The change is measured and the gate is a
recorded table, **and their `ch parse` errors move with it.**

### L138. A new seat landed a file mid-build, and it was the second time today

**The tree was transiently red** — `rust/session_render.rs` appeared with a
private-module import error and fixed itself within a minute.

**Second time today `engine-and-codex` compiled against a file mid-landing, and
the first time it made them publish a wrong finding.** They said it out loud this
time rather than absorbing it.

**No fault and no action against the new seat** — this is the shared-checkout cost
the charter's announce-a-red-tree rule exists for, and a seat one hour old has not
had occasion to learn it. **Routed as practice, not correction:** land compiling
increments, or announce.

**The general point, which is not about either of them:** a red tree costs
whoever is *measuring*, not whoever is *building*, and the builder cannot see the
cost. That asymmetry is why the rule is an announcement rather than a prohibition.

### L139. F17 — two `chop_cells` in the tree, and they disagree

**Measured against live Rich, not inferred:**

    chop_cells("你好", 1)   Rich and cells.rs -> ["", "你", "好"]
                            terminal.rs       -> ["你", "好"]

`cells.rs:288` is public and gated on **20,056 recorded Rich answers across four
Unicode versions**. `terminal.rs:655` is private, hand-written, and landed with
the `wrap_preserving_spaces` fix. **It carries an extra `&& !line.is_empty()`
guard, so it never emits the leading empty piece Rich emits when the very first
grapheme already exceeds the width.**

**Bounded honestly: it needs a grapheme wider than the whole width, so it is
unreachable above width 1** — `chop_cells` is only called when the word is already
wider than the line. At `COLUMNS=1` with CJK it fires.

**Recorded for its shape rather than its blast radius: this is F16 again, one file
over.** Standing constraint 4 — *a copy that compiles is not an extraction* — in
its harder form: **not a copy but a divergent reimplementation under the same
name, in a module that could call the gated one.**

**Ruled: `terminal.rs` calls `metrics.chop_cells` and deletes its own.** Queued
for `engine-and-codex`, who are already in that file and landed the neighbouring
fix. **Replacing a hand-written implementation with one gated on 20,056 recorded
answers is strictly better and needs no further justification.**

### L140. Ruled: gate the duplicated wrap primitives, do not unify them yet

**Rich's `re_word` splitter now exists twice** — `terminal.rs::rich_words` and
`session_render::words` — **and `rstrip_end` twice.** Both pairs implement the
same three Rich rules. **Neither is wrong; both are needed**, one for the message
wrap path and one for the markdown wrap path.

**`message-renderer` declined to unify them and their reasoning is right and is
the desk's own:** it is a refactor across two owners' files and a third's gate,
and **doing it while `search-runtime` is reserved for the cutover arm buys a
tidier tree at the cost of the thing only they can do.** That is L109 applied by
someone else — *what does doing this cost the thing only one person can do*.

**Ruled: defer the unification to after the cutover — and gate both copies against
the same recorded table now.**

**The reason for the second half.** Deferring duplication is safe only if drift is
caught, and 22f says a copy goes stale silently. `engine-and-codex` has just built
**`probes/wrap-oracle.tsv` — 235 rows across five widths, with a corpus
deliberately built so the wrap boundary lands in every position relative to a
space.** **One table over both copies catches divergence without paying for the
refactor**, and it costs a test rather than a cross-owner change.

**Mechanism over documentation.** "Remember to unify these later" is the form that
has failed every time this week; a shared gate is the form that has held.

**The right home when it is done is a shared wrap module beside `cells.rs`**, and
that is a post-cutover item, not a lost one.

### L141. `session_render.rs` exists — and unsupported constructs are typed rather than approximated

Compiles in all configurations run. Carries the Rich render primitives — `Text`
with spans, wrap, `divide_line`, justify, `split_and_crop_lines`,
`adjust_line_length` — the markdown token conversion proved in M2, and the element
walk for paragraphs, headings, rules, blockquotes and lists.

**Fences, tables, links and images return a typed `Unsupported` rather than
rendering approximately.** Two consequences the seat named and both are right:
**a construct cannot silently vanish**, and **nothing can be wired to production
while any remain.** That is the red-gate discipline built into the type system
rather than into a test — the strongest available form, and it means the
partial-render failure mode this class of port usually ships with **cannot occur
here.**

**Next: the oracle test — 865 recorded Rich renders over 173 cases at five
widths** — described by its author as *where I find out how much of the above is
actually right*, which is the correct expectation to hold.

### L142. ▶ The markdown oracle: 775 of 775 — and the three defects it found are worth more

**173 markdown cases at five widths — 13, 20, 40, 72, 120 — curated shapes plus
120 real message text blocks, compared against Rich's own recorded renders
segment by segment, style by style.** Every supported construct reproduces
**byte-identically**: paragraphs, headings, horizontal rules, blockquotes, bullet
and ordered lists, all four inline styles, wrapping, word folding, tab expansion,
centring. 160 lib + 1 bin + 44 doctests green.

**Both falsification mutations fire**, so the gate has been **observed to fail**.
The second is the one worth having: **merging adjacent same-styled runs changes
escape structure without changing a single visible character** — the class this
desk has been bitten by twice.

**⚠ The first pass was not green, and all three defects are one shape: identical
text, different structure.**

1. **An empty `Style` is falsy in Python**, so `Text.append` adds **no span** for
   it — **and a span, even an empty one, cuts the text into separate segments.**
   Every left-justified paragraph came out as `"hello world"` plus a separate run
   of spaces where Rich emits one padded run. **690 of 775 records.** **A
   comparator normalising colour, or comparing visible text, sees nothing.**
2. **`Text.render` yields its segment even when the text is empty.** An empty
   `Text` is how a horizontal rule produces the blank line after it; returning
   nothing loses the line.
3. A rule's trailing blank line must come from that same empty `Text` rather than
   from a hand-placed newline.

**⚠ THE RULE, and it is a fourth mechanism beside the three rehearsal failures:
the code matched the source that was read, and was wrong anyway.** Not a stale
tree, not an assumed interface, not a type system giving false assurance — **the
source was read correctly and implemented correctly, and the behaviour that
mattered was an emergent property of the data structures** rather than of the
lines. A falsy empty `Style` producing no span, producing different segmentation,
producing different bytes, is nowhere in the text of the function.

**Reading cannot reach this class. Only running the comparison can.**

### L143. The typed `Unsupported` list is asserted by the test

**Still refused, in frequency order over 20,000 real text blocks:** links
(**9,165** — blocked on one `Segment` field, asked of `views-and-colour`),
indented code and fences (stage two by the sequencing), tables (1.7% of blocks),
images (196).

**The list is asserted by the test**, so **landing a construct shrinks it, and a
construct that *starts* failing cannot hide by joining a skipped pile.** That is
the property a skip-list normally lacks — a growing set of exclusions usually
looks identical to a shrinking one, and here it cannot.

### L144. Links unblocked — and a boundary crossing ruled correct, with the rule that makes it narrow

**The decision.** `Segment` gains `link: Option<Link>` — **a field, not a parallel
structure**, so a run and its URL cannot be separated; and **out of `Style`**,
because a `String` there costs `Style` its `Copy`, which chrome depends on
everywhere. `message-renderer`'s shape, taken as proposed.

**One correction that would have cost a rebuild: OSC-8 wraps *outside* the SGR
pair, not inside.** Measured against Rich: link opens, then SGR, text, reset, then
link closes. **Two consequences fall out** — a link on an **unstyled** run still
gets the pair, and **a dumb terminal emits no OSC-8 at all**, because
`Style.render` returns the text untouched with no colour system and the link never
gets to wrap.

**⚠ THE BOUNDARY CROSSING, ruled correct — and the reasoning is narrow enough not
to become general precedent.** Adding the field broke every `Segment` struct
literal, and `session_render.rs` had **16**. `views-and-colour` inserted
`link: None` at all 16 and nothing else, **verified the diff contains no line that
is not that insertion**, told the owner plainly, and offered to revert.

**Ruled: right call. Four conditions made it right, and all four are checkable:**

1. The change was **mechanically entailed** by a change in their own file — not a
   judgement about the other file's content.
2. It was **verifiable as such**: the diff contains nothing but the insertion.
3. The alternative was **a red tree for a third party** mid-work, and a red tree
   costs whoever is measuring rather than whoever is building.
4. They **said so immediately** and offered to revert.

**The rule, stated so it cannot be stretched: a compile break you caused is yours
to close, in whatever file it lands, provided the fix is mechanically entailed,
the diff contains nothing else, and you announce it.** That is not *you may edit
another owner's file*. It is *you may not leave a break you created for someone
else to discover.*

Tree green: 160 lib + 1 bin + 44 doctests, all configurations, including the 775.

### L145. A standing condition written before it fires

**Rich's link id is `randint(0, 999999)` per render**, so byte parity on
link-bearing content is impossible **even for Python against itself** (L128).

**None of `views-and-colour`'s five corpora contains a link today, so none
normalises `id=<digits>`.** **The day a recorded case grows one, the gate fails
intermittently and looks exactly like a real defect.**

**Written into their brief now rather than discovered then.** That is the first
time on this mission anyone has recorded a failure mode **before the condition
that triggers it exists** — every other instance was recorded after it bit
someone.

### L146. The empty-`Style` defect has a twin, and both are invisible to any comparator over visible characters

**`views-and-colour`'s empty-segment defect is the renderer's empty-`Style`
defect one layer up.** Theirs: an empty segment emitting a pair Rich omits — 1,120
of 11,200. The renderer's: an empty span cutting a run Rich leaves whole — 690 of
775.

**Identical text, different structure, in both cases.** Two owners, two surfaces,
one class.

**⚠ Their consequence, and it is a G5 question: a fixture that normalises anything
would have hidden both.** The contract corpus normalises the age SGR by design.
**Whether that normalisation can also hide a structure-only difference is a real
question about the gate that will judge the cutover** — not urgent, because the
renderer is not wired and the contract suite cannot see its output yet. **Recorded
as a G5 item and put to `contract-owner` as a single question.** **✅ ANSWERED — see L147. Not a G5 item; the normalisation substitutes rather than strips, so all three structure-only shapes survive it.**

### L147. A normalisation that substitutes is safe; one that strips is not

**`contract-owner`, in four lines, measured rather than reasoned.** The contract
normalisation is **one-to-one on escape sequences** — it rewrites a sequence's
payload or maps one sequence to one placeholder, and **never deletes, inserts,
merges or splits one.**

Both defect shapes fed through `_normalize`:

    sees it  split run vs merged run
    sees it  extra empty escape pair
    sees it  empty span splitting a run
    HIDDEN   age colour vs other age colour

**The three structure-only shapes survive. Only the declared blindness hides
anything** — and that is a *value* difference, not a structural one.

**⚠ THE RULE, and it is the transferable half: a normalisation that *removes*
escapes — the common shape, "strip ANSI and compare text" — would hide all
three. One that *substitutes* preserves byte count and boundary positions, so
structure survives it.**

**That distinction is what makes this corpus safe, not care.** A team that had
been careful and had written a stripping normaliser would have shipped the same
blindness; a team that had been careless and written a substituting one would
not. **The property is in the shape of the transform, not in the diligence of its
author** — which means it is checkable by a reader who was not there, and that is
the whole point.

**Closes L146's G5 item.** `views-and-colour`'s framing — *a fixture that
normalises anything would have hidden both* — **is right in general and false
here**, for a reason nobody had articulated until it was measured.

### L148. ▶ The message body renders byte-identically — 56 of 56, first attempt

**Four widths — 24, 40, 68, 100.** Badges with role chips, part ordering, the
`---` rule between messages, blank lines, left rails, wrapping, wide characters,
tag escaping, **and highlight painting.** Recorded from `build_messages_group`
through the product's own console and theme. **162 lib + 1 bin + 45 doctests, all
five build configurations green**, release under `--no-default-features` included.

**The seam, ready to wire:**

    session_render::message_body_lines(messages, width, &BodyContext)
        -> Result<Vec<Vec<Segment>>, Unsupported>
    BodyContext { metrics, highlight: Option<&Regex>, conversation_tag: Option<&str> }

`width` is the panel interior — console width minus four — and the result is
`panel_lines`'s `body` argument unchanged. **The G4 fixture reaches no unsupported
construct, so all three renderer cases can go green on what exists today.**
`search_run.rs` untouched.

**Preserve item 10 is captured as a fixture rather than a comment.** Searching
`hello` against `the word **hel**lo is split, and hello is not` records the split
occurrence **unpainted** and the whole one painted, with a second test asserting
both halves directly and **a failure message saying that a port which paints the
split one is *better* and diverges.** **A fixture built from unformatted text
cannot fail; this one is built from formatted text on purpose.**

**⚠ The `İ`/`ﬀ` guard is structural rather than tested-around — and this is the
branch's one blocker closed at the mechanism.** Instead of a second matcher,
`Regex::find_all` was added to `search_query.rs`, returning match spans in
**character offsets taken from the haystack the engine already walks** — **so no
string is ever indexed with offsets measured on another.** The failure mode cannot
be written rather than being caught by a test.

Its doctest pins **both directions against Python's own answers**: `İ` **does**
match `i`, because `re.IGNORECASE` uses the simple one-to-one lowercase map; `ﬀ`
does **not** match `ff`, because that would need full folding. **The doctest was
wrong on first write and the engine was right** — L142's fourth mechanism, applied
by its author to themselves.

### L149. Ruled: extending an existing authority beats duplicating in your own file

**Two changes outside the seat's file, both to avoid a second authority rather
than to tidy.** `codecs::message_local_datetime` — the badge's `August 20th,
17:00` and the XML attribute's `2026-08-20 17:00` now share **one** parse instead
of two. And `Regex::find_all` above. **Both are additions with existing behaviour
refactored through them; the full suite is green either side.** Announced, with an
offer to route differently next time.

**Ruled in-bounds, and the rule is the mirror of L144.** L144 says *a compile
break you caused is yours to close.* **This says: when your change would otherwise
create a second authority for something an existing file already owns, extending
that file beats duplicating in yours** — provided the change is **additive**,
existing behaviour is **routed through** the addition rather than reimplemented,
the suite is **green either side**, and you **announce it.**

**The desk's own strongest constraints select this outcome.** Decision 6 — *one
authority; lift, do not fork.* Constraint 4 — *a copy that compiles is not an
extraction.* 22f — *import shared tooling, do not copy it.* **A second date parse
or a second matcher would have been the violation**, and both owners
(`session-core` at 87%, `search-runtime` at 90%+) are unable to review either way.

**Review routed to `slice-reviewer`**, who is holding for this seat as standing
top priority. **The boundary's purpose is that changes are reviewed, not that they
are made by a particular person** — with both owners stopped, routing the review
is what preserves it.

### L150. ⚠ Live divergence: the native route highlights inside left rails; Python does not

`session_render.rs:1941–1949` paints a `LeftRail` whose child is a
`Renderable::Text`. **In Python nothing inside a `LeftRail` is highlighted** —
`formatting.py` passes `highlight_regex` at exactly two sites, 334 and 336, and
**all five rail constructions omit it**: thinking (:340), subagent task (:344),
tool content (:283), `Read` output (:213), edit diff (:174).
`_text_renderable` is the only builder of a `HighlightedMarkdown` and is called
from 334 and 336 alone.

**A search term in a thinking block or a subagent task is highlighted natively and
plain in the product.** No exotic input — `--thinking` or agents shown, and a term
that occurs there.

**⚠ Preserve-item-10's shape a second time, in the same file, in the same
direction: the port highlights *more*.** Item 10 is a term straddling a style
boundary going unpainted; this is a whole **region** going unpainted. **Both look
like improvements, both are divergences, and neither is the kind of thing a
reviewer flags — nobody objects to a search term being visible.**

**Two shapes of one class in one file means it is a property of the surface**, not
two mistakes: **highlighting is the one thing in this renderer where the correct
behaviour is to do less.**

**One grep named and not run:** is the `highlight` flag ever true for a
rail-wrapped `Markdown`? Python's :283 does not highlight tool content either, **so
if it can be, the divergence exists there too.**

**Ruled on the second item rather than leaving it a comment.** `paint_highlight`
leaves a run **silently unpainted** when `find_all` trips the step budget. **D2
ruled *never silently return no-match*, and this is that shape one layer down.**
Python has no budget, so there is no counterpart. **Ruled: make it impossible or
make it loud.** Confirmation has already run the pattern over the *longer* full
text, so tripping the budget on a shorter run should be unreachable — **assert
that rather than degrading quietly.**

### L151. The three review items came back positive, and two are stronger than claimed

**`Regex::find_all` reproduces CPython exactly**, verified by running both:
`re.finditer('i', 'İi', IGNORECASE)` → `[(0,1),(1,2)]`;
`re.finditer('ff', 'ﬀff', IGNORECASE)` → `[(1,3)]`.
**And the pair pins two rules in one doctest:** `İ` matching `i` is the
single-codepoint `tolower` plus fixes table, while `ﬀ` **not** matching `ff` is
standing constraint 5 — `casefold('ﬀ')` is `ff` and `lower('ﬀ')` is `ﬀ`. **One
doctest, both halves of "`re.IGNORECASE` is not `casefold()`".**

**The `İ`/`ﬀ` guard is confirmed structurally closed.** The `Text` model stores
`characters: Vec<char>` and **every span is an index into that same vector** —
`self.characters[offset..next_offset]` in `render`, `characters[start..end]` in
`paint_highlight`. **There is no byte-offset string anywhere in the path, so there
is no second representation to index with the wrong offsets.** Closed by
construction rather than by a test that happens to pass.

**The item-10 fixture is sound, and the honest answer to *would it go red* is that
it would not — and should not.** It asserts over the **recorded oracle lines**, so
it is a **corpus-adequacy** test proving the discriminating case is present;
**the discrimination itself lives in the differential** that compares the port
against those same lines. **The split is right and the test's name says exactly
what it does.** Its assertions do discriminate — `painted("\"hel\"")` includes the
closing quote so it cannot match inside `"hello"` — and its failure message names
the improvement rather than the symptom.

**Stated limit:** the split half is over formatted text and the painted control is
over plain text, **necessarily** — a plain match is what proves painting works at
all. **So the test proves the corpus reaches the case, not that the case is the
only formatted one.**

### L152. Both highlight divergences closed at the mechanism

**Rails: `LeftRail` now renders its child under a context whose `highlight` is
`None`, so the regex cannot reach a rail child from any caller** — thinking,
subagent task, tool content, `Read` result, Edit diff. **A future rail-wrapped
`Markdown` cannot reintroduce it either**, which **answers the reviewer's unrun
grep without depending on the answer staying true**: line 283's tool content is
safe **by construction rather than by inspection.**

**The budget trip is loud.** `paint_highlight` panics rather than leaving a run
unpainted, with a message saying why it should be unreachable — confirmation
already ran the same pattern over the whole rendered message, **strictly longer
than any run of it**, so a run that trips the budget means the budget or the
pattern moved. D2 applied as ruled.

### L153. ⚠ Two fixtures that look like coverage and share no case

**Why the gate missed the rail divergence, and it is a new form.** The corpus had
**a thinking case** and it had **highlight cases**. It did not have **a thinking
case *with* a highlight term.** **Both dimensions covered, their intersection
not — so the corpus could not fail.**

**This is not a fixture that takes the answer as an input (F15's shape). It is two
fixtures that between them look like coverage and share no case.** Each is honest
about what it covers; the gap exists only in the join, and **nothing in either
fixture's description reveals it.**

**Third instance of the family**, after the ASCII-only highlight corpus and the
link-free determinism check — **and it arrived in a corpus built by someone who
had read about both of those.** Knowing the rule did not prevent the instance,
because the rule as previously stated was about a single fixture's blindness and
this one is about a pair's.

**The corpus now carries the intersection**, with a test asserting all three
halves directly: the visible text **is** painted, a rail line **does** carry the
term, and **no rail line is painted** — each with a failure message saying a port
which paints it is more helpful and diverges.

**Both preserve-because-wrong items on this surface are now fixtures rather than
prose, and both run the same direction: the port highlights *more*.**

**164 lib + 1 bin + 45 doctests, all five configurations green.** Links and images
landed; **the refused set is down to fences, indented code and tables.** The
markdown gate now compares **800 of 865** records against 775, with the floor
carrying that diagnosis in its failure message.

### L154. Renderer ordering, and stage two is now the binding question

**`message-renderer` reports 50% of the context window, named, current.** Their
own assessment: **the foundation is done and the remainder is structurally
straightforward** — Rich's render pipeline, the markdown element walk, the message
assembly and the highlighter all exist and are gated, and tables and tool bodies
plug into them.

**Ordering: tables next, as they proposed. Then stop and wait for the stage-two
ruling rather than opening it on half a window.**

**⚠ Stage two is now the binding question on the mission's finish**, and it is the
captain's: **a Pygments-shaped reimplementation (2,482 lines of prior art, must
add TypeScript or cover 78%) versus a Rust highlighting crate (same *class* of
result — plausible but different colours — for a fraction of the code).** Decision
16 already conceded that fence-interior parity is statistical rather than
provable, **so neither option buys parity and they differ by an order of magnitude
in cost.**

**It reaches 3.0% of entries as fenced blocks plus 0.6% as `Read` results**, and
`indented code` at 5.3% of text blocks is in the same bucket.

### L155. F18 — `saturating_sub` is only correct where the negative case cannot arise

**Rich's `_wrap.divide_line` computes `remaining_space = width - cell_offset` as
plain subtraction, which can go negative.** The Rust uses
`width.saturating_sub(cell_offset)`, **which floors at zero.**

**They differ when `cell_offset > width` and `word_length == 0`.** Python's
negative fails `>= 0`, the word takes the else branch and **inserts a break**; the
Rust's `0 >= 0` succeeds and **inserts none.** Different break positions in the
wrapped body.

**Reachable rather than theoretical:** `words()` yields `\s*\S+\s*` so every word
has a non-space run — **but a run of only zero-width characters measures zero
cells.** An overlong unfoldable word followed by a zero-width-only word wraps
differently. **Corpus reachability unmeasured**, stated as such.

**⚠ THE SHAPE, and it is a grep rather than a review: `saturating_sub` is the
idiomatic Rust translation of a Python subtraction, and it is only correct where
the negative case cannot arise.** `session_render.rs` ports arithmetic written in
a language without unsigned integers. **Every `saturating_sub` whose Python
counterpart is a plain `-` is a site where the question must be asked.**

**Two things confirmed correct, checked rather than accepted.** Part ordering —
subagent task, text, thinking, tools, plan — matches `model.py:268`, Python's
stated single source of truth. And `visible_parts` not re-checking `show_plans` is
safe **because `visibility.rs:545` clears the plan during projection**, verified
rather than taken from the comment.

### L156. Pre-implementation: `Part::Plan` must not get a plan renderer

**Recorded before the work rather than after it.** `Part::Plan` renders as
`Unsupported("plan")`, correctly marked as a gap — **but Python has no plan part
kind at all.** `model.py:336` emits the plan as a `MessagePartKind.TOOL` carrying
`ToolParts(tag=tool-input, attrs=[("name","ExitPlanMode")])`.

**So the correct implementation routes it through the tool renderer with a
synthesized `ToolParts`, not through a new plan renderer — and the Rust's fifth
`Part` variant is exactly what invites the second.**

**F15's shape a second time: cheap to say now, a finding once the wiring lands.**
The pattern is now established well enough to name: **a reviewer reading ahead of
an implementer converts a future defect into a sentence**, and the cost difference
is the entire value of reviewing unwritten work.

### L157. ⚠ Reviewer capacity is exhausted, and the largest new file is 17% reviewed

**`slice-reviewer` stopped at 88%** with a cold-entry `RESUME.md`, every artifact
a live symlink, and **no production file ever carrying an edit by that seat.**

**They read about 400 of `session_render.rs`'s 2,380 lines** and named exactly
what is unread: `markdown_segments`, `split_and_crop_lines`, `adjust_line_length`,
the badge, the panel chrome, the tool renderers.

**Their recommended order for a fresh reviewer, which I endorse:** the
`saturating_sub` grep first, because it is mechanical and the class is now named;
then `split_and_crop_lines` and `adjust_line_length`, **because they are the other
half of the wrap path and the fourth counting unit runs through them**; then the
badge, **which the byte differential already covers and therefore needs a reviewer
least.**

**The honest weighing, and it cuts both ways.** No reviewer has capacity —
`reviewer-profiler` 75%+ and holding all of G5, `context-curator` ~78%. **But this
file's gates carry more weight than any other on the mission**: 775 of 775, 800 of
865, 56 of 56, both mutations firing, and a typed `Unsupported` list asserted by
the test so a construct cannot silently vanish. **Gates are not review** — they
answer whether an algorithm matches its oracle over a parameterization, not
whether the parameterization was right — **but the gap here is smaller than 17%
suggests.**

**`slice-reviewer` can still take the oracle role if `views-and-colour`'s trigger
fires** — a smaller surface than a code review — **but will not start another
2,000-line file.**

### L158. Attribution correction — the two flag lists are `context-curator`'s

**I credited the two unguarded flag lists in `search_output.rs` to
`slice-reviewer` in a closing summary. They are `context-curator`'s** (L89), found
on the first trial of criterion 5. The desk record was right; **my message was
not.**

**`slice-reviewer`'s contribution to that finding was to *narrow* it**: the
batched list carries `message_selection` and the serial one does not, **the
asymmetry is faithful to Python**, and it is safe in the correctness direction —
**so the finding stands on the unguarded agreement of the two lists rather than on
today's contents, which is the stronger form.**

**⚠ Their reason for correcting it is the part to keep, and it is this desk's own
founding argument.** This mission exists because a completed rewrite finished and
was never recorded. **A successor reading a closing summary goes to the named
author for the reasoning — so a misattribution sends them to the wrong document
and the wrong person.** Attribution here is a pointer, not credit.

**And the reasoning behind that finding is `context-curator`'s and is load-bearing
downstream:** their account of why four structural passes missed it — their
criteria asked *does the code preserve the property* and never *would the test
notice if it stopped* — **is what produced criterion 5, and criterion 5 is what
produced most of what the third reviewer seat found afterwards.**

**Correctly attributed to `slice-reviewer`:** the false comment scheduling a wrong
refactor (F12), both highlight divergences, the universal-newline gap (F1), the C0
measurement correction, F18's `saturating_sub` class, and the two
pre-implementation notes.

**Seventh attribution or compression error by the first mate**, and the first that
was a misattribution rather than a dropped qualifier. Same cure: **the record was
correct and the summary was not, so summaries get checked against the record
rather than written from memory.**

### L159. On the renderer's coverage, both halves stand

**`slice-reviewer`'s sharpening, which I am adopting over my own phrasing:** 400
of 2,380 is thin, and that file's gates are unusually strong — 775 of 775 with
mutations firing, and an **asserted** `Unsupported` list, **which is the rare case
of a gap that announces itself.**

**Both facts are true and neither cancels the other. A reader who takes only the
second will believe the file is reviewed, and it is not.**

That is better than "the gap is smaller than 17% suggests", which invites exactly
the reading it warns against.

### L160. ▶ G4's gate is snapshotted, reproducible, and back to full reach — and the snapshot cost nothing

**Run 3: 3 mismatches, 4 unstable, and all three mismatches are the corpus.**
Measured, not assumed: `--full` gave `messages: 263` against `262` on
`search-runtime`'s own transcript, which grew between the two reads; `. -ll` at
width 60 differed by 37 bytes, **exactly one session id**, because a new session
file appeared mid-run; `. -ll` at width 100 had identical byte counts with **the
first two ids transposed**, from mtime churn.

**The general fact matters more than the three: nine sessions append to this pool
continuously, and every case enumerating it compares ~4,900 lines whose order is
mtime-derived. The reference cannot agree with itself over the measurement
window, so no byte-exact claim about the route is well-formed there. Chasing
individual mismatches was never going to converge.**

**⚠ THE CORRECTION, and it retires an argument I accepted. `cp -Rc` on APFS
clones copy-on-write.** 9 GB of pool, **11 GB apparent in the snapshot, 44
seconds, and free space did not move at all.** **The copy refused as unaffordable
is effectively free.**

**Their own words, and the transferable form: *I was wrong to argue from the disk
rather than from the filesystem.*** **"Too expensive" is a claim about a
mechanism, and it must be measured against the mechanism rather than the
resource.** The bytes were real; the cost was not, because the relevant fact was
the filesystem's clone semantics and nobody checked it. **I waived a standing rule
on that argument** (L126) — the waiver was already recorded as wrong, and the cost
is now measured at zero.

**Verified before spending an hour rather than after: legacy run twice against the
snapshot agrees with itself byte for byte, 4,871 ids.** **The same self-comparison
control, used as a *precondition* this time rather than as a diagnosis.** That is
the upgrade — a control that runs before the measurement cannot be reached for
only when something looks wrong.

**This upgrades the gate rather than weakening it.** L84 ruled that the synthetic
run's unique value was reproducibility, and that a high-reach irreproducible
instrument does not rank above a low-reach reproducible one. **The snapshot gives
the real-pool run both properties at once** — full reach **and** repeatability —
**so a finding can be confirmed and a green can be re-derived by anyone rather
than believed.**

**Two consequences, both priced.** **The reach limit is lifted: the two
invalid-date cases enumerate the whole pool and were destined to be permanently
unstable; on a frozen pool they are ordinary cases. The gate is 54 of 54 again,
not 52.** And **the snapshot is a point-in-time artefact and is stated as one** —
it is today's pool, it does not cover sessions written after it, and it is deleted
when the gate is green rather than left as 11 GB of clone.

**Running now against the frozen pool. This is the number that answers G4.**

## ▶ SOFT-PAUSE — 2026-08-29, 5h window at 92%

Admiral soft-pause. No hard aborts, no new gates or fixes, no spawning, no
recovery. Land safe edits, refresh `RESUME.md`, report an exact stop point, idle.

**Two teammates were active. Seven were already idle or stopped.**

**`engine-and-codex`** — the G4 differential against the frozen snapshot.
**Instruction: let it land if close** (read-only against a snapshot, so abandoning
it wastes the run without making anything safer), **stop it if early** — the
snapshot is durable and the run is re-derivable, which is the property it was
taken for. **Do not delete the snapshot: record its path and date.** It cost no
disk, it makes the next run reproducible, and nobody should find 11 GB of clone
without knowing what it is.

**`message-renderer`** — mid-tables. **Instruction: stop at a compiling boundary
with the construct still typed `Unsupported` rather than half-implemented.** The
asserted `Unsupported` list makes a refused construct a clean state and a
half-built one not — **that design decision is paying for itself at the pause.**

**Idle before the pause:** `slice-reviewer` (88–89%, cold-entry handoff, no
production file ever touched), `views-and-colour` (unknown past 75%, oracle role,
`slice-reviewer` named as successor), `reviewer-profiler` (75%+, holds all of G5,
runbook written), `context-curator` (~78%), `search-runtime` (90%+, cutover arm
rehearsed three times), `contract-owner` (87%, clean quotable baseline),
`session-core` (87%), `query-semantics` (stopped clean).

**Where the mission stands at the pause.**

- **The engine is complete.** `run(arguments, home, width) -> i32` exists; all five
  output modes, both sinks, the `Confirmed` adapter.
- **The renderer's markdown and message body are byte-identical to Rich** — 775 of
  775 and 56 of 56, with both mutations firing. Links and images landed. Refused:
  fences, indented code, tables.
- **G4's gate is two instruments**, both built: the whole-route differential
  (54 of 54 reach, now against a frozen snapshot with the reference proved to
  agree with itself) and the coloured pty gate (red by design; a third of its red
  is a wiring job).
- **G5's runbook is written** — 15 checks, 8 runnable, 7 blocked on the cutover.
- **The cutover arm is rehearsed three times and matches the tree.**

**Blocking the finish:** the differential's number, the `ColouredListSink` wiring,
the renderer's remaining constructs, and **the captain's stage-two ruling** — a
Pygments-shaped reimplementation against a Rust highlighting crate, differing by
an order of magnitude in cost for the same *class* of result.

### Stop point — `message-renderer`, idle and clean

**Tables landed fully rather than half.** Nothing refused that was
mid-implementation, nothing half-implemented. **All five configurations green with
zero warnings**, verified in a private target directory before anything landed.
**168 lib + 1 bin + 45 doctests.**

**Tables, complete.** `rich.table.Table` as `TableElement` — `box.SIMPLE`,
collapsed padding, no edge padding, header and no footer. Column measurement,
`_collapse_widths` and `ratio_reduce` ported and **pinned directly against Rich's
own answers on nine recorded inputs**, because **a corpus of tables that all fit
would have gated the box drawing and left both width algorithms untouched.** Seven
over-wide cases added for that reason, **and a test asserts the corpus still
reaches the narrowing branch — failing loudly if it stops.**

**⚠ Tables found a defect in code that was already green, and the mechanism is
worth more than the fix.** `justify = self.justify or options.justify` — **the
text's own setting wins, because `"default"` is a truthy string in Python.** The
precedence was backwards. **Markdown never sets `options.justify`, so 800 records
passed on an accident.** A table is the first place the two orders differ, because
a column renders with `justify="left"` while each cell carries its own alignment.

**The rule: a new construct is an instrument.** 800 passing records were passing
for the wrong reason, and **no amount of looking at the markdown corpus would have
shown it** — the discriminating input does not exist there. **Adding tables tested
markdown.** That is a third form beside a blind corpus and two fixtures sharing no
case: **a corpus in which a wrong implementation is indistinguishable from a right
one, revealed only by extending the subject rather than the corpus.**

**Both queued items are in.** **F18 fixed and pinned** — `divide_line`'s
remaining-space test is signed, and `wrap_tests` holds Rich's answers **plus a
falsification that reimplements the floor-at-zero version and requires it to still
disagree**, so the case cannot quietly stop reaching the branch. **That is a
falsifier guarding corpus adequacy rather than gate liveness**, which is a shape
this desk has wanted twice and not had.

**The `saturating_sub` sweep is complete** —
`M3-signed-subtraction-sweep.md`: **one fixed, four checked safe with the reason
recorded, three reachable only below a console width of eight and deliberately not
churned** into an unverified signed-width refactor. **Declining to churn is the
right call** and the reason is recorded rather than the decision alone.

**The rail fix is in at the mechanism, and the plan is now a second constructor of
the one tool part rather than a fifth `Part` variant** — so the tool renderer
**cannot** grow a second one beside it. `slice-reviewer`'s pre-implementation note
applied structurally rather than followed.

**Refused and typed: `fence` and `indented code`. Nothing else, and the test
asserts that exact set.** Both are stage two, untouched.

**Corpora:** markdown **900 records over 180 cases at five widths**, all supported
ones byte-identical; message bodies **60 of 60** at four widths. **Three
falsification mutations fire.**

**Uncommitted from this seat:** `rust/session_render.rs` (new), one line in
`rust/lib.rs`, the `markdown-it` line in `Cargo.toml`, `message_local_datetime` in
`codecs.rs`, `Regex::find_all` in `search_query.rs`, and two oracle files under
`tests/data/message-renderer/`.

**Context: no current reading.** Last was the harness reporting a crossing of 50%,
roughly a third of this window's work ago — **treat as stale and lower.**

### ▶ G4's GATE: 52 of 54 byte-identical, 0 unstable, frozen pool cloned 2026-08-29

**The snapshot did exactly what it was taken for: zero unstable, where three live
runs reported 4, 10 and 14.** Both mismatches reproduce at both widths.

**Both are `search . -ll`, 37 bytes apart — exactly one session id.** Legacy
returns 4,871, native 4,870. The missing one is a Pi session, and Python's two
paths against that single file:

    projection says:          MATCH
    authoritative path says:  no hit

**⚠ Python's projection disagrees with Python's own full search path, and the
projection wins**, because `_stream_dot_only_id_projection` prints the id on MATCH
and never consults the full path. **So `ch search . -ll` returns a session that
`ch search .` does not.**

**⚠ ELEVENTH PRESERVE-BECAUSE-WRONG ITEM, and it inverts an earlier framing of
mine and of theirs.** `_can_project_dot_only_id` was deferred as a **performance**
path with an open question about whether it could change results (L74). **It
changes results — on the real pool, on the commonest id-only query.** It is not an
optimisation to port later: **it is the whole remaining G4 gap, and it must be
ported as written, disagreement included.** Porting only the "correct" path
**loses a session the product shows.**

**Needs adding to `preserve-because-wrong.md` at resume** — that file is
`context-curator`'s and they are stopped, so it is recorded here meanwhile.

**52 of 54 byte-identical including stdout, stderr and exit status. The other 2
have one named cause and a one-file reproduction.**

### Stop point — `engine-and-codex`, idle

**Done since last report:** the serial byte gate ported and wired; **Rich's
wrapping ported faithfully — `divide_line`, `chop_cells`, `rstrip_end` — gated on
235 recorded rows**; the snapshot built **and verified stable before use.** 168 lib
tests, five configurations green.

**Untouched, all seven, each written up in `RESUME.md` with its mechanism and its
trap, in priority order:** the `codex.rs` predicate and comment, F14's error
string, the `ColouredListSink` wiring, the `HOME`-unset measurement,
`terminal.rs`'s duplicate `chop_cells`, the wrap-oracle gate over
`session_render.rs`'s copies, and economy 2's ordering test.

**The snapshot stays**, path and date in the brief with an explicit *do not
delete* and the reason: **it costs no disk while the originals are unchanged, and
it is what makes this gate re-derivable by anyone rather than believed.**

### L162. Two instruments, different surfaces, same rule, neither built from the other

**`views-and-colour` reported the wrap port closed 11 of their 135 stderr cases
independently.** Their corpus is **35 pty captures of the real console
functions**; the wrap gate is a **235-row recorded table**. **Neither was built
from the other.**

**That agreement is worth more than either number alone, and it is the strongest
evidence on this mission that a port is *right* rather than merely *green*.** A
single gate proves an implementation matches the oracle over its own
parameterization — 22i's limit. **Two independently-constructed instruments
agreeing on a rule they measure through different surfaces cannot both be blind in
the same way by construction**, because their parameterizations were chosen by
different people for different questions.

**This is the first time on the mission that convergent evidence has been
available at all**, and it happened by accident rather than design — worth
noticing as something to arrange deliberately at G5.

## ▶ RESUMED — 2026-08-29, new 5h window at 0%

**Correction to the dispatch framing: real-pool run 3 is done.** It landed at
**52 of 54, 0 unstable, frozen pool cloned 2026-08-29**, with one named cause and
a one-file reproduction. The critical path has moved past it.

**Two active owners. Seven idle or blocked, deliberately.**

| Owner | Assignment |
| --- | --- |
| `engine-and-codex` | **1.** Port `_can_project_dot_only_id` as written — the whole remaining G4 gap, and what turns 52 into 54. **2.** `ColouredListSink` wiring with the provider rule from the candidate pool — turns `g4-list` and `TIER IGNORED` green **and unblocks `reviewer-profiler`**. **3.** `codex.rs` predicate and comment. **4.** F14's error string. Then the remaining three. |
| `message-renderer` | **Measure stage two before building it**: what a Pygments-shaped port costs per lexer with TypeScript added, against what a Rust crate gives concretely. Report and hold. Optionally `indented code`'s **geometry** half, if the separation is real. |

**Held idle, with the reason:** `search-runtime` (90%+, cutover arm rehearsed —
wakes when the gate is 54 of 54); `reviewer-profiler` (75%+, G3 measurement
**blocked until the coloured sink is wired**, then holds all of G5);
`slice-reviewer` (89%, stopped, oracle-role successor only);
`views-and-colour` (unknown past 75%, oracle and interface role, on call);
`context-curator` (~78%), `contract-owner` (87%, on call for the flip),
`session-core` (87%), `query-semantics` (stopped clean).

**⚠ The standing gap nobody can currently fill: `session_render.rs` is ~2,400
lines and roughly 400 are reviewed.** All three reviewers are at or above 75%.
**Its gates are unusually strong — 900 markdown records, 60 of 60 message bodies,
three mutations firing, an asserted `Unsupported` set — and gates are not review.
Both facts are true and neither cancels the other.**

**The stage-two ruling remains the captain's**, and the `markdown-it` precedent
does **not** transfer: that crate made the parse half *provable* because it ports
Python's own reference implementation. **A highlighting crate does not.** This one
turns on cost, and decision 16 already conceded fence-interior parity is
statistical either way.

### L163. Stage two costed — and the measurements produced a third option neither question named

`M4-stage-two-costing.md`, promoted. **Nothing implemented.**

**The surface the decision actually covers, over 3,000 real fenced blocks / 1.37M
characters:**

- **39.4% of fenced characters get a non-default colour.** The other 60% carry
  Monokai's default whatever lexer runs.
- **The TypeScript family is 63.9% of every painted character** — densest at 75.5%
  painted against bash's 45.3%. **Not "one more lexer": the majority of the
  value.** Both earlier framings had it as a coverage gap.
- **`text` fences are 22% of blocks and 37% of characters, and Pygments paints
  none of them.**

**Two corrections to the received picture of the prior art, from reading it
function by function.** **767 of the 2,482 lines — the markdown renderer and wrap
core — are already replaced by this seat and are not remaining cost.** And
**`syntax_tokens`, the fence dispatcher, handles only python, sh/bash/zsh, json,
markdown and diff** — HTML, CSS and JavaScript are reachable only from the `Read`
path, and `javascript_tokens` is four lines calling the plain path. **The branch's
fence coverage is five families and it has no JavaScript either**, so "adopting
the branch buys 78%" was generous to it.

**Option B — syntect — fails on measurement, not preference.** No TypeScript, no
TSX, no plain-text syntax in the default set: **488 of 1,200 sampled blocks find
no syntax at all, and every TypeScript-family block is among them.** No Monokai
theme. And where both lexers run, the one comparable quantity without inventing a
mapping — **where each puts a run boundary, an upper bound on colour agreement
because no theme repairs a boundary in the wrong place** — is **62.3% overall,
bash 55.9%, json 60.6%, sh 47.9%.** **Not the same class of result in different
colours: the segmentation differs.**

**Option C — port Pygments' lexer *tables*, not its behaviour.** Its lexers are
`RegexLexer` subclasses: declarative `(pattern, token, state)` tables. **832 rules
across the five families that matter, and every regex feature they use is already
supported by the engine in this tree** — `search_query.rs` has `Backref`,
`Look { behind }`, `ScopedFlags` and named groups, against usage of inline flags
52, lookahead 23, lookbehind 15, backreference 6, named group 1. **Cost anchor
from the reference itself: TypeScript is 142 lines of Pygments where the branch
spends 867 on shell alone**, because the branch reimplements a regex state machine
as control flow. **JSON is the exception** — hand-written as a scanner, so an
imperative port either way.

**The recommendation, split where the measurements draw the line:**

**1. Land `Syntax`'s geometry now, as stage-one work.** Background, padding, line
count and word wrap are separable — every cell inside a fence carries
`48;2;39;40;34` and a token only replaces the foreground prefix. **With geometry
and the default foreground alone, `text` fences and unknown tags render
completely correctly rather than approximately** — 22.3% of blocks, 39.6% of
fenced characters, gateable exactly as the markdown corpus is. **The division is
real, and this is the half that is not a partial render.**

**2. Then C for the colours**, ordered by painted characters: TypeScript family,
bash/sh, json, python, markdown.

**What C changes about the standard, stated carefully by its author.** Decision 16
conceded statistical parity for a **reimplementation**. **Porting the reference's
own tables onto an engine that already reproduces Python's regex semantics makes
the measurement possible** — an enumerable divergence list rather than an
unbounded surface. **Not claimed provable until measured that way — and under
Option A that measurement cannot even be attempted.**

**⚠ One piece unmeasured, and I have asked before recommending: the tables are
declarative, the driver that runs them is not.**
`RegexLexer.get_tokens_unprocessed` is behaviour — the state stack with
`push`/`pop`/`#pop:2`, `bygroups`, `using(OtherLexer)`, `default`, `include`,
`inherit`, callback rules, and `\n` re-anchoring. **832 rules is the data cost;
the driver is the code cost, and the figures do not cover it.** If the five
families use `include`, `bygroups` and a shallow state stack, C is a transcription
with a small engine. **If they use `using()` and callbacks, the engine is a
Pygments interpreter and the estimate moves.**

**A broken probe caught by its author, in the same session they quoted the rule
against it.** The first feature scan reported **zero** advanced regex features
across 832 rules, because `RegexLexer._tokens` stores the compiled pattern's
**bound `match` method** rather than the pattern — so the scan was reading
`"<built-in method match…>"`. **A plausible wrong answer from a broken probe,
caught only by printing the instances.** Every figure above is from the corrected
scan.

### L164. The driver is measured: a transcription with a small engine

**Over the five families that would be ported — 832 rules, states per lexer
6 / 6 / 9 / 49 / 2:**

    plain token        687  82.6%        stay          602  72.4%
    bygroups(...)      138  16.6%        push one      178  21.4%
    default(...)         6   0.7%        pop one        50   6.0%
    hand-written cb      1   0.1%        push two        2   0.2%

**Deepest pop is one.** No `#pop:2` or deeper, no `#push`, no `combined()`.
**`bygroups` runs arity 2–6 with no `None` slots at all**, so the skip path is
unreachable. **`include` and `inherit` cost nothing** — `RegexLexerMeta` expands
both at class build, so a port copies an already-flat table.

**⚠ `using()` is present four times and is never a rule's direct action.** It
appears **only as an argument inside `bygroups`** — once in
`python/soft-keywords-inner`, three times in `markdown/root` — **and every one is
`using(this)`, the same lexer re-entered, never a different one**, three with a
starting stack of `('root', 'inline')`. **So the driver must re-lex a captured
group with its own table from a supplied stack. It does not need to nest a second
lexer**, which is the distinction the question turned on.

**The driver, specified:** an anchored rule walk with first-match-wins; three
actions — plain token, `bygroups` over 2–6 groups, `default`; a state stack with
push-one, push-two and pop-one; same-table re-entry over a captured group from a
given stack; and the no-match rule where **a newline resets to `root` and anything
else emits `Error` and advances one character.**

**Two caveats to carry rather than footnote.** **JSON is not a `RegexLexer` at
all** — a hand-written scanner, so it is an imperative port under **every** option,
at 12.4% of blocks. And **markdown's one hand-written callback**
(`_handle_codeblock`, fenced code inside a markdown fence) is the single piece
that is neither table nor small engine — **0.5% of blocks, deferrable without
touching anything else.**

### L165. ⚠ A calibrated instrument aimed at the wrong level — and it is the more dangerous form

**The first scan classified rule actions and found zero `using`. The detector was
not broken** — calibrated afterwards, it fires six times on the HTML lexer. **It
was a correct, calibrated instrument pointed at the wrong place: the mechanism
lives one level down, inside `bygroups`'s arguments.**

**Contrast with the same session's earlier miss**, which was a probe that **could
not see** — `RegexLexer._tokens` holding a bound `match` method. **This one could
see perfectly and was aimed at the wrong level.**

**THE RULE: calibrating an instrument proves it can see, not that it is aimed at
the thing.** And **a calibrated instrument's zero reads as far more trustworthy
than an uncalibrated one's** — which is exactly what makes this the more dangerous
form. Every calibration result on this desk asserts sensitivity; **none asserts
aim.**

That is the third distinct instrument-failure mode from one seat in one session,
and the only one that survives the desk's existing rules.

## ▶ G4's PIPED GATE IS GREEN — 54 of 54, 0 unstable, 2026-08-29

    pool: /private/tmp/ch-pool-snapshot
    compared 54 cases (27 shapes x 2 widths), colour off
    mismatches: 0   unstable (did not reproduce): 0

**The projection closed it.** `search . -ll` is byte-identical — **4,871 ids
against 4,871**, where it was 4,870. `_can_project_dot_only_id` and
`_stream_dot_only_id_projection` are ported **as written, disagreement included**:
the projection still returns the Pi session the authoritative path rejects,
**because that is what the product does.**

**The reproduction is recorded on the function itself**, with the file path and
both measured answers — **so the next person to read it finds the reason before
they find the temptation.** That is the strongest form of the preserve-because-
wrong defence: not a list entry, but the evidence at the site.

**It is also much faster, which was the original reason to port it and is now the
lesser one:** `search . -ll` over 4,871 sessions in **11 seconds.**

**⚠ What this green covers, stated by its author so it is not quoted wider.** 54
shapes across two widths, comparing **stdout bytes, stderr bytes and exit
status**, **colour off** — every mode that reaches a pipe. **It does not cover the
coloured panel or list row.**

**So G4 is not green. Its second instrument is.** L102 split the gate in two: the
piped differential and `views-and-colour`'s coloured pty gate. **The coloured gate
is still red, and one item stands between here and both being green.**

### L166. The last thing before the cutover is one wiring job

**`ColouredListSink` wiring is now the only work between the mission and a fully
green G4.** It turns `g4-list` and `TIER IGNORED` green, and **the renderer seam
makes `g4-default-matches`, `g4-full` and `g4-matches-no-metadata` reachable —
the G4 fixture reaches no unsupported construct** (L148).

**It also unblocks `reviewer-profiler`**, whose G3 measurement has been stalled
since every colour mode collapsed to one uncoloured output through the driver.

**The trap, restated because it is the one thing that could go wrong quietly:**
`show_provider` must derive from the **candidate pool**, not from the hits.
Deriving it from hits gives a different answer **and** would require buffering
every hit before the first row, destroying the economy the hoist exists to
protect. **And the fixtures take `show_provider` as an input, so a wrong rule
leaves all of them green** (F15).

**Sequencing after it lands:** run the coloured pty gate → both G4 instruments
green → wake `search-runtime` for the cutover arm → `reviewer-profiler`'s G3
measurement and then G5's seven blocked checks.

**`engine-and-codex` context: session budget 14.27M of 15M; context window ~82%.**
Handoff at 90%. Items 3 and 4 are small; **items 5–7 need a check-in first.**

### L167. ▶ STAGE-TWO RULING: geometry now, then the reference tables, TypeScript first

**Captain's ruling, 2026-08-29, on `message-renderer`'s costing.**

**Land complete fence geometry now. Then port the reference lexer tables onto the
existing small engine, TypeScript first.** **`syntect` rejected on measurement** —
no TypeScript, 62.3% boundary ceiling — **and hand-written lexers rejected.**

**The stated reason: the table port is enumerable, reviewable, and matches the
exact-parity definition of done.** Hand-writing leaves the divergence
unmeasurable; the crate changes segmentation, which no theme repairs.

**Required with it — gates and falsifying mutations for three things separately:**

1. **Geometry** — background, padding, line count, wrap, gated against Rich.
2. **The engine's actions and state** — plain token, `bygroups` 2–6, `default`;
   push-one, push-two, pop-one; same-table re-entry from a supplied stack; **and
   the no-match rule (newline resets to `root`, anything else emits `Error` and
   advances one character).** **A named mutation per invariant.** The no-match
   rule is the one a port gets subtly wrong and no corpus notices.
3. **Each promoted table family, separately** — its own gate and its own
   falsifier.

**Sequencing instruction added by the first mate: land one family complete with
its gate before starting the next.** The asserted `Unsupported` set already makes
a refused construct a clean state and a half-built one not — **the same discipline
applied to lexers means a family is either promoted and gated or absent**, so
every stopping point is safe at an unknown context position.

**Order by painted characters: TypeScript family (63.9% of painted characters),
bash/sh, json, python, markdown.**

**Both caveats stand.** **JSON is a hand-written scanner in the reference — an
imperative port under every option**, 12.4% of blocks, to be sequenced knowing it
rather than discovering it. **Markdown's `_handle_codeblock` is neither table nor
engine** — 0.5% of blocks, **deferred unless it falls out for free.**

**`engine-and-codex` stays on the `ColouredListSink` wiring and the cutover
path**, unchanged.

### L168. ⚠ The coloured gate needs a second sink, not a wire — and my "one wiring job" was wrong

**`ColouredListSink` is wired and `g4-list` now matches the reference on both
swept dimensions.** Measured per case rather than trusting the guards:

                           subject distinct / 5 tiers   reference
    g4-list                          5                      5
    g4-default-matches               2                      5
                           subject distinct / 3 clocks  reference
    g4-list                          3                      3

**⚠ So `TIER IGNORED` and `CLOCK IGNORED` are false for the case the wiring
covers.** `g4-list` is fully tier-responsive and honours `CH_NOW`.

**Both guards report a *route-wide* blindness from evidence that only covers cases
where the dimension is inert.** Three of the four G4 cases still render the plain
form, which has no age and no colour, **so they are legitimately clock- and
tier-invariant — and the guard attributes that to "the subject route".** **A claim
whose scope is narrower than its wording**, which is the week's recurring shape
arriving in a guard built to detect exactly that. **The guards are right that
something is inert and wrong about what.** Routed to `views-and-colour`.

**One real `g4-list` difference, with a reproduction.** Truecolor, width 72, byte
11022:

    reference   …back\slash plus  ␛[0m␛[3;38;2;154;160;166mtab café end
    subject     …back\slash plus\ttab café end

**Python expands a literal TAB in the headline to spaces at the tab stop and
splits the styled span there; the subject emits the raw tab.** It is Rich's `Text`
tab expansion **at render time** — the raw headline goes into `Text.append`
unexpanded — **so it belongs to the row renderer, not to `headline()`.** 26 bytes
across the case; one fixture carries the tab. `views-and-colour`'s file.

**⚠ AND THE SCOPE CORRECTION, which is mine: the other three cases need a coloured
*panel* sink that does not exist.** `ColouredListSink` covers `--list` only.
**`matches` and `--full` need `panel_lines` plus
`session_render::message_body_lines` wired into a second sink** — **real work
rather than a wire.** I told the captain one wiring job stood between the mission
and both halves of G4 green. **That was wrong.**

### L169. Ruled: the panel sink outranks stage two

**`message-renderer` pauses stage two and writes the coloured panel sink first.**

**The reasoning is critical-path rather than scope.** Both are required for the
definition of done. **But the panel sink unblocks the cutover, which unblocks G5's
seven blocked checks, `reviewer-profiler`'s stalled G3 measurement, and
`search-runtime` — who are at 90%+ and are a wasting asset.** **Stage two unblocks
nothing**: fences stay typed `Unsupported`, and the G4 fixture reaches none of
them.

**Owner: `message-renderer`**, who produce `message_body_lines` and hold the
seam's other end. **`search_views.rs` is `views-and-colour`'s**, whose position is
unknown and stale — **they are told as interface owner and may claim it if they
have the room**, which is the same pattern as the boundary rulings that have
worked here.

**`engine-and-codex` reported this rather than starting it, at 86%**, which is the
right call and the second time this week someone has handed over a piece rather
than beginning something they could not finish.

### L170. Operational: seven sessions renamed and their bare names stopped resolving

**All seven idle teammates now list with a prefix** — e.g.
`[08-28][chats][t:01a0] views-and-colour [c34011]`, with the roster noting *"says
it was views-and-colour until 33s ago"*. **`SendMessage` to the bare name fails,
and so does name-plus-ref. The full prefixed name works.**

    to: "[08-28][chats][t:01a0] views-and-colour"     delivered, then stopped working
    to: "views-and-colour"                            fails
    to: "views-and-colour [c34011]"                   fails

**⚠ AND THE PREFIX IS NOT STABLE.** It changed from `[t:01a0]` to `[t:6a91]`
within the hour, and `message-renderer` carries `[08-29]` where others carry
`[08-28]` — **so the prefix tracks a session's start date and a team token that
moves.** **Recording a prefix is useless. The rule is: run `ListAgents`
immediately before sending and copy the row exactly.** A prefix noted five minutes
ago may already be wrong.

**Affected: `context-curator`, `slice-reviewer`, `search-runtime`,
`views-and-colour`, `reviewer-profiler`, `query-semantics`, `contract-owner`,
`session-core`.** **Unaffected and still bare-addressable: `message-renderer`,
`engine-and-codex`** — the two that are busy.

**No session was lost.** All ten are alive and idle or busy. Recorded because a
successor waking `search-runtime` for the cutover, or `reviewer-profiler` for G5,
**will get "no agent named" and could reasonably conclude the seat is gone** —
which is what I concluded for thirty seconds. **Run `ListAgents` and copy the row
exactly.**

### L171. The guard commits the error it was built to catch

**`clock_responsiveness` and `tier_responsiveness` each probe *one* case** — a
hardcoded `-l` row and a `needle five` search — **and then report a conclusion
about the route.** When three of the four G4 cases render the plain form, that
single probe is inert **for a reason that has nothing to do with the route's
capability.**

**Its author's own statement, and it is the entry: the guard commits the error it
was built to catch — a claim whose scope is wider than its evidence.** It was
written to catch a dimension that looks swept and is not, **and it cannot tell
"the subject ignores this input" from "this case cannot express this input".**

**Fix: make the claim per-case rather than route-wide.** Count distinct outputs
for each case across the dimension and report only that **this case** is inert,
never that the route is. **A dimension is then genuinely swept when at least one
case responds** — which is the property actually wanted. Queued behind the red
tree.

**And the diagnosis came from the gate's own output.** The per-case numbers it
prints are what disproved its headline. **A guard that printed only a verdict
would have been believed.** 22x — a gate should print what it covered — paying for
itself against the gate that prints it.

### L172. The tab defect is larger than the case that found it

**Python expands a literal TAB at render time, to absolute 8-column stops across
the assembled line, and splits the styled span at each tab** — Rich emits the
padded run and the following text as **separate escape pairs with the same style
and never merges them.** Six shapes measured to get the stop arithmetic right.

**It lives in `render_line`, so it covers the list row, the panel body and the top
border together** rather than only the row that surfaced it. **The panel sink
inherits it, and the G4 fixture may not carry a tab.**

Confirmed as belonging to the row renderer rather than `headline()`: the raw
string goes into `Text.append` untouched and **only the render expands it.**

### L173. ⚠ Tree red, and the rule that says who fixes it

**`search_views.rs:1910` calls `crate::search_output::print_error`, which does not
exist. Nothing compiles for anyone.**

**`views-and-colour` did not touch it, correctly, and gave the reason that
distinguishes this from L144: the fix is a design choice, not a mechanical
entailment.** L144 says a compile break you caused is yours to close **in whatever
file it lands** — and its four conditions include *mechanically entailed*.
**A break whose repair requires a decision fails that condition, so nobody else
may guess at it.**

**That is the boundary working in both directions on the same day**: yesterday it
permitted an insertion at 16 sites because nothing else was possible; today it
forbids a fix because something else is.

### L174. ▶ Fence geometry is complete — stage one of the captain's ruling is done

**Landed:** tables complete with their width algorithms pinned against Rich;
**fence geometry complete — any block whose language reaches no lexer renders
exactly**, 22.3% of real fenced blocks and 39.6% of their characters, with a
**generated 915-entry Pygments alias table** deciding which those are; and the
**`ColouredPanelSink`**.

**The refused set is one entry: `fence lexer`.** Everything else in the renderer
is landed and gated. **171 lib + 1 bin + 47 doctests**, both configurations clean.

**The tree is green again**, fixed before either report of the red arrived.

### L175. ⚠ A third tab expansion, in different units and a different size, inside one panel

**`Syntax._process_code` expands tabs through Python's `str.expandtabs(4)` —
characters, not cells, and four, not eight — because it runs before any `Text`
exists.** The `Text` model expands at render in `RichText::wrap`, at Rich's
console `tab_size` of **8**, counted in **cells**.

**So one panel can contain both expansions, at different sizes, in different
units.** Pinned against CPython **with a falsifier requiring the cell-counting
version to still disagree on `你好\t`** — a case chosen so the two units cannot
coincide.

**And an interaction that would otherwise have been discovered by a diff.**
`views-and-colour`'s pending tab fix expands in `render_line`, which covers the
chrome — **but the panel body does not reach `render_line` with tabs in it**,
because `RichText::wrap` already expanded them, byte-exact at five widths. **So
their expansion must be idempotent on a body line, or the body must opt out.**
Raised between the two owners directly, before either landed.

### L176. The red tree, and its author's own diagnosis

**Fixed in the next tool call after the append — and not announced.** Their
account, which is the entry: **"The rule asks for an announcement, not for
atomicity, and I gave neither. I cannot see the cost, so 'it will be green in a
minute' is not mine to judge."**

**Second instance for the same seat, and the correction is now a standing
practice rather than an intention: anything appended to a shared file gets
announced before it lands, not after it compiles.**

**`views-and-colour` were right to leave it and right about why.** The author had
half-typed two different repairs — adding a `print_error` to `search_output`, and
copying the list sink's `eprintln!` plus `wrap_preserving_spaces`. **They took the
second, with a comment recording that it shares the known stderr-colour gap
deliberately rather than inventing a second answer.** A guess by anyone else would
have picked the other one.

### L177. "A sink never observed to render is not evidence"

**The `ColouredPanelSink` is written and unproven, and its author is gating it
before wiring it** — recording Python's panel bytes for hits built from authored
sessions, the way `ColouredListSink` is gated on real `SearchHit` values.

**Their formulation is the rule: a sink never observed to render is not evidence
any more than an untriggered gate is.** The desk has three entries about gates
that cannot fail; **this is the same property in a production object** — code that
compiles, is called by nothing, and is assumed to work because it exists.

### L178. ▶ `g4-list` is green through the real native route — the coloured gate is now exactly the renderer question

**Zero differences under a pty, across five colour tiers and two clock instants.**
That is the third of the coloured gate predicted to go green on wiring alone.
**The remaining red is the three panel cases and nothing else** — the gate is no
longer an undifferentiated hole.

**The guards are per case and honest.** A run now prints:

> `note: clock is inert for 3 of 4 cases (g4-default-matches, g4-full,
> g4-matches-no-metadata) and live for 1 (g4-list) — swept.`

**A dimension is swept when at least one case responds, and no case's silence is
attributed to the route.** No more false `TIER IGNORED` for anyone running it.

**Tabs fixed in `render_line`** — list row, panel body and top border covered
together — **idempotent on tab-free input**, with `message-renderer` asked to make
the body carry that guarantee **explicitly**, because **a tab surviving into a
body line would fire the expansion with a different column origin and be silently
two columns off.** Closed at both ends rather than at one.

### L179. A corpus that cannot express the difference under test reports a clean pass — third instance, first found by a peer

**`message-renderer` asked whether the frame pads a short body line in the body's
style. It pads unstyled, and the implementation was right — but every body line in
the 11,200-case panel corpus was plain text**, so *"pads unstyled"* and *"pads in
the body's style"* were **indistinguishable in everything gated.** **It was true
by luck.**

A styled short body is now in the corpus — **875 panels, 2,800 lines** — and the
mutation making padding inherit the style **fails on 1,050 of them.**

**Same shape as the empty-segment defect and the byte-identical Unicode oracle:
third instance in one owner's instruments, and the first found by someone else
asking rather than by the owner computing.** Its own note is the useful part —
**the previous two were found by the author interrogating their own corpus; this
one required a question from outside it.** Self-audit reaches a great deal and not
this.

### L180. Five counting units in one surface, and none may be unified

    code points     elide_to_width
    code points     truncate_middle
    UTF-16 units    Pi's responsePreview truncation
    cells at 8      Text / RichText::wrap
    characters at 4 a fence, via str.expandtabs(4)

**One panel can carry two expansions at different sizes in different units.** The
last arrives because `Syntax._process_code` runs **before any `Text` exists**.

**Recorded as a standing fact rather than a finding: any port that unifies them
changes behaviour**, and the tempting unification is the one that looks like
cleanup. The desk previously recorded three; **there are five.**

**All configurations green: 173 lib + 1 bin + 47 doctests.**

### L181. ▶ The panel sink is proved before wiring: 168 of 168 byte-identical

**Seven message shapes** — plain, two-message, markdown with a list and a quote, a
wrapping line, a plain fence, a table, wide characters — **across 3 widths ×
metadata on/off × `--full` on/off × highlight on/off**, built from real
`SearchHit` values the way the list sink's gate is. **Title elision, the facts
line, the badge, the body, highlight painting and the border cycle are all inside
the compared bytes.**

**Three falsifying mutations fire:** a sink that never cycles the border hue, one
that ignores `--no-metadata`, and one that lays the body out at the **console
width rather than the interior** — the natural off-by-four, **which shows only
once a line is long enough to wrap differently.** **Each assertion names the
corpus property that would have to have decayed for it to stop firing**, which is
the corpus-adequacy guard this desk asked for twice and now has in three places.

### L182. ⚠ RULED: the cutover cannot land until stage two lands

**`emit` panics if a body reaches a fenced block whose language has a lexer**,
rather than rendering it approximately. **The G4 fixture reaches none of it, so
the gate goes green — and real sessions will reach it.**

**Ruling, and it is mine rather than the seat's to make:**

- **Land the sink wiring into `search_run.rs`.** Safe: `search_run::run` has no
  caller from `main.rs`, so nothing user-facing reaches `emit`. **It turns the
  coloured gate green.**
- **Do NOT land the cutover branch in `main.rs` until stage two is complete.**

**Rejected alternatives, both quickly.** Rendering fenced blocks approximately is
the silent divergence the typed `Unsupported` design exists to prevent. Falling
back to `ch-legacy` for those sessions is the intermediate hybrid the charter
forbids.

**⚠ THE CONSEQUENCE, which changes the finish sequence: both G4 gates green does
NOT mean G4 is done.** G4 *is* the cutover. **The cutover waits for stage two —
the Pygments table port, TypeScript first — because the renderer must be complete
before a user-facing route reaches it.**

**This was always true and nobody had noticed that "the renderer is complete"
includes stage two.** The two gates measure the route; the panic measures what the
route does on content the gates do not carry.

**Practical effects.** `search-runtime` at 90%+ waits longer than planned — the
arm is rehearsed three times, recorded as a recipe, and `probes/searchdriver` is
near-verbatim, **so the cutover is transferable if they do not survive.**
`reviewer-profiler` still unblocks on the wiring, because G3 measurement runs
against the driver rather than the cutover.

### L183. The interface question that found a hole, from the outside

**Two items from the seam, both closed at both ends.**

**The padding question found a real hole in a peer's gate**, and they said so:
every body line in an 11,200-case corpus was plain text, so *padding is unstyled*
was indistinguishable from *padding inherits the body's style*. **True by luck
until asked.** Two-fixtures-sharing-no-case, **found from outside the corpus
rather than after the fact.**

**And the tab guarantee is explicit rather than lucky.** `render_line`'s expansion
**starts its column count at zero, while a body line begins two columns in, after
`│ `** — so a surviving tab would land its stops **two columns off, silently.**
Every body path already expands tabs first, so **the body now asserts it carries
none, with the column-origin reason in the message.**

**Tree: 173 lib + 1 bin + 48 doctests, zero warnings, all five configurations
green.**

### L184. ▶ Captain's requirement: G4 must carry a fence case, so green cannot depend on omission

**Ruling accepted — no cutover until stage two handles the code-fence path without
panic — with one requirement added: a G4 fixture that reaches an unsupported or
not-yet-covered fence.**

**The gate is currently green on the cases it carries because the fixture avoids
the case that panics.** That is a pass depending on what the corpus does **not**
contain — the omission form of every gate-cannot-fail entry on this desk, and the
first time it has been caught *before* the green was quoted.

**It will go red, and that is the point.** Same discipline as building the
coloured gate red before the renderer existed: **the red is the specification, and
it turns green when stage two covers that fence.** The panic is not to be softened
to make it pass.

**Assigned to `message-renderer`** — the file is `views-and-colour`'s, who are
stopped and stale past 75%, and the fence surface is the renderer's. Told to
coordinate on conventions rather than infer them, as with the panel sink.
`views-and-colour` notified, not woken.

**One instruction with it: choose the case deliberately and say which.** A fence
in a language that will **never** be covered tests the `Unsupported` path
permanently; one in a language stage two **will** cover tests the panic today and
the render later. **They prove different things and both are worth having.**

**Order confirmed by the captain: the engine's actions, state and the no-match
rule with their gates and named mutations, then TypeScript.**
`engine-and-codex` holds the wiring branch.

**Note for the record: `views-and-colour`'s gate has now caught three things
nothing else could** — the tier and clock guards' false scope, the tab expansion,
and an omission-dependent green — **all three because it prints per-case evidence
rather than a verdict.** 22x, three times, from one instrument.

### L185. ▶ The lexer engine is landed and gated against Pygments' own driver

**17 inputs, 83 tokens, byte-exact — and the gate compares two *drivers* rather
than two transcriptions.** **One table definition builds both the Python lexer
that produced the expected stream and the Rust table under test. Neither side
holds a second copy.** That is import-not-copy (22f) applied to a gate, and it is
the strongest instrument design on this mission.

**Every mechanism exercised**, including three the five families do not use —
`#push`, an integer pop, a `None` slot in `bygroups` — **so the engine is more
general than the tables need**, which is the right direction for a component a
successor extends.

**The no-match rule has direct assertions**, and one detail nobody had: **a
newline resets the stack to `root` and emits `Whitespace`, not `Text`.** An
unmatched character emits one `Error` and advances exactly one. **Plus a
falsification requiring un-reset lexing to still differ, and a corpus-adequacy
test asserting the recorded stream reaches all four fallback mechanisms by name.**

**⚠ The gate caught a real error on its first run, in the probe rather than the
port.** `using(this, stack=(…))` — **`using` honours only `state=`; anything else
in `kwargs` goes to the lexer's *constructor*, and the re-entry then silently
starts from `root`.** Python lexed three tokens as names where the probe lexed
them as string content.

**Their line is the entry: a wrong table would have looked exactly like this.**
**A gate built against the author's reading rather than against the reference
driver would have agreed with the author.** That is the whole argument for the
two-driver design, demonstrated by the design catching its own author within
minutes.

### L186. The two G4 fence rows, named for what they prove

Following `views-and-colour`'s convention exactly — additive rows in
`G4_COLOURED_CASES`, `--no-paging`, no `--color` — **and each term checked to
resolve to exactly one session in the fixture pool.**

- **`g4-fence-covered-later`** — `Renderfence python`. Python **is** in the
  promoted set, so this row **tests the refusal today and the rendering later.**
  It is the one that flips.
- **`g4-fence-never-covered`** — `Renderfence web`: javascript, html, css, **none
  promoted.** It **tests the `Unsupported` path permanently and should stay red
  for ever.**

**Both red by design, panic unsoftened.**

### L187. ⚠ ROSTER: the critical path's only seat is at 75% with its largest piece ahead

**`message-renderer` reports a current harness reading of 75% of the context
window** — named, not stale — **with the TypeScript table still ahead and more
than a quarter of the remaining work left. Plan for this seat not finishing it.**

**Every other seat is at or above 75%**: `engine-and-codex` ~86%,
`search-runtime` 90%+, `slice-reviewer` 89%, `reviewer-profiler` 75%+,
`views-and-colour` stale past 75%, `contract-owner` and `session-core` 87%,
`context-curator` ~78%.

**Ruled, and it sets the handoff boundary at the only place it stays clean:
finish the Monokai style table, then stop.** The **engine, its gate and the style
table are judgement** — they needed the driver comparison, the `using(this)`
discovery, the no-match distinctions. **The language tables are data**, transcribed
against a gate that already exists and proves itself. **A fresh seat can do
tables; nobody can rebuild the engine cheaply.**

**What their `RESUME.md` must carry above everything else: the promotion
procedure** — how a table gets added, what its gate must assert, and what the
corpus-adequacy test requires. **That exists only in their head.**

**Escalated to the captain as a roster question.** Stage two is the last thing
between the mission and its cutover, and the only seat that can do it is at 75%.

### L188. ▶ Stage two is handoff-ready: engine, gate, style table, and a written promotion procedure

**`PROMOTING-A-LEXER-TABLE.md`, promoted.** The artefact that existed only in one
window, and the reason a fresh seat can now take the tables.

**It carries five generator traps, each of which has already produced a wrong
answer here:**

1. **`_tokens` stores the bound `match` method, not the pattern** — the one that
   gave a confident *"zero advanced regex features"* across 832 rules.
2. **`using()` honours only `state=`**; anything else goes to the lexer's
   constructor and **the re-entry silently restarts from `root`.**
3. **`using()` is never a rule's direct action** — only a `bygroups` argument.
4. **A no-state-change rule is a two-tuple**, and an action is never `None` except
   through `default(...)`.
5. **Two escaping failures** — an apostrophe in `Cap'n Proto`, and a non-BMP alias
   that JSON writes as a surrogate pair Rust rejects.

**What a table's gate must assert:** the stream compared against Pygments over
**real** content in that language; a compared-count floor **whose message carries
its own diagnosis**; four named mutations — a dropped rule, two rules swapped,
`bygroups` emitting an empty group, a transition changed from push-one to stay —
**and a corpus-adequacy test asserting every declared rule is reached.**

**Five wiring steps**, including that `EXPECTED_UNSUPPORTED` is an **asserted exact
set** and will say so if shrunk wrongly, and that **`g4-fence-covered-later` flips
while `g4-fence-never-covered` must stay red for ever.**

**And the two things that are not tables:** JSON is a hand-written scanner in the
reference; markdown's `_handle_codeblock` is neither table nor engine.

**`syntax_styles.rs` is generated and doctested** — 80 token types with Monokai's
resolved style, and **`token_style` walking the ancestry the theme walks, so a
lexer emitting an unnamed descendant still gets a colour.** **That was the last
piece before any table can be promoted.** A successor writes a generator and a
gate and nothing else.

**Tree: 178 lib + 1 bin + 50 doctests, zero warnings in both feature
configurations, release green.** **No table promoted, so the refused set is still
the single `fence lexer` entry and the renderer's behaviour is unchanged by any of
the engine work.**

### L189. An owner cannot see how much of what they know is in the files

**Their note, and it is the reason the coordinator sets handoff boundaries rather
than the owner:** *"I was going to start TypeScript. The distinction between the
half that needs accumulated context and the half that is transcription against an
existing gate is the right cut, and it is only visible from where you sit, because
I could not see how much of what I know is in the files versus in the window."*

**That is a structural limit, not a lapse.** An owner reads their own files
*through* the context that produced them, so a file that is incomplete looks
complete from inside. **Everyone on this mission who wrote a good handoff wrote it
because someone outside asked for one at a boundary they had not chosen.**

**The operational form: the person who decides *when* to hand off should not be
the person whose knowledge is being externalised.**

## ▶ BOTH HALVES OF G4 ARE GREEN — 2026-08-29

**Uncoloured: 54 of 54, 0 unstable**, frozen pool. **Coloured: all four original
cases green, and both responsiveness guards have stopped firing.**

    210 comparisons over 6 coloured cases, widths 72, 7 clocks
       5 DIFFERS g4-fence-never-covered
       5 DIFFERS g4-fence-covered-later

**The 70 differences are the two new fence cases — 2 × 5 tiers × 7 clocks — which
panic by design.** `g4-list`, `g4-default-matches`, `g4-full` and
`g4-matches-no-metadata` all pass. **The panel sink did what its 168-of-168 gate
said it would.**

**The guards falling silent is its own result.** They previously reported the
route made no colour decision at all and ignored `CH_NOW`; **both were false for
the case that could show it, and both are quiet now that every case is wired.** A
guard that goes quiet when the world changes is behaving; one that stays loud
would have been the second defect.

**Uncoloured G4 re-run after F14 and the panel wiring: still 0 of 54. No
regression.**

**So the cutover's gates are met. The cutover itself waits on the lexer
tables** — the two red fence rows are the specification, and
`g4-fence-covered-later` is the one that flips.

### L190. Silence is not agreement — a probe that could not have seen the fix

**F14 took three attempts and two were the fixer's own.** The first version
printed the Rust-shaped line **twice** for a boolean query, **because Python's
raise aborts the whole prefilter while a per-term closure carries on to the next
term.** Corrected to record the failure and short-circuit; verified on a
`chmod 000` file across `the`, `the OR zzz` and `the AND zzz`, byte-identical
including exit status.

**⚠ And it was nearly reported fixed without ever being seen to work.** The first
probe was **inconclusive rather than passing** — neither route printed anything,
**because the chmod'd file never entered the pool.** **They built a proper
single-file probe rather than treating silence as agreement — and that is what
exposed the double-print.**

**The rule: two routes producing nothing is not two routes agreeing.** An empty
comparison is the same shape as a gate that cannot fail, arriving during a fix
rather than during a review — and it would have shipped a defect **introduced by
the fix for another defect.**

### L191. One authority for stderr errors, from a break in someone else's file

**`views-and-colour` called `search_output::print_error`, which did not exist.**
Its owner wrote it **and folded their three inline copies of wrap-then-print into
it**, so there is now **one authority for "print an error the way Rich's stderr
console does"** rather than four.

**The red tree produced a better structure than the code that was there before
it** — three copies existed and nobody had noticed, because each was correct.
Decision 6 and constraint 4 select this outcome, and it took an accidental compile
break to surface the duplication.

### L192. Economy 2 is guarded — by turning a difference in cost into a difference in kind

**`a_failed_mafter_returns_before_the_cafter_probe`** in `rust/search/plan.rs`,
with a control test beside it.

**The trick, and it solves a problem this desk had recorded as unsolvable: an
*invalid* `-ca` beside a rejecting `-ma`.** In the right order the `-ca` string is
**never parsed**, so the verdict is `Rejected`. **Swap the probes and parsing it
first turns the same case into `Failed`.**

**A difference in *kind*, not in cost — so a test can see it where no timing
instrument can.** `economy_probe` could not reach this economy because its cost is
one file open, and the tools that count opens are SIP-restricted. **The answer was
not a better instrument; it was finding an input on which the economy's absence
changes the *result* rather than the time.**

Falsified with a `cafter_probed_before_mafter` swap on a private copy: red, with a
self-explaining message. **The control earns its place** — without it the first
test would also pass against a screen that never looked at `-ca` at all.

### L193. ⚠ A printed warning was read as noise for hours; a hard refusal was acted on in seconds

**The controlled comparison this desk has been circling all week, both instances
in one seat's own instruments.**

**First: the falsifiers had stopped being able to build and neither said so.**
They sync the crate into a private directory, and two oracle-table tests
`include_str!` files under `thoughts/`, which the sync did not copy. **A falsifier
that cannot build is a falsifier that cannot run** — and nothing announced it.

**Then the engine falsifier *refused*:** `ANCHOR MATCHES 0 TIMES, EXPECTED 1 —
mutation not applied, result meaningless`, because the author's own `finish()`
addition had moved the anchor. **The refusal worked on its author, on their own
file, within seconds.** Without it the run would have read as a **clean pass with
one fewer mutation than the header claimed.**

**Compare L39: `mutate_pi.py` printed `ANCHOR MISSING` honestly for as long as it
existed, and it was read as noise.** Same information. **One printed it and was
ignored; one refused and was obeyed.**

**That is L67 — where a hazard has a mechanism, change the mechanism — with a
control.** Not two anecdotes: the same author, the same class of fault, the same
week, and the only variable is whether the tool **reported** or **refused**.
**Design refusals, not warnings.**

Anchor updated; **all 9 mutations die again.**

### Stop point — `engine-and-codex`, idle at ~81%

**180 lib tests, five build configurations green.** Uncoloured G4 **54 of 54, 0
unstable**; coloured G4 green on all four original cases, **red only on the two
fence cases the renderer refuses by design.** **Engine falsification 9 of 9;
Codex 10 of 11 with the survivor an unreachable branch.**

**Three items remain, all in the handoff with mechanisms: the `HOME`-unset
measurement, `terminal.rs`'s duplicate `chop_cells`, and the wrap-oracle gate over
`session_render.rs`'s copies. None blocks the cutover.**

**Private falsify crates removed, 48 GB free. The pool snapshot at
`/private/tmp/ch-pool-snapshot` stays**, recorded with its date and a
do-not-delete — **it is what makes G4 re-derivable.**

**Addressing note (L170) now applies to this seat too**: a session-wide rename
means bare names stop resolving. **`ListAgents` and copy the row exactly.**

### L194. ⚠ A document edited incrementally drifts exactly like a promoted copy — and this one did

**`engine-and-codex` caught three stale claims in their own handoff on a last
read**, all of their own making, all in the document a successor opens first: a
proof table saying **158 lib tests** (180) and **2 mismatches** (0 of 54); a whole
section describing the projection as **not ported and "the entire remaining G4
gap"** — the thing they had spent the session closing; and a queued heading still
reading **"none started"** after four items were done.

**Their diagnosis, which is the entry: *I updated this document eight or nine
times by patching the section I had just changed, and never re-read the whole.***

**A handoff edited incrementally drifts exactly like a promoted copy does, and for
the same reason. The symlink fix does not help**, because the contradiction is
between two sections of **one** file rather than between two files.

**⚠ AND IT APPLIED TO THIS DOCUMENT.** `state.md` has been appended to nearly two
hundred times, **and its header still read "Phase 1 closing. G2 blocked on one
measurement" while both G4 gates were green** — the first four lines a reader
sees, stale for a day. **Corrected, and the header now carries the reading rule
and the current state explicitly** rather than leaving "later supersedes earlier"
as a convention held only in my own `RESUME.md`.

**The general form: append-only is a mechanism for preserving reasoning and a
convention for finding the current answer.** The second half is the weak one, and
this desk's own rule says a convention loses to a default. **A file whose ordering
rule lives outside it has no ordering rule.**

### L195. Credit correction — one decoder, not three

**I wrote that `engine-and-codex` "ported three decoders' worth of gates". They
ported one — Codex — plus the raw-transcript parser nobody had listed.** **Claude
and Pi are `session-core`'s**, landed and proved at 2,436 and 24,367 cases before
that seat existed, and built upon without touching `session.rs`.

**Eighth attribution or compression error on my side.** Their reason for
correcting it is the same as `slice-reviewer`'s: **a successor reading it would
look in the wrong place for who holds that knowledge.** Attribution here is a
pointer, not credit.

**And a correction in the other direction, from them: the ordering trick's framing
was mine.** *"Assert the ordering, not the outcome"* is what sent them looking for
an input where the economy's absence changes the **result** rather than the time.
Recorded because the desk should show where a good move came from in both
directions, not only where credit was over-assigned.

### L196. ▶ New seat approved: `lexer-tables` — the last implementation seat

**`prompts/lexer-tables.md`.** Scope is **the reference lexer tables plus only the
engine integration they require. Nothing wider** — captain's explicit
instruction. If something outside looks broken, **report it; do not fix it.**

**`message-renderer` stays as interface and oracle owner at its completed seam.**
They wrote the new seat's procedure.

**The prompt carries:** the order by painted characters with TypeScript first at
63.9%; what already exists so none of it is rebuilt (the engine and its two-driver
gate, `syntax_styles.rs` with ancestry-walking `token_style`, complete fence
geometry); the engine contract including the no-match rule's
**`Whitespace`-not-`Text`** detail; **the five traps, each of which has already
produced a wrong answer here**; the four named mutations plus the corpus-adequacy
test; and the G4 rows — **`g4-fence-covered-later` flips, `g4-fence-never-covered`
must stay red for ever and a change that greens it is a defect.**

**The two things that are not tables are stated so they are sequenced rather than
discovered:** JSON is a hand-written scanner in the reference, an imperative port
under any approach at 12.4% of blocks; markdown's `_handle_codeblock` is neither
table nor engine, 0.5%, deferred.

**Two operational facts included because both have already cost time here:**
announce a red tree **before** it lands rather than after it compiles, and
**re-read `RESUME.md` whole before stopping** — a document patched section by
section contradicts itself, which has happened twice (L194).

**And the addressing note** — `ListAgents`, copy the row exactly; several sessions
carry a prefix and their bare names do not resolve.

### L197. "A procedure that needs its author present has not been handed off"

**`message-renderer`'s line, written to the seat they handed to, and it is the
strongest statement of handoff doctrine on this desk.** In full: *if a rule in the
procedure reads as a rule without a reason attached, that is a defect in my
writing, and they should tell me rather than have me explain it once.*

**That inverts the usual failure.** A handoff normally degrades because the
successor does not ask; this one treats every question as **evidence of a defect
in the document** and asks to be told. **The document improves rather than the
author being consulted.**

**They led the briefing with the gate design rather than the tables**, framed as
what decides whether the work is worth its cost — **one table definition building
both the Python lexer that produces the expected stream and the Rust table under
test, no second copy on either side** — with the `using(this, stack=…)` error as
the worked example, **including the line that matters: a gate built against my
reading would have agreed with me, because I would have written both sides from
the same wrong belief.**

**And they added a requirement nobody asked for, which is the one that fails
silently: the gate must assert that every rule the table declares is reached by
the corpus** — and **the corpus must be real fenced blocks in the language.**
TypeScript is **442,034 characters across 915 blocks, 75.5% painted**; **a
hand-written snippet proves nearly nothing about it.**

**"If I go, the document is the successor"** — said to the new seat directly, with
a request to spend the expensive questions early. **That is the oracle role held
correctly: not as availability, but as a document plus a person who knows it is
the document that matters.**

### L198. ▶ SETTLED, CONDITIONAL, OR EXPIRED — read this before re-opening anything

**Requested by `message-renderer`, and it is the gap they named exactly: a
successor who cannot tell a live condition from a closed one will either re-open
something finished or wait on someone who is gone.** Decision 2 is the precedent
— it carried a condition that expired and had to be re-read as settled.

#### SETTLED — no condition, no person, do not re-open

- **The branch is prior art, never an oracle** (d1). **A difference must be earned
  in both directions** (d18) — **not** "the branch is always wrong".
- **Neither reviewer converts to an implementer** (d2). **Its condition expired;
  it is now unconditional.**
- **The oracle is pinned by route digest**, `tests/oracle_digest.py` (d3).
- **Do not delete the Python search authority until the byte harness is green**
  (d13); **deletion is its own final slice.**
- **Promotion is by reference, not by copy** (L12).
- **G4's gate is two instruments and neither retires the other** (L102, L84).
- **`markdown-it` for the parse half** (L129).
- **Stage two: geometry, then reference tables, TypeScript first. `syntect` and
  hand-written lexers are rejected on measurement** (L167).
- **The cutover cannot land until the lexer tables cover code fences** (L182).
- **A compile break you caused is yours to close**, under four checkable
  conditions (L144). **Extending an existing authority beats duplicating in your
  own file** (L149).
- **Eleven preserve-because-wrong behaviours**, including the projection
  disagreeing with the full path, and the two highlight items where **correct
  means doing less.**
- **Five counting units, none unifiable** (L180).

#### CONDITIONAL — live, with the trigger named

| Ruling | Trigger |
| --- | --- |
| Promoted documents are symlinks; **frozen to copies** | **at G5**, when the record stops being worked on (L12) |
| **`/private/tmp/ch-pool-snapshot` is kept** | **until G5 is complete** — it is what makes G4 re-derivable. Not before. |
| **`search-runtime` is woken for the cutover arm** | **when `g4-fence-covered-later` flips green** |
| **`reviewer-profiler` runs G3 measurement, then G5** | measurement unblocked now; **G5's 7 blocked checks need the cutover** |
| **`contract-owner` runs the route flip** | at the cutover — **their 260 intended reds must all turn green** |
| **The unowned parity work** — F1, the C0/`\s`/`\w` set, F16, F17, `HOME`-unset, the wrap-oracle gate over both copies | **required before G5, blocking nothing now** |
| **`message-renderer` holds the oracle role; `slice-reviewer` succeeds them** | if the first cannot answer without a **new instrument** |
| **Markdown's `_handle_codeblock`** | deferred **unless it falls out free** |
| **⚠ Evaluate Arborium and delete the custom lexer engine, tables, generators, aliases/styles and oracle machinery** (`alternatives.md`) | **after G5 and the deletion of the Python search authority.** Admiral, 2026-08-30. **Explicit product intent, not current scope. Goal is maximal safe deletion, not addition beside.** Evaluate against the **held-out** corpus. |
| **⚠ A comparator over link-bearing content must normalise `id=<digits>` in OSC-8 on both sides** (M1, L128) | **fires on whoever next adds a corpus containing a link.** No corpus carries one today, so **nothing normalises it and nothing is failing** — and the first that does **will fail intermittently and look exactly like a real defect.** **A trigger with no owner: it fires on the person who adds the corpus, not the one who caused it.** |

#### EXPIRED OR SUPERSEDED — do not act on these, they are left for their reasoning

- **Decision 2's conditional offer** to convert a reviewer. **Expired.**
- **"Eight for eight, assume the ninth"** — the lazy form of d18. **Withdrawn**;
  the panel-frame example was withdrawn with it and **the rule survived.**
- **The snapshot waiver** (L126). Closed — the clone costs nothing on APFS.
- **"One wiring job stands before G4"** (L168). Wrong; a second sink existed.
- **The `colored_width_gate` "already recorded the answer" move** (L130).
  **Withdrawn at L132** — that aggregate is dominated by a term that cannot fail.
- **Decision 16's fidelity-only framing.** Superseded: **coverage is now a
  requirement**, not only fidelity.
- **Constraint 4's "three configurations".** Superseded by 22aj — **five.**
- **`TIER IGNORED` / `CLOCK IGNORED` as route-wide claims.** Fixed; the guards are
  per-case now.
- **F11, the two `terminal.rs` stderr defects, L146's G5 question.** All closed.

**The general rule this section exists to serve: a ruling with a condition must
name the trigger, and a ruling whose condition has expired must say so where the
ruling is, not somewhere else.** Decision 2 needed a paragraph added to it before
it read correctly, and until that paragraph existed the entry was an open offer
to anyone who found it.

### L199. A finding that has been acted on must say so, or it keeps reading as a proposal

**`message-renderer` applied L198 to their own desk and found the failure it
describes sitting in their costing document.** `M4-stage-two-costing.md` §5 was
headed **"Recommendation"** and read as an open proposal, with option B's numbers
laid out as an argument — **hours after the captain ruled.** A successor finding
it would have re-argued a settled decision from its own text.

**Fixed where the ruling is**, not elsewhere: the section now leads with what was
ruled, what has landed since, and the sentence that stops the re-argument — *do
not re-argue option B from these numbers, the ruling already weighed them.*

**All four findings now carry a status line as the first thing read.** M2 is
marked as **discharging L129's condition** rather than as a measurement, because
*"here is a measurement"* reads as an open question and *"this discharged a
condition"* does not. And M3's **three width reductions deliberately left alone**
are marked a **closed decision rather than an outstanding task** — **that one
would have been tidied by a successor doing exactly what looked like
housekeeping.**

**⚠ THE SHARPER FORM, and it is theirs: a measurement document is more dangerous
than a ruling, because it carries the reasoning for *both* sides.** It is
therefore **the ideal instrument for re-opening something settled, and using it
looks like diligence.** A ruling states a conclusion; a costing hands the next
reader the case against it, fully worked, with no marker saying the case was
heard.

**The general rule: a finding that has been acted on must say what was decided,
in the finding.** L198 said that for rulings. **This says it for evidence, which
is the more dangerous half.**

**And they identified a trigger with no owner, now in L198's conditional table:**
no corpus carries a markdown link yet, so **nothing normalises `id=<digits>` and
nothing is failing** — and **the first corpus that grows one will fail
intermittently and look exactly like a real defect.** **It fires on whoever adds
the corpus, not on whoever caused it**, which is the shape a conditional table
exists to catch.

### L200. A threshold crossing is not a reading — and all three artefacts decay toward confidence

**`message-renderer`'s correction, made against their own two reports.** The
harness told them once that they had **crossed** 75%. Several exchanges later they
reported *"past 75%, unchanged since my last report"* — **converting a threshold
crossing into a standing reading**, which is the same move as converting an
estimate into a measurement.

**The honest form: no current reading; last harness figure was a crossing of 75%,
several exchanges old, position higher by an unknown amount.**

**⚠ AND IT COMPLETES A PATTERN, which is theirs: rulings, costings and
measurements all decay into something more confident than they were.**

| Artefact | Decays into |
| --- | --- |
| **A ruling** whose condition expired (L198) | an open offer |
| **A costing** that was acted on (L199) | a live proposal, **carrying the case against the decision, fully worked** |
| **A measurement** taken at an instant (L200) | a standing fact |

**None of the three decays toward doubt. All three decay toward confidence** —
which is why they are dangerous in a document nobody is watching, and why the fix
is identical in all three cases: **the artefact must carry its own status at the
point where it is read**, not in a companion document, a message thread, or the
author's memory.

**Both corrections in this pair were made by their authors against their own
records, within minutes of writing the rule they broke.** The first mate invented
a context figure after recording the rule against invented figures; the renderer
seat converted a crossing into a reading after recording the rule about naming the
quantity. **Knowing a rule does not prevent the instance** — the third time this
desk has observed that, and the reason every one of these is a mechanism rather
than a caution.

### L201. ▶ TypeScript is landed and gated — and the gate's refusal found the next finding

**`rust/syntax_tables.rs`** — generated, Pygments' own TypeScript `_tokens`, **94
rules over 6 states**, with a `promoted_lexer` lookup that is the whole interface.
**`rust/syntax_table_gates.rs`** — the gate. The fence arm routes a promoted
display name to its table and appends one run per token through `token_style`, and
**`render_plain_code_block` became `render_code_block` taking the lexer, so the
geometry stays one authority and promoting a table cannot move a line.**

**Tree green in all five configurations. 189 lib + 51 doctests**, from 180 + 50.

**The gate:** **589 recorded streams over 313,795 characters of real fenced
TypeScript from session files**, byte-exact against Pygments; **then the rendered
block end to end against Rich — 275 records over 55 fenced cases at five widths,
byte-identical.** Four mutations, all changing the stream: a dropped rule, a
swapped pair, a dropped `bygroups` slot, **a lost push into the template-literal
state.** **The mutation helper refuses when the rule it names has moved, and that
refusal has its own test, so it has been seen to fire.**

**⚠ Coverage: 85 of 94 rules reached, and the other 9 cannot be reached by any
input — with reasons the generator *derived* rather than the author asserted.**
Four are in `commentsandwhitespace`, an `include`-only state nothing transitions
into; two are byte-identical to the rule immediately above; one is anchored `\A`
in a state never at position 0; two are shadowed by a keyword rule whose
alternation contains `super`, **checked against a witness.**

**The generator refuses to emit an oracle carrying an unreached rule it cannot
explain** — the corpus-adequacy requirement implemented as a **refusal** rather
than a report (L193). **And that refusal is what found the next item.**

### L202. ⚠ TSX is a different lexer, not an alias — the costing grouped by fence tag

**`TsxLexer` is 161 rules over 11 states against TypeScript's 94 over 6**, adding
the JSX element, attribute, fragment and expression states.

**The costing's first row — "TypeScript / ts / tsx at 63.9%" — groups by *fence
tag*. By *lexer* it is two families.** So `typescript` and `ts` are done; **TSX is
its own family.**

**Real `tsx` fences are thin: 33 blocks in a 1,200-file harvest, reaching 65 of
161 rules.** So its gate would need **roughly thirty authored cases where
TypeScript needed thirteen** — and **authored cases are a weaker gate than real
fenced blocks in the language**, which is the standard `message-renderer` set.

**RULED: bash/sh next, TSX after.** Ordering is by painted characters, and
`typescript`+`ts` already carry the bulk of that 63.9% while `tsx` is 0.9% of
blocks; bash and sh together are 31.7% of blocks **with a real corpus that can
gate them properly.** **TSX is queued as its own family and flagged: its gate will
rest largely on authored cases, and that must be stated in the gate rather than
discovered.**

**Neither G4 fence row moves** — `g4-fence-covered-later` is python,
`g4-fence-never-covered` is javascript/html/css. **Both stay red exactly as
designed**, and `EXPECTED_UNSUPPORTED` is unchanged at the single `fence lexer`
entry because the markdown corpus's refused fence is python.

### L203. Three reported and not fixed, per the scope rule

**1. ⚠ `generate_markdown_oracle.py` cannot be regenerated reproducibly.** Its
sampled half **re-reads the live session directory, so the same seed gives a
different corpus.** Measured, not inferred. **That is why the rendered-fence gate
is its own fixture rather than cases added to that corpus, and why nobody should
regenerate the markdown oracle casually.** **`message-renderer`'s** — and it is
the L1/L23 class in a worse form: **an oracle that looks regenerable and is not.**

**2.** Two unused imports warn under `cargo test --no-run --no-default-features`,
at `search_views.rs:2144` and `session_render.rs:2727` — **the only warnings in
any configuration.** Neither is `lexer-tables`'.

**3. ⚠ `Syntax.highlight` appends through `Text._text.append`, not
`Text.append`** — so **Rich does not strip control codes inside a fence where the
port does.** Pre-existing on the plain path; **a form feed is the only way in**,
since markdown normalises newlines. **Preserve-because-wrong candidate**, and
`message-renderer`'s surface.

**Reporting rather than fixing is the scope rule working**: all three are outside
the lexer tables, all three are named with mechanisms, and none was silently
absorbed.

### L204. ⚠ `search_query`'s backreference folds case unconditionally — a search-truth defect

**`rust/search_query.rs`, the `Instruction::Backref` arm, ~line 1506:**

    CPython  re.match(r"(\w+)x\1", "PYxpy")        -> None
    CPython  re.match(r"(\w+)x\1", "PYxpy", re.I)  -> matches
    ours     both -> matches

**The case-insensitive direction is right and the case-sensitive one is not.**
**`ch search '(\w+)\1'` on the native route returns hits CPython would not, and
nothing in the output says so** — the extra sessions look like ordinary results.

**Standing constraint 5's family one level down: a fold applied where no flag
asked for one.** Not user-visible today, because the shipped route is Python —
**it becomes user-visible at the cutover, so it is required before it.**

**⚠ How it surfaced, and the route is the finding.** Bash's heredoc rule is
`<<-?\s*('?)\\?(\w+)[\w\W]+?\2` — **it backreferences the opening word to find the
closing one.** On **2 of 1031 real shell blocks** a heredoc opened with `<<'PY'`
ended at the **`py` inside `print("hello from uv python")`.**

**No hand-written snippet would have contained that.** It took a **real corpus**
of a language **whose grammar uses a backreference at all — and of the five
families, bash is the only one that does.** The corpus-must-be-real rule earning
its keep on the one family where it could.

**Reported with both directions as a ready falsification, including the control
that stops a fix from turning the fold off everywhere.** File not touched.

### L205. Bash is finished and deliberately held out of the tree

**189 rules over 9 states under `MULTILINE`. Corpus: 1031 cases, 260,900
characters of real shell** from `bash`, `sh`, `zsh`, `shell` and `ksh` fences,
plus 20 authored. **132 rules reached; 57 unreachable with derived reasons** —
`basic`, `data` and `interp` are `include`-only states nothing transitions into;
`curly` and `math` open with catch-all rules shadowing most of the shared body
they include — **each checked against a witness.** Five mutations, all changing
the stream, **including one that turns DOTALL *on*** — falsifying the flag channel
landed the same day.

**Held out because gating it found the defect above.** Fixtures in place, gate
parked at `teammates/lexer-tables/bash-gate.rs.pending`, and the generator's
promoted list carries a **`PAUSED` line naming the reason.** Re-landing is two
edits **in the same step**: paste the gate back, restore `("bash", "Bash")` to
`FAMILIES`, regenerate.

**Their reason is the rule: a promoted family with no gate is the one state this
work must not stop in** — which is why bash is **absent** rather than
**promoted-and-red.** A red gate is a specification; a promoted family with no
gate is a claim nobody is checking.

### L206. A seeded shuffle over a live directory is not a seed

**Their harness took a seeded shuffle's prefix of the session directory, and that
directory is live: the same seed gave 589 blocks, then 465, then 507 — within an
hour.** **Adding a file reshuffles every position**, so the sample is not a
function of the seed at all.

**Fixed by ordering on a hash of the path**, so a new file lands in **one** place
and a regenerated corpus **grows at its tail rather than churning.**

**And the thing it protects is named: a rule that only one sample happened to
reach.** **One did disappear between two runs**, and it now has an authored case.

**Same class as `generate_markdown_oracle.py`'s irreproducibility (L203), found
independently and fixed at the mechanism rather than documented.** Two instruments
on this desk sampled a live directory and called it seeded.

### L207. ⚠ The backreference defect was already fixed — L204's report was stale

**`search-runtime`, on a current build:** the `Instruction::Backref` arm carries
`ignorecase: flags.ignorecase` from compilation, `search_query.rs:1506` uses
`literal_matches_icase` when the pattern asked and plain equality otherwise, **and
two tests pass — including the control `lexer-tables` specified.** The comment
there names the exact `(\w+)x\1` case.

**⚠ NOT CLOSED, because one thing does not add up and it is routed between them.**
Pygments' bash lexer compiles under **`MULTILINE` alone, no IGNORECASE** — so
`\2` should already be case-sensitive there, **and a heredoc opening `<<'PY'`
should not terminate at the `py` in `print("hello from uv python")`.**

**Either the observation was against an older tree — in which case bash is
unblocked — or the fold is entering by a path other than the flag, which is a
different defect from the one reported.** `lexer-tables` is reproducing on a
current build. **Bash stays out until it is settled**: a promoted family with a
gate that passes **for the wrong reason** is worse than one with no gate.

### L208. ▶ ADOPTED: a report about tree state carries when it was taken

**`search-runtime`'s rule, adopted effective immediately, and it is mechanical
rather than a caution.**

**Three stale reports today** — the `wrap_preserving_spaces` defect,
`views-and-colour`'s eleven stderr cases, and L204's backreference — **each
accurate when taken and obsolete when acted on.** `views-and-colour` reached the
same conclusion independently after theirs.

**Their diagnosis, and it is not carelessness: four sessions edit this tree
continuously, and a report crosses a fix in the time it takes to write the
message.**

**A timestamp or a digest would have let the last one be answered in one read
instead of four.**

**This is L200's third artefact in a fourth place.** A ruling decays into an open
offer; a costing into a live proposal; a measurement into a standing fact; **and a
report about tree state decays into a claim about the *current* tree.** All four
decay toward confidence, and all four are fixed the same way — **the artefact
carries its own status where it is read.**

**On the offered trade — corrected, at `search-runtime`'s request, to what
happened rather than to an apportionment.** I had recorded the trajectory to 94%
as mine to own. **Their objection: the offer was bounded, the falsification was
already written, the reasoning that the cutover had receded was correct, and they
had independently decided they would have taken it. The judgment was sound in both
directions and the arithmetic ran out.**

**That is more accurate and more useful than an attribution**, and it is the third
time on this mission a teammate has corrected the first mate for over-assigning
fault to themselves. **A record that apportions where nothing was misjudged is
inaccurate in the same way as one that apportions wrongly** — and a successor
reading "the first mate spent a teammate's context" learns to be cautious about
offering bounded work, which is the wrong lesson. **What happened is that a
correct decision met a finite resource.**

### Stop point — `search-runtime`, idle at 94%

**Nothing in flight, no production edit half-applied. Tree green: 191 lib tests,
1 bin, both build modes clean.** The backreference fix needed nothing — the report
had crossed the instruction.

**Their handoff puts the cutover at the very top**, so a successor meets *"If you
are taking the cutover, read this first"* before anything else. It carries **the
three things nothing type-checks**: the `&arguments[1..]` off-by-one, the two
width resolvers and which arm takes which, and warnings printing before the match
with `eprint!`.

**And it says to *diff* against `probes/searchdriver` rather than read it** —
because **diffing is what caught the off-by-one, on a pass whose stated purpose
was checking something else entirely.** It names G5's runbook as the verification
**so nobody arranges that separately.**

**What they learned about the fold path, bounded as stated:** `Instruction::Backref`
carries `ignorecase` from compilation and `search_query.rs:1506` branches on it;
two tests hold both directions. **"The fold path is not applied anywhere it was
not asked for, at least at that site. I did not survey the others and would not
claim more than I checked."**

### L209. ⚠ The bash defect is real and it is DOTALL, not the fold — a convenience default standing in for two specifications

**The fold is clean.** `Regex::compile(pattern, ignorecase)` passes the caller's
value straight through, and the only `ignorecase: true` literal in the file is in
a test. **A backreference compiled with `ignorecase = false` compares
case-sensitively.**

**But `Regex::compile` hardcodes two other flags:**

    pub fn compile(pattern: &str, ignorecase: bool) -> Result<Regex, ()> {
        Regex::compile_with_flags(pattern, ignorecase, true, true)
    }
    //                                     ignorecase  multiline  dotall

**It forces `multiline: true` and `dotall: true` unconditionally.** Pygments' bash
lexer compiles under **`MULTILINE` alone — no DOTALL.** **Under DOTALL `.` matches
newlines**, so a heredoc rule scanning for its closing word **runs past the end of
its line** and finds the `py` inside `print("hello from uv python")` on a later
line. **The reported symptom exactly, arriving through a flag rather than a
fold.**

**Labelled by its finder as a hypothesis fitted to the symptom, not a
measurement** — flag plumbing read, the case not run. **One falsification names
it:** compile the same rule with `compile_with_flags(pattern, false, true,
false)`. **If the heredoc stops terminating early it is DOTALL; if it still
terminates it is a third thing** and must be reported rather than assumed.

**⚠ WITHDRAWN — I assigned this to the two-width-resolvers class and it is not
that shape.** See L210. `Regex::compile` has **exactly two production callers**,
both `ch search`'s own query compilation, **which is the route pinned to CPython
with MULTILINE|DOTALL. Every other caller already uses `compile_with_flags`.** The
hardcoded defaults belong to their only callers — **one specification, not two
sharing a default.** The grep I asked for is what disproved my own framing.

**Routed to `lexer-tables` with the falsification. Bash re-lands when the gate
passes for the *right* reason** — their own rule, and the strongest form of it:
a promoted family with a gate passing for the wrong reason is worse than none.

**They already hold the instrument, pointed the other way: one of their five bash
mutations turns DOTALL *on*.**

**And the handover is the model at 94%:** mechanism found in one read, hypothesis
labelled as such, falsification named, fix shape sketched, **handed over rather
than chased** — with the cap holding regardless of what was found.

### L210. ▶ Bash is landed. DOTALL falsified, the fold confirmed, and my class assignment withdrawn.

*Reported with the L208 field: taken 2026-08-29T14:12Z, `search_query.rs`
e420a4a12126, `syntax_lexer.rs` 5a53411818e6, `syntax_tables.rs` 167484eab53b.*

**The falsification, run on the real heredoc rule and the real block:**

    MULTILINE only         -> ...print("hello from uv python")\nPY
    MULTILINE + DOTALL     -> ...print("hello from uv python")\nPY
    IGNORECASE + MULTILINE -> ...print("hello from uv py

**DOTALL changes nothing, and there is a reason it cannot: the rule scans with
`[\w\W]`, a character class, not a dot. A class crosses newlines whatever DOTALL
says.** **IGNORECASE reproduces the symptom character for character.** So the fold
was the cause and `query-semantics` fixed the right thing — **a good hypothesis
that the measurement disposes of.**

**And it is settled independently: the flags were already right when the failure
was seen.** `message-renderer` landed `LexerFlags` and `compile_with_flags`
**before** the bash table was generated, and the table declared `dotall: false` in
the run that produced the two divergences. **DOTALL was off the whole time.**

**⚠ My class assignment is withdrawn, disproved by the grep I asked for.**
`Regex::compile` has **exactly two production callers** — `search_query.rs:152`
and `:168`, `compile_search_term` and its escaped-literal sibling, **both `ch
search`'s own query compilation, the route the module header pins to CPython with
MULTILINE|DOTALL.** Every other caller already goes through `compile_with_flags`.
**The defaults belong to their only callers: one specification, not two sharing a
default.** **Naming a class is a claim, and this one was made on a resemblance
rather than a count.**

**Bash landed and gated: 1031 of 1031 recorded streams byte-exact; 132 of 189
rules reached with the other 57 unreachable and derived; the rendered block
against Rich over 280 records at five widths.** Five mutations, all dying —
**including one that turns DOTALL *on*, falsifying the flag channel from the other
side.**

### L211. The mutation that did not die is the one that taught something

**One of the five was aimed wrong and the mutation test is what said so.** The
push-one-to-stay mutation, aimed at the backtick rule, **left all 1031 streams
identical.**

**`backticks` is `root`'s body plus a pop, and its own nested-backtick rule is
shadowed by that pop** — so a backtick that stays in `root` produces the same
tokens. **The corpus reaches it; the state is genuinely unobservable in the
stream.** Re-aimed at the push into `string`, whose content rule takes a whole run
as one token where `root` would cut it into several.

**Their line is the entry: a mutation that dies proves the gate sees it; the one
that did not die is the one that taught me something.**

**That is 22i's counterpart.** This desk has recorded many times that a surviving
mutation means the corpus is blind. **Here a surviving mutation meant the *state*
was unobservable — a fact about the grammar, not about the corpus or the gate** —
and only aiming a mutation at it could have revealed that.

### L212. An independent evaluation of Rust alternatives is in flight — what it must beat

**Captain's note, 2026-08-29: a fresh Codex researcher is evaluating
battle-tested Rust alternatives to the Pygments-table plan.** **`lexer-tables`
does not pause. The report is evidence for possible simplification, not a new
gate.** The captain routes the recommendation when ready.

**Recorded now, before it arrives, so it can be read against a fixed bar in one
pass rather than re-litigated.** These are measured, promoted, and in
`M4-stage-two-costing.md`:

**What the surface is.** 3,000 real fenced blocks, 1.37M characters. **39.4% of
fenced characters get a non-default colour.** **TypeScript-family is 63.9% of all
painted characters.** `text` fences are 22% of blocks and Pygments paints none.

**What `syntect` measured at, and any alternative must be measured the same
way.** **No TypeScript, no TSX, no plain-text syntax in the default set: 488 of
1,200 sampled blocks find no syntax at all, and every TypeScript-family block is
among them.** No Monokai theme. **And where both lexers do run, run-boundary
agreement is 62.3% overall** — bash 55.9%, json 60.6%, sh 47.9% — **an upper bound
on colour agreement, because no theme repairs a boundary in the wrong place.**

**The comparison that is fair and does not require inventing a token mapping is
where each puts a run boundary.** That is the measurement to ask any alternative
for.

**What the current plan has already delivered, which is the real baseline now** —
not the plan as costed, but the work as landed: **TypeScript 589 streams over
313,795 characters byte-exact against Pygments plus 275 rendered records against
Rich; bash 1031 of 1031 byte-exact plus 280 rendered records; a lexer engine gated
against Pygments' own driver with no second copy on either side; and a promotion
procedure a fresh seat used to land a family the same day.**

**So the question an alternative now answers is not "is this cheaper than writing
2,482 lines" — two of five families are already written and gated.** It is
**whether it is better than transcribing three more tables against an engine that
exists and a procedure that has been used.**

**And one thing it cannot buy, stated so it is not assumed away: the current path
makes the divergence *enumerable*.** Decision 16 conceded fence-interior parity is
statistical either way; **the table port makes the difference measurable rather
than merely plausible**, and that is the property the captain's Option A ruling
turned on.

### L213. ▶ Three of five families landed. Ruled: python next, json last.

*Taken 2026-08-29T14:19Z — `syntax_tables.rs` 746a25da6dbc,
`syntax_table_gates.rs` d82fde80b7a2, `session_render.rs` 2c5b71207e87.*

| Family | Table | Corpus | Rules reached |
| --- | --- | --- | --- |
| TypeScript | 94 rules, 6 states | ~500 cases, ~270,000 chars | 85 of 94 |
| TSX | 161 rules, 11 states | 97 cases, 28,946 chars | 145 of 161 |
| Bash | 189 rules, 9 states | 1031 cases, 260,900 chars | 132 of 189 |

Plus the rendered block against Rich for all three at five widths. **204 lib +
52 doctests, five configurations, zero warnings.** `Unsupported` unchanged at its
single entry; **both G4 fence rows still red as designed.**

**Ruled: python next, json after.** Their case — python is a table on machinery
used three times, json is an **imperative port of 263 lines with no table, no
generator and no corpus-adequacy story**, and python is the row that flips
`g4-fence-covered-later`. **The argument I added: json needs none of this seat's
machinery, which makes it the piece most safely left to a successor.** Same cut as
the engine-versus-tables boundary — **give the accumulated context the work that
depends on it.**

**At 50% of the context window (harness-volunteered, 14:20Z), plan for this seat
not finishing both.**

**TSX's gate states in its module doc that its evidence rests largely on authored
cases** — 66 real blocks from a **6,000**-file harvest against TypeScript's
several hundred, with 30 authored carrying the rest. **Their sentence is why it is
stated rather than noted: a snippet cannot surprise the way a real block can, and
the backreference defect is what that difference costs.**

### L214. Two surviving mutations, same symptom, opposite diagnoses — now side by side

**Bash's survivor meant the *state* was unobservable** — `backticks` is `root`'s
body plus a pop, its nested rule shadowed by that pop, so the corpus reaches it
and the grammar has no observable difference there.

**TSX's survivor meant the *corpus* was blind** — the keyword/`super(...)` swap
changed nothing because the corpus contained no `super(` at all. **Ordinary
reading; the case was added.**

**Same symptom, opposite diagnosis, and only reading the failure told them
apart.** Both are now documented in one file, **so a successor meeting a surviving
mutation has two worked readings rather than a rule.**

### L215. ⚠ OPEN, captain-level: what happens at the cutover for a fence we will never cover?

**`g4-fence-never-covered` is specified to stay red for ever**, and the renderer
**panics** on a fence whose language Pygments has a lexer for but which is not
promoted. **Five families will be covered; Pygments ships 259 lexer files.**

**So the terminal state is undefined.** Panic is unshippable. **Rendering plain is
a divergence** — Pygments would colour it, and that is the silent-improvement
class the typed `Unsupported` design exists to prevent, arriving from the other
direction.

**Neither the seat's question nor its work.** It does not change which family is
next. **But "the cutover waits on stage two" (L182) currently has no definition of
when stage two is finished**, and that definition is a captain-level decision
about acceptable divergence rather than an engineering one.

**On the alternatives review, one point only `lexer-tables` could make:** if the
report names `two-face` or a bundled `.sublime-syntax`, **those add grammars to
`syntect` and do not touch the boundary or theme numbers** — **and the 62.3%
run-boundary ceiling was measured with `syntect`'s grammars already present.**

### L216. ⚠ ADMIRAL: parity is not required for syntax highlighting — and that changes which measurement decides

**Clarification, 2026-08-29, syntax highlighting only.** **Perfect Pygments parity
is not required.** A mature Rust alternative is **preferred** if fidelity is
*pretty good* and it avoids thousands of maintained lines. **Reject options whose
quality is mediocre or whose integration cost erases the savings.** No change or
pause until the captain reviews the Codex report and rules.

**⚠ The consequence nobody has stated: our disqualifying measurement was designed
for a parity bar and is the wrong instrument for this one.**

**The 62.3% run-boundary agreement was chosen because it is comparable without
inventing a token mapping — an upper bound on *colour* agreement under a parity
standard.** Under *"pretty good"*, it answers a question nobody is now asking:
**two highlighters can disagree on where a run ends and both look correct to a
reader.** **Boundary agreement is a proxy for parity, not for quality.**

**The right measurement under the new bar is different and has not been taken.**
Something closer to: **do the two agree on which spans are keywords, strings,
comments and identifiers** — token *class* rather than token *span* — **and does
the rendered block read correctly.** That is the measurement to ask the report
for, and if it is not there, it is the gap.

**What survives the bar change unchanged, because it is coverage rather than
fidelity.** `syntect`'s default set has **no TypeScript, no TSX, no plain-text
syntax: 488 of 1,200 sampled blocks find no syntax at all, and every
TypeScript-family block is among them.** **TypeScript-family is 63.9% of all
painted characters.** **Rendering 63.9% of painted characters as plain text is not
*pretty good fidelity*; it is absence** — and no relaxation of a parity bar
reaches it. **`lexer-tables`' note is the one that matters here: `two-face` and
bundled `.sublime-syntax` files *add grammars* and would address exactly this,
while touching neither the boundary nor the theme numbers.**

**⚠ And the savings side needs a correction before it is weighed: the tables are
generated, not hand-written.** **The maintained artefacts under the current path
are the generator and the engine — not the 444 rules already landed, nor python's
435 or json's 263.** A regenerated table is not a maintained line. **So "avoids
thousands of maintained lines" is measuring the wrong quantity if it counts the
tables**, and the honest comparison is **generator + engine + promotion procedure**
against **crate + grammar bundle + theme + integration.**

**Three of five families are already landed and gated**, so the alternative is no
longer weighed against writing them — **it is weighed against transcribing two
more against machinery used three times, one of which (json) is an imperative port
that no alternative avoids either.**

**No action taken. `lexer-tables` continues on python, already told a report is in
flight and not to gold-plate against it.**

### L217. ▶ Python landed — four of five families. `g4-fence-covered-later` should flip.

*Taken 2026-08-29T14:31Z — `syntax_tables.rs` e2a0c286f1c3,
`syntax_table_gates.rs` d3aca1b779b9, `session_render.rs` b5afffd97d9a.*

**211 lib + 52 doctests, five configurations, zero warnings. Four promoted and
gated: TypeScript, TSX, Bash, Python.**

**Python is the largest by a wide margin — 435 rules over 49 states** against
TypeScript's 94 over 6. 270 cases, 63,591 characters. **315 rules reached, 120
unreachable with every one derived. It reproduced Pygments byte-exact on its first
run.**

**Two things different in kind rather than size.** It is the **first family to use
`using(this)` in production** — `soft-keywords-inner` re-lexes a captured group
with the same table, **so the re-entry path whose `state=` trap was found by the
engine's own gate now runs outside that gate.** And **110 of the 120 unreachable
rules are in `include`-only states**: python factors `keywords`, `expr`,
`numbers`, `name`, `builtins`, `magicfuncs` and the string bodies into states
nothing transitions into, and the metaclass copies each into every including
state. **The copies are reached; the originals cannot be.** Same mechanism as
bash's `basic`/`data`/`interp` **at four times the scale — so the unreachable
fraction is a property of how a family is written, not a smell.**

**⚠ `EXPECTED_UNSUPPORTED` went empty, and the seat did not leave it there.**
Promoting python emptied it, exactly as the procedure's §4 step 3 predicted. **But
an empty set because nothing in the corpus reaches the path is indistinguishable
from an empty set because the path is gone** — the omission-dependent green the
captain caught on the G4 fixture, **arriving in the seat's own work and caught by
its author.**

**The refusal is now asserted directly:**
`a_fence_in_an_unpromoted_language_is_still_refused` requires **javascript, html,
css, js and rust** fences to return `Unsupported("fence lexer")` — each reaching a
Pygments lexer with no promoted table. **The property no longer depends on what a
corpus happens to contain, and `g4-fence-never-covered` stays red by the same
set.**

**Python's corpus is the most authored of the four and its gate says so.** Real
fenced Python reaches **198 of 435**; the rest is **generated rather than written
out**, because the surface is combinatorial — one rule per prefix per quote style,
`rf` `f` `rb` `r` `u` `b` and bare against four quote styles, then a state per
combination.

**⚠ Correction to `M4-stage-two-costing.md`: it records "no `combined()` state
anywhere in the five". Python has fourteen**, `_tmp_0` through `_tmp_15`. **Costs
the driver nothing** — the metaclass resolves them before `_tokens` exists — **but
the claim is wrong and a successor sizing python from it would be surprised.**
L199's shape inside the costing itself: **a measurement accurate over what was
examined, read later as a statement about the five families.** Routed to its owner
to fix where the claim is.

**Remaining: json** — the one with **none** of this machinery, a hand-written
scanner in the reference, an imperative port under any approach, 263 lines, 12.4%
of blocks — **then markdown**, 0.5%, whose `_handle_codeblock` callback **the
generator refuses rather than dropping.**

**`tests/data/lexer-tables/` is 12 MB across eight fixtures**, comparable to
`parse-round-trip-fixtures` at 8.3 MB. **Every one regenerates from a checkout.**

**The gate run is with `engine-and-codex`**, who have held the launcher window
before. `lexer-tables` cannot take it.

### L218. ⚠ Three instrument failures from one seat, and they form a progression toward looking correct

**Re-measured rather than taken on trust, and the correction's own number moved:
python has *sixteen* combined states, `_tmp_0` through `_tmp_15`, with 64
transitions into them.** The other four families have none. **Cost conclusion
unchanged** — `RegexLexerMeta` resolves a `combined()` into an ordinary named
state before `_tokens` exists, so the driver never sees one.

**Even a correction should be measured.** The reported figure was fourteen.

**⚠ Why the scan missed them, and it is the third and most disguised of three.**
The classifier tested `target.startswith("_")` — **a correct test** — sitting
after a branch that caught tuples. **Pygments stores every named push as a tuple,
including a single one**, so the string branch was **unreachable** and the
combined names were inside the tuples already counted. **The bucket printed zero.**

**Nothing looked missing, because nothing was. Every rule landed in some bucket
and the totals were exhaustive. The wrong bucket held them.**

**The progression, all three from one seat in one day:**

| | Failure | What it was |
| --- | --- | --- |
| 1 | `_tokens` held a bound `match` method | a probe that **could not see** |
| 2 | `using()` lives inside `bygroups`' arguments | a calibrated detector **aimed one level too high** |
| 3 | the string branch sat after a tuple branch | a detector that **could see, was aimed right, and was unreachable** |

**Their observation is the entry: the progression is toward failures that look
more and more like working instruments — and only the *shape of the answer* gave
any of them away, a zero where a zero was implausible.**

**Nothing on this desk detects the third form.** Calibration proves sensitivity;
aim was the second's gap and is checkable; **reachability of a classifier's own
branches is checked by nothing we have.** The only defence used here was
**disbelieving a plausible zero**, which is 22c — *no finding from an aggregate
alone* — and it is the fourth time that rule has been the last line.

### L219. Ruled: fold the direct refusal into the procedure, with attribution

**`message-renderer` declined to change §4 for `lexer-tables`' improvement, on the
grounds that they would rather the discoverer own the text. Ruled the other way.**

**The procedure is what the next person reads. An assertion living only in a test
file is not in the procedure**, and the next family — json, then markdown, then
anyone porting a sixth in six months — inherits §4 rather than that test.

**Fold it in with attribution.** The improvement: §4 step 3 predicted
`EXPECTED_UNSUPPORTED` would empty and stopped there. **An empty set because
nothing reaches the path is indistinguishable from an empty set because the path
is gone** — so the refusal is asserted **directly**, against named fence languages
that reach a Pygments lexer and have no promoted table.

**That is the corpus-adequacy rule applied to an assertion rather than to a
corpus, and it arrived from the person who *read* the procedure rather than the
one who wrote it** — which is the procedure working as designed, including the
part where following it exposed a hole in the step being followed.

**And `using(this)` reaching production is the engine gate's discovery becoming
load-bearing.** The `state=` trap was found on a synthetic table; it now runs on
real python content **outside** that gate, where the stream comparison against
Pygments is what would catch a wrong port. **The two-driver design arriving where
it matters.**

### L220. §4 folded — and a sixth trap that is the defence against all three instrument failures

**§4 step 3 now carries the direct refusal**, with the reason before the
instruction: once the set empties, **an empty set from absence is
indistinguishable from an empty set from deletion, and the gate passes either
way.** javascript, html, css, js and rust must each return `Unsupported("fence
lexer")`. **Credited to `lexer-tables`, and marked as *superseding* the step
rather than supplementing it — so nobody follows the old one and stops.** That is
L198's rule applied inside a procedure rather than to it.

**⚠ A sixth trap added to §2, and it is the important half.** The `combined()`
miss was **not a wrong number in a costing — it was a *classifier* failure, and
every family's generator has a classifier in it.** The trap: **your own branches
must be reachable, and an exhaustive total is not evidence that they are.**
*Nothing looked missing, because nothing was.*

**It carries the three-failure progression, because the shape only reads with all
three, and it ends actionable rather than as a caution:**

> **When your generator counts, assert each bucket is non-empty where it should
> be, or print an instance from each and read it.**

**That is the only defence that would have worked on any of the three** — the
probe that could not see, the detector aimed one level too high, and the branch
that was unreachable. It is 22c turned into an instruction a generator author can
follow rather than a rule they must remember.

### L221. Declining to duplicate a true rule into the wrong document

**They left *"even a correction should be measured"* at team level rather than
folding it into their procedure**, on the grounds that it is a **method** rule
rather than a lexer-table rule, **and duplicating it is the drift this desk has
argued against.**

**Worth recording as the counterweight to "write it down".** A procedure that
accumulates every true statement stops being usable, and the second copy drifts —
which is 22f and L12 arriving in a document rather than in code or a corpus.

**The test they applied: does the next person need this *to do this task*, or is
it something they should know anyway?** The first goes in the procedure; the
second stays where it is and gets linked.

**And they noted what it bought without importing it: it is the reason M4's number
is right.** Fourteen was reported in good faith; it is sixteen.

**Tree: 211 lib + 1 bin + 52 doctests, zero warnings in every configuration** —
grown by twenty-two since their last report as python and bash gates landed, and
all of it green.

## ▶ `g4-fence-covered-later` IS GREEN — 2026-08-29

| case | result |
| --- | --- |
| `g4-list` | green |
| `g4-default-matches` | green |
| `g4-full` | green |
| `g4-matches-no-metadata` | green |
| **`g4-fence-covered-later`** | **green — the flip** |
| `g4-fence-never-covered` | **red, by design and permanent** |

**Guards: none fired.** Python landed correctly — byte-exact against the reference
across all five colour tiers and all seven clocks.

### L222. A display cap made a correct output misleading in both directions

**The gate printed `FAILED 35 differences` and only ten `DIFFERS` lines — a
display cap.** The distinct case ids across the **whole file** are exactly one,
and **35 = 5 tiers × 7 clocks × 1 case**, so the arithmetic and the id set agree.

**Reading the ten printed lines alone would have understated it. Reading the
headline alone would have said the gate failed.** Neither is wrong; both are
partial, **and the correct reading required going past the display to the file.**

**This desk has recorded gates that print too little (22x) and headlines whose
scope exceeds their evidence (the tier guards). This is a third: a truncated
display, where the tool is behaving correctly and the number shown is not the
number that matters.**

### L223. Two corrections from the person who ran it, both against my framing

**The launcher window was not needed and was not taken.** The gate takes
`--subject` and `--reference` as explicit binary paths; the reference defaults to
`.venv/bin/ch-legacy`. **They checked the harness for `~/.local/bin`, `uv sync`
and `uv tool install` before acting — none appears.** **My premise that this was
"the only thing on the mission that needs someone who can install" was wrong**,
and they said so rather than holding an exclusive resource they did not need.

**And they rebuilt the driver before running**, so the run graded **today's tree**
rather than yesterday's binary — the stale-binary hazard `tests/run_all.sh`
refuses on. **Stated explicitly because a green from a stale driver would have
looked identical.** That is the L208 report-timestamp discipline applied to the
*subject* rather than to the report.

### L224. ⚠ The terminal-state question (L215) is now the whole critical path

**With five of six green and the sixth red by design, the only thing between the
mission and the cutover is what `g4-fence-never-covered` represents.**

**The renderer panics on a fence whose language Pygments can highlight and we have
not promoted.** Four families are promoted; **json and markdown remain, and
Pygments ships 259 lexer files.** **So a user with a javascript, html or css fence
hits a panic on the native route — and javascript, html and css are exactly the
languages that row pins.**

**json and markdown are no longer the critical path.** Completing them changes
nothing about this: **the panic is for languages that will never be covered, not
for the two that are pending.**

**The decision, and it is the captain's because it is about acceptable
divergence:** panic is unshippable; **rendering an uncovered fence plain is a
divergence — Pygments would colour it** — and it is the silent-improvement class
inverted, since the port would render *less* than the product does.

**Everything else is built:** both gates, the cutover arm rehearsed three times,
G5's runbook with seven checks waiting, `contract-owner` on call for the route
flip.

### L225. ⚠ MEASURED: the tail does not terminate — 5.6% of fenced blocks after every planned family

**Over the same 3,000 real blocks as the costing, after TypeScript, TSX, bash,
json, python and markdown all land:**

    JavaScript  2.97%   CSS 0.83%   HTML 0.47%   XML 0.43%   SQL 0.33%
    JSX 0.23%   Awk 0.10%   YAML 0.10%   Bash Session 0.07%   Diff 0.03%

**Every one returns `Unsupported("fence lexer")` today, and
`ColouredPanelSink::emit` panics on a refusal.** That was right while nothing
user-facing could reach it. **On the cutover it means `ch search` crashes on any
session containing a CSS or SQL fence.**

**No amount of promotion ends it: Pygments has 500-plus lexers and the tail is
real content, not exotica.**

**RULED, the half that is mine: JavaScript is promoted next, before json.** 2.97%
alone, the largest single item, **and `TypeScriptLexer` inherits `JavascriptLexer`
so its rules are already understood.** **Residue 5.6% → ~2.6% before the captain
rules**, which is the cheapest available influence on the decision. Not a scope
widening — a lexer table on machinery used four times.

**ESCALATED, the half that is not: what a known-but-unpromoted language does at
the cutover.**

**`message-renderer`'s framing, carried intact because it is what makes it
decidable: this is option B's shape at an order of magnitude smaller — ~2.6%
against the 22% that ruling weighed — and unlike then, there is no alternative
that finishes.** The earlier ruling rejected shipping 78% coverage **when full
coverage was reachable.** It is not reachable, **and the only other option is a
route that crashes.**

Size, stated: ~2.6% of fenced blocks, fences ~4.5% of text blocks, **so roughly
0.1% of message bodies.**

**And the condition that distinguishes it from the rejected option: a decision
with a gate, not a fallback.** Assert **directly** that a known-but-unpromoted
language renders plain — the shape `lexer-tables` used for the refusal — and put
it in the change log as a named divergence with its measured size. **A silent
fallback is exactly what the typed `Unsupported` exists to prevent; a ruled
degradation with a test is not the same thing.**

### L226. A false comment describing the behaviour we want rather than the one we have

**`render_code_block` already has a branch rendering an unpromoted-but-known
language plain — and it is dead**, because the token walk refuses before reaching
it. **And `promoted_lexer`'s doctest says *"Not promoted, so the fence renders
with no lexer rather than approximately"*, which is false about the system
today.**

**Third instance of the false-comment class, and the most dangerous form: it
describes the behaviour we would want rather than the behaviour we have** — so it
will read as **confirmation** to whoever implements the ruling, rather than as a
claim to check.

**Ruled: correct the comment now, leave the dead branch and the behaviour.** The
comment is a defect today; the branch is a decision.

**And it was reported rather than acted on, with the right reason: a behavioural
ruling should not be decided by whoever noticed it.**

### L227. ⚠ The brief I sent up was wrong in two ways, and both change the decision

**`engine-and-codex` corrected it before the captain could act, and both
corrections are mine.**

**1. It is a process panic, not a rendering difference.** `ColouredPanelSink::emit`
calls `panic!` on `Unsupported`. **I framed the decision as one about "acceptable
divergence", which invites a judgement about how different output may look. The
actual question is whether `ch search` may crash on ordinary content.** The
divergence framing is the shape of the *remedy*, not of the *status quo* — and
putting it first makes the crash sound like one option among two rather than the
thing being escaped.

**2. ⚠ The exposure figure is disputed, and the shapes differ as much as the
sizes.**

| | `message-renderer` | `engine-and-codex` |
| --- | --- | --- |
| corpus | ~3,000 fenced blocks | **366 Claude sessions, 9,706 tagged blocks** |
| refusing | **5.6% of blocks** | **11.0% of blocks, 33.3% of sessions** |
| top items | JavaScript 2.97, CSS 0.83, HTML 0.47, XML 0.43, SQL 0.33 | **sql 272, rust 189, xml 158, js 145, html 110, yaml 85** |

**`sql`, `rust`, `xml` and `yaml` together outnumber js/html/css by more than two
to one in the second — and none of the four appears in the first's top five.**

**Method stated rather than buried, and it is conservative:** aliases resolved
from an observed mapping rather than by calling `lexer_for_tag` per tag, **any
unmappable tag counted as refusing** — so **11.0% is an upper bound.** The four
largest were confirmed individually to resolve to real Pygments lexers that
`promoted_lexer` does not cover.

**Routed to the two of them to reconcile. I am not picking a number, and the
captain has been told it is disputed.** **`rust` at 189 is the first thing to
check** — a Rust project's own sessions being full of Rust fences is exactly the
corpus-specific effect that differs between two harvests and is invisible from
either side alone.

**3. And a smaller correction: markdown *is* in the refusing set**, 35 occurrences
between `md` and `markdown`, **so completing it does reduce the exposure.** I told
the captain json and markdown change nothing about the size. Wrong.

**What did not change: JavaScript is still promoted next**, and the ruling that a
behavioural decision belongs to the captain rather than to whoever noticed it.

**The reporter explicitly declined to propose a remedy** — *"whether to promote
more families, downgrade the panic to a plain render, or hold the cutover is a
product call"* — **and said only that the captain should be deciding about a crash
on a third of sessions rather than a rendering difference on three languages.**

### L228. ⚠ It is not a crash. It is a truncation that ends in a crash.

**Measured on the panel path with the offending session not first:**

    panels visible before the crash:   11
    bytes on stdout before the crash:  20,700

**Results stream normally, then stop at an arbitrary point.** No `catch_unwind` in
the loop, no `panic = "abort"` — it unwinds out of `main`.

**⚠ Why that decides the framing. stdout carries plausible, complete-looking
results; stderr carries the panic.** **A user who redirects stderr or pipes to a
file sees a result set that simply stops, with nothing saying it was cut off.**
**Newest-first ordering sets the cut point** — if the offending session is the
newest match they get nothing; if it is the fortieth they get thirty-nine results
and no signal there were more.

**"One search in three crashes" undersells it. A crash is loud. Silent truncation
of a search is the failure mode this product's users would be least able to
detect** — and it is **the same class as the disk-full run reporting
`mismatches: 0` over 170 fewer sessions**: a plausible, complete-looking answer
over a silently reduced input.

### L229. The two measurements converged, and the honest answer is a headline plus a range

**Reconciled by the two owners directly, without me picking a number.**

**Session figure — the headline: 33.3% and 34.1%.** Two corpora, two methods,
**independently.** That is the number to carry.

**⚠ Block exposure is a range — 2.6% to 11% — and must not be reconciled to a
point.** Two real reasons: one alias resolution **counted unmappable tags as
refusing**, which is the **already-correct** case and therefore the wrong
direction even for an upper bound, while the other goes through the production
`lexer_for_tag`; and **one corpus was this Rust project's own sessions, where
`rust` is 189 blocks and absent from the other entirely.**

**Block exposure is a property of whose sessions.** A point estimate would be
false in a way the range is not.

**Completing markdown moves 34.1% to 29.2%** — so my "changes nothing about the
size" was wrong twice over.

**Method note worth keeping: the seat with the weaker instrument on an axis said
so and handed that axis to the other**, keeping the session figure as the headline
because the other's instrument is better on it. **Neither defended their own
number.**

### L230. ▶ Reconciled: the refusal has become the defect it was built to prevent

**`message-renderer` carries the block axis at `engine-and-codex`'s request.
Neither defended their own number.**

**Session exposure ~one in three, two corpora two methods independently:** 33.3%
over 366 Claude sessions; **34.1% over 600 files across Claude, Pi and Codex.**
**After markdown lands, 29.2%.**

**Block exposure 2.6%–11%, deliberately not a point.** **Method:** the alias
resolution that counted an *unmappable* tag as refusing was wrong in the
**inflating** direction — **an unmappable tag falls through to the plain lexer,
which the renderer reproduces exactly.** The other goes through the production
`lexer_for_tag` and is the one to use: **2.56% of all fences, 3.11% of tagged**;
SQL 43, CSS 31, XML 26, JSX 18, HTML 15, YAML 15. **Corpus:** `rust` is 189 in one
sample and **absent from the other** — a Rust project's own sessions. **Block
exposure is a property of whose sessions, so a point estimate would mislead.**

**⚠ And the truncation makes the block rate nearly irrelevant to severity: one
refusing fence anywhere in a session ends the scan from that point. Whether it is
2.6% or 11% changes how often, not how bad.**

**Plus the detail neither had alone: newest-first ordering means the cut point
moves as sessions are modified — so the same query returns different result counts
on different days, with no visible error.**

**⚠ THE ARGUMENT THAT DECIDES IT, and it is theirs: the refusal has inverted into
the defect it was built to prevent.** The typed `Unsupported` exists **so a
construct cannot silently vanish.** In the sink it produces **something strictly
worse — a silently vanished *result set*.** **It protected us precisely while
nothing was wired to it; now that something is, it is the defect rather than the
guard.**

**Their recommendation: the tail renders plain, with a gate asserting it and a
named divergence in the change log carrying its measured range.** **Trading a
visible, bounded loss of colour on a small share of blocks for the removal of an
invisible, unbounded loss of results.** **Every other option leaves a route that
truncates.**

**⚠ One assumption, flagged by them rather than left to pass: nobody measured
whether the truncation is visible downstream.** The truncation itself is measured;
**whether an exit code or the pager surfaces it is not.** **If the exit code is
non-zero and a script would catch it, the severity is lower than stated.**
Measurement requested from `engine-and-codex` — exit code, and what a user sees
straight to a terminal, under `2>/dev/null`, and under `> file`.

### L231. ▶ Six families landed. Only markdown remains, and it is not a separate decision.

*Taken 2026-08-29T14:43Z — `syntax_tables.rs` ebb5aa0cbcd5, `syntax_json.rs`
a793155a0f51, `syntax_table_gates.rs` 6c4af20370cd, `session_render.rs`
0ee92432fa91.* **223 lib + 53 doctests, five configurations, zero warnings.**

| Family | Table | Corpus | Reached |
| --- | --- | --- | --- |
| TypeScript | 94 rules, 6 states | 624 cases, 312,893 chars | 85 of 94 |
| TSX | 161 rules, 11 states | 97 cases, 28,946 chars | 145 of 161 |
| Bash | 189 rules, 9 states | 1857 cases, 430,266 chars | 132 of 189 |
| Python | 435 rules, 49 states | 270 cases, 63,591 chars | 315 of 435 |
| JavaScript | 78 rules, 6 states | 443 cases, 134,809 chars | 71 of 78 |
| JSON | **no table** | 574 cases, 111,867 chars | 133 of 140 **lines** |

**json was finished before the reordering ruling arrived, so it cost nothing.**

**RULED: markdown is not a separate decision.** `_handle_codeblock` lexes a
nested fence **with a second lexer chosen by the info string**, which the driver
does not model. **But the captain is ruling now on what a known-but-unpromoted
language does at a fence — and if that is "renders plain", a nested fence
rendering plain is the same behaviour by the same rule**, not a second concession
and not an engine change. **Hold markdown until the tail ruling, then promote with
the nested case plain and gated.** Adding a second `GroupAction` kind for 0.5% of
blocks would be the expensive answer to a question about to be settled for free.

**A computed waiver rather than an asserted one.** JavaScript carries **three**
mutations, not four: **its only two `bygroups` rules are both unreachable, so
there is no reachable slot to misalign.** The adequacy test was **made aware of
it** — the empty-group requirement now applies **only where a reachable
`bygroups` rule exists, computed from the oracle** — so a family with none passes
for a **stated** reason and a family with one still has to reach it.

**Third surviving mutation, third diagnosis, all three now side by side in one
file:** a **blind corpus** (TSX), an **unobservable state** (bash), and **two
rules that cannot both match anything** — JavaScript's builtin and exception
alternations are **disjoint**, so their order is not load-bearing.

**JSON's gate is a different instrument and worth reading rather than assuming.**
No table, so **the reference's executable lines stand in for a table's rules**:
the generator traces `get_tokens_unprocessed` and **refuses an oracle whose corpus
leaves a line unexecuted.** Seven exemptions with a mechanical reason — final-flush
branches closed because `Syntax` builds the lexer with `ensurenl=True` and
`_process_code` appends a newline — **and the generator checks that premise on
every case rather than asserting it.** Mutations are applied to the **recorded**
side: with `ours == recorded` established, `ours != mutate(recorded)` proves the
same thing by the same equality.

**The dead branch is now `unreachable!()` naming the fence arm** — so it cannot be
quietly turned into a plain render, and the ruling is not pre-empted.

### L232. An assertion whose subject was one promotion away from moving

**A two-minute red tree, and the same trap hit two seats thirty seconds apart.**
`a_fence_in_an_unpromoted_language_is_still_refused` named **`javascript`** — **an
assertion about non-promotion whose subject was itself queued for promotion.**
`message-renderer` hit the identical trap in the generated doctest.

**Both now name `CSS` and four others. And `mermaid` would be the wrong
substitute — it reaches no lexer at all, so it would pass for the wrong reason**,
which is the mistake available to whoever fixes it.

**The general form: an assertion that something is *absent from a set* must choose
a subject that cannot join the set.** Two people picked the largest, most obvious
member of the refusing set — **which was also the one most likely to be promoted
next.**

### L233. ▶ MEASURED: the scope is narrower than either framing. Exit 101 always; redirected stdout is unaffected.

    shape                        exit   stdout    panic seen?
    terminal, stderr visible      101   24,856B   yes
    terminal, 2>/dev/null         101   24,380B   no
    stdout > file                   0   25,446B   no — no panic at all
    with the pager (less)         101    5,054B   yes

**1. Exit code is 101 in every failing shape.** Non-zero, **so any script or CI
catches it.**

**2. ⚠ `stdout > file` does not hit the bug at all.** Redirecting stdout means
stdout is not a tty, **colour resolves off, the plain path is taken, and
`ColouredPanelSink` is never constructed.** Exit 0, complete results, no panic.
**The brief's "redirecting stderr *or piping to a file*" was wrong in its second
half — that shape is unaffected.**

**3. The pager does not hide it.** `less` runs and the panic text still reaches
the user. Exit 101.

**THE MEASURED STATEMENT, and it replaces both earlier framings: one interactive
coloured search in three truncates and exits 101 — loudly on a terminal, quietly
only if stderr is explicitly discarded.**

**Both earlier framings were wrong in named directions, by their author.**
*"One search in three crashes"* **undersold** it by ignoring the truncation.
*"A result set that simply stops with nothing saying so"* **oversold** it by
ignoring the exit code **and by including a shape that does not fail.**

**What still stands at its true size:** in the **default interactive case**, about
**one session in three** gives partial results followed by a Rust panic naming a
source file and line number. **A real blocker for a user-facing route — and it is
neither silent nor invisible to automation.**

**One thing deliberately not inferred: whether the partial output *before* the
panic is byte-identical to what the product would produce for those same hits.**
It looked right; it was not diffed; **it is not asserted.**

**Method note for the record: three successive framings of one defect, each
corrected by its own author against their own previous statement — crash,
then silent truncation, then the measured scope.** **The first two were reasoned
from mechanism; only the third was measured**, and it is the one that moves in
both directions at once — worse than the first, better than the second.

## ▶ POST-CUTOVER DIRECTION — Arborium. Admiral, 2026-08-30. Durable.

**Decision for the current cutover: finish the Pygments-table/engine path. Do not
switch to Arborium now. Do not pause current lexer work.**

**⚠ AND A DURABLE POST-CUTOVER PROJECT, recorded as explicit product intent and
NOT part of current completion scope.**

**After G5 and the deletion of the Python search authority: evaluate Arborium
against the held-out corpus, and use it as aggressively as practical to delete
custom code.** Named targets:

- the custom **lexer engine**
- the **language tables** — TypeScript, TSX, bash, Python, JavaScript, JSON, and
  markdown if promoted
- the **generators**
- the **aliases and styles** — the 915-entry alias table, `syntax_styles.rs`
- the **bespoke oracle machinery** — the two-driver gate, the per-family gates,
  the corpus-adequacy and mutation apparatus

**The goal is maximal safe deletion of custom code, not adding Arborium beside
it.** A change that leaves the engine standing has not done the thing.

**Reference: `alternatives.md`** (promoted; source
`teammates/rust-highlighter-research/alternatives.md`, 204 lines) **and its
measured go bars.** **Evaluate against the held-out corpus**, not against a fresh
harvest — the held-out set is what makes a later comparison honest.

**Why this is recorded here rather than left to memory.** Everything this desk has
learned about decay applies hardest to a decision that fires **after** the mission
ends: **a ruling with a condition must name its trigger** (L198), and this one's
trigger — *after G5 and deletion* — is beyond the horizon of every current seat.
**It is in L198's conditional table.**

**And one thing to carry into that evaluation, because it will be tempting to
skip:** the current path's gates are the measurement any replacement must match —
**589 streams over 313,795 characters byte-exact for TypeScript, 1031 of 1031 for
bash, python byte-exact on first run, JSON traced by executable line.** **A
replacement is evaluated against those, not against whether it looks right.**

### L234. ▶ There was no held-out corpus. Now there is, and all six families passed unseen on the first run.

*Taken 2026-08-30T06:38Z — `syntax_table_gates.rs` 3b764496f8f7. 225 lib + 53
doctests, five configurations, zero warnings.*

**My ask assumed a held-out corpus existed. It did not, and nobody had noticed.**
**Every corpus was used while building** — rules counted against it, cases added
until coverage closed, mutations aimed with it. **None of it answered whether a
table reproduces Pygments on content nobody looked at.**

**Built from seed 101 after the tables were finished: real content only, no
authored cases, no coverage requirement, different session files from the building
corpora at seed 23.** Written only by a `--held-out` flag, to their own paths.

    typescript  511 blocks  296,231 chars      bash    899 blocks  222,836 chars
    javascript  128 blocks   40,524 chars      json    489 blocks  146,207 chars
    python       64 blocks   26,366 chars      tsx      28 blocks   13,015 chars

**2,119 blocks and 745,179 characters of unseen content, byte-exact, all six
families, first run.**

**JSON's is worth the most of the six: it is the one port of *behaviour* rather
than a projection of *data*, so unseen content is the only evidence the scanner
was ported rather than fitted.**

**⚠ The rule that keeps it evidence is in the gate's failure message rather than
in a note: nothing is ever repaired against these.** A failure is a defect in a
table, a generator or the driver. **Regenerating the held-out corpus to make it
pass would convert the only unseen evidence into more of the seen kind** — and
that is exactly the move someone under time pressure would make. **The separate
flag and separate paths exist so it cannot happen by accident**, which is the
mechanism rather than the caution.

**And it closes the actual gap in the Arborium brief.** The numbers a replacement
must match are now on content that no seat has met, **committed with the seed that
separates them from the building corpora** — so the evaluation is actionable by
someone who never met this seat.

### L235. ⚠ Qualification to the deletion goal, from the person who built both sides

**Not an objection, and it changes what "maximal safe deletion" can mean.**

**The engine, the tables and the generators are deletable if a replacement
matches. The gates and these corpora are the measurement — so deleting them
deletes the evidence that the replacement *is* one.**

**The admiral's list names "bespoke oracle machinery" among the deletion targets,
and that phrase covers the gates.** **Their line, and it is the qualification:
whatever survives, they should.**

**The distinction to carry into that project: the deletion target is the
*implementation*, not the *measurement*.** A replacement proved against the
held-out corpus and then shipped with the corpus deleted **leaves no way to
re-establish the claim** — which is L1 and L23 exactly, arriving in a project that
has not started, and about artefacts that do not exist yet in the form they will
need to survive in.

**Raised to the captain as a qualification rather than settled here.**

## ▶ TAIL RULING — Captain, 2026-08-30. The cutover is unblocked.

**Known-but-unported *and* unknown fence languages render with complete fence
geometry and plain unstyled code. They must never truncate or panic.**

**Gate the fallback on the current red row plus representative known and unknown
tags. State the limitation in the change log. Do not expand long-tail lexer
coverage in this cutover.**

**The same ruling applies to markdown fenced-code highlighting if its table is not
already complete. Markdown *document structure* remains the existing renderer's
responsibility.** Matches the admiral's pretty-good highlighting policy.

### ⚠ L236. The consequence that must be stated: `g4-fence-never-covered` changes meaning, not colour

**That row compares the native route against `ch-legacy`. Python *colours* a
javascript fence. Under this ruling the native route renders it *plain*. So a byte
comparison still differs — the row stays red, for a different reason.**

**It must stop being a parity comparison and become a behaviour assertion.**
Otherwise G4 carries a permanently-red row whose redness is expected, **which is
the omission-dependent state this desk has spent two days removing** — and nobody
can tell an expected red from a regression.

**What it must assert instead:** the native route renders **complete geometry,
background and padding, with plain unstyled code**, and **exits 0**. Not that it
matches legacy — **it deliberately does not.**

**Owners.** The fence arm and the fallback are `message-renderer`'s
(`session_render.rs`, and the `unreachable!()` they placed there). **The gate
rework is theirs with `lexer-tables`' representative tags.** **Markdown's table
follows the same rule and is `lexer-tables`'.**

**Recorded in the deliberate-divergences table above**, which is what
`final-change-log.md` is assembled from, **with the measured range rather than a
point** — because block exposure is a property of whose sessions.

### L237. ▶ The fallback is landed. The cutover is unblocked and markdown is off the critical path.

*Taken 2026-08-30T00:34Z — `session_render.rs` ff8823f08cbd. 225 lib + 1 bin + 53
doctests, five configurations, zero warnings.*

**A language Pygments knows and no table covers now takes the same path as a tag
Pygments does not know:** complete geometry, background, padding, plain unstyled
code. **It cannot refuse, so it cannot panic, so it cannot truncate.** Six
families, unchanged.

**⚠ MARKDOWN IS NO LONGER ON THE CRITICAL PATH.** Unported languages render plain,
**and markdown is currently unported — so it renders plain like the rest.** It is
now a **coverage improvement** (35 occurrences; 34.1% → 29.2% of sessions), not a
blocker. **The critical path is: confirm the representative tag set → cutover.**

**The `unreachable!()` moved rather than came out, and the choice is the better
one.** The fence arm maps an unported language to `None` **before**
`render_code_block` is called, **so the plain render happens once, in one place**,
and reaching that arm now means the two have drifted apart. **The obvious
alternative — passing the name down and rendering plain there — would have put the
same decision in two places, which is how they diverge later.** The comment states
which guarantee it now makes.

### L238. The row was removed rather than rewritten — and the removal is documented where the row was

**`g4-fence-never-covered` is gone.** A parity row for a **deliberate divergence
cannot pass**: Python colours a CSS fence, the native route renders it plain, **by
ruling.** **Leaving it red would have recreated the state this desk spent two days
removing — an expected red nobody can distinguish from a regression.**

**Replaced by a Rust behaviour assertion**,
`a_fence_in_an_unpromoted_language_renders_plain`, over `css`, `html`, `sql`,
`xml`, `yaml`: **byte-identical to an untagged fence** — geometry, background,
padding, plain code — **and separately that it never refuses**, with the reason in
the message: *a refusal panics the sink and truncates a scan that has already
printed.*

**⚠ And the differential carries a comment where the row was**, saying the removal
is **the point rather than a retreat**, naming the Rust test that replaced it, and
telling the next reader **not to restore it.** **Without that, someone re-adds it
in a month and it fails for a reason that looks like a defect.** That is L198's
rule — *a ruling whose condition expired must say so where the ruling is* —
applied to a **deleted test**, which is the hardest place to leave a note because
there is nothing left to attach it to.

**`g4-fence-covered-later` is a real parity row again.** Python is promoted, so
the native route lexes that fence with Pygments' own table and **must match
`ch-legacy` byte for byte.** It earns its place instead of standing in for a gap.

**One item outstanding and flagged rather than assumed: the representative tag set
is currently the implementer's choice, not the owner's.** `css`, `html`, `sql`,
`xml`, `yaml` as an interim set — all reaching a real Pygments lexer, none a
promotion candidate, **`mermaid` deliberately excluded** because it reaches no
lexer at all and would pass for the wrong reason. **`lexer-tables` asked to confirm
or extend.**

**Markdown's remaining piece is a named callback for the block's own structure —
five fixed groups and the info string — which is document structure and stays with
the renderer.** The second `GroupAction` kind is **not needed.**

## ⚠ L239. THE TAIL RULING IS RETRACTED — coverage is not relaxed

**Captain, 2026-08-30, superseding the ruling recorded four hours earlier.**

**Every fence language or alias that legacy `ch search` recognizes and colours
must still receive syntax colouring after the cutover.** ***Pretty-good* relaxes
exact token and colour fidelity, NOT language coverage.** **Plain unstyled
fallback is allowed only where the legacy route also rendered plain because the
language or tag was genuinely unrecognised.**

**So JavaScript, HTML and CSS are not an intentional unsupported set. They need
colouring, and `g4-fence-never-covered` must go green for the right reason.**

**"Do not expand long-tail lexer coverage in this cutover" is withdrawn.**
**Arborium stays out per the admiral — we finish with the generator.**

### What survives from the work built against the retracted ruling

**Most of it, and this is worth stating so nothing is torn out that should not
be.**

- **The plain path stays — for genuinely unrecognised tags.** That is now its
  correct and only scope, **and legacy renders plain there too, so it is parity
  rather than divergence.**
- **The `unreachable!()` moved to guard the one-place invariant: keep it.** Right
  independently of the ruling.
- **The never-refuse property stays.** A refusal panicking the sink and truncating
  a printed scan is a defect under **any** coverage policy.

### What must change

- **`a_fence_in_an_unpromoted_language_renders_plain` asserts the wrong thing for
  `css`, `html`, `sql`, `xml`, `yaml`** — all recognised, all coloured by legacy.
  It must assert plain **only for genuinely unrecognised tags**, and **`mermaid`
  — excluded as the wrong subject — is now exactly the right one.**
- **The removed differential row comes back** for languages that will be covered.
- **⚠ And the comment left where that row was, telling the next reader not to
  restore it, now needs rewriting rather than honouring.** **L200's decay arriving
  inside four hours** — a correct instruction that outlived its ruling. It is the
  clearest instance this desk has: the note was written well, placed well, and is
  now wrong.

### The question the rule does not close

**Pygments ships 500-plus lexers. Any observed set is finite. A user can write a
fence in any of them.** **So "every language legacy recognizes" is unbounded in
principle and measured in practice**, and the residue — a recognised tag appearing
in no corpus — **needs a number and an answer before the cutover rather than
after.** Enumeration commissioned from `lexer-tables`.

### L240. `message-renderer` stopping at 90% — and their last judgement is the one to carry

**Harness-reported, current: 90% of the context window. Plan for that seat
ending.** Retraction recorded in `RESUME.md` **as a block at the head of the
section it invalidates**, because that section said *"ruled"* with no marker that
it could move. **Nothing rebuilt; nothing started.**

**⚠ THE MEASUREMENT THAT REFRAMES THE PLAN: under the corrected rule, the
fallback's correct scope — genuinely unrecognised tags — is 0.3% of blocks.**

**At that size the never-refuse property matters more than the fallback does.**
Their words, and the thing to carry into whatever the coverage plan becomes:
**whatever else changes, nothing may truncate a printed scan.** The plain path is
now a **0.3% parity case**; the truncation it prevents was **one interactive
coloured search in three.**

**And the representative tag set changed *purpose*, not just membership.** Under
the old rule the question was *which unported languages render plain*; under the
corrected one it is **which tags legacy itself leaves plain.** **`mermaid` is the
answer to the second and the wrong answer to the first** — the same name, opposite
roles, four hours apart.

**Their assessment of the remaining work, which matches mine: it is tables, not
engine.** The engine takes any `RegexLexer` family; JavaScript, HTML and CSS are
generator work on a procedure used six times.

**⚠ Tree is red and it is not theirs.** Two of `lexer-tables`' markdown mutation
tests fail — `markdown::losing_the_heading_push_changes_the_stream` and
`::swapping_the_two_fence_rules_changes_the_stream`. **229 pass, 2 fail.**
Mid-landing markdown; reported to them directly.

### L241. ▶ The coverage enumeration — fourteen of twenty-one need nothing new

*Taken 2026-08-30T10:20Z. `coverage-enumeration.md` promoted. Tree green, 225 lib
+ 53 doctests. **Markdown un-promoted and parked, so the two failing mutations are
gone.***

**Over 36,539 fenced blocks from 3,000 real session files, two sets of different
sizes and different kinds of work:**

    reaching NO Pygments lexer — plain is parity        401 blocks  1.1%  29 tags
    reaching a lexer with no table — the coverage gap  1,122 blocks  3.1%  21 lexers

**The plain set needs no work, and its members answer the fallback-tag question:**
`just` 184, `tsv` 65, `mdx` 39, `mermaid` 26, `txt` 22, `justfile` 19. **`mermaid`
is right for the fallback gate under the corrected rule and was wrong under the
old one — the property that disqualified it, reaching no lexer, is now the
qualification.** **The interim five are all wrong, because legacy colours every
one.**

**The coverage gap by kind:**

    table          616 blocks  14 lexers   no engine change; the procedure as it stands
    callback       290 blocks   4 lexers   needs one new named-callback action
    scanner        105 blocks   1 lexer    an imperative port, as JSON was
    foreign lexer   11 blocks   2 lexers   needs a group action entering another table

**⚠ The two commonest are the two smallest tables in the list. SQL is 337 blocks
and 15 rules over 2 states — it closes 30% of the gap and is smaller than any
family already landed.** XML is 144 blocks, 16 rules over 3. **Fourteen table
families carry 55% of the gap and are batch work.**

**The three that need the engine, with cost visible.** Markdown, HTML, YAML and
BibTeX carry hand-written callbacks — **290 blocks, one new `Action` kind plus
four separate hand ports.** `console` is **the hardest thing on the list relative
to its size**: not a `RegexLexer`, **and a shell session delegates its commands to
`BashLexer`, so it is a scanner and a foreign-lexer case at once** — 105 blocks,
6,935 characters. **VimL and Docker need `using(OtherLexer)` for 11 blocks between
them: the engine addition costs more than the coverage it buys.**

**Gateability, which the counts do not show.** Eight gateable on real content.
Three thin, TSX precedent applies. **Ten cannot have a real-content gate at all** —
Java, Rust, PowerShell, GLSL, INI, Nix, Fish, VimL, Docker, BibTeX, **34 blocks
between them** — so their gates rest almost entirely on authored cases **and must
say so.**

### L242. ⚠ 597 lexers, 27 named by this corpus — an enumerated set is a coverage floor

**Pygments defines 597 lexers. This corpus names 27.** **A user can write a fence
in any of the other 570, and by the corrected rule every one legacy colours must
be coloured.** **So the enumerated set is a coverage *floor*, not coverage, and
3.1% is a floor for the same reason.**

**Three readings, stated by `lexer-tables` as the captain's choice:**

1. **Accept the floor** — an unseen language renders plain where legacy coloured
   it. *(This is what the retracted ruling said, at a smaller size.)*
2. **Port by class rather than by observation** — a different project whose cost is
   **gating rather than generating, because 597 corpora do not exist.**
3. **Revisit what an unported language does** — **which the corrected rule
   rejects, and which is the only answer that is correct for a language nobody has
   seen.**

**A fourth reading the enumeration implies and nobody named: generate broadly,
gate narrowly.** The generator handles any pure `RegexLexer`, and **generation is
cheap while gating is the cost.** So the tables for most of the 597 could be
*emitted* — and the honest statement would be that **ungated families are
transcriptions of the reference with no independent evidence**, which is a weaker
claim than every family landed so far makes, and a stronger one than rendering
plain. **It trades provability for coverage, in the opposite direction to every
choice this mission has made.**

**RULED, the unambiguous half: the fourteen table families go now, in block
order.** They need nothing new, they are right under every reading, and **SQL
alone closes 30% of the gap.** **The callbacks, the scanner and the 570-lexer
residue wait on the captain.**

### L243. The engine needs ONE addition, not two — and markdown is parked for a retraction-caused reason

**Two sharpenings from the cost model, folded into the procedure at 90% by its
author after I had told them to stop. Their judgement, named as theirs: folding it
beat losing it. It was the right call and I have said so** — the content arrived
*"before you go"*, it was time-critical, and the procedure **is** the successor.

**1. A single named-callback `Action` unlocks four lexers at once** — Markdown,
HTML, YAML, BibTeX, **290 blocks.** **The foreign-lexer re-entry costed earlier
for markdown is worth 11 blocks and should not be built.** The earlier procedure
assumed markdown needed it; **it does not.** So the captain's engine decision is
**one addition worth 290 blocks and one worth 11**, not a single bundled question.

**2. `console` reads as the opposite of what it is.** `BashSessionLexer` is **not
a `RegexLexer` and delegates to `BashLexer`** — a scanner **and** a foreign-lexer
case at once. **By block count it looks small; it is the hardest thing on the
list.**

**The fallback tag question is closed and answered by measurement.** Tags legacy
leaves plain — reaching **no** Pygments lexer — are **401 blocks, 1.1%, across 29
tags**, led by `just`, `tsv`, `mdx`, `mermaid`. **Recommended subjects: `mermaid`,
`just`, `mdx`.** **The interim five were all wrong** — legacy colours every one —
**and that is now recorded as answered, with attribution.**

**⚠ Markdown is parked at `markdown-gate.rs.pending` for a retraction-caused
reason worth naming: it was built against `handlecodeblocks=False`, and the
retraction makes that the wrong configuration.** The work is not wasted; **its
premise moved.** That is the second artefact this week invalidated by a ruling
rather than by a defect — and unlike the first, **this one was caught before it
landed rather than after.**

**Tree green: 225 lib + 53 doctests, 2026-08-30T10:20Z.** The two failures were
the markdown landing and are gone.

**`message-renderer` stopped at 90%, harness-reported, current. Their standing
request, unchanged and carried: whatever the coverage plan says, nothing may
truncate a printed scan.**

## ▶ L244. FINAL SCOPE — a bounded handful, not the language universe. Admiral, 2026-08-30.

**Do NOT support the full legacy/Pygments language universe. Target a bounded
handful of product-relevant languages. Broad coverage expansion stops before it
starts** — my dispatch of the fourteen families is **withdrawn**, and
`lexer-tables` is stopped.

**JavaScript, HTML and CSS are not automatically required.** They earn a place
only on measured footing. **Unpromoted languages use the gated plain fallback** —
**so the fallback built against the retracted ruling is the standing answer
again**, at its correct scope.

**No cutover scope change until the captain approves a final list.**

### The report

**1. Implemented and gated — six families.** TypeScript (94 rules / 6 states),
TSX (161 / 11), Bash (189 / 9), Python (435 / 49), JavaScript (78 / 6), JSON
(no table — a ported scanner, traced by executable line). **All six pass a
held-out corpus built after the tables were finished: 2,119 blocks, 745,179
characters of unseen content, byte-exact on the first run.**

**2. Their share of real fenced blocks: 95.8%.** Of 36,539 fenced blocks across
3,000 real session files — **1,122 in the coverage gap (3.1%), 401 reaching no
lexer at all (1.1%), 35,016 covered (95.8%).**

**⚠ Painted characters for the six as a set is NOT measured and I am not inferring
it.** What exists: **39.4% of fenced characters receive a non-default colour**,
and **TypeScript-family is 63.9% of all painted characters.** The figure for the
six together has been requested.

**3. Smallest candidate additions, by marginal coverage against cost:**

| Candidate | Blocks | Table | Gateable on real content |
| --- | --- | --- | --- |
| **SQL** | **337 (30% of the gap)** | **15 rules, 2 states** | yes |
| **XML** | **144 (13% of the gap)** | **16 rules, 3 states** | yes |
| Diff | small | 8 rules | thin |
| TOML, CSS, JSX | ≤ ~50 each | small | thin or authored-only |
| HTML, YAML, Markdown, BibTeX | 290 together | **need a new engine `Action`** | mixed |
| `console` | 105 | **scanner + foreign lexer at once — hardest on the list** | thin |
| VimL, Docker | **11 together** | **need foreign-lexer re-entry** | **authored only** |

**⚠ Ten of the fourteen table candidates cannot be gated on real content at all** —
Java, Rust, PowerShell, GLSL, INI, Nix, Fish, VimL, Docker, BibTeX, **34 blocks
between them.** Under a bounded policy that is a poor trade: **families whose
evidence is authored, bought for tens of blocks.**

### RECOMMENDED FINAL LIST — the six, plus SQL and XML. Eight.

**SQL and XML together are 43% of the remaining gap for about 31 rules** — **less
than any single family already landed**, both gateable on real content, and both
on the same generator and procedure used six times.

**After them the curve collapses**: every remaining candidate is ≤ ~50 blocks, or
needs an engine addition, or cannot be gated on real content.

**Coverage at eight: 95.8% + 1.3% ≈ 97.1% of fenced blocks**, with the residue on
the gated plain fallback.

**JavaScript stays because it is already landed and gated** — no cost to keep.
**HTML and CSS do not earn a place**: HTML needs the new engine `Action`, and CSS
is tens of blocks.

**And the property that survives every version of this decision, carried from
`message-renderer`: nothing may truncate a printed scan.** Under the bounded
policy the plain fallback covers more than the 1.1% it did an hour ago — **which
makes the never-refuse property more load-bearing, not less.**

### L245. ▶ PAINTED CHARACTERS: the seven landed families carry 98.2%. My XML recommendation is withdrawn.

*Taken 2026-08-30T10:26Z — `syntax_tables.rs` 1dfb6f41dac7,
`syntax_table_gates.rs` 1fa0569e4b13, `session_render.rs` 22e3921c8d79. Tree
green: 231 lib + 53 doctests, zero warnings. **SQL landed; nothing after it
started.***

**Over 25,940 real fenced blocks and 11,915,699 characters. 34.3% of fenced
characters are painted away from Monokai's default at all.**

    * TypeScript   62.5%      * JavaScript    6.2%       Diff     0.4%      Markdown  0.2%
    * Bash         15.6%      * Python        1.6%       XML      0.3%      JSX       0.1%
    * JSON         10.9%      * SQL           1.1%       YAML     0.3%      CSS       0.1%
                              * TSX           0.2%       HTML     0.2%      the rest  0.1%

**The seven starred families are 4,010,773 of 4,083,499 painted characters —
98.2%.** **TypeScript at 62.5% cross-checks the costing's independently measured
63.9%** — two instruments, two corpora, convergent.

**⚠ MY XML RECOMMENDATION IS WITHDRAWN, disproved by measurement.** I recommended
the six plus SQL and XML on **block counts** — SQL and XML as 43% of the gap.
**Painted characters say SQL was worth 1.1% and XML is worth 0.3%**, because XML
fences are **short and sparsely coloured**. **SQL was worth landing; XML is not.**

**The two figures disagree because a language's share of *blocks* and its share of
*colour* are different quantities** — the same inversion I spotted one level up
(the two commonest gaps being the two smallest tables), **arriving one level
further and against me.**

**The entire remaining tail — all fourteen table families, all four callbacks, the
scanner and both foreign-lexer cases — is 1.8% between them. No single one reaches
half a per cent.** Diff is the largest at 0.4% for 8 rules.

**RECOMMENDED FINAL LIST, corrected: the seven that exist. Land nothing further.**
The captain's *"bounded handful of product-relevant languages"* is answered by
**the handful that is already built and gated.**

**The plain fallback is the standing answer for 1.8% of painted characters and 401
blocks of genuinely unrecognised tags. It is built, gated, and never truncates** —
**under a bounded policy it is doing the job it was designed for rather than
covering a retreat.**

**SQL's own numbers, as the last thing landed.** 15 rules over 2 states, 52 cases
over 49,007 characters, **and 15 of 15 rules reached — the first family whose
corpus reaches everything it declares, with nothing to exempt.** Four mutations,
all dying, **and the fourth is new: SQL is the first family to declare
`IGNORECASE` and nothing else — not even `MULTILINE` — so the third `LexerFlags`
field reaches a table for the first time and has its own mutation rather than
merely being used.** Held-out corpus green with the rest.

### L246. The last implementation seat is idle at 75%, with a whole-rewritten brief

*2026-08-30T10:31Z, harness-volunteered — 75% of the context window, replacing a
twenty-hour-old 50%. Nothing queued, so the remaining quarter is uncommitted.*

**Tree green and unchanged: 231 lib + 53 doctests.** `markdown-gate.rs.pending`
parked with its staleness note. **Nothing started after SQL.**

**The whole-rewrite found nothing wrong — the first time a whole read has not.**
The previous one **was asserting the opposite of its own code about the refusal
test.** That is now four whole-document re-reads on this mission, three of which
found a contradiction the author had introduced by patching. **The practice earns
its keep at a rate of three in four.**

**`teammates/lexer-tables/RESUME.md` carries, in one cold-actionable document:**
the seven families with corpora and coverage; **why it stops at seven, with the
98.2% figure and the blocks-versus-colour trap stated *as a trap***; the held-out
corpora with the never-repair rule; **what an unported language does and the two
assertions that hold it**; every gate and what it compares; the generators and how
to add a family; the four things that bite; the seven findings sent out; markdown
parked with its reason; and the two open decisions.

**Stating the blocks-versus-colour inversion as a trap rather than as a finding is
the right form** — it is what made the first mate's recommendation wrong, and a
successor ordering work by block count would repeat it.

## ▶ MISSION STATE — all seats idle, awaiting the language list

**Nothing is in flight.** Every implementation seat is stopped with a
cold-entry brief. **The only open item is the captain's approval of the final
language list — recommended: the seven that exist.**

**On approval, the order is:** rebuild the fallback gate with the corrected
subjects (`mermaid`, `just`, `mdx` — measured, and the interim five were all
wrong because legacy colours them) → **restore `g4-fence-never-covered` as a real
parity row** for the seven, or retire it with its replacement named → cutover →
G5's seven blocked checks → route flip → deletion slice, **with every instrument's
last consultation stored first.**

**Unowned and required before G5:** F1's universal-newline fix; the C0 set as
widened by `\s` and `\w`; F16 and F17's duplicate helpers; the `HOME`-unset
measurement; the wrap-oracle gate over both `words`/`rstrip_end` copies.

**Post-cutover, recorded as durable product intent: the Arborium evaluation**
against the held-out corpus, targeting maximal safe deletion of the engine,
tables, generators, aliases and styles — **with the qualification that the gates
and corpora are the measurement and must survive whatever replaces the
implementation.**

## ▶ L247. FINAL LANGUAGE SET APPROVED — exactly seven. Captain, 2026-09-01.

**The final syntax language set is the seven measured families already landed and
gated: TypeScript, TSX, Bash/sh/zsh, Python, JavaScript, JSON, SQL.** They carry
**98.2% of painted characters** and passed the held-out corpus. **Do not add more
language families.** Unpromoted languages use the complete, non-panicking, gated
plain fallback. **Arborium remains post-cutover deletion intent, not current
scope.**

This closes the question opened at L239's retraction and bounded at L244. **L244's
"six plus SQL and XML" is superseded; L245's corrected recommendation of the seven
is what was approved.** The withdrawn XML recommendation stays in the record as
the blocks-versus-colour trap, not as a pending item.

### The route to completion, and who holds each step

1. **Fallback gate rebuilt with the corrected subjects** — `mermaid`, `just`,
   `mdx`. `lexer-tables`. The interim five (`css`, `html`, `sql`, `xml`, `yaml`)
   were all wrong because legacy colours every one [L240].
2. **`g4-fence-never-covered` resolved** — restored as a real parity row for the
   seven, or retired with its replacement named. `lexer-tables`. **No permanently
   red row survives into the cutover.**
3. **Cutover.** One `search` branch in `rust/main.rs`. `engine-and-codex` lands it;
   `search-runtime` holds the rehearsed arm and answers on it.
4. **G5's blocked checks.** `reviewer-profiler`, 15-check runbook.
5. **Route flip.** `contract-owner`. 260 intended reds must all turn green.
6. **Deletion of the Python search authority, then re-prove** — with every
   instrument's last consultation stored first (decision 6, L1, L23).

### The parity list is the one thing with no owner who has context

**F1's universal-newline fix; the C0 set as widened by `\s` and `\w`; F16/F17's
duplicate helpers; the `HOME`-unset measurement; the wrap-oracle gate over both
`words`/`rstrip_end` copies.** Required before G5. It touches `session.rs`,
`python_io.rs` and `raw_transcript.rs` — **disjoint from `main.rs` and from the
gates**, so it parallelises cleanly with the cutover. Its natural owner
`session-core` is at 87%. **Raised to the captain as a roster question, which is
the only class this seat escalates.**

### L248. G5's owner is at 90% and the runbook found three contradictions in itself

*2026-09-01. `reviewer-profiler` re-read the G5 runbook whole before running any
of it. **All three faults were their own, all three from patching.***

1. **A count that disagreed with itself in three places and with the file** — 68
   in one block, 76 in a check row, **82 on disk.** Six per-file-error stderr
   shapes were added after the last verify and no count followed them.
2. **A zero-drift result presented as covering the set it predates.** Taken at 76
   entries. Now stated as *"taken at 76, not re-taken at 82"*, with a full
   `--verify` at 82 as the first thing to run.
3. **Two present-tense claims that were dated facts** — *"the cutover has not
   happened"* and *"`run` has no callers"*. Both still true today, both rewritten
   as **preconditions to re-check at run time.** The second **expires the moment
   `engine-and-codex` lands the three-arm function, because that caller is the
   first one and it chooses the width source.** Routed to them.

**That is five whole-document re-reads on this mission and four that found a
contradiction the author introduced by patching.** The practice is not a courtesy;
it is the highest-yield check this desk has.

**They declined to run the `--verify` while holding the argument that it was
safe** — the route digest is unchanged at `dd6ab701` across 38 changed Rust files,
so it measures an unmoved oracle. Their words: *"almost certainly safe is how a
run gets taken during a window someone else declared unquiet."* **Backed.**

**Ruling: `reviewer-profiler` does not start G5.** At 90%, eight checks carry into
a failure they cannot afford to diagnose, and a stall at check five costs more
than starting later. **Their last tenth is reserved as the author on call.** The
runbook is now the transfer — 15 checks, each with its command, what it proves,
its preconditions, and the six things that get got wrong without being told.

**The constraint that decides who replaces them, and it is in the document: G5
cannot be run by someone who built the thing.** That is decision 2 in its now
unconditional form, arriving at the last gate.

## ▶ TWO SEATS ARE NEEDED, AND THE ROSTER IS THE CAPTAIN'S

**Neither is optional and neither can be the same seat**, because one is
production editing and the other must have no stake in any answer being right.

1. **The parity list** — F1's universal-newline fix, the C0 set as widened by `\s`
   and `\w`, F16/F17's duplicate helpers, the `HOME`-unset measurement, the
   wrap-oracle gate over both `words`/`rstrip_end` copies. Touches `session.rs`,
   `python_io.rs`, `raw_transcript.rs`. **Disjoint from `main.rs` and the gates**,
   so it runs beside the cutover. Natural owner `session-core` is at 87%.
2. **G5** — runs the written runbook, then the seven checks the cutover unblocks.
   **Must not be an implementer.** `slice-reviewer` is at 89% and `context-curator`
   at ~78%; neither has room for a fifteen-check gate.

**Addendum — the three the author says are easy to read past, in the order they
bite.** All three are in `g5-runbook.md`; they are recorded here because "in the
document" and "read" are different states.

1. **Re-check both preconditions before anything else.** They are written as
   preconditions because they expire, and the shape changes when the three-arm
   function lands.
2. **The first run is `--verify` at 82, not any gate.** The zero-drift baseline
   predates six entries and everything downstream assumes it still describes the
   oracle.
3. **Check 10 is the one with a control, and the control is the half people
   drop.** Search rendering hits proves nothing alone. **`info --help` failing
   with the private-entry error is what proves the probe can tell the two routes
   apart.**

**And the width question is answered in advance, prepaid**: the runbook is
complete for a caller passing `terminal_width()`. **For anything else, check 7 is
already the gate and needs no change** — a route pinned to a constant renders
identically at 60, 120 and 200, which is what it caught on the branch.

All three `reviewer-profiler` documents confirmed live as symlinks. Idle at 90%.

## ⚠ L249. THE CUTOVER IS BLOCKED: styled tool rendering was never built

*2026-09-01. Measured by `engine-and-codex` against the fixture home, colour on,
under a pty. Confirmed structurally by `search-firstmate`.*

| shape | exit | panicked | bytes |
| --- | --- | --- | --- |
| default | 0 | no | 85,083 |
| **`--tools`** | **101** | **yes** | **46,070 — truncated** |
| `--thinking` | 0 | no | 85,989 |

**`message_content_renderables` builds Text, Thinking and SubagentTask in full and
sends `Part::Tool` straight to `Unsupported("tool")`; `ColouredPanelSink::emit`
panics on `Unsupported`.** `rg -ln 'ToolPart|Part::Tool' rust/` returns
`session_render.rs` alone, and no function in it turns a tool part into segments.
**This is an unbuilt surface, not an unwired one.**

**The fence ruling does not reach it.** Tools are not a language-coverage question,
so no fallback decision covers this. **`--tools` is an ordinary flag and almost
every session contains tool calls**, so the failure the fence fallback was built to
prevent — a streamed scan that stops at an arbitrary point and exits 101 — now
arrives through a commoner door.

**⚠ AND THE GATE THAT SHOULD HAVE CAUGHT IT IS GREEN.** The body oracle at
`session_render.rs:2659` asserts *"the recorded corpus reaches no unsupported
construct"* and passes — **which proves the body corpus contains no tool part at
all.** Seventh confirmed blind corpus on this mission. **A green result over a
blind corpus is not evidence**, and this is the most expensive instance yet
because it stands between the mission and the cutover.

**Sizing requested from `lexer-tables`, who is freshest and already in the file.
Measured, not estimated** — "too expensive" is a claim about a mechanism and must
be measured against the mechanism. **Nothing is fixed until the size is known.**

### L250. The same trap in two files by two people in one week: an assertion whose subject decayed

**`lexer-tables`' fallback gate was passing for the wrong reason twice over.** Its
old form asserted that an unported language renders like an untagged fence, over
`css`, `html`, **`sql`**, `xml`, `yaml`. **`sql` stayed in that list after SQL was
promoted and nothing went red** — because the sample word was `placeholder`, a
bare identifier **every lexer paints in Monokai's default foreground.** A coloured
SQL fence rendered byte-identically to a plain one. **Wrong subject *and* a sample
that could not discriminate: the assertion survived the exact event it was written
to catch.**

**Cured mechanically rather than by comment.** Four tests now.
`the_fallback_subjects_are_still_the_right_ones` derives each tag from
`lexer_for_tag` and `promoted_lexer`, so **promoting a language moves the tag and
says which**. `the_fallback_sample_is_coloured_by_a_promoted_family` is the control
that makes plain output mean something. Parity on `mermaid`, `just`, `mdx`; the
accepted divergence on `css`, `html`, `xml`, `yaml` **asserted separately, so one
can never be read as the other.**

**The removed `g4-fence-never-covered` row carried the same decay**: it justified
itself on javascript never being promoted, and **JavaScript was promoted on
2026-08-30.** Corrected in `pty_differential.py` with the three replacement tests
named individually.

**⚠ `g4-fence-covered-later` is now an ordinary parity row and must actually go
green.** Python is promoted, so the native route lexes that fence with Pygments'
own table and must match `ch-legacy` byte for byte. **It needs the launcher
window — `contract-owner`, not `lexer-tables`. It is no longer red by design and
must not be read as such.**

**The class, stated as the question rather than the list: an assertion names
subjects, and promotion moves them. Derive the subject set or it decays silently.**

### L251. `HOME` measured — and a third instance makes falsy-versus-absent a class

*`engine-and-codex`, 2026-09-01. Closes item 4 of the required parity list.*

| `HOME` | legacy | `std::env::home_dir()` |
| --- | --- | --- |
| a path | that path | same ✓ |
| **unset** | passwd → real home, **search works** | same ✓ |
| **empty** | **`/`** | real home ✗ |

**`.expect("HOME")` crashes where the product works** — Python's `Path.home()`
falls back to passwd. **And `home_dir()` fixes that while introducing a smaller
divergence**: Python's `expanduser` returns `/` for a present-but-empty `HOME`.

**Approved: the three-branch resolver**, landed in `probes/searchdriver` so it
travels with the arm. Two of its three branches are measured product behaviours.
**The rule it applies: reproduce what Python accepts, not what it appears to
intend.**

**Empty custom title, empty script object, empty `HOME` — three sites this week
where Python distinguishes *unset* from *set-to-empty* and a Rust convenience
function collapses them. Three is a count, so this is a class and not a
resemblance.** The useful form is a question to ask at the call site: **does this
call distinguish absent from empty, and does the product?**

*And the tell worth keeping: `.expect("HOME")`'s panic named `main.rs:31` — a probe
file had already become a production file in everything but name.*

### ⚠ L252. The blocked surface is `--full`, not `--tools` — five shapes panic

*`engine-and-codex`, 2026-09-01, all under a colour pty on the fixture home.*

**Panics, exit 101:** `--full`, `--plans`, `--tools`, `--tools Bash`,
`--tools --full`.
**Clean, exit 0:** default, `--thinking`, `--agents`, `--branches`, `--short`.
(`--custom` exits 2, unrelated.)

**`--full` reaches the unbuilt surface with no tool flag at all.** It is a headline
flag, not an expert one. **So the exposure is not "users who ask for tools", it is
anyone asking to see whole conversations in colour** — and `search-firstmate`'s
first report upward said the former and has been corrected.

**Mechanism, marked read rather than measured by the person who found it.**
`session.rs:1460` sets `tools_always_visible` on a synthesized message carrying a
**failed Bash** tool result; `visibility.rs:468` is `(requested ||
tools_always_visible) && !tools.is_empty()`, so that message shows its tools with
`--tools` off. Default mode escapes only because the matched messages happened not
to include one. **`--full` displays every message, so it reaches them.**

**Ruled: the real-corpus rate is not to be measured.** It does not move the
decision — a headline flag that aborts a printed scan makes the surface mandatory
at any rate. **The rate would say how loudly to report it, and it has to be
reported regardless.** Declining a measurement because it is not load-bearing is
the same discipline as taking one that is.

**And the restraint is the record's, not just the reporter's:** the fixture home is
small and curated, and a rate extrapolated from it would have repeated the fence
range's near-miss. **The chain was marked "read, not measured" unprompted** — an
unanswered question and a "no" look identical from below unless someone says
which.

*Kept from the same exchange: **a file that names its future in a stack trace is
telling you what it has become.** `.expect("HOME")` printed `main.rs:31` while
still living in `probes/searchdriver`.*

## ▶ L253. The tool surface measured: 93.6% of it is required and cheap; one item is a captain's call

*`lexer-tables`, 2026-09-01T12:0xZ, read-only against `session_render.rs`
`5517968077d4`. Legacy spec is `formatting.py:86–294`, entry `render_tool_rich`.*

**Prevalence, corrected before it travelled: 282 of 309 `.claude/projects`
sessions (91%) and 971 of 1,211 `.codex/sessions` (80%).** The first pass said
**4.7%**, an average over 3,536 `.pi` files that store tools differently. **An
aggregate over mixed populations reported a number true of nothing** — caught by
its author before it reached a decision. Same class as 22c, one level up: **not a
finding read from an aggregate, but an aggregate that spanned two populations.**

**What legacy renders:** a header — `⏺`/`⎿`, a label in one of four accents,
`· error` on failure, the first display-worthy attribute home-collapsed and
**elided at the width it renders at** — and a body, always under `LeftRail`,
chosen three ways.

| Body | Python spec | Share of tool parts | Ruling |
| --- | ---: | ---: | --- |
| Markdown under a rail | ~120 lines | **87.6%** | **required — build it** |
| `Read` line-number gutter | ~60 lines | 6.0% | **required — build it** |
| `Edit` unified diff | **687 lines** | 6.3% | **captain's call** |

**The common path is about 150 new Rust lines** — six theme colours, a
`ToolHeader` renderable, the dispatch and the input lookup. **Everything else it
needs is landed and gated:** `LeftRail`, the markdown body, `elide_to_width`,
`collapse_home`, wrap, segments, and fence rendering for the seven. `codecs.rs`
already walks the same attribute and content keys the header and body chooser
consume.

### Three rulings made here, so they are not re-opened

**1. The `Read` gutter is required, because line numbers are unconditional
geometry, not highlighting.** Same distinction the fence ruling turned on.

**2. The extension finding does not reopen the seven.** `Read` lexes by file
extension: over 2,497 real calls with a path, **48.3% resolve to a promoted
language, 40.3% to an unported one, 11.4% to none — and markdown alone is 930,
37%, the single largest.** The latter two take the plain fallback, exactly as
approved at L247. **Half the extension work delivering no colour is the approved
outcome, not a shortfall.**

**3. The failing oracle case is built first, and it is not skippable.** The body
oracle's cases are authored JSONL and one already carries a `thinking` + `text`
content array, **so a tool case is the same mechanism and turns the vacuously-green
unsupported assertion red immediately.** **Make the gap visible before closing
it** — otherwise the only evidence the gate works is that it went green after the
fix, which is the `placeholder` shape and the `sql`-subject shape from the same
week.

### Escalated: the `Edit` diff

**It must reproduce CPython's `SequenceMatcher` exactly, autojunk heuristic
included.** Its cost is **fidelity risk rather than volume**, and if an `Edit`
rendered its content instead of a diff, **legacy would still show a diff** — a
product-visible divergence, not a fidelity relaxation, so the fence ruling does not
cover it.

**⚠ But "687 lines" is a Python line count, not a measured cost.** Before the fork
goes up, `lexer-tables` answers one question: **does a Rust crate reproduce
`SequenceMatcher` including autojunk, and does it match on real input?** If one
does, **the fork may not exist.** *"Too expensive" is a claim about a mechanism and
must be measured against the mechanism* — the rule that was earned when a
gigabytes-of-disk argument met `cp -Rc` on APFS at 44 seconds and zero disk.

### Ownership moved

**`session_render.rs`'s tool surface is `lexer-tables`'.** Their language guard
existed to stop broad expansion, which is settled and closed; this is a build in a
file they are already inside, and they are the freshest implementer.
**`message-renderer` remains oracle and interface owner at 90% for one narrow
question.**

## ⚠ L254. THE TREE IS DELIBERATELY RED — and the vacuous green had a mechanism

*2026-09-01T12:2xZ. One test fails, everything else green:
`session_render::body_oracle_tests::every_recorded_message_body_reproduces`, with
`the recorded corpus reaches no unsupported construct: Unsupported("tool")`.*
**Both waiting seats were told; `search-firstmate` had called the tree quiet an
hour earlier and corrected it.**

**The red is the specification**, the same way G4's coloured gate was red before
the renderer existed. Six authored cases now carry a tool part, chosen to be the
corpus the build needs rather than one that merely fails:

    tool-call-and-result                   the 87.6% path — header, rail, fenced body
    tool-error-result                      the error accent and the `  ·  error` suffix
    tool-read-result-promoted-extension    the gutter, restored from line 12, .py lexed
    tool-read-result-unported-extension    .md — the largest real Read extension, no colour
    tool-edit-diff                         old_string against new_string
    tool-header-key-argument-elided        the key argument elided at its render width

**⚠ THE MECHANISM BEHIND THE VACUOUS GREEN, AND IT IS THE PART TO CARRY:
`flags_from` handled only `show_thinking`, so no recorded case could ever have set
`show_tools`. The gate could not have been given a tool part even by someone
trying.**

**That is not a thin corpus. It is a corpus unable to express the case** — and it
is the second this week, beside `placeholder`, where the assertion could not
discriminate rather than merely happening not to. **In both, what would have shown
the fault was the artefact at fault.**

**Stated as the question, and it belongs beside `held-parameters.md`'s four: what
can this corpus not say?** A held parameter nobody chose, living in the corpus's
vocabulary rather than in a harness default. Routed to `reviewer-profiler` with an
explicit out — **if their remaining tenth is better spent elsewhere it stays here**,
because a finding in two places is better than a seat spent moving it.

### Ruled: build the common path, then stop and hand off

**`lexer-tables` raised their own stopping point before the build rather than at
it**, with a day-stale 75% reading they correctly treat as a floor rather than a
figure. Two options were offered and the recommended one is approved.

**Build the common path — 87.6%, the piece that turns the panic into a render —
land it green, stop, write the handoff. Leave the `Read` gutter cases red with
their note. Do not start the gutter.** If the common path runs long, stop mid-way
and hand off from there; the corpus makes that recoverable.

**Their reason is the ruling's reason: a corpus that already fails in exactly the
places the work remains is a better starting position than any prose.** A successor
arriving to four named failures knows more than one arriving to a to-do list.

## ▶ THREE SEATS ARE NEEDED, NOT TWO — and the order is now fixed

**Revised from the earlier two-seat request. The tool build is the critical path,
so it goes first.**

1. **Tool-build successor** — `session_render.rs`, continues from `lexer-tables`'
   handoff and a red corpus. **Blocks the cutover.** Most urgent.
2. **Parity-list implementer** — F1, the widened C0 set, F16/F17, the wrap-oracle
   gate. `session.rs`, `python_io.rs`, `raw_transcript.rs`. **Blocks G5.** Item 4
   (`HOME`) is closed.
3. **G5 runner, and it must not be an implementer** — runs the written runbook,
   then the seven checks the cutover unblocks. **Blocks completion.**

**Seats 1 and 2 are disjoint by file and run in parallel. Seat 3 cannot be either
of them** — decision 2, in its now unconditional form, arriving at the last gate.

### L255. The fifth bound is *vocabulary*, and it pairs with the reflow finding

*`reviewer-profiler` took L254's finding into `held-parameters.md` rather than
leave it here — one idea, one home.*

**Fifth bound: the corpus cannot express the case.** Not a thin corpus, an
**incapable** one. `flags_from` handling only `show_thinking` meant the body oracle
was green over a space that did not contain the thing it asserted.

**Paired in the document with the reflow finding, because it is the same quantity
one layer earlier:** there, a width gate's *query* selected only short bodies while
the corpus held a 617-character line; here the fixture *generator* could not emit
the flag at all. **Capacity in the corpus is not capacity in the cases a gate
runs.** Both invisible from inside the gate. **Both answered by measuring what the
cases can express before trusting what they report.** A successor meets the pair
rather than two instances.

### ⚠ L256. Check 10's control gets sharper while `--full` panics — into the runbook

**A `-ll` probe never touches the panel renderer, so the no-Python proof would pass
over a route that cannot render at all.** Whoever runs check 10 must use a shape
that reaches the coloured sink.

**The class: a gate that passes for a reason unrelated to what it proves.**
Invisible to anyone who has not seen `--full` exit 101.

**Written into `g5-runbook.md` rather than left here**, on the author's own
argument from L255: a note in a message thread dies, and the runbook is the
transfer. **Whoever runs G5 will not read the thread it was found in.**

**L256 landed in two places, on the author's own distinction: the check row is
what a runner reads, the gotchas note is what someone reads when a green result
looks too easy.** The row sends the search half to a shape reaching the coloured
sink; the note says why, dated. **Read the exit status as well as the output.**
Runbook 132 lines, desk symlink verified identical. `reviewer-profiler` idle for
good.

### L257. The one sentence this mission would keep

**Every one of the three runbook contradictions was a true statement that had
quietly stopped being true.**

They were in a document its own author wrote four days earlier and had already
corrected twice, and they surfaced only because the re-read was *whole* rather than
scoped to the part that had changed. **A check of what changed cannot find a
sentence that decayed without being touched.**

**That is the same failure this desk spent the week catching everywhere else** — in
`sql` surviving its own promotion, in `g4-fence-never-covered` justifying itself on
a language promoted two days prior, in `run` having no callers, in a 76-entry
baseline describing an 82-entry set, in "the cutover has not happened". **Code,
relays, numbers, instruments, and finally the transfer document itself: the one
artefact whose entire purpose is to be read by someone who cannot ask.**

**So the practice is not a courtesy and not a style preference. Re-read whole,
never scoped — five times on this mission, four of which found a contradiction the
author had introduced by patching.**

## ▶ L258. The common path is landed and the tree is green. The `Edit` fork closed by measurement.

*`lexer-tables`, 2026-09-01T12:12Z — `session_render.rs` `df063bbe3d9d`,
`codecs.rs` `3cf2657960c5`. 234 lib + 53 doctests, five configurations, zero
warnings.*

**87.6% of tool parts render**: header, accent, `· error` suffix, the key argument
elided **at the width it renders at**, and a coloured rail around a fenced markdown
body. **`ToolHeader` is a renderable rather than a build-time string**, so elision
happens after the panel and rail claim their columns — the shipped defect that
fixed the header at 44 columns.

**Approved, outside the surface and the good kind:** `codecs.rs` computed a tool's
attributes and content inline in each XML renderer; `tool_use_parts` and
`tool_result_parts` were extracted and **both XML renderers routed through them**.
Additive, behaviour unchanged, **one authority replacing two** — the
`message_local_datetime` shape. **`BodyContext` gained `home`**, because *a
renderer that reads the environment cannot be gated at two different homes.*

### ⚠ RULED WITHOUT ESCALATION: build the `Edit` diff on a vendored `difflib`

**L253 escalated this as fidelity against cost. The measurement removed the
tradeoff, so the fork does not exist and was not taken up.** *A fork with one
dominant option is not a decision.*

**`difflib` 0.4.0, patched, agrees with CPython on 2,814 of 2,814 real Edit calls —
100%.** About **500 vendored MIT lines with one operator corrected, against a
687-line hand port**: cheaper *and* exact. **`similar` agrees on 9.7% and is not a
difflib reproduction — do not consider it.**

**⚠ AND THE NUMBER THAT NEARLY WENT UNMEASURED IS THE ONE THAT MATTERS. Only 3 of
2,814 real Edits reach 200 lines, so a clean pass on the real corpus proves almost
nothing about autojunk** — the thing most likely to be wrong. A second corpus of
900 pairs from real file bodies over 200 lines, **where autojunk changes CPython's
own answer on 23.9%**, gives **published crate 28.0%, patched 99.67%.**

**The defect is one operator.** CPython adds elements appearing in over 1% of
positions to `bpopular` and **deletes** them; the crate **keeps exactly those**. The
filter is inverted, so on long input it matches against a handful of blank lines.
**28% correct on large input means the patch is not optional.**

**Residue 3 of 900 (0.33%), mechanism unknown, none reachable from real Edits. And
a hypothesis was tested and disproved rather than left standing** — a two-phase
`find_longest_match` extension made it *worse*, 99.67% → 92.56%, because with
`isjunk=None` the second phase extends over nothing. Reverted; **the figure is from
the reverted state.**

**This is L255's fifth bound answered in advance rather than found afterwards** —
the corpus that *could* see the defect was built instead of the one that could not.
First time on this mission in that order.

### ⚠ L259. The `Read` gutter has NO failing case — and L254's list was wrong on my word

**`tool-read-result-promoted-extension` and `tool-read-result-unported-extension`
pass, so they are not the specification L254 recorded them as.** **A Claude
`tool_result` carries no tool name**, so a result's name resolves to `Tool` rather
than `Read`, and **both routes fall through to the fenced body.** They agree for a
reason that has nothing to do with the gutter. **Third corpus this week that
agreed for the wrong reason**, after `placeholder` and `sql`.

**The successor's FIRST question, not their second: how does the product resolve a
result's tool name from its paired use?** Until that is answered, **a wrongly-shaped
case would be worse than a missing one** — which is why the gap was left named
rather than filled.

**`tool-edit-diff` still differs and is held in `KNOWN_UNBUILT_BODIES`, an asserted
exact set** — the gap stays named while the tree stays quiet, **building the diff
makes the case agree and the test then demands its own removal**, and any other
case joining the set is a regression rather than a gap.

**Cutover status: still blocked, but no longer by a crash.** `engine-and-codex` is
re-measuring the five shapes. **A visible parity break is still a parity break**, so
the arm waits on the diff and the gutter — measured, cheap and named work.

### L260. `lexer-tables` stopped clean — the last implementation seat is closed

*2026-09-01T12:15Z. `session_render.rs` `df063bbe3d9d`, `codecs.rs` `3cf2657960c5`,
`syntax_tables.rs` `1dfb6f41dac7`, `syntax_table_gates.rs` `1fa0569e4b13`.
**234 lib + 53 doctests green, five configurations, zero warnings, tree quiet.***

`teammates/lexer-tables/RESUME.md` covers both halves of the seat after a whole
read. **What a successor meets first:** the Edit recorded **as a ruling, not a
question**; the autojunk corpus written down **as the reason the first corpus could
not see the defect**; the disproved two-phase hypothesis **kept with its worse
figure**; the `Read` gutter recorded as **having no failing case, in those words**,
with the tool-name-resolution question stated as the successor's first;
`KNOWN_UNBUILT_BODIES` documented as **demanding its own removal**.

**Two reconciliations the whole read produced:** the uncommitted-edits list now
names the tool work and the `codecs.rs` extraction rather than only the fence
changes, and the parked markdown note now states that the seven-language closure
makes its live answer **no**, so it reads as parked rather than pending.

**They stopped on a two-day-stale 75% treated as a floor** — the stop was raised
before the build and honoured at it, and everything landed today landed green.

## ▶ MISSION STATE — one seat active, three seats needed

**`engine-and-codex` is re-measuring the five previously-panicking shapes.
Everything else is stopped with a cold-entry brief.**

**Blocking the cutover, both named and both cheap:** the `Edit` diff (ruled: vendor
the patched `difflib`) and the `Read` gutter (blocked on one question, not on
work).

**Seats needed, in order:** the tool-build successor in `session_render.rs`
(blocks the cutover); the parity-list implementer in `session.rs` / `python_io.rs`
(blocks G5, disjoint, parallel); the G5 runner, **who must not be an implementer**
(blocks completion).

## ▶ L261. Eleven shapes clean — and the panic class is NOT closed

*`engine-and-codex`, 2026-09-01, against the rebuilt driver.*

**Clean, exit 0:** default, `--full`, `--thinking`, `--plans`, `--agents`,
`--branches`, `--short`, `--tools`, `--tools Bash`, `--tools --full`.
(`--custom` exits 2 — grammar error, not a panic.) **`Part::Tool(_) =>
Unsupported("tool")` is gone.**

**⚠ `search-firstmate` wrote "if they are clean, the panic class is closed" and
that inference is wrong.** The panic at `search_views.rs:1968` still exists and
**exactly one route still reaches it**: `Unsupported("fence lexer budget")` at
`session_render.rs:3700`, step-budget exhaustion inside the syntax lexer.

**That route is content-driven, not flag-driven, so no flag sweep can rule it
out.** Eleven clean shapes over a small curated fixture is the evidence shape this
mission has been caught by seven times.

**A 147 KB pathological Python fence — long unterminated strings, 80-deep nesting,
repeated 400 times — rendered fine at exit 0. Reported as unmeasured, not as
safe: not easily reachable, not proved unreachable.**

### ⚠ RULED: the fence ruling transfers. A budget-exhausted fence renders plain.

**The comment at `session_render.rs:3700` justifies refusing on the grounds that
Python's `re` has no step budget, so there is no behaviour to reproduce. That was
written when refusing meant a typed error.** Once the panel sink existed, refusing
began producing a truncated scan and exit 101 — **a failure worse than the
approximation it prevented. Identical in structure to the fence-language case, and
strictly rarer.**

**So: a fence exhausting the step budget renders plain, with complete geometry, and
never refuses.** The false comment goes with the fix — **a false comment directs
the next change, and that one has been false since the sink landed.**

**Two constraints on whoever implements it.** The gate must **force** exhaustion —
a real corpus cannot reach it, so **a test that shrinks the budget and asserts
plain output with no panic is the only honest falsifier.** And **close the route
structurally rather than with a second refusal**: once no producer of `Unsupported`
remains on that path, the sink's panic should be **impossible by construction, not
merely unreached.** Removing the possibility beats guarding it.

### L262. `engine-and-codex` at 90% — the arm needs a seat

**They flagged the reading before taking work and declined the landing themselves.**
**A landing abandoned midway in `main.rs` is the one failure mode this mission has
no cheap recovery from.** Handoff being written; it carries the preparation, the
three verified hazards, the `HOME` resolver, this ruling, and the budget route
recorded as unmeasured.

**The seat count is unchanged at three, with the cutover landing folded into the
first**, which carries the critical path end to end and hands off if it runs out:

1. **Critical path to the cutover** — `session_render.rs`: the `Edit` diff on the
   vendored patched `difflib`, the `Read` gutter, the budget-exhaustion plain
   fallback. **Then land the arm** from `engine-and-codex`'s brief.
2. **Parity list** — `session.rs`, `python_io.rs`, `raw_transcript.rs`. Disjoint,
   parallel, blocks G5.
3. **G5 runner, not an implementer.** Blocks completion.

### L263. `engine-and-codex` stopped clean at 90% — the mission is fully at rest

*2026-09-01. Tree digest `ca874ce060f1` over `rust/**/*.rs` hashed in sorted order.
`search_engine.rs` `bd23b41526de`, `search_confirm.rs` `f35a86bf8c54`,
`search_output.rs` `a358e67632a5`, `search_run.rs` `f478f84bd73d`, `codex.rs`
`4c7bfd2c4e98`, `raw_transcript.rs` `76df0701b527`, `python_io.rs` `ff245bf7c517`.*

**`teammates/engine-and-codex/RESUME.md`, 456 lines**, carries the three verified
hazards, G5's expiring width precondition **and its answer** so nobody spends
`reviewer-profiler`'s question on it, the `HOME` resolver with its three-state
table, the eleven-shape sweep, the panic narrowed to one route in the words
required — **not easily reachable, not proved unreachable** — and the budget ruling
recorded **as ruled and not implemented**, with both constraints.

**Nothing partially written, no mutation in any file. The snapshot at
`/private/tmp/ch-pool-snapshot` stays, with its date and reason.**

### ⚠ L264. Five seats reached the same conclusion today without coordinating

**A brief patched section-by-section drifts exactly like a stale copy, and only a
whole re-read catches it.**

`engine-and-codex` reconciled their own brief three times against a tree that moved
underneath it: **it claimed 173, 180 and 234 tests in three places, and it recorded
a deliberate red that had since been resolved — which would have sent a successor
hunting a failure that no longer happens.** That is the most expensive shape a
handoff can take: the reader has no way to know it is wrong and every reason to
trust it.

**Today alone:** `reviewer-profiler`'s runbook (three contradictions, all true
statements that had stopped being true); `lexer-tables`' whole read (two
reconciliations, and earlier a brief asserting the opposite of its own code);
`engine-and-codex`'s brief (three test counts, one resolved red); the `sql`
fallback subject and the removed `g4-fence-never-covered` row (both justified on
languages promoted since). **Five arrivals, five seats, no coordination.**

**And the half usually left out, from the person who did the reconciling: it is
internally consistent as of that digest, and it will not stay that way on its own.
A reconciled document is true at a digest, not thereafter** — which is why every
report on this desk carries when it was taken.

## ▶ MISSION FULLY AT REST — every seat stopped, three seats needed

**Nothing is in flight. Every seat has a cold-entry brief. The tree is green,
quiet, and uncommitted at `ca874ce060f1`.**

**Blocking the cutover, all three named, measured and cheap:** the `Edit` diff
(ruled — vendor the patched `difflib`); the `Read` gutter (blocked on one question,
not on work); the budget-exhaustion plain fallback (ruled, not implemented).

**The three seats, in priority order, are with the captain.**

## ▶ L265. THREE TAIL SEATS APPROVED. Captain, 2026-09-01, on a fresh window.

**Roles and prompts, written from current state and both handoffs:**

| Role | Prompt | Owns exclusively | Blocks |
| --- | --- | --- | --- |
| `cutover-finisher` | `prompts/cutover-finisher.md` | `rust/session_render.rs`, `rust/main.rs`, `probes/searchdriver`, the vendored diff module | **the cutover** |
| `parity-finisher` | `prompts/parity-finisher.md` | `rust/session.rs`, `rust/python_io.rs`, `rust/raw_transcript.rs`, the wrap-oracle gate | **G5** |
| `g5-runner` | `prompts/g5-runner.md` | **nothing — edits no production source and no tests** | **completion** |

**Seats 1 and 2 are disjoint by file and run in parallel; that disjointness is
stated in both prompts as the reason.** Seat 3 is **read-only until the cutover
lands**, because a run started against a moving tree measures nothing —
`search-firstmate` gives it the word.

**Seat 3 must not be an implementer.** Decision 2 in its unconditional form,
arriving at the last gate: **G5 cannot be run by someone who built the thing.**

**Each prompt carries its own definition of done, its falsifiers, and an explicit
"not yours" list** naming the peer who holds those files and instructing the seat
to **report rather than fix.**

**The three rulings already made are written as rulings, not questions** — the
`Edit` diff on the vendored patched `difflib`, the budget-exhaustion plain
fallback, and the seven-language closure — **so no seat re-opens a settled
tradeoff.**

**And the two deliberately-open items are written as open, with their reasons:**
the `Read` gutter has no failing case and its first question is tool-name
resolution, not the gutter; and the C0 enumeration is **provisional and must be
re-derived from the code rather than inherited from the list.**

### L266. The three tail seats are live and reading. No dispatch was sent.

*2026-09-01. `cutover-finisher [5aa89f]`, `parity-finisher [09264a]`,
`g5-runner [d99ab3]` — **all three address by bare name, no prefix.** Every prior
owner stays idle.*

**Nothing was messaged to them on launch, deliberately.** Their prompts already
carry the ownership boundaries, the rulings, the open items with their reasons,
the definitions of done, the falsifier requirement, and `g5-runner`'s hold. **A
welcome message would have cost three seats context to tell them what they were
already reading.**

**The two things `search-firstmate` still owes them, and neither is due yet:**
`g5-runner`'s word to start, once the cutover lands and the tree is quiet; and
routing `g4-fence-covered-later`'s launcher window to `contract-owner` when
`cutover-finisher` asks for it.

## ⚠ L267. BOTH OWNERSHIP LISTS WERE WRONG, AND IN THE SAME WAY

**`search-firstmate` wrote both new prompts' file lists from descriptions of the
work by its *symptoms* rather than by its *files*. Both seats caught it within
their first hour. Twice in one day is a defect in how the lists were written, not
an accident.**

**`parity-finisher`:** three of four items were not in the three files they were
given. **F16's second `truncate_to_cells` is `search_output.rs:129`; F17's second
`chop_cells` is `terminal.rs:655`; the wrap splitters are `terminal.rs::rich_words`
and `session_render.rs::words`; the two `rstrip_end` are `terminal.rs:676` and
`session_render.rs:280`. All private to their own modules** — so no external test
can call them, and no public caller separates the two copies. **They had been on a
list for days as "duplicate helpers" with neither copy ever located.**

**`cutover-finisher`:** item 3 says *close the route structurally*, which is an
edit in `search_views.rs` — **a file the list excluded.**

**Ruled and both prompts corrected on disk.** `parity-finisher` gains
`terminal.rs`, `search_output.rs`, `cells.rs` — all held by stopped seats — and
reads its DoD as *no edit in `cutover-finisher`'s files*. **`cutover-finisher`
gains `search_run.rs` and `search_views.rs`.** **`session_render.rs`'s wrap copy is
driven through its public entry, read-only, and the gate states that as a coverage
limit at the top: composed, not isolated.**

**`lib.rs` is shared, one appended `mod` line each, by announcement.** The in-tree
precedent is `#[cfg(test)] mod syntax_table_gates;`. **A `#[path]` detour to dodge a
one-line collision was rejected** — a second pattern is worse than one message.

**F17 needs no re-derivation: L139 already ruled it.**

## ⚠ L268. THE FOURTH CONTRADICTION IS IN THE REMEDY FOR THE THIRD

*`g5-runner`, read-only, coverage limit stated first, both digests declared stale
by construction.*

**`g5-runbook.md:103` — written to fix L256 — reproduces the defect it prevents.**
It says use `--full` or `--color always` without `-ll`. **`--full` alone does not
reach the coloured sink:** `search_run.rs:125` and `:148` gate both coloured sinks
on the **resolved** `flags.color`; a probe run non-interactively is piped,
`--color auto` resolves off, and `--full` lands in `PlainSink` at `:187`.

**It decayed the same way the other three did.** The note's own sentence says
*"panics on a colour terminal"*, and **check 10 specifies an empty directory and a
stripped PATH and never specifies a terminal** — the condition that made the
sentence true is not carried into the check. **A remedy is a dated fact too.**

**Fix: check 10's search half passes `--color always`, unconditional, no pty.**
`--full` may ride along; it must not be the whole shape. **And the same sentence's
"`--full` panics with exit 101" is stale — L261 measured it clean.**

**Ruled: `g5-runner` does not edit the runbook.** It is the specification of the
proof they run, and **a runner who can edit the specification can weaken it** — the
held-out-corpus hazard in different clothes. `reviewer-profiler` holds the
correction.

### The identities `g5-runner` re-derived first-hand, all at `ca874ce060f1`

**Oracle route digest `sha256:dd6ab701…badcee0`, UNCHANGED — production search is
still Python.** Rust tree digest matches L263 exactly. Corpus 695 files,
1,183,541,907 bytes, `de693c35…284965`. **Frozen reference set: 82 entries on
disk**, confirming L248.

**One precondition holds** — `rg -n 'search' rust/main.rs` returns nothing; the
cutover has not landed. **One EXPIRED, and not the way the runbook predicted:**
`search_run::run` now has a caller — `probes/searchdriver/src/main.rs:12` — because
**the rebuilt driver got there before the cutover**, and L261's eleven-shape sweep
ran through it. **The consequence was checked rather than assumed: the driver
passes `terminal_width()`, the intended source.**

### ⚠ Open and in flight: does anything sweep `COLUMNS` against help and error?

**The arm uses two width sources** — `terminal_width()` for `run`,
`argparse_columns()` for help and errors — **and they read `COLUMNS` by different
rules**: `columns_override` follows Rich and rejects `+96`; `python_int` follows
`int()` and accepts it. **Reported as an unanswered question, not a no.**
`reviewer-profiler` is answering. **If nothing sweeps it, the arm makes the hole
reachable and `cutover-finisher` closes it before landing.**

## ⚠ L269. ANSWERED: no gate sweeps `COLUMNS`. It is a hole, and it is now a ruling.

*`reviewer-profiler`, verified across their own eleven gates rather than recalled.*

**`COLUMNS` appears only as a FIXED value of 80** — the piped base and the freeze —
**never as a swept input, and it is in no sweep table.** **`pty_harness` actively
scrubs it from inherited environments**, so the width gate varies the *pty*, not the
variable. **And the only help shape anywhere is `performance_gates`' `search
--help`, which is timed, not byte-compared** — it could not see a rendering
difference if one existed.

**So the two-resolver divergence is unreachable by every gate that exists.**
`argparse_columns` uses `python_int`, following `int()`, and **accepts `+96`**;
`terminal_width` uses `columns_override`, following Rich, and **rejects it**. **Help
and error shapes take the first, and nothing has ever compared their output at a
swept `COLUMNS`.**

**RULED, and `cutover-finisher` closes it before landing the arm: a gate that
sweeps `COLUMNS` against the help and error shapes, byte-compared against
`ch-legacy`, including a value the two resolvers disagree on. Do not stop at
`+96`** — a gate built from one known-divergent value proves the value, not the
parameter. **This gate is what makes the arm's two-resolver split safe to keep**,
and the hazard it guards is a later "simplification" to one resolver.

**Held parameter nobody chose, second bound.** A shared harness scrubbed `COLUMNS`
and every downstream gate inherited the blindness **while each one's own description
stayed accurate** — the `stderr=DEVNULL` mechanism exactly.

**"Unanswered" became "hole" because someone could check eleven gates and say it is
unreachable by all of them.** `g5-runner` could only report that nobody knew.
**Those are different claims and only one is actionable.**

### L270. The limit of the whole-re-read practice, found by the practice

**`reviewer-profiler`, on `g5-runner` finding the fourth contradiction:** *"I wrote
that sentence four hours ago, corrected the document twice since, and would not
have looked at it again."*

**A whole re-read catches what a scoped check cannot — but only when someone else
does the reading.** The author's own whole read had already passed over that
sentence twice. **That is the argument for the fresh seat, stated by the seat it
replaced.**

**`held-parameters.md` is now six bounds numbered 1–6** — Inputs, Conditions,
Categories, Direction, Streams, Vocabulary — and the dangling *"the fourth is the
one to look for"* now names **Streams**, with its reason: **a held parameter
someone chose is usually documented; one inherited from a shared helper's default
is invisible everywhere downstream while the helper's docstring stays accurate.**

**Check 10's correction is written in as the fourth instance rather than quietly
applied**, because *a remedy is a dated fact too* is the transferable half. **A
document that records why its own fix decayed teaches what a clean fix hides.**

**`reviewer-profiler`'s seat is closed for good.**

## ▶ L271. THE PANIC CLASS IS CLOSED BY CONSTRUCTION. `Unsupported` no longer exists.

*`cutover-finisher`, 2026-09-01. `rg 'Unsupported\('` over `rust/**` returns
nothing.*

**A budget-exhausted fence renders plain with complete geometry.
`render_code_block` returns `Vec<Segment>`; `ColouredPanelSink::render` returns
`String`. The sink has nothing to panic on.** The route was removed rather than
guarded, as ruled at L261.

**Six false comments, five found by this seat.** The budget refusal at
`session_render.rs:3700`; `search_run.rs:159-162`; the panic message at
`search_views.rs:1968`; **the fence arm's own header comment, contradicting the
2026-08-30 ruling three lines below it**; and a sixth in the generated
`syntax_tables.rs`, whose `promoted_lexer` doc tells a reader **not to repair the
branch or the comment into agreement** because the ruling is in flight — **it
landed at L237.**

**Ruled: the generated comment is in scope** — fix `probes/generate_lexer_tables.py`
and regenerate — **with the constraint that the regeneration diff must be shown to
be comment-only.** A generated file regenerated by a different hand can move for
reasons nobody asked for.

**Every one of the six asserted a ruling that had since landed.** A false comment
directs the next change.

### The gate, and why it is the shape to cite

It shrinks the **real** step budget inside the **real** VM via 25 `#[cfg(test)]`
thread-local lines in `search_query.rs` — **approved, stays there, test-only**;
moving it would mean an unreachable private budget or a production seam, both
worse.

**Four tests, and two of them are the reason it is a gate rather than a
description:** a **control** proving a whole budget colours the same fence, **so the
first test is not comparing plain against plain**; and a falsification running
**two** deliberately wrong fallbacks — a refusal *and* a truncation — through the
same judgement. **Falsified by hand in both directions, and both failure messages
name the modelled cause.**

## ⚠ L272. THE RECORDER COULD NOT EXPRESS THE CASE — third time this week

**`generate_body_oracle.py` calls `build_messages_group(messages, flags, None, …)`
where the product passes `_build_tool_id_map(hit.messages)`. With `None`, no tool
result can ever resolve its name**, so every result rendered as `Tool` and **four
behaviours became unreachable at once.** Measured both ways at width 68:

1. **The `Read` gutter fires with the map and not without it** — `⎿ Tool` /
   `▎      12  def add(a, b):` becomes `⎿ Read` / `▎   12 def add(a, b):`.
   **This is the failing case item 2 was missing.**
2. The result header label `Tool` → `Read`.
3. **A fifth unbuilt body:** `_tool_result_label` returns `"output"` for a
   Bash-result message, so the header is `⎿ output`, not `⎿ Bash`. **Rust's
   `tool_renderables` has no `result_label` parameter at all.** In scope.
4. The message badge ` User ` → ` Bash `. **Rust already gets this one right**,
   because `visibility::resolve_result_name` resolves at projection time.

**After `flags_from` and `placeholder`, this is the third recorder or corpus this
week that could not express the case it asserted on.**

**The body oracle and `probes/generate_body_oracle.py` are `cutover-finisher`'s.**
`contract-owner` told, so it is not an unannounced move; **`tests/` proper, the
fixtures and the route-flip suite stay theirs.**

### ⚠ Twelfth preserve-because-wrong item — recorded here, not in the document

*`preserve-because-wrong.md`'s owner is idle by the captain's instruction, so this
lives in `state.md` until someone can add it.*

**A tool result's NAME comes from `id_map` over ALL the hit's messages; the
`file_path` its gutter needs comes from `input_by_id`, built inside
`build_messages_group` from the DISPLAYED messages only.** The two scopes differ.
**So under a non-`--full` search, a `Read` result whose call is not displayed
resolves its name and finds no input, and falls through to the fenced body.**

**Build the asymmetry intact and record it at the call site.** A port that "fixes"
it passes every gate we have, **because the output looks better and nobody flags an
improvement.**

*Tree note: `ca874ce060f1` was re-derived at start rather than trusted and matched.
It has since moved — `python_io.rs`, `session.rs`, `terminal.rs`, `cells.rs` carry
`parity-finisher`'s live edits. **244 lib + 54 doctests spans two seats; report
deltas or name the side.***

## ⚠ L273. L258's TWO PERCENTAGES ARE REPORTED, NOT RE-DERIVABLE

**The 2,814-Edit and 900-pair `difflib` measurements cannot be reproduced from this
checkout.** No corpus, no probe, nothing under `tests/data/`. **`lexer-tables`
measured them in a session that has stopped.**

**This is decision 6 arriving early, by a door nobody watched.** The rule stores
every instrument's last consultation *before the oracle is deleted* — cheap now,
impossible after. **Here the instrument was a session, and the session ended.**
**A percentage whose instrument is gone is a claim, not a measurement.**

**⚠ `search-firstmate` ruled the `Edit` diff on those percentages and told the
captain the fork was closed by measurement. The ruling stands; its stated evidence
does not.** The ruling survives on two grounds that need no corpus: **the inverted
operator is verifiable from the code itself, and 500 vendored lines against a
687-line hand port is an arithmetic comparison.** **The quality figures are
reported until the fixtures land.**

**`cutover-finisher` is rebuilding both corpora as frozen fixtures with the inputs
AND CPython's answers stored** — decision 6's rule applied rather than quoted.

**And the published crate's inverted filter is kept in the vendored code as a
`#[cfg(test)]` mutation, so the gate must KILL it rather than assert it would** —
the difference between a falsifier and a claim about one.

### The vendored module

`rust/difflib.rs`, ~400 lines, `difflib` 0.4.0 (MIT, Dima Kudosh). **`lib.rs` line
`pub mod difflib;` announced, checked against `parity-finisher`'s absent line, and
appended.**

**Three deviations, each recorded at its site:** the inverted popular-element
filter; `ntest` as integer division rather than a floored `f32`; `unified_diff`'s
header dates and `lineterm` returned to CPython's.

**`Differ`, `get_close_matches`, `context_diff` and `ratio` were NOT vendored** —
the product reaches none of them, and **an ungated vendored function is a
liability.**

**⚠ `find_longest_match`'s doubled extension pass is kept verbatim, with the
99.67%-against-92.56% measurement in a comment telling the next reader not to "fix"
it into CPython's literal two-phase form.** **This is the first named trap on this
mission that was avoided rather than rediscovered** — L258 recorded the disproved
hypothesis, the brief carried it, and the next hand disarmed it without paying for
it again.

## ▶ L274. F1, the C0 set and F16 landed — and two unlisted defects that change search results

*`parity-finisher`, 2026-09-01. `lib.rs` line appended after reading the file:
`#[cfg(test)] mod wrap_gates;`, following the `syntax_table_gates` precedent.
`cutover-finisher`'s `pub mod difflib;` was already in at line 3.*

**F1 — universal newlines.** `python_io::read_text` **decodes then translates, in
that order**, because text mode decodes first and `UnicodeDecodeError` positions
are byte offsets into the undecoded input. **0 of 5,061 `.jsonl` files under
`~/.claude`, `~/.pi` and `~/.codex` carry a literal `\r`, so F1 joins the
ungradeable set** and its five gates are authored and say so. **Reverted, the
composed gate reports `left: []`: a lone-`\r` Claude session is classified `Raw`
and yields nothing.**

**The C0 set is 23 sites, not 20.** Search shapes stated: every `trim` substring;
every `\s \S \w \W \b \d \D`; `is_whitespace` / `split_whitespace` /
`is_ascii_whitespace`; **and a cross-check from the Python side**, every
`.strip(`/`.lstrip(`/`.rstrip(` in `parsing.py` mapped by enclosing function to its
Rust port.

**⚠ The three the inherited list missed — `extract_text_blocks`,
`codex_text_blocks`, `pi_response_matches_preview` — are all written
`.map(str::trim)`. The inherited enumeration searched for `.trim()` with
parentheses, so the function-path form escaped it.** Same failure as its `\s`
miss, one level down. **Twice now the defect was that enumeration's *search shape*,
not its judgement.**

**Both character classes measured over all 1,114,112 scalar values by both
engines:** CPython `\s` is Rust `[\s\x{1C}-\x{1F}]`, **exact both directions**;
CPython `\w` is `[\p{L}\p{Nd}\p{Nl}\p{No}_]`, exact, **and the bare classes differ
both ways** — 2,642 scalars Rust accepts and CPython rejects (combining marks,
`Join_Control`), 915 the other way (`Nl`/`No` numerics such as `½`).

**The C0 gate injects separators into the real pool** rather than authoring 23
fixtures, and **imports `session-core`'s differential rather than copying it**.
Control arm re-serializes without injecting and must report zero. **2,520 cases,
0 mismatches, control 0. Falsified by reverting `python_is_space`: 670/840 Claude,
840/840 Pi, 784/840 Codex** — a spread that names which provider a regression hits.

**F16 landed.** `search_output.rs`'s private `truncate_to_cells` deleted, `rule`
calls `metrics.truncate_to_cells`. **The survivor was proved against the caller by
two tables:** the recorded 99 rows stay green, **and 48 new rows separate the two
implementations**, generated by a script that **regenerates all 99 from live Rich
and refuses to write unless they reproduce**. Before unification the new table was
red at width 6. **Its falsifier keeps the deleted implementation and requires it to
fail at least 11 of the 48** — the measured figure.

### ⚠ L275. Two defects nobody had listed, both changing search results

**1. A mismatched command block was hidden in Rust and visible in Python.** Python
closes with the backreference `</(?P=tag)>`; **the `regex` crate has none, so the
Rust pattern accepted `<command-a>x</command-b>`.** Measured both ways. The closing
name is now captured and compared.

**⚠ This is a class, not a bug: a Python pattern that cannot be expressed in Rust's
regex silently becomes a MORE PERMISSIVE pattern. The code compiles, the tests
pass, the behaviour differs.** **A sweep is commissioned** — backreferences and
conditional groups in the authority's own internal patterns on the search route,
excluding user query compilation, **to be reported as a measured negative if
none.**

**2. `dedent` could panic, and was not `textwrap.dedent` at all.** It sliced a line
at a byte count taken from a **different** line, so `"\u{a0}a\n\u{2028}b"` landed
inside U+2028. **CPython 3.14 takes the common prefix of the lexicographic min and
max non-blank lines, restricted to space and tab**, so `" a\n\tb"` is unchanged
where a shortest-indent rule gives `"a\nb"`. Faithful port, gated on twelve
transcribed CPython answers.

**And the sharpening that explains why it was wrong: `session-core` classified the
two `dedent` sites "correctly bare". The action was right and the reason was not.**
It is not that `.trim()` is correct there — **it is that the value is discarded on
both routes**, because Python's only consumer `_render_user_command_input` has no
callers. **So `dedent` was free to be wrong, and was.** **A correct classification
resting on a wrong reason survives every review and fails the moment someone adds a
caller.**

**Clean negative, stated so nobody re-runs it:** outside those three files, **no
module on the search route has a bare Rust whitespace trim.** `codex.rs`,
`pool_filter.rs`, `search_run.rs`, `search_confirm.rs` all already call
`python_strip`. `session.rs` was the last holdout.

**Routed: `rust/codex.rs` goes to `parity-finisher` for one deletion only** — its
private `is_python_space`, three call sites becoming
`session::python_strip_start(...)`. **Its comment claiming the duplication exists
because "`session.rs` is frozen and keeps it private" is the seventh false comment
whose stated reason had expired**, and it goes with the deletion.

## ▶▶ L276. THE ARM IS LANDED. `ch search` RUNS ON RUST.

*`cutover-finisher`, 2026-09-01. Tree digest `9e2d2c3fb533` — `session_render.rs`
`11eabc889b7d`, `main.rs` `09584ac967a8`, `search_views.rs` `bfc99dbf15af`,
`search_run.rs` `cdfbe2e14b4b`, `difflib.rs` `5e6cee1aabfe`, `codecs.rs`
`aaf99c346c25`. **264 lib + 56 doctests across two seats; this seat's delta is +30
lib and +3 doctests** against the 234 + 53 it started from.*

**All four pieces are in.** The `Edit` diff, the `Read` gutter, the plain fallback,
and the arm.

### ⚠ The blocker: the mission's central gate is unrunnable, and nothing is wrong

**`test_search_command_contract.py` refuses to run.** `_reject_foreign_launcher`
rejects the built launcher because it embeds `logicalParentUuid`. **The guard's
premise was "a launcher containing this string cannot have come from HEAD" — and
landing the arm made that false in the honest direction**, because the search arm
links the whole `_native` library into `ch` for the first time. **The decayed-
assertion class again, now standing between the mission and its proof.**

**RULED: invert the guard. No checkpoint commit.** A commit would make the guard
pass **by changing the world rather than fixing the guard**, and the false premise
would survive to reject the next fresh build carrying uncommitted work — which is
every build during development. **A positive freshness proof — the binary must
carry a marker only the current tree produces — cannot decay that way.**

**Three constraints.** It must be **strictly stronger**: still catching a stale
`wip/cycle-02` binary squatting in `target/`, a hazard this mission has hit.
**Falsified — a stale binary must fail it, demonstrated.** And its failure message
must say what a failure means. **`cutover-finisher` is changing the guard that
blocks their own proof, so the boundary is named rather than trusted:
strengthening is fine, removing is not.**

### ▶ THE ROUTE FLIP HAS ARRIVED

**The contract suite's own header — *"Today `ch` hands search to `ch-legacy`, so
this compares a process with itself"* — stopped being true when the arm landed.**
**It has become the differential it was built to be, and 260 assertions that have
never been able to fail are about to be able to.** Nobody has seen it run in that
state. **`contract-owner` is woken when the guard is settled, and not before.**

### The `COLUMNS` gate — the hole is closed

**0 differences over 72 comparisons.** Four shapes — `--help`, an unknown option,
an invalid date, a no-results run — against **eighteen** `COLUMNS` values,
byte-compared with `ch-legacy` on stdout, stderr and exit status.

**It does not stop at `+96`:** empty, zero, negative, `0096`, `' 96'`, `'96 '`,
`'  120  '`, fullwidth `９６`, Arabic-Indic `١٢٠`, `1e3`, `abc`, and a value
carrying its own newline. **Eight move the help width and argparse reads them; the
rest it ignores — which is what makes it a parameter test rather than a value
test.** New file `tests/test_search_columns_sweep.py`, so `run_all.sh` picks it up
with no edit to anyone's script.

### The `Read` gutter — and a third corpus bought by a mutation that survived

**The asymmetry is ported intact with its reason at the call site** (L272's twelfth
preserve-because-wrong item).

**Three gates:** the body oracle's synthetic pair; a render oracle of **144 records
from 2,676 real `Read` results at two widths**; and **a lexer-resolution oracle of
353 real paths.**

**⚠ The third exists because a mutation survived.** Disabling the `*.js` delegation
test left the render oracle green — **its 144 records happened to hold no `.js`
file Pygments hands to a template delegate, and the wide corpus holds five.** **A
mutation that catches nothing was a question about the corpus, and the answer was a
third corpus.**

**Six mutations falsified by hand, all named**, five dying with messages naming the
modelled cause; **the sixth bought the third corpus.**

**Two product facts for the desk.** **Reading a `.sql` file renders plain:**
`SqlLexer`, `TransactSqlLexer` and `SqlJinjaLexer` all claim `*.sql`, `SqlLexer`
can never score above zero, and **the tie-break is the class name — so Transact-SQL
always wins, and SQL is promoted for fences and unreachable here.** And **a `.js`
file containing `${…}` goes to `JavaScript+Genshi Text` and also renders plain** —
6 of 127 real `.js` reads.

**The unported-language divergence is bounded rather than allowed.** Markdown is
37% of real `Read` calls and unpromoted. Both oracles compare such a case by
**exact geometry, exact text and per-character backgrounds, freeing only the
foreground — and each asserts the relaxation is not inert.** **A promoted family
gets no relaxation at all.**

**`syntax_tables.rs` regenerated and the diff is comment-only** — one doc block,
nothing else moved, exactly the constraint set at L271.

### L277. The falsifying artifact for the inverted guard exists only in this hour

*`g5-runner`, holding, raised because `cutover-finisher` is in that file now.*

**A positive freshness proof that has never been shown to fail on a stale binary is
green for an unknown reason.** L9's shape — **a falsifier proves a gate fires for
the modelled cause, not merely that it fires** — and check 10's shape one file
over.

**The demonstrated red was already required at L276. What this adds is that the
artifact able to prove it exists only while `cutover-finisher` still has one.**
Rebuilding a `wip/cycle-02` binary later to falsify a guard is the expensive
version of something nearly free today. **The same rule as storing an instrument's
last consultation before the oracle goes: cheap now, awkward afterwards** — and the
second time in two days that rule has arrived through an unwatched door (L273 was
the first).

**Instruction issued: keep one stale build, show the guard red against it, keep the
reproduction.**

**And the reason it matters more today than it would have yesterday: the fix is to
a gate, made by an implementer, on the day 260 assertions become able to fail for
the first time.** Decision 2's reasoning exactly. **The boundary was named when the
ruling was made; naming it is not the same as proving it.** The seat raised a
pressure rather than an accusation, which is what the seat is for.

*Closed, so nobody carries it: `search_run.rs:159-162` and `search_views.rs:1968`
were fixed this morning with the plain-fallback landing — six false comments in
that pass, including the generated one, regenerated comment-only.*

### L278. The C0 set outside `session.rs` is four sites, not six

**`parity-finisher` traced each of their own three to its caller before editing and
found only one real.**

- **`codecs.rs:1071` — real.** `inner_opening_regex`, used by `encode_xml_text` at
  line 396, porting `xml_transport.py:15-19`, whose `\s` and `\w` are CPython's.
  **It decides whether message text gets HTML-escaped, and that reaches
  `render_message_inner_xml` — the string search matches against.** Taken.
- **`codecs.rs:1056` and `:1065` — no oracle.** Both serve only
  `parse_document_message` and `find_inner_opening`, the **XML-tagged-Markdown →
  JSON** direction, reachable only from `main.rs:267`. **`cmd_parse` formats *to*
  xml/json/raw and never back, so Python has no counterpart at all.** **Widening
  them would be a change with nothing behind it.** Left alone, **with the reason
  written at the site so the next reader does not "finish the set"** — an
  unexplained two-of-three looks like an oversight and gets tidied up by someone
  helpful.

**`cutover-finisher`'s two stand: `session_render.rs:2470` and `:2477` have a live
oracle at `formatting.py:320` and `:330`.** `search_views.rs:1585` unchanged.

**Third time this week an enumeration was right about the shape and wrong about the
members, and the second time this seat caught its own.**

### ⚠ L279. The ratio gate fixes ROT, not NOISE — and the control must be proved to scale

*Interleaved, five pairs each, subject and control alternating so drift hits both
arms.*

| shape | subject | control | ratio | spread |
| --- | ---: | ---: | ---: | ---: |
| `search . -ma 4h --list` | 1,474 ms | 30,044 ms | **0.049** | 1.33× |
| `search . -l -d .` | 3,473 ms | 28,439 ms | **0.122** | 1.19× |

**⚠ The ratio is barely more stable than the subject alone** — 1.33× against 1.38×,
1.19× against 1.20× — **because the control is the stable arm and the subject
carries all the noise. The ratio does not fix the flapping, and the gate must say
so.**

**What it does fix is the rot.** The control grows with the pool exactly as the
subject does, **so the bound stops needing to be pushed from 1,000 to 1,200 to
1,750 ms as the pool grows** — which is the defect the test's own comment
describes.

**And that is enough, because the failing test is not flapping — it has been
overtaken.** A 3,473 ms median against a 2,500 ms absolute is a budget the pool
grew past. **A ratio at 0.122 with 1.19× spread has room where the absolute has
none.** *Selling the ratio as a noise fix would have been the easy sentence and
wrong within a week.*

**RULED on the control: prove it scales with the pool; do not assume it.** The
honest control costs **30 seconds a run** — about five minutes across two shapes,
against a perf suite that currently takes seven. **A cheap control that turns out
not to grow with the pool silently reintroduces exactly the rot it was picked to
remove, and nothing in the gate would ever say so.** Candidates measured: `ch -1`
at ~950 ms, a no-match search at ~7–10 s. **Show the scaling, take the cheapest
that survives, and put the scaling evidence where the gate is read** — so the next
person to doubt the control finds the measurement rather than the choice.

**The other four shapes stay on absolutes and nothing is relaxed to pass.**

## ▶ L280. The launcher guard is an AGREEMENT, not a premise — and the suite is runnable

**For each of six probe strings the binary must carry it IF AND ONLY IF the working
tree does.** A stale artifact fails because it is **missing what the tree added**; a
foreign one fails because it **carries what the tree removed**. **The old guard
could only ever catch one direction, for one string.** `logicalParentUuid` is still
a probe — **tree-relative now instead of forbidden.**

**A seventh assertion guards the guard: fewer than four live probes and it
refuses**, because a decayed probe set can agree by accident. **A gate that knows
how it will rot.**

**Falsified against the real thing, and the artifact is kept.** A `wip/cycle-02`
binary built 2026-08-25 is committed as
`tests/data/launcher-provenance/ch-0ffde41`, 6.2 MB, with a `provenance.json`
carrying its digest, origin, **why it is kept**, and the rebuild recipe.
`tests/test_launcher_provenance.py`, four tests green, asserts the stale binary is
rejected, **rejected for the modelled reason rather than some other**, that the
message still says a failure means real staleness, that a matching launcher is
accepted, and **that the artifact is still on disk.**

**L277's one-hour opportunity is now permanent.**

### ⚠ L281. The sweep found two defects within an hour of existing

**1. `terminal_width()` disagrees with Rich at `COLUMNS=0` — routed to
`parity-finisher`.** `terminal_width_for` ends
`.filter(|width| *width > 0).unwrap_or(FALLBACK_TERMINAL_WIDTH)`, so `COLUMNS=0`
becomes 80. **Rich keeps the 0.** Measured in process: `Console(stderr=True,
theme=APP_THEME)` reports `_width == 0` and `width == 0`, and **the product prints
NOTHING** — `ch-legacy search zz -d /nope` at `COLUMNS=0` exits 1 with empty stdout
and stderr, where the native route printed the whole line.

**The filter is right for one path and wrong for the other, which is why it reads
as correct.** Rich's `width = width or 80` **belongs to the ioctl answer** — its
own comment says `get_terminal_size` can report `0, 0` from a pseudo-terminal. But
`Console.__init__` reads `COLUMNS` into `_width` and `size` returns it untouched,
**so an explicit `COLUMNS=0` is never clamped. One filter is applied to both
answers. Clamp only the measured branch.** Two sweep cases red until it lands.

**"Reproduce what Python accepts, not what it appears to intend" in its purest
form: printing nothing at `COLUMNS=0` looks like a bug and is the product.**

**2. `print_hint` folds at terminal width; both native sites did a raw `eprint!`.**
**It agreed at every width wide enough not to fold — which is every width a
developer types, and not `COLUMNS=40`.** Now wrapped through
`wrap_preserving_spaces` and byte-identical at widths 1, 2, 3, 40, 79, 80.

**⚠ And the empty-pool fixture hid it completely, because the line only appears
when the pool has sessions.** **A held parameter nobody chose, in the fixture
itself — switching the sweep to the contract corpus exposed both defects at once.**

**The three C0 substitutions are done.** `session_render.rs`'s two `\s` sites and
`search_views.rs`'s `\w`, each with the measurement in a comment. **What the `\s`
one was:** `formatting.py`'s tag-escaping pattern decides whether message text gets
escaped at all, **so a tag followed by a file separator was escaped by the product
and left alone here.**

## ▶ `contract-owner` IS AWAKE. THE ROUTE FLIP RUN IS THEIRS.

**`./tests/run_all.sh | cat` and the contract suite, with the tree digest at the
time. 260 assertions that compared a process with itself are now a real
differential.** **Two knowns so they are not chased:**
`test_search_dir_filter_list_under_2500ms` (overtaken by pool growth, conversion in
flight) and the two `COLUMNS='0'` sweep cases (the routed defect).
**`g4-fence-covered-later` is theirs too, with the launcher window.**
**`cutover-finisher` does not run `run_all.sh` — one seat in that window.**

## ▶▶ L282. THE ROUTE FLIP RAN. 230 of 260 GREEN. 30 diverge, and they are real.

*`contract-owner`, 2026-09-01, at 88%. **The first run on this mission that could
fail, and it failed. The failures are the deliverable.***

**The same 30 fail in all three classes — byte lock, live differential, authority
proof.** **That identity is the measurement: a harness fault would have failed the
three differently.**

    byte lock / live differential / authority proof   30 each, identical set
    frozen pattern successors                         23 + 1 generated
    age token and style                                7 of 7
    early-close gate                                   1  (a control firing, not a defect)

### ⚠ One behaviour accounts for 24 of the 30

**`--color always` produces no colour on the native route.** Measured:

    target/contract-suite/release/ch  search … --color always  → 0 lines with an escape
    .venv/bin/ch-legacy               search … --color always  → 3 lines with an escape

**It accounts for every `colored-*`, every `render-fence-*`, wide glyphs, long
wrap, the provider column, the title-elision pair, the pager case — and all 7 age
failures.**

**⚠ The age assertions are NOT the bucket misalignment this desk spent the day
predicting. They fail because there is no colour at all.** **A tired reader records
that as "age still broken" and hands it on.** Whether `--color always` is ignored
or colour is gated on a tty is undiagnosed. **One thing to fix, not twenty-four.**

### The other two

**A misplaced newline in warning emission** — `role-contradiction-warning`,
`fb-posix-class-warning`, `fb-posix-class-bare-warning`:

    expected  …disabling those options.\nNo sessions match "needle five".
    actual    …disabling those options.No sessions match "needle five".\n

**This is the third of the three hazards nothing type-checks, arriving exactly
where it was predicted** — the warning carries its own newline and prints before
the match with `eprint!`. **Verified correct in the driver; the arm diverged.**

**`lowercase-z-rendered-dates`** — the fixture built for exactly this, not yet
diffed.

**Nothing relaxed, nothing restamped. All 30 stand.**

### The early-close failure is a control firing correctly — recorded as a pass

*"Expected the full scan to take long enough to measure. It took 153 ms."* **The
800-session corpus went from 557 ms through Python to 153 ms through Rust, under
the 400 ms floor. The gate declined to report a ratio it could no longer measure
rather than passing on noise.** **A corpus adjustment, not a relaxed expectation**,
and the distinction belongs where the change is made.

### ⚠⚠ `rebless_oracle.py` HAS SILENTLY CHANGED MEANING — make it refuse

**It replays through the built launcher, which is now Rust.** **Re-blessing on its
verdict would stamp records current because the NEW implementation agrees with
them. Circular.** **It is a parity check now, not a re-bless tool.**

**The next person to reach for it will be someone with thirty reds and a
deadline.** **A comment will not hold it — where a hazard has a mechanism, change
the mechanism** (L193's controlled case: a tool that *printed* was ignored for
hours, one that *refused* was obeyed in seconds). **Ruled: it refuses when the
launcher is the native route, and the refusal says the verdict is circular.**

### Sequencing

**`run_all.sh` is NOT run now** — it would re-report the same 30.
**`cutover-finisher` fixes the three defects → `search-firstmate` releases the
suite → `g5-runner` runs `run_all.sh` as check 1 of G5.**
**`contract-owner` at 88%: the refusal first, the corpus second, handoff if
neither fits.**

### ⚠ L283. THE SEVEN AGE TESTS WILL LOOK FIXED WHEN COLOUR RETURNS, AND WILL NOT BE

*`contract-owner`, who wrote them. The most valuable line in the route-flip
exchange and it nearly went unsaid.*

**They do not assert that colour is present. They pin the label-and-colour
pairing — including that a `3d` row wears the WEEK colour and `2w` wears MONTH.
That misalignment is preserved on purpose.**

**⚠ So a colour fix that also aligns those two tables turns seven tests green for
the wrong reason, and a documented deliberate divergence dies silently** — every
gate green, the output looking better, and nobody flagging an improvement.

**Instruction to `cutover-finisher`: after the colour fix, re-run those seven
specifically and confirm the PAIRS, not the presence of escapes.**

**This is the first `preserve-because-wrong` item to sit directly in the path of a
fix somebody was about to make. The other eleven have the same exposure.**

### L284. `rebless_oracle.py` refuses, and it detects the condition by behaviour

    REFUSED: the launcher serves search natively, so this tool's verdict is circular.
    It re-blesses when replayed bytes match the record. Those records hold Python's
    answers. A native launcher matching them proves parity, not that the oracle is
    unchanged — so re-blessing here would stamp the record current on the strength of
    the port agreeing with it.
    Parity is what the contract suite measures. If the oracle has genuinely moved,
    re-characterize from `ch-legacy` with `generate_fixtures.py`.

**The detection is behavioural, not source-reading: a copy of the launcher alone in
a directory with no `ch-legacy` sibling — if it can still serve a search, the route
is native.** **The authority proof reused as a precondition, for one subprocess.**
**It cannot go stale against a source refactor** — which is exactly how the guard
it stands beside decayed, and how four other assertions decayed this week.

**And the refusal was verified by RUNNING it, not by reading it** — the distinction
between this and the six false comments found today.

**Early-close corpus raised 800 → 3000; both timing gates pass. The streaming gate
was checked for the same exposure unprompted and still discriminates.** **The
400 ms floor and the 0.7 ratio are unchanged — only the amount of work is**, stated
at the constant where the change was made.

**`contract-owner`'s seat is closed at 89% after appending the 30 to
`teammates/contract-owner/2026-08-28T16:20-contract-owner-handoff.md`.**

## ⚠ L285. THE RATIO CONVERSION IS CANCELLED — the plan did not survive its own admissibility test

*`parity-finisher` built the instrument ruled at L279 and used it to disprove the
plan it was built to support. `probes/control_scaling.py`, ~4 minutes, survives as
the admissibility instrument for whoever asks next.*

**Synthetic pools at 500 / 1,000 / 2,000 / 4,000 sessions. Growth = time ratio
normalised by session-count ratio: 1.00 grows in step with the pool, 0.00 is
flat.**

| command | 500 | 1000 | 2000 | 4000 | growth |
| --- | ---: | ---: | ---: | ---: | ---: |
| `search . --list` | 583 | 885 | 1122 | 1971 | **0.34** |
| `search zzzznomatchzzz --list` | 282 | 364 | 331 | 469 | 0.10 |
| `-1` | 300 | 349 | 381 | 656 | 0.17 |
| `search . -ma 4h --list` | 392 | 332 | 372 | 581 | **0.07** |
| `search . -l -d .` | 604 | 992 | 1318 | 3031 | **0.57** |

**1. `-ma 4h --list` does not grow with the pool at all — 0.07. It has no rot to
convert**, and its 1,763 against 1,750 was one flap in four runs. **A ratio gate
there would be ceremony.**

**2. No candidate control is admissible for `-d .`.** The closest grower is
`search . --list` at 0.34 against the subject's 0.57, **and the ratio itself rots:
1.04, 1.12, 1.18, 1.54 across the four pool sizes** — more slowly than the
absolute, in the same direction, for the same reason.

**3. The instrument states its own bound.** The synthetic pool grows in **file
count at fixed tiny file size**; the real pool grows in **both**. Real-pool ratio
for the same pair is **0.122** against a synthetic 1.04–1.54. **So it answers "does
this grow with file count", not "does this grow the way the real pool grows."**

**And the instrument caught its own held parameter first:** every synthetic session
stamped with one old timestamp, so `-ma 4h` matched nothing and the probe measured
a **short-circuit rather than a scan.** Re-run with a fixed recent share.

### ⚠ RULED: do not convert — but the premise is measured, not assumed

**The argument rests on "these budgets time `ch`, which today is the Python
route." The arm landed today.** Whether `.venv/bin/ch search` still hands to
`ch-legacy` depends on whether the installed launcher was rebuilt.

**If the launcher is already native the argument INVERTS: 3,031 ms is the native
route, the 7× headroom does not exist, and `-d .` is a real regression rather than
a doomed budget.** **The failing test reports 2,656–3,044 ms on the real pool — the
same order as the synthetic 4,000-session figure, which is what a 6–8× speedup
should already have moved.**

**Measurement ordered, using `contract-owner`'s behavioural test** — the launcher
alone in a directory with no `ch-legacy` sibling. One subprocess. **The ruling
stands or flips on the answer.**

**Assuming it holds: all four budgets stay untouched and unrelaxed, the record says
which route they measure, and they are re-taken after the cutover proof** — where
an absolute on the native route has real headroom and the ratio question can be
re-asked against a control shown to work on the **real** pool. **Converting now
would be decision 6's own trap: an instrument built around a route about to
vanish.**

### L286. `codecs.rs:1071` and the `COLUMNS=0` clamp landed

**`inner_opening_regex` builds from `PYTHON_SPACE_CLASS` / `PYTHON_WORD_CLASS`.**
Six cases from a live `encode_xml_text` run, three discriminating, **one running
the other way**: `<thinking\u{1c}id="1">` and `<thinking ½="1">` are escaped by
Python and were not by us; **`<thinking ́="1">`, a lone combining mark, is escaped
by the crate's `\w` and left alone by Python.** Red before green observed.

**The `COLUMNS=0` mechanism is one step subtler than recorded at L281.** `size`
**does** compute `width = width or 80` and then **throws it away** in its final
expression — `width - legacy_windows if self._width is None else self._width`.
**The clamp runs and is discarded.**

**Two `terminal.rs` changes, both gated.** The clamp applies **only** to the
measured branch. And **`wrap_preserving_spaces(_, 0)` now returns the empty string
where it returned the whole message** — measured against live Rich,
`Console(width=0).print(Text(...))` writes `''`. **Zero cells is nothing, not
everything, and returning the message reads as a sensible guard, which is why it
survived.**

**Sweep status: `no-results` at `COLUMNS=0` closed** — 0 bytes, exit 1, matching
Python, because `emit_hint` already guards on `width == 0`. **`invalid-date` still
red: 4,947 bytes of bare newlines against Python's 0**, from
`eprintln!("{}", wrap_preserving_spaces(...))` at **`search_run.rs:204` and
`:452`** — an empty string still costs a line. **Routed to `cutover-finisher`, who
holds that file.** *At `COLUMNS=40` the same command writes 1,005,497 bytes on the
Python route: the error repeats once per candidate.*

## ▶▶ L287. ALL THREE ROUTE-FLIP DEFECTS FIXED. 54 of 54 through the landed arm.

*`cutover-finisher`, 2026-09-01. **267 lib + 56 doctests, five configurations, zero
warnings.***

### 1. `--color always` — one hard-coded field, and the gates could not see it

**`stdout_capabilities()` set `forced_terminal: false`.** `cli.py` computes
`color = (value == "always") or (value == "auto" and sys.stdout.isatty())` and
hands it to `init_module_console` as `force_color`, which becomes Rich's
`force_terminal` — **and that value is exactly `flags.color`.** Now threaded rather
than recomputed. **The field already existed and `resolve_color` already honoured
it. Nothing was passing it.**

**⚠ Why no gate saw it: every coloured gate runs under a pty, where the forced flag
and the tty check happen to agree.** **Third held parameter nobody chose, today
alone** — after the empty-pool fixture and the `flags_from` recorder. **This
mission's defects do not hide in the code. They hide in what the harness holds
still.**

### ▶ The age pairs survived, and were checked the way L283 demanded

**Measured, not assumed: `1w` wears `#6b7076` = `search.age.month`, ONE BUCKET
OLDER THAN ITS LABEL, and `13m` wears `search.age.now`.** Extracted
`(colour, token)` **tuples** compared on the contract corpus **and a second pool** —
pairs, not escapes. **The colour fix touched the colour system and not the two
tables, so the deliberate misalignment stands and the seven are green for the right
reason.** *The single most likely way to lose a preserve-because-wrong item today,
and it did not happen.*

### 2. Not a misplaced newline — a missing wrap, and it was in the rehearsal too

**`print_warning` is a Rich `Console.print`, so the warning FOLDS at terminal
width.** Legacy reads `…continuing with\nboth filters…`; the arm emitted one long
line and the hint ran on.

**⚠ The arm was byte-identical to the driver** — diffed rather than read — **so the
defect was in the rehearsal, and the rehearsal's verification had only ever met a
warning short enough not to fold. The rehearsal had a held parameter of its own.**

***All three predicted hazards were right about the place and wrong about the
mechanism.*** Worth knowing about predictions.

### 3. `chrono` accepts a lowercase `z` that `fromisoformat` rejects

`parse_iso` rewrites only an uppercase `Z`, then hands the untouched string to
`DateTime::parse_from_rfc3339`, **which accepts lowercase.** CPython raises, so the
caller falls back to the filesystem clock. Guarded, reason at the site, in
`rust/pool_filter.rs` — **which stays `cutover-finisher`'s.** All four
`lowercase-z-*` cases reproduce their recorded bytes and exits, **including the two
that split the pair under `-ma` and `-ca`.** *Same class as `+96`: a Rust
convenience more permissive than CPython, silently.*

### 4. Width zero — four sites, not two

`search_run.rs` had the query-error site and **two undecidable sites** besides the
per-candidate one. **All four now go through `print_stderr_wrapped`, which carries
the guard.** `ch search zz -ma bogus` at `COLUMNS=40` is **byte-identical at 5,341
bytes.**

**⚠ ONE SITE LEFT, and it is `parity-finisher`'s: `search_output.rs:54`,
`print_error`** — the plain sink's per-candidate error, still a newline per file at
width 0, 21 against Python's 0. **It is the last thing holding `invalid-date` at
`COLUMNS='0'` red. Everything else in the 72-case sweep is green.**

### The route differential through production `main.rs`: 54 of 54, 0 unstable

**Against the frozen pool with colour off — the same figure the driver got, now
through the landed arm.** *That run used the binary from before these four fixes
and is being re-taken; a full native-against-legacy comparison over both fixture
corpora is running too.*

## ▶ SEQUENCING

**`search_output.rs:54` lands → tree quiet → `g5-runner` takes `run_all.sh` as
check 1 of G5.** **`contract-owner` stays closed at 89%; their suite runs inside
that.** **`g5-runner` released now for the `--verify` at 82 only**, which measures
the frozen reference set against `ch-legacy` and is unaffected by a moving tree.

## ▶ L288. 254 of 260 comparing the two ROUTES directly. The six are two rulings, not two defects.

*`cutover-finisher`. **Comparing native against `ch-legacy` rather than against the
recorded bytes sidesteps the suite's path normalisation and asks the question the
route flip actually asks.** Amendment corpus **33 of 33**; contract corpus 221 of
227.*

### Four: the unported-language fence divergence, living inside the contract corpus

`render-fence-web` carries `css`, `html`, `javascript`; `render-fence-data` carries
`diff`, `json`, `markdown`. **The promoted halves render identically —
`render-fence-shell` and `render-fence-python` are green at both widths — which is
what proves the divergence is the language list and not the renderer.** What
differs is `css`, `html`, `diff`, `markdown`: a Pygments lexer and no table, so
plain. **2 KB smaller, identical apart from missing foregrounds inside those
blocks.**

**These are `g4-fence-never-covered` living in the contract corpus.** They were
recorded before the ruling and still encode the pre-ruling answer.

**RULED: accepted. Not a new question.** L247 closed the list at seven on the
captain's approval. **Promoting four languages to turn a fixture green would reopen
a settled decision to satisfy a fixture.** *And `rebless_oracle.py` was correctly
not reached for — it now refuses, and a re-bless would have stamped the native
answer as the expectation.*

### Two: a warning's provenance decoration — and reproducing it means fabricating it

    legacy  {SEARCH_QUERY_SOURCE}:96: FutureWarning: Possible nested set at position 1
              regex = re.compile(pattern, flags)
    native  FutureWarning: Possible nested set at position 1

**The warning text, the stream and the ordering are all correct. What is absent is
CPython's `warnings` decoration** — path, line number, echoed source line. The
normaliser rewrites the path but keeps `:96:` and the source line literal, **so the
expectation genuinely demands them.**

**RULED: accepted, and reproduction is ruled OUT explicitly.** **Reproducing it
means emitting a path to `search_query.py:96` and echoing a line of Python that the
cutover deletes.** That is **the fabricated-traceback pattern this project already
fixed** — a prior team faked a broken-pipe traceback and baked build paths into the
binary, and removing it is one of the four repairs `main` has already made.
**Re-introducing it would be a regression against a defect fixed on purpose.**

**Ruled rather than escalated: one option is a known-bad pattern, so there is no
fork.** *A fork with one dominant option is not a decision.*

### ⚠ THE SHAPE BOTH TAKE: an asserted exact difference, never an expected red

**Neither becomes a red row.** *An expected red is indistinguishable from a
regression, and this desk spent two days removing the last one.*

**Both become asserted exact difference sets, the way `KNOWN_UNBUILT_BODIES`
works.** For the fences: the diff must be **exactly** the missing foregrounds
inside blocks tagged `css`, `html`, `diff`, `markdown` — **a geometry change, a
byte outside those blocks, or a fifth language joining all fail.** For the
warnings: the missing prefix specified, **so a change to the warning text itself
still fails.** **The reason written at the rows.**

**Both enter the deliberate-divergences table, which `final-change-log.md` is
assembled from. Six of 260, two classes, each with its reason and its bound. The
captain is told they exist, not asked.**

*Everything else is closed: `role-contradiction-warning` green, all four
`lowercase-z-*` green, every coloured case green, the age pairs holding.*

*`cutover-finisher`'s handoff was written whole and re-read whole, catching one
drifted line — the sixth time today. **It names what the seat did NOT do:**
`run_all.sh` unrun and why, the differential's re-take, the coloured-stderr gap
left alone.*

## ▶ L289. The launcher is measured: `.venv/bin/ch search` STILL hands to `ch-legacy`

*Measured with `contract-owner`'s behavioural test — the launcher alone with no
`ch-legacy` sibling:*

    exit=1, stdout 0 bytes, stderr 88 bytes
    Error: Cannot start the private ch legacy entry: No such file or directory (os error 2)

**The premise of L285 holds. The ratio-gate ruling stands: do not convert. The four
budgets time the outgoing route.**

### ⚠ The suite was already carrying the answer, quoted as a baseline and not read as evidence

**`test_search_journey_needs_no_private_legacy_entry` fails 260 of 260 with that
exact error string — the same fact, asserted 260 times, in a number already
reported to this desk as a known baseline.**

**The class: a figure quoted as background is not being read.** It is why the
measurement was worth ordering even though the answer was right — **an assertion
nobody has read as evidence is not evidence.**

### ▶ A hedge corrected in the direction of LESS doubt

**`parity-finisher`'s caveat said the synthetic pool cannot model the real cost
structure. They withdrew it as too pessimistic.** 4,000 synthetic sessions of
400 bytes cost about what 5,062 real ones of megabytes cost, **so the cost tracks
file count far more than file size**: the probe **models the dominant term** and
misses only a size-driven regression.

**Almost every correction on this mission has moved toward more caution. Moving
toward less, on evidence, is rarer and harder — and a hedge that overstates doubt
misleads exactly as much as one that understates it.**

### `search_output.rs:54` landed — the last width-zero site

`print_error` returns before printing at zero width, **with the reason at the site:
`eprintln!` adds a newline to an empty string, so the cost is one line per
candidate rather than one line.**

| case | native | python |
| --- | --- | --- |
| `search zz -ma bogus` @ `COLUMNS=0` | exit 1, **0 bytes** | exit 1, 0 bytes |
| `search zz -d /nope` @ `COLUMNS=0` | exit 1, **0 bytes** | exit 1, 0 bytes |
| `search zz -d /nope` @ `COLUMNS=40` | 50 bytes | 50 bytes, **byte-identical** |

**Five configurations green, 267 lib + 56 doctests, zero failures. `search_run.rs`
untouched by this seat.**

**`parity-finisher`'s seat is closed.** Ledger: F1; the C0 set re-derived 20 → 23;
F16; F17; the wrap-oracle gate over both copies; the backreference sweep as a
measured negative; `codecs.rs:1071` narrowed from three sites to one; both
`terminal.rs` width-zero divergences; `search_output.rs:54`; the `codex.rs`
duplicate deleted; **and an admissibility instrument that disproved the plan it was
built to serve.** **Three defects nobody had listed, all changing search results.**

**⚠ The tree is NOT yet quiet: `cutover-finisher` is still building the two
asserted-difference sets. `g5-runner` waits on them.**

## ⚠⚠ L290. CHECK 3 IS UNSATISFIABLE — 21 of 82 frozen answers can never match

*`g5-runner`, `--verify` at 82, taken 2026-09-01T14:16:59Z–14:17:19Z. Oracle route
digest `sha256:dd6ab701…` UNCHANGED; reference identity `22236c087af33dea` is the
stored one exactly.*

**⚠ Raw result 75 of 82 drifted. Do not act on that number — the oracle has not
drifted at all.** After pinning two instrument variables, **61 are byte-identical
and the remaining 21 differ ONLY by a per-run temp path. Not one entry differs for
any behavioural reason.**

**This run compares the Python reference against ITSELF. It says nothing about the
Rust route.** Baseline integrity only.

**The 75 decompose 54 + 21, no remainder.**

**Cause 1 — 54 entries, ORDERING, not drift.** Same bytes, same lines, two panels
swapped. **`freeze_references.py` copies the fixture home and never applies
`MTIMES.json`, which the contract suite does apply.** Fixture files carry restamped
mtimes of 2027-01-15; `seed_width_probe` writes with a wall-clock mtime and no
stamp, so `sort_by_modified` ranks it differently than on 2026-08-29. **A held
parameter nobody chose, living in a helper — the `run_at_width` `DEVNULL` shape
again.** *Checked for flapping before concluding: 12 fresh runs, 1 distinct output.
**It flipped once; it does not flap.***

**Cause 2 — 21 entries, and this is the finding. A random per-run path is frozen
into the bytes.** Every stderr entry embeds the `tempfile.mkdtemp()` directory —
`/var/folders/…/T/tmpv_upkrod/home/.claude/projec`. **Freeze and verify are
separate runs, so those 21 cannot match on any fresh run, today or ever.**
**`stderr/no-match-filtered` is the control proving the mechanism:** it
short-circuits on `-p codex`, never reaches the erroring file, prints no path, and
matches. *A control that explains why the others fail is worth more than the
failures.*

**⚠ So check 3 — the runbook's own load-bearing check — is NOT STALE, IT IS
UNSATISFIABLE. It cannot return 0 drifted at 82, for a reason unrelated to the
port.**

### RULED: fix the instrument and re-freeze, before the flip. Four constraints.

**The freeze exists so the oracle's answers survive its deletion. 21 of 82
currently cannot, and the deletion slice is downstream. Decision 6 arriving early:
cheap while `ch-legacy` is alive, impossible afterwards.**

**Given to `g5-runner`, and the line is stated rather than papered over:**
**`g5-runbook.md` is the specification of what counts as proof and they may not
edit it; `freeze_references.py` is an instrument that records answers and they
may. You may make the instrument capable of recording. You may not make a record
agree.**

1. **Instrument only, never records.** Apply `MTIMES.json`, stamp the probe
   deterministically, normalise the temp root in **both** freeze and verify.
   **Nothing is re-frozen because it disagrees.**
2. **Prove the normalisation is not inert** — a path difference **outside** the
   temp root must still fail, demonstrated. **A normaliser that swallows a real
   divergence is worse than 21 unsatisfiable entries, because it fails silently
   instead of loudly.**
3. **Re-freeze from `ch-legacy` with the oracle route digest recorded** — not from
   the built launcher. *`rebless_oracle.py` refuses for this reason; the same
   reasoning binds here.*
4. **Now.**

### ⚠ Open, and asked of `reviewer-profiler`: how did check 3 ever pass at 76?

**Only six entries were added since 76, so at least fifteen of the twenty-one
should have been present and failing then.** The 76-entry file is unrecoverable.
**Either the runbook's arithmetic is wrong, or that recorded PASS was not a fresh
verify.** **An unreal PASS in the record is worth more to correct than anything
else that seat's remaining context could buy** — and *"I do not remember"* is an
acceptable answer, where a reconstruction offered as memory is not.

### L291. The seventh whole re-read — and the mechanism, finally stated

**`parity-finisher` found six drifts, including a table with two stacked header
rows** left by an edit that replaced a body and not a head. Also: a stale tree
digest and three stale per-file digests, "264 lib tests" against 267, a status line
naming a decision already ruled, **a bullet saying `reviewer-profiler` had been
told to convert the budgets and had not — true when written, stopped being true,
L264 decaying inside the document that records L264** — and a heading saying "two
follow-ups, both done" above five.

**⚠ THE MECHANISM, in the author's own words: *"I had not seen it because I only
ever re-read the paragraph I was changing."*** **A scoped edit reads a scoped
window, so anything that decays outside the window is invisible no matter how many
times the document is touched.** That is why a visibly broken table survived
several passes by an attentive author. **Seven whole re-reads, six found
something.**

*Also corrected: `COLUMNS=0` took **seven sites across three files**, not three;
and the ownership section now separates what was **granted** from what was actually
**edited**, because `cells.rs` was granted and never needed — an undifferentiated
list reads as a claim about the code.*

**`parity-finisher` idle. Tree `5cfd1e8e7f4b`, 267 lib + 56 doctests, five
configurations, all 13 shell suites green. `RESUME.md` 500 lines, internally
consistent at that digest — and it says so, because it will not stay that way on
its own.**

## ▶ L292. THE PASS WAS REAL — taken at 68, not 76. The 21 were CREATED at 82.

*`reviewer-profiler`, reconstructed from the code rather than from memory, and
checkable.*

1. **At 68**, stderr entries held only the no-match hint — no path. **The verify
   against install `22236c08` returned 0 drifted, 0 new. Real and fresh.**
2. **At 76** (the `--color` matrix) **no full verify was run** — only a
   distinctness check on the new entries.
3. **At 82** the errno shapes were added, and with them a **directory** at
   `.claude/projects/alpha/99999….jsonl` to provoke `[Errno 21]`.
   **`freeze_references.py:130` creates it BEFORE the stderr loops at 148 and
   152**, so from that freeze onward **every** stderr capture carries
   `Error processing conversation file /var/folders/…/tmpXXXX/…`.

**So nothing was missed at 76. The failures were created at 82, by a side effect of
the author's own addition** — and `{HOME}` was normalised **only for the six errno
entries they were thinking about. The twenty-one were collateral.**

**⚠ "Taken at 76" was itself a correction, and it was wrong. Fifth instance of the
decay, inside a fix for the decay.**

### Fixed

    before   82 stored, 21 raw temp paths, 21 permanently unverifiable
    after    82 stored, 0 drifted, 0 new on a fresh run with a new temp home
             0 raw temp paths, 27 entries carrying {HOME}

**A *fresh* verify — separate process, separate `mkdtemp`.** The baseline now does
what a frozen reference is for.

### ⚠⚠ AN ARTIFACT THAT VALIDATES AGAINST ITSELF IS NOT VALIDATED

**Freeze and verify share a temp home *within* a run and differ *between* runs, so
the defect was invisible in the run that created it.** **The sharpest form of the
corpus-blindness class this mission has produced.** It belongs beside
`held-parameters.md`'s vocabulary bound.

**And the rule that catches it had been written one edit earlier, by the same
hand** — *recorded raw it would be the one row nobody could re-derive* — **and
applied to the six entries in view, not to the twenty-one the same change had just
broken.**

**That is L291's mechanism in a different medium: a scoped edit attends to a scoped
window, and what the change breaks OUTSIDE that window is invisible. Two seats
found the same mechanism today, one in a document and one in an instrument.**

### The split, re-ruled deliberately

**`reviewer-profiler` fixed the instrument and keeps the runbook edit** — they wrote
it, they have no stake in the port's outcome, **and it keeps the runner separate
from what the runner verifies against**, which is why the grant to `g5-runner`
carried four constraints at all.

**Two constraints become `g5-runner`'s to CHECK rather than the author's to
ASSERT:** an independent fresh verify from a separate process, **and proof that the
normalisation is not inert — a path difference outside the temp root must still
fail, demonstrated.** *That second one was not reported, and it is the one that
matters: a normaliser that swallows a real divergence fails silently instead of
loudly.*

### L293. The freeze fix is recorded with its mechanism above it; `reviewer-profiler` closed

**Runbook 148 lines, desk symlink identical.** Check 3 records the PASS at **68**,
names the earlier "76" as the fifth decay instance, and carries the re-take at 82
on 2026-09-01 — **fresh process, fresh temp home, 0 drifted, 0 new.**

**The mechanism is stated ABOVE the fix, because a successor extending the set will
hit it otherwise:** the `[Errno 21]` shapes need a **directory** where a session
file is expected, `freeze_references.py` creates it before the stderr loops, **so
every stderr capture from that freeze on named a per-run path.** Six normalised,
twenty-one not.

**The standing rule it produced: any future entry naming a filesystem path must be
normalised, and the check is a verify from a SEPARATE PROCESS — not a second call
in the same one.**

### ⚠ What to suspect if the non-inertness check comes back green too easily

**From the author of the fix, and now `g5-runner`'s to test: suspect that the
`{HOME}` replacement is eating more than the temp root.**

**The failure mode is a normaliser whose reach is too WIDE, not one that fails to
catch.** **A green from an over-wide normaliser and a green from a correct one are
indistinguishable unless someone goes looking.** So the failing case must differ in
a path **genuinely outside** what `{HOME}` should cover, and must still fail.

*`reviewer-profiler` named the two checks as the ones they could not honestly make
about their own fix. That sentence is the answer to why this desk kept a reviewer
idle rather than converting them.*

**Seat closed for good.** Ledger: G5's runbook, `held-parameters.md`'s six bounds,
four contradictions found in their own work, and the frozen reference set — **twice,
the second time actually verifiable.**

## ▶ L294. The asserted-difference gate is landed and falsified both ways

**`tests/test_deliberate_divergences.py`, eleven tests green.** The set is exact and
each divergence must still differ.

**The fence four are pinned three ways:** text-identical with styling stripped;
native styles a **subset** of legacy's; **and every legacy-only style carrying
Monokai's fence background `48;2;39;40;34`** — *that third clause is what confines
the difference to code blocks rather than merely describing it.* **The controls
`render-fence-shell` and `render-fence-python` must be byte-identical INCLUDING
COLOUR at both widths.** The warning pair is spelled out as prefix + native stderr
verbatim + echoed source line, **so a change to the warning text still fails.**

**Falsified both ways, and both were RUN rather than asserted.** Adding a
non-diverging case dies on *"an inert allowance is worse than none"*; removing a
diverging one dies on the exactness sweep, **naming `fb-posix-class-bare-warning`
as having joined.**

## ⚠⚠ L295. A `-ca` FILTER RETURNS A SESSION NATIVELY THAT LEGACY EXCLUDES

*Found by `cutover-finisher` sweeping `preserve-because-wrong.md` against the live
route — nobody asked for that sweep, and it only pays once the route has flipped.*

**`ch search . -ca 2026-08-25 -ll` returns a session the legacy route excludes.**
`first_timestamp` is what moves. **Two causes, both a Rust parser stricter than
CPython's:**

1. **`NaN`.** A session's first line ends `"score":NaN`. **`json.loads` accepts it;
   `serde_json` rejects it**, so `pool_filter::entry_timestamp` skips line 1 and
   takes line 2 — created renders `16:01` against legacy's `16:00`.
2. **`0x1C`.** A session begins with a C0 file separator. **`inventory::
   trim_python_byte_whitespace` strips only `\t \n \v \f \r` and space, not
   `0x1C`–`0x1F`**, so the line never parses and the probe falls through to
   filesystem birthtime — **rendering today's date where legacy renders
   2026-08-20.**

**Python's `_find_first_timestamp` is `line.strip()` then `json.loads(line)` — both
halves of the difference are in that one line.**

### ⚠ THE CORPUS HAS THE INPUTS AND NOT THE ASSERTION

**Both sessions were built for exactly these cases** — one is named *"Rendernan
first line"*, the other *"Renderctrl separator line"* — **and both passed the
260-case comparison, because no recorded case renders their metadata block.**

**The fixtures exist. The question was never asked of them.** **A new member of the
blind-corpus family and the most uncomfortable one: not a corpus that lacks the
case, but one that contains it deliberately and never interrogates it.**

### Routing

**`parity-finisher` woken for three:** make `session::detection_lenient`
`pub(crate)` (one word — **duplicating twenty lines of NaN scanning would be the
wrong shape, and half-fixing only `0x1C` would be worse**); **audit
`inventory::trim_python_byte_whitespace` as a CLASS** — *the C0 set escaping its
enumeration a third time, and this time by **file** rather than by search shape,
since `inventory.rs` was never in the scoped three*; and **`ch search a -r` emitting
`<subagent-task>` at column zero where legacy indents two spaces** — **`-r` is a
public `ch search` shape, so it is on the route and in the cone.**

**`cutover-finisher` lands the `pool_filter.rs` half once the helper is reachable,
and continues the `preserve-because-wrong` sweep — twelve items, at least one of
which was being asserted by nothing.**

*Previous route differential through the landed arm: 0 mismatches, 0 unstable,
54 of 54. Re-take running. Tree `bc090bf57d02`, 267 lib + 56 doctests.*

## ⚠⚠ L296. NOBODY CAN SAY WHICH INSTRUMENT PRODUCED THE FROZEN RECORD

*`g5-runner`, disclosing rather than proceeding.*

**1. The instrument on disk is `g5-runner`'s code.** They had patched
`freeze_references.py` before the stand-down reached them. **So either
`reviewer-profiler`'s version is not what is on disk, or theirs landed on top of
it. Either way the author/verifier split this desk built is not in force on that
file, and they said so instead of quietly verifying their own work.** *Their first
check reported the file as the other seat's; that was a line-based grep missing a
phrase wrapped across two lines, and they corrected it before drawing any
conclusion from it.*

**2. The artifact was not produced by the instrument on disk.**
`frozen_reference.json` carries `oracle_state: "HEAD 8cb4c5f, oracle route digest
…"` — **the old hardcoded constant, which the on-disk version deletes entirely.**
**So a third version produced it, and that version is gone. The artifact and the
instrument do not correspond, so checking one does not validate the other.**

### ▶ THE DURABLE CURE: the artifact records the digest of the instrument that made it

**Decision 3's lesson arriving at a different artifact — a revision alone is not
enough.** **Whatever is frozen next carries its instrument's digest, so no reader
can ever be in this position again.** *Name the cure, not the instance.*

### ⚠ Constraint 3 named the wrong oracle, and that is `search-firstmate`'s error

**`22236c087af33dea` is the STORED `reference_route_identity` — a uv tool install
at `~/.local/share/uv/tools/chats/bin/ch`, OUTSIDE the working tree, unaffected by
this cutover, and pinned on purpose.** **`.venv/bin/ch-legacy` (`c1821a3a86ee9a88`)
lives IN the tree and is what the deletion slice removes.**

**So "re-freeze from `ch-legacy`, not from anything native" may have pointed at the
LESS stable of the two.** Written thinking of the built launcher, without
distinguishing the pinned install from it.

**RULED: change nothing until one measurement lands.** Does `~/.local/bin/ch` serve
search natively, or hand it to a Python entry? **`contract-owner`'s behavioural
test — a copy alone with no legacy sibling.** **If it hands off, it is the better
oracle and the record is reached correctly. If it serves natively, the frozen
record of the Python authority is not a record of Python at all — which is far
larger than a provenance problem.**

### Constraint 2 is MET and accepted

*Fresh separate process, fresh `mkdtemp`, 2026-09-01T14:32:38Z–14:32:57Z:
**82 stored, 0 drifted, 0 new**; 27 entries carry `{HOME}`, 0 carry a raw temp
path; all three reported figures reproduce exactly.*

**Five cases, including the over-reach one that was warned about:**

- the ephemeral home hidden across two temp roots → agrees. **PASS**
- a path difference **outside** the home → still fails. **PASS**
- a path difference **under** the home but past the prefix → still fails. **PASS**
  *(the eats-too-much case)*
- a home prefix cut by render width → **raises rather than freezing an
  unre-derivable entry.** **PASS**
- `record()` with no home → `TypeError`. **PASS**

**And the reach is structurally bounded, not merely tested: the replacement is one
long unique `mkdtemp` path, so it cannot span anything a shorter or commoner string
would.** *The difference between a normaliser that passes tests and one that cannot
over-reach.*

## ▶ L297. `preserve-because-wrong.md` swept item by item against the live route

*`probes/preserve_because_wrong_sweep.py` — a session pool per item, both binaries
compared byte for byte on stdout, stderr and exit status. **The first time any list
on this mission has been swept against the live route.***

| Item | Verdict |
| --- | --- |
| 1 `collapse_home` prefix, not boundary | **same** — both render `directory: ~X/dev/chats` |
| 3 `elide_to_width` counts code points | **same** at three widths |
| 4 `truncate_middle` normalization-sensitive | **same** over 400 NFD characters under `--short` |
| 5 30-day months, 365-day years | **same** across 359/360/364/365/366 days |
| 7 a DST fold collapses two instants | **same**, rendering and `-ma`, under `TZ=Asia/Jerusalem` |
| 8 one trailing space on the last line | **same** across all three shapes, fenced and raw |

**With 2, 9, 11 and 12 confirmed separately and 6 the one that diverged and is
fixed: eleven of twelve.**

### ⚠ Every verdict reports the bytes behind it — and that caught the probe itself

***"Both printed nothing" and "both printed the same wrong-on-purpose answer" look
identical in a pass column.***

**Probe 3 agreed on its first run while proving nothing.** `elide_to_width` is
reached **only** from the coloured list row and panel title, and **plain list mode
never elides** — so it was comparing two **un-elided** outputs. It now asserts that
an ellipsis actually appeared, and it does.

**The blind-corpus shape arriving inside the instrument built to hunt it, found by
requiring the instrument to show its evidence rather than its verdict.**

### ⚠ Item 10 is UNTESTED, not confirmed — and it is not out of reach

**`--color never` still colours stderr when stderr is a tty. Nobody has measured it
since the arm landed, and the coloured route is exactly what changed.**

**`script` failing to allocate a pty is a fact about `script`, not about this
environment.** **This mission owns `probes/pty_differential.py` and its
`pty_harness`; every coloured G4 gate runs under a pty, and a 135-case stderr
corpus was measured through that machinery.** **Ruled: use the instrument that
exists.**

**The one thing to establish first: can the harness put a tty on *stderr*
specifically, or only on stdout?** If only stdout, that is a measured limitation
and escalates. **A "cannot" resting on one tool having failed is not yet a
measurement** — *"too expensive" and "impossible" are both claims about a mechanism
and must be measured against the mechanism.*

*`session::detection_lenient` is still private; `parity-finisher` holds that change
among three. The `pool_filter.rs` half is two lines with a reproduction in hand.
The re-taken route differential is still running.*

## ▶ L298. THE REFERENCE IS VINDICATED — `~/.local/bin/ch` hands search to Python

*`g5-runner`. The binary copied alone into an empty directory, no `ch-legacy`
sibling, `env -i` with `PATH=/nonexistent`. 3,039,008 bytes, `22236c087af33dea`.*

    search "needle five" --color always --no-paging --no-metadata
      exit 1, stdout 0 bytes
      stderr: Cannot start the private ch legacy entry: No such file or directory (os error 2)
    info --help   (the control)
      exit 1, same error

**Search cannot run without the Python entry, so the frozen bytes ARE the Python
authority's.** **And the structural evidence agrees: the binary links only
libiconv, CoreFoundation and libSystem and carries ZERO undefined `Py_` symbols —
it holds no interpreter, so exec'ing the sibling is the only way it can answer at
all.** *A behavioural test and a structural one agreeing is worth more than
either.*

**Constraint 3 named the less stable of the two.** The uv tool install is outside
the working tree and unaffected by the cutover; **`.venv/bin/ch-legacy` reaches
`src/chats/` through the editable install and is what the deletion slice removes.**
**`22236c08` is the better oracle. THE FREEZE STANDS.**

### RULED: provenance closes in the artifact, not in a different pair of hands

**One re-freeze from `22236c08`, stamping the instrument's digest — and the
disclosure goes IN the artifact.**

**`reviewer-profiler` is not woken a fourth time to launder authorship.** **The
record being made is of *Python's* answers, and `g5-runner` has no stake in those.
The stake this desk guards is in the Rust port's answers, and no seat that has one
is near this file.** The non-inertness proof already covers how the instrument
could be wrong, including over-reach.

**The artifact records: the instrument's digest, the reference identity, the oracle
route digest, and a line saying the instrument was written by the seat that
verified it.** *An artefact carries its own status where it is read.* **A successor
re-verifies without asking anyone — the property that was missing — and can tell
one instrument from another without asking either author. That retires the class,
not the instance.**

### ⚠ CHECK 10'S "BEFORE" STATE IS NOW RECORDED, and it is a baseline not a defect

**Both halves fail identically today — same error, same exit 1 — because
pre-cutover both routes are Python.** **After the flip, search must render while
`info --help` still fails with that exact string.** **So today's identical pair is
what the post-cutover run is measured against.** *The artifact tested is the Aug 28
install, not the Sep 1 build that carries the arm.*

***A control that cannot discriminate yet is worth recording precisely because it
will.*** **Goes where check 10 is read, not only in a report.**

## ▶ L299. The re-taken differential: 0 mismatches, 0 unstable, 54 of 54

**Current binary, frozen pool, colour off, twenty-seven shapes at two widths,
through production `main.rs` after all four route-flip fixes.** Same figure as the
pre-fix run **and** as `engine-and-codex`'s through the driver. **Three
instruments, three runs, one number.**

## ⚠⚠ L300. ITEM 10 MEASURED FOR THE FIRST TIME — all eight shapes diverge

*`probes/stderr_tty_colour.py` puts a pty on **stderr** and a pipe on stdout — the
shape the item is actually about. **`pty.openpty()` works here; `script` failing
was a fact about `script`.***

| shape | legacy | native |
| --- | --- | --- |
| no-results hint — bare, `never`, `always`, `auto` | 95 B, coloured | 39 B, bare |
| role-contradiction warning — bare, `never` | 207 B, coloured | bare |
| invalid-date error — bare, `never` | 363 B, coloured | bare |

**Legacy colours all three stderr consoles whenever stderr is a tty, `--color
never` INCLUDED** — the colour choice reaches stdout's console and none of the
stderr ones. The hint arrives as `search.empty` **plus Rich's `ReprHighlighter`
painting the quoted term green**, so closing it needs the theme style *and* the
repr highlighter — **which `search_views`'s `COMBINED_PATTERN` already carries.**

**⚠ It is bigger than the sinks' comment implies: not one sink, but all three
stderr consoles under every colour setting. The comment understates it and the
record goes where the comment is.**

### ⚠ WHY IT WAS NEVER ASKED: every coloured gate on this mission puts its pty on STDOUT

**A held parameter nobody chose, in the harness, for the fourth time today — and
this one hid an entire SURFACE rather than a single case.**

### RULED: capture the baseline NOW, unconditionally. Then open the slice.

**The capture is not contingent on the fix.** Legacy's coloured stderr can only be
captured while `ch-legacy` lives and the deletion slice is downstream. **Even if we
shipped the divergence the baseline would still have to be taken today.**
**Decision 6, third arrival in two days.** *If the seat runs low: capture the
baseline and hand off — the capture is the irreversible half.*

**Then open it, because item 10 is a preserve-because-wrong item.** The behaviour is
**legacy colouring stderr when explicitly told not to.** **Leaving it unfixed does
not preserve a wrong behaviour — it silently DROPS one**, which is the exact
failure the list exists to prevent, **and the second time today one of its items
has sat in the path of a decision.** Three call sites; the machinery exists.

### ⚠ The correction is worth more than the finding

**Item 10 was reported unreachable on the strength of one tool failing — a limit of
one's instruments stated as a property of the world.** **Second time this desk has
caught that shape**, after the disk-versus-filesystem argument that met `cp -Rc` at
44 seconds. ***"Too expensive" and "impossible" are both claims about a mechanism
and must be measured against the mechanism.***

**Eleven confirmed identical, one fixed, one measured and diverging. No item on
`preserve-because-wrong.md` is now untested — the first time this mission can say
that about any list.**

## ▶ L301. THE FREEZE IS RE-TAKEN AND SELF-DESCRIBING — and not one answer changed

*`g5-runner`, 2026-09-01T14:36:58Z–14:37:18Z. 82 outputs, 104,179 bytes.*

**⚠ Entries whose recorded answer changed: 0. None added, none removed.** **So the
previous artifact's CONTENT was already right and only its provenance was
unknowable. The repair was provenance-only — the cleanest possible evidence that
nothing was quietly re-frozen into agreement.** *That outcome could not have been
arranged, only failed to be achieved.*

**What the artifact now carries:**

- `instrument_digest: sha256:71aee37e…4724fb`
- **`instrument_digest_recipe` — sha256 over name+bytes of `freeze_references.py`,
  `pty_harness.py`, `width_probe_fixture.py`, `generate_cell_oracle.py`. All four,
  because a digest of the entry script alone would miss a change in the pty capture
  or in the probe's own generator.** *Decision 3's reasoning — digest the whole
  route, not `src/` — applied by someone who understood why it was made rather than
  copying its shape.*
- `oracle_state`, `source_digest`, `source_digest_recipe` — **derived at freeze
  time, not transcribed. The hardcoded constant is deleted.**
- `reference_route_identity: 22236c087af33dea`
- **`provenance` — the disclosure IN the artifact:** the instrument was written by
  the seat that verified it; the record is of Python's answers and that seat has no
  stake in them; the way it could be wrong is normalisation reaching too far, proved
  against separately; **re-verify from a separate process with a fresh temp home,
  never a second call inside one.**

**Verified three ways after the re-freeze.** A fresh separate process with a fresh
`mkdtemp` at 14:37:41Z — **82 stored, 0 drifted, 0 new.** **The instrument digest
re-derived BY HAND outside the instrument, matching exactly — so the stamp is
checkable by a stranger rather than a self-assertion, which is the part most
implementations of this idea get wrong.** And 0 raw temp paths, 27 entries carrying
`{HOME}`.

### Check 10's baseline promoted verbatim — and the edge of the runbook rule

**`g5-runner` declined to edit `g5-runbook.md` and wrote a drop-in block instead,
leaving the edge to `search-firstmate`. Ruled: the rule bars changing WHAT COUNTS
AS PROOF. A record of what check 10 measured before the flip is EVIDENCE, not
criteria.** Promoted verbatim; runbook now 202 lines; a placement line states that
no pass condition was changed to admit it.

***Writing the block phrased for the runbook rather than for the report is what
made a verbatim promotion possible*** — a report pasted into a specification would
have needed rewriting by someone who had not measured it.

**It carries the identical-pair baseline, the Aug 28 versus Sep 1 artifact
distinction, the two-tests-agree structural evidence, and the one thing that would
break the reading: a piped `--full` landing in `PlainSink` and proving nothing.**

### ⚠ One field left: `revision` is the only one nobody re-derives

**Carried forward as a foreign stamp from `contract-owner`'s re-bless path.** It
matches `HEAD` today — **exactly how the field just deleted behaved for a week.**

**Ruled: derive it or delete it. Measure whether anything reads it; if nothing
does, delete.** *Removing the field beats deriving it, and an artifact with one
un-derived field reads as an oversight to the next person, who will assume the
others are un-derived too.*

## ▶ L302. `revision` deleted, not derived — and it exposed a two-writer conflict

*`g5-runner`, measured rather than assumed.*

**Nothing reads it.** `slice-reviewer/probes/responsiveness.py` reads `["entries"]`
only. **`test_search_command_contract.py:174` reads `ORACLE['revision']` — but
`ORACLE = CORPORA[0].oracle`, which is `tests/data/search-contract-fixtures/
ORACLE.json`, a DIFFERENT ARTIFACT.** **Two files identical from a grep: a sweep
matching on the field name would have concluded the field was read.** *Naming the
subject is what made the measurement right.* **The only program touching the field
is a writer** — `rebless_oracle.py:51`'s `_stamp_foreign_records`.

**So: deleted, not derived — and the carry-forward deleted with it**, because
removing the value while keeping the mechanism puts it back on the next run. **The
instrument now derives every field it writes, and the artifact has no field a
reader cannot re-derive.**

**Re-frozen and re-verified twice more.** **Answers changed across all three
re-freezes: 0. The set has never moved.** Fresh separate process: 82 stored, 0
drifted, 0 new, 0 raw temp paths. **`instrument_digest` moved `71aee37e…` →
`ddcef743…` because the instrument was edited — the stamp proving itself LIVE
rather than transcribed** — re-derived by hand outside the instrument and matching.

### ⚠ RULED: `rebless_oracle.py` stops stamping this file, and `g5-runner` makes the change

**`_stamp_foreign_records` writes `source_digest`, `source_digest_recipe` and
`revision`; the freeze instrument now derives the first two and drops the third.
Two writers disagree about the same fields.**

**⚠ The hazard is LIVE, not latent.** `rebless_oracle.py` refuses when the launcher
serves search natively — **but the pinned `~/.local/bin/ch` hands off to Python, so
pointed at the reference the refusal does not fire.**

**Why it is `g5-runner`'s despite the runbook rule:** that rule bars them from **the
specification of the proof** and from **making a record agree**. **This is a tool
that would CORRUPT the artifact, and removing a writer that downgrades a stamp is
unambiguously strengthening.** `contract-owner` is closed at 89% and their `work/`
tool's reason has been removed rather than worked around.

**⚠ THE DIRECTION IS THE ARGUMENT, NOT THE COLLISION.** *Stamping a frozen artifact
without re-recording its entries is decision 3's rejected restamp exactly* — **a new
digest on an artifact previously carrying a blind one asserts the oracle has not
moved since generation.** **The artifact now carries a stamp derived AT generation,
the strong form. A re-bless would replace it with an asserted-afterwards one — a
downgrade, not a refresh.** That sentence goes into the artifact's `provenance`, so
a reader who finds the two writers knows which one was right.

**Check 3 is closed: reproducible, provenanced, self-describing, independently
re-derivable, and its answers never moved across three re-freezes.**

## ▶ L303. CHECK 3 IS CLOSED — and the shape of the whole day is three deletions

*`g5-runner`, re-frozen 14:43:26Z, verified from a fresh process 14:43:47Z.*

**82 stored, 0 drifted, 0 new. Answers changed against the first snapshot: 0. Four
re-freezes, four instrument versions, the set has never moved.** 0 raw temp paths.
**8 fields, every one derived by the thing that wrote it.** `instrument_digest`
`27f4c60d…`, **moved again because the instrument was edited again, and re-derived
by hand outside it — three separate demonstrations that the stamp tracks the code
rather than being transcribed.** *That property is what makes the artifact
checkable by someone who trusts none of us.*

### The writer, removed inside a narrow grant

**`FOREIGN_RECORDS` held `frozen_reference.json` as its ONLY member, so removing it
empties the tuple.** **Emptied rather than deleted — staying inside the grant on
someone else's file — and the emptiness documented as deliberate**, dated,
attributed, with the reason, the decision-3 argument, **the live-hazard note that
`_refuse_if_the_launcher_is_native` does not fire for the pinned launcher, and the
condition under which a member should be added back: it holds recorded Python
answers and cannot stamp itself.**

***An undocumented empty tuple would have read as exactly the oversight that was
fixed one field over, in the same hour.*** **Verified by importing the module, not
by reading it; one modified block confirmed by structured diff.**

### The provenance now names which writer was right

*Every stamp here is derived at generation; `rebless_oracle.py` used to add them
afterwards and no longer does; stamping a frozen artifact without re-recording its
entries asserts the oracle has not moved since generation, which a later stamp
cannot support; derived-at-generation is the strong form and asserted-afterwards is
a downgrade, not a refresh;* **"if you find both writers in the history, this one
was right."**

## ⚠⚠ L304. THE SHAPE OF THE DAY, IN ONE MEASUREMENT

**"The aggregate said 75 of 82 had drifted and the truth was that nothing had."**

**Everything real came from dumping the instances and reading them** — 22c, arriving
at the largest aggregate on the mission.

**And every fix since removed a mechanism rather than adding one: the defaulted
parameter, the carry-forward, and the second writer. Three deletions, no new
guards — and the artifact ends up saying more about itself than when it had more
code behind it.**

***That is this desk's engineering argument arriving as a measured outcome rather
than a principle.***

## ⚠ L305. THE C0 CLASS HAS FOUR SITES, THREE ORACLES AND THREE DIFFERENT RIGHT ANSWERS

*`parity-finisher`, audited as a class rather than fixed as a pattern.*

| site | oracle | diverges on |
| --- | --- | --- |
| `pool_filter::first_in_band_timestamp` | `_find_first_timestamp` — **pure CPython** | the trim **and** the parse |
| `inventory::cwd_from_path` | `extract_cwd_from_jsonl_file` — same pair | the trim **and** the parse |
| `inventory::last_timestamp` | **the accelerator**, not pure Python | **the parse only** |
| `python_extension::timestamp_from_line` | **it IS the oracle** | **nothing — do not touch** |

**⚠ "Make them all use `python_strip`" would be WRONG at one site.**
`get_jsonl_last_timestamp` calls the Rust `find_last_jsonl_timestamp`, **so on that
path the trim is already Rust's and only the parse is Python's. Changing
`python_extension`'s trim would MOVE the oracle rather than match it.**

**Four measured mismatches, two of them previously unreported:**

    nan-first-line       first_timestamp  python 2026-08-20  native 2026-08-27
    ctrl-separator-line  first_timestamp  python 2026-08-20  native 2026-09-01 (birthtime)
    ctrl-separator-line  cwd              python /tmp/...    native None
    ctrl-separator-line  last_timestamp   python …:45.233497  native …:45

**⚠⚠ THE `cwd` ROW BELOW IS RETRACTED — SEE L310. `cwd_from_path` HAS NO CALLERS;
`-d` does NOT silently exclude. Original text kept for its reasoning:**

**⚠ `cwd_from_path` returning `None` means `-d` SILENTLY EXCLUDES such a session on
the native route — a second public filter, found only because all four sites were
measured rather than the two that were named.**

**And a fifth divergence, not C0 at all: `filesystem_mtime` and
`filesystem_birthtime` build with `timestamp_opt(seconds, 0)`, dropping sub-second
precision where `datetime.fromtimestamp(st_mtime)` keeps microseconds. It changes
newest-first ordering between two files written in the same second** — the ordering
this product is built on.

**⚠ AND THE TRIM GAP IS WIDER THAN U+001C–001F. Python strips the DECODED line with
`str.strip()`, so a byte-level ASCII trim misses every non-ASCII space — U+00A0,
U+2028, U+3000.** **Fixing only the C0 range would leave the class half-closed and
looking finished, which is worse than leaving it open.**

**Routed: `parity-finisher` takes `inventory.rs` entirely and does not touch
`python_extension.rs`. `cutover-finisher` keeps `pool_filter.rs`.**

### L306. `-r` indentation: the false comment sent both of us to the wrong file

**`raw_transcript.rs` has ZERO mentions of `subagent-task`.** The renderer is
`search_output::format_raw`, **whose doc comment already said "Agent blocks are
indented two spaces" — a comment describing the behaviour we WANTED rather than the
one we had. The code never did it.** L226's class, and it misdirected the routing.

Python's rule is `format_to_raw:585-586`: indent when the wrapper is `AGENT`, **and
only in the multi-message branch**, because `len(visible) == 1` returns first. Both
halves reproduced. **`ch search 'subagent-task' -r` byte-identical at 311,661
bytes.**

**`textwrap.indent` was two more instances of the class at once.** Its line
boundaries are Python's — `\v`, `\f`, U+001C–U+001E, U+0085, U+2028, U+2029 — and
its predicate is `not line.isspace()`, **whose set includes U+001C–U+001F. The two
sets are NOT the same set: U+001F is whitespace and not a boundary.**

**⚠ The gate caught the implementer's own backwards reasoning on its first run.**
*"`"".isspace()` is False so an empty line takes the prefix"* — **Python's predicate
runs on the line WITH its ending, and `"\n".isspace()` is true.** *The recorded
table said so immediately, which is the whole argument for transcribing CPython's
answers rather than deriving them.*

*Bound, measured: `ch search a -r` could not be verified live — at 62 MB **the
oracle differs from itself** between back-to-back runs, because three sessions
write to the pool and `a` matches everything. The frozen snapshot at
`/private/tmp/ch-pool-snapshot` exists for exactly this.*

## ▶ L307. The stderr-colour baseline is captured — the irreversible half is done

**`tests/data/stderr-colour/legacy-stderr-baseline.json`: 240 recorded answers, 120
carrying colour.** Six stderr shapes × four `--color` settings × **five terminal
tiers** × two widths, **pty on stderr, pipe on stdout.**

**The tier is in the matrix because `print_hint`'s grey is an RGB triple that
downgrades while `print_error`'s red is a palette index that never does.** The
width is in it because these messages fold.

**⚠ A companion assertion refuses a capture with fewer than 100 coloured cases or a
missing tier — because a recording taken through a pipe by mistake would look like
a corpus and prove the opposite of what it claims.** **The first attempt captured
nothing and said so:** an off-by-one in `parents[4]`, the `ch-legacy is gone`
assertion fired, **and the probe refused rather than writing 240 empty cases. That
is why it cost a minute.**

**The slice was mostly already built.** `search_views` carried `StderrConsole`,
`highlight_spans` — the measured subset of `ReprHighlighter` these messages reach —
and `render_stderr_message`. **Missing: a stderr capability resolver and five call
sites.** `--color` is deliberately not threaded into it and `forced_terminal:
false` says why at the site.

### ⚠⚠ L308. A TRUNCATED INSTRUMENT REPORTED A PLAUSIBLE NUMBER AND WAS BELIEVED

**`pytest … | tail -5` showed five `FAILED` lines. Read as 235 of 240 passing. The
true number was 72 failing.**

**Caught only by reconciliation** — a `-k` run showed thirty-two failures in **one
shape**, which could not be squared with five. **Believed for ten minutes; nothing
left the session on it.**

***The suspicion did not catch it. The arithmetic did.***

**The 72 are two things, not seventy-two.** **40 are `warning-posix-class`** — the
`FutureWarning` decoration already ruled against reproducing, where the baseline
demanded byte-equality the desk had already excused. **Now pinned in its COLOURED
form: the text must be present, legacy's must still carry `search_query.py:96:` and
the echoed source line, and the native MUST NOT START EMITTING THEM.** ***That is
better than what was ruled — `search-firstmate` said accept the difference; this
asserts the prohibition. A gap and a prohibition look identical until someone
"fixes" it.*** **32 are `error-invalid-date`** on one call site —
`search_output::print_error`, **routed to `parity-finisher`**, the same function as
the width-zero guard.

**And the defect the gate found in its author's own work is the whole finding one
level down: `terminal_width()` resolves dumbness from *stdout* while these consoles
are on *stderr*.** With stdout piped and stderr on a dumb pty, the native wrapped
at the pty's width where Rich returns 80 before consulting `COLUMNS` at all.
**A property read from the wrong stream, invisible until something put a tty on the
other one.**

### `first_timestamp` is closed

`detection_lenient` opened, the two lines landed. **`search . -l` is byte-identical
to legacy and `-ca` now agrees on the session it disagreed about.** **A third
divergence went with it: a decode failure was skipping a line where Python aborts
the whole probe.** 269 lib + 56 doctests, zero warnings.

## ▶▶ L309. RULED: THE PRESERVE-BECAUSE-WRONG SWEEP BECOMES A FROZEN GATE

**The exposure, named by `cutover-finisher`:** *"A gap and a prohibition look
identical in a passing test suite and behave completely differently a month later,
when someone reads a missing decoration as an unfinished port and helpfully adds
it."*

**⚠ The eleven other items on `preserve-because-wrong.md` are ACCEPTED DIFFERENCES
WITH NO PROHIBITION BEHIND THEM. The same exposure, eleven times over — and that is
what the sweep was really measuring.**

**The fix is one change, not eleven.** `probes/preserve_because_wrong_sweep.py`
**already asserts every prohibition** — it compares native to legacy byte for byte,
so a port that "improves" any item fails it. **What it lacks is not assertions. It
is a schedule. A probe run once protects nothing after the run; a gate protects
until someone deletes it.**

**Two constraints.** **It compares against `ch-legacy`, so it cannot survive the
deletion slice: capture the frozen baseline NOW, as was done for stderr. Decision 6,
fourth arrival in two days — the capture is the irreversible half and the gate is
not.** **And give the capture the same refusal as the stderr one: a recording that
came out empty, or missing an item, must refuse rather than look like a corpus.**

**Then the twelve become prohibitions that outlive the oracle. That is the
difference between a list that records what must not change and a list that can
silently die.**

### The trim class is closed, confirmed rather than assumed

**`first_in_band_timestamp` calls `session::python_strip` on the DECODED `String`
from `BufReader::lines()`.** `python_strip` is `trim_matches(python_is_space)`;
`python_is_space` is `char::is_whitespace() || '\u{1c}'..='\u{1f}'` — **so the
Unicode `White_Space` property covers U+00A0, U+2028 and U+3000, and the C0
separators sit on top. `trim_python_byte_whitespace` is not on that path at all.**

### The stderr re-run, counted from the whole file rather than its tail

| | |
| --- | --- |
| pinned as the ruled `FutureWarning` divergence | **40** |
| byte-compared against frozen bytes | **200**, of which **168 reproduce** |
| failing | **32**, every one `error-invalid-date` |

**⚠ The failure shape IS the diagnosis.** Of `error-invalid-date`'s forty cases,
**the eight `no-colour` ones pass** — both routes emit no escapes — **and all four
colour-emitting tiers fail at both widths under all four `--color` settings.**
**One site that never colours, not a downgrade going wrong at some tiers.**
`search_output::print_error`, held by `parity-finisher`.

**Every `TERM=dumb` case reproduces after the stdout-versus-stderr dumbness fix.**
*Tree `886494cdbc6e`, 269 lib + 56 doctests, five configurations, zero warnings.*

## ⚠ L310. RETRACTED: `-d` does NOT silently exclude. `cwd_from_path` has no callers.

**L305's claim that `cwd_from_path` returning `None` means `-d` silently excludes a
session is WITHDRAWN.** `search-firstmate` reported it upward as "a second public
filter" and is unsaying it.

**`ch search`'s `-d` reaches cwd through `session::cwd(&entries)` at
`search_confirm.rs:270`, not through that function.** `cwd_from_path` ports
`extract_cwd_from_jsonl_file`, which in Python serves
`pool_filter.passes_path_for_index` — **the `ch -1 -d` index path, which has not
been ported.** **So the measured mismatch was dead Rust code against live Python: a
real function-boundary divergence that reaches no user.**

**And the live `-d` path is right BY CONSTRUCTION**: it decodes through
`session::decode_entries`, porting `_iter_jsonl_entries` — **orjson, which rejects
`NaN` exactly as `serde_json` does.** The module doc already said so.

***The discipline that was skipped is the finding: the same seat traced the caller
one paragraph earlier on `codecs.rs` and did not here. The habit is not the hard
part; applying it to the finding you are excited about is.***

## ▶ L311. `inventory.rs` landed — the two sites needed OPPOSITE treatment

- **`last_timestamp`: the byte trim STAYS, only the parse changed.** Its trim **is**
  the oracle. The parse goes through `session::detection_lenient`, because
  `_jsonl_line_timestamp` is stdlib `json.loads` and takes `NaN`.
- **`cwd_from_path`: both changed** — `python_strip` on the decoded line plus the
  lenient parse, its oracle being pure CPython.
- **`python_extension.rs` untouched.**

**⚠ The new assertion caught what the existing fixtures could not.** **Both corpus
sessions put `NaN` on line ONE, so the backward scan's half of the divergence was
invisible to them.** `nan-last-line` was added and run against the pre-fix driver:
red, `last_timestamp` python `2026-08-27` against native `2026-08-20`. **The
fixtures the corpus already had could not have caught the fix being made** —
L295's shape, closed by the seat that inherited it.

**`print_error` now delegates to `search_run::print_stderr_wrapped`** rather than
repeating it, inheriting the colour, the **stderr**-derived dumbness and the
zero-width return at once — **and the seat's own width-zero guard went with it. One
authority, not two**, in a week where duplicated helpers were three separate
defects.

**Three gaps recorded at the site rather than fixed, because nothing reaches them:**
Python requires a **truthy** cwd, so an empty string falls through where this
returns `Some("")`; Python then falls back to the Codex `<environment_context>`
reader, which has no equivalent; **and Python opens in TEXT mode, so a lone `\r` is
a separator to it and not to `BufRead::read_line` — F1's class arriving in a file
F1 never touched.** All three go live if `ch -1 -d` is ported.

**One measured mismatch remains: the sub-second `filesystem_mtime` construction,
routed to `cutover-finisher`.** *`timestamp_opt(seconds as i64, 0)` throws away what
`inventory::stat_mtime` already returns as `f64` including nanoseconds.*

*The snapshot run was offered and declined with a reason: the mechanism is covered
by 21 CPython-transcribed pairs and a byte-identical 311,661-byte run, so a third
pass buys breadth that cannot be spent — **and the snapshot is better kept for a
shape with no unit-level gate at all.** **Declining a run with a reason is the same
discipline as taking one.***

## ▶▶ L312. INVISIBLE RULINGS — a decision that removes work leaves no trace

*`parity-finisher`'s "what is not done" section, and the durable idea from that
seat.*

**A ruling that removes work looks exactly like an omission.** Three in that seat
alone: **the perf budgets not converted; `codecs.rs:1056`/`:1065` deliberately left
on the crate's own classes; `python_extension.rs` deliberately untouched.** **Each
has a measurement behind it. A successor who "finishes" any of them undoes a
measured decision, and every gate stays green.**

**The section was first written listing ONE. Two more had become invisible rulings
in the meantime.**

**⚠ So a handoff needs a section naming what a reader must NOT read as a gap** —
distinct from what is done and from what is left.

**The same shape one level down, and worth copying:** the text-mode `\r` gap is
recorded at `cwd_from_path` **with the note that it does NOT apply to
`last_timestamp`**, because `for_each_line_backward` is the accelerator's own line
splitting and on that path it **is** the oracle. **Without that sentence the next
reader closes a gap that is not one.**

### The eighth whole re-read: five more drifts, every one outside the edited window

A heading saying "Five follow-ups" above nine; a divergence set described as three
after a grant made it four; a cross-reference to a renamed section; **three
instruments missing from the instrument table**; two handed-up items missing.
**None findable by re-reading what changed.**

### The retraction's useful half

***A function-boundary divergence in dead code and a live filter defect look
identical in a measurement and are not the same finding.*** *That is the sentence
worth keeping; "I was wrong" is not.*

**`parity-finisher` idle. Five configurations green, 269 lib + 56 doctests, all 13
shell suites green, tree `0f22f462fbba`. Their ten files are byte-identical to
their own table; only the whole-tree digest moved, because `cutover-finisher` is
still writing — which the note above that table says will happen.**

**Ledger:** F1; the C0 set re-derived, then re-derived again as a four-site class
with three oracles; F16; F17; the wrap-oracle gate; the backreference sweep;
`codecs.rs`; both `terminal.rs` width divergences; `search_output.rs` twice;
`codex.rs`; `inventory.rs`; the `-r` indentation and `textwrap.indent`; **and an
admissibility instrument that disproved its own plan.** **Four defects nobody had
listed, three of which change search results.**

## ▶▶ L313. THE TWELVE ARE PROHIBITIONS NOW — the sweep is frozen and gated

**`tests/data/preserve-because-wrong/legacy-baseline.json`** — 14 cases over 7
committed pools, **captured while `ch-legacy` lives** — and
`tests/test_preserve_because_wrong.py` compares against it. **All 15 tests green.**
The capture **refuses rather than writes** on an empty case, a missing item or a
short list. **`CH_NOW` and `TZ` are pinned in the recording so item 5's tokens do
not rot overnight** — the difference between a frozen baseline and one that
expires.

### ⚠ THE FALSIFIER MUTATES TOWARD *RIGHT*, AND THAT IS THE RULE

**`collapse_home` was mutated to match on a PATH BOUNDARY — the correct
implementation, the one any reviewer would ask for — and the gate went red** on the
mangled sibling, with a message naming why.

***A preserve-because-wrong gate must be falsified by mutating toward right, not
toward wrong. Mutating toward wrong proves the gate notices damage; mutating toward
right proves it notices HELP, which is the only failure mode this list has.***

### Two fixture bugs, both plausible, and the second is the dangerous one

**Item 5's ages came out in minutes:** the first version set file mtimes and left
every entry at one content timestamp, **but `last_timestamp` prefers the in-band
value and only falls back to the filesystem — so the mtimes were never read.** A
fixture that set the wrong dial.

**⚠ The reach assertion failed twice on its OWN ENCODING.** The recording stores
exact bytes through latin-1, **so a UTF-8 needle like `…` never matches the decoded
string — and looks exactly like a corpus that lost the behaviour.** ***An
instrument failing in the shape of the thing it measures is the worst kind.***

### The sub-second fix needed more than dropping the zero

**`datetime.fromtimestamp` rounds the fraction to microseconds with BANKER'S
ROUNDING and then carries; `f64::round` is half-away-from-zero and disagrees on
every exact half-microsecond.** Both constructors now share one
`local_from_unix_seconds`. **`search . -l` is byte-identical** where it rendered
`…:55` against `…:55.004794`.

### The last eight stderr failures were the sink's own, not `parity-finisher`'s

Their `print_error` delegation closed **24 of 32**. The remaining eight were
**`--color always` only, across all four colour-emitting tiers and both widths** —
**both sinks' `emit_error` in `search_views.rs`.**

**⚠ Each carried a comment saying the gap was "a separate slice with its own frozen
baseline" — and the baseline now exists, so the comment described a gap that had
just been closed everywhere else. Eighth false comment on this mission whose stated
reason had expired.** **Both now delegate to `print_stderr_wrapped`: two sinks
answering the colour question separately is how they drift apart.**

*And stated as a principle rather than a table, arrived at independently by two
seats: **`serde_json` rejecting `NaN` is right by construction wherever Python uses
orjson, and wrong only where it uses the stdlib.***

## ▶▶ L314. THE STDERR GATE IS GREEN — 0 failures. Both frozen gates green together.

    240 recorded cases
      40  pinned as the ruled FutureWarning decoration divergence
     200  byte-compared against the frozen legacy bytes — all reproducing
       0  failing

**Three steps, three different sites:** the stdout-versus-stderr dumbness fix closed
every `TERM=dumb` case; `print_error` delegating closed 24 of the remaining 32;
**the last eight were both sinks' own `emit_error`.** **Every stderr line the
product writes now goes through one function.**

**269 lib + 56 doctests, five configurations, zero warnings. The arm reproduces
`ch-legacy` on 54 of 54 whole-pool shapes. Both baselines captured while
`ch-legacy` lives, both gated, the twelve items are prohibitions.**

## ⚠⚠ L315. THE MISSION'S FINDING: the defects hid in what an instrument held still

***"Not in the code, but in what an instrument held still."***

**`cutover-finisher`'s six, in one day:** an empty pool; a `tail -5`; a pty on the
wrong stream; a recorder passing `None`; a fixture whose mtimes were never read; a
needle in the wrong encoding.

**And the desk's, across six seats in two days:** a corpus that could not express
`show_tools`; a fallback gate whose subjects had decayed; a sample word every lexer
paints identically; a freeze that validated against itself; a `COLUMNS` variable a
shared harness scrubbed; `stderr=DEVNULL` inherited by six gates. **Eleven, one
shape.**

### ⚠ AND THE TWO THINGS THAT CAUGHT THEM WERE NOT SUSPICION

**Suspicion caught none of these.** What did:

- **Reconciliation.** A `-k` run showing thirty-two failures in one shape that could
  not be squared with a `tail`'s five.
- **Making every verdict show its evidence.** A probe required to report whether an
  ellipsis actually appeared. A control proving a whole budget colours the same
  fence. A normaliser required to fail on a path outside the temp root. A capture
  that refuses rather than writing empty cases.

***Every one is an instrument being made to prove it can discriminate — not a
person looking harder.***

## ▶▶ G5 IS RELEASED. THE TREE IS QUIET AND BOTH IMPLEMENTATION SEATS ARE CLOSED.

**`g5-runner` starts with `run_all.sh` as check 1, then works the runbook in its own
order.** Nothing further will be written into the tree.

**Two knowns, not to be chased:** `test_search_dir_filter_list_under_2500ms`, the
pool having grown past an absolute bound **on the outgoing route** (ruled not to
convert, L285); and the two asserted-exact divergence sets — **the four fence
languages and the `FutureWarning` decoration — rulings with their reasons at the
rows.**

**Expect reds. Every gate green before today was a formality; the byte lock could
not fail on Rust nothing called. Failures are reported as failures with their
output. Nothing is relaxed and no expectation is restamped.**

### L316. The falsification discipline, in one sentence

***"A gate that cannot fail and a gate that did not fail are indistinguishable from
the outside, and the only way to tell them apart is to make one fail on purpose."***
— `cutover-finisher`, closing.

**And on L315's eleven: no seat found more than two, and none could have seen it as
a class from inside their own.** ***That is an argument for the desk existing, not
for any individual being careful.*** **The number exists only because every seat
reported its own instrument failing rather than only its findings** — which nobody
here had to be asked to do.

*One post-release edit, disclosed: `teammates/cutover-finisher/RESUME.md` only. Its
tree digest had gone stale from that seat's own last edits, and the warning beside
it said the digest moves "without this seat touching anything" — **false in the one
direction that matters.** It now names both reasons and says re-derive rather than
trust. **A knowingly-wrong digest in a handoff is the decay class itself.***

**FINAL TREE: `b59b2496b9b6`. 269 lib + 56 doctests, five configurations, zero
warnings. Both frozen gates green, both baselines captured while `ch-legacy`
lives.**

## ⚠⚠ L317. CHECK 9 IS RED — 18 failed, 21 errors — and NEITHER cause is a port defect

*`g5-runner`, 14:57:05Z–14:58:56Z, 110.8s. Oracle route digest `dd6ab701…` and rust
tree digest `b59b2496…` **identical before and after**. 2354 passed.*

**COVERAGE LIMIT, STATED FIRST: `run_all.sh` uses `set -e`, so it STOPS at the first
pytest failure and never reaches the perf suite or the 13 shell suites. The command
as specified reports the FIRST FAILURE ONLY — a short failure list is not a small
failure count.** The enumeration of the remainder was the runner's, not the gate's.

### Root cause 1 — all 21 errors: a second, un-updated copy of the launcher guard

**`tests/test_parse_command_contract.py:35` still holds the OLD NEGATIVE form** —
`HEAD_ABSENT_LAUNCHER_MARKERS = (b"logicalParentUuid",)`, a static one-element
denylist asserted absent from the binary. **Its premise is false in the honest
direction, exactly as the one that was fixed**: the string is legitimately in the
tree at `rust/session.rs:894` and `:916` and absent from committed HEAD, **so a
correctly built binary embeds it and the guard rejects it.**

**The positive freshness proof landed in `test_search_command_contract.py:195`
ONLY. Two functions, same name, two files, one fixed.** **The fix was correct and
complete for the file it was in — the failure was that nobody knew there were
two.** *Fourth duplicated helper this week and the first in `tests/`.*

### Root cause 2 — all 18 failures: the parity suite does not defer to the divergences

**The 18 are EXACTLY the six ruled ids × the three parity functions, no
remainder.** `test_deliberate_divergences.py` defines those six as `DELIBERATE` and
asserts each difference exactly, 11 of 11 green. **`test_search_command_contract.py`
knows nothing about it and still asserts byte-parity on all six.**

**⚠ The two suites assert OPPOSITE things about the same cases, so the suite cannot
be green by construction.**

**And the divergence suite's own opening line is the argument against the state it
is in:** *"An expected red is indistinguishable from a regression. This desk spent
two days removing the last row that was allowed to fail, so these six are not left
red."* **They ARE left red — in the other suite. The mechanism was built and the
parity suite was never taught to defer to it.**

**RULED, so the fix cannot recreate cause 1: `DELIBERATE` is the SINGLE AUTHORITY
and the parity suite imports it. No second copy of that list. And the exemption
must not be a silent skip — if an id leaves `DELIBERATE`, the parity suite must
start asserting it again on its own**, the divergence suite already killing the
other direction with *"an inert allowance is worse than none"*. ***Fix a
duplicate-authority defect in a way that cannot itself become one.***

### Not wrong, so nobody chases it

**All 13 shell suites pass. 2354 tests pass. No behavioural divergence anywhere.**
The perf suite fails twice — **both are the retired live-pool budgets at 1750 and
2500 that check 9's own row explicitly excludes**, and the runner named the one this
desk had not.

### The runbook is corrected — by `search-firstmate`, signed and dated

**Three expired preconditions MARKED, not rewritten**, keeping the originals because
the reasoning is the useful part: the cutover landed; `run` now has callers and
passes `terminal_width()`; **and check 10's panic is gone while its rule is not — a
`-ll` probe still never touches the panel renderer, so it still passes the no-Python
proof over a route whose rendering it never exercised. The premise moved; the reason
did not.** **The `set -e` finding is added where check 9 is read.** 222 lines,
symlink identical, **no pass condition changed.**

## ▶▶ L318. BOTH CAUSES FIXED — the search contract suite is green. One red left, and it is the cutover succeeding.

**Fix 1:** `test_parse_command_contract.py` now **imports** `_reject_foreign_launcher`
instead of holding a second, older copy; its `HEAD_ABSENT_LAUNCHER_MARKERS` is
deleted. **21 errors → 0.**

**Fix 2:** `tests/deliberate_divergences.py` is the single authority and **both**
suites import it. **18 failures → 0.**

**⚠ And the exemption is not a skip.** Each of the three parity functions asserts
the case **still differs** and names where the strong assertion lives. **Remove an
id and the parity suite starts asserting byte-parity on it again by itself; leave
one that has stopped diverging and it fails here as an exemption allowing nothing
AND there as an inert allowance. Neither suite can quietly stop meaning anything
without the other going red.** *Fixed in a way that cannot become the defect it
repairs.*

### ⚠ The last red: a test asserting the cutover has not happened

**`test_uncompleted_public_journeys_keep_exact_legacy_behavior` lists `search` and
asserts `b"python" in loader_trace`** — *"Expected uncompleted search to remain on
the private Python legacy route."* **It fails because `ch search` no longer loads a
Python interpreter. That is the cutover succeeding.**

**The fix is a CLASSIFICATION, not a line.** `search` belongs in the **completed**
set, **where the same file already asserts a journey bypasses the PyO3 extension —
the opposite check, and the one search should now pass.** **Deleting the case would
remove an assertion rather than move it, which is the worst of the three options.**
Routed to `contract-owner`: what their file means is their call.

**⚠ MIRROR IMAGE OF THE GUARD, IN THE SAME FILE, DATED BY THE SAME EVENT.** The
guard asserted a fresh binary **cannot** contain a string it now legitimately does;
this asserts a journey **must** still be Python when it is now Rust. **And the
second only became visible once the first stopped erroring the file out.** ***A
decayed assertion can hide another one behind it.***

**`cutover-finisher` closed at 91%, having diagnosed it precisely and deliberately
not started a semantic change to someone else's suite with nothing left to verify
it.** *Naming all three options and taking none is the judgement, not the caution.*

**Everything that seat held is green:** 269 lib + 56 doctests, five configurations,
zero warnings; both frozen gates; the search contract, divergence and
launcher-provenance suites.

**Seat ledger:** the tool surface; the `Edit` diff and its autojunk corpus; the
`Read` gutter and its three oracles; the removal of `Unsupported` from the crate;
the launcher guard rebuilt as an agreement with a stale binary kept to falsify it;
the `COLUMNS` sweep; all four route-flip defects; `first_timestamp`; the stderr
slice from *unreachable* to a frozen 240-case gate; **and the twelve
preserve-because-wrong items turned into prohibitions on its own argument.**
**Eight false comments found, five of them its own. Three public self-corrections.**

## ▶▶ L319. THE CLASSIFICATION LANDED — G5 IS RUNNING

*Confirmed on disk by `search-firstmate` rather than taken on report:
`tests/test_parse_command_contract.py`'s uncompleted list now holds only
`default-session-parse` and `legacy-name`. **`search` is in the completed journey
test**, asserting `b"python" not in loader_trace` and `_native`/`abi3` absent.*

**The case MOVED rather than being deleted, and the docstring says why: deleting it
would drop an assertion instead of relocating one, and this is the assertion the
charter actually asked for — search bypasses Python.**

### ⚠ A note from that docstring that bears on check 10

***A legacy journey `exec`s into a hardened-runtime interpreter, and macOS purges
`DYLD_*` across that exec, so the trace stops at the handoff and shows nothing. A
completed journey does the work in this process, so what it loaded is what the
trace lists.***

**The loader trace is meaningful on the COMPLETED side in a way it is not on the
legacy side.** *A quiet trace is not proof by itself* — routed to `g5-runner`
before they run check 10.

## ▶ G5 DISPATCHED — `g5-runner` alone, every implementer idle

**Re-derive both digests immediately before the run; re-run check 9; if green, work
the remaining thirteen in runbook order.** A defect gets its owner named and routed
through the first mate — **one narrow owner-specific item only, no side work.**

**Two knowns, not to be chased:** the two retired live-pool perf budgets that check
9's row excludes, and **`run_all.sh`'s `set -e` stopping at the first pytest
failure — the note is in the runbook where check 9 is read.**

## ▶▶ L320. G5 CHECKS 1–9: EIGHT GREEN, ONE RED

*`g5-runner`. Digests `dd6ab701…` and `b59b2496…` **identical before and after every
run.** **Coverage limit: `run_all.sh`'s `set -e` stopped at the excluded perf budget
again, so the 13 shell suites were run separately — that enumeration is the
runner's, not the gate's.***

**✅ 9 core suite — 2394 passed, 3 skipped, 0 failed, 0 errors** (was 18 failed /
21 errors). All three fixes hold. **All 13 shell suites pass.** The only failure is
`dir_filter_list_under_2500ms` at 2845 ms, one of the two retired live-pool budgets
the row excludes.

**✅ 1 no PyO3** — `target/release/ch`, **7,588,720 bytes now that the arm links
`_native`**; libiconv, CoreFoundation, libSystem only; **0 undefined `Py_` symbols,
0 `_native`/`abi3`/`libpython` strings.**
**✅ 2 corpus identity** — 695 files, 1,183,541,907 bytes, `de693c35…` exact.
**✅ 3 frozen set** — 82 stored, 0 drifted, 0 new.
**✅ 4 age pairing** — 259 tokens, 10 pairings, 7 units. **`1w → month` deliberate
misalignment INTACT** — the divergence most likely to have died this week.
**✅ 6 colour capability** — all 6 tiers identical.
**✅ 7 coloured width** — identical at 60, 120, 200; 80 is the demonstration.
**Not pinned to a constant.**
**✅ 8 scoped diff** — 117 paths, all inside `rust/`, `tests/`, `thoughts/`,
`Cargo.*` and the one charter-named `src/chats/commands/search.py`.

### ⚠ The flap, observed rather than argued

**`mafter_4h_list_under_1750ms` failed at 14:57 and passed at 17:43 on an UNCHANGED
TREE.** **The retired-budget pattern demonstrating itself inside the gate that
excludes it** — predicted by the record at the pause, now measured.

## ❌ L321. CHECK 5 RED — `FORCE_COLOR` and `TTY_COMPATIBLE` are ignored by the native route

*Piped sweep. The pty sweep is clean both directions; reverse list empty in both.*

    FORCE_COLOR=1     native 259 bytes, 0 escapes | python 298 bytes, 4 escape runs
    TTY_COMPATIBLE=1  native 259 bytes            | python 298 bytes
    unset (control)   native 259 bytes            | python 259 bytes   identical

**The control isolates it exactly: the routes agree until the variable is set.**

**The site is one line — `rust/search/parse.rs:465`, resolving `--color auto` as
`_ => std::io::stdout().is_terminal()`.** **`terminal::resolve_color` already
reproduces Rich's whole cascade including both inputs, with tests named
`tty_compatible_outranks_force_color_and_isatty` and
`a_forced_terminal_overrides_every_other_signal`. The parser never calls it.**
`stdout_capabilities` reads all five variables correctly and passes them correctly
— **the defect is upstream of it, in the flag decision, not in the resolver.**

**⚠ THIRD INSTANCE OF ONE SHAPE TODAY, SECOND IN THIS EXACT FUNCTION: the field
exists, the resolver honours it, and the call site does not consult it.** Same seam
as `stdout_capabilities` hard-coding `forced_terminal: false`, one caller over.

**Two consequences: `paging` defaults to `color` at line 466, so this drives TWO
visible behaviours** (22d's isatty cascade), **and these are 2 of the documented
five-gap seam in 22af** — `COLORTERM`, `NO_COLOR`, `TERM=dumb` now fixed and green.

**⚠ Reported as UNRULED rather than known: 22af calls all five one seam and a
defect, and NO DECISION EVER ACCEPTED THESE TWO.** ***A gap inside a documented
seam is the easiest thing in the world to file as known.*** Routed to
`cutover-finisher` at 91% **with an explicit out** — `parity-finisher` takes it if
they decline. Checks 10–15 continue in parallel.

## ⚠⚠ L322. "ONE LINE" WAS AN UN-MEASURED CLAIM, AND IT MAY BE THE WRONG FIX

**`g5-runner` sized check 5's defect as one line, `search-firstmate` relayed it, and
neither measured it** — in a week where this desk has said four times that *"too
expensive" is a claim about a mechanism and must be measured against the
mechanism.* ***"One line" is the same claim wearing the opposite sign, and it is
more dangerous, because nobody audits an estimate that makes work sound small.***

**`cutover-finisher` looked before declining, and the apparent site may be the
wrong fix in the right file.**

`rust/search/parse.rs:465` resolves `--color auto` as plain
`stdout().is_terminal()`, and `terminal::resolve_color` already reproduces Rich's
whole cascade with tests named after both variables. **But `cli.py` computes
`color` with plain `isatty()` too — NOT Rich's cascade. Neither variable reaches
that decision. They reach the CONSOLE: when `color` is false, `init_module_console`
builds a bare `Console(theme=APP_THEME)`, and Rich consults both variables itself
to decide it is a terminal.**

**⚠ So Python may be taking the PLAIN route under `FORCE_COLOR=1` and emitting
escapes anyway, from the console rather than from the flag.** **Making the parser
call `resolve_color` would then flip the SINK as well as the colour — and `paging`
with it, since `paging` defaults to `color` one line down. Two visible behaviours,
where the product may only move one.**

**THE MEASUREMENT THAT SETTLES IT, ordered before any edit: under `FORCE_COLOR=1`,
piped, does the Python route print a LIST ROW or a PANEL?** That says whether
`flags.color` flipped or only the console's colour did. **Same shape as
`stdout_capabilities` versus the stderr consoles: a choice reaching one console and
not another.**

**Routed to `parity-finisher`, measurement first, then a gate covering both `color`
and `paging` with a falsifier. `rust/search/parse.rs` is theirs for this and
nothing else.**

### `cutover-finisher` closed for good at 91% — and the decline is the judgement

**Not "I might run out": the fix would fit, and the GATE plus falsifier is where
they would run out mid-way — and a half-landed change in a shared checkout while G5
is running is the one failure with no cheap recovery.** **Two declines today, both
for stated mechanisms, everything else taken. That is what an accurate
self-assessment looks like from outside.**

***Their closing line, the seat's own lesson landing on itself: "too expensive" and
"one line" are both claims about a mechanism, and neither is true until
measured.***

## ▶▶ L323. MEASURED: `flags.color` NEVER FLIPS. The apparent fix was the wrong fix.

*`parity-finisher`, measured before touching a line. Fixture home, piped,
`COLUMNS=100`.*

    list mode      control 478B / 0 escapes   FORCE_COLOR=1 531B / 6 escapes   stripped -> 478B, identical
    matches mode   control 589B / 0 escapes   FORCE_COLOR=1 642B / 6 escapes   stripped -> 589B, identical

**Byte-identical after stripping, in both modes. The product still takes the plain
`console.rule()` + `display_search_result` route — `flags.color` stays false, the
sink does not move, and `paging` does not move with it.**

**⚠ So making `rust/search/parse.rs:465` call `terminal::resolve_color` would have
changed TWO visible behaviours where the product changes NEITHER** — flipping to a
coloured list row or a conversation panel and turning paging on. ***The wrong fix
in the right file, disproved rather than argued.* `rust/search/parse.rs` needs no
change at all.**

**What actually paints is one thing: `console.rule()`.** Nothing else gains an
escape — `session_id:`, `provider:` and the body stay plain. The six runs are the
rule's filler and title. **`search_output.rs:245` is the only production call
site**; the other three are that seat's own tests.

### The tier table — every ambient variable controlled

| tier | bytes | rule codes |
| --- | ---: | --- |
| control | 478 | none |
| truecolor | 531 | `38;2;0;255;186` + `1;37` |
| eight-bit | 517 | `38;5;49` + `1;37` |
| standard / no `TERM` | 507 | `96` + `1;37` |
| `TERM=dumb` | 418 | none — **60 bytes SHORTER than the control, the width drops to 80** |
| `NO_COLOR=1` | 486 | `1m` only — **bold survives, colour is stripped** |
| `TTY_COMPATIBLE=1` | 531 | same as truecolor |
| **`FORCE_COLOR=0`** | 531 | **coloured — PRESENCE, NOT TRUTH** |
| **`TTY_COMPATIBLE=0` + `FORCE_COLOR=1`** | 478 | none — **`TTY_COMPATIBLE=0` WINS** |

**`resolve_is_terminal`'s documented behaviour confirmed END TO END rather than at
the unit level, and `NO_COLOR` is preserve-because-wrong item 10 showing up on
stdout.**

### ⚠ The twelfth held parameter — inside the probe built to find them

**The first sweep cleared only `FORCE_COLOR` and `TTY_COMPATIBLE`, so the parent
shell's `COLORTERM` leaked into every tier and "eight-bit" reported truecolor
bytes.** Caught before it reported. **The table above is from the corrected run,
clearing all five variables Rich consults.** *A wrong table would have looked
entirely reasonable.*

### Granted, with the capture first

**`search_output.rs:245` for this; `rust/search/parse.rs` untouched.** Measured
size: **60–100 lines plus a generated table**, the F16 and wrap-oracle shape. **The
gate is the larger half — exactly where `cutover-finisher` judged they would run
out.**

**⚠ CAPTURE THE TABLE FROM LIVE PYTHON FIRST. Fifth arrival of decision 6 in three
days:** the nine-environment table must come from `ch-legacy`, which the deletion
slice removes. **Capture, then fix, then gate — with the same refusal the stderr and
preserve-because-wrong baselines carry: a recording with no escapes in any tier must
refuse rather than look like a corpus**, which is exactly what the `COLORTERM` leak
would have produced.

## ▶ L324. The rule-colour oracle is captured, and its refusal is falsified against a real leak

**`probes/rule-colour-oracle.json`, 20 rows** — ten environments × two output shapes
— **captured from `ch-legacy`** while it lives, stdout bytes verbatim,
`COLUMNS=100`, deterministic fixture.

**It needs no clock override, and that was CHECKED rather than assumed.** The plain
route prints `created:` and `modified:` as **absolute** times from in-band
timestamps, **no age token reaches it**, and the temporary home collapses to `~` in
rendered paths — **so nothing varying reaches the bytes.** *A recorded table that
needed a clock override and did not get one would have rotted overnight and looked
like a regression in the morning.*

**⚠ Four refusals, and the one that matters was falsified by reintroducing the
EXACT `COLORTERM` leak the seat's own first probe had:**

    REFUSING TO WRITE:
      - list: truecolor, eight-bit and standard did not all differ. That is the
        signature of an ambient COLORTERM leak, not of a product that renders
        them alike.

**It refuses, names the MECHANISM rather than the symptom, and writes nothing.**
***A capture that can only fail on a leak it has already suffered is the strongest
form of that guard.*** Three companions close the other directions: the control
must carry zero escapes, at least one tier must carry escapes, `TERM=dumb` must
carry none.

### Granted: the one word, taken by `parity-finisher` rather than waking a closed seat

**`search_run::stdout_capabilities` → `pub(crate)`, and nothing else in that file.**
`cutover-finisher` is closed for good at 91% and was told nothing further would be
asked; **waking a seat to type one visibility keyword spends a wake on a keyword,
and they are writing nothing, so there is no collision.** Same shape as the
`codex.rs` grant.

**⚠ And the symmetric move was rejected for a mechanism, which is the ruling.**
Adding the field to `PlainOutput` **breaks `search_run.rs:179` the instant it is
made**, because a Rust struct literal must name every field — **a knowingly red
tree in a shared checkout while G5 is running, the exact thing `cutover-finisher`
declined over.** **Resolving once in `PlainSink::new` — own function, own file — is
no new field, no struct-literal break, nothing red at any moment.**

**`stdout_capabilities(false)` is right because the plain arm is only reached when
`flags.color` is false** — a fact about the call graph, not a convention.

*Two things the capture confirmed, both from `console.py:98`: when `force_color` is
falsy Python builds `Console(theme=APP_THEME)` with **no `force_terminal` at all**,
so Rich's own cascade decides — **which is exactly why the variables reach the
console and not the flag.** And the painted spans are **three**, not one:
`[filler]left+space[/]`, `[bold white]title[/]`, `[filler]space+right[/]`.*

## ▶▶ L325. CHECK 10 PASSES AND DISCRIMINATES FOR THE FIRST TIME

*`target/release/ch` alone in an empty directory, no `ch-legacy` sibling, `env -i`
with `PATH=/nonexistent`.*

- **search: exit 0, 934 bytes, 31 escape runs — a full coloured panel with no
  Python anywhere.**
- **`info --help`: exit 1, "Cannot start the private ch legacy entry".**

**This morning both halves failed identically because both routes were Python. Now
search renders and the control still fails.** ***The probe can tell the two routes
apart, so the search half means something for the first time.*** **The before-state
recorded at L298 paid for itself the same day.** Run with `--color always`, per the
rule whose premise moved and whose reason did not.

## ❌ L326. CHECK 11 RED — A REAL NATIVE REGRESSION, roughly 2×

    broad list, absolute date        976.3ms  vs   650ms   FAIL
    selective literal, id-only        0.439x  vs  0.30x    FAIL  (906ms vs 2067ms)
    broad regex miss, id-only         0.435x  vs  0.25x    FAIL  (1637ms vs 3764ms)

**Not contention.** Reproduced independently, interleaved, three repetitions:
**0.438–0.448 and 0.434–0.436 — a 2% spread**, with native absolutes equally tight
at 902–921ms and 1630–1638ms. *The machine was NOT quiet — load 1.80 — and the
runner separated load from regression before reporting rather than after being
asked.*

**⚠ The NATIVE side moved. Python is stable and slightly faster than the old ratio
implies, at 2057–2067ms.** `selective literal, id-only` was **360.3 / 372.8 /
568.0 ms on 2026-08-28** and is **902–921 ms now.**

**The caveat, stated rather than buried: that old figure had a 56% run-to-run
spread and today's has 2%. Comparing a stable number to an unstable one is a real
weakness — and the movement survives it, because the WORST old reading (568 ms)
sits well below today's BEST (902 ms).**

**⚠ THE CAUSE IS UNMEASURED. A great deal landed on the scan path today across two
seats. A bisect over today's landings is the instrument, and it comes AFTER checks
13–15** — switching mid-gate costs more than it buys. **Nobody, including
`search-firstmate`, may call this a known number until it is localised.**

### ⚠ And a hole in the gate itself, which is not a port defect

**`--falsify` requires every shape to fail against the reference, and one did not:
`broad literal miss, id-only` measured 462.4 ms on the PYTHON route against a
750 ms budget and passed it.**

***A budget the reference route also passes cannot discriminate between the routes
at all.*** That shape proves nothing today and presumably has not for as long as
the budget has sat there. **Same class as check 10's control before this morning.**

## ◐ L327. CHECK 12 — the documented 1.29×, unchanged, and already owned

**Subject +576 MB, reference +447 MB. 576/447 = 1.288**, which the record carries to
the same digits with the mechanism resolved — slopes 9.00 against 7.01, two extra
resident copies — and rules *"its own task, not part of B1"*, awaiting exactly the
allocation profile that is check 13. **The control passed, both arms near zero: the
gate is working and the red is the known one.** Reported together with 13.

## ▶▶ L328. ALL FIFTEEN G5 CHECKS RUN — 10 green, 4 red, 1 gate defect

**Green:** 1, 2, 3, 4, 5-pty, 6, 7, 8, 9, 10, 14.
**Red:** 5-piped (routed), 11, 12, 13, 15.
**The `--falsify` hole in 11 is a gate defect, not a port defect.**
**Three of the four reds are one story:** 12 and 13 are the same two extra resident
copies; 11 is a timing regression whose cause is unmeasured; **15 is a release step
plus a hazard.**

### ❌ Check 13 — the queued prediction is FALSIFIED, and that is a real answer

    subject    peak = 9.00 x payload + 23 MB fixed
    reference  peak = 6.99 x payload + 84 MB fixed
    frozen gate: subject slope 9.00 against 7.36   FAIL

**The prediction was that if `session`'s clone-to-move change was the mechanism the
slope would fall from 9.00 toward 7.00. It did not move at all — 9.00 to three
digits. So clone-to-move was NOT the mechanism, and the two extra resident copies
remain unattributed.**

**And the old model reproduced precisely** — recorded 9.00/+21MB and 7.01/+82MB
against today's 9.00/+23MB and 6.99/+84MB — **with its crossover prediction holding
again: predicted at 30.5 MB, and at 32 MB the arms are 311 against 310.** **The
native route still wins on small sessions: 95 MB against 140 MB at 8 MB.**
***A model that predicts a crossover and hits it is worth more than the gate it
failed.***

### ✅ Check 14 — the wheel, built from a purged `build/` and `dist/`

**Exactly one file named `ch`**, Mach-O, `47fa6038…`, **byte-identical to
`target/release/ch` — the route identity the perf gate recorded, so everything
measured is the shipped artifact.** `entry_points` expose only
`ch-legacy = chats.cli:main`. **Extracted alone with no sibling it passes check 10
on its own** — search exit 0, 934 bytes, 31 escape runs; `info --help` exit 1.
libiconv, CoreFoundation, libSystem only; 0 `Py_` symbols.

***Stated precisely rather than glossed: the wheel holds a SECOND Mach-O,
`chats/_native.abi3.so`*** — the PyO3 extension the retained `ch-legacy` route uses
and the charter keeps. **"One Mach-O `ch`" is satisfied; "one Mach-O in the wheel"
would not be, and that difference should not be discovered by someone else later.**

## ⚠⚠ L329. THE INSTALL HAZARD — nobody installs until the reference moves

    wheel            47fa603892be92e8…   built 2026-09-01T18:00
    ~/.local/bin/ch  22236c087af33dea…   installed 2026-08-28T15:33

**Check 15 is red because the install step has not happened** — its proposition,
*the shipped artifact is the one measured*, is currently false.

**⚠ BUT THE PYTHON REFERENCE AND THE INSTALL TARGET ARE THE SAME PATH.**
`~/.local/bin/ch` at `22236c08` is the pinned pre-cutover build that hands search to
Python, **which is exactly why it is the reference for checks 3, 5, 6, 7 and 11.**

**Installing the wheel overwrites it with the native route, and every gate pointed
at it would compare NATIVE AGAINST NATIVE** — *"this compares a process with
itself"*, the failure the contract suite escaped this morning, **reintroduced
through the install step.**

**⚠ And `freeze_references.py --verify` never checks the stored reference identity —
it compares entries, so a swapped reference reports DRIFT and reads as the port
breaking. It fails in the shape of a different problem.**

**RULED, in this order, and `g5-runner` owns all three:**

1. **Move checks 3, 5, 6, 7 and 11 to `.venv/bin/ch-legacy`**, which installing does
   not touch. `reference_route_identity` changes with it — **derived, recorded, and
   the change stated in `provenance` with its reason.**
2. **Make `--verify` REFUSE on a reference-identity mismatch**, naming the
   mechanism. **Fix the class: any gate whose reference identity can be swapped
   underneath it should say so rather than report drift.**
3. **Then localise check 11** — bisect over today's landings, measure rather than
   reason. **They report the cause and its site; the fix goes to an owner.**

***This inverts `search-firstmate`'s L296 ruling, which withdrew constraint 3
because the pinned install was the more stable of the two. Correct then. It
inverts the moment the wheel lands.***

## ▶▶ L330. CHECK 5 CLOSED — 20 of 20 byte-identical against `ch-legacy`

**The fix is entirely in `search_output.rs`.** `rule()` builds from a private
`rule_parts()`; `rule_styled()` paints the same three runs through
`search_views::render_segment`. **One authority for the arithmetic, so the 147
recorded rows that gate `rule()` also gate the painted form against drift.**
`PlainSink::new` resolves the rendering once. **No field added to `PlainOutput`, so
`search_run.rs` never stopped compiling for a moment.**

**The two styles are what the measurement said:** filler `#00ffba` as a **triplet**
so it downgrades; title `bold white` where **`white` is a palette colour**, so it
stays `1;37` at every depth while the filler moves around it.

**The main gate drives the WHOLE CHAIN** — recorded environment map →
`terminal::resolve_color` → `color::rendering` → `rule_styled` — **so a cascade
defect and a painting defect both land there.** *Those two were entangled in the
original report and only a measurement separated them; the gate keeps them
separated.* **Falsifier counts matched the capture without adjustment: 14 of 20
rows carry colour, 6 do not.**

### ⚠ A second defect found end to end, and it was a WIDTH difference, not colour

    list     TERM=dumb   python 418 bytes   native 478
    matches  TERM=dumb   python 529 bytes   native 589

**`terminal::stdout_is_dumb_terminal` tested `isatty` directly.** Rich's
`is_dumb_terminal` is `is_terminal && TERM in ("dumb","unknown")`, **and
`is_terminal` is the WHOLE CASCADE** — so under `FORCE_COLOR=1` a pipe **is** a
terminal, a pipe with `TERM=dumb` **is** dumb, and the width drops to 80. **The
product wrapped at 80; the native route wrapped at 100.**

***`cutover-finisher`'s stderr mechanism arriving on stdout — the third surface
where a property was read from a narrower signal than Rich's cascade.***

### ⚠ Ninth false comment, and the first of a new kind

**`format_raw`'s claimed a behaviour that never existed. This one stated a rule that
is TRUE UNDER A PRECONDITION IT DID NOT NAME** — *"a pipe is never dumb however
`TERM` is set"* holds only while nothing forces terminal-ness. ***So it reads as
correct and is correct most of the time, which is harder to catch than a plain
falsehood.***

### The layering inversion, accepted as a deliberate debt with its reason

**`stdout_is_dumb_terminal` now delegates to `stdout_capabilities(false).is_dumb` —
`terminal.rs` reaching into `search_run.rs`, which is upside down.** **The
alternative was a second copy of the same five-variable environment read, and a
fork of that exact shape has been three separate defects this week while odd
layering has been none.** ***The failure mode this desk has actually measured was
chosen over the one that merely looks wrong.***

**⚠ It is an INVISIBLE RULING in L312's sense: it looks like something to tidy, and
tidying it by duplicating the read would reintroduce the class.** Consolidate only
when someone owns both files.

*Blast radius checked rather than assumed: with none of `FORCE_COLOR`,
`TTY_COMPATIBLE` or `forced_terminal` set, `resolve_is_terminal` returns `is_a_tty`,
so the cascade and the old `isatty` agree and nothing moves in the common case.
**Gated env-free**, because the neighbouring `COLUMNS` tests mutate the environment
in parallel threads. **Falsifier asserts an unforced pipe is NOT dumb — without it
both positive assertions would pass if every pipe were dumb.***

**Five configurations green, 272 lib + 56 doctests, all 13 shell suites green.
`parity-finisher` standing by for check 11's fix.**

## ▶▶ L331. THE REFERENCE IS MOVED — proved answer-neutral BEFORE the move

**`reference_route_identity` is now `c1821a3a86ee9a88` (`.venv/bin/ch-legacy`).**
`instrument_digest` moved to `30c672ef…` because the instrument was edited.
**0 recorded answers changed.**

**⚠ The equivalence was MEASURED, not hoped.** The existing frozen file's
`--verify` was run against `.venv/bin/ch-legacy` **while it was still frozen against
the old reference: 82 stored, 0 drifted, 0 new.** ***So the two references are
equivalent across all 82 entries rather than across the two shapes a sample would
have covered.***

**The provenance carries the move and its reason**, so a reader meets the why rather
than a discrepancy: both references measured equivalent over all 82 before the move;
installing the wheel overwrites `~/.local/bin/ch` with the native route and would
make the gate compare native against native **while reporting drift**;
**`ch-legacy` is the route `oracle_digest.py` actually defines, and installing does
not touch it.**

### The refusal, falsified rather than asserted

    FALSIFIER 1  old reference  ~/.local/bin/ch   → REFUSES, exit 1
    FALSIFIER 2  THE INSTALL HAZARD, native ch    → REFUSES, exit 1
    CONTROL      .venv/bin/ch-legacy              → 82 stored, 0 drifted, exit 0

**⚠ Falsifier 2 is the hazard itself, run as a test** — the thing this reordering
exists to prevent, executed and refused. **The message names the mechanism rather
than the mismatch: every entry would disagree and the run would report drift, which
reads as the port breaking.**

**Three properties checked rather than assumed, and the first is the day's lesson
repeating: the first exit-status reading was `tail`'s, not the gate's** — the same
instrument that reported 235 of 240 this afternoon, **caught in seconds this time
because the seat already knew it.** It writes to **stderr**. And it **refuses
before collecting**, so a wrong reference costs no pty runs. *The docstring records
why refusing beats warning: a warning here is read AFTER the drift list, and by then
the drift list has been believed.*

### Checks 5, 6, 7 re-run on the new reference — all reproduce exactly

5a clean both directions; 6 identical across all six tiers; 7 identical at 60, 120,
200.

**⚠ And check 5's red reproduced unchanged — the same two variables.** ***A red that
survives a change of reference is a stronger red than one measured once***, and it
retires any suspicion that the finding was an artefact of the old reference.
*`parity-finisher` has since closed it at 20 of 20.*

## ⚠ L332. RULED: THE INSTALL IS UNBLOCKED BY THE MOVE AND STAYS BLOCKED BY CHECK 11

**`~/.local/bin/ch` is what the user actually runs. Installing now would ship a
native route carrying an unexplained two-fold regression.** **The install happens
after check 11 is localised and resolved — a product decision, not a gate
ordering.**

*Expected before the number rather than after it: `ch-legacy` has no Mach-O exec
hop, so the Python side may come back faster and the ratios may look worse. **If so
that is the more honest number, not a regression on top of a regression.***

## ▶▶ L333. "A MAINTAINED NUMBER IS A DRIFT GENERATOR"

*`parity-finisher`, and it is a change in kind rather than another correction.*

**Every count this desk has written has gone stale, some within the hour:** nine
above ten; five above nine; three above four; "the four bounds" above six;
173 / 180 / 234 in three places in one file; "two follow-ups, both done" above five.
**Six seats have been fixing the counts.**

**They removed the mechanism that produces them.** Headings now point at sections
and the sections are the list. **The one count kept is the one that must not move:
20 of 20 byte-identical.**

***That is the Tetris move — remove the circumstance rather than the symptom.***

### ⚠ The false-comment sub-class a reviewer cannot catch by reading

**`format_raw`'s comment said something that was NEVER true** — findable by anyone
who reads the code beside it.

**This one said something that stops being true only when a variable is set**:
*"a pipe is never dumb however `TERM` is set"*. **It reads as correct and is correct
almost always.**

***A comment true under a precondition it does not name survives every review that
does not run the case.*** **Ninth false comment on this mission and the first of its
type.**

### The ninth whole re-read — the stacked-header shape a third time

**The instruments table had grown DUPLICATE ROWS across two separate appends**,
listing `character_class_parity.py` twice and `rule_oracle_wide.py` both alone and
paired. **Visibly wrong, and invisible because the author only ever re-read the rows
being added.** **Eight of nine whole re-reads have now found something.**

### "What is not done" now carries four invisible rulings

**The perf budgets not converted; `codecs.rs:1056`/`:1065` left on the crate's own
classes; `python_extension.rs` untouched; and the `terminal.rs` → `search_run.rs`
layering inversion — kept because consolidating it by duplicating the environment
read reintroduces the class that has caused three defects this week.**

***The fourth entry exists because the author was told what they had just written:
an invisible ruling is invisible to its own author first.***

*Tree `7b3267a6a22e`, five configurations green, 272 lib + 56 doctests, all 13 shell
suites green. `parity-finisher` **standing by, not closed**, with room, fixture
homes, drivers and recorded tables ready.*

## ⚠⚠ L334. CHECK 11 LOCALISED — and the gates may never have described this port

*`g5-runner`, interleaved, three repetitions, same corpus. **The baseline is
`tests/data/launcher-provenance/ch-0ffde41`, the `wip/cycle-02` build kept to
falsify the launcher guard — found by re-reading the record after concluding it was
absent.** That artefact has now paid twice.*

    shape              today       branch(08-25)  today/branch
    literal miss       262-268ms   304-312ms      0.84-0.87x   <- today is FASTER
    regex miss        1654-1739ms  356-411ms      4.14-4.65x
    selective literal  916-954ms   252-296ms      3.10-3.78x

**Today's port BEATS the branch on plain literal scanning. It loses on exactly two
things.**

**Cost centre 1 — regex evaluation, 4.1–4.7×.** The regex shape finds **nothing**,
so this is not hit handling. **This port reproduces Python's regex semantics
exactly; the branch is prior art with known deviations.**

**Cost centre 2 — per matching session, and NOT per hit. The obvious hypothesis was
tested and failed:**

    query           matching sessions   today    branch
    zqxjvwmkbphfgd         0            262ms    282ms
    needle                25            925ms    273ms
    function             177           1721ms    335ms
    the                  553           1577ms    380ms

**Per-hit cost falls from 26.5 ms to 2.4 ms as hits rise, and 553 sessions cost
less than 177 — so it does not scale with hit count. It tracks work done on matched
sessions.** **The branch stays at 273–380 ms whatever it matches: it pays this cost
essentially not at all.**

**Grounded hypothesis, NOT a measured attribution: the confirmation pass.**
`search_confirm.rs:323` resolves `first_timestamp` per candidate, **and the record
already establishes that agent-bearing sessions MUST defer to confirmation or
produce false negatives, with two tests pinning it.** *So if the cost lives there,
some of it is the price of correctness rather than a defect — and the gate never
priced it.* Separating regex from confirmation needs source access and a profiler;
`sample` returns no frames under the hardened runtime.

### ⚠⚠ THE PART THAT CHANGES WHAT A CHECK 11 FAILURE MEANS

**The ratio gates are 0.30 and 0.25, set with margin above recorded ratios of 0.142
and 0.105 — recorded 2026-08-28 in the same window as `selective literal, id-only`
at 360.3 / 372.8 / 568.0 ms.** **The branch build measures 252–296 ms on that exact
shape.** **And on 2026-08-28 the cutover had not landed and `search_run::run` had no
callers, so the branch build was the ONLY native route that could serve it.**

**⚠ So the gates were almost certainly derived from the branch — prior art that
decision 1 rules is NEVER an oracle, on the grounds that its outputs carry known
deviations.** ***The runbook's own rule landing on the runbook's own gates:
"'Native ignores X' and 'the branch ignores X' are different claims."***

**Stated as a strongly-supported inference, not established fact. It cannot be
closed by measurement** — only by whoever was in that window. **Asked of
`reviewer-profiler`, the one person who was.**

**RULED IN ADVANCE, both ways:** if the subject was the branch, **the gates are
re-derived against this port with its correctness costs priced in — a CORRECTION,
not a relaxation.** If it was something else, **check 11 is a real regression and
gets an owner.** **Nothing is relaxed either way** — that is how the live-pool
budgets reached 1750 and 2500.

*Two `g5-runner` self-corrections enabled this: the bisect declared impossible and
then found in the record — **a stated negative closes an enquiry, including for the
person who stated it** — and the exec-hop prediction, stated publicly before
measuring and wrong in the direction that mattered (`ch-legacy` slower at 2120 vs
2067, not faster).*

## ▶▶ L335. CONFIRMED FROM THE RECORD: the perf gates were derived from the branch

**`review-profile-plan.md:99`, in the section that defines those gates:**

> *"The native column is the reference branch binary — **evidence that these budgets
> are reachable, not a claim about our deliverable.**"*

**Written in the same edit as the numbers.** L334's inference is confirmed **by the
record rather than by memory** — the disqualifier was there from the day.

**⚠ AND THE TWO BRANCH BUILDS ARE DIFFERENT ARTIFACTS.**
`private-binaries/ch-native` sha `40a5b5d8…`, 6,528,976 bytes, built from the
`0ffde41` worktree with `uv sync` — against
`tests/data/launcher-provenance/ch-0ffde41` sha `257f5052…`. **Same source
revision, different build.** **So 252–296 ms and 360.3–568.0 ms are two builds of
the branch, not one, and neither is a baseline for the other. Both are excluded.**

### ⚠ RULED: re-derive ALL SIX, port against Python, one interleaved window

**The four absolute budgets came from the same window and are the same class.**
**Five constraints, and the third keeps it a correction rather than a relaxation:**

1. **Interleaved, port against `.venv/bin/ch-legacy`, one window, repetitions
   stated.**
2. **Ignore both branch builds entirely.**
3. **⚠ The gate RECORDS that the previous ceilings were derived from the branch,
   with the quoted caveat and its line reference.** *Without it a later reader sees
   ceilings loosened and reads a relaxation — an invisible ruling in the making,
   written down before it becomes one.*
4. **Price the correctness costs beside the numbers** — regex semantics reproduced
   exactly where the branch deviates, and the confirmation pass the record says is
   mandatory or agent-bearing sessions produce false negatives. ***A ceiling with no
   account of what it is paying for is a number someone will try to tighten.***
5. **Close the `--falsify` hole:** `broad literal miss, id-only` at 462.4 ms on the
   Python route against a 750 ms budget **passes on both routes and discriminates
   nothing.** Its new ceiling must fail against Python.

**`g5-runner` measures; `parity-finisher` lands the numbers.** Same split as the
freeze.

### ⚠ AND THIS MAY REFRAME THE WHOLE RED

**On the ratio shapes the port is roughly 0.43–0.44× of Python — more than twice as
fast as the route it replaces.** **If that holds across all six there is NO
user-visible regression at all**, and the install is blocked by nothing but the
gates having been wrong. **Sent back to `g5-runner` to confirm against their own
numbers rather than taken from `search-firstmate`.**

### L336. Proximity is the property, not accuracy

**The caveat was present, correct, and one section away from the table.** It kept
the document honest **and did not stop the numbers being used as though they
described the port.**

***A true caveat that does not travel with its number is not doing the work.***

**Sixth instance of L55's class, and the only one where the qualifier was right the
whole time** — which makes it the cleanest evidence that **proximity is the
property.** *Recorded in the words of the person who wrote both the caveat and the
gotchas line it violated: "a caveat one section away from a table is the failure I
recorded on 2026-08-28 and then committed here."*

**`reviewer-profiler` closed for the third and last time. Woken three times; each
answer was one no measurement could have produced.**

## ▶▶ L337. EVERY SHAPE IS FASTER THAN THE ROUTE IT REPLACES

*`g5-runner`, check 11 against `.venv/bin/ch-legacy`, all six shapes.*

    help                          4.7ms  vs   196.4ms   0.024x
    colored matches            2346.1ms  vs 21390.0ms   0.110x
    broad list, absolute date  1000.5ms  vs  2445.0ms   0.409x
    selective literal, id-only  927ms    vs  2120ms     0.437x
    broad regex miss, id-only  1683ms    vs  3839ms     0.438x
    broad literal miss, id-only 267.9ms  vs   471.3ms   0.568x

**The worst is 0.568× — still 1.8× faster. The best is 41× faster.** **Check 11 was
failing ceilings that were never about this port.**

### ⚠⚠ THE BOUNDARY: "no user-visible regression" is TRUE OF TIME ONLY

**`search-firstmate` told the captain "no user-visible regression at all" and that
sentence is WRONG. Corrected upward.**

**On memory the port is worse and measured so today** — checks 12 and 13,
**+576 MB against +451 MB, slope 9.00 against 6.99, two extra resident copies,
unattributed.** ***A user searching agent-bearing sessions gets an answer faster and
pays more resident memory for it.*** That is the sentence that travels.

***`g5-runner` drew the boundary before the sentence travelled — the difference
between this and the six times something did. A true claim with an unstated scope
is the same defect as a caveat one section from its table.***

## ▶ L338. RULED: ALL SIX BECOME INTERLEAVED RATIO GATES — constraint 5 dissolves

**A ratio gate cannot be passed by the reference, because the reference is 1.0.**

**The finding that decided it, and it is better than the margin question it came
wrapped in:** `broad literal miss` at 268 ms against 471 ms. **A 1.5× margin lands
at ~400 ms with 18% headroom to Python; a 2× margin reintroduces the exact hole
constraint 5 exists to close.** ***A gate whose margin is bounded above by
discrimination is a gate that is barely discriminating*** — and the alternative was
a caveat at the row that someone had to read. **As a ratio the problem does not
exist.**

**⚠ And this is NOT the ratio construction L285 disproved. Say so at the gate so
nobody reads the two rulings as contradicting.** L285 failed because **the
denominator was a DIFFERENT COMMAND whose growth did not track the subject's, so
the ratio rotted.** **Here the denominator is the same query on the same corpus
through the Python route in the same window — it scales identically by
construction.** *Ratios fix rot; they do not fix noise; the noise here is 2%.*
**All three conditions met here, none met there.**

**Margin: 1.5× the port's slowest observed ratio.** *A margin is a policy, not a
measurement — and 1.5× over the slowest observed is a rule a reader can check
rather than a number someone chose.*

*Both branch numbers dropped, **including the part that favoured the port**, and
marked superseded on the runner's desk rather than deleted, with the reason.
**A measurement withdrawn is more useful than one erased, and withdrawing the half
that flattered you is what makes the withdrawal credible.***

**`g5-runner` produces the numbers; `parity-finisher` lands them.**

## ▶▶ L339. SIX RE-DERIVED RATIO GATES — two windows, ~2% agreement

*Interleaved, 5 pairs per shape, one window, port against `.venv/bin/ch-legacy`.*

    shape                        port med   python med   ratio  worst  spread    old
    help                            5.8ms      189.8ms    0.030  0.032   1.29x    25ms
    broad literal miss, id-only   261.8ms      478.8ms    0.550  0.568   1.11x   750ms
    broad list, absolute date     988.9ms     2450.8ms    0.404  0.405   1.04x   650ms
    colored matches              2332.0ms    21596.6ms    0.109  0.109   1.02x  4000ms
    selective literal, id-only    914.0ms     2091.1ms    0.438  0.444   1.02x   0.30x
    broad regex miss, id-only    1654.7ms     3818.8ms    0.434  0.445   1.03x   0.25x

**Every ratio is below 1.0: the port is 1.8× to 33× faster than the route it
replaces, on every shape.**

**Reproducibility, run before anyone asked whether one window was enough:** a
separate earlier window of different design gave 0.030, 0.549, 0.400, 0.109, 0.430,
0.436 against these. **Two windows, ~2% agreement, no shape disagreeing.**

### ⚠ RULED: margin is 1.25× the worst observed, and 2.0× for `help` — tied to measured spread

**1.5× was proposed and declined, because the runner stated what it amounts to
rather than leaving it to be discovered: *"every one of these gates tolerates the
port becoming 50% slower before it fires."*** **Against a measured noise band of
2–4% on five of six shapes that is roughly twelve times the headroom the noise
needs, and 50% is exactly the size of regression a refactor introduces.**

**`help` gets 2.0× because its spread is 1.29× against 1.02–1.11× elsewhere** — a
5.8 ms measurement dominated by process startup. **A margin tied to measured spread
rather than applied uniformly is still a stated, checkable rule — and a better one,
because it is derived from the thing it protects against.** **The 1.29× is recorded
at that row, so the wider multiple is visibly earned rather than granted.**

Ceilings: `help` ~0.064, `broad literal miss` ~0.710, `broad list` ~0.506,
`colored matches` ~0.136, `selective literal` ~0.555, `broad regex miss` ~0.556.
**All well below 1.0, so discrimination by construction is untouched.**

### ⚠ THE STANDING RULE AT THE GATE

**If a row flaps, it is widened WITH A RECORDED MEASUREMENT and never quietly.**
***That is exactly how the live-pool budgets reached 1750 and 2500 — every widening
was locally reasonable and none was recorded as a measurement.***

### Three notes go at the rows, verbatim, not in a message

1. **Why the previous ceilings were higher** — the branch provenance with
   `review-profile-plan.md:99` quoted. *Without it a reader sees loosened ceilings
   and reads a relaxation.*
2. **Why this is not the construction L285 disproved** — that denominator was a
   different command whose growth did not track the subject; **this one is the same
   query, same corpus, same window, and scales identically by construction.**
3. **What the port is paying for** — exact regex semantics where the branch
   deviates, and the mandatory confirmation pass. ***A ceiling with no account of
   what it buys is a number someone will try to tighten.***

*And at `broad literal miss`: at 0.550 it is the thinnest advantage, **so it is both
the row most likely to catch a real regression and the row with least room. As an
absolute it was the row that could not discriminate at all; as a ratio it
discriminates by construction and is the most valuable of the six.***

**`parity-finisher` lands them; `g5-runner` re-runs check 11 after.**

## ⚠⚠ L340. THE PERF GATE WOULD HAVE MEASURED PYTHON AGAINST PYTHON

**`tests/test_search_perf.py` invokes `["uv", "run", "ch", …]`.** **`.venv/bin/ch`
still hands search to the private Python entry** — re-measured rather than quoted: a
copy alone in a directory exits 1 with *"Cannot start the private ch legacy entry"*,
both files unchanged since 2026-08-28 15:33.

**⚠ Written against the launcher, every ratio would have been about 1.0 against
ceilings near 0.1 — SIX ROWS RED for a reason unrelated to the port**, and the next
reader would have called it a regression.

***This repo already carries that exact defect on its record — "the contract suite
binds the wrong installed ch binary" — and it was about to be committed a second
time, in a new file.***

**The numerator is `target/release/ch`, settled by check 14: byte-identical to the
`ch` in the wheel, so it is the shipped artifact. Nothing else qualifies.**

### RULED: an explicit refusal, never a fallback

**When the binary is missing or stale the gate REFUSES.** *A silent fallback to the
launcher makes the gate pass by measuring the wrong thing — the same failure in a
new place.* L193's controlled case stands: a tool that **printed** was ignored for
hours; one that **refused** was obeyed in seconds.

*Arithmetic checked rather than trusted, which is what putting both inputs in the
table is for — 0.032×2.00=0.064, 0.568×1.25=0.710, 0.405×1.25=0.506,
0.109×1.25=0.136, 0.444×1.25=0.555, 0.445×1.25=0.556. **All six match.** The table
doing its job on the day it was built rather than in six months.*

*And note 2 lands cleanly: the two ratio rulings do not contradict. **L285's
denominator was a different command whose growth did not track the subject —
measured drift 1.04 → 1.54 across an 8× pool.** L338's is the same query, same
corpus, other route, same window, scaling identically by construction.*

**`parity-finisher` reports 75% of the context window — the first such reading the
harness has volunteered to that seat all session, and the quantity that binds.**
Landing is transcription; **stop at the landing if it turns, not mid-gate.**

## ▶▶ L341. THE SIX CEILINGS ARE LANDED — and the guard fired for the wrong cause

**All six ratio ceilings and the six row notes are in `performance_gates.py`
verbatim, with the refusal. Nothing re-measured, no ceiling adjusted.**

### ⚠⚠ The landing was not a transcription, and the reason was the guard

**The native-binary refusal was written using THE ABSENT LITERAL the gates measure —
and it refused `target/release/ch`.**

***A successful `search zqxjvwmkbphfgd -ll` finds nothing, so it exits 1 with no
output: byte-for-byte the verdict a delegating binary gives, for the opposite
reason.***

**The probe is now `search . -ll`, which matches every session in the corpus, and
the reason is written at the guard so nobody re-picks the absent literal for
symmetry with the gates.**

**⚠ AND IT WAS CATCHABLE ONLY BECAUSE `g5-runner` SENDS DIGESTS WITH NUMBERS.**
`47fa603892be92e8`, 7,588,720 bytes. **Against an unknown binary the seat would have
read its own false refusal as a finding and reported a delegating artifact that was
not one.** *A habit paying for something it was not built for.*

***A guard that fires proves it fired, not that it fired for the modelled cause*** —
said about other people's gates all week, **landing inside a guard written to
enforce it, on its first run.**

**Both directions verified:** `target/release/ch` accepted, `.venv/bin/ch` refused
with the private-entry error. **Freshness IMPORTED, not copied** —
`_reject_foreign_launcher` from the contract tests, **with the note that a second
drifted copy caused this morning's 21 errors and a third would be the same fault
queued.** *The same defect refused a third time in one day.*

**Arithmetic reproduced from `worst × margin`, all six matching. `help` measured
alone end to end: 0.032 against its 0.064 ceiling, reproducing 0.030 inside the band
the two windows agreed to.** `colored matches` deliberately not duplicated — minutes
for a number that is `g5-runner`'s to produce.

**Recorded verbatim at the rows, because a reader in three months cannot ask:** the
branch provenance with its quoted line; why this is not the disproved construction,
**with the measurement behind it — 1.04 → 1.54 across an 8× pool, because that
denominator was a different command**; what the port buys; **why `help` earns 2.0×,
with its 1.29× spread at the row**; the widen-only-with-a-recorded-measurement rule;
**and that these gates are TIME ONLY, the port being worse on memory at +576 MB
against +451 MB.**

*`parity-finisher` at 75%, standing by, with room for one bounded item and not for
an open-ended one.*

## ⚠⚠ L342. A DATE-BLIND SORT COLLAPSED FOUR DAYS INTO ONE EVENING

**`g5-runner` reported the binary was two files stale, then corrected themselves to
five files with someone still editing. The correction was wrong and the original
was right.** Measured with full dates:

    now                     2026-09-01 21:35:57
    target/release/ch       2026-09-01 21:00:10
    rust/terminal.rs        2026-09-01 21:04:03   <- newer
    rust/search_output.rs   2026-09-01 21:01:19   <- newer
    rust/search_run.rs      2026-09-01 21:00:04   <- 6s older, in the binary
    everything else         2026-09-01 17:54:30 or earlier

**`rust/search.rs` and `rust/search_engine.rs` are from AUGUST 28.**
`search_engine.rs` at **21:33:45 is four days old and looked like ninety seconds ago
because its CLOCK TIME is close to now.**

**The mechanism: a sort keyed on the time field with the date field ignored, so four
days collapsed into one evening.** ***The `tail -5` class again — an instrument
silently reordering, producing a plausible list, believed for one message.***
*Caught in seconds this afternoon because the seat already knew that instrument;
this one wore a different coat.*

### ⚠ AND THE DIRECTION IS UNUSUAL: a correction that was wrong

**The first message was measured correctly. The second was measured with a broken
sort — and was sent with MORE confidence than the first.**

***A correction is not self-verifying. It needs the same instrument check as the
claim it replaces.***

**Both messages were reports rather than actions, which is what let it be caught.**
*The seat declined to rebuild on its own judgement twice, and the second declining
was for a reason that did not exist.*

**Ruled: the tree has been quiet for thirty-two minutes. Announce, rebuild,
re-derive both digests, run check 11.**

### The freshness guard's limit — untouched by the above, and a bounded item

**`_reject_foreign_launcher` ACCEPTS a binary that is two files stale.** Correctly:
**it is a probe-string agreement test, proving the binary is neither foreign nor
from a different feature set. It cannot prove the binary includes the latest edit to
an arbitrary file, because a change touching no probe string is invisible to it.**

***"The freshness guard passes" does not mean "the binary is current", and check
11's subject can be stale while every guard is green.*** **A limit of the
instrument, not a fault in it — the same distinction as the loader trace.**
Being written at the guard by `parity-finisher`.

### L343. The mtime disagreement, settled by a date-aware measurement

    find rust -name '*.rs' -newer target/release/ch
      2026-09-01 21:01:19  rust/search_output.rs
      2026-09-01 21:04:03  rust/terminal.rs
      (nothing else)

    rust/search_engine.rs   2026-08-28 21:33:45
    rust/search/parse.rs    2026-08-28 21:11:44
    rust/search.rs          2026-08-28 21:08:27

**Exactly two files. All three others are FOUR DAYS OLD** and read as minutes
because their times-of-day sit near now — **the same coincidence twice in a row.**
*The untracked hypothesis was not the difference: nothing on this mission is
committed, so every new Rust file is untracked. **One reading carried the date and
the other did not.***

**`search-firstmate` withdrew nothing; `g5-runner`'s "you acted on a number and the
number was wrong" is withdrawn instead.**

### ▶ THE STANDING PROCEDURE FOR ANY BUILD ON THIS CHECKOUT

**Record the tree digest immediately before the build and immediately after. If they
match, the binary corresponds to exactly that tree state — whoever touched what and
when. If they differ, the run is void and the runner says so.**

***That answers by measurement what a timestamp only answers by inference*** — and
it is why proceeding was correct even while the mtime question was open. Digest
before: `63a34f4f26451d0c`, stable across three reads spanning two minutes.

### ⚠ L344. The guard's limit — and the class landing in the prose of the person who named it

**`verify_subject_freshness` ACCEPTS a binary two files stale.** Correctly: **it is a
probe-string agreement test.** Its docstring said *"a stale artifact fails for what
it lacks"* — **true only for staleness that removed or added a probe string.**

***That is L330's class arriving in the prose of the seat that recorded it, within
the hour: a claim true under a precondition it does not name.*** **They wrote the
rule about someone else's comment and then wrote one.** *Not a lapse — the
strongest evidence the class is real, because the person most primed to avoid it
did not.*

**The note states all of it**, including that **`verify_native_subject` cannot see
it either** — a stale native binary still serves a search on its own, **so neither
guard covers this.** *A limit stated for one guard and left implicit for its
neighbour would have been half a note.*

**RULED: no mtime check is added, on the seat's own reasoning.** ***A refusal that
can fire on a touched file is worse than a stated limit*** — `touch` changes mtime
without changing content, **and this file refuses rather than warns, so a spurious
refusal is expensive in a way a spurious warning is not.** **What closes the gap is
build order, not a check: rebuild, then measure, in one window** — recorded at the
guard.

*L333's rule completed rather than applied twice: the last count in that file is
gone. **"That list has grown three times and the number went stale every time"** —
and it was the rulings section, **the one place a stale count makes a deliberate
decision look like an omission plus a miscount.** Third heading to lose one, and
the last that held one. **The declined mtime check now sits there as a ruling rather
than an absence**, with both reasons and with what actually closes the gap.*

## ▶▶ L345. CHECK 11 IS GREEN — all six shapes, and the falsify hole closed by construction

*Run valid, not void: tree digest `63a34f4f…` **identical before and after the
build**; oracle `dd6ab701…` unchanged. **New binary `1f76081cd87a2808`,
7,588,272 bytes, built 21:37:07** — different from `47fa6038`, **confirming
`terminal.rs` and `search_output.rs` really were missing from the artifact nearly
measured.***

    help                          0.033x  vs 0.06x  PASS   (6ms vs 190ms)
    broad literal miss, id-only   0.552x  vs 0.71x  PASS   (258ms vs 467ms)
    broad list, absolute date     0.397x  vs 0.51x  PASS   (971ms vs 2448ms)
    colored matches               0.108x  vs 0.14x  PASS   (2340ms vs 21634ms)
    selective literal, id-only    0.435x  vs 0.56x  PASS   (907ms vs 2087ms)
    broad regex miss, id-only     0.433x  vs 0.56x  PASS   (1637ms vs 3783ms)
    three memory budgets          450MB / 598MB / 491MB     PASS

**⚠ THE FALSIFY HOLE CLOSED IN THE SHAPE IT WAS MEANT TO.** Every shape now fails
against the reference — 1.021, 1.001, 1.004, 1.000, 1.008, 1.005, **all at ~1.0 by
construction and all above their ceilings.** **`broad literal miss` passed its
750 ms absolute on the Python route at 462 ms and now fails at 1.001 against 0.71 —
same shape, from proving nothing to proving the most.**

### ⚠ A property nobody designed for: the ceilings are not overfitted to their artifact

**Derived on `47fa6038`, passing on `1f76081c`, a rebuild containing two changed
source files.** Measured 0.033/0.552/0.397/0.108/0.435/0.433 against derived
0.030/0.550/0.404/0.109/0.438/0.434. **A third independent window, still ~2%, on a
different binary.** ***That is exactly what a re-derived ceiling is most at risk of
being, and it was obtained without designing for it.***

## ⚠⚠ L346. CHECK 12's DEFERRAL HAS EXPIRED — the install is a captain decision

**`performance_gates.py` covers checks 11 and 12 in one command, so "the command
exited 1" and "check 11 failed" are different statements and only the first is
true.** ***Do not let the exit code be read as check 11.***

**Check 12: +576 MB against +446 MB, 1.29×** — the documented figure to three
digits, mechanism resolved, **unattributed**, control passing at both arms near
zero, so the gate is working.

**⚠ The record deferred it "awaiting an allocation profile" and ruled it "its own
task, not part of B1". CHECK 13 IS THAT ALLOCATION PROFILE. It has run and
FALSIFIED the hypothesis.** **The condition the deferral waited on has been met and
produced no explanation — so it reads as settled and is not.** *A ruling whose
condition expired reads as an open offer; the fifth time on this mission.*

**RULED: check 15 holds and the install is not authorised by this desk.** The runner
was right to insist: ***a real, measured, unexplained memory regression must not
travel without someone having said out loud that it is accepted.*** **They offered
no product view and refused to let an exit code stand in for a decision.**

**Two figures requested before it goes up:** **the crossover as a product sentence
— below roughly 30 MB of payload the native route uses LESS memory (95 MB against
140 MB at 8 MB) and above it more, so "1.29×" alone implies a uniformity that does
not hold** — and **the payload size of a typical real session, if the corpus can
say**, which decides whether most users sit above or below the crossover. *An
honest gap is preferred to an inferred number.*

## ⚠⚠ L347. REFRAMED: ON THE REAL CORPUS THE PORT USES ~40% OF PYTHON'S MEMORY

**`search-firstmate` told the captain the install "ships a real, measured,
unexplained memory regression". THAT SENTENCE IS WRONG and is corrected.**

**Check 11's own memory budgets had already measured both routes over the real
corpus, in the same window as the timings:**

    shape                        native   python   native/python
    selective literal, id-only    450MB   1141MB       0.39x
    broad list, absolute date     598MB   1459MB       0.41x
    colored matches               491MB   1435MB       0.34x

**A 2.5× IMPROVEMENT, not a regression.** *Python's figures come from the
`--falsify` half of the same run — one window, not two.*

**⚠ THIRD TIME TODAY AN ANSWER WAS SITTING INSIDE A RESULT ALREADY REPORTED** — the
260 intended reds, the launcher-provenance binary kept for the guard, and now this.
***A figure produced as a by-product is not being read.***

### The two measurements are not the same question

**Check 12's +576 MB against +446 MB is the OVERSIZED-LINE PARITY PROBE**: one
synthesized session with an agent marker and a deliberately oversized final line —
**a pathological shape chosen to expose allocation behaviour, not a session anyone
has.** The 40% is peak over the actual corpus.

***The honest sentence: the port uses substantially less memory than Python on real
work, and more on a synthetic worst case that 0.86% of real sessions approach in
size.***

### The crossover as a product sentence, and the corpus against it

**Below ~30 MB of payload the native route uses LESS memory; above it, more.**
At 8 MB, **95 MB against 140 MB** — the native route wins by a third. At 32 MB they
are level, 311 against 310. At 96 MB, 887 against 755. **The native fixed cost is
21 MB against Python's 82; it loses only on slope.**

    695 real sessions, 1,129 MB total
    median 0.54 MB   mean 1.62 MB   p90 2.82 MB   p95 5.54 MB   p99 22.00 MB   max 83.29 MB
    over  8 MB:  26 sessions  (3.74%)
    over 30 MB:   6 sessions  (0.86%)

**⚠⚠ THE READING BUILT ON THIS TABLE IS WITHDRAWN — SEE L348. The file-size
threshold was the wrong axis: the port is heavier than Python on id-only scanning at
EVERY size measured. "99.14% below the crossover" was a true statistic answering a
question nobody was asking.** *Table kept because the sizes are correct and the
inference was not.*

### ⚠ THE GAP, STATED RATHER THAN INFERRED

**The slope model has NOT been shown to transfer from the synthetic oversized-line
shape to a real 30 MB session spread across many lines.** ***A 30 MB session and a
30 MB single line are not obviously the same load, and the crossover was derived
only on the latter.*** **So "99.14% are below the crossover" is a claim about file
sizes against a threshold measured on a different shape.** *The 40% corpus figure
has no such gap — it is measured on the real thing.*

**Ordered before this goes up: peak memory on the six real sessions over 30 MB.**
**If they behave like the synthetic shape, say so; if they do not, the crossover
does not transfer and the footnote shrinks further. Either answer is usable; an
unmeasured one is not.**

## ⚠⚠ L348. THE CROSSOVER TRANSFERS — and the six real sessions give OPPOSITE answers by shape

    session   scan + confirm (. -ll)        full render (. coloured)
       MB     native  python  nat/py        native  python  nat/py
     34.6M      89M     56M   1.59x          126M    325M   0.39x
     37.9M      98M     56M   1.75x          139M    446M   0.31x
     41.7M     113M     56M   2.01x          155M    426M   0.36x
     47.2M     105M     56M   1.88x          154M    315M   0.49x
     61.9M     155M     56M   2.75x          218M    671M   0.32x
     83.3M     192M     56M   3.39x          276M    892M   0.31x

**⚠ THE FINDING IS PYTHON'S COLUMN, NOT THE PORT'S. On id-only scanning Python's
peak is FLAT at 56M from 34.6 MB to 83.3 MB — it does not grow at all. The native
route grows with the session, 89M to 192M, so the ratio climbs monotonically to
3.39× and would keep climbing.**

***That says the port's extra copies are a PER-SESSION ACCUMULATION rather than a
constant overhead*** — **a sharper starting point for checks 12 and 13 than two days
of synthetic probing produced.** *Streaming versus materialising is the obvious
reading and was deliberately NOT claimed: measured behaviour stated as measured
behaviour.*

**On full rendering it reverses decisively — 0.31–0.49× while Python climbs to
892M.** **So the 40% corpus figure is not wrong; it is a rendering-weighted answer.**

### ⚠ The "footnote" read is WITHDRAWN by the seat that offered it

***"The file-size threshold was the wrong axis."*** **The port is heavier than
Python on id-only scanning at EVERY size measured.** **The question is not how many
sessions exceed 30 MB — it is which shape the user is running, and `-ll` is a
headline flag, not an expert one.** ***"99.14% below the crossover" was a true
statistic answering a question nobody was asking.***

*Second withdrawal today of a judgement that flattered the outcome, by the person it
flattered. **A judgement withdrawn by the one who benefits from it is the only kind
that costs anything.***

### What is genuinely reassuring: the absolutes

**Worst native figure anywhere: 276M**, on a full coloured render of an 83 MB
session. **Worst scan figure: 192M.** **Neither is alarming on any machine this
product runs on, and 0.86% of sessions are even in this range.**

***The ratio is bad and the absolute is small, and both are true. The captain gets
the 3.39× and the 276M in the same sentence, because either alone misleads.***

**Corrected read, from the runner: not a blocker, and not the footnote they called
it — a real, size-dependent memory regression on one common shape, with a benign
absolute ceiling.**

## ▶▶ L349. CAPTAIN DECISION: INSTALL AUTHORISED. Scan-memory regression accepted as non-blocking.

**Authorised 2026-09-01. `g5-runner` installs once, re-derives both digests, re-runs
check 15, and builds or installs nothing else until it reports.**

### ⚠ Recorded together in G5 and the change log — ratio AND absolute, never one alone

**Accepted:**

- **The adverse scan ratio: up to 3.39× Python on id-only scanning, climbing
  monotonically with session size** — Python flat at 56 MB, native 89 MB → 192 MB
  across 34.6–83.3 MB sessions.
- **Worst scan absolute: 192 MB. Worst overall: 276 MB**, on a full coloured render
  of the corpus's largest session.
- **Full coloured rendering uses about one-third of Python's memory** — 0.31–0.49×,
  where Python climbs to 892 MB.
- **Every timing shape is 1.8× to 33× faster.**

***The gate is NOT hidden and NOT restamped.*** **Either number alone misleads: the
ratio is bad and the absolute is small, and both are true.**

## ▶ NAMED FOLLOW-UP: scan-memory per-session accumulation

**Trigger: after the deletion slice. Not current completion scope.**

**The diagnostic is the starting point and it is sharper than anything the synthetic
probe produced in two days: on id-only scanning Python's peak is FLAT at 56 MB
across sessions from 34.6 MB to 83.3 MB, and the native route's grows with the
session.** ***So the extra memory is a per-session accumulation, not a constant
overhead*** — which is what checks 12 and 13 were trying and failing to attribute
against a synthesized oversized line.

**What was deliberately NOT claimed and is the first thing to test: streaming versus
materialising is the obvious reading and has not been measured.**

**What this retires:** the oversized-line probe as the primary instrument. **It is a
pathological shape nobody has, and it sent two checks after a mechanism the real
corpus describes better.** *Check 13's falsified prediction — the slope not moving
at all — was a true answer to a question asked on the wrong shape.*

**And the axis to keep: the question is which SHAPE the user runs, not how large
their sessions are.** *"99.14% of sessions are below the crossover" was a true
statistic answering a question nobody was asking.*

## ▶▶▶ L350. G5 IS CLOSED. 15 of 15 run, 13 green, 2 red and accepted.

**Green:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15.
**Red and accepted with their numbers:** 12 and 13 — the per-session accumulation,
now carrying a named follow-up and a sharper diagnostic than the synthetic probe
produced.
**Nothing was relaxed, no expectation restamped, and the one gate defect found
(`--falsify`) was closed BY CONSTRUCTION rather than by a margin.**

### ✅ Check 15 — the shipped artifact is the one measured

    wheel            1f76081cd87a2808e0f6eed0407b98149e0e7212c4b4cedd7f16c529bd8e512f
    ~/.local/bin/ch  1f76081cd87a2808e0f6eed0407b98149e0e7212c4b4cedd7f16c529bd8e512f

**Full sha, not a prefix, because this is the row that exists to catch a near-miss.**
**The wheel was rebuilt from a purged `build/` and `dist/` after the earlier one was
found stale — the check would have PASSED against `47fa6038` and proved the wrong
thing.** Installed once, via `uv tool install --force`. **Digests identical before
and after: tree `63a34f4f26451d0c`, oracle `dd6ab701…`. The install moved neither.**

**Check 10 re-run on the INSTALLED artifact, not a build-tree copy:** alone, no
sibling, stripped `PATH` — **search exit 0, 934 bytes, 31 escape runs; `info --help`
exit 1.** *The thing users actually run passes check 10 by itself.*

### ⚠⚠ THE HAZARD MATERIALISED AND THE GUARD FIRED

**This morning `~/.local/bin/ch` was `22236c08`, Python-delegating, and the
reference for checks 3, 5, 6, 7 and 11. It is now `1f76081c`, the native route.**

    check 3 verify against .venv/bin/ch-legacy   -> 82 stored, 0 drifted, 0 new
    check 3 verify against ~/.local/bin/ch       -> REFUSES, exit 1
        "the reference is not the one these answers were frozen against
           frozen against c1821a3a86ee9a88
           given          1f76081cd87a2808"

**`.venv/bin/ch-legacy` untouched at `c1821a3a86ee9a88` — installing does not reach
it, which is the entire reason the move mattered.**

***Predicted this afternoon, reference moved, refusal built and falsified against a
hypothetical — and tonight the hypothetical became the real installed path and the
refusal fired on it, naming both identities. A guard built for a predicted event,
catching that event, inside the same day.***

## ⚠⚠ L351. THE ENUMERATION IS THE LAST GATE BEFORE DELETION

**Commissioned from `g5-runner`: every instrument that consults the Python search
authority, each with a status — last consultation STORED, or not.** *Decision 6
stated as a list rather than a principle.* **Nothing is deleted until it is ruled
on.**

**⚠ AND ONE ENTRY IS ALREADY KNOWN NOT TO BE STORED, BECAUSE IT WAS BUILT TODAY: the
six ratio gates take their denominator from `ch-legacy search` LIVE.** **The charter
keeps `ch-legacy` for default parsing and unscoped commands but deletes the Python
SEARCH authority — so the denominator goes and the gates cannot run.**

***Ratio gates were chosen this afternoon precisely because they do not rot, and
they depend on an oracle scheduled for deletion.***

**Not to be solved by the runner — measured and brought up.** **The honest answer
may be that ratios cannot survive the deletion at all**: a frozen Python timing
compared against a native timing on another machine next month is not a
measurement. **Whatever replaces them needs the ratio's evidence recorded as its
justification. That is a ruling, not an instrument change.**

**Required in the list:** every gate, probe, corpus and oracle that runs
`ch-legacy` or reaches `src/chats/` search code; **what it consults it for**;
**whether that consultation is already frozen — `frozen_reference.json`, the
stderr-colour baseline, the preserve-because-wrong baseline, the rule-colour oracle
and the contract corpus all are, confirmed rather than assumed**; **and what breaks
the day the authority goes.**

## ▶▶▶ L352. THE DELETION ENUMERATION — and three rulings before anything is removed

*`teammates/g5-runner/deletion-enumeration.md`, 116 lines. **Both of decision 6's own
named freezes verified on disk rather than assumed** — `frozen-oracle-age-colour`
15 files, `frozen-oracle-nfc-nfd` 13.*

**⚠ THE SCOPE DISTINCTION THAT ORGANISES THE LIST: `ch-legacy` IS NOT DELETED.** The
charter keeps it for default parsing and unscoped commands. **What goes is the
Python SEARCH authority — so an instrument running `ch-legacy parse` survives and
one running `ch-legacy search` does not. Same binary; the distinction is the
subcommand.**

**A. STORED — 9 artifacts, all confirmed on disk.** `frozen_reference.json`; the
454 `expected/` files over 227 cases; the preserve-because-wrong baseline; the
stderr-colour baseline (240 cases); the frozen differentials; the markdown oracle;
the rule-colour oracle; and decision 6's two named freezes.

**B. LIVE — dies at deletion.** Four contract-suite tests, **today's 0-of-72
`COLUMNS` sweep**, and **all four in `test_deliberate_divergences.py`.**

**⚠ The shape of the loss is worse than the count.** The contract suite runs its 227
cases twice — once against the stored files, once against live Python. **The stored
one survives; the live one dies. And the live one exists precisely to catch the
stored one going stale, so deleting the authority removes the check on the check.**

---

### ▶ RULING 1 — ratios become ABSOLUTES on the frozen corpus

**A frozen Python timing is not a denominator.** The ratio's soundness was *same
query, same corpus, same window, same machine*; a stored number satisfies none.

**⚠ But absolutes were retired because the LIVE POOL grew, and these gates run on
the corpus check 2 pins — 695 files, 1,183,541,907 bytes, digest `de693c35…`.**
***A frozen, digest-pinned corpus cannot rot from growth, which is the only thing
that killed the old absolutes.*** **Name the corpus digest at the gate as the reason
absolutes are admissible here**, or a reader sees absolutes restored and reads a
reversal.

**Derived tonight while both routes exist**, with the six measured ratios at their
rows as justification and **the Python numbers stored as historical evidence
explicitly marked NOT a denominator.** Margin from measured spread;
widen-only-with-a-recorded-measurement carries over.

**Rejected on measured grounds: a ratio against a surviving `ch-legacy`
subcommand.** `parse` outlives the deletion, **but a different command whose growth
does not track the subject is exactly L285's disproved construction, 1.04 → 1.54.**

### ▶ RULING 2 — `dd6ab701` stays re-derivable: the pre-deletion tree gets committed

**`tests/oracle_digest.py` digests the ROUTE — `src/chats/**/*.py` plus the entry
plus the installed RECORD. Deleting the Python search authority changes
`src/chats/`, so the oracle digest MOVES, and every artifact stamped `dd6ab701…`
becomes UNVERIFIABLE rather than wrong.** *Contents stay correct; stamps stop being
checkable.*

***Decision 3's failure from the other end: there a restamp turned unknown into
verified; here a deletion turns verified into unknown.***

**RULED: not a redefinition and not a re-stamp — make the route RECOVERABLE.
`search-firstmate` creates a checkpoint commit of the pre-deletion tree immediately
before the deletion**, under the charter's first-mate authority. **`dd6ab701` is then
re-derivable forever by checking out that revision.** **Record at each stamped
artifact: the revision, and that the digest is re-derived from it rather than from
the post-deletion working tree.** *Decision 3 completed rather than abandoned — pin
by route digest, and keep the route.*

### ▶ RULING 3 — the stored halves are accepted, with two conditions

**Accepted, because after the deletion there is nothing for the stored half to go
stale AGAINST.** Its purpose changes rather than weakens: from *"does the port still
match Python"* to *"does the port still do what it did on the day Python was
deleted."* **That is the cutover's definition, not a concession.**

**Condition 1: the last live run of every twin is EXECUTED AND RECORDED immediately
before deletion.** *On date X, at oracle digest `dd6ab701`, the live check passed —
that sentence is the consultation being stored.*

**Condition 2: the degradation is written AT each frozen twin — what it asserted
before and what it asserts after.** **`test_deliberate_divergences.py` gets the
sharpest form: frozen, it can only assert the port still produces what it produced
today; it can no longer assert that the difference from Python is still exactly
those six.** ***Without that line a reader in six months believes the gate is
stronger than it is.***

**Nothing is deleted until the checkpoint commit exists and the final live pass is
run and recorded.**

## ▶▶ L353. SIX ABSOLUTES DERIVED WHILE BOTH ROUTES EXISTED — all six discriminate

*Nine repetitions each, every one recorded. Ceiling = worst × margin, rounded **up**
to 5 ms. Spec at `teammates/g5-runner/perf-gate-absolutes.md`.*

    shape                        native med   worst  spread  margin  CEILING   python   headroom
    help                              5.3ms    8.2ms  2.02x   2.00x     20ms     199ms     9.94x
    broad literal miss, id-only     253.5ms  256.1ms  1.02x   1.25x    325ms     464ms     1.43x
    broad list, absolute date       967.7ms  990.0ms  1.03x   1.25x   1240ms    2410ms     1.94x
    colored matches                2300.4ms 2343.3ms  1.02x   1.25x   2930ms   21539ms     7.35x
    selective literal, id-only      904.8ms  985.2ms  1.10x   1.25x   1235ms    2080ms     1.68x
    broad regex miss, id-only      1628.1ms 1649.5ms  1.02x   1.25x   2065ms    3782ms     1.83x

**Every ceiling is below the Python route's time, so all six discriminate.** Corpus
digest `de693c35…` named at the gate as the reason absolutes are admissible.

### ⚠ Two faults in the first derivation, and the second would have shipped a hole

1. **Rounding to NEAREST put `help`'s ceiling at 5 ms — below its own worst run of
   5.8 ms. The gate would have failed a working product.** Ceilings now round up.
2. **⚠ One contended run of 490 ms against a 260 ms median drove `broad literal
   miss` to a 980 ms ceiling. Python does that work in 464 ms.** ***A ceiling above
   the reference discriminates nothing — the exact hole ratios were adopted to
   close, walking back the moment absolutes returned.*** Nine reps show 251–256 ms
   at 1.02× spread; **the 490 ms was the machine.**

***A 3× difference in a ceiling from a single run nobody would have seen*** — which
is why every repetition is printed. **Opposite failures from one rounding rule and
one outlier.**

### ▶ RULED: the risk becomes a MECHANISM, not a note

**Every ceiling must be below the recorded Python figure for its shape, asserted in
the gate, failing loudly.** The historical column is already present, **so the
assertion is free.**

***The cost of ruling 1, named by the seat that was given it: an absolute generous
enough to absorb a noisy machine can quietly stop discriminating, and a ratio could
not.*** **It was caught by hand once; the next person widening a row after a flaky
night will not — and widen-with-a-recorded-measurement does NOT stop a correctly
measured widening that crosses Python. The assertion does.**

### ⚠ The table that answers "were the ceilings relaxed"

    help                 25ms -> 20ms     tighter
    broad literal miss  750ms -> 325ms    tighter, 2.3x
    colored matches    4000ms -> 2930ms   tighter
    broad list          650ms -> 1240ms   LOOSER — the only one

**Three of four surviving absolutes get TIGHTER. Exactly one loosens** — `broad
list`, the shape that was failing, against a budget derived from the branch.
***A correction that tightens three ceilings is not a relaxation, and the table is
the argument rather than the prose.***

**The live ratios sit at the rows as justification — 0.033/0.552/0.397/0.108/0.435/
0.433 — with the Python column marked HISTORICAL EVIDENCE and explicitly NOT a
denominator.** *Taken while both routes existed; they can never be retaken.*

*`broad literal miss` has now changed character three times: it proved nothing at
750 ms, became the most valuable of six as a ratio, and at 325 ms with 1.43×
headroom is the sharpest and thinnest absolute. **Same shape, three instruments,
three roles.***

## ▶ ORDER TO THE DELETION — nothing skips

**1. The absolutes land.  2. `g5-runner` runs and records the final live pass on
every twin.  3. `search-firstmate` makes the checkpoint commit.  4. The deletion.**

***The final pass is the consultation being stored, so it happens with both routes
alive and its result is written down before anything is removed.***

## ▶▶ L354. THE ABSOLUTES ARE LANDED, AND THE HOLE CANNOT OPEN

**`verify_ceilings_discriminate` runs BEFORE anything is measured, beside the corpus
refusal** — *a check that runs after the measurements is read after the numbers, and
by then the numbers have been believed.*

    REFUSING: a ceiling at or above the route it replaces proves nothing.
      broad literal miss, id-only: ceiling 980ms is not below Python's 464ms
    Both routes would pass that row. Re-derive it; do not widen it.

**Falsified against the exact 980 ms ceiling that prompted it, and the message names
the remedy — the one that would otherwise be skipped.**

**Headroom over the historical Python figure printed at each row: 9.95× / 1.43× /
1.94× / 7.35× / 1.68× / 1.83×.** All six ceilings reproduce from `worst × margin`
rounded up. **Two rows run to prove the runner rather than re-measure — `help`
4.5 ms against 20, `broad literal miss` 266.8 ms against 325. The sharpest row
passes with the thin margin it is supposed to have.**

### ⚠ THE LINE THIS DESK HAS BEEN CIRCLING FOR THREE DAYS

***The docstring now says the hole CANNOT OPEN, rather than that `--falsify` will
catch it. A mechanism where there was a check.***

**The assertion restores `--falsify`'s meaning for absolutes**, which the ratio form
had carried by construction: **the whole set run against the reference can only fail
on every shape while every ceiling sits below what that route costs.**

### Three extras, each declared

**The module docstring described RATIOS and was rewritten** — otherwise the ninth
false comment on this mission, **and the second that seat has caught in its own
prose after naming the class.** *And it does the harder thing than deleting: it says
the gates passed through a ratio form for one afternoon and came back, and why both
moves were right for their moment.* ***A reader finding only the current form would
read the round trip as indecision*** — the kind of thing that gets "fixed" back.

**`interleaved_medians` is unreachable and KEPT, with the reason at the function in
both directions.** **It consumes two live routes, is dead by construction at
cutover, and produced the six recorded ratios that can never be retaken.** *It stays
beside them; the note stops both the tidying and the misuse.*

## ▶ THE FINAL LIVE PASS IS RUNNING — the consultation being stored

**Recorded in the form it will be read in, for each twin: on 2026-09-01, at oracle
route digest `dd6ab701…`, against `.venv/bin/ch-legacy`, this live check passed** —
with artifact identity and tree digest. **All of enumeration section B: four
contract-suite tests, the `COLUMNS` sweep, and all four in
`test_deliberate_divergences.py`.** **The degradation is written at each frozen twin
as it goes.**

**Then the checkpoint commit. Then the deletion.**

**⚠ AND THE DELETION HAS NO SEAT.** `parity-finisher` at 75% declined it before it
was offered and was right to; `cutover-finisher` is closed at 91%; `g5-runner` runs
and reports rather than edits. **A roster question for the captain.**

## ⚠⚠ L355. PLACEMENT IS PART OF THE RETRACTION

*`parity-finisher`'s tenth and final whole re-read — all 800 lines, not the parts
touched — found four drifts. **Nine of ten re-reads have now found something.***

**The one that generalises: a claim was corrected FORTY LINES BELOW ITSELF, IN THE
SAME SECTION.** ***A reader meets the wrong claim first and has no reason to keep
reading to the correction.*** **Correcting something later in the same document is
not correcting it.** The claim now carries **a forward marker at the point of first
contact.**

**⚠ APPLIED TO THIS FILE IMMEDIATELY, because it had the same defect twice.** L305's
`-d` claim sat **157 lines** above its L310 retraction with no marker, and L347's
crossover table sat above its L348 withdrawal with none. **Both now carry a forward
marker where a reader meets them.** *This file's own header promised that
convention and it was not being applied.*

### The other three drifts, and the first is about this conversation

**⚠ The file opened with *"Context: no reading. The harness has volunteered no
context figure this session."* It volunteered 75% during the ceilings landing and
was reported three times after.** **The document kept asserting the absence to any
reader arriving cold — a statement true when written and stopped being true, the
class this very file records, in its own first eight lines.**

**The status block still had `g5-runner` localising a check 11 regression** that had
become two landings ago. **It now records that the deletion slice was never offered
and would have been declined at that level — as a RULING rather than an omission**,
*because otherwise it reads as the thing nobody got to.*

**And the last count in a heading is gone** — fourth in that file, and the last that
held one.

### `parity-finisher`'s seat is closed

*Five configurations green, 272 lib + 56 doctests, zero failures. Tree
`7b3267a6a22e`, matching their own table exactly.*

***"A mechanism where there was a check"*** — the ceilings assertion, the capture's
refusals, `print_error` delegating instead of repeating, one authority for the rule
arithmetic. **Every one replaced a discipline someone had to remember with something
that fails loudly on its own.** **And the four rulings in *what is not done* are the
same move inverted: where a mechanism was not possible, the decision is written
where the work would have gone.**

*And on routing, from the seat: being told about the stderr mechanism is why the
stdout width defect was read as theirs in one step; being told their own list was
wrong is why they traced callers before editing. **Neither was reachable alone.***

## ▶▶ L356. THE FINAL LIVE CONSULTATION IS RECORDED — 373 comparisons, all passed

*`teammates/g5-runner/final-live-consultation.md`, 107 lines.*

**On 2026-09-01, at oracle route digest `sha256:dd6ab701…`, against
`.venv/bin/ch-legacy` at `c1821a3a…`, native route `1f76081c…`, corpus
`de693c35…`:**

    contract suite, four live twins    289 cases   289 passed, 0 failed
    COLUMNS sweep                       73 cases    73 passed, 0 failed
    deliberate divergences, all four    11 cases    11 passed, 0 failed

**Both digests re-derived after the run and identical, so the record is not void.
Full shas throughout. The installed launcher is byte-identical to the build, so this
describes the artifact users have.** **Step 2 closed.**

## ⚠⚠ L357. THREE TWINS HAVE NO SUCCESSOR AT ALL — and the degradation note found it

**`test_named_defect_patterns_select_the_same_sessions` and
`test_generated_patterns_select_the_same_sessions`** — pattern-selection parity, **no
stored twin, unasserted at deletion.** **`test_columns_sweep_reproduces_legacy`** —
today's 18 × 4 sweep at 0 differences over 72, **live-only, width parity under
`COLUMNS` unasserted at deletion.**

***A gate with no successor is not a weakened gate. It is a deleted gate — and
deleting a gate requires a reason nobody has given.*** The contract and colour twins
degrade to a stored baseline, which is the accepted trade. **These three stop
asserting anything, and that was never decided.**

**RULED: build frozen successors for all three, while both routes are alive.** All
three are **the same shape as the four captures already built today** — record
legacy's answers, assert the port reproduces them. *`test_columns_sweep` is the
stderr-colour baseline with a different matrix; the pattern pair is a stored set of
which sessions each pattern selects.* **Decision 6 read literally, sixth time in
three days.**

**Constraints carried over unchanged: each capture REFUSES rather than writes on an
empty result, a missing case or a short list** — *a recording that came out empty
must not look like a corpus* — **and each successor carries its degradation where it
is read.**

**Priority if context binds: the pattern pair.** *Python-compatible regex is the
deepest correctness surface on this mission, and the one place where losing the
assertion entirely would be hardest to notice later.* **Two captured and one recorded
as a named loss beats three started and one abandoned.**

### ⚠ It was found by writing the degradations, not by building the enumeration

***The act of writing down what CHANGES surfaced what DISAPPEARS.*** The enumeration
classified all three as live twins; **only the degradation note asked what each
one's frozen form would say, and two of them had no answer.** *Third time this week
an instrument produced its most useful output as a by-product.*

**The model degradation, for `test_deliberate_divergences.py`: frozen, it can only
assert the port still produces what it produced today. It can no longer assert that
the difference from Python is still exactly those six. A seventh divergence
appearing would be invisible. A case quietly agreeing would be invisible.** ***The
set was the assertion, and the set is what cannot be re-derived.***

**Order: the three successors → the checkpoint commit → the deletion.**

## ▶▶ L358. ALL THREE SUCCESSORS CAPTURED — 150 answers, refusal falsified five ways

**`tests/data/legacy-selection-baseline/legacy-selection-baseline.json`, 634,043
bytes.**

    defect-patterns      18   named defect patterns, `search <pattern> -ll` at 96 columns
    generated-patterns   60   seed 20260828, widths 52/96/110/140, coloured list
    columns-sweep        72   18 COLUMNS values x 4 shapes, TERM=dumb
                        150   total
    oracle  sha256:dd6ab701…    reference c1821a3a86ee9a88    revision recorded

**All three counts match what the live gates actually run — the successor covers the
same space rather than a convenient subset**, which is the difference between a
frozen gate and a souvenir. **Both streams AND the exit code stored for every
case**, since two of these gates assert on stderr and a stdout-only recording would
have silently dropped that half.

**The harness is IMPORTED, never copied** — `_run_search`, `_normalize`, `SHAPES`,
`COLUMNS_VALUES`, `_run`, the seed, the count, the widths, all from the live
modules. ***A hand copy grades the successor against a drifted definition of the
case, and both sides pass while measuring different things*** — the fault that cost
21 errors this morning. **Same defect refused a fourth time in one day.**

### The refusal, falsified five ways

    complete set                                          ACCEPTED  (control)
    one case short                                        REFUSED
    a whole group empty                                   REFUSED
    a group missing entirely                              REFUSED
    a case that cannot fail (exit 0, both streams empty)   REFUSED

**⚠ The fifth is the week compressed into one test case: *"a comparison that cannot
fail, recorded as if it could."*** *It would have looked like a corpus.*

### ⚠⚠ The second-order loss, named more honestly than this desk had named it

**The degradation is IN the file, as a field a reader meets BEFORE the data** —
*placement is part of the retraction, found on a handoff an hour earlier and applied
to an artifact without being told.*

**Its sharpest line, and it corrects `search-firstmate`'s framing:** *after the
deletion, the gate **can no longer detect that this recording was itself wrong,
because the route that would have said so is gone.***

***These successors were described as degrading from "matches Python" to "still does
what it did today". The second-order loss is that the recording's own correctness
becomes unfalsifiable at the same moment.*** **That is the general form and it
belongs at every frozen successor built today.**

### ▶ The boundary, ruled where the runner stopped

**`g5-runner` built the recording and stopped, unprompted, at the edge of a grant
they had not been given.** ***"The runner wrote the gate he then verified" is the
one sentence that would undo today's separation.***

**RULED their way: a capture probe is on the instrument side; the tests that assert
against it are not.** **`parity-finisher` writes the three assertions** — import the
harness rather than copy it, compare both streams and the exit code, each shipping a
falsifier that dies, and **point at the `degradation` field rather than restating
it.**

**Order: the assertions land → the checkpoint commit → the deletion.**

## ⚠⚠ L359. 15 OF 72 SWEEP ROWS ARE HOME-LENGTH DEPENDENT — the recording, not the assertions

**`tests/test_legacy_selection_frozen.py`: three gates plus two falsifiers, 75 of 93
assertions passing. The 18 failures are a defect in the RECORDING.**

**The `invalid-date` shape's stderr carries session paths. The output was wrapped at
the sweep width WHILE THE REAL PATH WAS STILL IN IT, and normalised to `{HOME}`
afterwards** — so the recorded bytes carry line breaks at positions set by the
record-time path length, **and a plain string replace cannot repair a break INSIDE a
path.** Replayed under a different `tmp_path`, the wrap points differ **even when the
product is byte-perfect.**

**Scope measured, not estimated: columns-sweep 15 of 72; defect-patterns 0 of 18;
generated-patterns 0 of 60.** *The other two groups emit session ids and no paths,
so they replay anywhere.*

### ▶ RULED: re-record the whole group under a fixed-length home. The workaround is rejected.

***A gate that cannot see wrapping is not a weaker version of that gate; it is a
different one that passes.*** **Collapsing whitespace inside paths before comparing
would remove the thing the sweep exists to prove** — `preserve-because-wrong`
item 9, two width resolvers composing correctly at every value. *The seat had the
cheap fix in hand, named what it would cost, and recommended against it.*

**All 72 rather than the 15, so the group is homogeneous rather than
mixed-provenance, with the fixed-home choice recorded AT the file** — *otherwise the
next person building a capture reaches for `tmp_path` because it is the obvious
thing, and this is the second time today a fixture's own shape has been the defect.*
Refusals unchanged; the other two groups stay as recorded.

**⚠ THE COMMIT IS HELD FOR THE WINDOW.** *These rows can only be re-recorded while
`ch-legacy` exists. If the deletion landed first, the `invalid-date` half would be
unrecoverable and the only choices left would be a gate that cannot run or no gate
at all.* **Raised without a request to hold — the fact given, the decision left
where it belongs.**

### Two things in the landing worth keeping

**The sweep is indexed on the recording's own `arguments` and `columns` fields
rather than on its key string.** The first attempt **reproduced their key format and
failed on `search|None`** — ***the same second-definition fault the import rule
exists to prevent, arriving in the one place that had to be written by hand.***
**The need for the second definition was removed rather than matched more
carefully** — the difference between fixing a copy and deleting one.

**The count falsifier checks BOTH sides:** that the live corpora still produce
18 / 60 / 72 **and** that the recording holds that many rows. **Neither a shrunken
recording nor a shrunken corpus passes quietly.** ***A count assertion that checks
only the stored side is exactly how a frozen gate dies without anyone noticing.***

*Harness imported never copied — `_run_search`, `_normalize`, `_run`, `SHAPES`,
`COLUMNS_VALUES`, the seed, count, widths and both home fixtures. All three streams
compared.*

## ⏸ L360. SOFT-PAUSE — admiral, 2026-09-01. Nothing is at risk.

**No hard aborts. No new work, gates, builds, installs, commits or deletion.
The checkpoint commit and the deletion are both blocked. Do not resume until the
captain says so.**

**⚠ THE WINDOW DOES NOT CLOSE DURING THE PAUSE, and both active seats were told so
before choosing a stop point.** The `columns-sweep` re-recording is time-critical
**only relative to the deletion** — it needs `ch-legacy`, and `ch-legacy` goes only
when the deletion happens, **which is itself blocked.** ***There is no reason to
rush the capture.*** *Left unsaid, that pressure is exactly what produces a partial
recording nobody can grade.*

**Captures refuse on a short or empty result, so a partial is safe by
construction.**

### Where it stands at the pause

**Closed and recorded, at no risk:** G5 — 15 of 15 run, 13 green, 2 red and
accepted; the install, with the shipped artifact byte-identical to the measured one;
the final live consultation, 373 comparisons all passed with both digests re-derived
after; the deletion enumeration with nine stored artifacts confirmed; the
degradations; the six re-derived absolutes with the discriminate-assertion; and
`legacy-selection-baseline.json` at 150 answers.

**Open, in order, and the ordering is the fragile part:**

1. **Re-record the whole `columns-sweep` group (72) under a fixed-length home** —
   `g5-runner`. **Needs `ch-legacy`.**
2. **`parity-finisher` re-runs `tests/test_legacy_selection_frozen.py`** — currently
   **75 of 93 passing, 15 of 72 sweep rows blocked on that re-recording.**
3. **`search-firstmate` makes the checkpoint commit** of the pre-deletion tree, so
   `dd6ab701` stays re-derivable and every stamp stays checkable.
4. **The deletion — which still has no seat.**

**Two things each seat was asked to make survive.** **The fixed-home decision
recorded even if its recording was not made**, so a successor does not rediscover
the `tmp_path` defect from scratch. **And that the whitespace-collapse workaround
was REJECTED and why** — *a gate that cannot see wrapping is not a weaker version of
that gate, it is a different one that passes* — **recorded as a ruling rather than
as an unfinished repair**, because someone with a red suite and a deadline reaches
for exactly that fix.

***Red for a known, measured, external reason is a different thing from red, and the
file should say which.***

**The pause costs nothing that was not already written down — which is the property
this desk has been building for three days.**

### ⚠ L360 CORRECTED — the re-recording is COMPLETE, not pending

**`legacy-selection-baseline.json`, 630,008 bytes, 150 answers — defect-patterns 18,
generated-patterns 60, columns-sweep 72. Oracle `sha256:dd6ab701…`, reference
`c1821a3a86ee9a88`. The whole sweep group re-recorded, so it is homogeneous.**

**The other two groups are BYTE-IDENTICAL to the previous recording** — *a self-check
that the fix reached only what it was aimed at, which is the question nobody asks
after a repair.*

**Falsified rather than assumed: all 72 sweep rows reproduce at a DIFFERENT home of
the same length** — `/tmp/ch-columns-sweep-ALTX/home` against
`/tmp/ch-columns-sweep-home/home`, **0 mismatches on stdout, stderr and exit code.**
***The length is the contract; the path is not*** — stated as a property rather than
demonstrated once.

**⚠⚠ IT WAS 16 ROWS, NOT 15, AND THE SIXTEENTH IS THE FINDING.** ***"Matching
lengths alone was never sufficient."*** **One row had already failed normalisation
outright, keeping a raw `/var/folders/…` path because the break landed INSIDE the
home rather than after it.** **Had only the reported fifteen been fixed, there would
be a second broken recording — and it would have passed, because the assertion that
caught the first was the one being repaired.** *A scope handed down was wrong and
was measured rather than worked to.*

**The capture now REFUSES any row still carrying a raw home path after
normalisation** — the fix and its guard in one, **so the class cannot return through
a different shape.**

**The fixed-home decision is recorded in two places — `RESUME.md` and at the field
in the recording itself — with the rejected workaround and its reason.**
***`tmp_path` is the obvious fixture for a capture and it is the defect***, said in
as many words. **Second time today a fixture's own shape was the fault.**

### ⏸ THE RESUME ORDER — three steps, and the ordering is the fragile part

1. **`parity-finisher` re-runs `tests/test_legacy_selection_frozen.py`** against the
   new recording. **⚠ THE 75-of-93 FIGURE BELOW IS SUPERSEDED — SEE L361. That seat
   was mid-edit at the pause and carries two open faults of its own.** *75 of 93
   passed against the old recording; the 18 failures were the defect now fixed.*
   **A gate run is a gate: this does NOT happen during the pause.**
2. **`search-firstmate`'s checkpoint commit — after step 1, so it captures passing
   gates.**
3. **The deletion.**

**⚠ STANDING INSTRUCTION, recorded here so it outlives the seat that gave it:
REFUSE THE DELETION until the frozen gates are green and the checkpoint exists.**

*Both seats idle. Nothing half-written; seven documents and one probe complete on
`g5-runner`'s desk. **The property this desk actually built is the reason a stop
mid-mission is a stop rather than a loss** — three days of writing things down where
they are read, tested by an interruption nobody chose.*

## ⚠ L361. CORRECTION — `parity-finisher` was MID-EDIT at the pause, not at a clean stop

**`search-firstmate` recorded both seats as idle with nothing half-written. That is
wrong for one of them.** After the new recording landed, that seat wired a
`fixed_length_sweep_home` fixture against it, ran once, and stopped there.
**The 75-of-93 figure predates that edit and is superseded.**

**Two open faults, both theirs, neither implicating the recording:**

1. **`ScopeMismatch`, erroring all 72 sweep cases.** The new fixture is
   `scope="session"` and requests `sweep_home`, which is module scoped. **The fix is
   to match the scope, not to widen theirs.**
2. **`defect-patterns` rows are recorded NORMALISED and compared as raw bytes.**
   `posix_class_future_warning` expects `{SEARCH_QUERY_SOURCE}:96: FutureWarning: …`
   and gets the unnormalised equivalent. **`_normalize` must be applied to both
   sides for that group, as the generated-patterns gate already does.**

**⚠ And whether fault 2 predates the re-recording is UNKNOWN and written as
unknown.** *It was not checked before the pause, and it is recorded as "I do not
know" rather than guessed — so a successor does not assume the re-recording caused
it.* ***An unanswered question and a "no" look identical from below.***

**The status block now says PAUSED MID-ITEM, and that "landed" does not mean
"finished" here** — the one place in that file where those differ, **said rather
than implied.**

### The rejection is recorded twice, and the second placement is the one that matters

**It was already in the section narrative. It is now item 5 of the rulings list in
*what is not done*, because that is where a successor with a red suite and a
deadline actually looks.** It states that the workaround makes every failing row
pass, that it stops the sweep seeing wrap differences, **that a gate which cannot
see wrapping is a different gate that passes**, and **that the ruling stands
unchanged through the pause.**

*Placement is part of the retraction — and it is part of a ruling too.*

**And the 16th row is recorded on that desk as its own diagnosis being one degree
understated**, with the consequence: **had only the reported fifteen been fixed, the
re-run would have gone green against a recording that was still broken, and the
assertion that would have caught it was the one being repaired.**

## ▶▶ L362. RESUMED — digests unchanged, and the checkpoint commit already exists

**Nothing moved across the pause. Verified by `search-firstmate` rather than taken
on report.**

    oracle route digest  sha256:dd6ab701…badcee0   UNCHANGED
    rust tree digest     63a34f4f26451d0c…         UNCHANGED
    .venv/bin/ch-legacy  c1821a3a86ee9a88
    target/release/ch    1f76081cd87a2808
    ~/.local/bin/ch      1f76081cd87a2808          byte-identical to the build

**`legacy-selection-baseline.json` untouched: 630,008 bytes, sha `4b69da31902febb1`,
counts 18/60/72, home length 31, 0 rows carrying a raw temp path.**

**⚠ THE TREE IS COMMITTED — `67d60532bb0d`, "Checkpoint native search Rust rewrite
WIP", 2026-09-02 12:18 +0300, 1,464 files, 890,358 insertions. Not by
`search-firstmate` and not by any seat.** `git status --short` went 117 → **0**.
**The deletion has NOT happened: `src/chats/commands/search.py` is present at 39,652
bytes, `.venv/bin/ch-legacy` is present, and the oracle digest proves the route is
intact.**

**Ruling 2 is discharged by that commit.** *It captured
`test_legacy_selection_frozen.py`, the baseline and the consultation record — the
gates are captured but not green, so ONE MORE checkpoint follows the re-run, for a
different purpose.*

## ⚠⚠ L363. NO ARTIFACT NAMES THE REVISION THAT MAKES `dd6ab701` RE-DERIVABLE

**The recording states `revision: 8cb4c5f79cf6` — and `8cb4c5f` predates every line
of this mission.** It was captured by `git rev-parse HEAD` **while the tree was
uncommitted**, so at the moment it was written **no revision could reproduce that
tree.** ***Honest and useless in the same breath.***

**⚠ A STALE REVISION IS WORSE THAN AN ABSENT ONE.** *A reader holding a digest, a
revision that predates the work, and no way to connect them is worse off than one
holding a digest and a blank — because the first will try the revision and conclude
the record is wrong.* **Correct it; do not add beside it.**

***Decision 3's whole point arriving at the last possible moment: pin by route
digest and keep the route — but a reader has to be told where the route is kept.***

### RULED

**Record `67d60532bb0d` in the recording and in `frozen_reference.json` now — it does
not wait for the re-run.**

**On the circularity: name the commit that CONTAINS THE ROUTE, not the commit that
contains the field.** *"`dd6ab701` is re-derivable at `67d6053`" stays true after
the field is added, because the claim is about that revision's `src/chats/`, not
about the artifact stating it.* **Non-circular, so it lands first.**

**⚠ The contract corpora and the stderr baseline belong to closed seats and are NOT
being re-opened for a field. Their mapping goes into `final-change-log.md` and here,
as a STATED gap:** ***these artifacts carry `dd6ab701` and do not name a revision;
the revision is `67d6053`.*** **A gap that is written down is navigable; one that is
not is a dead end.**

**Order: the revision field → `parity-finisher`'s re-run of all 93 → the second
checkpoint commit → the deletion → the post-deletion proof.**

## ⚠⚠ L364. `dd6ab701` IS **NOT** RE-DERIVABLE FROM `67d6053` — L363's ruling was a false claim

**Measured before writing, and the field was not written.** ***"Writing a provenance
claim I have not verified is the one thing this seat exists to prevent."***

    1. src/chats/**/*.py              31 files   IN THE COMMIT, byte-identical to the worktree
    2. .venv/bin/ch-legacy            321 bytes  NOT IN GIT — .gitignore:13 ignores .venv
    3. chats-0.1.0.dist-info/RECORD 1,062 bytes  NOT IN GIT

**Checking out `67d6053` gives 31 Python files and no venv.** So *"`dd6ab701`
remains re-derivable forever by checking out that revision"* **is false as stated,
and `search-firstmate` ordered it written into two artifacts as provenance.**
*Fourth time today a seat measured an instruction rather than executing it, and the
second time the instruction was the first mate's.*

### ⚠⚠ THE GENERAL FORM, and nobody had noticed it in three days

**The route digest exists BECAUSE a source-only digest is insufficient** — decision
3's own words: *"a `git diff` digest cannot see the launcher or the installed
RECORD, so a concurrent `uv sync` moves the oracle invisibly."*

***It was deliberately built to cover more than git can hold. It therefore cannot be
reproduced from git alone. The property that makes it a good pin is the property
that makes it unrecoverable from a commit.***

**Every artifact pinned that way has this shape.**

### ▶ RULED: store the 1,383 bytes, and prove the re-derivation before writing the field

***Naming lets a reader CHECK a candidate; storing lets them RECONSTRUCT one.*** For
1,383 bytes that is not a trade. **Seventh instance of cheap-now-impossible-after in
three days, and the cheapest by three orders of magnitude.**

1. **Store both under `tests/data/` with identities recorded** — `ch-legacy`
   `c1821a3a86ee9a88`, `RECORD` `863d603b8e2c49ed` — **and a note saying what they
   are and why.** *Two files that look like stray venv artifacts get deleted by the
   next person tidying.*
2. **Write the re-derivation PROCEDURE beside them**, not just the inputs: check out
   `67d6053`, restore these two to the paths the recipe reads, run
   `oracle_route_digest()`. **`oracle_digest.py` reads the live venv, so a reader
   with the files and no instructions still cannot do it.**
3. **⚠ EXECUTE THAT PROCEDURE AND CONFIRM IT YIELDS `dd6ab701` BEFORE THE FIELD IS
   WRITTEN.** *Otherwise two files are stored on a hypothesis and provenance is
   written on a second one.* ***Falsify rather than assert, applied to a provenance
   claim.***

**Then the field is true: `revision: 67d60532bb0d`, the two stored inputs by path
and identity, and that the re-derivation was verified on 2026-09-02.**

*The truthful weaker fallback was offered and rejected only because the better
option costs 1,383 bytes: `git diff HEAD -- src/chats` is empty and the source-only
digest is `b1ae8f94710ba066`, so a partial, accurate claim was available. **Offering
the weaker accurate answer alongside the stronger one is what made the ruling
easy.***

## ▶▶ L365. `dd6ab701` IS RE-DERIVABLE — verified, not asserted

    reconstructed  sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
    recorded       sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0

**`git archive 67d6053 src/chats tests` into a scratch tree — 31 Python files — plus
the two STORED copies rather than the live ones**, *which is what proves the stored
copies work*, then the digest run against the reconstruction.

**`tests/data/oracle-route-inputs/`** — `ch-legacy` (321 B, `c1821a3a…`), `RECORD`
(1,062 B, `863d603b…`), and a `README.md` opening **"⚠ DO NOT DELETE. These are not
stray virtualenv artifacts."** **It carries the reason** — the digest covers more
than git can hold, **so the property that makes it a good pin makes it unrecoverable
from a commit** — *so the next person who finds them understands rather than
obeys.* **The four-step re-derivation procedure sits beside them**, because
`oracle_digest.py` reads the **live** venv and a reader with the files and no
instructions still cannot do it.

### The field was DERIVED, not patched — a rule applied against its author's convenience

**`frozen_reference.json`: the field went into `freeze_references.py` and the file
was re-frozen**, so it is produced by the instrument like every other field.
***"Hand-patching would have reintroduced exactly what I deleted from this file
yesterday — a field nobody derived."*** **82 stored, 0 drifted, 0 new; instrument
digest `03bf8b92…`.** *L302 removed `revision` as the one field nobody re-derived,
and its author declined to add a new one the same way, one day later.*

**`legacy-selection-baseline.json` was patched, since no re-recording was
authorised — and the answers were proved untouched, 0 of 3 groups changed, by
hashing each group before and after. The capture script now derives the field, with
a comment saying `git rev-parse HEAD` was the wrong source and was used once.**
*A one-time exception that documents itself out of existence.*

*Self-corrected mid-task: a `RECORD` hash first written truncated to 16 characters
beside a full-length one. **A provenance record with two hash lengths invites a
reader to wonder which is authoritative.***

## ▶ REQUIRED CONTENTS OF `final-change-log.md` — a phase-5 deliverable, not yet written

**Recorded here so nothing is lost between now and then.**

1. **The deliberate-divergences table** — the four fence languages and the
   `FutureWarning` decoration, each with its reason and its bound, **as asserted
   exact differences rather than expected reds.**
2. **The memory outcome with BOTH numbers in one sentence** — the adverse scan ratio
   up to 3.39×, worst scan absolute 192 MB, worst overall 276 MB, **full coloured
   rendering at about one-third of Python's memory, and every timing shape 1.8× to
   33× faster.**
3. **The named follow-up:** scan-memory per-session accumulation, with the flat-56 MB
   diagnostic and the retirement of the oversized-line probe as primary instrument.
4. **The closed-seat provenance gap, stated:** *the contract corpora and the stderr
   baseline carry `dd6ab701` and name no revision; the revision is `67d6053`, and
   its two non-git inputs are stored at `tests/data/oracle-route-inputs/`.*
   ***A gap that is written down is navigable; one that is not is a dead end.***
5. **What every frozen successor can no longer assert**, in `g5-runner`'s form:
   **it can no longer detect that the recording was itself wrong, because the route
   that would have said so is gone.**
6. **The highlighting stated plainly** as a reimplementation of corpus-bounded
   fidelity over seven language families carrying 98.2% of painted characters, with
   the plain fallback for the rest.

## ▶ L366. Both faults fixed, the unknown answered from git, and the run released

**The unknown is settled from evidence rather than from the most recent change.**
`git show HEAD:…legacy-selection-baseline.json` proves **the previous recording
carries the identical bytes** — `{SEARCH_QUERY_SOURCE}:96: FutureWarning: …` —
**so the fault predates the re-recording and nothing about the recording is
implicated.** *Recorded as unknown at the pause rather than guessed, then answered
from git rather than from what changed last, which is what everyone assumes.*

**⚠ AND THE NUMBER BESIDE IT IS THE FINDING: only 1 of the 18 defect-pattern rows
carries a placeholder at all. Seventeen would have passed a raw comparison
forever.** ***The one row that could see the fault is the one that found it — which
is why a group is not covered by its majority.***

**Fault 1 — `ScopeMismatch`:** `fixed_length_sweep_home` is now `scope="module"`,
**matching `sweep_home` rather than widening it**, as ruled — *widening a fixture
another gate depends on changes when their corpus is built, for one seat's
convenience.*

**Fault 2 — normalisation, fixed one level up from where it bit.** The obvious
repair was the defect-patterns comparison; **`_compare` now normalises both sides
for every group, in one place, rather than each caller remembering** — **and the
columns-sweep rows are normalised too and were failing partly for the same reason.**
*Normalising the recorded side is a no-op, done anyway so the two sides are visibly
treated alike* — the symmetry that stops a future reader "simplifying" it back.
**All three gates now have the shape the generated-patterns gate already had.**

**⚠ And the rejected workaround would not have helped: the sweep failures were TWO
FAULTS WEARING ONE APPEARANCE** — a real home-length defect in the old recording
*and* a missing normalisation. ***It would have hidden the second while the first
was being properly fixed, and a hidden fault behind a correctly repaired one is the
worst outcome available.***

### The run is released, and the first mate is out of the digest loop

**`parity-finisher` re-derives both digests themselves immediately before the run
and records them with the result.** **The digests `search-firstmate` held are
stale** — `g5-runner` confirmed nothing moved across the pause and then edited the
tree themselves, storing `oracle-route-inputs` and re-freezing through the
instrument. **The precondition the wait existed for is satisfied; movement since is
recorded work.** ***A relayed digest is a report about tree state, and three of
those have gone stale between being taken and being acted on.***

*Tree verified quiet before release: no edits under `rust/`, `tests/` or `probes/`
in thirty minutes; nine uncommitted paths, all accounted for.*

## ⚠⚠ L367. 93 PASSED, 1 FAILED — and the red row is a RULED divergence, not a new defect

*Digests re-derived immediately before the run: oracle `sha256:dd6ab701…`, tree
`7b3267a6a22e1f7c`. **All 72 sweep rows pass, all 60 generated, 17 of 18 defect
patterns, both falsifiers.***

    recorded (python): b'{SEARCH_QUERY_SOURCE}:96: FutureWarning: Possible nested set at position 1\n  regex = re.compile(pattern, flags)\n'
    native:            b'FutureWarning: Possible nested set at position 1\n'

**`_normalize` is working correctly — there is no path in the native output to
normalise, because the port does not print one.**

**⚠ VERIFIED RATHER THAN INFERRED: `tests/deliberate_divergences.py` holds
`WARNING_DIVERGENCES = ("fb-posix-class-warning", "fb-posix-class-bare-warning")`,
and its docstring rules against reproduction explicitly** — *emitting a path to
`search_query.py:96` and echoing a line of Python the cutover deletes is the
fabricated-traceback pattern this project already removed once.* **The failing
`posix_class_future_warning` row is a THIRD case of the same divergence, reached
through a different corpus.**

***So this is not a relaxation and not a port change: the frozen selection gate must
defer to that authority, exactly as `test_search_command_contract.py` was taught to
this morning. THIRD INSTANCE TODAY of a gate asserting byte-parity on a case the
desk has ruled divergent.*** **And it must IMPORT, not copy** — that module's own
docstring says *a second copy of this list is the defect it exists to prevent.*

**Small, bounded, and it goes to whoever the captain resumes for the deletion.**

### It was hidden behind a correctly repaired fault

**The normalisation fault predated the re-recording and was that seat's own. This
one is underneath it and was hidden by it — fixing the comparison is what made it
visible.** ***Two faults wearing one appearance, for the second time in one seat***
— and the rejected workaround would have hidden this one while the other was
properly fixed.

## `parity-finisher`'s seat is closed at 90%

**Cleanup skipped deliberately rather than done badly.** ***A mistaken `rm` at 90%
is not recoverable and a leftover target directory is.*** **Three directories named
as safe for anyone to delete — a private `CARGO_TARGET_DIR` under the scratchpad and
two driver `target/` dirs under `teammates/parity-finisher/probes/drivers/`.** *All
reproducible, none referenced by any gate.* **Nothing on the preserve list touched.**

**Ledger, the longest on this mission:** F1; the C0 set twice re-derived, ending as
a four-site class with three oracles; F16; F17; the wrap-oracle gate; the
backreference sweep as a measured negative; `codecs.rs`; both `terminal.rs` width
divergences; `search_output.rs` three times; `codex.rs`; `inventory.rs`; the `-r`
indentation and `textwrap.indent`; the rule-colour slice; the six ceilings and their
discriminate-assertion; the three frozen gates. **Four defects nobody had listed,
three changing search results.**

**Two rules this desk keeps that came from that seat: *a maintained number is a
drift generator*, and *placement is part of the retraction*** — the second of which
corrected `state.md` twice within the hour of being found.

## ▶▶ L368. THE DELETION SEAT IS APPROVED — `deletion-owner`, `prompts/deletion-owner.md`

**Five items, in order, and no other scope:** wire the frozen selection gate to the
shared divergence authority by import; re-run all 94; **hand the second checkpoint
commit to `search-firstmate`** per charter commit policy; delete the Python search
authority; **hand a stable tree to `g5-runner` for the full post-deletion proof.**

### ⚠ THE PROMPT CARRIES NO DELETION LIST, ON PURPOSE

***Derive it. Do not inherit one.*** **`ch-legacy` is not deleted — the charter
keeps it for default parsing and unscoped commands. What goes is what is reachable
only from the `search` subcommand.**

**Two traps are named in the brief because each costs a day if a list is inherited
by filename:**

**`pool_filter.py` cannot simply go.** `extract_cwd_from_jsonl_file` serves
`passes_path_for_index` — **the `ch -1 -d` index path, which has NOT been ported**
(L310). **Deleting it breaks a journey the charter keeps.**

**The PyO3 extension stays.** `python_extension.rs` imports only `inventory` and
`scanner`, both used by `ch-legacy`. **The wheel legitimately ships
`chats/_native.abi3.so`** — check 14 records it and it is not a leftover.

**Derive by reachability from `cli.py`'s dispatch, not by name. Anything a surviving
command imports, survives.** **Report the list before deleting, so it is on the
record rather than in one seat's head.**

### The falsifier for a deletion, stated as the brief states it

***The proof that you deleted the right thing is that `ch-legacy`'s surviving
journeys still work — run them before and after and diff. A deletion is falsified by
what still has to pass.***

### Current modified paths, handed over

    M tests/data/legacy-selection-baseline/legacy-selection-baseline.json
    M tests/test_legacy_selection_frozen.py
    M thoughts/…/state.md
    M thoughts/…/teammates/g5-runner/RESUME.md
    M thoughts/…/teammates/g5-runner/probes/capture_selection_baseline.py
    M thoughts/…/teammates/parity-finisher/RESUME.md
    M thoughts/…/teammates/reviewer-profiler/freeze_references.py
    M thoughts/…/teammates/reviewer-profiler/frozen_reference.json
    ?? tests/data/oracle-route-inputs/
    ?? thoughts/…/teammates/g5-runner/evidence/

**Pre-deletion checkpoint `67d6053` already exists; the second one captures the
passing gates.** **`g5-runner`'s standing instruction binds the new seat: refuse the
deletion until the frozen gates are green and the checkpoint exists.**

## ▶ L369. `deletion-owner` IS LIVE — w76:tK / w76:p1C

**It exclusively owns: the shared divergence wiring, the 94/94 proof, the
checkpoint/deletion sequence, and the G5 handoff.** **All prior owners stay idle
unless it routes one narrow question.**

**No welcome message was sent.** *The brief carries the ownership boundaries, the
five items in order, the two deletion traps, the falsifiers, the definition of done,
the preserve list and the commit policy — a welcome would cost a seat context to
tell it what it is already reading.*

**`g5-runner` was told what changed, because they were holding for a seat that no
longer exists:** `parity-finisher` closed at 90%; **the red row is ruled, not
defective**; **their own standing instruction is now written into someone else's
brief as binding on them** — *it outlives their seat rather than remaining their
intention*; and **the post-deletion proof is the last thing on this mission and is
theirs.**

**State at handover:** `ch search` runs on Rust and is installed; G5 closed at 13 of
15 green with 2 accepted; 93 of 94 frozen assertions green; pre-deletion checkpoint
`67d6053` exists with `dd6ab701` **verified re-derivable** from it plus
`tests/data/oracle-route-inputs/`; nine stored artifacts confirmed; the final live
consultation recorded at 373 comparisons, all passed, **and unrepeatable.**
