# M4 — stage two, priced three ways

Commissioned before implementation: what a Pygments-shaped port costs, what a
highlighting crate gives instead, and a recommendation. **The measurements
produced a third option that neither question named.**

## 1. The surface the decision actually covers

Over 3,000 real fenced blocks (600 session files, 1.37M characters):

    characters a lexer paints away from Monokai's default   539,554 of 1,367,720   39.4%
    typescript family                957 blocks  31.9%   63.9% of ALL painted characters
    `text` fences                    660 blocks  22.0%   37.3% of characters, 0% painted
    no Pygments lexer at all          10 blocks   0.3%

**Three consequences, and each of them moves the decision.**

**Sixty per cent of fenced characters carry Monokai's default foreground whatever
lexer runs.** The colour question is about the other 39.4%.

**Two thirds of that 39.4% is one language family — the one the prior art does not
have.** TypeScript is not "one more lexer". It is the majority of the value, and
it is the densest: 75.5% of its characters are painted, against bash's 45.3%.

**`text` fences are 22% of blocks and 37% of characters, and Pygments paints none
of them.** They are correct today with no lexer at all — see §4.

`probes/fence_lexer_census.py`.

## 2. Option A — a Pygments-shaped hand-written port

**What the prior art actually spends**, measured function by function over
`0ffde41:rust/session_render.rs`:

    shell/bash   867      html   109        shared lexer core   504
    css          215      json    97        markdown renderer   511  (replaced)
    python       177      diff    11        wrap/segment core   256  (replaced)
    markdown     173      plain   34        javascript           4

**⚠ Two corrections to the received picture.** The markdown renderer and the wrap
core — 767 lines — are **already replaced** by this seat's work and are not part of
any remaining cost. And **`syntax_tokens`, the fence dispatcher, handles only
python, sh/bash/zsh, json, markdown and diff.** HTML, CSS and JavaScript are
reachable **only from the `Read` tool path**, which lexes by file extension.
`javascript_tokens` is four lines and calls the plain path. So the prior art's
fence coverage is **five families, not eight**, and it has no JavaScript either.

