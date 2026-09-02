# Red acceptance contract — the public `ch search` journey

Owner: `contract-owner`. Status: accepted and promoted; A1 complete.
Baseline: `main` at `8cb4c5f`. The oracle's tree state is recorded per corpus in
`ORACLE.json` and is no longer clean — see section 8.5, which is the mechanism
that keeps that fact from going stale in this sentence.

Live counts: **260 cases across two corpora** (227 frozen, 33 amendment), five
proof classes, two timing gates, and **88 frozen-successor rows** in
`tests/test_search_frozen_differentials.py`. Exactly one class is red, by
construction, across all 260 cases.

A case count is not a coverage measure — see §"the frozen pattern set". Do not
quote these numbers as coverage.

---

## 1. What this document is

The mission moves `ch search` into the package-owned Rust executable without
changing what a user sees. This document defines what "without changing what a
user sees" means, in terms that a machine can refuse.

It answers three questions:

1. What is the observable surface of `ch search` today?
2. What proof, running now, goes from red to green exactly when the Rust
   authority arrives — and for no other reason?
3. What could not be pinned, and therefore must not be treated as settled?

Everything here was measured against the product on current `main`. Where a
claim came from someone else's notes, it is marked as such and was re-measured
before it entered this document.

---

## 2. The shape of the thing being replaced

`ch` is a Rust binary. `rust/main.rs` handles exactly one command natively,
`ch parse`. Every other command, `search` included, is handed to a private
Python entry point:

```rust
// rust/main.rs:393
let executable = std::env::current_exe()
    .and_then(|path| path.parent().map(|parent| parent.join("ch-legacy")));
std::process::Command::new(executable).args(arguments).exec();
```

Two consequences shape this whole contract.

**The handoff is a file lookup.** `ch-legacy` is resolved as a sibling of the
running executable. Take that file away and the route cannot survive. This is
the only property of the handoff that can be observed from outside the process,
and section 5 builds the authority proof on it.

**The handoff is `exec`, not `fork`.** The Python interpreter replaces the `ch`
image in place, keeping the same process id. Every proof shaped like "did `ch`
start a Python child" is therefore vacuous. So is a `DYLD_PRINT_LIBRARIES`
trace: macOS strips `DYLD_*` when it execs a hardened-runtime interpreter, so
the trace ends at the handoff and reports zero Python libraries for a route that
is entirely Python. `reviewer-profiler` measured this independently by running
the same trace against `ch info --help`, which is Python by design and produced
the identical clean result. Neither proof is used here.

---

## 3. The observable surface, as measured

Measured by running the public journey against a deterministic fixture `HOME`.
The full sweep is at `teammates/contract-owner/work/sweep-out.txt`.

**Result modes.** `matches` (default), `-f/--full`, `-l/--list`, `-ll/--only-id`,
and `-r/--raw`, with precedence `only-id > list > full > matches`. `-ll` and `-r`
both force `--color never` and `--no-paging`.

**Two output families, not one.** Plain output prints a `console.rule()` band,
then YAML-ish frontmatter, then XML-tagged bodies. Colored output is a different
renderer: `--list` becomes two-line Rich rows with a trailing
`N sessions · newest first` summary, and `matches`/`full` become bordered Panels
whose hue cycles over four colors per conversation. These share almost no bytes.

**Ordering.** Newest first, by filesystem stat mtime, streamed in scan order as
each hit is confirmed. `-r/--raw` is the one exception and buffers every hit,
because its single-session-single-message case must know the totals up front.

**Two clocks, and they are not the same clock.** Ordering uses filesystem stat
mtime. The displayed `created:`/`modified:`, the colored age token and its
color, and the `-ma`/`-ca` filters all use *in-band JSONL timestamps* read from
the session content. A fixture that sets one and not the other tests less than
it appears to.

**Session-wide boolean truth.** `AND`, `OR`, `NOT`, parentheses. A term is
satisfied by a match anywhere in the session, so `AND` operands may match in
different messages. Uppercase operator words only. `NOT` cannot be mixed with
`AND`/`OR`. A pattern whose only operator token has no operand — `ch search AND`
— falls back to a single literal term, and matches sessions containing "and".

**Facets are outside message selection.** Terms also match session summaries and
the current custom title, and those are not filtered by `--only-user` /
`--only-assistant`. Proof: `--only-user --only-assistant` resolves to
`MessageSelection.NONE`, yet still returns facet-only hits with exit 0.

**Search truth is defined on rendered text.** Terms are evaluated against
`render_message_inner_xml(message, flags, tool_id_map)` — one string per
message — not against the parsed model and not against the raw JSONL. Anything
that changes rendering changes which sessions match.

**Visibility changes matching, not just display.** Content behind `-T`, `-t`,
`-a`, `-b`, `-A`, `--plans` is invisible to search until its flag is passed.
`--short` participates too: progressive shortening positions are assigned
*before* matching, so shortening can remove the text a term was looking for.

**Regex or literal.** A pattern is compiled as a regex with
`MULTILINE | DOTALL`, plus `IGNORECASE` unless `-s`. On `re.error` it is
recompiled as an escaped literal — still case-insensitively by default. The set
of patterns CPython *accepts* is therefore part of the public contract, because
acceptance decides whether a pattern behaves as a regex or as literal text.

**Exit codes.** `0` any hit. `1` no hit, or an empty candidate pool. `2` usage
and query-grammar errors. The no-hit hint goes to stderr and gains
`" with the current filters"` when any pool filter is set; `-ll` prints nothing.

**Grammar asymmetry worth naming.** `ch search -T needle` and
`ch search -t needle` are usage errors — exit 2, "the following arguments are
required: pattern" — because search never runs the positional repair that parse
mode runs. `--short` *is* repaired, so `ch search --short needle` works. A
native implementation that helpfully repairs `-T`/`-t` would break parity.

---

## 4. Where the corpus came from, and why every expectation was re-derived

`context-curator` found a finished native rewrite on branch
`wip/cycle-02-native-default-pause-20260821` at `0ffde41`, carrying a 173-case
installed-launcher contract. Its command shapes are the most valuable artifact
on this mission. Its expected outputs were produced by its own implementation.

