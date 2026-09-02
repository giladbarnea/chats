# Review and profile plan

**Oracle stamp:** HEAD `8cb4c5f`, oracle route digest
`sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0`, via
`tests/oracle_digest.py::oracle_route_digest`.

**This document previously carried `a99c3302d0f852ba`, a working-diff digest that has been
withdrawn, and the reason is worth more than the corrected value.** That digest covered
`src/` only. It could not see `.venv/bin/ch-legacy` or the installed `RECORD`, so it read
*unchanged* while a `uv sync` replaced the Python route underneath — twice, in one afternoon.
A stamp exists to detect exactly that substitution, and this one was structurally blind to it
while looking entirely plausible. `contract-owner` found it; the replacement digests the whole
route rather than the source tree.

The general form: **a stamp is only as wide as the thing it hashes, and a narrow stamp fails
silently rather than loudly.** A reader who sees only the corrected value learns the current
recipe; a reader who sees that one was withdrawn learns that a plausible digest can be blind to
what stamps exist for.

A digest, never "clean" — an artifact claiming a clean tree keeps claiming it after the next
oracle event. Re-verify or re-stamp on the next one.

Measured 2026-08-28 on this machine. Nothing is quoted from historical records.

This document is also the design for A2: the fixed-corpus gates that replace the two flapping
live-pool budgets.

## 1. The baseline is red before anyone writes Rust

`./tests/run_all.sh` **fails on clean `main` today**. Python unit tests pass — 1129 passed, 3
skipped in 94.8 s — and then `tests/test_search_perf.py` fails and `set -e` aborts the run, so
the thirteen shell suites never execute at all.

Re-run three times, and the failing test moves:

    run 1   search . -l -d .        3095 ms   budget 2500
    run 2   search . -ma 4h --list  1903 ms   budget 1750
    run 3   search . -l -d .        2564 ms   budget 2500

Both budgets sit on their own edge. This is a flapping gate, not a signal.

The cause is in the tests' own docstrings: they measure against the live session pool, which
grows, and the budgets have already been raised twice. `-ma 4h` is worse still — it drifts on
two axes at once, because the pool changes *and* "4h ago" changes, so the same command means
something different every hour.

**Consequence for the charter.** "`./tests/run_all.sh` is green" is currently unreachable, and
would have been discovered at G5 as an apparent regression caused by our own work.

## 2. Corpus identity

A frozen session universe at `~/.cache/ch-search-corpus/v1`. `ch` resolves every root from
`$HOME`, so a directory holding `.claude/projects`, `.codex/sessions` and `.pi/agent/sessions`
is a complete swappable pool.

| | files | bytes |
| --- | ---: | ---: |
| `.claude` | 392 | 513,894,109 |
| `.codex` | 302 | 666,202,653 |
| `.pi` | 1 | 3,445,145 |
| **total** | **695** | **1,183,541,907** |

Identity `sha256 de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965`, over the
sorted triples of relative path, size and per-file digest. `MANIFEST.json` sits in the corpus
root. Verifying that digest is the corpus's own gate.

Built by copy, not hard link: live sessions are still being appended to, and a corpus that
changes under a gate is the exact failure this corpus removes. On APFS the copies are
copy-on-write clones, so freezing 1.18 GB of content cost close to no disk.

**Honest limits.** Codex is a deterministic stride-4 subset, so absolute numbers are smaller
than the user's real pool. Pi is one fixture, because the live pool contains **zero** Pi
sessions — Pi is present for path coverage and carries no perf weight. And the corpus is a
frozen artifact, not a reproducible recipe: rebuilding from a grown pool yields a different
corpus, so if it is lost the gates must be re-baselined rather than regenerated.

## 3. Measurement rules

1. **Absolute dates only.** Never `-ma 4h`. A relative date makes the gate mean something
   different every hour and eventually matches nothing, which reads as a pass.
2. **Invoke the built binary directly**, by path. I measured the `uv run` wrapper and it adds
   nothing detectable, so this is about knowing which bytes ran, not about overhead.
3. **Prime once, then take the median of at least three warm repetitions.** Host noise floor is
   5–8 % with bimodal tails; single runs are not evidence.
4. **Interleave the routes inside one window** when comparing native against Python. Both then
   see a byte-identical corpus by construction. Cross-window comparison is untrustworthy.
5. **"Unprimed" means the first fresh process of a pair, never a cold page cache.** macOS denies
   `/usr/sbin/purge` on this machine. No summary may upgrade that word.
6. **Report time-to-first-visible-id and full completion separately.** They are different user
   outcomes; one past effort moved first-id from 16 s to 0.38 s with no change to completion.
7. **Any age-bearing output requires both sides to agree on `now`.** Age appears in every list
   row and every panel title. Without the approved clock injection point a byte diff across
   that surface is meaningless.
8. **Width is a measured dimension, never a fixed one.** See §8.

## 4. Performance gates

Measured on the frozen corpus, both routes interleaved, medians of three after a prime. The
native column is the reference branch binary — evidence that these budgets are reachable, not a
claim about our deliverable.

| shape (all: corpus-v1, COLUMNS=96, medians of 5) | command | native | Python | **gate** |
| --- | --- | ---: | ---: | ---: |
| help | `search --help` | 7.5 ms | 224.0 ms | **< 25 ms** |
| broad literal miss, id-only | `search zqxjvwmkbphfgd -ll` | 372.6 ms | 858.8 ms | **< 750 ms** |
| broad list, absolute date | `search . -ma 2026-08-01 -l --no-paging` | 362.3 ms | 3725.0 ms | **< 650 ms** |
| colored matches | `search the --color always --no-paging --no-metadata` | 2501.7 ms | 29202.5 ms | **< 4000 ms** |
| selective literal, id-only | `search needle -ll` | 0.181x | 1.043x | **ratio <= 0.30** |
| broad regex miss, id-only | `search 'zq[xj]{2}vwmk' -ll` | 0.111x | 1.198x | **ratio <= 0.25** |

