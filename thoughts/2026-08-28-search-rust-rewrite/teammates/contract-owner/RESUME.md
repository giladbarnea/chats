# RESUME — contract-owner

Keep current while working, not when stopping. A pause can arrive without warning.

Last updated: 2026-08-28, at the admiral's pause. Nothing reverted, nothing
committed.

---

## READ THIS BEFORE RE-RUNNING ANYTHING

**Correction to an earlier version of this file.** It said the two unintended
failures were a concurrent reinstall, with evidence, and I was wrong. They were
a real defect plus a harness bug of my own. That explanation is withdrawn; do
not act on it if you find it quoted anywhere.

**What they actually were.** The case was `amendment:lowercase-z-bodies`.
`ch search -f` over a session whose timestamp ends in a lowercase `z` **crashes**:
`model.py:34` does `datetime.fromisoformat(timestamp.replace("Z", "+00:00"))`,
which handles only the uppercase spelling. Exit 1, uncaught `ValueError`, stack
trace to stderr, on a spelling ISO 8601 permits.

It read as a flake because a traceback's first frame names the executing script,
and the private-launcher copy — the fix for the shared-artifact race — put a
per-run temporary path there. Reproducing by hand used the shared path and
matched. **A fix for one nondeterminism class created a second one, visible only
in the single case whose output names its own executable.**

Both are closed. The launcher directory is normalized, and the crashing case is
removed rather than re-recorded, because a traceback bakes machine paths and this
is a crash where the crash is the bug.

**Where things stand:**

1. ✅ `cargo build --release --bin ch --no-default-features`
2. ✅ `work/rebless_oracle.py` — **252 of 252 cases reproduced their recorded
   bytes**, so both corpora are re-blessed at revision `8cb4c5f79` with the
   route-wide digest. The oracle moved twice without moving behaviour.
3. ⏳ One confirming full run outstanding, held while `session-core` has the
   launcher window. Expect 251 intended reds from
   `needs_no_private_legacy_entry` and nothing else — 251, not 252, because the
   crashing case was removed. Targeted runs of the streaming test and every
   amendment case are green.

Do not re-derive expectations to make the guard quiet. That is the difference
between proving behaviour unchanged and re-characterizing, and re-characterizing
turns a parity net into a mirror.

---

## What I own

`tests/` in its entirety, and the fixture corpora under `tests/data/`. Nobody
else edits them. I edit no production source.

## What is done and green

- **`tests/test_search_command_contract.py`** — five proof classes over the
  public `ch search` journey. Byte lock, live differential against
  `ch-legacy search`, empty-directory authority proof (intended red) with two
  controls, query-validity differential, pty terminal differential.
- **`tests/data/search-contract-fixtures/`** — the frozen corpus, 227 cases.
  173 shapes inherited from branch `wip/cycle-02-native-default-pause-20260821`,
  every expectation **re-derived** from the Python product on `main`. 48 shapes
  are this contract's own.
- **`tests/data/search-amendment-fixtures/`** — 25 post-freeze cases in their own
  pool. Built, expectations derived, **not yet wired into the suite's runs**
  (see below).
- **`tests/query_pattern_corpus.py`** — `query-semantics`'s pattern generator and
  their 18 named defect patterns.
- **`tests/conftest.py`** — resets `chats.console`'s four cached `Console`
  globals per test. Validated green across the whole in-process suite under
  `-n 8 --dist=loadfile`.
- **`tests/lib.sh`** — shell fixture home moved to a per-run subdirectory so two
  concurrent shell suites stop deleting each other's fixtures.

## What is half-done — pick this up first

**Only the re-bless and clean re-run above.** Everything else is finished. Both
corpora are wired into the suite, 795 tests collect, and the first oracle event
has been handled.

## Three defects deliberately absent from the corpus

Recorded in `contract.md` under **"the surface no golden can own"**. Both are
public and reachable. Neither can be a fixture, for the same reason: the oracle
produces no usable answer, so there is nothing to record, and recording what it
does produce would commit the native route to reproducing a defect. Both are
ruled repaired rather than reproduced, and both become testable when the repair
lands.

