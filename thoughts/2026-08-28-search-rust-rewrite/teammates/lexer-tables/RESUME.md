# lexer-tables — RESUME

Cold entry. Nothing here assumes you followed the thread. **Written whole rather
than patched**, because a document edited section by section contradicts itself —
and the last whole read of this one found it asserting the opposite of its own code.

**The seat, in two parts.** It began as the lexer tables: port Pygments' tables onto
the engine `message-renderer` built, one family at a time, and wire each into the
fence arm. **That is finished at seven families.** The first mate then widened it on
2026-09-01 to **styled tool rendering**, because `ch search -t` with colour panicked
and truncated, and this seat was already inside `session_render.rs`. **The common
path of that is landed; two bodies are not.** Both parts are below.

**Read first:** `PROMOTING-A-LEXER-TABLE.md` at the desk root. It is the procedure.

**⚠ If nobody is left to route a question, the record is on the desk rather than in
a seat.** `state.md` is the mission record — **read its header first, then the
`L`-numbered section, then the mission-state block at the end**, because it is
append-only and later entries supersede earlier ones. **`L198` is the
settled/conditional/expired table**, and it is what stops a successor re-opening
something finished or waiting on someone who is gone. `decision-record.md` carries
why the rejected alternatives were rejected. **This seat's own decisions are all in
this file**; nothing about the lexer tables lives only in a message thread.

---

## State, taken 2026-09-01T12:12Z

**Seven families promoted and gated, approved by the captain as the final list. The
tool renderer's common path is landed. Two tool bodies are not built and are named.**
`syntax_tables.rs` 1dfb6f41dac7, `syntax_table_gates.rs` 1fa0569e4b13,
`session_render.rs` df063bbe3d9d, `codecs.rs` 3cf2657960c5.

**Tree green: 234 lib tests + 53 doctests**, and all five build configurations at
**zero warnings** — `cargo check`, `cargo check --no-default-features`, `cargo test
--no-run --no-default-features`, `cargo test --doc`, `cargo build --release
--no-default-features`.

| Family | Table | Corpus | Rules reached |
| --- | --- | --- | --- |
| TypeScript (`typescript`, `ts`) | 94 rules, 6 states | 624 cases, 312,893 chars | 85 of 94 |
| TSX (`tsx`) | 161 rules, 11 states | 97 cases, 28,946 chars | 145 of 161 |
| Bash (`bash`, `sh`, `zsh`, `ksh`, `shell`) | 189 rules, 9 states | 1857 cases, 430,266 chars | 132 of 189 |
| Python (`python`, `py`, `python3`, `py3`) | 435 rules, 49 states | 270 cases, 63,591 chars | 315 of 435 |
| JavaScript (`js`, `javascript`, `node`) | 78 rules, 6 states | 443 cases, 134,809 chars | 71 of 78 |
| JSON (`json`, `json-object`) | **no table** — a scanner | 574 cases, 111,867 chars | 133 of 140 **lines** |
| SQL (`sql`) | 15 rules, 2 states | 52 cases, 49,007 chars | **15 of 15** |

Every unreached rule is **named unreachable with a reason the generator derived**,
and the generator **refuses to write an oracle** carrying an unreached rule it
cannot explain.

## Why it stops at seven

**The seven carry 98.2% of every character a lexer paints.** Measured over 25,940
real fenced blocks and 11,915,699 characters by
`probes/painted_character_share.py`: 34.3% of fenced characters are painted away
from Monokai's default at all, and the seven carry 4,010,773 of the 4,083,499 that
are.

    TypeScript 62.5%   Bash 15.6%   JSON 10.9%   JavaScript 6.2%
    Python      1.6%   SQL   1.1%   TSX   0.2%

**The whole remaining tail is 1.8% between them.** Diff is the largest at 0.4%, XML
0.3%, and nothing else reaches a quarter of a per cent.

**⚠ Blocks and painted characters are different quantities, and this is the trap.**
By block count SQL and XML looked like 43% of the coverage gap, and the plan was to
land both. By colour, **SQL was worth 1.1% and XML is worth 0.3%** — XML fences are
short and sparsely coloured. **A language's share of appearances is not its share of
colour**, and the ordering that follows from each is different.

