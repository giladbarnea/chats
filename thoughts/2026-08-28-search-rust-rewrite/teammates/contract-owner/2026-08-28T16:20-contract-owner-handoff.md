# Handoff — contract-owner (supersedes the 16:15 version)

Written at 81% of window, seam finished, nothing in flight. Read this one; the
16:15 file is overtaken.

**Situation.** The red acceptance contract for the public `ch search` journey is
built, accepted, and green. Every instrument that would not survive the deletion
of the Python search authority has been converted. Nothing is blocked. What
remains is a role: as the port lands, every differential failure routes here.

**Read first, in this order.** They are the common ground; this document is only
the layer above them.

1. `thoughts/2026-08-28-search-rust-rewrite/charter.md`
2. `thoughts/2026-08-28-search-rust-rewrite/prompts/contract-owner.md`
3. `teammates/contract-owner/contract.md` — **the deliverable.** Everything below
   assumes it.
4. `teammates/contract-owner/RESUME.md` — shorter, operational, kept current.

---

## THE CUTOVER HAPPENED — first result, 2026-09-01

`ch search` is native. The suite stopped being a formality and failed, which was
the point.

**230 of 260 green. 30 diverge, and they are the *same 30* in all three classes**
— byte lock, live differential, authority proof. That identity is the evidence
they are real: a harness fault would fail the three differently. Also 23 frozen
pattern rows, 1 generated pattern, and 7 of 7 age cases.

**One behaviour accounts for 24 of the 30 plus all 7 age failures: `--color
always` emits no colour on the native route.** Measured — 0 escape sequences
against `ch-legacy`'s 3. Every `colored-*`, every `render-fence-*`, wide glyphs,
long wrap, provider column, title elision, the pager case.

**The age failures are not the bucket misalignment.** They fail for absence of
colour. **After the colour fix, re-run those seven and confirm the label-and-
colour *pairs*, not just that escapes are present.** A fix that also aligns
`humanize_age` and `age_style` turns them green for the wrong reason and kills a
preserve-because-wrong finding silently.

**Two divergences unrelated to colour:** a newline emitted after the following
message rather than after the warning (3 cases), and `lowercase-z-rendered-dates`.

**The early-close failure was my control working**, not a defect: 800 sessions
went 557 ms → 153 ms, under its own 400 ms floor, so it refused to report a ratio
it could not measure. Corpus raised to 3000. Floor and ratio unchanged.

**`rebless_oracle.py` now refuses against a native launcher** — its verdict went
circular at cutover. Detected by behaviour: the launcher alone in a directory
with no sibling. Do not work around it.

Nothing relaxed, nothing restamped. Full output: `work/suite-cutover.txt`.

### The 30, by cause

**Colour absent under `--color always` (26):**

```
amendment:normalization-title-elision-52   contract:render-fence-data-60
amendment:normalization-title-elision-72   contract:render-fence-data-96
amendment:normalization-title-panel-52     contract:render-fence-python-60
contract:carriage-return-colored           contract:render-fence-python-96
contract:colored-full-panel                contract:render-fence-shell-60
contract:colored-highlight-painting        contract:render-fence-shell-96
contract:colored-hue-cycle-four-hits       contract:render-fence-web-96
contract:colored-list-fixed-width          contract:render-fence-web-140
contract:colored-matches-panels            contract:render-wide-glyphs-40
contract:colored-narrow-columns-80         contract:render-wide-glyphs-96
contract:escape-incomplete-tag-colored     contract:render-wrap-long-40
contract:pager-engaged-real-less-piped     contract:render-wrap-long-96
contract:provider-column-multi-provider    contract:provider-column-single-provider
```

**Newline after the following message rather than after the warning (3):**

```
contract:fb-posix-class-bare-warning
contract:fb-posix-class-warning
contract:role-contradiction-warning
```

**Not attributed — the fixture built for this defect, not yet diffed (1):**

```
amendment:lowercase-z-rendered-dates
```

Frozen successors: 23 pattern rows plus 1 generated, same colour cause.
Age: all 7 — **read the warning above before calling them fixed.**


## Task and constraints

Own the red acceptance contract. Current Python behaviour is the oracle. **Edit
tests and fixtures only.** Constraints still binding: work in
`teammates/contract-owner/` and ask `search-firstmate` for promotion of anything
team-level; no `memo`, no `.optmem/`; no teammate commits; the corpus is frozen,
so amendments add cases and an *invalidating* finding goes to the first mate.

## State — hard facts

Last full run of the contract suite: **0 unintended failures, 259 of 259
intended reds.** The frozen-successor module: **88 of 88 green.**

Owned files:

| path | what it is |
| --- | --- |
| `tests/test_search_command_contract.py` | five proof classes, two timing gates, normalization guards |
| `tests/test_search_frozen_differentials.py` | the durable successors, 88 cases |
| `tests/test_tool_visibility_oracle.py` | the 7315-case table's three guards |
| `tests/oracle_digest.py` | **the canonical oracle-identity recipe, desk-wide** |
| `tests/conftest.py` | console reset, plus the two shared session fixtures |
| `tests/query_pattern_corpus.py` | `query-semantics`'s generator |
| `tests/lib.sh` | per-run shell fixture home |
| `tests/data/search-contract-fixtures/` | frozen corpus, 227 cases |
| `tests/data/search-amendment-fixtures/` | post-freeze pool, 32 cases |
| `tests/data/search-frozen-differentials/` | recorded Python answers, 88 cases |
| `tests/data/tool-visibility-oracle/` | 7315-case table, stamped |
| `teammates/contract-owner/work/` | seven tools; each one's *refusal* is listed in `RESUME.md` |

## What to do, in likely order of arrival

