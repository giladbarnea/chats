# Query semantics: authority map, evidence, and open decisions

Owner: `query-semantics`. Status: Phase 1 complete, awaiting G2. No production code touched.

Everything below that is marked *measured* was produced by a differential harness I built and ran in this session. It is kept at `harness/` next to this file, with reproduction steps in `harness/README.md`. Nothing here is quoted from the unmerged branch's own records as fact.

**Oracle revision: `8cb4c5f`.** Every characterization here was taken against CPython 3.14.7 running `src/chats/` at that commit. I ran the measurements through the working tree, so I verified rather than assumed the equivalence: `git diff 8cb4c5f -- src/chats/` is empty and there are no untracked files under it, so the tree was byte-identical to the commit throughout. This matters because `search-runtime` holds an exception to edit `src/chats/commands/search.py` for the clock seam, so the oracle is scheduled to move. Anything re-measured after that lands must name the new revision.

The candidate engine under test is `rust/search_query.rs` at `0ffde41`, and the crate comparison is `regex` 1.13.1.

---

## 1. Bottom line

Three results decide this scope.

1. **The Rust `regex` crate cannot carry `ch search` semantics.** Measured: 39 divergences from CPython across 50 probes, and the worst of them compile cleanly in both engines and silently mean different things. This is not a tuning gap. Any plan that assumes the crate is the query engine is unsound.
2. **A CPython-faithful engine is reachable, and one already exists.** The unmerged branch's `rust/search_query.rs` is std-only and 2,027 lines. I compiled it standalone and ran it against CPython, over both hand-written probes and 4,000 generated patterns. It diverges on 11 defect classes. I traced every one to a local, named cause. None require an engine-strategy change. Across the generated corpus its *matcher* never disagreed with CPython once, and its boolean grammar is exact — the divergences are in the validator, plus one leak of negated terms into highlighting.
3. **The step budget is the real problem, and its accepted framing is false.** The budget is not a catastrophic-backtracking guard. Measured: an ordinary pattern over an ordinary message returns a confident wrong answer.

Nothing in this scope is unreachable in Rust. The costs are enumerated in section 6.

---

## 2. Current authority

One file owns query truth today: `src/chats/search_query.py` (334 lines). Its only production consumer is `src/chats/commands/search.py`.

The parse path is `parse_search_query(pattern, case_sensitive) -> SearchQuery`, where `SearchQuery` is `SearchTerm | AndQuery | OrQuery | NotQuery`. A term carries four fields, all four of which cross the layer boundary into candidate planning: `pattern`, `regex`, `literal_candidate`, `case_sensitive`.

Three behaviors in that file are load-bearing and easy to lose in a rewrite.

**Regex-or-literal fallback.** `compile_search_term` compiles the pattern; on `re.error` it recompiles `re.escape(pattern)` instead. So the set of patterns CPython *accepts* is part of the public contract. If a native validity gate accepts a different set, matching silently changes in either direction, with no error anywhere. `search-runtime` observed `ch search '('` exiting 1 rather than erroring; that is this fallback, and it is deliberate — `search_query.py:102-104`.

**Two different case models coexist, and a guard keeps them apart.** Matching uses `re.IGNORECASE`, which is single-codepoint `tolower` plus a 50-entry fixes table — *not* full case folding. `literal_candidate` uses `str.casefold()`, which *is* full case folding. Measured, they genuinely disagree: for pattern `ß`, `literal_candidate` is `'ss'` while the compiled regex does not match `ss`. `literal_candidate` is therefore **not** a sound lower bound for the regex in general. What makes it sound today is the `.isascii()` guard on every byte-gate path in `commands/search.py`, where the two models coincide. That guard is a correctness invariant, not an optimization detail.

**Session-wide term evaluation.** `_search_conversation_content` satisfies each term by a match anywhere in the session — any summary, the current custom title, or any rendered message. So `AND` terms may match in different messages. Displayed matches are the union over positive terms; `NOT` contributes no terms to the display set (`NotQuery.iter_terms` yields nothing).

Highlighting is narrower than matching, by design: `_build_highlight_regex` highlights only terms that are plain literals, longest first, and is case-insensitive unless *every* term is case-sensitive.

---

