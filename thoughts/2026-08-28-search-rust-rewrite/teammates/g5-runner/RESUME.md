# g5-runner — RESUME

**Seat:** G5 runner. **Edits nothing.** No production source, no tests, no `memo`,
nothing under `.optmem/`. Runs the runbook and reports. Defects go to
`search-firstmate`, who routes them.

> ## ⚠ HOW TO READ THIS FILE
>
> **It is append-only and later entries supersede earlier ones.** It was written
> section by section across one day while the tree moved underneath it, so **any
> statement below is true as of when it was written and not necessarily now.**
> Superseded passages are kept with a `⚠` marker naming where they are corrected,
> **because the reasoning that was overturned is usually the useful part.**
>
> **This header itself said "No gate has been run" while all fifteen were done** —
> the exact failure `state.md`'s own header carried for a day, in the first lines
> a cold reader meets. Found by re-reading this file whole, which is the practice
> that has caught the same fault five times on this mission.

## ✅ THE POST-DELETION PROOF IS DONE AND GREEN — 2026-09-02T12:48–12:56Z

**`post-deletion-proof.md`, 111 lines. The last deliverable of this mission.**

**Green:** checks 1, 2, 8, 9 (1,963 passed + 13 of 13 shell suites), 10, 11's six
time gates and three memory budgets, 14, 15, and the deletion falsifier at **36 of
36 journeys**. **Check 10's bytes are identical to its pre-deletion run.**

**Dead by construction, as ruled:** checks 3, 5, 6, 7, 12, 13 — live differentials
with no surviving reference. Their stored successors are inside the 1,963.

**Three findings, none a product defect:**
1. **Memory parity measures an error path now — and the CONTROL caught it.** A red
   control is the difference between *this number is broken* and *the product got
   worse*.
2. **`performance_gates.py:44` hardcodes a stamp naming a route that no longer
   exists** — the fault fixed in `frozen_reference.json` yesterday, surviving in
   the file beside it.
3. **A stale comment names the deleted divergence gate as its live counterpart.**

**One unresolved disagreement: the other two seats report the rust tree digest as
`7b3267a6…`; I measure `63a34f4f…` and no recipe I tried yields theirs.** The
claim holds either way — `git diff HEAD -- rust` is empty.

---

## ▶ RESUMED 2026-09-02. Both digests unchanged across the pause.

**`dd6ab701…` and `63a34f4f…` both re-derived and identical.** The recording is
untouched (630,008 B → 631,188 B after the provenance correction below, answers
unchanged).

**⚠ THE TREE IS NOW COMMITTED.** `git status` went 117 paths → 0.
**`67d60532bb0d` — "Checkpoint native search Rust rewrite WIP", Gilad Barnea,
2026-09-02 12:18, 1,464 files.** Not the first mate's and not mine — **this seat
commits nothing.** The deletion has NOT happened: `src/chats/commands/search.py`
and `.venv/bin/ch-legacy` are both present.

**Waiting on `parity-finisher`'s re-run. That is the only thing before the second
checkpoint.**

---

## ⏸ (superseded) SOFT-PAUSED — 2026-09-01, admiral. STOP POINT IS CLEAN.

**Nothing is mid-run. No capture, gate, build or install was interrupted.**

**On disk and COMPLETE:** the re-recorded
`tests/data/legacy-selection-baseline/legacy-selection-baseline.json`, 630,008
bytes, **150 answers — defect-patterns 18, generated-patterns 60, columns-sweep
72.** Oracle `sha256:dd6ab701…`, reference `c1821a3a86ee9a88`.
**And the fix is falsified, not assumed: all 72 sweep rows reproduce at a
DIFFERENT home of the same length, 0 mismatches.**

**NOT done, and it is not mine:** `parity-finisher` re-running
`tests/test_legacy_selection_frozen.py` against the new recording. **75 of 93
passed against the OLD one; the 18 failures were the recording defect now fixed.**

**⚠ THE THREE STEPS WHEN THIS RESUMES, IN ORDER. The ordering is the fragile part.**
1. **`parity-finisher` re-runs the three frozen gates** against the new recording.
2. **The first mate makes the checkpoint commit** — after 1, so it captures them.
3. **The deletion.** *This seat refuses it if step 1 has not gone green.*

**The re-recording window does NOT close during the pause.** It needs `ch-legacy`,
and `ch-legacy` only goes at the deletion, which is blocked.

---

## ✅ G5 IS CLOSED. 15 of 15 run, 13 green, 2 red and accepted.

**Green:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15.
**Red and accepted with their numbers, not around them:** 12 and 13 — one story,
the per-session memory accumulation, with a named follow-up.

**Nothing was relaxed. No expectation was restamped.** The one gate defect found
(`--falsify`) was **closed by construction rather than by a margin.**

**The wheel is installed. `~/.local/bin/ch` is `1f76081cd87a2808…`, byte-identical
to the artifact every gate measured.**

**⚠ THE ONLY THING LEFT ON THIS MISSION IS THE DELETION SLICE — and before the
Python authority is deleted, every instrument that consults it must have its last
consultation stored** (decision 6, L1, L23). **Cheap now, impossible after.
REFUSE THE DELETION IF THAT IS NOT CONFIRMED.**

### The earlier state line, superseded

**ALL FIFTEEN CHECKS HAVE BEEN RUN.** 10 green, 3 red, 1 gate defect, 1 closed
since by another seat.

| | |
| --- | --- |
| **Green** | 1, 2, 3, 4, 5-pty, 6, 7, 8, 9, 10, 14 |
| **Red** | 11 (subject in question), 12, 13, 15 (release step + hazard) |
| **Closed since by `parity-finisher`** | 5-piped, at 20 of 20 |
| **Gate defect, not a port defect** | check 11's `--falsify` hole |

**What is open and who holds it:**
1. **Check 11's deciding question is with `reviewer-profiler`** — were the ratio
   gates derived from the **branch** build? If yes they never described this port
   and are re-derived, **a correction and not a relaxation.** If no, check 11 is a
   real regression and needs an owner.
2. **Checks 12 and 13 are one story** — the two extra resident copies, unattributed.
3. **Check 15: nobody installs the wheel until check 11 resolves.** The reference
   hazard itself is closed — see the reference move below.

**Nothing is relaxed and no expectation has been restamped.**

---

## Why no gate has run

`cutover-finisher` and `parity-finisher` were both **busy** at 2026-09-01
(`ListAgents`, started ~5 min before my check). A run started against a moving
tree measures nothing. `search-firstmate` gives the word.

## What was done, and what it proved

All four identities re-derived by me, first-hand, at tree digest `ca874ce060f1`.

| identity | expected | measured | verdict |
| --- | --- | --- | --- |
| oracle route digest | `sha256:dd6ab701…badcee0` | identical | **unchanged — production search is still Python** |
| rust tree digest | `ca874ce060f1` (L263) | `ca874ce060f1413f8b98e9f78ce7bb2b0c93c0651c66b2b0ce9b2e332c35619b` | **matches L263 exactly — tree had not moved when measured** |
| corpus identity | `de693c35…284965`, 695 files, 1,183,541,907 bytes | identical | **exact** |
| frozen reference set | 82 entries on disk | `entries` dict, **82** | **L248's correction holds** |

Tree digest recipe: `find rust -name '*.rs' -type f | sort | xargs shasum -a 256 | shasum -a 256`.

**Both digests are snapshots taken before the two implementer seats had saved
anything. They are already suspect. Re-derive before any run.**

## Preconditions — one HOLDS, one has EXPIRED

**⚠ SUPERSEDED. The half marked HOLDS is now false — the cutover landed at
~14:30 and `rust/main.rs` routes `search`. Corrected under "THE CUTOVER LANDED"
below. Kept because the expiry mechanism is the useful part.**

**HOLDS.** `rust/main.rs` does not route `search`. `rg -n 'search' rust/main.rs`
returns nothing at all. The cutover has not landed.

**EXPIRED.** `search_run::run` **does** have a caller outside its own file:
`teammates/engine-and-codex/probes/searchdriver/src/main.rs:12`. The runbook says
it has none, in two places, one of them dated 2026-09-01.

*It did not expire the way the runbook predicted.* The runbook expected the
cutover to create the first caller. The rebuilt driver got there first — and
`engine-and-codex`'s eleven-shape sweep (L261) ran through it, so every shape
result on this mission was taken through that caller.

**The consequence is benign and I verified it rather than assuming it.** The
driver passes `terminal_width()` at `main.rs:31` — the intended source. So the
runbook's width answer stands on substance: check 7 is the gate, no new gate is
needed.

**But the arm uses a second width source the runbook does not name.** Help and
error take `argparse_columns()` (`main.rs:23,27`), not `terminal_width()`. The two
read `COLUMNS` differently — `columns_override` follows Rich (`str.isdigit()`,
rejects `+96`, accepts fullwidth digits); `python_int` follows `int()` (accepts
`+96`, accepts whitespace and underscores). **The ambient sweeps vary `COLUMNS`,
so the input is swept; whether any gate sweeps it against the *help and error*
shapes is unconfirmed and is a question for `reviewer-profiler`.** Not a finding.

## The fourth contradiction — found, in check 10's own remedy

The prompt said to assume a fourth existed. It does, and it is in the note
written to fix the third.

`g5-runbook.md:103` — *"Use a shape that renders: `--full` or `--color always`
without `-ll`"*.

**`--full` alone does not reach the coloured sink.** `search_run.rs:125,148`
gates both coloured sinks on `arguments.flags.color`, which is the *resolved*
colour decision. A probe run non-interactively is piped, `--color auto` resolves
to off, and `--full` lands in `PlainSink` at `search_run.rs:187`. It never touches
`ColouredPanelSink`.

**So the remedy reproduces the defect it was written to prevent.** L256's finding
was "a `-ll` probe never touches the panel renderer, so the no-Python proof would
pass over a route that cannot render". Piped `--full` fails in exactly that way.

**Why it decayed the same way as the other three:** the note is true in its
author's situation and drops the condition on the way into the check. Its own
sentence says *"`ch search --full` panics with exit 101 **on a colour
terminal**"* — on a colour terminal `--full` does reach the panel sink. Check 10
specifies an empty directory and a stripped `PATH` and **never specifies a
terminal**, so the condition that made the sentence true is not carried.

**Fix, and it is one word: check 10's search half must pass `--color always`.**
That is unconditional and needs no pty. `--full` may ride along; it must not be
the whole shape.

