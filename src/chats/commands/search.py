from __future__ import annotations

import functools
import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
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
)
from ..model import (
    PROVIDERS,
    ConversationFlags,
    ConversationMetadata,
    Message,
    MessageSelection,
    Provider,
    SearchOutputMode,
)
from ..parsing import (
    _extract_antigravity_user_text,
    _extract_codex_text_blocks,
    _extract_custom_title_from_entry,
    _extract_text_blocks,
    _filter_hidden_user_text_blocks,
    _is_codex_preamble_text,
    get_jsonl_session_adapter,
)
from ..pool_filter import PoolFilter
from ..search_query import AndQuery, NotQuery, OrQuery, SearchQuery, SearchQueryError, SearchTerm, parse_search_query
from ..session_pool import SessionPool
from ..session_scan import SessionScan
from ..utils import age_style, collapse_home, elide_to_width, humanize_age
from . import resolve
from .common import _build_tool_id_map


def _total_match_count(
    matches: list[Message],
    matching_summaries: list[str],
    matching_custom_titles: list[str],
) -> int:
    """Total matches for a hit: matched messages + summaries + custom titles.

    >>> _total_match_count([], ["summary"], ["title-a", "title-b"])
    3
    """
    return len(matches) + len(matching_summaries) + len(matching_custom_titles)


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

    @property
    def match_count(self) -> int:
        """Total matches across messages, summaries, and custom titles."""
        return _total_match_count(
            self.matches, self.matching_summaries, self.matching_custom_titles
        )


_RENDER_DEPENDENT_SEARCH_TOKENS = ("<", '="', "```", "old_string:", "new_string:")
_ASCII_SCAN_CHUNK_SIZE = 1024 * 1024


class _ProjectionResult(Enum):
    MATCH = "match"
    NO_MATCH = "no-match"
    UNKNOWN = "unknown"


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

    match_count = hit.match_count
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
    """Build the conversation Panel's border title: tick, headline, full id, age."""
    session_id = resolve.get_display_session_id(hit.metadata.path)
    headline, is_fallback = _headline(hit)
    age_label = humanize_age(hit.metadata.mtime, now) if hit.metadata.mtime else "?"
    metadata_suffix_width = len(f"  ·  {session_id}  ·  {age_label}")

    title = Text(no_wrap=True, overflow="ellipsis")
    title.append("▎ ", style="search.tick")
    title.append(
        elide_to_width(headline, max(8, width - 2 - metadata_suffix_width)),
        style="search.title.fallback" if is_fallback else "search.title",
    )
    title.append("  ·  ", style="search.sep")
    title.append(session_id[:8], style="search.id.head")
    title.append(session_id[8:], style="search.id.tail")
    title.append("  ·  ", style="search.sep")
    title.append(
        age_label,
        style=age_style(hit.metadata.mtime, now) if hit.metadata.mtime else "search.age.old",
    )
    return title


