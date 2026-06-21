# Changelog

All notable changes to the `conversations` skill.

---
## [2026-06-21] Detect and gate off-main-branch (rewound) Claude messages

### Added

- A Claude transcript is a tree, not a line: rewinding to an earlier point and re-prompting forks it, leaving the abandoned attempt interleaved in file order as if it were linear history. `ch` now detects these abandoned branches and omits them by default, so a printed conversation follows only the main thread. The new `-b, --branches` flag includes them, each tagged with a `branch="N"` attribute (`-f json`: a `branch` key) and a `⑂N` chip in colored output. It is its own flag, deliberately independent of `-t, --tools`.
- The branch id groups a detour by its *head* — the first message that left the main line — so all messages from one rewind share an id while separate rewinds from the same fork point stay distinct.
- The main thread is resolved per era. Real eras are the session start and each `/compact` boundary (a boundary is a fresh `parentUuid: null` root, making a compacted file a forest); a rewind to the *first* message — a second null-parent user root — is an abandoned detour, recognized across compaction via the boundary's `logicalParentUuid`. Within an era the active branch is picked by the latest `last-prompt` `leafUuid` and then followed *down* to its tip and up to the root (longest continuation when no leaf is recorded), so the reply below the recorded leaf stays on the main thread; the leaf is preferred over subtree depth because the active branch can be shorter than an abandoned one. Compaction seams are never treated as branches, and resolution is iterative to stay safe on very deep threads. Claude only; the logic lives in `chats.parsing._resolve_branch_map`.

### Fixed

- A transcript snippet whose head is truncated has no `parentUuid: null` root; the resolver now treats a parent absent from the file as an era root, so partial logs are not wholly mislabeled as off-branch.

---
## [2026-06-21] Render Claude compaction summaries as Compaction blocks

### Added

- Claude `type: "user"` entries flagged `isCompactSummary: true` (the summary injected when a conversation is continued past its context limit) now render as a `<compaction>` block with a `## Compaction` header, shown by default like `<recap>` rather than as a regular `<user-message>`. In colored output the block gets its own fuchsia hue (`#a21caf`) and a "Compaction" badge; `-f json` emits `type: "compaction"`.

---
## [2026-06-18] Redesign the colored view as tag-free panels

### Changed

- Colored output (`--color=auto`/`always`) no longer wraps messages in XML tags. Parse renders each message as its own rounded panel titled with a colored role badge (role hue, index, model); `ch search` renders each matching conversation as one panel whose border hue cycles per conversation. The XML tags remain only in plain output (`--color=never`, `-f raw`) — the form meant for piping to tools or LLMs (`-f json` is structured separately and unaffected).
- Inside a message, thinking renders under a `✻ thinking` marker, subagent tasks under `✻ subagent task`, and tools as tag-free `⏺` call / `⎿` result headers over a colored left rail. Edit calls render as a unified diff and a Read result is syntax-highlighted by file extension; other tools fall back to fenced markdown.
- Internal cleanup: removed the dead `render_messages_with_rich` path and unified the duplicate header builders into one badge, dropped the unused `ContentBlockInfo.rich_style` field, deduped the search match-count behind one helper and `SearchHit.match_count`, and stored role hues bare so the panel border no longer re-parses a composite style string.

### Fixed

- Colored output silently dropped message text containing attributed XML-like tags (e.g. `<div class="box">`): Rich's Markdown treated them as unknown HTML and stripped them. Such tags are now escaped before rendering so they survive literally (bare tags like `<thinking>` were already handled, attributed ones were not).

---
## [2026-06-16] Stream search results to the terminal as they are found

### Changed