**Two gate kinds, chosen by what is measurable rather than by taste.** Four shapes are stable
run to run and carry absolute budgets at roughly twice the observed native median. Two are not:
`selective literal, id-only` swings **56%** across seven clean, route-bracketed repetitions —
360.3, 372.8 and 568.0 ms — so an absolute budget on it flaps wherever it is set. That is the
same defect that retired the live-pool budgets, so widening the budget until it stopped failing
would have reproduced exactly the thing this section replaces.

Those two carry interleaved ratio gates: subject and reference alternate so each pair sees the
same machine. The ratio is stable where neither absolute is, and a ratio gate falsifies itself
structurally, since the reference measured against itself is 1.0.

**Are the ratios properties or points on a curve?** Both routes have a fixed cost plus a
per-file cost, so a ratio measured at one corpus size need not travel. Measured across four
corpus sizes:

| files | selective literal | broad regex miss |
| ---: | ---: | ---: |
| 70 | 0.127 | 0.097 |
| 174 | 0.153 | 0.119 |
| 348 | 0.147 | 0.120 |
| 695 | 0.145 | 0.117 |

The ratio climbs off the smallest corpus and then flattens: from about 174 files upward it is
stable to within run-to-run noise. So it **is** a property of the implementation above a few
hundred sessions, and the gate corpus at 695 sits well inside the plateau. Below roughly 200
files it understates the work ratio, because Python's interpreter startup is a fixed cost the
native route does not pay and it dominates a small scan. The sentence "native is 0.145x Python"
travels for corpora of this order and larger, and not for small ones.

**Sensitivity, run and recorded.** Against the reference route every shape fails — four absolute
budgets, both ratios at 1.043x and 1.198x, and all three memory gates. No gate in the set is one
the Python route could meet.

Environment for every row: `HOME` at the corpus, `COLUMNS=96`, `NO_COLOR=1` except the colored
row.

**Cost of this replacement:** one new test module, one frozen corpus already built, and the
deletion of two live-pool budgets. No production surface.

## 5. Memory gates

Per-process peak resident set, measured individually. A cumulative `getrusage` reading across
children is monotonic and reports the same number for every shape — it must not be used.

| shape (all: corpus-v1, one small Pi session, so a floor not a guarantee) | native | Python | **budget** |
| --- | ---: | ---: | ---: |
| selective literal, id-only | 401 MB | 1125 MB | **700 MB** |
| broad list, absolute date | 565 MB | 1317 MB | **900 MB** |
| colored matches | 580 MB | 1315 MB | **900 MB** |

The oversized-line probe below is what covers the case this corpus cannot.

### 5a. The oversized-line probe, and what it found

Two arms holding one session each, byte-identical except for the size of the final message. The
searched literal is absent from both, so each file is read by candidate rejection and never
reaches confirmation. A bounded scanner shows the same peak RSS on both arms.

The real 3.75 MB artifact is not in this tree — the only Pi fixture here has a 0.87 MB longest
line and a 12 KB final line — and 3.75 MB cannot be separated from a several-hundred-megabyte
baseline anyway. The payload is amplified to 64 MB and the corpus reduced to one session, so the
signal cannot be mistaken for noise.

Peak RSS, small arm → large arm:

| arm | reference native | main Python |
| --- | --- | --- |
| Pi, carries the agent marker | 20 MB → 596 MB (**+576**) | 82 MB → 530 MB (**+448**) |
| Pi, marker removed | 11 MB → 10 MB (**−1**) | 55 MB → 54 MB (**−1**) |
| Claude | 10 MB → 10 MB (**+0**) | 54 MB → 54 MB (**+0**) |

**The two control arms are the finding.** A 64 MB line costs nothing on either route unless the
session carries the `"pi-user-agents"` marker. Strip the marker from the same Pi session and it
becomes as cheap as a Claude one.

So the trigger is the **marker, not the provider** — `search-runtime` predicted this from source
and the marker-free arm confirms it in one run. The gate supplies an evidence group only for Pi
sessions, and force-accepts only when the group actually matches the bytes, so a Pi file without
the marker is rejected normally like any other file.

Three consequences, and none of them is "the scanner is broken":

1. **The scanner is bounded.** Two arms prove it. The cost sits in confirmation, which reads,
   decodes, parses and renders the file, holding all four representations at once — that is the
   sevenfold-to-ninefold amplification.
2. **`main` has the same behavior**, at the same order. It is not something the branch's lift
   introduced, and repairing it inside a lift would stop the lift being a lift.
3. **The deferral is a correctness requirement, not a defect.** Joined Pi agent records
   synthesize visible text that is absent from the raw bytes — a failed joined agent renders a
   tool name that appears nowhere in the file's values. The gate cannot see that, so it must
   defer. Narrowing the evidence group to save memory buys false negatives, which is the
   silent-loss direction. Two existing tests pin this behavior.

### 5b. The ruled gate

**Parity, not boundedness.** Bounded memory on Pi is not a parity requirement because no route
has it, and legacy produces a usable answer here — it just costs 448 MB to do it.

    Gate: on the marker-bearing arm, the native delta must not exceed
          the Python delta by more than 5%, both measured in the same
          window, each the median of three runs.

