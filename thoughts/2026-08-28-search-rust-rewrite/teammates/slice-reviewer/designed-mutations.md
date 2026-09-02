---
date: 2026-08-29
author: slice-reviewer
role: the designed mutations for the gates whose outputs are verdicts or numbers rather than recorded bytes
for: reviewer-profiler, who owns every gate here and offered to run what I design
status: designs only — I have run none of them, because running one means editing a subject and this seat edits no production source
---

# Designed mutations for the five remaining gates

**Coverage limit first.** `held-parameters.md`'s question 2 was answerable by
computation for the gates that record **bytes**; that is done in
`held-parameters-answers.md`. These five record **verdicts or numbers**, so the
question needs a wrong implementation instead. **I have designed them and run
none.**

**The rule these are written against is L9, not 22i.** A falsifier proves a gate
can go red. It does not prove the gate goes red **for the modelled cause**, and a
falsifier that trips the wrong mechanism is indistinguishable from one that works.
**So every entry below names what the failure message must say**, not only that a
failure is expected.

**One correction carried before anything else.** `economy_probe` is **not** on this
list. `reviewer-profiler` corrected their own claim: it is falsified in both
directions by two real subjects — branch binary −4% and −1% on early close against
the Python route's 87% and 95%. **Two real subjects differing in the property is
better evidence than a designed mutation, because neither was built to be caught.**
What was missing was a designed mutation, and that is a weaker gap than "never
proved able to fail". Its residual gap is at the end of this document.

---

## 1. `colored_width_gate` — their corrected first pick

**Modelled cause:** a render that does not follow the terminal.

**Harness check first, because a gate's own harness can defeat it.**
`pty_harness.run_at_width` scrubs `COLUMNS` **only from an inherited environment**,
and this gate passes an explicit one. That explicit dict has no `COLUMNS`, so the
child sees none. **The gate can catch a `COLUMNS`-only implementation.** Stated
because the opposite — a harness exporting `COLUMNS` — would have made the gate's
whole stated purpose unreachable, and that is L22's shape.

| # | mutation | expected | the failure message must show |
| --- | --- | --- | --- |
| M1 | `terminal_width()` returns `columns_override(COLUMNS)` or 80, never measuring the terminal | FAIL at 60, 120, 200; PASS at 80 | `observed_width(native) == 80` **at every width**. Anything else means it failed for an unrelated render difference. |
| M2 | `terminal_width() - 1` | FAIL at 60, 120, 200 **and** at the 80 demonstration row | `observed_width` differing by exactly 1 |
| M3 | `min(terminal_width(), 100)` | FAIL at 120 and 200; PASS at 60 and 80 | `observed_width(native) == 100` at 120 and 200 |

**M2 is the one that separates two gates that look identical.** Without it, a gate
that only ever notices the collapse to 80 is indistinguishable from one that
measures width. M1 alone cannot tell them apart, because 80 is what M1 produces.

**⚠ M3 as written is wrong, and `reviewer-profiler` corrected it from the gate's
own output. The correction is the useful part of this section.**

I designed M3 to answer "do 120 and 200 discriminate". The gate's recorded widths
are 80/60/120/200, so they do — **but only because the coloured panel's border
spans the full terminal.** The border tracks the width unconditionally, whatever
the content does. **So M3 fails at both for the border alone**, meets its stated
expectation, and proves less than it appears to.

**The gate measures that the frame follows the terminal. It does not measure that
the text inside reflows.** Those are two properties and only one is gated.

**M3′, replacing M3.** Clamp only the **content** budget — the elision width — and
leave the frame at the terminal width. Expected FAIL at 120 and 200 **only if the
fixture content is naturally wider than 100 columns**, and passing is still the
finding.

**And the version that needs no mutation is now a different computation.** Strip
the border lines from the captures at 120 and 200 and compare the remainder. **If
the non-border content is identical, content reflow is untested at those widths**
however many rows the gate prints.

**The methodological point, and it is against my own instinct.** Three times on
this seat "the instrument already recorded the answer" has paid. **Here it did
not** — `observed_width` looks like it answers the question and does not, because
it is a maximum dominated by one element that tracks the dimension by
construction. That is 22c one level up: **an aggregate can be dominated by the one
term that cannot fail**, and reading the recorded number is not the same as
reading the instances behind it.