**Also decayed, same sentence:** *"`ch search --full` panics with exit 101"* was
true when written and is not true now. L261 measured `--full` clean at exit 0
against the rebuilt driver, and `Part::Tool(_) => Unsupported("tool")` is gone.

## Two stale statements in production source (reported, NOT fixed — not my file)

**⚠ SUPERSEDED — they were already fixed when I wrote this, and I verified it
myself. See "CORRECTED — the two stale comments were already fixed" below.**

1. `rust/search_run.rs:159-162` — the comment says the panel sink's `emit` panics
   on any fenced block with a lexer and that *"nothing in `main.rs` routes to
   `search_run`, so this arm exists for the gate until the lexer tables land."*
   The lexer tables landed at L247. The tool producer is gone.
2. `rust/search_views.rs:1968` — the panic message says *"until the lexer tables
   land"*. Same decay.

**The panic itself is real and L261's narrowing is confirmed by me:**
`rg -n 'Unsupported\('` over `rust/*.rs` leaves `session_render.rs:3700`,
`Unsupported("fence lexer budget")`, as the sole surviving producer on that route.
Content-driven, so no flag sweep rules it out. **The plain-fallback ruling for it
is ruled and not implemented.**

## One defect in `held-parameters.md`

**⚠ CLOSED. `reviewer-profiler` corrected it; the heading now reads "The six
bounds" and the items are numbered 1–6. A duplicated closing paragraph was left
by that patch and I flagged it separately.**

The heading reads **"The four bounds, in the order I found them"** and the list
holds **six** items, **two of them numbered 5** — `Streams` and `Vocabulary`.
Line 68's *"The fourth is the one to look for"* then sits after two fifths and
reads as pointing at `Direction`, which is closed and covered. L255 records
`Vocabulary` as the **fifth** bound; on disk it is a second 5 under a heading
saying four. Cosmetic against the ideas, wrong for anyone counting.

## Order of work when the word comes

**⚠ SUPERSEDED — all of it is done. Also: "the baseline was taken at 76" was
itself wrong. `reviewer-profiler` established it was taken at 68, and real.**

1. **Re-derive both digests first.** The ones above are stale by construction.
2. **First run is `--verify` at 82** (check 3). Not any gate. The zero-drift
   baseline was taken at 76 and everything downstream assumes it still describes
   the oracle.
3. Checks 1–8 (runnable now), then 9–15 once the cutover lands.
4. Every result carries **when it was taken and against which tree digest**.
5. **Before the Python authority is deleted: confirm every instrument that
   consults the oracle has its last consultation stored** (decision 6, L1, L23).
   **Refuse the deletion if it is not.**

## Standing rules for this seat

- **State the coverage limit at the top of a report, never the bottom.**
- **Never report a finding from an aggregate alone.** Dump the instances.
- **An unanswered question and a "no" look identical from below. Say which.**
- **Ask what each corpus cannot say** — seven confirmed blind corpora, and the
  newest was *incapable*, not thin.
- **Announce before running anything that builds or writes.**
- Context figure: report the harness's number **and name which quantity it is**.
  A session token budget is not a context-window percentage.


---

## Routing, settled — `search-firstmate`, 2026-09-01

**All three findings went to `reviewer-profiler`, batched into one interruption:**
the check 10 correction, the `held-parameters.md` numbering defect, and the
`argparse_columns` question.

### I do not edit the runbook, and the reason is the point

**The runbook is the specification of the proof I run. A runner who can edit the
specification can weaken it.** That is the held-out-corpus hazard wearing
different clothes. Keeping the author and the runner apart is the same separation
that makes my four re-derived identities worth anything.

**So the correction is `reviewer-profiler`'s, deliberately — not a queue
accident.** If a future occupant of this seat finds a runbook fault, the move is
to route it, never to fix it.

### The second width source is a real gap and it is in flight

**⚠ CLOSED. `tests/test_search_columns_sweep.py` sweeps eighteen `COLUMNS`
values against four help and error shapes: 0 differences over 72 comparisons.**

`cutover-finisher` has been told `argparse_columns()` may become a gate they must
close before landing, **and told not to chase it.** Not mine, not open on my side.

### What was accepted, so a successor knows which practices held

- **Coverage limit at the top of the report**, and both digests declared stale by
  construction rather than quoted as current.
- **Re-deriving four identities first-hand instead of quoting L263.** That is how
  I can say the tree had not moved, which is a different claim from assuming it.
- **Checking the expired precondition's consequence rather than assuming it was
  benign.** It expired the way nobody predicted — the rebuilt driver became a
  caller before the cutover.

### The rule the fourth contradiction earned

**A remedy is a dated fact too.** The check 10 note carried its condition — *"on a
colour terminal"* — into a check that specifies an empty directory and a stripped
`PATH` and never a terminal. **Fifth arrival at that rule on this mission, and the
sharpest instance: the fault was in the remedy for the third.**

## Next action when the word comes

**A full `--verify` at 82. Not a gate.** Re-derive both digests immediately before
it.


---

## ⚠ THE CUTOVER LANDED — `search-firstmate`, 2026-09-01. STILL HOLDING.

**`ch search` runs on Rust. Both runbook preconditions are now expired.**
`rg -n 'search' rust/main.rs` no longer returns nothing. **The runbook said its
whole shape changes the moment this lands. It has landed. Re-read the runbook
whole before running it — scoped re-reading is what produced all four of its
faults.**

**Do not start.** `parity-finisher` is live in `codecs.rs` and the performance
gates. `cutover-finisher` is in the launcher guard. **Two files moving.** The word
comes from `search-firstmate`.

### The route flipped but is NOT yet proved

`tests/test_search_command_contract.py` refuses to run. Its launcher guard rejects
the built binary for carrying a string it assumed only a stale branch build could
have. **Landing the arm made that premise false in the honest direction** — the
search arm links the whole `_native` library into `ch` for the first time.
`cutover-finisher` is inverting the guard into a positive freshness proof.

### What I raised on it, and what I will ask for at run time

**An inverted guard needs its own falsifier.** The old guard was negative — reject
a binary containing string X. The new one is positive — prove the binary is fresh.
**A positive freshness proof never shown to fail on a stale binary is green for an
unknown reason.** L9's shape, and check 10's shape one file over.

**The question I will ask when I run: does the new guard go red against a
deliberately stale build?** One kept stale artifact and one red run is the whole
falsifier, and it exists only while `cutover-finisher` still has one. Raised now
for that reason alone.

**Why it deserved the interruption:** the fix is to a gate, made by an implementer,
on the day the route flips. Decision 2's reasoning is about exactly that pressure.
Not an accusation. This is the one hour in which proving it is free.

### Today is the day my seat exists for

**Every gate green before the cutover was a formality.** The contract suite's own
header said *"this compares a process with itself"* and has stopped being true.
**Its 260 assertions can fail for the first time.** Expect reds. **Treat them as
the point of the exercise, not as breakage.**

### One question I raised is now answered

**The `COLUMNS` hole is closed.** `tests/test_search_columns_sweep.py` sweeps
eighteen values against four help and error shapes, byte-compared: **0 differences
over 72 comparisons.** That was the `argparse_columns` gap I could only mark as an
unanswered question rather than a no. It is now a measured no.

### ⚠ CORRECTED — the two stale comments were already fixed. I verified it myself.

**I recorded them as outstanding. They were not.** They landed with the
plain-fallback fix this morning, in the same pass that found six false comments.
**A phantom in a brief is the most expensive shape a handoff takes** — L264 — so
this is corrected in place rather than appended to.

**Verified first-hand, not taken on the relay** (`rg 'lexer tables land' rust/`
returns nothing):

- `search_run.rs` — the false paragraph is gone. The third arm keeps only its
  true comment about Python's `_display_hit` ordering.
- `search_views.rs:1988` — `ColouredPanelSink::emit` now calls
  `self.render(hit, ordinal)` **directly**. No `unwrap_or_else`, no `panic!`.

### ⚠ AND THE PANIC CLASS IS CLOSED STRUCTURALLY, WHICH IS MORE THAN WAS REPORTED

**The `Unsupported` type is gone from `rust/` entirely.** The one surviving match
is an unrelated XML error string in `codecs.rs:1436`. Every `panic!` left in
`search_views.rs` is in test-oracle loading or theme-token lookup. **None is on
the production emit path.**

**That is L261's constraint met in its strong form**, not its weak one: *"close
the route structurally rather than with a second refusal — the sink's panic should
be impossible by construction, not merely unreached."* It is now impossible by
construction. **L261 said this class was NOT closed. It is closed. Do not carry
the open version forward.**

### ⚠ BUT MY CHECK 10 CORRECTION SURVIVES THE PANIC FIX — do not read it as moot

**The easy wrong inference: the panic is gone, so the check 10 note no longer
matters.** It still matters, because **the panic was never the reason.**

The reason is sink reachability. `search_run.rs` gates both coloured sinks on the
**resolved** `flags.color`. A probe run non-interactively is piped, `--color auto`
resolves off, and `--full` still lands in `PlainSink`. **A piped `--full` proves
nothing about rendering whether or not anything panics.**

**So check 10's search half still requires `--color always`.** What the panic fix
changed is only the consequence of getting it wrong: before, a wrong shape hid a
crash; now it hides an unexercised renderer. **Still a gate passing for a reason
unrelated to what it proves.**

### First run, unchanged and now more load-bearing

**A full `--verify` at 82.** Everything downstream measures a route that moved
today. **Re-derive both digests immediately before it** — the pre-cutover values
in the table above are dead.

---

## ✅ CHECK 3 RUN — `--verify` at 82. Taken 2026-09-01T14:16:59Z–14:17:19Z.

**Coverage limit, first: this compares the Python reference against ITSELF. It
says nothing about the Rust route. Baseline integrity only. I edited nothing and
re-froze nothing.**

**Identities at run time.** Oracle route digest `sha256:dd6ab701…` **unchanged**.
Reference `~/.local/bin/ch` → `~/.local/share/uv/tools/chats/bin/ch`, identity
`22236c087af33dea`, **matching the stored `reference_route_identity` exactly.**
Rust tree digest had moved to `c41ae1f805c4…`, which is expected and irrelevant
here. Fixture home `tests/data/search-contract-fixtures/home`.

### Raw result: 75 of 82 drifted. THE ORACLE HAS NOT DRIFTED AT ALL.