- `ch search` now displays each matching session the moment it is confirmed instead of scanning the whole pool, sorting, then paging. On a ~1900-file pool, the first result appears in well under a second (e.g. ~0.76s) rather than after the full ~9–13s scan, making a bare `ch search <pattern>` usable again.
- Paged, colored output streams through `less -r` via a new `StreamingPager`: `less` is spawned up front and each hit's Rich-rendered ANSI is written and flushed as it is produced (instead of Rich's `Console.pager()`, which buffers everything until the scan finishes). Quitting `less` early stops the search and tears down cleanly, mirroring `UnicodeSafePager`'s SIGPIPE handling.
- Display order is now scan order — newest first by filesystem mtime — rather than a post-scan re-sort by in-band (semantic) modified time. This matches the precedent already set by recent-index resolution and is what enables streaming; the two orderings are near-identical in practice (they differ only for artifacts like forks whose file mtime and last in-band timestamp diverge).
- The colored `ch search -l` list view streams its rows; its `N sessions · newest first` line now prints as a trailing summary (the count is only known once scanning finishes), and per-row provider labels are decided from whether the searched candidate pool spans multiple providers rather than from the providers among the final hits.
- `ch search -r/--raw` stays buffered: its single-visible-message special case needs every hit up front.

---
## [2026-06-12] Classify Claude background-task notifications as the TaskNotification tool

### Changed

- Claude `type: "user"` entries carrying a `<task-notification>...</task-notification>` payload (emitted when a background `Agent` task finishes) no longer render as regular user messages. They now parse into a synthetic `tool_use` named `TaskNotification`: hidden by default, shown with `-t`, and filterable by name like any tool (`-t TaskNotification`, `-t !TaskNotification`).
- Three fields become `<tool-input>` XML attributes — the shortened `tool_use_id` (which links back to the originating `Agent` dispatch), `status`, and `summary` — and the `result` markdown becomes the tool body. Double quotes embedded in attribute values are downgraded to single quotes rather than escaped. JSON output exposes the same fields on a typed `tool-input` block.

---
## [2026-06-11] Prefix auto-generated rename titles with session date and cwd

### Changed

