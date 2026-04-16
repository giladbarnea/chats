from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .console import get_console, print_error
from .date_filters import parse_date_filter
from .forking import fork_session
from .formatting import (
    format_to_json,
    format_to_raw,
    format_to_xml,
    print_metadata,
    render_message_inner_xml,
    render_messages_with_rich,
)
from .utils import collapse_home
from .model import ConversationFlags, ConversationMetadata, Message, Provider
from .ordering import is_single_negative_index, resolve_negative_index, sort_by_modified
from .parsing import (
    detect_format,
    extract_custom_titles_from_content,
    extract_summaries_from_jsonl,
    extract_cwd_from_jsonl,
    get_display_session_id,
    get_jsonl_session_adapter,
    get_native_session_id,
    get_jsonl_timestamps,
    is_sidechain_session_file,
    parse_jsonl,
    parse_raw_cli_transcript,
)
from .session_pool import SessionPool
from .session_scan import SessionScan


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
    """Find all agent files in the same directory that belong to a session."""
    agent_files = []

    for agent_file in conv_file.parent.glob("agent-*.jsonl"):
        try:
            with open(agent_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    entry = json.loads(first_line)
                    if entry.get("sessionId") == session_id:
                        agent_files.append(agent_file)
        except (json.JSONDecodeError, OSError):
            continue

    return agent_files


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

    provider = get_jsonl_session_adapter(conv_file).name
    return ConversationMetadata(conv_file, ctime, mtime, provider=provider)


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
    return order(_load_conversation_metadata(conv_file) for conv_file in conversation_files)


def _resolve_recent_conversation_file(
    identifier: str,
    conversation_files: Sequence[Path],
) -> Path | None:
    """Resolve a negative index like '-1' against globally recent supported sessions."""
    ordered_metadata = _build_conversation_metadata(conversation_files)
    ordered_main_conversations = [
        meta.path for meta in ordered_metadata if not is_sidechain_session_file(meta.path)
    ]
    return resolve_negative_index(identifier, ordered_main_conversations)


def _try_resolve_conversation_file(
    identifier: str,
    conversation_files: Sequence[Path] | None = None,
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
        if recent_path := _resolve_recent_conversation_file(stripped, conversation_files):
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


def _resolve_input_content(input_arg: str | None) -> tuple[str, Path | None]:
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
        content_or_path.strip()
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


def _print_ambiguous_error(identifier: str, matches: list[tuple[Path, str]]) -> None:
    """Print error message for an ambiguous conversation/session identifier."""
    console = get_console()
    console.print("[red]Error: Ambiguous conversation/session identifier[/red]")
    console.print(f"[yellow]'{identifier}'[/yellow] matches multiple sessions:")
    console.print()
    for conv_file, summary in matches:
        console.print(f"  * [cyan]{get_display_session_id(conv_file)}[/cyan]: {summary}")
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
    list_only: bool,
    only_id: bool,
    emit_metadata: bool,
    provider: Provider | None = None,
    created_at: datetime | None = None,
    modified_at: datetime | None = None,
    matching_summaries: list[str] | None = None,
    matching_custom_titles: list[str] | None = None,
    last_custom_title: str | None = None,
) -> None:
    """Display a single search result in unified XML format."""
    if only_id:
        print(get_display_session_id(conv_file))
        return

    if emit_metadata:
        match_count = len(matches) + (len(matching_summaries) if matching_summaries else 0) + (len(matching_custom_titles) if matching_custom_titles else 0)
        print_metadata(
            conv_file,
            cwd,
            len(messages),
            match_count,
            matching_summaries,
            provider=provider,
            last_custom_title=last_custom_title,
            created_at=created_at,
            modified_at=modified_at,
            color=flags.color,
            dedupe_frontmatter_separators=False,
        )

    if list_only:
        return

    if not matches:
        return

    tool_id_map = _build_tool_id_map(messages)

    if flags.color:
        render_messages_with_rich(matches, flags, tool_id_map)
    else:
        print(format_to_xml(matches, flags, tool_id_map))
        print()


def cmd_search(
    pattern_arg: str,
    flags: ConversationFlags,
    list_only: bool,
    only_id: bool = False,
    dir_filter: str | None = None,
    mafter: str | None = None,
    cafter: str | None = None,
    *,
    emit_metadata: bool = True,
    provider_filter: Provider | None = None,
) -> None:
    """Handle search subcommand."""
    mafter_dt = parse_date_filter(mafter)
    cafter_dt = parse_date_filter(cafter)

    # Compile regex (treat invalid regex as literal string like grep -F)
    try:
        regex = re.compile(pattern_arg, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    except re.error:
        regex = re.compile(
            re.escape(pattern_arg), re.IGNORECASE | re.MULTILINE | re.DOTALL
        )

    pool = SessionPool.discover(include_sidechains=flags.show_agents)
    search_files = (
        pool.by_provider[provider_filter]
        if provider_filter is not None
        else pool.files
    )
    if not search_files:
        sys.exit(1)

    hits: list[SearchHit] = []
    for conv_file in search_files:
        try:
            hit = _search_hit_for_file(
                conv_file,
                regex,
                flags,
                dir_filter,
                mafter_dt,
                cafter_dt,
            )
        except Exception as e:
            print_error(f"Error processing conversation file {conv_file}: {e}")
            continue
        if hit is None:
            continue
        hits.append(hit)

    if not hits:
        sys.exit(1)

    ordered_hits = sort_by_modified(hits, modified_at=lambda hit: hit.metadata.mtime)
    pager_ctx = (
        nullcontext()
        if only_id or not flags.paging
        else get_console().pager(styles=True)
    )

    with pager_ctx:
        for hit in ordered_hits:
            meta = hit.metadata
            if not only_id:
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
                list_only=list_only,
                only_id=only_id,
                emit_metadata=emit_metadata,
                provider=meta.provider,
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
    flags: ConversationFlags,
    dir_filter: str | None,
    mafter_dt: datetime | None,
    cafter_dt: datetime | None,
) -> SearchHit | None:
    """Return one search hit with metadata, or None when the file should not be shown."""
    result = _search_conversation(conv_file, regex, flags, dir_filter)
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
    if not _passes_date_filters(metadata, mafter_dt, cafter_dt):
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


def _passes_date_filters(
    meta: ConversationMetadata, mafter_dt: datetime | None, cafter_dt: datetime | None
) -> bool:
    """Check if conversation file passes date filters."""
    if not mafter_dt and not cafter_dt:
        return True

    if mafter_dt:
        if not meta.mtime or meta.mtime < mafter_dt:
            return False
            
    if cafter_dt:
        if not meta.ctime or meta.ctime < cafter_dt:
            return False
            
    return True


def _search_conversation(
    conv_file: Path,
    regex: re.Pattern,
    flags: ConversationFlags,
    dir_filter: str | None,
) -> tuple[list[Message], list[Message], str | None, list[str], list[str], str | None] | None:
    """
    Search a single conversation file.

    Returns tuple of (messages, matches, cwd, matching_summaries, last_custom_title)
    or None if the conversation should be skipped.
    """
    scan = SessionScan.from_file(conv_file, flags)
    messages = list(scan.messages)
    cwd = scan.cwd

    # Apply directory filter
    if dir_filter is not None:
        if cwd is None:
            return None
        try:
            Path(cwd).resolve().relative_to(Path(dir_filter).resolve())
        except ValueError:
            return None

    matching_summaries = [summary for summary in scan.summaries if regex.search(summary)]
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


def cmd_rename(conversation_id: str, new_name: str) -> None:
    """Rename a conversation by appending custom-title and agent-name entries."""
    import time

    new_name = new_name.strip()
    if not new_name:
        print_error("New name cannot be empty.")
        sys.exit(1)

    conv_file = resolve_conversation_file(conversation_id)
    session_id = get_native_session_id(conv_file)

    # Read content to extract project path (cwd) before appending
    content = conv_file.read_text(encoding="utf-8")
    project = extract_cwd_from_jsonl(content) or ""

    custom_title_entry = {
        "type": "custom-title",
        "customTitle": new_name,
        "sessionId": session_id,
    }
    agent_name_entry = {
        "type": "agent-name",
        "agentName": new_name,
        "sessionId": session_id,
    }

    try:
        with open(conv_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(custom_title_entry, separators=(",", ":")) + "\n")
            f.write(json.dumps(agent_name_entry, separators=(",", ":")) + "\n")
    except Exception as e:
        print_error(f"Error writing file: {e}")
        sys.exit(1)

    # Append to global history.jsonl
    history_entry = {
        "display": f"/rename {new_name}",
        "pastedContents": {},
        "timestamp": int(time.time() * 1000),
        "project": project,
        "sessionId": session_id,
    }
    history_file = Path.home() / ".claude" / "history.jsonl"
    try:
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(history_entry, separators=(",", ":")) + "\n")
    except Exception as e:
        print_error(f"Error writing history.jsonl: {e}")

    console = get_console()
    console.print(f"[green]v[/green] Added custom title to [cyan]{conv_file.name}[/cyan]")
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
        dirs_to_remove = _collect_session_dirs(session_uuid, project_dir_name, claude_dir)
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
    console.print("  * A session UUID or identifier (e.g., 5078a7c7-0646-43cc-9412-7e1454a282b4)")
    console.print("  * A file path to a .jsonl file")
    sys.exit(1)


