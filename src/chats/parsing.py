from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import textwrap
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import orjson

from ._native import (
    classify_native_session_path,
    discover_session_files,
    files_contain_ascii_json_strings,
    find_last_jsonl_timestamp,
    scan_resolution_facets,
)
from .model import ConversationFlags, Message, Provider, SubagentMetadata
from .codex_delegation import delegated_parent, verified_cli_forks
from .claude_delegation import AgentOrigins, agent_origins, notification_messages
from .registry import (
    ContentBlockType,
    normalize_tool_input_keys,
    normalize_tool_name,
)
from .utils import shorten_tool_use_id

NameEntryBuilder = Callable[[list[dict], str, str], list[dict]]
FirstEntryMatcher = Callable[[dict], bool]


@dataclass(frozen=True)
class JsonlSessionAdapter:
    """A parser adapter for one JSONL session shape."""

    name: Provider
    parse_messages: Callable[[str, ConversationFlags], list[Message]]
    build_name_entries: NameEntryBuilder
    find_session_matches: Callable[[str], list[tuple[Path, str]]] | None = None
    is_sidechain_path: Callable[[Path], bool] = lambda _path: False
    extract_session_id: Callable[[Path], str | None] = lambda path: path.stem
    extract_parent_session: Callable[[Path], str | None] = lambda _path: None
    extract_forked_from: Callable[[Path], str | None] = lambda _path: None
    extract_forked_at: Callable[[Path], str | None] = lambda _path: None
    own_entries: Callable[[list[dict]], list[dict]] = lambda entries: entries
    matches_first_entry: FirstEntryMatcher | None = None


def get_jsonl_timestamps(file_path: Path) -> tuple[datetime | None, datetime | None]:
    """
    Efficiently extract first and last timestamps from a JSONL file.

    Returns (created_at, modified_at) as datetime objects (or None).
    Uses optimized forward scan for start time and backward scan for end time.
    """
    return get_jsonl_first_timestamp(file_path), get_jsonl_last_timestamp(file_path)


def get_jsonl_first_timestamp(file_path: Path) -> datetime | None:
    """Stream a JSONL file forward for the first in-band timestamp, falling back to filesystem birth time."""
    if first_ts := _find_first_timestamp(file_path):
        if parsed := _parse_iso_timestamp(first_ts):
            return parsed
    try:
        return datetime.fromtimestamp(file_path.stat().st_birthtime)
    except OSError:
        return None


def get_jsonl_last_timestamp(file_path: Path) -> datetime | None:
    """Stream a JSONL file backward for the last in-band timestamp, falling back to filesystem mtime."""
    if last_ts := find_last_jsonl_timestamp(
        str(file_path), _jsonl_line_timestamp, json.JSONDecodeError
    ):
        if parsed := _parse_iso_timestamp(last_ts):
            return parsed
    try:
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    except OSError:
        return None


def _entry_timestamp(entry: dict) -> str | None:
    timestamp = entry.get("timestamp") or entry.get("created_at")
    return timestamp if isinstance(timestamp, str) and timestamp else None


def _jsonl_line_timestamp(line: str) -> str | None:
    return _entry_timestamp(json.loads(line))


