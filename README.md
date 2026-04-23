---
name: conversations
description: Format, search, and manage supported AI CLI conversation history files from Claude Code, Codex, and PI JSONL session directories. Use this skill when users request formatting, converting, or reading .jsonl conversation history files, searching across sessions for specific content, or removing/deleting old Claude conversation sessions. The script extracts user messages and assistant text responses (excluding tool calls by default).
---

# Conversations

> Verified true as of 26-04-16, working tree after 3cd8c1b

## Overview

Format and search supported AI CLI conversation history files. The `ccc` CLI converts session files to readable XML format with markdown rendering and provides powerful search capabilities across Claude Code, Codex, and PI sessions.

**Core functions:**
- **Parse**: Convert conversation history to XML-tagged markdown
- **Fork**: Duplicate a session into a thinner resumable copy
- **Search**: Find conversations using regex patterns with rich display
- **Format**: Convert between JSONL and raw transcript formats
- **Remove**: Safely delete conversation sessions and all associated files
- **Rename**: Assign custom titles to conversations for easier discovery
- **Catalog**: AI-powered session cataloging to sessions.yaml files

## When to Use This Skill

Use this skill when the user asks to:
- Format or convert a .jsonl conversation history file
- Parse raw conversation transcripts (with ⏺ and > prefixes)
- Search across all supported sessions for specific content or patterns
- Find conversations mentioning specific topics
- Export conversation history
- Delete or remove conversation sessions
- Clean up old conversations
- Catalog or organize conversation sessions
- Work with files from `~/.claude/projects/*/`, `~/.codex/sessions/**`, or `~/.pi/agent/sessions/**`

## Commands

### Parse Mode (Default)

Convert conversation files to XML-tagged markdown.

**Input Resolution:**
1. Full file path: `/path/to/conversation.jsonl`
2. Recent negative index: `-1` (most recently modified supported session), `-2`, ...
3. Conversation/session ID or filename: `b177e4f8-bb24-43e9-8a53-4e064be4457d`
4. Summary text (case-insensitive prefix match): `"Extract PII"`
5. Stdin: `cat file.jsonl | ccc`

Negative recent indices use the same global modified-time ordering as `ccc search` across Claude, PI, and Codex sessions: oldest first, newest last, so `-1` means “the newest supported session”. Claude agent sidechain files are excluded from this selector.
Use `-p, --provider claude|pi|codex` with a negative recent index to restrict that recency lookup to one provider, for example `ccc -p codex -1`. Provider filtering applies only when the first positional parse argument is a recent index; with session IDs, paths, summaries, or stdin, the CLI warns and ignores the flag.
Single-token identifiers are matched against that same unified supported-session pool by exact filename/native session id before any summary scan, so PI and Codex session ids resolve directly without a separate provider-specific fallback pass.

Conversations can have multiple summary entries (prepended as conversation evolves), each with a unique `leafUuid` tracking the conversation endpoint. Summary matching searches all summaries in all files.

**Message Slicing:**

Optional second-and-later positional arguments use Python slice notation to select message ranges. Multiple selectors are ORed: each message matching any selector is included once in original conversation order.

```bash
ccc -1              # Most recently modified supported session
ccc -2              # Second most recently modified supported session
ccc -l -1           # Metadata only for the newest supported session
ccc -ll -1          # Only the newest supported session id
ccc <id> "1"       # First message only
ccc <id> "-1"      # Last message only
ccc <id> "5:"      # From index 5 to end
ccc <id> "-5:"     # Last 5 messages
ccc <id> ":5"      # First 5 messages
ccc <id> ":-5"     # All but last 5
ccc <id> "2:5"     # Indices 2,3,4
ccc <id> "2:-1"    # Index 2 to before last
ccc <id> "-5:-1"   # 5th from end to before last
ccc <id> "1" "2"   # First and second messages
ccc <id> "1:7" "-2" "8:-3"
```

**Format Detection:**

Automatically detects input format by examining **first non-empty line only** (deterministic, not heuristic):
- **JSONL**: Line contains valid JSON with `type` field
- **Raw transcript**: Line has `> ` or `⏺ ` CLI prefix

