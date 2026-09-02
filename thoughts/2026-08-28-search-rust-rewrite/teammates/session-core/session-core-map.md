# session-core map

Owner: `session-core`. Baseline: HEAD `8cb4c5f`, working tree clean except this desk.
**Oracle revision for every characterization in this document: `8cb4c5f`.** Each result
below was measured against the Python at that revision, through a `src/chats/` working
tree equal to it. A characterization that does not name its oracle revision is not
evidence, and `src/chats/commands/search.py` is scheduled to move under an exception.
Status: Phase 1 (G1 candidate). No production file touched.

Companion: `branch-reconciliation.md` — this boundary compared against the finished native
rewrite on branch `0ffde41`. Read it with §4 and §5 below; it amends both.
Amendments from team findings are in §10.

## 1. Bottom line

Search truth is one string per message plus two session-level strings. Everything my scope
owns exists to produce those strings exactly as Python produces them today:

```
JSONL bytes
  -> decode entries                 (provider adapter: claude | pi | codex)
  -> normalize into Message list    (branches, agents, tools, metadata)
  -> apply flags                    (visibility, role/tool filters, shortening)
  -> render semantic inner XML      (per message, transport encoding OFF)
```

The renderer at the end of that pipeline **already exists in Rust**. The three decoders at
the front of it **do not exist in Rust at all**. That asymmetry is the single most important
fact in this map, and it is the opposite of what the file names suggest.

## 2. Current authority

### 2.1 What Rust owns today

`rust/model.rs` and `rust/codecs.rs` are not a session parser. They are the transport codec
behind `ch parse`: canonical JSON <-> XML-tagged Markdown, over an **already normalized and
already filtered** message list. `ch parse` is the only subcommand the native binary owns;
every other argv falls through to `run_legacy`. (`ch-legacy parse` resolves `parse` as a
session identifier — the Python `parse` subcommand no longer exists.)

Concretely, `codecs.rs::render_message_content` emits parts in the order
`subagent-task, text, thinking, tools, plan` — byte-identical in structure to Python's
`_render_message_inner_xml`, because it was built from the same spec. It hardcodes
transport encoding on, because its only caller is `ch parse`.

`rust/model.rs::Message` mirrors Python's `to_json_dict` projection, not Python's `Message`
dataclass. It is complete as a *render-time* model and incomplete as a *decode-time* model
(§4.1).

### 2.2 What Python owns today

| Concern | Python authority | Lines | Rust today |
|---|---|---|---|
| Format detection, entry decode | `parsing.py:443-492` | ~50 | none |
| Adapter selection | `parsing.py:1623-1712` | ~90 | none |
| Claude decode + branches + agent suppression | `parsing.py:645-860,1756-1947` | ~450 | none |
| Pi decode (inline skills, user-agents, compaction) | `parsing.py:863-1168,1948-2180` | ~530 | none |
| Codex decode (script tool calls, reasoning, preamble) | `parsing.py:1169-1330,2069-2555` | ~650 | none |
| Facets: summaries, custom titles, cwd | `parsing.py:130-442,2621-2660` | ~310 | partial (`scan_resolution_facets`, PyO3-gated) |
| Message model + visibility + progressive | `model.py` | 679 | partial (struct only) |
| Tool filters | `tool_filter.py` | 263 | none |
| Shortening | `shortening.py`, `utils.py:8-40` | ~140 | none |
| Tool -> parts -> XML | `tools.py`, `xml_transport.py`, `registry.py` | ~440 | **complete** |
| Inner-XML render | `formatting.py:434-501` | ~70 | **complete but transport-only** |
| One-pass scan | `session_scan.py` | 67 | none |

Roughly 3200 Python lines in my cone. About 450 of them already have a working Rust
counterpart. The rest is new construction.

### 2.3 What is *not* mine, despite looking like it

`_merge_agent_messages` (`commands/parse.py:281`) splices subagent transcripts read from
disk into the message list. It is called only by the `parse` command. **Search never merges
agents.** I am not porting it, and native search must not gain it. Anyone who assumes
`--agents` in search implies transcript merging is wrong; in search, `show_agents` only
gates already-in-file agent content.

## 3. Falsifiers

### 3.1 Attempted and CONFIRMED — this changed the plan

**Claim under test:** the existing Rust renderer is byte-exact with the Python renderer, so
reusing it is free.

**Disproved.** Message text whose line starts with an inner tag name followed by a space,
without a well-formed attribute list, is escaped by Rust and left alone by Python.

```
input text:  "<thinking is my hobby\nand a second line"

ch parse -f xml        -> <user-message i="1" text_encoding="html">
                          &lt;thinking is my hobby
Python format_to_xml   -> <user-message i="1">
                          <thinking is my hobby
```

Cause: `codecs.rs::has_inner_opening_tag` accepts `<tag` followed by `>` **or a space**.
`xml_transport.py:_INNER_XML_BLOCK_OPENING_PATTERN` requires a complete opening tag,
`^<tag(\s+[\w-]+="[^"]*")*>`.

**Correction — the divergence is bidirectional, not one-directional as I first wrote.**
I originally reasoned that Rust is strictly more eager. It is not: Python's `\s+` admits a
tab or a newline where Rust tests only for a literal space, and Python's pattern is
`re.MULTILINE`, so an opening tag may continue onto the next line while Rust's check is
strictly per-line. Measured against both binaries:

| text line | Python escapes | Rust escapes | |
|---|---|---|---|
| `<thinking is my hobby` | no | **yes** | Rust over-eager |
| `<thinking\tname="x">` | **yes** | no | Rust under-eager |
| `<thinking\nname="x">` | **yes** | no | Rust under-eager, cross-line |
| `<thinking name="x">` | yes | yes | agree |
| `<thinking>` | yes | yes | agree |

So the repair is not "make Rust stricter." It is "implement Python's actual grammar," which
means the full `\s` class in the attribute separator and the cross-line continuation. A
fixture set covering only the over-eager direction would leave two shapes untested. Probe:
`probes/reverse.py`.

The existing suite is green because `ch parse` round-trips its *own* escaping faithfully.
Round-trip fidelity is not cross-implementation parity. **Consequence:** reuse stands, but
as reuse-plus-repair. I do not get to assume any part of `codecs.rs` is parity-correct
without a differential test behind it.

This one is out of search's own truth path (`render_message_inner_xml` never transport-
encodes) but it is a live `ch parse` defect today. Handed to `contract-owner` and
`search-firstmate`; I will repair it inside `codecs.rs` when I own that file.

### 3.2 Open falsifiers, per slice

| # | Slice | Falsifier (a result that kills the approach) | Positive definition of done |
|---|---|---|---|
| F1 | Renderer reuse | Any real corpus message where Rust `render_message_content(encode_transport=false)` differs from Python `render_message_inner_xml`, beyond §3.1 | Every message of every fixture session, all flag configurations, renders byte-identical; diff count 0 |
| F2 | Shortening | A code-point-vs-byte divergence: any non-ASCII payload where Rust `truncate_middle` cuts at a different character than Python | Property test over multi-byte and astral-plane strings at limits 8..600 agrees on every input |
| F3 | Claude branches | Any corpus session where the native branch id map differs from Python's, in membership or in numbering | Branch map identical across every Claude session in the fixed corpus, including compaction and rewind-to-first-message shapes |
| F4 | Progressive shortening | Any session where the set of progressive-qualifying messages or their positions differ | `assign_progressive_shortening` equivalence on the corpus under `-s:p`, `-t:s=p`, and mixed local/global policies |
| F5 | Tool filters | Any `--tools` spec where visibility or the winning short policy differs, especially specificity ties | Full cross product of the spec grammar against a tool-dense session agrees on visibility and limit |
| F6 | Adapter selection | A session whose provider resolves differently when path classification is unavailable and first-entry matching decides | Provider identical for every corpus file, with path classification both present and suppressed |

F1 is the gate for the whole scope: if the renderer cannot be made byte-exact, every other
slice is measuring against a moving target.

## 4. Proposed boundary

### 4.1 Existing files I need to own

**`rust/model.rs`** and **`rust/codecs.rs`**. These are the shared canonical model and the
renderer; they are the two files my scope cannot avoid. Required changes:

- `Message` gains `tools_always_visible: bool` (decode-time property, drives visibility).
- `ToolUse` gains `name_aliases: Vec<String>` — `tool_filter.py:_resolve_tool_names` matches
  against them and they have no Rust counterpart today.
- `render_message_content` takes `encode_transport: bool` instead of hardcoding `true`.
- `has_inner_opening_tag` repaired to the Python grammar (§3.1).

I do **not** need `Message` to carry `progressive_position` / `progressive_qualifying_count`.
Python mutates messages to place them; I will compute a `ProgressiveAssignment` alongside the
list and pass it into the render. Same output, no shared mutable state, smaller diff to a
file that `ch parse` also depends on.

