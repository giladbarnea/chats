# RESUME — search-firstmate

Cold-entry brief. **Rewritten whole 2026-09-01**, after the language set was
approved at seven, the tool surface was found unbuilt, the common path landed, and
every seat stopped. **The previous version said the only open question was a
language list. That is how fast this document goes wrong, and it is why it was
rewritten rather than patched** — see §8.

**Read [`../../state.md`](../../state.md) first.** Its header carries the reading
rule, the `L`-numbered section at the end is newer than everything above it, and
[L198] is the settled / conditional / expired table. Then
[`../../decision-record.md`](../../decision-record.md).

---

## 1. Where the mission is

**Every seat is stopped with a cold-entry brief. Nothing is in flight.** The tree
is **green, quiet and uncommitted** at digest `ca874ce060f1` — 234 lib tests + 53
doctests, five build configurations, zero warnings.

**⚠ THE CUTOVER HAS NOT LANDED.** `rust/main.rs` does not route `search`.

**The language set is closed at seven** — TypeScript, TSX, Bash/sh/zsh, Python,
JavaScript, JSON, SQL. Captain-approved on the painted-character measurement: they
carry **98.2%** of painted characters, and the whole remaining tail is 1.8% with
nothing above half a per cent [L245, L247]. **Do not add a family.** Unpromoted
languages take the gated plain fallback.

**Both G4 gates are green.** The piped gate is **54 of 54, 0 unstable**, against a
frozen pool at `/private/tmp/ch-pool-snapshot` — **do not delete it; it is what
makes G4 re-derivable and it is kept until G5 is complete.**

**Styled tool rendering was never built, and finding it is what stopped the
cutover** [L249]. `ch search --full` panicked with exit 101 on a colour terminal —
**a headline flag, not an expert one**, because messages carrying a failed Bash
result force their tools visible. **The common path is now landed**: 87.6% of tool
parts render, and all eleven command shapes are clean [L258, L261].

---

## 2. What blocks the cutover — three items, all named, measured and cheap

1. **The `Edit` diff.** Ruled, not implemented: **vendor the patched `difflib`
   crate** — about 500 MIT lines with one operator corrected, against a 687-line
   hand port. It agrees with CPython on **2,814 of 2,814** real Edit calls
   [L258]. **This is a ruling, not a question. Do not re-open it as a tradeoff.**
   `tool-edit-diff` is held in `KNOWN_UNBUILT_BODIES`, an asserted exact set that
   **demands its own removal** when the diff lands.
2. **The `Read` line-number gutter.** **It has no failing case, and that is
   deliberate** [L259]. Its two corpus cases pass for a reason unrelated to the
   gutter: a Claude `tool_result` carries no tool name, so it resolves to `Tool`
   and both routes fall to the fenced body. **The first question is how the
   product resolves a result's tool name from its paired use** — not the gutter
   itself. **A wrongly-shaped case would be worse than a missing one.**
3. **The budget-exhaustion plain fallback.** Ruled, not implemented [L261]. One
   route still reaches the sink's panic: `Unsupported("fence lexer budget")` at
   `session_render.rs:3700`. **The gate must *force* exhaustion — no real corpus
   reaches it, so shrink the budget in a test.** **Close the route structurally:**
   the panic should become impossible by construction, not merely unreached. **The
   false comment at that site goes with the fix.**

**Then land the arm.** One `search` branch in `rust/main.rs`, from
`teammates/engine-and-codex/RESUME.md` (456 lines) — three hazards nothing
type-checks, the `HOME` three-branch resolver already in `probes/searchdriver`, and
the instruction to **diff against `probes/searchdriver` rather than read it**.

**Then:** G5's blocked checks → route flip by `contract-owner`, whose **260
intended reds must all turn green** → deletion slice, **with every instrument's
last consultation stored first** (decision 6, L1, L23).