The gate compares the two deltas rather than a stored constant, so it is self-calibrating: it
cannot drift with the machine and never needs re-baselining. The 5% tolerance is measured, not
guessed — over three runs the native delta spread 0.3 MB while the Python delta spread 11 MB, or
about 2.4%, so 5% clears the observed noise floor with margin.

The gate is **red on the reference implementation today at 1.29×** (576 MB against 448 MB), so
it is a live target rather than a formality. That 1.29× is the part the extraction actually
changed, and it is the only part this gate asks anyone to fix.

**Recorded, quantified, and deliberately not gated:** a 64 MB line inside an agent-bearing
session costs 448–576 MB on every current route. That is the price of a correctness deferral
rather than a defect — see consequence 3 above. Making it cheap without losing hits is a real
product improvement and belongs in a separate proposal to the captain, with these numbers
attached.

## 6. Authority proofs

**No Python — the proof that discriminates.** Put `ch` alone in an empty directory, no
`ch-legacy` sibling, `PATH` stripped. Search must render real hits and `-ll` must list ids;
`ch info --help` must fail with the private-entry error. The `info` half is not decoration — it
proves the probe can tell the two routes apart.

**Rejected: the loader trace.** `DYLD_PRINT_LIBRARIES` reports "842 libraries, 0 python" for
`ch search` *and* for `ch info --help`, which must use Python. `run_legacy` uses `exec` and
macOS purges `DYLD_*` for a hardened-runtime interpreter, so the trace stops at the handoff.
842 is just the size of `ch`'s own library set. This check passes for a route that is entirely
Python and must not be used.

**No PyO3 — structural, on the shipped artifact.** `otool -L` shows no libpython; `nm -u` shows
zero `Py_` symbols. Asserted against the artifact rather than the `--no-default-features` flag,
because the flag states intent while the artifact states fact — and the flag is satisfied
equally by today's fully-Python search route, so on its own it proves nothing about the cutover.

**Package.** The wheel carries exactly one Mach-O `ch`, byte-identical to the installed
launcher; `entry_points` expose only `ch-legacy`; the extracted binary serves search with no
sibling present. Purge `build/` first — setuptools' cache silently re-packages modules deleted
from `src/`, which already resurrected two deleted files into a wheel on the reference branch.

**Provenance.** The suite refuses to run when the binary is older than the Rust sources rather
than rebuilding silently.

## 7. Detecting a lift that forked

The standing rule is that a lift deletes the original or proves the two byte-identical. The
reference branch shows why: `python_extension.rs` trims Python's four-byte JSON whitespace set
while `inventory.rs` trims Rust's full Unicode whitespace property, so a line beginning with
U+00A0 parses on one route and is rejected on the other. That fork passed `cargo` in both
feature modes, a 704-case suite, and an independent review.

Every gate we would otherwise plan misses it, because all of them probe the public surface
where the two routes agree. So:

1. **Both feature modes compile the shared modules and run the same shared tests.** A
   feature-gated second implementation cannot satisfy this without showing up.
2. **Differential at the seam, not the surface.** Drive the same adversarial inputs through both
   faces — the extension called from Python, the binary called as `ch` — and compare bytes.
   The input set is generated at the seam's own boundaries: Unicode whitespace classes, JSON
   escape forms, case-folding pairs, malformed intervals, and truncated UTF-8.

## 8. Width, and the shape it belongs to

Colored output must be diffed under a pty at two or more widths, **neither of them 80**, and
width must be a generated dimension of the differential fuzz.

The reason is exact: Rich follows the terminal — 80 piped, 120 and 200 under a pty — while a
`COLUMNS`-only helper returns 80 in all three. The two agree at 80 and nowhere else, so a diff
at 80 certifies the one width at which the defect is invisible. This project has already paid
for this shape twice: a hard-coded 44-column element passed every colored test because all of
them pinned one console width.

**Built, calibrated and run.** `pty_harness.py`, `calibrate_pty.py` and `colored_width_gate.py`
in this directory. The gate against the reference branch, with every ambient input pinned:

     width    native    python  verdict
        80        80        80  demo  (identical)
        60        80        60  FAIL  (differ)
       120        80       120  FAIL  (differ)
       200        80       200  FAIL  (differ)

The columns are the widest visible line each route actually produced. The native route reports
80 at every terminal size; the Python route tracks the terminal exactly. **At 80 the two are
byte-identical**, which is the demonstration rather than a pass: the one width where a diff
proves nothing is the one width where this defect agrees.

That identity at 80 is also a strong positive result. With width removed as a variable, the
branch's colored rendering matches today's Python byte for byte — panels, borders, hue cycling,
highlight painting. The defect is width resolution alone, not the renderer.

**Second ambient defect, found by chasing the anomaly.** Before the ambient set was pinned the
two differed at 80 as well. The cause was not width: the native route emitted 24-bit truecolor
(`38;2;…`) while Rich emitted the 256-colour palette (`38;5;…`), because `COLORTERM` was unset.
Setting `COLORTERM=truecolor` makes them byte-identical. **The native route ignores `COLORTERM`
and always emits truecolor**, which is the same defect family as width — an ambient input the
Python side honors and the native side does not. It needs its own gate row.

**Instrument note, recorded because the rule binds me first.** The first run of this gate
reported widths of 240/180/360/600. `observed_width` was counting bytes, and the box-drawing
characters in a panel border are three bytes each. The numbers were exactly 3× and the verdicts
happened to be right, which is precisely the "plausible number from a broken instrument" case
§10a exists to catch. Fixed to count display columns before any of it was quoted.

## 8a. Ambient inputs, enumerated

Width, the clock and `COLORTERM` were each found after they had already corrupted a measurement.
They share one shape: an input the Python route resolves from the environment that the native
route resolves differently or not at all. The domain is enumerable, so it is enumerated rather
than sampled.

