# Chats

> Verified true as of 26-06-19, working tree after d1992c0

## Overview

Format and search supported AI CLI conversation history files. The `ch` CLI converts session files to readable XML format with markdown rendering and provides powerful search capabilities across Claude Code, Codex, PI, and Antigravity CLI sessions.

**Core functions:**
- **Parse**: Convert conversation history to XML-tagged markdown
- **Search**: Find conversations using regex patterns with rich display
- **Format**: Convert between JSONL and raw transcript formats
- **Remove**: Safely delete conversation sessions and all associated files
- **Name**: Assign custom titles to conversations for easier discovery
- **Catalog**: AI-powered session cataloging to sessions.yaml files
- **Info**: Aggregate per-session statistics (tokens, cost, durations, message counts) for Claude and PI

## When to Use

Use `ch` when you want to:
- Format or convert a .jsonl conversation history file
- Parse raw conversation transcripts (with ⏺ and > prefixes)
- Search across all supported sessions for specific content or patterns
- Find conversations mentioning specific topics
- Export conversation history
- Delete or remove conversation sessions
- Clean up old conversations
- Catalog or organize conversation sessions
- Work with files from `~/.claude/projects/*/`, `~/.codex/sessions/**`, `~/.pi/agent/sessions/**`, or `~/.gemini/antigravity-cli/brain/*/.system_generated/logs/`

## Commands

### Parse Mode (Default)

Convert conversation files to XML-tagged markdown.

**Input Resolution:**
1. Full file path: `/path/to/conversation.jsonl`
2. Recent negative index: `-1` (most recently modified supported session), `-2`, ...
3. Conversation/session ID or filename: `b177e4f8-bb24-43e9-8a53-4e064be4457d`
4. Current session name/title (case-insensitive substring match, latest title only): `"patch endpoint"`
5. Summary text (case-insensitive prefix match): `"Extract PII"`
6. Stdin: `cat file.jsonl | ch`

Negative recent indices resolve across the unified Claude/PI/Codex/Antigravity session pool using the last in-band JSONL timestamp, so `-1` means “the newest supported session by transcript content”. If a session has no readable timestamp, it falls back to filesystem mtime for ordering. Claude agent sidechain files are excluded from this selector.
The same session-pool filters used by `ch search` also narrow the recent-index lookup: `-p, --provider claude|pi|codex|antigravitycli`, `-d, --dir DIR`, `-ma, --mafter DATE`, and `-ca, --cafter DATE`. For example, `ch -p codex -1` resolves the newest Codex session, and `ch -d ~/dev/proj -1` resolves the most recent session whose cwd exactly matches `~/dev/proj`. Recent-index resolution uses cheap timestamp and cwd probes instead of eagerly loading full metadata for the whole pool. These filters apply only when the first positional parse argument is a recent index; with session IDs, paths, summaries, or stdin, the CLI warns and ignores them.
Single-token identifiers are matched against that same unified supported-session pool by exact filename/native session id before any title/summary scan, so PI, Codex, and Antigravity session ids resolve directly without a separate provider-specific fallback pass. If exact-id resolution misses, `ch` scans each session's latest title for a case-insensitive substring match before falling back to summary-prefix matching.

Conversations can have multiple summary entries (prepended as conversation evolves), each with a unique `leafUuid` tracking the conversation endpoint. Summary matching searches all summaries in all files.

**Message Slicing:**

Optional second-and-later positional arguments use Python slice notation to select message ranges. Multiple selectors are ORed: each message matching any selector is included once in original conversation order.

```bash
ch -1              # Most recently modified supported session
ch -2              # Second most recently modified supported session
ch -l -1           # Metadata only for the newest supported session
ch -ll -1          # Only the newest supported session id
ch <id> "1"       # First message only
ch <id> "-1"      # Last message only
ch <id> "5:"      # From index 5 to end
ch <id> "-5:"     # Last 5 messages
ch <id> ":5"      # First 5 messages
ch <id> ":-5"     # All but last 5
ch <id> "2:5"     # Indices 2,3,4
ch <id> "2:-1"    # Index 2 to before last
ch <id> "-5:-1"   # 5th from end to before last
ch <id> "1" "2"   # First and second messages
ch <id> "1:7" "-2" "8:-3"
```

**Format Detection:**

Automatically detects input format by examining **first non-empty line only** (deterministic, not heuristic):
- **JSONL**: Line contains valid JSON with `type` field
- **Raw transcript**: Line has `> ` or `⏺ ` CLI prefix

