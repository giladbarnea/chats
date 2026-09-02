---
date: 2026-08-29
author: slice-reviewer
role: the outside answer to the two questions `reviewer-profiler` states they cannot ask about their own gates
input: teammates/reviewer-profiler/held-parameters.md
method: computed from `frozen_reference.json`'s recorded outputs — no mutation, no re-run
oracle_route_digest: the frozen file's own stamp, sha256:dd6ab701… at revision 8cb4c5f, carried rather than re-derived
---

# Held parameters — the two questions answered, and a third

**Coverage limit first.** This answers both questions **for the gates whose outputs
are frozen** — `freeze_references.py`'s 76 entries across eight dimensions. It says
nothing about `performance_gates`, `economy_probe`, `allocation_profile`,
`tool_visibility_oracle` or `calibrate_harness`, whose outputs are numbers or
verdicts rather than recorded bytes. **For those, question 2 still needs a
mutation**, and I have not designed one.

**And the frozen file records the REFERENCE route only.** Every "inert" below means
*Python does not respond to that input under that condition*. It is a statement
about the oracle and the fixture, not about the port.

---

## The method, which is the transferable part

**Question 2 is answerable post hoc from any gate that records its outputs, with no
mutation and no re-run.** For each swept input, compare the recorded bytes at its
two settings. Identical bytes mean that input moved nothing, so every row the sweep
reports for it is a row that could not have failed.

**My first cut of this was wrong and the correction is the useful half.** I began by
counting distinct outputs **per dimension** and got "13 of 18 members identical"
under a pty — which reads as a finding. Reading the instances killed it: the
collapsed group is every input's *unset* setting, which **should** reproduce the
baseline. The question is not whether members differ from each other; it is whether
**one input's two settings differ from each other.** 22c, on my own aggregate,
before it reached anybody.

---

## Question 2 — does the subject respond to each swept dimension?

    ambient-pty       5 of 9 inputs respond    COLORTERM  NO_COLOR  TERM=dumb  TZ  UNICODE_VERSION
    ambient-piped     3 of 9                   FORCE_COLOR  TTY_COMPATIBLE  TZ
    stderr-ambient    3 of 9                   COLORTERM  NO_COLOR  TERM=dumb
    width             4 of 4 members distinct

**This independently reproduces three of this desk's existing conclusions from the
frozen data alone**, which is the best evidence I can offer that the method is
sound rather than novel:

- **22af.** The pty and pipe sweeps see disjoint subsets — colour inputs are inert
  under a pipe because colour is already off, tty-negotiation inputs are inert
  under a pty because colour is already forced on.
- **22af again.** `LINES` and `TTY_INTERACTIVE` are inert under **both** conditions,
  which is exactly the ruling that they are genuinely inert rather than gaps.
- **L21.** Exactly three colour-resolution inputs act on stderr — `COLORTERM`,
  `NO_COLOR`, `TERM=dumb` — and no others.

**One thing that is new.** `UNICODE_VERSION` responds under a pty and is **inert
under a pipe**. 22an records that it was found by porting `rich.cells` rather than
by sweeping; this shows the pipe sweep structurally could not have found it.

---

## The third question, which is the one that pays

**Does an input's response distinguish it from every *other* input, or only from
the baseline?** An input can respond — A ≠ B — and still produce the *same* pair of
outputs as a different input. Those two are then not independently checked: an
implementation that handled one as the other passes.

    ambient-pty      every responsive input is distinguishable
    ambient-piped    FORCE_COLOR and TTY_COMPATIBLE are INDISTINGUISHABLE
    stderr-ambient   NO_COLOR and TERM=dumb are INDISTINGUISHABLE

### The stderr pair is the one to act on

`rust/color.rs` documents **three** rendering states, and its own comment says why:

> `TERM=dumb` and a redirected stream emit **no SGR at all**, while `NO_COLOR`
> strips the colour and **keeps the attributes**. A renderer that collapses them
> drops the bold from every styled span of every `NO_COLOR` invocation.

**On stderr the frozen reference cannot tell those two states apart.** Both settings
produce the same bytes, presumably because the no-results hint carries colour and no
attributes, so "attributes only" and "suppressed" coincide there.

**Named mutation, per criterion 5: collapse `AttributesOnly` into `Suppressed` in
the stderr console. The stderr baseline stays green.** The pty stdout sweep would
catch it; the stderr freeze would not.

**Why this matters more than the arithmetic.** The stderr surface is the one
`views-and-colour` is porting right now, it is the one carrying a known baseline
divergence (L21), and L28 froze it **specifically so the port would have something
durable to be measured against**. That baseline is sound for what it covers and is
**blind to the exact distinction `color.rs` exists to preserve**.

### ⚠ Corrected twice. The finding holds; my fix was wrong; the correction to my fix was also wrong. `views-and-colour` settled it by running the mutation.

**Recorded as a chain rather than a quiet edit**, per L43: two of the three claims
below were stated confidently and closed a line of enquiry, and only executing the
mutation reopened it.

**1. My claim — the blind spot.** `frozen_reference.json`'s stderr entries cannot
separate `NO_COLOR` from `TERM=dumb`. **Holds.** `reviewer-profiler` confirmed it
from their own file, and confirmed the stdout half is checked:

    stdout   NO_COLOR 1533B vs TERM=dumb 1485B   distinguished
    stderr   NO_COLOR   37B vs TERM=dumb   37B   INDISTINGUISHABLE

with stdout under `NO_COLOR` retaining six attribute-only sequences, `\x1b[1m` and
`\x1b[3m`.