**Never report a finding from an aggregate alone.** I dumped the instances. The
75 decompose into two instrument defects, 54 + 21, with no remainder and **zero
behavioural drift**.

| after pinning | entries |
| --- | ---: |
| byte-identical | 61 |
| differ ONLY by the per-run temp path | 21 |
| **differ for any other reason** | **0** |

### Cause 1 — 54 entries: the width-probe session's ORDERING, not drift

Same byte count, same line count, **the two panels swapped position.**

`freeze_references.py` copytrees the fixture home and **never applies
`MTIMES.json`**, which the contract suite does apply. The fixture files carry
restamped mtimes of 2027-01-15. `seed_width_probe` writes its session with a
wall-clock mtime and no stamp. `ordering.sort_by_modified` then ranks the probe
differently than it did on 2026-08-29.

**Applying `MTIMES.json` and stamping the probe deterministically takes 75 → 21.**

**Checked for flapping before concluding: 12 fresh runs of the same reference gave
1 distinct output, 12 of 12. It flipped once. It does not flap.** `CH_NOW` pinned
alone changes nothing, so the wall clock is not the cause.

**A held parameter nobody chose, living in a helper — the same shape as
`run_at_width`'s `DEVNULL`.**

### Cause 2 — 21 entries: A RANDOM PER-RUN PATH IS FROZEN INTO THE BYTES

Every stderr entry embeds the `tempfile.mkdtemp()` directory, e.g.
`/var/folders/…/T/tmpv_upkrod/home/.claude/projec`. **Freeze and verify are
separate runs, so the path differs every time.**

**These 21 cannot match on any fresh run, today or ever.**

`stderr/no-match-filtered` is the control that proves the mechanism: it
short-circuits on `-p codex`, never reaches the erroring file, prints no path,
**and matches.**

**So check 3 is not stale. It is UNSATISFIABLE.** The runbook calls it the
load-bearing check and it currently cannot pass, for a reason unrelated to the
port.

The 21: `stderr/no-match`, `stderr/no-match-colour-never`,
`stderr/no-match-colour-always`, and `stderr-ambient/<9 inputs>/{A,B}`.

### Open question I could NOT close — stated as a question, not a no

**How was "0 drifted, 0 new against install 22236c08" ever obtained at 76?** 21
unsatisfiable entries exist now and only six were added since, so at least fifteen
should have been present and failing at 76. **I cannot recover the 76-entry file**
— the only copy on disk is the 82-entry one, written 2026-08-29T02:29:52. Either
the runbook's arithmetic is wrong or that PASS was not a fresh verify. **Routed to
`reviewer-profiler`.**

### Why this is urgent rather than tidy

**The freeze exists so the oracle's answers survive its deletion. 21 of 82 are
unusable and the deletion slice is downstream.** Decision 6's *cheap now,
impossible after*, arriving early. **Fix the instrument and re-freeze BEFORE the
route flip.**

### Method notes worth keeping

- The aggregate said 75 drifted and the truth was 0. **The aggregate was true of
  nothing.**
- I tested each cause by removing it rather than by arguing it: `MTIMES` applied,
  probe stamped, `CH_NOW` pinned, each measured separately.
- `rg -rn` twice cost me a wrong-looking result — **`-r` is `--replace`, not a
  companion to `-n`.** Use `grep -rn` or `rg -n`.

**Scratch scripts** in the session scratchpad: `stability.py`,
`verify_with_mtimes.py`, `rootcause.py`, `final.py`. **They are a scratchpad copy,
which is not storage** — if any is wanted, it must be promoted to
`probes/drivers/`.

---

## ⚠ INSTRUMENT REPAIR — I PATCHED IT, THEN WAS STOOD DOWN. DISCLOSED.

**Sequence, so a successor is not confused by the file's authorship.**
`search-firstmate` granted me the repair with four constraints. **I patched
`freeze_references.py`. The stand-down arrived after I had already written it**,
saying `reviewer-profiler` had made the fix and I should verify instead.

**The file on disk is MY code.** Six strings I invented are in it, including whole
docstrings and the helper names `restore_fixture_mtimes`, `stamp_width_probe`,
`oracle_stamp`. **So I am NOT an independent verifier of that instrument.**
Disclosed to `search-firstmate` rather than proceeding quietly.

**My first check said the file was theirs. That was wrong and I caught it before
concluding anything** — `grep -c` is line-based and the phrase I searched for
wraps across two lines. **A line-based search cannot find a wrapped phrase.**

### What I changed, for the record

1. `record(output, home)` — **`home` made required, not defaulted.** The
   normalisation already existed and **only 1 of 9 call sites passed it.** Closing
   it structurally, so a call site cannot omit it, rather than adding a guard.
2. A fail-loud check: if the ephemeral directory name survives normalisation, it
   **raises rather than freezing an unre-derivable entry.**
3. `restore_fixture_mtimes` — applies `MTIMES.json` as the contract suite does.
4. `stamp_width_probe` — continues the fixture's own stamping scheme.
5. `oracle_stamp` — derives the digest instead of transcribing a constant.

### ⚠ THE ARTIFACT WAS NOT PRODUCED BY THE INSTRUMENT ON DISK

`frozen_reference.json` carries the **old hardcoded** `oracle_state`, which my
version deletes. **So a third instrument version produced it and is gone.** The
artifact and the instrument do not correspond, **so checking one does not validate
the other.**

**The durable cure, `search-firstmate`'s wording: the artifact must record the
digest of the instrument that produced it.** Decision 3 arriving at a different
artifact — a revision alone is not enough. **It also retires this whole class: a
reader could then tell my instrument from `reviewer-profiler`'s without asking
either of us.**

## ✅ VERIFY #2 — fresh process, fresh temp home. 2026-09-01T14:32:38Z.

**82 stored, 0 drifted, 0 new.** 27 entries carry `{HOME}`, 0 carry a raw temp
path. Reproduces the reported figures exactly. **Caveat that must travel with it:
green over an instrument I wrote.**

### Constraint 2 — the normalisation is not inert. Accepted by the first mate.

| case | result |
| --- | --- |
| hides the ephemeral home across two temp roots | agrees ✓ |
| path differs **outside** the home | **still fails** ✓ |
| path differs **under** the home, past the prefix | **still fails** ✓ ← the over-reach case |
| home prefix cut by render width | **raises** ✓ |
| `record()` with no home | `TypeError` ✓ |

**Reach is structurally bounded, not merely tested:** the replacement is one long
unique `mkdtemp` path, so it cannot span what a shorter or commoner string would.

## ✅ THE PINNED INSTALL HANDS SEARCH TO PYTHON — constraint 3 named the wrong oracle

**Measured, not reasoned.** `~/.local/share/uv/tools/chats/bin/ch` alone in an
empty directory, no `ch-legacy` sibling, `env -i`, `PATH=/nonexistent`:

    search "needle five" --color always …   exit 1, stdout 0 bytes
    info --help                             exit 1, same error
    both: "Cannot start the private ch legacy entry: No such file or directory"

**Search cannot run without the Python entry, so the frozen bytes ARE Python's.**
Structural agreement: links only libiconv, CoreFoundation, libSystem; **0
undefined `Py_` symbols**, so it holds no interpreter and exec is its only route.

**`22236c08` is the MORE stable oracle**, not the less: the uv tool install is
outside the working tree and untouched by the cutover, while `.venv/bin/ch-legacy`
reaches `src/chats/` through the editable install and is what the deletion slice
removes. **The freeze stands. No re-freeze for provenance of reference.**

### ⚠ FREE AND WORTH KEEPING: this recorded CHECK 10's "BEFORE" STATE

**Both halves fail identically today — same error, same exit 1 — because
pre-cutover both routes are Python.** Not a defect. The baseline.

**After the flip: search must render while `info --help` still fails with that
exact string.** The control only discriminates once the arm is in the shipped
artifact, **so today's identical pair is what the post-cutover run is measured
against.** The artifact tested is the Aug 28 install, **not** the Sep 1 build that
carries the arm.

## Still open

**Provenance is unresolved even though the reference is vindicated.** The
instrument is mine; the artifact came from a third version. `search-firstmate`'s
call.

---

## ✅ RE-FROZEN WITH PROVENANCE — 2026-09-01T14:36:58Z. PROVENANCE IS CLOSED.

**Ruled by `search-firstmate`: re-freeze once from `22236c08`, stamp the
instrument's digest into the artifact, and put my own disclosure in it too.
Not a different pair of hands — the artifact carries what it is, including its
own weakness.**

**Their reasoning, which is the part to keep:** the risk I disclosed is that the
instrument's author verified it, **but the record is of Python's answers and this
seat has no stake in those.** The stake this desk guards is in the Rust port's
answers, and no seat holding one is near this file.

### The headline result

**Entries whose recorded answer changed: 0. None added, none removed.**

So the previous artifact's **content was already correct** and only its provenance
was unknowable. **The repair was provenance-only — which is itself the evidence
that nothing was re-frozen into agreement.**

### What the artifact now carries

| field | value |
| --- | --- |
| `instrument_digest` | `sha256:71aee37e…4724fb` |
| `instrument_digest_recipe` | sha256 over name+bytes of `freeze_references.py`, `pty_harness.py`, `width_probe_fixture.py`, `generate_cell_oracle.py` |
| `source_digest` / `oracle_state` | **derived at freeze time**, hardcoded constant deleted |
| `reference_route_identity` | `22236c087af33dea` |
| `provenance` | the disclosure, in the artifact |

**All four modules are digested, not just the entry script** — a digest of
`freeze_references.py` alone would miss a change in the pty capture or in the
probe's own generator. Same reasoning as digesting the whole route, not `src/`.

### Verified three ways, all after the re-freeze

1. **Fresh separate process, fresh `mkdtemp`, 14:37:41Z: 82 stored, 0 drifted,
   0 new.**
2. **The instrument digest re-derives independently.** I recomputed it from the
   four files outside the instrument and it matches. **The stamp is checkable by a
   stranger rather than self-asserted, which was the entire point.**
3. 0 raw temp paths in any entry, 27 carrying `{HOME}`.

### One field nobody re-derived — named, not fixed

**`revision` is still carried forward** as a foreign stamp field from
`contract-owner`'s re-bless path. It matches `HEAD` today, so it is correct.
**It is the only field in the file nobody re-derived, and it is the same shape as
the problem just closed, one field over.**

