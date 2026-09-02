# Every instrument that consults the Python search authority

**Built by `g5-runner`, 2026-09-01, before the deletion slice.** Decision 6 stated
as a list rather than a principle: **before the oracle is deleted, every
instrument consulting it must have its last consultation stored.**

**This seat refuses the deletion until this list is ruled on.**

**Scope note, stated first: `ch-legacy` itself is NOT deleted.** The charter keeps
it for default parsing and unscoped commands. **What goes is the Python SEARCH
authority.** So an instrument that runs `ch-legacy parse` survives and one that
runs `ch-legacy search` does not — **the same binary, and the distinction is the
subcommand.** Several entries below turn on exactly that.

---

## ⚠ CORRECTION — THIS ENUMERATION WAS INCOMPLETE BY A WHOLE CLASS

**Added 2026-09-02 by `g5-runner` after `deletion-owner` found the gap. Read this
before the sections below, because they are organised on the axis that caused it.**

**Sections A–C enumerate instruments that consult the authority through a
SUBPROCESS — things that run `ch-legacy search`. They miss every instrument that
IMPORTS the Python search module IN-PROCESS.** *A different mechanism of
consultation, and the whole class was invisible to how I looked.*

**Measured floor, verified by me rather than taken on report:**

| file | imports | collected |
| --- | --- | ---: |
| `tests/test_search_orchestration.py` | `chats.commands.search` | **78** |
| `tests/test_native_ascii_candidate_scanner.py` | `_file_contains_ascii` and others | **59** |
| `tests/test_colored_rendering.py` | `cmd_search` | **36** |

**`test_native_ascii_candidate_scanner.py` is the sharpest: it imports
`_file_contains_ascii` from `commands/search.py` to GRADE THE NATIVE SCANNER
AGAINST IT.** *An instrument consulting the Python authority as its oracle,
reached by an import rather than a subprocess — exactly the shape this document
was written to catalogue, and exactly the shape it could not see.*

**51 test files import `chats` at all; 3 import `commands.search` directly.**
`deletion-owner` counts **16 files and 281 tests** against a wider module set —
**theirs is derived by reachability from `cli.py`'s dispatch and supersedes my
floor.** *I am naming the class and the measurement; the list is theirs.*

**⚠ AND I HAD THE EVIDENCE AND DID NOT USE IT.** Building this document I ran two
sweeps: one for `ch-legacy` invocations and one for `chats` imports. **I
classified the first and moved past the second.** *Not a search that missed — a
result that was collected and never read. The same defect as reading an aggregate
without dumping the instances, one layer up.*

**The general form, which cost two seats an hour between them: a document can be
clean of the fault you checked it for and carry a different one.** I wrote that
sentence about my own recording an hour before this instance proved it about my
own enumeration. **Neither of us found the other's half by looking harder at our
own.**

---

## A. STORED — the consultation is frozen. These survive.

| artifact | size | gated by | note |
| --- | ---: | --- | --- |
| `reviewer-profiler/frozen_reference.json` | 82 entries | `freeze_references.py --verify` | **provenanced, instrument-digested, independently re-derivable.** Reference `c1821a3a86ee9a88` |
| `tests/data/search-contract-fixtures/expected/` | 454 files | contract suite | the characterized legacy bytes, **227 cases** |
| `tests/data/preserve-because-wrong/legacy-baseline.json` | 15 files | `test_preserve_because_wrong.py` | the twelve deliberately-wrong behaviours as **prohibitions** |
| `tests/data/stderr-colour/legacy-stderr-baseline.json` | 2 files | `test_stderr_colour.py` | 240 cases, captured while `ch-legacy` lives |
| `tests/data/search-frozen-differentials/` | 2 files | `test_search_frozen_differentials.py` | |
| `tests/data/message-renderer/markdown-oracle.json` | 4 files | renderer gates | |
| `parity-finisher/probes/rule-colour-oracle.json` | present | rule-colour gate | |
| `frozen-oracle-age-colour/` | **15 files** | fuzz harness | **decision 6's first named freeze — confirmed present** |
| `frozen-oracle-nfc-nfd/` | **13 files** | `nfc_nfd_probe` | **decision 6's second — confirmed present** |

**Both of decision 6's named freezes are on disk. Verified, not assumed.**

---