### 4.2 Files I create

Under one module root, ordinary Rust, no PyO3 on any path:

```
rust/session/decode.rs       format detection, entry decode, adapter selection
rust/session/claude.rs       Claude entries, branch resolution, agent-dispatch suppression
rust/session/pi.rs           Pi entries, inline skills, user-agent responses, compaction
rust/session/codex.rs        Codex entries, script tool calls, reasoning, preamble
rust/session/facets.rs       summaries, custom titles, cwd, entry-level text blocks
rust/session/flags.rs        ConversationFlags, MessageSelection
rust/session/visibility.rs   visible parts, progressive assignment
rust/session/tool_filter.rs  ToolFilter, parse_tool_spec, resolve_tool_visibility
rust/session/shortening.rs   ShortPolicy, ShortSpec, truncate_middle, shorten_data
rust/session/scan.rs         SessionScan
```

`rust/lib.rs` needs module declarations. It is the lift owner's file; I will send the lines
rather than edit it, unless G2 says otherwise.

### 4.3 Boundary I am *proposing*, not asserting

`parse_tool_spec` is argument-shaped and lives beside the matching semantics it feeds.
Splitting the 263-line file across two owners buys nothing. I propose core owns the whole
tool-filter unit and `search-runtime`'s launcher calls `parse_tool_spec`. If `search-runtime`
wants the grammar, I will take only `ToolFilter` + `resolve_tool_visibility` and we keep the
seam at the struct.

## 5. Interfaces

Provisional signatures, offered now so G2 can freeze them.

### 5.1 To `search-runtime`

```rust
pub struct SessionScan {
    pub provider: Option<Provider>,
    pub cwd: Option<String>,
    pub summaries: Vec<String>,
    pub custom_title: Option<String>,
    pub messages: Vec<Message>,
}

impl SessionScan {
    pub fn from_content(
        content: &str,
        flags: &ConversationFlags,
        path_provider: Option<Provider>,
    ) -> Result<SessionScan, String>;
}

pub fn build_tool_id_map(messages: &[Message]) -> ToolIdMap;
pub fn assign_progressive_shortening(
    messages: &[Message], flags: &ConversationFlags, tool_id_map: &ToolIdMap,
) -> ProgressiveAssignment;

pub fn render_message_inner_xml(
    message: &Message, flags: &ConversationFlags,
    tool_id_map: &ToolIdMap, progressive: &ProgressiveAssignment,
) -> String;
pub fn format_to_raw(/* same inputs, message slice */) -> String;
pub fn format_to_xml(/* same inputs, message slice */) -> String;

// entry-level prefilter helpers, for the candidate gate
pub fn entry_text_blocks(content: &Value) -> Vec<String>;
pub fn codex_entry_text_blocks(content: &Value) -> Vec<String>;
pub fn filter_hidden_user_text_blocks(blocks: Vec<String>) -> Vec<String>;
pub fn is_codex_preamble_text(text: &str) -> bool;
pub fn custom_title_from_entry(entry: &Map<String, Value>) -> Option<String>;
pub fn select_adapter(
    path_provider: Option<Provider>, first_entry: Option<&Map<String, Value>>,
) -> Result<Provider, String>;
```

Note `path_provider: Option<Provider>` rather than a path. Path classification is the lifted
core's job, not mine; taking its *result* keeps one authority and unblocks me from the lift's
schedule (§7).

### 5.2 To `query-semantics`

Core produces strings. Query semantics matches strings. Core knows nothing about regex,
literals, or boolean evaluation, and query semantics knows nothing about messages.

```rust
pub struct SearchableSession<'a> {
    pub summaries: &'a [String],
    pub custom_title: Option<&'a str>,
    pub rendered_messages: &'a [(usize, String)],  // message index -> rendered inner XML
}
```

Those three fields are exactly the search truth Python evaluates today
(`commands/search.py:1189-1219`): a term is satisfied by a hit in any summary, in the current
custom title, or in any rendered message. Nothing else in the session is searchable. If
`query-semantics` needs a fourth source, that is a contract change, and I need it at G2.

## 6. Contract needs

For `contract-owner`, in priority order:

1. **Renderer differential.** Byte-exact `render_message_inner_xml` over every corpus session
   and every flag configuration. This is F1 and it gates everything.
2. **The §3.1 case.** Text starting with an inner tag name plus a space. Not covered by the
   round-trip fixtures, and it is a live defect.
3. **Shortening at code-point boundaries.** Non-ASCII and astral-plane payloads at limits
   around `MIN_SHORT_MAX_CHARS` and the placeholder length. Python slices code points; a
   naive Rust port slices bytes and panics or truncates differently.
4. **Branch resolution shapes.** Compaction boundaries, rewind to first message, a leaf
   recorded in a later era, and a truncated head. Python's own docstring names these; I have
   not confirmed the corpus contains one of each.
5. **Tool-filter specificity ties.** Two matching short filters of equal specificity: Python
   resolves by later position. Easy to get backwards.
6. **Adapter selection without path classification.** Content-signature fallback.

## 7. Dependency on the lifted core

One item, and it is small. My decode path needs provider classification for a path, which is
`classify_native_session_path` in the PyO3-gated file. I do not want a second copy.

**I have removed this from my critical path** by taking `Option<Provider>` as an input
instead of a path (§5.1). The caller supplies it. So the lift is a dependency of the *route*,
not of my slices, and it does not need to land before I start. The content-signature fallback
that runs when classification yields nothing is entry inspection, so it stays mine.

Everything else in that file — discovery, mtime, the ASCII gate, the logical-JSON-string
gate, the backward timestamp scan, resolution facets — my scope does not call.

## 8. Slices

Ordered by dependency. One public green boundary at the end, per the charter.

1. **Renderer reuse + repair** — `model.rs`, `codecs.rs`. Falsifier F1. Nothing else can be
   measured until this is exact.
2. **Shortening + tool filters** — pure functions, no session I/O. F2, F5.
3. **Visibility** — flags to visible parts, progressive assignment. F4.
4. **Claude decode** — the largest and the only one with a graph algorithm. F3.
5. **Pi decode**, **Codex decode** — independent of each other, both depend on 1-3.
6. **Facets + `SessionScan`** — assembly, and the prefilter helpers `search-runtime` needs. F6.

Slices 2 and 3 are the cheapest place to prove the differential harness works, so I would
rather run them before slice 4 even though slice 4 is the long pole.

## 9. Decisions recorded

- **Progressive positions computed alongside, not stored on `Message`.** Rejected: mutating
  `Message` as Python does. Why: `ch parse` shares that struct, and a smaller diff to a shared
  file is worth more than mirroring Python's internal mechanics. Output is identical.
- **Core takes `Option<Provider>`, not a path.** Rejected: core calling the path classifier
  directly. Why: it would either duplicate the classifier or block my slices on the lift.
- **Agent transcript merging stays out of the native core.** Why: search does not use it
  today, and the charter forbids widening behavior.

## 10. Amendments

### 10.1 Three first-line policies, two JSON parsers — verified

My decode path reads the first line of a session three different ways, and the three
disagree by design. A single Rust helper for all three is the most likely way to break this.

| Function | Blank lines | First non-blank line decides? | Malformed / non-object |
|---|---|---|---|
| `detect_format` | skipped | yes, and it must be an object **with a `type` key** | falls back to `"raw"` |
| `_read_first_jsonl_entry` | skipped | yes | returns `None`, **aborts** |
| `_iter_jsonl_entries` | skipped | no | **skips the line, keeps going** |

Worse, they do not share a JSON parser. `detect_format` uses stdlib `json`;
`_iter_jsonl_entries` and `_read_first_jsonl_entry` use `orjson`. Verified divergence:

```
content: '{"type": "user", "v": NaN}\n{"type": "user", "message": {...}}'

detect_format(content)        -> "jsonl"     (stdlib json accepts NaN)
decode_jsonl_entries(content) -> 1 entry     (orjson rejects NaN, line dropped)
```

The file is treated as JSONL and its first entry silently disappears. A Rust port with one
parser for both paths diverges either way: reject NaN everywhere and the file becomes `raw`;
accept it everywhere and the entry survives. **New falsifier F7:** any session line accepted
by exactly one of the two parsers must reproduce this asymmetry. **Contract need:** a fixture
whose first line is stdlib-valid and orjson-invalid.

This extends `context-curator`'s verified rule that `_read_first_jsonl_entry` aborts rather
than skips — the abort-vs-skip split is real, and the parser split rides on top of it.

### 10.2 Interface additions requested by `search-runtime`

Add to §5.1:

```rust
pub fn display_session_id(path: &Path, provider: Provider) -> Result<String, String>;
pub fn native_session_id(path: &Path, provider: Provider) -> Result<String, String>;
pub fn forked_from(path: &Path, provider: Provider) -> Option<String>;
```