## 3. Evidence: the Rust `regex` crate against CPython

Measured, 50 probes × 2 case modes, CPython 3.14.7 against `regex` 1.13.1 under `MULTILINE|DOTALL[|IGNORECASE]`. **39 divergent pairs.** Three kinds, worst last.

**CPython accepts, the crate rejects** — so the crate takes the literal fallback and returns nothing where legacy returns hits: lookahead, lookbehind, backreferences, named backreferences, conditionals, atomic groups, inline comments `(?#…)`, `\Z`, octal escapes, `\N{…}`.

**The crate accepts, CPython rejects** — so the crate returns hits legacy never returns: `\p{L}` and `\p{Greek}`, and mid-pattern global flags such as `foo(?i)bar`. Both are things a user plausibly types. `(?R)` is the sharpest case: the crate reads `R` as its CRLF flag, making the pattern empty, so `ch search '(?R)'` would match **every session** where legacy matches none.

**Both accept, meanings differ — no error anywhere.** POSIX classes (`[[:alpha:]]`), class intersection (`[\w&&[^a]]`), class difference (`[a-z--[aeiou]]`), and every case-folding gap in section 4.

That third group is why this is a ruling and not a trade-off. A divergence that raises no error on either side cannot be caught by anything except a differential test that already knows to look.

---

## 4. Evidence: Unicode case folding is a closed, three-pair problem

I swept **all 2,965** ordered pairs of cased codepoints in Unicode — every `(c, partner)` where partner is `c.lower()`, `c.upper()`, `c.casefold()`, or a CPython `_EXTRA_CASES` entry — and compared CPython's `re.IGNORECASE` verdict against the crate's.

CPython matches all 2,965. The crate diverges on exactly **three**, all the same character:

| pattern | text | CPython | `regex` crate |
| --- | --- | --- | --- |
| `i` | `ı` U+0131 | match | no match |
| `ı` U+0131 | `I` | match | no match |
| `ı` U+0131 | `i` | match | no match |

This is the one place where a scary-sounding open-ended risk turned out to be finite and small. CPython's table adds Turkish dotless i to ASCII i; default Unicode simple folding does not.

I re-probed the folding pins `context-curator` sent, independently: `ss` does **not** match `ß` in either direction; `i`/`İ`, `s`/`ſ`, and `k`/`K` (U+212A) all match in both directions. All confirmed.

---

## 5. Evidence: the branch engine against CPython

I extracted `rust/search_query.rs` and its 39,965-line Unicode name table from `0ffde41` into a standalone harness. It is std-only and compiles clean. I ran it against the same probes.

It is far closer than the crate: **11 defect classes** across roughly 4,500 probes and cases, versus 39 divergences in 50 for the crate alone. The strategy is sound. The defects are not strategic.

| # | Defect | Proof | Cause |
| --- | --- | --- | --- |
| 1 | **Literal fallback drops IGNORECASE** | `ch search 'Foo('` matches `foo(` today; engine returns no match | `compile_search_term` calls `Regex::compile(&escaped, false)`, hard-coding case-sensitive. CPython keeps the caller's flags |
| 2 | **`\d` is ASCII-only** | `\d` misses `٠` (Arabic-Indic) and `०` (Devanagari) | `category_matches` for the digit category |
| 3 | **Character ranges ignore the extra-cases table** | `[a-z]` misses `ſ`; `[h-j]` misses `ı`; `[^h-j]` wrongly matches `ı` | `ClassMatcher` applies `extra_for` to single literals but not to ranges |
| 4 | **`\z` unsupported** | CPython 3.12+ accepts `\z`; engine rejects, falls to literal | validator predates the CPython addition |
| 5 | **Malformed intervals reject the whole pattern** | `zzz\|a{5,x}` finds nothing; CPython finds `zzz` | validator errors instead of backtracking to a literal `{` |
| 6 | **FutureWarning carries a baked build path** | stderr printed `…/rustprobe/src/chats/search_query.py:96` from my harness dir | `env!("CARGO_MANIFEST_DIR")` plus `SEARCH_QUERY_SOURCE_LINE = 96`, naming a file that branch deletes |
| 7 | **Quantified zero-width assertions wrongly accepted** | CPython rejects `\b{2}`, `\B{2}`, `^{2}a` as "nothing to repeat"; engine compiles them | validator permits a quantifier after an assertion atom. Quantified *groups* such as `(?=a){2}` are correct in both |
| 8 | **Invalid group names wrongly accepted** | `(?P<1n>a)`: CPython falls to literal and matches the text `(?P<1n>a)`; engine matches `a` | group-name validation does not reject a leading digit or a dash |
| 9 | **`(?a)` and `(?u)` flags wrongly rejected** | `(?u)\w` matches `é` in CPython; engine falls to literal and matches nothing | validator knows `i m s x` but not the ASCII and Unicode mode flags. `(?L)` is correctly rejected by both |
| 10 | **`\w` over-matches on 6,167 codepoints** | exhaustive sweep of all 1,114,112 codepoints: engine matches where CPython does not, on combining marks such as U+0345 and U+0363–U+036F. Zero divergences the other way | `is_word_character` is Rust's `is_alphanumeric()`, which uses the Alphabetic *derived property*. CPython's is category-based |
| 11 | **Negated terms leak into highlighting and the match set** | `ch search 'a NOT b'` — CPython's `iter_terms` yields `['a']`, the engine yields `['a','b']`, and the engine paints a span over `b` that CPython does not | `Query::iter_terms` line 127: `Query::Not(operand) => operand.iter_terms()`. CPython's `NotQuery.iter_terms` yields nothing |

