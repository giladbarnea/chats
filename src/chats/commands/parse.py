from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path

from ..console import UnicodeSafePager, get_console, print_error
from ..formatting import (
    build_metadata_text,
    build_session_title,
    format_to_json,
    format_to_raw,
    format_to_xml,
    print_metadata,
    render_message_panels,
)
from ..model import (
    ConversationFlags,
    Message,
    ParseOutputMode,
    SubagentMetadata,
    assign_progressive_shortening,
    messages_from_json_data,
)
from ..parsing import (
    detect_format,
    extract_cwd_from_jsonl,
    extract_latest_custom_title_from_content,
    get_display_session_id,
    parse_jsonl,
    parse_raw_cli_transcript,
)
from ..pool_filter import PoolFilter
from ..xmlmd import messages_from_xmlmd
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


def cmd_parse_json(input_file: Path | None, *, output_format: str = "xml") -> None:
    """Convert between structured parse JSON and XML-tagged Markdown."""
    input_description = "structured JSON" if output_format == "xml" else "XML-tagged Markdown"
    try:
        content = (
            input_file.read_text(encoding="utf-8") if input_file is not None else sys.stdin.read()
        )
        messages = (
            messages_from_json_data(json.loads(content))
            if output_format == "xml"
            else messages_from_xmlmd(content.rstrip("\n"))
        )
        flags = ConversationFlags(
            show_thinking=True,
            show_tools=True,
            show_plans=True,
            color="never",
            paging=False,
        )
        formatter = format_to_xml if output_format == "xml" else format_to_json
        formatted = formatter(messages, flags, _build_tool_id_map(messages))
    except (OSError, TypeError, ValueError) as error:
        print_error(f"Error parsing {input_description}: {error}")
        sys.exit(1)

    if not formatted:
        return
    resolve._write_parse_output(formatted, None)


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
    if output_mode == ParseOutputMode.ONLY_ID:
        try:
            input_file_path = resolve._resolve_input_path(
                input_arg,
                pool_filter=pool_filter,
            )
        except Exception as error:
            print_error(f"Error reading input: {error}.")
            sys.exit(1)
        resolved_path = resolve._require_file_backed_input(
            input_file_path,
            "`--only-id`",
        )
        try:
            session_id = get_display_session_id(resolved_path)
        except ValueError as error:
            print_error(str(error))
            sys.exit(1)
        resolve._write_parse_output(session_id, output_file)
        return

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

    if output_mode == ParseOutputMode.ONLY_METADATA and input_file_path is None:
        resolve._require_file_backed_input(input_file_path, "`--only-metadata`")

    format_type = detect_format(content)
    if format_type == "jsonl":
        try:
            messages = parse_jsonl(content, flags, source_path=input_file_path)
        except ValueError as error:
            print_error(str(error))
            sys.exit(1)
        cwd = extract_cwd_from_jsonl(content)
    else:
        messages = parse_raw_cli_transcript(content, flags)
        cwd = None

    if flags.show_agents and input_file_path and format_type == "jsonl":
        messages = _merge_agent_messages(messages, input_file_path, flags)

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
    assign_progressive_shortening(messages, flags, tool_id_map)

    current_custom_title = (
        extract_latest_custom_title_from_content(content)
        if format_type == "jsonl"
        else None
    )
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
            last_custom_title=current_custom_title,
            created_at=metadata.ctime if metadata else None,
            modified_at=metadata.mtime if metadata else None,
            include_frontmatter_separator=False,
        )
        resolve._write_parse_output(metadata_text, output_file)
        return

    session_title = None
    if (
        emit_metadata
        and input_file_path is not None
        and output_file is None
        and output_format not in {"json", "raw"}
    ):
        if flags.color:
            session_title = build_session_title(
                input_file_path,
                custom_title=current_custom_title,
                cwd=cwd,
                created_at=metadata.ctime,
                modified_at=metadata.mtime,
            )
        else:
            print_metadata(
                input_file_path,
                cwd,
                len(messages),
                provider=metadata.provider,
                forked_from=metadata.forked_from,
                last_custom_title=current_custom_title,
                created_at=metadata.ctime,
                modified_at=metadata.mtime,
                color=flags.metadata_color,
                to_stderr=not flags.color,
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

    pager_ctx = (
        get_console().pager(pager=UnicodeSafePager(), styles=True)
        if flags.paging
        else nullcontext()
    )
    with pager_ctx:
        if session_title is not None:
            get_console().print(session_title)
            get_console().print()
        render_message_panels(messages, flags, tool_id_map)


def _merge_agent_messages(
    messages: list[Message],
    input_file_path: Path,
    flags: ConversationFlags,
) -> list[Message]:
    """Merge subagent transcripts into the main timeline.

    Provider-agnostic: discovery and identity are resolved per adapter. Each
    subagent's messages are stamped with its agent_id, nickname, type, and model,
    and its block is placed at its own dispatch time so late or concurrent agents
    land where they ran instead of clustering at the earliest agent's timestamp.
    """
    session_id = get_display_session_id(input_file_path)
    transcripts = resolve.find_subagent_transcripts(input_file_path, session_id)

    agent_blocks: list[list[Message]] = []
    for transcript in transcripts:
        agent_content = transcript.read_text(encoding="utf-8")
        agent_messages = parse_jsonl(agent_content, flags, source_path=transcript)
        if not agent_messages or not agent_messages[0].timestamp:
            continue

        meta = resolve.read_subagent_metadata(transcript)
        block = _build_subagent_block(agent_messages, meta)
        if block:
            agent_blocks.append(block)

    if not agent_blocks:
        return messages

    merged = _interleave_subagent_blocks(messages, agent_blocks)
    for index, message in enumerate(merged, start=1):
        message.index = index
    return merged


def _interleave_subagent_blocks(
    messages: list[Message], agent_blocks: list[list[Message]]
) -> list[Message]:
    """Merge each contiguous subagent block into the timeline at its own anchor time.

    A block is anchored by its first message's timestamp and emitted just before the
    first main message that does not predate it — the same per-dispatch placement a
    single agent already received, now applied independently per agent so blocks stay
    contiguous and chronologically ordered.
    """
    pending = sorted(agent_blocks, key=lambda block: block[0].timestamp or "")
    merged: list[Message] = []
    for message in messages:
        while pending and message.timestamp and (pending[0][0].timestamp or "") <= message.timestamp:
            merged.extend(pending.pop(0))
        merged.append(message)
    for block in pending:
        merged.extend(block)
    return merged


def _build_subagent_block(
    agent_messages: list[Message], meta: SubagentMetadata
) -> list[Message]:
    """Reframe a subagent transcript for display.

    The initiating prompt (the last user-text message before the agent's first
    reply) becomes a `<subagent-task>` head; the leading prompt/context messages
    are dropped; and every message is stamped with the subagent's identity.
    """
    first_reply = next(
        (index for index, message in enumerate(agent_messages) if message.role != "user"),
        len(agent_messages),
    )
    leading, rest = agent_messages[:first_reply], agent_messages[first_reply:]
    task_text = next((message.text for message in reversed(leading) if message.text), None)

    block: list[Message] = []
    if task_text:
        block.append(
            Message(role="agent", timestamp=leading[0].timestamp, subagent_task=task_text)
        )
    block.extend(rest)

    # Claude carries identity on each message; Codex carries it in metadata. Resolve
    # both so the synthetic task message is stamped consistently with the rest.
    agent_id = meta.agent_id or next(
        (message.agent_id for message in agent_messages if message.agent_id), None
    )
    model = meta.model or next(
        (message.model for message in agent_messages if message.model), None
    )
    for message in block:
        message.agent_id = agent_id
        message.name = meta.name
        message.subagent_type = meta.subagent_type
        message.model = model
    return block
