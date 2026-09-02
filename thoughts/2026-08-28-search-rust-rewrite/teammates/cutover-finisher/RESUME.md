# cutover-finisher — RESUME

Cold entry. Nothing here assumes you followed the thread. **Written whole rather than
patched**, because five seats on this mission reached the same conclusion in one day: a
brief edited section by section drifts exactly like a stale copy, and only a whole
re-read catches it.

**Read first:** `state.md`'s header, then its `L`-numbered section, then the
mission-state block at the end. It is append-only and later entries supersede earlier
ones. `decision-record.md` carries why the rejected alternatives were rejected.

---

## The seat, and where it ended

Four pieces blocked the cutover. **All four are landed and `ch search` runs on Rust.**

| Piece | State |
| --- | --- |
| Budget-exhaustion plain fallback | **done.** `Unsupported` no longer exists in the crate. |
| The `Edit` diff | **done**, on a vendored patched `difflib`, gated on two rebuilt corpora. |
| The `Read` line-number gutter | **done**, gated on three corpora, one of them bought by a surviving mutation. |
| The arm in `main.rs` | **landed.** `ch search` no longer execs `ch-legacy`. |

Plus three the first mate added mid-seat: **a `COLUMNS` sweep** against the help and
error shapes, **the launcher-provenance guard**, which landing the arm had broken, and
**an asserted-exact-difference gate** for the six rows that diverge on purpose. All
three are landed.

**And landing the arm turned the contract suite into a real differential, which found
four more defects.** Three were this seat's and are fixed; one is `parity-finisher`'s.
Section 7 has them.

**A sweep of `preserve-because-wrong.md` against the live route found one more, and it
moved which sessions a `-ca` filter returned.** Three causes, all a Rust parser stricter
than CPython's. **Closed. Section 8.**

## State, taken 2026-09-01, and it will not stay true

Tree digest `b59b2496b9b6` over `rust/**/*.rs` hashed in sorted order.

    session_render.rs  b6ae06a0bec4      search_run.rs   f78eaa77ac06
    main.rs            836c7a2b0c7c      difflib.rs      5e6cee1aabfe
    search_views.rs    ec9fd55d9ee7      pool_filter.rs  b4e92105a463

**⚠ This digest was taken at the seat's last edit and moves for two reasons.**
`parity-finisher` is live in the same checkout, **and this seat kept editing after an
earlier digest was written down** — which is how the first version of this line became
false. **Re-derive it rather than trust it.**

**269 lib tests + 56 doctests, five build configurations, zero warnings.** That total
spans both seats. **This seat contributed +35 lib tests and +3 doctests** against the
234 + 53 it started from, plus three new Python test files. Do not quote the total as one
seat's work.

---

## The launcher-provenance guard, inverted

**Landing the arm broke the contract suite's own guard, and the guard was the thing at
fault.** `_reject_foreign_launcher` rejected any launcher carrying `logicalParentUuid`,
a string the unmerged `wip/cycle-02` branch produced and HEAD did not. The arm links the
whole `_native` library into `ch` for the first time, so **a legitimately fresh build now
carries every string in the working tree's `session.rs`, that one included.** The suite
errored at setup on every case.

**Ruled: invert it, do not take a checkpoint commit.** A commit would have made the
guard pass by changing the world while its false premise survived — it would then reject
the next fresh build carrying uncommitted work, which is every build during development.
**Where a hazard has a mechanism, change the mechanism.**

**The replacement is an agreement rather than a premise.** For each of six probe strings
the binary must carry it **if and only if** `rust/**/*.rs` does. A stale artifact fails
because it is missing what the tree has added; a foreign one fails because it carries
what the tree has removed. The old guard could catch only one of those directions, for
one string. `logicalParentUuid` is still a probe, now tree-relative. **A seventh
assertion guards the guard:** fewer than four live probes and it refuses, because a
decayed set can agree by accident.

### The stale artifact is kept, and that is the load-bearing part

**A positive freshness proof that has never been shown to fail is green for an unknown
reason.** `/Users/giladbarnea/dev/chats-cycle02-ox/target/release/ch` still existed — a
real branch build from 2026-08-25 — and it is now
`tests/data/launcher-provenance/ch-0ffde41`, 6.2 MB, beside a `provenance.json` carrying
its digest, its origin, **why it is kept**, and the recipe to rebuild it.

`tests/test_launcher_provenance.py` asserts five things: the stale binary is rejected;
it is rejected **for the modelled reason** rather than some other; the failure message
still tells the next reader a failure means real staleness; a launcher matching the tree
is accepted; and **the artifact is still on disk**, because without it the falsification
is a claim about one.

**Rebuilding a stale binary later to falsify a guard is the expensive version of
something that was nearly free while a copy still existed.** Same rule as storing an
instrument's last consultation before the oracle goes.

### The suite's own header has turned over

It says *"Today `ch` hands search to `ch-legacy`, so this compares a process with
itself"*. **That stopped being true when the arm landed.** The suite has become the
differential it was built to be, and **260 assertions that have never been able to fail
are about to be able to.** Expect reds and treat them as the point. `contract-owner` owns
that window.

## 1. The budget-exhaustion fallback, and why the type is gone

**Ruled before this seat: a fence that exhausts the step budget renders plain, with
complete geometry, and never refuses.** Refusing was right only while nothing was wired
to the panel sink; once the sink existed, refusing produced a truncated scan and exit
101, which is worse than an uncoloured block.