**Also for G4:** `g4-fence-covered-later` is now an ordinary parity row and **must
actually go green.** It needs the launcher window — `contract-owner`.

---

## 3. Unowned parity work — required before G5, blocking nothing now

The `HOME`-unset item is **closed** [L251]. Four remain:

- **F1** — `python_io::read_text` drops Python's universal-newline translation.
  One root cause, one fix site, two consequences; the second lands on
  `raw_transcript.rs`, the module the real corpus provably cannot grade.
- **The C0 set**, as widened: ~20 `.strip()` sites in `session.rs`, **plus four
  `\s` regex sites** (766, 790, 1186, 1360) the original enumeration could not
  contain because it enumerated `.trim()` sites, **plus one `\w` site** — `\w`
  differs in **both** directions. **`session-core`'s enumeration is by function
  name and its "correctly bare" classification is provisional.**
- **F16 / F17** — two `truncate_to_cells` and two `chop_cells`, divergent
  reimplementations under the same name.
- **The wrap-oracle gate over both `words` / `rstrip_end` copies** —
  `probes/wrap-oracle.tsv`, 235 rows. The unification is deferred past the
  cutover; **the gate is what makes deferring safe.**

---

## 4. The three seats — with the captain, in this order

1. **Critical path to the cutover.** `session_render.rs`: the three items in §2,
   then land the arm. Hands off if it runs out.
2. **Parity list.** `session.rs`, `python_io.rs`, `raw_transcript.rs`. **Disjoint
   by file from seat 1, so it runs in parallel.** Blocks G5.
3. **G5 runner — and it must not be an implementer.** Decision 2, in its now
   unconditional form, arriving at the last gate. Runs
   `g5-runbook.md` (132 lines): 15 checks, each with its command, what it proves,
   its preconditions, and the things that get got wrong without being told.

---

## 5. What this role is

Wider, shallower authority. **Edit no production source and no tests.** Rule on
cross-scope decisions, prevent overlapping edits in one shared checkout, keep
`state.md` current, and answer the captain with: completed, active, blocker, next
gate.

**No upward escalation** except to the captain for policy, roster, and numbers you
cannot see. Everything else you decide and record — with the dilemma, the chosen
path, the rejected alternative, and why.

**And a fork with one dominant option is not a decision.** The `Edit` question went
up as fidelity against cost and came back as neither, because the measurement
removed the tradeoff. **Escalating it anyway would have spent the captain's
attention on arithmetic** [L258].

---

## 6. Addressing — read before messaging anyone

**Run `ListAgents` immediately before every send and copy the row exactly.**

Most sessions carry a `[08-28][chats][t:6a91] ` prefix and **the bare name fails**
— `engine-and-codex` and `reviewer-profiler` both failed on the first attempt this
session. `lexer-tables` carries **no** prefix. **Prefixes are not stable**; they
have changed twice within an hour. **A failed send looks like a lost seat and is
not** [L170].

---

## 7. Roster — every seat stopped

| Who | Context, as last reported | Holds |
| --- | --- | --- |
| `lexer-tables` | 75%, **two days stale — a floor, not a reading** | The seven families, the generators, the held-out corpora, the tool common path, the `difflib` measurement. **Stopped clean.** |
| `engine-and-codex` | **90%**, current | The engine, Codex decode, G4's piped differential, the pool snapshot, **the cutover arm brief**. **Stopped clean.** |
| `reviewer-profiler` | **90%**, current | **All of G5** and its runbook, `held-parameters.md`. **Idle for good** unless asked a runbook question. |
| `search-runtime` | 94% | The rehearsed arm. Capped by the captain. |
| `message-renderer` | 90% | Oracle and interface owner at a completed seam. Wrote `PROMOTING-A-LEXER-TABLE.md`. |
| `slice-reviewer` | 89% | G3 structural findings. |
| `contract-owner` | 87% | `tests/` and all fixtures. **On call for the route flip and for `g4-fence-covered-later`'s launcher window.** |
| `session-core` | 87% | Decoders, `probes/drivers/`. Natural owner of the parity list, without the room. |
| `views-and-colour` | unknown, stale past 75% | The pty differential, the 135-case stderr corpus, `color.rs`, `cells.rs`. |
| `context-curator` | ~78% | `decision-record.md`, `preserve-because-wrong.md`, the timing economies. |
| `query-semantics` | stopped clean | `search_query.rs`, transferred to `search-runtime` at L31. |

