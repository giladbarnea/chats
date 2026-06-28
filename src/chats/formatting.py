from __future__ import annotations

import difflib
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.markdown import Markdown as _Markdown
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from . import theme
from .console import get_console
from .model import ConversationFlags, Message, Provider
from .parsing import get_display_session_id
from .parts import MessagePart, MessagePartKind, ToolParts
from .registry import ContentBlockType
from .tools import render_tool_xml
from .utils import collapse_home, elide_to_width


class PaddedInlineCodeMarkdown(_Markdown):
    """Markdown subclass that renders inline code with 1-space padding on each side."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for token in self.parsed:
            for child in token.children or []:
                if child.type == "code_inline" and child.content:
                    child.content = f" {child.content} "


Markdown = PaddedInlineCodeMarkdown


class HighlightedMarkdown:
    """Render Markdown, then re-style substrings matching a regex (search hits).

    Works on the rendered segment stream rather than reaching into Rich's
    Markdown internals, so the term highlight survives full markdown formatting
    and the renderable still wraps/sizes itself inside a Panel. Matches that fall
    within one rendered run — the common case for a search term — are
    highlighted; a term split across a style boundary is left untouched.
    """

    def __init__(self, markup: str, regex: re.Pattern[str], style: str) -> None:
        self.markup = markup
        self.regex = regex
        self.style_name = style

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        highlight = console.get_style(self.style_name)
        for text, style, control in console.render(Markdown(self.markup), options):
            if control is not None or not text or not self.regex.search(text):
                yield Segment(text, style, control)
                continue
            cursor = 0
            for match in self.regex.finditer(text):
                if match.start() > cursor:
                    yield Segment(text[cursor : match.start()], style, control)
                combined = style + highlight if style else highlight
                yield Segment(match.group(), combined, control)
                cursor = match.end()
            if cursor < len(text):
                yield Segment(text[cursor:], style, control)


def _text_renderable(markup: str, highlight_regex: re.Pattern[str] | None):
    """Return a Markdown renderable, highlighting search terms when asked."""
    if highlight_regex is None:
        return Markdown(markup)
    return HighlightedMarkdown(markup, highlight_regex, "search.match")


class LeftRail:
    """Prefix every line of a renderable with a thin colored left rail (``▎``).

    The rail's vertical span marks a tool block's extent without a horizontal
    rule (which is already the message/conversation separator). Renders the
    child at reduced width so the rail fits inside its enclosing Panel.
    """

    def __init__(self, renderable, style: str, glyph: str = "▎ ") -> None:
        self.renderable = renderable
        self.style = style
        self.glyph = glyph

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        rail = Segment(self.glyph, console.get_style(self.style))
        inner = options.update_width(max(1, options.max_width - len(self.glyph)))
        lines = console.render_lines(self.renderable, inner, pad=False)

        is_blank = lambda line: all(not segment.text.strip() for segment in line)
        start, end = 0, len(lines)
        while start < end and is_blank(lines[start]):
            start += 1
        while end > start and is_blank(lines[end - 1]):
            end -= 1

        for line in lines[start:end]:
            yield rail
            yield from line
            yield Segment.line()


def _tool_key_arg(attrs: list[tuple[str, str]]) -> str | None:
    """The first display-worthy tool argument (path / pattern / url), collapsed."""
    for key, value in attrs:
        if key in ("name", "id", "is_error"):
            continue
        collapsed = collapse_home(value)
        if "/" in collapsed:
            collapsed = elide_to_width(collapsed, 44, where="middle")
        return collapsed
    return None


def _edit_diff_renderable(input_data: dict, accent: str) -> LeftRail | None:
    """Render an Edit's old_string→new_string as a colored unified diff."""
    old = str(input_data.get("old_string", "")).splitlines()
    new = str(input_data.get("new_string", "")).splitlines()
    body = Text()
    for line in list(difflib.unified_diff(old, new, lineterm="", n=2))[2:]:
        if line.startswith("@@"):
            continue
        style = (
            "diff.add"
            if line.startswith("+")
            else "diff.remove"
            if line.startswith("-")
            else "dim"
        )
        body.append(line + "\n", style=style)
    return LeftRail(body, accent) if body else None


