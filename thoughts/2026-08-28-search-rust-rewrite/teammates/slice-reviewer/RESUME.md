# slice-reviewer — cold-entry resume note

Current as of 2026-08-29. **Nothing is half-written and no production file carries
an edit by this seat, by design.**

---

## Who you are

The **third reviewer seat**, approved at L49. Your prompt is
`prompts/slice-reviewer.md`.

**The one rule: you edit no production source and no tests.** Findings go to
`search-firstmate`, who routes them. Your value is having no stake in any answer
being right — `decision-record.md` entry 2, which also forecloses converting you
to an implementer.

**Write only inside `teammates/slice-reviewer/`.** The desk entry
`g3-review-slice-reviewer-01.md` is a **symlink** to this directory, so a
correction after promotion is live immediately and needs no request. Do not run
`memo`. Do not write under `.optmem/`.

## Scope, and where it stands

The original six files were narrowed mid-session when `context-curator` took back
`plan.rs` and `cells.rs`. **The narrowed scope is covered**, with one deliberate
exclusion stated rather than left to be inferred.

| File | Depth |
| --- | --- |
| `python_io.rs` | **Done.** 81 lines. |
| `color.rs` | **Done**, including the `StyleColor` enum that landed under this seat on 2026-08-29. |
| `session.rs` | **Done.** All 1,692 lines: detection, decode, provider selection, facets, Claude branch resolution, the Claude decoder, and the whole Pi half. |
| `codex.rs` decoder | **Done.** Lines 40–500 — decode, ordering, error paths, post-edit. |
| `codex.rs` script parser | **Done**, lines 500–820. Four divergences, all measured at zero over 17,106 generated scripts. |
| `search_output.rs`, `search_engine.rs`, `search_run.rs` | **Done** as they stood on 2026-08-29 — the bonus engine surface. `search_run.rs` has since gained the `ColouredListSink` wiring, and `session_render.rs` is new. |
| `plan.rs`, `cells.rs` | Read before the narrowing. `plan.rs` produced F2, handed to `context-curator`. `cells.rs` produced nothing. |

## Also delivered

**`renderer-review-criteria.md`** — nine criteria for `message-renderer`, written
**before** `session_render.rs` exists, each naming the mutation that should break
it. Two items in it are findings rather than criteria:

- **A tenth preserve-because-wrong behaviour.** A search term split across a style
  boundary is **not** highlighted — `HighlightedMarkdown` re-styles per rendered
  segment, so `hello` against `**hel**lo` matches neither segment and nothing is
  highlighted. **The most likely of the ten to be silently fixed**, because the
  natural implementation is more useful and nobody reviews a highlight as a
  defect. It also composes badly with the branch's one blocker: the natural better
  version is the lower-then-index pattern that aborts on `İ`.
- **`chop_cells` is unported and this renderer is its first consumer.** Correct
  until now — the search views clip and never wrap. The message body is a Markdown
  inside a Panel, which wraps. Its single-cell fast path slices by **code points**,
  a fourth counting unit arriving in the file that holds the other three.

**`designed-mutations.md`** — the wrong implementations for the five gates whose
outputs are verdicts rather than bytes, written against L9 so each names what the
failure message must say. Outcomes so far, all run by `reviewer-profiler`:

- **`calibrate_harness` passes the null probe** — but *by construction* rather than
  by design, and they have commented `_blind_dimensions` to say so.
- **`tool_visibility_oracle` has one of four discriminators.** The alphabet is
  `['Bash', 'Read']` — two names is not an alphabet, it is a pair. Prefix and case
  pairs absent; both are live behaviours; 7,315 cases test neither.
- **`colored_width_gate`'s M3 was wrong and is replaced by M3′**, then resolved:
  the gate's query returns one session whose longest body line is 36 characters, so
  **reflow is unanswerable with this gate**. The requirement is a fixture with a
  visible body line of 117–196 characters.

**The rule that came out of it, in `reviewer-profiler`'s better form: capacity in
the corpus and capacity in the cases a gate actually runs are different
quantities.**

## Also delivered

**`held-parameters-answers.md`** — the outside answer to the two questions
`reviewer-profiler` states they cannot ask about their own gates, computed from
`frozen_reference.json` with no mutation and no re-run. It reproduces three of the
desk's existing conclusions from the frozen data alone, which is why the two new
results are trustworthy:

- **The stderr freeze cannot tell `NO_COLOR` from `TERM=dumb`** — byte-identical
  there — while `color.rs` documents them as two of three distinct rendering
  states. Named mutation: collapse `AttributesOnly` into `Suppressed` in the stderr
  console and the baseline stays green. Fixture fix: one stderr shape carrying an
  attribute.
- **Two of six capability tiers are byte-identical** (`16 colour` == `8 colour`,
  because Rich maps both to `ColorSystem.STANDARD`) — the empirical proof that a
  chosen parameterization collapsed.
- **The `stderr` dimension already held L17's evidence** — three of its four shapes
  are identical, which is `--color` not reaching stderr. The instrument recorded
  it; nobody asked the data that question.

It also proposes a **third question** beside their two: does an input's response
distinguish it from every *other* input, or only from the baseline?

## The correction chain on the stderr finding — read this before quoting it

Three claims, two of them wrong, and only a measurement reopened the question.

1. **Mine, and it holds:** the freeze cannot separate `NO_COLOR` from `TERM=dumb`
   on stderr. Confirmed at 37B vs 37B.
2. **My proposed fix, wrong:** "add a stderr shape carrying an attribute."
3. **`reviewer-profiler`'s correction, also wrong:** ruled impossible, from the
   three stderr consoles' styles — none of which carries an attribute.
4. **`views-and-colour` settled it by running the mutation: 9 of 135 red.** The
   attribute does not come from the console style; it comes from the **message
   content**. Rich's `repr.brace` is bold with no colour, so any message containing
   `[ ] { } ( )` separates the two states.

**Plus a second separator neither reviewer had:** `TERM=dumb` pins Rich to 80
columns *before `COLUMNS` is read*, so the states also diverge on **wrapping** — 13
of 27 case-slots. A stderr freeze captured only at 80 is blind to that too.

**Actionable form:** the stderr freeze needs an entry whose message carries a brace
**and** capture at a width other than 80. Both are natural product output.

**The lesson to carry:** two reviewers reasoned from the console styles and reached
opposite conclusions, both wrong, because the attribute enters one layer down.
22y — a claim confirmed only by reading is a lead, not a result — cost two rounds
among people who all know the rule.

## The renderer review — where it got to, and what is left

**Assigned half: the wrap engine and part ordering.** The badge and chrome are the
other half, reachable by the byte differential over recorded renders.

**F17 — the rail's text is painted where Python does not. Live, routed.**
`session_render.rs:1941–1949` paints a `LeftRail` whose child is a `Text`.
`formatting.py` passes `highlight_regex` at exactly two sites, 334 and 336 — the
message text and its escaped form. **Every rail is built without it**: thinking
(340), subagent task (344), tool content (283), Read output (213), edit diff (174).
So a search term in a thinking block is highlighted natively and plain in the
product. **Preserve-item-10's shape a second time, same file, same direction: the
port highlights more.**
*Unchecked and named:* whether the `highlight` flag can be true for a rail-wrapped
`Markdown`, since Python's :283 does not highlight tool content either. One grep.

**F18 — `divide_line` saturates where Python goes negative.** Rich:
`remaining_space = width - cell_offset`, **plain subtraction**. Rust:
`width.saturating_sub(cell_offset)`, **which floors at 0**. They differ when
`cell_offset > width` **and** `word_length == 0`: Python's negative remaining fails
`>= 0` and inserts a break; the Rust's `0 >= 0` succeeds and inserts none.
**Reachable** because `words()` yields `\s*\S+\s*`, and a `\S+` run made only of
zero-width characters measures 0 cells — so an overlong unfoldable word followed by
a zero-width-only word breaks differently. **Not measured for corpus reachability.**

**Checked and correct in this half:**

- **Part ordering matches exactly** — subagent task, text, thinking, tools, plan,
  against `model.py:268`'s `iter_visible_parts`, which is Python's stated single
  source of truth for ordering.
- **`visible_parts` not re-checking `show_plans` is safe**, because
  `visibility.rs:545` clears the plan during projection. The "already projected"
  claim in its comment holds; I checked rather than accepting it.
- **`Regex::find_all`'s doctest reproduces CPython exactly** — `[(0,1),(1,2)]` for
  `i` in `İi` and `[(1,3)]` for `ff` in `ﬀff` — and the pair pins both halves of
  "`re.IGNORECASE` is not `casefold()`" in one place.
