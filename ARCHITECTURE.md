# `conversations` Skill Architecture

## Overview

Parse and search Claude Code conversation history files (JSONL format). Converts to XML/JSON with Rich markdown rendering.

**Core capability:** Transform conversation files → Human-readable XML/JSON with markdown highlighting

---

## Data Model

### Message Class
Represents a single conversation turn:
```python
@dataclass
class Message:
    role: str              # "user" | "assistant"
    text: str              # Main content
    thinking: str          # Claude's thinking (if any)
    tools: List[dict]      # Tool calls (tool_use/tool_result)
    plan: Optional[str]    # ExitPlanMode plan content (shown by default)
    index: int             # Position in conversation
    agent_id: Optional[str] # Set if this is a subagent message
    timestamp: Optional[str] # ISO timestamp for chronological sorting
    subagent_type: Optional[str] # Type of subagent if applicable
    model: Optional[str]   # Model used for the message
    is_meta: bool          # Whether this is a meta user message
    source_tool_user_id: Optional[str] # Tool ID associated with user message
```

Key method: `iter_visible_parts(flags)` → Yields structured `MessagePart` objects (TEXT, THINKING, TOOL) based on flags

`ConversationFlags` also carries role-level visibility for the regular parse-mode defaults:
- `show_user_messages`
- `show_assistant_messages`

Those flags hide only the default text/plan content for each role. Thinking, tools, and agent sidechains stay orthogonal so combinations like `--no-user --tools` and `--no-assistant --agents` compose without downstream contradiction handling.

---

## Content Block Type Registry

**Problem solved:** XML tag knowledge was scattered across 4 functions. Adding new content types required editing multiple locations.

**Solution:** Single source of truth enum (in `src/conversations/registry.py`):

```python
class ContentBlockType(Enum):
    # Message wrappers (outer blocks)
    USER_MESSAGE = ContentBlockInfo("user-message", "# User", "bold cyan")
    ASSISTANT_RESPONSE = ContentBlockInfo("assistant-response", "# Assistant", "bold green")
    AGENT = ContentBlockInfo("agent", "# Agent", "bold magenta")
    SESSION_RENAME = ContentBlockInfo("session-rename", "# Renamed Session", "bold yellow")

    # Content blocks (inner blocks)
    THINKING = ContentBlockInfo("thinking", None, "dim italic")
    TOOL_INPUT = ContentBlockInfo("tool-input", None, "dim")
    TOOL_OUTPUT = ContentBlockInfo("tool-output", None, "dim")
```

Each entry defines:
- `xml_tag` - Tag name in output
- `header` - Display header (None for inner blocks)
- `rich_style` - Rich console style string

**Impact:** Adding new content type = 1 line of code (enum entry)

---

## Tool Schema Registry

**Problem solved:** `format_tool_for_xml()` had 9 hardcoded `elif` branches (one per tool). Adding tools required code changes.

**Solution:** Data-driven schema lookup (in `src/conversations/registry.py`):

```python
TOOL_SCHEMAS: Dict[str, ToolSchema] = {
    "Bash": ToolSchema([], "command", "sh"),
    "Read": ToolSchema(["file_path"], None, None),
    "Glob": ToolSchema(["pattern", "path"], None, None),
    "Grep": ToolSchema(["pattern", "path", "glob", "type", "output_mode"], None, None),
    "Write": ToolSchema(["file_path"], "content", None),
    "Edit": ToolSchema(["file_path"], None, None),  # Special case: old_string/new_string
    "Task": ToolSchema(["subagent_type", "model"], "prompt", None),
    "WebFetch": ToolSchema(["url"], "prompt", None),
    "WebSearch": ToolSchema(["query"], None, None),
}
```

Each schema defines:
- `attr_keys` - Which input fields become XML attributes
- `content_key` - Which field becomes content body (None = attributes only)
- `content_lang` - Language for code fence (None = no fence)

**Impact:** Adding new tool = 1 line of code (dict entry). Edit tool has special handling in `_format_edit_content()`.

---

## Rendering Pipeline

Two paths from `List[Message]` to user display:

### Path 1: Plain XML (no color)
```
Messages → iter_visible_parts() → render_message_inner_xml() → stdout
                ↓
         Uses ContentBlockType registry
         Uses tool_to_parts() / render_tool_xml()
```

