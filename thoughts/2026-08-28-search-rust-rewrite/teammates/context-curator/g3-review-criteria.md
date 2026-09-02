---
date: 2026-08-28
author: context-curator
role: independent reviewer, G3 handed-off packages
oracle_revision: 8cb4c5f
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0 (canonical recipe, tests/oracle_digest.py)
oracle_verification: RE-DERIVED at this digest on 2026-08-28. Every oracle-dependent
  claim in this document was re-run and reproduced identically. The earlier stamp on
  this file was a `git diff -- src/chats` digest, which cannot see .venv/bin/ch-legacy
  or the installed RECORD, so it could not have supported this claim — hence the
  re-derivation rather than a restamp.
status: written before the packages arrive, deliberately
---

# G3 review criteria

Written before either package exists. The charter's own discipline is that falsification criteria come before implementation; the same argument applies to reviewing it. A reviewer who decides what would falsify the work only after seeing it can rationalise around whatever it turns out to contain.

These are the specific things I will look for, committed in advance. Anything I find outside this list is a bonus, not a substitute.

---

## Package A — provider decode

### The governing trap

**A decode implementation that is *correct* about timestamps is wrong for us.** Rust's `chrono` is better than what we have. That is the problem, not the solution.

| Behaviour | Must remain | Falsifies the port if |
| --- | --- | --- |
| Lowercase ISO `z` | **rejected**, falling back to filesystem mtime | `2026-08-20T10:00:00z` parses |
| DST fold | two instants an hour apart **compare equal** in the fold | they order correctly |
| Sub-second precision | truncated to **microseconds** | nanoseconds survive |
| Uppercase `Z` and explicit offsets | parse to naive local | anything else |

The DST case cannot come from a corpus. It has to be constructed, and its absence looks exactly like adequate coverage.

### Decode semantics

- `first_jsonl_entry` **aborts** on the first non-blank line if it is invalid UTF-8, malformed JSON, or a valid non-object. Blank lines skip. It never scans onward. A port that skips-and-continues is wrong in the more helpful direction.
- **Two trim layers, opposite directions, and they must not be unified.** Byte-level trimming uses Python's four-byte JSON whitespace set. `str`-level trimming uses `str.isspace()`, which strips U+001C–001F where Rust's `.trim()` does not, and neither strips U+200B. A shared helper reintroduces whichever bug it did not inherit.
- Pi joined-agent envelopes: the `<duration_ms>` terminator is **optional**. Ambiguity resolves to `None`.
- Paths carry as **bytes** throughout. A path round-tripped through UTF-8 reintroduces the `UnicodeEncodeError` crash on non-UTF-8 filenames.

### Structural

- No fork of a scan. If a helper is extracted, the original is deleted in the same change or proven byte-identical. A copy that compiles is not an extraction.

---

## Package B — engine and views

### The eight that must not be fixed

Two land squarely here.

| Behaviour | Must remain | Falsifies if |
| --- | --- | --- |
| Age label vs colour | colour is **one bucket older** than the label — `1d` painted week, `1w` month, `1mo` old | they agree |
| `collapse_home` | **string prefix** match, so `/Users/<home>X/y` renders `~X/y` | path-component matching |
| `elide_to_width` | counts **code points**, so 8 CJK characters at budget 8 return unchanged at 16 columns | display-width measurement |
| `truncate_middle` | counts **code points**, so NFD loses 37% more than NFC | graphemes or columns |
| Age arithmetic | 30-day months, 365-day years | calendar arithmetic |
| Trailing space | exactly **one**, on exactly the **last** line, deleted; two preserved; non-last preserved | uniform stripping or uniform preservation |

The age one is the highest risk on the mission: the byte comparator normalizes that SGR away, so it can regress with no gate firing.

### Engine behaviour

- **Date verdicts are content-only.** No stat-mtime pre-filter, in any arm. Both the parallel and pager arms use the same predicate. The guarded variant was analysed and permanently closed — it cannot win on I/O.
- **Highlight painting never indexes the original string with offsets measured on a lowered copy.** Fold per character over the original using the same equivalence that defines search truth. `İ` grows 2 bytes to 3; the ligatures shrink 3 to 2.
- **Provider column reads discovery rows**, not gate survivors — all files, or the single `-p` provider.
- **A mid-window filter error flushes the accumulated window before printing**, or output order changes.
- **`re.IGNORECASE` is not `casefold()`.** Single-codepoint `tolower` plus the 50-entry fixes table. `ss` must not match `ß`.
- Native gate stays conservative: `True` means semantic confirmation is required, never that the session matches.

