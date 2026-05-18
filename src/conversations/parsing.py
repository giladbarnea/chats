from __future__ import annotations

import json
import os
import re
import textwrap
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .model import ConversationFlags, Message, Provider
from .registry import (
    ContentBlockType,
    normalize_tool_input_keys,
    normalize_tool_name,
)
from .utils import shorten_tool_use_id

RenameEntryBuilder = Callable[[list[dict], str, str], list[dict]]


@dataclass(frozen=True)
class JsonlSessionAdapter:
    """A parser adapter for one JSONL session shape."""

    name: Provider
    matches: Callable[[Path | None], bool]
    parse_messages: Callable[[str, ConversationFlags], list[Message]]
    build_rename_entries: RenameEntryBuilder
    writes_claude_history: bool = False
    find_session_files: Callable[[], list[Path]] | None = None
    find_session_matches: Callable[[str], list[tuple[Path, str]]] | None = None
    is_sidechain_path: Callable[[Path], bool] = lambda _path: False
    extract_session_id: Callable[[Path], str | None] = lambda path: path.stem
    extract_forked_from: Callable[[Path], str | None] = lambda _path: None


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
    if last_ts := _find_last_timestamp(file_path):
        if parsed := _parse_iso_timestamp(last_ts):
            return parsed
    try:
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    except OSError:
        return None


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
                    if "timestamp" in entry:
                        return entry["timestamp"]
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return None


def _find_last_timestamp(file_path: Path, chunk_size: int = 4096) -> str | None:
    """Finds the last timestamp by reading from the end (backwards)."""
    try:
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            remaining_bytes = file_size
            buffer = b""

            while remaining_bytes > 0:
                read_size = min(chunk_size, remaining_bytes)
                f.seek(-read_size, os.SEEK_CUR)
                chunk = f.read(read_size)
                # Reset cursor to before this read for the next iteration
                f.seek(-read_size, os.SEEK_CUR)

                remaining_bytes -= read_size

                # Prepend whatever was left from the previous (later) chunk
                chunk += buffer
                lines = chunk.split(b"\n")

                # The first element is likely a partial line from the *previous* (earlier) chunk
                # so we keep it in the buffer for the next iteration, unless we are at the start of the file.
                if remaining_bytes > 0:
                    buffer = lines.pop(0)
                else:
                    buffer = b""  # We are at start, process everything

                # Iterate lines in reverse
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        # Decode utf-8 safely
                        entry = json.loads(line.decode("utf-8"))
                        if "timestamp" in entry:
                            return entry["timestamp"]
                    except (json.JSONDecodeError, UnicodeDecodeError):
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


def extract_summaries_from_entries(entries: list[dict]) -> list[str]:
    """Extract all summary fields from parsed JSONL entries."""
    return _extract_field_from_entries(entries, "summary", "summary")


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


def extract_latest_custom_title_from_entries(entries: list[dict]) -> str | None:
    """Extract only the latest shared custom-title value from parsed JSONL entries."""
    latest_custom_title: str | None = None
    for entry in entries:
        if custom_title := _extract_custom_title_from_entry(entry):
            latest_custom_title = custom_title
    return latest_custom_title


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


def extract_resolution_facets_from_jsonl(file_path: Path) -> tuple[str | None, list[str]]:
    """Extract the current title and summaries needed for identifier fallback resolution."""
    latest_custom_title: str | None = None
    summaries: list[str] = []

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or not stripped.startswith("{"):
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue

                if entry.get("type") == "summary":
                    summary = entry.get("summary")
                    if isinstance(summary, str) and summary:
                        summaries.append(summary)

                if custom_title := _extract_custom_title_from_entry(entry):
                    latest_custom_title = custom_title
    except OSError:
        return None, []

    return latest_custom_title, summaries


def detect_format(content: str) -> str:
    """
    Detect if content is JSONL or raw format.

    JSONL format: First non-empty line is valid JSON with a 'type' field.
    Raw format: CLI transcript with "> " and "... " prefixes (never valid JSON).

    These formats are mutually exclusive - the first non-empty line is deterministic.
    """
    # Find first non-empty line
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "type" in obj:
                return "jsonl"
        except (json.JSONDecodeError, ValueError):
            pass
        break

    return "raw"


def _iter_jsonl_entries(content: str) -> list[dict]:
    """Parse a JSONL string into a list of JSON object entries."""
    entries: list[dict] = []

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
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


def _parse_user_string_content(
    content: str,
) -> tuple[str, ContentBlockType | None]:
    """Detect special Claude user string content that needs wrapper/content overrides."""
    if _is_hidden_user_command_text(content):
        return "", None

    return content, None


