from __future__ import annotations

import re
import sys
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..console import UnicodeSafePager, get_console, print_error
from ..formatting import (
    format_to_raw,
    format_to_xml,
    print_metadata,
    render_message_inner_xml,
    render_messages_with_rich,
)
from ..model import (
    ConversationFlags,
    ConversationMetadata,
    Message,
    Provider,
    SearchOutputMode,
)
from ..ordering import sort_by_modified_descending
from ..pool_filter import PoolFilter
from ..session_pool import SessionPool
from ..session_scan import SessionScan
from . import resolve
from .common import _build_tool_id_map


@dataclass
class SearchHit:
    """One matched conversation ready for ordered display."""

    metadata: ConversationMetadata
    messages: list[Message]
    matches: list[Message]
    cwd: str | None
    matching_summaries: list[str]
    matching_custom_titles: list[str]
    last_custom_title: str | None


_RENDER_DEPENDENT_SEARCH_TOKENS = ("<", '="', "```", "old_string:", "new_string:")
_REGEX_META_CHARACTERS = frozenset(".^$*+?{}[]\\|()")


def _display_messages_for_hit(
    messages: list[Message],
    matches: list[Message],
    output_mode: SearchOutputMode,
) -> list[Message]:
    """Return the message list that should be rendered for one search hit."""
    return messages if output_mode == SearchOutputMode.FULL else matches


def display_search_result(
    conv_file: Path,
    messages: list[Message],
    matches: list[Message],
    cwd: str | None,
    flags: ConversationFlags,
    *,
    output_mode: SearchOutputMode,
    emit_metadata: bool,
    provider: Provider | None = None,
    forked_from: str | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
    matching_summaries: list[str] | None = None,
    matching_custom_titles: list[str] | None = None,
    last_custom_title: str | None = None,
) -> None:
    """Display a single search result in unified XML format."""
    if output_mode == SearchOutputMode.ONLY_ID:
        print(resolve.get_display_session_id(conv_file))
        return

    if emit_metadata:
        match_count = (
            len(matches)
            + (len(matching_summaries) if matching_summaries else 0)
            + (len(matching_custom_titles) if matching_custom_titles else 0)
        )
        is_list_output = output_mode == SearchOutputMode.LIST
        print_metadata(
            conv_file,
            cwd,
            len(messages),
            match_count,
            matching_summaries,
            provider=provider,
            forked_from=forked_from,
            last_custom_title=last_custom_title,
            created_at=created_at,
            modified_at=modified_at,
            color=flags.color,
            dedupe_frontmatter_separators=is_list_output,
            include_frontmatter_separator=not is_list_output,
        )

    if output_mode == SearchOutputMode.LIST:
        return

    display_messages = _display_messages_for_hit(messages, matches, output_mode)
    if not display_messages:
        return

    tool_id_map = _build_tool_id_map(messages)
    if flags.color:
        render_messages_with_rich(display_messages, flags, tool_id_map)
        return

    print(format_to_xml(display_messages, flags, tool_id_map))
    print()