**Display Options:**

```bash
--color auto     # Default: Rich format in terminal, plain when piped
--color always   # Force Rich formatting (pipe to less -R)
--color never    # Plain output only

--paging         # Force use of a pager (e.g. less)
--no-paging      # Disable pager

-f, --format FORMAT  # Output format: xml (default), json, or raw
-r, --raw            # Alias for: -f raw (implies --no-metadata)
--no-metadata        # Disable outputting metadata frontmatter
-l, --only-metadata  # Show only metadata frontmatter (no conversation body)
-ll, --only-id       # Show only the resolved session ID (implies --color never and --no-paging)
-p, --provider PROVIDER
                    # Restrict recent-index lookup to claude, pi, or codex
-T, --thinking       # Include thinking tokens
--only-user          # Show only regular user messages
--only-assistant     # Show only regular assistant messages
--no-user            # Hide regular user messages
--no-assistant       # Hide regular assistant messages
-t, --tools [SPEC]*  # Include tool use/result details. Filter with modifiers:
                     #   Name:    -t Bash, -t Read, -t !Bash (exclude)
                     #   Direction: -t i (inputs), -t o (outputs), -t Bash:i
                     #   Error:   -t e (errors only), -t Bash:e
                     #   Short:   -t s (shorten), -t Read:o:s
                     #   Combine: -t "Read:o:s Bash:i" or -t Read:o:s -t Bash:i
                     #   Order-free: -t i:Bash == -t Bash:i
                     #   Long form: -t input, -t output, -t short, -t error
-a, --agents         # Include subagent messages
-A, --all            # Show everything (thinking, tools, agents)
--no-plans           # Hide plan content (ExitPlanMode) - shown by default
-s, --short          # Shorten string values in output (width=40)

-o FILE          # Save output to file

* SPEC: Read TOOL_SPEC.md for complete and formal definition.
```

`--only-metadata` and `--only-id` require a resolved session/file-backed input. Raw stdin/content has no stable session identity to report.

`--only-user` and `--only-assistant` take precedence over `--thinking`, `--tools`, `--agents`, and `--all`. When combined, the CLI emits a warning, disables the contradictory extras immediately, and continues with the normalized flags. `--only-user --only-assistant` is also warned about; it is allowed to fall through to an empty result naturally.

`--no-user` and `--no-assistant` hide only the regular default text for that role. Explicit extras still work with them. For example, `ccc --no-user --tools ...` still shows tool outputs from user turns, and `ccc --no-assistant --thinking --tools --agents ...` still shows assistant-side thinking, tools, and agent messages.

Metadata frontmatter emits `forked_from:` only when the raw session exposes a fork parent id. Sessions without that data omit the field entirely.

**Output Formats:**

**XML Format (default):**

Metadata frontmatter (optional), XML to stdout, separated by `---`:

```xml
<user-message i="1" isMeta="true" sourceToolUserId="a1b2">
{user message text}
</user-message>

---

<assistant-response i="2">
{assistant text response}
</assistant-response>
```

Rich mode renders markdown with syntax highlighting and auto-dedenting.

**JSON Format:**

JSON array to stdout (no metadata; always valid JSON):

```json
[
  {
    "content": "User message text",
    "role": "user"
  },
  {
    "content": "Assistant response text",
    "role": "assistant"
  }
]
```

JSON format:
- Always outputs plain JSON (no Rich formatting)
- Only includes text content from user/assistant messages
- Respects parse-mode visibility flags (`--only-user`, `--only-assistant`, `--no-user`, `--no-assistant`, `-T`, `-t`, `-a`, `-A`)
- Suitable for programmatic processing

**Raw Format:**

Markdown-only output intended for piping into files or other tools.

- If exactly one visible message is output: prints just the message content.
- If multiple messages are output: prints role headers (`# User`, `# Assistant`, etc.) with `---` separators.
- Implies `--no-metadata`.

### Search Mode

Search all supported sessions using regex patterns against visible rendered message content, summaries, and custom titles.

```bash
ccc search [OPTIONS] <pattern>
```

