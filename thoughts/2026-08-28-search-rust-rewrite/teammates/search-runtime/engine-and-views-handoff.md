# Handoff: the native search engine and its views

For `query-semantics`, who takes the engine, and for whoever takes the views.
Written for a competent reader arriving cold. Nothing here assumes you followed
my working thread.

Provenance: HEAD `8cb4c5f`, oracle route digest `sha256:dd6ab701e9b8450e…` via
`tests/oracle_digest.py::oracle_route_digest()`. An earlier working-diff hash was
withdrawn: it could not see a `uv sync` replacing the installed entry script,
which is the failure a stamp exists to catch.

---

## 1. What these two packages are

`ch search` today is Python. `rust/main.rs` routes `parse` natively and sends
everything else to `ch-legacy`, the Python entry point. The mission is to make
the search route native and cut over once.

Two packages, both now in flight rather than unbuilt:

**The engine** — scan the session pool newest-first, reject files cheaply with
the byte gates, confirm survivors semantically, order the hits, stream them,
handle per-file errors, and exit with the right status. It also owns the *plain*
output modes: `--only-id`, `--list`, matches, full, and `--raw`.

**The views** — the coloured rendering only: list rows, the conversation panel,
and highlight painting.

There is prior art: an abandoned branch, `wip/cycle-02-native-default-pause-20260821`
at `0ffde41`, has `search.rs` (1,057 lines, argument grammar), `search_engine.rs`
(1,271) and `search_views.rs` (594). Read them with `git show 0ffde41:<path>`.
**Do not switch the shared checkout to that branch** — six sessions work in it.

---

## 2. The rule that governs every line you take from that branch

The branch forked on 2026-08-25 and `main` has landed fixes since. So **`main`
wins by default and the branch must earn each individual difference.** A
difference is evidence of a missing fix until shown otherwise, never evidence of
a design choice.

This is not abstract. Four defects `main` already fixed are still in that
branch's code, and two more turned up when the rule was applied:

1. A fabricated Python traceback with build-time absolute paths baked into the
   literal, emitted on a broken pipe (`main.rs:354`). `main` exits silently.
2. `JsonEscapeValidator` in its scanner, which does not exist on `main` at all —
   `main` has `EscapedRiskScalarTracker` after a fuzz campaign showed the naive
   deletion was unsafe.
3. `terminal_width()` reading `COLUMNS` only, defaulting to 80. Shells do not
   export `COLUMNS`, so under zsh that renders at 80 columns always.
4. A tool key argument elided at a hard-coded 44 columns, which `main` fixed by
   eliding at render time against the real width.
5. Its "single-sweep" scanner optimisation is welded to the validator in (2), so
   it cannot be taken without the defect. Ruled: discard it.
6. `risk_character_pattern()`, the one thing that looked like a genuine branch
   improvement — **I benchmarked it and it is ~2.1× slower** than what `main`
   does. 18.4–18.9 ms against 39.3–40.6 ms over a 128 KiB non-ASCII chunk.
   Closed as a rejection.

Seven for seven. Assume the eighth exists.

**But the rule is that a difference must be *earned*, not that it cannot be.**
The seventh looked like the branch's first win — `views-and-colour` measured its
hand-rolled panel frame as matching Rich at four widths — and they withdrew it
after a larger corpus: the *outcomes* agree, the *mechanism* does not, and a
title of exactly `width - 5` overflows.

Keep the generalisation rather than the tally: **an outcome that matches at
every sampled point is not evidence that the mechanism matches.** Two tells —
agreement across a small sample, and a rewrite that *removes* a branch rather
than adding one, since the single-pass version is usually the real one.

---

## 3. What exists now, and what blocks you

Landed and green: `inventory` (discovery, provider classification, the shared
line walk), `scanner` (the byte gates), `terminal` (width and colour-system
resolution), `clock` (the `CH_NOW` seam), `pager`, `codecs`, `model`,
`search_query`, `shortening`, `tool_filter`.