def cmd_search(
    pattern_arg: str,
    flags: ConversationFlags,
    pool_filter: PoolFilter | None = None,
    *,
    output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
    output_format: str = "xml",
    emit_metadata: bool = True,
) -> None:
    """Handle the search subcommand."""
    pool_filter = pool_filter or PoolFilter()
    literal_candidate = None

    try:
        regex = re.compile(pattern_arg, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if _is_plain_literal_search_pattern(pattern_arg):
            literal_candidate = pattern_arg.casefold()
    except re.error:
        regex = re.compile(
            re.escape(pattern_arg),
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        literal_candidate = pattern_arg.casefold()

    pool = SessionPool.discover(include_sidechains=flags.show_agents)
    candidate_files = pool_filter.candidate_files(pool)
    if not candidate_files:
        sys.exit(1)

    candidate_file_set = set(candidate_files)
    search_files = [
        session_file
        for session_file in reversed(pool.stat_mtime_sorted)
        if session_file in candidate_file_set
    ]

    hits: list[SearchHit] = []
    for conv_file in search_files:
        try:
            hit = _search_hit_for_file(
                conv_file,
                regex,
                pattern_arg,
                literal_candidate,
                flags,
                pool_filter,
            )
        except Exception as error:
            print_error(f"Error processing conversation file {conv_file}: {error}")
            continue
        if hit is not None:
            hits.append(hit)

    if not hits:
        sys.exit(1)

    ordered_hits = sort_by_modified_descending(
        hits,
        modified_at=lambda hit: hit.metadata.mtime,
    )
    if output_format == "raw":
        raw_output = _format_search_hits_to_raw(ordered_hits, flags, output_mode)
        if raw_output:
            print(raw_output)
        sys.exit(0)

    pager_ctx = (
        nullcontext()
        if output_mode == SearchOutputMode.ONLY_ID or not flags.paging
        else get_console().pager(pager=UnicodeSafePager(), styles=True)
    )

    with pager_ctx:
        for hit in ordered_hits:
            metadata = hit.metadata
            if output_mode != SearchOutputMode.ONLY_ID:
                get_console().rule(
                    title=f"[bold white]{resolve.get_display_session_id(metadata.path)}[/]",
                    style="#00ffba",
                )
            display_search_result(
                metadata.path,
                hit.messages,
                hit.matches,
                hit.cwd,
                flags,
                output_mode=output_mode,
                emit_metadata=emit_metadata,
                provider=metadata.provider,
                forked_from=metadata.forked_from,
                created_at=metadata.ctime,
                modified_at=metadata.mtime,
                matching_summaries=hit.matching_summaries,
                matching_custom_titles=hit.matching_custom_titles,
                last_custom_title=hit.last_custom_title,
            )

    sys.exit(0)


def _format_search_hits_to_raw(
    hits: list[SearchHit],
    flags: ConversationFlags,
    output_mode: SearchOutputMode,
) -> str:
    """Render search hits as plain raw markdown."""
    rendered_sessions: list[tuple[str, str]] = []
    total_visible_messages = 0

    for hit in hits:
        display_messages = _display_messages_for_hit(
            hit.messages,
            hit.matches,
            output_mode,
        )
        if not display_messages:
            continue

        tool_id_map = _build_tool_id_map(hit.messages)
        body = format_to_raw(display_messages, flags, tool_id_map)
        if not body:
            continue

        total_visible_messages += len(display_messages)
        session_label = f"Session {resolve.get_display_session_id(hit.metadata.path)}"
        rendered_sessions.append((session_label, body))

    if not rendered_sessions:
        return ""
    if len(rendered_sessions) == 1 and total_visible_messages == 1:
        return rendered_sessions[0][1]

    return "\n\n---\n\n".join(
        f"{label}\n{'=' * len(label)}\n\n{body}"
        for label, body in rendered_sessions
    )


def _search_hit_for_file(
    conv_file: Path,
    regex: re.Pattern,
    pattern_arg: str,
    literal_candidate: str | None,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
) -> SearchHit | None:
    """Return one search hit with metadata, or None when the file should not be shown."""
    if pool_filter.has_date_filters() and not pool_filter.passes_path_for_date(
        conv_file
    ):
        return None
    if pool_filter.needs_content_for_dir() and not pool_filter.passes_path_for_index(
        conv_file
    ):
        return None

    content = conv_file.read_text(encoding="utf-8")
    if not _search_candidate_matches(content, pattern_arg, literal_candidate, flags):
        return None

    result = _search_conversation_content(conv_file, content, regex, flags, pool_filter)
    if result is None:
        return None

    (
        messages,
        matches,
        cwd,
        matching_summaries,
        matching_custom_titles,
        last_custom_title,
    ) = result
    if not (matches or matching_summaries or matching_custom_titles):
        return None

    return SearchHit(
        metadata=resolve._load_conversation_metadata(conv_file),
        messages=messages,
        matches=matches,
        cwd=cwd,
        matching_summaries=matching_summaries,
        matching_custom_titles=matching_custom_titles,
        last_custom_title=last_custom_title,
    )


def _search_candidate_matches(
    content: str,
    pattern_arg: str,
    literal_candidate: str | None,
    flags: ConversationFlags,
) -> bool:
    """Return True when raw content is a plausible superset match candidate."""
    if any(token in pattern_arg for token in _RENDER_DEPENDENT_SEARCH_TOKENS):
        return True
    if literal_candidate is None:
        return True
    if literal_candidate in content.casefold():
        return True

    markers: list[str] = []
    if flags.show_thinking:
        markers.append("thinking")
    if flags.show_tools or flags.show_plans:
        markers.append("tool-input")
    if flags.show_tools:
        markers.append("tool-output")
    if flags.show_plans:
        markers.append("ExitPlanMode")

    return any(literal_candidate in marker.casefold() for marker in markers)


def _is_plain_literal_search_pattern(pattern: str) -> bool:
    """Return True when a search pattern contains no regex metacharacters."""
    return not any(character in _REGEX_META_CHARACTERS for character in pattern)


def _search_conversation_content(
    conv_file: Path,
    content: str,
    regex: re.Pattern,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
) -> (
    tuple[list[Message], list[Message], str | None, list[str], list[str], str | None]
    | None
):
    """Search already-read conversation content."""
    scan = SessionScan.from_content(content, flags, source_path=conv_file)
    messages = list(scan.messages)
    cwd = scan.cwd

    if not pool_filter.passes_cwd(cwd):
        return None

    matching_summaries = [
        summary for summary in scan.summaries if regex.search(summary)
    ]
    matching_custom_titles = (
        [scan.custom_title]
        if scan.custom_title is not None and regex.search(scan.custom_title)
        else []
    )
    tool_id_map = _build_tool_id_map(messages)
    matches = [
        message
        for message in messages
        if regex.search(render_message_inner_xml(message, flags, tool_id_map))
    ]

    return (
        messages,
        matches,
        cwd,
        matching_summaries,
        matching_custom_titles,
        scan.custom_title,
    )
