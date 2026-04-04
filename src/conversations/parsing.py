from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from .model import ConversationFlags, Message
from .utils import shorten_tool_use_id


@dataclass(frozen=True)
class JsonlSessionAdapter:
    """A parser adapter for one JSONL session shape."""

    name: str
    matches: Callable[[Path | None], bool]
    parse_messages: Callable[[str, ConversationFlags], list[Message]]
    find_session_matches: Callable[[str], list[tuple[Path, str]]] | None = None


def get_jsonl_timestamps(file_path: Path) -> tuple[datetime | None, datetime | None]:
    """
    Efficiently extract first and last timestamps from a JSONL file.
    
    Returns (created_at, modified_at) as datetime objects (or None).
    Uses optimized forward scan for start time and backward scan for end time.
    """
    first_ts = _find_first_timestamp(file_path)
    last_ts = _find_last_timestamp(file_path)
    
    return (
        _parse_iso_timestamp(first_ts) if first_ts else None,
        _parse_iso_timestamp(last_ts) if last_ts else None
    )


def _find_first_timestamp(file_path: Path) -> str | None:
    """Finds the first timestamp by reading from the beginning."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if 'timestamp' in entry:
                        return entry['timestamp']
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return None


def _find_last_timestamp(file_path: Path, chunk_size: int = 4096) -> str | None:
    """Finds the last timestamp by reading from the end (backwards)."""
    try:
        with open(file_path, 'rb') as f:
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
                lines = chunk.split(b'\n')

                # The first element is likely a partial line from the *previous* (earlier) chunk
                # so we keep it in the buffer for the next iteration, unless we are at the start of the file.
                if remaining_bytes > 0:
                    buffer = lines.pop(0)
                else:
                    buffer = b"" # We are at start, process everything

                # Iterate lines in reverse
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        # Decode utf-8 safely
                        entry = json.loads(line.decode('utf-8'))
                        if 'timestamp' in entry:
                            return entry['timestamp']
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
            if isinstance(entry, dict) and entry.get("type") == entry_type:
                if value := entry.get(field_name):
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
                    if isinstance(entry, dict) and entry.get("type") == entry_type:
                        if value := entry.get(field_name):
                            values.append(value)
                except json.JSONDecodeError:
                    pass
                buffer = ""

    return values


def _extract_field_from_jsonl(
    file_path: Path, entry_type: str, field_name: str
) -> list[str]:
    """Extract field values from a jsonl file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        return _extract_field_from_content(content, entry_type, field_name)
    except OSError:
        return []


def extract_summaries_from_content(content: str) -> list[str]:
    """Extract all summary fields from JSONL content string."""
    return _extract_field_from_content(content, "summary", "summary")


def extract_summaries_from_jsonl(file_path: Path) -> list[str]:
    """Extract all summary fields from a jsonl conversation file."""
    return _extract_field_from_jsonl(file_path, "summary", "summary")


def extract_custom_titles_from_content(content: str) -> list[str]:
    """Extract all custom-title fields from JSONL content string."""
    return _extract_field_from_content(content, "custom-title", "customTitle")


def extract_custom_titles_from_jsonl(file_path: Path) -> list[str]:
    """Extract all custom-title fields from a jsonl conversation file."""
    return _extract_field_from_jsonl(file_path, "custom-title", "customTitle")


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