For JSONL, provider resolution checks the native file path first. External files then require a recognized first object: Codex uses `type: "session_meta"`; PI uses `type: "session"` with an integer `version`. Other external JSONL files fail instead of being assumed to be Claude. Claude files are recognized through their native `~/.claude/projects/` path because Claude has no stable first-object signature.

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
-d, --dir DIR        # Restrict recent-index lookup to sessions whose cwd exactly matches DIR
-ma, --mafter DATE   # Restrict recent-index lookup to sessions modified after DATE
-ca, --cafter DATE   # Restrict recent-index lookup to sessions created after DATE
-T, --thinking       # Include thinking tokens
--only-user          # Show only regular user messages
--only-assistant     # Show only regular assistant messages
--no-user            # Hide regular user messages
--no-assistant       # Hide regular assistant messages
-t, --tools [SPEC]*  # Include tool use/result details. Filter with modifiers:
                     #   Name:    -t Bash, -t Read, -t !Bash (exclude)
                     #   Aliases: -t exec_command, -t shell_command, -t run_command
                     #   Direction: -t i (inputs), -t o (outputs), -t Bash:i
                     #   Error:   -t e (errors only), -t Bash:e
                     #   Short:   -t s (fixed 500), -t s=p, -t Read:o:s=p=80
                     #   Combine: -t "Read:o:s Bash:i" or -t Read:o:s -t Bash:i
                     #   Order-free: -t i:Bash == -t Bash:i
                     #   Long form: -t input, -t output, -t short, -t error
-a, --agents         # Include subagent messages and Pi agent custom records
-b, --branches       # Include abandoned (rewound) branch messages, tagged branch="N"
-A, --all            # Include thinking, tools, agents, plans, and visible Pi custom records
--plans              # Show plan content (ExitPlanMode)
-s, --short [SHORT_SPEC]  # Shorten string values; supports fixed and progressive limits

-o FILE          # Save output to file
```

See [SHORT_SPEC.md](SHORT_SPEC.md) for shortening values and [TOOL_SPEC.md](TOOL_SPEC.md) for complete tool-filter syntax.

`--only-metadata` and `--only-id` require a resolved session/file-backed input. Raw stdin/content has no stable session identity to report.

`--only-user` and `--only-assistant` take precedence over `--thinking`, `--tools`, `--agents`, `--plans`, and `--all`. When combined, the CLI emits a warning, disables the contradictory extras immediately, and continues with the normalized flags. `--only-user --only-assistant` is also warned about; it is allowed to fall through to an empty result naturally.

`--short` accepts a fixed limit such as `128`, progressive mode with `p` or `progressive`, or progressive mode with a final limit such as `p=128` or `progressive=128`. Progressive mode gives early qualifying messages smaller limits and the final one the full limit. A bare `--short` remains fixed at 500. Tool-local `:s` and `:short` accept the same values; a bare local modifier inherits the global policy.

```bash
ch <id> --short                  # Fixed 500
ch <id> --short=p                # Progressive, ending at 500
ch <id> --short=progressive=128  # Progressive, ending at 128
ch <id> -t Read:o:s=p            # Progressive Read outputs
ch <id> --short=p=128 -t:s       # Tools inherit the global policy
```

Detached parsing keeps legacy message selectors after the input. `ch <id> -s 7` and `ch <id> -s 32:64` mean bare fixed-500 shortening plus that selector. Attached `--short=<value>` forms are strict.

`--no-user` and `--no-assistant` hide only the regular default text for that role. Explicit extras still work with them. For example, `ch --no-user --tools ...` still shows tool outputs from user turns, and `ch --no-assistant --thinking --tools --agents ...` still shows assistant-side thinking, tools, and agent messages. Claude `isMeta=true` user messages are treated as tool-adjacent protocol noise and stay hidden unless `--tools` is enabled.

Metadata frontmatter emits `forked_from:` only when the raw session exposes a fork parent id. Sessions without that data omit the field entirely.

**Output Formats:**

**XML Format (default):**

Plain XML sends optional metadata frontmatter to stderr and the conversation body to stdout. Colored terminal output uses a session title instead. XML messages are separated by `---`:

```xml
<user-message i="1">
{user message text}
</user-message>

---

