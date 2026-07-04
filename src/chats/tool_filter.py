from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SHORT_MAX_CHARS = 500

# Maps short/long modifier keywords to (field_name, value) pairs.
# Adding a new modifier = adding entries here.
MODIFIERS: dict[str, tuple[str, str | bool]] = {
    "i": ("direction", "input"),
    "input": ("direction", "input"),
    "o": ("direction", "output"),
    "output": ("direction", "output"),
    "e": ("error_only", True),
    "error": ("error_only", True),
}
SHORT_MODIFIERS = {"s", "short"}


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
    short_max_chars: int | None = None

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
    Modifiers: i/input, o/output, e/error, s/short, s=NUMBER/short=NUMBER
    Order of tokens doesn't matter. Leading colon is optional.
    """
    negate = spec.startswith("!")
    body = spec[1:] if negate else spec

    tf = ToolFilter(negate=negate)
    for token in body.split(":"):
        if not token:
            continue
        token_keyword, separator, token_value = token.partition("=")
        token_keyword = token_keyword.lower()
        if token_keyword in SHORT_MODIFIERS:
            tf.short = True
            tf.short_max_chars = (
                _parse_short_max_chars(token_value) if separator else None
            )
            continue
        action = MODIFIERS.get(token.lower())
        if action:
            setattr(tf, *action)
        else:
            tf.name = token
    return tf


def _parse_short_max_chars(candidate: str) -> int:
    if candidate.isdigit() and int(candidate) > 7:
        return int(candidate)
    raise ValueError(f"Invalid tool short value: {candidate!r}. Expected digits > 7.")


def _resolve_tool_name(tool: dict, id_map: dict[str, str]) -> str | None:
    """Extract the tool name from a tool dict, resolving tool_result via id_map."""
    tool_type = tool.get("type")
    if tool_type == "tool_use":
        return tool.get("name")
    if tool_type == "tool_result":
        return id_map.get(tool.get("tool_use_id"))
    return None


def resolve_tool_visibility(
    tool: dict,
    filter_value: bool | list[ToolFilter],
    id_map: dict[str, str],
    *,
    default_short_max_chars: int = DEFAULT_SHORT_MAX_CHARS,
) -> tuple[bool, int | None]:
    """Determine whether a tool is visible and its local short limit, if any.

    Returns `(show, local_short_max_chars)`. Negative filters are AND'd as a
    blocklist: if any negative filter's criteria match, the tool is excluded.
    Positive filters are OR'd as an allowlist. Among matching positive filters,
    the most specific filter that declares a short limit controls that limit.
    """
    if isinstance(filter_value, bool):
        return filter_value, None

    for tool_filter in filter_value:
        if tool_filter.negate and tool_filter._matches_criteria(tool, id_map):
            return False, None

    positive_filters = [
        tool_filter for tool_filter in filter_value if not tool_filter.negate
    ]
    if not positive_filters:
        return True, None

    matching_filters = [
        tool_filter
        for tool_filter in positive_filters
        if tool_filter._matches_criteria(tool, id_map)
    ]
    if not matching_filters:
        return False, None

    matching_short_filters = [
        tool_filter for tool_filter in matching_filters if tool_filter.short
    ]
    if not matching_short_filters:
        return True, None

    selected_filter = max(
        enumerate(matching_short_filters),
        key=lambda item: (_tool_filter_specificity(item[1]), item[0]),
    )[1]
    return True, _local_short_max_chars(selected_filter, default_short_max_chars)


def _tool_filter_specificity(tool_filter: ToolFilter) -> int:
    return sum([
        tool_filter.name is not None,
        tool_filter.direction is not None,
        tool_filter.error_only,
    ])


def _local_short_max_chars(
    tool_filter: ToolFilter,
    default_short_max_chars: int,
) -> int | None:
    if not tool_filter.short:
        return None
    return tool_filter.short_max_chars or default_short_max_chars