Output: Plain XML with markdown code fences. Byte-identical to pre-2026 versions.

### Path 2: Rich Rendering (colored)
```
Messages → render_messages_with_rich() → Rich console
                ↓
         iter_visible_parts() → List[MessagePart]
         
         Loop over parts:
           TEXT     → Markdown(text)
           THINKING → Text("<thinking>", dim) + Text(content, italic)
           TOOL     → render_tool_rich(ToolParts)
```

**Key insight:** Path 2 **never** passes XML tags to the Markdown parser.
- Old broken way: `get_visible_content()` → string with tags → `Markdown()` → tags stripped
- New way: Structured parts → explicit `Text` objects for tags, `Markdown` only for content

---

## Format Detection

Input format detected by examining **first non-empty line only** (deterministic):

```python
def detect_format(content: str) -> str:
    first_line = [l for l in content.split("\n") if l.strip()][0]
    try:
        obj = json.loads(first_line)
        if isinstance(obj, dict) and "type" in obj:
            return "jsonl"
    except json.JSONDecodeError:
        pass
    return "raw"  # Default for non-JSONL (including raw transcripts)
```

- **JSONL:** Valid JSON dict with `type` field
- **Raw transcript:** Anything else (including `> ` or `⏺ ` prefixed lines)

No heuristics, no "looking at multiple lines". First non-empty line determines format.

---

## Key Design Decisions

### Why registries instead of inheritance?
- Tool schemas are data, not behavior
- Adding entries doesn't require new classes
- Easy to serialize/validate at runtime

### Why two rendering paths?
- Plain XML path needed for piping/saving (`/export` command)
- Rich path optimized for terminal display
- Keeping both avoids conditional complexity in single function

### Why structured MessageParts?
Old design (`get_visible_content`) returned a string with embedded XML tags. This caused Rich's Markdown parser to treat tags as HTML and strip them.
New design (`iter_visible_parts`) yields `(kind, data)` tuples. This keeps data "malleable" until the very last moment, allowing the renderer to decide how to format tags (as XML strings or styled Text objects) without ambiguity.

### Why a domainless ordering helper?
Recent-session selectors like `-1` and the `search` command both depend on the same global modified-time ordering. The shared helper in `ordering.py` keeps that ordering logic generic and injectable via a callback (`modified_at=...`), while conversation-specific code stays responsible only for producing `ConversationMetadata`.

---

## Module Structure

```
src/conversations/
├── __init__.py                       # Package exports
├── catalog/                          # Catalog command module
│   ├── __init__.py                   # Cataloging logic and LLM orchestration
│   └── assets/                       
│       └── sessions.template.yaml    # Template for new sessions.yaml files
├── cli.py                            # argparse + main()
├── commands.py                       # cmd_parse/search/rename/catalog + resolution/slicing
├── parsing.py                        # detect_format + parse_jsonl/raw + extract_*
├── formatting.py                     # xml/json/raw formatting + Rich rendering
├── model.py                          # Message + ConversationFlags
├── ordering.py                       # Generic modified-time ordering + negative-index resolution
├── tools.py                          # tool_to_parts + tool renderers
├── registry.py                       # ContentBlockType + TOOL_SCHEMAS
├── parts.py                          # MessagePartKind + ToolParts + MessagePart
├── tool_filter.py                    # ToolFilter dataclass + spec parsing
├── console.py                        # Rich console singleton + print_error()
└── utils.py                          # shorten_data + extract_text_from_content + helpers
```

Primary commands:
- `cmd_parse()` - Parse and format conversations
- `cmd_search()` - Regex search across conversations
- `cmd_catalog()` - Catalog sessions to sessions.yaml using an LLM

---

## Integration Points

### /export Slash Command
Location: `~/.claude/commands/export.md`
```bash
ccc --color never <conversation-id>
```
Copies XML output to clipboard (macOS) or saves to file.

### PreCompact Hook
Location: `~/.claude/hooks/export-before-compact.py`
Auto-exports conversations before compaction (lossy operation).
Saves to: `~/.claude/projects/pre-compact/{session_id}-{timestamp}.xml`

**Dependency:** Both integration points rely on plain XML output format remaining stable.