**No reviewer has capacity.** `session_render.rs` is past 3,700 lines and roughly
400 are reviewed. **Both facts are true and neither cancels the other** — its gates
are unusually strong, and it is not reviewed.

---

## 8. The rule five seats arrived at independently in one day

**A document patched section-by-section drifts exactly like a stale copy, and only
a whole re-read catches it** [L264].

`reviewer-profiler`'s runbook held three contradictions — **every one a true
statement that had quietly stopped being true** [L257]. `engine-and-codex`'s brief
claimed 173, 180 and 234 tests in three places and recorded a red since resolved,
**which would have sent a successor hunting a failure that no longer happens.**
`lexer-tables`' earlier brief asserted the opposite of its own code. The `sql`
fallback subject and the removed `g4-fence-never-covered` row both justified
themselves on languages promoted since.

**A check of what changed cannot find a sentence that decayed without being
touched.** That is why the re-read must be whole. **Six times on this mission, five
found something.**

**And the half usually dropped: a reconciled document is true at a digest, not
thereafter.** Every report on this desk carries when it was taken.

---

## 9. What decides whether the finish means anything

**Every gate green before the cutover is a formality.** 260 of `contract-owner`'s
assertions say the route is still Python, and the byte lock cannot fail on Rust
nothing calls. **It becomes a real gate the day the route flips.**

**A green result over a blind corpus is not evidence — seven confirmed cases.** The
worst is the newest: the body oracle asserted *"the recorded corpus reaches no
unsupported construct"* and passed, **because `flags_from` handled only
`show_thinking` and no recorded case could ever have set `show_tools`** [L254].
**Not a thin corpus, an incapable one.** `held-parameters.md` carries it as the
fifth bound, *vocabulary*, paired with the reflow finding: **capacity in the corpus
is not capacity in the cases a gate runs.**

**Ask what a corpus cannot say, and whether a passing case passes for the right
reason.** Three agreed for the wrong reason this week: `placeholder` (a word every
lexer paints the same), `sql` (a subject that survived its own promotion), and the
two `Read` cases (a result with no tool name). **Check 10 of G5 is the same shape**
— a `-ll` probe never touches the panel renderer, so the no-Python proof would pass
over a route that cannot render [L256].

**An outcome matching at every sampled point is not evidence the mechanism
matches** [22as]. **Two tells: agreement across a small sample, and a rewrite that
*removes* a branch rather than adding one.**

**"Too expensive" is a claim about a mechanism and must be measured against the
mechanism.** A gigabytes-of-disk argument met `cp -Rc` on APFS at 44 seconds and
zero disk. **A 687-line hand port met a 500-line crate with one operator wrong.**

**Where a hazard has a mechanism, change the mechanism** [L193]. A tool that
*printed* `ANCHOR MISSING` was ignored for hours; one that *refused* was obeyed in
seconds. **Design refusals, not warnings** — and the fallback subjects are now
*derived* from the promotion tables rather than asserted, so promotion moves them
instead of silently invalidating them [L250].

**A short form is true only under a disambiguation that travels separately from
it** [L55] — "zero warnings" over two build modes, "stdout" as a helper's held
default, "context %" as two quantities seventeen-fold apart.

**Five counting units exist in the render surface and none may be unified** [L180].
**One panel can carry two of them.** The tempting unification is the one that looks
like cleanup.