## B. ⚠ LIVE — consults `ch-legacy search` at run time. These DIE at deletion.

### B1. Committed tests — these are the ones that matter

| test | file:line | what it consults it for |
| --- | --- | --- |
| `test_search_journey_matches_live_legacy_implementation` | contract:404 | every case re-run against live Python |
| `test_named_defect_patterns_select_the_same_sessions` | contract:571 | pattern selection parity |
| `test_generated_patterns_select_the_same_sessions` | contract:610 | generated-pattern parity |
| `test_colored_terminal_output_matches_live_legacy_implementation` | contract:710 | coloured pty parity |
| `test_columns_sweep_reproduces_legacy` | columns_sweep:112 | **the 0-of-72 `COLUMNS` gate built today** |
| all four in `test_deliberate_divergences.py` | 110, 154, 172, 211 | **the six ruled divergences, asserted exactly** |

**⚠ The contract suite has a stored twin for one of these and not the others.**
`test_search_journey_matches_characterized_legacy_bytes` compares against the 454
stored `expected/` files and **survives**;
`..._matches_live_legacy_implementation` runs Python and **dies**. *Two tests over
the same 227 cases, one durable and one not — the live one exists precisely to
catch the stored one going stale, so deleting the authority removes the check on
the check.*

**⚠ `test_deliberate_divergences.py` is the sharpest loss.** It asserts the six
ruled divergences **exactly** — and it does so by running both routes. **Frozen,
it can only assert that the port still produces what it produced today; it can no
longer assert that the difference from Python is still exactly those six.**

### B2. ⚠ THE SIX RATIO GATES — the one the first mate already named

**`performance_gates.py` takes its denominator from `ch-legacy search` live.**
**We built ratio gates this afternoon *because* they do not rot, and their
denominator is scheduled for deletion.**

**Measured, not solved, as instructed. My reading of the design question:**
**a frozen Python timing is not a denominator.** The ratio's whole soundness came
from *same query, same corpus, same window, same machine* — L279's disproved
construction failed for exactly the missing-fourth-condition reason. **A stored
2026-09-01 Python number compared against a native number measured next month on
another machine satisfies none of those conditions and is a worse instrument than
the absolutes it replaced.**
**So the honest answer may be that ratios cannot survive the deletion at all**, and
what replaces them must carry **the ratio evidence as its justification** — the
0.033/0.552/0.397/0.108/0.435/0.433 measured against a live Python route, recorded
as the reason the successor's ceilings are where they are. **That is a ruling, not
an instrument change.**

### B3. Teammate probes — perishable by L1 regardless

`route_differential.py` (54/54, **no stored json at all**), `help_width_sweep.py`,
`reference_capture.py`, `reproduce_branch_corpus.py`, `pty_differential.py`
(2 stored refs), `grammar_oracle.py` (generator; **its output is stored**).

**L1 already rules these die at session exit, not at cutover.** Listed so the
count is honest, not because they are recoverable.

---

## C. NOT a search consultation — survives, and one of them is a trap

- **`test_parse_command_contract.py`** — runs `ch-legacy parse`. **The charter
  keeps that.** Survives.
- **`_place_legacy_sibling`** (contract:257) — places the sibling so the native
  binary can route **uncompleted** journeys. Survives.
- **⚠ `tests/oracle_digest.py` — the trap.** It does not run search; it **digests
  the route**: `src/chats/**/*.py` + the entry script + the installed RECORD.
  **Deleting the Python search authority changes `src/chats/`, so the oracle
  digest MOVES.** Every artifact stamped `sha256:dd6ab701…` — `frozen_reference.json`,
  the contract corpora, the stderr baseline — **becomes unverifiable rather than
  wrong.** *A stamp that cannot be re-derived is decision 3's failure from the
  other end.*
  **This needs a ruling before deletion, not after: either the stamp's meaning is
  re-defined, or the artifacts are re-stamped with a recorded note that the
  pre-deletion window was verified and the post-deletion one cannot be.**

---

## What I would want ruled before anything is deleted

1. **B2 — the ratio gates.** Ratios probably cannot survive. Name the replacement
   and record the ratio evidence as its justification.
2. **C — the oracle digest moves.** Decide what `dd6ab701` means afterwards.
3. **B1 — the live/stored twins.** For each, decide whether the stored half alone
   is accepted, **knowing the live half was the check on the stored half.**
