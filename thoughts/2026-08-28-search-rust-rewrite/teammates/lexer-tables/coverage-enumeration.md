---
date: 2026-08-30
author: lexer-tables
purpose: what is left to port under the corrected coverage rule, counted and classified
corpus: 36,539 fenced blocks over 3,000 real session files, seed 23
probe: teammates/lexer-tables/probes/enumerate_target_lexers.py
---

# What is left to port

**The corrected rule is that every fence language legacy recognises and colours must
still be coloured after the cutover.** Plain output is parity only where legacy also
rendered plain, which is where the tag reaches no Pygments lexer at all.

So there are two sets, and they are different sizes and different kinds of work.

## The two sets

    tags reaching NO Pygments lexer — plain is parity        401 blocks   1.1%   29 tags
    tags reaching a lexer with no table — the coverage gap  1,122 blocks   3.1%   21 lexers

**The plain set is small and needs no work at all**, because the plain path already
exists and is already gated. Its commonest members are `just` (184), `tsv` (65),
`mdx` (39), `mermaid` (26), `txt` (22) and `justfile` (19). **`mermaid` is the right
representative for a fallback gate** and the five interim tags — `css`, `html`,
`sql`, `xml`, `yaml` — are all wrong, because legacy colours every one of them.

## The coverage gap, ordered and classified

**The classification is the cost model.** A pure `RegexLexer` is batch work on
machinery used six times. Anything else needs an engine addition first.

| Lexer | Blocks | Chars | Kind | Tags |
| --- | ---: | ---: | --- | --- |
| SQL | 337 | 165,824 | table | `sql` |
| XML | 144 | 23,361 | table | `xml` |
| Markdown | 127 | 116,337 | **callback** | `markdown`, `md` |
| Bash Session | 105 | 6,935 | **scanner** | `console` |
| HTML | 83 | 44,233 | **callback** | `html` |
| YAML | 79 | 25,709 | **callback** | `yaml` |
| Diff | 57 | 30,022 | table | `diff` |
| TOML | 56 | 8,134 | table | `toml` |
| CSS | 52 | 12,853 | table | `css` |
| JSX | 38 | 7,988 | table | `jsx` |
| Lua | 10 | 4,458 | table | `lua` |
| VimL | 6 | 137 | **foreign lexer** | `vim` |
| Java | 6 | 638 | table | `java` |
| Docker | 5 | 887 | **foreign lexer** | `dockerfile` |
| Rust | 5 | 2,094 | table | `rust` |
| PowerShell | 4 | 505 | table | `powershell`, `pwsh` |
| GLSL | 3 | 300 | table | `glsl` |
| INI | 2 | 193 | table | `ini` |
| Nix | 1 | 99 | table | `nix` |
| Fish | 1 | 99 | table | `fish` |
| BibTeX | 1 | 13,452 | **callback** | `bibtex` |

**By kind:**

    table          616 blocks  14 lexers   no engine change; the procedure as it stands
    callback       290 blocks   4 lexers   needs a named callback action
    scanner        105 blocks   1 lexer    an imperative port, as JSON was
    foreign lexer   11 blocks   2 lexers   needs a group action that enters another table

**Fourteen of the twenty-one need nothing new**, and they carry 55% of the gap. The
two commonest of all — SQL at 15 rules over 2 states and XML at 16 over 3 — are the
two smallest tables in the list. **SQL alone closes 30% of the gap and is smaller
than any family already landed.**

## What each non-table kind actually needs

**Callback (Markdown, HTML, YAML, BibTeX).** A rule whose action is a hand-written
Python function. Markdown's is the fenced-code dispatcher, HTML's is in
`script-content`, YAML's is in `root`, BibTeX's opens a brace. **Each is a separate
hand port**, and the engine needs one new `Action` kind to name them. Markdown's is
already transcribed as a `bygroups` and held; see below.

**Scanner (Bash Session).** Not a `RegexLexer` at all, like JSON. **It is also the
hardest thing on this list relative to its size**, because a shell session
interleaves prompts with command output and delegates the commands to `BashLexer` —
so it is a scanner *and* a foreign-lexer case at once, for 105 blocks and 6,935
characters.

**Foreign lexer (VimL, Docker).** `using(PythonLexer)` and `using(BashLexer)`
respectively. The engine models `using(this)`, re-entering the same table; these
need a group action naming a different one. **11 blocks between them**, so the
engine addition costs more than the coverage it buys.

## Gateability, which the count does not show

**The gate this desk requires is real fenced content in the language.** Bash had
1,857 blocks and 430,266 characters; TSX had 66 and its gate says so.

    gateable on real content, comfortably    SQL, XML, Markdown, HTML, YAML, Diff, TOML, CSS
    thin — the TSX precedent applies         JSX, Bash Session, Lua
    authored cases would carry the gate      Java, Rust, PowerShell, GLSL, INI, Nix, Fish, VimL, Docker, BibTeX

**Ten of the twenty-one cannot have a real-content gate**, together carrying 34
blocks. **Their gates would rest almost entirely on authored cases**, which the TSX
precedent says must be stated in the gate rather than discovered.

## ⚠ The residue the count cannot close

**Pygments defines 597 lexers. This corpus names 27 of them.** A user can write a
fence in any of the other 570, and by the corrected rule every one that legacy
colours must be coloured.

**So an enumerated set is a coverage floor, not coverage.** Three ways to read that,
and the choice is the captain's rather than mine:

1. **Accept the floor.** Port what the corpus shows, and accept that a fence in an
   unseen language renders plain where legacy coloured it. **The measured exposure
   is 3.1% of blocks in this corpus, and it is a floor because the tail is long.**
2. **Port by class rather than by observation.** Every pure `RegexLexer` in Pygments
   is generatable by the machinery that exists; the generator refuses the ones that
   are not. **That is a different project from this one**, and its cost is dominated
   by gating, not by generating — 597 corpora do not exist.
3. **Change what an unported language does.** The plain fallback is already built,
   already gated and never truncates. **The corrected rule rejects it as a policy**,
   but it remains the only answer that is correct for a language nobody has seen.

**My recommendation, and it is only that:** take the fourteen table families in
block order, which needs nothing new and closes 55% of the gap; then decide on the
callbacks and the scanner with their real cost visible; and put the 570-lexer
residue in front of the captain as a policy question rather than a porting one,
because **no amount of porting closes it.**

## Markdown, held

Its table, corpus and gate are written and parked at
`teammates/lexer-tables/markdown-gate.rs.pending`. **They were built against
`handlecodeblocks=False`**, which the retracted ruling made correct and this rule
does not: a nested fence in a language legacy recognises must be coloured, which is
the nested-lexer case. **The oracle needs regenerating and the transcribed action
needs revisiting** if markdown is promoted under the corrected rule.

Two of its four mutations were also still failing when it was parked, and both are
findings rather than defects: **nothing transitions into `inline`**, so there is no
push to lose, and **the two fence rules are disjoint** — the untagged one requires a
newline immediately after the backticks — so swapping them is invisible.
