from __future__ import annotations

import json
import re
import textwrap
from datetime import datetime
from pathlib import Path

from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.markdown import Markdown as _Markdown
from rich.padding import Padding
from rich.segment import Segment
from rich.text import Text

from .console import get_console
from .model import ConversationFlags, Message, Provider
from .parsing import get_display_session_id
from .parts import MessagePartKind
from .registry import ContentBlockType
from .tools import render_tool_rich, render_tool_xml
from .utils import collapse_home


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


def _compact_header_meta(msg: Message, conversation_tag: str | None) -> str:
    """Dim suffix after a compact role badge: conversation id · #index · model."""
    parts = (
        conversation_tag,
        f"#{msg.index}",
        msg.model.removeprefix("claude-") if msg.model else None,
    )
    return "  ·  ".join(part for part in parts if part)

_HEADER_BADGE_STYLE: dict[str, str] = {
    "user-message": "bold white on #3b82f6",
    "user-command-input": "bold white on #3b82f6",
    "user-command-output": "bold white on #3b82f6",
    "recap": "bold white on #1d4ed8",
    "assistant-response": "bold white on #7c3aed",
    "agent": "bold white on #0f766e",
    "session-rename": "bold white on #d97706",
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


def build_messages_group(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
    *,
    highlight_regex: re.Pattern[str] | None = None,
    conversation_tag: str | None = None,
    compact_header: bool = False,
) -> Group:
    """Build the Rich renderable for a list of messages.

    Key invariant: Only TEXT content is passed to Markdown().
    XML-like tags are always rendered as dim Text.

    This fixes the bug where Rich's Markdown() stripped custom tags like
    <thinking> and <tool-input> because it treated them as HTML.

    Search passes ``highlight_regex`` to mark matched terms in bodies and
    ``conversation_tag`` to restate the session's short id on every message
    header; both default to off, so parse output is unchanged. ``compact_header``
    (used by the search Panel) folds the role, id, index, and model onto one
    line and drops the dim ``<tag>`` open/close lines, which the Panel and its
    ``---`` separators already make redundant.
    """
    # Pattern to detect HTML/XML-like tags in content
    xml_tag_pattern = re.compile(r"<[a-zA-Z][a-zA-Z0-9\\-]*[>\\s]")

    print_targets = []

    for i, msg in enumerate(messages):
        parts = msg.iter_visible_parts(flags, tool_id_map)
        if not parts:
            continue

        if i > 0:
            print_targets.append(Markdown("---"))

        wrapper_type = msg.get_wrapper_type()
        tag = wrapper_type.value.xml_tag
        header = msg.get_header()
        attrs = msg.get_wrapper_attrs()

        if not compact_header:
            print_targets.append(Text(f"<{tag} {attrs}>\n", style="dim"))

        if header:
            header_text = re.sub(r"^#+\s*", "", header)
            badge_style = _HEADER_BADGE_STYLE.get(tag, "bold white on blue")
            if compact_header:
                header_line = Text()
                header_line.append(f" {header_text} ", style=badge_style)
                meta = _compact_header_meta(msg, conversation_tag)
                if meta:
                    header_line.append(f"  ·  {meta}", style="search.idtag")
                print_targets.append(header_line)
                print_targets.append(Text(""))
            else:
                print_targets.append(Text(f" {header_text} ", style=badge_style))
                if conversation_tag:
                    print_targets.append(
                        Text(f"  ·  {conversation_tag}", style="search.idtag")
                    )
                print_targets.append(Text("\n"))

        for part in parts:
            if part.kind == MessagePartKind.TEXT:
                # Use Text() for content with XML tags to avoid Markdown mangling
                if xml_tag_pattern.search(part.data):
                    escaped_data = re.sub(
                        r"<(/?)([a-zA-Z][a-zA-Z0-9\\-]*)(\\s+[^>]*?)?>",
                        r"\\<\1\2\3>",
                        part.data,
                    )
                    print_targets.append(
                        _text_renderable(escaped_data, highlight_regex)
                    )
                else:
                    print_targets.append(_text_renderable(part.data, highlight_regex))

            elif part.kind == MessagePartKind.THINKING:
                bt = ContentBlockType.THINKING
                print_targets.append(Text(f"\n<{bt.value.xml_tag}>\n", style="dim"))
                print_targets.append(Text(part.data, style=bt.value.rich_style))
                print_targets.append(Text(f"\n</{bt.value.xml_tag}>", style="dim"))

            elif part.kind == MessagePartKind.SUBAGENT_TASK:
                bt = ContentBlockType.SUBAGENT_TASK
                print_targets.append(Text(f"\n<{bt.value.xml_tag}>\n", style="dim"))
                print_targets.append(Text(part.data, style=bt.value.rich_style))
                print_targets.append(Text(f"\n</{bt.value.xml_tag}>", style="dim"))

            elif part.kind == MessagePartKind.TOOL:
                print_targets.append(Text("\n", style="dim"))
                print_targets.extend(render_tool_rich(part.data))

        if not compact_header:
            print_targets.append(Text(f"</{tag}>", style="dim"))

    return Group(*print_targets)


def render_messages_with_rich(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> None:
    """Render messages to the module console with the standard parse padding."""
    group = build_messages_group(messages, flags, tool_id_map)
    get_console().print(Padding(group, pad=(0, 2, 0, 2)))
