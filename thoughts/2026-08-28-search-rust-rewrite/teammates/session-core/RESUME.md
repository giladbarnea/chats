# session-core — resume state

Kept current as work proceeds. Oracle revision: `8cb4c5f`.
**Context: 74% used (harness figure, not an estimate).** My own estimates ran high twice
today, by 10 and 11 points. Report the harness number; do not estimate.
Read `session-core-map.md` for the reasoning; this is the state that document cannot hold.

## Uncommitted production edits, all mine

| file | state |
|---|---|
| `rust/codecs.rs` | slice 1: escaping repair + `render_message_inner_xml(msg, encode_transport)`. **Proved.** |
| `rust/shortening.rs` | new. Policy, spec grammar, `truncate_middle`, `shorten_data`, argv helpers. **Proved.** |
| `rust/tool_filter.rs` | new. `--tools` grammar, matching, short-policy resolution. **Proved.** |
| `rust/visibility.rs` | new. Flags, selection, visible-message projection, progressive assignment. **Proved.** |
| `rust/session.rs` | new. Format detection, entry decode, provider selection, facets, branch map, **Claude decode**. **Proved.** |
| `rust/model.rs` | additive: `tools_always_visible`, tool-name aliases, `normalize_tool_input_keys`. |
| `rust/lib.rs` | module declarations only. |

`cargo build --release --no-default-features` green; lib tests and doctests green.

## Proof held

Four **live** differentials — both sides compute fresh, out-of-process via a driver that
links the crate as a path dependency. **No PyO3 exposure needed**; not a stored table and
not an end-to-end comparison.

| differential | cases | result |
|---|---|---|
| `truncate_middle` | 308 | 0 mismatches |
| `parse_tool_spec` | 2006 | 0 mismatches |
| `branch_map` | 355 | 0 mismatches |
| **full Claude route** (decode + visibility + render, 7 configurations) | **2,436** | **0 mismatches** |
| **full Pi route** (same, 3,481 sessions) | **24,367** | **0 mismatches** |

Pi carries three synthesized fixtures in `pi-fixtures/`, all validated against Python and
all three hazards discriminated by `probes/mutate_pi.py`: `require_duration_ms` catches 7,
`skills_never_split` 546, `ambiguity_takes_the_first` 7.

Each has been falsified against deliberately wrong ports. The `branch_map` tie-break
mutation was invisible until an `equal-depth-fork` fixture was added — the corpus cannot
produce that shape.

Branch fixtures **store** their expected maps; the generator refuses to emit one Python
disagrees with. They do not re-derive.

## Instrument properties a successor must keep

- **Snapshot sessions before comparing.** This project's own session directory is under
  active write by other agents. `query-semantics` added where it lands: the instability
  concentrates in the **newest** files, which is exactly where a newest-first scan looks
  first — so the artifact appears at the top of every diff and is maximally convincing.
  Their first pool comparison showed 10 differing positions out of 5,036 and looked
  precisely like an ordering defect. It was the team's own live transcripts. Pass the *original* path for provider classification
  (Python classifies by location) and read the *snapshot* bytes on both sides.
- **Guard the row count.** A driver returning fewer rows than cases misaligns every later
  comparison and reads as concentrated product defects.
- **Digest both sides or neither.**

## What comes next, in order

1. ~~Pi decode~~ **DONE** — 24,367 cases, 0 mismatches. Superseded text: Python authority
   `parsing.py:863-1168` and `1948-2180`. The joined user-agent envelope's
   `<duration_ms>` is **optional** (`parsing.py:974-978`); the prior team shipped a parser
   that required it and silently dropped content. Ambiguity must yield nothing, never a guess.
2. **Codex decode** — `parse_codex`, in **its own module, not `rust/session.rs`** (ruled:
   that file holds landed Claude and Pi decoders and is frozen). The one-line dispatch arm
   in `session.rs` is `session-core`'s to add. Full handoff: `codex-handoff.md`. The named
   case is **39 sessions, not 3** — the smaller number came from a 695-file sample. Not started. Write it against the three
   all-scaffolding sessions (`developer` role, AGENTS.md blob, `<environment_context>`,
   `<turn_aborted>`): Python hides all of it and excludes those sessions from `search .`.
   A merely-more-permissive decoder surfaces empty sessions as results.
3. **`rust/color.rs` is NOT mine — it belongs to `views-and-colour`.** Ruled handed off.
   Do not open that file. What I leave them: `colour-downgrade-oracle.json` (1499 rows)
   and `probes/falsify_colour_gate.py`, both live and both theirs to use. `NO_COLOR` is
   **not** an absent colour system — it strips colour and keeps attributes.

4. **A `resolve_tool_visibility` test** consuming `reviewer-profiler`'s 7315-case table
   once `contract-owner` places it under `tests/`.


## The C0 / `.trim()` work — specified, fixture built and proved RED, not landed

