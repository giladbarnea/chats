from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class MessagePartKind(Enum):
    """The kind of content part within a message."""

    TEXT = "text"
    THINKING = "thinking"
    TOOL = "tool"


class ToolParts(NamedTuple):
    """Normalized representation of a tool call (input, output, or plan-as-tool).

    Both XML and Rich renderers consume this.
    """

    tag: str  # "tool-input" or "tool-output"
    attrs: list[tuple[str, str]]  # Ordered key-value pairs for XML attributes
    content: str | None  # Body content (may include fenced code blocks)
    is_empty: bool  # True -> render as <tag ...></tag> (inline)


class MessagePart(NamedTuple):
    """A single content block within a message.

    Yielded by Message.iter_visible_parts().
    Consumed by renderers without further transformation.
    """

    kind: MessagePartKind
    data: str | ToolParts  # str for TEXT/THINKING, ToolParts for TOOL
