# views-and-colour — handoff

**Role as of the captain's Option A ruling: oracle and interface owner.** A new seat,
`message-renderer`, builds the styled message renderer. I own `cells.rs`, `color.rs`,
`ColouredListSink`, the pty differential and the stderr corpus; I answer interface
questions and read gate output. **I do not write the renderer, and they do not touch
these modules without asking.** The boundary is the captain's and holds both ways.

Written cold. Nothing here assumes you followed my thread.

**Context: 75% of the context window used** — a harness reading, taken when this line
was written. Roughly a quarter left. Earlier figures in this brief's history were
extrapolations wrongly labelled as measurements and were withdrawn. I cannot query a
reading on demand, so once this one is stale I say it is stale rather than deriving a
newer one.

Oracle revision `8cb4c5f`.

**Verified at the stop, not asserted:** `cargo check`, `cargo check --no-default-features`
and `cargo build --release --no-default-features` all green; **148 lib + 1 bin + 43
doctests**, zero failures. My own modules are `color` 5, `cells` 7, `search_views` 12.
`search_views.rs` byte-matches its pre-mutation backup and the two mutation anchors in
`color.rs` and `cells.rs` are intact, so no falsification edit was left behind. The
whole-suite counts move under me — this is a shared checkout with several sessions
editing.

---

## 1. What you own

Four things, two landed and two waiting:

| Package | State |
|---|---|
| **The colour seam** — `rust/color.rs` | Landed, gated, falsified |
| **The chrome** — `rust/search_views.rs`, `cells.rs`, `cell_tables.rs` | Landed, gated, falsified |
| **The coloured list sink** — `ColouredListSink` | **Landed, gated, falsified** |
| **The conversation panel and highlight painting** | Blocked on a styled message renderer that **does not exist** |
| **The four stderr consoles** | **Landed and gated on all 135 cases.** |

The **plain** output modes are `engine-and-codex`'s. The pager is the engine's and must
never be visible from views. `session_render` is `session-core`'s — you draw the frame,
they fill it.

---

## 2. Production files, all mine, all uncommitted

| File | Holds |
|---|---|
| `rust/color.rs` | Rich's `Color.downgrade`; `ColorRendering`; SGR parameters |
| `rust/cells.rs` | Rich's cell measurement: `cell_len`, `set_cell_size`, `split_text`, `truncate_to_cells` |
| `rust/cell_tables.rs` | **Generated.** 21 Unicode width tables, 7,045 ranges. Do not edit — regenerate with `probes/generate_cell_tables.py` |
| `rust/search_views.rs` | The four display helpers, the styled-line model, list row, summary, panel title, panel facts line, panel frame, **and `ColouredListSink`** |
| `rust/lib.rs` | Four lines of module declaration. Nothing else in that file is mine |

In-crate tests: `color` 6, `cells` 8, `search_views` 18. Suite: **173 lib + 1 bin + 47 doctests**.

---

## 3. Proof held

| Gate | Scope | Result |
|---|---|---|
| colour downgrade | 1,499 oracle rows, EIGHT_BIT + STANDARD | 0 mismatches |
| cell measurement | **20,056** recorded Rich answers, **4 distinct** Unicode oracles | 0 mismatches |
| display helpers | 597 recorded Python answers | 0 mismatches |
| list row, end to end | **43,680 rendered lines** vs Python's bytes, 13 widths | 0 mismatches |
| panel frame | 2,275 lines vs Rich's bytes, 7 widths | 0 mismatches |
| whole panel | **11,200 lines** vs Python's bytes | 0 mismatches |
| **the sink, from real hits** | **21,840 rendered hits**, gating the projection | 0 mismatches |
| **stderr consoles** | **135 recorded cases**, 5 colour tiers x 3 widths | 0 mismatches |

Every gate ships a falsification. **Nineteen mutations, each a port somebody would
plausibly write, all caught, and all now replayable:**

| Harness | Covers |
|---|---|
| `probes/falsify_color_and_cells.py` | 8 — rounding, float redmean, the joiner path, selector 16, code-point cropping, a single hardcoded table |
| `probes/falsify_views.py` | 5 — no cell clip, byte-measured reserve, budget, age fallback, elision side |
| `probes/falsify_panel.py` | 6 — dash count, title box, border cycle, bottom border, merged escapes, interior padding |
| `probes/falsify_panelview.py` | 6 — empty segment, title budget, facts budget, strip spacing, strip clip, byte-measured suffix |
| `probes/falsify_sink.py` | 6 — falsy headline, match count, provider column both ways, absent age, summary at zero |