**TypeScript at 62.5% here against `M4-stage-two-costing.md`'s independent 63.9% is
convergent evidence from two instruments over two corpora**, which is what makes the
98.2% trustworthy rather than merely computed.

The full enumeration of what is *not* ported — 21 lexers, classified by whether each
needs an engine addition, with gateability — is `coverage-enumeration.md` beside
this file.

## What an unported language does

**It renders with complete fence geometry and plain unstyled code.** That path is
built, gated, and never refuses, panics or truncates. **Four assertions hold it**,
all in `session_render.rs`'s `fence_render_oracle_tests` and all listed in the
closing section below — a subject check, a control, a parity case and a divergence
case. **Plus the `unreachable!()` in `render_code_block`'s unpromoted arm**, which is
deliberate: the fence arm maps an unported language to `None` before that function
sees it, so the plain render happens once in one place.

**Tags reaching no Pygments lexer at all are 401 blocks, 1.1%, across 29 tags** —
`just` (184), `tsv` (65), `mdx` (39), `mermaid` (26), `txt` (22), `justfile` (19).
For these, plain output is **parity** with legacy rather than a divergence.
**`mermaid` is the right subject for a fallback gate and `css` is the wrong one**,
because legacy colours CSS. That was the other way round under an earlier ruling;
the property did not change, the question did.

---

## The held-out corpora, and the rule that keeps them evidence

**Every corpus in the table above was used while building.** Rules were counted
against it, cases added until coverage closed, mutations aimed with it. So none of
it answers the question a reader actually wants answered: does the table reproduce
Pygments on content nobody looked at?

**`tests/data/lexer-tables/<family>-heldout-oracle.json` answers it.** Harvested
from **seed 101** after each table was finished, with **no authored cases and no
coverage requirement** — real fenced content only, from files the building corpora
at seed 23 did not draw. Written only by the generators' `--held-out` flag, to their
own paths.

**Result, all seven families, zero differences: 2,154 blocks and 786,472 characters
of unseen content, byte-exact against Pygments.**

    typescript 511 blocks 296,231 chars    bash        899 blocks 222,836 chars
    json       489 blocks 146,207 chars    javascript  128 blocks  40,524 chars
    python      64 blocks  26,366 chars    sql          35 blocks  41,293 chars
    tsx         28 blocks  13,015 chars

**⚠ Nothing is ever repaired against these.** A failure is a defect in a table, a
generator or the driver. **Regenerating a held-out corpus to make it pass converts
the only unseen evidence into more of the seen kind**, and it is exactly the move
someone under time pressure makes because it looks like fixing a corpus. The gate's
failure message says so; the separate flag and separate paths mean it cannot happen
by accident.

**They are also what a replacement has to match.** An evaluation of any other
highlighting library, by someone who never met this seat, has to beat these numbers
on this content or it is not a replacement. **The deletion target is the
implementation, not the measurement.**

---

## Uncommitted edits from this seat

- `rust/syntax_tables.rs` — **new and generated. Do not edit.** Six tables and
  `promoted_lexer`, which is the whole interface to them. JSON is not among them.
- `rust/syntax_json.rs` — new. Pygments' JSON scanner, hand-ported.
- `rust/syntax_table_gates.rs` — new. Every family's gate. Test-only module.
- `rust/lib.rs` — three lines.
- `rust/session_render.rs` — the fence arm routes a promoted display name to its
  lexer; `render_plain_code_block` became `render_code_block`, taking the lexer; a
  new `fence_render_oracle_tests` module. **Plus the whole tool renderer** — the
  accents, `Renderable::ToolHeader`, `tool_renderables`, `home` on `BodyContext`, and
  `KNOWN_UNBUILT_BODIES` in the body oracle. **This is `message-renderer`'s file**;
  the fence changes are §4 of their own procedure and they reviewed them before
  stopping, and the tool work was assigned by the first mate after they did.
- `rust/codecs.rs` — `tool_use_parts` and `tool_result_parts` extracted, with both
  XML renderers routed through them. Additive; behaviour unchanged.
