# Rust syntax-highlighting alternatives

Evidence snapshot: 2026-08-29T14:33Z. The tree already has TypeScript, TSX,
Bash, and Python tables. JSON and Markdown remain.

## Keep the current port for this cutover

**Arborium is the only viable full replacement I found.** Its measured colour
quality is good, and its integration surface fits the renderer. It can replace
the custom lexer engine and all language tables. It cannot replace only the
tables because Tree-sitter grammars require the Tree-sitter engine.

I still recommend finishing the current port. Four exact families are now
landed, while Arborium's wrapper is less than one year old. Switching now also
replaces proven exact gates with a new statistical quality gate. JSON and
Markdown remain unmeasured under Arborium.

Arborium is worth keeping as a later deletion project. The final experiment
below can promote it sooner if the team values long-term source reduction more
than the shortest cutover path.

## Arborium gives good visible fidelity, despite different token boundaries

[Arborium](https://github.com/bearcove/arborium) bundles Tree-sitter grammars,
queries, highlighting, and raw byte spans. Its selective Cargo features cover
TypeScript, TSX, Bash, Zsh, JSON, Python, and Markdown. Downstream builds use
checked-in generated parsers and queries. They need no Python, network, or
runtime grammar files.

The first probe compared run boundaries against the current Pygments oracles.
That metric looked mediocre for Bash and Python. Gilad's clarification made it
the wrong decision metric. Different boundaries can still paint the same style.

I therefore learned one Pygments Monokai style per Arborium language and capture
tag on four folds. I scored the fifth fold, then rotated all five folds. This is
a small realistic mapping, not a per-token repair. Each family used 9 to 15
capture tags.

| Family | Cases | Characters | Boundary agreement | Exact boundary cases | Monokai style agreement | Painted recall | Painted precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TypeScript | 507 | 272,654 | 86.8% | 25 | **91.6%** | 89.8% | 92.6% |
| TSX | 97 | 28,946 | 87.8% | 9 | **90.6%** | 88.6% | 90.6% |
| Bash | 1,031 | 260,900 | 59.3% | 28 | **96.9%** | 93.8% | 99.8% |
| Python | 270 | 63,591 | 61.5% | 15 | **89.3%** | 81.7% | 93.5% |

The weighted style agreement is 93.5% over 626,091 characters. Painted recall
and precision prevent default-coloured text from hiding weak highlighting.

These corpora contain real chat fences and malformed snippets. Arborium returned
spans for all 1,905 cases. Tree-sitter explicitly targets useful results during
syntax errors, which matches this input shape. [Tree-sitter documents that
contract directly](https://github.com/tree-sitter/tree-sitter).

TSX has weaker evidence because authored cases carry much of its gate. JSON and
Markdown have no current token oracle, so their visible fidelity remains
unknown. Markdown is low-share, but JSON is not.

Probe sources and locked dependencies are under
`probes/arborium-boundaries/` and `probes/style_agreement.py`. The three original
oracle SHA-256 prefixes were `bf5839d6`, `6ccc9500`, and `fc3310e0`.

## Arborium replaces both the engine and the tables

Arborium's `highlight_spans` returns start, end, and capture name. Its
[`Span` contract](https://docs.rs/arborium-highlight/latest/arborium_highlight/struct.Span.html)
uses byte offsets. `spans_to_flat_tokens` resolves overlaps into one theme tag
per byte.

The integration keeps all existing code-block geometry. It needs only a target
language selector, a byte-span adapter, and a language-specific style map. The
measured maps need 9 to 15 entries per family. Search highlighting and terminal
colour downgrade remain after this layer.

This replaces `syntax_lexer.rs`, `syntax_tables.rs`, and their exact stream
gates. It can also shrink the 950-line Pygments alias table and the 524-line
style table. The maintained savings are smaller than the raw line count because
the large tables are generated.

It also changes the JSON cost. Arborium's JSON grammar removes the custom
scanner which every Pygments-shaped option needs.

The real maintenance reduction is the 573-line driver, about 1,500 lines of
generation and corpus tools, and Pygments-specific promotion logic. The current
12 MB oracle set can also leave after a new quality gate exists.

The wrapper is not yet battle-tested. The repository started on 2025-11-30. It
now has about 483 stars, 26 crates.io reverse dependencies, and frequent 2026
releases. [Discord has built an Arborium runtime around it](https://github.com/discord/arborium-rt),
but that runtime also records upstream overlap fixes.

Its base is much stronger. Tree-sitter has over 26,000 stars, over 11,000 GitHub
dependents, and 99 releases. Its highlighting library is used on GitHub.com for
several languages. The target grammar crates have millions of downloads.

Arborium uses pinned forks of Tree-sitter and its highlighter. The fork supports
its plugin and WebAssembly systems. Pinning gives deterministic behaviour, but
it also makes Arborium the security and update authority.

Licensing is clean for this set. Arborium is MIT or Apache-2.0. The selected
grammar crates declare MIT licenses. Arborium also ships a generated third-party
license inventory.

## The build cost is material, while runtime cost is small

The selective probe enabled seven requested languages. Markdown pulled HTML,
CSS, JavaScript, JSDoc, TOML, and YAML for injections. Cargo reported 33 unique
normal dependency-tree lines.

The standalone release binary was 7.6 MiB. The current `ch` binary was 3.0 MiB.
These sizes are not additive because both binaries share Rust and regex code.
Expect a several-MiB package increase, not a precise 4.6 MiB increase.

The three-language clean build took 12.5 seconds on this M2 Pro. Adding the
remaining features took 6.7 seconds with shared dependencies cached. The probe
target directory reached 145 MiB.

Runtime was small. Arborium processed the 507 TypeScript cases in 0.12 seconds.
TSX took 0.05 seconds, and Bash took 0.04 seconds. Peak process memory was 35 MB
for TypeScript. This work should not bind `ch search`.

Arborium requires Rust 1.85 for its grammar and highlight crates. That matches
this package's declared minimum.

## Direct Tree-sitter is mature, but it recreates Arborium's integration work

The official [`tree-sitter-highlight`](https://docs.rs/tree-sitter-highlight/latest/tree_sitter_highlight/)
crate and individual grammar crates are the mature substrate. They cover every
target language and expose byte spans. They tolerate incomplete code and package
offline through Cargo.

This combination **can replace the custom engine and language tables**. It
cannot replace only the tables. The grammar, highlight query, and highlight
engine form one unit.

Using it directly requires selecting compatible grammar and query revisions.
It also requires flattening nested events and resolving Markdown injections.
That creates local version-sync and integration work which Arborium already
owns. I reject the direct combination for this rewrite.

## Two-face fixes Syntect's coverage, but its processing cost is too high

[`two-face`](https://docs.rs/two-face/latest/two_face/) bundles Bat's Syntect
syntaxes and themes. It adds TypeScript and TypescriptReact, plus every other
target language. It also bundles Monokai Extended, not Pygments' Monokai.

This option **can replace the custom engine and language tables**. It cannot
replace only the language tables. Its TextMate grammars require Syntect.

It is mature by Rust-library standards. It has about 6.7 million downloads and
102 crates.io reverse dependencies. Current users include Typst, GitUI, and
Iced's highlighter.

The specific two-face probe found 86.0% TypeScript boundary agreement, 84.0%
TSX, and 57.5% Bash. That does not prove weak visible quality after the parity
bar changed.

The command cost rejects it first. The pure-Rust `fancy-regex` build took 2.45
seconds and 171 MB for the TypeScript corpus. Bash took 0.35 seconds and 37 MB.
Arborium ran the same corpora in 0.12 and 0.04 seconds.

Two-face loads a broad embedded syntax set. Pruning or serializing a custom set
would add asset-generation ownership and erase much of its simplicity. I reject
it for a short-lived CLI process.

## The remaining packages cannot meet the current contract

[`Syntastica`](https://docs.rs/syntastica/latest/syntastica/) supports all target
languages and raw highlight data. It **could replace both engine and tables**.
Its crates.io parser set is limited and described by its author as outdated.
Its full set fetches pinned Git repositories during the build. That breaks the
desired offline build shape. Version 0.6.1 has one crates.io reverse dependency,
and its main crate uses MPL-2.0. I reject it on packaging and maturity.

[`Inkjet`](https://github.com/Colonial-Dev/inkjet) covers every target language
and packages parsers offline. It **could replace both engine and tables**. Its
owner archived it in September 2025 and states that it is unsupported. I reject
it on maintenance.

[`Lumis`](https://github.com/leandrocp/lumis) is Inkjet's active successor. It
covers every target language and **could replace both engine and tables**. Its
current crate requires Rust 1.91, while this package declares Rust 1.85. It has
three crates.io reverse dependencies. I reject it for this rewrite.

The default Syntect set remains rejected. It omits the language family which
contains 63.9% of painted characters. Two-face fixes that omission, so the
default-set result does not reject two-face by itself.

I found no maintained Rust implementation of Pygments `RegexLexer`. General
regex and lexer crates would keep the language definitions and state logic local.
They therefore **cannot replace the custom work**.

## The shortest remaining experiment measures the original 1,200 blocks

Freeze the same 1,200-block corpus used for the Syntect decision. Run Arborium
for all target tags, including JSON and Markdown. Learn each language's capture
map on 80%, then score the held-out 20%.

Record exact style agreement, painted recall, painted precision, parse failures,
and process time. Inspect the 30 blocks with the lowest agreement side by side.
This single run separates harmless boundary differences from visible mistakes.

Use a go bar of at least 90% weighted style agreement, at least 80% painted
recall per major family, and zero failures. If Arborium passes, it is good enough
for a later simplification. If it misses, finish the Pygments path permanently.
