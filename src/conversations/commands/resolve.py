from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from pathlib import Path

from ..console import get_console, print_error
from ..model import ConversationMetadata
from ..ordering import is_single_negative_index, resolve_negative_index, sort_by_modified
from ..parsing import (
    extract_resolution_facets_from_jsonl,
    get_display_session_id,
    get_jsonl_session_adapter,
    get_jsonl_timestamps,
    is_sidechain_session_file,
)
from ..pool_filter import PoolFilter
from ..session_pool import SessionPool


ConversationMetadataOrder = Callable[
    [Iterable[ConversationMetadata]],
    list[ConversationMetadata],
]


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
            with open(agent_file, "r", encoding="utf-8") as handle:
                first_line = handle.readline().strip()
            if not first_line:
                continue
            entry = json.loads(first_line)
            if entry.get("sessionId") == session_id:
                agent_files.append(agent_file)
        except (json.JSONDecodeError, OSError):
            continue

    return sorted(agent_files)


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
    return order(_load_conversation_metadata(conv_file) for conv_file in conversation_files)


def _resolve_recent_conversation_file(
    identifier: str,
    conversation_files: Sequence[Path],
    pool_filter: PoolFilter | None = None,
) -> Path | None:
    """Resolve a negative index like '-1' against globally recent supported sessions."""
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
    for metadata in ordered_metadata:
        if is_sidechain_session_file(metadata.path):
            continue
        if pool_filter is not None and not pool_filter.passes_metadata(metadata):
            continue
        eligible.append(metadata.path)

    if pool_filter is not None and pool_filter.needs_content_for_dir():
        eligible = pool_filter.narrow_for_index(eligible)

    return resolve_negative_index(identifier, eligible)


def _try_resolve_conversation_file(
    identifier: str,
    conversation_files: Sequence[Path] | None = None,
    pool_filter: PoolFilter | None = None,
) -> tuple[Path | None, list[tuple[Path, str]]]:
    """Try to resolve a conversation/session identifier to a file path."""
    stripped = identifier.strip()

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
        recent_path = _resolve_recent_conversation_file(
            stripped,
            recent_files,
            pool_filter,
        )
        if recent_path is not None:
            return recent_path, []

    exact_match = pool.resolve_exact_identifier(stripped)
    if exact_match is not None:
        return exact_match, []

    query_lower = stripped.lower()
    title_matches: list[tuple[Path, str]] = []
    summary_matches: list[tuple[Path, str]] = []
    for conversation_file in conversation_files:
        current_title, summaries = extract_resolution_facets_from_jsonl(
            conversation_file
        )
        if current_title is not None and query_lower in current_title.lower():
            title_matches.append((conversation_file, current_title))
            continue
        for summary in summaries:
            if summary.lower().startswith(query_lower):
                summary_matches.append((conversation_file, summary))
                break

    if len(title_matches) == 1:
        return title_matches[0][0], []
    if len(title_matches) > 1:
        return None, title_matches

    if len(stripped) >= 32 and "-" in stripped:
        return None, []

    if len(summary_matches) == 1:
        return summary_matches[0][0], []
    if len(summary_matches) > 1:
        return None, summary_matches
    return None, []


def _print_ambiguous_error(identifier: str, matches: list[tuple[Path, str]]) -> None:
    """Print an error message for an ambiguous conversation/session identifier."""
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
    """Resolve a conversation/session identifier to a file path."""
    resolved_path, ambiguous_matches = _try_resolve_conversation_file(conversation_id)
    if resolved_path is not None:
        return resolved_path

    if ambiguous_matches:
        _print_ambiguous_error(conversation_id, ambiguous_matches)
        sys.exit(1)

    console = get_console()
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

    resolved_path, ambiguous_matches = _try_resolve_conversation_file(
        content_or_path.strip(),
        pool_filter=pool_filter,
    )
    if resolved_path is not None:
        return resolved_path.read_text(encoding="utf-8"), resolved_path

    if ambiguous_matches:
        _print_ambiguous_error(content_or_path.strip(), ambiguous_matches)
        sys.exit(1)

    return content_or_path, None


def get_input_content(input_arg: str | None) -> str:
    """Get input content from a CLI argument or stdin."""
    content, _ = _resolve_input_content(input_arg)
    return content


def _require_file_backed_input(input_file_path: Path | None, mode_name: str) -> Path:
    """Require a resolved session/file path for identity-dependent output modes."""
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
        print(f"[debug] Wrote formatted conversation to: {output_file}", file=sys.stderr)
        return
    print(output)