<assistant-response i="2">
{assistant text response}
</assistant-response>
```

In a terminal, colored output drops the XML tags and renders each message as its own rounded panel titled with a colored role badge (role hue, index, and model): the body is markdown with syntax highlighting, thinking appears under a `✻ thinking` marker, and tools render as tag-free `⏺` call / `⎿` result headers over a colored left rail (an Edit shows a unified diff; a Read result is syntax-highlighted by file extension). The XML tags are kept only in plain output (`--color=never`, `-f raw`) — the form meant for piping into tools or LLMs.

**JSON Format:**

JSON array to stdout (no metadata; always valid JSON):

```json
[
  {
    "type": "user-message",
    "role": "user",
    "original_index": 1,
    "content": [
      "User message text"
    ],
    "timestamp": "2026-07-17T12:34:56.789Z"
  },
  {
    "type": "assistant-response",
    "role": "assistant",
    "original_index": 2,
    "model": "sonnet-4-6",
    "content": [
      "Assistant response text",
      {
        "type": "tool-input",
        "name": "Bash",
        "id": "abcd",
        "command": "git status",
        "workdir": "/tmp"
      }
    ],
    "timestamp": "2026-07-17T12:35:01.234Z"
  }
]
```

JSON format:
- Always outputs plain JSON (no Rich formatting)
- Mirrors the structured message model instead of embedding XML wrappers into strings
- Each message carries its wrapper tag as `type` plus any XML-attribute metadata such as `original_index`, `model`, `agent_id`, or `sourceToolUserId`
- Messages carry their raw ISO `timestamp` when present; custom and agent messages preserve `custom_type`, `inherited_context`, `status`, and optional agent identity metadata across a round trip
- `content` is an ordered array of raw strings and typed blocks like `thinking`, `tool-input`, and `tool-output`
- Tool blocks expose structured fields instead of XML tags / fenced pseudo-content
- Raw text that happens to contain XML-like strings stays a plain string value
- Respects parse-mode visibility flags (`--only-user`, `--only-assistant`, `--no-user`, `--no-assistant`, `-T`, `-t`, `-a`, `-A`)
- Suitable for programmatic processing

**Raw Format:**

Markdown-only output intended for piping into files or other tools.

- If exactly one visible message is output: prints just the message content.
- If multiple messages are output: prints role headers (`# User`, `# Assistant`, etc.) with `---` separators.
- Implies `--no-metadata`.

### Convert Structured JSON and XML-tagged Markdown

`ch parse` converts the two provider-free parse representations in either direction. It accepts a file or stdin:

```bash
ch "$SESSION_ID" -t:s --agents -f json > session.json
ch parse session.json > session.md
ch parse -f json session.md > canonical.json
cat canonical.json | ch parse > session.md
```

The default direction rebuilds plain XML-tagged Markdown from structured JSON. `-f json` reverses canonical XML-tagged Markdown into structured JSON. Once XML has been canonicalized to JSON, both `JSON → XML → JSON` and `XML → JSON → XML` compositions are byte-stable. Visibility decisions—including tool inclusion, shortening, and merged agent messages—are already baked into either representation; `ch parse` does not reapply them or discover a session provider.

The XML representation intentionally carries less information than the structured JSON emitted directly from a native session. XML dates have minute precision, tool IDs are shortened, schema-irrelevant tool fields are omitted, attribute values are strings, and tool outputs are rendered text. XML-to-JSON conversion preserves everything represented in XML and canonicalizes those lossy fields; it does not invent the discarded native values. For custom messages, canonical XML escapes wrapper metadata. Delimiter-like message text and typed-block bodies use reversible HTML transport encoding, which `ch parse` decodes.

The command writes only the conversation body to stdout and emits no session metadata frontmatter. Ordinary session parsing may send optional YAML frontmatter to stderr, but neither transport representation contains enough session-level information to reconstruct it.

### Search Mode

Search all supported sessions using regex patterns against visible rendered message content, summaries, and the latest current custom title.

```bash
ch search [OPTIONS] <pattern>
```

**Boolean operators:**

Patterns may combine terms with uppercase `AND` / `OR` / `NOT`, evaluated per session: each term may match anywhere in the session (different messages, a summary, or the current title). `AND` binds tighter than `OR`; parentheses group.

```bash
ch search 'docker AND timeout'                  # Session must contain both terms
ch search 'docker OR podman'                    # Session contains either term
ch search 'deploy AND (staging OR prod)'        # Compound grouping
ch search 'alpha AND bravo AND charlie'         # Term chains
ch search '"hello world" AND foo'               # Quote multi-word terms
ch search 'docker NOT timeout'                  # Session has docker but not timeout
ch search '"hello world" NOT goodbye NOT earth' # Multiple exclusions
```

`NOT` excludes sessions matching the negated term: `foo NOT bar` matches sessions containing `foo` where `bar` does not appear in any visible facet. Multiple `NOT` terms are ANDed. `NOT` cannot be mixed with `AND`/`OR` in the same query; parentheses are not supported with `NOT`.

