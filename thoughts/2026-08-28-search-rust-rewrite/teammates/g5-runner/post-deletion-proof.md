# The complete post-deletion proof

**Run by `g5-runner`, 2026-09-02T12:48–12:56Z. Every figure measured here, none
taken from a report.**

## Provenance — identical either side of every run

    oracle route digest  sha256:08f036afd97dd82f…   MOVED from dd6ab701 — the deletion succeeding
    rust tree digest     63a34f4f26451d0c…          unchanged (see the disagreement below)
    launchers            .venv/bin/ch = target/release/ch = ~/.local/bin/ch = 1f76081c
    corpus               de693c35…  695 files, 1,183,541,907 bytes

**The Python search authority is gone:** `src/chats/commands/search.py` deleted,
and `ch-legacy search .` now exits 1 with *"Ambiguous conversation/session
identifier 'search'"* — **it does not have a search subcommand any more.**
`ch-legacy parse` still works, as the charter requires.

## GREEN — what was proved

| check | result |
| --- | --- |
| **1 no PyO3** | 7,588,272 B; libiconv, CoreFoundation, libSystem only; **0 undefined `Py_`** |
| **2 corpus identity** | `de693c35…` exact |
| **8 scoped diff** | 52 paths, **none outside `rust/ tests/ thoughts/ src/chats probes/ Cargo.*`** |
| **9 full suite** | **1,963 passed, 3 skipped, 0 failed**; **13 of 13 shell suites pass** |
| **10 no Python on route** | search **exit 0, 934 bytes, 31 escape runs**; `info --help` exit 1, private-entry error |
| **11 time gates** | **6 of 6 PASS** — 6.0/278.3/1038.3/2393.0/949.6/1745.1 ms against 20/325/1240/2930/1235/2065 |
| **11 memory budgets** | **3 of 3 PASS** — 413/447/499 MB against 700/900/900 |
| **14 package** | one Mach-O `ch` = the measured binary; `entry_points` expose only `ch-legacy` |
| **15 installed launcher** | **byte-identical to the wheel**, full sha |
| **deletion falsifier** | **36 of 36 surviving journeys reproduce** |

**⚠ Check 10's output is byte-identical to its pre-deletion run** — 934 bytes and
31 escape runs, same as 2026-09-01. **The deletion changed nothing the product
emits.**

**The one suite failure is `test_search_dir_filter_list_under_2500ms`**, one of the
two retired live-pool budgets **check 9's own row explicitly excludes.** `set -e`
truncated the script again, so the 13 shell suites are mine, not the gate's.

**No `test_stderr_colour.py` flake in this run.** 241 of 241 inside the 1,963.
*Absence in one run is evidence, not proof.*

## DEAD BY CONSTRUCTION — and this was the ruled outcome, not a surprise

**Checks 3, 5, 6, 7 were live differentials against `ch-legacy search`. There is no
longer a reference.** Their successors carry the stored side: the frozen selection
gate (94), the operator-facet gate (4), oracle provenance (4),
preserve-because-wrong (15), stderr-colour (241) — **all inside the 1,963 and all
green.**

## ⚠ THREE FINDINGS

### 1. Memory parity now measures an error path — and the CONTROL caught it

```
agent-bearing    subject +576MB   reference  +65MB   FAIL
control (claude) subject   +0MB   reference  +66MB   FAIL   ← the control
```
**`memory_delta` runs the absent-literal search through both binaries. The
reference cannot search, so its arm measures Python interpreter startup on an
error path.** +65 and +66 MB are startup, not search.

**The control's contract is that BOTH arms stay near zero, and the reference came
back +66MB — so the control went red.** ***That is the gate reporting that its own
measurement is invalid rather than that the port regressed.*** **A red control is
the difference between "this number is broken" and "the product got worse", and it
is the only reason this section is not a false regression report.**

**Checks 12 and 13 are dead for the same reason and were expected to be.**

### 2. ⚠ `ORACLE_STAMP` is hardcoded and now names a route that does not exist

`performance_gates.py:44` prints `HEAD 8cb4c5f, oracle route digest
sha256:dd6ab701…` on every run. **Live values are `e74f5a0` and
`sha256:08f036af…`.**

**This is the exact fault corrected in `frozen_reference.json` yesterday — a
hardcoded stamp from a version no longer on disk — surviving in the file next to
it, because nothing derived it.** *The fix was applied to one of two places, for
the sixth time on this mission.*

### 3. A stale comment names a deleted file as its live counterpart

**`tests/deliberate_divergences.py` documents the loss properly** — *"it ran
`ch-legacy search` and died with the Python search authority… the set was the
assertion, and the set is what cannot be re-derived… no gate can any longer prove
that these lists are complete."*

**But `test_search_command_contract.py:113` and `:191` still name
`test_deliberate_divergences.py` in the present tense**, and `:191` asserts
*"Neither suite can quietly stop meaning anything without the other going red."*
**One of the two suites is deleted, so that sentence is false.**

**What actually survives:** `_assert_deliberate_divergence_still_differs` is still
called at `:346` and `:431`, comparing each named id against its **stored** bytes.
**So an exemption cannot become vacuous** — but the shape of each divergence is
pinned only where a stored baseline covers it, and **nothing proves the list is
complete.**

## A digest disagreement, reconciled rather than left standing

**Both other seats report the rust tree digest as `7b3267a6a22e1f7c…`. I measure
`63a34f4f26451d0c…`**, unchanged from my own pre-deletion value and reproduced
from two independent framings. **No recipe I tried yields theirs.**

**The substantive claim holds and I verified it independently: `git diff HEAD --
rust` is empty, so no Rust was touched.** *A recipe difference, not a state
difference — but two seats quoting "the rust tree digest" at different values is
the naming hazard this mission has hit repeatedly.* **My recipe is the one recorded
on this desk and it reproduced L263's `ca874ce060f1` exactly.**