**Options:**
- `-l`: List mode - show only file paths and metadata
- `-ll`, `--only-id`: Show only matching session IDs (implies `--color never` and `--no-paging`)
- `-p, --provider claude|pi|codex`: Restrict search to sessions from a specific provider
- `-d DIRPATH`: Restrict search to specific directory
- `-ma, --mafter DATE`: Only conversations modified after DATE
- `-ca, --cafter DATE`: Only conversations created after DATE
- `--no-metadata`: Disable outputting metadata frontmatter
- Reuses standard display flags (`-T`, `-t`, `-a`, `-A`, `--no-plans`) to control both what counts as a match and what gets rendered

**Date formats:** ISO dates (`2024-12-15`, `24-12-15`), with time (`2024-12-15T14:30`, `2024-12-15 14:30:45`), or relative (`1h`, `2d`, `3w`, `4m`, `5y`).

**Examples:**

```bash
ccc search "error message"              # Case-insensitive search
ccc search "implement.*feature"         # Regex pattern
ccc search -l "bug fix"                 # List matching files only
ccc search -ll "bug fix"                # Print only matching session IDs
ccc search -d ~/dev/project "feature"   # Filter by directory
ccc search --mafter=1d "TODO"           # Modified in last day
ccc search --mafter=2024-12-01 "deploy" # Modified since Dec 1
ccc search --cafter=1w --mafter=1d "."  # Created last week, modified today
ccc search -p claude "bug fix"          # Search only Claude sessions
ccc search -p codex "TODO"              # Search only Codex sessions
```

**Search Features:**
- Case-insensitive regex (multiline, DOTALL)
- Searches visible rendered message content, conversation summaries, and custom titles
- Visibility flags affect search semantics: hidden thinking/tools/agents/plans do not count as matches
- `-a` changes the search universe itself by including Claude sidechain agent sessions
- Invalid regex patterns treated as literal strings (like `grep -F`)
- Plain-literal queries get a cheap candidate prefilter before the normal rendered-content confirmation pass
- Results sorted by modification time ascending across Claude, PI, and Codex sessions
- Extracts working directory from conversation files
- Full markdown rendering with syntax highlighting

### Fork Mode

Create a new supported session file that keeps only the parts of the conversation you want to carry forward.

```bash
ccc fork [OPTIONS] <session>
```

`fork` resolves the input session the same way parse does for file paths, recent negative indices, session identifiers, and summary prefixes, then writes a new native session file back to disk. The fork keeps the original ecosystem’s on-disk format:

- Claude forks become new `~/.claude/projects/.../<session-id>.jsonl` files
- Codex forks keep their `rollout-...-<session-id>.jsonl` filename shape
- PI forks keep their timestamp-prefixed `<timestamp>_<session-id>.jsonl` filename shape

By default, `fork` strips thinking, tool payloads, and Claude sidechains, which makes the new session much smaller than the original transcript. You can opt content back in with the same visibility knobs as parse:

```bash
ccc fork -1
ccc fork -t session-id
ccc fork -T short -t Read:o:s -t Bash:i session-id
ccc fork -A session-id
```

**Options:**
- `-T, --thinking [full|short]`: Include thinking content, optionally shortened
- `-t, --tools [SPEC]`: Include tool use/result content, with the same filter syntax as parse
- `-a, --agents`: Include Claude sidechain agent sessions and keep Task linkage intact
- `-A, --all`: Include thinking, tools, and agents

**Display:**
- File paths: cyan bold
- Metadata: dim gray
- Message indices: green
- User messages: blue, assistant: yellow
- 4-space indented content

### Rm Mode

Remove a conversation session and all associated files.

```bash
ccc rm [OPTIONS] <session>
```

**What Gets Removed:**
1. Main conversation file: `projects/{project}/{session_id}.jsonl`
2. Agent files: `projects/{project}/agent-*.jsonl` (matching sessionId)
3. Directories:
   - `file-history/{session_id}/`
   - `projects/{project}/{session_id}/`
   - `session-env/{session_id}/`
