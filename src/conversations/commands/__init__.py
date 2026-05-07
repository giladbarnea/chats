from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..console import get_console, print_error
from ..forking import fork_session
from ..formatting import render_message_inner_xml
from ..model import (
    ConversationFlags,
    ConversationMetadata,
    Message,
    ParseOutputMode,
    Provider,
    SearchOutputMode,
)
from . import parse, rename, resolve, rm, search
from .parse import (
    _apply_slice_selectors,
    _convert_slice_bound,
    _extract_task_dispatches,
    _merge_agent_messages,
    _normalize_slice_selectors,
    _parse_single_index,
    cmd_parse,
    parse_slice_notation,
)
from .rename import _clean_line, _generate_auto_name, _parse_auto_session_name, cmd_rename
from .resolve import (
    _build_conversation_metadata,
    _load_conversation_metadata,
    _order_metadata_by_modified_time,
    _print_ambiguous_error,
    _require_file_backed_input,
    _resolve_input_content,
    _resolve_recent_conversation_file,
    _try_resolve_conversation_file,
    _write_parse_output,
    find_agent_files_for_session,
    find_all_conversations,
    get_input_content,
    resolve_conversation_file,
)
from .rm import (
    _collect_session_dirs,
    _collect_session_files,
    _display_rm_preview,
    _execute_removal,
    _file_meta,
    _filter_history_lines,
    _human_size,
    _is_claude_session_path,
    _line_count,
    _render_dir_tree,
    _resolve_session_for_rm,
    cmd_rm,
)
from .search import (
    SearchHit,
    _is_plain_literal_search_pattern,
    _search_candidate_matches,
    _search_conversation_content,
    _search_hit_for_file,
    cmd_search,
    display_search_result,
)


def cmd_fork(session_id: str, flags: ConversationFlags) -> Path:
    """Fork a supported session into a thinner resumable copy."""
    conv_file = resolve_conversation_file(session_id)
    target_path = fork_session(conv_file, flags)

    console = get_console()
    console.print(
        f"[green]v[/green] Forked [cyan]{conv_file.name}[/cyan] -> [cyan]{target_path.name}[/cyan]"
    )
    return target_path


def cmd_catalog(args: list[str]) -> None:
    """Catalog conversation sessions into sessions.yaml."""
    from ..catalog import catalog_sessions

    try:
        catalog_sessions(args)
    except Exception as error:
        print_error(f"Error executing catalog: {error}")
        sys.exit(1)