Defect 1 is the one I would lead with. Case-insensitive is the default mode, an unbalanced paren is a common shell-quoting accident, and the failure is silent.

Defect 6 is the same anti-pattern this project already removed once — a fabricated Python artifact built from a build-time path.

Defects 7, 8, and 9 came out of the generated corpus in section 5a, not from hand-written probes. That is the argument for the generator: they are all boundary cases nobody would think to write down.

Defect 10 came from neither. The generated corpus produced no `\w` disagreement in 4,000 patterns, because a divergence needs one of 6,167 specific codepoints in the haystack and my haystacks were built from the pattern's own literals. I only found it by enumerating all of Unicode. **Two engine behaviors looked suspicious and the corpus was silent on both; one was real and one was clean.** Silence from a test that cannot express the case is not evidence, which is why both got enumerated rather than sampled.

The clean one, recorded so nobody re-opens it: the engine's `tolower` keeps only the first scalar of a lowering. Exactly one scalar in Unicode has a multi-scalar lowering — U+0130 `İ` — and CPython's `re.IGNORECASE` equates it with the kept scalar anyway, so the truncation is harmless. Closed.

### 5a. The generated-pattern falsifier, built and run

Falsifier 1 is no longer a design. `harness/generate_patterns.py` assembles patterns from a fragment grammar spanning CPython's syntax surface and the near-misses just outside it, then `harness/classify.py` buckets the divergences by construct so each bucket is one fix.

Measured on 4,000 generated patterns (seed 20260828, CPython accepts 41.9%), against the branch engine:

- **994 divergent pairs, and every single one is an accept/reject disagreement. Zero match-semantics divergences.** For patterns both engines accept, the branch's matcher agreed everywhere in this corpus. That is a strong positive result for its VM and its folding model, and it concentrates all remaining risk on the validator.
- **644 of the 994 — about two-thirds — are the single known malformed-interval bug** from defect 5.

One caveat on reading the bucket table: `classify.py` assigns each pattern to its first matching signature, so buckets overlap and some are mislabelled. For example `\B{,2}` lands under "open-min interval" when the real cause is defect 7. The isolated probes in `gen_probes4.py` are authoritative; the buckets are for triage only. I re-probed `a{,2}`, `a{,}`, `a{}`, and `a{4,2}` directly and all four agree with CPython, confirming those constructs are genuinely fixed.

**The four constructs `context-curator` flagged are genuinely fixed at `0ffde41`.** I probed `a{,2}`, `a{,}`, `a{}`, `(?x)`, `(?x:…)`, verbose comments, variable-width lookbehind rejection, and `(?-m:^two$)`/`(?m:…)`. None diverged. That trap list is closed, verified independently.

---

## 6. Reachable, costly, or unreachable

**Nothing in this scope is unreachable in Rust.** The branch is the existence proof. What follows is cost, not possibility.

