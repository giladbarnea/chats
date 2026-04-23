from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import StrEnum
from typing import Literal

from .parts import MessagePart, MessagePartKind, ToolParts
from .registry import ContentBlockType
from .tool_filter import ToolFilter, resolve_tool_visibility
from .tools import tool_to_parts
from .utils import shorten_data, truncate_middle


Provider = Literal["claude", "pi", "codex"]


class ParseOutputMode(StrEnum):
    """Special parse output modes."""

    FULL = "full"
    ONLY_METADATA = "only-metadata"
    ONLY_ID = "only-id"


@dataclass
class ConversationMetadata:
    """Metadata for a conversation file to avoid repeated I/O."""

    path: Path
    ctime: datetime | None
    mtime: datetime | None
    provider: Provider
    forked_from: str | None = None


class ConversationFlags:
    """Flags controlling what content to include."""

    show_user_messages: bool
    show_assistant_messages: bool
    show_thinking: bool
    show_tools: bool | list[ToolFilter]
    show_agents: bool
    show_plans: bool
    allow_empty_output: bool
    shorten: bool
    shorten_thinking: bool
    color: bool
    paging: bool

    def __init__(
        self,
        *,
        show_user_messages: bool = True,
        show_assistant_messages: bool = True,
        show_thinking: bool = False,
        show_tools: bool | list[ToolFilter] = False,
        show_agents: bool = False,
        show_plans: bool = True,
        allow_empty_output: bool = False,
        shorten: bool = False,
        shorten_thinking: bool = False,
        color: bool = False,
        paging: bool | None = None,
    ):
        self.show_user_messages = show_user_messages
        self.show_assistant_messages = show_assistant_messages
        self.show_thinking = show_thinking
        self.show_tools = show_tools
        self.show_agents = show_agents
        self.show_plans = show_plans
        self.allow_empty_output = allow_empty_output
        self.shorten = shorten
        self.shorten_thinking = shorten_thinking
        self.color = (color == "always") or (color == "auto" and sys.stdout.isatty())
        # Paging defaults to color value unless explicitly set
        self.paging = paging if paging is not None else self.color

    @property
    def show_all(self) -> bool:
        return self.show_thinking and self.show_tools and self.show_agents

    def __repr__(self) -> str:
        return (
            f"ConversationFlags(show_user_messages={self.show_user_messages}, "
            f"show_assistant_messages={self.show_assistant_messages}, "
            f"show_thinking={self.show_thinking}, "
            f"show_tools={self.show_tools}, show_agents={self.show_agents}, "
            f"show_plans={self.show_plans}, allow_empty_output={self.allow_empty_output}, "
            f"shorten={self.shorten}, "
            f"shorten_thinking={self.shorten_thinking}, "
            f"color={self.color}, paging={self.paging})"
        )


@dataclass
class Message:
    """Represents a single message in a conversation."""

    role: str  # 'user' or 'assistant'
    index: int = 0  # Message number in conversation
    text: str = ""  # Main visible text content
    thinking: str | None = None
    tools: list[dict] = field(default_factory=list)  # tool_use and tool_result items
    plan: str | None = None  # ExitPlanMode plan content
    agent_id: str | None = None
    timestamp: str | None = None  # ISO timestamp for chronological sorting
    subagent_type: str | None = None  # e.g., "codebase-analyzer:multiple-subsystems"
    model: str | None = None  # e.g., "claude-sonnet-4-5-20250929"
    is_meta: bool = False
    source_tool_user_id: str | None = None
    wrapper_type: ContentBlockType | None = None

    def iter_visible_parts(
        self, flags: "ConversationFlags", tool_id_map: dict[str, str] | None = None
    ) -> list[MessagePart]:
        """Yield all visible content parts based on flags.

        This is the single source of truth for:
        - What content is visible (flag-based filtering)
        - Content ordering (text, thinking, tools, plan)
        - Shortening (text/thinking/plan via shorten_data; tool bodies via truncate_middle)

        Plans are represented as TOOL parts with name="ExitPlanMode".
        """
        parts: list[MessagePart] = []

        # Text content
        if self.text:
            text = shorten_data(self.text) if flags.shorten else self.text
            parts.append(MessagePart(MessagePartKind.TEXT, text))

        # Thinking block
        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(self.thinking) if should_shorten_thinking else self.thinking
            )
            parts.append(MessagePart(MessagePartKind.THINKING, thinking))

        # Tools
        if flags.show_tools and self.tools:
            self._append_tool_parts(parts, flags, tool_id_map)

        # Plan (as tool-like part with name="ExitPlanMode")
        if flags.show_plans and self.plan:
            plan_content = shorten_data(self.plan) if flags.shorten else self.plan
            plan_parts = ToolParts(
                tag=ContentBlockType.TOOL_INPUT.value.xml_tag,
                attrs=[("name", "ExitPlanMode")],
                content=plan_content,
                is_empty=False,
            )
            parts.append(MessagePart(MessagePartKind.TOOL, plan_parts))

        return parts

    def _append_tool_parts(
        self,
        parts: list[MessagePart],
        flags: "ConversationFlags",
        tool_id_map: dict[str, str] | None,
    ) -> None:
        """Append visible tool parts based on filters."""
        id_map = tool_id_map or {}
        filters = flags.show_tools

        # Build local id_map when filters need name resolution and no global map provided
        if isinstance(filters, list) and not tool_id_map:
            if any(f.name is not None for f in filters):
                for tool in self.tools:
                    if tool.get("type") == "tool_use" and "id" in tool:
                        id_map[tool["id"]] = tool.get("name", "Unknown")

        for tool in self.tools:
            show, filter_short = self._should_show_tool(tool, filters, id_map)
            if not show:
                continue

            tool_parts = tool_to_parts(tool, id_map)
            should_shorten = flags.shorten or filter_short
            if should_shorten and tool_parts.content:
                tool_parts = tool_parts._replace(content=truncate_middle(tool_parts.content))

            parts.append(MessagePart(MessagePartKind.TOOL, tool_parts))

    def _should_show_tool(
        self,
        tool: dict,
        filter_value: bool | list[ToolFilter],
        id_map: dict[str, str],
    ) -> tuple[bool, bool]:
        """Determine if a tool should be shown and whether to shorten it."""
        return resolve_tool_visibility(tool, filter_value, id_map)

    def has_content(self) -> bool:
        """Check if message has any displayable content."""
        return bool(self.text or self.thinking or self.tools or self.plan)

    def get_wrapper_type(self) -> ContentBlockType:
        """Return the XML wrapper type for this message."""
        if self.wrapper_type is not None:
            return self.wrapper_type
        if self.role == "user":
            return ContentBlockType.USER_MESSAGE
        elif self.role == "session-rename":
            return ContentBlockType.SESSION_RENAME
        elif self.agent_id:
            return ContentBlockType.AGENT
        return ContentBlockType.ASSISTANT_RESPONSE

    def get_wrapper_attrs(self) -> str:
        """Build XML attributes string for this message's wrapper tag."""
        attrs = [f'i="{self.index}"']
        if self.role == "user":
            if self.is_meta:
                attrs.append('isMeta="true"')
            if self.source_tool_user_id:
                attrs.append(f'sourceToolUserId="{self.source_tool_user_id}"')
        if self.agent_id:
            attrs.append(f'agent_id="{self.agent_id}"')
            if self.subagent_type:
                attrs.append(f'subagent_type="{self.subagent_type}"')
        if self.model:
            attrs.append(f'model="{self.model.removeprefix("claude-")}"')
        return " ".join(attrs)