def _strip_read_line_numbers(text: str) -> tuple[str, int]:
    """Strip Read's ``<n>\\t`` line-number gutter, returning (code, first_line)."""
    lines = text.split("\n")
    stripped: list[str] = []
    first: int | None = None
    matched = 0
    for line in lines:
        match = re.match(r"\s*(\d+)\t(.*)$", line)
        if match:
            matched += 1
            first = first if first is not None else int(match.group(1))
            stripped.append(match.group(2))
        else:
            stripped.append(line)
    if matched < max(1, len(lines) // 2):
        return text, 1
    return "\n".join(stripped), first or 1


def _read_output_renderable(
    output_text: str, file_path: str, accent: str
) -> LeftRail:
    """Render a Read tool result as source highlighted by the file's extension."""
    code, start_line = _strip_read_line_numbers(output_text)
    try:
        lexer = Syntax.guess_lexer(file_path, code)
    except Exception:
        lexer = "text"
    syntax = Syntax(
        code,
        lexer,
        theme="monokai",
        line_numbers=True,
        start_line=start_line,
        word_wrap=True,
    )
    return LeftRail(syntax, accent)


def render_tool_rich(
    parts: ToolParts, input_by_id: dict[str, dict] | None = None
) -> list:
    """Render a tool call/result tag-free: a ⏺/⎿ header plus a colored left rail.

    Edit renders as a diff and a Read result is highlighted by the extension of
    its paired input's path (looked up via ``input_by_id``); every other tool
    falls back to its fenced markdown content.
    """
    is_result = parts.tag == ContentBlockType.TOOL_OUTPUT.value.xml_tag
    is_error = any(key == "is_error" for key, _ in parts.attrs)
    name = parts.name or next(
        (value for key, value in parts.attrs if key == "name"), "Tool"
    )

    accent = "tool.error" if is_error else "tool.result" if is_result else "tool.call"
    header = Text()
    header.append(f"{'⎿' if is_result else '⏺'} ", style=accent)
    header.append(name, style=accent)
    if is_error:
        header.append("  ·  error", style="tool.error")
    if key_arg := _tool_key_arg(parts.attrs):
        header.append(f"  ·  {key_arg}", style="message.meta")

    out: list = [header]
    out.append(_tool_body_renderable(parts, name, is_error, is_result, accent, input_by_id))
    return [item for item in out if item is not None]


def _tool_body_renderable(
    parts: ToolParts,
    name: str,
    is_error: bool,
    is_result: bool,
    accent: str,
    input_by_id: dict[str, dict] | None,
):
    """Pick the richest body for a tool: Edit diff, Read highlight, or fenced content."""
    if name == "Edit" and parts.input_data:
        return _edit_diff_renderable(parts.input_data, accent)

    read_input = (input_by_id or {}).get(parts.tool_use_id or "")
    if (
        is_result
        and not is_error
        and name == "Read"
        and parts.output_text
        and read_input
        and read_input.get("file_path")
    ):
        return _read_output_renderable(
            parts.output_text, read_input["file_path"], accent
        )

    if not parts.is_empty and parts.content:
        return LeftRail(Markdown(parts.content), accent)
    return None


def _tool_input_by_id(messages: list[Message]) -> dict[str, dict]:
    """Map each tool_use id to its raw input, so an output can find its input."""
    return {
        tool["id"]: tool.get("input", {})
        for message in messages
        for tool in message.tools
        if tool.get("type") == "tool_use" and "id" in tool
    }


def _compact_header_meta(msg: Message, conversation_tag: str | None) -> str:
    """Dim suffix after a compact role badge: conversation id · #index · model · date."""
    parts = (
        conversation_tag,
        f"#{msg.index}",
        msg.model.removeprefix("claude-") if msg.model else None,
        msg.get_display_date(),
    )
    return "  ·  ".join(part for part in parts if part)


def _message_content_renderables(
    parts: list[MessagePart],
    highlight_regex: re.Pattern[str] | None,
    input_by_id: dict[str, dict] | None = None,
) -> list:
    """Render a message's visible parts (text, thinking, tools) to renderables.

    The message wrapper tag/header is the caller's job; this is only the body,
    shared by the inline (search) and per-message-Panel (parse) views.
    """
    # Pattern to detect HTML/XML-like tags in content
    xml_tag_pattern = re.compile(r"<[a-zA-Z][a-zA-Z0-9-]*[>\s]")
    out: list = []
    for part in parts:
        if out:
            out.append(Text(""))

        if part.kind == MessagePartKind.TEXT:
            # Escape tag-like text so Markdown leaves it literal, not dropped
            if xml_tag_pattern.search(part.data):
                escaped_data = re.sub(
                    r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)(\s+[^>]*?)?>",
                    r"\\<\1\2\3>",
                    part.data,
                )
                out.append(_text_renderable(escaped_data, highlight_regex))
            else:
                out.append(_text_renderable(part.data, highlight_regex))

        elif part.kind == MessagePartKind.THINKING:
            out.append(Text("✻ thinking", style="message.meta"))
            out.append(LeftRail(Text(part.data, style="dim italic"), "message.meta"))

        elif part.kind == MessagePartKind.SUBAGENT_TASK:
            out.append(Text("✻ subagent task", style="message.meta"))
            out.append(LeftRail(Text(part.data, style="italic"), "message.meta"))

        elif part.kind == MessagePartKind.TOOL:
            out.extend(render_tool_rich(part.data, input_by_id))

    return out