4. Files:
   - `debug/{session_id}.txt`
   - `todos/{session_id}-agent-{session_id}.json`
5. History entries: Lines in `history.jsonl` with matching sessionId

**Session Resolution:**
- **Direct file path**: `/path/to/session.jsonl`
- **Session UUID**: `5078a7c7-0646-43cc-9412-7e1454a282b4`

**Options:**
- `-n, --dry-run`: Preview what would be removed without prompting for confirmation

**Examples:**

```bash
# Remove by UUID (shows preview, then prompts for confirmation)
ccc rm 5078a7c7-0646-43cc-9412-7e1454a282b4

# Remove by file path (shows preview, then prompts for confirmation)
ccc rm ~/.claude/projects/my-project/session-id.jsonl

# Dry run - preview only, no confirmation prompt
ccc rm -n session-uuid
```

**Safety Features:**
- Automatic dry run preview before removal
- Interactive confirmation prompt: "Proceed with removal? [y/n]"
- Dry run mode (`-n`) for safe preview without any risk of removal
- Defensive existence checks - missing files don't cause errors
- Clear summary of removed items after execution

### Rename Mode

Rename a conversation by appending a custom title entry.

```bash
ccc rename <session> "New Title"
```

This mutates the conversation file by appending `custom-title` and `agent-name` entries and updates the global `history.jsonl` file.

**Session Resolution:**
- **Direct file path**: `/path/to/session.jsonl`
- **Recent negative index**: `-1`, `-2`, ... across the unified supported-session space
- **Session UUID**: `5078a7c7-0646-43cc-9412-7e1454a282b4`

### Catalog Mode

Catalog conversation sessions by upserting entries to a sessions.yaml file.

```bash
ccc catalog [SESSION_IDS OR FILE_PATHS]
```

This command uses an AI model (via the `claude` CLI) to analyze conversation sessions and maintain a `sessions.yaml` catalog file. The command reads session content and either creates new entries or updates existing ones with meaningful descriptions organized by date.

**Input Methods:**
- **Direct session IDs**: `ccc catalog 00000000-0000-0000-0000-000000000000`
- **File paths**: `ccc catalog path/to/session.jsonl`
- **Piped input**: `ccc search -ca 1d . -l | ccc catalog`
- **Multiple sessions**: Accepts multiple sessions but **only catalogs the first one found**.

**Features:**
- Automatically creates sessions.yaml if it doesn't exist
- Groups sessions by date with `# Mon DD YYYY` comments
- Updates existing session descriptions when new information is added
- Skips sessions already cataloged with the same message count
- Supports an 'ignored' list for empty/meaningless sessions

**Examples:**
- Catalog a specific session: `ccc catalog 5078a7c7-0646-43cc-9412-7e1454a282b4`
- Catalog from search results (uses only first result): `ccc search -ca 1d . -l | ccc catalog`
- Catalog from multiple IDs (uses only first ID): `ccc catalog id1 id2`

**Note:** This command requires the `claude` CLI to be configured in the user's environment.

## Conversation File Structure

Conversations are stored as JSONL files where each line is a JSON entry.

**Entry Types:**

1. **User messages** (`type: "user"`)
   - `message.content`: string or array (can include tool results)
   - Claude string content made only of `<command-*>...</command-*>` tags renders as `<user-command-input>` with a YAML-like code block body derived dynamically from those tags, preserving source line order and relative indentation
   - Claude string content wrapped in `<local-command-stdout>...</local-command-stdout>` renders as `<user-command-output>` with the wrapper tags stripped
   - Common fields: `cwd`, `sessionId`, `version`, `gitBranch`, `uuid`, `parentUuid`, `timestamp`

2. **Assistant messages** (`type: "assistant"`)
   - `message.content[]`: Array containing:
     - `{type: "text", text: "..."}` - shown by default
     - `{type: "thinking", thinking: "..."}` - hidden by default (use `-T`), renders as `<thinking>`
     - `{type: "tool_use", ...}` - hidden by default (use `-t`), renders as `<tool-input name="...">`
     - `{type: "tool_use", name: "ExitPlanMode", input: {plan: "..."}}` - shown by default (use `--no-plans` to hide)
     - `{type: "tool_result", ...}` - hidden by default (use `-t`), renders as `<tool-output>`
     - `{type: "image", ...}` - skipped (not rendered)