**The route is closed structurally rather than guarded.** `render_code_block` returns
`Vec<Segment>`, `ColouredPanelSink::render` returns `String`, and **the `Unsupported`
type has been deleted from the crate** — `rg 'Unsupported\('` over `rust/**` returns
nothing. The sink has nothing left to panic on. Removing the possibility beat guarding
it, which is what the ruling asked for.

**The gate forces exhaustion for real.** `search_query.rs` gained a `#[cfg(test)]`
thread-local step-limit override, 25 lines, no production effect — the first mate ruled
it stays there. **No corpus can reach twenty million steps**; a 147 KB pathological
Python fence rendered fine. Fabricating the symptom would have asserted the stub rather
than the renderer.

`fence_budget_exhaustion_tests` carries four tests: the exhausted fence renders plain; a
**control** proving a whole budget colours the same fence, so the first is not comparing
plain against plain; a falsification running two deliberately wrong fallbacks — a
refusal and a truncation — through the same judgement; and an end-to-end `markdown_lines`
comparison against a `mermaid` fence, which reaches no lexer at all and is therefore the
right subject.

**Six false comments went with this work.** The budget refusal at `session_render.rs`,
`search_run.rs:159-162`, the panic message in `search_views.rs`, the fence arm's own
header, `syntax_tables.rs`'s doc on `promoted_lexer` (generated — fixed in
`generate_lexer_tables.py` and regenerated, **diff comment-only**), and the markdown
oracle's floor comment. **Every one asserted a ruling that had since landed.**

---

## 2. The `Edit` diff

`rust/difflib.rs`, about 400 lines vendored from `difflib` 0.4.0 (MIT, Dima Kudosh).
**Three deviations, each recorded at its site:** the inverted autojunk filter corrected,
`ntest` as integer division rather than a floored `f32`, and `unified_diff`'s header
dates and `lineterm` brought back to CPython's. `Differ`, `get_close_matches`,
`context_diff` and `ratio` were **not** vendored — an ungated vendored function is a
liability.

**The named trap was avoided rather than rediscovered.** `find_longest_match`'s doubled
extension pass is kept verbatim with the 99.67%-against-92.56% measurement in a comment,
so the next reader is told not to "fix" it into CPython's literal two-phase form.

### ⚠ The percentages this was ruled on had no instrument left

The 2,814-Edit and 900-pair figures came from a seat that stopped, with **no corpus, no
probe and nothing under `tests/data/`**. That is decision 6 arriving by a different
door: the instrument was a session, and the session ended.

**Both corpora are rebuilt and frozen, with the inputs and CPython's answers stored
together.** Re-derived:

    real Edit calls   3,000 of 3,153 found in the frozen pool   0 reach 200 lines
      as published    2,998 / 3,000   99.93%
      corrected       3,000 / 3,000   100%

    long-body pairs   400, autojunk changes CPython's own answer on 80 (20.0%)
      as published      116 / 400   29.0%
      corrected         400 / 400   100%

**That lands within a point of the lost measurement, which is convergence rather than
agreement** — nothing of the first survived to be copied.

**The gate's shape is the point.** `the_published_autojunk_filter_dies_on_the_long_corpus_and_survives_the_real_one`
runs the published inverted filter through the same emission and asserts it is killed on
one corpus and **survives on the other**. A gate built only from real Edits would have
shipped the defect.

`long-bodies.json` stores a **digest** of CPython's answer rather than its text, plus the
full text for the first forty cases. 400 whole diffs over 400 whole bodies is 75 MB of
fixture; the digest answers the only question this corpus asks, and the forty keep a
failure readable.

---

## 3. The `Read` gutter, and the recorder defect that hid it

**The predecessor left this with no failing case, deliberately, and named the first
question: how does the product resolve a result's tool name from its paired use?**

### The answer, measured

`generate_body_oracle.py` called `build_messages_group(messages, flags, None, …)`. The
product calls it with `_build_tool_id_map(hit.messages)`. **With `None`, no tool result
can resolve its name**, so every result rendered as `Tool` and **four behaviours became
unreachable at once**: the `Read` gutter, the result header label, `_tool_result_label`'s
`"output"` for a Bash-result message, and the ` Bash ` badge on that message.

**Two maps, two scopes, and the asymmetry is the product's.** A result's *name* comes
from `_build_tool_id_map` over **all** the hit's messages. The *`file_path`* the gutter
needs comes from `input_by_id`, built inside `build_messages_group` from the
**displayed** messages only. So under a search that is not `--full`, a `Read` result
whose call did not match resolves the name `Read` and finds **no input**, and falls
through to its fenced body. **That reads as a bug, it is the behaviour, and a port that
widens the map renders a gutter where the product renders a fence.** The first mate
recorded it as preserve-because-wrong item twelve.

### A fifth unbuilt body, found by the same fix

`_tool_result_label` returns `"output"` for a message that is only Bash results, and it
**replaces** the tool's name in the header. `tool_renderables` had no such parameter.
Built.

### The coloured panel sink was rendering unprojected messages

`ColouredPanelSink` had no `flags` and passed `hit.messages` — the raw parse — straight
to `message_body_lines`, where the plain sink projects through
`visibility::visible_message`. Parse-time visibility had already filtered them, so no
flag was ignored, but **nothing was shortened and no result name was resolved**. The sink
now projects the same way the plain one does, from the same function.

### Three gates, and the third was bought by a surviving mutation

1. **The body oracle** — the synthetic pair, inside a whole message body.
2. **`tests/data/read-gutter/read-gutter-oracle.json`** — 144 records from 2,676 real
   `Read` results at two widths, rendered through the real rail.
3. **`tests/data/read-gutter/read-lexer-oracle.json`** — 353 real paths and bodies with
   `Syntax.guess_lexer`'s answer.