**2. My fix — "add one stderr shape carrying an attribute". `reviewer-profiler`
ruled it impossible**, from the three stderr consoles' styles: `red`, `yellow` and
`search.empty`, none of which carries an attribute, while the theme's bold and
italic styles (`search.title`, `search.title.fallback`, `search.count`) are used
nowhere on stderr. On that evidence the defect was reclassified as latent and
undetectable in the product.

**3. Both of us were wrong, and `views-and-colour` proved it by running the
mutation: 9 of 135 cases go red.** Their stderr corpus **does** separate the two
states.

**The mechanism we both missed: the attribute does not come from the console
style. It comes from the message content.** Rich's `repr.brace` is
`Style(bold=True)` — **bold with no colour** — so any stderr message containing
`[ ] { } ( )` carries an attribute that survives `NO_COLOR` and vanishes under
`TERM=dumb`:

    NO_COLOR=1   \x1b[1m[\x1b[0mErrno \x1b[1m21\x1b[0m\x1b[1m]\x1b[0m Is a directory: '…'
    TERM=dumb    [Errno 21] Is a directory: '…'          no SGR at all

Three of their nine messages carry a brace — the two `[Errno 21]` shapes and
`Search pattern exceeded its step budget: (a+)+b` — and three messages across three
widths is the 9.

**So the gap is in the freeze, not in the product and not in their corpus**, and
**my original fix was available after all** — through a shape the product already
emits on every per-file error, so no synthetic fixture is needed.

**And there is a second separator neither of us had:** `TERM=dumb` pins Rich to 80
columns *before `COLUMNS` is read* (`console.py:1021`), so at any width other than
80 the two states diverge on **wrapping** even with no attribute present — 13 of
their 27 case-slots separate that way. **A stderr freeze captured at 80 only is
blind to that as well**, and then the brace fixture is carrying the whole
discrimination alone.

**The actionable form, superseding everything above:** the stderr freeze needs one
entry whose message contains a brace, and stderr capture at a width other than 80.

**What this episode is really an instance of.** Two of us reasoned from the
*console styles* and reached opposite conclusions, both wrong, because the
attribute enters through the *content*. The oracle owner ran the mutation and had
the answer in one measurement. 22y: a claim confirmed only by reading is a lead,
not a result — and it cost two rounds here, from people who both knew the rule.

### The piped pair is benign and worth stating anyway

`FORCE_COLOR` and `TTY_COMPATIBLE` both turn colour on under a pipe and produce the
same bytes. Nothing today distinguishes them, so a port that honoured one and
ignored the other passes. Lower stakes — both are "force colour on" — but it is the
same shape, and it is the reason the question generalises.

---

## Question 1 — derived or chosen

Your own answer is right, and the frozen data supplies the empirical proof you said
a chosen set cannot give itself.

**A chosen set that demonstrably collapsed:** the six capability tiers include
`16 colour` and `8 colour`, and they produce **byte-identical** output. Rich maps
both to `ColorSystem.STANDARD`, so there is no 8-colour system to distinguish — the
collapse is correct behaviour and it means **one of six tiers proves nothing the
other does not.** That is `views-and-colour`'s two byte-identical Unicode oracles
(L19), in your parameterization, found the same way: by asking the data rather than
the author.

**A second, milder one:** the `--color` flag has four members and **two** effective
values under each condition — `absent == auto == never` piped, `absent == always ==
auto` under a pty. Correct, and it means the flag dimension is two-valued, not
four-valued.

**And a third thing the freeze already knew.** The `stderr` dimension's four shapes
collapse to two: `no-match == no-match-colour-always == no-match-colour-never`.
**That is L17** — `--color` does not reach stderr — sitting in the frozen data.
L18 records that the defect "lived in the blind spot of every instrument built to
find that class" and needed a purpose-built inverted probe. **`freeze_references.py`
had recorded the evidence; nobody asked the data that question.** L39's shape one
level over: there a diagnostic was printed and read as noise, here a result was
stored and never queried.

**On your one derived set:** the width codepoints are the only parameterization that
could report its own collapse, and it did — after two false negatives from choosing
them. That is the argument for deriving, and it is now a measurement rather than a
recollection.

---

## What I did not answer

- **Six gates whose outputs are not recorded bytes.** `performance_gates`,
  `economy_probe`, `allocation_profile`, `tool_visibility_oracle`,
  `calibrate_harness`, `colored_width_gate`. Question 2 needs a designed mutation
  for each and I have designed none.
- ~~**Your six-unfalsified list.** `economy_probe` is the one I would want
  falsified first.~~ **Withdrawn — `reviewer-profiler` corrected their own claim,
  and the correction is to my input rather than to my reasoning.** `economy_probe`
  **is** falsified, in both directions, by two real subjects rather than a designed
  mutation: the branch binary saves −4% and −1% on early close (economy absent, and
  the probe says so) against the Python route's 87% and 95% (economy present, and
  the probe reports it). Sensitivity and specificity both observed. What they
  lacked was a *designed* mutation, and they had let that stand as "never proved
  able to fail", which is the stronger claim. **Two real subjects differing in the
  property is better evidence than a mutation, because neither was built to be
  caught.**

  **The list is five, and their own pick is now `colored_width_gate`** — the gate
  the colour port will be measured by, which has only ever been observed catching
  the branch's pinned width. I agree, and it displaces my answer entirely.
- **Anything about the port.** The frozen file records the reference route, so every
  verdict here is about the oracle and the fixture.
