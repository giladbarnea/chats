# message-renderer — RESUME

Cold entry. Nothing here assumes you followed the thread.

**The seat:** turn one message into styled lines. `Vec<Segment>` per line; the
panel frame closes around them. Highlight painting is inside this package.

**The gate:** `probes/pty_differential.py --g4 --subject <searchdriver>
--subject-takes-search-token no --widths 72`. `g4-default-matches`, `g4-full` and
`g4-matches-no-metadata` go green when the engine wires the renderer.
`g4-list` and `TIER IGNORED` are `engine-and-codex`'s wiring job, not this seat's.

## This seat also holds an oracle role

**`lexer-tables` builds the language tables on this seat's procedure, and this seat
is their interface and oracle owner.** Inherit it with the files.

**Theirs:** the generators, the tables, their gates, and the wiring steps in §4 of
`PROMOTING-A-LEXER-TABLE.md`. **Ours:** `syntax_lexer.rs`, `syntax_styles.rs`,
`syntax_lexers.rs`, the fence geometry in `session_render.rs`, and the engine's own
gate. They ask before touching ours — not to guard it, but because a change there
invalidates gates they cannot see.

**Answer freely**: the engine contract, `match_at`'s character-offset captures, why
`EXPECTED_UNSUPPORTED` is an asserted *exact* set, how a promoted family reaches
`token_style`.

**And hold it the way it was handed over: the document is the successor, not the
person.** A question that the procedure should have answered is a defect in the
procedure — fix the document rather than answering once. **A procedure that needs
its author present has not been handed off.**

**Three things to put in front of them if they have not read the procedure yet**,
in this order, because the first decides whether the rest is worth anything:

1. **Gate against Pygments' *driver*, not against a reading of it.** One table
   definition builds both sides, no second copy anywhere. A gate built from a
   reading agrees with the reading.
2. **The five generator traps are history.** Each produced a wrong answer here.
3. **The gate must assert every declared rule is reached by the corpus**, over real
   fenced blocks in the language. A perfectly transcribed table gated against
   content exercising half of it looks identical to a complete one, **and there is
   no reviewer left on the roster to catch the difference.**

---

## Stop point

**Clean. Nothing is half-written.** All five build configurations green with
**zero warnings**: `cargo check`, `cargo check --no-default-features`,
`cargo test --no-run --no-default-features`, `cargo test --doc`, and
`cargo build --release --no-default-features`.

**168 lib + 1 bin + 45 doctests.**

**Uncommitted edits from this seat:**

- `rust/session_render.rs` — new, the whole renderer.
- `rust/lib.rs` — one `pub mod session_render;` line.
- `Cargo.toml` — `markdown-it = { version = "0.6", default-features = false }`.
- `rust/codecs.rs` — `message_local_datetime` extracted so the badge's date and
  the XML attribute's share one parse. Existing behaviour routed through it.
- `rust/search_query.rs` — `Regex::find_all`, match spans in character offsets.
- `tests/data/message-renderer/markdown-oracle.json` and `body-oracle.json`.

Both changes outside this seat's file were ruled in-bounds by the first mate:
additive, existing behaviour routed through the addition, suite green either
side, announced. Review is routed to `slice-reviewer`.

---

## What is landed and gated

**Three recorded corpora, all byte-exact against Rich, all with falsifications
that fire.**

| Gate | Records | Widths |
| --- | --- | --- |
| markdown renders | **865+ of 965** compared, all identical | 13, 20, 40, 72, 120 |
| message bodies | **60 of 60** identical | 24, 40, 68, 100 |
| **whole panels, through the sink** | **168 of 168** identical | 40, 68, 100 |

The panel corpus spans 7 message shapes × metadata on/off × `--full` on/off ×
highlight on/off, built from real `SearchHit` values. Its three mutations: a sink
that never cycles the border hue, one that ignores `--no-metadata`, and one that
lays the body out at the console width instead of the interior.

The markdown corpus is 180 cases — curated shapes plus 120 real message text
blocks. The body corpus is 15 cases built from authored JSONL sessions.