**The third exists because a mutation survived the second.** Disabling the `*.js`
delegation test left the render oracle green: its 144 records held no `.js` file that
Pygments hands to a template delegate. The wide corpus holds five. **A mutation that
catches nothing is a question about the corpus, and the answer was a third corpus.**

### The lexer resolution, and what was deliberately not ported

`Syntax.guess_lexer` is Pygments' `guess_lexer_for_filename`: every lexer whose globs
match is scored by its own `analyse_text`, and the winner is the maximum by
`(score, is primary, priority, class name)`. **Porting every analyser is unnecessary and
the reason is measured:** of the globs the seven promoted families claim, all but two
have a single candidate, so the filename decides. Over 127 real results an
extension-only answer agreed on the promotion decision 121 times, and **every
disagreement was `*.js` resolving to `js+genshitext`**.

`rust/session_render/read_lexers.rs` is generated by
`probes/generate_read_lexers.py`, which decides each glob's verdict by **asking Pygments
with a battery of eleven probe texts** rather than by argument. Two conditionals survive
and each carries its rule by name: `js-delegates` and `python-shebang`.

**Two product facts worth keeping:**

- **`Read`ing a `.sql` file renders plain.** `SqlLexer`, `TransactSqlLexer` and
  `SqlJinjaLexer` all claim `*.sql`, `SqlLexer` can never score above zero, and the
  tie-break is the class name — so Transact-SQL always wins. SQL is promoted for fences
  and unreachable here. The generator drops the glob and says so.
- **A `.js` file containing `${…}` renders plain**, because `JavaScript+Genshi Text`
  scores above zero and JavaScript scores zero.

### The unported-language divergence is bounded, not allowed

Markdown is **37% of real `Read` calls** and is deliberately outside the seven, so Rich
paints tokens this port renders plain. Both oracles compare such a case by **exact
geometry and text, with backgrounds compared per character**, and free only the
foreground. **A promoted family gets no relaxation at all.** Each gate asserts its own
relaxation is *not inert* — a case that matches exactly must not be sitting in the
allowed set.

**The split point is read out of the recording, not recomputed.** The number column is
found by its colour, `#656660`, the blend `_get_line_numbers_color` produces. Recomputing
the width from the implementation under test would move the split on both sides and
cancel a wrong width out.

---

## 4. The arm

One `search` branch in `rust/main.rs`, matching `cli.py`'s `sys.argv[1] == "search"`
exactly and passing `&arguments[1..]`, which is what `sys.argv[2:]` is.

**The three things nothing type-checks are all in place**, each with the reason at its
site: `&arguments[1..]`; **two width resolvers**, `argparse_columns()` for help and
errors and `terminal_width()` for `run`; and `eprint!` rather than `eprintln!` before the
match, because a warning carries its own newline.

**The `HOME` resolver travelled with the arm**, three branches, with the measured table
in its doc. **Do not replace it with `home_dir()`:** an empty `HOME` yields `/` in the
product and the real home from the convenience call, so a "correction" returns results
where the product returns none.

---

## 5. The `COLUMNS` sweep, and the two defects it found

`tests/test_search_columns_sweep.py`, a new file, so `run_all.sh` picks it up with no
edit to anyone's script.

**Four shapes** — `--help`, an unknown option, an invalid date, a no-results run —
against **eighteen `COLUMNS` values**, byte-compared with `ch-legacy` on stdout, stderr
and exit status. **It does not stop at `+96`:** empty, zero, negative, `0096`, `' 96'`,
`'96 '`, `'  120  '`, fullwidth `９６`, Arabic-Indic `١٢٠`, `1e3`, `abc`, and a value
carrying its own newline. Eight move the help width and argparse reads them; the rest it
ignores. A second test asserts the sweep spans both halves and that **`+96` is among the
ones argparse takes** — the value `terminal.rs` proves Rich rejects. **The two tests are
one claim in two places.**

**⚠ The first pool this sweep used could not see either defect.** An empty home makes the
no-results line print nothing on both sides, which is a comparison that cannot fail. It
now runs against the contract corpus, and **switching the pool exposed two defects at
once.**

**Current result: 70 of 72 comparisons green.** The two reds are `invalid-date` and
`no-results` at `COLUMNS='0'`, and they are defect two below, which is not this seat's
file.

### Defect one, mine, fixed: the no-results hint was never wrapped

`print_hint` is a Rich `Console.print`, so the line **folds at the terminal width**. Both
native emit sites did `eprint!` of the raw string. **That agreed with the product at
every width wide enough not to fold, which is every width a developer types and not
`COLUMNS=40`.** Now routed through `emit_hint`, and byte-identical to legacy at widths 1,
2, 3, 40, 79 and 80.

### Defect two, not mine, reported: `terminal_width()` clamps `COLUMNS=0`

`terminal_width_for` ends `.filter(|width| *width > 0).unwrap_or(FALLBACK_TERMINAL_WIDTH)`,
so `COLUMNS=0` becomes 80. **Rich keeps the 0 and prints nothing** — measured in process,
`Console(stderr=True, theme=APP_THEME)` reports `_width == 0`, and `ch-legacy search zz -d
/nope` at `COLUMNS=0` exits 1 with empty stdout and empty stderr.