Once an uppercase operator is present, every multi-word or regex-shaped term must be quoted (`"..."` or `'...'`): `ch search 'hello world AND foo'` is an error. Operator recognition is exact: only `AND`, `OR`, and `NOT` are syntax. Lowercase and mixed-case words stay inside one regex pattern, so `hello world and foo`, `black AnD white`, and `deploy-(prod|staging)` remain single patterns. Malformed boolean queries (unquoted multi-word terms, dangling operators, unbalanced parens) exit with code 2.

**Options:**
- `-l`: List mode - show only file paths and metadata
- `-ll`, `--only-id`: Show only matching session IDs (implies `--color never` and `--no-paging`)
- `-f`, `--full`: Show entire matching conversations instead of only matching messages
- `-r`, `--raw`: Render search results as plain markdown (implies `--no-metadata`, `--color never`, and `--no-paging`)
- `-s`, `--case-sensitive`: Match letter case exactly (default: false)
- `-i`, `--case-insensitive`: Ignore letter case (default: true)
- `--short [SHORT_SPEC]`: Shorten string values in search output, with fixed or progressive limits
- `-p, --provider claude|pi|codex|antigravitycli`: Restrict search to sessions from a specific provider
- `-d DIRPATH`: Restrict search to specific directory
- `-ma, --mafter DATE`: Only conversations modified after DATE
- `-ca, --cafter DATE`: Only conversations created after DATE
- `--no-metadata`: Disable outputting metadata frontmatter
- `--only-user`: Search/render only regular user-message body matches
- `--only-assistant`: Search/render only regular assistant-message body matches
- Reuses standard display flags (`-T`, `-t`, `-a`, `-b`, `-A`, `--plans`) to control both what counts as a match and what gets rendered

`--only-user` and `--only-assistant` narrow regular message matches. Session summaries and the latest current title remain searchable facets, so a title/summary hit can still return a session even when role filtering leaves no matching message body. As in parse mode, these `--only-*` flags override `--thinking`, `--tools`, `--agents`, `--plans`, and `--all` with a warning.

`--case-sensitive` and `--case-insensitive` are mutually exclusive. The selected mode applies to every regex or literal term, including terms inside boolean queries; it does not change the uppercase-only `AND`, `OR`, and `NOT` grammar. Search-mode shortening uses the long `--short` spelling because `-s` selects case-sensitive matching.

**Date formats:** ISO dates (`2024-12-15`, `24-12-15`), with time (`2024-12-15T14:30`, `2024-12-15 14:30:45`), or relative (`1h`, `2d`, `3w`, `4m`, `5y`).

**Examples:**

```bash
ch search "error message"              # Case-insensitive search
ch search -s "Error Message"           # Case-sensitive search
ch search "implement.*feature"         # Regex pattern
ch search -l "bug fix"                 # List matching files only
ch search -ll "bug fix"                # Print only matching session IDs
ch search -f "bug fix"                 # Print full conversations that match
ch search -r "bug fix"                 # Print matching messages as plain markdown
ch search -r -f "bug fix"              # Print full matching conversations as plain markdown
ch search -d ~/dev/project "feature"   # Filter by directory
ch search --mafter=1d "TODO"           # Modified in last day
ch search --mafter=2024-12-01 "deploy" # Modified since Dec 1
ch search --cafter=1w --mafter=1d "."  # Created last week, modified today
ch search -p claude "bug fix"          # Search only Claude sessions
ch search -p codex "TODO"              # Search only Codex sessions
ch search -p antigravitycli "TODO"     # Search only Antigravity CLI sessions
```

**Search Features:**
- Case-insensitive regex by default; `-s, --case-sensitive` opts into exact-case matching (multiline, DOTALL)
- Searches visible rendered message content, conversation summaries, and the latest current custom title
- By default renders only matching messages; `-f, --full` renders every visible message from each matching conversation
- Visibility flags affect search semantics: hidden thinking/tools/agents/plans and non-selected regular-message roles do not count as message matches
- `-a` changes the search universe itself by including Claude sidechain agent sessions
- Invalid regex patterns treated as literal strings (like `grep -F`)
- Plain-literal queries get a cheap candidate prefilter before the normal rendered-content confirmation pass
- Results stream to the terminal as each match is confirmed, so the first hit appears in well under a second instead of after the whole pool is scanned. Colored, paged output is streamed through `less -r` (quit early with `q` to stop the scan)
- Results are displayed newest first by filesystem mtime (scan order) across Claude, PI, Codex, and Antigravity sessions. `-r/--raw` is the exception and stays buffered, since its single-message formatting needs every hit first. In the colored `-l` view, the `N sessions · newest first` count prints as a trailing summary
- Extracts working directory from conversation files
- `search --raw` mirrors parse raw output: a single visible message prints as content only; otherwise each session is labeled with a setext `Session <id>` heading and sessions are separated by one `---`
- Full markdown rendering with syntax highlighting