Every one of the 173 shapes was replayed against the product on current `main`
and its expectation re-derived from what `main` printed. Result: **166 agreed
byte for byte, 7 disagreed.**

All seven disagreements are the same single difference, and it is not a
behavioral one. The colored age token is rendered inside a style whose color
encodes an age *bucket*. The branch's harness normalized the age *text* to
`{AGE}` but left the color. Its fixture sessions carry a fixed `2026-08-20`
timestamp, which was six days old when characterized and is eight days old now,
so the bucket moved from "week" (`#878c92`) to "month" (`#6b7076`).

**The branch's colored expectations went from green to red in three days, with
no code change anywhere.** There is no hidden divergence behind them; there is a
corpus that cannot reproduce itself.

That is a sharper reason to re-derive than the one the rule was written for, and
it produces a design rule this contract follows: **normalize both the token and
its color, or neither.** Section 6 pays for that normalization.

---

## 4.5 Two corpora, and why they must stay two

The contract corpus is **frozen**: 227 cases, expectations re-derived from the
Python product. Freezing it makes a changed expectation a correctness event
rather than routine maintenance.

Post-freeze findings go into a second corpus, `search-amendment-fixtures`, 25
cases in a pool of its own. This is not tidiness. **The session pool is an input
to every broad-pattern case in a corpus** — `.` and `zznope|` match everything —
so adding six session files to the frozen corpus would move roughly a fifth of
its expectations. That is invalidation wearing an amendment's clothes. A second
pool is additive by construction: nothing added later can perturb what is frozen.

**Why a second, real-session corpus exists elsewhere and this one does not
replace it.** `reviewer-profiler`'s framing, which is sharper than the size
argument I first gave: *curated fixtures cover the cases someone thought of; a
real-session corpus covers the ones nobody would.* Their corpus found a Codex
session composed entirely of injected scaffolding — a `developer`-role
permissions block, an AGENTS.md blob, an `<environment_context>` element — which
the Python product correctly hides from `search .` and the branch showed. Nobody
writes that fixture, because it is not interesting; real usage produces it at
roughly one percent. This corpus could have been ten times larger and still not
contained it, because the generating process was a person deciding what mattered.
Size was never the axis.

**A synthesized fixture must be validated against the real thing it was
synthesized from, and where they disagree the fixture is the suspect.** Fixtures
here are synthesized rather than copied, because a real 19–44 KB transcript pins
a hundred properties when it means to pin one, and a failure cannot tell you
which moved. The cost is that a synthesized adversarial fixture reaches what
usage never produces, so nothing else can check whether it reproduces the shape
it claims.

Done for the all-preamble Codex sessions. The three real specimens from
`reviewer-profiler`'s corpus were run through `search . -ll` alongside one
visible control: all three hidden, control visible. The six synthesized sessions
behave identically, and searching the preamble text directly — `permissions
instructions`, `AGENTS.md instructions`, `environment_context`, `previous turn
was interrupted` — returns exit 1 and no output for every one, so the text is
genuinely unreachable rather than merely absent from `.`.

The rule that follows: an amendment adds a case and regenerates *that case*.
Regenerating the corpus to add one shape would silently re-derive 250
expectations against whatever the product does today, which is how a parity net
turns into a mirror. `generate_fixtures.py --amend ID…` exists so the rule is
mechanical rather than a promise.

What the amendment corpus carries, each because a named defect had no fixture:
`session-core`'s six branch fixtures at shapes real corpora hold at 1–2%
prevalence; the DST fold; the lowercase `z`; the trailing-space asymmetry; and
the NFC-versus-NFD title elision pair.

**The distinction that decides which corpus a shape belongs in** — and the one
that took an argument to reach — is this. *A shape defined relative to `now`
cannot be a fixture. A shape defined at a fixed calendar instant is exactly what
a fixture is for.* An age band drifts: a session placed at month scale today is
at year scale in five months, which is how the inherited corpus rotted from
green to red in three days. The DST fold does not drift: `2026-10-24T22:30:00Z`
is the same instant forever. Age bands therefore live in a clock-relative test;
the DST fold lives in the corpus.

## 5. The proof, in five classes

Five classes, kept separate because each fails for a different reason. The
first three are the spine; the last two cover dimensions no frozen corpus can
hold. All run
against a launcher this suite builds itself with
`cargo build --release --bin ch --no-default-features`, mirroring
`[[tool.setuptools-rust.bins]]`, and refuses any binary carrying strings this
HEAD cannot produce.

### 5.1 Byte lock — green today, must stay green

`test_search_journey_matches_characterized_legacy_bytes`

Every manifest case pins exit status, stdout, and stderr against the re-derived
expectations. This is the parity net. It is green now, which is what makes it
useful: a change that turns it red is a change in observable behavior.

### 5.2 Live differential — green today, load-bearing at cutover

`test_search_journey_matches_live_legacy_implementation`

The same shapes run through `ch-legacy search` and through `ch search`, and the
bytes must match. Today `ch` hands search to `ch-legacy`, so this compares a
process with itself and proves only that the harness is wired. Once search is
native, it becomes a parity oracle that **cannot rot**, because it compares two
live processes on the same corpus instead of comparing one process against a
recorded past.

This class exists only because the first mate ruled the Python implementation
stays alive through cutover. It is the direct payoff of that ruling.

**And it has a lifetime, which should be recorded before someone is surprised by
it.** Deleting the Python side is its own final slice. When that lands, this
class stops being runnable — there is no second implementation to compare
against. The byte lock survives, because recorded bytes need nobody to still be
able to compute them; that is the same property that makes a stored table oracle
outlast an in-process differential.

So the order matters: **this class is the proof that the cutover preserved
behaviour, and the byte lock is the proof that survives it.** Do not let the
deletion slice land while this class is the only thing that has verified a
change, and expect its removal to be part of that slice rather than a
regression.

