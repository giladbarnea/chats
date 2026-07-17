from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from .parts import MessagePart, MessagePartKind, ToolParts
from .registry import TOOL_SCHEMAS, ContentBlockType
from .tool_filter import ToolFilter, resolve_tool_visibility
from .tools import tool_input_needs_wrapper, tool_to_json, tool_to_parts
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
    shorten_max_chars: int
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
        show_branches: bool = False,
        show_plans: bool = False,
        allow_empty_output: bool = False,
        shorten: bool = False,
        shorten_max_chars: int = 500,
        shorten_thinking: bool = False,
        color: bool | Literal["always", "never", "auto"] = False,
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
        self.shorten_max_chars = shorten_max_chars
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
            f"shorten={self.shorten}, shorten_max_chars={self.shorten_max_chars}, "
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
                shorten_data(self.text, max_chars=flags.shorten_max_chars)
                if flags.shorten
                else self.text
            )
            parts.append(MessagePart(MessagePartKind.TEXT, text))

        # Thinking block
        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(self.thinking, max_chars=flags.shorten_max_chars)
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
                shorten_data(self.plan, max_chars=flags.shorten_max_chars)
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
                shorten_data(self.text, max_chars=flags.shorten_max_chars)
                if flags.shorten
                else self.text
            )
            content.append(text)

        if flags.show_thinking and self.thinking:
            should_shorten_thinking = flags.shorten or flags.shorten_thinking
            thinking = (
                truncate_middle(self.thinking, max_chars=flags.shorten_max_chars)
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
                shorten_data(self.plan, max_chars=flags.shorten_max_chars)
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

        if self.model:
            payload["model"] = self.model.removeprefix("claude-")

        if self.timestamp:
            payload["timestamp"] = self.timestamp

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
        for tool in self.tools:
            show, local_short_max_chars = resolve_tool_visibility(
                tool,
                flags.show_tools,
                id_map,
                default_short_max_chars=flags.shorten_max_chars,
            )
            if not show:
                continue
            if local_short_max_chars is not None:
                tool = _shorten_tool_payload(tool, max_chars=local_short_max_chars)
            elif flags.shorten:
                tool = _shorten_tool_payload(tool, max_chars=flags.shorten_max_chars)
            yield tool

    def _append_tool_parts(
        self,
        parts: list[MessagePart],
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None,
    ) -> None:
        """Append visible tool parts based on filters."""
        id_map = self._tool_name_id_map(flags.show_tools, tool_id_map)
        for tool in self._iter_visible_tools(flags, id_map):
            parts.append(MessagePart(MessagePartKind.TOOL, tool_to_parts(tool, id_map)))

    def _visible_tool_json_content(
        self,
        flags: ConversationFlags,
        tool_id_map: dict[str, str] | None,
    ) -> list[dict[str, object]]:
        """Return visible tools in structured JSON form."""
        id_map = self._tool_name_id_map(flags.show_tools, tool_id_map)
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


_MESSAGE_WRAPPER_TYPES = {
    block_type.value.xml_tag: block_type
    for block_type in ContentBlockType
    if block_type.value.header is not None
}
_MESSAGE_JSON_KEYS = {
    "type",
    "role",
    "original_index",
    "content",
    "branch",
    "isMeta",
    "sourceToolUserId",
    "agent_id",
    "subagent_type",
    "name",
    "model",
    "timestamp",
}


def messages_from_json_data(data: object) -> list[Message]:
    """Reconstruct messages from the structured array emitted by ``-f json``.

    >>> messages_from_json_data([])
    []
    """
    if not isinstance(data, list):
        raise ValueError("Expected the JSON root to be an array of messages.")
    return [
        _message_from_json_data(payload, position)
        for position, payload in enumerate(data, start=1)
    ]


def _message_from_json_data(payload: object, position: int) -> Message:
    context = f"message {position}"
    if not isinstance(payload, dict):
        raise ValueError(f"Expected {context} to be an object.")

    unexpected_keys = set(payload) - _MESSAGE_JSON_KEYS
    if unexpected_keys:
        raise ValueError(
            f"Unexpected keys in {context}: {sorted(unexpected_keys)!r}."
        )

    wrapper_name = payload.get("type")
    if not isinstance(wrapper_name, str):
        raise ValueError(f"Expected {context}.type to be a string.")
    wrapper_type = _MESSAGE_WRAPPER_TYPES.get(wrapper_name)
    if wrapper_type is None:
        raise ValueError(f"Unknown message type in {context}: {wrapper_name!r}.")

    role = payload.get("role")
    if not isinstance(role, str):
        raise ValueError(f"Expected {context}.role to be a string.")

    original_index = payload.get("original_index")
    if type(original_index) is not int:
        raise ValueError(f"Expected {context}.original_index to be an integer.")

    content = payload.get("content")
    if not isinstance(content, list):
        raise ValueError(f"Expected {context}.content to be an array.")

    is_meta = payload.get("isMeta", False)
    if type(is_meta) is not bool:
        raise ValueError(f"Expected {context}.isMeta to be a boolean.")

    message = Message(
        role=role,
        index=original_index,
        agent_id=_optional_json_string(payload, "agent_id", context),
        timestamp=_optional_json_string(payload, "timestamp", context),
        subagent_type=_optional_json_string(payload, "subagent_type", context),
        name=_optional_json_string(payload, "name", context),
        model=_optional_json_string(payload, "model", context),
        is_meta=is_meta,
        source_tool_user_id=_optional_json_string(
            payload, "sourceToolUserId", context
        ),
        wrapper_type=wrapper_type,
        branch_id=_optional_json_string(payload, "branch", context),
    )
    _populate_message_content(message, content, context)
    return message


def _optional_json_string(
    payload: dict[object, object], key: str, context: str
) -> str | None:
    value = payload.get(key)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"Expected {context}.{key} to be a string.")