def _find_first_timestamp(file_path: Path) -> str | None:
    """Finds the first timestamp by reading from the beginning."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if timestamp := _entry_timestamp(entry):
                        return timestamp
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return None


def _parse_iso_timestamp(ts_str: str) -> datetime | None:
    """Parse ISO timestamp string to naive local-time datetime.

    JSONL timestamps are typically UTC (trailing 'Z'). We convert to local time
    so comparisons with datetime.now() (used by relative date filters) are correct.
    """
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        return None


def _extract_field_from_content(
    content: str, entry_type: str, field_name: str
) -> list[str]:
    """
    Extract field values from JSONL entries matching a specific type.

    Handles both compact JSONL (one JSON per line) and pretty-printed JSON.

    Args:
        content: JSONL content string
        entry_type: The "type" field value to match (e.g., "summary", "custom-title")
        field_name: The field to extract from matching entries

    Returns:
        List of field values found in the content
    """
    values = []

    # Try to parse as compact JSONL first (most common)
    for line in content.split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
            if (
                isinstance(entry, dict)
                and entry.get("type") == entry_type
                and (value := entry.get(field_name))
            ):
                values.append(value)
        except json.JSONDecodeError:
            pass

    # If no values found, try parsing multi-line JSON objects
    if not values:
        buffer = ""
        brace_count = 0
        for line in content.split("\n"):
            buffer += line
            brace_count += line.count("{") - line.count("}")

            if brace_count == 0 and buffer.strip():
                try:
                    entry = json.loads(buffer)
                    if (
                        isinstance(entry, dict)
                        and entry.get("type") == entry_type
                        and (value := entry.get(field_name))
                    ):
                        values.append(value)
                except json.JSONDecodeError:
                    pass
                buffer = ""

    return values


def _extract_field_from_entries(
    entries: list[dict], entry_type: str, field_name: str
) -> list[str]:
    """Extract field values from parsed JSONL entries."""
    values: list[str] = []
    for entry in entries:
        if entry.get("type") != entry_type:
            continue
        value = entry.get(field_name)
        if isinstance(value, str) and value:
            values.append(value)
    return values


def _extract_field_from_jsonl(
    file_path: Path, entry_type: str, field_name: str
) -> list[str]:
    """Extract field values from a jsonl file without loading it entirely."""
    values = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("{"):
                    continue
                # Fast path: skip JSON parsing if entry_type isn't in the raw string
                if f'"{entry_type}"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                    if (
                        isinstance(entry, dict)
                        and entry.get("type") == entry_type
                        and (value := entry.get(field_name))
                    ):
                        values.append(value)
                except json.JSONDecodeError:
                    pass
        return values
    except OSError:
        return []


def extract_summaries_from_content(content: str) -> list[str]:
    """Extract all summary fields from JSONL content string."""
    return _extract_field_from_content(content, "summary", "summary")


def extract_summaries_from_jsonl(file_path: Path) -> list[str]:
    """Extract all summary fields from a jsonl conversation file."""
    return _extract_field_from_jsonl(file_path, "summary", "summary")


def _extract_custom_title_from_entry(entry: dict) -> str | None:
    """Return the shared custom-title abstraction from one provider-native entry."""
    raw_title: object | None = None

    if entry.get("type") == "custom-title":
        raw_title = entry.get("customTitle")
    elif entry.get("type") == "session_info":
        raw_title = entry.get("name")
    elif entry.get("type") == "event_msg":
        payload = entry.get("payload", {})
        if payload.get("type") == "thread_name_updated":
            raw_title = payload.get("thread_name")

    if not isinstance(raw_title, str):
        return None

    custom_title = raw_title.strip()
    return custom_title or None


def extract_custom_titles_from_content(content: str) -> list[str]:
    """Extract all shared custom-title values from JSONL content string."""
    values: list[str] = []

    for line in content.split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if custom_title := _extract_custom_title_from_entry(entry):
            values.append(custom_title)

    if values:
        return values

    buffer = ""
    brace_count = 0
    for line in content.split("\n"):
        buffer += line
        brace_count += line.count("{") - line.count("}")

        if brace_count != 0 or not buffer.strip():
            continue

        try:
            entry = json.loads(buffer)
        except json.JSONDecodeError:
            buffer = ""
            continue

        if isinstance(entry, dict) and (
            custom_title := _extract_custom_title_from_entry(entry)
        ):
            values.append(custom_title)
        buffer = ""

    return values


def extract_custom_titles_from_entries(entries: list[dict]) -> list[str]:
    """Extract all shared custom-title values from parsed JSONL entries."""
    values: list[str] = []
    for entry in entries:
        if custom_title := _extract_custom_title_from_entry(entry):
            values.append(custom_title)
    return values


def extract_custom_titles_from_jsonl(file_path: Path) -> list[str]:
    """Extract all shared custom-title values from a jsonl conversation file."""
    values: list[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("{"):
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if custom_title := _extract_custom_title_from_entry(entry):
                    values.append(custom_title)
        return values
    except OSError:
        return []


def extract_latest_custom_title_from_content(content: str) -> str | None:
    """Extract only the latest shared custom-title value from JSONL content."""
    latest_custom_title: str | None = None

    for line in content.split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if custom_title := _extract_custom_title_from_entry(entry):
            latest_custom_title = custom_title

    if latest_custom_title is not None:
        return latest_custom_title

    buffer = ""
    brace_count = 0
    for line in content.split("\n"):
        buffer += line
        brace_count += line.count("{") - line.count("}")

        if brace_count != 0 or not buffer.strip():
            continue

        try:
            entry = json.loads(buffer)
        except json.JSONDecodeError:
            buffer = ""
            continue

        if isinstance(entry, dict) and (
            custom_title := _extract_custom_title_from_entry(entry)
        ):
            latest_custom_title = custom_title
        buffer = ""

    return latest_custom_title


def extract_latest_custom_title_from_jsonl(file_path: Path) -> str | None:
    """Extract only the latest shared custom-title value from a jsonl conversation file."""
    latest_custom_title: str | None = None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("{"):
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if custom_title := _extract_custom_title_from_entry(entry):
                    latest_custom_title = custom_title
    except OSError:
        return None

    return latest_custom_title


def _jsonl_line_resolution_facets(line: str) -> tuple[str | None, str | None]:
    """Extract a possible current title and summary from one marker-positive line.

    >>> _jsonl_line_resolution_facets('{"type":"summary","summary":"keep"}')
    (None, 'keep')
    """
    stripped = line.strip()
    if not stripped or not stripped.startswith("{"):
        return None, None

    entry = json.loads(stripped)
    if not isinstance(entry, dict):
        return None, None

    summary = entry.get("summary") if entry.get("type") == "summary" else None
    if not isinstance(summary, str) or not summary:
        summary = None
    return _extract_custom_title_from_entry(entry), summary


def extract_resolution_facets_from_jsonl(file_path: Path) -> tuple[str | None, list[str]]:
    """Extract the current title and summaries needed for identifier fallback resolution."""
    return scan_resolution_facets(
        os.fsencode(file_path),
        _jsonl_line_resolution_facets,
        json.JSONDecodeError,
    )


_JSON_ESCAPED_ASCII_CHARACTERS = frozenset('"\\') | {chr(code) for code in range(0x20)}


def files_possibly_containing_text(files: list[Path], text: str) -> list[Path]:
    """Drop files whose JSON strings cannot contain `text`, case-insensitively.

    A conservative parallel byte gate that never drops a file holding the text.
    Text the gate cannot express (non-ASCII, or characters JSON escapes) keeps every file.

    >>> files_possibly_containing_text([Path("/missing.jsonl")], 'say "hi"')
    [PosixPath('/missing.jsonl')]
    """
    if not text.isascii() or not _JSON_ESCAPED_ASCII_CHARACTERS.isdisjoint(text):
        return files
    decisions = files_contain_ascii_json_strings(
        [os.fsencode(file) for file in files], text.encode("ascii")
    )
    return [file for file, decision in zip(files, decisions, strict=True) if decision]


def validate_jsonl(content: str) -> None:
    """Raise ValueError unless the first non-empty line is a typed JSON object.

    >>> validate_jsonl('{"type": "user"}')
    """
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "type" in obj:
                return
        except (json.JSONDecodeError, ValueError):
            pass
        break

    raise ValueError("Expected JSONL input with a 'type' field in its first non-empty line.")


def _iter_jsonl_entries(content: str) -> list[dict]:
    """Parse a JSONL string into a list of JSON object entries."""
    entries: list[dict] = []

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            entry = orjson.loads(line)
        except orjson.JSONDecodeError:
            continue

        if isinstance(entry, dict):
            entries.append(entry)

    return entries


def decode_jsonl_entries(content: str) -> list[dict]:
    """Decode JSONL content into parsed object entries."""
    return _iter_jsonl_entries(content)


def _extract_text_blocks(content_data: object) -> list[str]:
    """Collect text blocks from a message content field."""
    if isinstance(content_data, str):
        return [content_data] if content_data else []

    if not isinstance(content_data, list):
        return []

    text_blocks: list[str] = []
    for item in content_data:
        if not isinstance(item, dict):
            continue
        if text := item.get("text", "").strip():
            text_blocks.append(text)
    return text_blocks


_TASK_NOTIFICATION_PATTERN = re.compile(
    r"\s*<task-notification>(?P<body>.*)</task-notification>\s*",
    re.DOTALL,
)


def _is_task_notification(content: str) -> bool:
    """Whether a Claude user string is a background-task notification.

    Native agent deliveries require separate origin and dispatch checks before
    they become agent messages; shell notifications remain hidden.

    >>> _is_task_notification("<task-notification><status>completed</status></task-notification>")
    True
    >>> _is_task_notification("typed <task-notification> text")
    False
    """
    return _TASK_NOTIFICATION_PATTERN.fullmatch(content) is not None


_TAG_ATTRIBUTE_PATTERN = re.compile(r'([\w-]+)="([^"]*)"')
_CLAUDE_PEER_MESSAGE_PREFIX = "Another Claude session sent a message:"
_CLAUDE_PEER_BLOCK_OPENING_PATTERN = re.compile(
    r"<(?P<tag>teammate-message|cross-session-message)(?P<attributes>[^>]*)>"
)
# The attribute naming the sending session, per peer block kind.
_CLAUDE_PEER_SENDER_ATTRIBUTES: dict[str, str] = {
    "teammate-message": "teammate_id",
    "cross-session-message": "from-name",
}


_CLAUDE_TEAM_LEAD = "team-lead"


def _split_claude_peer_blocks(
    content: str, *, in_agent_transcript: bool = False
) -> list[tuple[str | None, str]]:
    """Split a message relayed from another Claude session into (sender, body) pairs.

    Claude Code stores a teammate or cross-session message as a user string:
    a fixed prefix line, one block per relayed message, and a fixed trailer.
    Inside a teammate's own transcript the blocks arrive without the prefix.
    Anything else yields no blocks.

    >>> _split_claude_peer_blocks(
    ...     "Another Claude session sent a message:\\n"
    ...     '<teammate-message teammate_id="scout" color="blue">\\nhello\\n</teammate-message>\\n'
    ...     '<cross-session-message from="uds:/x.sock" from-name="lead">\\nhi\\n</cross-session-message>\\n'
    ...     "\\nThis came from another Claude session.\\n"
    ... )
    [('scout', 'hello'), ('lead', 'hi')]
    >>> _split_claude_peer_blocks('typed text mentioning <teammate-message teammate_id="x">')
    []
    >>> _split_claude_peer_blocks(
    ...     '<teammate-message teammate_id="team-lead">\\ngo\\n</teammate-message>',
    ...     in_agent_transcript=True,
    ... )
    [('team-lead', 'go')]
    """
    stripped = content.lstrip()
    relayed = stripped.startswith(_CLAUDE_PEER_MESSAGE_PREFIX) or (
        in_agent_transcript and stripped.startswith("<teammate-message")
    )
    if not relayed:
        return []
    blocks: list[tuple[str | None, str]] = []
    cursor = 0
    while opening := _CLAUDE_PEER_BLOCK_OPENING_PATTERN.search(content, cursor):
        closing_tag = f"</{opening.group('tag')}>"
        close_start = content.find(closing_tag, opening.end())
        if close_start == -1:
            break
        attributes = dict(_TAG_ATTRIBUTE_PATTERN.findall(opening.group("attributes")))
        sender = attributes.get(_CLAUDE_PEER_SENDER_ATTRIBUTES[opening.group("tag")])
        blocks.append((sender, content[opening.end() : close_start].strip()))
        cursor = close_start + len(closing_tag)
    return blocks


def _claude_peer_text(body: str) -> str:
    """Keep delivered reports inside idle envelopes, but omit bare status pings.

    >>> _claude_peer_text('{"type":"idle_notification","from":"x"}')
    ''
    >>> _claude_peer_text('{"type":"idle_notification","result":"done"}')
    'done'
    >>> _claude_peer_text("{not json")
    '{not json'
    """
    if not body.startswith("{"):
        return body
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    if not isinstance(payload, dict) or payload.get("type") != "idle_notification":
        return body
    return payload.get("result") or payload.get("summary") or payload.get("failureReason") or ""


def _claude_peer_message(
    entry: dict, sender: str | None, body: str, flags: ConversationFlags
) -> Message | None:
    """Represent one relayed message: the team lead plays the user, any other sender is an agent.

    Idle envelopes keep their delivered result; empty status pings render nothing.
    """
    body = _claude_peer_text(body)
    if not body:
        return None
    if sender == _CLAUDE_TEAM_LEAD:
        if not flags.show_user_messages:
            return None
        return Message(role="user", timestamp=entry.get("timestamp"), text=body)
    if not flags.show_agents:
        return None
    return Message(
        role="agent",
        agent_id=sender,
        name=sender,
        timestamp=entry.get("timestamp"),
        text=body,
        wrapper_type=ContentBlockType.AGENT,
    )


_COMMAND_TAG_LINE_PATTERN = re.compile(
    r"(?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</(?P=tag)>[ \t]*",
    re.DOTALL,
)
_LOCAL_COMMAND_STDOUT_PATTERN = re.compile(
    r"\s*<local-command-stdout>(?P<value>.*?)</local-command-stdout>\s*",
    re.DOTALL,
)


def _normalize_command_tag_value(raw_value: str) -> str:
    """Trim outer whitespace while preserving meaningful internal indentation."""
    stripped = raw_value.strip()
    if "\n" not in stripped:
        return stripped
    return textwrap.dedent(stripped).strip()


def _parse_command_tag_lines(content: str) -> list[tuple[int, str, str]] | None:
    """Parse pure command-tag lines while preserving their relative indentation."""
    parsed_lines: list[tuple[int, str, str]] = []

    for raw_line in content.splitlines():
        if not raw_line.strip():
            continue

        match = _COMMAND_TAG_LINE_PATTERN.fullmatch(raw_line)
        if match is None:
            return None

        indent = len(match.group("indent").expandtabs(4))
        key = match.group("tag").removeprefix("command-")
        value = _normalize_command_tag_value(match.group("value"))
        parsed_lines.append((indent, key, value))

    return parsed_lines or None


def _render_command_yaml_line_with_indent(key: str, value: str, level: int) -> str:
    """Render one command line with indentation derived from the source tree."""
    indent = "  " * level
    if "\n" not in value:
        return f"{indent}{key}: {_render_command_yaml_scalar(value)}"

    block_indent = indent + "  "
    indented_value = textwrap.indent(value, block_indent)
    return f"{indent}{key}: |-\n{indented_value}"


def _render_command_yaml_scalar(value: str) -> str:
    """Quote scalar command values unless they already look like YAML primitives."""
    if (
        value.isnumeric()
        or value.removeprefix("-").isnumeric()
        or value in ("true", "false")
    ):
        return value

    escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped_value}"'


def _render_user_command_input(content: str) -> str | None:
    """Convert pure `<command-*>` user strings into a YAML code block."""
    parsed_lines = _parse_command_tag_lines(content)
    if parsed_lines is None:
        return None

    base_indent = min(indent for indent, _, _ in parsed_lines)
    relative_indents = sorted({indent - base_indent for indent, _, _ in parsed_lines})
    indent_levels = {indent: level for level, indent in enumerate(relative_indents)}

    yaml_lines: list[str] = []
    for indent, key, value in parsed_lines:
        level = indent_levels[indent - base_indent]
        yaml_lines.append(_render_command_yaml_line_with_indent(key, value, level))

    if not yaml_lines:
        return None

    return "```yaml\n" + "\n".join(yaml_lines) + "\n```"


def _is_hidden_user_command_text(content: str) -> bool:
    """Return True when a user text block is protocol command I/O that stays hidden."""
    if _LOCAL_COMMAND_STDOUT_PATTERN.fullmatch(content):
        return True
    return _parse_command_tag_lines(content) is not None


def _filter_hidden_user_text_blocks(text_blocks: list[str]) -> list[str]:
    """Drop user text blocks that represent hidden command protocol content."""
    return [text for text in text_blocks if not _is_hidden_user_command_text(text)]


_CLAUDE_FORK_BOILERPLATE_CLOSE = "</fork-boilerplate>"


def _strip_claude_fork_boilerplate(text: str) -> str:
    """Drop the worker boilerplate Claude Code prepends to a fork's directive.

    >>> _strip_claude_fork_boilerplate("<fork-boilerplate>\\nrules\\n</fork-boilerplate>\\n\\nYour directive: go")
    'Your directive: go'
    >>> _strip_claude_fork_boilerplate("typed <fork-boilerplate> text")
    'typed <fork-boilerplate> text'
    """
    if not text.lstrip().startswith("<fork-boilerplate>"):
        return text
    _, closed, directive = text.partition(_CLAUDE_FORK_BOILERPLATE_CLOSE)
    return directive.strip() if closed else text


def _parse_user_string_content(
    content: str,
) -> tuple[str, ContentBlockType | None]:
    """Detect special Claude user string content that needs wrapper/content overrides."""
    if _is_hidden_user_command_text(content):
        return "", None

    return content, None


def _is_claude_foreign_record(entry: dict) -> bool:
    """Whether a record was copied from another session by a Claude fork.

    Copied records keep the writer's snake_case `session_id`; camelCase `sessionId`
    names the session that holds the file.

    >>> _is_claude_foreign_record({"session_id": "parent", "sessionId": "child"})
    True
    >>> _is_claude_foreign_record({"session_id": "child", "sessionId": "child"})
    False
    >>> _is_claude_foreign_record({"sessionId": "child"})
    False
    """
    writer = entry.get("session_id")
    return bool(writer) and writer != entry.get("sessionId")


def _claude_own_entries(entries: list[dict]) -> list[dict]:
    """Remove copied context only when embedding a delegated fork in its parent.

    >>> _claude_own_entries([{"session_id": "p", "sessionId": "c"}, {"type": "user"}])
    [{'type': 'user'}]
    """
    end = next((index + 1 for index in range(len(entries) - 1, -1, -1)
                if _is_claude_foreign_record(entries[index])), 0)
    while end and end < len(entries) and entries[end].get("type") == "system":
        end += 1
    return entries[end:]


def _claude_successful_bash_calls(entries: list[dict]) -> list[tuple[str, str]]:
    """Pair this session's executed Bash calls with successful results by exact tool id.

    >>> _claude_successful_bash_calls([])
    []
    """
    calls: dict[str, str] = {}
    completed = []
    for entry in _claude_own_entries(entries):
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if entry.get("type") == "assistant" and block.get("type") == "tool_use" and block.get("name") == "Bash":
                calls[block["id"]] = block.get("input", {}).get("command", "")
            if entry.get("type") == "user" and block.get("type") == "tool_result" and not block.get("is_error"):
                command = calls.get(block.get("tool_use_id"))
                if command:
                    completed.append((command, "\n".join(_extract_text_blocks(block.get("content")))))
    return completed


def _claude_background_fork_prefixes(entries: list[dict]) -> list[str]:
    """Read child identifiers from native user `/fork` launch receipts, not quoted text.

    >>> _claude_background_fork_prefixes([])
    []
    """
    children = []
    pending = False
    for entry in _claude_own_entries(entries):
        if entry.get("type") != "system" or entry.get("subtype") != "local_command":
            continue
        content = entry.get("content", "")
        if "<command-name>" in content:
            pending = "<command-name>/fork</command-name>" in content
            continue
        match = re.fullmatch(r"<local-command-stdout>session running · .* · ([0-9a-f]{8})</local-command-stdout>", content)
        if pending and match:
            children.append(match.group(1))
        pending = False
    return children


@dataclass(frozen=True)
class ClaudeLineage:
    """What a Claude transcript proves about where it came from."""

    parent_session: str | None = None
    forked_from: str | None = None
    forked_at: str | None = None


@functools.lru_cache(maxsize=8)
def _read_claude_lineage(session_file: Path) -> ClaudeLineage:
    """Read a Claude transcript's spawner and fork source from its own records.

    A subagent transcript names its parent session: a fork's leading
    `fork-context-ref` through `parentSessionId`, any other subagent through the
    `sessionId` its records carry. Scan all provenance tags because a fork can insert
    its own environment record before its copied history.
    """
    lineage = ClaudeLineage()
    with session_file.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "fork-context-ref":
                parent = entry.get("parentSessionId")
                return ClaudeLineage(parent_session=parent, forked_from=parent)
            if entry.get("isSidechain") is True:
                return ClaudeLineage(parent_session=entry.get("sessionId"))
            if not entry.get("session_id"):
                continue
            if not _is_claude_foreign_record(entry):
                continue
            lineage = ClaudeLineage(
                forked_from=entry["session_id"],
                forked_at=entry.get("timestamp") or lineage.forked_at,
            )
    return lineage


def _parse_default_jsonl_entries(
    entries: list[dict], flags: ConversationFlags
) -> list[Message]:
    """Parse Claude-style JSONL entries into the shared Message model."""
    branch_of = _resolve_branch_map(entries)
    agent_tool_ids = _claude_agent_tool_ids(entries)
    origins = agent_origins(entries) if flags.show_agents else None
    messages = []
    index = 1
    for entry in entries:
        branch_id = branch_of.get(entry.get("uuid"))
        if branch_id is not None and not flags.show_branches:
            continue  # abandoned rewind branch, hidden unless -b/--branches

        entry_type = entry.get("type")
        if entry_type == "user":
            parsed_messages = _parse_user_entry(entry, index, flags, agent_tool_ids, origins)
        elif entry_type == "assistant":
            parsed_messages = _parse_assistant_entry(entry, index, flags)
        elif entry_type == "system":
            parsed_messages = [_parse_system_entry(entry, index, flags)]
        elif entry_type == "attachment":
            parsed_messages = [_parse_hook_additional_context_entry(entry, index, flags)]
        else:
            parsed_messages = []

        for msg in parsed_messages:
            if msg and msg.has_content():
                msg.index = index
                msg.branch_id = branch_id
                messages.append(msg)
                index += 1

    return messages


# Tools that talk to agents rather than act on the world: agent content, like Pi's team_*.
_CLAUDE_AGENT_MESSAGING_TOOLS = frozenset({"Agent", "SendMessage", "ListAgents"})


def _claude_agent_tool_ids(entries: list[dict]) -> frozenset[str]:
    """Collect the ids of agent-messaging tool calls, so their results classify with them.

    >>> sorted(_claude_agent_tool_ids([{"type": "assistant", "message": {"content": [
    ...     {"type": "tool_use", "id": "a", "name": "SendMessage"},
    ...     {"type": "tool_use", "id": "b", "name": "Bash"},
    ... ]}}]))
    ['a']
    """
    return frozenset(
        item["id"]
        for entry in entries
        if entry.get("type") == "assistant"
        and isinstance(content := (entry.get("message") or {}).get("content"), list)
        for item in content
        if isinstance(item, dict)
        and item.get("type") == "tool_use"
        and item.get("name") in _CLAUDE_AGENT_MESSAGING_TOOLS
        and item.get("id")
    )


def _collect_subtree(root: str, children: dict[str | None, list[str]]) -> set[str]:
    """Return every uuid reachable from `root` (iterative; safe on deep threads)."""
    seen: set[str] = set()
    stack = [root]
    while stack:
        node_uuid = stack.pop()
        if node_uuid in seen:
            continue
        seen.add(node_uuid)
        stack.extend(children.get(node_uuid, []))
    return seen


def _subtree_depths(
    roots: list[str], children: dict[str | None, list[str]]
) -> dict[str, int]:
    """Longest downward chain length per node (iterative reverse-preorder memo)."""
    depth: dict[str, int] = {}
    for root in roots:
        order: list[str] = []
        stack = [root]
        while stack:
            node_uuid = stack.pop()
            order.append(node_uuid)
            stack.extend(children.get(node_uuid, []))
        for node_uuid in reversed(order):
            kids = children.get(node_uuid, [])
            depth[node_uuid] = 1 + max((depth[kid] for kid in kids), default=0)
    return depth


def _deepest_descendant(
    root: str, children: dict[str | None, list[str]], depth: dict[str, int]
) -> str:
    """Follow the deepest child from `root` to its leaf (the longest continuation)."""
    cursor = root
    while children.get(cursor):
        cursor = max(children[cursor], key=lambda child: depth[child])
    return cursor


def _resolve_branch_map(entries: list[dict]) -> dict[str, str]:
    """Map each off-main-branch node uuid to a stable branch id.

    A Claude transcript is a forest. Real eras are the session start and each
    `/compact` boundary; a rewind to the first message adds an abandoned null-parent
    user root, which is a detour, not an era. Within each era the active branch is
    chosen by the latest `last-prompt` `leafUuid` and followed *down* to its tip (the
    reply below the recorded leaf), then up to the root; with no recorded leaf the
    longest continuation wins. Nodes off every era's main path are abandoned rewind
    branches, each identified by its *head* — the first node that left the main thread
    — so one detour shares one id; ids are numbered by first appearance.
    """
    nodes = {entry["uuid"]: entry for entry in entries if "uuid" in entry}
    if not nodes:
        return {}

    children: dict[str | None, list[str]] = defaultdict(list)
    parent: dict[str, str | None] = {}
    for node_uuid, node in nodes.items():
        parent_uuid = node.get("parentUuid")
        children[parent_uuid].append(node_uuid)
        parent[node_uuid] = parent_uuid

    # A root starts a tree: parentUuid is null (session start or compaction boundary)
    # or points outside this file (a snippet whose head was truncated).
    all_roots = [
        node_uuid
        for node_uuid, node in nodes.items()
        if node.get("parentUuid") is None or node.get("parentUuid") not in nodes
    ]
    leaves = [
        entry["leafUuid"]
        for entry in entries
        if entry.get("type") == "last-prompt" and entry.get("leafUuid") in nodes
    ]
    depth = _subtree_depths(all_roots, children)

    # Compaction boundaries are real eras. Session-start roots are real too, except
    # that a rewind to the first message leaves a second null-parent user root: only
    # the one holding the active leaf is real, the rest are abandoned. When the leaf
    # can't disambiguate them (it lives in a later era, or none is recorded), keep all.
    def _is_compaction(node_uuid: str) -> bool:
        node = nodes[node_uuid]
        return node.get("type") == "system" and node.get("subtype") == "compact_boundary"

    def _origin_session_root(start_leaf: str) -> str | None:
        """The session-start root of the lineage the active leaf belongs to, hopping
        back across compaction boundaries via their `logicalParentUuid`."""
        cursor: str | None = start_leaf
        visited: set[str] = set()
        while cursor in nodes and cursor not in visited:
            visited.add(cursor)
            root = cursor
            while parent.get(root) in nodes:
                root = parent[root]
            if not _is_compaction(root):
                return root
            cursor = nodes[root].get("logicalParentUuid")
        return None

    active_leaf = leaves[-1] if leaves else None
    session_roots = [root for root in all_roots if not _is_compaction(root)]
    compaction_roots = [root for root in all_roots if _is_compaction(root)]
    origin_root = _origin_session_root(active_leaf) if active_leaf else None
    era_roots = compaction_roots + ([origin_root] if origin_root else session_roots)

    main: set[str] = set()
    for root in era_roots:
        members = _collect_subtree(root, children)
        anchor = next((leaf for leaf in reversed(leaves) if leaf in members), root)
        # Follow the chosen branch down to its tip so the reply below the recorded
        # leaf stays on the main thread, then walk up to the root.
        cursor = _deepest_descendant(anchor, children, depth)
        while cursor in nodes:
            main.add(cursor)
            cursor = parent.get(cursor)

    def branch_head(node_uuid: str) -> str:
        cursor = node_uuid
        while True:
            ancestor = parent.get(cursor)
            if ancestor is None or ancestor in main:
                return cursor
            cursor = ancestor

    head_ids: dict[str, str] = {}
    branch_of: dict[str, str] = {}
    for entry in entries:  # file order → stable, human-friendly numbering
        node_uuid = entry.get("uuid")
        if node_uuid is None or node_uuid not in nodes or node_uuid in main:
            continue
        branch_of[node_uuid] = head_ids.setdefault(
            branch_head(node_uuid), str(len(head_ids) + 1)
        )
    return branch_of


def _parse_default_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse the existing Claude-style JSONL conversation shape."""
    return _parse_default_jsonl_entries(_iter_jsonl_entries(content), flags)


