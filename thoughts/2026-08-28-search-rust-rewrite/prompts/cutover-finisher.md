# Role: cutover finisher

Read in this order:

1. `@thoughts/2026-08-28-search-rust-rewrite/charter.md`
2. `state.md` — **read the header first. The `L`-numbered section at the end is
   newer than everything above it**, and the most recent `L` on a subject is the
   current one.
3. `teammates/lexer-tables/RESUME.md` — the seat you continue in
   `session_render.rs`. It carries the tool surface, the rulings, and the two
   gaps left deliberately open.
4. `teammates/engine-and-codex/RESUME.md`, 456 lines — the arm, three verified
   hazards, and the `HOME` resolver.
5. `decision-record.md`, `preserve-because-wrong.md`,
   `timing-shaped-behaviours.md`.

Load `load-project-context`, `tdd`, `write-tests`, `ai-to-leader`,
`ai-to-delegated`.

## You are the critical path. Everything else in the mission waits on you.

`ch search` still runs on Python. **The cutover is four pieces of work away and
you own all four.** Two are already ruled and need building, not deciding.

**Tree at handoff: green, quiet, uncommitted, digest `ca874ce060f1`** — 234 lib
tests + 53 doctests, five build configurations, zero warnings. **Re-derive it
before you trust it; a report about tree state decays.**

## Exclusive ownership

**Yours:** `rust/session_render.rs`, `rust/main.rs`, `rust/search_run.rs`,
`rust/search_views.rs`, `probes/searchdriver`, and the vendored diff module you
create. **Nobody else edits these.**

**`rust/lib.rs` is shared** — one appended `mod` line each, you and
`parity-finisher`. **Announce before you append and check the file if they have
announced already.**

**Three false comments are in your surface and each goes with the fix it
describes:** `session_render.rs:3700` justifies refusing on a step budget Python
does not have; `search_run.rs:159-162` claims the panel sink panics on any lexed
fence and that nothing routes to `search_run`; `search_views.rs:1968`'s panic
message says *"until the lexer tables land"*. **The tables landed at L247.** **A
comment that is false is more dangerous than a test that cannot fail** — a weak
test at worst fails to catch something; a false comment directs the next change.

**Not yours:** `rust/session.rs`, `rust/python_io.rs`, `rust/raw_transcript.rs` —
`parity-finisher` holds them, in parallel, disjoint by file. **Do not touch them
and do not fix what you find there. Report it.** `tests/` and fixtures are
`contract-owner`'s.

## The four pieces, in order

### 1. The `Edit` diff — a ruling, not a question

**Vendor `difflib` 0.4.0 (MIT), about 500 lines, and correct the one inverted
operator:** CPython adds elements appearing in over 1% of positions to `bpopular`
and **deletes** them; the crate **keeps exactly those**. **`similar` agrees on
9.7% and is not a difflib reproduction — do not consider it.**

**Do not re-open this as a tradeoff.** It was escalated as fidelity against cost
and the measurement removed the tradeoff: cheaper than a 687-line hand port *and*
exact on 2,814 of 2,814 real Edit calls.

**⚠ The real corpus cannot grade the risky part.** Only 3 of those 2,814 reach 200
lines, so **a clean pass on real Edits proves almost nothing about autojunk.** The
second corpus — 900 pairs from real file bodies over 200 lines, where autojunk
changes CPython's own answer on 23.9% — is the one that matters: **published crate
28.0%, patched 99.67%.** Residue 3 of 900, mechanism unknown, none reachable from
real Edits.

**`tool-edit-diff` sits in `KNOWN_UNBUILT_BODIES`, an asserted exact set that
demands its own removal when this lands.** Any *other* case joining that set is a
regression, not a gap.

### 2. The `Read` line-number gutter — start with the question, not the code

**It has no failing case, deliberately.** Its two corpus cases pass for a reason
unrelated to the gutter: **a Claude `tool_result` carries no tool name**, so the
result resolves to `Tool`, and both routes fall through to the fenced body.

**Your first question is how the product resolves a result's tool name from its
paired use.** Answer that, then build the case, then build the gutter. **A
wrongly-shaped case is worse than a missing one** — the previous seat left it
missing on purpose rather than guess.

