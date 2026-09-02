# Handoff: the coloured search views

For whoever takes views. Written cold — nothing here assumes you followed my
thread. I held this package's context and did not implement it, so this is
analysis rather than a status report.

Provenance: HEAD `8cb4c5f`, oracle route digest
`sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0`.

---

## 1. What views is

`ch search` renders hits two ways. Without colour it prints XML-ish text. With
colour — the default on a terminal — each hit becomes a bordered panel, or in
`--list` mode a two-line row. Views is **only** the coloured half, and only the
*search-specific* part of it.

The dividing line, which the first mate ruled and which you should not move:

- **`session_render`** turns one message into styled lines. Markdown, code
  fences, syntax highlighting, tool bodies. That is `session-core`'s, ~3,700
  lines on the reference branch, and it is the bulk of the colour problem.
- **views** owns the search chrome around it: the list row, the panel frame and
  its title, highlight painting of matched terms, and the trailing summary line.
  594 lines on the reference branch.

Reference implementation: `git show 0ffde41:rust/search_views.rs`. Read it, do
not switch the shared checkout to that branch.

**The pager is not yours.** It already landed as `rust/pager.rs`, in the
engine's dependency position, because the engine's scan loop reads `closed()` to
decide whether to keep scanning — early close is scan control, not rendering.
Views never touches it.

---

## 2. The dependency that makes this package larger than it looks

**I sized this wrongly to the first mate at first, and so did they. Do not
repeat it.**

The obvious reading is that chrome is independent of the colour-downgrade work,
because the downgrade is an algorithm — map a truecolor triple to an 8-bit or
16-colour code — and chrome just draws boxes. That is true of the *algorithm*
and false of the *decision*.

Every chrome surface emits truecolor SGR literals directly. The reference
implementation opens with about twenty of them:

```rust
const TICK_STYLE: &str = "38;2;92;200;168";
const MATCH_STYLE: &str = "1;38;2;20;24;29;48;2;230;180;80";
const ROLE_HUES: [(&str, &str); 9] = [("user-message", "113;185;244"), ...];
const BORDER_CYCLE: [&str; 4] = ["92;200;168", ...];
```

Every one of those has to route through whatever `session-core` lands as the
downgrade entry point, so the terminal's actual colour depth is honoured. That
is **a wiring dependency spread across the whole package**, not a single seam
you can stub and revisit. It is the specific reason "start it and stop halfway"
is the worst shape for this module, and the reason I declined to start it with
the context I had left.

What *is* ready for you: `terminal::resolve_color` already decides which colour
system applies, proved against a 12,096-row table generated from Rich itself,
zero mismatches. You consume its `TerminalCapabilities`. Note that
`color_system: None` (no SGR at all) and `no_color: true` (strip colour, **keep
bold**) are different states — measured, not assumed — so do not collapse them.

---

## 3. Four behaviours that are wrong and must stay wrong

A port that fixes any of these diverges from the product. In every case the
correct implementation is the natural one, which is what makes them dangerous.

**3.1 The age label and the age colour disagree by one bucket.** `humanize_age`
and `age_style` carry separate, unaligned thresholds. A row reading `1d` is
painted with the *week* colour, `1w` with *month*, `1mo` with *old* — one bucket
older than its own label, at every age. I have seen this in live output, not
just been told it.

**This is the highest-risk item in the package.** The fixture normalises the age
*label* to a placeholder and the comparator normalises the age *colour* away, so
**nothing checks the pairing**. Driving both from one table is the obvious
cleanup and it silently repaints every coloured row with no gate firing.
`age_pairing_gate.py` exists to pin the label-to-colour pairing rather than the
absolute colour; do not let it be replaced by a test that records today's
colours, which a unified table would also satisfy.

**3.2 `humanize_age` uses 30-day months and 365-day years.** Twelve months is
360 days, so an age between 360 and 365 renders `12mo` before jumping to `1y`.

**3.3 `collapse_home` matches a string prefix, not a path boundary.** So
`/Users/<home>X/dev` renders as `~X/dev`, and any sibling directory whose name
starts with the home directory's name is mangled. It reaches both the list row
and the panel title.

**3.4 `elide_to_width` counts code points, not display columns.** So wide text
overflows its own budget — `你好你好你好你好` at a budget of 8 comes back
unchanged at 16 columns. Four call sites across both views. The codebase already
counts in three different units, including UTF-16 code units in Pi
`responsePreview` truncation, so **any port that unifies them changes
behaviour**.

Note that the reference branch keeps its own copies of `collapse_home`,
`humanize_age`, `age_style` and `elide_to_width` inside `search_views.rs`,
duplicating `src/chats/utils.py`. Whether those live in views or move somewhere
shared is your call — but they must not be *corrected* on the way.

**3.5 A fourth width defect, found by `views-and-colour` after this document was
first written, and not previously logged anywhere.** `render_line` in
`0ffde41:rust/session_render.rs` is `line.iter().map(Segment::ansi).collect()` —
a bare concatenation with **no cell clipping at all**. The product wraps every
chrome line in `Text(no_wrap=True, overflow="ellipsis")`, which clips to the
console width in *cells*. Measured: at width 40 with a CJK headline the branch
emits 97 cells where the product emits 40.

Note this is a **second, independent** width defect from the `terminal_width`
one in §4 — fixing the resolver does not fix this. And note that it is invisible
to the branch's 704-case corpus for the same reason as the other three: every
case pins `COLUMNS=96`, and there appears to be no wide-character headline
anywhere in it. So the count is now **one unexamined dimension, four defects**.

That is also why §3.4 matters twice over: `elide_to_width` clips the headline and
the directory by code points, and Rich then clips the assembled line by cells.
Two clipping layers, different units, both load-bearing.

