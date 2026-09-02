# Reconciling the branch's search half onto current `main`

Requested by `search-firstmate` as the G2 task-DAG input: the shape and the size
of the work, honestly estimated, including what does not survive contact with
`main`.

Read via `git show 0ffde41:<path>`. The shared checkout was never switched, and
I have run nothing. Every divergence below was read at source, not taken from
the branch's records — its closure review overturned four of its own nine
findings, so its self-assessment is a lead, not a verdict.

Sizes are estimates from reading code, not from building it. I say so wherever
a number is soft.

---

## Bottom line

**Adopting the branch's search half is a reconciliation of roughly eight
distinct pieces of work, four of which are repairs to defects `main` has already
fixed and the branch never received.** The branch is not stale in the sense of
being out of date with a moving codebase. It is stale in the narrower and more
awkward sense that `main` litigated four specific correctness questions after
the branch forked, and the branch still carries the losing answer to all four.

The largest single honest finding: **Ruling 1 saves routing, not code.** Keeping
the default session journey on `ch-legacy` removes about forty lines of dispatch
from `main.rs`. It does not remove `session.rs`, `session_provider.rs`, or
`session_render.rs`, because the native search route parses and renders sessions
and therefore depends on all three. Adopting search means adopting roughly 7,900
lines of session code regardless of Ruling 1.

---

## 1. Divergence ledger

The branch forked at `a7e89eb`. `main` has eight commits since; two carry code.
The branch has twenty-six.

### D1 — Fabricated BrokenPipe traceback (`47b3db9`, T1)

`rust/main.rs:354` on the branch synthesizes a fake Python traceback string with
**build-time absolute paths baked into it**, emitted on a broken pipe. `main`
removed it: EPIPE now exits silently via `handle_output_write_error`.

Verified: the branch's literal is present at line 354; `main` has
`handle_output_write_error` at line 216 and no traceback literal.

User-visible, and the fabricated paths are the kind of thing that leaks a
developer's home directory into a shipped binary. **Size: small.** Delete the
literal, adopt `main`'s handler.

### D2 — `JsonEscapeValidator` versus `EscapedRiskScalarTracker` (`47b3db9`, T2)

The branch's `rust/scanner.rs:138` carries `JsonEscapeValidator`. `main`'s
`rust/python_extension.rs` has **no `JsonEscapeValidator` at all** — it has
`EscapedRiskScalarTracker`, which is what landed after a fuzz campaign showed
that deleting the validator entirely was unsafe: case-folding risk scalars such
as U+212A folding onto ASCII `k` keep the defer path load-bearing, so a partial
deletion landed instead.

**This is the one I would not treat as a merge.** The two are not the same
mechanism with different names. The branch's validator is a JSON escape
well-formedness state machine including surrogate-pair states (`ExpectLowU`,
`LowUnicode`); `main`'s tracker watches `\uXXXX` escapes that fold onto ASCII.
They overlap in purpose and differ in what they accept. Reconciling means
deciding which behavior is correct against the fuzz evidence `main` already
generated, then porting that decision — not textually merging two state
machines.

**Sizing revised after checking the surrounding code — this is the one estimate
in the document that moved, and it moved the wrong way.**

I first wrote "small in lines, medium in risk." That is true only if the
branch's performance work is discarded along with its validator, because the two
are welded together.

The branch's `validate_chunk_encoding` is a **single-sweep guard that fuses the
UTF-8 ambiguity check with `JsonEscapeValidator`**. Its inner loop is driven by
`escape_validator.state != JsonEscapeState::Plain`. `main` does not fuse: it
calls `validate_candidate_utf8_chunk` and `escaped_risk_tracker.scan` separately.
So the fusion is structurally dependent on the exact state machine `main`
deleted. You cannot adopt the fusion without settling the validator question,
and you cannot adopt `main`'s tracker without unpicking the fusion.

Two outcomes, and they price very differently:

- **Discard the fusion.** Take `main`'s `EscapedRiskScalarTracker` as-is, drop
  `validate_chunk_encoding`. Small, safe, and it forfeits a measured
  single-sweep optimization.
- **Keep the fusion.** Someone re-derives it on top of
  `EscapedRiskScalarTracker`. That is new work, not a merge, and it is the only
  item in this document I would not estimate from reading.

I also checked the reverse direction, which is what the branch has *earned*.
`47b3db9`'s change to `python_extension.rs` is **entirely** the validator
replacement — no other structural change hides in that commit, so D2 bounds the
scanner divergence from `main`'s side completely. From the branch's side there
are two genuine improvements: the fusion above, and `risk_character_pattern()`,
a compiled literal alternation over the twenty risk scalars where `main` does a
`binary_search` per character. **The second is independent of the validator
question and can be taken on its own merits.** The first is not.

### D3 — Terminal width resolved from `COLUMNS` only (`a51f32c`)

