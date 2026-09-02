# search-runtime — resume state

## If you are taking the cutover, read this first

**Everything you need is the section "The cutover, as a recipe someone else can
follow". It is rehearsed three times against a moving tree, and every rehearsal
found something reading had not.** Do not skip to the code.

Three things in it that nothing type-checks and no test catches until after the
branch lands:

1. **`&arguments[1..]`, not `&arguments`.** `main.rs` has already matched the
   `search` token. Two skips, not one. Both are `&[OsString]`, so passing the
   whole slice compiles and makes `search` the search pattern.
2. **`terminal_width()` for the `Run` arm, `argparse_columns()` for help and
   error.** Two different rules that disagree on `+96` and `' 96'`. Everything
   the search renders is Rich-rendered; everything argparse emits is not.
3. **Warnings print before the match, with `eprint!`** — they carry their own
   newline.

`probes/searchdriver/src/main.rs` is the same three arms as a standalone binary
and is near-verbatim. **Diff against it rather than reading it** — that is what
caught the off-by-one, on a pass whose stated purpose was checking something
else.

Verification after landing is **G5's runbook**, which `reviewer-profiler` wrote;
seven of its fifteen checks are the ones blocked on the cutover. It is not a
separate job to arrange.

**Nothing of mine is half-done.** No production edit is in flight.

## Right now

**No first mate.** The seat was handed to a successor who is gone from the
roster; the original is past 90%. Until someone holds it, coordination is direct:
I own the G4 cutover, `engine-and-codex` owns the critical path (confirmation and
the plain sinks), `views-and-colour` owns the coloured sink. `state.md`,
`decision-record.md` and the handoffs are the mission record.

**Every part of the `Run` arm that is mine is done**: items 1–3 in
`rust/search/plan.rs`, item 6 in `rust/search.rs`. The cutover waits only on
item 4 (confirmation, `engine-and-codex`, in flight) and item 5 (the two sinks).

Standing commitment: the moment those work, I drop everything and land the
cutover. It is one branch in `main.rs`, proved on my side, and the only thing in
the mission with no second owner.

Views went to `views-and-colour`, a new owner, with `views-handoff.md` as their
starting point. I declined it as an implementation package: my context is well
past two-thirds, and taking the largest remaining package while holding the
irreplaceable small one inverts the priority.

Deliberately **not** started: anything I cannot finish. That judgment produced
the handoff instead of a half-built module.


Tree green: 139 lib tests, 1 bin, 41 doctests, release build in the shipping
configuration.

Provenance for anything quoted here: HEAD `8cb4c5f`, oracle route digest
`sha256:dd6ab701e9b8450e…` via `tests/oracle_digest.py::oracle_route_digest()`.
An earlier working-diff hash was withdrawn — it could not see a `uv sync`
replacing the installed entry script, which is the failure stamps exist for.

## The cutover, as a recipe someone else can follow

Written because the cutover has one owner. Not code: a `search` branch that
handles only part of the route is the intermediate hybrid the charter forbids,
so this lands whole or not at all.

### The branch

`rust/main.rs::main` currently routes `parse` natively and sends everything else
to `run_legacy`. Add one arm before that fallthrough:

```
if arguments.first().is_some_and(|a| a == "search") {
    return run_search(&arguments[1..]);
}
```

### `run_search`, three arms

`search::parse::parse_search_arguments(&arguments) -> ParsedSearch`, then match
`.outcome`:

| Arm | Do | Exit |
| --- | --- | --- |
| `Help` | `print!("{}", search::render_help(terminal::argparse_columns()))` | 0 |
| `Error(msg)` | `eprint!("{}", search::render_error(&msg, terminal::argparse_columns()))` | 2 |
| `Run(args)` | compose the scan, below | `Outcome::exit_status()` |

Print `parsed.warnings` to stderr before the `Run` arm — the role-visibility
warnings, which argparse emits before the search runs.

**Use `argparse_columns()`, not `terminal_width()`.** They are different rules
and disagree on `+96` and `' 96'`. Anything argparse emits uses the first.

### Diffed against `probes/searchdriver` — three things it pins that prose did not