def _message_header_badge(msg: Message, *, conversation_tag: str | None = None) -> Text:
    """A message's role badge: colored role chip + dim id/index/model suffix.

    Shared by both colored views — the parse per-message Panel title and the
    search Panel's inline per-message headers (the latter passing the
    conversation's short id as ``conversation_tag``).
    """
    tag = msg.get_wrapper_type().value.xml_tag
    header = msg.get_header()
    header_text = re.sub(r"^#+\s*", "", header) if header else msg.role.title()
    badge = Text()
    if msg.branch_id:
        badge.append(f" ⑂{msg.branch_id} ", style="bold white on #475569")
    badge.append(
        f" {header_text} ",
        style=f"bold {theme.INK} on {_ROLE_HUE.get(tag, _DEFAULT_ROLE_HUE)}",
    )
    meta = _compact_header_meta(msg, conversation_tag)
    if meta:
        badge.append(f"  ·  {meta}", style="message.meta")
    return badge


def _message_border_style(tag: str) -> Style:
    """The message's role hue, used as the Panel border color."""
    return Style(color=_ROLE_HUE.get(tag, _DEFAULT_ROLE_HUE))


_DEFAULT_ROLE_HUE = theme.GRAY

# One distinct palette hue per role, well-separated around the color wheel: the
# human is blue, the AI magenta, a subagent cyan; the system events (recap,
# compaction, rename) take the remaining green/yellow/red. The three user-* tags
# share blue on purpose — they are one actor.
_ROLE_HUE: dict[str, str] = {
    "user-message": theme.BLUE,
    "user-command-input": theme.BLUE,
    "user-command-output": theme.BLUE,
    "recap": theme.GREEN,
    "compaction": theme.YELLOW,
    "assistant-response": theme.MAGENTA,
    "agent": theme.CYAN,
    "session-rename": theme.RED,
}


def render_message_inner_xml(
    msg: Message, flags: ConversationFlags, tool_id_map: dict[str, str] | None = None
) -> str:
    """Render message inner content (text, thinking, tools) to XML string.

    Iterates msg.iter_visible_parts(flags), formats each part.
    Does NOT include outer wrapper tag or header.
    """
    output_parts: list[str] = []
    tool_parts: list[str] = []

    def flush_tools() -> None:
        nonlocal tool_parts
        if tool_parts:
            output_parts.append("\n".join(tool_parts))
            tool_parts = []

    for part in msg.iter_visible_parts(flags, tool_id_map):
        if part.kind == MessagePartKind.TEXT:
            flush_tools()
            output_parts.append(part.data)

        elif part.kind == MessagePartKind.THINKING:
            flush_tools()
            tag = ContentBlockType.THINKING.value.xml_tag
            output_parts.append(f"<{tag}>\n{part.data}\n</{tag}>")

        elif part.kind == MessagePartKind.SUBAGENT_TASK:
            flush_tools()
            tag = ContentBlockType.SUBAGENT_TASK.value.xml_tag
            output_parts.append(f"<{tag}>\n{part.data}\n</{tag}>")

        elif part.kind == MessagePartKind.TOOL:
            tool_parts.append(render_tool_xml(part.data))

    flush_tools()

    return "\n\n".join(output_parts)