- **The `İ`/`ﬀ` guard is closed by construction.** The `Text` model holds
  `characters: Vec<char>` and every span is an index into that same vector. **There
  is no second representation to index with the wrong offsets.**
- **The preserve-item-10 fixture is sound**, and would **not** go red on a wrong
  port — correctly: it is a corpus-adequacy test and the discrimination lives in
  the differential over the same recorded lines.

**A pre-implementation note, recorded before the work rather than after.**
`Part::Plan` renders as `Renderable::Unsupported("plan")` — an acknowledged gap.
**Python has no plan part kind at all**: `model.py:336` emits the plan as a
`MessagePartKind.TOOL` carrying `ToolParts(tag=tool-input, attrs=[("name",
"ExitPlanMode")])`. **So the correct implementation routes it through the tool
renderer with a synthesized `ToolParts`, not through a new plan renderer.** Writing
a plan renderer produces different chrome, and the Rust's fifth `Part` variant is
what invites it.

**Not reviewed in this half:** everything in `session_render.rs` outside
`divide_line`, `visible_parts`, `paint_highlight` and `Text::render` — including
`markdown_segments`, `split_and_crop_lines`, `adjust_line_length`, the badge, the
panel chrome and the tool renderers. **2,380 lines; I read perhaps 400.**

## Standing assignments

1. **Review `message-renderer`'s work as it lands.** They are the critical path,
   the largest single body of code in the mission, and **they have no other
   reviewer**. `rust/session_render.rs` did not exist as of 02:30 on 2026-08-29.
   **This takes precedence over everything else the moment a slice appears.**
2. **`views-and-colour`'s named successor for the oracle role**, if their handover
   trigger fires. That takes precedence over both.
3. `designed-mutations.md` is delivered; `reviewer-profiler` runs them.

## Resume here

1. **The engine surface — half done.** `search_output.rs` lines 390–650, the
   candidate-gate half, is **read** and produced F14. **Still unread: the sinks,
   `rule`, `metadata_block`, `displayed_messages`, and all of `search_engine.rs`
   outside the scan loop.** Against **non-timing** criteria — the timing economies
   are `context-curator`'s and are closed. They also covered the two
   hand-maintained flag lists at `search_output.rs:397` and `:573`.

   *Criteria still unchecked on that surface:* a mid-window filter error flushes
   the accumulated window before printing; the provider column reads discovery
   rows rather than gate survivors; highlight painting never indexes the original
   string with offsets measured on a lowered copy; empty pool exits 1; and the
   `Outcome`-to-exit-status mapping.
2. **`reviewer-profiler`'s two questions over `held-parameters.md`** are still
   unanswered by this seat, and they asked directly. Derived-or-chosen, and
   whether the subject responds to each swept dimension.
3. **The `codex.rs` script parser**, if the first mate wants it.

## What you found

Thirteen divergences, in `g3-review-slice-reviewer-01.md` with the coverage limit
at the top. **The classes matter more than the count.**

### Live today — one

- **F14** — the same unreadable file produces two different error lines, and the
  comment at `search_output.rs:591–593` says it produces one. Python's serial gate
  prints `Permission denied (os error 13)` (a **Rust**-shaped string, because the
  message comes from Rust through PyO3); the native route defers to confirmation
  and prints `[Errno 13] Permission denied: '/p'` (a **Python**-shaped string,
  because `python_io_error` models `OSError.__str__`). Executed both halves on a
  `chmod 000` file. The batched arm's comment four lines away is correct. Needs no
  unusual content, only an unusual file state — a permission change, a `.jsonl`
  path that is a directory, or a file removed between discovery and scan.

### Live blast radius on a scheduled refactor — one

- **F12** — `codex.rs:278` and `session.rs:1137` hold **different** `has_content`
  predicates; the Codex comment says they are the same and proposes promoting the
  **wrong** one into `model.rs`. `session.rs` matches Python's truthiness,
  `codex.rs` uses `is_some()`. Unreachable inside `codex.rs`, which is why the
  differential is green. **Measured: 12,911 Claude assistant entries** would be
  resurrected by that promotion, and each shifts every following message index.
  Needs `show_thinking`, which defaults off, so that is a population rather than a
  per-invocation impact. **The fix is to promote `session.rs`'s version instead.**
  Routed to `engine-and-codex`; `session-core` owns `model.rs` and is stopped, so
  the warning is recorded rather than delivered.

### Latent — correct today, no trigger

