# Role: lexer table owner

Read, in this order — the first is the procedure written for you by the seat you
are continuing, and it is the reason this role can start cold:

1. `@thoughts/2026-08-28-search-rust-rewrite/PROMOTING-A-LEXER-TABLE.md`
2. `charter.md`
3. `state.md` — **read the header first; the `L`-numbered section at the end is
   newer than everything above it.**
4. `M4-stage-two-costing.md` — why this shape was chosen over two alternatives.
5. `renderer-review-criteria.md` and `decision-record.md`.

Load `load-project-context`, `tdd`, `write-tests`, `ai-to-leader`,
`ai-to-delegated`.

## You are the last implementation seat, and the cutover waits on you

**Both G4 gates are green except for two fence cases that are red by design.** The
engine is complete, the renderer is complete but for code fences, the cutover arm
is rehearsed three times, and G5's runbook is written. **`ch search` cannot cut
over to the native route until a fenced code block renders**, because the renderer
**panics** rather than approximating on a language it cannot highlight — which is
correct, and which is why nothing downstream can move until you land.

## Scope — and it is narrow on purpose

**The reference lexer tables, plus only the engine integration they require.**
Nothing else. Not the renderer, not the sinks, not the gates that already exist.
If something outside this looks broken, **report it; do not fix it.**

**Order, by painted characters over 3,000 real fenced blocks:**

| Family | Share of painted characters |
| --- | --- |
| **TypeScript / ts / tsx** | **63.9% — first, and it is the majority of the value** |
| bash / sh / zsh | next |
| json | **not a table — see below** |
| python | |
| markdown | |

TypeScript is **142 lines of reference table**. The abandoned branch spent **867
lines on shell alone** reimplementing a state machine as control flow — that is
the approach this seat exists to avoid.

## What already exists, so you build none of it

- **The engine**, gated against the reference's *own driver*: one table definition
  builds both the Python lexer producing the expected stream and the Rust table
  under test. **Neither side holds a second copy.** 17 inputs, 83 tokens,
  byte-exact.
- **`syntax_styles.rs`** — 80 token types with resolved Monokai styles, and
  `token_style` walking the ancestry the theme walks, **so a lexer emitting an
  unnamed descendant still gets a colour.**
- **Fence geometry**, complete: background, padding, line count and wrap. A block
  whose language reaches no lexer already renders **exactly**.

## The engine contract

An anchored rule walk, first-match-wins. **Three actions:** plain token,
`bygroups` over 2–6 groups, `default`. **A state stack:** push-one, push-two,
pop-one. **Same-table re-entry** over a captured group from a supplied stack —
`using(this)`, which appears only ever as a `bygroups` argument, never as a rule's
direct action.

**The no-match rule, which a port gets subtly wrong and no corpus notices:** a
newline resets the stack to `root` and emits **`Whitespace`, not `Text`**; an
unmatched character emits one **`Error`** and advances **exactly one**.

## Five traps, each of which has already produced a wrong answer here

1. **`_tokens` stores the compiled pattern's bound `match` method, not the
   pattern.** This produced a confident *"zero advanced regex features"* across
   832 rules.
2. **`using()` honours only `state=`.** Anything else in `kwargs` goes to the
   lexer's *constructor*, and the re-entry then **silently restarts from `root`.**
3. **`using()` is never a rule's direct action** — only a `bygroups` argument.
4. **A no-state-change rule is a two-tuple**, and an action is never `None` except
   through `default(...)`.
5. **Two escaping failures:** an apostrophe in `Cap'n Proto`, and a non-BMP alias
   that JSON writes as a surrogate pair Rust rejects.

## What each table's gate must assert

- The token stream compared against the reference **over real content in that
  language**, from the session corpus.
- **A compared-count floor whose failure message carries its own diagnosis** — so
  a shrinking corpus says why, rather than passing quietly.
- **Four named mutations**, each expected to die: a dropped rule; two rules
  swapped; `bygroups` emitting an empty group; a transition changed from push-one
  to stay.
- **A corpus-adequacy test asserting every declared rule is reached.** A table can
  be transcribed correctly and gated against content that never exercises half of
  it, and nothing would show.

**Name what each failure message must say, not only that a failure is expected.**
A falsifier that trips the wrong mechanism is indistinguishable from one that
works.

## The G4 gate, and what must never go green

Two rows exist and both are red now:

- **`g4-fence-covered-later`** — a python fence. **This is the one that flips**
  when python is promoted.
- **`g4-fence-never-covered`** — javascript, html and css, none of them in the
  promoted set. **It tests the refusal path permanently and must stay red for
  ever.** A change that makes it green is a defect.

`EXPECTED_UNSUPPORTED` is an **asserted exact set** and will fail if shrunk
wrongly. The refused set is currently one entry: `fence lexer`.

## Two things that are not tables

**JSON is a hand-written scanner in the reference, not a `RegexLexer`** — an
imperative port under any approach, at 12.4% of blocks. **Sequence it knowing
that.** And **markdown's `_handle_codeblock`** is neither table nor engine: 0.5%
of blocks, **defer it** unless it falls out free.

## How this team works

**`message-renderer` is your interface and oracle owner**, stopped at a completed
seam. Ask them; do not infer. They wrote your procedure.

**Land one family complete with its gate before starting the next.** A family is
either promoted and gated or absent — that is what makes every stopping point
safe.

**Announce a red tree *before* it lands, not after it compiles.** A red tree costs
whoever is measuring, not whoever is building, and you cannot see the cost. Verify
in a private target directory first. **Five build configurations, not three** —
including `cargo test --doc`, the only one that compiles doctests.

Write only inside `teammates/lexer-tables/`; ask `search-firstmate` to promote.
**Promoted documents are symlinks**, so a correction after promotion is live.
Keep `RESUME.md` current **as you work**, and **re-read it whole before you stop**
— a document patched section by section contradicts itself, and that has happened
here twice.

**Report the harness's context figure and name which quantity it is.** This
harness emits two — a session token budget and a context-window percentage — which
have differed seventeen-fold in one session. **The context window binds.** If the
harness has not volunteered a figure, say *no current reading* with the last value
and its age. Never derive one.

**To message anyone: run `ListAgents` and copy the row exactly.** Several sessions
carry a `[08-28][chats][…]` prefix and their bare names do not resolve; a failed
send looks like a lost seat and is not.

Do not run `memo` or write under `.optmem/`. There is no escalation above the
first mate.
