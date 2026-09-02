# RESUME — query-semantics (final)

Session ended at ~10% context. **Clean stop: nothing unfinished, nothing unproven,
nothing mid-flight.**

Read `e1-confirmation-handoff.md` if you are taking the engine, `query-semantics-map.md`
if you are taking the query layer. Both are symlinked onto the desk and current — I
verified the links resolve to these files byte for byte. This document holds only what
is in neither: the answers to questions nobody asked.

---

## Delivered

| module | state |
| --- | --- |
| `rust/search_query.rs` | native query engine. 994 → **0** divergences over 4,000 generated patterns; 18 defects fixed; 11 mutations caught |
| `rust/pool_filter.rs` | date and directory filtering. **36/36** against CPython; 5 mutations caught |
| `rust/session_pool.rs` | discovery, provider partition, newest-first order. **0 of 5,036** positions differ |
| `rust/search_engine.rs` | scan loop. Now `engine-and-codex`'s; they restructured it and all 8 of my properties survived |

At handoff: 135 lib tests, 36 doctests, release build green in the shipping configuration.

---

## Answers to questions nobody asked yet

**"Can I widen `CANDIDATE_WINDOW`?"** The measurement sits beside the constant:
128 / 256 / 512 completed a full scan in 1.422 / 1.188 / 1.182 s, and 512 bought 6 ms of
completion while adding **207 ms to the first barrier**. The window exists to make
newest-first streaming visible, so widening trades the user's first result for almost
nothing. `engine-and-codex` re-pointed it at *path-filter survivors* rather than scanned
files, which is what Python counts; the measurement still holds.

**"Why is `PoolFilter`'s date state private?"** `mafter`/`cafter` are settable only
through `PoolFilter::new`, which parses. That makes an unparsed date unrepresentable
rather than merely discouraged.

**"Why `Vec<(Provider, Vec<PathBuf>)>` and not a map?"** `Provider` is `inventory`'s type
and does not derive `Hash`. Three providers make a linear find cheaper than a cross-file
edit to a peer's enum. If `Hash` is added for another reason, a map is a fine
simplification — nothing depends on the ordering.

**"Why does `parse_date_filter` need the clock seam?"** Relative filters (`1d`, `2w`) are
measured from `clock::resolved_now()`. **Any differential touching date filters must set
`CH_NOW` on both sides**, or it compares two clocks and looks like a filter defect.

**"Why not chrono's `%Y` directly?"** It accepts a two-digit year where CPython requires
exactly four. `-ma 24-12-15` parsed as **year 24** natively and 2024 in Python — a
two-thousand-year error on a plausible input, silently widening the filter to everything.
The format set is chosen from the year token's width. See `harness/date_filter_gate.md`.

**"Is `filesystem_birthtime` safe where `created()` is unsupported?"** Yes — returns
`None` and the caller falls through as Python does when `st_birthtime` raises.

**"The handoff says date filters never read stat mtime, but the code does."** Both true,
and the distinction is the point. The *probe* is content-only; the *fallback* beneath it
is filesystem time, for files with no in-band timestamp. A port that reads the handoff
literally and deletes the fallback drops every timestamp-less file. A prior team shipped
an mtime *short circuit* replacing the probe and withdrew it permanently — imports,
`touch -t` and restore tools produce files whose mtime precedes their content.

---

## Instruments

Under `harness/`, with `README.md` covering each.

- `falsify_gates.py` — mutation runner for the query engine. **Mutates a private copy of
  the crate**, never the shared checkout.
- `date_filter_gate.md`, `pool_order_gate.md` — what each proves, and how.
- `grammar_oracle.py` — drives either binary under a pty at a given width. Strips **all**
  carriage returns; replacing only `\r\n` leaves a stray `\r` at widths where a line
  exactly fills the terminal, inventing mismatches precisely where a real wrapping defect
  would live.

---

## Standing cautions earned here

- **A gate that reimplements the thing it grades is grading itself.** Mine returned the
  correct number and could never have failed.
- **A check can be wrong in time, not just in scope.** A build that skipped test targets;
  a verification that ran after a multi-step edit had closed the gap it opened; a mutation
  run whose crash left the tree mutated.
- **Announce before starting on a shared file.** That a file is absent is a fact about the
  past; announcing is a fact about your intent, and only the second is visible to a peer
  about to return.
- **L9 — a falsifier proves a gate fires, not that it fires for the modelled cause.** Read
  the failure *message*, not the exit status. My `SystemExit` shadow modelled a clean exit
  rather than a crash; the test went red on an older assertion and I nearly recorded a pass.
- **Both directions happen.** Four of five surprising gate failures here were the
  instrument, not the code — but the fifth was the code, and that one changed a type. A
  prior of "assume it is the instrument" would have shipped inert error buffering behind
  seven green tests.

---

## Open

Nothing owned by me. The transient suite failure is **resolved**: `width_parity` could not
distinguish a crashed oracle from a divergence. Fixed and falsified in all three parity
helpers.

One residual, documented and deliberately not fixed by `search-runtime`: the precondition
catches a crash that prints a traceback, not a *clean* non-zero exit from a broken import.
Every alternative discriminator is worse, because exits 1 and 2 are both legitimate here.