Sources: every `environ`, `isatty`, `Path.home`, `datetime.now` and `astimezone` read in
`src/chats/`, the same set inside Rich's `Console`, and every `env::var` in the reference
branch's `rust/`.

| ambient input | Python route | reference branch | gate row |
| --- | --- | --- | --- |
| terminal size | `os.get_terminal_size` on the fd | **not read** | width, ≥2 widths, none 80 |
| `COLUMNS` | honored, wins over the fd | honored, only source | width override |
| `LINES` | honored | **not read** | height / pager row |
| `TERM=dumb` | pins 80 **and** drops color | read only for color on/off | dumb-terminal row |
| `COLORTERM` | selects truecolor vs 256 | **no color-depth concept** | color-depth row |
| `NO_COLOR` | honored | honored | color-off row |
| `FORCE_COLOR` | honored | **not read** | forced-color row |
| `TTY_COMPATIBLE` | honored | **not read** | row |
| `TTY_INTERACTIVE` | honored | **not read** | row |
| `isatty` | `--color auto`, **and paging defaults to it** | error color only | auto-color + pager cascade |
| `HOME` | `Path.home()` | `env::var("HOME")` | already a standing constraint |
| local timezone | `.astimezone()` on every `date=` | `.with_timezone(&Local)` | `TZ` row |
| wall clock | `datetime.now()` | `Local::now()` | clock seam (A1) |

### 8a-measured. The enumeration, checked against the product

Source reading says which inputs a route *reads*. It does not say which ones change *this*
output. `ambient_gate.py` asks both questions per input — does a route respond to the input at
all, and do the two routes agree at each setting — under a pty, width pinned at 80 so the known
width defect cannot swamp the row:

| ambient input (condition: pty, `--color always`) | subject responds | reference responds | verdict |
| --- | --- | --- | --- |
| `COLORTERM` | no | yes | **gap** |
| `NO_COLOR` | no | yes | **gap** |
| `TERM=dumb` | no | yes | **gap** |
| `FORCE_COLOR` | no | no | no divergence |
| `TTY_COMPATIBLE` | no | no | no divergence |
| `TTY_INTERACTIVE` | no | no | no divergence |
| `LINES` | no | no | no divergence |
| `TZ` | yes | yes | agrees at both settings |

**Under a pty with colour forced: three gaps.** But that was a conditional result and the
condition mattered — see the piped half below.

**`NO_COLOR` is the new one and the most serious.** The reference emits no colour with
`--color always` and `NO_COLOR` set; the subject emits colour regardless. `NO_COLOR` is a
widely honoured convention, and the subject reads it only inside `stderr_color_enabled()`,
which governs error output rather than the render.

### 8a-piped. The other condition, and why one sweep was never enough

The pty sweep forces colour, so inputs that only act when colour is *not* forced cannot move
anything. `ambient_gate_piped.py` is the other condition: output on a pipe, colour left at its
default so the `isatty` cascade is live.

| ambient input (condition: piped, colour default) | subject | reference | verdict |
| --- | --- | --- | --- |
| `FORCE_COLOR` | no | yes | **gap, invisible under a pty** |
| `TTY_COMPATIBLE` | no | yes | **gap, invisible under a pty** |
| `COLORTERM`, `NO_COLOR`, `TERM=dumb` | no | no | inert when piped |
| `LINES`, `TTY_INTERACTIVE` | no | no | inert in both conditions |
| `TZ` | yes | yes | agrees in both conditions |

### 8a-sixth. `UNICODE_VERSION`, and the bound my sweep could not see

`views-and-colour` found a sixth, by porting `rich.cells` rather than by sweeping. Rich resolves
its cell-width table through `rich._unicode_data.load("auto")`, which reads `UNICODE_VERSION`
and falls back to the newest table it ships. `cell_len` defaults to `"auto"`, and `segment.py`
calls it with that default, so the product's render path reaches it.

Confirmed at both levels, with the probe codepoints derived from the table delta rather than
guessed at:

    load("auto")      latest -> 464 spans      9.0.0 -> 371 spans
    rendered bytes    python  2513B / 2492B    DIFFERS
                      branch  2513B / 2513B    same

So it is a genuine sixth gap on the branch binary. `views-and-colour` reports `rust/cells.rs`
already reproduces it, so this is a statement about the abandoned branch and not about their
work.

**The bound worth recording is why no sweep of mine could have found it.** My enumeration is
organised around two categories, colour inputs and width resolvers. `UNICODE_VERSION` is
neither: it does not decide whether colour is emitted, and it does not decide how many columns
the terminal has. It decides how wide a *character* is, which is the layer between them. An
exhaustive sweep of both categories misses it however carefully it runs.

That is the same shape as the pty-versus-piped bound, one level up: **a sweep is bounded by its
inputs, by its conditions, and by its categories — and the categories are the ones invisible
from inside it.** Conditions I found by suspecting them. This category I could not have
suspected, because naming it requires knowing the layer exists.

**Where cell measurement can and cannot move bytes.** Counted in-process: the cell-measurement
family is called on *every* output shape — 86 times for piped plain and piped list mode, 1035
for coloured panels under a pty. So "the plain routes never reach it" is false.

But `UNICODE_VERSION` moves bytes only under a pty with colour, and the mechanism is that
**the product's own elision counts code points, not columns.** `elide_to_width` tests
`len(text)` and slices `text[:left]`, despite a docstring promising columns. So cell metrics can
only change output where *Rich itself* lays out — panel borders, titles, `no_wrap`/`overflow` —
plus `formatting.py:147`, the single site where the product asks Rich for a cell length.

