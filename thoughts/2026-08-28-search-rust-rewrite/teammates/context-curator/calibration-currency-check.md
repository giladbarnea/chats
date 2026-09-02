---
date: 2026-08-28
author: context-curator
task: calibration currency check, plus the assumption most worth funding a check on
verdict: no stale copies; one instrument failing its own gate; one sizing error of mine
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: NOT ORACLE-DEPENDENT. This document's claims are about commits,
  documents, or teammates' tooling rather than about oracle behaviour, so a digest
  neither strengthens nor dates them. Recorded to say so explicitly: an earlier
  version carried a behaviour stamp, which implied a dependency it does not have.
---

# Calibration currency check

## Answer: nobody is running a stale copy

`reviewer-profiler`'s probe table is the only definition of it that exists anywhere on this desk. A repository-wide search for a second `PROBES` table returns exactly one hit, theirs. Nothing was copied.

| Owner | Instrument | How it reaches the calibrator | Currency |
| --- | --- | --- | --- |
| `reviewer-profiler` | `calibrate_harness.py` | canonical source, 14 dimensions | — |
| `contract-owner` | `calibrate_contract_harness.py` | imports it | current |
| `context-curator` | `fuzz_harness.py` | imports it by path | current, passes all 14 |
| `query-semantics` | pattern harness | not applicable | — |
| `session-core` | one-shot probes | not wired | see below |
| `search-runtime` | none | — | — |

`query-semantics` is the interesting exemption. Their harness compares CPython `re` results against a candidate engine — it never captures process output, so the byte-capture calibration does not apply to it. That is a different instrument class, not an uncalibrated one. Whatever grades it has to grade *their* claim, which is about pattern semantics rather than captured bytes.

## Two things found on the way

### `contract-owner`'s comparator is failing its own gate right now

Running their calibrator today:

```
capture                              CALIBRATED
comparator (capture + _normalize)    BLIND in 1
                                     - cannot see: SGR between two age buckets
FAIL: the comparator has undeclared blindness in ['SGR between two age buckets'].
```

Their instrument is working exactly as designed — it caught this itself and fails loudly. But the fact deserves attention on its own: **the byte lock is the most-quoted instrument on this mission, and it is currently blind in precisely the dimension where a real signal was found this morning.** The age-colour SGR is what separated the branch's seven apparent failures from a genuine parity break. A comparator that normalizes it away cannot make that distinction again.

Not staleness, and not mine to fix. Reported because a red gate on the most-cited instrument should not wait to be noticed.

### One latent `text=True`, which is not a live defect

`session-core/probes/reverse.py` captures with `text=True`, the exact trap they themselves discovered and warned the team about.

**It does not bite there.** The comparison in that probe is a substring test — whether `text_encoding="html"` appears in the output — and universal-newline rewriting cannot change whether a substring is present. I checked the instance rather than reporting the grep hit, per this morning's rule.

It is one edit away from biting. If that probe is ever changed to compare outputs rather than test for a marker, it becomes the trap. Their other two capturing probes, `carriage_return.py` and `parse_blast_radius.py`, capture bytes and decode explicitly, which is correct.

## The generalization

Import-versus-copy is the right frame and it held everywhere here. The reason it matters is visible in my own case: `reviewer-profiler`'s probe set grew from 8 dimensions to 14 between two of my runs, and my harness inherited all 14 with no change on my side. A copy would have kept reporting "calibrated" against a six-dimension-smaller definition of the word.

Nothing else on this desk was copied rather than referenced, as far as a search for duplicated tables, builders, and normalizations can show.

---

# The assumption I would least want to be wrong about

Not the branch. **The oracle.**

The whole mission rests on `main`'s Python being the fixed behavioral truth. Nobody has pinned what that means, and it is not currently a commit.

My 173-of-173 reproduction ran through `.venv/bin/ch-legacy`, which resolves through the editable install to the `src/chats/` **working tree**. Not to a revision. Every characterization anyone has taken today has the same property.

Right now that is harmless: `src/chats/` is clean, so the working tree equals HEAD `8cb4c5f`, and every result holds. But:

- `src/chats/` is shared and unowned under the charter's collision rule.
- `rust/` already has three dirty files from a live refactor moving `terminal_width` into a shared module.
- The moment anyone edits `src/chats/`, every characterization taken before that edit silently describes a different oracle, and **nothing in the current process would notice**. There is no equivalent of the launcher-provenance guard for the oracle's own source.

That is the same failure this team has spent the day finding in other people's work — a result that is true of a thing nobody pinned. It is now ours.

**The fix is cheap:** declare the oracle to be `8cb4c5f`, record that revision in every artifact that characterizes behaviour, and require re-characterization if it moves. One line per artifact, and it converts a silent failure into a visible one.

## A sizing error of mine, which three owners are about to build on

I told the team the reconciliation surface is "two commits, five files, 185 insertions against 152 deletions."

The commit count is right. The rest was the `src/` and `rust/` slice only, because that is what I scoped the diff to. The full surface of those two commits:

| Commit | Files | Insertions | Deletions |
| --- | ---: | ---: | ---: |
| `47b3db9` | 22 | 656 | 163 |
| `a51f32c` | 4 | 257 | 15 |
| **Total** | **26** | **913** | **178** |

I understated the insertions by roughly five times. The omitted part is `tests/` — 364 insertions across eleven files, including the empty-optionals fixture pair, 202 lines of parse-contract tests, and the colored-rendering width tests.

That omission matters more than the number. **The tests are the part that keeps the fixes from regressing.** An owner porting `47b3db9` onto the branch by replaying the source hunks alone would restore the three behaviours and none of the guards that prove them, which is the exact shape of defect the fixes were written to close.
