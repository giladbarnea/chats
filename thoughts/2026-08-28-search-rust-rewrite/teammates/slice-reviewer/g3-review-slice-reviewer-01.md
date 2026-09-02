---
date: 2026-08-28
author: slice-reviewer
role: G3 structural review, pass three (third reviewer seat, L49)
oracle_revision: 8cb4c5f
oracle_route_digest: NOT RE-DERIVED — see the coverage limit below
scope_as_narrowed: color.rs, python_io.rs, and the decode logic, ordering and error paths of session.rs and codex.rs
verdict: sixteen divergences in four classes — one live today, one with a measured blast radius on a scheduled refactor, two Package-B criteria not yet implemented; plus one measurement correction that changes a premise of L47
status: scope complete except the codex.rs script parser, which is named in the coverage table
---

# G3 structural review 03 — decode paths, colour, and the Python I/O seam

## Coverage limit, stated first

The named scope is covered **except the `codex.rs` script parser below line 500**,
which is stated in the table rather than left to be inferred. 22ae: a limitation
below a result is not quotable and the result is.

| File | Depth reached |
| --- | --- |
| `rust/python_io.rs` | **Read in full.** 81 lines. |
| `rust/color.rs` | **Read in full.** 482 lines, checked line by line against `rich/color.py`. |
| `rust/session.rs` | **Read to line ~1180 of 1692.** Format detection, entry decoding, provider selection, facets, Claude branch resolution and the whole Claude decoder. |
| `rust/session.rs` — Pi decoding | **Read in full, 2026-08-29.** Lines ~1176–1692. Inline skills, user-agent envelopes, compaction, subagent records, `parse_pi`. |
| `rust/codex.rs` | **Decoder, ordering and error paths read, 2026-08-29** — lines 40–500, post-edit and post-engine-landing. The script parser below line 500 was re-differentialled at 0 mismatches after its `.trim()` fixes and I did **not** re-read it. |
| `rust/search_output.rs` | **Read, 2026-08-29** — the gate half, `rule`, `truncate_to_cells`, `display_session_id`, `metadata_block`, `PlainSink::render`, `displayed_messages` and both sinks. |
| `rust/search_engine.rs` outside the scan loop | **Read, 2026-08-29** — `Outcome`, `exit_status`, `wants_no_results_hint`, `stream_search`, `flush`. The `HitSink` trait's own tests are not read. |
| `rust/search_run.rs` | **Read as it stood on 2026-08-29** — the pool assembly, the empty-pool exit and the hint decision. `ColouredListSink` was being wired into it, so the sink construction has moved since. |
| `rust/search/plan.rs`, `rust/cells.rs` | Read in full **before** the scope narrowing removed them. One `plan.rs` finding is recorded below for `context-curator` rather than discarded. `cells.rs` produced nothing and is not reported. |

**Three further limits on what any verdict here means.**

1. **I ran no Rust.** Every verdict is from reading the Rust against the Python
   at `8cb4c5f`, plus execution of the **Python** half. Nothing here is confirmed
   against the built artifact. Where the Rust half rests on a library
   specification rather than on execution, the finding says so.
2. **I did not re-derive the oracle route digest**, so this document carries none
   rather than an inherited one — 22ah, a restamp alone upgrades "unknown" to
   "verified". The Python measurements below were taken against the working tree
   as of 2026-08-28 with `src/chats/` modified; they are reads of behaviour that
   the two commits on this desk do not touch, but that is an argument, not a proof.
3. **The shape I searched for.** L43: a stated negative is only as strong as the
   shape searched for. I searched for **three shapes**: a Python built-in whose
   Rust counterpart has a different character class (`strip`/`trim`,
   `splitlines`/`lines`, `re \s`/`regex \s`, `expandtabs`); a Python expression
   that tests **truthiness or key presence** where the Rust tests type and
   emptiness; and a Python regex feature the `regex` crate lacks. I did **not**
   systematically search for arithmetic errors, ordering errors, or missing
   entry-type arms. A negative from me does not cover those.

---

## The correction, and it is the one to act on

`session-core`'s C0 audit reported, and L47 quotes:

    files scanned:                              5046
    files containing U+001C-001F anywhere:         0
    string values with a C0 separator at an edge:  0

**The first number is over raw file bytes.** These characters reach a transcript
as JSON escapes — `` — so they are not raw bytes in the file and a byte
scan cannot see them. Over **decoded string values** the same pool carries:

| character | occurrences | files |
| --- | ---: | ---: |
| U+000D | 131,120 | 445 |
| U+000C | 9,367 | 32 |
| U+000B | 8,870 | 27 |
| U+001E | 8,344 | 22 |
| U+001C | 8,044 | 27 |
| U+001D | 7,552 | 26 |
| U+0085 | 63 | 8 |
| U+2028 | 29 | 8 |
| U+2029 | 7 | 2 |

**I dumped the instances before writing this down** — 22c, and it changes the
reading twice.

- Most are **binary tool output**: Mach-O headers, `__PAGEZERO`, protocol traces,
  a Finnish JSON-schema dump. Ordinary usage, unrelated to this mission.
- Three of the files carrying the *rarer* characters are **this mission's own
  transcripts**, one of them a fuzz-corpus definition listing
  `["\x1c", "\x1d", "\x1e", "\x1f", "\xa0", " ", "　", "\x85", "​"]`
  and another a discussion of `splitlines`. A live corpus that grows while the
  team works now contains the team's own probe characters. That is a new instance
  of the live-corpus property behind 22al and L1, arriving as **contamination**
  rather than as drift.

**Their ruling stands and only the premise sentence is wrong.** I re-ran the
measurement the strip ruling actually depends on — a separator at a string
**edge** — and it reproduces at **0 across every string value in the pool**,
exactly as they reported. `.strip()` sites remain corpus-invisible. What the
"anywhere" number changes is a different half, which nobody had looked at, and
which is F4 below.

---

## F1 — `python_io::read_text` does not reproduce Python's universal-newline translation

**The severity ranking is mine and this is first**, because it is one root cause,
one fix site, and two consequences, one of which lands in the module the real
corpus provably cannot grade.