---

## 4. Which width rule the chrome uses

There are two, deliberately, and they disagree.

- `terminal::terminal_width` — Rich's rule, `str.isdigit()`. **This is the one
  views wants**, because everything views emits is Rich-rendered on the Python
  side.
- `terminal::argparse_columns` — argparse's rule, via `shutil`, so Python
  `int()`: accepts `+96`, `' 96'`, `9_6` and Unicode digits, and measures
  **stdout only**. That one belongs to help and usage text.

At `COLUMNS=+96` the help wraps at 96 while Rich-rendered output wraps at 80, in
the same invocation. A test asserts the two resolvers disagree on `+96` and
`' 96'`, so if someone unifies them it fails and explains itself. Do not reach
for `argparse_columns` in a view.

**The reference branch's own `terminal_width` is defective** — `COLUMNS` only,
defaulting to 80, which under zsh renders at 80 columns always. It is one of the
seven defects that branch carries. Use the landed resolver.

---

## 5. How to prove it

The Python implementation is deliberately still alive, so
`ch-legacy search ARGS` and `ch search ARGS` can be byte-diffed on the same
corpus. That is the whole instrument: **nothing in the new native surface is
reachable from Python**, so there is no in-process differential available for
any of it.

Requirements that came out of the day, each bought with someone's mistake:

1. **Pin the clock.** `CH_NOW`, format `%Y-%m-%dT%H:%M:%S` exactly, on both
   sides. Age appears in every list row and every panel title; without it any
   diff across them is meaningless.
2. **Drive both binaries under a pty at two or more widths, neither of them 80.**
   80 is also the fallback constant, so a diff there hides both a width defect
   and a total failure to measure. Make one width narrow enough to force elision
   in list rows and panel titles.
3. **Strip every `\r` from a pty capture, not `\r\n` pairs.** A pty emits
   `\r\r\n` when a line exactly fills the terminal; a `.replace("\r\n", "\n")`
   consumes one pair and leaves a stray `\r`, which invents mismatches at
   exactly the boundary widths where a real wrapping defect would live. This
   cost a teammate two phantom failures, and it is *not* true that a pty
   corrupts structure — I proposed that and was refuted by measurement.
4. **Re-derive a recorded table before trusting it, not just re-stamp it.** A
   digest answers "did the route change"; only re-deriving answers "was my
   recording ever reproducible". My own grammar oracle had two cases embedding
   the capture run's temp `HOME`, which could never reproduce, and a correct
   digest would have passed them.
5. **Normalise machine-specific paths** in any recorded output, and prove
   determinism by capturing twice and diffing.
6. **Every gate ships with its own falsification** — a demonstration that it
   fails against a deliberately wrong implementation. A gate that has never been
   observed to fail is not yet evidence.

Five build configurations, each catching something the others cannot:
`cargo check`, `cargo check --no-default-features`, `cargo test --no-run`,
`cargo test --doc`, and `cargo build --release --no-default-features`. The
binary is the `--no-default-features` build, and it is the one with the least
ambient feedback. Validate in a private `CARGO_TARGET_DIR`; `target/release/` is
contended.

---

## 6. Honest sizing

The chrome itself is roughly 600 lines and mostly mechanical: box drawing,
padding, elision, segment assembly.

**The cost is not the lines.** It is three things: wiring every colour literal
through the downgrade decision, reproducing four wrong behaviours precisely
while resisting the natural fix for each, and building the pty-based byte
harness with all six requirements above before you can tell whether any of it
is right.

The reference branch is prior art, not an oracle. Of its differences from `main`
examined so far, six turned out to be the branch carrying the losing answer,
including one "optimisation" I benchmarked at 2.1× slower than what it replaced.

**The rule is still that a difference must be *earned*, not that it cannot be** —
I rejected `risk_character_pattern()` on a benchmark, and a benchmark could just
as well have accepted it. Examine every difference; expect most to lose; take the
ones that measure well.

**But do not cite the panel frame as the example. It was withdrawn.** I
promoted it here as the branch's first win on `views-and-colour`'s measurement,
and they retracted it after a larger corpus: the branch's frame **outcomes** agree
with Rich at widths 40, 60, 96 and 100, and its **mechanism** is wrong. Rich has
no fits-or-truncates decision at all — it assembles the whole strip between the
corners (space, title, space, then dashes to fill) and clips *that* to
`width - 4` in one pass. A title of exactly `width - 5` therefore overflows,
because the trailing space sits inside the measured strip. An 11,200-line panel
corpus caught it at that one boundary, where a short session id and a `?` age
land a title exactly there. Seven examined, seven losing.

**The generalisable lesson is worth more than the example was, and it is not
about this branch.** *An outcome that matches at every sampled point is not
evidence that the mechanism matches.* Four widths agreed and the model underneath
was still wrong. Two tells to watch for: sampled agreement across a small set,
and a rewrite that **removes** a branch rather than adding one — the single-pass
version is usually the real one.

§3.5, the missing cell clip, is unaffected by this retraction and remains the
sharpest of the four width defects. That one is a whole missing layer rather
than a boundary.

---

## 7. Where the rest lives

`teammates/search-runtime/`: `engine-and-views-handoff.md` (the engine's
requirements, including five timing-shaped behaviours no byte gate can catch),
`search-runtime-map.md` (§13 inherited constraints, §15 the `.isascii()`
invariant, §17 preserve-because-wrong), `reconciliation-draft.md` (the branch
divergence ledger), `RESUME.md` (current state), `probes/` (the colour oracle,
the grammar oracle and its provenance, the help width sweep).