1. **The cutover.** When the search route flips to native, every gate stops being
   a formality at once. Nothing to prepare.
2. **Differential failures route here.** For each: reproduce standalone before
   believing it; print the differing bytes before reporting a cause; check
   `git status --short src/` and `.venv/bin/ch-legacy`'s mtime before calling it
   a defect. Three times a "flake" was a real finding, twice it was contention.
3. **Oracle events.** Run `work/rebless_oracle.py`. It replays every case in both
   corpora and the frozen set and re-blesses only if nothing moved. **Never
   re-derive expectations to quiet the guard.**
4. **Not done, small, mine if anyone's:** `reviewer-profiler`'s
   `frozen_reference.json` needs registering with the oracle guard so it
   re-blesses like the corpora. I did not do it because it lives on their desk
   and my tool writing there is the coupling I spent the day recording. It wants
   either moving under `tests/` first, or a declared-roots list they own.
5. **Unfunded, recorded as a visible choice:** the frozen pattern set's 78 rows
   collapse onto 18 distinct answers, because generated patterns mostly match
   everything or nothing against this corpus. Sound but weaker than the count
   suggests. `query_pattern_corpus.adversarial_haystacks` is the known fix; it is
   corpus work, not harness work.

## The dozen things that would be expensive to rediscover

All are in `contract.md` with evidence. These are the ones that change decisions:

**The no-Python proof is a filesystem proof, and both alternatives are measured
dead.** `exec` replaces the process image, so "did `ch` spawn a Python child"
sees nothing; macOS purges `DYLD_*` across that exec, so a loader trace reports
zero Python libraries for a route that is entirely Python.

**A shape defined relative to *now* cannot be a fixture; a shape at a fixed
calendar instant is exactly what a fixture is for.** Why the inherited corpus
rotted green-to-red in three days and this one does not.

**Isolation severs relationships; de-duplication creates them.** Five instances
of the first today, one of the second, all mine. Before moving or copying
anything, enumerate what it resolves relative to itself and what resolves
relative to it.

**A normalization that silently no-ops is invisible in exactly the same way as
one that is unnecessary.** Mine was, for a day, in seventeen files.

**Freeze the output, not the judgement about the output.** A gate storing bytes
cannot decay into a gate about *whether*; a gate storing a verdict can. "Does it
diverge" passes anything that diverges at all, by ninety characters or by nine.
This is the sharpest form of the conversion rule — `reviewer-profiler`'s, and the
reason their 42 frozen references stayed strong where an NFC probe went weak.

**Re-posing a question is free durability only when it is the same question.**
The test: *what answer does the re-posed question give if the new subject is
wrong?* If still "pass", the question got weaker.

**A table that re-derives its own answers is not a fixture**, and **a table that
needs its generator to be interpreted is a cache.**

**Stamp and re-verification fail differently.** The stamp answers *was this
generated against the current oracle*; re-verification answers *does it still
describe that oracle*. Any table where re-verification is possible gets both.

**"We have a differential for X" requires "through what?"** No new native code is
reachable from Python. The three available methods are a stored table, an
end-to-end CLI comparison, and an out-of-process harness. Do not widen the
bindings for testability.

**Today's green is not evidence about new code.** The byte lock *could not have
failed* on any of the new Rust modules, because none is reachable from the route
it measures.

**Three defects are deliberately absent from the corpus** — a hang, a crash on
`--short ²`, and a crash on a lowercase `z` timestamp. All under *"the surface no
golden can own"*. **Do not add fixtures for them.**

**A case count is not a coverage measure; distinct outcomes are.** The frozen
pattern set is 78 rows, 45 of them empty, collapsing onto 18 distinct answers —
and "78 cases" is what would have been quoted. It is still sound in both
directions, which is the distinction a reader needs: weaker than its count, not
vacuous. Worth asking of every large number on this desk; several are circulating
and nobody has counted distinct answers for any of them.

**Record from the oracle, not from the route that reaches it.** The frozen sets
were captured by running `ch-legacy` explicitly rather than `ch`. Today those
produce identical bytes, because `ch` execs its sibling — so it looks like a
distinction without a difference, and it is not. A record has to name what
produced it. After cutover, `ch` is the native route and a record captured
through it would be the port checking itself.

**Look at the data before writing the test that consumes it.** Both times a
conversion could have been silently weakened today, it was caught by opening the
recorded bytes, never by reasoning about the instrument's shape.

## Context to preserve

**The user is the Pi captain** and asks for one-line deltas shaped *completed
proof, active work, blocker, next gate*. They read as a cold entry: outcome
first, no internal shorthand, plain prose. **Report the harness's context figure,
not your own estimate** — standing roster rule after two teammates were wrong in
opposite directions by ten to fifteen points.

**Teammates.** `search-firstmate` is the leader. `reviewer-profiler`,
`session-core`, `query-semantics`, `context-curator`, `search-runtime` are peers,
desks at `teammates/<name>/`.

**The habit doing the most work here:** nobody quietly reconciles a discrepancy.
Two numbers that should agree and do not is always a question. That caught four
relay errors, two withdrawn measurements, and two wrong conclusions today.

**Commands.**

```sh
CARGO_TARGET_DIR=target/contract-suite cargo build --release --bin ch --no-default-features
uv run pytest tests/test_search_command_contract.py -q -rf
uv run pytest tests/test_search_frozen_differentials.py -q
uv run python .../work/rebless_oracle.py            # replay + re-bless; refuses on movement
uv run python .../work/calibrate_contract_harness.py # grades capture and comparator
```

The suite builds into `target/contract-suite`, never the shared `target/release`,
and needs no resource windows.

**Nothing is owed to anyone.** Both commissioned gates delivered, the table
placed and guarded, the three conversions done and registered.
