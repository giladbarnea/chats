from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from rich.markdown import Markdown
from rich.text import Text

from .console import get_console
from .model import ConversationFlags, Message
from .parts import MessagePartKind
from .registry import ContentBlockType
from .tools import render_tool_rich, render_tool_xml
from .utils import collapse_home


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
            # Tools are joined with \n (no blank line between them), prefixed with \n
            output_parts.append("\n" + "\n".join(tool_parts))
            tool_parts = []

    for part in msg.iter_visible_parts(flags, tool_id_map):
        if part.kind == MessagePartKind.TEXT:
            flush_tools()
            output_parts.append(part.data)

        elif part.kind == MessagePartKind.THINKING:
            flush_tools()
            tag = ContentBlockType.THINKING.value.xml_tag
            output_parts.append(f"\n<{tag}>\n{part.data}\n</{tag}>")

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
        header = wrapper_type.value.header
        attrs = msg.get_wrapper_attrs()

        output_parts.append(f"<{tag} {attrs}>\n{header}\n\n{content}\n</{tag}>")

    return "\n\n---\n\n".join(output_parts)


def format_to_json(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> str:
    """Format messages to JSON format."""
    output = []

    for msg in messages:
        if msg.role not in ("user", "assistant", "session-rename"):
            continue

        content = render_message_inner_xml(msg, flags, tool_id_map)
        if not content:
            continue

        output.append({"content": content.rstrip(), "role": msg.role})

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
        header = msg.get_wrapper_type().value.header
        block = f"{header}\n\n{content}" if header else content
        blocks.append(block)

    return "\n\n---\n\n".join(blocks)


def print_metadata(
    file_path: Path,
    cwd: str | None,
    total_messages: int,
    matched_messages: int | None = None,
    matching_summaries: list[str] | None = None,
    *,
    last_custom_title: str | None = None,
    color: bool = False,
    dedupe_frontmatter_separators: bool = False,
) -> None:
    """Print conversation metadata to stdout in YAML format."""
    stat = file_path.stat()

    yaml_lines = [f"session_id: {file_path.stem}"]

    if cwd:
        yaml_lines.append(f"directory: {collapse_home(cwd)}")

    yaml_lines.append(f"history_path: {collapse_home(str(file_path))}")

    try:
        created = datetime.fromtimestamp(stat.st_birthtime).strftime("%Y-%m-%d %H:%M")
        yaml_lines.append(f'created: "{created}"')
    except AttributeError:
        pass

    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    yaml_lines.append(f'modified: "{modified}"')
    yaml_lines.append(f"messages: {total_messages}")

    if matched_messages is not None:
        yaml_lines.append(f"matches: {matched_messages}")

    if matching_summaries:
        for summary in matching_summaries:
            yaml_lines.append(f'matched_summary: "{summary}"')

    if last_custom_title:
        yaml_lines.append(f'custom_title: "{last_custom_title}"')

    content = "\n".join(["---", *yaml_lines])

    if color:
        get_console().print(Text(content, style="dim"))
        if not dedupe_frontmatter_separators:
            get_console().print(Text("---", style="dim"))
    else:
        print(content)
        if not dedupe_frontmatter_separators:
            print("---")


def render_messages_with_rich(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> None:
    """Render messages to Rich console.

    Key invariant: Only TEXT content is passed to Markdown().
    XML-like tags are always rendered as dim Text.

    This fixes the bug where Rich's Markdown() stripped custom tags like
    <thinking> and <tool-input> because it treated them as HTML.
    """
    # Pattern to detect HTML/XML-like tags in content
    xml_tag_pattern = re.compile(r"<[a-zA-Z][a-zA-Z0-9\\-]*[>\\s]")

    print_targets = []

    for i, msg in enumerate(messages):
        parts = msg.iter_visible_parts(flags, tool_id_map)
        if not parts:
            continue

        if i > 0:
            print_targets.append(Text("\n---\n\n", style="dim"))

        wrapper_type = msg.get_wrapper_type()
        tag = wrapper_type.value.xml_tag
        header = wrapper_type.value.header
        header_style = wrapper_type.value.rich_style
        attrs = msg.get_wrapper_attrs()

        print_targets.append(Text(f"<{tag} {attrs}>", style="dim"))

        if header:
            print_targets.append(Text(f"\n{header}\n\n", style=header_style))

        for part in parts:
            if part.kind == MessagePartKind.TEXT:
                # Use Text() for content with XML tags to avoid Markdown mangling
                if xml_tag_pattern.search(part.data):
                    print_targets.append(Text(part.data))
                else:
                    print_targets.append(Markdown(part.data))

            elif part.kind == MessagePartKind.THINKING:
                bt = ContentBlockType.THINKING
                print_targets.append(Text(f"\n<{bt.value.xml_tag}>\n", style="dim"))
                print_targets.append(Text(part.data, style=bt.value.rich_style))
                print_targets.append(Text(f"\n</{bt.value.xml_tag}>", style="dim"))

            elif part.kind == MessagePartKind.TOOL:
                print_targets.append(Text("\n", style="dim"))
                print_targets.extend(render_tool_rich(part.data))

        print_targets.append(Text(f"\n</{tag}>", style="dim"))
        print_targets.append(Text("\n", style="dim"))

    get_console().print(*print_targets)