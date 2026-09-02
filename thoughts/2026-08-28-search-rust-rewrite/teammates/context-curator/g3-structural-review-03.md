---
date: 2026-08-28
author: context-curator
role: G3 structural review, pass three
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
scope: rust/search/plan.rs, rust/cells.rs (color.rs and python_io.rs reassigned to slice-reviewer)
verdict: plan.rs passes; cells.rs passes. Finding 3 RETRACTED — it was an instrument artifact, twice over.
---

# G3 structural review 03 — planning and cell measurement

**Coverage, at the top.** Two files, both read against criteria and both at full depth: `plan.rs` (238 lines) and `cells.rs` (513, excluding the 7,384-line generated table, which I did not read). `color.rs`, `python_io.rs`, and the decode logic of `session.rs` and `codex.rs` are `slice-reviewer`'s.

---

## 1. `plan.rs` — **pass, and it documents its own economies**

The conservative-gate criterion is satisfied structurally, in the strongest available form: **the type is named for it.** `Gated::Survives`, not `Gated::Match`. Surviving means joining the pending batch; it never means the session matched.

Three further properties, each stated in the code rather than merely implemented:

- **The Pi deferral is called a correctness requirement.** "A Pi file carrying the joined-agent marker cannot be rejected here, because that record synthesises visible text absent from the raw bytes. **Deferring is a correctness requirement, not a missed optimisation.**" That is the exact sentence a future optimiser needs to meet, at the point they would reach for the optimisation.
- **Positional decisions, with the assertion justified.** "Returns one decision per input path, positionally. The engine asserts the length, because a mismatch would misalign every decision in the batch rather than failing loudly." The old Python carried both a length check and a `strict=True` zip, which a reviewer flagged as redundant. Here there is one check with a stated reason — the redundancy resolved in the right direction.
- **Timing economy 2 survives and is documented in the module header:** probing is lazy per filter and short-circuits, so a file rejected by `-ma` is never opened for `-ca`.

`Gated::Failed(String)` preserves Python's error text "including its `[Errno N]` shape".

## 2. `cells.rs` — the correction is honoured, in the header

The module opens with the second-truncation finding stated as its reason for existing:

> Every chrome line the product emits is wrapped in a Rich `Text` with `overflow="ellipsis"`, which clips the assembled line to the console width in **cells**. That is a second clip on top of `elide_to_width`, which counts code points — two layers, two units, both load-bearing. **A port carrying only the first is correct at every ASCII width and wrong on the first wide character.**

That is `views-and-colour`'s correction to my item 3, encoded where the next reader meets it. Nothing further needed on that criterion.

## 3. RETRACTED — there is no divergence, and the finding was an instrument artifact

**I claimed `cells.rs` reads an ambient input the oracle does not have. That is false.** Python reads `UNICODE_VERSION` too, at `rich/_unicode_data/__init__.py:67`. Retracted in full; the section is kept rather than deleted so the failure is visible.

### Two instrument errors, and I made both

**First: `rg` honours `.gitignore`, and `.venv` is ignored.** My "no match anywhere in site-packages" came from a search that silently skipped the entire directory. Reproduced just now:

```
rg -n  "UNICODE_VERSION" .venv/   ->  nothing
rg -un "UNICODE_VERSION" .venv/   ->  rich/_unicode_data/__init__.py:67
```

**This project's own instructions specify `rg -u`.** I had the guidance and did not apply it. `reviewer-profiler` hit the identical trap earlier today and caught it before reporting; I did not.

**Second, and worse: my attempt to verify the correction fell into the trap I had praised them for avoiding an hour earlier.** I measured `cell_len` with and without the variable using a plausible-looking non-ASCII character and got 40 both ways — which would have "confirmed" my wrong finding. Their probe characters are *derived from the table delta*; mine was a guess. Measured correctly the values are 40 and 60, and end to end the same headline renders 31 characters unset and 20 under `9.0.0`.

I wrote to them that deriving probe characters from the delta was the part worth keeping, and then verified with a character I picked because it looked foreign. **A probe that cannot distinguish the two states reports "no difference" and reads exactly like a result.**

### The true picture

`UNICODE_VERSION` is read by **both** routes. Rich does not use `unicodedata` for cell width at all — it ships 21 tables and selects one from that variable. `cell_tables.rs` is those same tables generated from the installed Rich, and `for_version` reproduces the selection rule, including that an unknown-but-valid version falls back to the newest table *older* than it. A deliberate seam, correctly ported.

The "native side ignores it" reading that reached me was about the **abandoned branch binary**, which predates `rust/cells.rs`. `reviewer-profiler` scoped that explicitly; the scope was lost by the time it reached my desk, not by them.

### The one thing worth keeping from this

`search_run.rs:108` threads `from_environment()` into `PlainSink`. That is correct and currently **inert** — cell measurement is reached on the plain routes but cannot change their bytes, because the product's own elision counts code points rather than columns.

**It becomes load-bearing the moment anyone repairs `elide_to_width` to count columns.** That is a live coupling between preserve-because-wrong item 3 and a threading decision in a different file, and it is invisible to whoever makes that repair. Worth a comment at the repair site rather than at the threading site.

## Not covered

The 7,384-line `cell_tables.rs` is generated data; I checked its consumers, not its contents.

**Closed in principle after this review.** The tables are generated from the installed Rich, which ships twenty-one of its own and selects one by `UNICODE_VERSION`. So the correctness of `cell_tables.rs` reduces to **the generator plus the installed Rich**, not to 7,384 lines nobody read. That is a better answer than "unreviewable", and it names what a reviewer would actually have to check.
