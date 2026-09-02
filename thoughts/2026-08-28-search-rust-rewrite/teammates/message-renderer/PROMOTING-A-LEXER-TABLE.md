# Promoting a lexer table

**Written for a successor who has the engine and none of the reasoning.** The
engine is done and gated; each language is a transcription against a gate that
already proves itself. This is the procedure, the traps, and what a table's own
gate must assert before it is promoted.

**Order, by painted characters** — from `M4-stage-two-costing.md`, measured over
3,000 real fenced blocks:

| Family | Share of every painted character |
| --- | --- |
| **TypeScript** (`typescript`, `ts`) | **63.9%** with `tsx` |
| bash / sh | ~14% |
| json | ~9% |
| python | ~5% |
| markdown | ~2% |

**⚠ `tsx` is a different lexer, not an alias.** `TsxLexer` is 161 rules over 11
states against `TypeScriptLexer`'s 94 over 6, adding four JSX states. The 63.9%
groups by **fence tag**; by lexer it is two families. Found by `lexer-tables`
through a `tsx` fixture case being refused.

**One family at a time, complete with its gate before the next starts.** A family
is either promoted and gated or absent. That is what makes any stopping point
safe, and it is the same discipline the typed `Unsupported` set already enforces.

---

## 1. What exists

`rust/syntax_lexer.rs` — the driver. Pygments' `RegexLexer.get_tokens_unprocessed`,
gated against Pygments' own driver over 17 inputs.

`rust/syntax_styles.rs` — generated. Every Pygments token type with the style
Monokai resolves it to, and `token_style(path)` walking the ancestry as the theme
does.

`rust/syntax_lexers.rs` — generated. Pygments' 915 aliases, so `lexer_for_tag`
answers *which* lexer a fence tag reaches, and whether it reaches one at all.

`search_query::Regex::match_at` — anchored match with **character-offset** capture
groups. The driver's whole interface to the regex engine.

`session_render::render_plain_code_block` — the block's geometry: `padding=1`, the
Monokai background on every cell, `str.expandtabs(4)` in **characters**, the
`code_width = width - 2` wrap. **A promoted table changes only which token each run
carries; it changes no geometry.**

---

## 2. Generating a table

Pygments' lexers are `RegexLexer` subclasses whose `_tokens` is the flat,
already-expanded rule table. Write a generator beside the others in `probes/` that
walks it and emits Rust.

**Five traps, every one of which has already bitten this desk.**

**`_tokens` stores the compiled pattern's bound `match` method, not the pattern.**
`getattr(rule[0], "pattern", …)` silently returns `"<built-in method match …>"`.
The source is `rule[0].__self__.pattern`. **This produced a confident, plausible
"zero advanced regex features used" across 832 rules.**

**`using()` honours only `state=`.** Anything else in `kwargs` is forwarded to the
lexer's *constructor* and the re-entry then silently restarts from `root`.
`state='inline'` becomes the stack `('root', 'inline')`; a list or tuple is used as
given. **The engine's own gate caught this on its first run.**

**`using()` is never a rule's direct action in the five families — it appears only
inside `bygroups`' arguments.** A scan over rule actions finds none. Every instance
is `using(this)`, the same lexer re-entered, never a second lexer nested.

**A rule that does not change state is a two-tuple.** Pygments asserts on a
three-tuple whose third element is `None`. And an action may never be `None` except
through `default(...)`, which compiles to an **empty pattern** with no action.

**`include` and `inherit` cost nothing.** `RegexLexerMeta` expands both when the
class is built, so the generator emits the flat table and the engine never sees
them.

**A classifier's own branches must be reachable, and an exhaustive total is not
evidence that they are.** Sizing the families, I bucketed every transition and got
zero `combined()` states. The test was correct — `target.startswith("_")` — and it
sat behind a branch that caught tuples, and **Pygments stores every named push as a
tuple, including a single one**. So the string branch was unreachable and the
sixteen combined states python actually has were inside tuples already counted.
**Nothing looked missing, because nothing was: every rule landed in some bucket and
the totals were exhaustive. The wrong bucket held them.**

This is the third of three instrument failures on this surface, and they run in one
direction: a probe that **could not see**, then one **aimed one level too high**,
then one that **could see, was aimed correctly, and was unreachable**. **Each looks
more like a working instrument than the last, and the only thing that caught any of
them was disbelieving a zero.** When your generator counts things, spend one line
asserting each bucket is non-empty where it should be — or print an instance from
each and read it.