- `tests/data/lexer-tables/` — 22 fixtures, 28 MB: a token oracle, a render oracle
  and a held-out corpus per family. Every one regenerates from a checkout.
- `tests/data/message-renderer/body-oracle.json` — six tool cases added, and the
  generator's `CASES` with them.

## What each family's gate asserts

| Gate | What it compares |
| --- | --- |
| `the_table_reproduces_pygments_over_…` | every recorded stream, byte-exact, with a floor whose message says what a shrunken corpus means |
| `the_corpus_reaches_every_declared_rule` | the generated table declares exactly Pygments' rules in order; each is reached or named unreachable; and an empty `bygroups` group is matched **wherever a reachable `bygroups` rule exists** |
| four mutations per family | a dropped rule, a swapped pair, a dropped `bygroups` slot, a lost push — each must change the stream |
| `lexing_bash_under_dotall_changes_the_stream` | the DOTALL field of `LexerFlags`, falsified rather than merely used |
| `lexing_sql_case_sensitively_changes_the_stream` | the IGNORECASE field, the same way |
| `the_corpus_reaches_every_line_of_the_reference_scanner` | JSON only: the reference's executable lines, seven exempt for a checked reason |
| `a_mutation_aimed_at_the_wrong_rule_refuses` | the refusal itself, seen to fire |
| `every_table_reproduces_pygments_on_content_it_was_not_built_against` | the held-out corpora |
| `every_recorded_fence_in_a_promoted_language_renders_exactly` | the **rendered** block against Rich, seven families, five widths |
| `a_recorded_fence_carries_more_than_one_foreground` | the corpus can tell a highlighted block from a plain one |

**Three families carry three mutations rather than four, and each time it is a fact
about the table rather than a waiver.** JavaScript's only two `bygroups` rules are
both unreachable; SQL has no `bygroups` rule at all. **The adequacy test computes the
exemption from the oracle** rather than accepting an assertion, so a family with a
reachable `bygroups` rule still has to reach it.

**`EXPECTED_UNSUPPORTED` is empty**, because every fence in the markdown corpus now
renders. The refusal path it used to guard is asserted directly instead.

---

## The generators, all in `probes/`

    generate_lexer_tables.py        Pygments' _tokens  -> rust/syntax_tables.rs
    generate_lexer_table_oracle.py  real fences        -> the token oracle
    generate_json_oracle.py         the scanner        -> JSON's oracle, with line tracing
    generate_fence_render_oracle.py the token oracle   -> the rendered oracle
    harvest_family_corpus.py        the harvest and the coverage measurement
    python_supplements.py           Python's authored half, generated
    inspect_table.py                what one family's table holds, before writing anything
    enumerate_target_lexers.py      what is unported, classified by cost
    painted_character_share.py      what a family is worth, in colour rather than blocks

Run from the repository root. **Adding a family is one line in `FAMILIES` plus a
gate module**; the generator refuses everything it cannot account for, so the work
is bounded and it tells you what is left.

---

## Four things that will bite the next family

**1. The corpus moves under you.** The session directory is live, and the first
harvest took the prefix of a seeded shuffle over it — so adding a file reshuffled
every position. The same seed gave 589 blocks, then 465, then 507 within an hour,
and **a rule that one sample happened to reach disappeared between two runs.** The
harvest now orders paths by a hash of the path, so a new file lands in one place and
the corpus grows at its tail. **Regeneration is still a deliberate act:** read the
generator's summary line rather than assuming the fixture is the one you had.

**2. A rule is often unreachable, and how often is a property of the family.** Nine
of TypeScript's 94, sixteen of TSX's 161, fifty-seven of Bash's 189, a hundred and
twenty of Python's 435 — and **none of SQL's 15.** The reasons are always one of
four, all derived rather than asserted:

- **A state nothing transitions into.** Every `include` target — `basic`, `data` and
  `interp` in bash, `commentsandwhitespace` and `jsx` in the TypeScript family, and
  a hundred and ten of Python's.
