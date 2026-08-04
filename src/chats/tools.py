from __future__ import annotations

import json

from .parts import ToolParts
from .registry import TOOL_SCHEMAS, ContentBlockType
from .utils import extract_text_from_content, shorten_tool_use_id
from .xml_transport import render_inner_xml_block


def _format_edit_content(input_data: dict) -> str:
    """Format Edit tool content with old_string/new_string blocks."""
    parts = []
    if old_string := input_data.get("old_string", ""):
        parts.append(f"old_string:\n```\n{old_string}\n```")
    if new_string := input_data.get("new_string", ""):
        parts.append(f"new_string:\n```\n{new_string}\n```")
    return "\n".join(parts)


def tool_input_needs_wrapper(name: str, input_data: dict) -> bool:
    """Return whether flattening a tool-input dictionary would be ambiguous.

    >>> tool_input_needs_wrapper("Unknown", {"content": "value"})
    True
    >>> tool_input_needs_wrapper("Write", {"content": "value"})
    False
    >>> tool_input_needs_wrapper("Patch", {"input": {"type": "inner"}})
    True
    """
    input_keys = set(input_data)
    schema = TOOL_SCHEMAS.get(name)
    is_schema_content = schema is not None and schema.content_key == "content"
    return (
        bool({"type", "name", "id"}.intersection(input_keys))
        or (input_keys == {"content"} and not is_schema_content)
        or (
            input_keys == {"input"}
            and isinstance(input_data.get("input"), dict)
        )
    )


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


def tool_to_json(
    tool: dict,
    id_map: dict[str, str] | None = None,
) -> dict[str, object]:
    """Convert a raw tool dict to structured JSON-friendly data."""
    tool_type = tool.get("type", "")
    input_tag = ContentBlockType.TOOL_INPUT.value.xml_tag
    output_tag = ContentBlockType.TOOL_OUTPUT.value.xml_tag

    if tool_type == "tool_use":
        return _tool_use_to_json(tool, input_tag)

    if tool_type == "tool_result":
        return _tool_result_to_json(tool, output_tag, id_map)

    return {
        "type": input_tag,
        "name": "Unknown",
        "content": tool,
    }


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

    return ToolParts(
        tag=tag,
        attrs=attrs,
        content=content,
        is_empty=not content,
        name=name,
        input_data=input_data if isinstance(input_data, dict) else None,
        tool_use_id=tool.get("id"),
    )


def _tool_use_to_json(tool: dict, tag: str) -> dict[str, object]:
    """Convert tool_use to structured JSON data."""
    name = tool.get("name", "Unknown")
    payload: dict[str, object] = {
        "type": tag,
        "name": name,
    }
    if short_tool_id := shorten_tool_use_id(tool.get("id")):
        payload["id"] = short_tool_id
    if native_tool_call_id := tool.get("native_tool_call_id"):
        payload["native_tool_call_id"] = native_tool_call_id
    if "native_content_index" in tool:
        payload["native_content_index"] = tool["native_content_index"]

    input_data = tool.get("input", {})
    if not input_data:
        return payload
    if not isinstance(input_data, dict):
        payload["content"] = input_data
        return payload

    if tool_input_needs_wrapper(name, input_data):
        payload["input"] = input_data
        return payload

    payload.update(input_data)
    return payload


def _tool_result_to_parts(
    tool: dict, tag: str, id_map: dict[str, str] | None = None
) -> ToolParts:
    """Convert tool_result to ToolParts."""
    content_text = "\n".join(extract_text_from_content(tool.get("content", "")))
    is_error = tool.get("is_error", False)
    tool_use_id = tool.get("tool_use_id")

    if "name" in tool:
        name = tool["name"] or ""
    else:
        name = id_map.get(tool_use_id, "") if id_map and tool_use_id else ""
    attrs: list[tuple[str, str]] = []
    if name:
        attrs.append(("name", name))
    if short_tool_id := shorten_tool_use_id(tool_use_id):
        attrs.append(("id", short_tool_id))
    if is_error:
        attrs.append(("is_error", "true"))

    content = f"```\n{content_text}\n```" if content_text else None

    return ToolParts(
        tag=tag,
        attrs=attrs,
        content=content,
        is_empty=not content,
        name=name,
        output_text=content_text or None,
        tool_use_id=tool_use_id,
    )


def _tool_result_to_json(
    tool: dict,
    tag: str,
    id_map: dict[str, str] | None = None,
) -> dict[str, object]:
    """Convert tool_result to structured JSON data."""
    payload: dict[str, object] = {"type": tag}
    tool_use_id = tool.get("tool_use_id")
    if "name" in tool:
        name = tool["name"]
    else:
        name = id_map.get(tool_use_id) if id_map and tool_use_id else None
    if name:
        payload["name"] = name
    if short_tool_id := shorten_tool_use_id(tool_use_id):
        payload["id"] = short_tool_id
    if native_tool_call_id := tool.get("native_tool_call_id"):
        payload["native_tool_call_id"] = native_tool_call_id
    if tool.get("is_error", False):
        payload["is_error"] = True
    if "content" in tool:
        payload["content"] = tool.get("content")
    return payload


def render_tool_xml(parts: ToolParts, *, encode_transport: bool) -> str:
    """Render ToolParts to an XML string."""
    attribute_text = " ".join(f'{name}="{value}"' for name, value in parts.attrs)
    opening_tag = (
        f"<{parts.tag} {attribute_text}>" if attribute_text else f"<{parts.tag}>"
    )

    if parts.is_empty:
        return f"{opening_tag}</{parts.tag}>"
    return render_inner_xml_block(
        parts.tag,
        parts.content,
        parts.attrs,
        encode_transport=encode_transport,
    )
