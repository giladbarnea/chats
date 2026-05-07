from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .console import get_console, print_error
from .forking import fork_session
from .formatting import (
    build_metadata_text,
    format_to_json,
    format_to_raw,
    format_to_xml,
    print_metadata,
    render_message_inner_xml,
    render_messages_with_rich,
)
from .model import (
    ConversationFlags,
    ConversationMetadata,
    Message,
    ParseOutputMode,
    Provider,
    SearchOutputMode,
)
from .ordering import (
    is_single_negative_index,
    resolve_negative_index,
    sort_by_modified,
    sort_by_modified_descending,
)
from .parsing import (
    decode_jsonl_entries,
    detect_format,
    extract_custom_titles_from_content,
    extract_cwd_from_jsonl,
    extract_summaries_from_jsonl,
    get_display_session_id,
    get_jsonl_session_adapter,
    get_jsonl_timestamps,
    get_native_session_id,
    is_sidechain_session_file,
    parse_jsonl,
    parse_raw_cli_transcript,
)
from .pool_filter import PoolFilter
from .session_pool import SessionPool
from .session_scan import SessionScan
from .utils import collapse_home


def _build_tool_id_map(messages: list[Message]) -> dict[str, str]:
    """Build a map of tool ID to tool name from all messages."""
    tool_id_map = {}
    for msg in messages:
        for tool in msg.tools:
            if tool.get("type") == "tool_use" and "id" in tool:
                tool_id_map[tool["id"]] = tool.get("name", "Unknown")
    return tool_id_map


def find_all_conversations(projects_dir: Path) -> Iterable[Path]:
    """Find all .jsonl conversation files in the projects directory."""
    if not projects_dir.exists():
        raise FileNotFoundError(f"Projects directory does not exist: {projects_dir}")

    return projects_dir.glob("*/*.jsonl")