**Ruled option 1 by `search-firstmate` (L47): build the fixture, prove it red, then edit.
Owner changed at 87% context. The fixture step is done; the 20 edits are not.**

**Deadline is the deletion slice, not G4.** Decision 13 keeps `ch-legacy search` alive as a
live oracle *through* cutover, so there is real room. Do not rush it.

### What is already done

`probes/make_c0_fixture.py` writes `claude-fixtures/c0-separators-at-string-edges.jsonl`
and validates it **against Python**: 3 messages, every separator removed. It is **proved
red against the current code — 7 mismatches**, one per flag configuration. So the fixture
fires. Do not re-derive it; run it.

### The enumeration — this is the work, and rebuilding it costs an hour

Python `str.strip()` removes U+001C–001F; Rust `str::trim` does not. `session.rs` defines
`python_strip` for exactly this and these sites do not use it. Line numbers will drift;
the functions will not.

**Port `.strip()` — replace bare `.trim()` with `python_strip`:**
`custom_title_from_entry` (title); `codex_cwd_from_entry` (the `<environment_context>`
text and the `<cwd>` group); `command_tag_lines` (blank-line skip);
`normalize_command_tag_value` (both calls); `parse_assistant_entry` (text-block emptiness
test and the pushed value, and the thinking block); `parse_system_entry` (recap);
`parse_hook_additional_context_entry` (block emptiness); `split_pi_inline_skills` (skill
body); `parse_pi_compaction_entry` (summary); `extract_pi_user_agent_response` (content,
and each response candidate); `parse_pi_user_agent_entry` (task); `parse_pi_message_entry`
(thinking, both the emptiness test and the pushed value).

**Port `.lstrip()` — needs a leading-only variant:** the two cursor advances in
`split_pi_inline_skills` (`text.trim_start()` and `tail.trim_start()`).

**Correctly bare — do NOT change these three:** the two inside `dedent`, which ports
`textwrap.dedent` and its own whitespace notion; and the assertion inside
`python_strip_removes_the_c0_separators_rust_trim_leaves`, which asserts the *wrong*
behaviour on purpose so a reader who simplifies gets an explanation rather than a diff.

### Measured, so nobody re-runs it

**5,046 files scanned; zero contain U+001C–001F anywhere; zero string values carry one at
an edge.** Every differential I hold — 2,436 Claude, 24,367 Pi — is blind to this. That is
an instrument limit, not a property of the world: transcripts carry arbitrary tool output.

The differentials **can** verify the edits break nothing else, which is what makes 20
mechanical changes safer than they look.

### The rule that applies

A synthesized fixture is not done when it exists, it is done when its **mutation catches
something**. My Pi ambiguity fixture caught zero on its first version — it omitted the
preview, which short-circuits before the check the mutation removes. A fixture that fails
to fire looks exactly like the corpus answer it was written to replace.

## Binding constraints a successor must not undo

- Do not unify the three counting units: code points in `truncate_middle` and
  `elide_to_width`, UTF-16 code units in Pi `responsePreview`, display columns nowhere.
- `elide_to_width`, `truncate_middle` normalization-sensitivity and `collapse_home`
  prefix-matching are preserved-because-wrong.
- Reproduce `s[-0:]` returning the whole string in `truncate_middle`; do not guard it.
- A **bool** `color=true` resolves colour off and metadata colour on.
- An empty `ToolVisibility::Filters` list is falsy, not "all".
- Branch ids are numbered by **first appearance in file order**, never traversal order.
- `branch_map` builds its graph from the **deduplicated node map**, not the entries. Real
  sessions carry duplicate uuids and building from entries changes the answer.
- **Keep the `visited` set in `origin_session_root`.** It is byte-identical on every
  well-formed file and prevents a hang on a corrupt one, so no output comparison can
  justify it — and this project's own anti-defensive-programming rules argue for deleting
  it. Do not.

## Open items handed to others, not to a successor

- **Codex** is `engine-and-codex`'s. Handoff at `codex-handoff.md`, **corrected** — my
  original mechanism was wrong and theirs is recorded at the top of that section.
- **`parse_raw_cli_transcript` is unported.** `SessionFormat::Raw` exists in `session.rs`
  with no parser behind it. A gap, not a decision. It is a no-op across the entire real
  corpus, so no corpus can ever grade it — it needs a synthesized fixture from the first
  line of code.
- **`session::select_provider` returning `Err` is deliberate.** Python's
  `_select_jsonl_session_adapter` raises rather than falling back to Claude, and the Claude
  adapter cannot be selected by content matching at all. Do not map that error to Claude.
- **The one-line Codex dispatch arm** in `session.rs` is owed to `engine-and-codex` when
  their `rust/codex.rs` compiles. `session.rs` transfers frozen otherwise.

## Not blocking

Shipping build and `cargo test` are green. The contract suite's setup errors are
`contract-owner`'s oracle guard reacting to `src/chats/` movement, not a regression.
