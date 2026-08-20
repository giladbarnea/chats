from __future__ import annotations

import html
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from .parts import MessagePart, MessagePartKind, ToolParts
from .registry import TOOL_SCHEMAS, ContentBlockType
from .shortening import ShortPolicy
from .tool_filter import ToolFilter, resolve_tool_visibility
from .tools import tool_to_json, tool_to_parts
from .utils import shorten_data, truncate_middle

Provider = Literal["claude", "pi", "codex"]
PROVIDERS: tuple[Provider, ...] = ("claude", "pi", "codex")


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
    show_custom: bool
    show_branches: bool
    show_plans: bool
    allow_empty_output: bool
    shorten: bool
    shorten_max_chars: int
    shorten_progressive: bool
    shorten_thinking: bool
    color: bool
    metadata_color: bool
    paging: bool

    def __init__(
        self,
        *,
        message_selection: MessageSelection = MessageSelection.ALL,
        show_thinking: bool = False,
        show_tools: bool | list[ToolFilter] = False,
        show_agents: bool = False,
        show_custom: bool = False,
        show_branches: bool = False,
        show_plans: bool = False,
        allow_empty_output: bool = False,
        shorten: bool = False,
        shorten_max_chars: int = 500,
        shorten_progressive: bool = False,
        shorten_thinking: bool = False,
        color: bool | Literal["always", "never", "auto"] = False,
        paging: bool | None = None,
    ):
        self.message_selection = message_selection
        self.show_thinking = show_thinking
        self.show_tools = show_tools
        self.show_agents = show_agents
        self.show_custom = show_custom
        self.show_branches = show_branches
        self.show_plans = show_plans
        self.allow_empty_output = allow_empty_output
        self.shorten = shorten
        self.shorten_max_chars = shorten_max_chars
        self.shorten_progressive = shorten_progressive
        self.shorten_thinking = shorten_thinking
        self.color = (color == "always") or (color == "auto" and sys.stdout.isatty())
        self.metadata_color = color != "never" if isinstance(color, str) else color
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
            and self.show_custom
            and self.show_branches
            and self.show_plans
        )

    @property
    def global_short_policy(self) -> ShortPolicy | None:
        """Return the active global short policy, if shortening is enabled."""
        if not self.shorten:
            return None
        return ShortPolicy(self.shorten_max_chars, self.shorten_progressive)

    def __repr__(self) -> str:
        return (
            f"ConversationFlags(message_selection={self.message_selection!r}, "
            f"show_user_messages={self.show_user_messages}, "
            f"show_assistant_messages={self.show_assistant_messages}, "
            f"show_thinking={self.show_thinking}, "
            f"show_tools={self.show_tools}, show_agents={self.show_agents}, "
            f"show_custom={self.show_custom}, show_branches={self.show_branches}, "
            f"show_plans={self.show_plans}, allow_empty_output={self.allow_empty_output}, "
            f"shorten={self.shorten}, shorten_max_chars={self.shorten_max_chars}, "
            f"shorten_progressive={self.shorten_progressive}, "
            f"shorten_thinking={self.shorten_thinking}, "
            f"color={self.color}, metadata_color={self.metadata_color}, paging={self.paging})"
        )