**The mutation lists are the evidence, not the tooling.** The colour and cell eight ran
ad hoc while those modules were built and left no durable record until now; if a gate
later stops catching one, only these tables say what it used to catch.

All thirteen probes are importable — no module-level `sys.argv` — so the mutation tables
can be enumerated without running anything.


## 3b. Two negative results, both obtained by computing them

**The stderr corpus separates `NO_COLOR` from `TERM=dumb`.** `slice-reviewer` found
that `frozen_reference.json` cannot tell them apart and the concern was routed to me as
if my corpus shared it. It does not: collapsing `AttributesOnly` into `Suppressed`
turns **9 of 135** cases red.

The mechanism is worth keeping, because it tells you what shape a fixture needs.
Rich's `repr.brace` is `Style(bold=True)` — **bold with no colour** — so any message
containing a brace carries an attribute that survives `NO_COLOR` and vanishes under
`TERM=dumb`. Three of my nine messages contain one, and those three produce the nine.
`[Errno N]` is emitted by the product on **every** per-file error, so a freeze needs no
synthetic row — and a synthetic row would be the one nobody could re-derive later,
which is the property a freeze exists to have.

The two states also separate on **width**, independently: `TERM=dumb` pins Rich to 80
columns before `COLUMNS` is read. A single-width freeze is therefore blind twice over.

**No two of the five colour tiers are identical.** `reviewer-profiler` found two of
their six capability tiers byte-identical — 16-colour and 8-colour both map to
`ColorSystem.STANDARD` — so I computed mine rather than assuming. Every pair separates
on at least **13 of 27** case-slots; the three coloured tiers separate on 15 of 27, and
the 12 that do not are the messages whose only colour is a palette index, since Rich's
`"red"` and `"yellow"` emit `31` and `33` at every depth while a themed triple
downgrades.

**Both are negative results and neither was knowable without running it.** A chosen
parameterization cannot tell you it collapsed.

---

## 3c. The interface changed for the renderer, and it is proved lossless

`Segment.style` now carries a resolved `Style`, not a theme-token name. `message-renderer`
asked for it and the reason is sound: markdown styles **compose** — `***both***`, a
`**bold**` inside a blockquote, a heading's style under its inline styles, the search
highlight over any of them — and that space is not enumerable as tokens. Worse,
`theme_style` **panics** on an unknown token, so the old model's failure mode was
aborting mid-render on arbitrary user content.

`Style` is Rich's shape: `Option<bool>` per attribute plus `Option<StyleColor>` for
foreground and background, with `over()` as `Style.__add__`. It is the stderr half's
`ResolvedStyle` **promoted**, not a second type — a second style type with a conversion
at the boundary is the live fork the standing rules forbid, and the conversion is the
lossy step.

`Segment::styled(text, "search.tick")` is unchanged and resolves the token **at
construction**, which moves the unknown-token panic strictly earlier.

**Lossless is measured, not assumed:** all five byte-exact corpora compare identical
after the promotion — 43,680 row lines, 11,200 panel lines, 2,275 frame lines, 21,840
sink hits, 135 stderr cases.

## 3d. `chop_cells`, and a fast path that is provably an optimisation

Added for `message-renderer`'s wrap port, with `split_graphemes` and
`is_single_cell_widths` made public. I had scoped it out as unneeded because views uses
`no_wrap`; "minimum code" was the wrong call once it had a consumer.

Rich's fast path slices by **code points** where the grapheme walk counts cells — a
fourth counting unit in that file. Removing the fast path entirely changed **nothing**
across 20,056 cases, which could have meant a thin corpus. It does not: **every
codepoint in Rich's fast-path ranges is exactly one cell in all 21 shipped tables**, so
the two agree by construction. That is now a test rather than a comment, and if it ever
fails the function has acquired a real second behaviour.

**So the fourth counting unit is real in the source and inert in effect** — unlike the
other three, which all move bytes.

---

## 3g. Three fixes after the sink was wired, all found by the gate

**`g4-list` is GREEN** — zero differences through the real native route under a pty,
across five colour tiers and two clock instants. The third of the G4 gate that needed
only wiring. **The remaining red is the three panel cases and nothing else**, so the
gate is now exactly the renderer question.

