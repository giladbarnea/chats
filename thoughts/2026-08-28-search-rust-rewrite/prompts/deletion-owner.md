# Role: deletion owner

Read in this order:

1. `@thoughts/2026-08-28-search-rust-rewrite/charter.md`
2. `state.md` — **read the header first. The `L`-numbered section at the end is
   newer than everything above it, and the last ~60 entries are this week.**
   **L349–L367 are the state you inherit.**
3. `teammates/g5-runner/deletion-enumeration.md` — **every instrument that consults
   the Python search authority, each with its consultation stored or not.** The
   list you are deleting against.
4. `teammates/g5-runner/final-live-consultation.md` — **373 live comparisons, all
   passed, taken while both routes existed. It cannot be retaken.**
5. `teammates/parity-finisher/RESUME.md` and `teammates/cutover-finisher/RESUME.md`.
6. `decision-record.md`, `preserve-because-wrong.md`.

Load `load-project-context`, `tdd`, `write-tests`, `ai-to-leader`,
`ai-to-delegated`.

## You are the last seat. Five things, in order, and nothing else.

**`ch search` already runs on Rust and is installed.** G5 is closed — 15 checks, 13
green, 2 red and accepted with their numbers. **What remains is removing the Python
search authority and proving the route still works without it.**

1. **Wire the frozen selection gate to the shared divergence authority.**
2. **Re-run all 94 assertions.**
3. **After green, hand the checkpoint commit to `search-firstmate`** — see commit
   policy below.
4. **Delete the Python search authority.**
5. **Hand a stable tree to `g5-runner` for the full post-deletion proof.**

**No other parity work. No refactors. If you find a defect outside these five,
report it; do not fix it.**

## 1 — the gate wiring, and it is smaller than it looks

**`tests/test_legacy_selection_frozen.py` fails one row: `posix_class_future_warning`
in the `defect-patterns` group.** The native route emits the bare warning text where
Python emits `file:line:` before it and the offending source line after.

**⚠ This is not a defect. It is already ruled.** `tests/deliberate_divergences.py`
holds `WARNING_DIVERGENCES` and rules against reproduction explicitly: **emitting a
path to `search_query.py:96` and echoing a line of Python the cutover deletes is the
fabricated-traceback pattern this project already removed once.**

**Import that authority. Do not copy it** — that module's own docstring says a second
copy of the list is the defect it exists to prevent, **and the launcher guard fixed
in one of two files that held it cost 21 errors this week.**

**And make a stale entry fail loudly in both directions**, as the contract suite
already does: **an id that leaves the authority must restore byte-parity on it here
automatically; an id that stops diverging must fail as an inert allowance.** *An
exemption that can quietly stop meaning anything is the thing this gate exists to
prevent.*

## 2 — re-run all 94

**93 pass today.** Report green or red with numbers. **Re-derive both digests
immediately before the run and record them with the result** — a relayed digest has
gone stale three times on this mission.

## 3 — the commit is not yours

**Charter: workers do not commit independently; the first mate creates accepted
checkpoint commits.** **Tell `search-firstmate` when the gates are green and hand it
over.** The pre-deletion checkpoint `67d6053` already exists; **this second one
captures the passing gates.**

## 4 — the deletion, and the list is DERIVED, not inherited

**⚠ There is no deletion list in this brief on purpose. Derive it.**

**`ch-legacy` is NOT deleted** — the charter keeps it for default parsing and
unscoped commands. **What goes is the Python search authority: what is reachable
only from the `search` command.** *Same binary; the distinction is the subcommand.*

**Two traps that are recorded and will cost you a day each if you inherit a list by
filename.**

**`pool_filter.py` cannot simply go.** `extract_cwd_from_jsonl_file` serves
`pool_filter.passes_path_for_index` — **the `ch -1 -d` index path, which has NOT been
ported.** L310 records this: a mismatch measured there was **dead Rust code against
live Python**, and the live `-d` path reaches cwd through `session::cwd` instead.
**Deleting it breaks a journey the charter keeps.**

**The PyO3 extension stays.** `python_extension.rs` imports only `inventory` and
`scanner`, and `ch-legacy` uses both. **The wheel legitimately ships a second Mach-O,
`chats/_native.abi3.so`** — check 14 records that and it is not a leftover.

**Derive by reachability from `cli.py`'s dispatch, not by name.** **Anything a
surviving command imports, survives.** *Report what you find before you delete it,
so the list is on the record rather than in your head.*

## 5 — hand the tree to `g5-runner`

**They run the complete post-deletion proof and they hold a standing instruction:
refuse the deletion until the frozen gates are green and the checkpoint exists.**
**That instruction outlives their seat and it binds you.**

## Definition of done

**All 94 green; the second checkpoint made by `search-firstmate`; the Python search
authority gone with the derived list recorded; `ch-legacy`'s surviving journeys
working; a stable tree handed over.** **`./tests/run_all.sh | cat` is
`g5-runner`'s to run, not yours.**

## Falsifiers

**Every change ships one, and name what each failure message must say.**

**For the gate wiring:** an id removed from the authority restores byte-parity here;
an id that stops diverging fails as an inert allowance. **Both run, not asserted.**

**For the deletion:** ***the proof that you deleted the right thing is that
`ch-legacy`'s surviving journeys still work — run them before and after and diff.***
**A deletion is falsified by what still has to pass.**

## Cleanup boundaries

**Clean only your own scratch and targets.** **PRESERVE, named so you do not judge
them:** every frozen recording and baseline; **`tests/data/oracle-route-inputs/`** —
1,383 bytes that make `dd6ab701` re-derivable, small and unfamiliar and exactly what
a tidy-up deletes; **`tests/data/launcher-provenance/ch-0ffde41`**, a falsifier not a
leftover; **`target/release/ch` at `1f76081c`**, byte-identical to the installed
launcher; **`/private/tmp/ch-pool-snapshot`**; all `RESUME.md` files and promoted
docs.

**Three directories are named safe to delete by their owner:** a private
`CARGO_TARGET_DIR` under the scratchpad and two `target/` dirs under
`teammates/parity-finisher/probes/drivers/`.

## How this desk works

**Announce a knowingly red tree before it lands.** **Five build configurations, not
three**, including `cargo test --doc`. **Write only inside
`teammates/deletion-owner/`; ask `search-firstmate` to promote.** **Keep `RESUME.md`
current as you work and re-read it WHOLE before you stop** — ten whole re-reads on
this mission, nine found something, and every one was outside the paragraph being
edited.

**Report the harness's context figure and name which quantity it is.** Two exist and
they have differed seventeen-fold. **The context window binds.** If the harness has
volunteered nothing, say *no current reading* with the last value and its age.
**Never derive one.**

**To message anyone, run `ListAgents` and copy the row exactly.**

**Four rules this desk paid for, in the order they will bite you.**

**A mechanism where there was a check.** Where a hazard has a mechanism, change the
mechanism — a tool that *printed* was ignored for hours; one that *refused* was
obeyed in seconds.

**A gate that cannot fail and a gate that did not fail are indistinguishable from
the outside.** Make one fail on purpose.

**Placement is part of the retraction.** A correction below its claim is not a
correction; put a forward marker where a reader meets the claim.

**And the one that governs a deletion: cheap now, impossible after.** Seven times in
three days, most recently for 1,383 bytes. **Before you remove anything, ask what
consults it and whether that consultation is stored.**

Do not run `memo` or write under `.optmem/`. **There is no escalation above the
first mate.**
