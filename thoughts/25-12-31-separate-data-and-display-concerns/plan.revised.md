---
session_id: 4f9cc978-6e0e-4de5-97da-badcb8f9132d
directory: ~/.claude
history_path: ~/.claude/projects/-Users-giladbarnea--claude/4f9cc978-6e0e-4de5-97da-badcb8f9132d.jsonl
created: "2025-12-31 10:25"
modified: "2026-01-01 12:58"
messages: 1
---
# Assistant

I'll write a complete implementation plan. Let me think through this carefully.

---

# Implementation Plan: Structured Data → Render Last Architecture

## 1. Overview

### 1.1 Goals
1. **Fix the bug**: `--color=always` strips thinking/tool content because Rich's `Markdown()` treats custom XML tags as HTML
2. **Land the architecture**: Postpone formatting until render time; keep data structured as long as possible
3. **Prevent drift**: Tool formatting logic lives in one place, consumed by both XML and Rich renderers

### 1.2 Success Criteria
- `ccc file.jsonl --color=always -T -t` shows identical logical content to `--color=never`
- XML output is byte-identical to before (no regression)
- All existing tests pass
- New regression test catches the original bug

### 1.3 Constraints
- Complete in one refactor (no partial migration state left behind)
- Minimize window where old and new implementations coexist
- When coexistence is necessary, mark old code with `# DEPRECATED: replaced by {new_name}`

---

## 2. Behavioral Specification

### 2.1 Visibility Rules (unchanged)
| Flag | Effect |
|------|--------|
| `-T, --thinking` | Include `<thinking>` blocks |
| `-t, --tools` | Include `<tool-input>` and `<tool-output>` blocks |
| `--no-plans` | Exclude ExitPlanMode tool calls |
| `-a, --agents` | Include agent messages |
| `--shorten` | Truncate long content via `shorten_data()` |

### 2.2 XML Output Format (unchanged)
```
<user-message i="1">
# User

{message text}

<thinking>
{thinking text}
</thinking>

<tool-input name="Bash" command="echo hello">
```sh
echo hello
```
</tool-input>
</user-message>

---

<assistant-response i="2">
# Assistant
...
```

### 2.3 Rich Output Format (THE FIX)
- **Same logical content** as XML output
- XML tags (`<user-message>`, `<thinking>`, `<tool-input>`, etc.) rendered as `Text(..., style="dim")`
- Headers (`# User`, `# Assistant`) rendered with `wrapper_type.value.rich_style`
- **Only message text** passed to `Markdown()` — never XML tags
- Thinking content rendered as `Text(..., style="dim italic")`
- Tool content rendered as `Markdown()` (for code block formatting)
- Same `---` separators between messages

### 2.4 Tool Formatting Rules (unchanged)
- Attribute extraction via `TOOL_SCHEMAS` registry
- Edit tool: special `old_string`/`new_string` diff format
- Unknown tools: fallback to JSON dump
- `tool_result`: content in code block, `is_error="true"` attribute if applicable
- Empty content: `<tag attrs></tag>` (inline, no newlines)

### 2.5 The Bug (root cause)
```python
# Current broken code in render_messages_with_rich():
content = msg.get_visible_content(flags)  # Returns "<thinking>...</thinking>" embedded
md = Markdown(content)  # Rich strips <thinking> as unknown HTML
```

---

## 3. Test Specification

### 3.1 Test Strategy
Write tests **before** implementation. Tests encode behavior, not implementation details.

### 3.2 Test 1: Golden Reference for XML Output (regression prevention)

**Behavior**: XML output format must not change.

**Test file**: `tests/test_structured_rendering.sh` (new)

```bash
# Capture golden reference (run once before refactor, save output)
# tests/data/golden_xml_output.txt

test_xml_output_unchanged() {
    actual=$(ccc tests/data/synthetic_flags.jsonl -T -t --color=never 2>/dev/null)
    expected=$(cat tests/data/golden_xml_output.txt)
    assert_eq "$actual" "$expected" "XML output should be unchanged"
}
```

**Action before implementation**: Generate and commit `tests/data/golden_xml_output.txt`

### 3.3 Test 2: Rich Output Contains Thinking/Tools (the bug fix)

**Behavior**: With `--color=always`, thinking and tool content must appear in output.

