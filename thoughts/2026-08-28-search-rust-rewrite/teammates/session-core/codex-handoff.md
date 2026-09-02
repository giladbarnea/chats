# Codex decode — handoff

From `session-core`. Oracle revision `8cb4c5f`. Claude and Pi are landed and proved;
Codex is the third and last decoder. Everything below is measured on this machine unless
it says otherwise.

Read `session-core-map.md` for the reasoning behind the layers you sit on, and
`RESUME.md` for the tree state. This document is only what a Codex owner needs.

## What you are writing

`parse_codex(entries, flags) -> Vec<Message>` in **its own module** — `rust/codex.rs` or
similar — importing what it needs from `session`. **Not inside `rust/session.rs`.**

Ruled by `search-firstmate`: that file holds the Claude and Pi decoders, landed and proved
at 2,436 and 24,367 cases, and a new owner editing it is the collision the ownership rules
exist to prevent. Same pattern as `rust/color.rs` sitting beside `terminal.rs` rather than
inside it.

**The dispatch arm in `session.rs` is one line and it is `session-core`'s to add** — ask
directly rather than editing it. If that session has ended, the file transfers whole: the
Claude and Pi code in it is frozen, so you inherit something you must not edit rather than
something you must first understand.

The layers underneath are done and proved: entry decoding, provider selection, facets, the
visibility projection, shortening, tool filters, and the renderer. You produce `Message`s;
everything downstream already works.

Python authority: `parsing.py:1172-1330` for the entry loop, `2069-2555` for the Codex
helpers. `_CODEX_AGENT_LIFECYCLE_TOOLS` is `spawn_agent`, `wait_agent`, `close_agent`.

## CORRECTED: the named case, and my original mechanism was wrong

**Read this section as corrected by `engine-and-codex`, who measured it.** My original
claim — that 39 non-trivial sessions reach `parse_codex` and are filtered — was wrong
about the mechanism, and the six files I named below never reach `parse_codex` at all.

Their measurement, which I verified: those files' first non-empty line is a JSON object
with keys `id, timestamp, instructions, git` and **no `type` key**, so `detect_format`
returns `raw` and `SessionScan` takes the `parse_raw_cli_transcript` branch — which also
forces `cwd=None`, `summaries=()` and `custom_title=None`. The `developer` block and the
`<environment_context>` element really are in those files. Python never looks at them.

The true split, of 44 Codex sessions excluded from `search .`:

- **8 are raw-format**, excluded by format dispatch, and every large one is in this group
  (612, 449, 253, 179, 87, 37, 4, 3 entries). All six files listed below are these.
- **36 are jsonl-format**, genuinely decoded and filtered, every one with 2 to 4 entries —
  trivial rather than non-trivial.

**So a more permissive `parse_codex` cannot surface the large ones and would wrongly
surface the small ones.** Write against the 36, not the 8.

**And `parse_raw_cli_transcript` is a total no-op across the whole corpus** — a genuine
`> ` / `... ` CLI transcript does not exist anywhere in the pool. That is the 477-of-477
result in a second instance: zero occurrences, so no corpus can grade it. It is **not
ported**: `SessionFormat::Raw` exists in `session.rs` with no parser behind it. A known
gap, not a decision. Anyone porting it needs a synthesized fixture from the first line of
code, because nothing will ever fail without one.

## The original section, kept for the file list only

## The named case, and it is bigger than the team thinks

`reviewer-profiler` found **3** all-scaffolding sessions in a 695-file corpus and that
number has been repeated since. Measured against the full Codex corpus:

```
codex sessions on this machine:                    1208
non-trivial sessions Python renders as EMPTY:        39
roles present in those files:  user 60, developer 12
```

**39, not 3.** They contain no human-written content: a `developer`-role permissions
block, an AGENTS.md instruction blob, an `<environment_context>` element, and sometimes
only a `<turn_aborted>` notice. Python hides all of it — `developer` is neither `user` nor
`assistant`, and the user-role text is removed by the preamble and hidden-block filters —
so it concludes the session has nothing to show and **excludes it from `search .`**.