Per-provider, so they are mine: Pi and Codex read their id out of the session header, Claude
uses the file stem, and `forked_from` is Codex-only today.

### 10.3 Scope removals

- **`scan_resolution_facets` is off the native search route.** Its only consumers are
  identifier resolution for `parse`, `name`, `rm` and `info`; `cmd_search` never resolves an
  identifier. Mine to own, but no native decoder this mission.
- **Agent transcript merging stays out.** `_merge_agent_messages` is parse-command-only.

### 10.4 Colored rendering is now a distinct slice

Colored `MATCHES` and `FULL` output routes message bodies through Rich's Markdown renderer
and Pygments-backed syntax highlighting. It is its own slice with its own gate, and its
parity harness is a byte diff of `ch-legacy search --color always` against
`ch search --color always` on a fixed corpus — not `tests/test_colored_rendering.py`, whose
three colored-search tests assert substrings and SGR codes at a single console width.

Sizing, from the branch that implemented it: roughly 2500 lines reimplementing both
libraries by hand, including per-language lexers and hard-coded Monokai colors. See
`branch-reconciliation.md` §5 for why this makes colored parity statistical rather than
provable, and for the recommendation that needs a decision before the slice opens.

### 10.5 Slice order revised

Insert after slice 6: **7. Colored rendering**, gated separately.

### 10.6 Terminal width: smaller than feared, and I measured it

The concern raised was that a colored port must reconcile three width behaviors. It does not.
`main`'s Rust helper and Rich already agree on every ordinary input; they diverge on exactly
two, and I ran both to find them.

`main.rs::terminal_width` (commit `a51f32c`): `COLUMNS` parsed as `usize`, else `ioctl
TIOCGWINSZ` across fds 0/1/2, else 80.
Rich `Console.size`: `os.get_terminal_size` across fds 0/1/2, then `COLUMNS` overrides it if
`str.isdigit()`, else 80.

Different order, same outcome — a valid `COLUMNS` wins in both, and the terminal is asked in
both. The two disagreements are parser disagreements:

| `COLUMNS` | Rust `parse::<usize>()` | Python `isdigit()` + `int()` | Effect |
|---|---|---|---|
| `"+80"` | `Some(80)` | rejected | Rust pins 80, Rich measures the terminal |
| `"８０"` (fullwidth) | `None` | `80` | Rust measures the terminal, Rich pins 80 |
| `"80"`, `" 80"`, `"0"`, invalid | agree | agree | none |

So the native colored renderer should **call `main`'s existing helper, not re-derive width**,
and that helper needs two lines of repair to match Rich: accept Python-`isdigit` strings,
reject a leading `+`. The branch's own helper reads `COLUMNS` only and defaults to 80, so
under zsh — which sets `COLUMNS` without exporting it — it renders at 80 columns always.
That is a real defect in the prior art, and it is the same defect `main` already fixed once.

Consequence for ownership: `terminal_width()` currently lives in `rust/main.rs`. It has to
move somewhere both the binary and the renderer can see. That is a seam with `search-runtime`,
not a decision I should take alone.

### 10.7 Case-folding offsets — noted, and not mine

Never index a string using offsets measured on its lowercased copy: `İ` grows from 2 bytes to
3 when lowercased, and `ﬀﬁﬂﬃﬄ` shrink from 3 to 2. Cumulative drift aborts the process; below
that it paints the wrong span.

My core does no case folding — matching and highlight painting belong to `query-semantics`
and `search-runtime`. Recording it here so it is not lost, and flagging it to them rather than
absorbing it.

### 10.8 Generated text — the shape where a green suite proves nothing

Verified against Python on `main`, `parsing.py:974-978`. The `<duration_ms>` block in the Pi
user-agent envelope is wrapped in `(?:...)?` — **optional**:

```
r"(?P<before_response_close>.*)\r?\n</response>"
r"(?:\r?\n<duration_ms>\r?\n.*\r?\n</duration_ms>)?"
r"\r?\n</user_agent>"
```

A native parser that requires the terminator silently drops joined Pi user-agent responses.
The prior team shipped exactly that through a full acceptance cycle, because no fixture
carried the shape.

The conservative rule around it is also real and must survive the port: one candidate wins
outright; otherwise fall to `responsePreview` matching; **if that does not resolve to exactly
one, return `None`**. Ambiguity yields nothing rather than a guess.

**Why this is more than one field.** Joined Pi agent records are one of two places where
normalization *generates visible text that the raw JSON never contained* — generated tool
names are the other. That is why the Python candidate gate carries
`_PI_USER_AGENT_EVIDENCE = b'"pi-user-agents"'` unconditionally (`commands/search.py:98`):
the cheap gate cannot reason about text that normalization invents, so it admits the file on
sight of the marker and lets confirmation decide.

This couples my scope to the gate's soundness argument in both directions. If native
normalization drops or alters generated text, the marker protects content that no longer
exists and the gate over-admits; if native normalization invents text Python does not, the
gate under-admits and hits vanish. Neither failure is visible in any current test.

**New falsifier F8:** a Pi session with a joined user-agent response whose envelope omits
`duration_ms`, asserted to survive all the way to rendered output, plus an ambiguous-candidate
case asserted to yield nothing. **Contract need:** both fixtures; neither exists today.

### 10.9 Line trimming: Python `str.strip()` is not Rust `.trim()`

`_iter_jsonl_entries` and `detect_format` both trim with Python `str.strip()`, which strips
every character where `str.isspace()` is true. Rust `str::trim` uses the Unicode `White_Space`
property. **These sets differ**, and I measured where:

| line prefix | Python `str.strip()` | Rust `.trim()` | agree? |
|---|---|---|---|
| U+001C..U+001F (FS, GS, RS, US) | strips | **does not strip** | **no** |
| U+0085 NEL, U+00A0 NBSP, U+2028 LS, U+3000 | strips | strips | yes |
| U+200B ZWSP | does not strip | does not strip | yes |

Measured: a line prefixed with U+001C decodes to 1 entry in Python and `detect_format` calls
the file `jsonl`. A naive Rust port using `.trim()` leaves the byte, the line fails to parse,
and the whole file falls to `raw`. That is a **whole-file** behavior change from one leading
control character, not a single dropped line.

