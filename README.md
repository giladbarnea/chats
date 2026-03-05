---
name: conversations
description: Format, search, and manage conversation history files from ~/.claude/projects/ directory. Use this skill when users request formatting, converting, or reading .jsonl conversation history files, searching across conversations for specific content, or removing/deleting old conversation sessions. The script extracts user messages and assistant text responses (excluding tool calls by default).
---

# Conversations

> Verified true as of 25-12-22 13PM IST, 1fbb406

## Overview

Format and search Claude Code conversation history files. The `ccc` CLI converts conversation files to readable XML format with markdown rendering and provides powerful search capabilities across all conversations.

**Core functions:**
- **Parse**: Convert conversation history to XML-tagged markdown
- **Search**: Find conversations using regex patterns with rich display
- **Format**: Convert between JSONL and raw transcript formats
- **Remove**: Safely delete conversation sessions and all associated files
- **Rename**: Assign custom titles to conversations for easier discovery
- **Catalog**: AI-powered session cataloging to sessions.yaml files

## When to Use This Skill

Use this skill when the user asks to:
- Format or convert a .jsonl conversation history file
- Parse raw conversation transcripts (with ⏺ and > prefixes)
- Search across all conversations for specific content or patterns
- Find conversations mentioning specific topics
- Export conversation history
- Delete or remove conversation sessions
- Clean up old conversations
- Catalog or organize conversation sessions
- Work with files from `~/.claude/projects/*/` directories

## Commands

### Parse Mode (Default)

Convert conversation files to XML-tagged markdown.

**Input Resolution:**
1. Full file path: `/path/to/conversation.jsonl`
2. Conversation UUID or filename: `b177e4f8-bb24-43e9-8a53-4e064be4457d`
3. Summary text (case-insensitive prefix match): `"Extract PII"`
4. Stdin: `cat file.jsonl | ccc`

Conversations can have multiple summary entries (prepended as conversation evolves), each with a unique `leafUuid` tracking the conversation endpoint. Summary matching searches all summaries in all files.

**Message Slicing:**

Optional second argument uses Python slice notation to select message ranges:

```bash
ccc <id> "1"       # First message only
ccc <id> "-1"      # Last message only
ccc <id> "5:"      # From index 5 to end
ccc <id> "-5:"     # Last 5 messages
ccc <id> ":5"      # First 5 messages
ccc <id> ":-5"     # All but last 5
ccc <id> "2:5"     # Indices 2,3,4
ccc <id> "2:-1"    # Index 2 to before last
ccc <id> "-5:-1"   # 5th from end to before last
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
-T, --thinking       # Include thinking tokens
-t, --tools [SPEC]   # Include tool use/result details. Filter with modifiers:
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
```

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
- Respects content visibility flags (-T, -t, -a, -A)
- Suitable for programmatic processing

**Raw Format:**

Markdown-only output intended for piping into files or other tools.

- If exactly one visible message is output: prints just the message content.
- If multiple messages are output: prints role headers (`# User`, `# Assistant`, etc.) with `---` separators.
- Implies `--no-metadata`.

### Search Mode

Search all conversations using regex patterns.

```bash
ccc search [OPTIONS] <pattern>
```

**Options:**
- `-l`: List mode - show only file paths and metadata
- `-d DIRPATH`: Restrict search to specific directory
- `-ma, --mafter DATE`: Only conversations modified after DATE
- `-ca, --cafter DATE`: Only conversations created after DATE
- `--no-metadata`: Disable outputting metadata frontmatter
- Reuses standard display flags (`-T`, `-t`, `-a`, `-A`) to control match output

**Date formats:** ISO dates (`2024-12-15`, `24-12-15`), with time (`2024-12-15T14:30`, `2024-12-15 14:30:45`), or relative (`1h`, `2d`, `3w`, `4m`, `5y`).

**Examples:**

```bash
ccc search "error message"              # Case-insensitive search
ccc search "implement.*feature"         # Regex pattern
ccc search -l "bug fix"                 # List matching files only
ccc search -d ~/dev/project "feature"   # Filter by directory
ccc search --mafter=1d "TODO"           # Modified in last day
ccc search --mafter=2024-12-01 "deploy" # Modified since Dec 1
ccc search --cafter=1w --mafter=1d "."  # Created last week, modified today
```

