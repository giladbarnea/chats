---
date: 2026-08-28
author: context-curator
question: Are more deviations hiding in the branch beyond the nine known?
verdict: No new ones found at source. But adopting the branch would reintroduce four defects `main` has already fixed.
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: RE-DERIVED at this digest on 2026-08-28. Every oracle-dependent
  claim in this document was re-run and reproduced identically. The earlier stamp on
  this file was a `git diff -- src/chats` digest, which cannot see .venv/bin/ch-legacy
  or the installed RECORD, so it could not have supported this claim — hence the
  re-derivation rather than a restamp.
---

# Branch deviation sweep

## Answer in two parts

**No new deviations found.** Three independent source sweeps — self-admitted compromises in comments, the argument grammar, and the theme colour tables — turned up nothing beyond the nine already known. Two of the three found the branch to be *more* faithful than expected.

**But the sweep found the risk running the other way.** `main` has moved since the fork, and the branch predates every one of those changes. Adopting it wholesale would reintroduce four defects that `main` has already fixed and tested — three of them the output of the post-review fix campaign.

## Part 1: the hunt for new deviations came up empty

### Comments admit nothing

Swept all 15 Rust files (excluding the 39,965-line generated Unicode name table) for the vocabulary of a self-admitted compromise: `diverge`, `differs`, `unlike legacy`, `unsupported`, `approximate`, `best effort`, `TODO`, `FIXME`, `for now`, `simplif`, `assume`, `limitation`. Twenty-one hits, all of them deliberate parity annotations pointing *at* legacy rather than away from it — for example `inventory.rs:403` citing `parsing._read_first_jsonl_entry` for blank-line handling, and `search_engine.rs:1226` recording that the date pre-filter is content-only.

This is worth stating because the record that lost a deviation was their **prose**, not their code. Their code annotates its parity obligations carefully.

### The argument grammar is faithful, including where nothing pins it

Fourteen long-form option spellings appear in `search --help` and are exercised by **zero** of the 173 manifest cases: `--agents`, `--all`, `--branches`, `--cafter`, `--case-insensitive`, `--case-sensitive`, `--dir`, `--full`, `--list`, `--mafter`, `--only-id`, `--provider`, `--raw`, `--tools`. Their semantics are covered through short forms, but the long spellings themselves are not, and neither is any abbreviation.

That matters because argparse accepts unambiguous long-option abbreviations, and a hand-written grammar has to emulate that. `main`'s parse launcher demonstrably fails this exact test today — it emulates abbreviation for `--format` but not `--help`, so `ch parse --h` errors where argparse printed help. The same bug class in search would be invisible to all 704 cases.

Measured on `main`'s Python: `--prov`, `--pro`, `--case-s`, `--li`, `--only-i`, and `--thin` all resolve, and `--p` and `--c` correctly fail with exit 2.

**The branch implements it correctly.** `search.rs::normalize_option_tokens` prefix-matches against a `LONG_OPTIONS` table, gives exact matches priority over prefixes, and errors on ambiguity. Two details show this was done deliberately rather than by luck:

- The ambiguity message lists candidates in `LONG_OPTIONS` declaration order, and that order was chosen to reproduce argparse's registration order. Probed both sides: `--p` yields `--provider, --plans, --paging` and `--o` yields `--only-id, --only-user, --only-assistant`, identically.
- The error envelope is `{USAGE}ch search: error: {message}\n`, and a cargo test asserts `USAGE` equals the leading bytes of the help fixture, so the two cannot drift apart.

### The theme tables match

Compared every colour in `src/chats/theme.py` against the RGB triples in the branch's renderer. All 17 search-specific entries match exactly, including the four age colours and the match highlight — `MATCH_STYLE = "1;38;2;20;24;29;48;2;230;180;80"` is `bold #14181d on #e6b450`, byte for byte the Python theme. The colours that do not appear in `search_views.rs` are the message-body and tool colours, which live in `session_render.rs` as expected.

This is the surface guarded by only 8 colored cases at two fixed widths, so it was the most plausible place for an unpinned drift. There is none.

## Part 2: what the sweep actually found

`main` and the branch forked at `a7e89eb`, 2026-08-21. Since then **`main` has exactly two commits touching `src/` or `rust/`**, and the branch predates both.

### `47b3db9`, 2026-08-26 — the post-review fix campaign

Three of its four fixes are absent from the branch, verified at source:

| Fix | State on `main` | State on branch |
| --- | --- | --- |
| **T1** honest broken-pipe handling | fabricated traceback deleted; `BrokenPipe` handled at the write site with a permanent `cargo` test | **alive** — `main.rs:347 print_broken_pipe_traceback()`, building a fake Python traceback from `env!("CARGO_MANIFEST_DIR")` at line 352, citing `cli.py:368`, `commands/parse.py:146`, `resolve.py:405` — none of which exist |
| **T2** `JsonEscapeValidator` deletion | deleted (risk-scalar defer path deliberately kept) | **alive** — `scanner.rs:134` |
| **T4** empty-string optional parity | `model.rs::optional_string` returns `Ok((!value.is_empty()).then(...))`; `codecs.rs` strips nine empty attributes before emission | **alive** — `model.rs:298` still `Ok(Some(value.clone()))`, and the attribute guard is absent |

T4 deserves emphasis: it is a **legacy-parity defect**, the exact class the branch exists to avoid. Legacy guards every message metadata field with Python truthiness, so `{"branch": "", "status": ""}` renders as bare `<user-message i="1">`. The branch renders `branch="" status=""`.

T1 is the same weasel-code shape twice over: it bakes build-machine paths into shipped stderr, which is also blind spot number four on the branch's own list.

### `a51f32c`, 2026-08-28 — terminal width from the terminal

`main` now resolves width through `ioctl TIOCGWINSZ` across file descriptors 0, 1, and 2, with `COLUMNS` as an override. The branch reads `COLUMNS` only and defaults to 80. This is already known deviation 3, but it is worth restating in this frame: it is not merely a branch limitation, it is a place where `main` moved *after* the branch measured against it. A reconciliation has three behaviours to consider, not two.

## What follows

The reconciliation surface is small and fully enumerable: two commits. Anyone porting from the branch must replay both onto it, or the port ships four regressions — three of which cost a dedicated fix campaign to find and close, and one of which (T4) is precisely the kind of silent parity break the mission exists to prevent.

The good news is the size. **Two commits, 26 files, 913 insertions against 178 deletions.**

*Correction, same day:* an earlier version of this line said "five files, 185 insertions against
152 deletions". That was the `src/` and `rust/` slice only, because that is what I scoped the
diff to, and three owners were sizing their port on it. The omitted 364 insertions are `tests/`,
which are the guards that keep those three fixes from regressing — an owner replaying source
hunks alone restores the behaviours and none of the proofs. Full figures: `47b3db9` is 22 files /
656 / 163; `a51f32c` is 4 files / 257 / 15.

## Confidence and limits

- Everything in Part 2 is verified by reading both trees at source, not from any record.
- Part 1 is a bounded negative, not proof of absence. It covers comments, the argument grammar, and the colour tables. It does not cover provider decoding, visibility, shortening, or the renderer's tokenizers, where a deviation would need differential execution to surface rather than reading.
- I did not build or run the branch. Everything here is source comparison plus probes against `main`'s Python.