**One known asymmetry.** The two sides do not agree on `sys.argv[0]`: `ch` execs
its sibling, so the interpreter sees the launcher's path, while `ch-legacy`
invoked directly sees the virtualenv's. Anything the product prints that names
its own executable therefore differs for a reason that is not a parity break.
Today exactly one thing does — a traceback's first frame — and it is normalized.
After cutover the native route has no Python `argv[0]` at all, so the asymmetry
disappears rather than widening.

### 5.3 Authority proof — red today, by construction

`test_search_journey_needs_no_private_legacy_entry`

The launcher is copied alone into an empty directory, with `PATH` stripped to
`/usr/bin:/bin`, and every search shape must produce the same bytes and the same
exit status it produces normally. `run_legacy` cannot find a `ch-legacy` sibling
there, so this fails today for exactly one reason: the search route is not yet
native. **This is the only thing in the suite that is allowed to be red.**

Two controls keep it honest, because a proof that cannot fail proves nothing:

- `test_solitary_launcher_harness_is_sound` — `ch parse --help`, already native,
  must succeed in the same directory. Without it, an unrelated regression could
  turn the authority proof red and be read as "still not native".
- `test_solitary_launcher_still_refuses_a_legacy_owned_command` — `ch info
  --help`, still legacy-owned, must fail there with the private-entry error.
  Without it, an empty directory that silently stopped isolating anything would
  turn the authority proof green with no native code written.

### 5.4 Query-validity differential — green today, and the only view of a silent class

`test_named_defect_patterns_select_the_same_sessions`
`test_generated_patterns_select_the_same_sessions`

`compile_search_term` catches `re.error` and recompiles the escaped pattern, so
an invalid pattern silently becomes a literal search. **The set of patterns
CPython accepts is therefore part of the public contract.** A validator that
accepts a different set flips a pattern between regex and literal and changes
which sessions match, with no error raised on either side.

`query-semantics` measured where the risk actually lives: across 4,000 generated
patterns, all 994 engine divergences were accept-or-reject and **none** were
match semantics. At the product level an accept-or-reject disagreement has
exactly one visible trace — a different set of session ids — so this differential
is the only thing in the mission that can see it.

Two halves, because they fail differently. 18 named patterns behind the known
defect classes are held by name, since two of those classes came from
enumerating Unicode rather than from generation and no seed would reproduce
them. 60 generated patterns come from `query-semantics`'s generator, live rather
than frozen, because three defect classes came out of it that nobody would have
written by hand. Width is a generated dimension across them — 52, 96, 110 and
140, none of them 80 — so a width defect cannot hide inside a pattern diff.

The generator filters catastrophic-backtracking shapes before they reach the
suite; `query-semantics` measured the whole 4,000-pattern corpus at 10.2 ms
total, slowest pattern 0.111 ms, after that filter.

### 5.5 Terminal differential — green today, and the only view of interactive width

`test_colored_terminal_output_matches_live_legacy_implementation`

Five colored shapes — list rows, matches panels, a full panel carrying fenced
code, CJK plus emoji, and long wrapped lines — driven through both binaries on a
pseudo-terminal at 52 and 110 columns, with `COLUMNS` and `LINES` deleted from
the environment. A differential rather than a golden, because the size of a
terminal is not something a fixture can record.

Neither width is 80. Eighty is `main`'s own fallback constant, so it is the one
point where a width-aware renderer and a hard-coded one produce identical bytes;
a diff taken there measures nothing while looking like coverage.
`test_narrow_terminal_actually_elides` proves 52 columns really does force
elision, so the parameterization cannot drift wide and silently stop testing the
width path.

### Exact commands

```sh
# The whole contract.
uv run pytest tests/test_search_command_contract.py -q

# The intended red, alone.
uv run pytest tests/test_search_command_contract.py -q \
  -k "needs_no_private_legacy_entry or solitary_launcher"

# The parity net and the live oracle, which must be green at every moment.
uv run pytest tests/test_search_command_contract.py -q \
  -k "characterized_legacy_bytes or live_legacy_implementation"

# Re-derive every expectation from the Python product (after an accepted
# behavior change, never to make a red test green).
cargo build --release --bin ch --no-default-features
uv run python thoughts/2026-08-28-search-rust-rewrite/teammates/contract-owner/work/generate_fixtures.py
```

---

## 5.6 Harness calibration — the instrument is graded before its results are quoted

`reviewer-profiler`'s calibration injects one minimal mutation per observable
dimension and requires the harness to notice it. A dimension where the mutation
passes unseen is a dimension where every parity result the harness ever reported
is vacuous. Run it with:

```sh
uv run python thoughts/2026-08-28-search-rust-rewrite/teammates/contract-owner/work/calibrate_contract_harness.py
```

It grades **two** instruments, not one, because they are blind in different
places: the capture, and the comparator, which is the capture plus
`_normalize` — the thing the byte lock and the live differential actually
compare. Grading only the capture would hide the normalization, which is the
same mistake the normalizations exist to be honest about.

Current result:

```
capture                              CALIBRATED
comparator (capture + _normalize)    BLIND in 1
                                     - cannot see: SGR colour code
```

And the blindness is narrower than that label, measured rather than assumed:

```
BLIND    the two age-bucket colours the probe used
sees it  arbitrary colours (red vs green)
sees it  the conversation panel hue cycle
sees it  an age colour against a non-age grey
```

The comparator is blind only to distinctions *among the four age colours*, not
to colour generally. Overstating your own blindness misdescribes the instrument
exactly as much as understating it does. The script fails on any capture
blindness at all, and on any comparator blindness other than the declared one,
so a new normalization cannot be added without this gate noticing.

## 6. What normalization hides, and what pays for it

Two byte classes cannot be owned by a fixed corpus, so they are replaced with
placeholders. Each one is confessed here and paid for by a test that pins what
it hides. This list is the complete set; adding to it requires the same payment.

| Placeholder | What it hides | What pays for it |
| --- | --- | --- |
| `{HOME}`, `{PROJECT_ROOT}` | Absolute paths of the fixture tree | Nothing needed: the paths are the harness's own, not the product's |
| `{AGE}` and `{AGE_STYLE}` | The relative age token and the color encoding its bucket | `test_search_age_token_and_style_track_the_clock` pins both across all four buckets — hours, days, weeks, years — using a fixture built relative to the current clock |
| `{SEARCH_QUERY_SOURCE}` | The source path baked into a Python warning | Ruled away rather than paid: the native route omits the location. See U2 |

