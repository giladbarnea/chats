---
role: context-curator
updated: 2026-08-28
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: RE-DERIVED at this digest on 2026-08-28. Every oracle-dependent
  claim in this document was re-run and reproduced identically. The earlier stamp on
  this file was a `git diff -- src/chats` digest, which cannot see .venv/bin/ch-legacy
  or the installed RECORD, so it could not have supported this claim — hence the
  re-derivation rather than a restamp.
current_assignment: independent reviewer, G3 handed-off packages
---

# RESUME — context-curator

**ON CALL, 2026-08-29, context window ~78%. G3 structural review is COMPLETE — all five passes delivered and promoted. Scope empty.**

**If you are cold, read `decision-record.md` first, then `g3-review-criteria.md`.**

**The two irreplaceable passes are done.** The four timing economies — byte-invisible and cost-unmeasured by design, so no corpus or byte gate can reach them — are all confirmed preserved (passes three and four). That is the review `decision-record.md` entry 2 exists to protect, and it is closed.

**Five G3 passes, one finding each worth carrying:**
1. Pass 1 — extraction and reconciliation surfaces. No defects. Watch item: `scan_resolution_facets_impl` is the last un-extracted scan (`state.md` L10).
2. Pass 2 — grammar and strip semantics. No defects. The `python_strip` test that asserts the *wrong* behaviour beside the right one is the mission's standard for that pattern.
3. Pass 3 — `plan.rs`, `cells.rs`. Both pass. **Finding retracted**: `UNICODE_VERSION` is parity, not divergence. See the `rg -u` warning below.
4. Pass 4 — timing economies 1, 3, 4. All preserved. Economy 4's test is the standard: exact count, reason in the code, plus a negative control.
5. Pass 5 — gate soundness. **Criterion 5's first trial found an unguarded invariant**: two hand-maintained nine-flag lists at `search_output.rs:397` and `:573` with no test on their agreement. Fix queued for `engine-and-codex` before G5 — one table test over 2⁹ combinations asserting exact complements.

**Criterion 5, in the form that actually works:** for each preserved property, does a test exist that *fails* when the property is removed? Operationally, do not audit tests for falsifiability — **start from the invariant list and ask which invariants have no test at all.** An absence is far cheaper to spot than an inert presence, and both catch the same class.

**Earlier state below.**

**SOFT-PAUSED at the admiral's 91% window mark, at a clean seam. Pass three delivered and accepted; nothing in progress.**

**Read this before running any `rg` search:** `rg` honours `.gitignore`, and `.venv` is ignored. **Use `rg -u`** — the project instructions say so and I did not. That default produced three confident false negatives across the team today, one of them mine: I reported that Python does not read `UNICODE_VERSION` when it does, at `rich/_unicode_data/__init__.py:67`. Finding 3 of pass three is retracted in place.

**Also retracted:** my verification of that retraction. I measured `cell_len` with a plausible-looking character rather than one derived from the table delta, got identical numbers, and would have confirmed my own wrong finding. Derive probe inputs from the thing that differs, never from what looks foreign.

**Earlier stop point below.**

**STOPPED at ~78% of context window, mid-G3, by the first mate's instruction. Not a capacity boundary after all — I had measured nothing.**

**What is left of my scope, and it is larger than my window was:** `color.rs`, `cells.rs`, `plan.rs`, `python_io` are **unread** (`state.md` L46). The four timing economies are still held for the engine. I declined to produce four thin passes rather than leave the gap visible — recorded as a decision, not an omission.

**Routed, not mine any more:** the bare-`.trim()` question. 23 sites in `session.rs` to `session-core`, 9 in `codex.rs` to `engine-and-codex`. The question is whether each site's Python counterpart uses `.strip()`; if it does, they diverge on C0 separators.

**Earlier state below.**

**SOFT-PAUSED 2026-08-28 at 92% of the 5h window, mid-port. Idle at the pause, nothing in progress, nothing lost.**

**Stop point:** all commissioned work complete. Last action was correcting `preserve-because-wrong.md` items 3 and 4 after `views-and-colour` rendered item 3 and found its predicted symptom wrong — item 3's overflow never reaches the screen (Rich clips a second time in cells, so a gate must pin composed bytes, not the function's return); item 4 does reach the screen unmodified (400 visible chars NFC against 247 NFD, rendered). Both corrections landed. No G3 slice ever arrived for review.

**Situation.** The team is porting `ch search` to Rust. My original job (classifying historical `thoughts/`) is complete. My current job is **independent reviewer** for the packages `session-core` and `search-runtime` hand off. Nothing has arrived to review yet.