**A second cost anchor, from the reference itself.** Pygments' own definitions are
declarative regex tables and are far smaller than the branch's imperative
equivalents:

    TypeScript 142 (37 + JavaScript's 105)   Bash 102   Python 386   Markdown 118
    JSON 263 — and **not a RegexLexer**: Pygments hand-writes it as a scanner

The branch spends 867 lines where Pygments spends 102, because it reimplements a
regex state machine as control flow.

## 3. Option B — a Rust highlighting crate

**The crate is `syntect`.** Measured against the census rather than described.

**It has no TypeScript, no TSX and no plain-text syntax in its default set.**
Enumerated directly: 488 of 1,200 sampled blocks find no syntax at all, and every
one of the TypeScript-family blocks is among them. **The language that is 63.9% of
the painted surface is absent**, and `two-face` or a bundled `.sublime-syntax`
would be needed to add it.

**It ships no Monokai theme** — InspiredGitHub, two Solarized and four base16.

**And where both lexers do run, they do not agree on where the tokens are.**
syntect maps TextMate *scopes* through a theme; Pygments maps its own *token
types* through a style map, and no mapping between the two exists to borrow. So
the comparable quantity is **where each puts a run boundary**, which needs nothing
invented — and **a boundary in the wrong place is a divergence no theme can
repair**, so this is an *upper bound* on what any theme mapping could achieve:

    overall     62.3%       bash 55.9%    json 60.6%    sh 47.9%
                            python 81.7%  js 91.6%      markdown 22.6%

**On the two commonest lexed languages after TypeScript, fewer than two thirds of
run boundaries land in the same place.** That is not "the same class of result in
different colours"; the segmentation itself differs.

`probes/lexer_boundary_agreement.py`.

## 4. Option C — port Pygments' lexer *tables*, not its behaviour

**The measurements produced this and it was not on the list.** Pygments' lexers
are `RegexLexer` subclasses: declarative `(pattern, token, state)` tables. Porting
the **table** reproduces the token types exactly, which is the `markdown-it`
argument arriving by a different route — *port the reference's data rather than
reimplement its behaviour*.

**832 rules across the five regex lexers that matter** — typescript 94,
javascript 78, bash 189, python 435, markdown 36 — with 687 plain token actions,
138 callbacks (`bygroups` / `using`) and 832 state transitions.

**Every regex feature they use is already supported by the engine in this tree.**
`search_query.rs` carries a Python-compatible engine with `Backref`, `Look
{ behind }`, `ScopedFlags` and named groups. Feature counts across the 832 rules:
inline flags 52, lookahead 23, lookbehind 15, backreference 6, named group 1.

**What this option does not cover: JSON.** Pygments hand-writes it as a scanner,
so JSON is 263 lines of imperative port whichever option is chosen. It is 12.4% of
blocks and 9% of painted characters.

**⚠ A probe of mine reported "zero advanced regex features used" and it was
false.** `RegexLexer._tokens` stores the compiled pattern's **bound `match`
method**, not the pattern, so reading `.pattern` fell through to `str()` and
scanned `"<built-in method match…>"` — which contains no regex syntax. **Zero was
a plausible wrong answer from a broken probe**, and it survived until a spot check
printed the instances. The numbers above are from the corrected scan.

## 5. Recommendation — **RULED, and this section is history**

**The captain ruled in favour of what follows, so read this as the reasoning
behind a decision rather than as an open question.** Landed since: the fence
geometry, the lexer engine and its gate, and the Monokai style table.
`syntect` is rejected and hand-written lexers are rejected. The tables are
`lexer-tables`' work, on `PROMOTING-A-LEXER-TABLE.md`.

**Nothing below is a live proposal. Do not re-argue option B from these
numbers — the ruling already weighed them.**


**Reject Option B.** It misses the language family that is two thirds of the
painted surface, ships none of the theme, and where it does run it agrees with
Pygments on 62% of run boundaries — an upper bound, before colour.

**Split the remaining work at the line the measurements draw, not at the one the
question assumed.**

**Land `Syntax`'s geometry first, as stage-one work.** The block's line count,
padding, background and word wrap are separable from token colours — every cell
inside a fence carries `48;2;39;40;34` and tokens only replace the foreground
prefix inside that run. With geometry and the default foreground alone, **`text`
fences and unknown tags render *completely correctly*, not approximately**: 22.3%
of blocks and 39.6% of fenced characters, deterministic and gateable against Rich
exactly the way the markdown corpus already is. **It is not a partial render, and
it shrinks stage two to colours alone.**

**Then take Option C for the colours, in order of painted characters:** TypeScript
family (63.9%), bash/sh, json (as an imperative port), python, markdown.

**What Option C changes about the standard.** Decision 16 conceded that
fence-interior parity is statistical because the input is arbitrary user code. That
is true of a *reimplementation*. Porting the reference's own tables onto an engine
that already reproduces Python's regex semantics makes the token types provable
and moves the residue to the same place `markdown-it` moved it: an enumerable
divergence list rather than an unbounded surface. **I would not claim it is
provable until it is measured the way M2 measured the parser — but that
measurement becomes possible, and under Option A it does not.**

---

## 6. The driver, measured — the code cost beside the data cost

**The tables are declarative; the thing that runs them is not.** Commissioned
before the brief went up. Measured over the five families that would be ported —
typescript, javascript, bash, python, markdown — 832 rules, states per lexer 6, 6,
9, 49 and 2.

**Rule actions**

    plain token                          687   82.6%
    bygroups(...)                        138   16.6%
    default(...) — state change only       6    0.7%
    hand-written callback                  1    0.1%   markdown's _handle_codeblock

**State transitions**

    stay                                 602   72.4%
    push one state                       178   21.4%
    pop one state                         50    6.0%
    push two states                        2    0.2%

**Deepest pop is one**, and there is no `#pop:2` or deeper and no `#push`.

**⚠ CORRECTED: `combined()` states are not absent. Python has sixteen** —
`_tmp_0` through `_tmp_15` — **with 64 transitions into them.** The other four
families have none. Re-measured after `lexer-tables` reported it while porting
python.

**It costs the driver nothing**, which is why the cost conclusion is unchanged:
`RegexLexerMeta` resolves a `combined()` into an ordinary named state before
`_tokens` exists, so the engine only ever sees a name. **But the claim as written
was wrong, and a successor sizing python from it would have been surprised.**

**Why the scan missed them, because it is the third instance of one failure and
the most disguised yet.** My classifier tested `target.startswith("_")` — a correct
test — after a branch that caught tuples. **Pygments stores every named push as a
tuple, including a single one**, so the string branch was unreachable and the
combined names were *inside* the tuples it had already counted. The bucket printed
zero and the totals looked complete.

The first instance was a probe that could not see: reading a bound `match` method
instead of a pattern. The second was a correct, calibrated detector aimed one level
too high: `using()` lives inside `bygroups`' arguments, not in a rule's action.
**This is the third: a correct test made unreachable by an earlier branch, in a
classifier whose output looked exhaustive because every rule landed in some
bucket.** Nothing was missing from the total; the wrong bucket held it.

**`bygroups` shape:** arity 2 to 6, and **no `None` slots at all** — every group's
text is emitted, so the skip path is unreachable here.

**`include` and `inherit` cost nothing.** `RegexLexerMeta` expands both when the
class is built, so `_tokens` is already flat. A port copies the expanded table.

**⚠ `using()` is present, and my first scan reported zero.** It is never a rule's
direct action in these five, so a scan over rule actions finds none. **It appears
only as an argument inside `bygroups`** — four instances:

    python/soft-keywords-inner   using(this)
    markdown/root  x3            using(this, stack=('root', 'inline'))

**Every one is `using(this)` — the same lexer re-entered, never a different one.**
So the driver needs to re-lex a captured group's text with its own table from a
supplied state stack. **It does not need to nest a second lexer**, which is the
distinction that decides the cost.

**This is the third variant of one failure in two days, and the sharpest.** The
first was a broken probe reading a method object. This one was a **correct,
calibrated instrument pointed at the wrong place** — the detector fires six times
on the HTML lexer, so it works; it was looking at rule actions when the mechanism
lives one level down. *Calibrating an instrument proves it can see, not that it is
aimed at the thing.*

## 7. The answer to the question that was asked

**The driver these five families need:**

1. An anchored rule walk, first match wins.
2. Three actions: plain token, `bygroups` over 2–6 groups, and `default`.
3. A state stack with push-one, push-two and pop-one. Nothing deeper.
4. Re-entry into **the same** table over a captured group, from a given stack.
5. On no match: newline resets the stack to `root` and emits `Text`; otherwise
   emit `Error` and advance one character.
6. One hand-written callback, in markdown, which is 0.5% of fenced blocks and can
   be deferred without touching anything else.

**That is the first of the two branches you named: `include`, `bygroups` and a
shallow state stack, and nothing else.** It is a transcription with a small
engine, not a Pygments interpreter. **JSON remains the exception** — not a
`RegexLexer` in Pygments at all — and is an imperative port under every option.