def _shorten_tool_payload(tool: dict, max_chars: int) -> dict:
    """Shorten only user-authored tool payload fields, preserving tool metadata.

    >>> _shorten_tool_payload({"type": "tool_use", "name": "Bash", "input": {"command": "abcdefghi"}}, 8)["type"]
    'tool_use'
    """
    shortened_tool = dict(tool)
    if shortened_tool.get("type") == "tool_use" and "input" in shortened_tool:
        shortened_tool["input"] = shorten_data(shortened_tool.get("input"), max_chars)
    if shortened_tool.get("type") == "tool_result" and "content" in shortened_tool:
        shortened_tool["content"] = shorten_data(shortened_tool.get("content"), max_chars)
    return shortened_tool


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
    native_entry_id: str | None = None
    subagent_type: str | None = None  # e.g., "codebase-analyzer:multiple-subsystems"
    name: str | None = None  # subagent nickname (Codex assigns these; Claude does not)
    subagent_task: str | None = None  # the prompt given to a subagent, shown as a block
    model: str | None = None  # e.g., "claude-sonnet-4-5-20250929"
    is_meta: bool = False
    source_tool_user_id: str | None = None
    wrapper_type: ContentBlockType | None = None
    custom_type: str | None = None
    inherited_context: bool | None = None
    status: str | None = None
    tools_always_visible: bool = False
    branch_id: str | None = None  # abandoned rewind-branch id; None on the main thread
    progressive_position: int | None = field(default=None, repr=False)
    progressive_qualifying_count: int = field(default=0, repr=False)

    @property
    def off_main_branch(self) -> bool:
        """True when this message sits on an abandoned rewind branch."""
        return self.branch_id is not None

    def _effective_short_max_chars(self, policy: ShortPolicy) -> int:
        return policy.effective_max_chars(
            self.progressive_position,
            self.progressive_qualifying_count,
        )

    def _global_short_max_chars(self, flags: ConversationFlags) -> int:
        return self._effective_short_max_chars(
            ShortPolicy(flags.shorten_max_chars, flags.shorten_progressive)
        )

    def iter_visible_parts(
        self, flags: ConversationFlags, tool_id_map: dict[str, str] | None = None
    ) -> list[MessagePart]:
        """Yield all visible content parts based on flags.

        This is the single source of truth for:
        - What content is visible (flag-based filtering)
        - Content ordering (text, thinking, tools, plan)
        - Shortening: every payload (text, thinking, plan, tool input/output) is
          shortened at the source before rendering, so scaffolding stays out of the budget

        Plans are represented as TOOL parts with name="ExitPlanMode".
        """
        parts: list[MessagePart] = []

        # Subagent task prompt — always shown (it is what was handed to the agent).
        if self.subagent_task:
            parts.append(MessagePart(MessagePartKind.SUBAGENT_TASK, self.subagent_task))

        # Text content
        if self.text:
            text = (
                shorten_data(
                    self.text,
                    max_chars=self._global_short_max_chars(flags),
                )
                if flags.shorten
                else self.text
            )
            parts.append(MessagePart(MessagePartKind.TEXT, text))

        # Thinking block
        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(
                    self.thinking,
                    max_chars=(
                        self._global_short_max_chars(flags)
                        if flags.shorten
                        else flags.shorten_max_chars
                    ),
                )
                if should_shorten_thinking
                else self.thinking
            )
            parts.append(MessagePart(MessagePartKind.THINKING, thinking))

        # Tools
        if (flags.show_tools or self.tools_always_visible) and self.tools:
            self._append_tool_parts(parts, flags, tool_id_map)

        # Plan (as tool-like part with name="ExitPlanMode")
        if flags.show_plans and self.plan:
            plan_content = (
                shorten_data(
                    self.plan,
                    max_chars=self._global_short_max_chars(flags),
                )
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
                shorten_data(
                    self.text,
                    max_chars=self._global_short_max_chars(flags),
                )
                if flags.shorten
                else self.text
            )
            content.append(text)

        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(
                    self.thinking,
                    max_chars=(
                        self._global_short_max_chars(flags)
                        if flags.shorten
                        else flags.shorten_max_chars
                    ),
                )
                if should_shorten_thinking
                else self.thinking
            )
            content.append({
                "type": ContentBlockType.THINKING.value.xml_tag,
                "content": thinking,
            })

        if (flags.show_tools or self.tools_always_visible) and self.tools:
            content.extend(self._visible_tool_json_content(flags, tool_id_map))

        if flags.show_plans and self.plan:
            plan_content = (
                shorten_data(
                    self.plan,
                    max_chars=self._global_short_max_chars(flags),
                )
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
            if self.name:
                payload["name"] = self.name

        if model := self.get_display_model():
            payload["model"] = model

        if self.custom_type:
            payload["custom_type"] = self.custom_type

        if self.inherited_context is not None:
            payload["inherited_context"] = self.inherited_context

        if self.status:
            payload["status"] = self.status

        if self.timestamp:
            payload["timestamp"] = self.timestamp

        if self.native_entry_id:
            payload["native_entry_id"] = self.native_entry_id

        return payload

    def _iter_visible_tools(
        self,
        flags: ConversationFlags,
        id_map: dict[str, str],
    ) -> Iterator[dict]:
        """Yield each visible tool dict, shortened at the source when asked.

        Shortening once here — on the raw tool payload — is the single shortening
        point for tools, mirroring how text, thinking and plans are shortened at
        the source. tool_to_parts/tool_to_json then build their views (XML content,
        the colored diff/highlight, JSON) from already-short data, so no
        representation can be left untruncated.
        """
        for tool, local_short_policy in self._iter_visible_tool_policies(
            flags,
            id_map,
        ):
            short_policy = local_short_policy or flags.global_short_policy
            if short_policy is not None:
                tool = _shorten_tool_payload(
                    tool,
                    max_chars=self._effective_short_max_chars(short_policy),
                )
            yield tool

    def _iter_visible_tool_policies(
        self,
        flags: ConversationFlags,
        id_map: dict[str, str],
    ) -> Iterator[tuple[dict, ShortPolicy | None]]:
        """Yield visible tools with their winning local short policy."""
        filter_value = True if self.tools_always_visible else flags.show_tools
        for tool in self.tools:
            show, local_short_policy = resolve_tool_visibility(
                tool,
                filter_value,
                id_map,
                default_short_max_chars=flags.shorten_max_chars,
                default_short_progressive=(
                    flags.shorten and flags.shorten_progressive
                ),
            )
            if show:
                yield tool, local_short_policy

    def has_progressive_payload(
        self,
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None = None,
    ) -> bool:
        """Return whether one visible payload uses a progressive short policy."""
        global_policy = flags.global_short_policy
        global_payload_visible = bool(
            self.text
            or flags.show_thinking and self.thinking
            or flags.show_plans and self.plan
        )
        if (
            global_policy is not None
            and global_policy.progressive
            and global_payload_visible
        ):
            return True

        if not ((flags.show_tools or self.tools_always_visible) and self.tools):
            return False
        filter_value = True if self.tools_always_visible else flags.show_tools
        id_map = self._tool_name_id_map(filter_value, tool_id_map)
        return any(
            (policy := local_policy or global_policy) is not None
            and policy.progressive
            for _, local_policy in self._iter_visible_tool_policies(flags, id_map)
        )

    def _append_tool_parts(
        self,
        parts: list[MessagePart],
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None,
    ) -> None:
        """Append visible tool parts based on filters."""
        filter_value = True if self.tools_always_visible else flags.show_tools
        id_map = self._tool_name_id_map(filter_value, tool_id_map)
        for tool in self._iter_visible_tools(flags, id_map):
            parts.append(MessagePart(MessagePartKind.TOOL, tool_to_parts(tool, id_map)))

    def _visible_tool_json_content(
        self,
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None,
    ) -> list[dict[str, object]]:
        """Return visible tools in structured JSON form."""
        filter_value = True if self.tools_always_visible else flags.show_tools
        id_map = self._tool_name_id_map(filter_value, tool_id_map)
        return [tool_to_json(tool, id_map) for tool in self._iter_visible_tools(flags, id_map)]

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

    def get_display_model(self) -> str | None:
        """Return the model metadata in its provider-normalized display form."""
        if self.model is None or self.custom_type:
            return self.model
        return self.model.removeprefix("claude-")

    def get_date_attribute(self) -> str | None:
        """Return the message date and time for XML attributes, semi-machine-friendly."""
        if timestamp := _message_timestamp_datetime(self.timestamp):
            return f"{timestamp:%Y-%m-%d %H:%M}"
        return None

    def get_display_date(self) -> str | None:
        """Return the human-friendly message date and time for Rich panel titles."""
        timestamp = _message_timestamp_datetime(self.timestamp)
        if timestamp is None:
            return None
        return f"{timestamp:%B} {_ordinal_day(timestamp.day)}, {timestamp:%H:%M}"

    def get_wrapper_attrs(self, *, text_encoding: str | None = None) -> str:
        """Build XML attributes string for this message's wrapper tag."""
        attrs: list[tuple[str, str | int]] = [("i", self.index)]
        if self.branch_id:
            attrs.append(("branch", self.branch_id))
        if self.role == "user":
            if self.is_meta:
                attrs.append(("isMeta", "true"))
            if self.source_tool_user_id:
                attrs.append(("sourceToolUserId", self.source_tool_user_id))
        if self.agent_id:
            attrs.append(("agent_id", self.agent_id))
            if self.subagent_type:
                attrs.append(("subagent_type", self.subagent_type))
            if self.name:
                attrs.append(("name", self.name))
        if model := self.get_display_model():
            attrs.append(("model", model))
        if self.custom_type:
            attrs.append(("custom_type", self.custom_type))
        if self.inherited_context is not None:
            attrs.append(("inherited_context", str(self.inherited_context).lower()))
        if self.status:
            attrs.append(("status", self.status))
        if text_encoding:
            attrs.append(("text_encoding", text_encoding))
        if date := self.get_date_attribute():
            attrs.append(("date", date))
        escape_attributes = self.custom_type is not None
        return " ".join(
            f'{name}="{html.escape(str(value), quote=True) if escape_attributes else value}"'
            for name, value in attrs
        )


def assign_progressive_shortening(
    messages: list[Message],
    flags: ConversationFlags,
    tool_id_map: dict[str, str] | None = None,
) -> None:
    """Assign one shared progressive position to each qualifying message."""
    for message in messages:
        message.progressive_position = None
        message.progressive_qualifying_count = 0

    qualifying_messages = [
        message
        for message in messages
        if message.has_progressive_payload(flags, tool_id_map)
    ]
    qualifying_count = len(qualifying_messages)
    for position, message in enumerate(qualifying_messages):
        message.progressive_position = position
        message.progressive_qualifying_count = qualifying_count