This is a *different* divergence from the byte-level one `context-curator` found in the
extracted scanners (Python's four-byte JSON whitespace set versus Rust `.trim()`). Both are
real; they sit at different layers. Mine is at the `str` layer, where Python strips *more*
than Rust. Theirs is at the byte layer, where Rust strips *more* than Python. A port that
"fixes" one by copying the other's helper reintroduces the opposite bug.

**New falsifier F9:** JSONL lines prefixed with each of U+001C..U+001F, U+0085, U+00A0,
U+2028, U+3000 and U+200B must reproduce Python's decode outcome *and* Python's
`detect_format` verdict. **Contract need:** one fixture per class; none exists today.

### 10.10 Extraction rule I am adopting

From `context-curator`'s finding that the prior extraction left `find_last_jsonl_timestamp_impl`
and `scan_resolution_facets_impl` forked between `python_extension.rs` and `inventory.rs`,
with the two halves already disagreeing on trimming and on memory bounds:

**A copy that compiles is not an extraction.** Delete the original in the same change, or
prove the two byte-identical. Where a thin PyO3 wrapper must survive for the legacy routes,
the wrapper calls the native module — it does not carry its own body.

This binds my `codecs.rs` work directly. `render_message_inner_xml` is shared between
`ch parse` and native search, and the parameterized-single-renderer design is chosen
precisely so no second renderer can drift. I will not add a search-specific renderer
alongside it.

### 10.11 The colored reproduction cannot see the width defect

Measured, three ways, with `COLUMNS` unset:

| context | Rich width |
|---|---|
| piped (what a subprocess byte-diff harness sees) | **80** |
| real pty, `stty cols 120` | 120 |
| real pty, `stty cols 200` | 200 |

Rich follows the terminal. The branch's helper reads `COLUMNS` only and defaults to 80, so it
returns 80 in every one of those three contexts.

Therefore the two implementations **agree exactly at 80 and nowhere else**. A colored byte
diff performed at 80 columns — piped, or under a default-width pty — certifies the one width
at which the defect is invisible, because 80 is both implementations' fallback. It cannot
distinguish "follows the terminal" from "always returns 80".

This is the same failure mode that already cost this project once: every colored test passed a
hard-coded 44-column element because all of them pinned a single console width.

**Gate requirement:** the colored harness must drive both binaries under a pty at **at least
two widths**, neither of them 80. A single-width diff is not evidence about width, whatever
else it proves. Probe: `teammates/session-core/probes/width_tty.py`, run piped and under
`script` with `stty cols`.

### 10.12 Blast radius of the escaping repair: zero bytes on the real corpus

`search-firstmate` asked me to characterize which public `ch parse` bytes move before the
repair lands. Answer: **none**, on 5026 real sessions.

Method. Gate the corpus by raw text for all three divergent shapes, then run the true public
route over every candidate — Python renders canonical JSON, the installed `ch parse -f xml`
converts it, byte-compared against Python's own `format_to_xml`, in three flag configurations.

```
raw-text gate       508 files contain `<tag ` (over-eager shape)
                      0 files contain `<tag\t` or `<tag\n` (under-eager shapes)
differential        451 supported sessions x 3 configurations = 1353 comparisons
result              1348 identical, 0 differ
```

So the divergent shapes do not occur in real transcripts at all. The 508 raw-text hits are
inside fenced tool payloads or mid-line, never at the start of a rendered line. The repair is
therefore safe to land on the corpus, and it matters only for adversarial input — which is
exactly why it still needs the three fixtures in §3.1, and why the corpus cannot be the
evidence for it.

### 10.13 Two harness traps I walked into, both mine

Worth recording because the whole team is building byte-diff harnesses this week, and both of
these produce *confident, completely wrong* numbers rather than errors.

**Trap 1 — the CLI's trailing newline.** `ch parse` ends its output with a newline;
`format_to_xml` returns the document without one. My first run reported **1348 differ, 0
identical** — every comparison in the corpus, off by that single byte. A red result that
looked like a catastrophic parity failure was one byte of CLI framing.

**Trap 2 — `subprocess.run(..., text=True)` translates newlines.** `text=True` implies
universal newlines, so captured stdout has `\r\n` and lone `\r` rewritten to `\n`. My second
run reported that native `ch parse` normalizes carriage returns inside content across 53 real
sessions, with a clean minimal repro. It does not. My harness ate the CRs. Capture bytes and
`.decode("utf-8")` explicitly.

Trap 2 is the dangerous one for this mission specifically: **any byte-diff harness comparing
CR-bearing content through `text=True` silently agrees where the implementations differ, and
appears to differ where they agree.** It is the same shape as the 80-column blind spot, and
as round-trip fidelity read as cross-implementation parity — a measurement narrower than, or
simply other than, the claim it supports.

I caught both only because the numbers were implausible in opposite directions. A harness
bug that produced a *plausible* number would have shipped.

### 10.14 F2 characterized: `truncate_middle` has two live defects and one reachable quirk

Pinned against Python. Probe: `probes/shortening_boundaries.py`.

**The mechanism behind both defects.** `truncate_middle` ends with
`s[:first_half] + placeholder + s[-second_half:]`. When `second_half == 0`, `s[-0:]` is
`s[0:]` — **the whole string**, not the empty string. So the function returns *more* than it
was asked to keep.

`second_half == 0` exactly when `max_chars` is 4 or 6:

| `max_chars` | placeholder | result | length |
|---|---|---|---|
| 4 | `"..."` | `s[:1] + "..." + s` | input + 4 |
| 6 | `"\n...\n"` | `s[:1] + "\n...\n" + s` | input + 6 |

**Reachability: not through the public surface.** `parse_short_spec` rejects any limit below
`MIN_SHORT_MAX_CHARS = 8`, and `ShortPolicy.effective_max_chars` floors its progression at 8,
so every `truncate_middle` call from the CLI carries `max_chars >= 8`. The defects are real
and unreachable.

**Binding implementation instruction, from `contract-owner`.** These two get no fixture,
because a contract that reaches past its own public boundary stops being a statement about
behavior. Instead the contract carries the instruction directly: **reproduce `s[-0:]`
returning the whole string verbatim; do not guard it.** A port that "helpfully" returns the
empty string for `second_half == 0` diverges the moment `MIN_SHORT_MAX_CHARS` moves, and the
fixture that would catch that cannot exist until then. I am implementing it that way.

**The reachable quirk.** The passthrough test is `len(s) <= max_chars - len(placeholder)`, so
a string shorter than the limit is still truncated, and the result can be *longer* than the
input. At `--short 8`, a 6-character string becomes 8 characters. Measured at limit 10:

```
len= 5 -> untouched
len= 6 -> 'xxx\n...\nxx'   (6 code points in, 10 out)
len=11 -> 'xxx\n...\nxx'
```

This one is reachable and must be reproduced exactly.

**Code points, not bytes — confirmed across scripts.** At limit 16: Hebrew 16 code points /
27 bytes, CJK 16 / 38, astral 16 / 49, ZWJ emoji 16 / 44, combining `é` 16 / 27. The function
counts and slices code points and splits grapheme clusters freely — it cuts ZWJ sequences and
separates combining marks from their base. A Rust port indexes `char` boundaries and must not
"improve" this to graphemes or display width.

**Progression, pinned.** `ShortPolicy(128, True).effective_max_chars`: count 1 gives `[128]`,
count 2 gives `[8, 128]`, count 4 gives `[8, 48, 88, 128]`. `position=None` and
non-progressive both give the unmodified limit.

### 10.15 Open item closed: `name_aliases` is dead

I predicted `ToolUse` needs a `name_aliases` field and flagged that the branch omits it. **The
branch is right and I was wrong.** `name_aliases` is read in exactly one place,
`tool_filter.py:171`, and written nowhere in `src/`; its only appearance otherwise is that
function's own doctest. `tool.get("name_aliases", ())` always returns `()` in production.

My Rust `ToolUse` omits it. Not removing the Python read — out of charter, and it costs
nothing where it sits.

### 10.16 Timezone is a parity axis in my files, separate from the clock

`model.py:37` converts to local time with `.astimezone()`; `model.py:616` renders
`%Y-%m-%d %H:%M` from it. `codecs.rs:645` does `.with_timezone(&Local)` with the same format.

So **every `date=` attribute on every XML message is rendered in the harness's local zone.**
A differential cannot see this, because both implementations shift together. A pinned
expectation file breaks on every message the moment it is generated in one zone and verified
in another, and this corpus was generated in Asia/Jerusalem.

This is a different axis from A1's frozen clock: freezing *when* the run happens does not pin
*which zone* renders the timestamp. **New falsifier F10:** the same session rendered under two
`TZ` values must differ in exactly the `date=` attributes and nowhere else, and any pinned
expectation must declare the zone it was generated in.

### 10.17 A third instance of the two-parser split

Verified: a JSON string containing a lone surrogate, `"\ud800"`, is **accepted by stdlib
`json` and rejected by `orjson`**. Same shape as the `NaN` case in §10.1 — `detect_format`
reads with stdlib, `_iter_jsonl_entries` and `_read_first_jsonl_entry` read with orjson. So
the file is classified by one reader and decoded by another, and a line can be visible to the
classifier and invisible to the decoder.

Three known instances now: `NaN` (and the other JSON non-finites), lone surrogates, and the
`str.strip()` versus `.trim()` boundary in §10.9. A Rust port choosing one JSON parser for
both paths cannot reproduce any of them. Probe: `probes/invisible.py`.

### 10.18 Normalization form interacts with the code-point truncation

`café résumé naïve` is 17 code points / 21 bytes in NFC and 21 / 25 in NFD, rendering
identically. Because `truncate_middle` counts and slices **code points** (§10.14), the same
visible string truncates at a different place depending on its normalization form. The product
never normalizes, so whichever form the transcript carries is what gets counted. Not a defect
— but it is a fixture shape, and a port that normalizes anywhere in the pipeline diverges
invisibly.

### 10.19 F3 answered: the branch shapes exist, and three are nearly extinct

I listed "branch resolution shapes" as a contract need and admitted I had not confirmed the
corpus contains one of each. Censused now, over 347 real Claude sessions. Probe:
`probes/branch_shapes.py`.

| shape | sessions |
|---|---|
| has an off-main branch | 221 |
| a forking node | 219 |
| more than one distinct branch id | 121 |
| **no recorded `last-prompt` leaf** (longest-continuation path) | **71** |
| **truncated head — parent outside the file** | **7** |
| **compaction boundary** | **6** |
| **more than one null-parent root — rewind to first message** | **3** |

All four structural cases the docstring names do exist. Three of them are rare enough that a
random corpus sample almost certainly misses them: compaction at 6 sessions, rewind-to-first
at 3, truncated head at 7, out of 347. **That is the same shape that cost the prior team the
Pi envelope defect — the fixture corpus simply did not contain one.**

Two specific gifts from the census:

1. **One session carries the hardest combination.** `194f2192-…-7d9cad99f810.jsonl` is the
   example for compaction, compaction-plus-branch, compaction-plus-rewind-first, *and*
   rewind-first-with-a-recorded-leaf simultaneously. It exercises the era logic,
   `_origin_session_root`'s hop across `logicalParentUuid`, and the abandoned-null-root rule
   in one file.
2. **The numbering logic has a real stress case.** One session resolves to **78 distinct
   branch ids**. Ids are assigned by first appearance in file order, so this is the case that
   catches any port that numbers by traversal order instead.

Distribution of distinct branch ids per session: 126 sessions have none, 100 have one, and the
tail runs 2, 3, 4, 5, 6, 7, 9, 10, 11, 13, 15, 16, 20, 24, 25, 78.

### 10.20 Six synthesized branch fixtures, authored and verified

`contract-owner` asked me to author minimal sessions rather than copy real ones, on three
grounds I agree with: real transcripts are conversation content in a committed tree, a
78-branch session is large, and a real file pins every one of its properties at once, so a
failure cannot be attributed. Written to `branch-fixtures/`, generator at
`probes/make_branch_fixtures.py`.

| fixture | entries | branch map | reaches |
|---|---|---|---|
| `truncated-head` | 5 | `{u3:1}` | root parent outside the file |
| `compaction-boundary` | 7 | `{u3:1}` | compaction root + `logicalParentUuid` hop |
| `rewind-to-first` | 5 | `{u1:1, a1:1}` | two null-parent roots, one holds the leaf |
| `no-recorded-leaf` | 6 | `{u3:1}` | no `last-prompt`, longest continuation wins |
| `combined-eras` | 9 | `{u1:1, a1:1, u4:2}` | all of the above together |
| `numbering-order` | 13 | `{bA:1, bB:2, bC:3, bD:4}` | file-order numbering |

Each is asserted twice: the structural precondition it claims to contain, and the exact map
`_resolve_branch_map` returns. A fixture that does not reach its own logic is worse than a
missing one.

**My first `numbering-order` draft was decorative and I nearly handed it over.** I listed the
branch heads deepest-attachment-first, reasoning that this reversed the traversal order. It
does not. A depth-first walk that descends the main chain first *also* meets them
deepest-first, so file-order and traversal-order numbering produced the identical map and the
fixture could never fail against the implementation it exists to catch. Listing them
shallowest-first is what separates them.

The generator now enforces this: `discriminates()` simulates traversal-order numbering and
`numbering-order` fails generation unless the two rules disagree. Same discipline
`reviewer-profiler` applied to the width gate — a gate that cannot fail is worth nothing.

**On the count question:** four branches is enough, and count was never the variable. What
separates the two numbering rules is that the orders are exactly reversed, which four achieves
as decisively as seventy-eight. The real 78-branch session is a worse test despite being more
extreme, because its file and traversal orders happen to agree in stretches.

### 10.21 The fixtures are self-contained; one pool-order coupling removed

`contract-owner` is landing the six in a second fixture home with its own small pool, because
adding session files to the frozen corpus would move every broad-pattern expectation in it.
They asked whether any shape depends on interacting with other sessions.

**No.** `_resolve_branch_map` takes one file's entries and nothing else — no path, no pool, no
siblings. Searching the six alone changes none of their maps.

But the small pool exposed a coupling that was harmless among forty sessions.
`compaction-boundary` and `no-recorded-leaf` both ended at `10:05`. Newest-first ordering is
`sorted(..., reverse=True)`, a stable sort, so a tie keeps pool discovery order — lexical by
filename. Correct today, and silently dependent on names I happened to choose; a rename would
invert a passing ordering assertion.

Fixed by giving each session its own hour, so all six last timestamps are distinct and
ordering is a function of content rather than of filenames. Regenerated and re-verified: maps
unchanged, preconditions met, `numbering-order` still discriminates.

Same shape as the fixture that could never fail, one level up: the artifact was correct, and
what made it correct was accidental.

### 10.22 Colour downgrade: oracle built before the code, and proven able to fail

Approved to build the colour-system downgrade, with exhaustive enumeration as the gate.
Oracle-first, because the algorithm is portable and its input set is finite.

**The oracle**, at `colour-downgrade-oracle.json`, generated by
`probes/colour_downgrade_oracle.py`. 1411 rows, each carrying Rich's expected EIGHT_BIT and
STANDARD result:

- **44 palette triples** — every RGB the branch renderer can emit, extracted from
  `session_render.rs` and `search_views.rs` by regex rather than retyped, unioned with the
  Python theme. This proves today's output.
- **1367 algorithm-critical triples** — all 256 values in each channel position (the cube path
  is per-channel independent, so this is genuinely exhaustive for it), plus a dense grid across
  the saturation and lightness boundary for the grayscale branch. This proves the algorithm.

**The gate is proven able to fail.** I implemented the wrong port — a careful one reaching for
`f64::round` without a second thought — and ran it against the oracle:

```
rows where the naive half-away-from-zero port is wrong:  11
  in the palette section:                                 0
  in the algorithm-critical section:                     11
```

Examples: `(155,0,255)` expects 93 and the naive port gives 129; `(235,0,255)` expects 165
against 201; `(187,171,155)` expects 144 against 145.

**Zero of the eleven are in the palette.** A gate that enumerated only the colours the product
emits today would have passed a wrong implementation, silently, and broken on the next colour
anyone added. That is the concrete vindication of making enumeration the gate rather than a
suggestion, and it is the same shape as the width diff at 80 and the fixture that could never
fail: a green result measuring something narrower than the claim it supports.

**Remaining hazards to carry into the implementation**, both still unproven:
`rgb_to_hls` must match Python's `colorsys` branch for branch, and the STANDARD downgrade must
stay integer arithmetic — `//` and `>>` in the weighted redmean distance — or nearest-match
ties flip.

### 10.23 The colour gate had a blind spot; found by falsifying it, now closed

I said I would write wrong versions of the two remaining hazards before calling the gate
complete. Doing so found that my oracle could not see one of them at all.

`probes/falsify_colour_gate.py` implements three plausible-but-wrong ports and requires the
oracle to reject each. First run, against the 1411-row table:

| hazard | caught on | in palette |
|---|---|---|
| `f64::round` instead of round-half-to-even | 11 rows | 0 |
| HSV saturation instead of the HLS branch | 99 rows | 5 |
| **float arithmetic instead of `//` and `>>`** | **0 rows** | — |

The third was invisible. I did not assume it was therefore harmless — I searched for it, and
it is real: on a stride-3 grid of 636,056 triples the integer and float versions disagree 56
times, roughly one in eleven thousand. When they disagree they pick an **entirely different
colour**, not an adjacent one: `(9,129,69)` resolves to 8 under Rich's integer distance and 2
under a float port.

Those rows are invisible to the palette *and* to the cube-path grid, because the STANDARD
downgrade is a nearest-match over 16 colours and nothing else in the table stresses its
argmin. The generator now derives them explicitly.

Oracle is 1459 rows. Re-run: all three hazards discriminated, and `falsify_colour_gate.py`
exits non-zero if any ever stops being. The gate now tests itself.

### 10.24 Behaviours in my surface that must NOT be repaired

From `context-curator`'s sweep. Each is a case where a native implementation that is *better*
diverges, and `contract-owner` is pinning them with fixtures that say so in a comment.

1. **`elide_to_width` counts code points, not display columns.** `你好你好你好你好` at a
   budget of 8 comes back unchanged and occupies 16 columns. A port measuring display width
   elides to four and fits — correctly, and wrongly. Four call sites in `commands/search.py`
   across list and panel views, plus `formatting.py:152`.
2. **`truncate_middle` counts code points, so shortening is normalization-sensitive.** 400
   visible characters survive intact as NFC; the same 400 as NFD come back as 253. Reaches
   `model.py` directly and through `shorten_data` at six more sites, so it surfaces in every
   `--short` mode. Related: §10.14, §10.18.
3. **`collapse_home` matches a string prefix, not a path boundary.** `/Users/giladbarneaX/dev`
   renders as `~X/dev`. A port comparing path components is right and diverges.

**The codebase counts in three different units** — code points here, UTF-16 code units in the
Pi `responsePreview` truncation (§10.8), display columns nowhere. Any port that unifies them
changes behaviour. I am not unifying them.

### 10.25 Colour is resolved per stream, not per process — measured

`search-runtime` cautioned that stdout and stderr resolve colour independently. Verified, and
the source is sharper than the caution: there are **four** consoles in `console.py`, not two.

| console | stream | theme | forced? |
|---|---|---|---|
| `_console` | stdout | `APP_THEME` | `force_terminal=force_color`, **only when truthy** |
| `_error_console` | stderr | none | never |
| `_warning_console` | stderr | none | never |
| `_hint_console` | stderr | `APP_THEME` | never |

Measured end to end, stdout redirected to a file and stderr on a pty:

```
stderr: \x1b[38;2;135;140;146mNo sessions match \x1b[0m\x1b[32m"…"\x1b[0m…
```

Full truecolor on stderr while stdout is a plain file. **So a native renderer cannot take one
process-wide capability.** It needs the stdout capability for the render path and a separately
resolved stderr capability for errors, warnings and hints.

Two further source facts: `init_module_console` passes `force_terminal` **only when
`force_color` is truthy**, so `--color never` never forces the Console off — suppression
happens above, in `ConversationFlags`. And the three stderr consoles receive no force
argument at all, so the `--color` flag does not reach them.

**Not claimed:** what `--color never|always` does to stderr colour in practice. My probe
returned empty output and I did not resolve why, so I am recording the source reading and not
the behaviour. That one needs a working probe before anyone relies on it.

My first attempt at this measurement was also wrong — I redirected *both* streams to files, so
neither was a tty, saw no colour anywhere, and nearly concluded the caution did not reproduce.

### 10.26 `NO_COLOR` is not an absent colour system

I proposed collapsing not-a-tty, `NO_COLOR` and `TERM=dumb` into one "no colour" state.
`search-runtime` measured it and I was wrong:

```
truecolor + NO_COLOR=1   ->  \x1b[1msample\x1b[0m      bold kept, colour stripped
TERM=dumb                ->  sample                    no SGR at all
```

`NO_COLOR` strips colour and **keeps attributes**; an absent colour system emits nothing. A
renderer treating them alike drops the bold from every styled span of every `NO_COLOR`
invocation. I consume their two-field shape — `color_system: Option<ColorSystem>` plus
`no_color: bool` — rather than the single value I asked for.

Placement settled: `rust/color.rs`, mine, importing `terminal::ColorSystem`.

## 11. B2 slice 1 — the renderer repair. Done, pending a coordinated suite run.

`rust/codecs.rs`, 32 insertions and 29 deletions. Oracle `8cb4c5f`.

**The root cause was a duplicated grammar, so the repair is a deletion.** `codecs.rs`
already contained `inner_opening_regex()` —
`(?m)^<(?:thinking|tool-input|tool-output|subagent-task)(?:\s+[\w-]+="[^"]*")*>` — which is
Python's pattern character for character. It was used for parsing XML back in. The encoding
side used `has_inner_opening_tag`, a separate hand-rolled per-line prefix check, and only one
of the two matched Python.

So the fix is not new logic: `encode_xml_text` now calls the regex the file already had,
`has_inner_opening_tag` is deleted, and `INNER_TAGS` goes with it — the tag list now lives in
exactly one place. One authority instead of two, which is what made them able to drift.

Also landed the convergent seam: `render_message_content` is now
`pub fn render_message_inner_xml(message, encode_transport)`, threaded through the tool render
path. Same name and signature the branch reached independently, rebased onto `main` rather
than merged.

**Proof.**

| check | result |
|---|---|
| `cargo build --release --no-default-features` | clean, no warnings |
| `cargo test --release` | 1 unit + 3 doctests pass |
| escaping differential, 11 shapes | **6/11 before, 11/11 after** |
| corpus regression, 451 sessions x 3 configurations | 1348 identical, **0 differ** |

The differential is a gate that can fail: run against the unrepaired installed binary it
reports 6/11 and exits non-zero. Probe: `probes/escaping_parity.py`, `CH=` selects the binary.

Binary identity recorded either side of the corpus run: `12ec81d881825767`, unchanged.

**Built into a private `CARGO_TARGET_DIR`, not `target/release`.** That directory is contended
and installing over `~/.local/bin/ch` would change the binary other teammates are currently
measuring against. The full suite needs an installed build, so that run has to be scheduled
rather than taken unilaterally.

### 11.1 Gate self-audit, prompted by `query-semantics`

Their predicate gate had copied the engine's predicate into itself, so it graded a
transcription and could never fail — while returning a correct, quotable number.

Audited mine. The colour oracle's expected values come from `Color.downgrade` itself; I
spot-checked 200 rows against a fresh Rich call, zero mismatches, so the grading is against
Rich rather than my reading of Rich.

**One real weakness, stated rather than dismissed:** `standard_critical()` *does* transcribe
Rich's distance function, to select which triples to include. A wrong transcription would
choose rows that fail to discriminate — it could not produce wrong expected values, but it
could silently produce a weaker gate. That loop is closed empirically rather than structurally:
`falsify_colour_gate.py` reports 48 rows catching the float port, so the selection demonstrably
worked. If that count ever drops to zero the gate fails the build.

## 12. B2 slice 2a — `rust/shortening.rs`. Written and proved.

New file, plus one line in `rust/lib.rs`. Ports `shortening.py` and `truncate_middle` /
`shorten_data` from `utils.py`. Oracle `8cb4c5f`.

**Proof.**

| check | result |
|---|---|
| `cargo build --release --no-default-features` (the shipping config) | green |
| module unit tests | 6/6 pass |
| **differential against Python, 14 samples × 22 limits** | **308 cases, 0 mismatches** |

The corpus is adversarial by construction: NFC against NFD of the same visible text, ZWJ
family emoji, astral plane, Hebrew, CJK, control bytes, and every limit from 0 to 11 so both
`s[-0:]` defect branches are covered.

**The differential can fail.** Two wrong ports, built and run:

| mutation | mismatches |
|---|---|
| guard `second_half == 0` — the "helpful" fix | **24** |
| measure the passthrough test in bytes | **4** |

**Read these two numbers as different kinds of evidence, not as one scale.** 24 is
differential coverage: the gate saw a wrong answer. 4 is not — byte-length only reaches the
passthrough comparison and never the slicing, so the mutation is largely inert, and the
mutation that would really hurt (slicing at byte offsets) is caught by a panic rather than by
the gate. A mutation caught by the compiler is caught, but not by this instrument, and the two
must not be quoted as the same thing.

Honest note on the second: 4 is thin, and the weakness is my mutation rather than the gate.
Byte-length only reaches the passthrough comparison, not the slicing, so it is mostly inert.
The mutation that would really hurt — slicing by byte offset — panics on a non-boundary index
rather than diverging, which is the good failure but a different one. Worth a sharper mutation
when this moves into the crate's own test target.

**Preserved deliberately, with tests naming why:** code points not columns; `s[-0:]` returning
the whole string, so `truncate_middle(s, 4)` is *longer* than its input; and the passthrough
test subtracting the placeholder first, so a 6-character string comes back 10 characters at
`--short 8`.

**One divergence recorded rather than reproduced.** Python guards its limits with
`str.isdigit()` and then calls `int()`. Those disagree on digits without a decimal value —
`"²".isdigit()` is true while `int("²")` raises — so Python raises an uncaught `ValueError`
instead of its own message. Unreachable through a valid spec. My `parse_python_digits`
accepts Unicode decimal digits (`"５００"` → 500, matching Python) and rejects the rest.
Contract gap, not a fixture.

**Blocked from the crate's own test target:** `cargo test` does not compile, with 8 errors in
`search_query.rs` test code belonging to `query-semantics`. `cargo check` skips test targets,
so lib and binary are green while the test target is red — three configurations, not two.
Verified in a standalone harness meanwhile, with the one unrelated helper stubbed rather than
transcribed.

### 12.1 The red doctest was my expectation, not the implementation

Ran it in-crate the moment `cargo test` was unblocked. It genuinely failed, so it was not
the harness:

```
left:  "abc\n...\nij"   (my implementation)
right: "abc\n...\nab"   (my doctest expectation)
```

Python settles it: `truncate_middle("abcdefghij", 10)` is `'abc\n...\nij'`. At limit 10 the
placeholder takes 5, leaving 5 — three characters of head and two of **tail**. I had written
the first two characters where the last two belong. Candidate 1 of the three in `state.md`,
and the implementation was never wrong.

**Two things worth keeping from a one-character typo.**

The 308-case differential passed the whole time. The generated oracle was right and my
hand-written expectation was wrong — which is the argument for generating expectations rather
than typing them, arriving from the direction where it costs least.

And the unit test next to it **could not have caught this**. It asserted
`truncate_middle("xxxxxx", 10) == "xxx\n...\nxx"` — a uniform sample, where head and tail are
indistinguishable, so swapping them passes. I have changed it to `"abcdef"` and added
`the_tail_comes_from_the_end_of_the_string`. A sample whose symmetry hides the property under
test is the same failure as a gate that cannot fail, one level down.

Standalone verification after the fix: 7/7 unit tests, 308/308 differential.

**Blocked again from in-crate runs**, by a new error in `search_query.rs` —
`Node::NonCapturing` not covered in a match, in `query-semantics`' file. Lib and lib-test both
red; my modules verified standalone meanwhile.

## 13. B2 slice 2b — `tool_filter.rs` and `visibility.rs`. Landed and proved.

Three modules now declared in `lib.rs`: `shortening`, `tool_filter`, `visibility`.
`cargo build --release --no-default-features` green; **24 unit tests and 7 doctests pass
in-crate**, not in a standalone copy.

### 13.1 `tool_filter.rs`

Ports `tool_filter.py`. Compiled first time with 16/17 tests passing; the one failure was
my expectation again, not the code (§13.3).

**Differential: 2006 generated specs, 0 mismatches** — 1362 accepted, 644 rejected, with
every field compared, so both the accept/reject decision and the parsed values agree.
Specs are generated combinatorially from names × modifiers × short forms × trailing and
repeated separators, because hand-written expectations for this grammar have now been
wrong twice.

**The differential can fail.** Three mutations, built and run:

| mutation | mismatches |
|---|---|
| remove the short-modifier lookahead | 162 |
| let a bare token always overwrite the name | 6 |
| default `short_progressive` to false | 504 |

### 13.2 `visibility.rs`

`MessageSelection`, `ConversationFlags`, `SearchOutputMode`, `ParseOutputMode`. Landed
ahead of the rest of the visibility layer because `search-runtime` traced these two types
as gating three packages — their argument grammar, the engine, and the views.

**One Python quirk reproduced rather than fixed.** `color` is compared against the strings
`"always"` and `"auto"`, so a **bool** `color=True` matches neither and resolves colour
**off** — while still setting `metadata_color` **on**. `ConversationFlags(color=True)` is
therefore `color=False, metadata_color=True`. There is a test named for it.

### 13.3 The tool-spec expectation I got wrong

I asserted `parse_tool_spec("Bash:s=p:128")` yields a 128-character progressive policy.
**Python raises.** The lookahead in `_tool_short_value` joins the next token when both look
like short components, producing `"p:128"`, and `parse_short_spec` then rejects the colon
form. So `s=p:128`, `s=8:p` and `s=8:` are all errors; the valid spelling is `s=p=128`.

The lookahead exists to name the whole value in the error message, not to accept it —
which is not what its shape suggests, and is exactly why this grammar needed generated
expectations rather than my reading of it.

**Second hand-written expectation wrong in an hour, both caught by running the oracle.**
The pattern is consistent enough to state plainly: for anything with a parser in it, my
intuition about the expected value is not evidence. Generate it.

### 13.4 Codex all-scaffolding sessions — the case to write the decoder against

Found by `reviewer-profiler` over a 695-file corpus: the native route returns **563** ids for
`search .` where Python returns **560**. Three Codex sessions, one mechanism.

They contain **no human-written content at all** — a `developer`-role permissions block, an
AGENTS.md instruction blob, an `<environment_context>` element, and in one case only a
`<turn_aborted>` notice. Python hides every part: `developer` is neither `user` nor
`assistant` so it is never visible, and the user-role text is removed by the preamble and
hidden-block filters. The oracle therefore concludes the session has nothing to show and
excludes it. A decoder that is *merely more permissive* surfaces empty abandoned sessions as
search results.

**This is the shape my differentials cannot reach.** A generated corpus explores what a
grammar can express; this is a boring accident real usage produces constantly, and no one
writes it as a fixture because it is not interesting. The 173-case manifest contains no
all-preamble Codex session for exactly that reason.

**It also proves the day-one risk concretely:** rendered visibility *is* search truth, so a
decode that is more permissive than Python changes which sessions match without changing any
single message's bytes. Nothing at the message level would show the divergence.

Write the Codex decoder against these three sessions. `contract-owner` is adding them to the
contract.

## 14. `session`: Claude branch resolution. Landed and proved.

**Differential: 355 sessions, 0 mismatches** — 7 synthesized fixtures plus every one of
the 347 real Claude sessions, 227 of which carry at least one branch. Probe:
`probes/branch_map_differential.py`, driver built against the real crate rather than a
copy.

### 14.1 A real-corpus defect the fixtures could not have found

First run: 354 compared, **1 mismatch** — and it was `194f2192`, the session my census
had already identified as carrying the hardest combination.

Cause: Python builds `nodes` as a dict comprehension and then builds the graph from
**`nodes`**, not from the entries. A repeated uuid therefore contributes its edges once.
I had built `children`, `parent` and `all_roots` from the entries, so a duplicate
double-counted. That file has 2,919 entries with uuids and 2,917 distinct ones — two
duplicates, enough to move the whole branch map.

No synthesized fixture would have contained this. It is the same class as the
all-scaffolding Codex sessions: a boring accident real usage produces, which nobody
writes down because it is not interesting. Now built from an `IndexMap` that reproduces
Python's dict semantics exactly — first-seen key position, last value wins.

### 14.2 The gate had a blind spot, and my first attempt to close it silently failed

Three mutations against the differential:

| mutation | mismatches |
|---|---|
| build the graph from entries (the duplicate-uuid bug) | 1 |
| treat compaction roots as ordinary roots | 8 |
| **tie-break to the last maximal child instead of the first** | **0** |

The third was invisible. Python's `max` keeps the **first** maximal element and Rust's
`max_by_key` keeps the **last**, so an equal-depth fork resolves differently — and
nothing in 347 real sessions produces a tie where the choice is observable.

I added an `equal-depth-fork` fixture. **My first attempt silently did nothing**: the
insertion matched a comment marker that did not exist in the file, and my script printed
success regardless. The differential still said "6 fixtures" and the mutation still
scored 0 — which is what caught it. The edit now asserts its anchor and asserts the
result is present in the written file.

With the fixture: 355 sessions, 0 mismatches clean, and the tie mutation is caught.

**Two lessons, both mine.** A script that reports success without checking its own effect
is the same defect as a gate that cannot fail. And the count in the differential's own
output — "6 fixtures" where I expected 7 — is what made the no-op visible, which is an
argument for gates printing what they covered rather than only whether they passed.

## 15. F1 passed for Claude: the whole route, 2436 cases, zero mismatches

Decode, branch resolution, visibility, shortening and the semantic inner-XML render,
compared as the one string search matches against — **every real Claude session (348) in
7 flag configurations, zero mismatches.** Probe: `probes/claude_render_differential.py`.

Configurations: bare, with-tools, tools-and-agents, thinking, branches, shortened
(`--short 120`), progressive (`--short p=128`).

### 15.1 The one product defect it found

Python resolves a tool result's `name` through the tool-id map **at render time**, inside
`tool_to_parts(tool, id_map)`. My renderer takes only a `Message`, so results rendered as
`<tool-output id="01Fr">` where Python emits `<tool-output name="Bash" id="01Fr">`. 124 of
280 cases in the first sample.

Fixed by resolving the name during the visibility projection, where the id map is already
in hand. That keeps the renderer taking only a `Message` and matches Python's rule
exactly: the lookup happens **only when the result carries no `name` key at all** — a
present-but-empty name stays empty.

### 15.2 Three instrument failures in a row, all mine

The product was right and my harness was wrong, three times, before this run was
trustworthy.

1. **Digest on one side only.** I switched the driver to emit digests and left Python
   emitting raw text. 2386 "mismatches", every one a string against a hash.
2. **No row-count guard.** The driver returned fewer rows than there were cases, so `zip`
   silently misaligned every later comparison. Read as 36 product defects. The probe now
   refuses to compare when the counts differ, and says so.
3. **Live files.** Several sessions in the corpus belong to agents working *right now*.
   The driver read each file and Python read it again moments later, and it had grown in
   between. That produced message-count differences that were the clock's, not the code's.
   The probe now snapshots every session first — and passes the *original* path for
   provider classification, since Python classifies by location, while both sides read the
   *snapshot* bytes.

Every one produced a confident, plausible number. The second is the sharpest: 36 mismatches
concentrated in a few sessions looked exactly like a real decode defect.

**The corpus being alive is worth stating as a property, not a nuisance.** Any differential
over this project's own session directory is reading files under active write, so a
snapshot is a correctness requirement rather than a tidiness one.

## 16. Converting live differentials into durable tables

At cutover the Python authority is deleted and every live differential stops being
runnable. Stored tables are the durable tier. The conversion is cheap **only if the table
is a recording of a passing live run rather than a second artifact**.

**The pattern, implemented as a reference in `probes/tool_spec_differential.py`:** add
`--emit-table <path>`. It refuses to emit from a run with mismatches, then writes the same
`(input, expected)` pairs the run just compared, stamped with the oracle revision and the
generator's name. Verified: 2006 cases emitted from a green run.

Three properties that make this the right shape:

1. **The table can never disagree with the differential**, because the differential
   produces it. Two hand-maintained artifacts drift; one generated from the other cannot.
2. **Regeneration is free**, so a moved oracle is a re-run rather than a re-derivation.
   That is what makes the stamping discipline enforceable instead of aspirational.
3. **It refuses to record a failing run**, so a table can only ever describe a state that
   was actually green.

**Answer to `reviewer-profiler`'s question — both, in this order.** A live differential
against `resolve_tool_visibility` should exist *and* their 7315-case table should be
regenerated from it before cutover. Not because the table is wrong, but because a table
generated once can only fail on the cases someone chose; a live differential explores new
input every run and then *emits* the table as its residue. Their artifact does not get
replaced — it gets a generator, which is the thing it currently lacks.

**Remaining work for a successor:** the same `--emit-table` mode belongs on the other three
probes — `shortening_differential.py`, `branch_map_differential.py`,
`claude_render_differential.py`. Each is the same dozen lines. None is done.

### 16.1 Two of the four differentials cannot become tables at all

`reviewer-profiler` is taking the `--emit-table` work across all four probes. Two of them
**must not** get the mechanical treatment.

`branch_map_differential` and `claude_render_differential` are keyed by **file path**, over
the user's live private sessions. A stored table from either is broken three ways: it is
not portable, because the expected values derive from content that exists only on this
machine; it is not stable, because those sessions are under active write; and it would
**embed private conversation content** into a committed `tests/` tree.

What converts: the **seven synthesized branch fixtures**, which are checked-in content
authored to be portable. What does not: the 347-session and 2436-case real-corpus results.

Those two are **point-in-time proofs, not durable gates.** The right treatment before
cutover is to run them once more, record the result with the corpus identity and the date,
and state in the change log that this coverage was live-only and ends with the Python
authority. Emitting a table of rendered user sessions to preserve a number would be worse
than losing the number.

`shortening_differential` is genuinely mechanical — inputs are authored pairs, no paths, no
private data.

### 16.2 The declared/undeclared ratchet

From `reviewer-profiler`, accepted without reservation. `--emit-table` refusing on *any*
mismatch is right for undeclared divergences and wrong for **declared** ones — this mission
has deliberately ruled several, including the broken-pipe traceback and the ambient-input
gaps. A table that refuses on all of them cannot record the expectations that most need
pinning, and silently narrows to the uncontested cases while looking complete.

Three clauses: refuse on an undeclared mismatch; allow a declared one carrying its reason;
**and report a declaration that no longer diverges**, so it surfaces as stale rather than
permanently excusing a mismatch that stopped happening.

## 17. Pi decode. Landed and proved — 24,367 cases, zero mismatches

Every Pi entry type Python's adapter handles: `message` (user, assistant and toolResult,
including inline-skill expansion), `compaction`, `custom` (with the user-agent and
subagent-record specialisations), and `custom_message`. Nothing else, exactly as Python
ignores it.

