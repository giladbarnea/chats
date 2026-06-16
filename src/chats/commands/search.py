from __future__ import annotations

import functools
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from ..console import StreamingPager, get_console, print_error, print_hint
from ..formatting import (
    build_messages_group,
    format_to_raw,
    format_to_xml,
    print_metadata,
    render_message_inner_xml,
    render_messages_with_rich,
)
from ..model import (
    PROVIDERS,
    ConversationFlags,
    ConversationMetadata,
    Message,
    Provider,
    SearchOutputMode,
)
from ..pool_filter import PoolFilter
from ..search_query import SearchQuery, SearchQueryError, SearchTerm, parse_search_query
from ..session_pool import SessionPool
from ..session_scan import SessionScan
from ..utils import age_style, collapse_home, elide_to_width, humanize_age
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

# Border hues cycled per conversation in the colored full/matches view, so the
# persistent left edge of each Panel changes color at every conversation
# boundary — the orientation cue that survives scrolling through `less`.
_CONVERSATION_BORDER_CYCLE: tuple[str, ...] = (
    "#5cc8a8",
    "#9d7cd8",
    "#d8a657",
    "#7aa2f7",
)


def _build_highlight_regex(query: SearchQuery) -> re.Pattern[str] | None:
    """Compile one case-insensitive regex over the query's plain-literal terms.

    Only literal terms are highlighted; regex terms are skipped to avoid greedy
    spans painting half a message. Longer literals first so alternation prefers
    the most specific match.
    """
    literals = sorted(
        {
            term.pattern
            for term in query.iter_terms()
            if term.literal_candidate is not None and term.pattern
        },
        key=len,
        reverse=True,
    )
    if not literals:
        return None
    return re.compile("|".join(re.escape(literal) for literal in literals), re.IGNORECASE)


def _display_messages_for_hit(
    messages: list[Message],
    matches: list[Message],
    output_mode: SearchOutputMode,
) -> list[Message]:
    """Return the message list that should be rendered for one search hit."""
    return messages if output_mode == SearchOutputMode.FULL else matches


def _headline(hit: SearchHit) -> tuple[str, bool]:
    """Return the row headline and whether it is a fallback (not a real title)."""
    if hit.last_custom_title:
        return hit.last_custom_title, False
    if hit.matching_summaries:
        return hit.matching_summaries[0], True
    for message in hit.matches:
        first_line = message.text.strip().splitlines()
        if first_line:
            return first_line[0], True
    return "(untitled session)", True


def _build_search_list_row(
    hit: SearchHit,
    *,
    now: datetime,
    width: int,
    show_provider: bool,
) -> Group:
    """Build one two-line search-list row: bold headline, then a dim facts line."""
    session_id = resolve.get_display_session_id(hit.metadata.path)
    headline, is_fallback = _headline(hit)

    title_line = Text(no_wrap=True, overflow="ellipsis")
    title_line.append("▎ ", style="search.tick")
    title_line.append(
        elide_to_width(headline, max(8, width - 2)),
        style="search.title.fallback" if is_fallback else "search.title",
    )

    match_count = (
        len(hit.matches)
        + len(hit.matching_summaries)
        + len(hit.matching_custom_titles)
    )
    match_word = "match" if match_count == 1 else "matches"
    age_label = humanize_age(hit.metadata.mtime, now) if hit.metadata.mtime else "?"
    provider = hit.metadata.provider

    reserved = (
        len(f" · {session_id}")
        + len(f" · {match_count} {match_word}")
        + len(f" · {age_label}")
    )
    if show_provider:
        reserved += len(f" · {provider}")
    directory = collapse_home(hit.cwd) if hit.cwd else "(unknown directory)"
    directory = elide_to_width(directory, max(16, width - 4 - reserved), where="middle")

    facts_line = Text(no_wrap=True, overflow="ellipsis")
    facts_line.append("  ")
    facts_line.append(directory, style="search.dir")
    if show_provider:
        facts_line.append(" · ", style="search.sep")
        facts_line.append(provider, style="search.label")
    facts_line.append(" · ", style="search.sep")
    facts_line.append(str(match_count), style="search.count")
    facts_line.append(f" {match_word}", style="search.label")
    facts_line.append(" · ", style="search.sep")
    facts_line.append(
        age_label,
        style=age_style(hit.metadata.mtime, now) if hit.metadata.mtime else "search.age.old",
    )
    facts_line.append(" · ", style="search.sep")
    facts_line.append(session_id[:8], style="search.id.head")
    facts_line.append(session_id[8:], style="search.id.tail")

    return Group(title_line, facts_line)


