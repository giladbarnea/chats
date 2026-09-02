# Handoff: the search engine's confirmation half

For whoever wires `ch search`'s scan loop to real files. Written for a competent
reader arriving cold; nothing here assumes you followed my working thread.

Provenance: oracle is `src/chats/commands/search.py` at `8cb4c5f`, unchanged in
the parts this describes. Everything marked *proved* was measured, not read.

---

## 1. What you are taking

`ch search` today is Python. The mission is to make the route native and cut over
once. The engine's job: scan the session pool newest-first, reject files cheaply,
confirm survivors by actually reading them, stream hits as they are found, and
exit with the right status.

**The scan half is built and proved. You are taking the confirmation half.**

Built, in the tree, uncommitted:

| module | state |
| --- | --- |
| `rust/pool_filter.rs` | proved — date and directory filtering, 36/36 against CPython, 5 mutations caught |
| `rust/session_pool.rs` | proved — discovery, provider partition, newest-first order, 0 of 5,036 positions differ |
| `rust/search_engine.rs` | proved — the streaming loop, 8 tests, 6 mutations caught |

---

## 2. The seam you are filling

`stream_search` takes two closures and nothing else touches the filesystem:

```rust
pub fn stream_search<S: HitSink>(
    scan_order: &[PathBuf],
    sink: &mut S,
    gate: impl FnMut(&[PathBuf]) -> Vec<Gated>,
    confirm: impl FnMut(&Path) -> Confirmed,
) -> Outcome
```

**`gate`** decides a whole 256-file window cheaply. It must return **one verdict
per input path, positionally** — the loop asserts the count, because a
length mismatch would silently misalign every decision in the window. Build it
from `scanner::files_contain_ascii_json_strings_impl` for the batch literal path,
plus `pool_filter`'s `passes_path_for_date` and the directory predicate.

**`confirm`** reads one survivor and decides it for real: `session::parse_claude`
for messages, `codecs::render_message_inner_xml` to render each, then evaluate the
query against the three search sources in section 4.

**`HitSink`** is where hits go and how the engine learns the reader stopped.
`rust/pager.rs` is the production implementation; `closed()` is a method, not a
field, so nothing outside can set it.

---

## 3. The error-buffering trap — read this before you write the gate

**The existing handoff's wording led me to build this wrong, and it will lead you
the same way.** It says "a mid-window filter error must flush the accumulated
window before it prints". I read that as *confirmation* errors and wrote the loop
to hold them and release them on the next hit.

That buffering was **inert**. Confirmation is serial and in scan order, so holding
a confirmation error and emitting it immediately produce identical output. I only
found out because a deliberate mutation removing the buffering survived every test —
there was nothing for a test to catch.

**The real hazard is a gate failure.** The gate runs over the entire window before
anything is confirmed, so a failure on a late file is already known while earlier
files are still unread. Emitting it when it is discovered puts it above hits that
precede it in scan order.

So the rule is: **every outcome prints at its own scan position.** A gate failure
lands after the hits that precede it and before the hits that follow, which is what
Python reaches by flushing the accumulated window and only then printing.

**Corrected by `engine-and-codex` against the live oracle.** My first fix held gate
failures until the *end of the window*. That is wrong, and my test could not tell:
it placed the failure at the last position, where holding and positional emission
agree. Their repro — a six-file pool with a directory in the middle — shows Python
emitting `f1, f2, error, f3, f4, f5` where the held version gives the error last.

The correction *removes* code. Because confirmation is already serial and in scan
order, emitting in position order **is** Python's order, so no buffering is needed at
all. Both directions are now pinned, and the `gate_failures_held_to_end` mutation is
caught.

This is why `Gated` is a three-way enum — `Survives`, `Rejected`, `Failed(String)` —
rather than a bool. A bool cannot express "the gate itself failed", which is the
only thing the ordering rule is about. If you find yourself simplifying it back to
a bool, you have removed the mechanism the rule protects.

Pinned by `a_gate_failure_prints_at_its_own_scan_position` (the direction that
distinguishes the two rules) and `a_gate_failure_never_overtakes_an_earlier_hit`
(the failure-last case both rules agree on, kept so the first test cannot simply be
inverted). Falsified by the `gate_failures_held_to_end` mutation.

---

## 4. Engine facts you cannot infer from the code

- **Search truth is three sources, not one.** A term matches a session if it matches
  any summary, **or** the current custom title, **or** any rendered message.
  Evaluation is session-wide, so `AND` terms may match in different messages.
- **Displayed matches are the union over positive terms.** `NOT` contributes none —
  `Query::iter_terms` returns empty for a `Not` node, deliberately. Getting this
  wrong paints highlights on excluded terms and counts them as matches.
- **An invalid regex is not an error.** `compile_search_term` catches the compile
  failure and recompiles the escaped literal, so a bad pattern becomes a literal
  search. Only a malformed *boolean* query raises and exits 2.
- **`Regex::search` returns `Result<bool, StepBudgetExceeded>`.** The error arm means
  the pattern was too expensive to decide. Surface it as a non-zero exit with its
  `Display` message. **Never swallow it into "no match"** — that is the confident
  wrong answer the guard exists to prevent.
- **`--raw` is the one mode that must buffer.** A single session with exactly one
  visible message prints the bare body; anything else gets `Session <id>` headers
  joined by `\n\n---\n\n`. Every other mode streams per hit.
- **Per-file error text is Python's**, including the `[Errno N]` prefix and the
  repr-quoted path: `[Errno 21] Is a directory: '…'`.
