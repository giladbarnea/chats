from __future__ import annotations

from dataclasses import dataclass

from .shortening import (
    DEFAULT_SHORT_MAX_CHARS,
    PROGRESSIVE_SHORT_COMPONENTS,
    ShortPolicy,
    parse_short_spec,
)

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
    short_progressive: bool | None = None

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
    tokens = body.split(":")
    position = 0
    parsed_short_value: str | None = None
    while position < len(tokens):
        token = tokens[position]
        if not token:
            position += 1
            continue
        token_keyword, separator, token_value = token.partition("=")
        token_keyword = token_keyword.lower()
        if token_keyword in SHORT_MODIFIERS:
            consumed, parsed_short_value = _apply_short_modifier(
                tf,
                tokens,
                position,
                separator,
                token_value,
            )
            position += consumed
            continue
        action = MODIFIERS.get(token.lower())
        if action:
            setattr(tf, *action)
        elif tf.name is None or not tf.short:
            tf.name = token
        else:
            value = (
                f"{parsed_short_value}:{token}"
                if parsed_short_value is not None
                else token
            )
            raise ValueError(f"Invalid tool short value: {value!r}.")
        position += 1
    return tf


def _apply_short_modifier(
    tool_filter: ToolFilter,
    tokens: list[str],
    position: int,
    separator: str,
    token_value: str,
) -> tuple[int, str | None]:
    if tool_filter.short:
        raise ValueError("Invalid tool short value: repeated short modifier.")
    tool_filter.short = True
    if not separator:
        return 1, None

    candidate, additional_components = _tool_short_value(
        tokens,
        position,
        token_value,
    )
    short_spec = parse_short_spec(candidate)
    tool_filter.short_max_chars = short_spec.max_chars
    tool_filter.short_progressive = short_spec.progressive
    return additional_components + 1, candidate


def _tool_short_value(
    tokens: list[str],
    position: int,
    first_component: str,
) -> tuple[str, int]:
    """Collect the short-spec components without consuming tool modifiers."""
    next_position = position + 1
    if next_position >= len(tokens):
        return first_component, 0

    next_component = tokens[next_position]
    continues_short_spec = _is_short_component(first_component) and (
        not next_component or _is_short_component(next_component)
    )
    if not continues_short_spec:
        return first_component, 0

    candidate = f"{first_component}:{next_component}"
    following_position = next_position + 1
    if following_position < len(tokens) and not tokens[following_position]:
        candidate += ":"
    return candidate, 1


def _is_short_component(candidate: str) -> bool:
    return candidate.isdigit() or candidate.lower() in PROGRESSIVE_SHORT_COMPONENTS


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
    default_short_progressive: bool = False,
) -> tuple[bool, ShortPolicy | None]:
    """Determine whether a tool is visible and its local short policy, if any.

    Returns `(show, local_short_policy)`. Negative filters are AND'd as a
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
    return True, _local_short_policy(
        selected_filter,
        ShortPolicy(default_short_max_chars, default_short_progressive),
    )


def _tool_filter_specificity(tool_filter: ToolFilter) -> int:
    return sum([
        tool_filter.name is not None,
        tool_filter.direction is not None,
        tool_filter.error_only,
    ])


def _local_short_policy(
    tool_filter: ToolFilter,
    default: ShortPolicy,
) -> ShortPolicy | None:
    if not tool_filter.short:
        return None
    return ShortPolicy(
        max_chars=tool_filter.short_max_chars or default.max_chars,
        progressive=(
            default.progressive
            if tool_filter.short_progressive is None
            else tool_filter.short_progressive
        ),
    )