**Rendering that exists and reproduces Rich exactly:** `Text` with spans, wrap,
`divide_line`, `words`, `rstrip_end`, tab expansion, `Lines.justify`,
`split_and_crop_lines`, `adjust_line_length`; paragraphs, headings, horizontal
rules, blockquotes, both list kinds, all four inline styles, links, images and
**tables** — including `_collapse_widths` and `ratio_reduce`, pinned against
Rich's own answers and reached by seven over-wide table cases; the role badge and
its chip colours; `LeftRail`; part ordering; and highlight painting.

**Tables and fence geometry are complete.** A code block whose language reaches
no Pygments lexer — an unknown tag, an empty tag, or `text` — now renders
**exactly**, which is 22.3% of real fenced blocks and 39.6% of their characters.
`rust/syntax_lexers.rs` is a generated 915-entry alias table deciding which those
are; its generator is `probes/generate_lexer_aliases.py`.

**`rust/syntax_styles.rs` is generated**: every Pygments token type with the style
Monokai resolves it to, and `token_style(path)` walking the ancestry the theme
walks. 80 entries, from `probes/generate_token_styles.py`. **This is the last piece
before a table can be promoted.**

**The lexer engine is written and gated: `rust/syntax_lexer.rs`.** Pygments'
`RegexLexer` driver — plain tokens, `bygroups`, `default`, push-one, push-two,
`#pop`, `#push`, integer pop, `using(this)` re-entry, and both no-match paths.
Gated against Pygments' **own driver** over 17 inputs: one table definition builds
both the Python lexer that produced the expected stream and the Rust table under
test, so it compares drivers rather than transcriptions.
`probes/generate_lexer_engine_oracle.py`.

**No table is promoted**, so the engine changes no rendering yet and every
stopping point is clean. `search_query::Regex::match_at` — anchored match with
character-offset capture groups — is the driver's whole interface to the engine.

**⚠⚠ THE RULING BELOW WAS RETRACTED ON 2026-08-30, HOURS AFTER IT LANDED. READ
THIS BLOCK BEFORE ACTING ON ANYTHING IN THIS SECTION.**

**Corrected product rule:** every fence language or alias that legacy `ch search`
recognises **and colours** must still receive colouring after the cutover.
*Pretty-good* relaxes **token and colour fidelity, not language coverage.** Plain
unstyled output is correct **only where legacy also rendered plain because the tag
was genuinely unrecognised.**

**So JavaScript, HTML and CSS are not an intentional unsupported set.** They need
tables. `g4-fence-never-covered` must go green **for the right reason**, not be
replaced by a behaviour assertion.

**What survives the retraction — most of it:**

- **The plain path stays, with its scope corrected to genuinely unrecognised tags
  only.** There it is *parity*, not divergence: legacy renders those plain too.
- **The `unreachable!()` guarding the one-place invariant stays.** Right
  independently of the ruling.
- **The never-refuse property stays.** A refusal panics the sink and truncates a
  printed scan; that is a defect under **any** coverage policy.

**What is now wrong and must not be honoured:**

- **`a_fence_in_an_unpromoted_language_renders_plain` asserts the wrong thing** for
  `css`, `html`, `sql`, `xml`, `yaml` — legacy colours all five. It should assert
  plain rendering **only for genuinely unrecognised tags**, and **`mermaid`, which
  I excluded for reaching no lexer, is now exactly the right subject.**
- **The comment in `pty_differential.py` telling the next reader not to restore
  `g4-fence-never-covered` must be rewritten rather than obeyed.** The row comes
  back for languages that will be covered.
- **The 2.6%–11% "accepted divergence" is not accepted.** It is the size of the
  remaining coverage gap, not of a ruled trade.

**HOLD. Do not rebuild the gate.** `search-firstmate` is returning a coverage plan
to the captain, and its shape decides which tags the gate asserts colouring for and
which it asserts plain for.

**And note the shape of what happened, because it is this desk's own L200 arriving
inside four hours: a ruling landed, was implemented, was documented as settled, and
was retracted — and the document said "ruled" with no marker that it could move.**

---

**Nothing is refused any more. Ruled 2026-08-30 — RETRACTED, see above: a fence in a language Pygments
knows and no table covers renders with complete geometry, background, padding and
plain unstyled code** — the same treatment as a tag Pygments does not know. It must
never refuse, panic or truncate. `Unsupported("fence lexer budget")` remains and
has never fired.