**Line numbers are unconditional geometry, not highlighting.** Over 2,497 real
`Read` calls with a path, 48.3% resolve to a promoted language, 40.3% to an
unported one and 11.4% to none — **markdown alone is 37%, the largest, and
deliberately outside the seven. Half the extension work delivering no colour is
the approved outcome, not a shortfall. Do not promote a language to fix it.**

### 3. The budget-exhaustion plain fallback — close the last panic route

`Unsupported("fence lexer budget")` at `session_render.rs:3700` is the **one
remaining route** to the sink's panic at `search_views.rs:1968`. **A fence that
exhausts the step budget renders plain, with complete geometry, and never
refuses.**

**The comment at that site is false and goes with the fix.** It justifies refusing
because Python's `re` has no step budget — reasoning written when refusing meant a
typed error, not a truncated scan.

**Two constraints.** The gate must **force** exhaustion: no real corpus reaches it
(a 147 KB pathological fence rendered fine), so shrink the budget in a test and
assert plain output and no panic. And **close the route structurally** — once no
producer of `Unsupported` remains on that path, the panic must be impossible by
construction, not merely unreached. **Removing the possibility beats guarding it.**

### 4. Land the arm

One `search` branch in `rust/main.rs`. **Diff against `probes/searchdriver` rather
than read it.**

**Three things nothing type-checks, all verified:** `&arguments[1..]` — `main.rs:34`
already sets the convention one line from where the arm goes; **two width
resolvers** — `argparse_columns()` for help and errors, `terminal_width()` for
`run`, and the hazard is a later "simplification" to one; **`eprint!` not
`eprintln!`** for warnings before the match, because the warning carries its own
newline.

**The `HOME` resolver is written and verified against the live legacy route.** It
sits in `probes/searchdriver` deliberately so it travels with the arm. **Do not
replace it with `home_dir()`:** `HOME=""` yields `/` in the product and the real
home from the convenience call.

## Definition of done, and the falsifiers

**Done:** all four landed; `KNOWN_UNBUILT_BODIES` empty of `tool-edit-diff`; the
`Read` gutter gated on a case that failed before it; the budget route structurally
closed; the arm landed; **`./tests/run_all.sh | cat` green**; both G4 gates green
including `g4-fence-covered-later`, which is now an **ordinary parity row that must
actually go green** and needs the launcher window — **ask `search-firstmate` to
route it to `contract-owner`, do not take that window yourself.**

**Every gate ships with an automated falsification** — a deliberately wrong
implementation, run as part of the gate, failing the build if the gate stops
catching it. **Name what each failure message must say.** **A mutation that catches
nothing is a question about your corpus, not a pass.**

**Ask of every corpus: what can it not say?** The body oracle was green because
`flags_from` handled only `show_thinking`, so **no case could ever have set
`show_tools`** — not a thin corpus, an incapable one. Three corpora agreed for the
wrong reason this week.

## Practicalities

Direct shared checkout. **Announce a knowingly red tree before it lands, not after
it compiles** — a red tree costs whoever is measuring. **Five build
configurations, not three**, including `cargo test --doc`, the only one that
compiles doctests.

Write only inside `teammates/cutover-finisher/`; ask `search-firstmate` to
promote. **Promoted documents are symlinks**, so a correction after promotion is
live. **Keep `RESUME.md` current as you work, and re-read it whole before you
stop** — patched section by section it drifts like a stale copy, and that has
happened to four briefs on this mission.

**Report the harness's context figure and name which quantity it is.** This harness
emits two — a session token budget and a context-window percentage — which have
differed seventeen-fold. **The context window binds.** If the harness has not
volunteered one, say *no current reading* with the last value and its age. **Never
derive one.**

**To message anyone, run `ListAgents` and copy the row exactly.** Most sessions
carry a `[08-28][chats][t:6a91] ` prefix and bare names fail. **A failed send looks
like a lost seat and is not.**

Do not run `memo` or write under `.optmem/`. **There is no escalation above the
first mate.**
