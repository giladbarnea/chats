from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from ..console import get_console, print_error
from ..parsing import get_display_session_id, get_jsonl_session_adapter
from ..utils import collapse_home
from . import resolve


def cmd_rm(session_id: str, *, dry_run: bool = False) -> None:
    """Remove a conversation session and all associated files."""
    conv_file = _resolve_session_for_rm(session_id)
    try:
        session_uuid = get_display_session_id(conv_file)
    except ValueError as error:
        print_error(str(error))
        sys.exit(1)
    project_dir_name = conv_file.parent.name
    claude_dir = Path.home() / ".claude"
    is_claude = get_jsonl_session_adapter(conv_file).name == "claude"

    if is_claude:
        files_to_remove = _collect_session_files(conv_file, session_uuid, claude_dir)
        dirs_to_remove = _collect_session_dirs(session_uuid, project_dir_name, claude_dir)
        filtered_lines, history_lines_to_remove = _filter_history_lines(
            claude_dir / "history.jsonl",
            session_uuid,
        )
    else:
        files_to_remove = [conv_file]
        dirs_to_remove = []
        filtered_lines = None
        history_lines_to_remove = 0

    _display_rm_preview(
        session_uuid,
        project_dir_name,
        files_to_remove,
        dirs_to_remove,
        history_lines_to_remove,
    )

    console = get_console()
    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    console.print()
    try:
        response = input("Proceed with removal? [y/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelled[/yellow]")
        sys.exit(0)

    if response != "y":
        console.print("[yellow]Cancelled[/yellow]")
        sys.exit(0)

    history_file = claude_dir / "history.jsonl" if is_claude else None
    removed_files, removed_dirs = _execute_removal(
        files_to_remove,
        dirs_to_remove,
        filtered_lines,
        history_file,
    )
    console.print(
        f"\n[green]v[/green] Removed session [cyan]{session_uuid}[/cyan]: "
        f"{removed_files} files, {removed_dirs} directories, {history_lines_to_remove} history entries"
    )


def _resolve_session_for_rm(session_id: str) -> Path:
    """Resolve a session identifier to a file path via the shared resolver."""
    stripped = session_id.strip()
    resolved_path, ambiguous_matches = resolve._try_resolve_conversation_file(stripped)
    if resolved_path is not None:
        return resolved_path

    if ambiguous_matches:
        resolve._print_ambiguous_error(stripped, ambiguous_matches)
        sys.exit(1)

    console = get_console()
    console.print(f"[red]Error: Session not found: [yellow]{session_id}[/yellow][/red]")
    console.print()
    console.print("[dim]Provide:[/dim]")
    console.print(
        "  * A session UUID or identifier (e.g., 5078a7c7-0646-43cc-9412-7e1454a282b4)"
    )
    console.print("  * A file path to a .jsonl file")
    sys.exit(1)


def _collect_session_files(
    conv_file: Path,
    session_uuid: str,
    claude_dir: Path,
) -> list[Path]:
    """Collect all files associated with a session."""
    files = [conv_file]
    files.extend(resolve.find_agent_files_for_session(conv_file, session_uuid))
    files.append(claude_dir / "debug" / f"{session_uuid}.txt")
    files.append(claude_dir / "todos" / f"{session_uuid}-agent-{session_uuid}.json")
    return files


def _collect_session_dirs(
    session_uuid: str,
    project_dir_name: str,
    claude_dir: Path,
) -> list[Path]:
    """Collect all directories associated with a session."""
    return [
        claude_dir / "file-history" / session_uuid,
        claude_dir / "projects" / project_dir_name / session_uuid,
        claude_dir / "session-env" / session_uuid,
    ]


def _filter_history_lines(
    history_file: Path,
    session_uuid: str,
) -> tuple[list[str] | None, int]:
    """Filter history.jsonl to remove lines for a session."""
    if not history_file.exists():
        return None, 0

    try:
        lines = history_file.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as error:
        print_error(f"Error reading history.jsonl: {error}")
        return None, 0

    filtered: list[str] = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered.append(line)
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            filtered.append(line)
            continue

        if entry.get("sessionId") == session_uuid:
            removed += 1
        else:
            filtered.append(line)

    return filtered, removed