def _collect_session_files(
    conv_file: Path, session_uuid: str, claude_dir: Path
) -> list[Path]:
    """Collect all files associated with a session."""
    files = [conv_file]

    # Agent files
    for agent_file in find_agent_files_for_session(conv_file, session_uuid):
        files.append(agent_file)

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


def cmd_parse(
    flags: ConversationFlags,
    input_arg: str | None,
    slice_str: str | None,
    output_file: Path | None,
    *,
    output_format: str = "xml",
    emit_metadata: bool = True,
) -> None:
    """Handle parse command (default behavior)."""
    try:
        content, input_file_path = _resolve_input_content(input_arg)
    except Exception as e:
        print_error(f"Error reading input: {e}.")
        sys.exit(1)

    if not content.strip():
        print_error("Input is empty.")
        sys.exit(1)

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

    # Apply slice
    start, stop = parse_slice_notation(slice_str)
    if start is not None or stop is not None:
        messages = messages[start:stop]
        if not messages:
            print_error(f"Slice {slice_str} produced no messages.")
            sys.exit(0)

    # Print metadata for XML output
    if (
        emit_metadata
        and input_file_path
        and not output_file
        and output_format not in ("json", "raw")
    ):
        custom_titles = extract_custom_titles_from_content(content) if format_type == "jsonl" else []
        last_custom_title = custom_titles[-1] if custom_titles else None
        metadata = _load_conversation_metadata(input_file_path)

        print_metadata(
            input_file_path,
            cwd,
            len(messages),
            provider=metadata.provider,
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
        print(f"[debug] Wrote formatted conversation to: {output_file}", file=sys.stderr)
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