**Tabs.** Python expands a literal TAB **at render time**, to absolute 8-column stops
across the assembled line, and **splits the styled span at each one** — Rich emits the
padded run and the following text as separate escape pairs with the same style and never
merges them. `expand_tabs` lives in `render_line`, so the list row, panel body and top
border are covered together. Idempotent on tab-free input.

**The guards were lying.** `clock_responsiveness` and `tier_responsiveness` probed a
single hardcoded case and reported a conclusion about **the route**, so they could not
tell *the subject ignores this input* from *this case cannot express it*. That is a claim
whose scope is wider than its evidence — in a guard built to catch that shape. Now per
case: a dimension is swept when **at least one case responds**, and the run prints which
cases are inert and which are live. The diagnosis came from the gate's own printed
numbers; a guard that printed only a verdict would have been believed.

**The panel corpus proved its padding by luck.** Every body line in it was plain text, so
"the frame pads with unstyled spaces" was indistinguishable from "the padding inherits
the body's style". Found by `message-renderer` asking, not by me. A styled short body is
now in the corpus (875 panels, 2,800 lines) and the mutation that makes padding inherit
the style fails on **1,050** of them.

**Five counting units in this surface, none of which may be unified:** code points in
`elide_to_width`, code points in `truncate_middle`, UTF-16 units in Pi's preview, cells
at 8 in `Text`, characters at 4 in a fence via `str.expandtabs(4)`.

## 3e. `Segment` carries a link, and one condition is recorded before it can bite

`Segment { text, style, link: Option<Link> }`, where `Link { url: String, id: u32 }`.
A **field** rather than a parallel structure so a run and its URL cannot be separated,
and **out of `Style`** because a `String` there would cost `Style` its `Copy`, which
chrome depends on everywhere. `link` is `None` throughout the chrome; only message
bodies set it.

**OSC-8 wraps *outside* the SGR pair.** Measured, not read — `message-renderer` had it
inside and it would have cost them a rebuild:

```
\x1b]8;id=893615;URL\x1b\   \x1b[4;34mthe docs\x1b[0m   \x1b]8;;\x1b\
```

`Style.render` builds the styled string first and wraps the finished thing, so two
things follow: a link on an **unstyled** run still gets the pair, and a **dumb terminal
emits no OSC-8 at all**, because `Style.render` returns the text untouched when there is
no colour system and the link never gets to wrap. `ColorRendering::Suppressed`
short-circuits before the link, deliberately.

### ⚠ Standing condition: the day a corpus grows a link, a gate will look defective

Rich's link id is `randint(0, 999999)` **per render**, so byte parity on link-bearing
content is impossible even for Python against itself. **None of the five corpora
contains a link today, so none normalises `id=<digits>`.**

So: if a recorded case ever grows a link — a session title with a URL, a directory that
parses as one — the affected gate starts failing **intermittently**, and it will look
exactly like a real defect. **Normalise `id=<digits>` on both sides before believing
it.** Written down before the condition exists rather than after it bit someone.

## 3f. The one time I edited another owner's file

Adding `link` broke all 16 `Segment` literals in `session_render.rs`. I inserted
`link: None` at each and nothing else, verified the diff contained no other line,
announced it immediately and offered to revert.

The first mate ruled it and the rule is narrow: **a compile break you caused is yours to
close, in whatever file it lands, provided the fix is mechanically entailed, the diff
contains nothing else, and you announce it.** Not permission to edit another owner's
file — a prohibition on leaving a break you created for someone else to find. The
reason it is safe to grant is that all four conditions are checkable, and the reason it
was granted at all is that it was asked rather than assumed.

---

## 4. The seam to the engine

Agreed with `engine-and-codex`. `HitSink::emit` takes `&SearchHit`, not a rendered
string, because rendering needs the ordinal and confirmation cannot know it.

```rust
list_row(&ListRow, home: &str, width, &CellMetrics, ColorRendering) -> String
list_summary(count, width, &CellMetrics, ColorRendering) -> String
panel_lines(&[Segment] title, &[Vec<Segment>] body, ordinal, width,
            &CellMetrics, ColorRendering) -> Vec<String>
panel_title(&ListRow, width) -> Vec<Segment>
panel_facts_line(&ListRow, home, width) -> Vec<Segment>
```

They return `String`/`Vec<String>` and touch no I/O. The engine owns the sink and the
early-close check.

- **`ordinal` is yours to count**, incremented per `emit`. It drives the four-hue border
  cycle.
- **`finish` is called unconditionally except when the reader has gone.** You suppress on
  mode, colour and count; the not-closed half stays with the pager, which is not yours.
