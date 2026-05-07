from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path

from ..console import get_console, print_error
from ..formatting import (
    build_metadata_text,
    format_to_json,
    format_to_raw,
    format_to_xml,
    print_metadata,
    render_messages_with_rich,
)
from ..model import ConversationFlags, Message, ParseOutputMode
from ..parsing import (
    detect_format,
    extract_custom_titles_from_content,
    extract_cwd_from_jsonl,
    get_display_session_id,
    parse_jsonl,
    parse_raw_cli_transcript,
)
from ..pool_filter import PoolFilter
from . import resolve
from .common import _build_tool_id_map


def parse_slice_notation(slice_str: str | None) -> tuple[int | None, int | None]:
    """Parse 1-indexed slice notation into 0-indexed Python slice bounds."""
    if not slice_str:
        return (None, None)
    if ":" not in slice_str:
        return _parse_single_index(slice_str)

    parts = slice_str.split(":")
    if len(parts) != 2:
        print_error(f"Invalid slice notation: {slice_str}.")
        sys.exit(1)

    start = _convert_slice_bound(parts[0], "Start")
    stop = _convert_slice_bound(parts[1], "Stop")
    return (start, stop)


def _parse_single_index(idx_str: str) -> tuple[int | None, int | None]:
    """Parse a single index into slice bounds."""
    try:
        idx = int(idx_str)
    except ValueError:
        print_error(f"Invalid slice notation: {idx_str}.")
        sys.exit(1)

    if idx > 0:
        return (idx - 1, idx)
    if idx < 0:
        return (idx, None) if idx == -1 else (idx, idx + 1)

    print_error("Index must be >= 1 or < 0 (got 0).")
    sys.exit(1)


def _convert_slice_bound(bound_str: str, name: str) -> int | None:
    """Convert a slice bound string to int, handling 1-based indexing."""
    if bound_str == "":
        return None

    bound = int(bound_str)
    if bound > 0:
        return bound - 1
    if bound == 0:
        print_error(f"{name} index must be >= 1 or < 0 (got 0).")
        sys.exit(1)
    return bound


def _normalize_slice_selectors(
    slice_str: str | Sequence[str] | None,
) -> list[str]:
    """Normalize legacy single-selector input and CLI multi-selector input."""
    if slice_str is None:
        return []
    if isinstance(slice_str, str):
        return [slice_str] if slice_str else []
    return [selector for selector in slice_str if selector]


def _apply_slice_selectors(
    messages: list[Message],
    selectors: Sequence[str],
) -> list[Message]:
    """Apply ORed slice/index selectors while preserving original message order."""
    selected_positions: set[int] = set()
    message_positions = range(len(messages))

    for selector in selectors:
        start, stop = parse_slice_notation(selector)
        selected_positions.update(message_positions[start:stop])

    return [
        message
        for position, message in enumerate(messages)
        if position in selected_positions
    ]