The branch's `session_render.rs:3586`:

```rust
pub(crate) fn terminal_width() -> usize {
    std::env::var("COLUMNS").ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(80)
}
```

Shells set `COLUMNS` without exporting it, so under zsh this resolves to nothing
and pins every colored render to 80 columns. `main` fixed exactly this at
`a51f32c` with `ioctl(TIOCGWINSZ)` across fds 0, 1 and 2, with `COLUMNS` as an
override.

This is the single width source for the whole colored renderer — panels, list
rows, wrapping. **Size: small.** Adopt `main`'s helper.

### D4 — Tool key argument elided at a hard-coded 44 columns (`a51f32c`)

The branch's `session_render.rs:3346` elides a tool header's key argument at a
build-time constant — 22 characters, ellipsis, 21 characters — and
`rich_tool_use_lines` appends the result with no width awareness. `main` has no
width constant in `_tool_key_arg` at all; elision moved into
`ToolHeader.__rich_console__`, fitted against `options.max_width` at render
time, precisely because a fixed width wraps in narrow terminals and wastes wide
ones.

**Size: small,** but it interacts with D3 and with the corpus — see section 3.

### D5 — Empty-optional normalization (`47b3db9`, T4)

`main` changed `rust/model.rs` and `rust/codecs.rs` so empty-string fields drop
rather than render: `optional_string` went from `Some(value.clone())` to
`(!value.is_empty()).then(...)`, and `parse_document_message` gained a strip of
nine empty attributes on the XML-to-JSON side.

**Sized by `session-core`, and my first framing was wrong.** I wrote that the
branch's `model.rs` "diverged independently" from its line count. It did not.
They read the bodies: the branch's `optional_string` is the pre-fix body
verbatim and its `codecs.rs` has no strip. The branch is **stale, not
divergent** — the 799-versus-786 line difference is its own unrelated additions.
It would emit `branch="" status="" agent_id=""` where `main` emits nothing.

Theirs to reconcile, and it rebases onto `main` rather than merging with it.

---

## 2. Work that is new on both sides

### N1 — Collapse the duplicated scanners

The fork I reported and `context-curator` confirmed at source: `last_timestamp`
and `resolution_facets` exist twice, in `python_extension.rs` and in
`inventory.rs`. Two costs, and the curator's sharpening is worth restating
because it upgrades this from tidiness to correctness:

- **Trim divergence is a parse-outcome difference.** Python's JSON whitespace set
  is four bytes; Rust `str::trim` strips the whole Unicode `White_Space`
  property. A line beginning with U+00A0, U+2028 or U+3000 is trimmed to a bare
  `{` and parses on the native path, and is left intact and rejected by
  `json.loads` on the legacy path. One route finds a timestamp, the other falls
  through to filesystem mtime. Same file, different answer.
- **`read_to_string` is a memory hazard.** The streaming scanner exists because
  its contract bounds memory to one physical line plus one fixed chunk. The
  reason on record is a real Pi session with a 3,752,303-byte final line.
  Sessions here run to hundreds of megabytes.

Fix: one chunked line walk, forward and backward, parameterized by a line
handler. **Size: small-to-medium.** Mine.

**Correction to my own first design, from `session-core`'s measurement.** I
originally proposed putting the Python whitespace trim *inside* the shared walk
so both callers saw identical lines. That is wrong, and it would have imposed
one trim policy on two callers that need different ones. There are two Python
trim sets in play and they fail in opposite directions:

- **Byte-layer scanning** wants Python's four-byte JSON whitespace set. Rust
  `.trim()` strips *more* — a line starting with U+00A0 parses natively where
  legacy rejects it.
- **`str`-layer decoding** (`_iter_jsonl_entries`, `detect_format`) wants
  Python's `str.isspace()` set, which is *not* Unicode `White_Space`. Rust
  `.trim()` strips *less* here: U+001C through U+001F are stripped by Python and
  left by Rust. A first line beginning with U+001C decodes to one entry in
  Python and the file is classified `jsonl`; with `.trim()` the line fails to
  parse and the whole file falls to `raw`. One leading control character flips a
  whole-file verdict.

U+0085, U+00A0, U+2028 and U+3000 are stripped by both. U+200B by neither.

So the trim belongs to the **handler**, not the walk. Rust `.trim()` is correct
for neither layer and must not appear in either. Session-core's probes are at
`teammates/session-core/probes/trim_probe.py` and `.rs`.

### N2 — Relocate and repair `terminal_width`

`session-core` needs the colored renderer to call one width helper rather than
re-derive width, and `main`'s helper lives in `rust/main.rs`, which the library
cannot see. It moves into the lift.

`session-core` also measured `main`'s helper against Rich and found exactly two
divergences: `COLUMNS="+80"`, where Rust's `parse::<usize>()` accepts the sign
and Rich's `isdigit()` rejects it, and `COLUMNS="８０"` in fullwidth digits,
where the reverse happens. Their finding, carried not re-derived. A two-line
repair, not a rewrite.