**That is also a defect worth pinning, in the preserved-because-wrong family.** Measured against
a 20-column budget:

    ascii  ->  20 columns   (+0)
    CJK    ->  39 columns  (+19)
    mixed  ->  23 columns   (+3)

A CJK headline overruns its budget by 95%. Same class as the NFC/NFD truncation divergence, and
from the same cause: a width function counting the wrong unit.

### 8a-stderr. The stream was a held parameter, and holding it hid a divergence

`run_at_width` sent stderr to `DEVNULL`, so the six gates importing it observed stdout and
nothing else. That is a third bound after inputs and conditions: **which stream you are looking
at**, held fixed and invisible from inside every sweep built on it. Colour on stderr is decided
by whether *stderr* is a terminal, so a harness sending it to `DEVNULL` or a pipe cannot see
stderr colour at all — it is off by construction.

The harness now takes `stream="stdout" | "stderr" | "both"`, defaulting to stdout so no existing
caller changes. Swept on the no-match shape, which is what writes to stderr:

**No new input names.** The same three colour-resolution inputs act there — `COLORTERM`,
`NO_COLOR`, `TERM=dumb` — so the six-gap count stands as a count of inputs.

**But a divergence the stdout sweeps could not reach.** At baseline, with no ambient input
varied at all:

    subject     37B  'No sessions match "zqxjvwmkbphfgd".'
    reference   92B  grey text, green-highlighted query, colour throughout

The branch emits an uncoloured hint where Python emits a coloured one. That is not an ambient
gap; it is a surface that no gate was watching. Every "agree" cell in the stderr sweep reads NO
for that reason, at every setting.

**Scope of the earlier figure, corrected rather than withdrawn:** six gaps is a statement about
**stdout**. On stderr the same three act, plus a baseline divergence independent of any of them.

**Six real gaps in total** — three visible only under a pty, two only when piped, and
`UNICODE_VERSION` above. Source reading proposed seven; measurement across both conditions plus
the sixth confirms six; `LINES` and `TTY_INTERACTIVE` move this output under neither condition. The two halves see disjoint subsets: the
three colour-depth gaps are invisible when piped because colour is already off, and the two
tty-negotiation gaps are invisible under a pty because colour is already forced. Neither sweep
alone could have found more than three of the five.

So my earlier "three, not seven" was itself a conditional result stated as a count — the same
error one level down from the source-read over-count it was correcting. The stable finding is
that source reading proposed seven, measurement across both conditions confirms five, and
`LINES` and `TTY_INTERACTIVE` do not move this output under either.

**The `isatty` cascade is in parity on both halves, measured separately.** Colour: piped output
carries no colour on either route, 259 bytes each. Paging: under a 10-row pty with default
flags both routes spawn `less`, both hold the terminal, both emit 1160 bytes; with
`--no-paging` both exit with no child process and emit 1120 bytes. The `--no-paging` arm is the
control that makes the first arm mean something.

**Of the reads found by enumeration, one is structural rather than a missing lookup.** The native route's
colors are hard-coded truecolor literals — `38;2;…` constants throughout `session_render.rs` —
with no color-system decision anywhere. So it cannot downgrade for a 256-color terminal, a
16-color one, or a dumb one. "It ignores `COLORTERM`" understates it: there is nothing to
ignore with, and `NO_COLOR` is the only off switch it has.

### 8b. The colour-downgrade surface, measured

Width pinned at 80 so it cannot confound the verdict, `--color always`, one row per declared
terminal capability:

| environment | native | Python | verdict |
| --- | --- | --- | --- |
| truecolor | 8 truecolor | 8 truecolor | identical |
| 256 colour | 8 truecolor | 8 palette | diverges |
| 16 colour | 8 truecolor | no colour | diverges |
| 8 colour | 8 truecolor | no colour | diverges |
| dumb terminal | 8 truecolor | no colour | diverges |
| `NO_COLOR` | 8 truecolor | no colour | diverges |

Python downgrades on five distinct supported environments. The native route emits the same
truecolor on all six.

**Sizing.** The mapping a downgrade needs is 31 distinct foreground truecolor constants — 19 in
`session_render.rs`, 14 in `search_views.rs` — plus 5 background values. Thirty-six in total,
not an open-ended surface.

**Useful pointer for whoever builds it:** the branch already reads `NO_COLOR` and `TERM=dumb`,
but only inside `stderr_color_enabled()`, which governs error and warning output. The main
render path consults neither.

**Recorded because it nearly went out wrong.** The first two runs of this sweep were confounded
twice over: the harness stripped `NO_COLOR` because the caller had set it, and it defaulted
`COLORTERM=truecolor` into rows that were meant to test lower tiers. Both runs produced coherent,
readable tables — one showed everything diverging, the next showed four tiers identical — and I
nearly sent a retraction based on the second. What caught it both times was §10b: the per-row
colour profiles contradicted the verdict column. The harness now applies defaults only to an
inherited environment; a caller who passes one owns it verbatim.

### 8c. The age pairing gate, which closes a blind spot in my own gates

`humanize_age` switches unit at 1 minute, 1 hour, 1 day, 7 days, 30 days and 365 days.
`age_style` switches bucket at 1 day, 7 days and 30 days only. From one day onward the colour is
exactly one bucket older than the label reads: `3d` is painted week, `2w` month, `5mo` old.

That is a behaviour to preserve, and **every comparator on this mission is blind to it** — mine
and `contract-owner`'s both fold the age colour away to survive wall-clock drift. So a port that
drives label and colour from one aligned table, which is the first simplification any reviewer
would propose, would change the colour of every coloured row with no gate firing. Found by
`context-curator` sweeping for behaviours that must be preserved *because* they are wrong.