**✅ RESOLVED, and by a third method after the first two were both contaminated.**

`reviewer-profiler`'s line-level separator failed the same way: the panel **title**
line is content and frame padding on one line, so what it reported as a difference
was width-dependent rule padding. **Two instruments in one gate defeated by a term
that cannot fail is a property of the subject** — a panel makes content and frame
inseparable at the line level by construction, so any measurement of panelled
output must be span-level or input-level from the start.

**The move that settled it: stop separating the output, measure the input's
capacity to exercise the property.** Output-side asks *did it reflow*; input-side
asks *could it*.

    the gate's query "needle five" returns exactly 1 session
    its longest body line is 36 characters
    panel interior is ~116 columns at width 120, ~196 at width 200

**Nothing 36 characters long can wrap at either width.** No output parsing, no
frame to separate, and it stays true however the panel is drawn.

**So M3′ is not unanswered — it is unanswerable with this gate**, and the finding
is a fixture requirement rather than a mutation result:

> the width gate needs a case whose **visible** body has a line of 117–196
> characters, so it wraps at 120 and not at 200.

**Unmet, and not by a one-line query change.** The obvious query for the corpus's
122-character line returns no matches: that text is not reachable under default
visibility.

**And the refinement is theirs, correcting their own expectation rather than
confirming it.** They expected reflow to be untested and were right *by accident*:
the fixture **corpus** has ample capacity — a 617-character line and a
122-character one — so "the fixture is too small" would have been wrong.
**The gate's *query* is what selects only short bodies.**

> **Capacity in the corpus and capacity in the cases a gate actually runs are
> different quantities.** Measure the second.

---

## 2. `allocation_profile`

**Modelled cause:** the native route holding more resident copies of the payload
than the reference.

| # | mutation | expected | the failure message must show |
| --- | --- | --- | --- |
| M1 | hold one extra copy of the decoded content — one additional `clone()` on the confirmation path | slope moves ~9.00 → ~10.0; the frozen `7.01x + 82` comparison goes red | **the slope**, not "peak RSS exceeded". A fixed-cost regression and a slope regression must not produce the same message, because separating them is the entire reason this instrument exists. |
| M2 | add a large **fixed** allocation independent of payload size | intercept moves, slope does not | the **intercept** moving alone. If M1 and M2 produce the same message the gate has collapsed back into the single ratio it was built to replace. |

**The blind spot to name, and it needs a different mutation than either.** This gate
varies payload **size** and holds the **session shape** fixed — one oversized final
line. **A copy proportional to the number of entries rather than to payload bytes
leaves the slope unchanged and is invisible.** The mutation that would expose it
holds total bytes fixed and varies entry count. That is a second axis, not a
second value on the existing one, and it is exactly 22an's category bound.

---

## 3. `tool_visibility_oracle`

**Already falsified** — two plausible wrong ports caught 558 and 634 of 7,315. So
question 2 is answered for the *rules*. **The open question is the alphabet**,
which `held-parameters.md` records as chosen.

**Do not add a mutation. Derive the alphabet instead**, which is strictly stronger:
a chosen set cannot tell you it collapsed, and this one has never been asked.

Derive members from the difference they are meant to expose:

1. **A name that is a prefix of another** — `Read` and `ReadFile`. A
   prefix-matching bug is invisible unless the alphabet contains such a pair.
2. **Two names differing only in case** — the desk already knows
   `re.IGNORECASE` is not `casefold()`.
3. **Two filters matching one tool at equal specificity**, so the tie-break to the
   later filter is exercised by construction rather than by luck. The generator's
   own docstring says the space is built to produce ties in quantity; **built for
   quantity is not the same as built to contain the pair that discriminates.**

**✅ Measured by `reviewer-profiler`, 2026-08-29. One of three present, and the two
absent are the two that were predicted.**

    names in the alphabet : ['Bash', 'Read']
    prefix pair           : ABSENT
    case pair             : ABSENT
    equal-specificity tie : PRESENT   (Bash:s=100 / Bash:s=200, e:s=600 / o:s=400)

