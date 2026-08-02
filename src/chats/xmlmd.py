from __future__ import annotations

import html
import json
import re

from .model import Message
from .registry import TOOL_SCHEMAS, ContentBlockType


_OUTER_TYPES = {
    block_type.value.xml_tag: block_type
    for block_type in ContentBlockType
    if block_type.value.header is not None
}
_OUTER_TAG_PATTERN = "|".join(re.escape(tag) for tag in _OUTER_TYPES)
_DOCUMENT_MESSAGE = re.compile(
    rf'<(?P<tag>{_OUTER_TAG_PATTERN})(?:\s+[\w-]+="[^"]*")*>\n.*?'
    rf'\n</(?P=tag)>(?:\n\n---\n\n|\Z)',
    re.DOTALL,
)
_OUTER_MESSAGE = re.compile(
    r'^<(?P<tag>[\w-]+)(?P<attrs>(?:\s+[\w-]+="[^"]*")*)>\n'
    r'(?P<header>[^\n]*)\n\n(?P<body>.*)\n</(?P=tag)>$',
    re.DOTALL,
)
_ATTRIBUTE = re.compile(r'([\w-]+)="([^"]*)"')
_INNER_BLOCK = re.compile(
    r'^<(?P<tag>thinking|subagent-task|tool-input|tool-output)'
    r'(?P<attrs>(?:\s+[\w-]+="[^"]*")*)>'
    r'(?P<body>.*?)</(?P=tag)>$',
    re.DOTALL | re.MULTILINE,
)
_FENCED_BODY = re.compile(r'^```[^\n]*\n(?P<content>.*)\n```$', re.DOTALL)
_EDIT_BODY = re.compile(
    r'^(?:old_string:\n```\n(?P<old>.*?)\n```)?'
    r'(?:\n?new_string:\n```\n(?P<new>.*?)\n```)?$',
    re.DOTALL,
)
_ROLE_BY_WRAPPER = {
    ContentBlockType.USER_MESSAGE: "user",
    ContentBlockType.USER_COMMAND_INPUT: "user",
    ContentBlockType.USER_COMMAND_OUTPUT: "user",
    ContentBlockType.COMPACTION: "user",
    ContentBlockType.CUSTOM: "custom",
    ContentBlockType.SESSION_RENAME: "session-rename",
}


def messages_from_xmlmd(content: str) -> list[Message]:
    """Reconstruct canonical messages from ``ch parse`` XML-tagged Markdown."""
    messages: list[Message] = []
    cursor = 0
    while cursor < len(content):
        match = _DOCUMENT_MESSAGE.match(content, cursor)
        if match is None:
            raise ValueError(f"Expected XML-tagged Markdown message {len(messages) + 1}.")
        block = match.group().removesuffix("\n\n---\n\n")
        messages.append(_message_from_xmlmd(block, len(messages) + 1))
        cursor = match.end()
    return messages


def _message_from_xmlmd(block: str, position: int) -> Message:
    match = _OUTER_MESSAGE.fullmatch(block)
    if match is None:
        raise ValueError(f"Expected XML-tagged Markdown message {position}.")

    tag = match.group("tag")
    wrapper_type = _OUTER_TYPES.get(tag)
    if wrapper_type is None:
        raise ValueError(f"Unknown message type in message {position}: {tag!r}.")

    attributes = dict(_ATTRIBUTE.findall(match.group("attrs")))
    if "i" not in attributes:
        raise ValueError(f"Expected message {position} to have an integer i attribute.")
    try:
        original_index = int(attributes.pop("i"))
    except ValueError as error:
        raise ValueError(
            f"Expected message {position} to have an integer i attribute."
        ) from error

    expected_header = _expected_header(wrapper_type, attributes)
    if match.group("header") != expected_header:
        raise ValueError(
            f"Expected message {position} header {expected_header!r}."
        )

    body = match.group("body")
    if wrapper_type is ContentBlockType.AGENT:
        body = _unindent_agent_body(body, position)

    date = attributes.pop("date", None)
    timestamp = f"{date.replace(' ', 'T')}:00" if date is not None else None
    is_meta = attributes.pop("isMeta", "false") == "true"
    source_tool_user_id = attributes.pop("sourceToolUserId", None)
    custom_type_value = attributes.pop("custom_type", None)
    custom_type = (
        html.unescape(custom_type_value) if custom_type_value is not None else None
    )
    status_value = attributes.pop("status", None)
    status = html.unescape(status_value) if status_value is not None else None
    inherited_context_value = attributes.pop("inherited_context", None)
    if inherited_context_value not in {None, "true", "false"}:
        raise ValueError(
            f"Expected message {position} inherited_context to be true or false."
        )
    inherited_context = (
        inherited_context_value == "true"
        if inherited_context_value is not None
        else None
    )
    message = Message(
        role=_ROLE_BY_WRAPPER.get(wrapper_type, "assistant"),
        index=original_index,
        text=body,
        agent_id=attributes.pop("agent_id", None),
        timestamp=timestamp,
        subagent_type=attributes.pop("subagent_type", None),
        name=attributes.pop("name", None),
        model=attributes.pop("model", None),
        custom_type=custom_type,
        inherited_context=inherited_context,
        status=status,
        is_meta=is_meta,
        source_tool_user_id=source_tool_user_id,
        wrapper_type=wrapper_type,
        branch_id=attributes.pop("branch", None),
    )
    if attributes:
        raise ValueError(
            f"Unexpected attributes in message {position}: {sorted(attributes)!r}."
        )

    _populate_xmlmd_content(message, body, position)
    if wrapper_type is ContentBlockType.AGENT:
        if is_meta or source_tool_user_id or _contains_only_tool_outputs(message):
            message.role = "user"
        elif message.subagent_task:
            message.role = "agent"
    return message


