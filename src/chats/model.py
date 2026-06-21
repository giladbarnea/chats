from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from .parts import MessagePart, MessagePartKind, ToolParts
from .registry import ContentBlockType
from .tool_filter import ToolFilter, resolve_tool_visibility
from .tools import tool_to_json, tool_to_parts
from .utils import shorten_data, truncate_middle

Provider = Literal["claude", "pi", "codex", "antigravitycli"]
PROVIDERS: tuple[Provider, ...] = ("claude", "pi", "codex", "antigravitycli")


def _message_timestamp_datetime(timestamp: str | None) -> datetime | None:
    """
    Parse a message timestamp into local time.

    >>> _message_timestamp_datetime("2026-06-21T09:30:00").date().isoformat()
    '2026-06-21'
    >>> _message_timestamp_datetime(None) is None
    True
    """
    if timestamp is None:
        return None
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone().replace(tzinfo=None)


def _ordinal_day(day: int) -> str:
    """
    Render a calendar day with an English ordinal suffix.

    >>> [_ordinal_day(day) for day in (1, 2, 3, 4, 11, 12, 13, 21)]
    ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st']
    """
    if 10 <= day % 100 <= 20:
        return f"{day}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


class ParseOutputMode(StrEnum):
    """Special parse output modes."""

    FULL = "full"
    ONLY_METADATA = "only-metadata"
    ONLY_ID = "only-id"


class SearchOutputMode(StrEnum):
    """Search result output modes."""

    MATCHES = "matches"
    FULL = "full"
    LIST = "list"
    ONLY_ID = "only-id"


class MessageSelection(StrEnum):
    """Visible regular-message role selection."""

    ALL = "all"
    ONLY_USER = "only-user"
    ONLY_ASSISTANT = "only-assistant"
    NO_USER = "no-user"
    NO_ASSISTANT = "no-assistant"
    NONE = "none"


@dataclass
class ConversationMetadata:
    """Metadata for a conversation file to avoid repeated I/O."""

    path: Path
    ctime: datetime | None
    mtime: datetime | None
    provider: Provider
    forked_from: str | None = None


@dataclass(frozen=True)
class SubagentMetadata:
    """Identity of a spawned subagent, read from its transcript.

    `name` is the subagent's nickname (Codex assigns these, e.g. "Leibniz";
    Claude does not, so it stays None).
    """

    agent_id: str | None = None
    name: str | None = None
    subagent_type: str | None = None
    model: str | None = None