### Rm Mode

Remove a conversation session and all associated files.

```bash
ch rm [OPTIONS] <session>
```

**What Gets Removed:**
1. Main conversation file: `projects/{project}/{session_id}.jsonl`
2. Agent files: `projects/{project}/{session_id}/subagents/agent-*.jsonl`, matching sessionId
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
ch rm 5078a7c7-0646-43cc-9412-7e1454a282b4

# Remove by file path (shows preview, then prompts for confirmation)
ch rm ~/.claude/projects/my-project/session-id.jsonl

# Dry run - preview only, no confirmation prompt
ch rm -n session-uuid
```

**Safety Features:**
- Automatic dry run preview before removal
- Interactive confirmation prompt: "Proceed with removal? [y/n]"
- Dry run mode (`-n`) for safe preview without any risk of removal
- Defensive existence checks - missing files don't cause errors
- Clear summary of removed items after execution

### Name Mode

Rename a conversation by appending a custom title entry.

```bash
ch name <session> "New Title"
ch name <session> --auto
ch name -n <session> --auto
```

This mutates the conversation file by appending the provider-native session-title entry shape:
- Claude: `custom-title` plus `agent-name`
- Codex: `event_msg.payload.type == "thread_name_updated"`
- PI: `session_info.name`

All three native shapes surface back through the same shared current-title abstraction for resolution, search, and metadata. Only the latest title is acknowledged; older historical titles are ignored.

**Options:**
- `--auto`: Ask `pi` to generate the new title from the visible transcript. The generated title is prefixed with the `MM-DD` date of the session's first message (e.g. `06-11 chats fix flaky tests`).
- `-n, --dry-run`: Print the resolved or generated title to stdout without modifying the session file.

Dry-run still performs `--auto` generation work; it just stops before writing JSONL/history side effects and prints only the resulting title.

**Session Resolution:**
- **Direct file path**: `/path/to/session.jsonl`
- **Recent negative index**: `-1`, `-2`, ... across the unified supported-session space
- **Session UUID**: `5078a7c7-0646-43cc-9412-7e1454a282b4`

### Catalog Mode

Catalog conversation sessions by upserting entries to a sessions.yaml file.

```bash
ch catalog [SESSION_IDS OR FILE_PATHS] [-a STRING]
```

This command uses an AI model (via the `claude` CLI) to analyze conversation sessions and maintain a `sessions.yaml` catalog file. The command reads session content and either creates new entries or updates existing ones with meaningful descriptions organized by date.

**Input Methods:**
- **Direct session IDs**: `ch catalog 00000000-0000-0000-0000-000000000000`
- **File paths**: `ch catalog path/to/session.jsonl`
- **Piped input**: `ch search -ca 1d . -l | ch catalog`
- **Multiple sessions**: Accepts multiple sessions but **only catalogs the first one found**.

**Features:**
- Automatically creates sessions.yaml if it doesn't exist
- Groups sessions by date with `# Mon DD YYYY` comments
- Updates existing session descriptions when new information is added
- Skips sessions already cataloged with the same message count
- Supports an 'ignored' list for empty/meaningless sessions

**Options:**
- `-a STRING`, `--append-prompt STRING`: Append extra instructions to the AI user message, wrapped in `<additional-instructions>` tags.

**Examples:**
- Catalog a specific session: `ch catalog 5078a7c7-0646-43cc-9412-7e1454a282b4`
- Catalog from search results (uses only first result): `ch search -ca 1d . -l | ch catalog`
- Catalog from multiple IDs (uses only first ID): `ch catalog id1 id2`
- Catalog with extra instructions: `ch catalog <id> -a "Note the primary language used."`

**Note:** This command requires the `claude` CLI to be configured in the user's environment.

### Info Mode

Aggregate and print one session's statistics.

```bash
ch info <session>
```

`info` resolves the session the same way parse does (file path, recent negative index, session id, or name), then prints a report:

```
Session Info

 Name: [06-21] session status info
 File: /Users/.../8f0a0094-9a14-4103-82ac-8db2ba8a46e0.jsonl
 ID: 8f0a0094-9a14-4103-82ac-8db2ba8a46e0
 Total duration (API):  11s
 Total duration (wall): 31m 03s
 Model: Claude Opus 4.8
 Usage by model:
    claude-opus-4-8:  5.8k input, 37.8k output, 4.5m cache read, 346.3k cache write ($5.41)

Messages
 User: 2
 Assistant: 22
 Tool Calls: 40
 Tool Results: 39
 Total: 63

Tokens
 Input: 5,811
 Output: 37,793
 Cache Read: 4,546,764
 Cache Write: 346,253
 Total: 4,936,621
 Cost: 5.4113
```