def cmd_parse(
    flags: ConversationFlags,
    input_arg: str | None,
    slice_str: str | Sequence[str] | None,
    output_file: Path | None,
    *,
    output_format: str = "xml",
    emit_metadata: bool = True,
    pool_filter: PoolFilter | None = None,
    output_mode: ParseOutputMode = ParseOutputMode.FULL,
) -> None:
    """Handle the parse command."""
    try:
        content, input_file_path = resolve._resolve_input_content(
            input_arg,
            pool_filter=pool_filter,
        )
    except Exception as error:
        print_error(f"Error reading input: {error}.")
        sys.exit(1)

    if not content.strip():
        print_error("Input is empty.")
        sys.exit(1)

    if output_mode == ParseOutputMode.ONLY_ID:
        resolved_path = resolve._require_file_backed_input(
            input_file_path,
            "`--only-id`",
        )
        resolve._write_parse_output(get_display_session_id(resolved_path), output_file)
        return

    if output_mode == ParseOutputMode.ONLY_METADATA and input_file_path is None:
        resolve._require_file_backed_input(input_file_path, "`--only-metadata`")

    format_type = detect_format(content)
    if format_type == "jsonl":
        messages = parse_jsonl(content, flags, source_path=input_file_path)
        cwd = extract_cwd_from_jsonl(content)
    else:
        messages = parse_raw_cli_transcript(content, flags)
        cwd = None

    if flags.show_agents and input_file_path and format_type == "jsonl":
        messages = _merge_agent_messages(messages, content, input_file_path, flags)

    if not messages:
        if flags.allow_empty_output:
            return
        print_error("No messages found in input.")
        sys.exit(0)

    tool_id_map = _build_tool_id_map(messages)
    selectors = _normalize_slice_selectors(slice_str)
    if selectors:
        messages = _apply_slice_selectors(messages, selectors)
        if not messages:
            joined_selectors = " ".join(selectors)
            print_error(f"Slice {joined_selectors} produced no messages.")
            sys.exit(0)

    custom_titles = (
        extract_custom_titles_from_content(content) if format_type == "jsonl" else []
    )
    last_custom_title = custom_titles[-1] if custom_titles else None
    metadata = (
        resolve._load_conversation_metadata(input_file_path)
        if input_file_path is not None
        else None
    )

    if output_mode == ParseOutputMode.ONLY_METADATA:
        resolved_path = resolve._require_file_backed_input(
            input_file_path,
            "`--only-metadata`",
        )
        metadata_text = build_metadata_text(
            resolved_path,
            cwd,
            len(messages),
            provider=metadata.provider if metadata else None,
            forked_from=metadata.forked_from if metadata else None,
            last_custom_title=last_custom_title,
            created_at=metadata.ctime if metadata else None,
            modified_at=metadata.mtime if metadata else None,
            include_frontmatter_separator=False,
        )
        resolve._write_parse_output(metadata_text, output_file)
        return

    if (
        emit_metadata
        and input_file_path is not None
        and output_file is None
        and output_format not in {"json", "raw"}
    ):
        print_metadata(
            input_file_path,
            cwd,
            len(messages),
            provider=metadata.provider,
            forked_from=metadata.forked_from,
            last_custom_title=last_custom_title,
            created_at=metadata.ctime,
            modified_at=metadata.mtime,
            color=flags.color,
        )

    if output_format == "json":
        formatted = format_to_json(messages, flags, tool_id_map)
    elif output_format == "raw":
        formatted = format_to_raw(messages, flags, tool_id_map)
    else:
        formatted = format_to_xml(messages, flags, tool_id_map)

    if not formatted:
        return

    if output_file is not None or output_format in {"json", "raw"} or not flags.color:
        resolve._write_parse_output(formatted, output_file)
        return

    pager_ctx = get_console().pager(styles=True) if flags.paging else nullcontext()
    with pager_ctx:
        render_messages_with_rich(messages, flags, tool_id_map)


def _merge_agent_messages(
    messages: list[Message],
    content: str,
    input_file_path: Path,
    flags: ConversationFlags,
) -> list[Message]:
    """Merge agent messages into the main conversation timeline."""
    session_id = get_display_session_id(input_file_path)
    agent_files = resolve.find_agent_files_for_session(input_file_path, session_id)
    task_dispatches = _extract_task_dispatches(content)

    all_agent_messages: list[Message] = []
    for agent_file in agent_files:
        try:
            agent_content = agent_file.read_text(encoding="utf-8")
            agent_messages = parse_jsonl(agent_content, flags, source_path=agent_file)
            if not agent_messages or not agent_messages[0].timestamp:
                continue

            first_timestamp = agent_messages[0].timestamp
            matched_subagent_type = None
            for dispatch_timestamp, subagent_type in task_dispatches:
                if first_timestamp > dispatch_timestamp:
                    matched_subagent_type = subagent_type

            if matched_subagent_type is None:
                continue

            for message in agent_messages:
                message.subagent_type = matched_subagent_type
            all_agent_messages.extend(agent_messages)
        except Exception:
            continue

    if not all_agent_messages:
        return messages

    all_agent_messages.sort(key=lambda message: message.timestamp or "")
    first_agent_timestamp = all_agent_messages[0].timestamp
    insert_index = 0
    for index, message in enumerate(messages):
        if message.timestamp and message.timestamp < first_agent_timestamp:
            insert_index = index + 1

    messages[insert_index:insert_index] = all_agent_messages
    for index, message in enumerate(messages, start=1):
        message.index = index
    return messages


def _extract_task_dispatches(content: str) -> list[tuple[str, str]]:
    """Extract Task tool dispatches from JSONL content."""
    dispatches: list[tuple[str, str]] = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue

        timestamp = entry.get("timestamp")
        if not timestamp:
            continue

        content_items = entry.get("message", {}).get("content", [])
        if not isinstance(content_items, list):
            continue

        for item in content_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use" or item.get("name") != "Task":
                continue
            subagent_type = item.get("input", {}).get("subagent_type", "")
            dispatches.append((timestamp, subagent_type))
    return dispatches