**The filter is right for one path and wrong for the other, which is why it reads as
correct.** Rich's own `width = width or 80` clamp exists because `get_terminal_size` can
report `0, 0` from a pseudo-terminal — it belongs to the **ioctl** answer. This Rich
reads `COLUMNS` in `Console.__init__` and stores it as `_width`, which `size` returns
untouched, so an explicit `COLUMNS=0` is never clamped. **One filter was applied to both
answers.** `terminal.rs` is `parity-finisher`'s; reported rather than fixed, and **they
landed it** — the clamp now applies only to the measured branch, and
`wrap_preserving_spaces(_, 0)` returns the empty string, because **zero cells is nothing,
not everything**.

**One site is still open and it is theirs: `search_output.rs`'s `print_error`.** It needs
the same `width == 0` return. `eprintln!` of an empty wrap still costs a newline, and
that error repeats **once per candidate file** — 21 newlines on a small fixture pool
against Python's zero, and 4,947 on a real one. **It is the only thing keeping
`invalid-date` at `COLUMNS='0'` red; the other 71 sweep comparisons are green.**

## 6. Three character-class substitutions

`session_render.rs`'s two `\s` sites now use `session::PYTHON_SPACE_CLASS` and
`search_views.rs`'s `\w` uses `PYTHON_WORD_CLASS`, each with the measurement at the site.
The classes were measured over all 1,114,112 scalar values by both engines and are exact
in both directions.

**The `\s` one was not cosmetic.** The tag-escaping pattern from `formatting.py` decides
whether message text is escaped *at all*, so a tag followed by a file separator was
escaped by the product and left alone here. `parity-finisher` traced both sites to their
oracle at `formatting.py:320` and `:330` before I changed them.

## 7. The route flip fired, and what it caught

**Landing the arm turned the contract suite from a self-comparison into a differential,
and 260 assertions that had never been able to fail became able to.** The first run was
**230 green, 30 diverging — the same 30 in all three classes**, which is what makes them
real: a harness fault would fail the three differently. Four defects behind them, all
fixed here except one that is another seat's.

### `--color always` emitted no colour, and it was one hard-coded field

`stdout_capabilities()` set `forced_terminal: false`. `cli.py` computes
`color = (value == "always") or (value == "auto" and sys.stdout.isatty())` and passes it
to `init_module_console` as `force_color`, which becomes Rich's `force_terminal` — **and
that value is exactly `flags.color`**, so it is threaded now rather than recomputed.
**The field already existed and `resolve_color` already honoured it. Nothing was passing
it.**

**No gate saw it because every coloured gate runs under a pty**, where the forced flag
and the tty check agree. A held parameter nobody chose, for the third time on this seat.

**⚠ It accounted for 24 of the 30, and seven of those were the age tests — which do not
assert that colour is present.** They pin the label-and-colour **pairing**, including
that a `3d` row wears the *week* colour: the misalignment preserved on purpose. **A
colour fix that also aligned the two tables would have turned seven tests green for the
wrong reason and killed a documented divergence silently.** Confirmed by extracting the
`(colour, token)` tuples from both routes rather than by looking for escapes: `1w` wears
`#6b7076`, which is `search.age.month`, and the bytes are identical to legacy.

### The warning was a missing wrap, not a misplaced newline

`print_warning` is a Rich `Console.print`, so it folds at the terminal width. Legacy
reads `…continuing with\nboth filters…`; the arm emitted one long line and the hint ran
on. **The arm was byte-identical to the rehearsal driver** — diffed rather than read —
so this was in the driver too, and its verification had only met a warning short enough
not to fold.

### `chrono` accepts the lowercase `z` that `fromisoformat` rejects

`parse_iso` in `pool_filter.rs` correctly rewrites only an uppercase `Z`, then hands the
untouched string to `DateTime::parse_from_rfc3339`, **which accepts a lowercase `z`**.
CPython raises, so the caller falls back to the **filesystem** clock — and such a session
sorts by a different clock, filters differently, and renders a different date.
Preserve-because-wrong item 6, now guarded. All four `lowercase-z-*` amendment cases
reproduce their recorded bytes and exit statuses exactly.

### Width zero: four sites, not two

`eprintln!` of an empty wrap still costs a newline, and the per-candidate error repeats
**once per candidate file** — 4,947 newlines at `COLUMNS=0` against Python's nothing.
All four `search_run.rs` sites now go through `print_stderr_wrapped`, which carries the
guard. **`search_output.rs`'s `print_error` is the fifth and it is `parity-finisher`'s**,
and it is the last thing holding one sweep case red.

**The shape all four share: each agreed with the product at every width, colour setting
and timestamp a developer would try by hand.**

### Where it landed: 254 of 260, and the last six are rulings

Both fixture corpora run natively against `ch-legacy` **directly** — comparing the two
routes rather than the recorded bytes sidesteps the suite's path normalisation and asks
the same question. **Amendment corpus 33 of 33. Contract corpus 221 of 227.**

**⚠ Four are the unported-language fence divergence, already ruled.** `render-fence-web`
carries `css`, `html` and `javascript`; `render-fence-data` carries `diff`, `json` and
`markdown`. **The promoted halves are green at both widths** — `render-fence-shell` and
`render-fence-python` both reproduce exactly. What differs is the four unported tags,
which render plain: 2 KB smaller and identical apart from the foregrounds inside those
blocks.

**These are `g4-fence-never-covered` living inside the contract corpus.** That row was
removed and documented where it stood; these were recorded before the ruling. **They
cannot go green while the language list is closed at seven, and `rebless_oracle.py` must
not be reached for** — it replays through the built launcher, which is now Rust, so a
re-bless would stamp the native answer as the expectation. **A hand ruling, with the
reason written where the rows are.**

