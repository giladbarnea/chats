---
date: 2026-08-28
author: context-curator
question: Do the branch's expected outputs reproduce against today's `main` Python?
verdict: Yes — 173 of 173 manifest cases
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: RE-DERIVED at this digest on 2026-08-28. Every oracle-dependent
  claim in this document was re-run and reproduced identically. The earlier stamp on
  this file was a `git diff -- src/chats` digest, which cannot see .venv/bin/ch-legacy
  or the installed RECORD, so it could not have supported this claim — hence the
  re-derivation rather than a restamp.
---

# Branch corpus reproduction against `main`

## Answer

**All 173 manifest cases reproduce against today's `main` Python.** Exit status, stdout, and stderr match byte for byte, after accounting for one normalization gap in the branch's own harness.

The corpus's expected outputs are faithful characterizations of legacy behavior, not artifacts of the native implementation that generated them. As a statement of what our oracle does, the corpus is sound and adoptable.

## Method

The branch's contract harness (`tests/test_search_command_contract.py` @ `0ffde41`) was replayed with one substitution: today's `main` Python via `.venv/bin/ch-legacy` in place of the branch's native launcher. `ch-legacy` is a console script resolving through the editable install, so it executes current `src/chats/` source. The stale `.venv/bin/ch` binary plays no part.

Everything else is the branch harness unchanged — the same fixture home copied fresh, the same 26 `MTIMES.json` timestamps applied, the same environment pinning (`HOME`, `TZ=Asia/Jerusalem`, `COLUMNS`, `LINES=40`, `TERM`, `COLORTERM`, `NO_COLOR` dropped only for colored cases), the same working directory, and the same `_normalize` function transcribed byte for byte.

Script: `reproduce_branch_corpus.py` in this directory. Raw per-case results: `/private/tmp/claude-501/.../scratchpad/repro/results.json`. Runtime 43 seconds.

## Raw result

| Measure | Count |
| --- | ---: |
| Cases | 173 |
| Exit-status mismatches | 0 |
| Stderr mismatches | 0 |
| Stdout mismatches | 7 |
| Fully reproducing before analysis | 166 |

## The 7 failures are one bug, and it is in the harness

Every failure is a colored case. Every one has **byte length identical to expected**, which rules out a rendering difference and points at an equal-length substitution.

The first differing byte in the smallest case:

```
expected: …\x1b[38;2;135;140;146m{AGE}\x1b[0m…
actual  : …\x1b[38;2;107;112;118m{AGE}\x1b[0m…
```

Those are two entries from `src/chats/theme.py`: `search.age.week` is `#878c92` = RGB(135,140,146), and `search.age.month` is `#6b7076` = RGB(107,112,118). The theme carries four such colors, and search picks one by how old the session is.

**The harness normalizes the age token's text but not its color.** `_normalize` replaces the rendered age with `{AGE}`, which stops the digits from rotting, and leaves the surrounding SGR sequence untouched. The fixture mtimes are fixed absolute timestamps, so the sessions age with wall-clock time and eventually cross a bucket boundary, changing the color while the normalized text stays put.

The oldest fixture is dated 2026-08-22. It was 2.2 days old when the corpus was generated on 2026-08-25 and is 5.8 days old today. It crossed a boundary in between.

Proof: folding the four age colors to a token makes **all seven byte-identical**.

| Case | Raw | Age-color folded |
| --- | --- | --- |
| `colored-list-fixed-width` | fail | **pass** |
| `colored-matches-panels` | fail | **pass** |
| `colored-full-panel` | fail | **pass** |
| `colored-hue-cycle-four-hits` | fail | **pass** |
| `colored-narrow-columns-80` | fail | **pass** |
| `colored-highlight-painting` | fail | **pass** |
| `pager-engaged-real-less-piped` | fail | **pass** |

So the corpus does not disagree with `main`. It decays on a clock.

This is the third instance of the same pattern in this project's history, and the first two are already on record: a normalization token added to stop fixture rot silently removed a real parity signal. Their `{AGE}` token hid an age-formatter bug that had to be found by hand. Here the same token half-covers a volatile value, so the cases rot anyway — just slower, and in a way that reads as a behavioral failure rather than as rot.

If we adopt these cases, the fix is to normalize the age color alongside the age text, or better, to pin the fixture mtimes relative to a frozen clock so neither needs masking.

## What this does not answer

1. **It tests the expectations, not the implementation.** It proves the 173 expected outputs are faithful to legacy. It says nothing about whether the branch's Rust reproduces them today — that is `reviewer-profiler`'s half.
2. **It covers 173 cases, not 704.** The suite's remaining assertions are loader traces, package and wheel equality, and hand-written cases outside the manifest (batch-window crossing, malformed-pool streaming, empty-pool silence, equal-mtime ordering). None were replayed.
3. **One deliberate deviation.** The harness installs a fake `less` on `PATH` for the pager case; I did not. `pager-engaged-real-less-piped` matched anyway, so the shim does not affect stdout parity for that invocation, but the case is not testing what the branch's suite tests.
4. **Colored coverage is thin, as their own reviewer said.** Eight colored cases, both widths explicitly set. Nothing here exercises width detection, which is the dimension `main` changed on 2026-08-27.

## What follows

The corpus's 173 command shapes and their expected bytes are adoptable as a legacy characterization, with the age-color rot fixed. That removes the largest single cost item from a contract-first rewrite, whichever way the build-versus-reconcile decision goes.