`age_pairing_gate.py` pins the label-to-colour pairing rather than the absolute colour. The
pairing is clock-independent even though the bucket is not, so it keeps working as the corpus
ages, and it costs nothing from the age normalization that the byte locks still need.

Both routes pass it today and agree exactly, and **it now covers all seven label units** rather
than the two the corpus reaches on its own. `views-and-colour` supplied the missing dimension:
`CH_NOW` is the approved clock pin, both routes honour it, so the instant is swept across seven
values and the Python route yields 12 distinct pairings spanning `now`, `m`, `h`, `d`, `w`, `mo`
and `y`. Falsified: an aligned table produces 20 violations.

**And widening it opened a vacuous-pass hole that the widening itself had to close.** A swept
dimension is only swept if the subject *responds* to it. The branch binary predates the clock
seam and reads the wall clock, so it returns two label units across all seven instants — and
passed, because the pairing rule genuinely holds for whatever labels it produced. The gate now
refuses a PASS below five units and says why. A route ignoring a pin is indistinguishable from
a dimension that does not matter, unless you count distinct outcomes against instants tried.

**Division of labour with `contract-owner`, so neither is mistaken for redundant.** They already
pin all seven pairings in `test_search_age_token_and_style_track_the_clock`, building a session
per case at `now - offset` so every age band is reachable, asserting the label token and the raw
SGR sequence through the real product, and deliberately bypassing `_normalize` so the declared
folding cannot reach the class it hides. That is the exhaustive, authoritative coverage — better
than anything a fixed corpus can offer, and it includes the 30-day-month artefact where 362 days
renders `12mo` before jumping to `1y`.

Mine is not a second copy of that and must not grow into one. It is a corpus-agnostic invariant:
it asserts the pairing rule over whatever ages happen to be present, so it can run inside a live
differential over the frozen corpus or the real pool without building a fixture or paying a
subprocess per case. On the current corpus that is two pairings, and the exhaustive seven live
with `contract-owner`.

Their per-pair comments carry more weight than their assertions, and the reasoning generalizes:
an assertion catches a change, but a comment saying *this is wrong on purpose, do not fix it* is
what stops the next reader from correcting the expectation and shipping the divergence through
our own contract. Every preserved-because-wrong pin on this mission needs that comment.

**The `isatty` cascade deserves its own row** because it is two behaviors from one input.
`ConversationFlags` resolves `color` from `sys.stdout.isatty()`, and then `paging` defaults to
whatever `color` resolved to. So tty-ness silently selects both the color and whether the pager
engages, and a harness that pipes one side while giving the other a pty compares colored against
uncolored *and* paged against unpaged.

## 8d. Which of these instruments survive the cutover

At cutover the Python search authority is deleted. Every instrument that compares two live
routes stops being runnable that day — including most of mine. A stored table does not, which
makes stored oracles the **durable** tier rather than the fallback tier.

So each instrument needs its reference side frozen *before* the deletion slice, or it is a
build-time tool that retires with Python. Audited:

| instrument | survives? | conversion needed before deletion |
| --- | --- | --- |
| `performance_gates.py` absolute budgets | yes | none |
| `performance_gates.py` ratio gates | **no** | freeze the final Python medians as constants; the ratio becomes an absolute budget derived from them |
| `colored_width_gate.py` | **no** | freeze Python's bytes per width as a fixture |
| `ambient_gate.py` / `_piped.py` | **no** | freeze Python's output per (input, condition) as fixtures |
| `colour_capability_sweep.py` | **no** | freeze Python's output per capability tier |
| `allocation_profile.py` | partly | the subject slope survives; freeze Python's `7.01x + 82` as the comparison constant |
| `ratio_scaling.py` | **no** | retires — it answers a question about the ratio gates, and they become absolute |
| `economy_probe.py` | **yes** | none. Each economy compares a binary against *itself* — closed against full, first byte against total — so it needs no oracle |
| `age_pairing_gate.py` | **yes** | none. It asserts a stored rule, not another route |
| `tool_visibility_oracle.json` | **yes** | none. This is the form the others must become |
| `calibrate_harness.py` and the pty harness | yes | none. Instruments, not gates |

**Five of eleven die at cutover unless converted, and two more partly.** The conversion is
cheap while Python is alive and impossible afterwards, so it belongs in the deletion slice's
prerequisites rather than in its follow-up.

### 8e. Re-pose before you freeze

An instrument that compares against a stored rule, or against **itself**, is durable by
construction. One that compares against a live peer is not.

**But re-posing is free durability only when the re-posed question is the same question.**
`contract-owner` caught the flaw in my first version of this section: I proposed self-comparisons
as *replacements* for four frozen differentials, and in every case the self-comparison asks
less. "Does the renderer read the terminal at all" is not "do both routes render identically" —
it is strictly weaker, and it survives for free precisely because it asks less.

So the correct treatment is **freeze the original and keep the cheap self-comparison alongside**,
not one instead of the other. The self-comparisons below are worth having — they catch a whole
class of failure early and they cost nothing after cutover — but none of them replaces the
frozen form:

| gate | self-comparison worth keeping *in addition to* the frozen form |
| --- | --- |
| `colored_width_gate` | the widest visible line must be ≤ the terminal width, and must change when the terminal does. That is a property of one binary. It is also what the gate was really testing — the oracle was only ever standing in for "tracks the terminal". |
| `ambient_gate` / `_piped` | the binary must **respond** to each of the five inputs. The responds column is self-contained; only the agrees column needed the oracle — and the responds column is what found all five gaps. |
| `colour_capability_sweep` | a stored rule per tier: palette at 256, none at dumb, none under `NO_COLOR`. No second route required. |
| `allocation_profile` | none. What I first called a re-posing here is a freeze wearing a different name: the threshold "slope must not exceed 7.0" *is* Python's measured 7.01 frozen as a constant. Labelling it a re-pose disguised a conversion as a redesign. |