def _list_show_provider(
    pool: SessionPool,
    candidate_file_set: set[Path],
    pool_filter: PoolFilter,
) -> bool:
    """Whether colored list rows should be labeled with their provider.

    Hoisted out of the per-hit loop so rows can stream without first collecting
    every hit: shown when the searched candidate pool spans more than one
    provider and no provider filter already pinned it to a single one.
    """
    if pool_filter.provider is not None:
        return False
    present = {
        provider
        for provider in PROVIDERS
        if candidate_file_set.intersection(pool.by_provider[provider])
    }
    return len(present) > 1


def _display_list_summary(count: int) -> None:
    """Print the colored-list trailing summary line (count known only at the end)."""
    summary = Text()
    summary.append(
        f"{count} session" + ("" if count == 1 else "s"),
        style="search.header",
    )
    summary.append("  ·  newest first", style="search.sep")
    get_console().print(summary)


def _panel_title(hit: SearchHit, *, width: int, now: datetime) -> Text:
    """Build the conversation Panel's border title: tick, headline, short id, age."""
    session_id = resolve.get_display_session_id(hit.metadata.path)
    headline, is_fallback = _headline(hit)
    age_label = humanize_age(hit.metadata.mtime, now) if hit.metadata.mtime else "?"

    title = Text(no_wrap=True, overflow="ellipsis")
    title.append("▎ ", style="search.tick")
    title.append(
        elide_to_width(headline, max(8, width - 24)),
        style="search.title.fallback" if is_fallback else "search.title",
    )
    title.append(f"  ·  {session_id[:8]}", style="search.id.head")
    title.append(
        f"  ·  {age_label}",
        style=age_style(hit.metadata.mtime, now) if hit.metadata.mtime else "search.age.old",
    )
    return title


def _panel_facts_line(hit: SearchHit, *, width: int) -> Text:
    """Build the in-Panel facts line: directory · provider · match count."""
    directory = collapse_home(hit.cwd) if hit.cwd else "(unknown directory)"
    match_count = (
        len(hit.matches)
        + len(hit.matching_summaries)
        + len(hit.matching_custom_titles)
    )
    match_word = "match" if match_count == 1 else "matches"

    line = Text(no_wrap=True, overflow="ellipsis")
    line.append(
        elide_to_width(directory, max(16, width - 28), where="middle"),
        style="search.dir",
    )
    line.append(" · ", style="search.sep")
    line.append(hit.metadata.provider, style="search.label")
    line.append(" · ", style="search.sep")
    line.append(str(match_count), style="search.count")
    line.append(f" {match_word}", style="search.label")
    return line