```bash
test_rich_output_contains_thinking() {
    # Pipe to force non-tty, strip ANSI codes
    output=$(ccc tests/data/synthetic_flags.jsonl -T --color=always 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
    
    assert_contains "$output" "<thinking>" "Should contain thinking open tag"
    assert_contains "$output" "</thinking>" "Should contain thinking close tag"
    assert_contains "$output" "I should reply hello" "Should contain thinking content"
}

test_rich_output_contains_tools() {
    output=$(ccc tests/data/synthetic_flags.jsonl -t --color=always 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
    
    assert_contains "$output" "<tool-input" "Should contain tool-input tag"
    assert_contains "$output" "<tool-output>" "Should contain tool-output tag"
    assert_contains "$output" "echo hello" "Should contain tool input content"
}
```

**Expected result before implementation**: FAIL (this is the bug)

### 3.4 Test 3: Rich/XML Content Equivalence

**Behavior**: Stripped Rich output should have same tags and structure as XML output.

```bash
test_rich_xml_equivalence() {
    xml_output=$(ccc tests/data/synthetic_flags.jsonl -T -t --color=never 2>/dev/null)
    rich_output=$(ccc tests/data/synthetic_flags.jsonl -T -t --color=always 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
    
    # Both should contain the same structural elements
    for tag in "<user-message" "</user-message>" "<assistant-response" "</assistant-response>" \
               "<thinking>" "</thinking>" "<tool-input" "</tool-input>" "<tool-output>" "</tool-output>"; do
        xml_count=$(echo "$xml_output" | grep -c "$tag" || true)
        rich_count=$(echo "$rich_output" | grep -c "$tag" || true)
        assert_eq "$xml_count" "$rich_count" "Tag count for $tag should match"
    done
}
```

### 3.5 Test 4: Visibility Flags Work Correctly

**Behavior**: Each flag controls its respective content.

```bash
test_thinking_flag_controls_visibility() {
    # Without -T: no thinking
    output=$(ccc tests/data/synthetic_flags.jsonl --color=never 2>/dev/null)
    assert_not_contains "$output" "<thinking>"
    
    # With -T: has thinking
    output=$(ccc tests/data/synthetic_flags.jsonl -T --color=never 2>/dev/null)
    assert_contains "$output" "<thinking>"
}

# Similar tests for -t, --no-plans, etc.
```

---

## 4. Architectural Contracts

### 4.1 Data Structures

```python
# --- New types (add near top of file, after imports) ---

class MessagePartKind(Enum):
    """The kind of content part within a message."""
    TEXT = "text"
    THINKING = "thinking"
    TOOL = "tool"


class ToolParts(NamedTuple):
    """Normalized representation of a tool call (input, output, or plan-as-tool).
    
    This is the single source of truth for tool structure.
    Both XML and Rich renderers consume this.
    """
    tag: str                        # "tool-input" or "tool-output"
    attrs: List[Tuple[str, str]]    # Ordered key-value pairs for XML attributes
    content: Optional[str]          # Body content (may include fenced code blocks)
    is_empty: bool                  # True → render as <tag ...></tag> (inline)


class MessagePart(NamedTuple):
    """A single content block within a message.
    
    Yielded by Message.iter_visible_parts().
    Consumed by renderers without further transformation.
    """
    kind: MessagePartKind
    data: Union[str, ToolParts]     # str for TEXT/THINKING, ToolParts for TOOL
```

### 4.2 Function Signatures

```python
def tool_to_parts(tool: dict) -> ToolParts:
    """Convert a raw tool dict to normalized ToolParts.
    
    Contains ALL tool formatting decisions:
    - TOOL_SCHEMAS attribute extraction
    - Edit tool special-casing
    - Unknown tool JSON fallback
    - tool_result formatting
    """
    ...

def render_tool_xml(parts: ToolParts) -> str:
    """Render ToolParts to XML string. Thin formatter, no decisions."""
    ...

def render_tool_rich(parts: ToolParts) -> List[Union[Text, Markdown]]:
    """Render ToolParts to Rich objects. Thin formatter, no decisions."""
    ...

def render_message_inner_xml(msg: Message, flags: ConversationFlags) -> str:
    """Render message inner content (text, thinking, tools) to XML string.
    
    Iterates msg.iter_visible_parts(flags), formats each part.
    Does NOT include outer wrapper tag or header.
    """
    ...

# Method on Message class:
def iter_visible_parts(self, flags: ConversationFlags) -> List[MessagePart]:
    """Yield all visible content parts based on flags.
    
    This is the single source of truth for:
    - What content is visible (flag-based filtering)
    - Content ordering (text, thinking, tools, plan)
    - Shortening (applies shorten_data if flags.shorten)
    
    Plans are represented as TOOL parts with name="ExitPlanMode".
    """
    ...
```

