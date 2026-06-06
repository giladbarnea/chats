from __future__ import annotations

from ..model import Message


def _build_tool_id_map(messages: list[Message]) -> dict[str, str]:
    """Build a map of tool id to tool name from all messages."""
    tool_id_map: dict[str, str] = {}
    for message in messages:
        for tool in message.tools:
            if tool.get("type") == "tool_use" and "id" in tool:
                tool_id_map[tool["id"]] = tool.get("name", "Unknown")
    return tool_id_map