def _is_squashed_pi_user_agent_message(entry: dict) -> bool:
    """Return whether this is a pi-user-agents result squashed into the main context.

    >>> _is_squashed_pi_user_agent_message({"type": "custom_message", "customType": "pi-user-agents", "details": {"mainContextState": "squashed"}})
    True
    """
    details = entry.get("details")
    return (
        entry.get("type") == "custom_message"
        and entry.get("customType") == "pi-user-agents"
        and isinstance(details, dict)
        and details.get("mainContextState") == "squashed"
    )


_PI_TEAM_CUSTOM_TYPE = "pi-simple-team"
_PI_TEAM_TOOL_PREFIX = "team_"
_PI_TEAM_UNPREFIXED_TOOLS = frozenset({"send_main_message", "get_context_window_usage"})


def _is_pi_team_message(entry: dict) -> bool:
    """Return whether a Pi entry is a pi-simple-team teammate message.

    >>> _is_pi_team_message({"type": "custom_message", "customType": "pi-simple-team"})
    True
    """
    return (
        entry.get("type") == "custom_message"
        and entry.get("customType") == _PI_TEAM_CUSTOM_TYPE
    )


def _is_pi_team_leader_message(entry: dict) -> bool:
    """Return whether a teammate message came from the recipient's team leader.

    The leader's briefing and follow-ups are the teammate's prompts.

    >>> _is_pi_team_leader_message({"type": "custom_message", "customType": "pi-simple-team", "details": {"from": "main", "to": "scout"}})
    True
    >>> _is_pi_team_leader_message({"type": "custom_message", "customType": "pi-simple-team", "details": {"from": "scout"}})
    False
    """
    details = entry.get("details")
    return (
        _is_pi_team_message(entry)
        and isinstance(details, dict)
        and details.get("from") == "main"
        and isinstance(details.get("to"), str)
        and bool(details["to"])
    )


def _is_pi_team_tool(native_name: object) -> bool:
    """Return whether a Pi tool is pi-simple-team delegation, which is agent content.

    >>> _is_pi_team_tool("team_send_message"), _is_pi_team_tool("send_main_message"), _is_pi_team_tool("zsh")
    (True, True, False)
    """
    return isinstance(native_name, str) and (
        native_name.startswith(_PI_TEAM_TOOL_PREFIX) or native_name in _PI_TEAM_UNPREFIXED_TOOLS
    )


def _is_hidden_pi_custom_entry(entry: dict) -> bool:
    """Return whether a Pi custom envelope is hidden duplicate plumbing.

    >>> _is_hidden_pi_custom_entry({"type": "custom", "display": False})
    True
    """
    return not (
        _is_squashed_pi_user_agent_message(entry) or _is_pi_team_message(entry)
    ) and (entry.get("display") is False or entry.get("type") == "custom_message")


def _pi_entry_milliseconds(entry: dict) -> int | None:
    """Return when a Pi entry's content was created: its message time, else its entry time.

    >>> _pi_entry_milliseconds({"timestamp": "2026-10-08T09:00:00.000Z", "message": {"timestamp": 5}})
    5
    >>> _pi_entry_milliseconds({"timestamp": "1970-01-01T00:00:01.000Z"})
    1000
    """
    message = entry.get("message")
    if isinstance(message, dict) and isinstance(message.get("timestamp"), int):
        return message["timestamp"]
    return _iso_milliseconds(entry.get("timestamp"))


def _iso_milliseconds(value: object) -> int | None:
    """Return an ISO timestamp as epoch milliseconds, or None when it is not one.

    >>> _iso_milliseconds("1970-01-01T00:00:01.500Z"), _iso_milliseconds(None)
    (1500, None)
    """
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return int(moment.timestamp() * 1000)


def pi_inherited_prefix_end(entries: list[dict]) -> int:
    """Return the index just past a forked Pi session's copied parent history, or 0.

    Every Pi fork path writes the copy before the child's own work, and the copied
    content predates the child's header: native forks copy entries verbatim, and
    pi-user-agents keeps each copied message's original `message.timestamp`.

    >>> header = {"type": "session", "timestamp": "1970-01-01T00:00:10.000Z", "parentSession": "/p.jsonl"}
    >>> pi_inherited_prefix_end([header, {"message": {"timestamp": 1}}, {"message": {"timestamp": 20000}}])
    2
    """
    header = entries[0] if entries else {}
    parent = header.get("parentSession")
    if header.get("type") != "session" or not (isinstance(parent, str) and parent):
        return 0
    born = _iso_milliseconds(header.get("timestamp"))
    if born is None:
        return 0
    end = 0
    for position, entry in enumerate(entries[1:], 1):
        created = _pi_entry_milliseconds(entry)
        if created is not None and created < born:
            end = position + 1
    return end