**Full corpus: 3,481 Pi sessions × 7 flag configurations = 24,367 cases, 0 mismatches.**

### 17.1 The corpus cannot see the prior team's defect

`require_duration_ms` — reintroducing the exact defect the previous native port shipped,
an unconditional `<duration_ms>` terminator where Python's grammar makes it optional —
**caught zero mismatches** against a 400-session sample.

So I measured the corpus rather than assuming: **477 joined user-agent envelopes exist
across every Pi session, and all 477 carry `<duration_ms>`. Not one omits it.**

That is why the defect survived a green suite and an independent review last time. It is
not that the fixtures were careless — the shape does not occur in real usage at all. All
24,367 of my green cases are equally blind to it.

Two synthesized fixtures now close it, in `pi-fixtures/`: the envelope without the
terminator, and the same envelope with it as a control. The generator asserts Python
itself yields the response from each, so a malformed fixture cannot masquerade as a
passing one.

**With the fixtures included, the mutation is caught on 7 cases.** Clean run stays at 0.

| mutation | before fixtures | after |
|---|---|---|
| require `<duration_ms>` | **0** | **7** |
| never split inline skills | 546 | 546 |

### 17.2 The instrument lesson, third instance

My first attempt at these mutations ran them through shell string substitution, and the
escape sequences were mangled before they reached the file. The anchor assertions caught
it — but the surrounding script still printed `mismatches: 0` for both, which reads
exactly like a passing falsification. A mutation that was never applied and a mutation
that was caught by nothing look identical in the output.