**A stored table should be the residue of a passing live run, never a second artifact kept
beside one.** `session-core`'s `--emit-table` is the right mechanism: it emits the same pairs
the differential just compared, stamped with the oracle revision, and refuses to emit from a run
with mismatches — so a table can only describe a state that was actually green.

One gap in "refuse on mismatch", and it is the same one `calibrate_harness` already solves.
Some divergences are **declared**: the broken-pipe traceback the native route deliberately does
not reproduce, and the five open ambient gaps. A table that refuses on any mismatch cannot
record those at all, so the expectations that most need pinning are the ones it drops. The fix
is the declared/undeclared ratchet: refuse on an **undeclared** mismatch, allow a declared one
carrying its reason, and report a declaration that no longer diverges so it gets deleted.
Without it the emit mode silently narrows the table to the uncontested cases.

### 8f. The freeze, done and proved not-weakened

`freeze_references.py` stored **46** reference outputs — four widths, eighteen ambient cases
under a pty, eighteen piped, six capability tiers — 79,616 bytes of output in a 113 KB file,
stamped with the oracle state and the reference route identity. (42 before `UNICODE_VERSION`
was added as a row and a width-probe session was seeded so that row could not read as a false
clear.) Every case runs against the checked-in
contract fixture home, so nothing derived from the user's sessions is stored.

**Checked what the frozen side actually contains rather than assuming**, per
`context-curator`'s caution that a conversion can rest on a freeze that was already wrong: all
46 entries carry a real search hit, none is empty, none contains an error or a traceback.

**Then the test that matters — what does the gate say when the subject is wrong?** Verified
against the native route, which has known width, ambient and colour-capability defects:

    46 stored, 14 drifted, 0 new

      width/60, width/120, width/200            the width defect
      ambient-pty/COLORTERM|NO_COLOR|TERM=dumb  the three pty-condition gaps
      ambient-piped/FORCE_COLOR|TTY_COMPATIBLE  the two piped-condition gaps
      capability/256|16|8|dumb|NO_COLOR         five of six tiers
      ambient-pty/UNICODE_VERSION                the sixth ambient gap

Every drift is a known defect and every known defect drifts. The two entries that *should* agree
do: `width/80`, where the defect is invisible by construction, and `capability/truecolor`, the
one tier where both routes emit the same thing. Thirty-two pass, fourteen fail, and the split falls exactly
on the line between where the native route is right and where it is wrong.

So the frozen form asks the same question the live differential asked. A weakened
re-posing — "does it respond to width at all" — would have passed all thirteen.

### Not everything convertible should be converted

`tests/` is committed. So a stored table must contain nothing derived from the user's private
sessions, and that rules out conversion for any differential keyed by a path into the live pool
rather than by authored inputs. `session-core` found this in two of their own four: a table
emitted from `claude_render_differential` would store the exact rendered text of the user's
conversations into a committed directory.

Three separate objections, and the third is the one that makes it a refusal rather than a
trade-off:

1. **Not portable** — expected values derived from files that exist on one machine.
2. **Not stable** — those sessions are under active write, so a table records content that has
   already changed.
3. **Not publishable** — it commits private conversation content to the repository.

**The right treatment for a live-only proof is to run it once more before cutover, record the
result with the corpus identity and the date, and say plainly in the change log that this
coverage was live-only and ends with the Python authority.** A point-in-time proof honestly
labelled is worth more than a table that launders private content into `tests/` to look durable.

So the conversion decision has four outcomes, not three: re-pose, freeze, retire, or **record as
point-in-time and let it lapse**.

Only the **ratio gates** genuinely need a frozen number, because "much faster than the thing we
deleted" has no self-contained form. Freeze the final Python medians and they become absolute
budgets derived from them.

**The general property, which is not only about corpora.** A live differential catches more and
catches it sooner, so it is the right tool while building. A stored rule is the only form that
outlives the oracle, and a stored *rule* outlives it better than a stored *output*. Every live
differential on this mission is excellent and temporary by construction — the choice at
conversion time is re-pose, freeze, or retire, in that order of preference.

## 9. Falsifiers

Each must be attempted, not merely available. A falsifier that cannot go red proves nothing.

1. **Stale binary.** Swap in a deliberately older `ch`. The suite must fail. This project has
   already shipped a contract suite that bound the wrong installed binary.
2. **Probe discrimination.** In the empty-directory proof, `ch info --help` must fail. If it
   succeeds, the probe is not measuring what it claims.
3. **Gate sensitivity.** Run every performance and memory gate against the *Python* route. Every
   one must go red. A gate the Python route can pass is not a gate.
4. **Corpus identity.** Mutate one byte of the corpus. The manifest digest must fail.
5. **Width.** An implementation that always returns 80 must pass an 80-only diff and fail the
   two-width pty gate. If it passes both, the gate is decorative.
6. **Clock.** With the injection point wired, pin two `now` values either side of a bucket
   boundary. The age style must change. If it does not, the injection is not connected and
   `age_style` has no coverage at all.
7. **The memory probe measures what it claims.** The Claude control arm must show a delta of
   roughly zero on both routes. If the Claude arm also blows up, the probe is measuring the
   corpus rather than the Pi path, and its Pi number means nothing. This control is the reason
   the defect was correctly attributed rather than blamed on the branch's lift, so it stays in
   the gate permanently rather than being a one-off diagnostic.