### 4.3 Single Point of Decision Table

| Decision | Location | Notes |
|----------|----------|-------|
| Is this part visible? | `iter_visible_parts()` | Checks flags.show_thinking, etc. |
| Apply shortening? | `iter_visible_parts()` | Applies `shorten_data()` before yielding |
| Tool attribute extraction | `tool_to_parts()` | Uses TOOL_SCHEMAS |
| Edit tool special format | `tool_to_parts()` | Calls `_format_edit_content()` |
| Unknown tool fallback | `tool_to_parts()` | JSON dump |
| tool_result error attr | `tool_to_parts()` | Sets attr if `is_error=True` |
| Plan → tool-like part | `iter_visible_parts()` | Creates ToolParts directly |
| Outer wrapper tag | `format_to_xml()` / `render_messages_with_rich()` | Uses `msg.get_wrapper_type()` |
| Header (# User) | `format_to_xml()` / `render_messages_with_rich()` | Uses `wrapper_type.value.header` |
| Message separator (---) | `format_to_xml()` / `render_messages_with_rich()` | Outer loop |

---

## 5. Implementation Plan

### Phase 0: Test Setup (before any code changes)

**0.1** Create `tests/test_structured_rendering.sh`
- Add test helper functions (assert_contains, assert_not_contains, assert_eq)
- Add placeholder test functions (will fail initially)

**0.2** Generate golden reference
```bash
ccc tests/data/synthetic_flags.jsonl -T -t --color=never > tests/data/golden_xml_output.txt
```
- Commit this file

**0.3** Run tests, verify:
- `test_xml_output_unchanged`: PASS (trivially, comparing to self)
- `test_rich_output_contains_thinking`: FAIL (the bug)
- `test_rich_output_contains_tools`: FAIL (the bug)

---

### Phase 1: Data Structures

**1.1** Add `MessagePartKind` enum after existing enums (~line 70)

**1.2** Add `ToolParts` NamedTuple after `ToolSchema`

**1.3** Add `MessagePart` NamedTuple after `ToolParts`

**Verification**: File parses without error. No behavior change yet.

---

### Phase 2: Tool Normalization Layer

**2.1** Implement `tool_to_parts(tool: dict) -> ToolParts`

Extract logic from `format_tool_for_xml()`:
- `tool_use` → extract attrs via TOOL_SCHEMAS, format content
- `tool_result` → extract content, set is_error
- Edit special case → call `_format_edit_content()`
- Unknown tool → JSON fallback

Place after `_format_edit_content()` function.

**2.2** Implement `render_tool_xml(parts: ToolParts) -> str`

Thin function:
```python
def render_tool_xml(parts: ToolParts) -> str:
    attr_str = " ".join(f'{k}="{v}"' for k, v in parts.attrs)
    tag_open = f"<{parts.tag} {attr_str}>" if attr_str else f"<{parts.tag}>"
    if parts.is_empty:
        return f"{tag_open}</{parts.tag}>"
    return f"{tag_open}\n{parts.content}\n</{parts.tag}>"
```

**2.3** Reimplement `format_tool_for_xml()` as thin wrapper

```python
def format_tool_for_xml(tool: dict) -> str:
    # DEPRECATED: This wrapper exists for compatibility.
    # Direct callers should migrate to tool_to_parts() + render_tool_xml().
    return render_tool_xml(tool_to_parts(tool))
```

**Verification**: 
- Run `ccc tests/data/synthetic_flags.jsonl -t --color=never`
- Output should be identical to before (tool formatting unchanged)
- `test_xml_output_unchanged`: PASS

---

### Phase 3: Message Parts Iterator

**3.1** Implement `Message.iter_visible_parts(flags) -> List[MessagePart]`

```python
def iter_visible_parts(self, flags: ConversationFlags) -> List[MessagePart]:
    parts = []
    
    # Text
    if self.text:
        text = shorten_data(self.text) if flags.shorten else self.text
        parts.append(MessagePart(MessagePartKind.TEXT, text))
    
    # Thinking
    if flags.show_thinking and self.thinking:
        thinking = shorten_data(self.thinking) if flags.shorten else self.thinking
        parts.append(MessagePart(MessagePartKind.THINKING, thinking))
    
    # Tools
    if flags.show_tools and self.tools:
        for tool in self.tools:
            tool_data = shorten_data(tool) if flags.shorten else tool
            parts.append(MessagePart(MessagePartKind.TOOL, tool_to_parts(tool_data)))
    
    # Plan (as tool-like part)
    if flags.show_plans and self.plan:
        plan_content = shorten_data(self.plan) if flags.shorten else self.plan
        plan_parts = ToolParts(
            tag=ContentBlockType.TOOL_INPUT.value.xml_tag,
            attrs=[("name", "ExitPlanMode")],
            content=plan_content,
            is_empty=False
        )
        parts.append(MessagePart(MessagePartKind.TOOL, plan_parts))
    
    return parts
```

**Verification**: Manual inspection in Python REPL
```python
msg = messages[0]
for part in msg.iter_visible_parts(flags):
    print(part.kind, type(part.data))
```

---

### Phase 4: XML Inner Renderer

**4.1** Implement `render_message_inner_xml(msg, flags) -> str`

```python
def render_message_inner_xml(msg: Message, flags: ConversationFlags) -> str:
    """Render message inner content to XML string."""
    output_parts = []
    
    for part in msg.iter_visible_parts(flags):
        if part.kind == MessagePartKind.TEXT:
            output_parts.append(part.data)
        
        elif part.kind == MessagePartKind.THINKING:
            tag = ContentBlockType.THINKING.value.xml_tag
            output_parts.append(f"<{tag}>\n{part.data}\n</{tag}>")
        
        elif part.kind == MessagePartKind.TOOL:
            output_parts.append(render_tool_xml(part.data))
    
    return "\n\n".join(output_parts)
```

**4.2** Reimplement `get_visible_content()` as thin wrapper

```python
def get_visible_content(self, flags: ConversationFlags) -> str:
    # DEPRECATED: replaced by iter_visible_parts() + render_message_inner_xml()
    # Kept for compatibility. Do not build on top of this.
    return render_message_inner_xml(self, flags)
```

**Verification**:
- `test_xml_output_unchanged`: PASS
- All existing behavior preserved

---

### Phase 5: Rich Tool Renderer

**5.1** Implement `render_tool_rich(parts: ToolParts) -> List[Union[Text, Markdown]]`

```python
def render_tool_rich(parts: ToolParts) -> List:
    """Render ToolParts to Rich objects."""
    result = []
    style = ContentBlockType.TOOL_INPUT.value.rich_style if parts.tag == "tool-input" \
            else ContentBlockType.TOOL_OUTPUT.value.rich_style
    
    # Opening tag
    attr_str = " ".join(f'{k}="{v}"' for k, v in parts.attrs)
    tag_open = f"<{parts.tag} {attr_str}>" if attr_str else f"<{parts.tag}>"
    result.append(Text(tag_open, style="dim"))
    
    if parts.is_empty:
        result.append(Text(f"</{parts.tag}>", style="dim"))
    else:
        result.append(Text("\n", style="dim"))
        # Content as Markdown (handles code fences nicely)
        result.append(Markdown(parts.content))
        result.append(Text(f"\n</{parts.tag}>", style="dim"))
    
    return result
```

**Verification**: Unit test `render_tool_rich(tool_to_parts(sample_tool))` produces expected Rich objects

---

### Phase 6: Rich Message Renderer (THE FIX)

**6.1** Rewrite `render_messages_with_rich()`

```python
def render_messages_with_rich(messages: List[Message], flags: ConversationFlags) -> None:
    """Render messages to Rich console.
    
    Key invariant: Only TEXT content is passed to Markdown().
    XML-like tags are always rendered as dim Text.
    """
    print_targets = []
    
    for i, msg in enumerate(messages):
        # Separator between messages
        if i > 0:
            print_targets.append(Text("\n---\n\n", style="dim"))
        
        # Wrapper info
        wrapper_type = msg.get_wrapper_type()
        tag = wrapper_type.value.xml_tag
        header = wrapper_type.value.header
        header_style = wrapper_type.value.rich_style
        attrs = msg.get_wrapper_attrs()
        
        # Opening tag (dim)
        print_targets.append(Text(f"<{tag} {attrs}>", style="dim"))
        
        # Header (styled)
        if header:
            print_targets.append(Text(f"\n{header}\n\n", style=header_style))
        
        # Inner content parts
        has_content = False
        for part in msg.iter_visible_parts(flags):
            has_content = True
            
            if part.kind == MessagePartKind.TEXT:
                # Only TEXT goes through Markdown
                print_targets.append(Markdown(part.data))
            
            elif part.kind == MessagePartKind.THINKING:
                bt = ContentBlockType.THINKING
                print_targets.append(Text(f"\n<{bt.value.xml_tag}>\n", style="dim"))
                print_targets.append(Text(part.data, style=bt.value.rich_style))
                print_targets.append(Text(f"\n</{bt.value.xml_tag}>", style="dim"))
            
            elif part.kind == MessagePartKind.TOOL:
                print_targets.append(Text("\n", style="dim"))
                print_targets.extend(render_tool_rich(part.data))
        
        # Closing tag
        if has_content:
            print_targets.append(Text(f"\n</{tag}>", style="dim"))
        else:
            print_targets.append(Text(f"</{tag}>", style="dim"))
        
        print_targets.append(Text("\n", style="dim"))
    
    get_console().print(*print_targets)
```

**Verification**:
- `test_rich_output_contains_thinking`: PASS ✓
- `test_rich_output_contains_tools`: PASS ✓
- `test_rich_xml_equivalence`: PASS ✓

---

### Phase 7: Integration (Wire Up Remaining Call Sites)

**7.1** Update `format_to_xml()` to use `render_message_inner_xml()`

Current:
```python
content = msg.get_visible_content(flags)
```

Change to:
```python
content = render_message_inner_xml(msg, flags)
```

(This is equivalent since `get_visible_content` now delegates, but makes the intent clear)

**7.2** Update `format_to_json()` to use `render_message_inner_xml()`

Find the call to `get_visible_content()`, replace with `render_message_inner_xml()`.

**7.3** Update `cmd_search()` to use `render_message_inner_xml()`

The search matches against visible content. Replace `get_visible_content()` call.

**Verification**:
- `test_xml_output_unchanged`: PASS
- JSON output format unchanged
- Search functionality unchanged

---

### Phase 8: Cleanup

**8.1** Remove deprecated `format_tool_for_xml()` wrapper

Search for any remaining callers. Should be none after Phase 7.
Delete the function.

**8.2** Remove deprecated `get_visible_content()` wrapper

Search for any remaining callers. Should be none after Phase 7.
Delete the method from `Message` class.

**8.3** Final verification

- Run full test suite: `./tests/run_all.sh`
- All tests pass
- No remaining references to deleted functions

---

## 6. Verification Checkpoints

| After Phase | Verification | Expected |
|-------------|--------------|----------|
| 0 | Run new tests | XML: PASS, Rich: FAIL |
| 1 | Python parses file | No errors |
| 2 | `ccc ... -t --color=never` | Identical to before |
| 3 | Manual REPL inspection | Parts yield correctly |
| 4 | `test_xml_output_unchanged` | PASS |
| 5 | Unit test render_tool_rich | Correct Rich objects |
| 6 | `test_rich_output_contains_*` | PASS ✓ |
| 7 | All integration points | Unchanged behavior |
| 8 | Full test suite | All PASS |

---

## 7. File Changes Summary

### New code (~150 lines)
- `MessagePartKind` enum (5 lines)
- `ToolParts` NamedTuple (10 lines)
- `MessagePart` NamedTuple (8 lines)
- `tool_to_parts()` (~50 lines, extracted from `format_tool_for_xml`)
- `render_tool_xml()` (~10 lines)
- `render_tool_rich()` (~20 lines)
- `render_message_inner_xml()` (~20 lines)
- `Message.iter_visible_parts()` (~25 lines)

### Modified code
- `render_messages_with_rich()`: Complete rewrite (~40 lines)
- `format_to_xml()`: 1 line change
- `format_to_json()`: 1 line change
- `cmd_search()`: 1 line change

### Deleted code (~80 lines)
- `format_tool_for_xml()` (after extraction to `tool_to_parts`)
- `Message.get_visible_content()` (after migration)

### New test file
- `tests/test_structured_rendering.sh` (~60 lines)
- `tests/data/golden_xml_output.txt` (generated)

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Subtle output differences | Golden reference test catches any change |
| Forgotten call site | grep for deprecated function names before deletion |
| Rich rendering edge cases | Test with multiple real conversation files, not just synthetic |
| Performance regression | Profile if concerned; new code has similar complexity |

---

## 9. Commit Strategy

1. **Commit 1**: Add test file + golden reference (Phase 0)
2. **Commit 2**: Add data structures (Phase 1)
3. **Commit 3**: Add tool normalization + renderers (Phases 2, 5)
4. **Commit 4**: Add message parts iterator + inner renderer (Phases 3, 4)
5. **Commit 5**: Rewrite Rich renderer (Phase 6) — THE FIX
6. **Commit 6**: Wire up remaining call sites (Phase 7)
7. **Commit 7**: Cleanup deprecated code (Phase 8)

Or squash into fewer commits if preferred. Each commit should leave the codebase in a working state.
