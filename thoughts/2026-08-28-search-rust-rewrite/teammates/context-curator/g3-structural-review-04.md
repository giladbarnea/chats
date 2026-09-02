---
date: 2026-08-29
author: context-curator
role: G3 structural review, pass four — the timing economies
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
scope: search_run.rs, search_output.rs, search_engine.rs — timing economies 1, 3, 4
verdict: all three preserved; economy 4's test is the standard; one cannot-fail guard confirmed in plan.rs, which pass three missed
---

# G3 structural review 04 — the timing economies

The review nobody else can do: these four behaviours are byte-invisible and cost-unmeasured by design, so no corpus and no byte gate can reach them. The only method is reading whether the economy survived.

Economy 2 was confirmed in pass three. This pass takes 1, 3 and 4.

---

## Economy 1 — per-ID flush · **preserved, and correctly scoped**

The measured behaviour: `commands/search.py:350` is `print(..., flush=True)`, and it moved first-ID latency from **15.995 s to 0.38 s** with completion time unchanged. A native engine that buffers regresses the product's most visible latency by 15.6 seconds and passes every byte gate.

`search_output.rs:308`: `if self.output.mode == SearchOutputMode::OnlyId && stdout.flush().is_err()`.

**The scoping is the part to check, and it is right.** Python flushes explicitly in exactly one place — `_print_session_id`, the `-ll` path. Not in the other streamed modes. So a native flush scoped to `OnlyId` mirrors the oracle rather than over-applying it. Flushing everywhere would be defensible and would not match.

`--raw` buffers, as it must: `search_run.rs:84` selects `BufferingSink`, and line 154 names it "the one mode that could not stream."

## Economy 3 — sidechains excluded before the probe · **preserved, and earlier than required**

`inventory.rs:336–339` computes `excluded_sidechain` during discovery and filters with `(!excluded_sidechain).then(...)`, so an excluded sidechain never becomes a row at all.

The economy required exclusion before the timestamp probe. This is stronger: it happens before the path enters the inventory.

## Economy 4 — early close stops the scan · **preserved, and its test is the standard**

This is the one `reviewer-profiler` measured as **lost on the branch build** — the branch kept scanning after the reader stopped, so `| head` cost a full corpus scan for identical bytes.

`search_engine.rs` states it in the module header as behaviour 1, and the sink trait carries `closed()`, checked at three points in the scan loop.

**The test is falsifiable, and defends against the weak version of itself.** `early_close_stops_scanning` asserts `visited == 1` **exactly**, with the reason in the code: *"A loop that stopped only at the next batch boundary would confirm 256 files and still satisfy a bound of 2,000."* An assertion of `visited < files.len()` would pass on an implementation that has lost the economy.

**And it carries a negative control.** `without_early_close_the_whole_pool_is_scanned` asserts 600 visited, so the first test is measuring the close rather than an unrelated stopping condition.

Sensitivity and specificity as a pair. That is the shape the width calibration needed and it is here without being asked for.

---

## The cannot-fail guard in `plan.rs` — confirmed, and pass three missed it

`slice-reviewer` found that `the_lazy_screen_agrees_with_the_eager_filter_on_valid_dates` cannot fail. Confirmed independently:

```rust
let missing = Path::new("/definitely/not/here.jsonl");
```

The only subject is a path that does not exist, so it yields no timestamps and all four filter combinations agree trivially. Swapping `>=` for `>` leaves it green.

**I passed `plan.rs` in pass three and did not catch this**, and the reason is a real limit of my method rather than an oversight.

My review asks *does the code preserve the property?* It does not ask *would the test notice if the code stopped?* Those are different questions, and only the first was in my criteria. A file can pass a structural review while its guards are inert, because I was reading the implementation against the behaviour and never the test against the implementation.

The two questions belong together, and the contrast is in this same pass: economy 4's test asserts an exact count *and* carries a negative control; the `plan.rs` guard has neither and looks equally reassuring in a diff.

**Added to my criteria for any remaining pass:** for each preserved economy, does a test exist that fails when the economy is removed? Not "is there a test" — would it go red.

---

## Coverage

Read at depth: the sink selection and flush path in `search_output.rs` and `search_run.rs`, the scan loop and early-close handling in `search_engine.rs`, and the two tests named above.

**Not read:** the rest of `search_engine.rs` (631 lines) beyond the scan loop and its economy tests, and `search_output.rs` beyond the sinks. Their correctness against non-timing criteria is unreviewed by this pass.