### Presentation

- Width resolves from the terminal, with `COLUMNS` as override — `main`'s behaviour since `a51f32c`, not the branch's COLUMNS-only.
- If the three stderr wrap implementations are unified, that is a behaviour change on wide characters and trailing spaces, and needs to be a decision rather than a tidy-up.

---

## Cross-cutting, both packages

1. **Every characterization records the oracle revision and the `src/chats` tree state.** A characterization that names neither is not evidence.
2. **No finding reported from an aggregate alone.** The instances that produced it get printed and inspected. Three saves today, none of which came from the number looking wrong.
3. **An invariant is only evidence over the modes where it is actually the contract.** A wrap assertion against raw mode manufactures failures on correct behaviour.
4. **Instruments are imported, not copied.** A copied calibration grades itself against a stale probe set and reports CALIBRATED while blind.
5. **For each preserved property, does a test exist that FAILS when the property is removed?** Not "is there a test" — *would it go red*. Added 2026-08-29 after my own method hole: my criteria asked *does the code preserve the property* and never *would the test notice if it stopped*, so I passed `plan.rs` while one of its guards was inert. `the_lazy_screen_agrees_with_the_eager_filter_on_valid_dates` has `/definitely/not/here.jsonl` as its only subject, yields no timestamps, and stays green if `>=` becomes `>`.

   The contrast that makes it checkable, both from one pass: economy 4's `early_close_stops_scanning` asserts `visited == 1` **exactly** — a bound of `< files.len()` would pass an implementation that stopped at the next batch boundary — and carries a **negative control**, `without_early_close_the_whole_pool_is_scanned`, proving it measures the close rather than an unrelated stop. Sensitivity and specificity as a pair. In a diff those two tests look equally reassuring.

   Practical form: name the mutation that should break it. If you cannot name one, the test is a description rather than a guard.

6. **A test whose expectation is deliberately wrong carries a comment saying so.** Otherwise the next reader repairs it in good faith and the divergence ships through our own contract.

## How I will review

Read the diff in full against these criteria, then probe the specific behaviours above against the built artifact rather than trusting either the diff or the author's summary. Report findings with instances attached. State plainly what I did not cover.

---

## Package A addendum — Claude branch resolution

Added before the slice arrived, from reading `parsing.py:761–855` at the oracle. `session-core` reports branch resolution landed and proved on 355 sessions, so this is the first structural review due.

Nine properties. Each is a place where a port can be *more sensible* than the oracle and diverge.

| # | Property | The plausible wrong version |
| --- | --- | --- |
| 1 | A root is `parentUuid is None` **or** a parent not present in this file | treating only null-parent as a root, losing truncated snippets |
| 2 | The active leaf is `leaves[-1]` — the **last** `last-prompt` in **file order** | picking the newest by timestamp, or the first |
| 3 | Within an era the anchor is the **latest** leaf in that subtree (`reversed(leaves)`) | taking the first match |
| 4 | Follow the anchor **down to its deepest descendant, then up** to the root | walking up from the leaf only |
| 5 | `era_roots = compaction_roots + (origin_root if known else all session_roots)` | always one, or always all |
| 6 | Branch ids numbered by **first appearance in file order** | numbering during tree traversal |
| 7 | One detour shares one id, keyed by its **head** — the first node off main | keying by leaf, or per-node ids |
| 8 | Compaction requires **both** `type == "system"` and `subtype == "compact_boundary"` | matching on subtype alone |
| 9 | `_origin_session_root` carries a `visited` set | omitting it, so a uuid cycle hangs instead of terminating |

**Property 4 is the one I expect to break.** Its whole purpose is that the reply *below* the recorded leaf stays on the main thread. An implementation that walks up from the leaf is the obvious reading of "follow the active branch", produces a coherent forest, and silently marks that reply abandoned — which hides it from default output.

**Property 5 is the second.** The fallback deliberately keeps *more* when the leaf cannot disambiguate. An implementation that always resolves to one root is tidier and drops real content.

**Property 6 is byte-visible** — ids render as `branch="1"` — so a corpus catches it. Properties 4, 5 and 9 are not reliably visible: 4 and 5 change which messages appear only in transcripts that have the shape, and 9 only shows up as a hang on a malformed file.

**Property 9 is a robustness property, not a behaviour.** It cannot be caught by any output comparison. It is in this list because a port that omits it is byte-identical on every well-formed file and hangs on one corrupt one.