**Search Features:**
- Case-insensitive regex (multiline, DOTALL)
- Searches both message content and conversation summaries
- Invalid regex patterns treated as literal strings (like `grep -F`)
- Results sorted by modification time ascending
- Extracts working directory from conversation files
- Full markdown rendering with syntax highlighting

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
- **Session UUID**: `5078a7c7-0646-43cc-9412-7e1454a282b4`

### Catalog Mode

Catalog conversation sessions by upserting entries to a sessions.yaml file.

```bash
ccc catalog [SESSION_IDS OR FILE_PATHS]
```

This command uses an AI model (via the `claudesn` CLI) to analyze conversation sessions and maintain a `sessions.yaml` catalog file. The command reads session content and either creates new entries or updates existing ones with meaningful descriptions organized by date.

**Input Methods:**
- **Direct session IDs**: `ccc catalog 00000000-0000-0000-0000-000000000000`
- **File paths**: `ccc catalog path/to/session.jsonl`
- **Piped input**: `ccc search -ca 1d . -l | ccc catalog`
- **Multiple sessions**: All input methods can handle multiple sessions

**Features:**
- Automatically creates sessions.yaml if it doesn't exist
- Groups sessions by date with `# Mon DD YYYY` comments
- Updates existing session descriptions when new information is added
- Skips sessions already cataloged with the same message count
- Supports an 'ignored' list for empty/meaningless sessions

**Examples:**

```bash
# Catalog a specific session
ccc catalog 5078a7c7-0646-43cc-9412-7e1454a282b4

# Catalog from search results (sessions modified in last day)
ccc search -ca 1d . -l | ccc catalog

# Catalog multiple sessions
ccc catalog session-id-1 session-id-2 path/to/session.jsonl
```

**Note:** This command requires the `claudesn` CLI to be configured in the user's environment.

## Conversation File Structure

Conversations are stored as JSONL files where each line is a JSON entry.

**Entry Types:**

1. **User messages** (`type: "user"`)
   - `message.content`: string or array (can include tool results)
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
   - Subtypes: `local_command`
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

## Integration Points

### `/export` Command

Slash command at `~/.claude/commands/export.md` uses `ccc` for XML export.

**Usage:**
```bash
/export                      # Copy to clipboard (macOS via pbcopy)
/export path/to/output.xml   # Save to file
```

Uses `--color never` flag for plain XML output.

### PreCompact Hook

Auto-exports conversations before compaction (lossy operation).

**Location:** `~/.claude/hooks/export-before-compact.py`
**Config:** `~/.claude/settings.json` → `hooks.PreCompact[0]`
**Output:** `~/.claude/projects/pre-compact/{session_id}-{timestamp}.xml`
**Notifications:** macOS notifications via `osascript`
**Shebang:** `#!/usr/bin/env -S uv run --with=rich python3.11`

Automatically preserves full conversation history before compaction.

Note: when modifying this tool, go over the files associated with the `/export` command and the PreCompact hook to make sure they are still consistent with the changes. `fd` and `rg` around `~/.claude/` for `export`, `hook`, etc.

## Technical Reference

**Location:** `~/dev/conversations` (installed globally as `ccc` via `uv tool install -e .`)

**Dependencies:**
- Python 3.13+
- Rich library (for formatting)

**Key Functions:**
- `extract_summaries_from_jsonl()` - Extract all summary fields from file
- `get_input_content()` - Resolve input from CLI arg, stdin, or conversation ID
- `detect_format()` - Deterministic format detection (first line only)
- `parse_jsonl()` - Parse JSONL conversation files
- `parse_raw_cli_transcript()` - Parse raw CLI transcripts
- `format_to_xml()` - Convert messages to XML format
- `render_messages_with_rich()` - Rich markdown rendering
- `print_metadata()` - Unified metadata output to stderr
- `parse_slice_notation()` - Convert slice strings to indices
- `find_all_conversations()` - Find all .jsonl files in projects
- `extract_cwd_from_jsonl()` - Extract working directory from JSONL
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
- No current solution (complexity vs benefit trade-off)

---

**Random Ideas:**
- This file contains `/plan` mode and interactive user ask tool: `projects/-Users-giladbarnea--claude/c5c0741a-f696-47c2-8337-d1a20de84c7a.jsonl`. Can be interesting to display.
