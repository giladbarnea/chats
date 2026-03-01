from __future__ import annotations

from dataclasses import dataclass


# Maps short/long modifier keywords to (field_name, value) pairs.
# Adding a new modifier = adding entries here.
MODIFIERS: dict[str, tuple[str, str | bool]] = {
    "i": ("direction", "input"),
    "input": ("direction", "input"),
    "o": ("direction", "output"),
    "output": ("direction", "output"),
    "e": ("error_only", True),
    "error": ("error_only", True),
    "s": ("short", True),
    "short": ("short", True),
}


@dataclass
class ToolFilter:
    """A single tool filter spec parsed from --tools arguments.

    Fields are all criteria (AND'd when matching). `negate` inverts the result.
    `short` is a display modifier, not a matching criterion.
    """

    name: str | None = None
    negate: bool = False
    direction: str | None = None  # "input" | "output"
    error_only: bool = False
    short: bool = False

    def matches(self, tool: dict, id_map: dict[str, str]) -> bool:
        hit = self._matches_criteria(tool, id_map)
        return not hit if self.negate else hit

    def _matches_criteria(self, tool: dict, id_map: dict[str, str]) -> bool:
        tool_type = tool.get("type")

        if self.direction == "input" and tool_type != "tool_use":
            return False
        if self.direction == "output" and tool_type != "tool_result":
            return False
        if self.error_only and not tool.get("is_error", False):
            return False
        if self.name is None:
            return True

        current_name = _resolve_tool_name(tool, id_map)
        return current_name == self.name


def parse_tool_spec(spec: str) -> ToolFilter:
    """Parse a single tool filter spec string into a ToolFilter.

    Syntax: [!][Name][:modifier[:modifier...]]
    Modifiers: i/input, o/output, e/error, s/short
    Order of tokens doesn't matter. Leading colon is optional.
    """
    negate = spec.startswith("!")
    body = spec[1:] if negate else spec

    tf = ToolFilter(negate=negate)
    for token in body.split(":"):
        if not token:
            continue
        action = MODIFIERS.get(token.lower())
        if action:
            setattr(tf, *action)
        else:
            tf.name = token
    return tf


def _resolve_tool_name(tool: dict, id_map: dict[str, str]) -> str | None:
    """Extract the tool name from a tool dict, resolving tool_result via id_map."""
    tool_type = tool.get("type")
    if tool_type == "tool_use":
        return tool.get("name")
    if tool_type == "tool_result":
        return id_map.get(tool.get("tool_use_id"))
    return None