def _parse_default_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse the existing Claude-style JSONL conversation shape."""
    messages = []
    index = 1

    for entry in _iter_jsonl_entries(content):
        entry_type = entry.get("type")

        if entry_type == "user":
            msg = _parse_user_entry(entry, index, flags)
        elif entry_type == "assistant":
            msg = _parse_assistant_entry(entry, index, flags)
        elif entry_type == "custom-title":
            msg = _parse_custom_title_entry(entry, index)
        else:
            msg = None

        if msg and msg.has_content():
            messages.append(msg)
            index += 1

    return messages


def _parse_pi_jsonl(content: str, flags: ConversationFlags) -> list[Message]:
    """Parse PI JSONL sessions into the shared Message model."""
    messages = []
    index = 1

    for entry in _iter_jsonl_entries(content):
        if entry.get("type") != "message":
            continue

        msg = _parse_pi_message_entry(entry, index, flags)
        if msg and msg.has_content():
            messages.append(msg)
            index += 1

    return messages


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


JSONL_SESSION_ADAPTERS = [
    JsonlSessionAdapter(
        name="pi",
        matches=_is_pi_jsonl_path,
        parse_messages=_parse_pi_jsonl,
        find_session_matches=_find_pi_session_matches,
    ),
    JsonlSessionAdapter(
        name="default",
        matches=lambda _source_path: True,
        parse_messages=_parse_default_jsonl,
    ),
]


def _select_jsonl_session_adapter(source_path: Path | None) -> JsonlSessionAdapter:
    """Select the first JSONL adapter whose matcher accepts the source path."""
    for adapter in JSONL_SESSION_ADAPTERS:
        if adapter.matches(source_path):
            return adapter
    return JSONL_SESSION_ADAPTERS[-1]


def parse_jsonl(
    content: str,
    flags: ConversationFlags,
    source_path: Path | None = None,
) -> list[Message]:
    """Parse a JSONL conversation via the matching session adapter."""
    adapter = _select_jsonl_session_adapter(source_path)
    return adapter.parse_messages(content, flags)


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


def _parse_user_entry(entry: dict, index: int, flags: ConversationFlags) -> Message | None:
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

    if isinstance(content_data, str):
        msg.text = content_data
    elif isinstance(content_data, list):
        text_blocks = _extract_text_blocks(content_data)
        for item in content_data:
            if isinstance(item, dict) and flags.show_tools and item.get("type") == "tool_result":
                msg.tools.append(item)

        if text_blocks:
            msg.text = "\n\n".join(text_blocks)

    return msg


def _parse_assistant_entry(entry: dict, index: int, flags: ConversationFlags) -> Message | None:
    """Parse an assistant-type JSONL entry."""
    message_data = entry.get("message", {})
    if message_data.get("role") != "assistant":
        return None

    agent_id = entry.get("agentId")
    if agent_id and not flags.show_agents:
        return None

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
                if plan_content := item.get("input", {}).get("plan", ""):
                    msg.plan = plan_content
            elif flags.show_tools:
                msg.tools.append(item)

    if text_blocks:
        msg.text = "\n\n".join(text_blocks)

    return msg


def _normalize_pi_tool_name(name: str | None) -> str:
    """Map PI tool names to the canonical names used by the shared renderer."""
    if not name:
        return "Unknown"

    known_names = {
        "bash": "Bash",
        "read": "Read",
        "write": "Write",
        "edit": "Edit",
        "grep": "Grep",
        "glob": "Glob",
        "task": "Task",
        "webfetch": "WebFetch",
        "websearch": "WebSearch",
    }
    return known_names.get(name.lower(), name)


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
        msg.tools.append(
            {
                "type": "tool_result",
                "tool_use_id": message_data.get("toolCallId"),
                "content": message_data.get("content", []),
                "is_error": message_data.get("isError", False),
            }
        )
        return msg
    else:
        return None

    content_items = message_data.get("content", [])
    text_blocks = _extract_text_blocks(content_items)
    if text_blocks:
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
                msg.tools.append(
                    {
                        "type": "tool_use",
                        "id": item.get("id"),
                        "name": _normalize_pi_tool_name(item.get("name")),
                        "input": item.get("arguments", {}),
                    }
                )

        if thinking_blocks:
            msg.thinking = "\n\n".join(thinking_blocks)

    return msg


def _parse_custom_title_entry(entry: dict, index: int) -> Message | None:
    """Parse a custom-title JSONL entry."""
    if custom_title := entry.get("customTitle", "").strip():
        return Message(role="session-rename", index=index, text=custom_title)
    return None


def _is_system_message(line: str) -> bool:
    """Check if a '> ' prefixed line is a system message (not user input)."""
    return line.startswith("> ") and "is running" in line.lower()


def parse_raw_cli_transcript(
    content: str,
    flags: ConversationFlags,  # noqa: ARG001 - reserved for future use
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


def extract_cwd_from_jsonl(content: str) -> str | None:
    """Extract the working directory (cwd) from JSONL conversation."""
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
            if cwd := entry.get("cwd"):
                return cwd
        except json.JSONDecodeError:
            continue

    return None