def _parse_default_jsonl_entries(
    entries: list[dict], flags: ConversationFlags
) -> list[Message]:
    """Parse Claude-style JSONL entries into the shared Message model."""
    messages = []
    index = 1

    for entry in entries:
        entry_type = entry.get("type")

        if entry_type == "user":
            msg = _parse_user_entry(entry, index, flags)
        elif entry_type == "assistant":
            msg = _parse_assistant_entry(entry, index, flags)
        elif entry_type == "system":
            msg = _parse_system_entry(entry, index, flags)
        else:
            msg = None

        if msg and msg.has_content():
            messages.append(msg)
            index += 1

    return messages


def _parse_default_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse the existing Claude-style JSONL conversation shape."""
    return _parse_default_jsonl_entries(_iter_jsonl_entries(content), flags)


def _parse_pi_jsonl_entries(
    entries: list[dict], flags: ConversationFlags
) -> list[Message]:
    """Parse PI JSONL entries into the shared Message model."""
    messages = []
    index = 1

    for entry in entries:
        entry_type = entry.get("type")

        if entry_type == "message":
            msg = _parse_pi_message_entry(entry, index, flags)
        else:
            msg = None

        if msg and msg.has_content():
            messages.append(msg)
            index += 1

    return messages


def _parse_pi_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse PI JSONL sessions into the shared Message model."""
    return _parse_pi_jsonl_entries(_iter_jsonl_entries(content), flags)


def _parse_codex_jsonl_entries(
    entries: list[dict], flags: ConversationFlags
) -> list[Message]:
    """Parse Codex JSONL entries into the shared Message model."""
    messages = []
    index = 1
    current_assistant: Message | None = None

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

        if payload_type == "function_call" and flags.show_tools:
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

        if payload_type == "function_call_output" and flags.show_tools:
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
            tool_name = _normalize_codex_tool_name(payload.get("name"))
            assistant.tools.append({
                "type": "tool_use",
                "id": payload.get("call_id"),
                "name": tool_name,
                "input": _normalize_codex_tool_input(tool_name, payload.get("input")),
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


def _is_pi_jsonl_path(source_path: Path | None) -> bool:
    """Return True when the source path is inside ~/.pi/."""
    if source_path is None:
        return False

    try:
        source_path.resolve().relative_to((Path.home() / ".pi").resolve())
    except ValueError:
        return False
    except OSError:
        return False

    return True


def _is_codex_jsonl_path(source_path: Path | None) -> bool:
    """Return True when the source path is inside ~/.codex/sessions/."""
    if source_path is None:
        return False

    try:
        source_path.resolve().relative_to(
            (Path.home() / ".codex" / "sessions").resolve()
        )
    except ValueError:
        return False
    except OSError:
        return False

    return True


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


def _extract_codex_session_meta_field(
    session_file: Path, field_name: str
) -> str | None:
    """Extract a string field from the Codex session_meta payload."""
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
                    break

                payload = entry.get("payload", {})
                value = payload.get(field_name)
                if isinstance(value, str) and value:
                    return value
                break
    except OSError:
        pass

    return None


def _extract_codex_session_id(session_file: Path) -> str | None:
    """Extract the Codex session id from the file's session_meta entry."""
    return _extract_codex_session_meta_field(session_file, "id")


def _extract_codex_forked_from_id(session_file: Path) -> str | None:
    """Extract the Codex fork parent id from the file's session_meta entry."""
    return _extract_codex_session_meta_field(session_file, "forked_from_id")


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


def _find_pi_session_files() -> list[Path]:
    """List PI session JSONL files."""
    sessions_dir = Path.home() / ".pi" / "agent" / "sessions"
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.rglob("*.jsonl"))


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


def _find_codex_session_files() -> list[Path]:
    """List Codex session JSONL files."""
    sessions_dir = Path.home() / ".codex" / "sessions"
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.rglob("*.jsonl"))


def find_all_supported_session_files(*, include_sidechains: bool = True) -> list[Path]:
    """List all known session files across Claude, PI, and Codex."""
    claude_projects_dir = Path.home() / ".claude" / "projects"
    claude_files: list[Path] = []
    if claude_projects_dir.exists():
        claude_files.extend(claude_projects_dir.glob("*/*.jsonl"))
        claude_files.extend(claude_projects_dir.glob("*/*/subagents/agent-*.jsonl"))
        claude_files = sorted(claude_files)

    adapter_files: list[Path] = []
    for adapter in JSONL_SESSION_ADAPTERS:
        if adapter.find_session_files is None:
            continue
        adapter_files.extend(adapter.find_session_files())

    session_files = claude_files + adapter_files
    if include_sidechains:
        return session_files

    return [path for path in session_files if not is_sidechain_session_file(path)]


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


