from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class MessagePartKind(Enum):
    """The kind of content part within a message."""

    TEXT = "text"
    THINKING = "thinking"
    TOOL = "tool"
    SUBAGENT_TASK = "subagent-task"


class ToolParts(NamedTuple):
    """Normalized representation of a tool call (input, output, or plan-as-tool).

    XML/raw consume tag/attrs/content; the colored renderer additionally uses the
    structured fields below to render natively (Edit as a diff, Read output
    highlighted by file extension) — they are ignored by the XML/raw path.
    """

    tag: str  # "tool-input" or "tool-output"
    attrs: list[tuple[str, str]]  # Ordered key-value pairs for XML attributes
    content: str | None  # Body content (may include fenced code blocks)
    is_empty: bool  # True -> render as <tag ...></tag> (inline)
    name: str = ""  # Canonical tool name (e.g. "Bash", "Read", "Edit")
    input_data: dict | None = None  # Raw tool_use input (for native Edit/diff)
    output_text: str | None = None  # Raw tool_result text (for native highlight)
    tool_use_id: str | None = None  # Full id, pairing an output back to its input


class MessagePart(NamedTuple):
    """A single content block within a message.

    Yielded by Message.iter_visible_parts().
    Consumed by renderers without further transformation.
    """

    kind: MessagePartKind
    data: str | ToolParts  # str for TEXT/THINKING, ToolParts for TOOL