class ConversationFlags:
    """Flags controlling what content to include."""

    message_selection: MessageSelection
    show_thinking: bool
    show_tools: bool | list[ToolFilter]
    show_agents: bool
    show_branches: bool
    show_plans: bool
    allow_empty_output: bool
    shorten: bool
    shorten_width: int
    shorten_thinking: bool
    color: bool
    paging: bool

    def __init__(
        self,
        *,
        message_selection: MessageSelection = MessageSelection.ALL,
        show_thinking: bool = False,
        show_tools: bool | list[ToolFilter] = False,
        show_agents: bool = False,
        show_branches: bool = False,
        show_plans: bool = False,
        allow_empty_output: bool = False,
        shorten: bool = False,
        shorten_width: int = 500,
        shorten_thinking: bool = False,
        color: bool = False,
        paging: bool | None = None,
    ):
        self.message_selection = message_selection
        self.show_thinking = show_thinking
        self.show_tools = show_tools
        self.show_agents = show_agents
        self.show_branches = show_branches
        self.show_plans = show_plans
        self.allow_empty_output = allow_empty_output
        self.shorten = shorten
        self.shorten_width = shorten_width
        self.shorten_thinking = shorten_thinking
        self.color = (color == "always") or (color == "auto" and sys.stdout.isatty())
        # Paging defaults to color value unless explicitly set
        self.paging = paging if paging is not None else self.color

    @property
    def show_user_messages(self) -> bool:
        return self.message_selection in {
            MessageSelection.ALL,
            MessageSelection.ONLY_USER,
            MessageSelection.NO_ASSISTANT,
        }

    @property
    def show_assistant_messages(self) -> bool:
        return self.message_selection in {
            MessageSelection.ALL,
            MessageSelection.ONLY_ASSISTANT,
            MessageSelection.NO_USER,
        }

    @property
    def show_all(self) -> bool:
        return (
            self.show_thinking
            and self.show_tools
            and self.show_agents
            and self.show_branches
            and self.show_plans
        )

    def __repr__(self) -> str:
        return (
            f"ConversationFlags(message_selection={self.message_selection!r}, "
            f"show_user_messages={self.show_user_messages}, "
            f"show_assistant_messages={self.show_assistant_messages}, "
            f"show_thinking={self.show_thinking}, "
            f"show_tools={self.show_tools}, show_agents={self.show_agents}, "
            f"show_branches={self.show_branches}, "
            f"show_plans={self.show_plans}, allow_empty_output={self.allow_empty_output}, "
            f"shorten={self.shorten}, shorten_width={self.shorten_width}, "
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
    name: str | None = None  # subagent nickname (Codex assigns these; Claude does not)
    subagent_task: str | None = None  # the prompt given to a subagent, shown as a block
    model: str | None = None  # e.g., "claude-sonnet-4-5-20250929"
    is_meta: bool = False
    source_tool_user_id: str | None = None
    wrapper_type: ContentBlockType | None = None
    branch_id: str | None = None  # abandoned rewind-branch id; None on the main thread

    @property
    def off_main_branch(self) -> bool:
        """True when this message sits on an abandoned rewind branch."""
        return self.branch_id is not None

    def iter_visible_parts(
        self, flags: ConversationFlags, tool_id_map: dict[str, str] | None = None
    ) -> list[MessagePart]:
        """Yield all visible content parts based on flags.

        This is the single source of truth for:
        - What content is visible (flag-based filtering)
        - Content ordering (text, thinking, tools, plan)
        - Shortening (text/thinking/plan via shorten_data; tool bodies via truncate_middle)

        Plans are represented as TOOL parts with name="ExitPlanMode".
        """
        parts: list[MessagePart] = []

        # Subagent task prompt — always shown (it is what was handed to the agent).
        if self.subagent_task:
            parts.append(MessagePart(MessagePartKind.SUBAGENT_TASK, self.subagent_task))

        # Text content
        if self.text:
            text = (
                shorten_data(self.text, width=flags.shorten_width)
                if flags.shorten
                else self.text
            )
            parts.append(MessagePart(MessagePartKind.TEXT, text))

        # Thinking block
        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(self.thinking, max_len=flags.shorten_width)
                if should_shorten_thinking
                else self.thinking
            )
            parts.append(MessagePart(MessagePartKind.THINKING, thinking))

        # Tools
        if flags.show_tools and self.tools:
            self._append_tool_parts(parts, flags, tool_id_map)

        # Plan (as tool-like part with name="ExitPlanMode")
        if flags.show_plans and self.plan:
            plan_content = (
                shorten_data(self.plan, width=flags.shorten_width)
                if flags.shorten
                else self.plan
            )
            plan_parts = ToolParts(
                tag=ContentBlockType.TOOL_INPUT.value.xml_tag,
                attrs=[("name", "ExitPlanMode")],
                content=plan_content,
                is_empty=False,
            )
            parts.append(MessagePart(MessagePartKind.TOOL, plan_parts))

        return parts

    def iter_visible_json_content(
        self,
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None = None,
    ) -> list[str | dict[str, object]]:
        """Yield visible content in a JSON-friendly structured form."""
        content: list[str | dict[str, object]] = []

        if self.subagent_task:
            content.append({"type": "subagent-task", "content": self.subagent_task})

        if self.text:
            text = (
                shorten_data(self.text, width=flags.shorten_width)
                if flags.shorten
                else self.text
            )
            content.append(text)

        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(self.thinking, max_len=flags.shorten_width)
                if should_shorten_thinking
                else self.thinking
            )
            content.append({
                "type": ContentBlockType.THINKING.value.xml_tag,
                "content": thinking,
            })

        if flags.show_tools and self.tools:
            content.extend(self._visible_tool_json_content(flags, tool_id_map))

        if flags.show_plans and self.plan:
            plan_content = (
                shorten_data(self.plan, width=flags.shorten_width)
                if flags.shorten
                else self.plan
            )
            content.append({
                "type": ContentBlockType.TOOL_INPUT.value.xml_tag,
                "name": "ExitPlanMode",
                "plan": plan_content,
            })

        return content

    def to_json_dict(
        self,
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None = None,
    ) -> dict[str, object] | None:
        """Render one visible message to structured JSON data."""
        content = self.iter_visible_json_content(flags, tool_id_map)
        if not content:
            return None

        payload: dict[str, object] = {
            "type": self.get_wrapper_type().value.xml_tag,
            "role": self.role,
            "original_index": self.index,
            "content": content,
        }

        if self.branch_id:
            payload["branch"] = self.branch_id

        if self.role == "user":
            if self.is_meta:
                payload["isMeta"] = True
            if self.source_tool_user_id:
                payload["sourceToolUserId"] = self.source_tool_user_id

        if self.agent_id:
            payload["agent_id"] = self.agent_id
            if self.subagent_type:
                payload["subagent_type"] = self.subagent_type

        if self.model:
            payload["model"] = self.model.removeprefix("claude-")

        return payload

    def _append_tool_parts(
        self,
        parts: list[MessagePart],
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None,
    ) -> None:
        """Append visible tool parts based on filters."""
        id_map = self._tool_name_id_map(flags.show_tools, tool_id_map)

        for tool in self.tools:
            show, filter_short = self._should_show_tool(tool, flags.show_tools, id_map)
            if not show:
                continue

            tool_parts = tool_to_parts(tool, id_map)
            should_shorten = flags.shorten or filter_short
            if should_shorten and tool_parts.content:
                tool_parts = tool_parts._replace(
                    content=truncate_middle(
                        tool_parts.content,
                        max_len=flags.shorten_width,
                    )
                )

            parts.append(MessagePart(MessagePartKind.TOOL, tool_parts))

    def _visible_tool_json_content(
        self,
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None,
    ) -> list[dict[str, object]]:
        """Return visible tools in structured JSON form."""
        id_map = self._tool_name_id_map(flags.show_tools, tool_id_map)
        tools: list[dict[str, object]] = []

        for tool in self.tools:
            show, filter_short = self._should_show_tool(tool, flags.show_tools, id_map)
            if not show:
                continue

            tool_json = tool_to_json(tool, id_map)
            if flags.shorten or filter_short:
                tool_json = shorten_data(tool_json, width=flags.shorten_width)
            tools.append(tool_json)

        return tools

    def _tool_name_id_map(
        self,
        filter_value: bool | list[ToolFilter],
        tool_id_map: dict[str, str] | None,
    ) -> dict[str, str]:
        """Return a tool id map, building a local one only when needed."""
        id_map = tool_id_map or {}
        if not (
            isinstance(filter_value, list)
            and not tool_id_map
            and any(filter_item.name is not None for filter_item in filter_value)
        ):
            return id_map

        for tool in self.tools:
            if tool.get("type") == "tool_use" and "id" in tool:
                id_map[tool["id"]] = tool.get("name", "Unknown")
        return id_map

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
        return bool(
            self.text or self.thinking or self.tools or self.plan or self.subagent_task
        )

    def get_wrapper_type(self) -> ContentBlockType:
        """Return the XML wrapper type for this message.

        agent_id takes precedence over role so that every message belonging to a
        subagent (including its tool-result `user` entries) renders as one block.
        """
        if self.wrapper_type is not None:
            return self.wrapper_type
        if self.agent_id:
            return ContentBlockType.AGENT
        if self.role == "user":
            return ContentBlockType.USER_MESSAGE
        if self.role == "session-rename":
            return ContentBlockType.SESSION_RENAME
        return ContentBlockType.ASSISTANT_RESPONSE

    def get_header(self) -> str | None:
        """Return the wrapper header, enriched with the subagent nickname when present.

        A user-initiated `/fork` (subagent_type "fork") is labelled `Fork` to set it
        apart from agent-initiated `Task` subagents, which stay `Agent`.
        """
        wrapper = self.get_wrapper_type()
        header = wrapper.value.header
        if wrapper is not ContentBlockType.AGENT:
            return header
        if self.subagent_type == "fork":
            return "## Fork"
        if self.name:
            return f"{header} '{self.name}'"
        return header

    def get_date_attribute(self) -> str | None:
        """Return the message date for XML attributes."""
        if timestamp := _message_timestamp_datetime(self.timestamp):
            return timestamp.date().isoformat()
        return None

    def get_display_date(self) -> str | None:
        """Return the message date for Rich panel titles."""
        timestamp = _message_timestamp_datetime(self.timestamp)
        if timestamp is None:
            return None
        return f"{timestamp:%B} {_ordinal_day(timestamp.day)}"

    def get_wrapper_attrs(self) -> str:
        """Build XML attributes string for this message's wrapper tag."""
        attrs = [f'i="{self.index}"']
        if self.branch_id:
            attrs.append(f'branch="{self.branch_id}"')
        if self.role == "user":
            if self.is_meta:
                attrs.append('isMeta="true"')
            if self.source_tool_user_id:
                attrs.append(f'sourceToolUserId="{self.source_tool_user_id}"')
        if self.agent_id:
            attrs.append(f'agent_id="{self.agent_id}"')
            if self.subagent_type:
                attrs.append(f'subagent_type="{self.subagent_type}"')
            if self.name:
                attrs.append(f'name="{self.name}"')
        if self.model:
            attrs.append(f'model="{self.model.removeprefix("claude-")}"')
        if date := self.get_date_attribute():
            attrs.append(f'date="{date}"')
        return " ".join(attrs)