Rehearsed by diffing rather than reasoning. The driver is the same three arms as
a standalone binary, so it differs from my arm in exactly one way and agrees
everywhere else.

**1. The argument slice is off by one, and getting it wrong shifts every
argument.** The driver is its own binary, so it parses `args_os().skip(1)`
entire. My arm sits after `main.rs` has already matched the `search` token, so it
must parse **`&arguments[1..]`** — where `arguments` is itself already
`args_os().skip(1)`. Two skips, not one. Nothing type-checks this: passing the
whole slice makes `search` the pattern and every real argument a positional.

**2. Warnings print before the match, not just before `Run`**, and with
`eprint!` rather than `eprintln!` — they carry their own newline. My earlier
wording said "before the `Run` arm", which would drop them on any outcome that
carries one.

```rust
for warning in &parsed.warnings {
    eprint!("{warning}");
}
```

**3. `home` is `std::env::var("HOME")`,** not `dirs`, not a cached constant. The
driver uses `.expect("HOME")`; in `main.rs` that is a panic on a missing
variable, so decide there rather than copying it. Python reaches the same place
through `Path.home()`.

Everything else matches the recipe as written, including the width split:
`argparse_columns()` for both text arms, `terminal_width()` for `run`.

### The `Run` arm — one call

`search_run::run(&args, home, width) -> i32` wraps the whole scan. My earlier
sketch composed `stream_search` by hand; that is now inside `run`, which already
calls `plan::scan_order`, `plan::lazy_screen`, `plan::probe`,
`render_no_results_hint` and `SearchPoolFilter::is_empty`. Nothing to re-derive.

```
let status = search_run::run(&args, home, terminal::terminal_width());
ExitCode::from(status as u8)
```

**The width argument is the one thing this arm decides, and it has no caller to
copy from — `search_run::run` has none until this branch exists.** Three sources
are in scope and only one is right here:

| Source | Rule | Use for |
| --- | --- | --- |
| `terminal::terminal_width()` | Rich's — `str.isdigit()`, then `ioctl` | **the `Run` arm** |
| `terminal::argparse_columns()` | argparse's — `shutil`, so Python `int()` | help and error text |
| anything else | — | never |

Passing `argparse_columns()` here, or a constant, or a fresh `ioctl`, compiles
and looks right. Everything the search renders is Rich-rendered, so it must be
Rich's rule. Nothing goes red until runbook check 7, after the cutover.

`engine-and-codex` built the three arms standalone at
`teammates/engine-and-codex/probes/searchdriver/src/main.rs` — it is nearly
copy-verbatim, and it uses `argparse_columns()` for help and error and
`terminal_width()` for `run`, which is the split above.

### Why `Confirmation` takes a directory rather than a filter (closed)

`search_confirm::Confirmation` holds a `filter: &PoolFilter` — the **eager**
type, whose constructor parses both dates and returns `Err` on a bad one. It
uses that filter for exactly one thing: `passes_cwd` at `search_confirm.rs:225`.
It never reads a date.

**Closed structurally rather than by instruction.** `Confirmation::new` now
takes `arguments.pool_filter.directory.clone()` — a directory, not a filter — so
no date can reach it and the wrong call cannot be written. That is better than
the documented rule I proposed.

Kept because it explains the API's shape. Had it taken a `PoolFilter`, passing
the date strings would have compiled, read naturally, and **silently reinstated
the fast failure that gap 2 exists to prevent**: `-ma notadate` would
error once at construction instead of once per candidate file. That is a
divergence `state.md` rules against, and nothing would catch it — the eager and
lazy paths agree on every *valid* date, which is exactly what the drift test in
`plan.rs` pins.

The dates belong to `plan::lazy_screen`, which parses them per path. This is the
same value reaching two code paths that disagree about when it is resolved.

### Verify in this order

Steps 1–4 are checkable **now** and I have run them. Steps 5–7 need the branch
to exist and are unrun — say so rather than assuming.

1. **Checked.** All three arms exist and are byte-proved against `ch-legacy`:
   help at twelve widths, whole-stderr error rendering at four, both hint forms.
