from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .parts import MessagePart, MessagePartKind, ToolParts
from .registry import ContentBlockType
from .tool_filter import ToolFilter
from .tools import tool_to_parts
from .utils import shorten_data


@dataclass
class ConversationMetadata:
    """Metadata for a conversation file to avoid repeated I/O."""

    path: Path
    ctime: datetime | None
    mtime: datetime | None


class ConversationFlags:
    """Flags controlling what content to include."""

    show_thinking: bool
    show_tools: bool | list[ToolFilter]
    show_agents: bool
    show_plans: bool
    shorten: bool
    color: bool
    paging: bool

    def __init__(
        self,
        *,
        show_thinking: bool = False,
        show_tools: bool | list[ToolFilter] = False,
        show_agents: bool = False,
        show_plans: bool = True,
        shorten: bool = False,
        color: bool = False,
        paging: bool | None = None,
    ):
        self.show_thinking = show_thinking
        self.show_tools = show_tools
        self.show_agents = show_agents
        self.show_plans = show_plans
        self.shorten = shorten
        self.color = (color == "always") or (color == "auto" and sys.stdout.isatty())
        # Paging defaults to color value unless explicitly set
        self.paging = paging if paging is not None else self.color

    @property
    def show_all(self) -> bool:
        return self.show_thinking and self.show_tools and self.show_agents

    def __repr__(self) -> str:
        return (
            f"ConversationFlags(show_thinking={self.show_thinking}, "
            f"show_tools={self.show_tools}, show_agents={self.show_agents}, "
            f"show_plans={self.show_plans}, shorten={self.shorten}, "
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

    def iter_visible_parts(
        self, flags: "ConversationFlags", tool_id_map: dict[str, str] | None = None
    ) -> list[MessagePart]:
        """Yield all visible content parts based on flags.

        This is the single source of truth for:
        - What content is visible (flag-based filtering)
        - Content ordering (text, thinking, tools, plan)
        - Shortening (applies shorten_data if flags.shorten)

        Plans are represented as TOOL parts with name="ExitPlanMode".
        """
        parts: list[MessagePart] = []

        # Text content
        if self.text:
            text = shorten_data(self.text) if flags.shorten else self.text
            parts.append(MessagePart(MessagePartKind.TEXT, text))

        # Thinking block
        if flags.show_thinking and self.thinking:
            thinking = shorten_data(self.thinking) if flags.shorten else self.thinking
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
            should_shorten = flags.shorten or filter_short
            tool_data = shorten_data(tool) if should_shorten else tool
            parts.append(MessagePart(MessagePartKind.TOOL, tool_to_parts(tool_data)))

    def _should_show_tool(
        self,
        tool: dict,
        filter_value: bool | list[ToolFilter],
        id_map: dict[str, str],
    ) -> tuple[bool, bool]:
        """Determine if a tool should be shown and whether to shorten it.

        Returns (show, filter_short).

        Negative filters are AND'd as a blocklist: if ANY negative filter's
        criteria match, the tool is excluded.
        Positive filters are OR'd as an allowlist: at least one must match.
        If only negative filters exist, the tool is shown (unless blocked).
        """
        if isinstance(filter_value, bool):
            return filter_value, False

        # Blocklist: any negative filter whose criteria match → exclude
        for f in filter_value:
            if f.negate and f._matches_criteria(tool, id_map):
                return False, False

        # Allowlist: positive filters OR'd
        positive = [f for f in filter_value if not f.negate]
        if not positive:
            return True, False

        for f in positive:
            if f._matches_criteria(tool, id_map):
                return True, f.short
        return False, False

    def has_content(self) -> bool:
        """Check if message has any displayable content."""
        return bool(self.text or self.thinking or self.tools or self.plan)

    def get_wrapper_type(self) -> ContentBlockType:
        """Return the XML wrapper type for this message."""
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
                attrs.append(f'model="{self.model}"')
        return " ".join(attrs)