def _render_conversation_panel(
    hit: SearchHit,
    flags: ConversationFlags,
    output_mode: SearchOutputMode,
    emit_metadata: bool,
    *,
    highlight_regex: re.Pattern[str] | None,
    ordinal: int,
    now: datetime,
) -> None:
    """Render one hit as a titled Panel whose border hue keys off its ordinal."""
    console = get_console()
    session_id = resolve.get_display_session_id(hit.metadata.path)
    border = _CONVERSATION_BORDER_CYCLE[ordinal % len(_CONVERSATION_BORDER_CYCLE)]

    display_messages = _display_messages_for_hit(hit.messages, hit.matches, output_mode)
    body = build_messages_group(
        display_messages,
        flags,
        _build_tool_id_map(hit.messages),
        highlight_regex=highlight_regex,
        conversation_tag=session_id[:8],
        compact_header=True,
    )

    rows: list = []
    if emit_metadata:
        rows.append(_panel_facts_line(hit, width=console.width))
        rows.append(Text(""))
    rows.append(body)

    console.print(
        Panel(
            Group(*rows),
            title=_panel_title(hit, width=console.width, now=now),
            title_align="left",
            border_style=border,
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def _display_hit(
    hit: SearchHit,
    flags: ConversationFlags,
    output_mode: SearchOutputMode,
    emit_metadata: bool,
    *,
    show_provider: bool,
    now: datetime,
    highlight_regex: re.Pattern[str] | None = None,
    ordinal: int = 0,
) -> None:
    """Render one search hit to the module console: id, colored row, or rule+body."""
    metadata = hit.metadata
    if output_mode == SearchOutputMode.ONLY_ID:
        print(resolve.get_display_session_id(metadata.path))
        return

    if output_mode == SearchOutputMode.LIST and flags.color:
        console = get_console()
        console.print(
            _build_search_list_row(
                hit, now=now, width=console.width, show_provider=show_provider
            )
        )
        console.print()
        return

    if flags.color and output_mode in (SearchOutputMode.MATCHES, SearchOutputMode.FULL):
        _render_conversation_panel(
            hit,
            flags,
            output_mode,
            emit_metadata,
            highlight_regex=highlight_regex,
            ordinal=ordinal,
            now=now,
        )
        return

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
    """Handle the search subcommand, streaming results to the terminal as found.

    Hits are displayed in scan order (newest first by filesystem mtime) the
    moment each is confirmed, instead of buffering the whole pool, sorting, then
    paging. `raw` is the one exception: its single-message special case needs
    every hit up front, so it stays buffered.
    """
    pool_filter = pool_filter or PoolFilter()

    try:
        query = parse_search_query(pattern_arg)
    except SearchQueryError as error:
        print_error(str(error))
        sys.exit(2)

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

    def iter_hits() -> Iterable[SearchHit]:
        for conv_file in search_files:
            try:
                hit = _search_hit_for_file(conv_file, query, flags, pool_filter)
            except Exception as error:
                print_error(
                    f"Error processing conversation file {conv_file}: {error}"
                )
                continue
            if hit is not None:
                yield hit

    if output_format == "raw":
        hits = list(iter_hits())
        if not hits:
            _emit_no_results(pattern_arg, pool_filter, output_mode)
        raw_output = _format_search_hits_to_raw(hits, flags, output_mode)
        if raw_output:
            print(raw_output)
        sys.exit(0)

    show_provider = (
        _list_show_provider(pool, candidate_file_set, pool_filter)
        if output_mode == SearchOutputMode.LIST and flags.color
        else False
    )
    _stream_search_results(
        iter_hits(),
        flags,
        output_mode=output_mode,
        emit_metadata=emit_metadata,
        show_provider=show_provider,
        pattern_arg=pattern_arg,
        pool_filter=pool_filter,
        highlight_regex=_build_highlight_regex(query),
    )


def _emit_no_results(
    pattern_arg: str, pool_filter: PoolFilter, output_mode: SearchOutputMode
) -> None:
    """Print the no-match hint (unless id-only) and exit with code 1."""
    if output_mode != SearchOutputMode.ONLY_ID:
        suffix = "" if pool_filter.is_empty() else " with the current filters"
        print_hint(f'No sessions match "{pattern_arg}"{suffix}.')
    sys.exit(1)


def _emit(pager: StreamingPager | None, render: Callable[[], None]) -> None:
    """Render via the module console, routing to the pager or straight to stdout.

    When paging, the hit is rendered into a captured ANSI buffer and written to
    `less` immediately; otherwise it prints directly, which is already
    incremental.
    """
    if pager is None:
        render()
        return
    with get_console().capture() as capture:
        render()
    pager.write(capture.get())


def _stream_search_results(
    hits: Iterable[SearchHit],
    flags: ConversationFlags,
    *,
    output_mode: SearchOutputMode,
    emit_metadata: bool,
    show_provider: bool,
    pattern_arg: str,
    pool_filter: PoolFilter,
    highlight_regex: re.Pattern[str] | None = None,
) -> None:
    """Display search hits incrementally, paging through `less` as they arrive."""
    use_pager = (
        flags.color and flags.paging and output_mode != SearchOutputMode.ONLY_ID
    )
    pager = StreamingPager() if use_pager else None
    now = datetime.now()
    found = 0
    try:
        for hit in hits:
            _emit(
                pager,
                lambda current=hit, ordinal=found: _display_hit(
                    current,
                    flags,
                    output_mode,
                    emit_metadata,
                    show_provider=show_provider,
                    now=now,
                    highlight_regex=highlight_regex,
                    ordinal=ordinal,
                ),
            )
            found += 1
            if pager is not None and pager.closed:
                break
        if (
            output_mode == SearchOutputMode.LIST
            and flags.color
            and found
            and (pager is None or not pager.closed)
        ):
            _emit(pager, lambda: _display_list_summary(found))
    finally:
        if pager is not None:
            pager.close()

    if found == 0:
        _emit_no_results(pattern_arg, pool_filter, output_mode)
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
    query: SearchQuery,
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
    if not _search_candidate_matches(content, query, flags):
        return None

    result = _search_conversation_content(conv_file, content, query, flags, pool_filter)
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
    query: SearchQuery,
    flags: ConversationFlags,
) -> bool:
    """Return True when raw content is a plausible superset match candidate."""
    content_casefolded = functools.cache(content.casefold)
    return query.evaluate(
        lambda term: _term_candidate_matches(content_casefolded, term, flags)
    )


def _term_candidate_matches(
    content_casefolded: Callable[[], str],
    term: SearchTerm,
    flags: ConversationFlags,
) -> bool:
    """Return True when raw content could plausibly satisfy one search term."""
    if any(token in term.pattern for token in _RENDER_DEPENDENT_SEARCH_TOKENS):
        return True
    if term.literal_candidate is None:
        return True
    if term.literal_candidate in content_casefolded():
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

    return any(term.literal_candidate in marker.casefold() for marker in markers)


def _search_conversation_content(
    conv_file: Path,
    content: str,
    query: SearchQuery,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
) -> (
    tuple[list[Message], list[Message], str | None, list[str], list[str], str | None]
    | None
):
    """Search already-read conversation content.

    The boolean query is evaluated session-wide: each term is satisfied by a
    match anywhere in the session (summaries, current title, or any rendered
    message), so `and` terms may match in different messages.
    """
    scan = SessionScan.from_content(content, flags, source_path=conv_file)
    messages = list(scan.messages)
    cwd = scan.cwd

    if not pool_filter.passes_cwd(cwd):
        return None

    tool_id_map = _build_tool_id_map(messages)
    rendered_messages = [
        (message, render_message_inner_xml(message, flags, tool_id_map))
        for message in messages
    ]

    def term_matches_session(term: SearchTerm) -> bool:
        return (
            any(term.regex.search(summary) for summary in scan.summaries)
            or (
                scan.custom_title is not None
                and bool(term.regex.search(scan.custom_title))
            )
            or any(term.regex.search(rendered) for _, rendered in rendered_messages)
        )

    if not query.evaluate(term_matches_session):
        return None

    terms = list(query.iter_terms())
    matching_summaries = [
        summary
        for summary in scan.summaries
        if any(term.regex.search(summary) for term in terms)
    ]
    matching_custom_titles = (
        [scan.custom_title]
        if scan.custom_title is not None
        and any(term.regex.search(scan.custom_title) for term in terms)
        else []
    )
    matches = [
        message
        for message, rendered in rendered_messages
        if any(term.regex.search(rendered) for term in terms)
    ]

    return (
        messages,
        matches,
        cwd,
        matching_summaries,
        matching_custom_titles,
        scan.custom_title,
    )