@dataclass(frozen=True)
class PiLineage:
    """What a Pi session's own file proves about where it came from."""

    parent_session: str | None = None
    forked_from: str | None = None
    forked_at: str | None = None


def _pi_parent_session_id(parent_path: str) -> str | None:
    """Return the id in a parent session file's header, or None when it cannot be read."""
    try:
        with open(parent_path, encoding="utf-8") as parent_file:
            header = orjson.loads(parent_file.readline())
    except (OSError, orjson.JSONDecodeError, UnicodeDecodeError):
        return None
    parent_id = header.get("id") if isinstance(header, dict) else None
    return parent_id if isinstance(parent_id, str) and parent_id else None


def pi_lineage(entries: list[dict]) -> PiLineage:
    """Return a Pi session's parent, fork source, and fork point, as its file proves them.

    A pi-user-agents dispatch record or a team leader's briefing proves a spawner. A
    copied history proves a fork source; an isolated side chat copied none.
    """
    header = entries[0] if entries else {}
    parent_path = header.get("parentSession")
    if header.get("type") != "session" or not (isinstance(parent_path, str) and parent_path):
        return PiLineage()
    parent_id = _pi_parent_session_id(parent_path)
    born = _iso_milliseconds(header.get("timestamp"))
    dispatch = next(
        (
            entry for entry in entries[1:2]
            if entry.get("type") == "custom"
            and entry.get("customType") == "pi-user-agents-dispatch"
            and born is not None
            and (created := _iso_milliseconds(entry.get("timestamp"))) is not None
            and created >= born
        ),
        None,
    )
    end = pi_inherited_prefix_end(entries)
    spawned = dispatch is not None or any(map(_is_pi_team_leader_message, entries[end:]))
    isolated = dispatch is not None and (dispatch.get("data") or {}).get("isolate") is True
    forked_at = _pi_entry_milliseconds(entries[end - 1]) if end else None
    return PiLineage(
        parent_session=parent_id if spawned else None,
        forked_from=None if isolated else parent_id,
        forked_at=None if forked_at is None else datetime.fromtimestamp(forked_at / 1000, UTC).isoformat(),
    )


def pi_own_entries(entries: list[dict]) -> list[dict]:
    """Return a Pi session's header and its own entries, without a fork's copied prefix.

    >>> header = {"type": "session", "timestamp": "1970-01-01T00:00:10.000Z", "parentSession": "/p.jsonl"}
    >>> pi_own_entries([header, {"message": {"timestamp": 1}}, {"id": "own", "message": {"timestamp": 20000}}])[1]["id"]
    'own'
    """
    return [*entries[:1], *entries[max(pi_inherited_prefix_end(entries), 1):]]


@functools.lru_cache(maxsize=1)
def _pi_lineage_of_file(session_file: Path) -> PiLineage:
    return pi_lineage(_iter_jsonl_entries(session_file.read_text(encoding="utf-8")))


_PI_TEAM_CREATION_RESULT_KEYS = {"team_spawn": "teammates", "team_add_teammates": "addedTeammates"}
_PI_PRINTED_OBJECT_START = re.compile(r"(?m)^[ \t]*(\{)")


