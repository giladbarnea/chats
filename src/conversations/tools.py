from __future__ import annotations

import json

from rich.markdown import Markdown
from rich.text import Text

from .parts import ToolParts
from .registry import TOOL_SCHEMAS, ContentBlockType
from .utils import extract_text_from_content, shorten_tool_use_id


def _format_edit_content(input_data: dict) -> str:
    """Format Edit tool content with old_string/new_string blocks."""
    parts = []
    if old_string := input_data.get("old_string", ""):
        parts.append(f"old_string:\n```\n{old_string}\n```")
    if new_string := input_data.get("new_string", ""):
        parts.append(f"new_string:\n```\n{new_string}\n```")
    return "\n".join(parts)


def tool_to_parts(tool: dict, id_map: dict[str, str] | None = None) -> ToolParts:
    """Convert a raw tool dict to normalized ToolParts.

    Contains ALL tool formatting decisions:
    - TOOL_SCHEMAS attribute extraction
    - Edit tool special-casing
    - Unknown tool JSON fallback
    - tool_result formatting
    """
    tool_type = tool.get("type", "")
    input_tag = ContentBlockType.TOOL_INPUT.value.xml_tag
    output_tag = ContentBlockType.TOOL_OUTPUT.value.xml_tag

    if tool_type == "tool_use":
        return _tool_use_to_parts(tool, input_tag)

    if tool_type == "tool_result":
        return _tool_result_to_parts(tool, output_tag, id_map)

    # Unknown type: fallback to JSON dump
    return ToolParts(
        tag=input_tag,
        attrs=[("name", "Unknown")],
        content=f"```json\n{json.dumps(tool, indent=2)}\n```",
        is_empty=False,
    )


def _tool_use_to_parts(tool: dict, tag: str) -> ToolParts:
    """Convert tool_use to ToolParts."""
    name = tool.get("name", "Unknown")
    input_data = tool.get("input", {})
    schema = TOOL_SCHEMAS.get(name)

    attrs: list[tuple[str, str]] = [("name", name)]
    if short_tool_id := shorten_tool_use_id(tool.get("id")):
        attrs.append(("id", short_tool_id))

    content: str | None = None

    if schema:
        for key in schema.attr_keys:
            if val := input_data.get(key):
                attrs.append((key, str(val)))

        if name == "Edit":
            content = _format_edit_content(input_data)
        elif schema.content_key and (val := input_data.get(schema.content_key)):
            lang = schema.content_lang or ""
            content = f"```{lang}\n{val}\n```"
    elif input_data:
        content = f"```json\n{json.dumps(input_data, indent=2)}\n```"

    return ToolParts(tag=tag, attrs=attrs, content=content, is_empty=not content)


def _tool_result_to_parts(
    tool: dict, tag: str, id_map: dict[str, str] | None = None
) -> ToolParts:
    """Convert tool_result to ToolParts."""
    content_text = "\n".join(extract_text_from_content(tool.get("content", "")))
    is_error = tool.get("is_error", False)
    tool_use_id = tool.get("tool_use_id")

    attrs: list[tuple[str, str]] = []
    if id_map and tool_use_id and (name := id_map.get(tool_use_id)):
        attrs.append(("name", name))
    if short_tool_id := shorten_tool_use_id(tool_use_id):
        attrs.append(("id", short_tool_id))
    if is_error:
        attrs.append(("is_error", "true"))

    content = f"```\n{content_text}\n```" if content_text else None

    return ToolParts(tag=tag, attrs=attrs, content=content, is_empty=not content)


def render_tool_xml(parts: ToolParts) -> str:
    """Render ToolParts to XML string."""
    attr_str = " ".join(f'{k}="{v}"' for k, v in parts.attrs)
    tag_open = f"<{parts.tag} {attr_str}>" if attr_str else f"<{parts.tag}>"

    if parts.is_empty:
        return f"{tag_open}</{parts.tag}>"
    return f"{tag_open}\n{parts.content}\n</{parts.tag}>"


def render_tool_rich(parts: ToolParts) -> list[Text | Markdown]:
    """Render ToolParts to Rich objects for console.print()."""
    attr_str = " ".join(f'{k}="{v}"' for k, v in parts.attrs)
    tag_open = f"<{parts.tag} {attr_str}>" if attr_str else f"<{parts.tag}>"

    if parts.is_empty:
        return [Text(f"{tag_open}</{parts.tag}>", style="dim")]

    result: list[Text | Markdown] = [Text(tag_open, style="dim")]
    if parts.content:
        result.append(Markdown(parts.content))
    result.append(Text(f"</{parts.tag}>", style="dim"))
    return result
