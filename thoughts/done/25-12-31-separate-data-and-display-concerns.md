# Separate Data and Display Concerns

**Bug fixed:** `--color=always` silently dropped `<thinking>` and tool blocks because `render_messages_with_rich()` passed entire XML+markdown hybrid strings to Rich's `Markdown()`, which stripped unknown HTML-like tags including their contents.

**Fix / architecture landed:** "structured data → render last" — postpone all serialization to render time.

Key additions to `model.py`:
- `MessagePartKind` enum (`TEXT`, `THINKING`, `TOOL`)
- `ToolParts` NamedTuple — single source of truth for tool shape (tag, attrs, content, is_empty)
- `MessagePart` NamedTuple — typed content block yielded per message
- `Message.iter_visible_parts(flags)` — sole authority on visibility, ordering, shortening
- `tool_to_parts(tool)` — all formatting decisions (TOOL_SCHEMAS, Edit diff, tool_result, fallback JSON)
- `render_tool_xml(parts)` / `render_tool_rich(parts)` — thin format-specific serializers
- `render_message_inner_xml(msg, flags)` — replaces `get_visible_content()`
- `render_messages_with_rich()` rewritten: only `TEXT` parts go through `Markdown()`; tags always rendered as `Text(..., style="dim")`

**Deleted:** `format_tool_for_xml()`, `Message.get_visible_content()`

**Tests added:** `tests/test_structured_rendering.sh` (6 tests), `tests/data/golden_xml_output.txt` golden reference.