Pass `-f, --format json` for a flat, snake-cased JSON document instead — handy for piping into `jq`:

```bash
ch info <session> --format json
```

```json
{
  "name": "[06-21] session status info",
  "file": "/Users/.../8f0a0094-9a14-4103-82ac-8db2ba8a46e0.jsonl",
  "id": "8f0a0094-9a14-4103-82ac-8db2ba8a46e0",
  "total_duration_api": 11,
  "total_duration_wall": 1863,
  "model": "claude-opus-4-8",
  "usage_by_model": {
    "claude-opus-4-8": {"input": 5811, "output": 37793, "cache_read": 4546764, "cache_write": 346253, "total": 4936621, "cost": 5.4113}
  },
  "messages": {"user": 2, "assistant": 22, "tool_calls": 40, "tool_results": 39, "total": 63},
  "tokens": {"input": 5811, "output": 37793, "cache_read": 4546764, "cache_write": 346253, "total": 4936621, "cost": 5.4113}
}
```

The JSON is the lower-level form the text report derives from: durations are numeric seconds (`null` when absent) that the report humanizes, and `model` is the dominant model id (by total token usage) that the report renders as `Claude Opus 4.8`. Every per-model entry and the aggregate `tokens` share one `CostStats` shape — `{input, output, cache_read, cache_write, total, cost}` — so the session's total cost is `tokens.cost`.

**Scope:** Claude and PI only. A Codex or Antigravity session is rejected with a clear error.

**Data points:**
- **Durations.** Wall-clock is the span between the first and last in-band timestamps. API (generation) duration is shown only when the file records it — for Claude that is the sum of `turn_duration` system entries (recent CLI versions only); PI records none, so the line is omitted rather than guessed from timestamp gaps.
- **Usage by model.** Token usage and cost are grouped by the per-message model, so a session that switched models mid-stream reports each separately. Claude writes one API response across several JSONL lines that repeat the same `message.id` and `usage`, so usage and the assistant-message count are deduplicated by `message.id`; `<synthetic>` placeholder and API-error lines are excluded.
- **Messages.** `Total` is users + assistants + tool results. Tool calls live inside assistant messages, so they are reported separately rather than added. Tool calls are counted by distinct `tool_use` id and tool results by distinct `tool_result` id.
- **Cost.** Taken straight from PI's stored `usage.cost`. Claude does not store cost, so it is computed from a per-model price table (cache reads at 0.1x input) that tolerates bare and date-stamped model ids. Cache writes are priced per TTL bucket from the `cache_creation` breakdown Claude records — 1-hour writes at 2x input, 5-minute writes at 1.25x — matching Claude Code's 1-hour-cache billing.
- **Provided over computed.** Where a file states a value, `info` reads it: PI's per-message `totalTokens` is summed for the token Total (Claude has no such field, so there it is the sum of the four categories).

## Conversation File Structure

Conversations are stored as JSONL files where each line is a JSON entry.

**Entry Types:**

1. **User messages** (`type: "user"`)
   - `message.content`: string or array (can include tool results)
   - User-side local command protocol payloads stay hidden by default across adapters, including Claude `<command-*>...</command-*>` inputs and `<local-command-stdout>...</local-command-stdout>` outputs
   - Claude `isMeta=true` user messages also stay hidden by default. When an `isMeta` text payload carries `sourceToolUseID`, it is treated as another output for that source tool, so direction/name filters apply (`-t:i` hides it, `-t:o` and `-t Skill:o` show it). Other meta text remains visible only with `-t, --tools`.
   - Claude background-task notifications (string content wrapped in `<task-notification>...</task-notification>`, emitted when a background `Agent` task finishes) classify as a synthetic `TaskNotification` tool: hidden by default, shown with `-t`, name-filterable (`-t TaskNotification`). The `tool_use_id` (linking back to the originating `Agent` dispatch), `status`, and `summary` render as `<tool-input>` attributes and the task result as the body; double quotes in attribute values are downgraded to single quotes
   - Claude post-compaction summaries (`isCompactSummary: true`, injected when a conversation is continued past its context limit) render as a visible `<compaction>` block — shown by default like `<recap>`, with its own hue and a "Compaction" badge in colored output, rather than as a regular user message
   - Common fields: `cwd`, `sessionId`, `version`, `gitBranch`, `uuid`, `parentUuid`, `timestamp`

