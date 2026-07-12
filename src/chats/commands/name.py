"""2026-07-12: aligned behavior with /Users/giladbarnea/.claude/hooks/auto_session_name.py and /Users/giladbarnea/.pi/agent/extensions/auto-session-name.ts. Keep all three aligned when changing.

Note: the other two renamers also rename `herdr` elements; this implementation avoids this intentionally.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from ..console import get_console, print_error
from ..formatting import format_to_xml
from ..model import ConversationFlags
from ..parsing import (
    decode_jsonl_entries,
    detect_format,
    extract_cwd_from_jsonl,
    get_jsonl_first_timestamp,
    get_jsonl_session_adapter,
    get_native_session_id,
    parse_jsonl,
    parse_raw_cli_transcript,
)
from . import resolve
from .common import _build_tool_id_map


_AUTO_NAME_MAX_LENGTH = 150
_AUTO_NAME_PROMPT = (
    "Name this session. The format is `<verb> <one lowercase phrase expressing the purpose "
    "of the session in its entirety — the end state the user wants to achieve>`.\n"
    "Clarification about <verb>: a single lowercase word pinning down the "
    "type of the session’s task."
)


def _clean_line(line: str) -> str:
    """Strip surrounding quotes/backticks, trim whitespace, and truncate to max length.

    >>> _clean_line('  "hello"  ')
    'hello'
    """
    line = line.strip()
    line = re.sub(r'^["\`\']+|["\`\']+$', "", line)
    return line[:_AUTO_NAME_MAX_LENGTH].strip()


def _parse_auto_session_name(output_text: str) -> str:
    """Parse LLM output into a session name."""
    output_lines = [
        cleaned
        for raw_line in _clean_line(output_text).split("\n")
        if (cleaned := _clean_line(raw_line))
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
        "\n\n===\n\n"
        f"<task>\n{_AUTO_NAME_PROMPT}\n</task>"
    )

    try:
        result = subprocess.run(
            [
                "pi",
                "--model",
                "openai-codex/gpt-5.4-mini",
                "--thinking",
                "high",
                "--no-skills",
                "--no-session",
                "--offline",
                "--no-themes",
                "--no-prompt-templates",
                "--no-extensions",
                "--print",
                "--system-prompt",
                prompt,
                "Follow the task instructions.",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"pi process failed: {error}") from error
    except FileNotFoundError as error:
        raise RuntimeError(
            "'pi' command not found. Ensure it is installed and in PATH."
        ) from error

    generated_name = _parse_auto_session_name(result.stdout)
    first_timestamp = get_jsonl_first_timestamp(conv_file)
    if first_timestamp is None:
        raise ValueError(f"could not determine first timestamp of {conv_file}")
    return f"[{first_timestamp:%m-%d}][{cwd_name}] {generated_name}"


def cmd_name(
    conversation_id: str,
    new_name: str | None,
    *,
    auto: bool = False,
    dry_run: bool = False,
) -> None:
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

    conv_file = resolve.resolve_conversation_file(conversation_id)
    adapter = get_jsonl_session_adapter(conv_file)
    session_id = get_native_session_id(conv_file)

    content = conv_file.read_text(encoding="utf-8")
    project = extract_cwd_from_jsonl(content) or ""
    entries = decode_jsonl_entries(content)

    if auto:
        try:
            new_name = _generate_auto_name(conv_file, content)
        except (RuntimeError, ValueError) as error:
            print_error(f"Auto-naming failed: {error}")
            sys.exit(1)

    assert new_name is not None

    if dry_run:
        print(new_name)
        return

    try:
        name_entries = adapter.build_name_entries(entries, session_id, new_name)
    except ValueError as error:
        print_error(str(error))
        sys.exit(1)

    try:
        with open(conv_file, "a", encoding="utf-8") as handle:
            handle.writelines(
                json.dumps(name_entry, separators=(",", ":")) + "\n"
                for name_entry in name_entries
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