**Both substitutions must fire, and for a day only one did.** The colour
replacement rewrites the SGR introducer that the token pattern anchors on, so
running it first silently disabled the token replacement: `{AGE}` appeared in
zero files while `{AGE_STYLE}` appeared in fifteen, and seventeen expectations
carried a live `1w` that would have rotted within days. That is the branch's
defect with the two halves swapped — and this document stated the rule correctly
while the code implemented its inverse.

**A normalization that silently no-ops is invisible in exactly the same way as
one that is unnecessary.** The corpus looks identical either way. So every
placeholder `_normalize` can emit is now declared alongside whether the corpus
should contain it, three are recorded as legitimately absent with reasons, and a
check asserts the declared set matches what the code emits. A placeholder cannot
be added or removed without a decision.

That gate caught itself on its first run: it globbed `*.stdout` and reported
`{SEARCH_QUERY_SOURCE}` dead, when it only ever lands on stderr. The instrument
built to detect dead substitutions was half-dead in the same way, and it failed
loudly rather than passing.

**The age pair is debt, not design.** It exists only because age is read from
wall-clock `now` with no injection point on either side, so the corpus has no
way to freeze the clock. `search-runtime` is landing a clock injection point —
read once at startup, one source, no branching, the same mechanism on both
sides, the same shape as the `$HOME` override. **Both normalizations come out
the day it lands**, and `age_style` returns to the byte lock at all four buckets
with a boundary case at each. Until then the clock-relative test above keeps the
class covered, so the interim measure hides nothing.

---

## 7. Seams the contract forces between the technical owners

These are the places where the contract's behavior cannot be satisfied by one
owner alone. They are interface decisions, not implementation details, and each
one has a failure mode that is silent if it is drawn in the wrong place.

**S1 — The rendered-message string.** `session-core` → `query-semantics`.
Search truth is defined on the inner-XML rendering of each message under the
active flags. Query evaluation consumes one string per message. *If two
renderers exist, search truth forks from parse truth with nothing to show for
it.* This is the seam behind the `has_inner_opening_tag` escaping defect
`session-core` found.

**S2 — The session facet triple.** `session-core` → `search-runtime`.
Summaries, current custom title, and cwd, extracted once per file, and
explicitly **not** subject to message selection. `search-runtime` owns the match
arithmetic over messages plus summaries plus titles. *Drawn wrong, facet-only
sessions vanish from results under `--only-user`.*

**S3 — Shortening runs before matching.** `session-core` → `query-semantics`.
Progressive shortening positions are assigned across all visible messages before
any term is evaluated, per `SHORT_SPEC.md`. *Drawn wrong, `--short` changes
which sessions match rather than only how they print.*

**S4 — The sound literal lower bound.** `query-semantics` → `search-runtime`.
Per term, `search-runtime` needs the pattern text, its case sensitivity, and a
literal that is a **sound lower bound**: present in the raw bytes whenever the
term can match. Today `literal_candidate` uses `str.casefold()` while matching
uses `re.IGNORECASE`, and those disagree — for `ß` the candidate is `ss`, which
the regex does not match. The `.isascii()` guard is the only thing keeping every
byte gate sound. *This is the most dangerous seam on the mission: an unsound
bound drops sessions silently, with no error on either side, and the natural
future "optimization" is to widen the gates to non-ASCII.* `search-runtime` is
pinning the guard; `query-semantics` owns the bound's definition.

**S5 — Two clocks.** `search-runtime` (stat mtime, for ordering) and
`session-core` (in-band timestamps, for display, age, and `-ma`/`-ca`).
*Conflated, ordering and date filtering both move, and a fixture that sets only
one clock cannot see it.*

**S6 — The highlight term inventory.** `query-semantics` → `search-runtime`.
Only literal terms are highlighted, longest first, case-insensitively unless
every term is case-sensitive. *Drawn wrong, colored output paints the wrong
spans while every plain-mode test stays green.*

**S7 — Conservative gate semantics.** `query-semantics` → `search-runtime`. The
candidate prefilter treats `NOT` as always-passing and must never reject a file
the authoritative pass would have matched. *One-directional: false accepts cost
time, false rejects lose results.*

**S8 — One provider classifier.** `session-core` → `search-runtime`, consumed
twice: for the pool partition (`-p`, and the colored provider column) and for
pi-specific candidate evidence. *Two classifiers drift, and the column and the
filter start disagreeing.*

---

## 8. Surfaces I could not pin — do not draw boundaries here yet

The first mate asked for this list explicitly, because an unpinned surface is a
boundary that must not be drawn. Each item names what is missing and why.

**U1 — Interactive terminal width.** *Closed.*
`test_colored_terminal_output_matches_live_legacy_implementation` drives both
binaries under a pseudo-terminal at 52 and 110 columns with `COLUMNS` and
`LINES` removed from the environment. Neither width is 80, because 80 is
`main`'s own fallback constant and therefore the single point where a
width-aware renderer and a hard-coded one agree. `test_narrow_terminal_actually_elides`
verifies that the narrow width really forces elision, so the parameterization
cannot drift wide and stop testing anything while still passing.

**U2 — The warning source path.** *Ruled.* The native route prints the warning
text and category verbatim and omits the source location. A Python warning's
`file:line` names a location in interpreter source that does not exist in a
native binary, so any value there is invented; the unmerged branch fabricated
one from `CARGO_MANIFEST_DIR` naming a Python file it deletes. Documented
divergence, recorded in the change log.

**U3 — Signals and the pager lifecycle.** SIGINT during pager streaming, SIGPIPE
mid-panel write, process groups, and reaping of `less`. Only whole-buffer EPIPE
is pinned. Nothing here is expressible as exit-code-plus-stdout-plus-stderr.

**U4 — Hostile inputs.** Non-UTF-8 argv, unset `HOME`, and a pool file created,
deleted, or rewritten between discovery and confirmation.