**Why the refusal had to go, because the reasoning is not obvious and someone will
want to restore it.** The typed refusal was right while nothing was wired to it.
Once the panel sink existed it produced a failure **strictly worse** than the
approximation it prevented: `emit` panicked, so results **streamed and then stopped
at an arbitrary point**, with the panic on stderr. A redirected run showed a
complete-looking result set that had silently been cut short. Measured by
`engine-and-codex`: 20,700 bytes and 11 panels printed before the process died.

**The accepted divergence is a range, not a point: 2.6% to 11% of fenced blocks**,
because block exposure is a property of whose sessions — a Rust project's sessions
are full of Rust fences. **Session exposure agreed across two corpora and two
methods at about one in three**, falling to 29.2% once markdown lands. That range
is what `final-change-log.md` gets assembled from.

**`g4-fence-covered-later` is a real parity row** — python is promoted, so the
native route lexes it with Pygments' own table and must match `ch-legacy`.

**`g4-fence-never-covered` was removed, and the removal is the point.** A parity
row for a *deliberate* divergence cannot pass: Python colours a CSS fence and we
render it plain, by ruling. Leaving it red would recreate the omission-dependent
state the gate spent two days removing — **an expected red nobody can tell from a
regression.** It is a behaviour assertion now, in
`a_fence_in_an_unpromoted_language_renders_plain`. The differential carries a
comment where the row was saying **not to restore it**.

**The `ColouredPanelSink` is wired.** `search_run.rs` carries the
`color && (Matches | Full)` arm. Landed by ruling after `engine-and-codex` was
taken off it.

---

## The seam the engine wires to

```rust
session_render::message_body_lines(
    messages: &[Message], width: usize, context: &BodyContext,
) -> Result<Vec<Vec<Segment>>, Unsupported>

BodyContext { metrics, highlight: Option<&Regex>, conversation_tag: Option<&str> }
```

`width` is the panel interior — console width minus four. The result is
`search_views::panel_lines`'s `body` argument unchanged. **The G4 fixture reaches
no unsupported construct**, so the three renderer cases can go green on what
exists. This seat has not touched `search_run.rs`.

---

## Queued items: both in

- **F18 is fixed and pinned.** `divide_line`'s remaining-space test is signed,
  because Rich's is: a negative fails `>= word_length` where a floor at zero
  succeeds for a zero-cell word. `wrap_tests` pins Rich's answers and carries a
  falsification that reimplements the floor-at-zero version and requires it to
  still disagree.
- **The `saturating_sub` sweep is done and written up** in
  `M3-signed-subtraction-sweep.md`: one fixed, four checked safe with the reason,
  three recorded as reachable only below a console width of eight.
- **The rail fix is in, at the mechanism.** `LeftRail` renders its child under a
  context whose `highlight` is `None`, so no rail child can be painted from any
  caller — which answers the unrun grep about tool content by construction rather
  than by inspection.
- **The plan is a tool part**, not a fifth `Part` variant:
  `ToolPart::{Real, ExitPlanMode}` under one `Part::Tool`, so the correct tool
  renderer cannot grow a second one beside it.

---

## Next, in order

**The critical path no longer runs through this seat.** It is: confirm the fallback
tag set → cutover.

1. **⚠ OUTSTANDING, and it is the one thing this seat owes.** The fallback gate's
   representative tag set is **my choice, not the owner's**. The captain's
   instruction was that it come from `lexer-tables`, who hold the per-language
   corpus figures. I used `css`, `html`, `sql`, `xml`, `yaml` as an interim set and
   asked them to confirm or replace it. **`mermaid` is deliberately excluded** — it
   reaches no Pygments lexer at all, so it would pass for the wrong reason.
   **ANSWERED 2026-08-30 by `lexer-tables`, from the corpus.** Under the corrected
   rule the set is *tags legacy leaves plain* — tags reaching **no** Pygments lexer
   at all. Measured over 36,539 real fenced blocks: **401 blocks, 1.1%, across 29
   tags**, led by `just` (184), `tsv` (65), `mdx` (39), `mermaid` (26).
   **Use `mermaid`, `just` and `mdx`** — the commonest, one that looks like a real
   language, and one that looks like a language we support but is a different tag.
   **My interim five are all wrong**: legacy colours every one of them.