def _panel_facts_line(hit: SearchHit, *, width: int) -> Text:
    """Build the in-Panel facts line: directory · provider · match count."""
    directory = collapse_home(hit.cwd) if hit.cwd else "(unknown directory)"
    match_count = hit.match_count
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
        match_count = _total_match_count(
            matches, matching_summaries or [], matching_custom_titles or []
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

    if _can_project_dot_only_id(query, flags, pool_filter, output_mode, output_format):
        _stream_dot_only_id_projection(search_files, query, flags, pool_filter)

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


def _can_project_dot_only_id(
    query: SearchQuery,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
    output_mode: SearchOutputMode,
    output_format: str,
) -> bool:
    """Whether the narrow `search . -ll` projection may replace full scanning."""
    return (
        output_mode == SearchOutputMode.ONLY_ID
        and output_format != "raw"
        and isinstance(query, SearchTerm)
        and query.pattern == "."
        and flags.message_selection == MessageSelection.ALL
        and not flags.show_thinking
        and not flags.show_tools
        and not flags.show_agents
        and not flags.show_branches
        and not flags.show_plans
        and not flags.shorten
        and not flags.shorten_thinking
        and not pool_filter.has_date_filters()
        and not pool_filter.needs_content_for_dir()
    )


def _stream_dot_only_id_projection(
    search_files: list[Path],
    query: SearchQuery,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
) -> None:
    """Stream ids for the narrow default-visibility `search . -ll` fast path."""
    found = False
    for session_file in search_files:
        result = _project_default_dot_match(session_file)
        if result == _ProjectionResult.MATCH:
            print(resolve.get_display_session_id(session_file))
            found = True
            continue
        if result == _ProjectionResult.NO_MATCH:
            continue

        try:
            hit = _search_hit_for_file(session_file, query, flags, pool_filter)
        except Exception as error:
            print_error(f"Error processing conversation file {session_file}: {error}")
            continue
        if hit is None:
            continue
        print(resolve.get_display_session_id(hit.metadata.path))
        found = True

    sys.exit(0 if found else 1)


def _project_default_dot_match(session_file: Path) -> _ProjectionResult:
    """Project whether default search for `.` would find any visible facet/content.

    Claude default visibility depends on branch resolution this projection does not
    replicate, so Claude files always defer to the full search path.
    """
    adapter = get_jsonl_session_adapter(session_file)
    if adapter.name == "claude":
        return _ProjectionResult.UNKNOWN

    try:
        with open(session_file, "r", encoding="utf-8") as handle:
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
                if _entry_has_default_visible_search_facet(entry, adapter.name):
                    return _ProjectionResult.MATCH
    except OSError:
        return _ProjectionResult.UNKNOWN

    return _ProjectionResult.NO_MATCH


def _entry_has_default_visible_search_facet(entry: dict, provider: Provider) -> bool:
    """Return True when an entry contributes to default visible search for `.`."""
    if entry.get("type") == "summary":
        summary = entry.get("summary")
        return isinstance(summary, str) and bool(summary.strip())
    if _extract_custom_title_from_entry(entry):
        return True
    if provider == "pi":
        return _pi_entry_has_default_visible_text(entry)
    if provider == "codex":
        return _codex_entry_has_default_visible_text(entry)
    if provider == "antigravitycli":
        return _antigravity_entry_has_default_visible_text(entry)
    return False


def _pi_entry_has_default_visible_text(entry: dict) -> bool:
    if entry.get("type") != "message":
        return False
    message = entry.get("message", {})
    role = message.get("role")
    if role not in {"user", "assistant"}:
        return False
    text_blocks = _extract_text_blocks(message.get("content", []))
    if role == "user":
        text_blocks = _filter_hidden_user_text_blocks(text_blocks)
    return any(text.strip() for text in text_blocks)


def _codex_entry_has_default_visible_text(entry: dict) -> bool:
    if entry.get("type") != "response_item":
        return False
    payload = entry.get("payload", {})
    if payload.get("type") != "message":
        return False
    role = payload.get("role")
    if role == "user":
        return any(
            text.strip() and not _is_codex_preamble_text(text)
            for text in _filter_hidden_user_text_blocks(
                _extract_codex_text_blocks(payload.get("content"))
            )
        )
    if role == "assistant":
        return any(
            text.strip() for text in _extract_codex_text_blocks(payload.get("content"))
        )
    return False


def _antigravity_entry_has_default_visible_text(entry: dict) -> bool:
    entry_type = entry.get("type")
    if entry_type == "USER_INPUT":
        return bool(_extract_antigravity_user_text(entry.get("content")).strip())
    if entry_type == "PLANNER_RESPONSE":
        content = entry.get("content")
        return isinstance(content, str) and bool(content.strip())
    return False


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
    if not _search_path_candidate_matches(conv_file, query, flags):
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


def _evaluate_prefilter(
    query: SearchQuery,
    term_matches: Callable[[SearchTerm], bool],
) -> bool:
    """Conservative boolean evaluation where NotQuery always passes."""
    if isinstance(query, NotQuery):
        return True
    if isinstance(query, AndQuery):
        return all(_evaluate_prefilter(operand, term_matches) for operand in query.operands)
    if isinstance(query, OrQuery):
        return any(_evaluate_prefilter(operand, term_matches) for operand in query.operands)
    return term_matches(query)


def _search_path_candidate_matches(
    path: Path,
    query: SearchQuery,
    flags: ConversationFlags,
) -> bool:
    """Return True when a file's bytes could plausibly satisfy the query."""
    return _evaluate_prefilter(query, lambda term: _term_path_candidate_matches(path, term, flags))


def _term_path_candidate_matches(
    path: Path,
    term: SearchTerm,
    flags: ConversationFlags,
) -> bool:
    """Conservatively reject ASCII literal terms absent from raw file bytes."""
    if _term_can_match_generated_marker(term, flags):
        return True
    needle = _ascii_literal_needle(term)
    if needle is None:
        return True
    return _file_contains_ascii_case_insensitive(path, needle)


def _ascii_literal_needle(term: SearchTerm) -> bytes | None:
    """Return an ASCII byte-search needle for safely probeable literal terms."""
    if any(token in term.pattern for token in _RENDER_DEPENDENT_SEARCH_TOKENS):
        return None
    if term.literal_candidate is None:
        return None
    if not term.pattern.isascii():
        return None
    return term.literal_candidate.encode("ascii")


def _file_contains_ascii_case_insensitive(path: Path, needle: bytes) -> bool:
    """Search a file for an ASCII literal using chunked byte reads.

    Sound only over ASCII bytes: a non-ASCII source character can case-fold to the
    ASCII needle (U+212A KELVIN SIGN -> 'k'), which `bytes.lower()` would not catch.
    Any non-ASCII byte therefore makes this gate defer to the decode-based content
    gate rather than risk rejecting a real hit.
    """
    if not needle:
        return True

    overlap_width = len(needle) - 1
    previous = b""
    with open(path, "rb") as handle:
        while chunk := handle.read(_ASCII_SCAN_CHUNK_SIZE):
            if not chunk.isascii():
                return True
            haystack = previous + chunk
            if needle in haystack.lower():
                return True
            previous = haystack[-overlap_width:] if overlap_width else b""
    return False


def _search_candidate_matches(
    content: str,
    query: SearchQuery,
    flags: ConversationFlags,
) -> bool:
    """Return True when raw content is a plausible superset match candidate."""
    content_casefolded = functools.cache(content.casefold)
    return _evaluate_prefilter(
        query, lambda term: _term_candidate_matches(content_casefolded, term, flags)
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
    if not term.pattern.isascii():
        return True
    if term.literal_candidate in content_casefolded():
        return True
    return _term_can_match_generated_marker(term, flags)


def _term_can_match_generated_marker(term: SearchTerm, flags: ConversationFlags) -> bool:
    """Return True when a literal could match renderer-generated marker text."""
    if term.literal_candidate is None:
        return False

    markers: list[str] = []
    if flags.show_thinking:
        markers.append("thinking")
    if flags.show_tools or flags.show_plans:
        markers.append("tool-input")
    if flags.show_tools:
        markers.append("tool-output")
        # AdditionalContext is a rendered tool name absent from the raw JSONL
        # (synthesized from hook attachments), so it needs the same escape hatch.
        markers.append("AdditionalContext")
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