**Status — this section was written when all three were blocked and is kept
because the dependency shape still explains the ordering.** All three blockers
have since cleared: `session-core` landed the visibility types and `session`,
the grammar landed, and both `search_engine.rs` and `search_views.rs` exist.

What remains of the `Run` arm, using the numbering in `RESUME.md`: items 1–3
(scan order, screen, probe) are landed in `rust/search/plan.rs` and item 6 (exit
status and the no-results hint) in `rust/search.rs`, both `search-runtime`'s.
Item 4 is confirmation, `engine-and-codex`'s, in flight. Item 5 is the sinks,
split — the coloured one `views-and-colour`'s, the plain modes
`engine-and-codex`'s.

`search_engine::stream_search` is the **scheduler** and nothing more: it takes
`scan_order`, a `HitSink`, a batch size, and `screen` / `probe` / `confirm`
closures, and returns an `Outcome`. There is no `run(SearchArguments) ->
ExitCode`; the cutover in `main.rs` composes those pieces. Anyone reading this
document for "what is left" should read `RESUME.md`, which is kept current.

---

## 4. The seam, and why the pager is where it is

**One-directional: the engine calls the views, the views return strings, nothing
flows back.**

The branch violates this. Its pager lives in `search_views.rs` while the
engine's loop constructs it, writes each hit through it, and reads
`pager.closed` to decide whether to keep scanning. That is scan control wearing
a rendering costume, and two owners either side of it would be editing each
other's loop.

`rust/pager.rs` already exists on `main` and holds the pager in the **engine's**
position. `closed()` is a method, not a public field, so the engine reads it and
nothing outside can set it. Consume it from the engine; the views must never
see it.

It is ported from `chats.console.StreamingPager`, which is the oracle, not from
the branch. One divergence from the branch is deliberate and recorded: the
branch flushes stdout in the fallback taken when `less` is missing, and Python
does not. Python's behaviour won.

---

## 5. The gate policy is mine and stays undivided

You own what a term *means*. I own whether a term may be *probed* against raw
bytes before anything parses the file. Do not split that policy across both
layers — it is safety-critical and asymmetric. A false accept costs a wasted
parse. **A false reject silently loses a user's search result**, with no error
anywhere.

What the engine reads from your layer, unchanged from what we agreed: an
`evaluate(term_matches) -> bool`, iteration over terms, and per term the
compiled matcher, `case_sensitive`, the raw `pattern`, and `literal_candidate`.
Plus a conservative prefilter walk where `NOT` always passes, `AND` is all,
`OR` is any.

**One invariant you must not relax.** The `.isascii()` guard on every byte-gate
path is *correctness*, not performance. `literal_candidate` uses `casefold`
while matching uses `re.IGNORECASE`, and they genuinely disagree: for `ß` the
candidate is `ss` while the compiled regex does not match `ss`. ASCII is the
only region where the two models coincide. Widening the gates to non-ASCII as
an optimisation buys silent loss.

**One thing you added that the engine must surface.** `Regex::search` now
returns `Result<bool, StepBudgetExceeded>`. The engine has to turn that error
arm into a non-zero exit with the `Display` message, not swallow it into "no
match".

---

## 6. Behaviours that are wrong and must be preserved

A port that fixes these diverges. The correct implementation is the natural one
in every case, which is exactly what makes them dangerous.

- **The age label and the age colour disagree by one bucket.** `humanize_age`
  and `age_style` carry separate, unaligned thresholds. A row reading `1d` is
  painted with the *week* colour, `1w` with *month*, `1mo` with *old*. I have
  seen this in live output, not just been told it. Driving both from one table
  is the obvious simplification and it silently repaints every coloured row.
  **This is the highest-risk item**: the fixture normalizes the label and the
  comparator normalizes the colour, so nothing checks the pairing. A unit gate
  exists (`age_pairing_gate.py`) that pins the *pairing* rather than the
  absolute colour — that is the only thing standing here.