2. **Markdown's named callback**, if anyone wants it. **No longer a blocker**: by
   the ruling, markdown is unported and therefore renders plain like everything
   else, so promoting it is a coverage improvement (35 occurrences, 34.1% → 29.2%
   of sessions) rather than a dependency.
   - Its nested fenced code falls under the fallback, **so the second
     `GroupAction` that was costed is not needed.**
   - What remains is `Action::Callback(MarkdownCodeBlock)`: five fixed groups and
     the info string. **Engine work, so this seat's**; the table, corpus and gate
     stay `lexer-tables`'.
3. **Tool bodies**, still unbuilt and still only reached under `--tools`.
   `render_tool_rich`: the `⏺`/`⎿` header whose key argument is elided at the width
   it renders at, the accent rail, the Edit diff, and the `Read` result lexed by
   **file extension** rather than a fence tag.

**Six families are promoted by `lexer-tables`**: TypeScript, TSX, Bash, Python,
JavaScript, JSON. `PROMOTING-A-LEXER-TABLE.md` is the procedure and it has been
used, corrected and extended by them — read it before touching a seventh.

**Engine additions this seat made for them**, all gated: `LexerFlags` on
`LexerTable` with `Regex::compile_with_flags` (**bash, python and markdown are
`MULTILINE` alone, not `MULTILINE|DOTALL`** — a `.` crossing a newline is silent),
`Regex::match_at` (anchored, character-offset captures), and
`RichText::append_tokens` (**no control-code strip, because `Syntax.highlight`
appends through `Text._text` and Rich does not strip inside a fence**).

---

## Findings on this desk

- `M1-link-nondeterminism.md` — the oracle is not byte-deterministic on markdown
  links. Accepted; every comparator over real bodies normalises `id=<digits>`.
- `M2-parser-equivalence.md` — the `markdown-it` crate against `markdown-it-py`,
  19,977 of 20,000 real text blocks identical after five named conversion rules.
- `M3-signed-subtraction-sweep.md` — above.

## Facts that cost someone a measurement

- **An empty `Style` is falsy in Python**, so `Text.append` adds no span for it —
  and a span, even an empty one, cuts a run into separate segments. 690 of 775
  records on the first pass. Identical text, different structure.
- **`Text.render` yields its segment even when the text is empty.** That empty
  segment is how a horizontal rule produces the blank line after it.
- **`justify = self.justify or options.justify`** — the text's own setting wins,
  because `"default"` is a truthy string. Markdown never sets `options.justify`,
  so only a table tells the two orders apart.
- **Highlighting is per segment**, so a term straddling a style boundary is left
  unpainted, and **nothing inside a rail is highlighted at all**. Both are wrong,
  preserved, and captured as fixtures with failure messages saying that a port
  which paints them is *better* and diverges.
- **`BlockQuote` renders its child at `max_width - 4`** while its prefix is two
  cells. `LeftRail` reduces by the glyph's length in code points.
- Inline code is padded one space each side by `PaddedInlineCodeMarkdown`, which
  mutates the parsed tokens before rendering.
- Outside a fence, markdown output is attribute-only. Inside, a Monokai
  background on every cell plus a per-token foreground.
- Palette colours — `markdown.h2`, `h3`, `item.number`, `link`, `block_quote`,
  the table border — are tier-invariant at every depth, truecolor included. The
  `markdown.code` override is a truecolor pair, so **one message body exercises
  both resolution paths**.

## The two rules this seat contributed

**A new construct is an instrument.** Adding tables tested markdown. The
`justify` precedence was backwards and 800 records passed on an accident, because
markdown never sets `options.justify` and so the discriminating input did not
exist in that corpus. **No amount of looking at the markdown corpus would have
shown it** — the gap closed by extending the *subject*, not the corpus. Held at
team level by `search-firstmate`; recorded here because it was found on this
surface and the next person on this seat will add constructs.

**Two fixtures that between them look like coverage and share no case.** The rail
divergence existed because there was a thinking case and there were highlight
cases and no thinking case *with* a highlight term. Each fixture was honest about
what it covered; the gap lived only in the join, where nothing in either
description revealed it. It arrived in a corpus built *after* reading about two
earlier fixture-blindness instances, because those rules were about a single
fixture's blindness and this is about a pair's.