**One sentence you must not lose:** my value to this team has come from having *no stake in any answer being right*, including my own. The first mate considered making me an implementer and decided against it on that basis. If you are asked to implement, re-read "Assignment" below before agreeing.

---

## 1. Task overview

Read the charter at `thoughts/2026-08-28-search-rust-rewrite/charter.md` and the desk `state.md`. My leader is `search-firstmate`. I do not edit production source or tests, except the fuzz corpus noted below, which `contract-owner` granted.

Success for my current role: each handed-off package is reviewed against criteria fixed **before** the package arrived, with findings backed by instances rather than aggregates.

Constraints that bind me:
- Only `search-firstmate` writes team-level files. I work in `teammates/context-curator/` and ask for promotion.
- I do **not** run `memo` or touch `.optmem/`. That is the first mate's alone.
- I cannot message the captain. Peers first; otherwise take the simplest sound path and record it.
- Do not switch branches in the shared checkout.

## 2. Prior state at session start

Clean `main`. Charter said build the native search route from scratch, treating historical notes as untrusted. Five teammates were holding all `thoughts/` material as untrusted pending my classification. That framing turned out to be built on a false premise — see Discoveries.

## 3. Current state

All my artifacts are promoted to the desk and duplicated in `teammates/context-curator/`.

**Created (mine, promoted):**
- `context-relevance.md` — classification of the four historical directories, plus the unmerged branch treated as a fifth.
- `branch-corpus-reproduction.md` — 173/173 of the branch's expected outputs reproduce against `main`'s Python.
- `branch-deviation-sweep.md` — no new branch deviations; the reconciliation surface is two commits.
- `content-fuzz-result.md` — the generated adversarial corpus and its results, including the NFC/NFD divergence.
- `calibration-currency-check.md` — nobody runs a stale calibration copy; the oracle was unpinned; my own sizing error corrected.
- `preserve-because-wrong.md` — **eleven behaviours that must be preserved because they are wrong.** The most reused artifact. Items 9–11 are a distinct class: *one value consumed by two code paths that disagree about what counts as supplied.* My original signature for that class said "two libraries" and was too narrow; withdrawn in place, along with a negative result it produced.
- `g3-structural-review-01.md` — first G3 pass, full depth. No defects. Watch item: `scan_resolution_facets_impl` is the last un-extracted scan and therefore where the branch's fork can still reproduce (`state.md` L10).
- `g3-structural-review-02.md` — second pass, **targeted not full-depth, and it says so at the top**. Grammar passes. The Python-vs-Rust strip divergence on C0 separators U+001C–U+001F is known and handled by `session::python_strip`, applied at 10 sites.
- `g3-review-criteria.md` — **read this first if a package has arrived.** My review criteria, fixed in advance.
- `decision-record.md` — **read this first if you are cold.** Twelve decisions with the alternatives rejected and the evidence that decided them, marked firsthand or secondhand. `state.md` has the rulings; this has why. Decision 2 explains why an idle reviewer is not a spare implementer, and decision 9 says what survives if the desk does not.
- `timing-shaped-behaviours.md` — five *right* behaviours whose absence is byte-invisible. The mirror class to preserve-because-wrong. **Recommendation revised in place:** gate items 1 and 4, after early-close was measured as lost on the branch build (branch deviation 10).

**Created (tooling, in `tests/data/search-content-fuzz/`, approved by `contract-owner`):**
- `SEED.json`, `build_home.py` — deterministic 169-session adversarial corpus, no wall-clock input.
- `fuzz_harness.py` — pty driver, two-axis calibration gate, invariant observer. **80 runs: 4 colour tiers x 5 output modes x 4 widths.** Colour tier was added 2026-08-28 after L22 — every earlier result was bounded to truecolor and did not say so. The width invariant is tier-aware: at `TERM=dumb` the product legitimately uses width 80, and asserting pty width there produced 8,529 false violations.
- `nfc_nfd_probe.py` — standalone.

**Scratch (mine, `teammates/context-curator/`):** `pty_probe.py`, `reproduce_branch_corpus.py`.

**Pre-cutover freezes (impossible to recreate once Python search is deleted):**
- `tests/data/search-content-fuzz/frozen-oracle-age-colour/` — the oracle's bytes for the 7 cases where the branch corpus and the oracle disagree.
- `tests/data/search-content-fuzz/frozen-oracle-nfc-nfd/` — 12 oracle renders that keep `nfc_nfd_probe` asking the same question after re-pointing.