2. **Checked.** `argparse_columns` and `terminal_width` exist and a test asserts
   they disagree, so the wrong one cannot be swapped in silently.
3. **Checked.** `plan::{scan_order, screen, probe}` match `stream_search`'s
   parameter shapes; `Outcome::{exit_status, wants_no_results_hint}` exist.
4. **Checked.** `search` currently falls through to `run_legacy`, so the branch
   is purely additive and reverting is deleting it.
5. **Unrun.** The full suite, then the shell suite, against a rebuilt binary.
6. **Unrun.** The differential: `ch-legacy search ARGS` against `ch search ARGS`
   over the corpus, `CH_NOW` pinned, under a pty at two widths neither of them 80.
7. **Unrun — the no-Python proof.** Remove `ch-legacy` from the launcher
   directory; `ch search` must still answer. This is the mission's bottom line
   and it cannot be checked before the branch lands.


## Uncommitted production edits (mine)

| File | State |
| --- | --- |
| `rust/terminal.rs` | new — width + colour-system resolution. Done, proved. |
| `rust/clock.rs` | new — `CH_NOW` seam, native half. Done, proved. |
| `rust/inventory.rs` | new — lifted. Done, proved. |
| `rust/scanner.rs` | new — lifted. Done, proved. |
| `rust/python_extension.rs` | rewritten 1399 → 301, wrappers only. Done. |
| `rust/lib.rs` | declares clock, inventory, scanner, terminal. |
| `rust/main.rs` | consumes `terminal::terminal_width`. |
| `src/chats/commands/search.py` | `CH_NOW` seam only, under the granted exception. |

Other untracked `rust/*.rs` files belong to session-core and query-semantics.
Nothing is committed; the first mate makes checkpoints.

## Done and accepted

**A3 — `rust/terminal.rs`.** Width resolved as Rich does (every Unicode decimal
digit accepted, leading `+` rejected) and the full colour-system decision.
Proved against a 12,096-row table generated from Rich itself, zero differences
(`probes/color-oracle.tsv`). Red-checked: a naive `forced || isatty` fails
exactly two tests.

**Clock seam.** `CH_NOW`, format `%Y-%m-%dT%H:%M:%S` pinned on both sides.
Three proofs: byte-identical to the `8cb4c5f` oracle when unset; four values give
four outputs; wiring it wrong collapses them to one.

**B1 — complete and accepted.** `inventory.rs` and `scanner.rs` lifted out of the
PyO3-only file. Falsifier held: scanner has exactly one substantive diff line
(the de-PyO3'd `evidence_groups` signature), inventory is pure addition after the
moved region. One shared backward line-walk primitive, **trim in the handler, not
the walk** — the branch's fork does not exist here. `validate_chunk_encoding` not
taken, as ruled. Full Python suite green against the rebuilt extension, which is
what exercises all seven wrapper functions through the new modules.

## Grammar — complete, both halves

`rust/search.rs` (usage and help formatting), `rust/search/wrap.rs` (a `textwrap`
port), `rust/search/parse.rs` (argv parsing). Written by `query-semantics` while
I was down, handed back, then reconciled by me onto the landed types.

Four permanent gates, all comparing live against `ch-legacy`:

- help byte-identical at twelve widths, including the narrow overflow at 27 and
  the boundaries either side of the longest line;
- a test proving that gate is not inert — a width-pinned formatter must disagree
  at every other width;
- every grammar-decidable argv case agreeing on the accept/reject decision *and*
  the exact error bytes;
- a regression for the lone-dash bug.

**Reconciliations that mattered**, all removing parallel authorities: the
branch's own `parse_tool_spec` took a `global_short` parameter Python does not
have, so it and two helpers were deleted in favour of session-core's, which is
proved over 2006 generated specs; its short-policy resolver now delegates;
`ToolVisibility::Hidden`/`Filtered` mapped onto `All(bool)`/`Filters(..)`.

**The bug the oracle found and reading would not have:** `ch search -`. argparse
treats a lone `-` as a positional by the stdin convention, so it is the pattern.
The ported parser rejected it as an unknown option and exited 2.

**Why the recorded table is the only instrument here.** Nothing in the new native
surface is reachable from Python, so there is no in-process differential for any
of it — end-to-end comparison through the CLI is the whole toolbox. The oracle is
stamped at `probes/grammar-oracle.provenance.json`; re-capture if `src/chats`
moves.

**Rendering is done too.** `render_help(columns)` and `render_error(message,
columns)` produce the exact bytes argparse writes, proved against live
`ch-legacy` on **whole streams** at four widths — not just the message, because
a wrong width rule would still produce the right message inside a wrong usage
block.

**Two width resolvers now exist and must stay separate.**
`terminal::terminal_width` is Rich's rule (`str.isdigit()`);
`terminal::argparse_columns` is argparse's (`shutil`, so Python `int()`, which
accepts `+96`, ` 96`, `9_6` and Unicode digits, and measures **stdout only**).
A test asserts they *disagree* on `+96` and `' 96'`, so unifying them fails with
an explanation rather than silently breaking one surface.