**⚠ Two are a warning's provenance decoration, and reproducing it means fabricating it.**

    legacy  {SEARCH_QUERY_SOURCE}:96: FutureWarning: Possible nested set at position 1
              regex = re.compile(pattern, flags)
    native  FutureWarning: Possible nested set at position 1

**The text, the stream and the ordering are right.** What is missing is CPython's
`warnings` decoration — the source path, the line number, and the echoed source line.
The normaliser rewrites the path and keeps `:96:` and the source line **literal**, so the
expectation genuinely demands them.

**Reproducing it means emitting a path to `search_query.py:96` and a line of Python the
cutover deletes.** That is the fabricated-traceback shape this project already fixed
once — a prior team faked a broken-pipe traceback and baked build paths into the binary,
and removing it was one of the accepted repairs. **Ruled against reproduction
explicitly**, because one of the two options is a known-bad pattern and a fork with a
known-bad option is not a fork.

### Both classes are asserted exact differences, not expected reds

**An expected red is indistinguishable from a regression**, and this desk spent two days
removing the last row that was allowed to fail. So neither class is left red:
`tests/test_deliberate_divergences.py` pins each one the way `KNOWN_UNBUILT_BODIES` does.

- **The set is exact.** Every other recorded case in both corpora must reproduce
  `ch-legacy` byte for byte; a seventh joining is a regression, and one that stops
  diverging must have its name removed.
- **Each divergence must still differ**, or the allowance is inert and hides whatever
  appears there next.
- **The fence four:** the text must be byte-identical with all styling stripped; the
  native's style set must be a **subset** of legacy's, so an unported language may only
  ever *omit* colour; and **every style only legacy emits must carry Monokai's fence
  background `48;2;39;40;34`**, which is what confines the whole difference to code
  blocks.
- **The control:** `render-fence-shell` and `render-fence-python` must be byte-identical
  **including colour**, at both widths. Without it, "the renderer drops colour on some
  fences" and "the language list does not cover four tags" are the same observation.
- **The warning two:** legacy's stderr must equal the prefix, plus the native's stderr
  verbatim, plus the echoed source line — **spelled out, so a change to the warning
  *text* still fails** even though its decoration is forgiven.

---

## 8. `first_timestamp` on two fixture sessions — found, and closed

Found by sweeping `preserve-because-wrong.md` against the live route after everything
else was green. **`ch search . -l` disagrees with `ch-legacy` on `created:` for two
contract sessions, and `ch search . -ca 2026-08-25 -ll` returns a session on the native
route that legacy excludes.** It moves which sessions match, not how they look.

**Two causes, both a Rust parser being stricter than CPython's.**

- **`…aaaaaaaa11` — `NaN`.** Its first line ends `"score":NaN`. **`json.loads` accepts
  `NaN`; `serde_json` rejects it**, so `pool_filter::entry_timestamp` skips line one and
  takes line two. `created` renders `16:01` against legacy's `16:00`.
- **`…aaaaaaaa12` — a C0 file separator.** The file begins with byte `0x1C`.
  **`inventory::trim_python_byte_whitespace` strips only `\t \n \v \f \r` and space,
  not `0x1C`–`0x1F`**, so the line never parses and the probe falls through to filesystem
  birthtime — today's date where legacy renders `2026-08-20`.

**Python's `_find_first_timestamp` is `line.strip()` then `json.loads(line)`.** Both
halves of the difference are in that one line. `session::python_strip` already carries
the right whitespace set; the byte helper does not.

**⚠ The corpus has the inputs and not the assertion.** Both sessions were built for
exactly this — one is named "Rendernan first line", the other "Renderctrl separator
line" — and **both pass the 260-case comparison**, because no recorded case renders their
metadata block. **The fixtures exist; the question was never asked of them.**

**Landed once `session::detection_lenient` became `pub(crate)`**, which was the one word
this waited on. `first_in_band_timestamp` now `python_strip`s each line and parses
leniently, and **`search . -l` is byte-identical to legacy while `-ca` agrees on the
session it used to disagree about.**

**A third, smaller divergence went with it.** The loop did `let Ok(line) = line else {
continue }` on a decode failure. **Python reads the file as text inside a bare
`except Exception: pass`, so invalid UTF-8 aborts the whole probe** rather than skipping
one line — and aborts it *lazily*, after any earlier line has already answered, which is
why this stays line by line rather than reading the file whole.

**Duplicating twenty lines of NaN scanning would have been the wrong shape, and fixing
only the `0x1C` half would have been worse than fixing neither** — it would have left a
divergence that looked closed.

**Smaller, and not this seat's:** `ch search a -r` emits `<subagent-task>` at column zero
where legacy indents it two spaces. That is the raw renderer.

### The rest of the sweep: twelve items, one divergence, one unreachable

`probes/preserve_because_wrong_sweep.py` builds a pool per item and compares both
binaries byte for byte. **Ten probes, all identical to legacy**, and each **reports the
bytes behind its verdict** — because "both printed nothing" and "both printed the same
wrong-on-purpose answer" look identical in a pass column.

| Item | Verdict |
| --- | --- |
| 1 `collapse_home` matches a prefix, not a boundary | **same** — both render `directory: ~X/dev/chats` |
| 2 age label and colour disagree by one bucket | **same** — `(colour, token)` tuples compared, not escapes |
| 3 `elide_to_width` counts code points | **same** at three widths |
| 4 `truncate_middle` is normalization-sensitive | **same** over 400 NFD characters under `--short` |
| 5 30-day months and 365-day years | **same** across the 359/360/364/365/366-day boundary |
| 6 a lowercase ISO `z` falls back to mtime | **was the one divergence.** Fixed |
| 7 a DST fold collapses two instants | **same**, rendering and `-ma`, under `TZ=Asia/Jerusalem` |
| 8 one trailing space on the last line is deleted | **same** across all three shapes, fenced and raw |
| 9 two width resolvers disagree in one run | **same** — the `COLUMNS` sweep, 71 of 72 |
| 10 `--color never` still colours stderr on a tty | **DIVERGES, 8 of 8 shapes.** The known deferred slice, now measured |
| 11 empty string: absent, or present and invalid | **same** across all four invocations |
| 12 `input_by_id`'s narrower scope | built in, with the reason at the call site |