- **Exit statuses**: 2 for a grammar or malformed-boolean error, 1 for no hits *and*
  for an empty candidate pool, 0 otherwise. An empty pool exits 1 **silently**; a
  no-hit search prints a hint unless `--only-id`. `Outcome::wants_no_results_hint`
  already encodes the distinction.
- **The provider-column predicate reads discovery rows, not gate survivors.**
  `SessionPool::candidate_files` gives you the discovery-order partition.

## 5. Take these as given — do not re-derive them

`SearchArguments` arrives from the grammar carrying a resolved `ConversationFlags`
and `ToolVisibility`. Two behaviours in that resolution are invisible from the argv
and wrong on purpose:

- **`metadata_color` does not follow `color`.** A bool `color=true` resolves colour
  *off* and metadata colour *on*, because Python compares against the strings
  `"always"` and `"auto"` and a bool matches neither.
- **`ToolVisibility::Filters(vec![])` is falsy.** An empty filter list does not mean
  "all".

An engine that re-derives either will look correct and diverge.

## 6. The `.isascii()` invariant, which is correctness not performance

`literal_candidate` uses full case folding while matching uses `re.IGNORECASE`, and
they genuinely disagree: for `ß` the candidate is `ss` while the compiled regex does
not match `ss`. ASCII is the only region where the two models coincide, and the
`.isascii()` guard on every byte-gate path is what keeps them apart. Widening the
gates to non-ASCII as an optimisation buys **silent loss of a user's search result**,
which is the asymmetric direction.

---

## 7. What is already proved, so you need not re-prove it

- Date filter parsing: 36/36 against CPython, 5 mutations caught
  (`harness/date_filter_gate.md`).
- Pool ordering: 0 of 5,036 positions differ, both sidechain modes
  (`harness/pool_order_gate.md`).
- Scan loop: early close mid-window and between windows, scan order across window
  boundaries, gate-failure position in both directions, empty-pool distinctness.
  8 tests, 6 mutations caught.
- The query layer beneath you: 0 divergences over 4,000 generated patterns, the
  boolean grammar exact across 73 queries, spans identical under folding stress.

## 8. How to prove your half

- **`ch-legacy search ARGS` and `ch search ARGS` diff on the same corpus** — Python
  is deliberately still alive. That differential is the oracle.
- **Pin the clock with `CH_NOW`** (`%Y-%m-%dT%H:%M:%S`) or every age-bearing diff is
  meaningless.
- **The corpus mutates while you measure it.** The session pool contains this team's
  own live sessions, and the instability concentrates in the newest files — which is
  exactly where a newest-first scan looks first. So the artifact lands at the top of
  every diff and looks precisely like an ordering defect. Freeze a copy, or capture
  both sides in the same instant. I lost time to this; the write-up is in
  `harness/pool_order_gate.md`.
- **Five build configurations, not four.** `check`, `check --no-default-features`,
  `test --lib --no-run`, `build --release --no-default-features`, and
  `test --doc`. The last is the only one that compiles doctests, and the shipping
  binary is the `--no-default-features` build. Use a private `CARGO_TARGET_DIR`;
  `target/release/` is contended.
- **A differential gate is only as trustworthy as its assumption that the oracle ran.**
  Every gate here shells out to `ch-legacy`, which is a Python console script importing
  `chats` from the live `src/` tree — a tree other sessions edit continuously. A mid-save
  gives exit 1, empty stdout and a traceback. Assert the oracle **succeeded** before
  comparing anything, as a *precondition*. Comparing the exit status as ordinary *data*
  alongside stdout is better than ignoring it, but it turns "the oracle crashed" into "the
  exit codes differ", which sends the reader to the wrong file. `search::width_parity` had
  exactly this defect and now asserts; `render_parity` and `parse::argparse_parity` still
  compare it as data.
- **Every gate ships with a falsification** — a deliberately wrong implementation,
  run as part of the gate, failing the build if the gate stops catching it. Mine are
  textual mutations applied to the module under test; the pattern is in
  `harness/falsify_gates.py`. Mutate a **private copy** of the crate, never the shared
  checkout: a crash mid-run otherwise leaves the tree mutated and poisons the next
  baseline, and a peer reading the file meanwhile will publish a wrong finding from it.
- **A falsifier proves a gate fires. It does not prove the gate fires for the modelled
  cause — unless you check the failure *message*.** I hit this directly: my shadow used
  `raise SystemExit(...)`, which Python exits on *without* printing a traceback, so it
  modelled a clean non-zero exit rather than a crash. The tests went red, but on an
  older assertion, not the new one. Had I recorded "falsified" from the red alone, the
  assertion would have been vouched for by a run that never exercised it. Read what the
  failure says, not that there was one.

## 9. Cautions earned the expensive way on this slice

- **A gate that reimplements the thing it grades is grading itself.** One of mine
  copied the engine's predicate into the test, returned the right number, and could
  never have failed.
- **A check can be wrong in time, not just in scope.** A build that skipped test
  targets; a verification that ran only after a multi-step edit had closed the gap it
  opened; a mutation run whose crash left the engine mutated and poisoned the next
  baseline.
- **Announce before you start on a shared file.** Checking that a file is absent is a
  fact about the past; an announcement is a fact about your intent, and only the
  second is visible to a peer about to return.
- **Four of five surprising gate failures on this slice were the instrument, not the
  code.** Treat a shocking result as your measurement until you have proved
  otherwise — but see section 3, where a surviving mutation meant the code really was
  wrong. Both directions happen.