**Two names is not an alphabet, it is a pair.** The set was chosen to produce ties
in bulk — 696 tie-bearing spec lists — and the tie discriminator is precisely the
one of three it has. **Built for quantity is not built to contain the
discriminating pair**, demonstrated on the instrument that prompted the sentence.

**Both absences are live behaviours, not hypotheticals.** `_tool_names_match` tries
an exact match, then normalises both sides through `normalize_tool_filter_name`,
which lowercases for the alias lookup. So a lowercase `bash` filter **should**
match a `Bash` tool, and `Read` **should not** match a hypothetical `ReadFile`.
**7,315 cases test neither.**

**A fourth member, derived from the normalisation table rather than the matcher,
and `reviewer-profiler` demonstrated it is observable:**

    ['exec_command:s=100', 'Bash:s=200']  ->  max_chars = 200
    ['Bash:s=200', 'exec_command:s=100']  ->  max_chars = 100

Both specs match the same tool at equal specificity — name-only, so 1 each — and
the **later one wins**. **So the alias collapses onto the canonical name *before*
the positional tie-break, and reversing the order reverses the answer.** A port
that collapsed *after* computing specificity, or that deduplicated the pair, gives
a different number and nothing in the 7,315 cases notices. **One of four present.**

---

## 4. `calibrate_harness`

**The stated objection — blind to any dimension nobody thought to add — is
unanswerable by adding probes, and I am not going to pretend otherwise.** But there
is a second-order property that *is* checkable, and it is the same one that makes
my own `f5_backref_scan` quotable.

**M1 — the null probe.** Add a probe whose mutation changes **nothing at all**.

**It must be reported as inert or blind, never as caught.** If the harness reports
`CALIBRATED` for it, then the harness cannot distinguish *"I observed the
mutation"* from *"the mutation did nothing"* — and every one of its fourteen
probes rests on that distinction.

This is criterion 5 applied to the calibrator itself. The tool exists to grade
other instruments; nothing currently grades it in this direction.

**M2 — a probe whose mutation the capture destroys.** The harness already has a
`BLIND` verdict for a pattern the capture removed. Feed it one deliberately and
require `BLIND` rather than a pass. That proves the `BLIND` path is reachable,
which is the same class of check as the null probe one level over.

---

## 5. `performance_gates`

**`--falsify` already exists and is the right shape** — all nine shapes red against
the reference route, and the ratio gates falsify themselves structurally because
the reference against itself is 1.0.

**So the gap is not "can it fail". It is whether the six shapes are six tests.**
`--falsify` proves the budgets are unmeetable by Python; it does not prove that any
two shapes exercise different code.

**Checkable without a mutation, from data the gate already produces:** if two
shapes' subject-to-reference ratios track each other across runs within noise, they
may be measuring the same path. That is the `16 colour == 8 colour` question in a
third instrument, and it is answerable by reading recorded runs rather than by
constructing anything.

**The mutation, if one is wanted:** slow down exactly one code path — say, the
literal prefilter — and check that the shapes which should notice do and the
others do not. **A mutation that moves all six equally means the six shapes are one
shape.**

---

## The one I could not design, stated as a limit of the instruments

**`economy_probe`'s fourth economy — lazy short-circuiting — has no timing
signature**, and I cannot design a mutation that gives it one.

The economy is `plan.rs::screen` returning before the `cafter` probe when the
`mafter` check fails, so a rejected file is never opened twice. **Its cost is one
file open, not measurable time**, and the tools that would count opens are
SIP-restricted on this machine, which `allocation_profile`'s own header already
records.

**22aa applies to me here: that is a limit of the instruments available, not a
property of the world.** Someone with `fs_usage` or an eBPF equivalent could
measure it directly.

**The available substitute is a stored-rule assertion rather than a measurement**,
and it is durable past cutover for the same reason `economy_probe` is: it compares
against a rule rather than a live peer. **A unit test that a failed `mafter` check
returns before the `cafter` probe runs.**

**That test does not exist.** `plan.rs`'s tests cover the cwd probe, the directory
rejection and an empty filter; **none of them asserts the ordering**, and the
economy is stated only in a doc comment. Named mutation: swap the two probes' order
in `screen`. Nothing goes red.

**That is a `plan.rs` finding, so it belongs to `context-curator`** rather than to
this document's owner — recorded here because it is where the question led.