Rewritten as a Python script that reports **ANCHOR MISSING — mutation not applied, result
meaningless** rather than a number. A falsification harness must distinguish "the gate saw
nothing" from "the mutation never happened".

### 10.27 The colour oracle was blind to half its own hazard

Found by `views-and-colour`, who re-derived the table before trusting it rather than
re-stamping it. Verified independently here before accepting.

**Rich rounds in two places in the truecolor→EIGHT_BIT downgrade, and my generator only
derived rows for one.** The cube path disagrees at channel bytes 155 and 235 — 11 rows,
which they reproduced exactly. The grayscale path rounds `l * 25.0`, which is
`(max + min) * 5 / 102`, so a tie needs `max + min` in {51, 153, 255, 357, 459}. Measured:
Python and Rust actually disagree only at **51, 255 and 459** — at 153 and 357 the
nearest-even and away-from-zero answers coincide. **2,358 real triples sit on a
disagreeing tie inside the grayscale branch, and the oracle held 391 grayscale rows and
zero of them.**

**The consequence is the sharp part.** The gate caught the rounding hazard on 11 cube
rows, so it was green-adjacent and looked adequate — and would have **stopped catching the
hazard entirely the moment someone repaired the cube path**, which is the exact next move a
red gate invites. A repaired cube, a green oracle, and a live grayscale defect.