2. **Assistant messages** (`type: "assistant"`)
   - `message.content[]`: Array containing:
     - `{type: "text", text: "..."}` - shown by default
     - `{type: "thinking", thinking: "..."}` - hidden by default (use `-T`), renders as `<thinking>`
     - `{type: "tool_use", ...}` - hidden by default (use `-t`), renders as `<tool-input name="...">`
     - `{type: "tool_use", name: "ExitPlanMode", input: {plan: "..."}}` - hidden by default (use `--plans` to show)
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
   - Summary text used for summary-prefix conversation matching

6. **Session title entries** (provider-normalized to the shared current-title abstraction)
   - Not rendered in the conversation body
   - Claude uses `type: "custom-title"` with `customTitle`
   - Codex uses `type: "event_msg"` with `payload.type: "thread_name_updated"` and `payload.thread_name`
   - PI uses `type: "session_info"` with `name`
   - Only the latest such entry is acknowledged for resolution, search, and metadata
   - Searchable in search mode and emitted as `custom_title:` in metadata frontmatter

7. **PI custom messages** (`type: "custom"` and selected `custom_message` records)
   - Joined `pi-user-agents` `custom_message` records are visible by default when `details.mainContextState` is exactly `joined`
   - Other custom records stay hidden by default
   - `--all` renders arbitrary `type: "custom"` data as JSON without assuming its schema, including incomplete special records that cannot normalize
   - `--agents` renders successful and failed `pi-user-agents` `custom` records and `subagents:record` records through the shared agent view
   - Failed `pi-user-agents` records use Bash error presentation without requiring `--tools`
   - Non-joined `custom_message`, `subagent-notification`, and other `display: false` records stay hidden, including with `--all`

8. **Hook additional-context attachments** (`type: "attachment"`, Claude)
   - `attachment.type: "hook_additional_context"` is the text a hook injects into the transcript (from `UserPromptSubmit`, `SessionStart`, `PreToolUse:*`, `PostToolUse:*`, ...)
   - Classifies as a synthetic `AdditionalContext` tool: hidden by default, shown with `-t`, name-filterable (`-t AdditionalContext`, `-t !AdditionalContext`)
   - `attachment.hookName` renders as the `hook_name` attribute and the joined `attachment.content` list as the body: `<tool-input name="AdditionalContext" hook_name="UserPromptSubmit">`
   - Obeys the shared tool policy across parse, JSON, and search; `-t`/`-t:s` keeps and shortens it. Other `attachment.type`s are skipped

9. **Antigravity CLI transcript entries**
   - Stored under `~/.gemini/antigravity-cli/brain/{session_id}/.system_generated/logs/`
   - `transcript_full.jsonl` is preferred when present; `transcript.jsonl` is used only when the full variant is missing
   - Session identity comes from the `{session_id}` brain directory, not from in-record fields
   - `USER_INPUT.content` renders only the `<USER_REQUEST>...</USER_REQUEST>` body by default, hiding Antigravity metadata wrappers
   - `PLANNER_RESPONSE.content` renders as assistant text; `thinking` and `tool_calls` are opt-in through the standard `--thinking` and `--tools` flags
   - Tool result records such as `RUN_COMMAND`, `VIEW_FILE`, and `CODE_ACTION` pair with the earliest pending call that expects their record type. Unmatched results keep a synthetic identity and remain name-filterable when the record type identifies one or more possible tools

**Non-linear structure (Claude):**

A Claude transcript is a tree, not a line — file order is not conversation order. Three mechanisms break linearity (others likely exist):
- **Rewind:** returning to an earlier point and re-prompting forks the tree — the rewind target gains an extra child, so one node has multiple children sharing the same non-null `parentUuid`. The surviving thread is the longest continuation; the shorter sibling subtrees are abandoned branches.
- **Compaction** (`/compact`): does *not* fork, it cuts. Each compaction ends the current tree and starts a fresh `parentUuid: null` root — a `system/compact_boundary` node whose sole child is the `isCompactSummary` summary — so a compacted file is a *forest* of disjoint trees, one per context-window era. Cross-era continuity lives out-of-band in the boundary's `compactMetadata.preservedSegment`, not in `parentUuid`; file order keeps the eras in sequence.
- **`/fork`** (user-initiated background agent): the parent session stores only the `/fork` command message and the returning `<task-notification>` — no `Task` tool_use, `agentId`, or `isSidechain` anchor in the main thread. The fork's transcript lives in a separate `subagents/agent-{slug}-{taskId}.jsonl` (plus a `.meta.json` with `isFork: true`) whose leading `fork-context-ref` links *back* to the parent (`parentLastUuid` = the forked-from node) while nothing links forward — unlike classic agent-initiated subagents, which anchor in-thread via a `Task` tool_use / `agentId`.

