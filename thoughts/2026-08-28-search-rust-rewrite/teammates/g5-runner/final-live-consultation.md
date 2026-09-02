# The final live consultation of the Python search authority

**This document IS the stored consultation.** Decision 6 requires that before the
oracle is deleted, every instrument consulting it has its last consultation
stored. **These instruments consult it by running it, so their stored
consultation is this record: what was asked, when, against what, and what it
answered.**

**Run by `g5-runner`, 2026-09-01T19:36:07Z–19:38:44Z, with both routes alive.**

---

## Provenance — identical before and after the run, so the record is not void

    oracle route digest  sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
    rust tree digest     63a34f4f26451d0cba1cf90876090b69918781bb7963424d327c95171e13ed29
    reference            .venv/bin/ch-legacy
                         c1821a3a86ee9a8821087e9149c034eed087033b81172189486b74bf09366b79
    subject (build)      target/release/ch
                         1f76081cd87a2808e0f6eed0407b98149e0e7212c4b4cedd7f16c529bd8e512f
    subject (installed)  ~/.local/bin/ch          — byte-identical to the build
    corpus               de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965

**Both digests re-derived after the run and identical. Full shas, not prefixes.**

---

## The result, in the form it will be read

**On 2026-09-01, at oracle route digest `sha256:dd6ab701…`, against
`.venv/bin/ch-legacy` at `c1821a3a…`, with the native route at `1f76081c…`:**

| twin | cases | result |
| --- | ---: | --- |
| `test_search_journey_matches_live_legacy_implementation` | — | **PASSED** |
| `test_named_defect_patterns_select_the_same_sessions` | — | **PASSED** |
| `test_generated_patterns_select_the_same_sessions` | — | **PASSED** |
| `test_colored_terminal_output_matches_live_legacy_implementation` | — | **PASSED** |
| *(the four above, together)* | **289** | **289 passed, 0 failed** |
| `test_columns_sweep_reproduces_legacy` | **73** | **73 passed, 0 failed** |
| `test_deliberate_divergences.py`, all four | **11** | **11 passed, 0 failed** |

**373 live comparisons against the Python search authority. Every one passed.**

**This is the last time any of these questions can be asked.**

---

## The degradation at each frozen twin — what it asserted, what it asserts now

### `test_search_journey_matches_live_legacy_implementation` → frozen twin is `..._matches_characterized_legacy_bytes`

**Before:** the port matches Python, re-executed, over 227 cases.
**After:** the port matches **454 stored files** recorded from Python.
**⚠ What is lost: the live half existed to catch the stored half going stale. The
deletion removes the check on the check.** Nothing can now detect a stored
expectation that was wrong when it was recorded.

### `test_named_defect_patterns_select_the_same_sessions` and `test_generated_patterns_select_the_same_sessions`

**Before:** both routes select the same sessions for a pattern, decided by running
both.
**After:** no successor. **These have no frozen twin.** Pattern-selection parity
becomes unasserted at deletion.

### `test_colored_terminal_output_matches_live_legacy_implementation`

**Before:** coloured pty output matches Python, re-executed.
**After:** the frozen colour baselines — `frozen_reference.json` (82 entries),
`stderr-colour` (240 cases), `rule-colour-oracle.json`. **Broad, and no longer
self-checking.**

### `test_columns_sweep_reproduces_legacy`

**Before:** 18 `COLUMNS` values × 4 shapes, both routes, **0 differences over 72
comparisons.**
**After:** no successor. **Built today and live-only.** Width parity under
`COLUMNS` becomes unasserted at deletion.

### ⚠ `test_deliberate_divergences.py` — the sharpest

**Before:** the six ruled divergences are **exactly** these six, and everything
else is byte-identical — decided by running both routes.
**After: frozen, it can only assert the port still produces what it produced
today. It can no longer assert that the difference from Python is still exactly
those six.**
**A seventh divergence appearing would be invisible. A case quietly agreeing would
be invisible.** *The set was the assertion, and the set is what cannot be
re-derived.*

---

## What survives, and it is not nothing

**Nine stored artifacts, all confirmed on disk** — `frozen_reference.json` (82,
provenanced and independently re-derivable), 454 `expected/` files,
preserve-because-wrong (15), stderr-colour (2), frozen differentials (2), markdown
oracle (4), rule-colour oracle, **and both of decision 6's own named freezes:
`frozen-oracle-age-colour` (15) and `frozen-oracle-nfc-nfd` (13).**

**And the route itself stays recoverable:** the first mate commits the
pre-deletion tree, so `dd6ab701…` can be re-derived by checking out that revision
and every stamped artifact stays checkable rather than becoming unverifiable.

---

**Recorded before deletion, as decision 6 requires. Cheap now, impossible after.**
