---
date: 2026-08-29
author: context-curator
role: G3 structural review, pass five — non-timing criteria
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
scope: search_engine.rs and search_output.rs outside the scan loop and sinks
verdict: behaviour faithful; one unguarded invariant, found by the criterion added yesterday
---

# G3 structural review 05 — gate soundness

First pass applying **criterion 5**: for each preserved property, does a test exist that *fails* when the property is removed? It found something the previous four passes would not have.

---

## The finding — two hand-maintained lists of nine flags, and nothing guards their agreement

The candidate gate's eligibility is decided in two places that must stay in step:

- `search_output.rs:397` — `can_use_json_string_gate`, listing the nine visibility flags **negated**.
- `search_output.rs:573` — `gate_bypassed` inside `term_path_candidate_matches`, listing the same nine **positive**.

**The behaviour is faithful, including both asymmetries.** `message_selection == All` appears only in the eligibility check, correctly — raw-byte presence is selection-independent. And `tools_requested()` handles both `ToolVisibility` variants, which is the Rust equivalent of Python needing `bool()` because `show_tools` can be a non-empty filter list. Those are the two things I said must survive a collapse, and they survived without one.

**But the structure was ported along with the behaviour, and nothing tests it.** No test function in the file names the gate, the bypass, visibility, or the flags. The two lists are independently maintained with no guard on their agreement.

**Named mutation that should break a test and does not:** add a tenth visibility flag to `gate_bypassed` and not to `can_use_json_string_gate` — or the reverse. Nothing goes red. The gates diverge silently, and the direction that loses hits is the one no byte gate can see, because a search that should have deferred instead rejects a file and the output is simply a missing result.

This is exactly the hazard my criteria named in the Python original: *"a tenth visibility flag requires touching both sites or the gates diverge silently."* I asked for the collapse. The port kept the duplication instead — which is a defensible choice, since collapsing risks changing behaviour — but then the invariant needs a test, and there is none.

**Cheapest guard:** one test asserting that for every flag combination, `can_use_json_string_gate` and `gate_bypassed` are exact complements on the nine. That is a table test over 2⁹ combinations and it fails the moment either list gains a member the other lacks.

## Why the earlier passes missed it

Passes one through four asked *does the code preserve the property?* The answer here is yes — and that is why it passed unremarked when I read this surface for economy 1.

Criterion 5 asks the second question, and the two answers differ: **the property holds and nothing would notice if it stopped.** That is the same shape as the `plan.rs` cannot-fail guard, one level up — there a test existed and could not fail; here the test does not exist at all, and both look identical from a diff that shows green.

## What else was read

`stream_search`, `flush`, `Gated`, `Confirmed`, `Outcome` in `search_engine.rs`; `confirmed_from`, `truncate_to_cells`, `display_session_id`, `metadata_block`, `path_candidate_matches`, `term_can_change_under_json_decoding`, `term_can_match_generated_marker`, `format_raw`, both sinks in `search_output.rs`.

The conservative-gate criterion holds throughout: every bypass returns `true`, never `false`, so uncertainty always reaches semantic confirmation. `term_path_candidate_matches` closes with `.unwrap_or(true)` and the comment records why — *"Answering `true` reaches the same place: confirmation opens the same file."*

## Not covered

The ~789 lines of tests in these two files were assessed only where they bear on the criteria above. I did not evaluate every test for falsifiability — criterion 5 applied to a whole file is a larger job than this pass, and the one instance it found here was reachable by asking which invariants have no test at all, rather than by auditing tests one by one.

That distinction is worth keeping: **"which invariant is unguarded" is cheaper to ask than "which test cannot fail", and it found the same class of hole.**