def _pi_printed_spawn_members(text: str, team_names: set[str]) -> list[dict]:
    """Read printed spawn receipts, not arbitrary session paths printed by the same script.

    >>> _pi_printed_spawn_members('{"teamName":"crew","teamId":"parent-crew","teammates":[{"sessionFile":"/c.jsonl"}]}', {"crew"})
    [{'sessionFile': '/c.jsonl'}]
    """
    members: list[dict] = []
    decoder = json.JSONDecoder()
    for opening in _PI_PRINTED_OBJECT_START.finditer(text):
        try:
            result, _ = decoder.raw_decode(text, opening.start(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(result, dict) or result.get("teamName") not in team_names or not result.get("teamId"):
            continue
        teammates = result.get("teammates")
        if isinstance(teammates, list):
            members.extend(member for member in teammates if isinstance(member, dict))
    return members


def _pi_created_teammate_files(entries: list[dict]) -> list[str]:
    """Return the session files of teammates these entries' team receipts created.

    A direct team_spawn or team_add_teammates result lists them in `details`. A
    codemode script that ran one keeps only what it printed, so its text is read.

    >>> receipt = {"message": {"role": "toolResult", "toolName": "team_spawn", "details": {"teammates": [{"sessionFile": "/a.jsonl"}]}}}
    >>> _pi_created_teammate_files([receipt])
    ['/a.jsonl']
    """
    files: list[str] = []
    for entry in entries:
        message = entry.get("message")
        if not isinstance(message, dict) or message.get("role") != "toolResult" or message.get("isError"):
            continue
        tool_name = message.get("toolName")
        details = message.get("details")
        if tool_name in _PI_TEAM_CREATION_RESULT_KEYS and isinstance(details, dict):
            members = details.get(_PI_TEAM_CREATION_RESULT_KEYS[tool_name])
            files += [
                member["sessionFile"]
                for member in (members if isinstance(members, list) else [])
                if isinstance(member, dict) and isinstance(member.get("sessionFile"), str)
            ]
        nested = message.get("nestedCalls")
        nested_calls = nested.get("calls") if isinstance(nested, dict) else None
        spawned_teams = {
            call["arguments"]["teamName"]
            for call in (nested_calls if isinstance(nested_calls, list) else [])
            if isinstance(call, dict) and call.get("name") == "team_spawn" and call.get("status") == "ok"
            and isinstance(call.get("arguments"), dict) and isinstance(call["arguments"].get("teamName"), str)
        }
        if tool_name == "codemode" and spawned_teams:
            text = "\n".join(_extract_text_blocks(message.get("content", [])))
            files += [
                member["sessionFile"] for member in _pi_printed_spawn_members(text, spawned_teams)
                if isinstance(member.get("sessionFile"), str)
            ]
    return files


@functools.cache
def _pi_children_by_parent(directory: Path) -> dict[Path, list[Path]]:
    """Index immutable parent headers once per CLI invocation, without retaining transcript bodies."""
    children: dict[Path, list[Path]] = defaultdict(list)
    for sibling in sorted(directory.glob("*.jsonl")):
        with sibling.open("rb") as stream:
            try:
                header = orjson.loads(stream.readline())
            except orjson.JSONDecodeError:
                continue
        parent = header.get("parentSession") if isinstance(header, dict) else None
        if isinstance(parent, str) and parent:
            children[Path(parent).resolve()].append(sibling.resolve())
    return dict(children)


def _pi_spawned_children_in_directory(session_file: Path) -> list[str]:
    """Return linked children that prove delegation, rather than ordinary context forks."""
    return [
        str(child) for child in _pi_children_by_parent(session_file.parent).get(session_file, [])
        if child != session_file and pi_lineage(_iter_jsonl_entries(child.read_text(encoding="utf-8"))).parent_session
    ]


def find_pi_delegated_children(session_file: Path, entries: list[dict] | None = None) -> list[Path]:
    """Return the sessions this Pi session delegated to, by its agent or its user.

    Copied receipts in a fork's inherited prefix belong to the parent, not to it.
    """
    session_file = session_file.resolve()
    if entries is None:
        entries = _iter_jsonl_entries(session_file.read_text(encoding="utf-8"))
    own_entries = entries[pi_inherited_prefix_end(entries):]
    candidates = [*_pi_created_teammate_files(own_entries), *_pi_spawned_children_in_directory(session_file)]
    return [Path(child) for child in dict.fromkeys(candidates) if Path(child).is_file()]


def read_pi_subagent_metadata(transcript: Path) -> SubagentMetadata:
    """Read a delegated Pi child's identity: a teammate's name, or a user side chat."""
    entries = _iter_jsonl_entries(transcript.read_text(encoding="utf-8"))
    own_entries = entries[pi_inherited_prefix_end(entries):]
    briefing = next(filter(_is_pi_team_leader_message, own_entries), None)
    header = entries[0] if entries else {}
    return SubagentMetadata(
        agent_id=header.get("id") if isinstance(header.get("id"), str) else None,
        name=briefing["details"]["to"] if briefing else None,
        subagent_type="teammate" if briefing else "user-agent",
    )


def _parse_pi_jsonl_entries(
    entries: list[dict], flags: ConversationFlags
) -> list[Message]:
    """Parse PI JSONL entries into the shared Message model."""
    messages = []
    index = 1

    for entry in entries:
        entry_type = entry.get("type")
        if entry_type in {"custom", "custom_message"} and _is_hidden_pi_custom_entry(
            entry
        ):
            continue

        if entry_type == "message":
            parsed_messages = _parse_pi_message_entry(entry, index, flags)
        elif entry_type == "compaction":
            parsed_messages = [_parse_pi_compaction_entry(entry, index, flags)]
        elif entry_type == "custom":
            parsed_messages = [_parse_pi_custom_entry(entry, index, flags)]
        elif entry_type == "custom_message":
            parsed_messages = [_parse_pi_custom_message_entry(entry, index, flags)]
        else:
            parsed_messages = []

        for msg in parsed_messages:
            if msg and msg.has_content():
                msg.index = index
                messages.append(msg)
                index += 1

    return messages


def _pi_native_entry_id(entry: dict) -> str | None:
    """Return a Pi entry's stable native id when it has one.

    >>> _pi_native_entry_id({"id": "entry-1"})
    'entry-1'
    >>> _pi_native_entry_id({"id": 1}) is None
    True
    """
    entry_id = entry.get("id")
    return entry_id if isinstance(entry_id, str) and entry_id else None


def _parse_pi_custom_entry(
    entry: dict,
    index: int,
    flags: ConversationFlags,
) -> Message | None:
    """Normalize a Pi custom entry through the shared message model."""
    custom_type = entry.get("customType")
    if not isinstance(custom_type, str):
        return None
    if not flags.show_custom:
        return None

    data = json.dumps(entry.get("data"), indent=2, ensure_ascii=False)
    return Message(
        role="custom",
        index=index,
        text=f"```json\n{data}\n```",
        native_entry_id=_pi_native_entry_id(entry),
        timestamp=entry.get("timestamp"),
        wrapper_type=ContentBlockType.CUSTOM,
        custom_type=custom_type,
    )


def _parse_pi_custom_message_entry(
    entry: dict,
    index: int,
    flags: ConversationFlags,
) -> Message | None:
    """Normalize a squashed Pi user-agent result, a leader's instruction, or, under --agents, a teammate message."""
    if _is_squashed_pi_user_agent_message(entry):
        return _parse_pi_squashed_user_agent_message(entry, flags)
    if _is_pi_team_leader_message(entry):
        return _parse_pi_team_leader_message(entry, flags)
    if flags.show_agents:
        return _parse_pi_team_message(entry)
    return None


def _parse_pi_squashed_user_agent_message(
    entry: dict, flags: ConversationFlags
) -> Message | None:
    """Show a squashed pi-user-agents result as the plain user message the main agent read."""
    if not flags.show_user_messages:
        return None
    return Message(
        role="user",
        text=entry.get("content") or "",
        native_entry_id=_pi_native_entry_id(entry),
        timestamp=entry.get("timestamp"),
    )


def _parse_pi_team_leader_message(entry: dict, flags: ConversationFlags) -> Message | None:
    """Show a team leader's message to a teammate as the user message the teammate read."""
    if not flags.show_user_messages:
        return None
    return Message(
        role="user",
        text=entry["details"].get("message") or "",
        native_entry_id=_pi_native_entry_id(entry),
        timestamp=entry.get("timestamp"),
    )


def _parse_pi_team_message(entry: dict) -> Message | None:
    """Represent one pi-simple-team teammate message as an agent named after its sender."""
    details = entry.get("details")
    if not isinstance(details, dict):
        return None
    sender = details.get("from")
    return Message(
        role="agent",
        agent_id=sender,
        name=sender,
        native_entry_id=_pi_native_entry_id(entry),
        timestamp=entry.get("timestamp"),
        text=details.get("message") or "",
        wrapper_type=ContentBlockType.AGENT,
        custom_type=_PI_TEAM_CUSTOM_TYPE,
    )


def _parse_pi_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse PI JSONL sessions into the shared Message model."""
    return _parse_pi_jsonl_entries(_iter_jsonl_entries(content), flags)


_CODEX_AGENT_TOOL_NAMESPACE = "collaboration"
_CODEX_ENCRYPTED_PREFIX = "gAAAAA"


@dataclass(frozen=True)
class _CodexThread:
    """Where this rollout's own records start, and which agent leads it."""

    first_own_ordinal: int
    leader_path: str | None


def _codex_thread(entries: list[dict]) -> _CodexThread:
    """Read the thread's history boundary and leader from its first session_meta.

    >>> _codex_thread([{"type": "session_meta", "payload": {"subagent_history_start_ordinal": 4, "agent_path": "/root/review"}}])
    _CodexThread(first_own_ordinal=4, leader_path='/root')
    >>> _codex_thread([{"type": "session_meta", "payload": {"id": "root"}}])
    _CodexThread(first_own_ordinal=0, leader_path=None)
    """
    header = entries[0].get("payload", {}) if entries and entries[0].get("type") == "session_meta" else {}
    agent_path = header.get("agent_path")
    return _CodexThread(
        first_own_ordinal=header.get("subagent_history_start_ordinal") or 0,
        leader_path=agent_path.rpartition("/")[0] if isinstance(agent_path, str) else None,
    )


def _codex_agent_message_text(payload: dict) -> str:
    """Render an inter-agent message: its plaintext payload, else its routing header.

    The header is shown as written, so search can find exactly what parse shows.

    >>> _codex_agent_message_text({"content": [{"type": "input_text", "text": "Message Type: NEW_TASK\\nSender: /root\\nPayload:\\n"}, {"type": "encrypted_content"}]})
    'Message Type: NEW_TASK\\nSender: /root'
    >>> _codex_agent_message_text({"content": [{"type": "input_text", "text": "Message Type: MESSAGE\\nPayload:\\nhello"}]})
    'hello'
    """
    text = "".join(
        block.get("text", "") for block in payload.get("content", []) if block.get("type") == "input_text"
    )
    header, _, plaintext = text.partition("Payload:\n")
    return plaintext if plaintext.strip() else header.strip()


def _codex_own_entries(entries: list[dict]) -> list[dict]:
    """Drop the parent records a forked subagent copied, keeping its session header.

    >>> [entry["ordinal"] for entry in _codex_own_entries([{"ordinal": 0, "type": "session_meta", "payload": {"subagent_history_start_ordinal": 2}}, {"ordinal": 1}, {"ordinal": 2}])]
    [0, 2]
    """
    first_own_ordinal = _codex_thread(entries).first_own_ordinal
    return entries[:1] + [entry for entry in entries[1:] if entry.get("ordinal", first_own_ordinal) >= first_own_ordinal]


def _redact_codex_ciphertext(tool_input: dict[str, object]) -> dict[str, object]:
    """Replace encrypted argument values, which carry no readable content.

    >>> _redact_codex_ciphertext({"target": "/root", "message": "gAAAAABq"})
    {'target': '/root', 'message': '[encrypted]'}
    """
    return {
        key: "[encrypted]" if isinstance(value, str) and value.startswith(_CODEX_ENCRYPTED_PREFIX) else value
        for key, value in tool_input.items()
    }


def _parse_codex_jsonl_entries(
    entries: list[dict], flags: ConversationFlags
) -> list[Message]:
    """Parse Codex JSONL entries into the shared Message model.

    Messages from this thread's leader are user instructions. Other delivered
    messages retain their sender under --agents, even without a child transcript.
    Collaboration controls are agent content.
    """
    messages = []
    index = 1
    current_assistant: Message | None = None
    thread = _codex_thread(entries)
    agent_control_call_ids: set[str] = set()

    def append_message(message: Message) -> None:
        nonlocal index
        flush_assistant()
        message.index = index
        messages.append(message)
        index += 1

    def flush_assistant() -> None:
        nonlocal current_assistant, index
        if current_assistant and current_assistant.has_content():
            current_assistant.index = index
            messages.append(current_assistant)
            index += 1
        current_assistant = None

    def ensure_assistant(timestamp: str | None) -> Message:
        nonlocal current_assistant
        if current_assistant is None:
            current_assistant = Message(role="assistant", timestamp=timestamp)
        elif current_assistant.timestamp is None:
            current_assistant.timestamp = timestamp
        return current_assistant

    for entry in entries:
        entry_type = entry.get("type")

        if entry_type != "response_item":
            continue

        payload = entry.get("payload", {})
        payload_type = payload.get("type")
        timestamp = entry.get("timestamp")

        if payload_type == "agent_message":
            sender = payload.get("author")
            from_leader = sender is not None and sender == thread.leader_path
            if from_leader and flags.show_user_messages:
                append_message(Message(role="user", text=_codex_agent_message_text(payload), timestamp=timestamp))
            if not from_leader and flags.show_agents:
                append_message(Message(
                    role="agent", agent_id=sender, name=sender,
                    wrapper_type=ContentBlockType.AGENT,
                    text=_codex_agent_message_text(payload), timestamp=timestamp,
                ))
            continue

        if payload_type == "message":
            role = payload.get("role")
            if role == "user":
                text_blocks = _extract_codex_text_blocks(payload.get("content"))
                visible_blocks = _filter_hidden_user_text_blocks(
                    [text for text in text_blocks if not _is_codex_preamble_text(text)]
                )
                if not flags.show_user_messages or not visible_blocks:
                    continue

                flush_assistant()
                messages.append(
                    Message(
                        role="user",
                        index=index,
                        text="\n\n".join(visible_blocks),
                        timestamp=timestamp,
                    )
                )
                index += 1
                continue

            if role == "assistant":
                if not flags.show_assistant_messages:
                    continue

                text_blocks = _extract_codex_text_blocks(payload.get("content"))
                visible_blocks = [text for text in text_blocks if text.strip()]
                if not visible_blocks:
                    continue

                assistant = ensure_assistant(timestamp)
                assistant.text = _append_codex_block(
                    assistant.text,
                    "\n\n".join(visible_blocks),
                )
                continue

            continue

        if payload_type == "reasoning" and flags.show_thinking:
            thinking_text = _extract_codex_reasoning_text(payload)
            if not thinking_text:
                continue

            assistant = ensure_assistant(timestamp)
            assistant.thinking = _append_codex_block(assistant.thinking, thinking_text)
            continue

        if payload_type == "function_call":
            if payload.get("namespace") == _CODEX_AGENT_TOOL_NAMESPACE:
                agent_control_call_ids.add(payload.get("call_id"))
                if flags.show_agents:
                    tool_name = _normalize_codex_tool_name(payload.get("name"))
                    append_message(Message(
                        role="assistant",
                        timestamp=timestamp,
                        tools_always_visible=True,
                        tools=[{
                            "type": "tool_use",
                            "id": payload.get("call_id"),
                            "name": tool_name,
                            "input": _redact_codex_ciphertext(
                                _normalize_codex_tool_input(tool_name, payload.get("arguments"))
                            ),
                        }],
                    ))
                continue
            if flags.show_tools:
                assistant = ensure_assistant(timestamp)
                tool_name = _normalize_codex_tool_name(payload.get("name"))
                assistant.tools.append({
                    "type": "tool_use",
                    "id": payload.get("call_id"),
                    "name": tool_name,
                    "input": _normalize_codex_tool_input(
                        tool_name, payload.get("arguments")
                    ),
                })
            continue

        if payload_type == "function_call_output":
            if payload.get("call_id") in agent_control_call_ids:
                if flags.show_agents:
                    append_message(Message(
                        role="assistant",
                        timestamp=timestamp,
                        tools_always_visible=True,
                        tools=[{
                            "type": "tool_result",
                            "tool_use_id": payload.get("call_id"),
                            "content": _parse_codex_tool_output(payload.get("output", "")),
                            "is_error": False,
                        }],
                    ))
                continue
            if flags.show_tools:
                assistant = ensure_assistant(timestamp)
                assistant.tools.append({
                    "type": "tool_result",
                    "tool_use_id": payload.get("call_id"),
                    "content": _parse_codex_tool_output(payload.get("output", "")),
                    "is_error": False,
                })
            continue

        if payload_type == "custom_tool_call" and flags.show_tools:
            assistant = ensure_assistant(timestamp)
            tool_name, tool_input = _normalize_codex_custom_tool_call(
                payload.get("name"), payload.get("input")
            )
            assistant.tools.append({
                "type": "tool_use",
                "id": payload.get("call_id"),
                "name": tool_name,
                "input": tool_input,
            })
            continue

        if payload_type == "custom_tool_call_output" and flags.show_tools:
            assistant = ensure_assistant(timestamp)
            assistant.tools.append({
                "type": "tool_result",
                "tool_use_id": payload.get("call_id"),
                "content": _parse_codex_tool_output(payload.get("output", "")),
                "is_error": False,
            })
            continue

    flush_assistant()
    return messages


def _parse_codex_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse Codex JSONL sessions into the shared Message model."""
    return _parse_codex_jsonl_entries(_iter_jsonl_entries(content), flags)


def _is_codex_session_header(first_entry: dict) -> bool:
    """Return whether a first JSONL entry has Codex's native session header.

    >>> _is_codex_session_header({"type": "session_meta"})
    True
    """
    return first_entry.get("type") == "session_meta"


def _is_pi_session_header(first_entry: dict) -> bool:
    """Return whether a first JSONL entry has Pi's native session header.

    >>> _is_pi_session_header({"type": "session", "version": 3})
    True
    >>> _is_pi_session_header({"type": "session", "version": "3"})
    False
    """
    return (
        first_entry.get("type") == "session"
        and type(first_entry.get("version")) is int
    )


def _extract_pi_session_id(session_file: Path) -> str | None:
    """Extract the PI session id from the file's session entry or filename."""
    try:
        with open(session_file, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") == "session":
                    session_id = entry.get("id")
                    if isinstance(session_id, str) and session_id:
                        return session_id
                    break
                break
    except OSError:
        pass

    stem = session_file.stem
    prefix, separator, suffix = stem.rpartition("_")
    if prefix and separator and suffix:
        return suffix
    return None


def _read_codex_session_meta(session_file: Path) -> dict:
    """Return the payload of the file's first entry when it is a Codex session_meta."""
    try:
        with open(session_file, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "session_meta":
                    return {}
                return entry.get("payload", {})
    except OSError:
        pass
    return {}


def _extract_codex_session_meta_field(
    session_file: Path, field_name: str
) -> str | None:
    """Extract a string field from the Codex session_meta payload."""
    value = _read_codex_session_meta(session_file).get(field_name)
    return value if isinstance(value, str) and value else None


def _codex_thread_spawn(session_meta: dict) -> dict:
    """Return a subagent's spawn record, the one place every current subagent header names its role."""
    source = session_meta.get("source")
    subagent = source.get("subagent") if isinstance(source, dict) else None
    return subagent.get("thread_spawn", {}) if isinstance(subagent, dict) else {}


def _extract_codex_session_id(session_file: Path) -> str | None:
    """Extract the Codex session id from the file's session_meta entry."""
    return _extract_codex_session_meta_field(session_file, "id")


def _extract_codex_forked_from_id(session_file: Path) -> str | None:
    """Extract the Codex fork parent id from the file's session_meta entry."""
    return _extract_codex_session_meta_field(session_file, "forked_from_id")


def _extract_codex_parent_thread_id(session_file: Path) -> str | None:
    """Extract the spawner proved by this Codex child's header."""
    return delegated_parent(_read_codex_session_meta(session_file))


def _extract_codex_forked_at(session_file: Path) -> str | None:
    """Return the timestamp of the last record a forked subagent copied from its parent."""
    first_own_ordinal = _read_codex_session_meta(session_file).get("subagent_history_start_ordinal")
    if not first_own_ordinal:
        return None
    forked_at = None
    with open(session_file, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("ordinal", first_own_ordinal) >= first_own_ordinal:
                break
            forked_at = entry.get("timestamp") or forked_at
    return forked_at


# NOTE: This centralizes a cross-adapter metadata/display concern that should probably be adapter-owned metadata semantics, not command-owned special casing.
# NOTE: Treat the current approach as a temporary smell marker, not as the desired long-term ownership boundary.
def get_display_session_id(session_file: Path) -> str:
    """Return the user-facing session id for a session file."""
    adapter = _select_jsonl_session_adapter(session_file)
    if adapter.name == "claude":
        return session_file.stem
    return adapter.extract_session_id(session_file) or session_file.stem


def get_native_session_id(session_file: Path) -> str:
    """Return the canonical in-band session id for a session file."""
    adapter = _select_jsonl_session_adapter(session_file)
    return adapter.extract_session_id(session_file) or session_file.stem


def _find_pi_session_matches(identifier: str) -> list[tuple[Path, str]]:
    """Find PI session files that match a PI session id."""
    if len(identifier.split()) != 1:
        return []

    sessions_dir = Path.home() / ".pi" / "agent" / "sessions"
    if not sessions_dir.exists():
        return []

    matches: list[tuple[Path, str]] = []
    for session_file in sorted(sessions_dir.rglob("*.jsonl")):
        if _extract_pi_session_id(session_file) != identifier:
            continue
        matches.append((session_file, f"PI session {identifier}"))
    return matches


def _find_codex_session_matches(identifier: str) -> list[tuple[Path, str]]:
    """Find Codex session files that match a Codex session id."""
    if len(identifier.split()) != 1:
        return []

    sessions_dir = Path.home() / ".codex" / "sessions"
    if not sessions_dir.exists():
        return []

    matches: list[tuple[Path, str]] = []
    for session_file in sorted(sessions_dir.rglob("*.jsonl")):
        if _extract_codex_session_id(session_file) != identifier:
            continue
        matches.append((session_file, f"Codex session {identifier}"))
    return matches


@dataclass
class _CodexDelegationIndex:
    children: dict[str, list[Path]]
    sessions: dict[str, tuple[Path, str | None]]


@cache
def _codex_delegation_index(home: Path) -> _CodexDelegationIndex:
    """Read the Codex header graph once for this CLI process; retain no message bodies."""
    children: defaultdict[str, list[Path]] = defaultdict(list)
    sessions: dict[str, tuple[Path, str | None]] = {}
    for path in sorted((home / ".codex" / "sessions").rglob("*.jsonl")):
        session_meta = _read_codex_session_meta(path)
        child_id = session_meta.get("id")
        if not child_id:
            continue
        sessions[child_id] = (path, session_meta.get("forked_from_id"))
        parent = delegated_parent(session_meta)
        if parent:
            children[parent].append(path)
    return _CodexDelegationIndex(dict(children), sessions)


def find_codex_subagent_transcripts(
    session_file: Path, session_id: str, entries: list[dict] | None = None,
) -> list[Path]:
    """Find direct delegated children using header edges and verified CLI receipts."""
    index = _codex_delegation_index(Path.home())
    if entries is None:
        entries = _codex_own_entries(decode_jsonl_entries(session_file.read_text(encoding="utf-8")))
    proven = list(index.children.get(session_id, []))
    for child_id, source in verified_cli_forks(entries, session_id):
        candidate = index.sessions.get(child_id)
        if candidate and candidate[1] == source:
            proven.append(candidate[0])
    return proven


def extract_codex_subagent_metadata(transcript: Path) -> SubagentMetadata:
    """Read a Codex subagent's identity from its rollout's session_meta."""
    session_meta = _read_codex_session_meta(transcript)
    thread_spawn = _codex_thread_spawn(session_meta)
    return SubagentMetadata(
        agent_id=session_meta.get("id"),
        name=thread_spawn.get("agent_nickname"),
        subagent_type=thread_spawn.get("agent_role"),
    )


NativeInventoryRow = tuple[Path, Provider | None, float]


def _discover_session_file_rows(
    *, include_sidechains: bool = True
) -> list[NativeInventoryRow]:
    """Return the native ordered inventory with provider and stat projections."""
    rows = [
        (Path(os.fsdecode(raw_path)), provider, mtime)
        for raw_path, provider, mtime in discover_session_files(
            os.fsencode(Path.home()), include_sidechains
        )
    ]
    if include_sidechains:
        return rows

    return [
        row
        for row in rows
        if row[1] is not None
        or not _select_jsonl_session_adapter(row[0]).is_sidechain_path(row[0])
    ]


def find_all_supported_session_files(*, include_sidechains: bool = True) -> list[Path]:
    """List all known session files across supported JSONL adapters."""
    return [
        path
        for path, _provider, _mtime in _discover_session_file_rows(
            include_sidechains=include_sidechains
        )
    ]


def _jsonl_timestamp_now() -> str:
    """Return a UTC timestamp string in the JSONL shape used by native sessions."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _require_last_entry_id(entries: list[dict], provider_name: str) -> str:
    """Return the last entry id for providers whose entries form an in-band parent chain."""
    if not entries:
        raise ValueError(f"Cannot rename an empty {provider_name} session.")

    last_entry_id = entries[-1].get("id")
    if isinstance(last_entry_id, str) and last_entry_id:
        return last_entry_id

    raise ValueError(
        f"{provider_name.capitalize()} rename requires the last session entry to have an id."
    )


def _build_claude_name_entries(
    _entries: list[dict],
    session_id: str,
    new_name: str,
) -> list[dict]:
    """Build the two Claude-native rename entries: custom-title and agent-name."""
    return [
        {
            "type": "custom-title",
            "customTitle": new_name,
            "sessionId": session_id,
        },
        {
            "type": "agent-name",
            "agentName": new_name,
            "sessionId": session_id,
        },
    ]


def _build_pi_name_entries(
    entries: list[dict],
    _session_id: str,
    new_name: str,
) -> list[dict]:
    """Build one PI-native session_info rename entry."""
    return [
        {
            "type": "session_info",
            "id": uuid.uuid4().hex[:8],
            "parentId": _require_last_entry_id(entries, "pi"),
            "timestamp": _jsonl_timestamp_now(),
            "name": new_name,
        }
    ]


def _build_codex_name_entries(
    _entries: list[dict],
    session_id: str,
    new_name: str,
) -> list[dict]:
    """Build one Codex-native thread-name update event."""
    return [
        {
            "timestamp": _jsonl_timestamp_now(),
            "type": "event_msg",
            "payload": {
                "type": "thread_name_updated",
                "thread_id": session_id,
                "thread_name": new_name,
            },
        }
    ]


JSONL_SESSION_ADAPTERS = [
    JsonlSessionAdapter(
        name="codex",
        parse_messages=_parse_codex_jsonl,
        build_name_entries=_build_codex_name_entries,
        find_session_matches=_find_codex_session_matches,
        extract_session_id=_extract_codex_session_id,
        extract_parent_session=_extract_codex_parent_thread_id,
        extract_forked_from=_extract_codex_forked_from_id,
        extract_forked_at=_extract_codex_forked_at,
        own_entries=_codex_own_entries,
        matches_first_entry=_is_codex_session_header,
    ),
    JsonlSessionAdapter(
        name="pi",
        parse_messages=_parse_pi_jsonl,
        own_entries=pi_own_entries,
        build_name_entries=_build_pi_name_entries,
        find_session_matches=_find_pi_session_matches,
        extract_session_id=_extract_pi_session_id,
        extract_parent_session=lambda path: _pi_lineage_of_file(path).parent_session,
        extract_forked_from=lambda path: _pi_lineage_of_file(path).forked_from,
        extract_forked_at=lambda path: _pi_lineage_of_file(path).forked_at,
        matches_first_entry=_is_pi_session_header,
    ),
    JsonlSessionAdapter(
        name="claude",
        parse_messages=_parse_default_jsonl,
        build_name_entries=_build_claude_name_entries,
        is_sidechain_path=lambda path: path.name.startswith("agent-"),
        extract_session_id=lambda path: path.stem,
        extract_parent_session=lambda path: _read_claude_lineage(path).parent_session,
        extract_forked_from=lambda path: _read_claude_lineage(path).forked_from,
        extract_forked_at=lambda path: _read_claude_lineage(path).forked_at,
        own_entries=_claude_own_entries,
    ),
]


def _read_first_jsonl_entry(source_path: Path | None) -> dict | None:
    """Read the first non-empty JSON object from a session path."""
    if source_path is None:
        return None
    try:
        with open(source_path, "rb") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = orjson.loads(line)
                return entry if isinstance(entry, dict) else None
    except (OSError, orjson.JSONDecodeError):
        return None
    return None


def _select_jsonl_session_adapter(
    source_path: Path | None,
    first_entry: dict | None = None,
) -> JsonlSessionAdapter:
    """Select a JSONL adapter by native path, then by first-entry signature."""
    native_provider: Provider | None = (
        classify_native_session_path(str(source_path), str(Path.home()))
        if source_path is not None
        else None
    )
    if native_provider is not None:
        return next(
            adapter
            for adapter in JSONL_SESSION_ADAPTERS
            if adapter.name == native_provider
        )

    first_entry = first_entry or _read_first_jsonl_entry(source_path)
    content_match = next(
        (
            adapter
            for adapter in JSONL_SESSION_ADAPTERS
            if adapter.matches_first_entry is not None
            and first_entry is not None
            and adapter.matches_first_entry(first_entry)
        ),
        None,
    )
    if content_match is not None:
        return content_match

    raise ValueError(
        "Cannot determine JSONL session provider from its path or first entry."
    )


def get_jsonl_session_adapter(source_path: Path | None) -> JsonlSessionAdapter:
    """Return the adapter that owns the given session path."""
    return _select_jsonl_session_adapter(source_path)


def is_sidechain_session_file(session_file: Path) -> bool:
    """Return True when a session file belongs to an adapter-specific sidechain."""
    return _select_jsonl_session_adapter(session_file).is_sidechain_path(session_file)


def parse_jsonl(
    content: str,
    flags: ConversationFlags,
    source_path: Path | None = None,
) -> list[Message]:
    """Parse a JSONL conversation via the matching session adapter."""
    return parse_jsonl_entries(
        _iter_jsonl_entries(content), flags, source_path=source_path
    )


def parse_jsonl_entries(
    entries: list[dict],
    flags: ConversationFlags,
    source_path: Path | None = None,
) -> list[Message]:
    """Parse already-decoded JSONL entries via the matching session adapter."""
    first_entry = entries[0] if entries else None
    adapter = _select_jsonl_session_adapter(source_path, first_entry)
    if adapter.name == "pi":
        return _parse_pi_jsonl_entries(entries, flags)
    if adapter.name == "codex":
        return _parse_codex_jsonl_entries(entries, flags)
    return _parse_default_jsonl_entries(entries, flags)


def resolve_session_identifier_via_adapters(
    identifier: str,
) -> tuple[Path | None, list[tuple[Path, str]]]:
    """Resolve a non-Claude session identifier by trying adapter matchers in order."""
    for adapter in JSONL_SESSION_ADAPTERS:
        if adapter.find_session_matches is None:
            continue

        matches = adapter.find_session_matches(identifier)
        if len(matches) == 1:
            return matches[0][0], []
        if len(matches) > 1:
            return None, matches

    return None, []


def _meta_source_tool_result(
    is_meta: bool,
    source_tool_use_id: str | None,
    text_blocks: list[str],
    flags: ConversationFlags,
) -> dict[str, str] | None:
    """Classify linked meta text as a tool output.

    >>> _meta_source_tool_result(True, "call", ["body"], ConversationFlags(show_tools=True))
    {'type': 'tool_result', 'tool_use_id': 'call', 'content': 'body'}
    """
    if not (flags.show_tools and is_meta and source_tool_use_id and text_blocks):
        return None
    return {
        "type": "tool_result",
        "tool_use_id": source_tool_use_id,
        "content": "\n\n".join(text_blocks),
    }


def _parse_user_entry(
    entry: dict, index: int, flags: ConversationFlags, agent_tool_ids: frozenset[str] = frozenset(),
    origins: AgentOrigins | None = None,
) -> list[Message]:
    """Separate human text, tool activity, and relayed agent messages in a user entry.

    Results of agent-messaging calls are agent content: shown by --agents regardless
    of tool filters, and never by --tools alone.
    """
    message_data = entry.get("message", {})
    if message_data.get("role") != "user":
        return []

    content_data = message_data.get("content")
    peer_blocks = (
        _split_claude_peer_blocks(content_data, in_agent_transcript=bool(entry.get("agentId")))
        if isinstance(content_data, str)
        else []
    )
    if peer_blocks:
        return [
            message
            for sender, body in peer_blocks
            if (message := _claude_peer_message(entry, sender, body, flags))
        ]
    source_tool_use_id = (
        entry.get("sourceToolUseID")
        or entry.get("sourceToolUseId")
        or entry.get("sourceToolUserId")
    )
    msg = Message(
        role="user",
        index=index,
        timestamp=entry.get("timestamp"),
        is_meta=entry.get("isMeta") is True,
        source_tool_user_id=shorten_tool_use_id(source_tool_use_id),
    )

    if isinstance(content_data, str) and _is_task_notification(content_data):
        return notification_messages(entry, origins) if origins is not None else []

    tool_message = Message(role="assistant", timestamp=msg.timestamp)
    agent_tool_message = Message(
        role="assistant", timestamp=msg.timestamp, tools_always_visible=True
    )
    show_user_text = flags.show_user_messages and (not msg.is_meta or flags.show_tools)

    if isinstance(content_data, str):
        if output := _meta_source_tool_result(msg.is_meta, source_tool_use_id, [content_data], flags):
            tool_message.tools.append(output)
        elif show_user_text:
            msg.text, msg.wrapper_type = _parse_user_string_content(
                _strip_claude_fork_boilerplate(content_data)
            )
    elif isinstance(content_data, list):
        text_blocks = [
            text
            for block in _filter_hidden_user_text_blocks(_extract_text_blocks(content_data))
            if (text := _strip_claude_fork_boilerplate(block))
        ]
        for item in content_data:
            if not (isinstance(item, dict) and item.get("type") == "tool_result"):
                continue
            if item.get("tool_use_id") in agent_tool_ids:
                if flags.show_agents:
                    agent_tool_message.tools.append(item)
            elif flags.show_tools:
                tool_message.tools.append(item)

        if output := _meta_source_tool_result(msg.is_meta, source_tool_use_id, text_blocks, flags):
            tool_message.tools.append(output)
        elif text_blocks and show_user_text:
            msg.text = "\n\n".join(text_blocks)

    # A post-compaction summary is injected as a user turn but is its own block:
    # shown by default like a recap, labeled Compaction rather than User.
    if entry.get("isCompactSummary") is True:
        msg.wrapper_type = ContentBlockType.COMPACTION

    return [msg, tool_message, agent_tool_message]


def _parse_assistant_entry(
    entry: dict, index: int, flags: ConversationFlags
) -> list[Message]:
    """Parse an assistant-type JSONL entry.

    Agent-messaging calls split into their own message, shown by --agents regardless
    of tool filters, and never by --tools alone.
    """
    message_data = entry.get("message", {})
    if message_data.get("role") != "assistant":
        return []

    agent_id = entry.get("agentId")
    if agent_id and not flags.show_agents:
        return []

    show_message_text = flags.show_agents if agent_id else flags.show_assistant_messages

    content_data = message_data.get("content", [])
    if not isinstance(content_data, list):
        return []

    msg = Message(
        role="assistant",
        index=index,
        agent_id=agent_id,
        timestamp=entry.get("timestamp"),
    )
    agent_tool_message = Message(
        role="assistant",
        agent_id=agent_id,
        timestamp=msg.timestamp,
        tools_always_visible=True,
    )
    text_blocks = []

    for item in content_data:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")

        if item_type == "text":
            if text := item.get("text", "").strip():
                text_blocks.append(text)
        elif item_type == "thinking" and flags.show_thinking:
            msg.thinking = item.get("thinking", "").strip()
        elif item_type == "tool_use":
            tool_name = item.get("name")
            if tool_name == "ExitPlanMode":
                if show_message_text and (
                    plan_content := item.get("input", {}).get("plan", "")
                ):
                    msg.plan = plan_content
            elif tool_name in _CLAUDE_AGENT_MESSAGING_TOOLS:
                if flags.show_agents:
                    agent_tool_message.tools.append(item)
            elif flags.show_tools:
                msg.tools.append({
                    **item,
                    "input": normalize_tool_input_keys(
                        "claude", tool_name, item.get("input", {})
                    ),
                })

    if text_blocks and show_message_text:
        msg.text = "\n\n".join(text_blocks)

    return [msg, agent_tool_message]


def _parse_system_entry(
    entry: dict, index: int, flags: ConversationFlags
) -> Message | None:
    """Parse Claude system entries that should be surfaced as visible messages."""
    if not flags.show_assistant_messages:
        return None

    if entry.get("subtype") != "away_summary":
        return None

    content = entry.get("content")
    if not isinstance(content, str):
        return None

    recap = content.removesuffix(" (disable recaps in /config)").strip()
    if not recap:
        return None

    return Message(
        role="assistant",
        index=index,
        text=recap,
        timestamp=entry.get("timestamp"),
        wrapper_type=ContentBlockType.RECAP,
    )


def _parse_hook_additional_context_entry(
    entry: dict, index: int, flags: ConversationFlags
) -> Message | None:
    """Represent a Claude hook's injected additional-context as an `AdditionalContext` tool.

    Hooks (UserPromptSubmit, SessionStart, Pre/PostToolUse, ...) can inject text
    into the transcript as a top-level `attachment` entry. Treating it as a
    synthetic tool_use lets it obey the shared `-t/--tools` visibility policy.
    """
    if not flags.show_tools:
        return None

    attachment = entry.get("attachment", {})
    if attachment.get("type") != "hook_additional_context":
        return None

    content = attachment.get("content")
    if not isinstance(content, list):
        return None
    text = "\n\n".join(block for block in content if isinstance(block, str) and block.strip())
    if not text:
        return None

    msg = Message(role="assistant", index=index, timestamp=entry.get("timestamp"))
    msg.tools.append({
        "type": "tool_use",
        "name": "AdditionalContext",
        "input": {"hook_name": attachment.get("hookName", ""), "content": text},
    })
    return msg


def _normalize_pi_tool_name(name: str | None) -> str:
    """Map PI tool names to the canonical names used by the shared renderer."""
    return normalize_tool_name("pi", name)


_PI_SKILL_TOKEN_PATTERN = re.compile(r"<skill(?:\s[^>]*)?>|</skill>")
_PI_SKILL_CLOSE_TAG = "</skill>"


@dataclass(frozen=True)
class PiInlineSkill:
    """One expanded inline skill peeled from the front of a Pi user message."""

    input_data: dict[str, str]
    body: str


def _parse_pi_skill_attributes(opening_tag: str) -> dict[str, str]:
    """Map a skill opening tag's attributes to Skill tool input keys.

    >>> _parse_pi_skill_attributes('<skill name="a" location="/a/SKILL.md">')
    {'skill': 'a', 'location': '/a/SKILL.md'}
    """
    return {
        ("skill" if key == "name" else key): value
        for key, value in _TAG_ATTRIBUTE_PATTERN.findall(opening_tag)
    }


def _split_pi_inline_skills(text: str) -> tuple[list[PiInlineSkill], str]:
    r"""Split the leading run of Pi inline-skill blocks from the typed user text.

    Only the leading run counts: the first non-skill text ends the scan, so
    literal <skill> tags pasted later in the message stay user text. An
    unclosed leading block means the message is not a skill expansion and is
    returned untouched.

    >>> skills, remainder = _split_pi_inline_skills(
    ...     '<skill name="a" location="/a">body</skill>\n\nhello'
    ... )
    >>> [skill.input_data for skill in skills], remainder
    ([{'skill': 'a', 'location': '/a'}], 'hello')
    >>> _split_pi_inline_skills('hi <skill name="a">x</skill>')
    ([], 'hi <skill name="a">x</skill>')
    """
    skills: list[PiInlineSkill] = []
    cursor = len(text) - len(text.lstrip())

    while opening := _PI_SKILL_TOKEN_PATTERN.match(text, cursor):
        if opening.group() == _PI_SKILL_CLOSE_TAG:
            break

        depth = 1
        close_end: int | None = None
        for token in _PI_SKILL_TOKEN_PATTERN.finditer(text, opening.end()):
            depth += -1 if token.group() == _PI_SKILL_CLOSE_TAG else 1
            if depth == 0:
                body = text[opening.end() : token.start()].strip()
                skills.append(
                    PiInlineSkill(_parse_pi_skill_attributes(opening.group()), body)
                )
                close_end = token.end()
                break
        if close_end is None:
            return [], text

        tail = text[close_end:]
        cursor = close_end + len(tail) - len(tail.lstrip())

    if not skills:
        return [], text
    return skills, text[cursor:]


def _pi_inline_skill_message(
    entry: dict, skill: PiInlineSkill, ordinal: int
) -> Message:
    """Represent one expanded inline skill as a synthetic Skill tool pair."""
    seed = f"{_pi_native_entry_id(entry)}:{ordinal}"
    tool_use_id = hashlib.sha1(seed.encode()).hexdigest()[:12]
    message = Message(
        role="assistant",
        timestamp=entry.get("timestamp"),
        native_entry_id=_pi_native_entry_id(entry),
    )
    message.tools = [
        {
            "type": "tool_use",
            "id": tool_use_id,
            "name": "Skill",
            "input": skill.input_data,
        },
        {"type": "tool_result", "tool_use_id": tool_use_id, "content": skill.body},
    ]
    return message

def _parse_pi_compaction_entry(
    entry: dict,
    index: int,
    flags: ConversationFlags,
) -> Message | None:
    """Parse a PI `type=compaction` entry as the shared compaction block."""
    summary = entry.get("summary")
    if (
        not flags.show_user_messages
        or not isinstance(summary, str)
        or not summary.strip()
    ):
        return None

    return Message(
        role="user",
        index=index,
        text=summary,
        native_entry_id=_pi_native_entry_id(entry),
        timestamp=entry.get("timestamp"),
        wrapper_type=ContentBlockType.COMPACTION,
    )


def _normalize_codex_tool_name(name: str | None) -> str:
    """Map Codex tool names to canonical names where a shared tool already exists."""
    return normalize_tool_name("codex", name)


def _pi_nested_team_calls_message(entry: dict, flags: ConversationFlags) -> Message:
    """Return the team calls a codemode script ran, as agent tool inputs under --agents.

    Pi's `nestedCalls` keeps each nested call's arguments, not its result.
    """
    message = Message(
        role="assistant",
        timestamp=entry.get("timestamp"),
        native_entry_id=_pi_native_entry_id(entry),
        tools_always_visible=True,
    )
    nested = entry["message"].get("nestedCalls")
    calls = nested.get("calls") if flags.show_agents and isinstance(nested, dict) else None
    for call in calls if isinstance(calls, list) else []:
        if not (isinstance(call, dict) and _is_pi_team_tool(call.get("name"))):
            continue
        tool_name = _normalize_pi_tool_name(call["name"])
        message.tools.append({
            "type": "tool_use",
            "id": call.get("id"),
            "native_tool_call_id": call.get("id"),
            "name": tool_name,
            "input": normalize_tool_input_keys("pi", tool_name, call.get("arguments") or {}),
        })
    return message


def _parse_pi_message_entry(
    entry: dict,
    index: int,
    flags: ConversationFlags,
) -> list[Message]:
    """Parse a PI `type=message` entry into its visible messages.

    A user entry whose text starts with expanded inline-skill blocks splits
    into one synthetic Skill message per block plus the typed remainder.
    `team_*` tool calls and results are agent content: an assistant entry's
    team calls split into their own message, shown by --agents regardless of
    tool filters, and never by --tools alone.
    """
    message_data = entry.get("message", {})
    role = message_data.get("role")
    native_entry_id = _pi_native_entry_id(entry)

    if role == "user":
        msg = Message(
            role="user",
            index=index,
            timestamp=entry.get("timestamp"),
            native_entry_id=native_entry_id,
        )
    elif role == "assistant":
        msg = Message(
            role="assistant",
            index=index,
            timestamp=entry.get("timestamp"),
            native_entry_id=native_entry_id,
        )
    elif role == "toolResult":
        nested_team_message = _pi_nested_team_calls_message(entry, flags)
        is_team_tool = _is_pi_team_tool(message_data.get("toolName"))
        if not (flags.show_agents if is_team_tool else flags.show_tools):
            return [nested_team_message]

        native_tool_call_id = message_data.get("toolCallId")
        msg = Message(
            role="assistant",
            index=index,
            timestamp=entry.get("timestamp"),
            native_entry_id=native_entry_id,
            tools_always_visible=is_team_tool,
        )
        tool_result = {
            "type": "tool_result",
            "tool_use_id": native_tool_call_id,
            "native_tool_call_id": native_tool_call_id,
            "content": message_data.get("content", []),
            "is_error": message_data.get("isError", False)
                or bool(message_data.get("details", {}).get("error")),
        }
        native_tool_name = message_data.get("toolName")
        if isinstance(native_tool_name, str) and native_tool_name:
            tool_result["name"] = _normalize_pi_tool_name(native_tool_name)
        msg.tools.append(tool_result)
        return [msg, nested_team_message]
    else:
        return []

    content_items = message_data.get("content", [])
    text_blocks = _extract_text_blocks(content_items)

    if role == "user":
        text_blocks = _filter_hidden_user_text_blocks(text_blocks)
        skills, remainder = _split_pi_inline_skills("\n\n".join(text_blocks))
        if remainder and flags.show_user_messages:
            msg.text = remainder
        skill_messages = (
            [
                _pi_inline_skill_message(entry, skill, ordinal)
                for ordinal, skill in enumerate(skills)
            ]
            if flags.show_tools
            else []
        )
        return [*skill_messages, msg]

    if text_blocks and flags.show_assistant_messages:
        msg.text = "\n\n".join(text_blocks)

    team_message = Message(
        role="assistant",
        timestamp=entry.get("timestamp"),
        native_entry_id=native_entry_id,
        tools_always_visible=True,
    )
    if role == "assistant" and isinstance(content_items, list):
        thinking_blocks: list[str] = []

        for native_content_index, item in enumerate(content_items):
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if item_type == "thinking" and flags.show_thinking:
                if thinking := item.get("thinking", "").strip():
                    thinking_blocks.append(thinking)
            elif item_type == "toolCall":
                is_team_tool = _is_pi_team_tool(item.get("name"))
                if not (flags.show_agents if is_team_tool else flags.show_tools):
                    continue
                native_tool_call_id = item.get("id")
                tool_name = _normalize_pi_tool_name(item.get("name"))
                (team_message if is_team_tool else msg).tools.append({
                    "type": "tool_use",
                    "id": native_tool_call_id,
                    "native_tool_call_id": native_tool_call_id,
                    "native_content_index": native_content_index,
                    "name": tool_name,
                    "input": normalize_tool_input_keys(
                        "pi", tool_name, item.get("arguments", {})
                    ),
                })

        if thinking_blocks:
            msg.thinking = "\n\n".join(thinking_blocks)

    return [msg, team_message]


def _extract_codex_text_blocks(content_data: object) -> list[str]:
    """Collect text blocks from Codex message payload content."""
    if not isinstance(content_data, list):
        return []

    text_blocks: list[str] = []
    for item in content_data:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type not in {"input_text", "output_text"}:
            continue
        if text := item.get("text", "").strip():
            text_blocks.append(text)
    return text_blocks


def _extract_codex_reasoning_text(payload: dict) -> str:
    """Extract visible reasoning summary text from a Codex reasoning payload."""
    summary = payload.get("summary", [])
    if not isinstance(summary, list):
        return ""

    text_blocks: list[str] = []
    for item in summary:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "summary_text":
            continue
        if text := item.get("text", "").strip():
            text_blocks.append(text)

    return "\n\n".join(text_blocks)


_CODEX_SCRIPT_TOOL_CALL_PATTERN = re.compile(
    r"\btools\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CODEX_SCRIPT_STRING_BINDING_PATTERN = re.compile(
    r"\bconst\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<value>\"(?:\\.|[^\"\\])*\")\s*;"
)


def _find_codex_script_call_end(script: str, opening_index: int) -> int | None:
    """Find a tool call's closing parenthesis without counting quoted text."""
    depth = 1
    quote: str | None = None
    escaped = False

    for index in range(opening_index + 1, len(script)):
        character = script[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'", "`"}:
            quote = character
            continue
        if character == "(":
            depth += 1
            continue
        if character != ")":
            continue
        depth -= 1
        if depth == 0:
            return index

    return None


def _split_codex_script_items(source: str) -> list[str]:
    """Split comma-separated JavaScript items without splitting nested values."""
    items: list[str] = []
    item_start = 0
    nested_depth = 0
    quote: str | None = None
    escaped = False

    for index, character in enumerate(source):
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'", "`"}:
            quote = character
            continue
        if character in "([{":
            nested_depth += 1
            continue
        if character in ")]}":
            nested_depth -= 1
            continue
        if character != "," or nested_depth:
            continue
        items.append(source[item_start:index].strip())
        item_start = index + 1

    items.append(source[item_start:].strip())
    return [item for item in items if item]


def _parse_codex_script_scalar(value: str) -> object:
    """Parse a generated JavaScript scalar while keeping dynamic expressions visible."""
    stripped = value.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    if stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1]
    return stripped


def _parse_codex_script_object(argument: str) -> dict[str, object] | None:
    """Parse the object literals generated for Codex tool calls."""
    stripped = argument.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return None

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    input_data: dict[str, object] = {}
    for item in _split_codex_script_items(stripped[1:-1]):
        property_match = re.fullmatch(
            r"\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<value>.+)\s*",
            item,
            re.DOTALL,
        )
        if property_match is None:
            return None
        input_data[property_match.group("key")] = _parse_codex_script_scalar(
            property_match.group("value")
        )
    return input_data or None


def _parse_codex_script_call(
    script: str,
    match: re.Match[str],
    string_bindings: dict[str, str],
) -> tuple[str, dict[str, object]] | None:
    """Parse one matched inner tool call from a generated Codex script."""
    closing_index = _find_codex_script_call_end(script, match.end() - 1)
    if closing_index is None:
        return None

    tool_name = match.group("name")
    argument = script[match.end() : closing_index].strip()
    if input_data := _parse_codex_script_object(argument):
        return tool_name, input_data
    if tool_name != "apply_patch":
        return None

    patch = string_bindings.get(argument)
    if patch is None:
        try:
            patch = json.loads(argument)
        except json.JSONDecodeError:
            return None
    if not isinstance(patch, str):
        return None
    return tool_name, {"input": patch}


def _merge_codex_script_tool_calls(
    tool_calls: list[tuple[str, dict[str, object]]],
) -> tuple[str, dict[str, object]] | None:
    """Represent one outer Codex exec envelope as one canonical tool call."""
    if len(tool_calls) == 1:
        return tool_calls[0]

    tool_names = {tool_name for tool_name, _ in tool_calls}
    if tool_names == {"apply_patch"}:
        patches: list[str] = []
        for _, input_data in tool_calls:
            patch = input_data.get("input")
            if not isinstance(patch, str):
                return None
            patches.append(patch)
        return "apply_patch", {"input": "\n\n".join(patches)}
    if tool_names != {"exec_command"}:
        return None

    input_blocks = [input_data for _, input_data in tool_calls]
    commands: list[str] = []
    for input_data in input_blocks:
        command = input_data.get("cmd")
        if not isinstance(command, str):
            return None
        commands.append(command)

    merged_input: dict[str, object] = {"cmd": "\n\n".join(commands)}
    for key in ("workdir", "yield_time_ms", "max_output_tokens"):
        values = [input_data.get(key) for input_data in input_blocks]
        if values[0] is not None and all(value == values[0] for value in values):
            merged_input[key] = values[0]
    return "exec_command", merged_input


def _parse_codex_exec_script_tool(
    script: str,
) -> tuple[str, dict[str, object]] | None:
    """Extract native tool calls from Codex's generated exec script.

    >>> _parse_codex_exec_script_tool('await tools.exec_command({cmd: "pwd"});')
    ('exec_command', {'cmd': 'pwd'})
    """
    matches = list(_CODEX_SCRIPT_TOOL_CALL_PATTERN.finditer(script))
    string_bindings = {
        binding.group("name"): json.loads(binding.group("value"))
        for binding in _CODEX_SCRIPT_STRING_BINDING_PATTERN.finditer(script)
    }
    tool_calls: list[tuple[str, dict[str, object]]] = []
    for match in matches:
        tool_call = _parse_codex_script_call(script, match, string_bindings)
        if tool_call is None:
            return None
        tool_calls.append(tool_call)
    return _merge_codex_script_tool_calls(tool_calls) if tool_calls else None


def _normalize_codex_custom_tool_call(
    native_name: str | None,
    raw_input: object,
) -> tuple[str, dict[str, object]]:
    """Normalize a direct custom call or Codex's generated exec envelope."""
    parsed_script_tool = (
        _parse_codex_exec_script_tool(raw_input)
        if native_name == "exec" and isinstance(raw_input, str)
        else None
    )
    if parsed_script_tool is not None:
        native_name, raw_input = parsed_script_tool

    tool_name = _normalize_codex_tool_name(native_name)
    return tool_name, _normalize_codex_tool_input(tool_name, raw_input)


def _parse_codex_tool_input(raw_input: object) -> dict[str, object]:
    """Normalize Codex tool input into a dict for the shared tool renderer."""
    if isinstance(raw_input, dict):
        return raw_input

    if isinstance(raw_input, list):
        return {"input": raw_input}

    if not isinstance(raw_input, str):
        return {}

    stripped = raw_input.strip()
    if not stripped:
        return {}

    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return {"input": raw_input}
        if isinstance(parsed, dict):
            return parsed
        return {"input": parsed}

    return {"input": raw_input}


def _normalize_codex_tool_input(
    tool_name: str,
    raw_input: object,
) -> dict[str, object]:
    """Normalize Codex tool argument keys for canonical shared tool schemas."""
    input_data = _parse_codex_tool_input(raw_input)
    return normalize_tool_input_keys("codex", tool_name, input_data)


def _parse_codex_tool_output(raw_output: object) -> object:
    """Normalize Codex tool outputs into shared text content blocks."""
    if isinstance(raw_output, list):
        return [
            {**block, "type": "text"}
            if isinstance(block, dict)
            and block.get("type") in {"input_text", "output_text"}
            else block
            for block in raw_output
        ]
    if not isinstance(raw_output, str):
        return raw_output

    stripped = raw_output.strip()
    if not stripped.startswith("{"):
        return raw_output

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return raw_output

    if not isinstance(parsed, dict):
        return raw_output

    for key in ("output", "content", "text"):
        value = parsed.get(key)
        if isinstance(value, str):
            return value

    return raw_output


def _append_codex_block(existing: str | None, new_text: str) -> str:
    """Append a non-empty Codex content block with paragraph spacing."""
    if not existing:
        return new_text
    return f"{existing}\n\n{new_text}"


def _is_codex_preamble_text(text: str) -> bool:
    """Return True when a Codex user text block is protocol/setup noise."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith("# AGENTS.md instructions for "):
        return True
    if stripped.startswith("<environment_context>"):
        return True
    if stripped.startswith("<recommended_plugins>"):
        return True
    return bool(stripped.startswith("<skill>"))


def _extract_cwd_from_codex_entry(entry: dict) -> str | None:
    """Extract cwd from Codex session metadata or environment preamble."""
    if entry.get("type") == "session_meta":
        payload = entry.get("payload", {})
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            return cwd
        return None

    if entry.get("type") != "response_item":
        return None

    payload = entry.get("payload", {})
    if payload.get("type") != "message" or payload.get("role") != "user":
        return None

    for text in _extract_codex_text_blocks(payload.get("content")):
        stripped = text.strip()
        if not stripped.startswith("<environment_context>"):
            continue

        match = re.search(r"<cwd>(.*?)</cwd>", stripped, re.DOTALL)
        if not match:
            continue

        cwd = match.group(1).strip()
        if cwd:
            return cwd

    return None


def _extract_cwd_from_entry(entry: dict) -> str | None:
    """Extract cwd from one decoded JSONL entry."""
    cwd = entry.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd
    return _extract_cwd_from_codex_entry(entry)


def extract_cwd_from_jsonl_file(file_path: Path) -> str | None:
    """Stream a JSONL file until the first cwd-bearing entry is found."""
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if cwd := _extract_cwd_from_entry(entry):
                    return cwd
    except OSError:
        return None

    return None


def extract_cwd_from_jsonl(content: str) -> str | None:
    """Extract the working directory (cwd) from JSONL conversation."""
    return extract_cwd_from_entries(_iter_jsonl_entries(content))


def extract_cwd_from_entries(entries: list[dict]) -> str | None:
    """Extract cwd from already-decoded JSONL entries."""
    for entry in entries:
        if cwd := _extract_cwd_from_entry(entry):
            return cwd
    return None