**⚠ Item 10 is measured, and it is the one real divergence left in this list.**
`probes/stderr_tty_colour.py` puts a pty on **stderr** and a pipe on stdout — the shape
the item is actually about — and **all eight shapes differ**:

| shape | legacy | native |
| --- | --- | --- |
| no-results hint, bare / `never` / `always` / `auto` | 95 B, coloured | 39 B, bare |
| role-contradiction warning, bare / `never` | 207 B, coloured | bare |
| invalid-date error, bare / `never` | 363 B, coloured | bare |

**Legacy colours all three stderr consoles whenever stderr is a tty, `--color never`
included**, because the colour choice reaches stdout's console and none of the stderr
ones. The hint arrives as `search.empty` **plus Rich's `ReprHighlighter` painting the
quoted term green** — so closing it needs the theme style *and* the repr highlighter,
which `search_views`'s `COMBINED_PATTERN` already carries.

**This is the known deferred slice, not a new defect** — the sinks' `emit_error` names it
and calls it "a separate slice with its own frozen baseline". **What is new is that it
has now been measured through the native route**, which is what changed under it.

**⚠ And the first attempt concluded it was unreachable, which was wrong.** `script`
cannot allocate a pty here; `pty.openpty()` can, and this mission already owns
`reviewer-profiler/pty_harness.py`. **A "cannot" resting on one tool having failed is not
a measurement** — every coloured gate here puts its pty on *stdout*, which is exactly why
nobody had asked this question of stderr.

**⚠ And probe 3 agreed about nothing on its first run.** `elide_to_width` is reached only
from the **coloured** list row and panel title; the plain list mode never elides, so the
first version compared two un-elided outputs. **It reports whether an ellipsis actually
appeared, which is how that was caught** — the same reach-reporting that every other
probe here carries.

---

## 9. The stderr-colour slice: baseline captured, then opened

**The capture came first and was not contingent on the fix.** Legacy's coloured stderr
can only be recorded while `ch-legacy` lives and the deletion slice is downstream — so
even a decision to ship the divergence would have needed this taken the same day.
Decision 6's third arrival in two days: **cheap now, impossible after.**

**`tests/data/stderr-colour/legacy-stderr-baseline.json` — 240 recorded answers, 120 of
them carrying colour.** Six stderr-writing shapes crossed with four `--color` settings,
five terminal tiers and two widths. The tier matters because `print_hint`'s grey is an
**RGB triple that downgrades** while `print_error`'s red is a **palette index that never
does**; the width matters because these messages fold.

**Then the slice opened, and the reason is that item 10 is a preserve-because-wrong
item.** The behaviour is legacy colouring stderr **when explicitly told not to**.
Leaving it unfixed does not preserve a wrong behaviour — **it silently drops one**, which
is the exact failure the list exists to prevent.

**Almost all the machinery already existed and was never wired.** `search_views` carried
`StderrConsole` with its three base styles, `highlight_spans` — the measured subset of
Rich's `ReprHighlighter` these messages actually reach — and `render_stderr_message`.
What was missing was a **stderr** capability resolver and five call sites. `--color` is
deliberately not threaded into it: `forced_terminal` is `false` there and says why.

### Where it stands: green, 240 of 240

| | |
| --- | --- |
| pinned as the ruled `FutureWarning` decoration divergence | **40** |
| byte-compared against the frozen bytes, all reproducing | **200** |
| failing | **0** |

**It got there in three steps and each one was a different site.** `parity-finisher`'s
`print_error` delegation closed 24 of the 32 that were left; the last **eight were
`--color always` only**, which is the coloured route, and they were **both sinks' own
`emit_error` in `search_views.rs` — this seat's file.** Each carried a comment saying the
gap was "a separate slice with its own frozen baseline". **The baseline now existed, so
the comment was describing a gap that had already been closed everywhere else.**

**Every stderr line the product writes now goes through one function.** Two sinks
answering the colour question separately is how they drift apart.

### ⚠ Two things this gate caught, and one of them was in how I read it

**A real defect: `terminal_width()` resolves dumbness from *stdout*, and these consoles
are on *stderr*.** A Rich console returns 80 columns for a dumb terminal *before* it
consults `COLUMNS` at all — so with stdout on a pipe and stderr on a dumb pty, the native
wrapped at the pty's width where the product wraps at 80. Now
`terminal_width_for(stderr_is_dumb)`. **The same shape as the whole finding, one level
down: a property read from the wrong stream, invisible until something put a tty on the
other one.**

**And a reading error worth more than the defect.** The first run went through
`pytest … | tail -5`; I counted five `FAILED` lines and read it as **235 of 240**. **The
output was truncated to five lines and the true number was 72.** It came apart only
because a `-k` run in isolation showed thirty-two failures in one shape, which could not
be reconciled with five. **A truncated instrument reporting a plausible number** — the
class this seat spent the day finding in other people's corpora, arriving in its own
reading of its own gate.

---

## 10. The whole list frozen as prohibitions