## 4. Important discoveries

**The founding one.** Branch `wip/cycle-02-native-default-pause-20260821` @ `0ffde41` contains a *completed*, independently verified native rewrite of all three journeys including search. Nothing in project memory mentions it. Ruled **prior art, never an oracle**; `main`'s Python is the sole behavioural truth. Its own closure review overturned four of its own nine findings — **read that branch's prose as leads, never verdicts; credit its source, distrust its paperwork.**

**Two invisible-divergence classes, opposite polarity.** (a) Eight preserve-because-wrong behaviours — wrong behaviours that look right; a port silently improves them. (b) Five timing-shaped behaviours — right behaviours whose absence looks identical; economies layered on a correct implementation, which a fast native port reads as removable complexity. Neither class is visible to a byte comparator.

**Detail on (a):** In `preserve-because-wrong.md`. The trap: a competent port silently *improves* them, output looks correct, no gate fires. Highest risk is the age label/colour one-bucket misalignment, because the byte comparator normalizes that colour away. The DST fold cannot appear in any fixture — it exists only inside the fold.

**Three method rules I contributed, now standing team constraints:**
1. No finding reported from an aggregate alone — dump and inspect the instances. Saved three wrong reports today, **none of which looked wrong**.
2. An invariant is only evidence over the modes where it is actually the contract.
3. Instruments are imported, never copied; a copy grades itself against a stale probe set and reports CALIBRATED while blind.
4. **A limit of your instruments is never a property of the world.** Say "nothing we have can see this", never "this cannot be seen". I broke this one myself: I called the timing behaviours unmeasurable, `reviewer-profiler` built the instrument anyway and found a live defect. Had they believed me it would have reached G5.
5. A discovery command that finds only the compliant cannot measure coverage — `rg oracle_tree_state` returns the artifacts already stamped, never the ones at risk.
6. **A recorded disagreement must store both sides.** If a finding says "X differs from Y" and only Y is on disk, the finding dies the moment X becomes unavailable. This is the rule behind both pre-cutover freezes and it generalises past cutover to anything transient — a live corpus, a wall-clock render, a machine-specific path.
7. **Converting an instrument: ask what the re-posed question answers if the new subject is wrong.** If the answer is still "pass", the question got weaker. An instrument can survive re-pointing perfectly and become worthless — my NFC probe did.
8. A stamp that does not apply dilutes the ones that do. Say NOT ORACLE-DEPENDENT explicitly rather than stamping for uniformity.

**The oracle rule (mine, now binding):** every characterization records the oracle revision **and** the `src/chats` tree state. `.venv/bin/ch-legacy` reaches the working tree via the editable install, so naming a revision alone can be quietly false.

**Two errors of my own, both caught by rule 1.** A consistent off-by-one at four widths that was my width measure counting U+200B as one column. And sizing the port reconciliation at five files/185 insertions when it is 26 files/913 — three owners were estimating on it. Both looked entirely plausible.

**Approach that worked:** probe the oracle, then read the instances. **Approach that did not:** mining the branch's Rust comments for admitted deviations — its code annotates its parity obligations carefully and yielded nothing.

## 5. Next steps

1. **If a package has arrived:** review it against `g3-review-criteria.md`. Method is committed there — read the diff in full, then probe behaviours against the **built artifact**, not the diff or the author's summary. Findings carry instances. State what you did not cover.
2. **If nothing has arrived:** stay idle. The first mate explicitly preferred me fresh over filling time.
3. **If asked to take an implementation package:** I told the first mate I would take it rather than let the port stall, and they accepted one condition in advance — the review criteria transfer to a **named person at the same moment**, not later.

Open, not mine: `contract-owner`'s comparator was failing its own gate on the age-SGR dimension; the first mate was resolving it with them.

## 6. Context to preserve

- **Never `text=True` on a capture.** Universal newlines rewrite `\r\n` and lone `\r`. A pty also applies ONLCR, so pty bytes may only be compared against pty bytes.
- The user has ADHD; write summaries as re-grounding for someone who saw none of the work. ASD-STE100, no fluff, no manufactured caveats. See the global instructions.
- Deliverables under `teammates/context-curator/`, then request promotion.
- Not covered, recorded by the first mate as a conscious gap: the three provider adapters' normalization rules line by line. Needs differential execution against real payloads, not pattern reading.
- Read at session start, in order: `charter.md`, the four historical directories, `ARCHITECTURE.md` (accurate for HEAD; prefer it for present-tense questions), then `git log` and the branch.