`session_scan.py:32` is `session_file.read_text(encoding="utf-8")`. That is
Python **text mode**, so `\r\n` and lone `\r` both become `\n` before
`detect_format` or `decode_jsonl_entries` ever see the content.
`rust/python_io.rs:26` is `std::fs::read` plus a UTF-8 decode and no translation,
and `search_confirm.rs:247` feeds its result straight into
`session::decode_entries`, which splits on `'\n'` alone.

**Executed, both sides.** A file holding

    {"type":"user","cwd":"/a"}\r{"type":"summary","summary":"FINDME"}\n

gives Python `[{'type': 'user', 'cwd': '/a'}, {'type': 'summary', 'summary': 'FINDME'}]`
and the native route **zero entries**, because the whole file is one unparseable
line. The summary is a search facet, so the session stops matching `FINDME`.

**CRLF alone is safe on the JSONL path** — `python_strip` removes the trailing
`\r` before the JSON parse — **and is not safe on the raw path.**
`parse_raw_cli_transcript` joins its accumulated lines with `"\n"`, so under CRLF
the native route keeps a trailing `\r` on **every line of every message** where
Python has none. `raw_transcript.rs`'s own docstring records that the real corpus
cannot grade that module: nine files take the branch and every one produces zero
messages.

**Corpus:** **0** raw CR bytes in 5,047 files. Real divergence, invisible to
every differential, same class as the strip divergence.

**Worth stating plainly:** the module is named for `Path.read_text` and its
docstring enumerates "exactly two ways it fails". The newline translation is what
that function does when it **succeeds**, and enumerating the failures is what
makes the omission read as complete.

**What is correct in that module, checked rather than assumed.** `decode_utf8`
reproduces CPython's `UnicodeDecodeError` text over 20 shapes — invalid start
byte, invalid continuation byte, truncated one/two/three-byte sequences,
overlongs, surrogates, out-of-range leads, and stray continuations — including
the classification boundary at 0xC2–0xF4. I expected the positions to be
chunk-relative on a file larger than one text-mode read and they are **absolute**;
a 20,001-byte file reports position 20000. `python_io_error` reproduces
`OSError.__str__` including Python's `repr` quoting of the path.

---

## F2 — the lazy/eager screen drift guard in `plan.rs` cannot fail

*Recorded for `context-curator`, who now owns this file. Found before the scope
narrowing arrived.*

`plan.rs` carries two screens: `screen(&PoolFilter)` and
`lazy_screen(&SearchPoolFilter)`. They must not drift, and
`the_lazy_screen_agrees_with_the_eager_filter_on_valid_dates` is the guard.

Its only subject is `/definitely/not/here.jsonl`. That path yields no timestamps,
so every one of the four filter combinations returns the same verdict on both
sides **trivially**, and the comparison `stamp >= threshold` is never reached.
Swapping `last_timestamp` for `first_timestamp` inside `lazy_screen`, or `>=` for
`>`, leaves the test green.

22k, one level up: a fixture must be asymmetric in the dimension it is checking,
and here the subject is degenerate in exactly that dimension.

---

## F3 — `branch_map` builds its maps by "is a non-empty string" where Python builds them by key presence and truthiness

Three sites in `session.rs`:

| site | Python | Rust |
| --- | --- | --- |
| `nodes` | `{entry["uuid"]: entry for entry in entries if "uuid" in entry}` — **key presence**, so a null or integer uuid becomes a node | `uuid_of` is `entry.get("uuid").and_then(Value::as_str)` — string only |
| `leaves` | `entry.get("leafUuid") in nodes` — any value | `.and_then(Value::as_str)` — string only |
| `era_roots`, `active_leaf` | `if origin_root` and `if active_leaf` — **truthiness**, so an empty-string uuid falls to the other branch | `Some`/`None`, so `Some("")` takes the first branch |

A single `"uuid": null` entry is enough to move the whole map in Python: it
becomes a node whose children are every real root, so `_collect_subtree` over it
spans the entire forest.

This is the L41 family — `is_empty()` against `is_none()` — which this desk has
already been bitten by once, in the no-results wording.

**Corpus:** **0** across 731,847 entries in 5,047 files. No null uuid, no
non-string uuid, no empty uuid, no non-string or empty `leafUuid`.

**Everything else in `branch_map` reproduces**, and I checked all nine properties
of the review-criteria addendum individually. Property 4, the one the criteria
expected to break, is present: the anchor is followed **down** to its deepest
descendant and then up. `deepest_descendant` replaces only on a **strictly**
greater depth, so it keeps the first maximal element as Python's `max` does —
22t's case, handled and commented. `origin_session_root` carries its `visited`
set, and its inner ascent has **no** visited set in either language, so a parent
cycle hangs both alike; that is faithful, not a defect. `head_ids.setdefault(key,
str(len(head_ids) + 1))` evaluates its default before insertion, and the Rust
computes `next_id` before the `entry()` call for the same reason.

---

## F4 — `str::lines()` is not `str.splitlines()`, and that is a second C0 class beside the strip one

**Measured.** `str.splitlines()` splits on **ten** characters:

    U+000A U+000B U+000C U+000D U+001C U+001D U+001E U+0085 U+2028 U+2029

Every one of them is `str.isspace()`-true. Rust's `str::lines()` splits on
U+000A alone and strips one trailing U+000D.

`session.rs:710`, inside `command_tag_lines`, uses `content.lines()` and ports
`parsing.py:572`'s `content.splitlines()` directly.

**Consequence.** `is_hidden_user_command_text` decides whether a user text block
is protocol plumbing that never renders. A block whose tag lines are separated by
any of the nine splits in Python and does not in Rust, so the block stops being
recognised as pure command tags and **renders as visible user text**. That is a
difference in rendered inner XML, which the charter defines as search truth — not
a chrome difference.

**Corpus:** measured over the surface this site actually consumes, which is user
message text blocks and not every string in the pool. **4,129 user text blocks,
zero occurrences.** Hypothetical, exactly like the strip class.