**Some behaviours are wrong and must stay wrong** — `preserve-because-wrong.md`,
eleven items. **Some right behaviours are invisible when absent** —
`timing-shaped-behaviours.md`. A port that improves either passes every gate we
have.

**Reproduce what Python accepts, not what it appears to intend.** `HOME=""` yields
`/`, and three sites this week collapsed *unset* and *set-to-empty* where Python
distinguishes them [L251]. **Ask at the call site: does this call distinguish
absent from empty, and does the product?**

---

## 10. How this seat has gone wrong

**Route findings; do not relay them.** Nine compressions or misattributions —
a site-specific fact became a general rule, a finding was credited to the wrong
seat, a subject was dropped so two compatible accounts read as a contradiction,
and today *"users who ask for tools"* stood in for *anyone viewing whole
conversations in colour*. **Summaries get checked against the record, not written
from memory. Send people to each other.**

**Do not infer a class from a clean sweep.** I wrote *"if they are clean, the panic
class is closed"* and it was wrong — one route is content-driven and no flag sweep
reaches it [L261]. **Eleven clean shapes over a curated fixture is the evidence
shape this mission has been caught by seven times.**

**Do not order work by the wrong quantity.** I recommended XML on block counts,
13% of the gap; it is **0.3% of painted characters** [L245]. **A language's share
of blocks and its share of colour are different quantities.**

**Naming a class is a claim, and it needs a count rather than a resemblance.** The
falsy-versus-absent class earned its name at three instances, not at one.

**Rulings stick because they are reasoned in public.** Every teammate has
overturned one of their own load-bearing sentences, and several have overturned
mine. **The rate at which this team finds its own errors is the only reason the
work is trustworthy.**

**An unanswered question and a "no" look identical from below.** Say which.

**Do not convert a reviewer to an implementer** — `decision-record.md` entry 2,
now unconditional. **Idleness was priced in.**

---

## 11. Post-cutover: the Arborium direction

**Durable product intent, not current scope.** Admiral, 2026-08-30. Reference
`alternatives.md` and its measured go bars. **Trigger: after G5 and the deletion of
the Python search authority.**

**Evaluate Arborium against the held-out corpus** — not a fresh harvest; the
held-out set is what makes a later comparison honest. **Use it as aggressively as
practical to delete custom code**: the lexer engine, the tables, the generators,
the alias and style tables. **The goal is maximal safe deletion, not adding
Arborium beside what exists.**

**⚠ The qualification, from the person who built both sides** [L235]: **the
engine, tables and generators are deletable if a replacement matches. The gates
and the held-out corpora are the *measurement*, so deleting them deletes the
evidence that the replacement is one.** The admiral's list names "bespoke oracle
machinery", which covers the gates. **The deletion target is the implementation,
not the measurement.**

**The bar any replacement must clear:** TypeScript 589 streams over 313,795
characters byte-exact; Bash 1031 of 1031; Python byte-exact on its first run; JSON
traced by executable line; SQL 15 of 15 rules reached with nothing exempted; **and
the held-out corpus at 745,179 unseen characters across all seven.**

**And the rule that must survive with the corpora: nothing is ever repaired against
them.** A failure is a defect in a table, a generator or the driver. **Regenerating
a held-out corpus to make it pass converts the only unseen evidence into more of
the seen kind.** The rule lives in the gate's failure message, and the separate
`--held-out` flag and paths exist so it cannot happen by accident.

---

## 12. The property that survives every version of this decision

**Nothing may truncate a printed scan.**

It has now been threatened three times from three directions: an unported fence
language, an unbuilt tool renderer reached by `--full`, and a step budget no
corpus can exhaust. **Each time the refusal was correct when written and became
the defect once something was wired to it.**

**Exit is 101 in every failing shape and redirected stdout never hits the bug at
all** [L233], so it is neither silent nor invisible to automation. **The
never-refuse property is still the one that must not be lost to any coverage,
fidelity or budget decision.**