- `humanize_age` uses 30-day months and 365-day years, so twelve months is 360
  days and an age between 360 and 365 renders `12mo` before jumping to `1y`.
- **`collapse_home` matches a string prefix, not a path boundary**, so
  `/Users/<home>X/dev` renders as `~X/dev`. Reaches both the list row and the
  panel title.
- `elide_to_width` counts code points, so wide text overflows its budget —
  `你好你好你好你好` at a budget of 8 returns unchanged at 16 columns. Four call
  sites across both views. The codebase counts in three different units, so any
  port that unifies them changes behaviour.

---

## 7. Engine mechanics you cannot infer from the code

- **Scan order is newest-first by filesystem stat mtime**, not by content
  timestamp. `SessionPool.stat_mtime_sorted` reversed.
- **Date filters read content timestamps only. Never stat mtime.** A previous
  team shipped an mtime short circuit and withdrew it permanently: imports,
  copies preserving foreign clocks, `touch -t` and restore tools all produce
  files whose mtime precedes their content timestamp, so it silently dropped
  hits. The guarded variant is closed too — for `-ca` the content probe *is* the
  cheap first read, and `-ma` already reads only 4 KB tail chunks backward, so
  guarding just adds stat calls.
- **Probe avoidance is contractual**: `-ma` alone must never read a first
  timestamp; `-ca` alone must never read a last timestamp.
- **Batches are exactly 256 files wide**, scanned in parallel, decisions
  returned in input order, confirmed **serially** before the next window opens.
  That is what preserves newest-first streaming. The 256 knee was measured:
  128 / 256 / 512 completed in 1.422 / 1.188 / 1.182 s, and 512 bought 6 ms of
  completion while adding 207 ms to the first barrier.
- **A mid-window filter error must flush the accumulated window before it
  prints**, or a later directory-filter error prints ahead of an earlier
  semantic read error and changes observable output order.
- **The provider-column predicate reads discovery rows, not gate survivors.**
  `_list_show_provider` gets the candidate set built from the pool's provider
  partitions, before any gate runs.
- **Per-file error text is Python's.** `[Errno 21] Is a directory:` must reach
  stderr with the `[Errno N]` prefix and the `repr`-quoted path.
  `main.rs::python_io_error` already does this shape for the parse route.
- **Exit statuses**: 2 for a grammar or malformed-boolean-query error, 1 for no
  hits *and* for an empty candidate pool, 0 otherwise. An empty pool exits 1
  silently; a no-hit search prints a hint unless `--only-id`.
- **An invalid regex is not an error.** `compile_search_term` catches `re.error`
  and recompiles `re.escape(pattern)`, so a bad pattern becomes a literal
  search. Only a malformed *boolean* query raises and exits 2.
- **`--raw` is the one mode that must buffer**: a single session with exactly
  one visible message prints the bare body, anything else gets `Session <id>`
  headers joined by `\n\n---\n\n`.
- **Search truth is three sources, not one**: a term matches a session if it
  matches any summary, the current custom title, **or** any rendered message.

### The one property no byte oracle can see

**Every streamed session id is flushed individually**, at
`commands/search.py:350` — `print(..., flush=True)`. Keep it, and keep it
explicit.

That flush is the entire deliverable of a measured performance scope. Before it,
`ch search 'CLIENT_ID/CARD' -ca 2m -ll | cat` showed its first id at **15.995
seconds**; after it, **0.38 seconds**. Completion time did not change at all —
the whole gain was Python block-buffering three short lines because stdout was a
pipe.

So an implementation that buffers those ids emits **byte-identical output in
identical order** and gives back 15.6 seconds of the product's most visible
latency. The byte comparator cannot see it. Exit codes cannot see it. The
704-case corpus cannot see it. Only a timing assertion can — time to first id
through a real pipe, which is how the original scope measured it.

It is the mirror image of the preserve-because-wrong list in §6: those are wrong
behaviours that look right; this is a right behaviour whose absence looks
identical. A future reader removing the flush for throughput would be making a
defensible-looking change.