In `ch` output, messages on an abandoned **rewind** branch are hidden by default and included only with `-b, --branches`, each tagged `branch="N"` (and a `⑂N` chip in colored output). Resolution runs per era, so compaction seams and prior eras are never mistaken for abandoned branches; within each era the main thread is the path to the latest `last-prompt` `leafUuid`.

**Agent/Subagent Conversations:**
- Hidden by default (use `-a` or `--agents` to show)
- Three kinds are captured: agent-initiated sidechains, user-initiated `/fork` background agents, and inline Pi `pi-user-agents` / `subagents:record` custom records
- Claude sidechains and `/fork` transcripts are stored separately under `{session_id}/subagents/`. Sidechains use `agent-{shortId}.jsonl`; a `/fork` uses `agent-{slug}-{taskId}.jsonl` with a sibling `.meta.json` carrying `agentType: "fork"`
- These file-backed transcripts use the same structure as main conversations. Their entries include `agentId` and `isSidechain: true`
- All three kinds render through the shared `<agent>` wrapper. File-backed Claude agents carry `agent_id` and `subagent_type`; inline Pi agents carry `custom_type`
- A user-initiated `/fork` carries `subagent_type="fork"` and is headed `Fork` (a `Fork` badge in colored output). Agent-initiated `Task` subagents stay `Agent`
- A classic subagent is anchored in-thread by its first line's `sessionId`; a `/fork` has no in-thread anchor and is matched instead by its leading `fork-context-ref.parentSessionId`
- Inline Pi records stay in the main transcript and do not create sidechain files
- Claude agent tool results include `agentId: xxx (for resuming...)` in content

**Why `TaskNotification` is an unpaired tool:**

Every other tool comes as an input/output pair. A `TaskNotification` is the exception: it's a standalone message Claude injects when a *background* `Agent` task finishes, long after the dispatch. It has no output of its own — instead its `tool_use_id` points back at the original `Agent` call (which keeps its own normal pair), so you can trace a finished task to where it started. That id is surfaced as a plain attribute rather than the tool's real id on purpose: reusing it would overwrite the `Agent` call's name in the id→name map and mislabel that call's output.

## Technical Reference

**Location:** `~/dev/chats` (installed globally as `ch` via `uv tool install -e . --force`)

**Dependencies:**
- Python 3.13+
- Rich library (for formatting)
- PyYAML (for catalog/sessions.yaml handling)

**Key Functions:**
- `extract_summaries_from_jsonl()` - Extract all summary fields from file
- `SessionPool.discover()` - Build the unified supported-session inventory for one invocation
- `SessionScan.from_content()` - Decode one session once into search facets and visible messages
- `get_input_content()` - Resolve input from CLI arg, stdin, or conversation/session ID
- `detect_format()` - Deterministic format detection (first line only)
- `parse_jsonl()` / `parse_jsonl_entries()` - Parse JSONL conversation files
- `parse_raw_cli_transcript()` - Parse raw CLI transcripts
- `format_to_xml()` - Convert messages to XML format
- `render_message_panels()` - Colored per-message panel rendering (parse color path)
- `print_metadata()` - Unified metadata output to stderr
- `parse_slice_notation()` - Convert slice strings to indices
- `find_all_supported_session_files()` - Find all supported Claude, PI, Codex, and Antigravity session files
- `sort_by_modified()` / `sort_by_modified_descending()` - Shared modified-time ordering helpers for recency-aware flows
- `extract_cwd_from_jsonl()` / `extract_cwd_from_entries()` - Extract working directory from JSONL
- `cmd_search()` - Search with rich display
- `cmd_rm()` - Remove session and all associated files
- `display_search_result()` - Plain (non-color) XML output for a search hit; colored search renders via `build_messages_group()`

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

## Development

**scripts/dev/jsonl_scout.py:** Generic JSONL bloat analyzer — recursively traverses any JSONL with zero shape assumptions, reports string path heat, array cardinality hotspots, per-line outlier attribution, dedup candidates, and ranked surgical cut recommendations.

---

**Random Ideas:**
- This file contains `/plan` mode and interactive user ask tool: `projects/-Users-giladbarnea--claude/c5c0741a-f696-47c2-8337-d1a20de84c7a.jsonl`. Can be interesting to display.