**U5 — `-ma`/`-ca` with an invalid date.** *Ruled: preserved exactly.*
`ch search -ma notadate needle` raises lazily inside the per-file scan loop, is
caught by the generic handler, prints one error per candidate file, and exits 1.
It is ugly, and it is preserved, because legacy still produces a usable answer
and smuggling an improvement into a parity rewrite is the failure this mission
is guarding against. Recorded in the change log as deliberately preserved, and
raised separately as a follow-up proposal.

**U6 — Concurrency between discovery and confirmation.** The pool is discovered
once and confirmed file by file. What a native implementation should do when a
file disappears in between is unpinned.

**U7 — Performance shapes.** `tests/test_search_perf.py` measures the user's
real session pool, so it is machine-dependent and non-reproducible. My corpus is
built for behavior, not for timing. Owned by `reviewer-profiler`, whose
fixed-corpus gates replace the two flapping live-pool budgets.

### The surface no golden can own

Two behaviours are public, reachable, and deliberately absent from the byte lock.
They share a property: **the oracle produces no usable answer, so there is
nothing to record**, and recording what it does produce would commit the native
route to reproducing a defect. Both are ruled to be repaired rather than
reproduced, under the divergence principle below. Both become testable for the
first time when the repair lands, and that test belongs to whoever writes it.

**U8 — Catastrophic backtracking cannot be pinned by any fixture.**
`ch search '(a+)+b'` against a session holding 40 consecutive `a` characters does
not terminate in CPython — measured at over ten seconds on the bare `re` call,
with no timeout, no warning, and no interrupt short of killing the process. The
oracle produces no answer, so no golden can record one. The corpus exercises the
backtracking path at a run length that terminates. The pathological case is a
characterized product behavior, ruled to be **repaired** rather than reproduced:
a literal prescan fixes the cost model, and a budget remains only as a guard
that fails loud. It becomes testable when the guard lands, and that test belongs
to whoever builds it.

**U9 — `truncate_middle` below the public floor.** Its final expression is
`s[:first_half] + placeholder + s[-second_half:]`, and when `second_half == 0`,
`s[-0:]` is the whole string rather than the empty one, so it returns *more* than
it was asked to keep — input plus 4 at `max_chars=4`, input plus 6 at 6. Both are
unreachable through the public surface, because `parse_short_spec` rejects
limits below 8 and `effective_max_chars` floors its progression at 8. No fixture
can express them without reaching past the boundary this contract is a statement
about, so there is none. **The instruction stands in their place: reproduce
`s[-0:]` verbatim, do not guard it.** A port that returns empty for
`second_half == 0` diverges the moment the floor moves, and the fixture that
would catch it cannot exist until then.

**U10 — `isdigit()` then `int()` raises, and the traceback cannot be a golden.**
Python's `str.isdigit()` accepts digits with no decimal value, so
`cli.py:73` and `cli.py:78` — `candidate.isdigit() and int(candidate) > N`, with
no guard — reach `int()` with something it rejects. Verified through the public
surface: `ch search --short ² needle` prints an uncaught `ValueError` traceback.
Ruled repaired as a class rather than reproduced: the native route accepts
Unicode decimal digits like `"５００"` → 500, matching Python where Python works,
and rejects the rest cleanly. A byte-lock case here would pin a stack trace
carrying this machine's paths, and would commit the native route to a crash we
have already decided to remove.

**U11 — A lowercase `z` timestamp crashes the renderer, and the traceback cannot
be a golden.** `model.py:34` does `datetime.fromisoformat(timestamp.replace("Z",
"+00:00"))`, which handles only the uppercase spelling, so `ch search -f` over a
session whose timestamp ends in a lowercase `z` exits 1 with an uncaught
`ValueError` and a stack trace. ISO 8601 permits the lowercase form.

This is strictly worse than the same finding in the metadata path, where the
unparsed timestamp merely falls back to the filesystem clock. Ruled repaired
under the same principle as U10. The lowercase-`z` fixture pair keeps its other
cases, including a `--mafter` split that pins the silent clock fallback with no
wall-clock value in the expectation.

*This one also cost a lesson about the harness.* It read as a flake for two runs
because a traceback's first frame names the executing script, and the
private-launcher copy — the fix for the shared-artifact race — put a per-run
temporary path there. **A fix for one nondeterminism class created a second one,
visible only in the single case whose output names its own executable.** The
launcher directory is now normalized.

### The divergence principle these rulings share

Legacy behavior is preserved, including behavior we consider poor, whenever
legacy produces a usable answer. Divergence is allowed only where legacy fails
to produce an answer at all. A hang costs the user the result; verbosity does
not. U5 is preserved under that rule and U8 is repaired under it.

---

## 8.5 The oracle guard

Every expectation here was derived by running the Python product, which is
reached through an editable install and therefore resolves to the `src/chats/`
**working tree** rather than to a commit. Naming a revision is necessary and not
sufficient: an uncommitted edit leaves the revision string true and the claim
false, and that is exactly the failure being guarded, since a teammate holds a
narrow exception to edit `src/chats/commands/search.py` for the clock seam.

`ORACLE.json` therefore records the revision **and** a SHA-256 over every
`src/chats/**/*.py`. The guard checks it twice:

- **Before the run**, so a moved oracle is reported as a moved oracle rather than
  as several hundred parity failures whose real cause is one edit.
- **After the run**, because the live differential runs two processes seconds
  apart, and an oracle that moves between them makes the comparison meaningless
  without either side erroring.

**The recipe, so nobody writes a second one.** The oracle's identity is
`oracle_route_digest()` in `tests/oracle_digest.py` — importable, doctested,
importing neither the suite nor the generators. **Do not compute a stamp any
other way.** A digest of the working diff (`git diff -- src/chats/ | shasum`)
looks equivalent and is structurally incapable of detecting what stamps exist to
detect: it cannot see `.venv/bin/ch-legacy` or the installed `RECORD`, so it
reads unchanged while a `uv sync` replaces the Python route underneath a run.
That happened twice here, and the route-wide digest caught both.