A decoder that is merely *more permissive* surfaces 39 empty abandoned sessions as search
results. Nothing at the message level shows the divergence; it changes which sessions
match without changing any message's bytes.

Six to start from, largest first, all under `~/.codex/sessions/`:

```
612 entries  rollout-2025-09-02T14-19-45-31052c3b-f800-4675-897d-0ae94e24ede3.jsonl
253 entries  rollout-2025-09-02T17-36-24-5499cd38-f137-49bc-b9b7-1e0cb0d48241.jsonl
179 entries  rollout-2025-08-31T12-30-33-09ebe887-5e6b-4600-8c12-769bb4424336.jsonl
 87 entries  rollout-2025-08-31T11-12-10-9ec267ad-b22a-4039-9bb7-7522fb104d9f.jsonl
  4 entries  rollout-2025-08-31T14-49-10-e5bf210a-9c19-430c-9009-b5abae88f674.jsonl
  3 entries  rollout-2025-09-09T14-16-13-d015004c-d5af-4d41-a631-37a06faf782b.jsonl
```

Re-derive the list rather than trusting it: the scan is a dozen lines and the corpus moves.

## The thing I most want you to take

**A real corpus cannot prove a Codex decoder complete, and I can show you the number.**

For Pi I reintroduced the prior team's exact defect as a mutation — requiring
`<duration_ms>` where Python's grammar makes it optional. It caught **zero** across 400
sessions. So I measured: **477 joined user-agent envelopes exist in the whole corpus and
all 477 carry the terminator.** Not one omits it. The shape does not occur in real usage,
so a corpus of any size is blind to it, and all 24,367 of my green Pi cases were exactly
as blind as the fixtures that missed it originally.

Codex has more optional grammar than Pi, not less — script tool calls, reasoning
extraction, preamble detection, `environment_context`. Expect the same. **The method that
works: write the decoder, mutate it toward the wrong version you would plausibly have
written, and when a mutation catches zero, measure whether the shape exists rather than
concluding you got it right.**

Fixtures for what the corpus lacks go in `codex-fixtures/`, following
`probes/make_pi_fixtures.py` — which asserts Python itself produces the behaviour from
each fixture, so a malformed fixture cannot pass as a working one.

## The instrument, already built for you

`probes/claude_render_differential.py` dispatches on `PROVIDER`. Add `"codex" =>
parse_codex(...)` to the driver's match and run `PROVIDER=codex`. It compares the full
route — decode, visibility, shortening, render — as the exact string search matches
against, over 7 flag configurations.

Four properties it has that you must not remove:

1. **It snapshots every session before comparing.** This project's own session directory
   is under active write by other agents, and the instability concentrates in the newest
   files — exactly where a newest-first scan looks first, so the artifact lands at the top
   of the diff and is maximally convincing.
2. **It passes the *original* path for provider classification while both sides read the
   *snapshot* bytes.** Python classifies providers by location. A naive snapshot fixes one
   intermittent failure and creates a systematic one.
3. **It guards the row count.** A driver returning fewer rows than cases misaligns every
   later comparison and reads as concentrated product defects. I lost an hour to that.
4. **It digests both sides or neither.**

Falsify with `scratchpad/mutate_pi.py` as the pattern. It reports **ANCHOR MISSING —
mutation not applied, result meaningless** rather than a number, because a mutation that
was never applied and a mutation that nothing caught both print zero.

## Results to match

| decoder | cases | result |
|---|---|---|
| Claude | 2,436 (348 sessions × 7) | 0 mismatches |
| Pi | 24,367 (3,481 sessions × 7) | 0 mismatches |
| Codex | 1,208 sessions available | yours |

## Two traps specific to Codex that I have not verified

Flagged as leads, not findings — I read them and did not run them.

- `_extract_cwd_from_codex_entry` reads `<cwd>` out of `<environment_context>` with a
  DOTALL regex, and `session_meta.payload.cwd` takes precedence. Already ported in
  `session::cwd`; your decoder should not duplicate it.
- `_merge_codex_script_tool_calls` merges consecutive script calls. Merging is the kind of
  behaviour a port simplifies away without changing any single message, which is precisely
  the failure class this handoff is about.