*Stating the narrowing because it matters:* the corpus-wide counts in the
correction above would overstate this finding by three orders of magnitude. Most
of those hits are binary **tool output**, which never reaches this site.

## F4b — the same gap in four `\s` regexes, and it is outside `session-core`'s enumeration entirely

Python's `re` `\s` matches U+001C–U+001F. The `regex` crate's `\s` is
`\p{White_Space}`, which does not. This is the widening `engine-and-codex`
applied to `codex.rs` this session, in a file nobody has applied it to.

| line | pattern | Python counterpart |
| --- | --- | --- |
| `session.rs:766` | `^\s*<local-command-stdout>.*?</local-command-stdout>\s*$` | `_LOCAL_COMMAND_STDOUT_PATTERN` |
| `session.rs:790` | `^\s*<task-notification>(?P<body>.*)</task-notification>\s*$` | `_TASK_NOTIFICATION_PATTERN` |
| `session.rs:1186` | `<skill(?:\s[^>]*)?>|</skill>` | Pi inline-skill token |
| `session.rs:1360` | `^<user_agent(?:\s[^>\r\n]*)?>\r?\n...` | Pi user-agent prefix |

The first two decide whether protocol content is hidden, so a divergence there
makes hidden plumbing visible.

**Why this was missed and is worth its own line.** `session-core` enumerated
**`.trim()` sites**, because that is the question they were handed. No `\s` site
can appear in a `.trim()` enumeration however carefully it is done. L43 in
production, and the shape came from whoever raised the question rather than from
whoever answered it.

**Confirmation status, stated because it is uneven.** The Python half is executed
— `re.fullmatch(r"\s", chr(0x1c))` matches, and so do 001D, 001E, 001F, 000B,
000C, 0085, 2028, 2029, 00A0, but not 200B. The Rust half is from the `regex`
crate's documented definition of `\s` and Unicode's White_Space list, **not** from
executing the crate. `engine-and-codex` reached the same fact independently from
the Codex side, which is corroboration rather than proof.

---

