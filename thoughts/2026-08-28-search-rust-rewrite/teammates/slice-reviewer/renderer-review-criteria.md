---
date: 2026-08-29
author: slice-reviewer
role: review criteria for `message-renderer`, written before the code exists
status: written deliberately in advance — the charter's rule that falsification criteria precede implementation applies to reviewing it too
oracle: src/chats/formatting.py and src/chats/lexer.py at 8cb4c5f, read directly
---

# Renderer review criteria

**Written before `rust/session_render.rs` exists.** `g3-review-criteria.md` was
written the same way and for the same reason: a reviewer who decides what would
falsify the work only after seeing it can rationalise around whatever it contains.

**Every entry names the mutation that should break it.** Criterion 5's practical
form: if you cannot name one, the test is a description rather than a guard.

**Scope limit.** These are the properties I can establish from the Python at the
oracle. They are not a plan and they do not cover the parts of the renderer I
cannot see from here — the style model, the wrap engine's internals, or whatever
the `markdown-it` verification concludes.

---

## 1. ⚠ A search term split across a style boundary is **not** highlighted

**This is a preserve-because-wrong behaviour and it is not on the list.** The list
has nine; this is a tenth, and it is the one most likely to be "fixed" by a port.

`HighlightedMarkdown.__rich_console__` renders the Markdown to a **segment
stream** and re-applies the highlight per segment. Its own docstring states the
consequence:

> Matches that fall within one rendered run — the common case for a search term —
> are highlighted; **a term split across a style boundary is left untouched.**

So searching `hello` against source `**hel**lo` yields two segments, `hel` bold and
`lo` plain. **The regex matches neither, and nothing is highlighted**, even though
the rendered line plainly reads `hello`.

**Why a port gets this wrong in the good direction.** Highlighting the assembled
plain text and mapping offsets back is the obvious implementation, it is more
useful, and **no reviewer objects to a search term being highlighted.** It is the
exact shape of the preserve-because-wrong class: the output looks better.

**Named mutation:** highlight over the concatenated plain text rather than per
segment. **A fixture whose match straddles a bold boundary must go red.** A fixture
built from unformatted text cannot fail, and unformatted text is what a first
fixture uses.

## 2. The highlight **combines** with the underlying style, never replaces it

    combined = style + highlight if style else highlight

A match inside a bold run renders bold **and** highlighted. **Named mutation:**
replace rather than combine. A fixture whose match lies in unstyled text cannot
tell the difference; the fixture must place a match **inside** a styled run.

## 3. `chop_cells` is unported, and this renderer is its first consumer

`cells.rs` ports `cell_len`, `character_cell_size`, `split_graphemes`,
`split_text`, `set_cell_size` and the ellipsis clip. **It does not port
`chop_cells`.**

That was correct for the search views, which are `Text(no_wrap=True,
overflow="ellipsis")` — they clip and never wrap. **The message body is a Rich
`Markdown` inside a `Panel`, which wraps**, and Rich's wrap path goes through
`chop_cells`.

**So the first module that needs it is the one being written now.** Its rules are
not the ellipsis rules: it emits a **list of lines**, it splits on grapheme spans
rather than characters, and its single-cell fast path is
`[text[i : i + width] for i in range(0, len(text), width)]` — a **code-point**
slice, which is a fourth counting unit appearing in the same file as the other
three.

**Named mutation:** wrap by code points rather than cells. **A fixture containing
one double-width character at the wrap boundary must go red.**

## 4. `LeftRail` renders its child at **reduced** width

The rail prefixes `▎ ` and renders the child narrower so the rail fits inside the
enclosing panel. **Every tool block's wrap width therefore differs from the
panel's by the rail's own width.** An off-by-one here moves every wrapped line in
every tool block, and it is invisible on any content short enough not to wrap.

**Named mutation:** render the child at the full width. **A fixture whose tool
block contains a line longer than the panel interior must go red.**

## 5. Inline code is padded with one space on each side

`PaddedInlineCodeMarkdown` exists solely for this. It is a subclass of Rich's
`Markdown`, so a port that reimplements Markdown rather than porting this subclass
loses it silently. **Named mutation:** drop the padding. A fixture with no inline
code cannot fail.

## 6. Syntax highlighting guesses a lexer from the **file path**, and falls back to `"text"`

    try:    lexer = Syntax.guess_lexer(file_path, code)
    except: lexer = "text"

**Decision 16 already rules that colour fidelity here is corpus-bounded**, so the
lexer set is not the criterion. **The criterion is the fallback**: which inputs
take it, and that `"text"` renders as unhighlighted source rather than as nothing.
A port whose fallback drops the body loses content, not colour.

**Named mutation:** make the fallback return empty. **A fixture whose `file_path`
has an unknown extension must go red.**

## 7. The three counting units stay three, and this file touches all of them

Code points for `elide_to_width` and `truncate_middle`; UTF-16 code units for the
Pi `responsePreview`; cells for everything Rich measures. **Adding `chop_cells`'s
code-point fast path makes the renderer the one place all of them meet.**

**Named mutation:** unify any two. The desk's existing fixtures cover the first two
— `你好你好你好你好` at budget 8, and the NFC/NFD pair — and they must keep
failing against a cell-based implementation.

## 8. The highlight must never index the original string with offsets measured on a lowered copy

**This was the branch's one blocker**, and it lands squarely here now that
highlighting is being written. `İ` grows from 2 bytes to 3 when lowercased; the
ligatures `ﬀﬁﬂﬃﬄ` shrink from 3 to 2. Enough drift aborts mid-render with exit
101; below that threshold it silently paints the wrong span.

**Fold per character over the original string, using the same equivalence that
defines search truth.**

**Named mutation:** lowercase, find, then slice the original at those offsets.
**The fixture must contain both a growing and a shrinking character** — `İ` and
`ﬀ`. A fixture with only one direction catches only half, and an ASCII fixture
catches neither.

## 9. `re.IGNORECASE` is not `casefold()`

Standing constraint 5, and the highlight regex is the newest place it applies.
`ss` must not match `ß`. **Named mutation:** casefold both sides. **The fixture is
one `ß` in a body and a search for `ss`** — it must **not** highlight.

---

## What I will check that is not a behaviour

**For each property above, does a test exist that fails when it is removed?** Not
"is there a test" — would it go red. That question, applied to `plan.rs`, found two
guards this mission would otherwise have shipped: one inert, one absent.

**And I will ask what each fixture holds fixed rather than what it varies.** The
renderer's fixtures will have a width, a colour tier, a terminal condition and a
`UNICODE_VERSION`, and every one of those has already been the held parameter that
hid something on this mission — L22, L35, L36, 22an.

## What these criteria do not cover

- **The style model and the wrap engine's internals**, which I cannot see yet.
- **Whatever `markdown-it` does or does not reproduce.** The verification is
  `message-renderer`'s and its result changes what is worth checking here.
- **Colour fidelity of syntax highlighting**, ruled corpus-bounded by decision 16
  and out of scope for a structural pass.
- **Arithmetic, ordering and missing-arm defects**, which are not the shapes I
  search for. L43: a negative from me does not cover them.