def find_agent_files_for_session(conv_file: Path, session_id: str) -> list[Path]:
    """Find all Claude agent files belonging to a session."""
    agent_files: list[Path] = []
    search_dir = conv_file.parent / session_id / "subagents"

    for agent_file in search_dir.glob("agent-*.jsonl"):
        try:
            with open(agent_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    entry = json.loads(first_line)
                    if entry.get("sessionId") == session_id:
                        agent_files.append(agent_file)
        except (json.JSONDecodeError, OSError):
            continue

    return sorted(agent_files)


ConversationMetadataOrder = Callable[
    [Iterable[ConversationMetadata]],
    list[ConversationMetadata],
]


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


def _load_conversation_metadata(conv_file: Path) -> ConversationMetadata:
    """Load created/modified timestamps for a conversation file."""
    ctime, mtime = get_jsonl_timestamps(conv_file)

    if ctime is None or mtime is None:
        try:
            stat = conv_file.stat()
            if ctime is None:
                ctime = datetime.fromtimestamp(stat.st_birthtime)
            if mtime is None:
                mtime = datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            pass

    adapter = get_jsonl_session_adapter(conv_file)
    return ConversationMetadata(
        conv_file,
        ctime,
        mtime,
        provider=adapter.name,
        forked_from=adapter.extract_forked_from(conv_file),
    )


def _order_metadata_by_modified_time(
    metadata_items: Iterable[ConversationMetadata],
) -> list[ConversationMetadata]:
    """Order conversation metadata from oldest to newest by mtime."""
    return sort_by_modified(metadata_items, modified_at=lambda item: item.mtime)


def _build_conversation_metadata(
    conversation_files: Iterable[Path],
    *,
    order: ConversationMetadataOrder = _order_metadata_by_modified_time,
) -> list[ConversationMetadata]:
    """Build ordered metadata for conversation files."""
    return order(
        _load_conversation_metadata(conv_file) for conv_file in conversation_files
    )


def _resolve_recent_conversation_file(
    identifier: str,
    conversation_files: Sequence[Path],
    pool_filter: PoolFilter | None = None,
) -> Path | None:
    """Resolve a negative index like '-1' against globally recent supported sessions.

    When `pool_filter` is provided, dir/date filters narrow the candidate set
    before applying the index.
    """
    if pool_filter is not None and pool_filter.needs_content_for_dir():
        if pool_filter.mafter_dt is None and pool_filter.cafter_dt is None:
            remaining_matches = abs(int(identifier))
            newest_first_paths = sorted(
                conversation_files,
                key=lambda candidate: candidate.stat().st_mtime,
                reverse=True,
            )
            for path in newest_first_paths:
                if is_sidechain_session_file(path):
                    continue
                if not pool_filter.passes_path_for_index(path):
                    continue
                remaining_matches -= 1
                if remaining_matches == 0:
                    return path
            return None

    ordered_metadata = _build_conversation_metadata(conversation_files)
    eligible: list[Path] = []
    for meta in ordered_metadata:
        if is_sidechain_session_file(meta.path):
            continue
        if pool_filter is not None and not pool_filter.passes_metadata(meta):
            continue
        eligible.append(meta.path)
    if pool_filter is not None and pool_filter.needs_content_for_dir():
        eligible = pool_filter.narrow_for_index(eligible)
    return resolve_negative_index(identifier, eligible)


def _try_resolve_conversation_file(
    identifier: str,
    conversation_files: Sequence[Path] | None = None,
    pool_filter: PoolFilter | None = None,
) -> tuple[Path | None, list[tuple[Path, str]]]:
    """
    Try to resolve a conversation/session identifier to a file path.

    Resolution order:
    1. Direct file path (if exists)
    2. Recent negative index (e.g. -1 for the most recently modified supported session)
    3. UUID exact match (single-word only)
    4. Summary prefix match (case-insensitive)

    Returns:
        Tuple of (resolved_path, ambiguous_matches):
        - If exactly one match: (Path, [])
        - If ambiguous: (None, [(path, summary), ...])
        - If not found: (None, [])
    """
    stripped = identifier.strip()

    # Try direct file path
    try:
        path = Path(stripped)
        if path.exists() and path.is_file():
            return path, []
    except (OSError, ValueError):
        pass

    pool = (
        SessionPool.discover()
        if conversation_files is None
        else SessionPool.from_files(conversation_files)
    )
    conversation_files = pool.files

    if is_single_negative_index(stripped):
        recent_files = (
            pool_filter.candidate_files(pool)
            if pool_filter is not None
            else conversation_files
        )
        if recent_path := _resolve_recent_conversation_file(
            stripped, recent_files, pool_filter
        ):
            return recent_path, []

    if exact_match := pool.resolve_exact_identifier(stripped):
        return exact_match, []

    # If it's a UUID-like identifier that didn't match, don't fallback to scanning all file summaries
    if len(stripped) >= 32 and "-" in stripped:
        return None, []

    # Try matching by summary prefix
    query_lower = stripped.lower()
    matches = []
    for conv_file in conversation_files:
        for summary in extract_summaries_from_jsonl(conv_file):
            if summary.lower().startswith(query_lower):
                matches.append((conv_file, summary))
                break  # Only count each file once

    if len(matches) == 1:
        return matches[0][0], []
    if len(matches) > 1:
        return None, matches

    return None, []


def _resolve_input_content(
    input_arg: str | None,
    *,
    pool_filter: PoolFilter | None = None,
) -> tuple[str, Path | None]:
    """Resolve CLI input to raw content and its backing session path, if any."""
    if input_arg:
        content_or_path = input_arg
    elif sys.stdin.isatty():
        print(
            "Error: No input provided. Provide a file path, raw content, or pipe to stdin.",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        content_or_path = sys.stdin.read()

    # Try to resolve as conversation file
    resolved_path, ambiguous_matches = _try_resolve_conversation_file(
        content_or_path.strip(),
        pool_filter=pool_filter,
    )
    if resolved_path:
        return resolved_path.read_text(encoding="utf-8"), resolved_path

    if ambiguous_matches:
        _print_ambiguous_error(content_or_path.strip(), ambiguous_matches)
        sys.exit(1)

    return content_or_path, None


def get_input_content(input_arg: str | None) -> str:
    """Get input content from CLI argument or stdin."""
    content, _ = _resolve_input_content(input_arg)
    return content


def _require_file_backed_input(input_file_path: Path | None, mode_name: str) -> Path:
    """Require a resolved session/file path for output modes that depend on metadata or ids."""
    if input_file_path is not None:
        return input_file_path

    print_error(
        f"{mode_name} requires a resolved session or file-backed input; "
        "raw stdin/content has no stable session identity."
    )
    sys.exit(1)


def _write_parse_output(output: str, output_file: Path | None) -> None:
    """Write parse output either to stdout or an explicit output file."""
    if output_file is not None:
        output_file.write_text(output + "\n", encoding="utf-8")
        print(
            f"[debug] Wrote formatted conversation to: {output_file}", file=sys.stderr
        )
        return

    print(output)


def _print_ambiguous_error(identifier: str, matches: list[tuple[Path, str]]) -> None:
    """Print error message for an ambiguous conversation/session identifier."""
    console = get_console()
    console.print("[red]Error: Ambiguous conversation/session identifier[/red]")
    console.print(f"[yellow]'{identifier}'[/yellow] matches multiple sessions:")
    console.print()
    for conv_file, summary in matches:
        console.print(
            f"  * [cyan]{get_display_session_id(conv_file)}[/cyan]: {summary}"
        )
    console.print()
    console.print("[dim]Use a more specific prefix or the full UUID[/dim]")


def resolve_conversation_file(conversation_id: str) -> Path:
    """
    Resolve a conversation/session identifier to a file path.

    Resolution order:
    1. Direct file path (if exists)
    2. Recent negative index (e.g. -1 for the most recently modified supported session)
    3. UUID exact match (single-word only)
    4. Summary prefix match (case-insensitive)
    """
    resolved_path, ambiguous_matches = _try_resolve_conversation_file(conversation_id)

    if resolved_path:
        return resolved_path

    console = get_console()

    if ambiguous_matches:
        _print_ambiguous_error(conversation_id, ambiguous_matches)
        sys.exit(1)

    # Not found
    console.print(
        f"[red]Error: Conversation/session not found: [yellow]{conversation_id}[/yellow][/red]"
    )
    console.print()
    console.print("[dim]Try one of:[/dim]")
    console.print("  * A Claude/Codex/PI session identifier or filename")
    console.print(
        "  * A recent negative index (e.g., -1 for the most recent supported session)"
    )
    console.print("  * A summary prefix (e.g., 'Locate SFTP')")
    console.print("  * A file path to a .jsonl file")
    sys.exit(1)


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
        print(get_display_session_id(conv_file))
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

    display_messages = messages if output_mode == SearchOutputMode.FULL else matches

    if not display_messages:
        return

    tool_id_map = _build_tool_id_map(messages)

    if flags.color:
        render_messages_with_rich(display_messages, flags, tool_id_map)
    else:
        print(format_to_xml(display_messages, flags, tool_id_map))
        print()


def cmd_search(
    pattern_arg: str,
    flags: ConversationFlags,
    pool_filter: PoolFilter | None = None,
    *,
    output_mode: SearchOutputMode = SearchOutputMode.MATCHES,
    emit_metadata: bool = True,
) -> None:
    """Handle search subcommand."""
    pool_filter = pool_filter or PoolFilter()
    literal_candidate = None

    # Compile regex (treat invalid regex as literal string like grep -F)
    try:
        regex = re.compile(pattern_arg, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if _is_plain_literal_search_pattern(pattern_arg):
            literal_candidate = pattern_arg.casefold()
    except re.error:
        regex = re.compile(
            re.escape(pattern_arg), re.IGNORECASE | re.MULTILINE | re.DOTALL
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
        except Exception as e:
            print_error(f"Error processing conversation file {conv_file}: {e}")
            continue
        if hit is None:
            continue
        hits.append(hit)

    if not hits:
        sys.exit(1)

    ordered_hits = sort_by_modified_descending(
        hits,
        modified_at=lambda hit: hit.metadata.mtime,
    )
    pager_ctx = (
        nullcontext()
        if output_mode == SearchOutputMode.ONLY_ID or not flags.paging
        else get_console().pager(styles=True)
    )

    with pager_ctx:
        for hit in ordered_hits:
            meta = hit.metadata
            if output_mode != SearchOutputMode.ONLY_ID:
                get_console().rule(
                    title=f"[bold white]{get_display_session_id(meta.path)}[/]",
                    style="#00ffba",
                )
            display_search_result(
                meta.path,
                hit.messages,
                hit.matches,
                hit.cwd,
                flags,
                output_mode=output_mode,
                emit_metadata=emit_metadata,
                provider=meta.provider,
                forked_from=meta.forked_from,
                created_at=meta.ctime,
                modified_at=meta.mtime,
                matching_summaries=hit.matching_summaries,
                matching_custom_titles=hit.matching_custom_titles,
                last_custom_title=hit.last_custom_title,
            )

    sys.exit(0)


def _search_hit_for_file(
    conv_file: Path,
    regex: re.Pattern,
    pattern_arg: str,
    literal_candidate: str | None,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
) -> SearchHit | None:
    """Return one search hit with metadata, or None when the file should not be shown."""
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

    metadata = _load_conversation_metadata(conv_file)
    if not pool_filter.passes_metadata(metadata):
        return None

    return SearchHit(
        metadata=metadata,
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


def _search_conversation(
    conv_file: Path,
    regex: re.Pattern,
    flags: ConversationFlags,
    pool_filter: PoolFilter,
) -> (
    tuple[list[Message], list[Message], str | None, list[str], list[str], str | None]
    | None
):
    """
    Search a single conversation file.

    Returns tuple of (messages, matches, cwd, matching_summaries, last_custom_title)
    or None if the conversation should be skipped.
    """
    content = conv_file.read_text(encoding="utf-8")
    return _search_conversation_content(conv_file, content, regex, flags, pool_filter)


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
    matching_custom_titles = [
        custom_title
        for custom_title in scan.custom_titles
        if regex.search(custom_title)
    ]

    tool_id_map = _build_tool_id_map(messages)

    matches = [
        msg
        for msg in messages
        if regex.search(render_message_inner_xml(msg, flags, tool_id_map))
    ]

    return (
        messages,
        matches,
        cwd,
        matching_summaries,
        matching_custom_titles,
        scan.last_custom_title,
    )


_AUTO_NAME_MAX_LENGTH = 150
_AUTO_NAME_PROMPT = (
    "Name this session. The format is <session's working directory's name> "
    "[verb] <One phrase expressing the purpose of the session in its entirety — "
    "the end state the user wants to achieve>.\n"
        "Clarification about `[verb]`: a single lowercase word pinning down the type of the session’s task.")


def _clean_line(line: str) -> str:
    """Strip surrounding quotes/backticks, trim whitespace, and truncate to max length.

    >>> _clean_line('  "hello"  ')
    'hello'
    """
    line = line.strip()
    line = re.sub(r'^["\`\']+|["\`\']+$', "", line)
    return line[:_AUTO_NAME_MAX_LENGTH].strip()


def _parse_auto_session_name(output_text: str, cwd_name: str) -> str:
    """Parse LLM output into a session name. Mirrors auto-session-name.ts parseSessionNameOutput.

    Raises ValueError when output cannot be reduced to a single usable name.
    """
    output_lines = [
        cleaned
        for raw in _clean_line(output_text).split("\n")
        if (cleaned := _clean_line(raw))
    ]

    if not output_lines:
        raise ValueError("model returned empty output")

    if len(output_lines) == 1:
        picked = output_lines[0]
    elif len(output_lines) == 2 and output_lines[0].endswith(":"):
        picked = output_lines[1]
    else:
        raise ValueError(
            f"could not pick a session name from model output:\n{output_text}"
        )

    if picked.lower() == cwd_name.lower():
        raise ValueError(
            f"refusing useless session name (same as cwd):\n{output_text}"
        )

    return picked


def _generate_auto_name(conv_file: Path, content: str) -> str:
    """Call pi to generate a session name from the conversation transcript."""
    flags = ConversationFlags(
        show_thinking=False,
        show_tools=False,
        show_agents=False,
        show_plans=False,
        shorten=False,
        color=False,
        paging=False,
    )

    format_type = detect_format(content)
    if format_type == "jsonl":
        messages = parse_jsonl(content, flags, source_path=conv_file)
        cwd = extract_cwd_from_jsonl(content)
    else:
        messages = parse_raw_cli_transcript(content, flags)
        cwd = None

    transcript = format_to_xml(messages, flags, _build_tool_id_map(messages))
    cwd_name = Path(cwd).name if cwd else conv_file.parent.parent.name

    prompt = (
        f"<transcript-of-session-to-name>\n{transcript}\n</transcript-of-session-to-name>"
        f"\n\n===\n\n"
        f"<task>\n{_AUTO_NAME_PROMPT}\n\nThe session working directory name is: {cwd_name}\n</task>"
    )

    try:
        result = subprocess.run(
            [
                "pi",
                "--model", "google/gemini-3-flash-preview",
                "--no-skills", "--no-session", "--offline", "--no-themes",
                "--no-prompt-templates", "--no-extensions",
                "--print",
                "--system-prompt", prompt,
                "Follow the task instructions.",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"pi process failed: {e}") from e
    except FileNotFoundError:
        raise RuntimeError("'pi' command not found. Ensure it is installed and in PATH.")

    return _parse_auto_session_name(result.stdout, cwd_name)


def cmd_rename(conversation_id: str, new_name: str | None, *, auto: bool = False) -> None:
    """Rename a conversation by appending the provider-native session-title entry."""
    import time

    if new_name is not None and auto:
        print_error("Cannot specify both a new name and --auto.")
        sys.exit(1)
    if new_name is None and not auto:
        print_error("Either provide a new name or use --auto to generate one.")
        sys.exit(1)
    if not auto:
        new_name = (new_name or "").strip()
        if not new_name:
            print_error("New name cannot be empty.")
            sys.exit(1)

    conv_file = resolve_conversation_file(conversation_id)
    adapter = get_jsonl_session_adapter(conv_file)
    session_id = get_native_session_id(conv_file)

    content = conv_file.read_text(encoding="utf-8")
    project = extract_cwd_from_jsonl(content) or ""
    entries = decode_jsonl_entries(content)

    if auto:
        try:
            new_name = _generate_auto_name(conv_file, content)
        except (RuntimeError, ValueError) as e:
            print_error(f"Auto-naming failed: {e}")
            sys.exit(1)

    assert new_name is not None

    try:
        rename_entries = adapter.build_rename_entries(entries, session_id, new_name)
    except ValueError as error:
        print_error(str(error))
        sys.exit(1)

    try:
        with open(conv_file, "a", encoding="utf-8") as handle:
            handle.writelines(
                json.dumps(rename_entry, separators=(",", ":")) + "\n"
                for rename_entry in rename_entries
            )
    except Exception as error:
        print_error(f"Error writing file: {error}")
        sys.exit(1)

    if adapter.writes_claude_history:
        history_entry = {
            "display": f"/rename {new_name}",
            "pastedContents": {},
            "timestamp": int(time.time() * 1000),
            "project": project,
            "sessionId": session_id,
        }
        history_file = Path.home() / ".claude" / "history.jsonl"
        try:
            with open(history_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(history_entry, separators=(",", ":")) + "\n")
        except Exception as error:
            print_error(f"Error writing history.jsonl: {error}")

    console = get_console()
    console.print(f"[green]v[/green] Renamed [cyan]{conv_file.name}[/cyan]")
    console.print(f"  [dim]Title:[/dim] [bold]{new_name}[/bold]")


def cmd_fork(session_id: str, flags: ConversationFlags) -> Path:
    """Fork a supported session into a thinner resumable copy."""
    conv_file = resolve_conversation_file(session_id)
    target_path = fork_session(conv_file, flags)

    console = get_console()
    console.print(
        f"[green]v[/green] Forked [cyan]{conv_file.name}[/cyan] -> [cyan]{target_path.name}[/cyan]"
    )
    return target_path


def _is_claude_session_path(conv_file: Path) -> bool:
    """Return True when conv_file is under ~/.claude/."""
    claude_dir = Path.home() / ".claude"
    try:
        conv_file.resolve().relative_to(claude_dir.resolve())
        return True
    except (ValueError, OSError):
        return False


def cmd_rm(session_id: str, *, dry_run: bool = False) -> None:
    """Remove a conversation session and all associated files."""
    conv_file = _resolve_session_for_rm(session_id)
    session_uuid = get_display_session_id(conv_file)
    project_dir_name = conv_file.parent.name
    claude_dir = Path.home() / ".claude"

    is_claude = _is_claude_session_path(conv_file)

    # Collect paths to remove
    if is_claude:
        files_to_remove = _collect_session_files(conv_file, session_uuid, claude_dir)
        dirs_to_remove = _collect_session_dirs(
            session_uuid, project_dir_name, claude_dir
        )
        filtered_lines, history_lines_to_remove = _filter_history_lines(
            claude_dir / "history.jsonl", session_uuid
        )
    else:
        files_to_remove = [conv_file]
        dirs_to_remove = []
        filtered_lines = None
        history_lines_to_remove = 0

    # Display what will be removed (always show preview)
    _display_rm_preview(
        session_uuid,
        project_dir_name,
        files_to_remove,
        dirs_to_remove,
        history_lines_to_remove,
        claude_dir,
        preview_mode=True,
    )

    console = get_console()

    # If dry run, exit without prompting
    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    # Ask for confirmation
    console.print()
    try:
        response = input("Proceed with removal? [y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled[/yellow]")
        sys.exit(0)

    if response != "y":
        console.print("[yellow]Cancelled[/yellow]")
        sys.exit(0)

    # Execute removal
    history_file = claude_dir / "history.jsonl" if is_claude else None
    removed_files, removed_dirs = _execute_removal(
        files_to_remove, dirs_to_remove, filtered_lines, history_file
    )

    console.print(
        f"\n[green]v[/green] Removed session [cyan]{session_uuid}[/cyan]: "
        f"{removed_files} files, {removed_dirs} directories, {history_lines_to_remove} history entries"
    )


def _resolve_session_for_rm(session_id: str) -> Path:
    """Resolve session identifier to file path via the shared resolver."""
    stripped = session_id.strip()
    console = get_console()

    resolved_path, ambiguous_matches = _try_resolve_conversation_file(stripped)
    if resolved_path:
        return resolved_path

    if ambiguous_matches:
        _print_ambiguous_error(stripped, ambiguous_matches)
        sys.exit(1)

    # Not found
    console.print(f"[red]Error: Session not found: [yellow]{session_id}[/yellow][/red]")
    console.print()
    console.print("[dim]Provide:[/dim]")
    console.print(
        "  * A session UUID or identifier (e.g., 5078a7c7-0646-43cc-9412-7e1454a282b4)"
    )
    console.print("  * A file path to a .jsonl file")
    sys.exit(1)


def _collect_session_files(
    conv_file: Path, session_uuid: str, claude_dir: Path
) -> list[Path]:
    """Collect all files associated with a session."""
    files = [conv_file]

    # Agent files
    files.extend(find_agent_files_for_session(conv_file, session_uuid))

    # Debug and todos
    files.append(claude_dir / "debug" / f"{session_uuid}.txt")
    files.append(claude_dir / "todos" / f"{session_uuid}-agent-{session_uuid}.json")

    return files


def _collect_session_dirs(
    session_uuid: str, project_dir_name: str, claude_dir: Path
) -> list[Path]:
    """Collect all directories associated with a session."""
    return [
        claude_dir / "file-history" / session_uuid,
        claude_dir / "projects" / project_dir_name / session_uuid,
        claude_dir / "session-env" / session_uuid,
    ]


def _filter_history_lines(
    history_file: Path, session_uuid: str
) -> tuple[list[str] | None, int]:
    """Filter history.jsonl to remove lines for session. Returns (filtered_lines, removed_count)."""
    if not history_file.exists():
        return None, 0

    try:
        lines = history_file.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as e:
        print_error(f"Error reading history.jsonl: {e}")
        return None, 0

    filtered = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered.append(line)
            continue

        try:
            entry = json.loads(stripped)
            if entry.get("sessionId") == session_uuid:
                removed += 1
            else:
                filtered.append(line)
        except json.JSONDecodeError:
            filtered.append(line)

    return filtered, removed


def _human_size(size_bytes: int) -> str:
    """Format byte count as human-readable size with commas for large numbers."""
    if size_bytes < 1024:
        return f"{size_bytes:,} B"
    elif size_bytes < 1024 * 1024:
        kb = size_bytes / 1024
        return f"{kb:,.1f} KB"
    else:
        mb = size_bytes / (1024 * 1024)
        return f"{mb:,.1f} MB"


def _line_count(path: Path) -> int:
    """Count lines in a file."""
    try:
        return sum(1 for _ in open(path, "rb"))
    except OSError:
        return 0


def _file_meta(path: Path) -> str:
    """Return human-readable metadata string for a file."""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    parts = [_human_size(size)]
    lines = _line_count(path)
    if lines:
        suffix = path.suffix.lower()
        label = "messages" if suffix == ".jsonl" else "lines"
        parts.append(f"{lines:,} {label}")
    return ", ".join(parts)


def _render_dir_tree(base: Path, claude_dir: Path) -> list[str]:
    """Render a recursive ASCII tree of directory contents with file metadata."""
    lines: list[str] = []

    def _walk(directory: Path, prefix: str) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda e: e.name)
        except OSError:
            return
        dirs = [e for e in entries if e.is_dir()]
        files = [e for e in entries if e.is_file()]
        items = files + dirs
        for i, entry in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            if entry.is_file():
                meta = _file_meta(entry)
                lines.append(f"{prefix}{connector}{entry.name}  [dim]({meta})[/dim]")
            else:
                lines.append(f"{prefix}{connector}{entry.name}/")
                extension = "    " if is_last else "│   "
                _walk(entry, prefix + extension)

    _walk(base, "      ")
    return lines


def _display_rm_preview(
    session_uuid: str,
    project_dir_name: str,
    files: list[Path],
    dirs: list[Path],
    history_lines: int,
    claude_dir: Path,
    preview_mode: bool = True,
) -> None:
    """Display preview of what will be removed."""
    console = get_console()

    console.print(f"\n[bold]Session:[/bold] [cyan]{session_uuid}[/cyan]")
    console.print(f"[bold]Project:[/bold] [dim]{project_dir_name}[/dim]\n")

    existing_files = [f for f in files if f.exists()]
    missing_files = [f for f in files if not f.exists()]
    existing_dirs = [d for d in dirs if d.exists()]
    missing_dirs = [d for d in dirs if not d.exists()]

    if existing_files:
        console.print("[bold]Files to remove:[/bold]")
        for f in existing_files:
            meta = _file_meta(f)
            meta_str = f"  [dim]({meta})[/dim]" if meta else ""
            console.print(f"  [red]x[/red] {collapse_home(str(f))}{meta_str}")

    if missing_files and preview_mode:
        console.print("\n[dim]Files not found (will be skipped):[/dim]")
        for f in missing_files:
            console.print(f"  [dim]  {collapse_home(str(f))}[/dim]")

    if existing_dirs:
        console.print("\n[bold]Directories to remove:[/bold]")
        for d in existing_dirs:
            console.print(f"  [red]x[/red] {collapse_home(str(d))}/")
            for tree_line in _render_dir_tree(d, claude_dir):
                console.print(tree_line)

    if missing_dirs and preview_mode:
        console.print("\n[dim]Directories not found (will be skipped):[/dim]")
        for d in missing_dirs:
            console.print(f"  [dim]  {collapse_home(str(d))}/[/dim]")

    if history_lines > 0:
        console.print(
            f"\n[bold]History entries to remove:[/bold] {history_lines} lines from history.jsonl"
        )


def _execute_removal(
    files: list[Path],
    dirs: list[Path],
    filtered_history: list[str] | None,
    history_file: Path | None,
) -> tuple[int, int]:
    """Execute file and directory removal. Returns (removed_files, removed_dirs)."""
    import shutil

    removed_files = 0
    removed_dirs = 0

    for f in files:
        if f.exists():
            try:
                f.unlink()
                removed_files += 1
            except OSError as e:
                print_error(f"Error removing {f}: {e}")

    for d in dirs:
        if d.exists():
            try:
                shutil.rmtree(d)
                removed_dirs += 1
            except OSError as e:
                print_error(f"Error removing {d}: {e}")

    if filtered_history is not None and history_file is not None:
        try:
            history_file.write_text("".join(filtered_history), encoding="utf-8")
        except OSError as e:
            print_error(f"Error writing history.jsonl: {e}")

    return removed_files, removed_dirs


def parse_slice_notation(slice_str: str | None) -> tuple[int | None, int | None]:
    """
    Parse 1-indexed slice notation into 0-indexed Python slice bounds.

    Examples:
        "1" -> (0, 1)       # First message
        "-1" -> (-1, None)  # Last message
        "2:" -> (1, None)   # From second to end
        ":-2" -> (None, -2) # All except last 2
        "2:4" -> (1, 3)     # Messages 2 and 3
    """
    if not slice_str:
        return (None, None)

    # Single index
    if ":" not in slice_str:
        return _parse_single_index(slice_str)

    # Range
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
    """Handle parse command (default behavior)."""
    try:
        content, input_file_path = _resolve_input_content(
            input_arg,
            pool_filter=pool_filter,
        )
    except Exception as e:
        print_error(f"Error reading input: {e}.")
        sys.exit(1)

    if not content.strip():
        print_error("Input is empty.")
        sys.exit(1)

    if output_mode == ParseOutputMode.ONLY_ID:
        resolved_path = _require_file_backed_input(input_file_path, "`--only-id`")
        _write_parse_output(get_display_session_id(resolved_path), output_file)
        return

    if output_mode == ParseOutputMode.ONLY_METADATA and input_file_path is None:
        _require_file_backed_input(input_file_path, "`--only-metadata`")

    # Parse conversation
    format_type = detect_format(content)
    if format_type == "jsonl":
        messages = parse_jsonl(content, flags, source_path=input_file_path)
        cwd = extract_cwd_from_jsonl(content)
    else:
        messages = parse_raw_cli_transcript(content, flags)
        cwd = None

    # Load agent files if enabled
    if flags.show_agents and input_file_path and format_type == "jsonl":
        messages = _merge_agent_messages(messages, content, input_file_path, flags)

    if not messages:
        if flags.allow_empty_output:
            return
        print_error("No messages found in input.")
        sys.exit(0)

    # Build tool_id_map before slicing so tool-output tags retain their name
    # even when the corresponding tool-input message is sliced out.
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
    metadata = _load_conversation_metadata(input_file_path) if input_file_path else None

    if output_mode == ParseOutputMode.ONLY_METADATA:
        resolved_path = _require_file_backed_input(input_file_path, "`--only-metadata`")
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
        _write_parse_output(metadata_text, output_file)
        return

    # Print metadata for XML output
    if (
        emit_metadata
        and input_file_path
        and not output_file
        and output_format not in ("json", "raw")
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

    # Format output
    if output_format == "json":
        formatted = format_to_json(messages, flags, tool_id_map)
    elif output_format == "raw":
        formatted = format_to_raw(messages, flags, tool_id_map)
    else:
        formatted = format_to_xml(messages, flags, tool_id_map)

    if not formatted:
        return

    # Emit output
    if output_file:
        output_file.write_text(formatted + "\n", encoding="utf-8")
        print(
            f"[debug] Wrote formatted conversation to: {output_file}", file=sys.stderr
        )
    elif output_format in ("json", "raw"):
        print(formatted)
    elif flags.color:
        pager_ctx = get_console().pager(styles=True) if flags.paging else nullcontext()
        with pager_ctx:
            render_messages_with_rich(messages, flags, tool_id_map)
    else:
        print(formatted)


def _merge_agent_messages(
    messages: list[Message],
    content: str,
    input_file_path: Path,
    flags: ConversationFlags,
) -> list[Message]:
    """Merge agent messages into main conversation timeline."""
    session_id = get_display_session_id(input_file_path)
    agent_files = find_agent_files_for_session(input_file_path, session_id)

    # Extract Task tool dispatches (timestamp -> subagent_type)
    task_dispatches = _extract_task_dispatches(content)

    # Load and match agent messages
    all_agent_messages = []
    for agent_file in agent_files:
        try:
            agent_content = agent_file.read_text(encoding="utf-8")
            agent_messages = parse_jsonl(agent_content, flags, source_path=agent_file)
            if not agent_messages or not agent_messages[0].timestamp:
                continue

            first_ts = agent_messages[0].timestamp
            matched_subagent_type = None
            for dispatch_ts, subagent_type in task_dispatches:
                if first_ts > dispatch_ts:
                    matched_subagent_type = subagent_type

            if matched_subagent_type is not None:
                for msg in agent_messages:
                    msg.subagent_type = matched_subagent_type
                all_agent_messages.extend(agent_messages)
        except Exception:
            continue

    if not all_agent_messages:
        return messages

    # Sort and insert
    all_agent_messages.sort(key=lambda m: m.timestamp or "")
    first_agent_ts = all_agent_messages[0].timestamp
    insert_idx = 0
    for i, msg in enumerate(messages):
        if msg.timestamp and msg.timestamp < first_agent_ts:
            insert_idx = i + 1

    messages[insert_idx:insert_idx] = all_agent_messages

    # Re-index
    for i, msg in enumerate(messages, start=1):
        msg.index = i

    return messages


def _extract_task_dispatches(content: str) -> list[tuple[str, str]]:
    """Extract Task tool dispatches from JSONL content."""
    dispatches = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("type") != "assistant":
                continue
            ts = entry.get("timestamp")
            if not ts:
                continue
            content_items = entry.get("message", {}).get("content", [])
            if not isinstance(content_items, list):
                continue
            for item in content_items:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "tool_use"
                    and item.get("name") == "Task"
                ):
                    subagent_type = item.get("input", {}).get("subagent_type", "")
                    dispatches.append((ts, subagent_type))
        except json.JSONDecodeError:
            continue
    return dispatches


def cmd_catalog(args: list[str]) -> None:
    """Catalog conversation sessions into sessions.yaml."""
    from .catalog import catalog_sessions

    try:
        catalog_sessions(args)
    except Exception as e:
        print_error(f"Error executing catalog: {e}")
        sys.exit(1)
