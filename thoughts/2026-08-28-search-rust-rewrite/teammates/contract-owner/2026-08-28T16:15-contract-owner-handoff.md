# Handoff — contract-owner

Written at 76% window with nothing in flight, on the first mate's instruction to
write it with room rather than at the threshold.

**Situation.** The red acceptance contract for the public `ch search` journey is
built, accepted and green. Both commissioned timing gates are in. Nothing is
blocked. What remains is a role rather than a task list: as the port lands, I am
the terminus every differential failure routes through.

**Background you need before anything else.** Read these three, in order. They
are the last common ground, and this document is only the layer on top.

- `thoughts/2026-08-28-search-rust-rewrite/charter.md` — the mission.
- `thoughts/2026-08-28-search-rust-rewrite/prompts/contract-owner.md` — the role.
- `thoughts/2026-08-28-search-rust-rewrite/teammates/contract-owner/contract.md` —
  **the deliverable, and the single most important thing to read.** Everything
  below assumes it.

Also `RESUME.md` beside this file: shorter, operational, kept current while
working. If the two ever disagree, `contract.md` is the reasoned record and
`RESUME.md` is the state.

---

## 1. Task

Own the red acceptance contract for the complete public `ch search` journey.
Current Python behaviour is the oracle. Edit tests and fixtures only — never
production source.

Success: proof that goes red-to-green exactly when the Rust authority arrives and
for no other reason, plus a parity net that cannot rot.

Constraints given during the session, all still binding:

- Only `search-firstmate` writes team-level files. I work in `teammates/contract-owner/`
  and ask for promotion.
- Do not run `memo` or touch `.optmem/`.
- No teammate commits. The first mate makes checkpoint commits.
- The corpus is frozen. Amendments add cases; a finding that *invalidates* the
  corpus goes to the first mate.

## 2. Prior state at session start

`ch` is a Rust binary that natively serves only `ch parse` and `exec`s a private
`ch-legacy` sibling for everything else. `ch search` was, and at the time of
writing still is, entirely Python. Ten new Rust modules have landed but **none is
on the search path yet.**

## 3. Current state — hard facts

Last full run: **0 unintended failures, 259 of 259 intended reds.**

Files I own and created or changed:

- `tests/test_search_command_contract.py` — five proof classes plus two timing
  gates and the normalization guards.
- `tests/data/search-contract-fixtures/` — the frozen corpus, 227 cases.
- `tests/data/search-amendment-fixtures/` — 32 post-freeze cases, own pool.
- `tests/data/tool-visibility-oracle/` — 7315-case table, stamped and guarded.
- `tests/test_tool_visibility_oracle.py` — the table's three guards.
- `tests/oracle_digest.py` — **the canonical oracle-identity recipe.** The first
  mate has ruled this the only recipe desk-wide.
- `tests/conftest.py` — resets cached `Console` singletons per test.
- `tests/query_pattern_corpus.py` — `query-semantics`'s generator, landed here.
- `tests/lib.sh` — per-run fixture home, so concurrent shell suites stop deleting
  each other's fixtures.
- `teammates/contract-owner/work/` — six tools. Each one's *refusal* is
  documented in `RESUME.md`, which is the column worth reading first.

## 4. Discoveries that would be expensive to rediscover

All are in `contract.md` with evidence. The five that change what you would do:

**The no-Python proof is a filesystem proof and both alternatives are measured
dead.** `exec` replaces the process image, so "did `ch` spawn a Python child"
sees nothing; macOS purges `DYLD_*` across that exec, so a loader trace reports
zero Python libraries for a route that is entirely Python. Only the absence of
the `ch-legacy` file can fail.

**A shape defined relative to *now* cannot be a fixture; a shape at a fixed
calendar instant is exactly what a fixture is for.** This is why the inherited
corpus rotted green-to-red in three days and mine does not.

**Isolation severs relationships; de-duplication creates them.** Four instances
of the first, one of the second, all mine, all in one day. Before copying an
artifact somewhere private, enumerate what it resolves relative to itself.

**A normalization that silently no-ops is invisible in exactly the same way as
one that is unnecessary.** Mine was, for a day, in seventeen files. Guarded now.

**Today's green is not evidence about new code.** The byte lock *could not have
failed* on any of the ten new Rust modules, because none is reachable from the
route it measures. Do not read a long run of green as verification.

Two defects are deliberately absent from the corpus because the oracle produces
no usable answer, plus one crash — all three under *"the surface no golden can
own"* in `contract.md`. **Do not add fixtures for them.**

## 5. Next steps

There is no queue. In likely order of arrival:

1. **When the search route flips to native, every gate stops being a formality.**
   That is the moment the suite starts meaning something and the moment failures
   start arriving. Nothing to prepare.
2. **Differential failures route to me.** For each: reproduce standalone before
   believing it, print the differing bytes before reporting a cause, and check
   `git status --short src/` and `.venv/bin/ch-legacy`'s mtime before treating it
   as a defect. Three times a "flake" was a real finding and twice it was
   contention.
3. **Oracle events.** Run `work/rebless_oracle.py`. It replays every case and
   re-blesses only if nothing moved. **Never re-derive expectations to quiet the
   guard** — that is how a parity net becomes a mirror.
4. **Before the Python search implementation is deleted — three conversions.**
   This is a scheduled obligation, not a maybe. Three instruments compare two
   live routes with nothing stored, so they become unrunnable the day the oracle
   goes: the named-defect patterns, the generated patterns, and the pty colour
   differential. Freeze each into stored bytes first. Under an hour for all three
   while Python is alive; impossible after. Full audit in `RESUME.md`
   §"Before the Python search implementation is deleted".
5. **If asked to audit other teams' table oracles**: the pattern is in
   `contract.md` §"Table oracles need both halves of the guard". The owners can
   apply it faster than you can reverse-engineer it.

Open, not blocking: whether artifacts stamped with the withdrawn working-diff
digest `a99c3302d0f852ba` were re-verified before restamping, or only restamped.
A weak stamp cannot support the claim that nothing moved before it.

## 6. Context to preserve

**The user is the Pi captain and asks for one-line deltas** in the shape
*completed proof, active work, blocker, next gate*. They read summaries as a cold
entry. Lead with outcome, drop internal shorthand, plain prose.

**Teammates.** `search-firstmate` is my leader. `reviewer-profiler`, `session-core`,
`query-semantics`, `context-curator`, `search-runtime` are peers. Their desks are
`teammates/<name>/`. Reference those rather than re-deriving their scopes.

**The habit that caught four relay errors today**: nobody quietly reconciles a
discrepancy. Two numbers that should agree and do not is always a question, never
an adjustment.

**Working commands.**

```sh
CARGO_TARGET_DIR=target/contract-suite cargo build --release --bin ch --no-default-features
uv run pytest tests/test_search_command_contract.py -q -rf
uv run python .../work/rebless_oracle.py          # replay + re-bless, refuses on movement
uv run python .../work/calibrate_contract_harness.py   # grades capture and comparator
```

The suite builds into `target/contract-suite`, never the shared `target/release`.
It needs no resource windows.

**Read at session start, if you want the same baseline:** `AGENTS.md`,
`SHORT_SPEC.md`, `TOOL_SPEC.md`, `rust/main.rs`, `src/chats/cli.py`,
`src/chats/commands/search.py`, `src/chats/search_query.py`, `tests/run_all.sh`,
`tests/lib.sh`.

**Promise outstanding to the first mate:** none. Both commissioned items are
delivered. The last thing I owed was this document.