Fixed: `grayscale_tie_critical()` derives the rows explicitly, the way `standard_critical()`
already derived the argmin rows. Oracle is 1499 rows. The rounding hazard now catches 51
rather than 11, and the **partial repair** — cube fixed, grayscale still wrong — is caught
on 40 rows, so the gate survives the move that would have defeated it.

**This is my own §10.22 rule landing on my own artifact.** Exhaustive is always exhaustive
over a parameterization. The cube path is per-channel independent, so all 256 values per
position is genuinely exhaustive for it. The grayscale branch is joint in saturation and
lightness — I said exactly that and used a dense grid across the boundary. **The grid was
the parameterization, and it missed.** A dense sample of a joint space is not a derivation
from its failure mode, and I had already written down why that matters.

**One correction they paid for and passed on.** Rich 14.3.3's cube path is
`c/95 if c < 95 else 1 + (c-95)/40`, not `round(component * 5.0)`. The older form is what
most references still show, and their first reimplementation failed its own control on 20
of 44 palette rows because of it. Anything on this mission carrying the `* 5.0` reading is
wrong.

### 17.3 My Codex named case had the wrong mechanism

`engine-and-codex` measured what I had inferred. The six files I named as the
all-scaffolding case **never reach `parse_codex`**: their first line has no `type` key, so
`detect_format` returns `raw`. Verified here — keys are `id, timestamp, instructions, git`.