def format_to_xml(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> str:
    """Format messages to XML-style tags."""
    output_parts = []

    for msg in messages:
        content = render_message_inner_xml(msg, flags, tool_id_map)
        if not content:
            continue

        # Strip trailing blank lines and single trailing space from last line
        content = content.rstrip("\n")
        lines = content.split("\n")
        if lines and lines[-1].endswith(" ") and not lines[-1].endswith("  "):
            lines[-1] = lines[-1][:-1]
        content = "\n".join(lines)

        wrapper_type = msg.get_wrapper_type()
        tag = wrapper_type.value.xml_tag
        header = msg.get_header()
        attrs = msg.get_wrapper_attrs()

        if wrapper_type is ContentBlockType.AGENT:
            content = textwrap.indent(content, "  ")

        output_parts.append(f"<{tag} {attrs}>\n{header}\n\n{content}\n</{tag}>")

    return "\n\n---\n\n".join(output_parts)


def format_to_json(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> str:
    """Format messages to structured JSON."""
    output = []

    for msg in messages:
        message_json = msg.to_json_dict(flags, tool_id_map)
        if message_json is None:
            continue
        output.append(message_json)

    return json.dumps(output, indent=2, ensure_ascii=False)


def format_to_raw(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> str:
    """
    Format messages to "raw" Markdown.

    - Single message: output just its content (no role header).
    - Multiple messages: include headers and separators.
    """
    visible: list[tuple[Message, str]] = []

    for msg in messages:
        if content := render_message_inner_xml(msg, flags, tool_id_map):
            visible.append((msg, content.rstrip()))

    if not visible:
        return ""

    if len(visible) == 1:
        return visible[0][1]

    blocks: list[str] = []
    for msg, content in visible:
        header = msg.get_header()
        if msg.get_wrapper_type() is ContentBlockType.AGENT:
            content = textwrap.indent(content, "  ")
        block = f"{header}\n\n{content}" if header else content
        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


def build_metadata_text(
    file_path: Path,
    cwd: str | None,
    total_messages: int,
    matched_messages: int | None = None,
    matching_summaries: list[str] | None = None,
    *,
    provider: Provider | None = None,
    forked_from: str | None = None,
    last_custom_title: str | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
    include_frontmatter_separator: bool = True,
) -> str:
    """Build conversation metadata as YAML frontmatter text."""
    yaml_lines = [f"session_id: {get_display_session_id(file_path)}"]

    if provider is not None:
        yaml_lines.append(f"provider: {provider}")

    if forked_from:
        yaml_lines.append(f"forked_from: {forked_from}")

    if cwd:
        yaml_lines.append(f"directory: {collapse_home(cwd)}")

    yaml_lines.append(f"history_path: {collapse_home(str(file_path))}")

    stat = None
    if created_at is None or modified_at is None:
        try:
            stat = file_path.stat()
        except OSError:
            stat = None

    resolved_created_at = created_at
    if resolved_created_at is None and stat is not None:
        try:
            resolved_created_at = datetime.fromtimestamp(stat.st_birthtime)
        except AttributeError:
            pass

    if resolved_created_at is not None:
        yaml_lines.append(
            f'created: "{resolved_created_at.strftime("%Y-%m-%d %H:%M")}"'
        )

    resolved_modified_at = modified_at
    if resolved_modified_at is None and stat is not None:
        resolved_modified_at = datetime.fromtimestamp(stat.st_mtime)

    if resolved_modified_at is not None:
        yaml_lines.append(
            f'modified: "{resolved_modified_at.strftime("%Y-%m-%d %H:%M")}"'
        )
    yaml_lines.append(f"messages: {total_messages}")

    if matched_messages is not None:
        yaml_lines.append(f"matches: {matched_messages}")

    if matching_summaries:
        for summary in matching_summaries:
            yaml_lines.append(f'matched_summary: "{summary}"')

    if last_custom_title:
        yaml_lines.append(f'custom_title: "{last_custom_title}"')

    if include_frontmatter_separator:
        return "\n".join(["---", *yaml_lines])
    return "\n".join(yaml_lines)


def print_metadata(
    file_path: Path,
    cwd: str | None,
    total_messages: int,
    matched_messages: int | None = None,
    matching_summaries: list[str] | None = None,
    *,
    provider: Provider | None = None,
    forked_from: str | None = None,
    last_custom_title: str | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
    color: bool = False,
    dedupe_frontmatter_separators: bool = False,
    include_frontmatter_separator: bool = True,
) -> None:
    """Print conversation metadata to stdout in YAML format."""
    content = build_metadata_text(
        file_path,
        cwd,
        total_messages,
        matched_messages,
        matching_summaries,
        provider=provider,
        forked_from=forked_from,
        last_custom_title=last_custom_title,
        created_at=created_at,
        modified_at=modified_at,
        include_frontmatter_separator=include_frontmatter_separator,
    )

    if color:
        get_console().print(Text(content, style="dim"))
        if include_frontmatter_separator and not dedupe_frontmatter_separators:
            get_console().print(Text("---", style="dim"))
    else:
        print(content)
        if include_frontmatter_separator and not dedupe_frontmatter_separators:
            print("---")


def build_session_title(
    file_path: Path,
    *,
    custom_title: str | None = None,
    cwd: str | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
) -> Text:
    """The rich parse view's header: a left-aligned white title carrying the
    session's name (when one exists), id, working directory, and created/modified
    dates.

    Distinct from the YAML frontmatter (``build_metadata_text``): a title, not a
    block — white so it reads as a heading above the role-colored message panels.
    """
    title = Text()
    if custom_title:
        title.append(custom_title, style="bold white")
        title.append("  ·  ", style="message.meta")
        title.append(get_display_session_id(file_path), style="white")
    else:
        title.append(get_display_session_id(file_path), style="bold white")

    if cwd:
        title.append("  ·  ", style="message.meta")
        title.append(collapse_home(cwd), style="message.meta")

    for label, value in (("created", created_at), ("modified", modified_at)):
        if value is not None:
            title.append("  ·  ", style="message.meta")
            title.append(f"{label} {value:%Y-%m-%d %H:%M}", style="message.meta")
    return title


def build_messages_group(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
    *,
    highlight_regex: re.Pattern[str] | None = None,
    conversation_tag: str | None = None,
) -> Group:
    """Build the inline Rich body for a conversation (the search Panel's content).

    Each message renders as a one-line role badge over its parts, with ``---``
    rules between messages. ``highlight_regex`` marks matched search terms in
    bodies; ``conversation_tag`` restates the session's short id on each header.
    """
    input_by_id = _tool_input_by_id(messages)
    print_targets = []

    for i, msg in enumerate(messages):
        parts = msg.iter_visible_parts(flags, tool_id_map)
        if not parts:
            continue

        if i > 0:
            print_targets.append(Markdown("---"))

        print_targets.append(
            _message_header_badge(msg, conversation_tag=conversation_tag)
        )
        print_targets.append(Text(""))
        print_targets.extend(
            _message_content_renderables(parts, highlight_regex, input_by_id)
        )

    return Group(*print_targets)


def build_message_panels(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
    *,
    highlight_regex: re.Pattern[str] | None = None,
) -> Group:
    """Render each message as its own titled, role-colored Panel (parse color view).

    The message wrapper tags are dropped; their job is taken over by the box
    (per-message orientation that survives scrolling a large message) and the
    colorful title chip, which carries the role plus index and model. Border and
    chip keep each message type's existing hue.
    """
    input_by_id = _tool_input_by_id(messages)
    panels: list = []
    for msg in messages:
        parts = msg.iter_visible_parts(flags, tool_id_map)
        if not parts:
            continue
        body = _message_content_renderables(parts, highlight_regex, input_by_id)
        panels.append(
            Panel(
                Group(*body),
                title=_message_header_badge(msg),
                title_align="left",
                border_style=_message_border_style(msg.get_wrapper_type().value.xml_tag),
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
    return Group(*panels)


def render_message_panels(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> None:
    """Print the colored per-message Panel view (parse color path)."""
    get_console().print(build_message_panels(messages, flags, tool_id_map))