**Next: `main.rs` routing, then G4 — blocked, and by more than I first wrote.**

The two grammar arms are done and proved:

```
parse_search_arguments  ->  Help  : print render_help(argparse_columns()), exit 0
                            Error : eprint render_error(msg, argparse_columns()), exit 2
                            Run   : ...see below
```

**Correction, made after `search_engine.rs` landed.** I previously wrote that the
`Run` arm was "the engine" and the cutover was a short function. That was wrong,
and I am fixing it here rather than leaving a future reader to discover it.

`search_engine` exposes `stream_search<S: HitSink>(scan_order, sink, batch_size,
screen, probe, confirm) -> Outcome`. It is the **scheduler** — ordering,
batching, the window-flush-on-error rule, early close — and nothing else. There
is no `run(SearchArguments) -> ExitCode`; the only `ExitCode` in the crate is in
`main.rs`.

So the `Run` arm still needs, none of which is landed:

1. `scan_order` — pool discovery, provider partition, newest-first by stat mtime.
2. `screen` — the per-path date and directory filters.
3. `probe` — the batched candidate gate over a window.
4. **`confirm`** — parse the session, render messages, evaluate the query. This
   is "the engine's confirmation half", which the first mate has listed as
   **unowned**.
5. A `HitSink` — `emit`, `closed`, `emit_error` — across all five output modes,
   routing through `pager::Pager` when paging.
6. `Outcome` mapped to exit status: 0 hits, 1 no hits *and* 1 empty pool, with
   the no-hit hint suppressed under `--only-id`.

**Items 1–3 are done.** `rust/search/plan.rs`, 139 lines, four tests, green.
`scan_order(pool, provider)`, `screen(&filter) -> impl FnMut(&Path) -> Gated`,
and `probe(needle, is_pi_session) -> impl FnMut(&[PathBuf]) -> Vec<bool>`. It is
assembly over landed machinery and owns no logic of its own. One addition it
needed: `inventory::cwd_from_path`, a streaming cwd probe, because the `-d`
filter runs in the *path* stage and must not decode a whole session.

One thing deliberately undecided there: `screen` returns only `Survives` and
`Rejected`, never `Failed`. Python's path-stage probes swallow `OSError` and
return `None`, so the filter rejects rather than raises, and the per-file error
text comes from the later read. If a path-stage failure must surface as
`Gated::Failed`, `engine-and-codex` will say so — better an unused arm than an
invented case.

**Item 4** is `engine-and-codex`'s, in progress.

**Item 5 is not one package**, which is why it looked wrong to take. It splits
along the seam that already exists: the **coloured** sink — panels, list rows,
highlight painting — is `views-and-colour`'s, and the **plain** modes are
`engine-and-codex`'s, inside their step 4 with `--raw` as the one that buffers.
Neither half is search-runtime's.

**Item 6 is done.** `Outcome::exit_status()` and `wants_no_results_hint()`
already existed in `search_engine`; what was missing was the hint itself.
`search::render_no_results_hint(pattern, filter_is_empty, output_mode)` in
`rust/search.rs`, four tests against the recorded oracle bytes.

