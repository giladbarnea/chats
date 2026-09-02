# The six performance gates, re-derived — a landing spec

**Measured by `g5-runner`, 2026-09-01T18:23–18:27Z. Landed by `parity-finisher`.**
**Same split as the freeze: the runner produces the numbers, an implementer writes
them.** The row text below is meant to go **at the rows**, not into a commit
message — every note here exists because a reader meeting the number later needs
it and cannot ask.

## What replaces what

**All six shapes become interleaved ratio gates against the Python route.** The
four absolutes and the two ratios were all derived in one window from the same
subject, so they are one class and are corrected together.

| shape | worst observed ratio | margin | **CEILING** | measured spread |
| --- | ---: | ---: | ---: | ---: |
| `help` | 0.032 | **2.00×** | **0.064** | **1.29×** |
| `broad literal miss, id-only` | 0.568 | 1.25× | **0.710** | 1.11× |
| `broad list, absolute date` | 0.405 | 1.25× | **0.506** | 1.04× |
| `colored matches` | 0.109 | 1.25× | **0.136** | 1.02× |
| `selective literal, id-only` | 0.444 | 1.25× | **0.555** | 1.02× |
| `broad regex miss, id-only` | 0.445 | 1.25× | **0.556** | 1.03× |

**Ceiling = worst observed ratio × margin.** Both inputs are in the table so the
arithmetic is checkable rather than trusted.

**Method:** interleaved, 5 pairs per shape, one window, `target/release/ch`
against `.venv/bin/ch-legacy`, `HOME` at the fixed corpus, `NO_COLOR=1`,
`COLUMNS=96`.

**Reproducibility:** a separate earlier window of different design gave 0.030,
0.549, 0.400, 0.109, 0.430, 0.436 against these 0.030, 0.550, 0.404, 0.109,
0.438, 0.434. **Two windows, ~2% agreement, no shape disagreeing.**

---

## Row notes — these go in verbatim

### 1. Why the previous ceilings were higher. It is not a relaxation.

**The previous ceilings were derived from the branch build, and the plan said so
in the same edit that set them.** `review-profile-plan.md:99`:

> *"The native column is the reference branch binary — **evidence that these
> budgets are reachable, not a claim about our deliverable.**"*

**Without this line at the gate, a reader sees ceilings loosened and reads a
relaxation.** It is a correction: the old numbers described a different program.

**⚠ And ignore both branch builds entirely.** Two exist —
`private-binaries/ch-native` `40a5b5d8…` and
`tests/data/launcher-provenance/ch-0ffde41` `257f5052…` — **same revision,
different artifacts, so neither is a baseline for the other.** A comparison
against the second was made and **withdrawn**, including the half that favoured
the port.

### 2. Why this is not the ratio construction that was disproved

**That one rotted because its denominator was a *different command* whose growth
did not track the subject's.** Here the denominator is **the same query, the same
corpus, the Python route, in the same window** — it scales identically by
construction.

**Ratios fix rot. They do not fix noise.** The noise here is **2–4% on five of six
shapes**, so nothing is being asked of the ratio that it cannot do. **All three
conditions hold here; none held there.** The two rulings do not contradict.

### 3. What the port is paying for

**Regex semantics reproduced exactly** where the branch deviates, and **the
confirmation pass** the record makes mandatory — without it, agent-bearing
sessions produce false negatives, and two tests pin that.

**A ceiling with no account of what it buys is a number someone will try to
tighten.**

### 4. `help` carries a wider margin, and it is earned rather than granted

**Its measured spread is 1.29×, against 1.02–1.11× on every other shape**, because
it is a **5.8 ms** measurement dominated by process startup. **The margin covers
the measured noise band** — that is the rule, and it is derived from the thing it
protects against rather than applied uniformly.

### 5. `broad literal miss, id-only` — the inversion worth a reader's attention

At **0.550** this is the port's **thinnest advantage**, so its ceiling sits closest
to 1.0. **It is simultaneously the row most likely to catch a real regression and
the row with least room to do it in.**

**As an absolute it was the row that could not discriminate at all** — 462 ms on
the *Python* route against a 750 ms budget, which both routes passed. **As a ratio
it discriminates by construction and is the most valuable of the six.** The same
shape went from proving nothing to proving the most.

### 6. Standing rule: a flapping row is widened with a recorded measurement, never quietly

**That is exactly how the live-pool budgets reached 1750 ms and 2500 ms — each
widening was locally reasonable and none was recorded as a measurement.**

---

## What these gates do NOT cover

**⚠ Time only.** On memory the port is **worse** than Python and measured so on
the same day: **+576 MB against +451 MB, slope 9.00 against 6.99, two extra
resident copies, unattributed** (checks 12 and 13).

**A user searching agent-bearing sessions gets an answer faster and pays more
resident memory for it.** *"No user-visible regression"* is true of time and false
in general.

## The consequence of the margin, stated so it is chosen and not discovered

**A 1.25× margin over the worst observed means these gates tolerate the port
becoming 25% slower before firing** (100% for `help`). Against a 2–4% noise band
that is real headroom without being blind. **The 1.5× first proposed would have
tolerated 50%, which is the size of regression a refactor introduces** — that is
why it was not taken.