def _human_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes:,} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:,.1f} KB"
    return f"{size_bytes / (1024 * 1024):,.1f} MB"


def _line_count(path: Path) -> int:
    """Count lines in a file."""
    try:
        return sum(1 for _ in open(path, "rb"))
    except OSError:
        return 0


def _file_meta(path: Path) -> str:
    """Return a human-readable metadata string for a file."""
    try:
        size = path.stat().st_size
    except OSError:
        return ""

    parts = [_human_size(size)]
    lines = _line_count(path)
    if lines:
        label = "messages" if path.suffix.lower() == ".jsonl" else "lines"
        parts.append(f"{lines:,} {label}")
    return ", ".join(parts)


def _render_dir_tree(base: Path) -> list[str]:
    """Render a recursive ASCII tree of directory contents with file metadata."""
    lines: list[str] = []

    def walk(directory: Path, prefix: str) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError:
            return

        directories = [entry for entry in entries if entry.is_dir()]
        files = [entry for entry in entries if entry.is_file()]
        items = files + directories
        for index, entry in enumerate(items):
            is_last = index == len(items) - 1
            connector = "└── " if is_last else "├── "
            if entry.is_file():
                meta = _file_meta(entry)
                lines.append(f"{prefix}{connector}{entry.name}  [dim]({meta})[/dim]")
                continue

            lines.append(f"{prefix}{connector}{entry.name}/")
            extension = "    " if is_last else "│   "
            walk(entry, prefix + extension)

    walk(base, "      ")
    return lines


def _display_rm_preview(
    session_uuid: str,
    project_dir_name: str,
    files: list[Path],
    dirs: list[Path],
    history_lines: int,
) -> None:
    """Display a preview of what will be removed."""
    console = get_console()
    console.print(f"\n[bold]Session:[/bold] [cyan]{session_uuid}[/cyan]")
    console.print(f"[bold]Project:[/bold] [dim]{project_dir_name}[/dim]\n")

    existing_files = [path for path in files if path.exists()]
    missing_files = [path for path in files if not path.exists()]
    existing_dirs = [path for path in dirs if path.exists()]
    missing_dirs = [path for path in dirs if not path.exists()]

    if existing_files:
        console.print("[bold]Files to remove:[/bold]")
        for path in existing_files:
            meta = _file_meta(path)
            meta_str = f"  [dim]({meta})[/dim]" if meta else ""
            console.print(f"  [red]x[/red] {collapse_home(str(path))}{meta_str}")

    if missing_files:
        console.print("\n[dim]Files not found (will be skipped):[/dim]")
        for path in missing_files:
            console.print(f"  [dim]  {collapse_home(str(path))}[/dim]")

    if existing_dirs:
        console.print("\n[bold]Directories to remove:[/bold]")
        for path in existing_dirs:
            console.print(f"  [red]x[/red] {collapse_home(str(path))}/")
            for tree_line in _render_dir_tree(path):
                console.print(tree_line)

    if missing_dirs:
        console.print("\n[dim]Directories not found (will be skipped):[/dim]")
        for path in missing_dirs:
            console.print(f"  [dim]  {collapse_home(str(path))}/[/dim]")

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
    """Execute file and directory removal."""
    removed_files = 0
    removed_dirs = 0

    for path in files:
        if not path.exists():
            continue
        try:
            path.unlink()
            removed_files += 1
        except OSError as error:
            print_error(f"Error removing {path}: {error}")

    for path in dirs:
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
            removed_dirs += 1
        except OSError as error:
            print_error(f"Error removing {path}: {error}")

    if filtered_history is not None and history_file is not None:
        try:
            history_file.write_text("".join(filtered_history), encoding="utf-8")
        except OSError as error:
            print_error(f"Error writing history.jsonl: {error}")

    return removed_files, removed_dirs