## ✅ CHECK 10 BASELINE — `check-10-baseline.md`, **promoted verbatim**; runbook now 222 lines

**I did not put it in the runbook, deliberately, and told the first mate why.**
They asked me to put it where check 10 is read. That is `g5-runbook.md`, which
they ruled I do not edit. **An evidence addendum probably does not break that
rule, but I am not the one who should decide where its edge is.**

Written as a **drop-in block phrased for the runbook**, 51 lines. Promote verbatim
and the rule stays intact. It carries the identical-pair baseline, the **Aug 28
install versus Sep 1 build** distinction, the behavioural and structural evidence
agreeing, and **the one thing that would break the reading: a piped `--full` lands
in `PlainSink` and proves nothing.**

## Where things stand

**Check 3 is done and sound.** The frozen set is reproducible, provenanced,
independently re-derivable, and its answers never moved.

**Still holding.** `cutover-finisher` owes the differential and one untested item.
**`run_all.sh` is check 1 of the release, the moment they report.**

---

## ✅ `revision` CLOSED BY DELETION — 2026-09-01T14:40Z. CHECK 3 IS DONE.

**Ruled: derive it or delete it, measure whether anything reads it, and if
nothing does, delete.** *Removing the field beats deriving it, and an artifact
with one un-derived field reads as an oversight to the next person, who will
assume the others are un-derived too.*

### The measurement — nothing reads it

| toucher | what it does |
| --- | --- |
| `slice-reviewer/probes/responsiveness.py` | reads `["entries"]` **only** |
| `test_search_command_contract.py:174` | reads `ORACLE['revision']` — but `ORACLE = CORPORA[0].oracle`, i.e. **`search-contract-fixtures/ORACLE.json`, a DIFFERENT artifact** |
| `contract-owner/work/rebless_oracle.py:51` | **writes** it |

**The only program that touches the field is a writer.** ⚠ **Naming the subject
mattered here** — the two `revision` fields are indistinguishable from a grep and
live in different artifacts.

### Deleted, and the mechanism deleted with it

**I removed the carry-forward too.** Deleting the value while keeping the
mechanism would restore it on the next run. **The instrument now derives every
field it writes, and the artifact has no field a reader cannot re-derive.**

Fields: `oracle_state`, `source_digest`, `source_digest_recipe`,
`instrument_digest`, `instrument_digest_recipe`, `provenance`,
`reference_route_identity`, `note`.

### Re-verified

- **Answers changed across all three re-freezes, measured against my first
  snapshot: 0. The set has never moved.**
- Fresh separate process: **82 stored, 0 drifted, 0 new.** 0 raw temp paths.
- **`instrument_digest` moved `71aee37e…` → `ddcef743…` because I edited the
  instrument.** That movement is the proof the stamp is **live rather than
  transcribed** — the exact failure it replaced. Recomputed by hand outside the
  instrument: matches.

### ⚠ A TWO-WRITER CONFLICT, REPORTED NOT FIXED — `contract-owner`'s file

`rebless_oracle.py::_stamp_foreign_records` writes `source_digest`,
`source_digest_recipe` **and** `revision` into this artifact. **My instrument now
derives the first two and drops the third, so the two writers disagree about the
same fields.** A re-bless restores what a freeze removes, and the reverse.

**The direction matters more than the collision.** Stamping a frozen artifact
**without re-recording its entries** is decision 3's rejected restamp exactly — *a
new digest on an artifact previously carrying a blind one asserts the oracle has
not moved since generation.* **The artifact now carries a stamp derived at
generation, the strong form. A later re-bless would replace it with an
asserted-afterwards one — a downgrade, not a refresh.**

**Recommendation, `contract-owner`'s call:** `rebless_oracle.py` should stop
stamping this file. It existed to give a prose-stamped artifact the
machine-checkable half; **the artifact now produces that half itself, so the
reason was removed rather than worked around.** I did not touch their file.

## CHECK 3 IS DONE

**Reproducible, provenanced, self-describing, independently re-derivable, and its
answers never moved across three re-freezes.**

**Next: `run_all.sh` as check 1 of the release, when `cutover-finisher` reports
the stderr-tty baseline and the differential.** Nothing else is mine until then.

---

## ✅ THE SECOND WRITER REMOVED — 2026-09-01T14:43Z. CHECK 3 FULLY CLOSED.

**Ruled by `search-firstmate`: I take the writer out myself.** The rule bars me
from the **specification of the proof** and from **making a record agree**.
`rebless_oracle.py` is neither — **it is a tool that would corrupt the artifact,
and removing a writer that downgrades a stamp is unambiguously strengthening.**
`contract-owner` is closed at 89% and waking them to delete a mechanism whose
reason was removed is not a good use of their last tenth.

**The hazard was live, not latent:** `_refuse_if_the_launcher_is_native` does
**not** fire for the pinned `~/.local/bin/ch`, because it hands search to Python.
The tool could have run and downgraded the stamp today.

### What I changed in their file — one block, nothing else

`FOREIGN_RECORDS` held `frozen_reference.json` as its **only** member, so removing
it empties the tuple. **I emptied it rather than deleting the mechanism**, staying
inside a narrow grant on another teammate's file.

**But an empty tuple reads as an oversight** — the exact fault just fixed on
`revision` — **so the emptiness is documented as deliberate**: dated, attributed,
with the decision-3 argument, the live-hazard note, and **the condition for adding
a member back** (it holds recorded Python answers and cannot stamp itself).

**Verified by importing the module rather than reading it:** imports clean,
`FOREIGN_RECORDS = ()`, `_stamp_foreign_records` is a no-op. A structured diff
confirms **one modified block** and nothing else. Backup at
`scratchpad/rebless_oracle.py.bak`.

### The provenance now names which writer was right

In the artifact, where a reader meets it: **every stamp here is derived at
generation**; `rebless_oracle.py` used to add them afterwards and no longer does;
**stamping a frozen artifact without re-recording its entries asserts the oracle
has not moved since generation, which a later stamp cannot support**;
derived-at-generation is the strong form, asserted-afterwards is a downgrade;
**if you find both writers in the history, this one was right.**

### Final state

| | |
| --- | ---: |
| verify, fresh process, 14:43:47Z | **82 stored, 0 drifted, 0 new** |
| answers changed vs the first snapshot | **0, across four re-freezes** |
| raw temp paths | **0** |
| fields, all derived by the writer | **8** |
| `instrument_digest` | `27f4c60d…`, **re-derived by hand: matches** |

**The stamp has now moved three times, once per instrument edit, and re-derived by
hand each time. That is three demonstrations it tracks the code rather than being
transcribed.**

## THE SHAPE OF THE WHOLE DAY, worth keeping

**The aggregate said 75 of 82 had drifted. The truth was that nothing had.**
Everything real came from **dumping the instances and reading them.**

**Every fix since has removed a mechanism rather than added one:** the defaulted
parameter, the carry-forward, the second writer. **Three deletions, no new guards,
and the artifact ends up saying more about itself than when it had more code
behind it.**

## Next

**`run_all.sh` as check 1 of the release**, when `cutover-finisher` reports the
stderr-tty baseline and the differential. Nothing is mine until then.

---

# ▶ G5 STARTED — 2026-09-01T14:56Z. THE TREE IS QUIET, BOTH SEATS CLOSED.

**Digests re-derived immediately before starting.** Oracle `dd6ab701…`
**unchanged**. Rust tree `b59b2496b9b6ca20…`, moved again (43 `.rs` files, 115
modified paths). **Re-derived after the run too: both identical, so the run is
valid rather than void.**

## ❌ CHECK 9 — FULL SUITE. RED.

**18 failed, 21 errors, 2354 passed, 3 skipped. 110.8s, 14:57:05Z–14:58:56Z.**

**⚠ COVERAGE LIMIT: `run_all.sh` uses `set -e`.** It stopped at the first pytest
failure and **never reached the perf suite or any of the 13 shell suites.** The
gate as specified reports the first failure only. I ran the remainder separately.

**Neither root cause is a port defect. The suite disagrees with itself, and both
causes are the same shape: a fix that landed in one of two places.**

### Root cause 1 — all 21 errors. A second, un-updated launcher guard.

`tests/test_parse_command_contract.py:35` still holds the **old negative** guard:

    HEAD_ABSENT_LAUNCHER_MARKERS = (b"logicalParentUuid",)

**The premise is false in the honest direction.** `logicalParentUuid` is
legitimately in the working tree at `rust/session.rs:894` and `:916`, and absent
from committed HEAD's `rust/`. **A correctly built binary embeds it and the guard
rejects it.**

> Launcher provenance cannot be proven fresh: `target/release/ch` embeds
> HEAD-absent strings `['logicalParentUuid']`.

**`cutover-finisher`'s positive freshness proof landed in
`test_search_command_contract.py:195` only.** Two functions, same name, two files,
one fixed. **All 21 errors are that one line.**

### Root cause 2 — all 18 failures. The parity suite ignores the ruled divergences.

The 18 are **exactly** the 6 ruled ids × the 3 parity functions, **no remainder**:
`render-fence-web-96/140`, `render-fence-data-96/60`, `fb-posix-class-warning`,
`fb-posix-class-bare-warning`.

**`tests/test_deliberate_divergences.py` defines those exact 6 as `DELIBERATE` and
passes 11 of 11**, asserting each difference exactly.
**`test_search_command_contract.py` knows nothing about it** — the import runs the
other way — so it still asserts byte-parity on all 6.

**The two suites assert opposite things about the same six cases. Both cannot
pass, so the suite cannot be green by construction.**

**The divergence suite's own opening line is the argument:** *"An expected red is
indistinguishable from a regression … so these six are not left red."* **They are
left red, in the other suite.** The mechanism was built; the parity suite was
never taught to defer to it.

### What is NOT wrong, so nobody chases it

- **All 13 shell suites pass.** Every one.
- Perf fails **twice** — `dir_filter_list_under_2500ms` at 2817ms **and**
  `mafter_4h_list_under_1750ms`. **Both are the two retired live-pool budgets at
  1750 and 2500 that check 9's own row explicitly excludes.** Neither makes
  check 9 red. *The first mate named one; the runbook covers both.*
- **No behavioural divergence anywhere.** 2354 passed.

### ⚠ The runbook is now stale, and I do not edit it