- `ch rename --auto` titles are now assembled programmatically as `MM-DD <cwd name> <generated phrase>` (date from the first message's in-band timestamp, falling back to file birth time), e.g. `06-11 chats fix flaky tests`. The LLM prompt only generates the phrase and is oblivious to both date and cwd. Explicit renames are unaffected; `--dry-run` prints the full title.

---
## [2026-06-10] Add boolean `and`/`or` search operators

### Added

- `ch search` patterns now support lowercase `and`/`or` operators with parentheses, e.g. `'docker and timeout'`, `'deploy and (staging or prod)'`. `and` binds tighter than `or`.
- Terms are evaluated session-wide: `and` terms may match in different messages, summaries, or the current title. Displayed matches are the union of messages matching any term.
- Multi-word or regex-shaped terms must be quoted once an operator is present (`'"hello world" and foo'`); malformed boolean queries exit with code 2 and a quoting hint.
- Patterns without a bare lowercase `and`/`or` token keep single-regex semantics, so `hello world`, `deploy-(prod|staging)`, and `black AND white` behave as before.
- New `search_query` module owns tokenizing, parsing, and per-term regex/literal compilation; the candidate prefilter now evaluates the same boolean tree over per-term raw-content plausibility with a lazily casefolded haystack.

---
## [2026-06-07] Add Antigravity CLI adapter

### Added

- `ch` now discovers Antigravity CLI transcripts under `~/.gemini/antigravity-cli/brain/{session_id}/.system_generated/logs/`.
- Antigravity discovery prefers `transcript_full.jsonl` when it exists and falls back to `transcript.jsonl` only when the full variant is absent.
- Antigravity `USER_INPUT`, `PLANNER_RESPONSE`, thinking, tool calls, and tool-result records parse into the shared message model; session ids come from the brain directory.
- `--provider antigravitycli` is available anywhere provider-scoped filtering is supported.

---
## [2026-05-31] Add `rename -n/--dry-run`

### Added

- `ch rename -n/--dry-run` now prints the resolved or generated title to stdout without mutating the session JSONL or Claude history.
- Dry-run still performs `--auto` title generation, so `ch rename -n <session> --auto` previews the real LLM result rather than a shortcut.

---
## [2026-05-16] Add `search -r/--raw` plain-markdown output

### Added

- `ch search -r/--raw` now mirrors parse raw formatting on the display path.
- Raw search implies `--no-metadata`, `--color never`, and `--no-paging`.
- If raw search would render exactly one visible message, it prints only that message content.
- Otherwise, raw search renders each matching session as plain markdown with a setext `Session <id>` heading, parse-style message bodies, and a single `---` separator between sessions.

---
## [2026-05-12] Fix PI adapter false negative for tool errors with `details.error`

### Fixed

- PI `toolResult` messages whose `.isError` is `false` but `.details.error` is present were not recognized as errors. The adapter now checks both signals.
- Added 4 regression tests covering the 2×2 matrix of `isError`={true,false} × `details.error`={present,absent}.

---
## [2026-05-12] Make `-f json` emit fully structured message data

### Changed

- JSON output now mirrors the structured message model instead of serializing XML-like wrappers into string content.
- Each visible message now emits its wrapper tag as `type`, keeps wrapper metadata like `original_index`, `model`, `agent_id`, and `sourceToolUserId` as fields, and exposes `content` as an ordered array.
- Thinking/tool blocks now become typed JSON objects (`thinking`, `tool-input`, `tool-output`) whose string values are the original content values rather than injected XML tags or fenced pseudo-markup.
- Added cross-provider regression fixtures/tests covering Claude, PI, and Codex JSON output for plain text, thinking, and tool visibility.

---
## [2026-05-10] Collapse recent-index resolution onto stat-mtime + cheap predicates

### Changed

- `_resolve_recent_conversation_file()` now walks candidates newest-first by `stat().st_mtime` and applies `PoolFilter.passes_path_for_index` (cwd) and `passes_path_for_date` (mtime/ctime) per file, short-circuiting at the Nth match.
- Removed the eager `_build_conversation_metadata()` slow path and its `_order_metadata_by_modified_time` helper; full `ConversationMetadata` is now built only for the resolved winner (during display), never for the candidate pool.
- Trade-off: "newest" is always filesystem mtime, not in-band semantic mtime. Extends the May 4 dir-only choice to all index-resolution filter combos.
- Real-world impact on a ~1500-file pool: `ch -1 -ma 4h` drops from ~1.13s to ~0.55s.

---
## [2026-05-10] Skip full read+parse when search dir filter rejects a candidate

### Changed

- `cmd_search` now applies `PoolFilter.passes_path_for_index` as a cheap streaming cwd probe before reading and parsing each candidate, mirroring the existing date pre-skip.
- `ch search ... -d DIR` no longer pays a full `read_text` + `SessionScan` for non-matching directories; the dir check happens once, at the top of `_search_hit_for_file`.
- Real-world impact on a ~1500-file pool: `ch search . -l -d .` drops from ~4.2s to ~1.45s. The remaining ~750ms is dominated by `SessionPool.discover` startup and full-parse of the matching files; further wins would require a `--list`-aware fast path inside `_search_conversation_content`.

---
## [2026-05-10] Probe only the timestamp each date filter actually needs

### Changed

- `--mafter` filtering now probes only the last in-band timestamp for rejected files; `--cafter` filtering probes only the first.
- New `PoolFilter.passes_path_for_date(path)` consolidates the per-path date check into one cheap predicate that streams only the relevant end of the JSONL file.
- `_load_conversation_metadata` now delegates timestamp probing (with stat fallback) to two cohesive helpers, `parsing.get_jsonl_first_timestamp` and `parsing.get_jsonl_last_timestamp`.
- Real-world impact on a ~1500-file pool: `ch search . -ma 4h --list` drops from ~0.8s to ~0.55s.

---
## [2026-05-09] Speed up date-filtered search

### Changed

- `ch search ... -ma DATE` and `ch search ... -ca DATE` now reject candidate sessions outside the date window before reading or parsing their JSONL content.
- Per-file timestamp metadata is probed only when a date filter is active, preserving the no-date-filter fast path that already skipped metadata for unrelated nonmatches.
- Real-world impact on a ~1500-file pool: `ch search . -ma 4h --list` drops from ~4.4s to ~0.8s.

---
## [2026-05-08] Resolve sessions by current name and ignore historical titles

### Changed

- Parse/rename-style session resolution now accepts the session's current latest title as an identifier, using case-insensitive substring matching after exact-id lookup and before summary-prefix fallback.
- Historical renamed-away titles are no longer acknowledged by resolution or search; only the latest provider-native title entry counts.
- Search/session-scan title semantics now treat Claude `custom-title`, PI `session_info.name`, and Codex `thread_name_updated` as one current-title facet instead of a historical title list.

---
## [2026-05-07] Hide user command protocol messages by default

### Changed

- Default parse/search output no longer renders user-side local command protocol payloads.
- Claude `<command-*>...</command-*>` inputs and `<local-command-stdout>...</local-command-stdout>` outputs now stay hidden, and the same hiding rule applies to equivalent PI and Codex user text blocks.
- Claude `isMeta=true` user messages now stay hidden unless `-t, --tools` is enabled.

---
## [2026-05-04] Speed up dir-filtered recent index resolution

### Changed

- `ch -d DIR -1` no longer eagerly loads timestamp metadata for every candidate session when no date filters are present.
- Dir-only recent-index resolution now walks candidates newest-first by filesystem mtime, streams each file only until it can extract `cwd`, and stops as soon as the requested negative index is satisfied.
- Added regression coverage proving the dir-only fast path avoids eager metadata loading and short-circuits after the newest matching session.

---
## [2026-05-04] Tighten Claude subagent layout handling

### Fixed

- Claude sidechain discovery now assumes only the `<session_id>/subagents/agent-*.jsonl` layout exists.
- `find_all_supported_session_files()` now only discovers `agent-*.jsonl` inside Claude `subagents/`, so unrelated JSONL files in that directory no longer leak into parse/search/recent-index flows.
- `ch fork --agents` now always writes Claude sidechains back into `<new_session_id>/subagents/`.

---
## [2026-05-03] Fix Claude agent detection for new subagents/ layout

### Fixed

- `find_agent_files_for_session()`, `_find_claude_sidechain_files()`, and `find_all_supported_session_files()` now discover agent files in Claude's new `<session_id>/subagents/` directory layout, while maintaining backward compatibility with the old flat layout.

---
## [2026-05-01] Hide plans and session-rename messages by default

### Changed

- Parse/search/fork now treat plan content as opt-in: `--plans` shows `ExitPlanMode` content, and `--all` now includes plans too.
- Default parse output no longer renders provider-native session-title records as `<session-rename>` blocks.
- Search still indexes custom titles as a metadata/search facet, but no longer renders rename records as visible message content.
- Catalog capture now mirrors the new default by omitting plan content unless explicitly opted in upstream.

---
## [2026-04-29] Make `rename` write native PI/Codex session-title records

### Changed

- `ch rename` is now provider-aware on the write path instead of always appending Claude-only `custom-title` / `agent-name` records.
- Claude rename behavior stays the same, including the `~/.claude/history.jsonl` side effect.
- PI renames now append one native `session_info` record with a fresh entry id, a parent chain to the previous entry id, and the requested `name`.
- Codex renames now append one native `event_msg` with `payload.type == "thread_name_updated"` and the canonical thread id.
- Added regression coverage proving PI and Codex renames write native records and do not create Claude history side effects.

---
## [2026-04-29] Flip search to newest-first ordering

### Changed

- `ch search` now scans candidate sessions newest first by filesystem mtime instead of walking the discovery pool in its implicit provider/lexical order.
- Search results now display newest first by semantic conversation modified time, while recent negative selectors keep their existing `-1 == newest` behavior.
- Added regression coverage for both result ordering and candidate scan ordering.

---
## [2026-04-26] Normalize native PI/Codex session names to custom titles

### Changed

- Codex `event_msg` rename events with `payload.type == "thread_name_updated"` now flow through the same custom-title/session-rename abstraction as Claude `custom-title` entries.
- PI `session_info.name` now flows through that same abstraction too, so both providers emit `custom_title:` in metadata frontmatter, render `<session-rename>` blocks in parse output, and participate in search/catalog/session-scan title extraction without provider-specific downstream branching.

---
## [2026-04-26] Pad inline code in Rich output

### Changed

- Inline code spans (`` `like this` ``) now render with 1 space of padding on each side when using `--color=always`. The padding is styled with the same `markdown.code` background, so it reads as a visual margin rather than extra text. Implemented via `PaddedInlineCodeMarkdown`, a minimal `Markdown` subclass that mutates `code_inline` token content after parsing — no Rich internals copied.

---
## [2026-04-25] Add full-conversation search output

### Added

- `ch search -f/--full` now renders every visible message from each matching conversation instead of only the messages that directly matched. Summary-only and custom-title-only hits also render the full visible conversation body in this mode.

### Changed

- Search output modes now distinguish the default matching-message display (`MATCHES`) from full-conversation display (`FULL`), keeping search confirmation separate from result rendering breadth.

---
## [2026-04-25] Share session-pool filters across parse and search

### Added

- Default parse mode now accepts `-d, --dir`, `-ma, --mafter`, and `-ca, --cafter` for recent negative selectors, mirroring `ch search`. So `ch -d ~/dev/proj -1` resolves the most recent session whose cwd exactly matches `~/dev/proj`.
- New `PoolFilter` declarative bundle (provider/dir/mafter/cafter) shared by both subcommands; `add_pool_filter_args` installs the same flag group on either parser.

### Changed

- The pre-existing parse `--provider` ignore-with-warning behavior now generalizes to any pool filter — when parse input is not a recent index, the CLI warns and ignores all four flags together.
- Search no longer defines its own `-d / -ma / -ca / -p` block; it composes the same `add_pool_filter_args` group, eliminating duplication.

---
## [2026-04-23] Add parse-only metadata and id modes

### Added

- Default parse mode now accepts `-l, --only-metadata` to emit just the resolved session metadata frontmatter without the conversation body.
- Default parse mode now accepts `-ll, --only-id` to emit just the resolved session ID, matching `ch search --only-id`.

### Changed

- Parse `--only-id` now forces plain output and disables paging, mirroring the existing search-mode behavior.
- Parse metadata-only output preserves the existing post-slice `messages:` count semantics, so `ch -l <session> "-1"` reports the sliced visible count rather than the full conversation length.

---
## [2026-04-23] Display fork ancestry metadata when available

### Added

- Metadata frontmatter now emits `forked_from:` when the raw session exposes a fork parent id.
- Codex sessions populate this field from `session_meta.payload.forked_from_id`; sessions without fork ancestry omit the field entirely.

---
## [2026-04-23] Add provider-scoped parse recent selectors

### Added

- Default parse mode now accepts `-p, --provider claude|pi|codex` for recent negative selectors, so commands like `ch -p codex -1` resolve the newest Codex session instead of the newest session overall.

### Changed

- Parse provider filtering is intentionally limited to recent-index inputs; when used with a session ID, path, summary, or stdin, the CLI warns and ignores the flag.

---
## [2026-04-21] Render common Codex tool inputs through shared schemas

### Changed

- Codex `exec_command` tool inputs now normalize to canonical `Bash` tool parts, putting command metadata on the `<tool-input>` tag and the shell command in a `sh` fenced body instead of falling back to raw JSON.
- Codex `apply_patch` tool inputs now normalize to canonical `Patch`, render as diff fenced bodies, and JSON-wrapped Codex tool outputs like `{"output": "..."}` render as their contained text.
- Provider-native tool name and input-key aliases now live in the shared registry, so adapters declare canonical tool mapping instead of carrying local lookup tables.

---
## [2026-04-21] Allow multiple parse message selectors

### Added

- Default parse mode now accepts multiple message index/slice positional selectors after the session input, ORs them together, and emits each matching message once in original conversation order.

---
## [2026-04-20] Render Claude away summaries as Recap blocks

### Added

- Claude `type: "system"` entries with `subtype: "away_summary"` now render as `<recap>` blocks with a `# Recap` heading instead of staying hidden.

### Changed

- Recap bodies strip the trailing ` (disable recaps in /config)` suffix before display.

---
## [2026-04-19] Render Claude local command user strings as dedicated command blocks

### Added

- Claude `type: "user"` string content made only of `<command-*>...</command-*>` tags now renders as `<user-command-input>` with a YAML-like code block body derived dynamically from the parsed tags, preserving source line order and relative indentation.
- Claude `type: "user"` string content wrapped in `<local-command-stdout>...</local-command-stdout>` now renders as `<user-command-output>` with the wrapper tags stripped from the visible body.

---
## [2026-04-15] Speed up exact session-id resolution

### Changed

- Exact single-token identifiers are now resolved against the unified supported-session pool by filename/native session id before any summary scan, so PI and Codex ids no longer pay for a Claude-first fallback walk.
- Negative-index metadata scans now run only for real `-N` selectors instead of every identifier lookup.
- `cmd_parse` now resolves the input once and reuses the resolved path for both content loading and metadata emission.

---
## [2026-04-15] Catalog only first session

### Changed

- `ch catalog` now only processes the first session ID it finds in the input (arguments, piped content, or greppable text). This prevents accidentally batch-cataloging many sessions at once.

---
## [2026-04-15] Make search-only-id fully plain

### Changed

- `ch search --only-id` now forces plain output end to end: no Rich color, no pager, and direct stdout printing of session IDs even if `--color always` was passed.
- Tightened the CLI seam and shell coverage so `--only-id --color always` still emits a bare session ID with no ANSI escapes.

---
## [2026-04-15] Add `-p/--provider` filter to search

### Added

- `ch search -p claude|pi|codex` restricts search to sessions from a specific provider. Filtering happens before metadata loading, so unmatched sessions incur no I/O overhead.

---
## [2026-04-15] Add `provider` metadata field

### Added

- `ConversationMetadata` now carries a `provider: Provider` field (`"claude"`, `"pi"`, or `"codex"`), derived from the session's adapter at load time.
- `print_metadata()` emits `provider:` in the YAML frontmatter for both `parse` and `search` output.
- `JsonlSessionAdapter.name` is now typed as `Provider` rather than `str`, giving static protection against unrecognized adapter names.

---
## [2026-04-13] Add search-only-id mode

### Added

- `ch search --only-id` and its `-ll` shorthand now print only matching session IDs, one per line, instead of the full search metadata block.

---
## [2026-04-11] Unify supported-session search space

### Changed

- Negative recent selectors (`-1`, `-2`, ...) now resolve across the same supported-session universe as direct file paths and adapter-backed session IDs, rather than only traversing Claude Code history.
- `ch search` now scans supported Claude Code, Codex, and PI session files through the same shared discovery path used by recency-aware resolution.

---
## [2026-04-05] Add parse-mode role visibility flags

### Added

- Support `--only-user`, `--only-assistant`, `--no-user`, and `--no-assistant` in default parse mode.

### Changed

- Role visibility is now normalized in the CLI before `ConversationFlags` are built, so contradictory `--only-*` combinations warn once, disable impossible extras upstream, and let the parse/render pipeline stay unaware of CLI validity rules.
- `--no-user` hides only regular user text, so explicit tool visibility can still surface user-side tool results.
- `--no-assistant` hides only regular assistant text/plan content, while explicit `--thinking`, `--tools`, and `--agents` can still show assistant-side extras.

---
## [2026-03-08] Add recent negative session selectors

### Added

- Support resolving `-1`, `-2`, ... as globally recent conversation selectors for parse/rename-style conversation resolution.

### Changed

- Extracted a domainless modified-time ordering helper so conversation resolution and `search` share the same oldest→newest ordering behavior.
- Negative recent selectors exclude agent sidechain files.

---
## 2026-01-04 Feat: `-ca,--cafter` and `-ma,--mafter` for Created/Modified After filter

---

## [2026-01-01] Fix: Rich Rendering Bug & Structured Data Refactor

### Fixed

**Thinking/Tools content stripped in colored output**
- **Problem:** `--color=always` output (and default colored output) stripped `<thinking>`, `<tool-input>`, and `<tool-output>` blocks entirely.
- **Root cause:** Rich's Markdown parser treated custom XML tags as unknown HTML and stripped them along with their content.
- **Solution:** Refactored rendering pipeline to separate structure from formatting. `render_messages_with_rich()` now handles tags as explicit `Text` objects and only passes actual message content to `Markdown()`.

### Changed

**Architecture Refactor: Structured Message Parts**
- Replaced `Message.get_visible_content()` (which returned a serialized string) with `Message.iter_visible_parts()` (which yields structured `MessagePart` objects).
- Introduced `MessagePart` and `ToolParts` named tuples for type-safe data flow.
- Tool formatting logic centralized in `tool_to_parts()` (shared by both XML and Rich renderers), preventing implementation drift.

**Resolved Technical Debt**
- Removed "Premature Serialization" debt. JSON output is now clean (no embedded XML tags in content).

---

## [2025-12-29] Support `custom-title` entries

Parse `type: "custom-title"` as `<session-rename>` blocks. Shown by default, searchable.

---

## [2025-12-22] Fix: Conversation Resolution Bugs

### Fixed

**"Not found" misreported as "ambiguous"**
- **Problem:** `_try_resolve_conversation_file()` returned `iter([])` for "not found" case. Since iterators are always truthy in Python, `resolve_conversation_file()` took the "ambiguous" branch even with zero matches.
- **Solution:** Return `[]` (list) instead of `iter([])`. Empty lists are falsy.

**Single-word summary prefix match failing**
- **Problem:** For single-word queries, the function iterated `conversation_files` twice (exact match, then summary prefix). If passed a generator (from `Path.glob()`), the first loop exhausted it.
- **Solution:** Materialize generator with `list(conversation_files)` before iteration.

**Ambiguous input silently treated as raw content**
- **Problem:** `get_input_content()` ignored `ambiguous_matches` return value, falling back to raw content parsing and producing "No messages found" instead of showing ambiguity.
- **Solution:** Check `ambiguous_matches` and exit with error listing matching conversations.

### Changed

**Factored out `extract_summaries_from_content()`**
- `extract_summaries_from_jsonl()` now wraps `extract_summaries_from_content(content: str)`
- `cmd_search()` reuses already-read content instead of re-reading file

### Added

**New test files:**
- `tests/test_resolution.py` - 10 tests for resolution bugs

### User Impact

**Improved error messages** for conversation resolution failures. No changes to CLI syntax or output format.

---

## [2025-12-10] Refactor: Centralized Content Block Handling

**Commits:**
- `d162af9` (2025-12-10 09:27) - Implementation
- `1a55d1b` (2025-12-10 09:36) - Added post-implementation review
- `54fcb6b` (2025-12-11 10:23) - Documentation updates

**Changed files:**
- `skills/chats/scripts/parse.py` (+374 lines, -151 lines)
- `skills/chats/DEVELOPMENT.md` (marked 2 issues resolved)

**New files:**
- `skills/chats/plan.claude.md` (implementation plan)
- `skills/chats/post-plan-implementation-review.md` (critique)

**Unchanged:**
- `skills/chats/SKILL.md` (no user-facing changes)

### Fixed

**Agent messages not displaying with --color flag**
- **Problem:** `render_xml_with_rich()` used regex that only matched `user-message` and `assistant-response` tags. Agent messages were silently skipped in colored output.
- **Root cause:** XML tag knowledge scattered across multiple functions. Renderer out of sync with message formatter.
- **Solution:** New `render_messages_with_rich()` works directly from Message objects, bypassing XML parsing entirely.

### Added

**Content Block Type Registry** (`ContentBlockType` enum, lines 52-63)
- Centralized definition of all 6 XML content block types
- Each type has: xml_tag, header, rich_style
- Single source of truth for message wrappers (user/assistant/agent) and inner blocks (thinking/tool-input/tool-output)

**Tool Schema Registry** (`TOOL_SCHEMAS` dict, lines 75-85)
- Data-driven tool formatting replacing 9 hardcoded `elif` branches
- Each schema defines: attr_keys, content_key, content_lang
- Adding new tool = adding dict entry (was: adding code branch)

**New rendering path** (`render_messages_with_rich()`, lines 955-999)
- Direct Message → Rich console rendering
- Eliminates XML → regex → render anti-pattern
- Recognizes all 6 content block types (old: only 2)

### Changed

**Architectural improvements:**
- Console initialization: `console: Console` → `console: Optional[Console] = None` with lazy init
- Added `get_console()` helper (lines 102-108)
- Added `get_wrapper_type()` method to Message class
- Extracted `_format_edit_content()` helper (lines 168-176)
- Refactored `format_tool_for_xml()` to use TOOL_SCHEMAS registry

**DEVELOPMENT.md updates:**
- [x] Marked `format_tool_for_xml_not_dynamic` resolved
- [x] Marked `render_xml_with_rich_flimsy` resolved
- Added "Random Ideas" section

### User Impact

**None.** This was a structural refactoring with no changes to:
- CLI flags or command syntax
- Output format (XML/JSON structure identical)
- Behavior (except agent message bug fix)
- SKILL.md documentation

### Known Issues

See `post-plan-implementation-review.md` for detailed critique.

**Premature Serialization:**
- `get_visible_content()` returns string with XML tags embedded
- Causes: (1) Rich styling for inner blocks unused, (2) JSON output polluted with XML
- Suggested fix: Return structured blocks instead of serialized string

---

## [2025-12-09] Color Handling Improvements

**Commit:** `2f18e34` (2025-12-09 10:49)

### Fixed
- Conversations color output consistency

---

## [2025-12-08] Console and Style Improvements

**Commits:**
- `c937a55` (2025-12-08 22:03) - Style improvements
- `0d9a169` (2025-12-08 20:55) - Console handling refactor

### Changed
- Centralized color/console handling
- Added `print_error()` utility
- Renamed `parse_raw()` → `parse_raw_cli_transcript()` for clarity
- Changed `List[Path]` → `Iterable[Path]` for better typing
- Batched Rich prints for performance
- Converted to keyword-only args in key functions

---

## [2025-12-07] Code Reuse and Metadata

**Commits:**
- `ed22297` (2025-12-07) - Code reuse improvements
- `843951e` (2025-12-07) - Tool output handling
- `6eceec8` (2025-12-07) - Metadata in YAML frontmatter
- `51ecbdd` (2025-12-07) - Initial commit

### Added
- YAML frontmatter for metadata
- Improved tool output handling (type=text with dict content)

### Changed
- Code reuse refactoring across parsing functions
