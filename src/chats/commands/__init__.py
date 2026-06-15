from __future__ import annotations

import sys
from pathlib import Path

from ..console import get_console, print_error
from ..forking import fork_session
from ..formatting import render_message_inner_xml as render_message_inner_xml
from ..model import (
    ConversationFlags,
)
from ..model import (
    ConversationMetadata as ConversationMetadata,
)
from ..model import (
    Message as Message,
)
from ..model import (
    ParseOutputMode as ParseOutputMode,
)
from ..model import (
    Provider as Provider,
)
from ..model import (
    SearchOutputMode as SearchOutputMode,
)
from . import parse as parse
from . import rename as rename
from . import resolve as resolve
from . import rm as rm
from . import search as search
from .parse import (
    _apply_slice_selectors as _apply_slice_selectors,
)
from .parse import (
    _convert_slice_bound as _convert_slice_bound,
)
from .parse import (
    _merge_agent_messages as _merge_agent_messages,
)
from .parse import (
    _normalize_slice_selectors as _normalize_slice_selectors,
)
from .parse import (
    _parse_single_index as _parse_single_index,
)
from .parse import (
    cmd_parse as cmd_parse,
)
from .parse import (
    parse_slice_notation as parse_slice_notation,
)
from .rename import (
    _clean_line as _clean_line,
)
from .rename import (
    _generate_auto_name as _generate_auto_name,
)
from .rename import (
    _parse_auto_session_name as _parse_auto_session_name,
)
from .rename import (
    cmd_rename as cmd_rename,
)
from .resolve import (
    _load_conversation_metadata as _load_conversation_metadata,
)
from .resolve import (
    _print_ambiguous_error as _print_ambiguous_error,
)
from .resolve import (
    _require_file_backed_input as _require_file_backed_input,
)
from .resolve import (
    _resolve_input_content as _resolve_input_content,
)
from .resolve import (
    _resolve_recent_conversation_file as _resolve_recent_conversation_file,
)
from .resolve import (
    _try_resolve_conversation_file as _try_resolve_conversation_file,
)
from .resolve import (
    _write_parse_output as _write_parse_output,
)
from .resolve import (
    find_agent_files_for_session as find_agent_files_for_session,
)
from .resolve import (
    find_all_conversations as find_all_conversations,
)
from .resolve import (
    get_input_content as get_input_content,
)
from .resolve import (
    resolve_conversation_file,
)
from .rm import (
    _collect_session_dirs as _collect_session_dirs,
)
from .rm import (
    _collect_session_files as _collect_session_files,
)
from .rm import (
    _display_rm_preview as _display_rm_preview,
)
from .rm import (
    _execute_removal as _execute_removal,
)
from .rm import (
    _file_meta as _file_meta,
)
from .rm import (
    _filter_history_lines as _filter_history_lines,
)
from .rm import (
    _human_size as _human_size,
)
from .rm import (
    _is_claude_session_path as _is_claude_session_path,
)
from .rm import (
    _line_count as _line_count,
)
from .rm import (
    _render_dir_tree as _render_dir_tree,
)
from .rm import (
    _resolve_session_for_rm as _resolve_session_for_rm,
)
from .rm import (
    cmd_rm as cmd_rm,
)
from .search import (
    SearchHit as SearchHit,
)
from .search import (
    _search_candidate_matches as _search_candidate_matches,
)
from .search import (
    _search_conversation_content as _search_conversation_content,
)
from .search import (
    _search_hit_for_file as _search_hit_for_file,
)
from .search import (
    cmd_search as cmd_search,
)
from .search import (
    display_search_result as display_search_result,
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