**Size: small.** Mine.

### N3 — One stderr wrapper (Ruling 3)

The branch deliberately kept three line-wrap implementations — one
character-counting and not width-aware, one UnicodeWidth-aware, one preserving
trailing spaces. Ruling 3 rejects that. The search route emits per-file errors
and the no-hit hint, so it needs one wrapper proven byte-identical to what
`ch-legacy search` produces.

**Size: small-to-medium.** The work is identifying which of the three the search
journey currently reaches and proving it against Python, not writing a wrapper.
Mine.

### N4 — Do not inherit the branch's deletions (Ruling 2)

The branch stubs `commands/search.py` to five lines and removes
`search_query.py` and `session_scan.py`, and changes `cli.py` to stop routing
search. None of that is adopted. Deletion becomes its own final slice, gated on
a green byte harness.

**Size: none — it is a matter of not taking commits.** Worth stating explicitly
because a naive cherry-pick of the branch's slice G would silently destroy the
oracle.

### N5 — Restore the `run_legacy` fallthrough (Ruling 1)

The branch's `main.rs` falls through to `_native::session::run(&arguments)`.
That reverts to `run_legacy`. **Size: small — roughly forty lines of dispatch.**

**And this is where the honest estimate bites.** It removes routing, not
modules. `search_engine.rs` parses and renders sessions, so `session.rs` (2,185
lines), `session_provider.rs` (1,989) and `session_render.rs` (3,749) all come
along. Ruling 1 keeps the default journey on `ch-legacy` and keeps this
mission's public surface honest; it does not reduce the code being adopted by
more than those forty lines.

---

## 3. What does not survive contact with `main`

1. The branch's `terminal_width` (D3) and fixed-44 elision (D4). Superseded.
2. The branch's `JsonEscapeValidator` (D2). Superseded by a question `main`
   already litigated with fuzz evidence.
3. The branch's fabricated BrokenPipe traceback (D1). Removed on `main`.
4. The branch's deletion of the Python search authority. Rejected by Ruling 2.
5. The branch's native default-session routing. Rejected by Ruling 1.
6. The branch's three-wrapper stderr stance. Rejected by Ruling 3.

**And one claim that does not survive as evidence.** The branch's "704/704
green" cannot be inherited as proof, for a reason separate from nobody having
re-run it. Every case in its manifest pins `COLUMNS`. So its corpus has coverage
at two explicit widths, 80 and 96, and **zero coverage of the code path that
decides the width when nobody sets it** — which is precisely the path D3 gets
wrong and the path `main` changed on 2026-08-27. Its own reviewer lists
interactive terminal width as blind spot number one.

The practical consequence is narrow and worth stating precisely, because it is
easy to overstate: fixing D3 will *not* churn the existing colored fixtures,
since they all set `COLUMNS` and both the old and new helper honour it. Fixing
D4 will churn any case whose expected bytes contain a tool header with a key
argument longer than 44 characters. The corpus is not invalidated. It is simply
silent on the axis that moved — the same shape of gap as the ASCII-only corpus
that could not see the lowercase-offset bug.

---

## 4. Proposed order

Repairs first, because they are small, independently provable, and three of them
are already-settled questions rather than open ones.

1. **N4 and N5** — adopt the branch's `rust/` files without its `src/chats/`
   deletions, restore `run_legacy`. Establishes the oracle before anything is
   measured against it.
2. **D1, D3, D4** — the three `main` repairs that are pure supersessions. Small,
   independent, no open questions.
3. **N2** — relocate and repair `terminal_width`. Unblocks session-core's
   renderer.
4. **N1** — collapse the duplicated scanners. Closes the live fork.
5. **D2** — the validator question. Needs a differential run against the fuzz
   evidence, so it wants to be after the harness exists, not before.
6. **N3** — one stderr wrapper, proven by diff.
7. Colored contract coverage, which is `contract-owner`'s, and which I would not
   trust the colored slice without.

Steps 1 through 4 are, on my reading, the smaller half. Step 5 is the one I
would not estimate from reading. Steps 6 and 7 depend on the harness existing.

---

## 5. Open decisions I cannot take

1. **D5 sizing** is session-core's. `model.rs` and `codecs.rs` diverged on both
   sides and I have not compared them.
2. **The colored parity standard.** `session-core` has asked for a ruling on
   whether corpus-bounded parity is the accepted standard, stated as such, since
   a byte harness proves parity on its corpus and cannot bound divergence off it
   when the input is arbitrary user code in transcripts. I agree with them that
   this wants deciding before the slice opens. It is not mine to decide.
3. **Whether D2 is a port or a re-decision.** I have described why I think it is
   a re-decision. If the first mate reads it as a port, the size drops sharply
   and so does my confidence in the result.