- **An identical pattern earlier in the same state**, which always matches first.
- **`\A` in a state that is never at position 0.**
- **A shadowing earlier rule, checked against a witness.** Bash is the extreme case:
  `curly` opens with `\w+` then a catch-all excluding seven characters, and `math`
  opens with its own operator and number rules, so most of the shared body they
  include is dead.

**3. Aim a mutation at a rule and it will tell you something you did not ask.**
**Three** of the mutations first chosen left the stream identical, and each meant
something different. TSX's meant **the corpus was blind** — it had no `super(...)` —
and a case fixed it. Bash's meant **the state was unobservable**: `backticks` is
`root`'s body plus a pop, with its own nested-backtick rule shadowed by that pop, so
a backtick that stays in `root` produces the same tokens. JavaScript's meant **the
two rules were disjoint**: its builtin alternation does not list `Error`, so swapping
it with the exception rule is not an ordering test at all. **Blind corpus,
unobservable state, disjoint rules — same symptom, three diagnoses, and only reading
the failure tells them apart.**

**4. An assertion about non-promotion must name a language that is not a promotion
candidate.** `a_fence_in_an_unpromoted_language_…` first named `javascript` and
turned red the moment that family landed; the generated doctest named `JavaScript`
and did the same, thirty seconds apart, by two people. **And `mermaid` is the wrong
substitute for a refusal assertion and the right one for a fallback assertion** — it
reaches no lexer at all, which is the wrong property for one question and the right
one for the other.

---

## Findings sent out, and where each went

1. **`search_query`'s backreference folded case unconditionally**, so bash's heredoc
   rule ended at the `py` inside `print("hello from uv python")`. Fixed by
   `query-semantics`, both directions tested. **Bash is the only promoted family
   whose grammar uses a backreference at all**, and no authored snippet would have
   carried that text — the corpus-must-be-real rule earning its keep on the one
   family where it could.
2. **A follow-up hypothesis that DOTALL was the cause is falsified by construction:**
   the rule scans with `[\w\W]`, a **character class, not a dot**, and a class
   crosses newlines whatever DOTALL says. `IGNORECASE` reproduces the symptom
   character for character.
3. **`Regex::compile`'s hardcoded flags are not a second defect.** Two production
   callers, both `ch search`'s own query compilation, which is the route pinned to
   CPython with exactly those flags.
4. **The markdown oracle could not be regenerated reproducibly.** Fixed by
   `message-renderer` with a `--from-existing` mode.
5. **`Syntax.highlight` does not strip control codes.** Fixed by `message-renderer`.
6. **M4 records "no `combined()` state anywhere in the five" and Python has
   fourteen**, `_tmp_0` through `_tmp_15`. Costs the driver nothing, but a successor
   sizing python from that line would be surprised.
7. **The `bygroups` empty-group criterion was a driver rule, not a table one.**
   `message-renderer` rewrote that entry of the procedure to ask for slot
   **misalignment**, and adopted the reachability guard that came out of JavaScript.

---

## Parked, and why

**`markdown-gate.rs.pending`** — markdown's table, corpus and gate are written and
**stale.** They were built against Pygments' `handlecodeblocks=False`, which was
correct under a tail ruling that has since been **retracted**. Under the current rule
a nested fence in a language legacy colours must be coloured, which is the
nested-lexer case. **The oracle needs regenerating and the transcribed action needs
revisiting** before markdown could be promoted. Two of its four mutations were also
still failing when it was parked, and both are findings rather than defects: nothing
transitions into `inline`, so there is no push to lose, and the two fence rules are
disjoint, so swapping them is invisible.

**Markdown is 0.2% of painted characters**, so under the bounded-list policy the
question is whether it is worth promoting at all rather than how to do it. **The
language list is closed at seven, so the live answer is no** — this is parked rather
than pending.

---

## The tool renderer

**Why it exists.** `Part::Tool` went straight to `Unsupported("tool")` and the panel
sink panics on a refusal, so **`ch search -t` with colour exited 101 having already
printed — silent truncation, not a visible failure.** Tool calls are in 91% of
`.claude` sessions and 80% of `.codex` ones.

