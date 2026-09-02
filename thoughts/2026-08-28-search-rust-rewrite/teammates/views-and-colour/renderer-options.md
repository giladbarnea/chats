# The panel body renderer — options brief

For `search-firstmate` and the captain. Every number below is measured by me at
`8cb4c5f`; none is an estimate. No durations, because I can measure an artifact and
a corpus and cannot measure how long someone takes to write library code.

## The gap, exactly

`ch search foo` typed in a terminal renders bordered panels whose bodies are
markdown with syntax-highlighted code. **Nothing in `rust/` turns a `Message` into
styled lines.** The panel *frame* is landed and byte-proven; the *body* does not
exist. `Matches` is the default mode and colour is on by default on a tty, so this
is the commonest invocation of the command.

## What is already landed and proved

| Piece | Proof |
|---|---|
| Panel frame, title, facts line | 2,275 lines vs Rich; 11,200 vs Python |
| Coloured list row, summary, sink | 43,680 lines; 21,840 hits through the sink |
| Four stderr consoles | 135 cases, 5 colour tiers |
| `cells.rs` (Rich's cell measurement) | 12,430 Rich answers, 4 Unicode versions |
| `color.rs` (downgrade, 3 rendering states) | 1,499 oracle rows |
| Part iteration | `codecs::render_message_inner_xml` already walks all **four** part kinds in Python's order |

So the structural half of a body renderer has a working precedent in the tree, and
everything the body would sit inside is done.

## The two paths into Pygments, and how often each is reached

Measured over 750 real session files, 248,672 JSONL entries:

| Path | Reach |
|---|---|
| Fenced code block in a message (`Markdown` → `Syntax`) | **3.0%** of entries |
| `Read` tool result (`Syntax.guess_lexer` **by file extension**) | **0.6%** of entries |

**Markdown itself applies to every text part** — headings, lists, bold, inline code,
wrapping, padding. That is not a minority path; it is all of them.

**And the styling divides cleanly.** Outside a fence, markdown output is
attribute-only — `Some \x1b[1mbold\x1b[0m text.` padded to width, no colour. Inside a
fence, Rich paints a Monokai background on every cell plus a per-token foreground.
**The block's geometry and background are separable from its token colours**, which
is what makes staging safe rather than throwaway.

## Language coverage, measured

1,173 files, **64,013 fenced blocks, 65 distinct tags**:

```
bash 17.7   python 15.6   text 15.1   typescript 14.8   sh 14.0   json 13.1
    -> top 6 = 90.3%          top 15 = 97.8%
```

The reference branch lexes bash/sh/zsh, python, markdown, javascript, css, html,
json, diff, text. **It has no TypeScript lexer.** TypeScript + `ts` + `tsx` is
**17.7%** — larger than python. So adopting its lexer set buys ~78% of real fenced
content, not the ~98% the top-15 figure suggests.

`Read` results are lexed by **file extension**, so their surface is the user's repo
rather than a tag list: 24 distinct extensions, top 12 covering 96.5%, led by `.md`
38%, `.ts` 15%, `.py` 13%, `.js` 9%.

## Options

### A — Build the full renderer

**User-visible:** full parity attempt on every body.

**What the oracle can prove:** `ch-legacy` is alive, so a live byte differential
under a pty at any width and colour tier is available today — my harness, calibrated,
six perturbations. It proves parity **on the corpus run**, not off it. That limit is
already an accepted ruling: the input is arbitrary user code in any language, often
malformed, so a fixed-corpus diff cannot bound divergence beyond it.

**Surface:** prior art is **3,749 lines, 89 functions, zero tests** — of which
**2,482 (66%) reimplement Rich's `markdown.py` (793) and `syntax.py` (985) plus
Pygments (112,447 lines across 259 lexer files)**. The remaining 1,235 lines are
message structure. A port needs the code, its tests, and reconciliation onto `main`.

**Coverage:** whatever lexers get written. Must add TypeScript or accept 78%.

### B — Markdown and structure now; syntax highlighting as its own decision

**User-visible:** every message body byte-identical to the product **except inside
fenced code blocks and `Read` results**, where the background and geometry match and
the per-token foreground colours are absent. Confined to 3.0% + 0.6% of entries.

**What the oracle can prove:** everything outside fences, byte-for-byte, against the
live oracle — that is ~100% of bodies and it is *provable*, not statistical. The
fence interior becomes a named, measured, disclosed divergence rather than an
unbounded one.

**Surface:** the 1,235-line structural half plus Rich's markdown behaviour (793
library lines to match). **No Pygments.** Stage 2 adds highlighting without redoing
stage 1, because the fence interior is separable.

**Coverage:** highlighting absent everywhere until stage 2; correctness everywhere
else.

### C — Hold the cutover

**User-visible:** nothing changes; `ch search` stays Python entirely.

**Note:** the charter forbids shipping an intermediate hybrid, so "cut over the
finished modes and leave coloured panels on Python" is not available. Holding means
holding all of it, including the sink, grammar, engine and stderr work that is done.

## Ruled out

**Cutting over with coloured modes rendering plainly.** A whole-output divergence on
the commonest invocation. Already rejected by the first mate; I agree.

## Recommendation — B, and the reason is the root cause

The root cause is not that a module is missing. It is that **the panel body couples
this rewrite to two third-party libraries whose output cannot be provably matched**,
and the two are being treated as one item when they have opposite properties:

- **Markdown is deterministic and provable.** Fixed grammar, fixed output, reachable
  by every message, and a live oracle exists to diff against today.
- **Syntax highlighting is statistical by construction** — already conceded — reaches
  under 4% of entries, and needs a lexer per language with an unbounded tail.

Building them together prices the provable half at the unprovable half's cost and
delays it behind the unprovable half's risk. Splitting them lets the large,
certain, high-reach part land against a live oracle, and turns the remainder into a
single scoped question with a measured answer.

**Two consequences the captain should weigh explicitly:**

1. If stage 2 is built as a Pygments-shaped reimplementation, it must include
   TypeScript or it covers 78%. That is 2,482 lines of prior art for a result that is
   still statistical.
2. If fence-interior parity is unachievable anyway, a Rust highlighting crate reaches
   the same *class* of result — plausible but different colours — for a fraction of
   the code. It buys no parity that the reimplementation buys; it costs far less.
   Worth deciding deliberately rather than by default.

**One thing to verify before committing to B**, and it is cheap: that omitting token
foregrounds leaves the fence's line count, padding and background byte-identical. I
measured the structure and it separates cleanly; I have not rendered a
no-highlighting variant end to end.

## Independent of the decision

**A third of G4's coloured gate is a wiring job.** `ColouredListSink` exists and is
gated on 21,840 hits; `search_run.rs` constructs only `PlainSink`. Wiring it turns
`g4-list` green with no renderer and no ruling, leaving the gate's remaining red as
exactly the renderer question.