*Already paid, if we reuse:* the `\N{…}` name table (39,965 generated lines), the 50-entry extra-cases table, and the validator's coverage of CPython's syntax surface.

*Cheap:* all six defects above. Each is local. Defects 1, 4, and 6 are a few lines each.

*Genuinely ongoing:* fidelity tracks the CPython version. `\z` is the live proof — CPython gained it in 3.12 and the branch never noticed. This is a maintenance cost that a differential suite converts into a test failure instead of a silent regression.

*Known incomplete, and not on the branch's own limitations list:* `\N{…}` excludes algorithmic CJK and Hangul names. I have not measured its blast radius.

---

## 7. The step-budget decision, with the measurement

This is the gating question. My recommendation is in section 8; the measurement is here because it changes the question.

The accepted framing is that the 2,000,000-step budget guards against catastrophic backtracking, and the trade is *wrong and fast* against *correct and unusable*. **Measured, that framing is false, because the budget cannot tell the two populations apart.** A step counter conflates "this pattern is pathological" with "this haystack is large."

**Population 1 — ordinary patterns, ordinary messages.** The budget is reachable here.

- `.*zzqqxx.*` trips the budget on a **1,000-character** haystack.
- `[a-z ]*NEEDLE` over a 20,000-character message that **does** contain `NEEDLE` returns **no match**. A confident wrong answer.
- CPython answers that same case correctly in **5.9 ms**, and a 400,000-character version in 121 ms.

So for this population the trade is not *wrong and fast* against *correct and unusable*. It is **wrong** against **correct and single-digit milliseconds**. There is no dilemma.

Real message sizes, sampled from 2,636 rendered messages across 40 live sessions: median 200 characters, p90 1,509, p99 7,562, max 28,393. Messages large enough to matter are a small share, but they are exactly the tool outputs and file reads people search for.

Much of this is self-inflicted. `Regex::search` restarts a fresh backtracking run at every start offset (`for start in 0..=haystack.len()`), making an unanchored pattern quadratic where CPython's SRE rides literal prefilters and a `.*` fast path.

**Population 2 — genuinely catastrophic patterns.** Here the accepted framing holds. CPython on `(a+)+b` is exponential: 19 characters takes 19 ms, 23 takes 301 ms, 27 takes 4.8 s, 29 takes 18.8 s. That is *correct and unusable*, and it is what legacy does today.

One more property worth naming: the warning fires **once per process**, so a run over thousands of sessions prints a single line and then returns wrong answers silently.

---

## 8. Recommendations

**On the step budget.** Do not choose between silent-wrong and loud-error yet, because both are answers to the wrong question. In order:

1. **Fix the cost model first.** Prescan for the required literal and stop restarting the VM at every offset. This removes population 1 from budget range entirely, which is where the wrong answers actually come from.
2. **Then keep a budget purely as a pathological-pattern guard, and fail loud on exhaustion** — a real error and a non-zero exit. The first mate's instinct is right, and it matches this project's first tenet. But it is only safe *after* step 1: failing loud on today's engine would turn ordinary searches into hard errors, which is worse for the user than the wrong answer we have.
3. **Never silently return "no match".** That is the worst of the three options and it is what ships today on that branch.

On population 2, failing loud is a real divergence from CPython and I recommend accepting it deliberately. Legacy's "correct" answer there takes longer than any user will wait, so we are not trading away a behavior anyone can observe.

**On malformed intervals.** Fix, do not accept. This is a parser bug, not an engine-strategy question. CPython's rule is that a `{` which cannot parse as a quantifier is a literal `{`. The branch already applies that rule to `a{}`, so the machinery exists — it just is not reached for the malformed-with-content cases. Backtrack on interval-parse failure and emit a literal. Cost is low and the divergence changes truth inside alternations, which I measured.

---

## 9. What the existing native gates already answer

`rust/python_extension.rs` encodes real prior art, and it answers a **different question** from mine. The gates decide whether a term may be *probed* against raw bytes. They never claim a match; they only claim safe absence. Their `PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS` list of 20 scalars answers "which non-ASCII scalars fold onto ASCII, so we must defer" — a rejection-safety question.