def _build_claude_rename_entries(
    entries: list[dict],
    session_id: str,
    new_name: str,
) -> list[dict]:
    """Build Claude-native rename entries including the /rename system command record."""
    parent_uuid = entries[-1].get("uuid", "") if entries else ""
    cwd = ""
    version = "UNKNOWN"
    git_branch = "HEAD"
    for entry in reversed(entries):
        if not cwd and "cwd" in entry:
            cwd = entry["cwd"]
        if not version and "version" in entry:
            version = entry["version"]
        if not git_branch and "gitBranch" in entry:
            git_branch = entry["gitBranch"]
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
        {
            "parentUuid": parent_uuid,
            "isSidechain": False,
            "type": "system",
            "subtype": "local_command",
            "content": f"<command-name>/rename</command-name>\n <command-message>rename</command-message>\n <command-args>{new_name}</command-args>",
            "level": "info",
            "timestamp": _jsonl_timestamp_now(),
            "uuid": uuid.uuid4().hex,
            "isMeta": False,
            "userType": "external",
            "entrypoint": "cli",
            "cwd": cwd,
            "sessionId": session_id,
            "version": version,
            "gitBranch": git_branch,
        },
    ]


def _build_pi_rename_entries(
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


def _build_codex_rename_entries(
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
        name="pi",
        matches=_is_pi_jsonl_path,
        parse_messages=_parse_pi_jsonl,
        build_rename_entries=_build_pi_rename_entries,
        find_session_files=_find_pi_session_files,
        find_session_matches=_find_pi_session_matches,
        extract_session_id=_extract_pi_session_id,
    ),
    JsonlSessionAdapter(
        name="codex",
        matches=_is_codex_jsonl_path,
        parse_messages=_parse_codex_jsonl,
        build_rename_entries=_build_codex_rename_entries,
        find_session_files=_find_codex_session_files,
        find_session_matches=_find_codex_session_matches,
        extract_session_id=_extract_codex_session_id,
        extract_forked_from=_extract_codex_forked_from_id,
    ),
    JsonlSessionAdapter(
        name="claude",
        matches=lambda _source_path: True,
        parse_messages=_parse_default_jsonl,
        build_rename_entries=_build_claude_rename_entries,
        writes_claude_history=True,
        is_sidechain_path=lambda path: path.name.startswith("agent-"),
        extract_session_id=lambda path: path.stem,
    ),
]


def _select_jsonl_session_adapter(source_path: Path | None) -> JsonlSessionAdapter:
    """Select the first JSONL adapter whose matcher accepts the source path."""
    for adapter in JSONL_SESSION_ADAPTERS:
        if adapter.matches(source_path):
            return adapter
    return JSONL_SESSION_ADAPTERS[-1]


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
    adapter = _select_jsonl_session_adapter(source_path)
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


def _parse_user_entry(
    entry: dict, index: int, flags: ConversationFlags
) -> Message | None:
    """Parse a user-type JSONL entry."""
    message_data = entry.get("message", {})
    if message_data.get("role") != "user":
        return None

    content_data = message_data.get("content")
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

    show_user_text = flags.show_user_messages and (not msg.is_meta or flags.show_tools)

    if isinstance(content_data, str) and show_user_text:
        msg.text, msg.wrapper_type = _parse_user_string_content(content_data)
    elif isinstance(content_data, list):
        text_blocks = _filter_hidden_user_text_blocks(_extract_text_blocks(content_data))
        for item in content_data:
            if (
                isinstance(item, dict)
                and flags.show_tools
                and item.get("type") == "tool_result"
            ):
                msg.tools.append(item)

        if text_blocks and show_user_text:
            msg.text = "\n\n".join(text_blocks)

    return msg