**Oracle of record: revision `8cb4c5f`, working tree digest recorded in each
corpus's `ORACLE.json`.** The revision alone is not the stamp, and this document
does not carry a copy of the digest on purpose — a stamp duplicated into prose
is a stamp that stops being true silently. `ORACLE.json` is the single place it
lives, and `rebless_oracle.py` is the only thing that writes it.

The guard brackets the **whole Python route**, not just its sources. A launcher
can be copied private; a Python route cannot — it is a script plus an
interpreter plus an installed distribution, and a concurrent reinstall replaces
the parts a copy does not cover. So the digest spans `src/chats/**/*.py`, the
`ch-legacy` entry script, and the installed distribution's `RECORD`.

**An oracle event has already occurred and been closed by proof.** The clock seam
moved `src/chats/commands/search.py`. The guard fired and named the cause in one
line. `rebless_oracle.py` then replayed every case in both corpora: 252 of 252
reproduced their recorded bytes, so the oracle moved without moving behaviour,
and the record was re-blessed. That is the second branch of the ruling —
*prove behaviour unchanged* — kept distinct from the first, which is what stops
the easy option from swallowing the hard one.

## 8.6 Nondeterminism found and closed: the suite raced the checkout

A run of this suite failed three to four cases, never the same set twice, none
reproducible standalone, none reproducible outside pytest. The cause was not in
the assertions.

`target/release/ch` is shared. `test_parse_command_contract.py`'s session fixture
unlinks and rebuilds exactly that path, and several suites place their own
`ch-legacy` sibling beside it. Under `--dist=loadfile` those land on a different
worker and run concurrently, so another process was deleting and rewriting the
binary this suite was mid-way through measuring. The failing set was whichever
cases fell inside a rebuild.

Evidence, not deduction: `target/release/ch` rebuilt at 14:40:47 inside a failing
run's window; `ch-legacy` replaced at 14:50:07 by a process that was not this
suite; and a replay of all 221 cases outside pytest during a quiet window, 0
mismatched.

**The fix removes the class.** The suite copies the built launcher to a
session-private path and runs every case from there, so the artifact under test
is immutable for the length of the run.

**The ordering-tie constraint, stated precisely.** Both routes sort on mtime at
sub-second precision — Python on `st_mtime`, the native side on
`mtime() + mtime_nsec()/1e9` — so neither produces ties on a real corpus.
`reviewer-profiler` initially measured 15 tie groups across 31 of 695 real files
and then withdrew it: they had counted with `stat -f '%m'`, which truncates to
whole seconds, and at full precision all 695 are distinct. So the constraint is
not "real corpora contain ties", it is: **any implementation that drops to
whole-second mtime creates 15 tie groups in 31 of 695 real files and falls
through to directory order.** The generator's refusal defends exactly that.

**Proved by falsification, not by absence.** A full 227-case run while a loop
rebuilt `target/release/ch` and replaced its sibling every twenty seconds
throughout: 0 unintended failures, 227 of 227 intended reds. The failure stopped
happening under the conditions that caused it.

Two hypotheses were tested and killed on the way, both worth recording because
each was plausible and specific. Parallel-worker state in cached `Console`
singletons: real, and it cannot reach this file, which runs every case in a
subprocess and reproduced the failure single-process. And an ordering tie: two
fixture sessions shared a stat mtime exactly, and search sorts newest-first with
a stable sort, so the tie fell through to `read_dir` order, which is not stable
across directory instances. That was a genuine defect and it was not this one.
The generator now refuses to build a corpus containing any ordering tie.

## 8.65 "We have a differential for X" now requires "through what?"

No function in the new native modules is reachable from Python. The binding
layer exports twelve functions, all older search-gate and inventory helpers;
the public surface of `tool_filter`, `visibility`, `terminal`, `pager`,
`search_query`, `shortening` and `clock` is exposed nowhere. Measured
independently twice, from opposite directions.

So **no *in-process* differential can reach any new code by direct call.** The
missing word matters, and I recorded the stronger claim before it was corrected.
Three methods remain, and the third is better than the two I first named:

1. **A stored table oracle** — Python's answers recorded once, Rust compared
   against them later. Asynchronous, and in two respects better than in-process:
   reproducible without both implementations being loadable at once, and it
   survives the deletion of the Python side, which an in-process differential
   cannot.
2. **An end-to-end comparison through the CLI** — the actual product surface,
   which is what parity means in the first place.
3. **An out-of-process differential** — a small binary linking the crate as a
   path dependency, speaking a line protocol over stdin, both sides computing
   fresh. Needs no bindings widened, and `session-core` already runs four of
   them: 308, 2006, 355 and 2436 cases.

The boundary is real; the conclusion that it forces recorded-only proof was not.
**Do not widen the bindings** to enable in-process differentials — that adds
production surface purely for testability, which the charter forbids on the
completed route. The clock injection was a different case: an ambient input both
sides had to agree on before any comparison could mean anything.

Two conditions a later reader must apply to every coverage claim here.

**"We have a differential for X" requires "through what?"** — a table, the CLI,
or a subprocess harness. On new code it is one of those three, or it is a
mistake.

**A table that re-derives its own answers is not a fixture.** It is the
implementation wearing a fixture's clothes, and it passes against any port that
shares the derivation. Both corpora here store literal bytes; the tool-visibility
table stores literal `show`, `max_chars` and `progressive` values. Check it per
artifact rather than assuming it.

### Table oracles need both halves of the guard

**The stamp** answers *was this generated against the current oracle*. **Re-verification**
answers *does it still describe that oracle*. They fail differently: a stale
stamp is caught by the first; a generator bug, or a hand re-bless that skipped
the proof, only by the second. Any table where re-verification is possible gets
both — and it usually is possible, because the unreachable half is the Rust one
while the Python side is an ordinary importable function.

**A table that needs its generator in order to be interpreted is a cache, not a
fixture.** The tool-visibility table carries the five Python tool shapes lifted
out of its generator, which is what makes it self-contained rather than a
reference to code that may move.

