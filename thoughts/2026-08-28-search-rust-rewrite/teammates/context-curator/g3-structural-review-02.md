---
date: 2026-08-28
author: context-curator
role: G3 structural review, pass two
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
scope: rust/search/parse.rs grammar, codex.rs, session.rs strip semantics, python_strip adoption
verdict: no defects; one bounded open question for the decode owner
method_limit: targeted against criteria, not full reads — see the boundary note
---

# G3 structural review 02 — grammar and strip semantics

**Method boundary, stated up front.** I am at 75% of my context window, so this pass targeted specific criteria rather than reading six files in full. That is a weaker review than pass one and I am marking it as such. What it covers, it covers by evidence; what it does not cover is named at the end rather than implied.

---

## 1. Argument grammar — **pass**

Checked the four properties I verified on the abandoned branch, since those are the ones a hand-written argparse emulation gets wrong.

| Property | `rust/search/parse.rs` |
| --- | --- |
| Long-option abbreviation | `LONG_OPTIONS` table at 83; prefix match at 657–659 |
| **Exact match beats prefix** | 661–663 — an exact hit collapses the candidate set to one |
| Ambiguity error | 666, listing candidates in table order |
| Error envelope | `ch search: error: ` at 884 |

Exact-match priority is the one worth calling out. Without it `--list` would be ambiguous against itself in any table containing a longer option with the same prefix. It is present.

## 2. The Python-versus-Rust strip divergence — **known, handled, and the right shape**

Python's `str.strip()` removes what `str.isspace()` accepts. Rust's `str::trim()` removes Unicode `White_Space`. **These differ on the C0 separators U+001C–U+001F**, which Python strips and Rust does not. Measured:

| Codepoint | Python strips |
| --- | ---: |
| U+001C–U+001F | **yes** |
| U+0085, U+00A0, U+2028, U+3000 | yes |
| U+200B | no |

`rust/session.rs:131` defines `pub fn python_strip(value: &str) -> &str`, and `session.rs:356` carries a test named `python_strip_removes_the_c0_separators_rust_trim_leaves`, asserting that a leading U+001C still yields one JSONL entry and adding `assert!(content.trim().starts_with('\u{1c}'))` — proving the divergence in the same test that guards against it.

**That test is the standard.** It does not merely pin the correct behaviour; it pins the incorrect behaviour beside it, so a reader who "simplifies" to `.trim()` gets a failure that explains what they broke.

`python_strip` is applied at **10 sites** across `search_confirm.rs`, `codex.rs`, and `session.rs` — the message-text and JSONL paths, which is where Python uses `.strip()`.

## 3. Open question for the decode owner — bounded, not a defect claim

Bare `.trim()` remains in use: **9 sites in `codex.rs`, 23 in `session.rs`**, the same file that defines `python_strip`.

The `codex.rs` sites I sampled are all inside **tool-script parsing** — `script[start + name.len()..].trim_start()`, `script[open + 1..close].trim()`, `argument.trim()`. That is a different domain from JSONL message text: it parses a generated shell script.

**So the question is not whether bare `.trim()` is wrong. It is whether the Python counterpart at each of those sites uses `.strip()`.**

- If Python uses `.strip()` there, those sites diverge on C0 separators, exactly as the message-text paths would have.
- If Python uses a regex, `shlex`, or a split, there is no divergence and bare `.trim()` is correct.

I could not resolve this within my remaining window. It is a fast check for whoever owns the decoder, because they know which Python function each site ports.

**Why it is worth asking rather than assuming.** This is the same shape as the stderr consoles: the correct helper exists in the tree, immediately beside code that does not use it. That is not evidence of a defect — but it is exactly the configuration where one hides, because the reviewer sees a correct pattern nearby and assumes it was applied everywhere it was needed.

## What this pass did not cover

Named rather than implied, since a stated negative is only as strong as the shape searched for:

- `color.rs`, `cells.rs`, `plan.rs`, `python_io` — not read.
- `codex.rs` and `session.rs` were queried against strip semantics and grammar properties only. Their decode logic, ordering, and error paths are unreviewed.
- The four timing economies remain held for the engine.