Re-read whole at 202 lines before running. **Its precondition block is stale in
precisely the way it warns about:** it still says the cutover has NOT landed, that
`main.rs` does not route `search`, and that `run` has no callers; the width
section repeats the no-callers claim; the seven post-cutover checks still sit
under a heading saying they are blocked **by construction**; and the check 10
bullet still says `--full` panics with exit 101.

**None of it changed what I ran.** Reported, not edited.

## Next

Awaiting routing on both root causes, and whether check 9 re-runs after. **Checks
1, 2, 4–8 and 10–15 are unstarted.**

### Routed, and the runbook corrected by `search-firstmate` — 222 lines

**Both root causes went to `cutover-finisher`.** Do **not** re-run check 9 until
the first mate gives the word: **a re-run against a half-landed pair produces a
number nobody can use.** Re-derive both digests first when it comes.

**The runbook was corrected by the first mate, not by me, and signed as theirs.**
The three expired preconditions are **marked rather than rewritten** — the
originals stay because the reasoning is the useful part.

**⚠ THE ONE CORRECTION TO CARRY, because it is easy to get backwards: check 10's
panic is gone and the RULE IS NOT.** A `-ll` probe **still** never touches the
panel renderer, so it **still** passes the no-Python proof over a route whose
rendering it never exercised. **The premise moved; the reason did not.** Use
`--color always`.

**My `set -e` finding is now recorded where check 9 is read:** the specified
command reports the first failure only, **so a short failure list is not a small
failure count.** My run is the worked example — one failure shown, 18 failed and
21 errors true.

**No pass condition was changed. All of it is evidence.**

## HOLDING. Checks 1, 2, 4–8 and 10–15 are unstarted.

**⚠ SUPERSEDED — every one of them has since been run. See "ALL FIFTEEN CHECKS
RUN" below.**

**The tree is moving again** while `cutover-finisher` lands both fixes, and the
test suite's own fixture rebuilds `target/release/ch`, **so check 1 and everything
measuring the artifact would move under a run too.** Holding on all of it, not
only on check 9.

---

# ▶ ALL FIFTEEN CHECKS RUN — 2026-09-01. 10 GREEN, 4 RED, 1 GATE DEFECT.

**Digests unchanged across every run:** oracle `dd6ab701…`, rust tree
`b59b2496…`. **Nothing here is void.**

**⚠ COVERAGE LIMIT, restated because it is the one that gets misread: `run_all.sh`
uses `set -e`.** It stops at the first pytest failure, so **the 13 shell suites
and the perf suite were run by me, not by the gate.** A short failure list is not
a small failure count.

| # | check | verdict |
| --- | --- | --- |
| 1 | no PyO3 | ✅ 0 `Py_`, 0 `_native`/`abi3` strings |
| 2 | corpus identity | ✅ `de693c35…` exact |
| 3 | frozen set | ✅ 82 stored, 0 drifted |
| 4 | age pairing | ✅ 259 tokens, `1w → month` intact |
| 5 | ambient, pty | ✅ clean both directions |
| 5 | ambient, piped | ❌ then **CLOSED by `parity-finisher`, 20 of 20** |
| 6 | colour capability | ✅ 6 tiers identical |
| 7 | coloured width | ✅ identical at 60/120/200 |
| 8 | scoped diff | ✅ 117 paths, nothing outside scope |
| 9 | full suite | ✅ 2394 passed, 0 failed, 0 errors |
| 10 | no Python on route | ✅ **and it discriminates now** |
| 11 | performance | ❌ 3 shapes + a gate defect |
| 12 | memory parity | ❌ known 1.29×, control passes |
| 13 | allocation slope | ❌ 9.00, **prediction falsified** |
| 14 | package ownership | ✅ |
| 15 | installed launcher | ❌ **plus a forward hazard** |

## ✅ Check 10 — the before-state paid for itself the same day

**This morning both halves failed identically because both routes were Python.**
Now: **search exit 0, 934 bytes, 31 escape runs, no interpreter anywhere**;
control `info --help` exit 1 with the private-entry error. **The probe can tell
the two routes apart, so the search half means something for the first time.**

## ❌ Check 11 — a REAL regression, not the machine

**⚠ QUALIFIED BY A LATER MEASUREMENT. The machine is still ruled out and that
stands. But the recorded ratios it is judged against appear to have been taken
against the BRANCH build, not this port — see "CHECK 11 LOCALISED" below. "A real
regression" is not yet established; "not the machine" is.**

```
broad list, absolute date   976.3ms vs 650ms
selective literal, id-only   0.439x vs 0.30x   (906ms vs 2067ms)
broad regex miss, id-only    0.435x vs 0.25x  (1637ms vs 3764ms)
```

**The machine was NOT quiet** — load 1.80, Chrome, `pi`, `agy`, six `claude`
processes. This gate is documented blind to concurrency. **So I reproduced before
reporting:** three interleaved repetitions gave **0.438–0.448 and 0.434–0.436, a
2% spread**, with Python stable at 2057–2067ms. **Contention does not produce
that.**

**The native side moved:** recorded 360.3/372.8/568.0ms on 2026-08-28 against
902–921ms now. **Caveat stated rather than buried: the old figure had a 56%
spread and today's has 2%.** But the worst old reading, 568ms, sits below today's
best, 902ms — **the movement survives its own caveat.**

**⚠ A GATE DEFECT, not a port defect: the `--falsify` hole.**
`broad literal miss, id-only` measured **462.4ms on the PYTHON route against a
750ms budget and passed it.** **A budget the reference also passes cannot
discriminate between the routes at all.** Same class as check 10's control before
this morning.

## ❌ Checks 12 and 13 — one story, and a prediction falsified

12: subject +576MB, reference +447MB, **576/447 = 1.288** — the record has it to
the same digits. **Control passes, both arms near zero.**

13: **subject slope 9.00 against a 7.36 gate.** The runbook predicted that if
`session`'s clone-to-move change was the mechanism the slope would fall toward
7.00. **It did not move at all. Clone-to-move was NOT the mechanism** and the two
extra resident copies stay unattributed. **That is an answer, not a non-result.**

**The old model reproduced precisely** — 9.00/+23MB and 6.99/+84MB against
recorded 9.00/+21MB and 7.01/+82MB — **and its crossover prediction held again:
predicted 30.5 MB, observed level at 32 MB, 311 against 310.** Native still wins
small, 95MB against 140MB at 8 MB.

## ✅ Check 14 — and one thing stated precisely

Wheel's `ch` is `47fa6038…`, **byte-identical to `target/release/ch`**, so
everything measured is the shipped artifact. `entry_points` expose only
`ch-legacy`. **Extracted alone it passes check 10 by itself.**

**The wheel holds a SECOND Mach-O, `chats/_native.abi3.so`** — the PyO3 extension
the retained `ch-legacy` route uses. "One Mach-O `ch`" is satisfied; **"one Mach-O
in the wheel" would not be.** Named so nobody discovers it later.

## ❌ Check 15 — AND THE HAZARD THAT MATTERS MORE THAN THE INSTALL

    wheel            47fa6038…  built     2026-09-01T18:00
    ~/.local/bin/ch  22236c08…  installed 2026-08-28T15:33

**⚠ THE PYTHON REFERENCE AND THE INSTALL TARGET ARE THE SAME PATH.**
`~/.local/bin/ch` at `22236c08` is the pinned pre-cutover build that hands search
to Python — which is exactly why it is the reference for checks 3, 5, 6, 7, 11,
and why `frozen_reference.json` records `reference_route_identity: 22236c08`.

**Installing the wheel overwrites that path with the native route. Every gate
pointed at it would then compare native against native** — the *"compares a
process with itself"* failure the contract suite escaped this morning,
reintroduced through the install step. **`--verify` does not check the stored
reference identity**, so it would report drift and read as the port breaking.

**Cure: move those gates to `.venv/bin/ch-legacy` BEFORE anyone installs.** That
was constraint 3's original instinct — **correct then, withdrawn for good reason,
and it inverts the moment the wheel lands.**

## Open

**⚠ SUPERSEDED AND WRONG IN ONE PARTICULAR.** I wrote that a bisect over today's
landings was the instrument and later that it was impossible for want of a
baseline. **Both were wrong: `tests/data/launcher-provenance/ch-0ffde41` is a
committed branch build and it served as the baseline.** See "CHECK 11 LOCALISED".

---

# ▶ REFERENCE MOVED, REFUSAL BUILT, CHECK 11 LOCALISED — 2026-09-01T18:0x–18:2xZ

## ✅ The reference is now `.venv/bin/ch-legacy` — and the move was proved neutral BEFORE it was made

**I did not move and hope.** I ran the existing frozen file's `--verify` against
`ch-legacy` **while it was still frozen against `~/.local/bin/ch`: 82 stored, 0
drifted, 0 new.** So the two are equivalent **across all 82 entries**, not across
a sample. Re-frozen after that: **0 answers changed.**

`reference_route_identity` → `c1821a3a86ee9a88`. Provenance carries the move, the
equivalence proof, and the reason.

**Why it had to move: installing the wheel overwrites `~/.local/bin/ch` with the
NATIVE route.** Every gate pointed there would then compare native against
native. **`ch-legacy` is the route `oracle_digest.py` defines and installing does
not touch it.**

**Checks 5, 6, 7 re-run on the new reference — all reproduce exactly.** And
**check 5's red reproduced unchanged**, so it was never an artefact of the old
reference. *(Since closed by `parity-finisher` at 20 of 20.)*

## ✅ `--verify` now REFUSES a swapped reference — falsified, not asserted

    FALSIFIER 1  old reference ~/.local/bin/ch  → REFUSES, exit 1
    FALSIFIER 2  THE INSTALL HAZARD, native ch  → REFUSES, exit 1
    CONTROL      .venv/bin/ch-legacy            → 0 drifted, exit 0

**Falsifier 2 is the hazard itself run as a test.** The message names the
mechanism, not the mismatch: every entry would disagree and the run would report
drift, **which reads as the port breaking.**

**Checked rather than assumed: exit 1 not 0** — my first reading was `tail`'s
status, not the gate's, so I re-measured without a pipeline. **stderr, not
stdout.** **Refuses before collecting**, so a wrong reference costs no pty runs.

## ❌→◐ CHECK 11 LOCALISED

### ⚠ I was wrong twice and both corrections are load-bearing

1. **I said a bisect was impossible — no commits, no older native binary. FALSE.**
   L280 records `tests/data/launcher-provenance/ch-0ffde41`, the `wip/cycle-02`
   branch build of 2026-08-25, **committed on disk with provenance.** Kept to
   falsify the launcher guard; it works as a performance baseline too. **Found by
   re-reading the record rather than searching for what I had concluded was
   absent.**