- `ch search '(a+)+b'` over 40 consecutive `a` characters never terminates.
- `ch search --short ² needle` raises an uncaught `ValueError` from `cli.py:78`;
  `str.isdigit()` accepts digits with no decimal value.
- `ch search -f` over a session whose timestamp ends in a lowercase `z` raises an
  uncaught `ValueError` from `model.py:34`. `session-core` owns the repair, which
  should close this and the silent metadata-path fallback together.

Do not add fixtures for these on resume. Adding one would lock in the defect
rather than the behaviour.

The last open item was the amendment corpus's wiring. `test_search_command_contract.py`
carries a `Corpus` dataclass and `ALL_CASES` spanning both corpora, and the three
case-parameterized proof classes take a `(corpus, case)` pair. Confirmed by
`rebless_oracle.py` exercising all 252 cases across both pools, and by a full
pytest run.

## The first oracle event, handled — worth reading before the next one

`search-runtime`'s clock seam moved `src/chats/commands/search.py`. The guard
fired and named the cause in one line rather than producing several hundred
parity failures that would have read as the seam breaking parity.

The seam claimed "does not change behaviour when unset". `rebless_oracle.py`
replayed all 252 cases in both corpora: **252 of 252 reproduced their recorded
bytes**, so the claim is measured rather than asserted, and both `ORACLE.json`
files are re-blessed to `sha256:b1ae8f94…`.

Do the same for the next oracle event. Do not re-derive expectations to make the
guard quiet.

## Blocked / waiting

Nothing. `cargo build --release --bin ch --no-default-features` was red for a
period during `session-core`'s exclusive window on `target/release`; it is green
again. Ask `search-firstmate` before reaching for the installed launcher or
`target/release`, because windows are granted rather than assumed.

## Uncommitted production edits

None by me. I edit no production source. `tests/` and `tests/data/` carry my
work and are uncommitted; `src/chats/commands/search.py` and `rust/` carry other
people's uncommitted edits.

## The normalization ordering defect — do not reintroduce it

`_normalize` must replace the **age token before the age colour**. The colour
replacement rewrites the SGR introducer the token pattern anchors on, so the
reverse order silently disables the token substitution: `{AGE}` appeared in zero
files while `{AGE_STYLE}` appeared in fifteen, and seventeen expectations carried
a live wall-clock `1w`. That is the exact defect this contract was written to
avoid, with the halves swapped.

Guarded now by `test_every_normalization_placeholder_is_accounted_for`,
`test_declared_normalizations_appear_in_the_corpus`, and
`test_no_expectation_carries_a_raw_age_token`. Every placeholder is declared with
whether the corpus should contain it; three are legitimately absent and say why.

The corpus was regenerated once for this, with `search-firstmate`'s approval, and
the movement was proved rather than asserted: age token neutralized on both
sides, byte-identity required, 17 files changed and nothing else.

## Before the Python search implementation is deleted — three conversions

Cheap while Python is alive, impossible afterwards. Enumerated mechanically, not
from memory: four test functions reach the Python route.

**Dies free, convert nothing.** `test_search_journey_matches_live_legacy_implementation`
— the byte lock already holds the expectations it would freeze into. Delete the
class as part of the slice. **It is over, not broken**, and that has to be in the
slice's record or it reads as a regression later.

**Need freezing — the comparison *is* the oracle and nothing is stored.** Run the
Python side once, store exit status and bytes, compare against the record after.
Under an hour for all three; the generator and normalization already exist.

1. `test_named_defect_patterns_select_the_same_sessions` — 18 patterns.
2. `test_generated_patterns_select_the_same_sessions` — 60 patterns × 4 widths.
3. `test_colored_terminal_output_matches_live_legacy_implementation` — 5 shapes ×
   2 pty widths.

**Survive.** The byte lock, the authority proof, the normalization gates, the
calibration, and the age token/style test. Plus three that survive *by accident*,
because they compare one binary against itself rather than against an oracle:
`test_narrow_terminal_actually_elides`, the streaming gate, the early-close gate.
None was designed for durability; the shape of the question gave it to them.