**Escaping.** Emit Rust string literals by escaping only `\` and `"` and writing
every other character literally in UTF-8. `repr` plus a quote swap breaks on a name
carrying an apostrophe; JSON escaping breaks on a non-BMP character, which it
writes as a surrogate pair that Rust rejects. Both happened.

**⚠ A table must declare its flags, and there is no default.** `RegexLexer.flags`
is a class attribute and differs by family:

    TypeScript, TSX, JavaScript    MULTILINE | DOTALL
    bash, python, markdown         MULTILINE alone

**Under DOTALL a `.` crosses a newline**, so compiling a bash rule with search's
flags lets a pattern run past the line it was written for — silently, and only on
multi-line input. `LexerTable` carries `LexerFlags { multiline, dotall,
ignorecase }` and `CompiledLexer` compiles through
`Regex::compile_with_flags`. **A default that is wrong for three of five families
is a trap, so the generator must read `type(lexer).flags` and emit what it finds.**

**Transitions.** Pygments resolves `#pop:n` to a negative integer before the driver
sees it — emit `Transition::Pop(n)`. A tuple of state words is
`Transition::States`, and its `#pop` guards `len > 1` while the integer pop guards
`abs(n) >= len`. The two guards are different and both are the reference's.

---

## 3. What a table's gate must assert

**Compare against Pygments itself, over real content in that language.** Not
against a reading of the table. Take fenced blocks of the family from real session
files — `probes/fence_lexer_census.py` shows how to harvest them — and record
`lexer.get_tokens_unprocessed(code)` as `(token path, text)` pairs. The Rust test
runs `syntax_lexer::tokenize` over the same code and compares the streams exactly.

**The corpus must be real content, and it must be large.** The census found
typescript at 75.5% painted and 442,034 characters in 915 blocks; a gate built from
a hand-written snippet proves almost nothing about a language that dense.

**Assert the compared count with a floor whose message carries the diagnosis**, so
a shrunken corpus cannot pass vacuously. Every gate on this desk does this.

**Name the mutation that breaks each claim**, per criterion 5. For a table, the
ones that matter:

- **A rule dropped.** The stream must differ; if it does not, the corpus never
  reaches that rule and the table is partly ungated.
- **Two rules swapped.** Rule order is significant — first match wins — and a
  generator that sorts or dedupes silently reorders them.
- **A `bygroups` slot misaligned by one.** The alignment error a generator actually
  makes. **Corrected from an earlier version of this document, which asked for a
  mutation making `bygroups` emit an empty group — that is a *driver* rule, not a
  table one**, and no table mutation can make the driver take the other branch.
  `lexer-tables` caught it and substituted correctly. The empty-group condition
  (`if data` for a token slot, `if data is not None` for a callable) is gated by
  the **engine's** own corpus. Do additionally record from Pygments which of your
  rules can match an empty group, and assert the corpus reaches at least one — the
  condition existing in the table is not the same as the gate touching it.
- **A state's transition changed from push-one to stay.** Catches a table that
  transcribed the actions and lost the states.

**And a corpus-adequacy test**: assert the recorded stream reaches every rule the
table declares, or names the ones it does not. A table whose gate exercises a
third of its rules is a third gated.

**⚠ Guard the empty-group requirement on reachability.** Requiring the corpus to
reach a rule whose `bygroups` can match empty is only meaningful where such a rule
is **reachable**. JavaScript's only two `bygroups` rules are its `super(...)` pair
and both are unreachable, so the condition does not exist in that table and
demanding it would demand an input nobody can write. **Compute reachability from
the oracle and apply the requirement only where it holds.** *Found and built by
`lexer-tables` while promoting JavaScript.*

### When a family has no table

**JSON is a hand-written scanner in Pygments, and its gate substitutes twice
over.** The shape generalises to any family that is not a `RegexLexer`, so read it
before deciding a family is unportable.

**The reference's executable lines stand in for a table's rules.** The generator
traces `get_tokens_unprocessed` and **refuses an oracle whose corpus leaves a line
unexecuted** — line coverage of the reference replacing rule coverage of the table.

**And the mutations are applied to the recorded side**, which proves the same
property by the same equality as mutating a table proves it from the other end.

**Exemptions must carry a checked premise, not a note.** Seven of JSON's lines are
exempt because `ensurenl=True` plus `_process_code`'s appended newline means the
text always ends in a newline, so the scanner's final-flush branches cannot run in
this product at all — **and the generator checks that premise on every case** rather
than asserting it once. *Built by `lexer-tables`.*

---

## 4. Wiring a promoted family in