## F5 — `command_tag_regex` lost Python's backreference, and this one needs no exotic input

    Python  (?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</(?P=tag)>[ \t]*
    Rust    ^(?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</command-[a-z0-9-]+>[ \t]*$

The `regex` crate has no backreferences. The port **widened the pattern** rather
than failing, so **any** command close tag now closes **any** open tag.

`<command-name>x</command-args>` fails Python's `fullmatch`, so
`_parse_command_tag_lines` returns `None`, the block is not hidden, and the user's
text renders. The Rust matches, `command_tag_lines` returns `Some`,
`is_hidden_user_command_text` returns true, and **the message disappears**.

The direction is the dangerous one: content is lost, not gained, and no gate on
this mission compares message counts.

**Reachability, measured 2026-08-29 — zero, and the instrument is proved able to
fire.** `probes/f5_backref_scan.py` applies both patterns with **identical** line
splitting, so it isolates the backreference from F4's `lines()`/`splitlines()`
gap. Over **4,128 user text blocks**, 150 of which mention `<command-`: **no block
makes the two patterns disagree**, and no line anywhere in them carries a
mismatched command-tag pair.

**The zero is quotable only because `--falsify` fires.** L48: a probe that catches
nothing may be broken rather than the world being flat, and the symptom is
identical. The falsifier disagrees on four synthetic shapes — a mismatched pair
bare and indented, a three-tag line with an outer mismatch, and a two-line block
with one bad line — and agrees on three controls.

**One-directional by construction:** the wide pattern accepts a superset of the
narrow one, so the native route can only ever hide *more* than Python, never less.

**What the zero does and does not say.** These tags are emitted by the Claude CLI
itself for slash commands, so a mismatched pair cannot arise from the machine. It
can only arise from a user **pasting** protocol-shaped text — which is exactly
the input `is_hidden_user_command_text` exists to distinguish from real protocol,
and exactly what one user's history is least likely to contain. The corpus is
one person's; the product is not.

**Count drift, stated because it changes how the number should be quoted.** Three
runs across 2026-08-28/29 gave 4,129, 4,124 and 4,126 blocks before this one. The
pool is being written by nine live sessions, so every count here is a dated
point-in-time proof. That is L1's ruling and 22al's live-corpus property arriving
from a third direction.

*Correct in the same function, and worth saying so:* the Rust adds
`captures.get(0)? != raw_line`, which restores `fullmatch` semantics that the
crate's non-multiline `$` alone would not guarantee.

---

## F6 — `expand_tabs` is a flat 4 per tab where Python advances to the next tab stop

`session.rs:729` against `parsing.py:580`'s `len(match.group("indent").expandtabs(4))`.

**Measured:**

    "\t"     Python 4   Rust 4    agree
    "\t\t"   Python 8   Rust 8    agree
    "\t "    Python 5   Rust 5    agree
    " \t"    Python 4   Rust 5    DIFFER
    "  \t"   Python 4   Rust 6    DIFFER

They agree whenever tabs come first and disagree whenever a space precedes a tab.
No exotic input is needed.

**The value is byte-visible.** `parsing.py:618–625` maps distinct indent values to
YAML nesting levels, so a changed indent changes the rendered command block.

**Corpus:** 127 pure command-tag blocks; the only two indent shapes present are
the empty string and twelve spaces. **No tabs at all.** Not live.

---

## F7 — `dedent` is not `textwrap.dedent`, and it corrects two of `session-core`'s three exceptions

`session.rs:741`. CPython's `textwrap.dedent` computes the common **prefix** of
the lexicographic min and max non-blank line, stopping at the first character
that differs **or is not in `' \t'`**, and emits `l[margin:] if not l.isspace()
else ''`.

The Rust computes a **byte count** of each line's leading Rust-Unicode
whitespace, takes the minimum, and slices that many bytes off every line
including the whitespace-only ones.

| input | Python | Rust |
| --- | --- | --- |
| `"\tfoo\n    bar"` | unchanged — no common prefix between a tab and a space | strips one byte from each line |
| `"  a\n    \n  b"` | `"a\n\nb"` — the blank line is blanked | `"a\n  \nb"` — two spaces survive |
| `"\u{a0}a\n\u{a0}b"` | unchanged — U+00A0 is not in `' \t'` | strips the NBSP from both |
| `"\u{2028}a"` beside `"  b"` | unchanged, margin 0 | `&line[2..]` lands **inside** the three-byte U+2028 and **panics** |

**This is a direct correction to `session-core`'s classification, and it is the
one the first mate asked me to re-check.** They listed the two `dedent` internals
among the three sites that are **correctly bare**. Under the widened criterion
both are wrong, in opposite directions:

- `line.trim().is_empty()` ports `l.isspace()` and is **too narrow** — it misses
  U+001C–U+001F.
- `line.len() - line.trim_start().len()` ports a `[ \t]`-only margin walk and is
  **too wide** — it accepts every Unicode whitespace character as indentation, and
  that is the byte index that can panic.

Their third exception, their own C0 test assertion, is correct and stays.

**Their enumeration is sound and the classification is provisional**, which is
what the first mate already said. This is the concrete instance.

**Corpus:** zero command-tag values contain a newline, so `dedent` never runs on
this pool. Not live.

---

## The Pi decoder — three latent divergences, and a different class from the rest

*Added 2026-08-29. `session.rs` lines 1176–1692, against `parsing.py`'s Pi adapter.
Reviewed invariant-first per criterion 5's cheaper form: start from the invariant
list, ask which have no test, rather than auditing tests for falsifiability.*

**These are a different class from F1–F7 and the tally should say so.** F1–F7 are
divergences the corpus cannot *reach*. These three are divergences with **no
trigger today at all** — the shape that produces them cannot currently arise from
either side. That is `search_output.rs`'s two-flag-lists shape: the behaviour is
faithful, and nothing would notice if it stopped.

### F8 — `isError` uses strict `bool` where Python uses truthiness, in the same expression that uses truthiness for its other operand

    Python  message_data.get("isError", False) or bool(details.get("error"))
    Rust    get("isError").and_then(as_bool) == Some(true)
              || details.get("error").is_some_and(value_is_truthy)

`value_is_truthy` exists in `model.rs` and the porter reached for it on the
**second** operand and not the first. `isError: 1` or `isError: "yes"` is an error
in Python and not natively.

**Also, Python's `or` returns the operand rather than a bool**, so `is_error` can
be stored as `1` or `"yes"` rather than `True`. The Rust field is `bool`, so it
cannot represent that.

**Measured: unreachable.** 129,157 Pi toolResult entries — `isError` is a real
bool every time (124,424 false, 4,733 true). `details.error` is a string 306 times
and null 148 times, both of which `value_is_truthy` gets right. Claude's
`is_error` is a real bool in all 13,543 occurrences.

**The tell is the asymmetry, not the reachability.** One expression, two operands,
two different notions of truth, and only one of them matches Python.

### F9 — the Pi `toolResult` content default models a state Python cannot produce

Python injects a default — `"content": message_data.get("content", [])` — so the
key is **always** present, and `shorten_data`'s `"content" in tool` test always
fires. `session.rs:1567–1568` sets `content: None, has_content: false` when the key
is absent.

**The Claude path is faithful and only the Pi path injects**, which is what makes
this specific rather than general: Python keeps `{**item}` for Claude, so presence
there is genuine, and `tool_from_json`'s `has_content: item.contains_key("content")`
is exactly right for it.

**Measured: unreachable.** Of 129,157 Pi toolResult entries, **every one carries a
`content` key**, none null, none empty. A future Pi that omits it diverges.

### F10 — the Claude tool-name normalisation happens at a different stage from Python's

Python passes the **raw** tool name to `normalize_tool_input_keys`:

    normalize_tool_input_keys("claude", item.get("name"), item.get("input", {}))

The Rust passes the **canonical** one:

    let name = normalize_tool_name("claude", item.get("name"));
    normalize_tool_input_keys("claude", &name, &input)

**They agree today for one reason only: `TOOL_NAME_ALIASES` has no `"claude"`
entry**, so the two names are the same string. The Pi path passes the canonical
name on both sides, so the asymmetry is Claude-specific and invisible next to it.

**The named mutation, per criterion 5: add one alias under `"claude"`.** Python
would then look up `TOOL_INPUT_KEY_ALIASES["claude"]` by the *native* name and find
nothing, while the native route looks it up by the *canonical* name and renames the
keys. Nothing goes red. No test asserts which name reaches that call, and no corpus
can, because the divergence needs a table entry that does not exist.

### Checked and clean in the Pi half

- **`_pi_inline_skill_message`'s hash seed.** Python's f-string renders a missing
  id as the literal `"None"`; the Rust writes `native_id.as_deref().unwrap_or("None")`.
  That is the kind of thing a port normally loses, and it decides every synthetic
  Skill tool id.
- **The index reassignment asymmetry is reproduced exactly.** Python's Pi loop
  reassigns `msg.index = index` after parsing, so a message entry yielding several
  messages gets sequential indices; Python's Claude loop never reassigns. The Rust
  mirrors this precisely — `parse_pi` writes `original_index` on keep, `parse_claude`
  does not — and `Message.original_index` is the field Python's `index` maps to,
  rendered as the `i` attribute. Easy to flatten, and it was not.
- **Thinking blocks: Claude overwrites, Pi joins with `\n\n`.** Both reproduced,
  including that Claude assigns even an empty string.
- `split_pi_inline_skills` reproduces `.match(text, pos)` anchoring via
  `find_at` plus an explicit `start() != cursor` check; the byte-versus-code-point
  cursor is correct in each language's own unit; an unclosed leading block discards
  already-collected skills in both.
- `extract_pi_user_agent_response`'s conservative resolution is intact — one
  candidate wins outright, otherwise the preview must resolve exactly one,
  otherwise nothing — and the optional `<duration_ms>` terminator is preserved with
  a comment naming the defect that omitting it caused.
- The UTF-16 preview length is measured in UTF-16 code units on both sides, which
  is the third counting unit this codebase uses and must not be unified.
- `is_hidden_pi_custom_entry` reproduces `display is False` as identity rather than
  falsiness, so `display: 0` hides on neither route.

### Two notes that are not findings

- **`extract_pi_user_agent_response` compiles a regex on every call.** Python's
  `re.compile` is cached, so the oracle pays that cost once per distinct task and
  the native route pays it per entry. Byte-invisible, so it belongs to the
  timing-shaped class rather than to this list. The corpus's longest task is 13,894
  characters, well inside the `regex` crate's 10 MB compiled-size limit, so the
  related `Regex::new(...).ok()?` — which would silently drop a message rather than
  raise — is not reachable either.
- **`\w` differs between the two engines**, in both directions: Python's `re` `\w`
  is `str.isalnum()` plus `_`, so it includes `\p{No}` and `\p{Nl}` (`²`, `Ⅸ`); the
  `regex` crate's is the UTS#18 word class, which excludes those and includes
  `\p{M}`, `\p{Pc}` and `\p{Join_Control}`. One site, `pi_skill_attribute_regex`'s
  `([\w-]+)="([^"]*)"`. Recorded beside `\s` because it is the same family and the
  desk has only ever recorded `\s`.

### One thing the existing corpus does cover, stated because I nearly reported it

`tool_from_json` keeps only `name`, `input` and `id`, where Python keeps `{**item}`
and overrides `input`. That looks like dropped keys — **and the 2,436-case Claude
differential exercises exactly this path on real tool-use items**, so a renderer
reading any other key would already have failed it. The existing gate is
sufficient here and I am not reporting it. Recording the near-miss because "the
Rust struct is narrower than the Python dict" is a shape that will look alarming to
the next reader too.

---

## The Codex decoder — and F12, the first finding on this seat with a live blast radius

*Added 2026-08-29, read post-edit and post-engine-landing. `codex.rs` is 820 lines;
this covers the decoder, ordering and error paths — lines 40–500. The script parser
below that was re-differentialled at 0 mismatches after its `.trim()` fixes and I
did not re-read it.*

### F12 — two `has_content` predicates that are not the same, a comment saying they are, and a documented refactor that would change 12,911 entries

`codex.rs:278` and `session.rs:1137` hold what the Codex comment calls "the same
predicate". **They are not the same.**

    codex.rs     message.thinking.is_some()
                 message.plan.is_some()
                 message.subagent_task.is_some()

    session.rs   message.thinking.as_deref().is_some_and(|v| !v.is_empty())
                 message.plan.as_deref().is_some_and(|v| !v.is_empty())
                 message.subagent_task.as_deref().is_some_and(|v| !v.is_empty())

Python is `bool(self.text or self.thinking or self.tools or self.plan or
self.subagent_task)` — **truthiness**, so an empty string is falsy. **`session.rs`
is right and `codex.rs` is wrong.**

**Inside `codex.rs` the difference cannot fire**, which is why the differential
passes: `reasoning()` returns early on empty text, so `thinking` is never
`Some("")`, and `plan` and `subagent_task` are never set on the Codex path at all.

**The trigger is not an input. It is the refactor the comment proposes.** The
comment names its real home as `Message::has_content()` in `model.rs`, "matching
Python", and calls promoting it "a five-line change pending its owner's ruling."
Promote *this* version and `session.rs`'s Claude path inherits it — and there
`parse_assistant_entry` **does** produce `thinking: Some("")`, from
`item.get("thinking").and_then(as_str).unwrap_or_default().trim()`.

**Measured blast radius: 12,911 Claude assistant entries** whose only content is an
empty or whitespace thinking block, across the real pool. Today Python and
`session.rs` both drop every one. Under the promoted predicate every one is kept.

**And the damage is not 12,911 empty blocks. It is every index in those
transcripts.** `parse_claude` increments `index` only for a kept message, so the
first resurrected entry shifts the `i` attribute of every message after it.

**Bounded honestly:** this needs `show_thinking`, which defaults to `False`, so it
reaches only invocations that ask for thinking. The count is the population, not
the per-invocation impact.

**Why this is a different class from F1–F11.** Every other finding on this seat is
a divergence the corpus cannot reach or that has no trigger today. This one has a
named, documented, scheduled trigger sitting in a comment, and the comment asserts
the safety property that is false. It is `plan.rs`'s inert guard inverted: there a
test existed and could not fail; here a **comment** exists and is wrong, and it is
the artifact the next person will act on.

**The fix is smaller than the finding.** `session.rs`'s version is already correct
and already matches Python. Promote **that** one.

### F13 — three absent-key defaults on the Codex path, all measured unreachable

Python supplies a default at each site; the Rust models absence.

| site | Python | Rust |
| --- | --- | --- |
| `function_call_output` / `custom_tool_call_output` | `payload.get("output", "")` → content `""` | `parse_tool_output(None)` → `Value::Null` |
| lifecycle `function_call` | `agent_lifecycle_call_ids.add(payload.get("call_id"))` — **adds `None`** when the key is absent | only string ids are recorded |
| `function_call_output` suppression | `payload.get("call_id") in agent_lifecycle_call_ids` — a `None` call_id **matches** the `None` added above and is suppressed | a `None` call_id never matches, so the output **renders** |

The second and third compose into one live shape: a lifecycle call with no
`call_id` followed by an output with no `call_id` is suppressed by Python and
rendered natively.

**Measured over the Codex pool: zero.** 31,393 `function_call`, 31,385
`function_call_output`, 19,244 `custom_tool_call_output` and 2,186 lifecycle calls —
every one carries both `output` and a **string** `call_id`.

### Checked and clean in the Codex decoder

- **`tool_result` sets `has_content: true` unconditionally**, with a comment saying
  Python always sets the key. **That is F9's fix, applied here and missed on the Pi
  path** — the same author reasoning would have caught F9, which is what makes F9 a
  local miss rather than a modelling disagreement.
- The assistant accumulator's ordering is exact: `flush_assistant()` runs **after**
  the user-visibility checks, so a hidden user message does not split the assistant
  turn, in both languages.
- `index` advances only for a kept message, so an assistant turn of nothing but
  suppressed lifecycle calls consumes no number. Reproduced.
- `ensure_assistant` adopts a timestamp only when it does not already have one.
- The assistant text filter uses `python_strip`, not `trim` — the L52 fix landed
  where it matters.
- `parse_tool_output` and `parse_tool_input` reproduce their Python counterparts
  branch for branch, including that a non-string non-list output is returned
  untouched and that a `{`-leading string that fails to parse falls back to raw.
- The `flush_assistant` `has_content` guard is documented as unreachable **and it
  is** — I checked all six `ensure_assistant` call sites and every one adds text,
  thinking or a tool before the next flush. The comment distinguishing "a branch no
  input can reach" from "a behaviour the corpus never exercises" is the right
  distinction and it is rarely made.

### The Codex script parser — four divergences, all unreachable, and one false finding I killed

*Added 2026-08-29, closing the last gap in the named scope. `codex.rs` lines
500–820 against `parsing.py` 2226–2420.*

| # | Python | Rust | measured |
| --- | --- | --- | ---: |
| 1 | `string_bindings` is a **dict** comprehension, so a duplicate `const` name keeps the **last** | a `Vec` searched with `.find()`, so the **first** wins | 0 |
| 2 | the property regex needs `(?P<value>.+)`, so `{a: }` fails and the **whole object** is unparsed — the envelope stays `exec` → `Bash` | `split_once(':')` yields `""` and the call parses as `{"a": ""}` | 0 |
| 3 | a lone `` ` `` satisfies both `startswith` and `endswith`, yielding `""` | guarded by `len() >= 2`, yielding `` "`" `` | 0 |
| 4 | a shared key that is explicitly `null` is dropped, because `values[0] is not None` | `Some(&Value::Null)` passes the guard, so `workdir: null` survives the merge | 0 |

Divergence 1 is 22t's first-versus-last hazard in a third place. Divergence 2 is
the same *more permissive than the oracle* class as both L32 defects, which this
module's own comments name as the class to watch — the port would parse a call the
product leaves unparsed, and the rendered tool name changes.

**Measured over 17,106 generated scripts** in the Codex pool, 800 of them carrying
more than one `tools.*` call. **All four at zero.**

**One false finding, killed by reading the instance.** The empty-value scan
returned **1**, which is exactly the shape that gets written down. The hit is
`'{(j:,'` — inside a **backtick-quoted shell string**, `${(j:,:)enabled_tool_names}`,
which is zsh parameter expansion. My regex ignored quoting; the real parser does
not. Python parses that script cleanly into a normal `exec_command`. **True count
zero.** Third time on this seat that 22c has turned an aggregate into nothing.

**Correct in the same file, checked rather than assumed.** `parse_exec_script_tool`
aborts the whole parse when **any** call site fails, exactly as Python's `if
tool_call is None: return None` does — the permissive alternative would surface a
partial call. The merge rules match branch for branch: a single call passes through
whatever its name, all-`apply_patch` joins with `\n\n`, all-`exec_command` joins
`cmd` and carries a shared key only when every call agrees, and any mixed set
returns `None` rather than inventing a combined call. And `parse_script_object`
returning `None` for `{}` where Python returns a falsy `{}` reaches the identical
outcome, because Python's caller tests it with `if input_data :=` — the emptiness
test moved one level up and the two agree.

### One note that is not a finding

`json.loads` accepts `NaN` and `Infinity`; `serde_json` does not. So a tool output
of `{"output": "x", "y": NaN}` yields `"x"` in Python and the raw string natively.
This is the same parser asymmetry `session.rs`'s module header already documents at
the entry level, arriving one layer down. Not separately reported.

---

## The engine gate surface — F14, a second false comment, and this one fires today

*Added 2026-08-29. `search_output.rs` lines 390–650, the candidate-gate half,
against `commands/search.py` 820–1160. `context-curator` covered the two
hand-maintained flag lists; this is the rest of the non-timing criteria.*

### F14 — the same unreadable file produces two different error lines, and the comment says it produces one

`search_output.rs:591–593` reads:

> Python does **not** swallow here, so an unreadable file becomes a per-file
> error. Answering `true` reaches the same place: confirmation opens the same
> file, fails the same way, and **prints the same line.**

**It reaches the same place and prints a different line.** Measured on a
`chmod 000` file, both halves executed:

    Python, at the SERIAL gate
      Error processing conversation file /p: Permission denied (os error 13)

    the native route, at CONFIRMATION
      Error processing conversation file /p: [Errno 13] Permission denied: '/p'

**The inversion is the reason nobody would guess it.** Python's gate message comes
from Rust — `file_contains_ascii_impl` returns `io::Error`, PyO3's
`From<io::Error> for PyErr` builds a `PermissionError` whose `str()` is Rust's
`"Permission denied (os error 13)"`. The native route's message comes from
`python_io_error`, which models `OSError.__str__` faithfully. **So Python prints
the Rust-shaped line and the native route prints the Python-shaped one**, for the
same file, on the same stream.

**This needs no unusual content — only an unusual file state.** A permission
change, a `.jsonl` path that is a directory, or a file removed between discovery
and scan while nine sessions write the pool. That puts it in a different class from
F1–F13: not a shape the corpus lacks, but a condition a corpus of transcripts
cannot represent at all.

**The batched arm's comment, four lines away, is correct** —
`_file_contains_ascii_json_strings` really does `except OSError: return True`, and
`path_candidate_matches` mirrors it with `.unwrap_or(true)`. One file, two
comments about the same swallow decision, one right and one wrong.

**Second instance of L103 in two files.** F12 is a comment asserting two predicates
are the same when they differ; this is a comment asserting two error paths converge
when they do not. Both are load-bearing for the next change, and neither can be
caught by asking whether a test would go red.

### The gate-conservatism criterion — checked arm by arm, and it holds

This is the criterion whose losing direction is invisible to every byte gate: a
`false` that should have been a `true` rejects a real hit and the user sees a
missing result, never an error.

- `evaluate_prefilter` returns `true` for **every** `Not`, so a negated term can
  never reject a file. `And` is `all`, `Or` is `any`. Matches Python exactly.
- `ascii_literal_needle` returns `None` — defer — for render-dependent tokens, for
  a non-ASCII pattern, and for a missing `literal_candidate`. Python checks the
  same three in a different order; all three are pure, so the order does not
  matter.
- `term_can_match_generated_marker` tests the candidate for being **contained in**
  the marker rather than the reverse, so searching `too` defers under `--tools`.
  That direction is easy to invert and it is right.
- **The two character classes really are different, and both are faithful.**
  `can_use_json_string_gate` excludes `"` and `\`;
  `term_can_change_under_json_decoding` excludes `"`, `\` **and `/`**. I expected
  the missing `/` to be a false-negative source and checked instead of reporting:
  Python has exactly the same split, `_LOGICAL_JSON_STRING_INELIGIBLE_CHARACTERS =
  frozenset('"\\')` against `_JSON_DECODE_UNSTABLE_CHARACTERS = frozenset('"\\/')`.
  The batched gate decodes JSON strings itself, so it does not need the `/` guard;
  the serial one searches raw bytes and does. Faithful.
- The `.isascii()` clause and its comment about `ß` folding to `ss` under
  `literal_candidate` while `re.IGNORECASE` does not match `ss` — correct, and it
  is the one clause whose widening would silently lose results.

**On `context-curator`'s two flag lists, one thing I can add.** The batched list at
`:397` carries `message_selection == All`; the serial `gate_bypassed` at `:573`
does not. **That asymmetry is faithful to Python** — the same difference exists
between `_can_use_logical_json_string_gate` and `_term_path_candidate_matches`. And
it is safe in the correctness direction, because `message_selection` makes the
render carry *less* text rather than synthesizing more, so a byte gate is still
sound without it. Their finding stands on the *unguarded agreement* of the two
lists, not on today's contents.

### F15 — the provider-column rule is unported, and its fixtures record the answer as an input so they can never grade it

**The criterion:** *the provider column reads discovery rows, not gate survivors.*

Python's `_list_show_provider(pool, candidate_file_set, pool_filter)` returns
`False` when `-p` pinned a provider, and otherwise whether the **candidate** set
spans more than one provider. Its own docstring says it is hoisted out of the
per-hit loop **so rows can stream without first collecting every hit.**

**`rg show_provider` over `rust/` finds only a struct field and test literals. No
derivation exists anywhere.** `search_run.rs` builds `PlainSink`; the coloured list
sink is not wired yet.

**The trap is specific and it is the natural implementation.** Whoever wires
`ColouredListSink` will be inside a streaming sink holding hits, and computing
"does this result set span two providers" from the **hits** is the obvious move. It
gives a different answer from the candidate pool, and getting the same answer would
require buffering every hit before the first row — which destroys the streaming
economy the Python docstring says the hoist exists to protect.

**Named mutation, and it already cannot be caught.** `search_views.rs:794` and
`:1282` read `show_provider` **out of the recorded oracle as an input**. So the
fixtures grade the *rendering given the flag*, never the flag's derivation. Change
the derivation to any wrong rule and every one of them stays green.

This is `plan.rs`'s inert guard and `context-curator`'s two flag lists in a third
shape: **a fixture that takes the thing under test as a parameter.** 22ad says a
table that re-derives its own answers is not a fixture; this is the mirror — a
table that is *handed* the answer.

**Recorded before the wiring lands rather than after**, which is the only time it
is guidance rather than a finding.

### F16 — two functions named `truncate_to_cells`, in two modules, with different semantics

`cells.rs:304` is public and models Rich: below the limit return unchanged, above
it `set_cell_size(text, limit - 1) + "…"`, **which pads with a space when a
double-width character cannot fit** — Rich's own behaviour, and the reason
`cells.rs` has a test named for the double-truncation finding.

`search_output.rs:115` is private and accumulates characters while
`cells + size <= limit - 1`, then appends `…`. **No padding.**

    "你好你好" at limit 6   cells.rs        -> "你好 …"   six cells
                            search_output   -> "你好…"    five cells

`rule()` is the only caller, and its only title is a session id.

**Measured: unreachable.** All 4,693 native session ids in the pool are ASCII, and
no filename stem is non-ASCII. The two implementations agree on every ASCII input,
which is every input this product can currently produce.

**Recorded because of what it is rather than what it does.** Standing constraint 4
is "a copy that compiles is not an extraction". This is the harder version: not a
copy, a **divergent reimplementation under the same name**, in a module that
already imports the correct one. The `rule` oracle at `search_output.rs:338` cannot
distinguish them, because a recorded corpus of ASCII session ids never reaches the
padding branch.

### A documented divergence that may not have reached the change log

`display_session_id` takes the native id **from the entries already decoded during
confirmation**. Python's `get_display_session_id(file_path)` **reopens the file**
at render time. The Rust comment states the choice and its reason — "a second read
would be a second chance to disagree with the first" — and I checked both
extraction rules and they agree: first parseable line, `session_meta`/`session`
type, non-empty string id, else the stem.

**It is the right call and it is still a divergence**, in the direction this
mission is most careful about: the native route is *more* consistent, and one
fewer read. The only observable difference needs the file to be rewritten between
confirmation and rendering, which a live pool can do. **Question for G5 rather than
a finding: is this on `final-change-log.md`'s list?** It is documented in the code,
which is where a porter would meet it, and not obviously anywhere a change log is
assembled from.

### The two Package-B criteria that are simply not there yet

Stated because an unported criterion and a passed one look identical in a review
that only lists defects.

- **Provider column** — F15 above.
- **Highlight painting.** *"Never index the original string with offsets measured
  on a lowered copy. `İ` grows 2 bytes to 3; the ligatures shrink 3 to 2. Enough
  drift aborts the process mid-render with exit 101."* This was **the branch's one
  blocker**. `rg` finds one `highlight_spans` in `search_views.rs:1432`, and it
  paints the quoted term inside the **no-results hint**, not query matches in
  message bodies. Query-match painting does not exist in the tree, consistent with
  L7's "highlight painting waits on confirmation".

  **What its guard has to do, since it will land after this review:** fold per
  character over the **original** string using the same equivalence search truth
  uses, and assert it on a case where the folded and original lengths differ in
  both directions — `İ` for growth, `ﬀ` for shrinkage. A test on ASCII cannot fail,
  and ASCII is what a first fixture uses.

### One cosmetic note

`can_use_json_string_gate` binds `candidate` and then discards it with
`let _ = candidate;`. The binding exists only for the `is_none` guard. Not a defect;
recorded because a deliberate discard reads as a leftover to the next reader.

---

## What is clean, checked rather than assumed

**`color.rs` — no defects, and it grew a `StyleColor` enum under me on 2026-08-29.**
Read against `rich/color.py` and `colorsys`. The verdict below covers **both**
versions; the addition is checked separately at the end.

- `downgrade_to_standard` uses `min_by_key`, which keeps the **first** minimum,
  matching Python's `min(range(...), key=...)`. That is the 22t hazard and it is
  handled.
- `redmean_distance` stays in integer arithmetic. The dropped `sqrt` is argued
  from monotonicity over a range where consecutive roots differ by ~5e-4 against a
  double's 2e-13, and the 1,499-row oracle proves the argmin end to end anyway.
- `lightness_and_saturation` uses `2.0 - maximum - minimum`, the post-gh-106498
  CPython form, and the comment names the bit that decides the branch.
- `round_ties_even` is CPython's `round`: C `round` plus a halfway correction to
  even is exactly roundToIntegralTiesToEven.
- `rendering()`'s **three** states are right, and the two that a port would
  collapse — `TERM=dumb` emitting no SGR, `NO_COLOR` keeping attributes — are
  pinned by a test.
- The standard-colour SGR split at 30/40 below 8 and 82/92 at or above matches
  `Color.get_ansi_codes` exactly.

### F11 — `StyleColor` is correct, has no caller, and has no test of the one property it exists for

Added to `color.rs` on 2026-08-29. It separates an authored RGB triple, which
downgrades with the terminal, from a palette index, which does not.

**The behaviour is right and I verified it against Rich rather than reasoning
about it.** `Color.parse("green")` yields `32` as a foreground at TRUECOLOR,
EIGHT_BIT **and** STANDARD; `bright_red` yields `91` at all three; and the theme's
`#878c92` becomes `37` at STANDARD. Rich's `downgrade` converts only *from*
truecolor, so a palette colour is genuinely tier-invariant, exactly as the doc
comment claims.

**`rg StyleColor` finds no use anywhere in `rust/` outside `color.rs`, and no
test.** It is landed ahead of the highlighter that will consume it.

> **⚠ Premise stale as of 2026-08-29, and `views-and-colour` checked rather than
> closing it from memory.** `StyleColor` now has **ten call sites** in
> `search_views.rs` — the three stderr console base styles and the five
> highlighter rules — and the named mutation goes red on **54 of 135** stderr
> cases. **The type arrived before its caller and this review caught the window
> between them**, so the finding was true when made and is not now.
>
> **The test was still worth writing and they wrote it**, because the 54 cases
> catch the collapse only *in composition*; the local assertion states the
> property directly — `Palette(1)` emits `31` at all three systems while
> `Triplet(#878c92)` gives three distinct answers — and **they verified it fails
> on its own** with the arms collapsed. Its doc comment spells out the
> consequence, because the failure mode is drift rather than breakage: a port
> resolving both the same way makes the highlighter's colours move as the terminal
> changes, which nobody reads as a bug.

**Named mutation, per criterion 5: collapse the two arms** — route `Palette(n)`
through the triplet path so it downgrades with the tier. **Nothing goes red**,
because nothing calls it. And that collapse is the *specific* tempting
simplification the enum exists to prevent: two arms that produce the same string
for the sixteen standard numbers at the standard tier, and diverge everywhere
else.

This is the `term_dot` shape from L31 and L38 with the opposite answer. There the
unused function turned out to be redundant scaffolding and was deleted with its
property kept as an invariant test. Here the code is **needed** and correct, and
what is missing is the test that would notice if the property stopped — so the
cheap move is the same one L38 landed: a test asserting that a `Palette` colour
emits identical parameters at all three systems, with the consequence spelled out.

**`cells.rs` — no defects.** Reviewed before the narrowing; reported only so the
next reader knows the ground was walked. Checked function by function against the
installed `rich/cells.py` (rich 14.3.3), including the grapheme walk's ZWJ and
variation-selector arms, `_split_text`'s offset guess, `set_cell_size`'s two fast
paths, the `codepoint and codepoint < 32 or 0x7F <= codepoint < 0xA0` precedence,
and `load()`'s version resolution against `table_index`. **The one model-level
collapse is guarded:** Rich carries `narrow_to_wide` per version and the Rust
carries one global constant — `generate_cell_tables.py` asserts they are identical
across all 21 versions before writing, and I verified that independently. The four
recorded oracles carry four distinct digests and their correct
`unicode_version` fields, so L19's collapsed-arm problem is closed here.

---

## Instruments

Four read-only probes, reproduced in `probes/` in this directory rather than left
in a session scratchpad. L1: a scratchpad is not storage, and L23: the scratchpad
copy is what a probe finds first.

| probe | question |
| --- | --- |
| `cr_scan.py` | raw CR bytes in the pool — F1's reachability |
| `uuid_scan.py` | non-string, null and empty uuid/leafUuid — F3's reachability |
| `splitlines_scan.py` | the ten separators in **decoded string values** — the correction |
| `edge_scan.py` | the same at a string **edge**, plus instance dumps — separates the strip question from the splitlines question |
| `usertext_scan.py` | the same over **user text blocks only** — F4's real reachability |
| `cmdtag_scan.py` | indent shapes and multi-line values in real command-tag blocks — F6 and F7's reachability |

Each prints what it covered, not only its verdict — 22x. Each is read-only over
the pool and writes nothing.