2. **My exec-hop prediction was wrong.** `ch-legacy` came back *slower*, 2120ms
   against 2067ms.

### The measurement — interleaved, three repetitions

| shape | today | branch 08-25 | today/branch |
| --- | ---: | ---: | ---: |
| literal miss | 262–268ms | 304–312ms | **0.84–0.87×** ← today FASTER |
| regex miss | 1654–1739ms | 356–411ms | 4.14–4.65× |
| selective literal | 916–954ms | 252–296ms | 3.10–3.78× |

**Two cost centres, and the plain scan is not one of them.**

**1. Regex evaluation, 4.1–4.7×.** The regex shape finds **nothing**, so this is
not hit handling. This port reproduces Python's regex semantics exactly; the
branch is prior art with known deviations.

**2. Per matching session — and it is NOT per hit. I tested that and it failed.**

    query            sessions   today    branch
    zqxjvwmkbphfgd          0   262ms    282ms
    needle                 25   925ms    273ms
    function              177  1721ms    335ms
    the                   553  1577ms    380ms

**Per-hit cost falls 26.5 → 2.4ms as hits rise, and 553 sessions cost LESS than
177.** It tracks work on matched sessions. **The branch pays it essentially not at
all**, staying 273–380ms whatever it matches.
**Grounded hypothesis, NOT a measured attribution: the confirmation pass**
(`search_confirm.rs:323` resolves `first_timestamp` per candidate; the record
establishes agent-bearing sessions *must* defer to confirmation or produce false
negatives, with two tests pinning it). **`sample` returns no frames against this
binary under the hardened runtime**, so finer attribution needs source access.

### ⚠ WHAT CHANGES THE MEANING OF A CHECK 11 FAILURE

**The gates are 0.30/0.25, set above recorded ratios of 0.142/0.105 — recorded in
the same window as `selective literal` at 360.3/372.8/568.0ms. I measure the
BRANCH at 252–296ms on that shape.** On 2026-08-28 the cutover had not landed and
`run` had no callers, **so the branch was the only native route that could serve
it.**

**So the gates were almost certainly derived from the branch — prior art that
decision 1 rules is never an oracle.** This is the runbook's own rule landing on
the runbook's own gates: *"'Native ignores X' and 'the branch ignores X' are
different claims."*

**Stated as a strongly-supported inference, not as fact.** What settles it is one
sentence from whoever ran that window: which binary was the subject. **I cannot
close it by measurement.**

**Recommended: if the subject was the branch, re-derive the two ratio gates
against this port with the correctness costs priced in. Do NOT relax them to
pass** — that is how the live-pool budgets reached 1750 and 2500.

---

# ▶ SIX RATIO GATES RE-DERIVED — 2026-09-01T18:23–18:27Z

**⚠ THE HEADLINE, AND IT SUPERSEDES "CHECK 11 IS A REGRESSION": the port is
FASTER than the route it replaces on every one of the six shapes, 1.8× to 33×.**
Check 11 was failing ceilings that were never about this port.

**Confirmed from the record, not inferred:** `review-profile-plan.md:99`, written
in the same edit that set the numbers — *"The native column is the reference
branch binary — **evidence that these budgets are reachable, not a claim about our
deliverable.**"*

## ⚠ AND MY OWN BRANCH COMPARISON IS WITHDRAWN

**The two branch builds are different artifacts.** The gates' subject was
`private-binaries/ch-native`, `40a5b5d8…`; mine was
`tests/data/launcher-provenance/ch-0ffde41`, `257f5052…`. **Same revision,
different build, so neither is a baseline for the other.**

**My 252–296 ms figures are withdrawn — including the half that favoured the
port.** Kept rather than deleted: *a measurement withdrawn is more useful than one
erased.* **Ignore both branch builds.**

## The numbers — interleaved, 5 pairs per shape, one window, vs `.venv/bin/ch-legacy`

| shape | port med | python med | ratio med | worst | spread | **proposed** | old |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| help | 5.8ms | 189.8ms | 0.030 | 0.032 | 1.29× | **0.048** | 25ms |
| broad literal miss, id-only | 261.8ms | 478.8ms | 0.550 | 0.568 | 1.11× | **0.852** | 750ms |
| broad list, absolute date | 988.9ms | 2450.8ms | 0.404 | 0.405 | 1.04× | **0.608** | 650ms |
| colored matches | 2332.0ms | 21596.6ms | 0.109 | 0.109 | 1.02× | **0.164** | 4000ms |
| selective literal, id-only | 914.0ms | 2091.1ms | 0.438 | 0.444 | 1.02× | **0.667** | 0.30× |
| broad regex miss, id-only | 1654.7ms | 3818.8ms | 0.434 | 0.445 | 1.03× | **0.668** | 0.25× |

**Reproducibility:** a separate earlier window with a different design gave 0.030,
0.549, 0.400, 0.109, 0.430, 0.436. **Two windows, ~2% agreement, no shape
disagreeing.**

## Why all six are ratios now

**Constraint 5 dissolves by construction: a ratio gate cannot be passed by the
reference, because the reference is 1.0.** As absolutes, `broad literal miss` had
its margin bounded *above* by discrimination — 1.5× landed at ~400ms with 18%
headroom to Python, and 2× reintroduced the hole. **A gate whose margin must be
hand-tuned to stay meaningful is barely working.**

**⚠ NOT the ratio construction that was disproved.** That one rotted because its
denominator was a **different command** whose growth did not track the subject.
**Here the denominator is the same query, same corpus, Python route, same window
— it scales identically by construction.** *Ratios fix rot, not noise; the noise
here is 2–4% on five of six.* **All three conditions hold now; none held there.**

## Two caveats I raised rather than buried

**1. What the margin buys. A 1.5× margin over the worst observed means every gate
tolerates the port becoming 50% slower before it fires.** Direct consequence of
the rule, uniform across rows. **Not an argument against it — it is checkable,
which is its virtue — but "50% slower passes" should be visible at the rows
rather than discovered later.**

**2. `help` is the one row where margin ≈ noise.** Spread **1.29×** against
1.02–1.11× elsewhere, because it is a 5.8ms measurement dominated by process
startup. Worst 0.032, ceiling 0.048. **The row most likely to flap — and the one
where flapping matters least.** No measurement settles it; it is a policy call.

**And `broad literal miss` is the thinnest advantage at 0.550**, so its 0.852
ceiling sits closest to 1.0: **most likely to catch a real regression, least room
to do it in.**

## Standing

**Measured by me; `parity-finisher` lands them. I edited nothing.**

---

# ✅ CHECK 11 IS GREEN — 2026-09-01T18:36:58Z–18:48:05Z

**⚠ THE COMMAND EXITS 1 AND CHECK 11 DID NOT FAIL.** `performance_gates.py`
covers checks 11 **and** 12 in one invocation. **The exit code is check 12's
memory parity. Do not read it as check 11.**

## The run is valid, not void

**Tree digest `63a34f4f26451d0c…` identical BEFORE and AFTER the build.** Oracle
`dd6ab701…` unchanged. New binary **`1f76081cd87a2808`, 7,588,272 bytes**, built
21:37:07 — **different from `47fa6038`, which confirms `terminal.rs` and
`search_output.rs` really were absent from the artifact I nearly measured.**

## All six pass

| shape | measured | ceiling | |
| --- | ---: | ---: | --- |
| help | 0.033× | 0.06× | PASS |
| broad literal miss, id-only | 0.552× | 0.71× | PASS |
| broad list, absolute date | 0.397× | 0.51× | PASS |
| colored matches | 0.108× | 0.14× | PASS |
| selective literal, id-only | 0.435× | 0.56× | PASS |
| broad regex miss, id-only | 0.433× | 0.56× | PASS |

Plus all three memory budgets: 450MB / 598MB / 491MB.

## The falsify hole closed in the shape it was meant to

**Every shape now fails against the reference** — 1.021, 1.001, 1.004, 1.000,
1.008, 1.005, **all ~1.0 by construction and all above their ceilings.**

**`broad literal miss` is the proof:** it passed its 750ms absolute on the *Python*
route at 462ms, and now fails at 1.001 against 0.71. **Same shape, from proving
nothing to proving the most.**

## ⚠ A property I did not design for, and it is the one that matters most

**The ceilings were derived on `47fa6038` and pass on `1f76081c`** — a rebuild
including two changed source files. Measured 0.033 / 0.552 / 0.397 / 0.108 /
0.435 / 0.433 against derived 0.030 / 0.550 / 0.404 / 0.109 / 0.438 / 0.434.

**Third independent window, still ~2%, and on a different binary. So the gates are
not overfitted to the artifact they came from** — which is exactly what a
re-derived ceiling is most at risk of being.

## Still red, owned, and not check 11

**Check 12: +576MB against +446MB, 1.29×** — the documented figure to three
digits, mechanism resolved, unattributed, ruled *"its own task, not part of B1."*
**Control passes at both arms near zero, so the gate works.** Check 13 is the same
story.

**Raised as a decision rather than an oversight: it is a real, measured,
unexplained memory regression, and I would not want the install to travel without
someone having said out loud that it is accepted.** I have no view on the product
tradeoff.

## ⚠ THE MISTAKE OF THE DAY WAS MINE AND IT REPEATED

**I printed file times without dates.** A file last touched **2026-08-28**
T21:33:45 sorted as newest because its clock time sits near now. **Four days
collapsed into one evening, twice.**

**And the direction is the unusual part: I corrected myself INTO being wrong**, and
sent the wrong version with more confidence than the right one. My first reading
was sound; the "correction" used the broken sort.

**A correction is not self-verifying. It needs the same instrument check as the
claim it replaces.** Same class as `tail`'s exit status this afternoon, which I
caught in seconds because I already knew it. **This one wore a different coat.**

**What kept it cheap: I reported both times instead of acting.**

## ✅ STANDING PROCEDURE EARNED HERE — for any build on this checkout

**Take the tree digest immediately before and immediately after the build. If they
match, the binary corresponds to exactly that tree state, whoever touched what and
when. If they differ, the run is void and is reported as void, not as numbers.**

**That answers by measurement what a timestamp only answers by inference** — which
is why my timestamp reading could be wrong twice without doing any damage.

---