8. **The parity gate can go red.** Run it with the native route pointed at a deliberately worse
   implementation; it must fail. Run it with both arms pointed at the same binary; it must pass.
   A comparison gate that cannot fail is a formality.

## 10. Review checkpoints

After each accepted slice, and independently of the implementer's route:

1. High-confidence bugs, missed contract surfaces, excess complexity, false parity.
2. A differential and a performance check I run myself, without reenacting their journey.
3. **The constraint-22 test, applied to every gate that slice added.** Name the claim the gate
   supports, then try to name an implementation that passes the gate and violates the claim. If
   I can name one, the gate is insufficient and I say so before the slice is accepted.

That third check is the generalization of four separate findings from one day: the loader trace
that passes for a Python route, the age fixture that asserts a proposition with an expiry date,
the colored diff pinned at the one width where the defect hides, and the two live-pool budgets
that measure a moving corpus. All four were green. None measured what it claimed.

### 10a. The same check, applied to the instrument

Three harness bugs surfaced the same day, and all three were caught because a number looked
implausible: `subprocess.run(..., text=True)` silently rewriting carriage returns, a trailing
newline read as total parity failure, and a width probe measuring the shell because `COLUMNS`
was mangled before the binary saw it. A harness bug that produces a *plausible* number ships.
Luck is not a method, so the instrument gets calibrated the way the code does.

**Procedure.** For every dimension a harness claims to observe, inject one minimal mutation in
exactly that dimension and require the harness to see it. A dimension where the mutation goes
unnoticed is a dimension the harness is blind in, and every parity result it has reported over
that dimension is vacuous. Run the null control first — identical input compared against itself
must report no difference — because a harness that reports spurious differences would otherwise
fake a pass on every sensitivity probe.

`calibrate_harness.py` in this directory implements it and is runnable. Its current output:

    bytes capture        CALIBRATED
    text=True capture    BLIND in 2
                         - cannot see: lone carriage return
                         - cannot see: CRLF versus LF

That is `session-core`'s finding reproduced mechanically rather than noticed. The dimensions it
grades: visible text, lone carriage return, CRLF versus LF, trailing newline, SGR colour code,
trailing whitespace, NUL byte, non-ASCII payload. Width and clock are graded by the pty and
clock falsifiers in §9, because they need a live subject rather than a byte payload.

**No harness result is quoted in a review or a gate until its calibration passes.** That
includes mine.

**Staleness announces itself.** The probe set went from 8 dimensions to 14 in one afternoon. A
copy of the tool would keep grading against the set it was copied with, report `CALIBRATED`, and
mean something weaker than the word implies. So every report prints its dimension count and a
probe-set digest, and a copy compares itself against the canonical file. A stale copy fails:

    stale copy                    FAILED   [8 dimensions, probe set 354fa3a6e4e393ee]
       PROBE SET STALE: regrade against the canonical tool

Note what that copy reported about itself: no blind dimensions at all. It was clean against its
own stale probes, which is exactly why the check cannot be left to whoever holds the copy.
`load_by_path` is provided for importing it, and registers the module in `sys.modules` before
execution — without that, `dataclasses` raises on the first `@dataclass` in any file loaded by
path. Import it; do not copy it.

### 10b. Two rules from `context-curator`, adopted

**Dump the instances before reporting the aggregate.** Their width sweep reported a one-column
overflow at four independent widths — the exact signature of a real wrapping off-by-one, and
entirely plausible. It was their instrument: a zero-width space counted as one column. The
aggregate looked clean and was wrong; the offending lines were unmistakable the moment they were
printed. So no finding is reported from a summary statistic alone. The specific instances that
produced it get dumped and inspected first. This is the answer to `session-core`'s worry about a
harness bug that produces a *plausible* number, and it is the only method here that does not
depend on the number looking odd.

**An invariant is evidence only over the modes where it is the contract.** They nearly asserted
a wrapping rule against raw mode, whose contract is to emit verbatim, over a corpus holding a
131,070-character line. Applying one invariant uniformly across modes looks like more coverage
and is less: it manufactures failures where the rule does not apply, and those crowd out real
ones. Each gate names the modes it governs.

## 11. Definitions of done

1. Every supported `ch search` shape preserves behavior through one Rust authority.
2. `./tests/run_all.sh` is green including the §4 and §5 gates and excluding the two retired
   live-pool budgets.
3. The empty-directory no-Python proof passes and its `info` control fails.
4. `otool -L` and `nm -u` are clean on the shipped artifact.
5. Package and installed-launcher proof green, from a purged `build/`.
6. Colored parity proven under a pty at two widths, neither 80.
7. Every falsifier in §9 attempted, with its result recorded.
8. Scoped diff clean.

## 12. Decisions recorded, with the alternatives rejected

- **Frozen corpus over a live pool.** Rejected the live pool: it moves, which is what makes the
  current budgets flap. The corpus costs disk and one honesty caveat about absolute numbers.
- **Copy over hard link.** A hard link costs no disk but shares content with a session still
  being appended to, so the corpus would not be frozen. APFS cloning made this free anyway.
- **Deterministic subset over a full snapshot.** A full 2.86 GB copy would take 11 % of the
  machine's remaining free space. I could not ask the captain, so I took the simplest sound
  path: a stride-4 Codex subset that keeps file count high and byte volume moderate. Comparability
  between routes is preserved because both measure the same corpus.
- **Absolute budgets *and* interleaved ratios.** Absolute budgets on a frozen corpus catch slow
  drift; interleaved same-window ratios survive corpus growth and are the only trustworthy
  cutover comparison. Neither alone is sufficient.