That is **closed** and should not be re-funded. What stays open is authoritative matching — `term.regex.search(rendered)` — which the gates never touch. Sections 3 through 7 are all in that open space.

I accept `search-runtime`'s proposed boundary as written: I own what a term *means*, they own whether a term may be *probed*. Eligibility policy stays theirs, undivided. I will add one invariant to it from section 2: the `.isascii()` guard is what keeps `literal_candidate` a sound lower bound, so it is load-bearing and must not be relaxed.

---

## 10. Falsifiers and definitions of done

**Falsifier 1 — the accept/reject boundary. Built and running.** `harness/generate_patterns.py` plus `harness/classify.py`. Asserts the native validator accepts *exactly* the set CPython accepts, failing on disagreement in either direction. This is the highest-value test in the scope: it is the only thing that catches a silent regex-versus-literal flip, and it found defects 7, 8, and 9 on its first run. It is deterministic under a seed, so a failing corpus is reproducible.

**Falsifier 2 — matching parity under generated input.** For patterns valid in both, assert identical match verdicts over generated haystacks, in both case modes. Seed the generator with every construct from sections 3, 5, and the folding table.

**Falsifier 3 — the budget cannot change truth.** Assert no input in the corpus yields a verdict that differs from CPython's because of resource exhaustion. This falsifier is what the current branch fails.

**Falsifier 4 — no fabricated provenance.** Grep the built binary for build-time paths. Any user-visible warning naming a source file must name one that exists.

Definitions of done:

1. Every supported pattern shape returns the same hits, in the same order, as `main`'s Python, over a recorded corpus.
2. Malformed boolean queries exit 2 with the same message text.
3. The four `SearchTerm` fields survive into the native representation, so candidate planning reads the same properties it reads today.
4. Falsifiers 1 through 4 are attempted and green.

---

## 11. Contract gaps

1. **Warning text is user-visible output and nobody owns it.** The POSIX-class FutureWarning goes to stderr with a source path and line number. Native code has no such file to name. Reproducing it faithfully requires fabricating a Python artifact; not reproducing it changes observable output. This needs a ruling. My recommendation is to reproduce the message and drop the fabricated file-and-line prefix, then pin the decision in a test.
2. **`\N{…}` CJK and Hangul coverage is unmeasured**, and fell off the branch's own limitations list.
3. **`ch search '(?R)'`-class patterns** — patterns the crate accepts and CPython rejects — have no fixture coverage today, in either direction.
4. **Highlighting has no differential coverage.** It is a separate regex built from literal terms only, and no test pins it against a rendered message.

---

## 12. Files

To own, if the lift lands as `search-runtime` proposed: `rust/search_query.rs` (new, ported or adopted), and any generated Unicode tables it needs. I need no other Rust file.

To read but not own: `rust/python_extension.rs` gate logic, which stays with `search-runtime`.

Python side: `src/chats/search_query.py` is the oracle and must not change until the single cutover.

Tests are `contract-owner`'s. The harness at `harness/` is mine and is not a test suite; it is a bench I will hand over if wanted.

---

## 13. Grading the instrument

The harness claims: *if a candidate engine disagrees with CPython on pattern semantics, this reports it.* That claim needs a grade, and the honest grade is not perfect.

**Measured grade: 10 of the 11 known defects, with 1 structurally invisible to it.** Defects 1 through 5 came from hand-written probes, 7 through 9 from the generated corpus, 11 from the boolean and span instrument, and 6 from stderr I happened to be watching rather than from anything the harness checks by design. **Defect 10 it could not have found at any sample size**, and the `tolower` question it could not have closed either. Both needed exhaustive enumeration instead.

**What would falsify the claim.** Inject a known divergence into a known-good engine and check the harness reports it. Five classes were open when I first graded it. Two are now closed, and the closures found a defect and produced two strong positives.

1. **Haystack-domain divergence.** *Open, and inherent.* Proven by defect 10: haystacks are built from each pattern's own literals, so any divergence needing a specific codepoint absent from the pattern is unreachable at any sample size.
2. **Grammar-absent constructs.** *Open, and inherent.* The generator emits only what its fragment tables express.
3. **The boolean layer.** *Closed.* `boolean_authority.py` and `src/bin/boolean.rs` compare parse outcome, error text, tree shape, and `iter_terms` across 73 queries.
4. **Match spans.** *Closed.* The same pair compares highlight literal selection and the resulting character spans.
5. **Warning output.** *Open by delegation.* FutureWarning text and the step-budget warning's once-per-process firing are user-visible, and this instrument does not capture stderr. That coverage lives in `contract-owner`'s suite as pinned product behavior, not here. Recorded so the gap is not mistaken for an absence of risk.