1. In `session_render.rs`, the fence arm currently refuses any tag whose
   `lexer_for_tag` is not `"Text only"`. Add the promoted lexer's display name — the
   value `lexer_for_tag` returns, for example `"TypeScript"` — to the accepted set.
2. Build the `Text` the way `render_plain_code_block` does, but append **one span
   per token** with `syntax_styles::token_style(path)` instead of one span of
   `SYNTAX_TEXT` over the whole block. Everything after that — the split, the wrap,
   the padding — is unchanged.
3. Shrink `EXPECTED_UNSUPPORTED` in `session_render.rs`'s markdown gate. **The test
   asserts the exact set**, so it will tell you if you shrank it wrongly.

   **⚠ And once the set empties, that assertion stops saying anything.** An empty
   set because no corpus case reaches the refusal looks **identical** to an empty
   set because the refusal path has been deleted. The gate goes on passing either
   way.

   **So assert the refusal directly, against languages that reach a Pygments lexer
   with no promoted table** — javascript, html, css, js and rust are the ones in
   use — and require each to return `Unsupported("fence lexer")`. **The property
   then no longer depends on what a corpus happens to contain.**

   *Found and built by `lexer-tables` while promoting python, following the step
   above. It supersedes the step; the step alone would have left the refusal
   ungated from the first empty set onward.*
4. Raise the markdown gate's compared-record floor, and add fenced cases in the new
   language to `probes/generate_markdown_oracle.py` so the *rendered* block is
   gated end to end, not only the token stream.
5. `g4-fence-covered-later` in `probes/pty_differential.py` flips from red to green
   when python lands. `g4-fence-never-covered` must stay red for ever — javascript,
   html and css are not in the promoted set, and that row exists to keep the
   `Unsupported` path tested.

---

## 4b. What the remaining families cost — measured, not estimated

*Enumerated by `lexer-tables` over 36,539 real fenced blocks. Full working in
`teammates/lexer-tables/coverage-enumeration.md`.*

**Fourteen of the twenty-one unported lexers are pure tables needing nothing new.**
The two commonest are also the two smallest: **SQL — 337 blocks, 15 rules over 2
states — closes 30% of the gap and is smaller than any family already landed.**
XML is 144 blocks and 16 rules. **Start there.**

**The engine needs one addition, not two.**

- **A named callback `Action` unlocks four lexers at once** — Markdown, HTML, YAML,
  BibTeX — worth **290 blocks**. That is the one to build.
- **`using(OtherLexer)` — re-entering a *different* lexer — is worth 11 blocks**
  across VimL and Docker. **It costs more than it buys; do not build it on this
  evidence.** An earlier version of this procedure assumed markdown needed it. It
  does not.

**⚠ `console` is the trap, and it looks like the opposite.** `BashSessionLexer` is
**not a `RegexLexer`** *and* it **delegates its commands to `BashLexer`** — a
scanner and a foreign-lexer case at once, for 105 blocks. **By block count it reads
as a small family; it is the hardest thing on the list.**

**The 597-lexer residue is a policy question, not a porting one.** Treat it as such.

## 5. Two things that are not tables

**JSON is not a `RegexLexer` in Pygments** — it is a hand-written scanner. It is an
imperative port under every option, and it is 12.4% of fenced blocks. Sequence it
knowing that rather than discovering it.

**Markdown is HELD, and the trigger is named: it resumes when the captain rules on
the unpromoted tail.** Superseding an earlier line here that said to defer it
unless it fell out for free — that reading was too weak, and the reason is not
cost.

`_handle_codeblock` is a hand-written callback, and reading it rather than
describing it is what settles the dependency. It dispatches through
`get_lexer_by_name(match.group('lang').strip())` to **any** Pygments lexer, with a
`String` fallback over the whole code when none is found. `handlecodeblocks`
defaults to `True` and Rich passes no options, **so it is live.**

**That makes markdown's nested dispatch the unpromoted tail, one level down.** A
nested ` ```rust ` fence highlights in the product; whether ours highlights,
refuses or renders it plain **is** the tail decision. Promoting markdown first
would either bake in a policy or grow a second one beside it.

**When the ruling lands, two additions belong to the engine's owner, not to the
table author:**

1. **A named callback kind** — `Action::Callback(MarkdownCodeBlock)`, hand-ported.
   It is not expressible as `bygroups`: five fixed groups, a dispatch on the info
   string, and a conditional fallback.
2. **A group action that re-enters a *different* lexer**, honouring whatever the
   tail policy is, so there is one policy rather than a nested second one.

**Until then the generator must keep refusing a hand-written callback.** That
refusal is the guard: it says so rather than emitting a table quietly missing a
rule.