# ▶ THE MEMORY QUESTION, MEASURED FOUR WAYS — 2026-09-01T18:5xZ

**Four numbers, and no two answer the same question. Any one alone misleads.**

## 1. The crossover, as a product sentence

**Below ~30 MB of payload the native route uses LESS memory; above it, more.** At
8 MB it is **95M against 140M**. Level at 32 MB (311 vs 310). At 96 MB, 887
against 755. **The port's fixed cost is 21 MB against Python's 82; it loses only
on slope.** *"1.29×" implies a uniform regression and there is not one.*

## 2. The real session distribution — 695 sessions, 1,129 MB

    median 0.54 MB   mean 1.62 MB   p90 2.82 MB   p95 5.54 MB   p99 22.00 MB   max 83.29 MB
    over  8 MB:  26  (3.74%)        over 30 MB:   6  (0.86%)

## 3. ⚠ Peak memory over the REAL corpus — the figure already inside check 11

| shape | native | python | ratio |
| --- | ---: | ---: | ---: |
| selective literal, id-only | 450MB | 1141MB | **0.39×** |
| broad list, absolute date | 598MB | 1459MB | **0.41×** |
| colored matches | 491MB | 1435MB | **0.34×** |

**On the real corpus the port uses ~40% of Python's peak — a 2.5× improvement.**
**This was sitting in check 11's own output the whole time and I nearly missed it.**
*Three seats today found the answer inside a result they had already reported.*

## 4. ⚠ THE SIX SESSIONS OVER 30 MB — and they REVERSE by shape

```
session   scan + confirm (. -ll)      full render (. coloured)
   MB     native  python  ratio       native  python  ratio
 34.6M      89M     56M   1.59x        126M    325M   0.39x
 37.9M      98M     56M   1.75x        139M    446M   0.31x
 41.7M     113M     56M   2.01x        155M    426M   0.36x
 47.2M     105M     56M   1.88x        154M    315M   0.49x
 61.9M     155M     56M   2.75x        218M    671M   0.32x
 83.3M     192M     56M   3.39x        276M    892M   0.31x
```

**⚠ THE FINDING IS PYTHON'S COLUMN.** On id-only scanning **Python's peak is FLAT
at 56M from 34.6 MB to 83.3 MB — it does not grow at all.** The port grows with
the session, so the ratio climbs monotonically to **3.39×** and would keep going.

**That says the extra copies are a PER-SESSION ACCUMULATION, not a constant
overhead** — a sharper starting point for checks 12 and 13 than the synthetic
probe gave in two days. **Streaming versus materialising is the obvious reading
and I did not measure it, so I am not claiming it.**

**On full rendering it reverses decisively**, 0.31–0.49×, which is where the 40%
corpus figure comes from. **It is a rendering-weighted answer.**

## ⚠ I WITHDREW MY OWN PRODUCT READ, AND WHY IT WAS WRONG

**I called this "a footnote, not a blocker" on the grounds that 99.14% of sessions
sit below the crossover. The file-size threshold was the WRONG AXIS.**

**The port is heavier on id-only scanning at EVERY size I measured**, and the six
were only where I looked. **The question is not how many sessions exceed 30 MB —
it is which shape the user runs, and `-ll` is a headline flag, not an expert one.**
*A true statistic answering a question nobody asked.*

**Corrected read: not a blocker, but not a footnote.** A real, size-dependent
memory regression on one common shape **with a benign absolute ceiling** — worst
native figure anywhere is **276M**. **The ratio is bad and the absolute is small,
and both are true.** The captain gets the 3.39× and the 276M in one sentence.

## Standing

**Check 15 held pending the captain's install decision. If authorised: install,
re-derive both digests, re-run 15, and nothing else gets built or installed until
I report.**

---

# ✅ CHECK 15 GREEN — G5 CLOSED. 2026-09-01T19:19Z

## The install

Wheel **rebuilt** from a purged `build/` and `dist/` — the earlier one was stale
at `47fa6038`. **Verified before installing: the wheel ships `1f76081cd87a2808`,
byte-identical to the binary every gate measured.** `entry_points` expose only
`ch-legacy`. Installed once, `uv tool install --force`.

**Digests identical before and after the install:** tree `63a34f4f26451d0c`,
oracle `dd6ab701…`.

## ✅ Check 15

    wheel            1f76081cd87a2808e0f6eed0407b98149e0e7212c4b4cedd7f16c529bd8e512f
    ~/.local/bin/ch  1f76081cd87a2808e0f6eed0407b98149e0e7212c4b4cedd7f16c529bd8e512f

**The shipped artifact is the one measured.** Full sha, not a prefix — this is the
row that exists to catch a near-miss.

## ✅ Check 10 re-run on the INSTALLED artifact, not a build-tree copy

Alone, no sibling, stripped `PATH`: **search exit 0, 934 bytes, 31 escape runs;
`info --help` exit 1 with the private-entry error.** **The thing users actually run
passes check 10 by itself.**

## ⚠ THE HAZARD MATERIALISED AND THE GUARD FIRED

**This morning `~/.local/bin/ch` was `22236c08`, a Python-delegating launcher, and
it was the reference for checks 3, 5, 6, 7 and 11. It is now `1f76081c`, the
native route.** Every one of those gates would now compare native against native.

    check 3 vs .venv/bin/ch-legacy   → 82 stored, 0 drifted, 0 new
    check 3 vs ~/.local/bin/ch       → REFUSES, exit 1
        frozen against c1821a3a86ee9a88
        given          1f76081cd87a2808

**`.venv/bin/ch-legacy` is untouched at `c1821a3a86ee9a88`. Installing does not
reach it — the entire reason the move mattered.**

**The loop closed: predicted in the afternoon, reference moved, refusal built and
falsified against a hypothetical, and by evening the hypothetical was the real
installed path and the refusal fired on it.** *It stopped being a precaution about
an hour before it was needed.*

## For whoever takes the deletion slice

**⚠ Before the Python authority is deleted, every instrument that consults it must
have its last consultation stored** — decision 6, L1, L23. **Cheap now, impossible
after. This seat refuses the deletion if that is not confirmed.**

**Two things that will bite the deletion specifically:**
1. **`.venv/bin/ch-legacy` IS the oracle** — `oracle_digest.py` defines the route
   as `src/chats/**.py` + that entry + the installed RECORD. Deleting the Python
   authority moves the oracle digest, and **every artifact stamped with
   `dd6ab701…` becomes unverifiable rather than wrong.**
2. **`frozen_reference.json` is the stored side of that conversation** and is
   already provenanced, self-describing and independently re-derivable. **It is
   what survives. Check it is what you think it is before you delete the live
   half.**

---

# ▶ THE DELETION SLICE — enumeration, three rulings, and the order

**Enumeration: `teammates/g5-runner/deletion-enumeration.md`, 116 lines.**
**Absolutes spec: `teammates/g5-runner/perf-gate-absolutes.md`, 96 lines.**

## The scope fact that organises everything

**`ch-legacy` is NOT deleted.** The charter keeps it for default parsing and
unscoped commands. **What goes is the Python SEARCH authority.** An instrument
running `ch-legacy parse` survives; one running `ch-legacy search` does not.
**Same binary — the distinction is the subcommand.**

## What the enumeration found

**A. STORED, 9 artifacts, all confirmed on disk rather than assumed** — including
**both of decision 6's own named freezes**, `frozen-oracle-age-colour` (15 files)
and `frozen-oracle-nfc-nfd` (13).

**B. LIVE, dies at deletion** — four contract tests, the 0-of-72 `COLUMNS` sweep
built today, and all four deliberate-divergence tests. Plus the six ratio gates.

**⚠ The shape of the loss beats the count: the contract suite runs 227 cases
twice, once against 454 stored files and once against live Python. The stored half
survives. But the live half exists to catch the stored half going stale — so the
deletion removes the check on the check.**

**C. ⚠ THE ONE NOBODY HAD: `tests/oracle_digest.py` digests the ROUTE**, which is
`src/chats/**/*.py` + entry + RECORD. **Deleting the search authority moves the
digest, so every artifact stamped `dd6ab701…` becomes UNVERIFIABLE rather than
wrong.** *Decision 3 from the other end: there a restamp turned unknown into
verified; here a deletion turns verified into unknown.*

## The three rulings

**1. Ratios become ABSOLUTES on the frozen corpus.** Sound here for a reason it
was not before: **absolutes died because the LIVE POOL grew, and a digest-pinned
corpus cannot grow.** Name `de693c35…` at the gate or a reader sees a reversal.
**Rejected: a ratio against a surviving `ch-legacy` subcommand** — a different
command whose growth does not track the subject is the construction
`parity-finisher` disproved at 1.04 → 1.54.

**2. `dd6ab701` stays re-derivable** — the first mate commits the pre-deletion tree
as a checkpoint, so the route is recoverable and every stamp stays checkable.
**Each stamped artifact records the revision and that the digest is re-derived
from it.**

**3. The stored halves are accepted, with two non-optional conditions:** the last
live run of every twin is **executed and recorded** immediately before deletion
(*that sentence is the consultation being stored*), and **the degradation is
written at each frozen twin** — what it asserted before, what it asserts after.

## ⚠ The cost of ruling 1, now an assertion rather than a habit

**An absolute generous enough to absorb a noisy machine can quietly stop
discriminating, and a ratio could not.** My first derivation proved it: **one
contended 490ms run against a 260ms median produced a 980ms ceiling — above
Python's 464ms.** Nine reps show 251–256ms. **A 3× ceiling difference from one run
nobody would have seen.**

**`parity-finisher` is landing it as a gate assertion: every ceiling must be below
the recorded Python figure, checked in the gate, failing loudly.** The historical
column is already there, so it costs nothing.

*The other fault was its opposite: rounding to nearest put `help`'s ceiling below
its own worst run and would have failed a working product. **One rounding rule and
one outlier, opposite failures.***

## THE ORDER FROM HERE — nothing skips

1. **The absolutes land** (`parity-finisher`).
2. **I run and record the final live pass on every twin** — with both routes alive,
   result written down before anything is removed.
3. **The first mate makes the checkpoint commit.**
4. **The deletion.**

**This seat refuses the deletion if step 2 is not done and recorded.**

---

# ✅ STEP 2 DONE — the final live consultation, recorded

**`teammates/g5-runner/final-live-consultation.md`, 107 lines. THAT DOCUMENT IS
THE STORED CONSULTATION.**