**What is landed: the common path, 87.6% of tool parts.** A header — `⏺`/`⎿`, the
tool name in one of four accents from `theme.py`, `  ·  error` when it failed, and
the first display-worthy attribute home-collapsed — then a coloured `LeftRail` around
a fenced markdown body.

**`ToolHeader` is a renderable rather than a build-time string**, and that is
load-bearing: panels and rails claim their columns first, so the key argument is
elided at the width it actually renders at. **Eliding earlier fixed the header at 44
columns, which was a shipped defect.**

**Two changes outside the tool code, both announced and both accepted.**
`codecs.rs` computed a tool's attributes and content inline inside each XML renderer;
`session_render` needs the same values, so `tool_use_parts` and `tool_result_parts`
were extracted and **both XML renderers routed through them** — one authority instead
of two, existing behaviour unchanged. And **`BodyContext` gained `home`**, because
`collapse_home` needs it and Python reads `Path.home()` inside the helper: **a
renderer that reads the environment cannot be gated at two different homes.**

### What is not built, and how each is held

**`KNOWN_UNBUILT_BODIES` in `body_oracle_tests` is an asserted exact set** holding
`tool-edit-diff`. The tree stays green and the gap stays named; **building the diff
makes that case agree and the test demands its own entry be removed.** Any other case
joining the set is a regression rather than a gap.

**1. The Edit diff. Ruled, do not re-open.** `Edit` renders a unified diff of
`old_string` against `new_string`; this renderer shows its fenced content. **The
ruling is to build it on the vendored `difflib` crate (0.4.0, MIT, ~500 lines) with
one operator corrected**, not to hand-port CPython's 687 lines. Measured:

    difflib as published, real Edits        2,812 / 2,814   99.93%
    difflib patched,      real Edits        2,814 / 2,814   100%
    similar,              real Edits          273 / 2,814    9.70%

**⚠ And the number that decides it is from a second corpus, because the first cannot
see the defect.** Only 3 of 2,814 real Edit calls reach 200 lines, so autojunk is
barely exercised. Over 900 pairs built from real file bodies above 200 lines — where
autojunk changes CPython's own answer 23.9% of the time — **the published crate is
28.0% correct and the patched one 99.67%.**

**The defect is one operator** in `sequencematcher.rs`'s `chain_second_seq`: CPython
**deletes** elements appearing in over 1% of positions, and the crate **keeps exactly
those**. The autojunk filter is inverted, so on any long sequence it matches against
blank lines. **Patching is not optional.**

Residue 3 of 900, 0.33%, mechanism unknown, none reachable from real Edits. **A
hypothesis was tested and disproved rather than left standing:** implementing
CPython's two-phase extension in `find_longest_match` made it *worse*, 99.67% →
92.56%, because with `isjunk=None` the second phase extends over nothing. Reverted;
the 99.67% is from the reverted state.

**2. ⚠ The `Read` line-number gutter, and it has NO failing case.** The two `Read`
cases in the body oracle **pass**, and they pass for a reason unrelated to the
gutter: **a Claude `tool_result` carries no tool name, so the result resolves to
`Tool` rather than `Read`, and both routes fall through to the fenced body.** They
agree by accident.

**So the successor's first question is not how to build the gutter — it is how the
product resolves a result's tool name from its paired use.** Until that is answered a
case cannot be shaped correctly, and **a wrongly-shaped case is worse than a missing
one.** The gutter itself is ~25 Rust lines plus a generated filename→lexer table on
the machinery that produced `syntax_lexers.rs`.

**Half the extension work delivers no colour, and that is the approved outcome.** Over
2,497 real `Read` calls with a path: 48.3% resolve to a promoted language, 40.3% to
an unported one, 11.4% to none. **Markdown alone is 37%, the single largest, and is
not promoted.** The gutter is needed regardless — **line numbers are unconditional
geometry, not highlighting.**

---

## Next

1. **The Edit diff**, on the vendored patched crate. Ruled; the measurement is above.
2. **The `Read` gutter**, after answering the tool-name-resolution question.

**Nothing else.** The language list is closed at seven, and the 570-lexer residue is a
property rather than a task: Pygments defines 597 lexers, this corpus names 27, and
the gated plain fallback is what everything else gets.