Do not generalise the pager's fallback rule into this. `rust/pager.rs` does not
flush its **stdout fallback**, matching `sys.stdout.write`, while it **does**
flush the pager's stdin per chunk. Three flush sites, three different answers,
all of them Python's.

### Four more of the same class, all in the engine

Confirmed intentional by test or source, all invisible to every byte gate:

1. **Date probing is lazy and short-circuits.** `pool_filter.py:79–88`. Each
   probe runs only if its own filter is active, and a failed `-ma` check returns
   *before* the `-ca` probe. An implementation that probes both up front and then
   evaluates is byte-identical and doubles pool-wide file I/O.
2. **Sidechains are excluded before the timestamp probe, not after.** Pure
   ordering, pinned by a test. Reversing it probes every sidechain for nothing.
3. **An early pager close stops later scanning.** `rust/pager.rs` exposes
   `closed()`; the requirement is that the engine's loop actually acts on it. A
   port that keeps scanning after the reader quit produces identical output —
   none — while burning the rest of the corpus.
4. **Non-raw modes stream per hit; `--raw` buffers deliberately.** A port that
   buffers uniformly is byte-identical and turns every search from incremental
   into all-at-the-end.

**Why these are at risk, which is the part to internalise.** Every one is doing
*less work, in a specific order, with an early exit*. None is an algorithm
choice — they are economies layered onto an already-correct implementation,
designed not to change the answer. **A native implementation is fast enough that
each one looks like unnecessary complexity.** Someone removing them in good
faith will be byte-identical, and right about everything except the thing that
mattered.

They are documented rather than gated on purpose: only the id flush has a
measured cost, and asserting a budget nobody has measured is how the age-colour
fixture rotted. This document is the only place a reader will meet them.

---

## 8. How to prove it

The differential oracle is the whole point and it is fragile — protect it.

`ch-legacy search ARGS` and `ch search ARGS` can be diffed on the same corpus at
any moment, because the Python implementation is deliberately still alive.
Deleting it is its own final slice, gated on a green byte harness, and the
fuzz-discovered cases must be frozen into fixtures **before** that deletion or
the coverage dies with the oracle.

- Pin the clock with `CH_NOW` (format `%Y-%m-%dT%H:%M:%S`, both sides accept
  exactly that and nothing else) or every age-bearing diff is meaningless.
- Drive both binaries under a pty at two or more widths, **neither of them 80**.
  80 is also `main`'s fallback constant, so a diff at 80 hides both a width
  defect and a total failure to measure. Make one width narrow enough to force
  elision in list rows and panel titles.
- **Three build configurations, not two.** `cargo check --no-default-features`
  green does not imply `cargo test` green — check skips test targets. The binary
  is the `--no-default-features` build, and it is the one with no ambient
  feedback. Validate in a private `CARGO_TARGET_DIR`; `target/release/` is
  contended and `uv tool install --force` deletes the existing install *before*
  building the replacement.
- The test suite runs the **installed** binary. If you have not rebuilt, a green
  suite is measuring code without your change in it.
- Every gate guarding a ported algorithm ships with an automated falsification
  that fails the build if it stops catching a deliberately wrong implementation.

---

## 9. The cutover

One branch added to `rust/main.rs` for `search`. No Python is edited, added or
deleted. Reverting is deleting the branch. The no-Python proof is process-level:
remove `ch-legacy` from the launcher directory and confirm `ch search` still
answers.

---

## 10. Where the rest of the reasoning lives

`teammates/search-runtime/`: `search-runtime-map.md` (authority map, falsifiers,
definitions of done, §13 inherited constraints, §15 the `.isascii()` invariant,
§17 preserve-because-wrong), `reconciliation-draft.md` (the full divergence
ledger and sizing), `branch-boundary-comparison.md` (why the branch's
decomposition beat mine), `RESUME.md` (current state).