- **Build `CellMetrics::from_environment()` once per process and thread it.** Do not
  re-read the environment per call.
- **Resolve `ColorRendering` from the stdout capability.** stderr resolves separately.
- `ListRow` is a small borrowed struct so views does not depend on the engine's type.
  Project `&SearchHit` into it at the call site.

**`headline()` is theirs and my gate does not cover it.** My oracle records the pair
Python's `_headline` *derived* and feeds that in, so 43,680 lines prove the row and
nothing about the fallback chain. The case that bites is a falsy-but-present title:
an empty custom title falls through to `(untitled session)` in the italic fallback
style.

---

## 5. What must not be changed

**Do not unify `AGE_UNITS` with `age_style`.** It is the obvious simplification, it
repaints every coloured row, and it is the highest-risk item on the mission because the
fixtures normalise the label and the comparators normalise the colour. Two independent
gates now fail on it — `reviewer-profiler`'s `age_pairing_gate.py` and my 76-of-597.

**Do not repair the other three preserved behaviours.** `collapse_home` matches a string
prefix, not a path boundary. `elide_to_width` counts code points, not columns.
`humanize_age` uses 30-day months and 365-day years. Each is marked at its definition
and each has a mutation proving the gate catches its repair.

**`--color never` still colours stderr, and that is preserved.** The flag reaches
stdout's console and none of the three stderr ones; stderr colour follows stderr's own
tty-ness alone. A port that resolves the choice once and applies it to all four consoles
is correct and diverges. **A fourth stderr console at `formatting.py:698` does the right
thing**, so the correct pattern sits one file away from the three wrong ones — whatever
comment you leave has to survive a reader who has already found it.

**The list row's `width - 2` headline budget is inert** — measured at every width from 2
to 129, it never changes a byte, because the outer cell clip subsumes it. Kept because
Python has it. `the_headline_budget_is_subsumed_by_the_outer_cell_clip` pins that it
stays inert. **The panel's title budget looks like the same expression and is
load-bearing** — a mutation ignoring the metadata suffix is caught on 1,048 lines. Do not
reason from one to the other.

**Two truncations stack and count different units.** `elide_to_width` clips by code
points, then Rich clips the assembled line by cells. Both are load-bearing. A port with
only the first is correct at every ASCII width and wrong on the first wide character.

---

## 6. The instruments, and their defaults

**Last run: 140 comparisons across five colour tiers, both streams on separate ptys,
zero differences.** That is the instrument working, not a parity result — see the caveat
below.

`probes/pty_differential.py` drives both routes under real ptys. Sweeps **width** (40, 60,
120 — never 80, which is Rich's fallback, never 96, which every recorded coloured case
pins; both are refused with an error rather than a comment), **clock** (7 instants), and
**colour tier** (5). Both streams captured on **separate** ptys.

Three guards, each against a vacuous pass:

- **Determinism** — the reference is captured twice per case and a route differing from
  itself fails before anything is compared.
- **`clock_responsiveness()`** — a route ignoring `CH_NOW` yields one outcome across seven
  instants and the sweep checks a seventh of what it reports.
- **`tier_responsiveness()`** — same, for the five colour tiers.

**Both of my instrument's defects today were inherited defaults, not code I wrote.**
`pty_harness.run_at_width` sends stderr to `DEVNULL`, so the stream carrying the
`--color never` defect was invisible; my environment pinned `COLORTERM=truecolor`, so
every capture saw one rendering of five. **The defaults you never typed are the ones you
never questioned.** When a shared tool's defaults are what you suspect, building your own
probe is right and import-not-copy does not apply.

**A green run today is calibration, not parity** — `ch search` still falls through to
`ch-legacy`, so both sides are the same Python. The tool prints that caveat itself.

---

## 6b. G4's coloured gate — built, and RED on purpose

```
cargo build --release --manifest-path \
  thoughts/.../teammates/engine-and-codex/probes/searchdriver/Cargo.toml

probes/pty_differential.py --g4 --subject <searchdriver> \
  --subject-takes-search-token no --widths 72 --clocks 2026-09-03T10:00:00
```

The whole-route differential is blind to every coloured mode for **two independent
reasons** — it sets `NO_COLOR=1` *and* captures through a pipe, so `flags.color`
resolves false through the isatty cascade either way. One fix cannot close it. This
covers the modes that need a terminal.

**Current result: 21 failures, and each is a specification.**

