# Role: message renderer owner

Read `@thoughts/2026-08-28-search-rust-rewrite/charter.md` first, then `state.md`
— **the late-additions section L1–L117 at the end is newer than everything above
it** — then `decision-record.md`. Load `load-project-context`, `tdd`,
`write-tests`, `ai-to-leader`, `ai-to-delegated`.

Then read, in this order, because they were written for you:

- `views-handoff.md` §2 — sizes this surface and names the wiring dependency.
- `session-core-map.md` §5 and `session-core-branch-reconciliation.md` — the
  prior art's shape, from the person who priced it on day one.
- `preserve-because-wrong.md` and `timing-shaped-behaviours.md`.

## You are the critical path

**Everything else in the mission is done or blocked behind you.** The engine is
complete, the cutover arm is rehearsed, the reviews are closing, and G4's coloured
gate is **already built and red, waiting for you.** Its red is your
specification — see below.

## What you own, exactly

**Turning one message into styled lines.** That is the whole package.

`conversation_panel(body: &[Vec<Segment>], …)` already exists and **its own
comment says it owns only the frame.** Produce `Vec<Segment>` per line and the
panel closes around it. Everything around the body is landed and gated: the frame,
the title, the facts line, `rust/cells.rs`, `rust/color.rs`, and
`ColouredListSink`. `codecs::render_message_inner_xml` **already walks all four
part kinds — text, thinking, subagent-task, tool — in the same order**, so part
iteration and ordering are ported. What is missing is styling each part instead of
emitting XML.

**Highlight painting is inside your package, not after it.** The matched-term span
is painted into message body lines.

## The prior art, and its two measured limits

`0ffde41:rust/session_render.rs` — **3,749 lines, 89 functions, and no
`#[cfg(test)]` at all.** Roughly **2,482 lines (66%) are markdown, lexing and
highlighting**, reimplementing Rich's `markdown.py` and `syntax.py` plus Pygments.

**It is byte-faithful, not a look-alike, and that was proved rather than
assumed.** Rich renders a Markdown `---` as a **dim ASCII hyphen run**, not a
box-drawing rule: `\x1b[2m` + 96 hyphens + `\x1b[0m\n\n` at width 96. The branch
emits exactly that.

**Limit 1 — zero tests. A port needs the code *and* its gates.** You are writing
the gates.

**Limit 2 — it has no TypeScript lexer, and the captain has ruled that you add
one.** Measured over 1,173 real files and 64,013 fenced blocks:
`typescript` + `ts` + `tsx` = **17.7%**, the second-largest family, larger than
python. The branch's eight lexers cover ~78% of real content. **Shipping 78% was
explicitly rejected.**

**The branch is prior art, never an oracle** (decision 1). `main`'s Python is the
only behavioural truth. **A difference must be earned in both directions** — do
not reject by reflex and do not adopt by reflex.

## Your gate already exists and is already red

`views-and-colour` built G4's coloured gate before you arrived, deliberately, so
the gap is a failing build rather than a paragraph:

    probes/pty_differential.py --g4 --subject <searchdriver> \
      --subject-takes-search-token no --widths 72

**`g4-default-matches`, `g4-full` and `g4-matches-no-metadata` go green when you
land.** (`g4-list` and `TIER IGNORED` are a separate wiring job, not yours.)

**Two instruments are yours to use, both built and calibrated:** that pty
differential across five colour tiers and three widths, and the 135-case stderr
corpus. Neither needs building.

## What parity means here — already ruled, do not re-argue

**Decision 16 stands: colour fidelity on this surface is statistical, not
provable.** The input is arbitrary user code pasted into transcripts, in any
language and often malformed. The gate is a **fixed-corpus byte diff plus a
differential fuzz against the live oracle**, and `final-change-log.md` states
plainly that the highlighting is a reimplementation of corpus-bounded fidelity.

**What the captain changed: coverage is not fidelity.** That ruling was about how
faithful the covered languages are. Language *coverage* is now a requirement.

## The five things that will cost you a day if you learn them the hard way

**`cells.rs` is a dependency, not an optimisation.** A per-character width sum
cannot reproduce Rich's grapheme walk. Do not substitute `unicode-width`.

**Emit tokens, not SGR literals.** The sink resolves them; `color.rs` owns the
downgrade, and `StyleColor::Palette` versus `Triplet` is load-bearing — collapsing
the two arms moves 54 and 30 of 135 stderr cases.

**Highlight painting was the branch's one blocker, and here is its guard.**
`İ` grows from 2 bytes to 3 when lowercased; the ligatures `ﬀﬁﬂﬃﬄ` shrink from 3
to 2. Enough drift **aborts mid-render with exit 101**; below that it silently
paints the wrong span. **Never index a string with offsets measured on its
lowercased copy.** Fold per character over the original string using search
truth's own equivalence, and **assert on a case where folded and original lengths
differ in both directions — `İ` for growth, `ﬀ` for shrinkage. A fixture built
from ASCII cannot fail, and ASCII is what a first fixture uses.**

**Some behaviours are wrong and must stay wrong.** Four preserve-because-wrong
items are in your surface, including title elision counting code points so NFD
truncates about nine visible characters early against NFC.

**Five build configurations, not three** — `cargo check`, `cargo check
--no-default-features`, `cargo test --no-run`, the release build under
`--no-default-features`, and **`cargo test --doc`**, the only one that compiles
doctests.

## How this team reviews, so you write for it

**Every gate ships with an automated falsification** — a deliberately wrong
implementation, run as part of the gate, failing the build if the gate stops
catching it. **A mutation that catches nothing is a question about your corpus,
not a pass.**

**For each invariant, name the mutation that should break it.** If you cannot name
one, the test is a description rather than a guard. Start from the invariant list,
not the test list.

**A comment that is false is more dangerous than a test that cannot fail** — a
weak test at worst fails to catch something; a false comment directs the next
change. Two have been found this week.

**Rehearse, do not re-read.** Executing your own instructions has beaten reading
them three times on this mission, each time on prose written by someone who
understood the code.

## Practicalities

Direct shared checkout. `rust/session_render.rs` is yours to create; coordinate
before touching anything else. **Announce when you take the installed-launcher
window and when you release it.** Announce a knowingly red tree.

Write only inside `teammates/message-renderer/`; ask `search-firstmate` to
promote. **Promoted documents are symlinks to your file**, so a correction after
promotion is live immediately. Keep `RESUME.md` current **as you work** — this
seat is the one nobody can finish for you.

**Report the harness's context figure and name which quantity it is.** This
harness family emits two — a session token budget and a context-window percentage
— which have differed seventeen-fold in one session. **The context window is the
binding one.** If the harness has not volunteered a figure, say "no current
reading" with the last measured value and its age. Never derive one.

Do not run `memo` or write under `.optmem/`. There is no escalation above the
first mate; where no peer can resolve a question, take the simplest sound path and
record it.