def _populate_message_content(
    message: Message, content: list[object], context: str
) -> None:
    text_values: list[str] = []
    text_positions: list[int] = []
    for position, block in enumerate(content, start=1):
        block_context = f"{context}.content[{position}]"
        if isinstance(block, str):
            text_values.append(block)
            text_positions.append(position)
            continue
        if not isinstance(block, dict):
            raise ValueError(f"Expected {block_context} to be a string or object.")

        block_type = block.get("type")
        if block_type == ContentBlockType.THINKING.value.xml_tag:
            message.thinking = _single_content_string(block, block_context)
            continue
        if block_type == ContentBlockType.SUBAGENT_TASK.value.xml_tag:
            message.subagent_task = _single_content_string(block, block_context)
            continue
        if block_type == ContentBlockType.TOOL_INPUT.value.xml_tag:
            _append_tool_input(message, block, block_context)
            continue
        if block_type == ContentBlockType.TOOL_OUTPUT.value.xml_tag:
            message.tools.append(_tool_output_from_json(block, block_context))
            continue
        raise ValueError(f"Unknown content type in {block_context}: {block_type!r}.")

    if text_positions and text_positions[-1] - text_positions[0] + 1 != len(text_positions):
        raise ValueError(f"Text values must be adjacent in {context}.content.")
    message.text = "\n\n".join(text_values)


def _single_content_string(block: dict[object, object], context: str) -> str:
    if set(block) != {"type", "content"} or not isinstance(
        block.get("content"), str
    ):
        raise ValueError(f"Expected {context} to contain one string content field.")
    return block["content"]


def _append_tool_input(
    message: Message, block: dict[object, object], context: str
) -> None:
    name = block.get("name")
    if not isinstance(name, str):
        raise ValueError(f"Expected {context}.name to be a string.")

    if name == "ExitPlanMode":
        if set(block) != {"type", "name", "plan"} or not isinstance(
            block.get("plan"), str
        ):
            raise ValueError(f"Expected {context}.plan to be a string.")
        message.plan = block["plan"]
        return

    tool_id = _optional_json_string(block, "id", context)
    input_fields = {
        key: value
        for key, value in block.items()
        if key not in {"type", "name", "id"}
    }
    nested_input = input_fields.get("input")
    is_collision_wrapper = (
        set(input_fields) == {"input"}
        and isinstance(nested_input, dict)
        and tool_input_needs_wrapper(name, nested_input)
    )
    schema = TOOL_SCHEMAS.get(name)
    is_schema_content = schema is not None and schema.content_key == "content"
    if is_collision_wrapper:
        input_data = nested_input
    elif set(input_fields) == {"content"} and not is_schema_content:
        input_data = input_fields["content"]
    else:
        input_data = input_fields

    tool: dict[str, object] = {
        "type": "tool_use",
        "name": name,
        "input": input_data,
    }
    if tool_id is not None:
        tool["id"] = tool_id
    message.tools.append(tool)


def _tool_output_from_json(
    block: dict[object, object], context: str
) -> dict[str, object]:
    allowed_keys = {"type", "name", "id", "is_error", "content"}
    unexpected_keys = set(block) - allowed_keys
    if unexpected_keys:
        raise ValueError(f"Unexpected keys in {context}: {sorted(unexpected_keys)!r}.")

    tool_id = _optional_json_string(block, "id", context)
    name = _optional_json_string(block, "name", context)
    is_error = block.get("is_error", False)
    if type(is_error) is not bool:
        raise ValueError(f"Expected {context}.is_error to be a boolean.")

    tool: dict[str, object] = {
        "type": "tool_result",
        "is_error": is_error,
    }
    if tool_id is not None:
        tool["tool_use_id"] = tool_id
    tool["name"] = name
    if "content" in block:
        tool["content"] = block["content"]
    return tool