| Failure | Goes green when |
|---|---|
| `TIER IGNORED` — one output across five colour tiers | the route makes any colour decision at all |
| `g4-list` | **`ColouredListSink` is wired.** It exists and is gated; `search_run.rs` wires only `PlainSink`. No renderer needed. |
| `g4-default-matches`, `g4-full`, `g4-matches-no-metadata` | the styled message renderer exists |

So the red splits cleanly: **one third of it is a wiring job with the sink already
built**, and two thirds waits on the renderer. The reference emits a coloured panel;
the subject emits a plain rule and XML frontmatter — a whole-output divergence, not a
styling difference.

**The guards no longer abort the run.** They exist to stop a vacuous *pass*; when one
fires the run fails regardless, so continuing to compare shows the divergence as well
as the blindness. Aborting hid the more useful half.

## 7. What to do next, in order

**The conversation panel and highlight painting are blocked on something that does not
exist**, and it is on the critical path. Nothing in `rust/` turns a `Message` into styled
lines — I searched rather than assumed; `codecs::render_message_inner_xml` produces XML
text. `SearchOutputMode::Matches` is the default and colour is on by default in a
terminal, so **`ch search foo` at a prompt renders panels**. The native route cannot.
Raised with `search-firstmate` as a cutover question and with `session-core`, who owns
rendering. `panel_lines` takes body lines already laid out, as `Vec<Vec<Segment>>` with
theme tokens rather than SGR literals — colours must arrive as tokens or the downgrade
cannot reach them.

1. ~~The coloured sink.~~ **Done.**
2. **Highlight painting** — blocked, see above. Fold over the **original** characters using the engine's own
   icase equivalence. Never index with offsets measured on a lowercased copy — `İ` grows
   2→3 bytes, `ﬀ` shrinks 3→2, and the drift aborts the process with exit 101. That was
   the reference branch's one blocker. Gate it across colour tiers over
   `tests/data/search-content-fuzz/`, which already carries the length-changing case
   folds; painting across tiers over content that moves byte offsets is the combination
   that finds this class, and neither axis alone does.
3. ~~The four stderr consoles.~~ **Done, all 135 cases.** Rich's `ReprHighlighter`
   paints these messages *on top of* the base style, so a port that applies a style
   and stops is wrong on every hint — every one carries a quoted term. The rules are
   **one alternation, not a pattern per rule**: `path` swallows `/x/1.jsonl` whole,
   which is the only reason `number` does not fire on the `1.` in a filename.
   `print_error` and `print_warning` have **no theme**, so their red and yellow are
   palette indices that stay `31` and `33` at every tier, while the themed hint's
   grey downgrades — which is why `color.rs` now distinguishes `StyleColor::Palette`
   from `StyleColor::Triplet`. Two items: `--color` not reaching them (preserve), and
   the native route emitting a plain hint where Python emits a coloured one (a gap to
   close). `reviewer-profiler` froze 68 Python stderr entries with per-entry digests; 34
   drift. That is the baseline. `run_at_width` now takes `stream="stdout"|"stderr"|"both"`.
   Rich's `ReprHighlighter` paints stderr — `repr.str` on the quoted term, `repr.path` and
   `repr.filename` on paths, `repr.number` and `repr.brace` on `[Errno N]` — so this is
   more than applying a style.
4. **The live pty differential against the native route**, once it exists.

---

## 8. Where things live

Everything of mine is under `teammates/views-and-colour/`:

- `probes/generate_*.py` — the oracle generators, each asserting its round trip against
  the installed Rich or Python before writing.
- `probes/*-oracle*.json` — the recorded corpora. **Imported at test time, never copied
  into the crate**: the colour table grew 1,459 → 1,499 rows within an hour, and a copy
  taken before that would still be reporting success.
- `probes/falsify_*.py` — the mutation harnesses.
- `probes/pty_differential.py` — the end-to-end instrument.

**No constant is hand-copied any more.** The seven clock instants are imported from
`reviewer-profiler`'s `age_pairing_gate.CLOCK_INSTANTS` — they moved their `sys.argv`
read inside `main()` to make that possible, and did the same across all sixteen of their
tools. `differing_between()` in my cell oracle generator runs the other way: their
`width_probe_fixture` imports mine. Keep it working.

The reason this mattered enough to do mid-flight: **two hand copies that agree do not
fail when they drift.** Both gates would have kept passing while measuring different
instants — no red, no diff, no signal — and the cost of closing it was set by *when*,
not by *what*.