Two traps in it, both one-liners to get wrong: the suffix appears when the
filter is **not** empty, so the parameter is the filter's emptiness rather than
"a filter is active"; and an empty pool prints nothing while still exiting 1,
which is why `wants_no_results_hint` is false for `EmptyPool`.

So the whole `Run` arm is mine-complete: items 1–3 in `search/plan.rs`, item 6
here. Only items 4 and 5 — confirmation and the two sinks — stand between the
tree and the cutover.

**The cutover is still mine and still one branch in `main.rs`. It is just not
close**, and anyone planning around "short function when the engine arrives"
should read the six items above first.

## Settled questions — do not re-open these

Each was decided by measurement. They are here so a successor does not spend a
day re-deriving them, and does not "helpfully" undo one.

**1. Do NOT take `risk_character_pattern()`. Measured, and it loses.** I
benchmarked it before adopting it. Over a 128 KiB realistic non-ASCII chunk,
200 iterations, three rounds:

```
binary_search (current main)  18.4–18.9 ms
regex (branch's version)      39.3–40.6 ms
```

**The branch's "optimization" is ~2.1× slower.** The current code short-circuits
on `is_ascii()` and only binary-searches 20 entries for non-ASCII characters;
the regex must scan every byte. It was on the B1 task list as "take it on its
merits" — it has none. Recorded so nobody re-litigates it. This was the last
open B1 item and it closes as a rejection.

**2. Pager — landed as `rust/pager.rs`.** It could not be a "move": neither
`search_views.rs` nor `search_engine.rs` exists in the tree, so there was no
source and no destination. Standing it alone in the engine's dependency position
enforces the seam structurally — the views never see it, and `closed()` is a
method rather than a public field, so early close stays scan control. Ported
from `chats.console.StreamingPager`, not the branch. One recorded divergence:
the branch flushes stdout in the no-`less` fallback and Python does not; Python
won. Three tests, green.

**3. Everything downstream is blocked on session-core.** Traced against what
exists, not against the branch's module structure:

| Module | Needs | Status |
| --- | --- | --- |
| `search.rs` (grammar, mine) | `ConversationFlags`, `MessageSelection`, 3 short-spec helpers | not landed |
| `search_engine.rs` | `search`, `session` | both missing |
| `search_views.rs` | `session_render` | not landed |

Session-core has landed `ShortPolicy`, `ToolDirection`, `ToolFilter` and
`ToolVisibility`, so the leaf types are mostly there. The two visibility types
are the gate. The first mate has made them session-core's top priority.

**4. Handoff written and promoted:** `engine-and-views-handoff.md`, for
`query-semantics` arriving cold at the engine. Its section "The one property no
byte oracle can see" is the highest-risk item in it: every streamed session id is
flushed individually at `commands/search.py:350`, worth 15.995 s → 0.38 s to
first id with completion time unchanged. Buffering them is byte-identical and
costs 15.6 seconds of visible latency. Only a timing assertion can fail on it.

## Do not lose these

- **Behaviours that must stay wrong** (map §17): the age label and its colour
  disagree by one bucket *by design*; `collapse_home` matches a string prefix,
  not a path boundary. In both cases the correct implementation is the natural
  one, which is what makes them dangerous. The age one has no gate on either side
  of the comparator.
- **The `.isascii()` guard is correctness, not performance** (map §15).
  `literal_candidate` uses `casefold` while matching uses `re.IGNORECASE`; for
  `ß` they disagree. Relaxing the guard silently loses search results.
- **Three build configurations, not two.** `cargo check --no-default-features`
  green does not imply `cargo test` green — check skips test targets. The binary
  is the `--no-default-features` build and it is the one with no ambient feedback.
- **Validate in a private `CARGO_TARGET_DIR`.** `target/release/` is contended,
  and `uv tool install --force` deletes the existing install *before* building
  the replacement.

## Open, not mine

- The 1.29× memory gap: its own task, waiting on an allocation profile. My
  earlier `read_to_string` flag was off-path — `resolution_facets` is called from
  `session.rs`, never from search.
- `uv build --wheel` isolates cargo but still writes setuptools' shared `build/`.
- `rust/shortening.rs — truncate_middle` doctest is red; session-core's.
