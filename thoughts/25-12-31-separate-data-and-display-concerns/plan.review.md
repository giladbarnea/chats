# Plan Review: Separate Data and Display Concerns (`conversations` / `ccc`)

## Context (What’s broken and why)

- `--color=always` routes output through `render_messages_with_rich()`.
- Today, `render_messages_with_rich()` calls `Message.get_visible_content()` and then does `Markdown(content)`.
- `get_visible_content()` produces an XML+markdown hybrid string that includes custom tags like `<thinking>`, `<tool-input>`, `<tool-output>`.
- Rich Markdown treats `<…>` as HTML and strips unknown tags **including their contents**, so thinking/tool blocks vanish in colored output.

## Requirements from this review

- Fix the bug **and** fully land the “structured data → render last” architecture in one go (no interim partial refactor).
- Prevent “tool rendering drift” between XML and Rich output without a large/over-engineered redesign.

---

## Proposed Plan (Complete in one go)

### 1) Introduce a single “visible parts” API on `Message` (data-only)

Add a new structured iterator as the single source of truth for “what’s visible”:

- `Message.iter_visible_parts(flags) -> list[MessagePart]` (or an iterator)
- `MessagePart` is a small typed structure (e.g. `NamedTuple`/`dataclass`) with a `kind` and payload:
  - `TEXT` → markdown string (from `msg.text`)
  - `THINKING` → plain string (from `msg.thinking`)
  - `TOOL` → `ToolParts` (see below) derived from `msg.tools`
  - `PLAN` should be represented as a `TOOL` part with `name="ExitPlanMode"` (so it reuses tool rendering)

Goal: `Message` continues to store structured fields; the “visible parts” iterator decides visibility/order, but **does not** serialize into XML-ish strings.

### 2) Normalize tool formatting once (drift mitigation)

Replace parallel “tool formatting” logic with one shared normalization step and two thin renderers.

Add:

- `ToolParts` (a small dataclass/NamedTuple), e.g.:
  - `tag: str` (`"tool-input"` or `"tool-output"`)
  - `attrs: list[tuple[str, str]]` (ordered; preserves stable printing)
  - `body_markdown: str | None` (markdown string; may include fenced blocks)
  - `inline_if_empty: bool` (to preserve `<tool-input …></tool-input>` formatting)

Implement:

- `tool_to_parts(tool: dict, flags) -> ToolParts`
  - This contains *all* decisions currently embedded in `format_tool_for_xml()` (attrs extraction via `TOOL_SCHEMAS`, Edit special-casing, tool_result code fencing, unknown-tool fallback).
  - Plan rendering (`ExitPlanMode`) becomes `ToolParts(tag="tool-input", attrs=[("name","ExitPlanMode")], body_markdown=plan_text, …)` without pretending it was a real tool_use entry.

Then implement **two tiny renderers** that consume `ToolParts`:

- `render_tool_xml(parts: ToolParts) -> str` (string)
- `render_tool_rich(parts: ToolParts) -> list[Text|Markdown|str]` (Rich renderables)

This keeps “how tools are shaped” in one place (`tool_to_parts`) and avoids drift without introducing a heavy abstraction layer.

### 3) Replace `get_visible_content()` with renderers that consume parts

Refactor all call sites to stop using stringly-typed “content with embedded XML tags”.

Add:

- `render_message_inner_xml(msg, flags) -> str`
  - Iterates `msg.iter_visible_parts(flags)`
  - `TEXT` → append raw text
  - `THINKING` → wrap with `<thinking>…</thinking>` (using `ContentBlockType.THINKING.value.xml_tag`)
  - `TOOL/PLAN` → `render_tool_xml(tool_parts)`

Update these flows to use the new structured pipeline:

- `format_to_xml()` → uses `render_message_inner_xml()` and then wraps with the outer message tag + header (as today).
- `format_to_json()` → still outputs the same JSON schema (`[{role, content}]`) but `content` comes from `render_message_inner_xml()` (not from `get_visible_content()`).
- `cmd_search()` message matching → uses `render_message_inner_xml()` for “visible text” matching (same semantics as today, but derived from parts).

What to do with the old method:

- Keep `Message.get_visible_content()` as a thin compatibility wrapper that calls `render_message_inner_xml(self, flags)` (optional), but **no internal caller should depend on it** anymore.
- This makes the refactor “complete” (one data layer + renderers) while avoiding any external breakage if something imports/calls the method.

### 4) Rewrite `render_messages_with_rich()` to never pass tags to `Markdown()`

New Rich rendering logic:

- Outer wrapper tags (`<user-message …>`, `</user-message>`, etc.) are printed as `Text(..., style="dim")`.
- The wrapper header (`# User`, `# Assistant`, etc.) is printed as styled `Text` using `wrapper_type.value.rich_style`.
- For each inner part from `iter_visible_parts()`:
  - `TEXT` → `Markdown(text)` (this is the only place `Markdown()` is used for main content)
  - `THINKING` → open/close tags as dim `Text`; body as `Text(..., style=ContentBlockType.THINKING.value.rich_style)` (or Markdown if desired later)
  - `TOOL/PLAN` → `render_tool_rich(tool_parts)` (open/close tags as dim `Text`, body as `Markdown(body_markdown)` when present)
- Insert the same `---` message separator used in plain XML (`Text("---", style="dim")` plus matching blank lines), so `--color=always | strip_ansi` is materially comparable to `--color=never`.

Key invariant: **only actual content strings are passed to `Markdown()`**, never any `<…>` tags.

### 5) Tests: add a regression that would have caught this

Current gap: `tests/test_colors.sh` only checks “has ANSI codes” vs “no ANSI codes”.

Add a small regression test (extend `tests/test_flags.sh` or add a new file) that:

- Runs `--color always` *while piped* (to mirror the real failure mode) and strips ANSI codes.
- Asserts that thinking + tool content survives.

Concrete test inputs:

- Use `tests/data/synthetic_flags.jsonl` (it has thinking, tool_use, tool_result).
- Assertions (after ANSI stripping):
  - For `-T --color always`: contains `<thinking>` and `I should reply hello`
  - For `-t --color always`: contains `<tool-input` and `<tool-output>` and `result`

ANSI stripping should be done in-shell (portable) or via a tiny Python snippet; avoid depending on `decolor`.

---

## Divergences from the original plan (and why)

1) **Add `tool_to_parts()` normalization (new):**
   - Original direction implied parallel XML vs Rich tool rendering.
   - Drift is likely if we implement two independent formatters.
   - `tool_to_parts()` is the smallest “single source of truth” that prevents drift without introducing a large framework.

2) **Treat `ExitPlanMode` as a first-class tool-like part (new):**
   - Keeps plan rendering consistent with `<tool-input …>` handling.
   - Reduces special cases and keeps ordering/formatting rules in one place.

3) **Keep `get_visible_content()` only as a wrapper (optional):**
   - Allows the refactor to be complete (all internal flows use parts+renderers),
     while avoiding an unnecessary hard break for any external callers.

---

## Acceptance Criteria

- `ccc … --color=always` shows the same logical content as `--color=never` (no missing thinking/tool/plan blocks).
- `tests/test_flags.sh` (or the new regression test) would fail on the old behavior and pass on the new one.
- Tool formatting rules live in exactly one place (`tool_to_parts()`), consumed by both XML and Rich renderers.