Classes 1, 2, and 5 stay open deliberately. For 1 and 2 the answer is the recorded rule — enumerate when the domain is enumerable, and treat silence from a sampled corpus as no evidence. For 5 the answer is that it is someone else's instrument, which is fine as long as it is written down.

### 13a. What closing classes 3 and 4 found

Measured over 438 cases — 73 queries against 6 haystacks, in both case modes.

**One defect: number 11.** All 48 divergent pairs trace to a single cause, `Query::iter_terms` returning the operand's terms for a `Not` node where CPython yields none. It is user-visible twice over, because that list drives both the highlight literals and the displayed match set: `ch search 'a NOT b'` paints a span over `b`, and marks a message containing only `b` as a match.

**Two positives worth as much as the defect.**

*The boolean grammar is exact.* Zero divergences in parse outcome, error message text, or tree shape across all 73 queries — including precedence, the flat `NOT` form, the uppercase-only operator rule, quoting, and every malformed shape that exits 2. That whole public grammar is proven identical rather than assumed.

*Two unrelated span algorithms agree.* CPython walks an escaped-literal alternation sorted longest-first under `finditer`; the branch compares character by character through its own case equivalence and takes the longest match at each offset. Wherever the literal set agrees they produce identical spans — including overlapping literals of different lengths where longest-first ordering decides the answer, and folding cases such as `ı`/`I`/`i`, `K`/`k`, and `ß`/`ss` where the two case models could most plausibly have parted company.

**Byte-capture calibration does not apply here.** The instrument compares CPython `re` results in-process and never captures process output, so the probes that grade byte fidelity have nothing to grade. That is an exemption, not a pass — the grade above is the one this instrument actually needs.

### 13b. Falsifying the gates — and one blind gate found

The rule is that a gate guarding a ported algorithm ships with a deliberately wrong implementation, run as part of the gate. `harness/falsify_gates.py` applies six named mutations to `search_query.rs`, rebuilds, reruns every gate, and fails unless each mutation produces divergences the baseline did not have.

Each mutation names the hazard it stands for, because the mutation set *is* this harness's parameterization and the parameterization is the assumption:

| mutation | hazard it stands for | caught by |
| --- | --- | --- |
| `icase_off` | case-insensitive literal matching | term (+16), boolean (+27) |
| `word_class_ascii_only` | the `\w` predicate | term (+9), predicate (+136,710) |
| `dotall_off` | default compile flags | term (+6) |
| `and_binds_looser` | boolean operator precedence | boolean (+312) |
| `and_iter_terms_truncated` | term enumeration behind highlights and the match set | boolean (+391) |
| `error_message_drift` | malformed-query error text, user-visible on exit 2 | boolean (+24) |

All six killed.

**The first run failed honestly, and that is the point.** `word_class_ascii_only` moved the predicate gate by exactly zero. It should have been impossible: the mutation rewrites the `\w` predicate and that gate exists to compare `\w` against CPython over all of Unicode. The cause was that `predicates.rs` had *copied* the engine's predicate into itself, so it was testing my transcription rather than the artifact. It could never have failed.

It is now wired through the real engine — it compiles `\w` and searches each codepoint — and the same mutation moves it by 136,710. The 6,167-codepoint result in defect 10 was re-measured through the live path and is unchanged.

The term gate caught that mutation anyway, so nothing downstream was wrong. But a gate that cannot fail is not evidence, and this one had been quoted as evidence.

## 14. Leads that did not verify

Recorded because the standing instruction is to treat that branch's paperwork as leads.

`context-curator` relayed a "suffixed POSIX class asymmetry" — that `[[:alpha:]]` hits the literal text `:]` while `[[:alpha:]] class` misses. **Measured, both match.** Either the original fixture used different text or the characterization is wrong. It should not be encoded in any contract until someone reproduces it.