True split of the 44 excluded Codex sessions: **8 raw-format** (every large one, excluded
by format dispatch) and **36 jsonl-format** (genuinely decoded and filtered, all 2-4
entries). A permissive decoder cannot surface the 8 and would wrongly surface the 36.

**Their sharper finding:** `parse_raw_cli_transcript` is a no-op across the entire corpus,
because a genuine `> ` / `... ` transcript exists nowhere in the pool. Second instance of
the 477-of-477 shape — zero occurrences, so no corpus can grade it. It is **unported**;
`SessionFormat::Raw` has no parser behind it. Recorded as a gap, not a decision.

**And a correction back to them, which matters more than my error.** They asked whether
`select_provider` returning `Err` should map to Claude, believing Python falls back. It
does not — `_select_jsonl_session_adapter` **raises**, and the Claude adapter has
`matches_first_entry=None` so content matching can never select it. Verified both ways.
Mapping the error to Claude would decode files Python refuses, surfacing sessions Python
excludes. The `Err` is deliberate.

### 14.3 The branch driver was lost, and is rebuilt in the tree

`reviewer-profiler` audited the instruments and found `branch_map_differential.py` had
become unrunnable: nothing on disk produced a branch map. **They were right, and the cause
was mine** — I repurposed the crate that produced it into the render driver, overwriting
its `main.rs`. The 355-case result was correct and unreproducible at the same time, and
had been for hours without anyone noticing, including me.

Rebuilt at `probes/drivers/branchmap/`, in the tree rather than a scratchpad, and
**re-run: 360 sessions, 227 with branches, 0 mismatches.**

Rebuilt by me rather than by a reader, on `search-firstmate`'s ruling: reconstructing
another person's driver from their notes imports the reconstructor's assumptions into the
number, producing a new measurement wearing the old one's identity.

**The count moved from 355 to 360 between the two runs.** Nothing regressed — the Claude
corpus grows while the team works. That is the live-corpus property once more, and it
means these counts are only meaningful with the date they were taken.

**Standing rule L1, from this:** a differential is convertible only while its oracle *and*
its driver both exist, and the driver dies at session exit. Every driver a gate depends on
belongs in the tree.