- **F10** — Claude tool-name normalisation happens at a different stage from
  Python's; they agree only because `TOOL_NAME_ALIASES` has no `"claude"` entry.
- **F8** — `isError` uses strict `bool` where Python uses truthiness, in the same
  expression whose *other* operand correctly uses `value_is_truthy`.
- **F9** — the Pi `toolResult` content default models a state Python cannot
  produce. `codex.rs` carries the fix one path away, which is what makes it a miss.
- **F11** — `StyleColor` is correct, has no caller and no test of tier-invariance.
  Routed to `views-and-colour`.
- **F13** — three absent-key defaults on the Codex path.

### Real but corpus-invisible — the class this seat produced most of

- **F1** — `python_io::read_text` skips universal-newline translation. One root
  cause, one fix site, two consequences; the second lands on `raw_transcript.rs`,
  the one module the real corpus provably cannot grade. **Rank this first for a
  fixer.**
- **F5** — `command_tag_regex` lost Python's backreference, so any close tag closes
  any open tag and a message can disappear. Measured at **zero** over 4,128 user
  text blocks, with the probe proved able to fire. One-directional by
  construction: the native route can only hide more, never less.
- **F4 / F4b** — `str::lines()` is not `str.splitlines()` (ten separators against
  one), and the crate's `\s` is not Python's `re` `\s`. Four `\s` sites in
  `session.rs`, none of which could appear in `session-core`'s `.trim()`
  enumeration.
- **F7** — `dedent` is not `textwrap.dedent`. Corrects two of `session-core`'s
  three "correctly bare" exceptions, wrong in opposite directions, plus a
  mid-codepoint slice that panics.
- **F6** — `expand_tabs` is a flat 4 per tab against Python's tab stops.
- **F3** — `branch_map` keys by "non-empty string" where Python keys by presence
  and truthiness.
- **F2** — for `context-curator`: the `plan.rs` lazy/eager drift guard cannot fail.

### Outside the classes

**The C0 measurement correction.** `session-core`'s "0 occurrences of U+001C-001F"
was over **raw file bytes**; over decoded string values the pool carries U+001C
8,044 times. Their **edge** measurement — the one the ruling actually depends on —
re-runs at 0, so L47's ruling stands and only its premise was marked wrong.

## Method notes worth keeping

**L86, from this seat's own report:** a method's null result is informative only if
the method could have found a non-null one by a route the existing gates do not
already cover. Pattern-matching built-in mismatches cannot surface a common-path
defect, because a differential would have caught it first.

**One data point landed on the other side of that**, and it is worth as much as any
finding: `tool_from_json` keeps only three keys where Python keeps the whole item
dict — and the 2,436-case Claude differential *does* cover that path, so it was
correctly **not** reported.

**The invariant-first form of criterion 5 is what found F12**, in about ten
minutes: start from the invariant list and ask which invariants have no test,
rather than auditing tests for falsifiability.

**L103, the rule inside F12:** criterion 5 asks whether a test would go red; this
asks whether **a claim in the code is true**. A test at worst fails to catch
something. A false comment actively directs the next change.

## The standing weakness

**You ran no Rust.** Every verdict is reading the Rust against the Python plus
execution of the **Python** half. Nothing is confirmed against the built artifact,
and F4b's Rust half rests on the `regex` crate's documented `\s` rather than on
execution. If a build window opens, a scratch binary exercising
`command_tag_lines`, `dedent` and `expand_tabs` would upgrade three findings at
once. **Announce before building — `target/` is contended.**

**And the tree moves under you.** `color.rs` grew a `StyleColor` enum mid-review
and `codex.rs` gained the whole engine. Read what is there, not what these notes
describe.

## Instruments

`probes/` holds ten read-only scans, in the tree rather than in a scratchpad (L1,
L23). Each prints what it covered, not only its verdict (22x).
`f5_backref_scan.py --falsify` is criterion 5 applied to a probe: it proves the
instrument can fire before its zero is quoted.

## Who you may talk to

`engine-and-codex` is uninterruptible — route through `search-firstmate`.
`reviewer-profiler` is your peer, not your subject. `session-core`,
`search-runtime` and `contract-owner` are stopped above 87% under an admiral
order: one narrow question each, inside their own ownership, only if the tree
cannot answer it.

## Context

**41% of the context window used** at the time of writing. The session token budget
is not the constraint. Report the window figure and name which quantity it is.
