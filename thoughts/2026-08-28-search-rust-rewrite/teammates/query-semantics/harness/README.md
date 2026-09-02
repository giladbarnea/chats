# Query-semantics differential harness

A bench for one question: **does a candidate engine agree with CPython's `re`?**

CPython on `main` is the oracle. Every runner here records CPython's verdict first, then asks a candidate engine the same question and reports only the disagreements. It is useful whether we adopt the unmerged branch's engine, port it, or write our own.

## Layout

| Path | What it does |
| --- | --- |
| `probes1.json` | 50 probes: syntax surface, anchors, Unicode classes, folding |
| `gen_probes2.py` | writes `probes2.json` — classes, ranges, boundaries, escapes |
| `gen_probes3.py` | writes `probes3.json` — predicted defects and the trap list |
| `gen_probes4.py` | writes `probes4.json` — constructs isolated from the generated corpus |
| `generate_patterns.py` | Falsifier 1: assembles patterns across CPython's syntax surface |
| `classify.py` | buckets divergences by construct, so each bucket is one fix |
| `gen_boolean_cases.py` | writes boolean-layer and span cases |
| `boolean_authority.py` | CPython's verdict for parse outcome, tree shape, `iter_terms`, and spans |
| `src/bin/boolean.rs` | the branch engine's answer for the same |
| `diff_boolean.py` | reports which facet diverged, grouped |
| `src/bin/predicates.rs` | enumerates `\w` and multi-scalar lowerings for exhaustive comparison |
| `compare_predicates.py` | compares those against CPython over all of Unicode |
| `falsify_gates.py` | breaks the engine on purpose and proves each gate notices |
| `python_authority.py` | records CPython's verdict per probe, mirroring `compile_search_term` |
| `foldpairs.py` | generates every cased codepoint pair with CPython's verdict |
| `diff.py` | prints disagreements, labelled `ACCEPT-BOUNDARY` or `MATCH-SEMANTICS` |
| `src/main.rs` | candidate: the Rust `regex` crate |
| `src/bin/branch.rs` | candidate: the unmerged branch's engine |
| `src/bin/folds.rs` | the full Unicode case-folding sweep |
| `src/bin/budget.rs` | when the branch engine's step budget trips |
| `src/bin/falsenegative.rs` | finds inputs where the budget yields a wrong answer |

`ACCEPT-BOUNDARY` means the engines disagree about whether the pattern is *valid*. Because search falls back to an escaped literal on invalid patterns, that flips a pattern between regex and literal and silently changes which sessions match. It is the more dangerous of the two labels.

## Running it

The branch engine is not vendored. Fetch it first:

```sh
mkdir -p src/branch
git show 0ffde41:rust/search_query.rs               > src/branch/search_query.rs
git show 0ffde41:rust/search_query_unicode_names.rs > src/branch/search_query_unicode_names.rs
cargo build --release
```

Then:

```sh
uv run python gen_probes2.py probes2.json
uv run python gen_probes3.py probes3.json

for batch in 1 2 3; do
  uv run python python_authority.py "probes${batch}.json" > "py${batch}.json"
  ./target/release/branch "probes${batch}.json" > "branch${batch}.json"
  uv run python diff.py "py${batch}.json" "branch${batch}.json"
done
```

Swap `./target/release/branch` for `./target/release/rustprobe` to test the `regex` crate instead.

The full folding sweep, roughly 3,000 pairs:

```sh
uv run python foldpairs.py foldpairs.json
./target/release/folds foldpairs.json
```

The boolean layer and highlight spans:

```sh
uv run python gen_boolean_cases.py boolcases.json
uv run python boolean_authority.py boolcases.json > bool_py.json
./target/release/boolean boolcases.json > bool_branch.json
uv run python diff_boolean.py bool_py.json bool_branch.json
```

Exhaustive predicate comparison over all of Unicode — this is the instrument that found what no sampled corpus could:

```sh
./target/release/predicates > predicates.json
uv run python compare_predicates.py predicates.json
```

Falsify the gates. A gate that has never failed is not known to work, so this must pass before quoting any gate as evidence:

```sh
uv run python falsify_gates.py .
```

Budget behavior — watch stderr, that is where the trip warning goes:

```sh
./target/release/budget
./target/release/falsenegative
```

Falsifier 1, the accept/reject boundary over generated patterns. The seed makes the corpus reproducible, so a failure can be handed to someone else verbatim:

```sh
uv run python generate_patterns.py gen.json 4000 20260828
uv run python python_authority.py gen.json > gen_py.json
./target/release/branch gen.json > gen_branch.json
uv run python classify.py gen_py.json gen_branch.json
```

`classify.py` assigns each pattern to its first matching signature, so buckets overlap and some rows are mislabelled. Use it to triage, then isolate the real construct with a hand-written probe before believing it.

## Results as of 2026-08-28

Against CPython 3.14.7:

- **`regex` crate 1.13.1** — 39 divergent pairs in 50 probes. Unsuitable as the query engine.
- **Branch engine at `0ffde41`** — 11 defect classes. Sound strategy, local defects.
- **Folding sweep** — 3 divergent pairs in 2,965, all Turkish dotless i against ASCII `i`/`I`.
- **Generated corpus, 4,000 patterns** — 994 divergent pairs, *all* accept/reject. Zero match-semantics divergences: where both engines accept a pattern, they agree on what it matches. Two-thirds of the 994 are the single malformed-interval bug.
- **Boolean layer and spans, 438 cases** — 48 divergent pairs, all one cause: negated terms leaking into `iter_terms`. Zero divergences in parse outcome, error text, or tree shape. Zero span divergences wherever the literal set agrees.
- **Exhaustive `\w` sweep** — the engine matches 6,167 codepoints CPython does not, none the other way.
- **Gate falsification** — six named mutations, all six caught. The first run exposed the predicate gate testing a copied predicate rather than the engine; rewired, and the same mutation now moves it by 136,710.

Detail and analysis in `../query-semantics-map.md`.

## Adding probes

A probe is `{"id", "pattern", "haystacks"}`. Choose haystacks that isolate one behavior, and prefer explicit `\uXXXX` escapes over literal characters so nothing is lost in transit. Both runners apply the product's real flags: `MULTILINE | DOTALL`, plus `IGNORECASE` unless the case-sensitive mode is under test.