def _parse_assistant_entry(
    entry: dict, index: int, flags: ConversationFlags
) -> Message | None:
    """Parse an assistant-type JSONL entry."""
    message_data = entry.get("message", {})
    if message_data.get("role") != "assistant":
        return None

    agent_id = entry.get("agentId")
    if agent_id and not flags.show_agents:
        return None

    show_message_text = flags.show_agents if agent_id else flags.show_assistant_messages

    content_data = message_data.get("content", [])
    if not isinstance(content_data, list):
        return None

    msg = Message(
        role="assistant",
        index=index,
        agent_id=agent_id,
        timestamp=entry.get("timestamp"),
        model=message_data.get("model"),
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
            elif flags.show_tools:
                msg.tools.append(item)

    if text_blocks and show_message_text:
        msg.text = "\n\n".join(text_blocks)

    return msg


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


def _normalize_pi_tool_name(name: str | None) -> str:
    """Map PI tool names to the canonical names used by the shared renderer."""
    return normalize_tool_name("pi", name)


def _normalize_codex_tool_name(name: str | None) -> str:
    """Map Codex tool names to canonical names where a shared tool already exists."""
    return normalize_tool_name("codex", name)


def _parse_pi_message_entry(
    entry: dict,
    index: int,
    flags: ConversationFlags,
) -> Message | None:
    """Parse a PI `type=message` entry."""
    message_data = entry.get("message", {})
    role = message_data.get("role")

    if role == "user":
        msg = Message(role="user", index=index, timestamp=entry.get("timestamp"))
    elif role == "assistant":
        msg = Message(
            role="assistant",
            index=index,
            timestamp=entry.get("timestamp"),
            model=message_data.get("model"),
        )
    elif role == "toolResult":
        if not flags.show_tools:
            return None

        msg = Message(role="user", index=index, timestamp=entry.get("timestamp"))
        msg.tools.append({
            "type": "tool_result",
            "tool_use_id": message_data.get("toolCallId"),
            "content": message_data.get("content", []),
            "is_error": message_data.get("isError", False)
                or bool(message_data.get("details", {}).get("error")),
        })
        return msg
    else:
        return None

    content_items = message_data.get("content", [])
    text_blocks = _extract_text_blocks(content_items)
    if role == "user":
        text_blocks = _filter_hidden_user_text_blocks(text_blocks)

    if (
        role == "user"
        and text_blocks
        and flags.show_user_messages
        or role == "assistant"
        and text_blocks
        and flags.show_assistant_messages
    ):
        msg.text = "\n\n".join(text_blocks)

    if role == "assistant" and isinstance(content_items, list):
        thinking_blocks: list[str] = []

        for item in content_items:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if item_type == "thinking" and flags.show_thinking:
                if thinking := item.get("thinking", "").strip():
                    thinking_blocks.append(thinking)
            elif item_type == "toolCall" and flags.show_tools:
                msg.tools.append({
                    "type": "tool_use",
                    "id": item.get("id"),
                    "name": _normalize_pi_tool_name(item.get("name")),
                    "input": item.get("arguments", {}),
                })

        if thinking_blocks:
            msg.thinking = "\n\n".join(thinking_blocks)

    return msg


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


def _parse_codex_tool_input(raw_input: object) -> dict:
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


def _normalize_codex_tool_input(tool_name: str, raw_input: object) -> dict:
    """Normalize Codex tool argument keys for canonical shared tool schemas."""
    input_data = _parse_codex_tool_input(raw_input)
    return normalize_tool_input_keys("codex", tool_name, input_data)


def _parse_codex_tool_output(raw_output: object) -> object:
    """Unwrap Codex JSON-string tool outputs when the wrapper only carries display text."""
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


def _is_system_message(line: str) -> bool:
    """Check if a '> ' prefixed line is a system message (not user input)."""
    return line.startswith("> ") and "is running" in line.lower()


def parse_raw_cli_transcript(
    content: str,
    flags: ConversationFlags,
) -> list[Message]:
    """
    Parse raw CLI transcript format.

    User messages start with: "> " (actual user text)
    Assistant responses start with: "... " and include system messages like "> /cmd is running"
    """
    messages = []
    index = 1
    current_role: str | None = None
    current_lines: list[str] = []

    def save_current_message() -> None:
        nonlocal index, current_lines
        if current_role and current_lines:
            if current_role == "user" and not flags.show_user_messages:
                current_lines = []
                return
            if current_role == "assistant" and not flags.show_assistant_messages:
                current_lines = []
                return
            messages.append(
                Message(role=current_role, text="\n".join(current_lines), index=index)
            )
            index += 1
        current_lines = []

    for line in content.split("\n"):
        if line.startswith("\u23fa "):  # ⏺
            # Assistant response marker
            if current_role != "assistant":
                save_current_message()
                current_role = "assistant"
            current_lines.append(line)

        elif line.startswith("> "):
            if _is_system_message(line):
                # System message - part of assistant response
                if current_role != "assistant":
                    save_current_message()
                    current_role = "assistant"
                current_lines.append(line)
            else:
                # User message
                if current_role != "user":
                    save_current_message()
                    current_role = "user"
                current_lines.append(line[2:])  # Strip "> " prefix

        elif current_role:
            # Continuation line
            current_lines.append(line)

    save_current_message()
    return messages


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