**Ruled after the sweep: the twelve items become a gate, not a probe run once.** The
sweep already asserted every prohibition — it compares native to legacy byte for byte, so
a port that "improves" any item fails it. **What it lacked was a schedule.** A probe run
once protects nothing after the run.

**`tests/data/preserve-because-wrong/legacy-baseline.json` — 14 cases over 7 committed
pools**, captured while `ch-legacy` lived. `tests/test_preserve_because_wrong.py`
compares the native against those bytes. **The capture refuses rather than writes** on an
empty case, a missing item, or a short case list.

**Everything wall-clock is pinned in the recording**: `CH_NOW` fixes the instant ages are
measured from and `TZ` fixes the fold, so item 5's tokens do not rot overnight.

**A reach assertion sits beside the byte comparisons**, naming the evidence each item is
about — `~X/` for the prefix match, an ellipsis for the elision, `12mo` **and** `1y` for
the 360/365-day boundary, two identical `"2026-10-25 01:30"` renders for the fold, both
readings of the empty string. **A recording that drifted away from its own subject fails
here rather than going quietly green.**

### ⚠ Two fixture bugs, both of which looked plausible

**Item 5's ages came out in *minutes*.** The first version set file mtimes at the
boundaries and left every entry at one content timestamp — but **`last_timestamp` prefers
the in-band value and only falls back to the filesystem**, so the mtimes were never
consulted. The boundaries are now in the timestamps themselves. A hard-coded epoch beside
`CH_NOW` was also twenty-seven hours out; it is derived from `CH_NOW` now.

**And the reach assertion failed twice on its own encoding.** The recording stores exact
bytes through latin-1, so a UTF-8 needle like `…` compared against the decoded string
never matches — **it looks exactly like a corpus that lost the behaviour.** The checks
search bytes.

### Falsified with the correction someone would actually make

`collapse_home` was mutated to match on a **path boundary** — the obvious right
implementation, and the one any reviewer would ask for. The gate went red on the mangled
sibling path with the message that names why: *"This behaviour is wrong on purpose. If
the change that broke this looks like a correction, that is the failure mode this gate
exists for."*

---

## 11. G5 reached these files: two contradictions, one shape

**G5 found 39 red across two root causes, and both are the same defect: a fix that
landed in one of two places.** Neither was a behavioural divergence — all 13 shell
suites and 2,354 tests were already passing.

### 21 errors — a second, un-updated copy of the launcher guard

`tests/test_parse_command_contract.py` held its **own** `_reject_foreign_launcher` with
the old forbidden-string premise, `HEAD_ABSENT_LAUNCHER_MARKERS = (b"logicalParentUuid",)`.
**That premise died with the cutover exactly as the other copy's did** — the string is
legitimately in the tree and absent from committed HEAD, so a correctly built binary
embeds it and the guard rejected it.

**The fix in section "The launcher-provenance guard, inverted" was correct and complete
for the file it was in. The failure was that nobody knew there were two.** The parse
suite now **imports** the corrected guard rather than carrying a copy. **Fourth
duplicated helper this week and the first in `tests/`.**

### 18 failures — the parity suite never learned to defer

**Exactly the six ruled ids × three parity functions, no remainder.**
`test_deliberate_divergences.py` defined those six and asserted each difference exactly,
11 of 11 green; `test_search_command_contract.py` knew nothing about it and went on
asserting byte-parity on all six. **Two suites asserting opposite things about the same
cases, so the suite could not be green by construction.**

**And this seat's own words were the argument against the state it was in:** *"An
expected red is indistinguishable from a regression."* **They were left red — in the
other suite.** The mechanism was built and the parity suite was never taught about it.

### The fix, shaped so it cannot become the defect it repairs

**`tests/deliberate_divergences.py` is the single authority.** Both suites import the
same names. **A second copy of that list is the defect it exists to prevent**, which is
why it is a plain module rather than a constant in either test file.

**The exemption is not a silent skip.** Each of the three parity functions asserts the
case **still differs** and names where the strong assertion lives. So:

- **Remove an id** and this suite starts asserting byte-parity on it again by itself.
- **Leave an id that has stopped diverging** and this suite fails it as an exemption
  allowing nothing, while the divergence suite fails it as an inert allowance.

**Neither suite can quietly stop meaning anything without the other going red.**

**Result: 21 errors → 0, 18 failures → 0, and the whole search contract suite green.**

### ⚠ A third decayed assertion, left for `contract-owner`

`test_uncompleted_public_journeys_keep_exact_legacy_behavior` lists **`search`** as an
uncompleted journey and asserts `b"python" in loader_trace` — *"Expected uncompleted
search to remain on the private Python legacy route."* **It fails because `ch search` no
longer loads a Python interpreter. That is the cutover succeeding.**

**Same file, same cause, mirror image of the guard.** The guard asserted a fresh binary
*cannot* contain a string it now legitimately does; this asserts a journey *must* still
be Python when it is now Rust. **The second only became visible once the first stopped
erroring the file out.**

**Nothing was landed for it and the reason is that the fix is a classification, not a
line.** `search` belongs in the **completed** set, where this same file already asserts a
journey **bypasses** the PyO3 extension — the opposite check, and the one search should
now pass. **Deleting the case would remove an assertion rather than move it**, which is
the worst of the three options. **The bytes are fine; only the route assertion is dated.**

---

## Falsification, in full

Eight mutations run by hand against the landed code, each restored afterwards:

| Mutation | Verdict |
| --- | --- |
| The budget fallback renders nothing | **died**, two tests, message names the cause |
| The step-limit override is disabled | **died**, the exhausted render came back coloured |
| The `Read` gutter always starts at line 1 | **died**, 4 records |
| The number column is one cell narrow | **died**, 130 of 144 records |
| No path resolves to a promoted family | **died**, names the file and both answers |
| The `js-delegates` rule never fires | **survived the render oracle — and bought a third corpus**, where it dies on 5 of 353 |
| A non-diverging case is added to the allowed set | **died** — "an inert allowance is worse than none" |
| A diverging case is removed from the allowed set | **died** — the exactness sweep names what left |
| `collapse_home` matches a path boundary, the "correct" version | **died** — the prohibition gate, naming why |

**The `js-delegates` row is the one worth carrying.** It is the only mutation on this
seat that caught nothing, and reading why produced a better gate than the seven that
worked.

---

## Files this seat owns, and what is uncommitted in them

**Mine, exclusively:** `rust/session_render.rs`, `rust/session_render/read_lexers.rs`,
`rust/main.rs`, `rust/search_views.rs`, `rust/search_run.rs`, `rust/difflib.rs`,
`probes/searchdriver`.

**⚠ `probes/searchdriver` is now redundant and is deliberately left alone.** It was the
rehearsal for the arm, and the arm has landed with its `HOME` resolver copied across, so
the two are duplicates. **Deleting it is a decision for whoever closes the mission**, not
a tidy-up: it is the only standalone way to run the search route without `main.rs`, and
somebody may still want that while the flip is being graded.

**Touched by agreement, each announced:** `rust/lib.rs` (one line, `pub mod difflib;`),
`rust/search_query.rs` (25 `#[cfg(test)]` lines), `rust/codecs.rs` (`output_text` added
to `ToolParts`), `rust/syntax_tables.rs` (regenerated, comment-only),
`tests/test_search_command_contract.py` (the provenance guard and the parity
exemption, ruled in scope), `tests/test_parse_command_contract.py` (its duplicate guard
replaced by an import), and
`rust/pool_filter.rs` (the lowercase-`z` guard — on nobody's list, and the first mate
ruled it stays here).

**Fixtures and generators:** `tests/data/edit-diff/` (22 MB, two files),
`tests/data/read-gutter/` (8.6 MB, two files), `tests/data/launcher-provenance/` (6.2 MB,
the kept stale binary and its provenance),
`tests/data/message-renderer/body-oracle.json` (re-recorded),
`tests/test_search_columns_sweep.py`, `tests/test_launcher_provenance.py`,
`tests/test_deliberate_divergences.py`, `tests/test_stderr_colour.py`,
`tests/test_preserve_because_wrong.py` and `tests/deliberate_divergences.py` (new),
`tests/data/stderr-colour/` and `tests/data/preserve-because-wrong/` (frozen baselines),
`teammates/message-renderer/probes/generate_body_oracle.py` (the recorder fix), and four
generators under `teammates/cutover-finisher/probes/`.

**Not mine, and not touched:** `rust/session.rs`, `rust/python_io.rs`,
`rust/raw_transcript.rs`, `rust/terminal.rs`, `rust/search_output.rs`, `rust/cells.rs` —
`parity-finisher` holds them and is live in the same checkout. `tests/` proper and the
route-flip suite are `contract-owner`'s.

---

## The generators, all under `teammates/cutover-finisher/probes/`

    generate_edit_diff_oracle.py     real Edit calls and long-body pairs -> the two frozen corpora
    generate_read_gutter_oracle.py   real Read results -> the rendered oracle
    generate_read_lexer_oracle.py    real Read paths -> Syntax.guess_lexer's answers
    generate_read_lexers.py          Pygments -> rust/session_render/read_lexers.rs
    tool_id_map_shape.py             the measurement that found the recorder defect

Run from the repository root. The first three read
`/private/tmp/ch-pool-snapshot`, the APFS clone taken 2026-08-29. **Do not delete it** —
it costs no disk and it is what makes these corpora re-derivable.

---

## Next, if anyone takes this seat

1. **`g5-runner` re-runs check 9** once the two suite-contradiction fixes are confirmed.
   `run_all.sh` is theirs, not this seat's — one seat in the launcher window at a time.
2. **`search_output.rs`'s `print_error` width-zero guard**, which is
   `parity-finisher`'s and holds one sweep case red.
3. **Item 10's stderr colour**, gated on 240 frozen legacy answers. See section 9.
4. **Both G4 gates**, including `g4-fence-covered-later`, which is now an ordinary parity
   row that must actually go green.

## What this seat did not do, said plainly

- **`./tests/run_all.sh` has not been run by this seat**, and it was told not to — one
  seat in the launcher window at a time. **`g5-runner` ran it and reported: all 13 shell
  suites green, 2,354 tests passing, no behavioural divergence anywhere**, and 39 red
  from the two suite contradictions in section 11. The two perf failures are the retired
  live-pool budgets check 9 excludes. Every other number here is from `cargo test`, from
  the gates this seat added, and from probes run by hand.
- **The whole-pool route differential was run twice through the landed arm and is
  green both times: 0 mismatches, 0 unstable, 54 of 54** on the frozen pool, colour off —
  once against the binary before the route-flip fixes and once after. To re-run it:
  `route_differential.py <shim> --home /private/tmp/ch-pool-snapshot`, where the shim is
  two lines that `exec` the built `ch` with `search` prepended — the driver takes search
  arguments directly and `ch` does not. **It takes about twenty minutes.**
- **The coloured stderr gap is untouched.** Python's stderr consoles colour whenever
  stderr is a tty regardless of `--color`; the sinks note it and so does this. It is
  preserve-because-wrong item 10 and it is not this seat's slice.