**Partial.** `test_tool_visibility_oracle.py::test_table_oracle_still_describes_the_python_product`
imports `chats.tool_filter`. Survives the search deletion since `tool_filter`
also serves parse; dies only if that module goes, leaving the table stamped but
no longer re-verified.

**Ordering, which is the point:** the live differential is the proof that the
cutover preserved behaviour; the byte lock is the proof that survives it. Do not
let the deletion land while the differential is the only thing that has verified
a recent change.

## Table oracles need both halves of the guard

`tests/data/tool-visibility-oracle/` holds 7315 recorded answers for
`resolve_tool_visibility`, guarded by `tests/test_tool_visibility_oracle.py`.

Two checks, because they fail differently:

- **The stamp** answers *was this generated against the current oracle*. Catches
  a stale table.
- **Re-verification** answers *does it still describe that oracle*. Catches a
  generator bug, or a hand re-bless that skipped the proof. A stamp alone cannot.

Any table where re-verification is possible should have both — and it usually is
possible, because the unreachable half is the Rust one; the Python side is an
ordinary importable function.

The table's third guard asserts its 696 specificity-tie cases survive. Everything
else in it passes against both falsified wrong ports, so a trim would leave a
green suite with no ability to fail. The two ports and their 558 and 634
divergence counts are in the module docstring, so the justification travels with
the fixture.

## The tools, and what each refuses to do

All under `work/`. Every one of them fails loudly rather than papering over.

| script | what it does | what it refuses |
| --- | --- | --- |
| `generate_fixtures.py` | Derives the frozen corpus from the Python product | Building a corpus where two sessions share a stat mtime, because search's stable sort then falls through to `read_dir` order |
| `generate_fixtures.py --amend ID…` | Derives only named cases | — |
| `generate_amendments.py` | Builds the amendment corpus | Same tie check |
| `rebless_oracle.py` | Updates `ORACLE.json` after an oracle event | Updating when any case's bytes moved; prints which |
| `calibrate_contract_harness.py` | Grades capture *and* comparator against `reviewer-profiler`'s 14 probes | Any capture blindness, any comparator blindness beyond the declared one, and a declared-blindness rule that has drifted permissive |
| `hunt_flake.py` | Replays the corpus outside pytest, printing differing bytes | — |

## Decisions that would be expensive to rediscover

**The corpus is frozen; amendments go in a second pool.** Adding a session file
to the frozen corpus is not an amendment. The session pool is an input to every
broad-pattern case in it — `.` and `zznope|` match everything — so six new
sessions move roughly a fifth of the expectations. That is invalidation wearing
an amendment's clothes.

**A shape defined relative to *now* cannot be a fixture; a shape at a fixed
calendar instant is exactly what a fixture is for.** Age bands are the first
kind and live in a clock-relative test. The DST fold is the second kind and
lives in the corpus. This distinction is why the inherited corpus rotted from
green to red in three days and mine does not.

**Some expectations are wrong on purpose and say so at their definition.** The
age label and colour disagree by one bucket. One trailing space on the last line
is deleted and two are not. `truncate_middle` counts code points and splits
grapheme clusters. Do not "fix" them: if a future change makes them right, the
behaviour has moved and those cases are supposed to say so.

**The no-Python proof is a filesystem proof and the alternatives are measured
dead.** `exec` replaces the process image, so "did `ch` spawn a Python child"
sees nothing; and macOS purges `DYLD_*` across the exec, so a loader trace
reports zero Python libraries for a route that is entirely Python. Only the
absence of the `ch-legacy` file on disk can fail.

**Suites must copy build artifacts before measuring them.** `target/release/ch`
is shared, and another suite's fixture unlinks and rebuilds it. Measuring it in
place produced a different failing set every run for an hour.

## Queued, specified, not built

Nothing. The DST fold, lowercase `z`, trailing-space asymmetry,
`session-core`'s six branch fixtures and my six shortening cases are all built —
the first three plus the branch fixtures in the amendment corpus, the shortening
cases inside the frozen 227.