**And a table must keep the cases that let it fail.** Everything in the
tool-visibility table except its 696 specificity ties passes against both
falsified wrong ports. A trim would leave 6619 cases, a green suite, and no
ability to fail — so the two ports and their 558 and 634 divergence counts live
in the module docstring, where the justification travels with the fixture.

## 8.7 What a green run does and does not mean today

**Every gate in this file is currently a formality.** Ten new Rust modules have
landed and five more are modified, and the byte lock and the live differential
are green against all of it — because the search route is still Python. Nothing
here has yet measured the native implementation.

They become the gate at the moment the route flips. A long run of green before
that moment is not a long run of verification, and a later reader should not
mistake one for the other.

## 9. Risks

**R1 — A stale launcher makes every proof lie.** `.venv/bin/ch` was one commit
behind the working tree when I checked; `uv run` does not rebuild it. I proved
it rather than inferring it: commit `a51f32c` added `.filter(|width| *width > 0)`
to the error-wrap width, so current source must ignore `COLUMNS=0`, and
`COLUMNS=0 .venv/bin/ch parse /nonexistent/...` wrapped at width zero. This
suite sidesteps the hazard by building its own launcher, and the first mate has
ruled that `tests/run_all.sh` asserts provenance rather than rebuilding
silently. The remaining exposure is every *other* test that runs `uv run ch`.

**R2 — Round-trip fidelity is not cross-implementation parity.** The branch's
suite was green while carrying a renderer escaping defect, because its
round-trip fixtures decoded its own escaping faithfully. Any proof that checks
an implementation against itself will do this. Class 5.2 exists to be the proof
that cannot.

**R3 — The corpus is a floor, not a census.** The branch's own accepted-
limitations list lost a deviation between slice and acceptance. Coverage
inherited from it should be read as "at least this", never "all of this".

**R4 — Colored coverage is thin relative to what it guards.** The inherited
corpus had 8 colored cases at 2 widths guarding a renderer with hand-written
per-language tokenizers. This contract now carries 23 colored cases spanning
shell with heredoc state, Python with f-string expansion, JavaScript, HTML, CSS,
JSON, Markdown and diff fences, long-line wrapping, and CJK plus emoji width, at
40, 60, 80, 96 and 140 columns, plus the terminal differential of section 5.4 at
52 and 110. It is much better; it is still a sample of a tokenizer, and a
tokenizer disagreement on a language none of these fences exercises would pass.

**R5b — The harness itself can be the thing that is wrong.** Two instrument
defects were found today that produce confident wrong numbers rather than
errors. `subprocess.run(..., text=True)` implies universal newlines, so captured
`\r\n` and lone `\r` become `\n`: a byte-diff harness built that way agrees where
the implementations differ and differs where they agree, and real transcripts
carry carriage returns constantly. And a CLI's trailing newline against a
library function's lack of one reads as total parity failure across an entire
corpus. This suite captures bytes and decodes explicitly throughout, audited
after the finding, and a carriage-return session is now in the corpus so the
product side is pinned too. A pty applies ONLCR, which is harmless for a
differential — both sides pass through it — and not harmless for any comparison
against pipe-captured bytes.

**R5c — Isolation keeps breaking relationships, and each fix has produced a new
instance of the class it closed.** Three times in one day, on this suite:

1. Copying the launcher private closed the rebuild race — and put a per-run
   temporary path into the one output that names its own executable, a
   traceback's first frame.
2. Copying the launcher private left the *Python route* shared, because a
   compiled binary is self-contained and a Python route is a script plus an
   interpreter plus an installed tree.
3. Building into a private cargo target removed the last shared path — and
   killed every case at the handoff, because `ch` resolves `ch-legacy` as its own
   sibling and the new directory had none.

The generalization is worth more than the three fixes: **the thing you are
isolating has neighbours, and isolation severs them.** Before copying an
artifact somewhere private, enumerate what it resolves relative to itself and
what resolves relative to it.

**R5c-inverted — De-duplication breaks relationships too, in the opposite
direction.** Removing a duplicated digest definition by having the generator
import the test module created a load-order dependency: computing the digest
then required reading a corpus the generator had just deleted, and both
`ORACLE.json` files were lost mid-regeneration. Nothing about "one authority for
the digest" suggests "the generator now depends on the test module's read
order". It lives in `tests/oracle_digest.py` now, importing neither side.

Together with R5c: **isolating something severs what it depends on; sharing
something creates a dependency that did not exist.** Both fail in the direction
nobody is looking. Expect the second class to appear as repeated logic is noticed
across the new Rust modules.

**R5d — A tool that refuses is only useful if its refusal is legible.** The
re-bless reporting "251 of 251 moved" told me the harness was broken; "3 of 251"
would have told me the product had. The count carried the diagnosis, and a 100%
move rate is implausible enough to be its own alarm. A refusal is only half a
design; the other half is whether its shape names the cause.

**R6 — Every gate must be checked against the claim it supports.** This mission
has now produced four green results measuring something narrower than the claim
they were read as supporting: round-trip fidelity read as cross-implementation
parity, a line count read as a diff, a loader trace read as a no-Python proof,
and a colored byte diff taken at the one width where the two renderers cannot
disagree. Three of the four were mine to inherit. Every class above therefore
carries a control whose job is to fail: the two solitary-launcher controls, the
elision check behind the narrow terminal, and the clock-relative age test behind
the age placeholders.

**R5 — The authority proof is a single mechanism.** If `run_legacy` ever gains a
second way to reach Python — a `PATH` lookup, an absolute path, an embedded
interpreter — the empty-directory proof stops covering it. It is guarded by the
`ch info` control, which would still fail, but a new mechanism would need a new
proof.

---

## 10. Definitions of done, and the falsifiers attempted

### Positive definitions of done

**D1.** Running `tests/test_search_command_contract.py` against a launcher built
from the accepted commit yields: every case green in class 5.1, every case green
in class 5.2, and every case green in class 5.3 — with the two solitary controls
still discriminating.

**D2.** Removing the native search route from `rust/main.rs` and rebuilding
turns class 5.3 red and leaves classes 5.1 and 5.2 green. The proof is
load-bearing rather than incidental.