def _unindent_agent_body(body: str, position: int) -> str:
    lines: list[str] = []
    for line in body.splitlines(keepends=True):
        if not line.strip():
            lines.append(line)
            continue
        if not line.startswith("  "):
            raise ValueError(f"Expected indented agent content in message {position}.")
        lines.append(line[2:])
    return "".join(lines)


def _populate_xmlmd_content(message: Message, body: str, position: int) -> None:
    matches = list(_INNER_BLOCK.finditer(body))
    if not matches:
        message.text = body
        return

    text_prefix = body[: matches[0].start()]
    message.text = text_prefix.removesuffix("\n\n")
    cursor = matches[0].start()
    for block_index, match in enumerate(matches):
        separator = body[cursor : match.start()]
        previous = matches[block_index - 1] if block_index else None
        if previous is not None and previous.group("tag") == "subagent-task":
            message.text = _text_between_blocks(separator, position)
        else:
            expected_separator = "" if previous is None else _inner_separator(previous)
            if separator != expected_separator:
                raise ValueError(f"Unexpected content between blocks in message {position}.")
        _append_inner_block(message, match, position)
        cursor = match.end()

    trailing = body[cursor:]
    if matches[-1].group("tag") == "subagent-task" and trailing:
        message.text = _text_between_blocks(trailing, position, trailing=True)
    elif trailing:
        raise ValueError(f"Unexpected content after blocks in message {position}.")


def _text_between_blocks(
    content: str, position: int, *, trailing: bool = False
) -> str:
    prefix = "\n\n"
    suffix = "" if trailing else "\n\n"
    if not content.startswith(prefix) or not content.endswith(suffix):
        raise ValueError(f"Unexpected content after subagent task in message {position}.")
    end = len(content) - len(suffix) if suffix else len(content)
    return content[len(prefix) : end]


def _inner_separator(previous: re.Match[str]) -> str:
    return "\n" if previous.group("tag").startswith("tool-") else "\n\n"


def _append_inner_block(
    message: Message, match: re.Match[str], position: int
) -> None:
    tag = match.group("tag")
    body = match.group("body")
    if body.startswith("\n"):
        body = body[1:]
    if body.endswith("\n"):
        body = body[:-1]
    if tag == "thinking":
        message.thinking = body
        return
    if tag == "subagent-task":
        message.subagent_task = body
        return

    attributes = dict(_ATTRIBUTE.findall(match.group("attrs")))
    name = attributes.pop("name", None)
    if tag == "tool-output":
        message.tools.append(_tool_output_from_xmlmd(name, attributes, body, position))
        return
    if name is None:
        raise ValueError(f"Expected tool input in message {position} to have a name.")
    if name == "ExitPlanMode":
        message.plan = body
        return
    message.tools.append(_tool_input_from_xmlmd(name, attributes, body, position))


def _tool_input_from_xmlmd(
    name: str, attributes: dict[str, str], body: str, position: int
) -> dict[str, object]:
    tool_id = attributes.pop("id", None)
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        input_data = json.loads(_unfence(body)) if body else attributes
    else:
        input_data = dict(attributes)
        if name == "Edit" and body:
            input_data.update(_edit_input_from_body(body, position))
        elif schema.content_key is not None and body:
            input_data[schema.content_key] = _unfence(body)

    tool: dict[str, object] = {"type": "tool_use", "name": name, "input": input_data}
    if tool_id is not None:
        tool["id"] = tool_id
    return tool


def _tool_output_from_xmlmd(
    name: str | None,
    attributes: dict[str, str],
    body: str,
    position: int,
) -> dict[str, object]:
    allowed = {"id", "is_error"}
    unexpected = set(attributes) - allowed
    if unexpected:
        raise ValueError(
            f"Unexpected tool output attributes in message {position}: {sorted(unexpected)!r}."
        )
    tool: dict[str, object] = {
        "type": "tool_result",
        "name": name,
        "is_error": attributes.get("is_error") == "true",
    }
    if tool_id := attributes.get("id"):
        tool["tool_use_id"] = tool_id
    if body:
        tool["content"] = _unfence(body)
    return tool


def _unfence(body: str) -> str:
    match = _FENCED_BODY.fullmatch(body)
    return match.group("content") if match is not None else body


def _edit_input_from_body(body: str, position: int) -> dict[str, str]:
    match = _EDIT_BODY.fullmatch(body)
    if match is None:
        raise ValueError(f"Expected canonical Edit body in message {position}.")
    return {
        key: value
        for key, value in (("old_string", match.group("old")), ("new_string", match.group("new")))
        if value is not None
    }


def _contains_only_tool_outputs(message: Message) -> bool:
    return bool(message.tools) and all(
        tool.get("type") == "tool_result" for tool in message.tools
    )


def _expected_header(
    wrapper_type: ContentBlockType, attributes: dict[str, str]
) -> str:
    if wrapper_type is not ContentBlockType.AGENT:
        return wrapper_type.value.header or ""
    if attributes.get("subagent_type") == "fork":
        return "## Fork"
    if name := attributes.get("name"):
        return f"## Agent '{name}'"
    return "## Agent"