3. **System messages** (`type: "system"`)
   - Short XML-like command logging: `<command-name>/bashes</command-name>`
   - `subtype: "away_summary"` renders as a visible `<recap>` block with the trailing ` (disable recaps in /config)` hint stripped from the body
   - Other subtypes like `local_command` stay hidden
   - 68-132 chars typical length

4. **File history snapshots** (`type: "file-history-snapshot"`)
   - Skipped (not rendered)
   - Track which files Claude is editing during conversation
   - `trackedFileBackups`: metadata for backups (actual content stored separately)
   - Format: `{backupFileName: "hash@v1", version: 1, backupTime: "..."}`
   - Used for undo/history/crash recovery

5. **Summary entries** (`type: "summary"`)
   - Skipped by parse mode (not rendered)
   - Multiple summaries per file (prepended as conversation evolves)
   - `leafUuid`: unique identifier for conversation endpoint (often doesn't match any message UUID)
   - Summary text used for conversation matching

6. **Custom title entries** (`type: "custom-title"`)
   - Rendered as `<session-rename>` with header `# Renamed Session`
   - `customTitle`: The renamed session title text
   - Searchable in search mode

**Agent/Subagent Conversations:**
- Hidden by default (use `-a` or `--agents` to show)
- Dispatched via `Task` tool with `subagent_type` (e.g., "Explore", "codebase-analyzer:single-subsystem")
- Stored separately as `agent-{shortId}.jsonl` (e.g., `agent-51c28bca.jsonl`)
- Same structure as main conversations
- Include `agentId` field and `isSidechain: true` at entry level
- Agent messages render as `<agent agent_id="..." subagent_type="...">`
- Tool results from agents include `agentId: xxx (for resuming...)` in content

## Technical Reference

**Location:** `~/dev/conversations` (installed globally as `ccc` via `uv tool install -e .`)

**Dependencies:**
- Python 3.13+
- Rich library (for formatting)

**Key Functions:**
- `extract_summaries_from_jsonl()` - Extract all summary fields from file
- `SessionPool.discover()` - Build the unified supported-session inventory for one invocation
- `SessionScan.from_content()` - Decode one session once into search facets and visible messages
- `get_input_content()` - Resolve input from CLI arg, stdin, or conversation/session ID
- `detect_format()` - Deterministic format detection (first line only)
- `parse_jsonl()` / `parse_jsonl_entries()` - Parse JSONL conversation files
- `parse_raw_cli_transcript()` - Parse raw CLI transcripts
- `format_to_xml()` - Convert messages to XML format
- `render_messages_with_rich()` - Rich markdown rendering
- `print_metadata()` - Unified metadata output to stderr
- `parse_slice_notation()` - Convert slice strings to indices
- `find_all_supported_session_files()` - Find all supported Claude, PI, and Codex session files
- `sort_by_modified()` - Domainless oldest→newest ordering helper for recency-aware flows
- `extract_cwd_from_jsonl()` / `extract_cwd_from_entries()` - Extract working directory from JSONL
- `cmd_search()` - Search with rich display
- `cmd_rm()` - Remove session and all associated files
- `display_search_result()` - Rich console output for search

**Error Handling:**
- Gracefully handles malformed JSON
- Validates file paths and regex patterns
- Falls back to literal string matching for invalid regex
- Clear error messages for missing files

**Known Edge Cases:**
- Message content with markdown (backticks, etc.) renders differently in display vs source
- Searching rendered text won't match source formatting
- Search candidate prefiltering only applies to plain-literal queries; render-dependent queries still fall through to the full rendered-content matcher
- No current solution (complexity vs benefit trade-off)

---

**Random Ideas:**
- This file contains `/plan` mode and interactive user ask tool: `projects/-Users-giladbarnea--claude/c5c0741a-f696-47c2-8337-d1a20de84c7a.jsonl`. Can be interesting to display.