### Falsifiers, and what happened when I attempted them

**F1 — "The existing suite already proves search parity."** *Disproved.* Every
search test on `main` except two shell scripts imports `chats.commands.cmd_search`
and calls it in-process. After cutover they would keep passing while exercising
Python that no user reaches. This is why the contract is process-level.

**F2 — "The delegation to `ch-legacy` is not observable from outside."**
*Disproved.* A copy of `ch` in a directory holding a shell script named
`ch-legacy` runs the script and returns its exit status, while `ch parse` in the
same directory ignores it. The handoff is observable, deterministic, and needs
no privileges.

**F3 — "A loader trace proves no Python."** *Disproved, and the test was
deleted.* `DYLD_PRINT_LIBRARIES` reports zero Python libraries for the
Python-served route, because macOS purges `DYLD_*` across the exec into a
hardened-runtime interpreter. `reviewer-profiler` reached the same result from
the other direction.

**F4 — "The branch's 173 expectations can be adopted as the oracle."**
*Disproved.* Seven of them fail against current `main`, all seven on a color
that encodes a wall-clock age bucket their normalization left exposed. The
corpus does not reproduce itself across three days.

**F5 — "The fixture corpus can use absolute timestamps."** *Disproved by F4.*
Any byte that encodes an age relative to now must be normalized or generated
relative to now. This contract does both: normalized in the byte lock, generated
relative to now in the test that pins the buckets. Superseded once the clock
injection point lands.

**F6 — "A backtracking-heavy pattern can be pinned like any other."**
*Disproved, and it stopped the fixture generator dead.* `(a+)+b` over 40
consecutive `a` characters does not terminate in CPython; the bare `re` call
exceeded ten seconds. An oracle that never answers cannot produce an
expectation. The corpus now caps the run length, and the pathological case is
carried as U8 rather than as a test.

**F7 — "Colored coverage at fixed `COLUMNS` covers interactive width."**
*Disproved.* `COLUMNS` set in the environment is exactly what makes a program
that reads only the variable indistinguishable from one that asks the terminal —
the shape of a width bug this project has already shipped. Section 5.4 removes
the variable and asks a real pseudo-terminal instead.

---

## 11. What I changed outside this desk

- `tests/test_search_command_contract.py` — new; the five proof classes.
- `tests/data/search-contract-fixtures/` — new; fixture `HOME`, `MTIMES.json`,
  `MANIFEST.json`, and re-derived expectations. 221 cases: the 173 inherited
  shapes plus 48 of this contract's own, each added because a named defect had
  no fixture shaped like it. The generator that produces them lives at
  `teammates/contract-owner/work/`, so every expectation can be re-derived from
  the Python product rather than hand-edited.
- `tests/data/search-amendment-fixtures/` — new; 25 post-freeze cases in their
  own pool. See section 4.5.
- `tests/query_pattern_corpus.py` — new; `query-semantics`'s pattern generator
  and their 18 named defect patterns, landed here because I own `tests/`. Its
  doctests pin determinism and the backtracking-safety filter and are worth
  keeping.
- `tests/conftest.py` — new; resets the four `Console` objects `chats.console`
  caches in module globals and never cleared. A Rich `Console` freezes width,
  colour system and `no_color` at construction, so the first test in a process to
  touch one fixed those for every test after it, and a later
  `monkeypatch.setenv("COLUMNS", …)` could not move it. That made width, colour
  and tty assertions across 49 in-process files order-dependent — and under
  `-n 8 --dist=loadfile`, dependent on which worker received which file. Found by
  `reviewer-profiler`. Validated green across the whole in-process suite.

### The 48 shapes this contract added, and why each exists

| Shapes | Added because |
| --- | --- |
| 14 colored cases at 40, 60, 96 and 140 columns: shell with heredoc state, Python with f-string expansion, JavaScript, HTML, CSS, JSON, Markdown and diff fences, long-line wrapping, CJK plus emoji | 8 colored cases at 2 widths were guarding a renderer with hand-written per-language tokenizers |
| 5 inner-tag escaping shapes: over-eager, under-eager by tab, under-eager across a line boundary, and the two that agree | `session-core` proved the disagreement runs **both** ways; a fixture built on the one-directional framing would have tested a third of it |
| 7 case-folding shapes across `ß`, `İ`, `ſ` and `K` | `re.IGNORECASE` and `casefold()` genuinely disagree, and an `.isascii()` guard is the only thing keeping every byte gate sound |
| 4 literal-fallback shapes around `Foo(` and `Foo[` | The literal fallback must stay case-insensitive; an unbalanced paren is an ordinary shell-quoting accident |
| 3 backtracking shapes at a terminating run length | See U8 — the pathological length has no derivable expectation |
| 2 shapes for a `NaN` first line | `detect_format` and `decode_jsonl_entries` use different JSON readers and disagree about whether the entry exists |
| 2 shapes for a U+001C-prefixed first line | Python `str.strip()` removes it and Rust `.trim()` does not, flipping a file between `jsonl` and `raw` |
| 4 carriage-return shapes including raw and colored | Real transcripts carry CRs constantly, and a `text=True` harness erases them; nothing was watching this |
| 3 Pi joined user-agent shapes with no `<duration_ms>` terminator | Optional in Python's grammar; a native parser that required it silently dropped these once already |
| 2 provider-column shapes, single-provider and multi-provider pools | Blind spot 3 on the inherited list |
| 2 alternate-escape searches over `&lt;thinking` and `<thinking>` | Distinguishes escaped from unescaped rendering at the search layer |
- `tests/lib.sh` — the shell suite's fixture home moved from one shared path to
  a per-run subdirectory. Two teammates running the shell suite at once used to
  delete each other's fixtures, because the shared path was wiped on every
  `source`. Verified with `test_cli_seam.sh` and `test_search_only_id.sh`.
  Tradeoff recorded: each run now leaves one small directory under `TMPDIR`
  instead of reusing one forever. A cleanup trap was rejected because
  `test_name.sh` and `test_rm.sh` install their own `EXIT` traps after sourcing
  `lib.sh`, which would silently replace it.
