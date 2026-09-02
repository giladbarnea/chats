# B3 fix plan: reconciling the query engine onto `main`

Prepared while B3 waits on A1. Line numbers are `rust/search_query.rs` at `0ffde41`. Every defect below was measured against CPython 3.14.7 with the harness beside this file; none is quoted from that branch's records.

## Rebase base check — done, and my file is clean

The standing rule is that `main` is the base and the branch must earn each difference. For this scope there is nothing to earn back:

- `src/chats/search_query.py` last changed on `main` at `8262afa`, **2026-08-09** — twelve days before the branch's merge-base (`a7e89eb`, 2026-08-21). The Python oracle is byte-identical on both sides.
- `src/chats/commands/search.py` is likewise untouched since the merge-base.

So no `main`-side repair to the query layer is missing from the branch, and the rebase for `rust/search_query.rs` is a clean port rather than a reconciliation.

**Two `main`-side repairs outside my file that the branch cannot contain**, flagged because the rule applies to whoever owns them: `src/chats/formatting.py` gained the `ToolHeader` width fix (`a51f32c`, 2026-08-28), which stops eliding a tool header's key argument at a hard-coded 44 columns and fits it to the width it actually renders at. `rust/main.rs` and `rust/python_extension.rs` also changed after the merge-base. The branch forked before all of it.

## Ordering

Cost model first, then the budget, then the validator defects. The first mate ruled this order and the reason is that the cost model is what takes ordinary patterns out of budget range — fixing the budget first would convert silent wrong answers into loud failures on ordinary searches, which is worse for the user.

### Step 1 — cost model (`Regex::search`, line 1531)

```rust
for start in 0..=haystack.len() { … vm.run(thread) … }
```

A fresh backtracking run at every start offset makes an unanchored pattern quadratic where CPython rides literal prefilters. Two changes: extract a required literal from the compiled program and prescan for it, and stop restarting the VM per offset. Measured effect to beat: `.*zzqqxx.*` currently trips the two-million-step budget on a 1,000-character haystack.

### Step 2 — budget as a pathological guard (lines 1235-1245)

Keep a budget, but fail loud on exhaustion — a real error and a non-zero exit. Never return `None` as if it meant "no match". Also remove the process-global `STEP_LIMIT_WARNED` latch: today the warning fires once per process, so a real run prints one line and then returns wrong answers silently for everything after. Accepted as a deliberate divergence from CPython for genuinely catastrophic patterns, and it goes in the change log as one.

## The eleven defects

| # | Site | Change |
| --- | --- | --- |
| 1 | line 167 | `Regex::compile(&escaped, false)` hard-codes case-sensitive. Pass `!case_sensitive`, matching CPython, which recompiles the escaped literal under the caller's flags |
| 2 | line 909-910 | `Category::Digit => character.is_ascii_digit()`. CPython's `\d` is Unicode: use the decimal-digit property so `٠` and `०` match |
| 3 | line 936-946 | The `ClassItem::Range` ignorecase arm ends in `extra_for(tolower(*low)).contains(&character) && false` — a dead expression. Test whether *any* member of the character's CPython case-equivalence class falls in the range |
| 4 | line 769 | Add `'z' => Ok(Node::Anchor(Anchor::StringEnd))` beside `'Z'`. CPython accepts `\z` since 3.12 |
| 5 | lines 421, 436 | The two `return Err(())` arms reject the whole pattern on a malformed interval. Do what the empty-minimum arm at 405-408 already does: `self.position = start; return Ok(None);` so `{` becomes a literal. Keep the `max < min` rejection at 378-381 — CPython rejects `a{4,2}` too, and I confirmed both agree |
| 6 | lines 262-283 | `warning_text` builds a path from `env!("CARGO_MANIFEST_DIR")` and `SEARCH_QUERY_SOURCE_LINE = 96`, naming a Python file this branch deletes. Drop the fabricated file-and-line prefix. Needs the section 11 ruling first |
| 7 | line 349-351 | `if matches!(node, Node::Anchor(_)) { return Ok(node) }` returns *before* looking for a quantifier, so `\b{2}` silently drops it. CPython raises "nothing to repeat". Return `Err(())` when a quantifier actually follows an anchor. Quantified groups such as `(?=a){2}` stay valid |
| 8 | line 479 | Group-name validation checks only emptiness and duplication. CPython also requires a valid Python identifier, so `(?P<1n>a)` and `(?P<n-x>a)` must be rejected and fall back to literal |
| 9 | lines 609-631 | The flag loop knows `i m s x` and rejects everything else. Accept `a` and `u`; keep rejecting `L`, which CPython also rejects for `str` patterns |

Defect 9 is the only one that is not purely local. `(?u)` is the default for `str` patterns, so accepting it is a parse-only change, but `(?a)` restricts `\w`, `\d`, `\s`, and `\b` to ASCII and therefore needs an ASCII flag threaded into `category_matches` the same way scoped multiline was threaded into anchor evaluation during the branch's own repair round. Defects 1, 4, and 7 are a few lines each.

## The two suspicious differences — both now measured

Both were enumerated rather than sampled, because both are finite and my generated corpus could not express either. One was real.

**Real, and it is defect 10.** `is_word_character` (line 903) is `is_alphanumeric() || '_'`. Swept over all 1,114,112 codepoints: the engine matches `\w` on **6,167 codepoints CPython does not**, and none the other way. The set is combining marks — U+0345, the U+0363–U+036F block, and similar — which Rust's `is_alphanumeric` admits via the Alphabetic derived property while CPython's predicate is category-based. Fix at line 903: use a category-based test rather than `is_alphanumeric`. `\W`, `[\w]`, and `\b` all read this predicate, so one fix covers four surfaces.

**Clean, and closed.** `tolower` (line 861) keeps only the first scalar of a lowering. Exactly one scalar in Unicode has a multi-scalar lowering — U+0130 `İ` — and CPython's `re.IGNORECASE` equates it with the kept scalar regardless, so the truncation cannot change a verdict. No change. Recorded so it is not re-opened.

Method note for whoever reviews this: the generated corpus was silent on both, and that silence meant nothing. A `\w` divergence needs one of 6,167 specific codepoints in the haystack, and my haystacks were built from each pattern's own literals, so the corpus could not have produced one at any sample size.

## What proves this done

Falsifier 1, the accept/reject boundary over generated patterns, must come back clean at a fixed seed — that is the test that catches a silent regex-versus-literal flip. Falsifier 3, that no input yields a verdict differing from CPython because of resource exhaustion, is what today's engine fails and what steps 1 and 2 exist to satisfy. Both live in `harness/`.

One caution carried forward: the negative results above are from corpora I designed, and a generator only finds what its grammar can express. Neither absence is proof.