**373 live comparisons against the Python search authority. Every one passed.**
Contract twins 289, `COLUMNS` sweep 73, deliberate divergences 11.
**Both digests re-derived after the run and identical, so the record is not void.**
Full shas throughout. **The installed launcher is byte-identical to the build, so
it describes the artifact users have.**

## ⚠ WRITING THE DEGRADATIONS FOUND WHAT THE ENUMERATION MISSED

**The enumeration classified these as live twins. Only the degradation note asked
what each one's FROZEN form would say — and three had no answer.**

`test_named_defect_patterns_select_the_same_sessions`,
`test_generated_patterns_select_the_same_sessions` and
`test_columns_sweep_reproduces_legacy` **had no frozen twin at all.**

**Ruled: a gate with no successor is not a weakened gate, it is a deleted gate —
and deleting a gate needs a reason nobody gave.** *Third time this week an
instrument produced its most useful output as a by-product.*

# ✅ THE THREE SUCCESSORS — captured, 150 answers

**`probes/capture_selection_baseline.py` → `tests/data/legacy-selection-baseline/`,
634,043 bytes.**

    defect-patterns      18   `search <pattern> -ll` at 96 columns
    generated-patterns   60   seed 20260828, widths 52/96/110/140
    columns-sweep        72   18 COLUMNS values x 4 shapes, TERM=dumb
                        150

**All three counts match what the live gates actually run** — the successor covers
the same space, **not a convenient subset.** Both streams **and** the exit code are
stored, because two of these gates assert on stderr.

**The harness is IMPORTED, never copied** — `_run_search`, `_normalize`, `SHAPES`,
`COLUMNS_VALUES`, `_run`, the seed, the count, the widths. **A hand copy grades the
successor against a drifted definition and both sides pass while measuring
different things.** *Fourth refusal of that defect in one day.*

## The refusal, falsified five ways

    complete set                                          ACCEPTED (control)
    one case short                                        REFUSED
    a whole group empty                                   REFUSED
    a group missing entirely                              REFUSED
    a case that cannot fail (exit 0, both streams empty)   REFUSED

**⚠ The fifth is the one I would not have thought to add a week ago: a comparison
that cannot fail, recorded as if it could. It would have looked like a corpus.**

## The degradation is IN the file, as a field met before the data

**BEFORE:** each gate ran both routes and could see the port drift from Python.
**AFTER:** it asserts the port still produces what Python produced on 2026-09-01
at `dd6ab701…`.
**⚠ AND THE SECOND-ORDER LOSS, which is the general form for every frozen
successor built today: it can no longer detect that this recording was itself
wrong, because the route that would have said so is gone.**

## ✅ THE BOUNDARY, RULED MY WAY

**I built the recording and stopped. `parity-finisher` writes the three
assertions.**

**The standing line, granted twice and it held: you may make the instrument
capable of recording; you may not make a record agree.** A capture probe is on the
instrument side; **the tests that assert against it are not.**

***"The runner wrote the gate he then verified" is the one sentence that would undo
today's separation.*** **Ask for the edge to be ruled rather than assume past it —
even when the task was handed to you.**

## ORDER — hold here

1. ~~absolutes land~~ ✅
2. ~~final live pass run and recorded~~ ✅
3. **`parity-finisher` lands the three assertions** ← waiting
4. first mate's checkpoint commit, **after 3 so it captures them**
5. the deletion

---

# ⏸ STOP POINT — 2026-09-01, soft-pause

## ⚠ THE FIXED-HOME DECISION, recorded so it is never rediscovered

**Even if this recording were lost, this reasoning must survive.**

**`tmp_path` is the obvious fixture for a capture and it is the defect.** The
`invalid-date` shape's stderr names session paths. **The product wraps that text at
the sweep width while the real path is still in it**, and `_normalize` substitutes
the home afterwards — **so a plain string replace cannot repair a break that landed
inside a path.** Recorded at one temporary home and replayed at another, the breaks
fall at different offsets and **a byte-perfect product fails.**

**Measured: 16 of 72 rows affected — and one had already failed normalisation
outright**, keeping a raw `/var/folders/…` path because the break landed *inside*
the home rather than after it. **So matching lengths alone was never sufficient.**

**The cheap workaround is REJECTED, and the reason is the ruling:** collapsing
whitespace inside paths before comparing **would stop the sweep seeing wrap
differences, and the wrap composition is the entire reason the gate exists** —
`preserve-because-wrong` item 9, two width resolvers composing at every value.
***A gate that cannot see wrapping is not a weaker version of that gate; it is a
different one that passes.***

**The cure:**

    columns_sweep_home        /tmp/ch-columns-sweep-home/home
    columns_sweep_home_length 31

**Replay at a home of EXACTLY that length. The path need not match — the LENGTH is
the contract.** Falsified by replaying at `/tmp/ch-columns-sweep-ALTX/home`:
different characters, same length, **72 of 72 byte-identical on stdout, stderr and
exit code.**

**And the capture now REFUSES any row whose output still carries a raw home path
after normalisation** — the fault converted from something a teammate caught into
something the instrument cannot do again.

## What is on disk from this seat

**⚠ Inventory refreshed 2026-09-02 after the disk cleanup. `evidence/` is new.**

| file | size | state |
| --- | --- | --- |
| `RESUME.md` | 83 KB | current |
| `evidence/final-live-pass.log` | 1,690 B | **⚠ raw output of a run that can never be re-taken** |
| `evidence/README.md` | 798 B | says why that one log was kept and the rest deleted |
| `deletion-enumeration.md` | 6.8 KB | complete |
| `final-live-consultation.md` | 4.9 KB | **the stored consultation, 373 comparisons** |
| `perf-gate-absolutes.md` | 4.9 KB | landed by `parity-finisher` |
| `perf-gate-rederivation.md` | 5.6 KB | superseded by the absolutes, kept |
| `check-10-baseline.md` | 2.3 KB | promoted verbatim into the runbook |
| `probes/capture_selection_baseline.py` | 10 KB | complete, refusals falsified |
| `tests/data/legacy-selection-baseline/` | 631,188 B | **complete, 150 answers, revision corrected** |
| `tests/data/oracle-route-inputs/` | 1,383 B + README | **⚠ DO NOT DELETE — makes `dd6ab701` re-derivable** |

**Nothing half-written. Nothing uncommitted that is mine to commit — this seat
commits nothing.**

---

# ⚠ `dd6ab701` WAS NOT RE-DERIVABLE FROM THE COMMIT — found, fixed, proved

**I was told to record `67d6053` as the revision. I verified before writing and
the claim was false.** *Writing a provenance claim I have not verified is the one
thing this seat exists to prevent.*

## The finding — the deepest thing about decision 3, and nobody had noticed

**`oracle_route_digest` has THREE inputs and git holds ONE.**

    1. src/chats/**/*.py    31 files   IN THE COMMIT
    2. .venv/bin/ch-legacy    321 B    NOT IN GIT — .gitignore:13 ignores .venv
    3. dist-info/RECORD     1,062 B    NOT IN GIT

**Checking out `67d6053` gives 31 Python files and no venv.**

**⚠ AND THE REASON IS DECISION 3'S OWN ARGUMENT.** The route digest exists
*because* a source-only digest is insufficient — *"a `git diff` digest cannot see
the launcher or the installed RECORD, so a concurrent `uv sync` moves the oracle
invisibly."* ***The property that makes it a good pin is the property that makes
it unrecoverable from a commit.*** **Every artifact pinned that way has this
shape.**

## The cure — 1,383 bytes, and the procedure EXECUTED not asserted

**`tests/data/oracle-route-inputs/`** — `ch-legacy`, `RECORD`, and a `README.md`
opening **"⚠ DO NOT DELETE. These are not stray virtualenv artifacts."** *Two
small files in a test directory look exactly like leftovers.* It carries the
reason, not just the instruction.

**The procedure is beside them because `oracle_digest.py` reads the LIVE venv** —
a reader with the files and no instructions still cannot do it.

**Executed 2026-09-02, using the STORED copies rather than the live ones, which is
what proves the stored copies work:**

    reconstructed  sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
    recorded       sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0

## How the field was written in each artifact, and why they differ

**`frozen_reference.json` — DERIVED.** The field went into
`freeze_references.py` and the file was re-frozen. **82 stored, 0 drifted, 0 new.**
***Hand-patching would have reintroduced exactly what I deleted from this file
yesterday — a field nobody derived.***

**`legacy-selection-baseline.json` — PATCHED, because re-recording was ruled out.**
**Proved the answers were untouched: 0 of 3 groups changed**, by hashing each
group before and after. **The capture script now derives it**, with a comment at
the site saying `git rev-parse HEAD` was the wrong source and was used once — *a
one-time exception that documents itself out of existence.*

**Why the old value was worse than nothing: `8cb4c5f79cf6` predates every line of
this mission.** Captured by `git rev-parse HEAD` against an uncommitted tree, so
**no revision could have reproduced it — honest and useless in the same breath.**
**A reader tries it and concludes the record is wrong.**

## Not mine, recorded as a stated gap by the first mate

The contract corpora and the stderr baseline are closed seats' artifacts: they
carry `dd6ab701` and name no revision. **The revision is `67d6053`.** *A gap
written down is navigable; one that is not is a dead end.* **`final-change-log.md`
does not exist yet — it is a phase-5 deliverable, written after the deletion and
the re-proof.**


---

## Disk cleanup — 2026-09-02, admiral's policy

**35 MB of my own scratch removed, nothing that changes a resume instruction.**
Binary copies (re-copied), timing logs (re-run), superseded probe scripts, the
pre-fix recording, and backups of files whose fixes are verified and re-frozen.

**One judgement made rather than escalated: the `dd6ab701` reconstruction tree is
disposable**, because the procedure regenerates it from `git archive` in four
steps — ***and that it regenerates is the whole point of having written the
procedure down.***

**One thing promoted rather than deleted: `evidence/final-live-pass.log`.** The
final live consultation can never be re-run. `final-live-consultation.md`
transcribes its counts; **this is the output they were transcribed from.** *A
number in a document and the run that produced it are two different records, and
only one of them stops being obtainable.*

**Preserved and spot-checked untouched:** `oracle-route-inputs/`,
`legacy-selection-baseline/`, `launcher-provenance/ch-0ffde41`,
`target/release/ch` at `1f76081c`, `/private/tmp/ch-pool-snapshot`.
