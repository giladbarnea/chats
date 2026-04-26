# Changelog

All notable changes to the `conversations` skill.

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

- `ccc search -f/--full` now renders every visible message from each matching conversation instead of only the messages that directly matched. Summary-only and custom-title-only hits also render the full visible conversation body in this mode.

### Changed

- Search output modes now distinguish the default matching-message display (`MATCHES`) from full-conversation display (`FULL`), keeping search confirmation separate from result rendering breadth.

---
## [2026-04-25] Share session-pool filters across parse and search

### Added

- Default parse mode now accepts `-d, --dir`, `-ma, --mafter`, and `-ca, --cafter` for recent negative selectors, mirroring `ccc search`. So `ccc -d ~/dev/proj -1` resolves the most recent session whose cwd is under `~/dev/proj`.
- New `PoolFilter` declarative bundle (provider/dir/mafter/cafter) shared by both subcommands; `add_pool_filter_args` installs the same flag group on either parser.

### Changed

- The pre-existing parse `--provider` ignore-with-warning behavior now generalizes to any pool filter — when parse input is not a recent index, the CLI warns and ignores all four flags together.
- Search no longer defines its own `-d / -ma / -ca / -p` block; it composes the same `add_pool_filter_args` group, eliminating duplication.

---
## [2026-04-23] Add parse-only metadata and id modes

### Added

- Default parse mode now accepts `-l, --only-metadata` to emit just the resolved session metadata frontmatter without the conversation body.
- Default parse mode now accepts `-ll, --only-id` to emit just the resolved session ID, matching `ccc search --only-id`.

### Changed

- Parse `--only-id` now forces plain output and disables paging, mirroring the existing search-mode behavior.
- Parse metadata-only output preserves the existing post-slice `messages:` count semantics, so `ccc -l <session> "-1"` reports the sliced visible count rather than the full conversation length.

---
## [2026-04-23] Display fork ancestry metadata when available

### Added

- Metadata frontmatter now emits `forked_from:` when the raw session exposes a fork parent id.
- Codex sessions populate this field from `session_meta.payload.forked_from_id`; sessions without fork ancestry omit the field entirely.

---
## [2026-04-23] Add provider-scoped parse recent selectors

### Added

- Default parse mode now accepts `-p, --provider claude|pi|codex` for recent negative selectors, so commands like `ccc -p codex -1` resolve the newest Codex session instead of the newest session overall.

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

- `ccc catalog` now only processes the first session ID it finds in the input (arguments, piped content, or greppable text). This prevents accidentally batch-cataloging many sessions at once.

---
## [2026-04-15] Make search-only-id fully plain

### Changed

- `ccc search --only-id` now forces plain output end to end: no Rich color, no pager, and direct stdout printing of session IDs even if `--color always` was passed.
- Tightened the CLI seam and shell coverage so `--only-id --color always` still emits a bare session ID with no ANSI escapes.

---
## [2026-04-15] Add `-p/--provider` filter to search

### Added

- `ccc search -p claude|pi|codex` restricts search to sessions from a specific provider. Filtering happens before metadata loading, so unmatched sessions incur no I/O overhead.

---
## [2026-04-15] Add `provider` metadata field

### Added

- `ConversationMetadata` now carries a `provider: Provider` field (`"claude"`, `"pi"`, or `"codex"`), derived from the session's adapter at load time.
- `print_metadata()` emits `provider:` in the YAML frontmatter for both `parse` and `search` output.
- `JsonlSessionAdapter.name` is now typed as `Provider` rather than `str`, giving static protection against unrecognized adapter names.

---
## [2026-04-13] Add search-only-id mode

### Added

- `ccc search --only-id` and its `-ll` shorthand now print only matching session IDs, one per line, instead of the full search metadata block.

---
## [2026-04-11] Unify supported-session search space

### Changed

- Negative recent selectors (`-1`, `-2`, ...) now resolve across the same supported-session universe as direct file paths and adapter-backed session IDs, rather than only traversing Claude Code history.
- `ccc search` now scans supported Claude Code, Codex, and PI session files through the same shared discovery path used by recency-aware resolution.

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
- `skills/conversations/scripts/parse.py` (+374 lines, -151 lines)
- `skills/conversations/DEVELOPMENT.md` (marked 2 issues resolved)

**New files:**
- `skills/conversations/plan.claude.md` (implementation plan)
- `skills/conversations/post-plan-implementation-review.md` (critique)

**Unchanged:**
- `skills/conversations/SKILL.md` (no user-facing changes)

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
