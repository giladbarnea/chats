from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from . import commands as commands_module
from .commands import cmd_catalog, cmd_info, cmd_name, cmd_parse, cmd_rm, cmd_search
from .console import init_module_console, print_warning
from .model import (
    ConversationFlags,
    MessageSelection,
    ParseOutputMode,
    SearchOutputMode,
)
from .ordering import is_single_negative_index
from .pool_filter import PoolFilter, add_pool_filter_args
from .tool_filter import ToolFilter, parse_tool_spec


def _resolve_thinking_mode(
    raw_thinking: str | None, show_all: bool
) -> tuple[bool, bool]:
    """Return (show_thinking, shorten_thinking) from raw CLI args."""
    if show_all:
        return True, False
    if raw_thinking is None:
        return False, False
    if raw_thinking not in {"full", "short"}:
        raise ValueError(
            f"Invalid thinking mode: {raw_thinking!r}. Expected one of: full, short."
        )
    return True, raw_thinking == "short"


def _resolve_show_tools(
    raw_tools: list[bool | str] | None, show_all: bool
) -> bool | list[ToolFilter]:
    """Convert raw --tools CLI args to the value ConversationFlags expects."""
    if show_all:
        return True
    if raw_tools is None:
        return False

    specs: list[str] = []
    for v in raw_tools:
        if v is True:
            continue  # bare --tools, no filter spec
        specs.extend(v.split())

    if not specs:
        return True  # only bare --tools with no filters

    return [parse_tool_spec(s) for s in specs]


def _looks_like_positive_integer(candidate: str) -> bool:
    """Return True when the candidate is a positive base-10 integer."""
    return candidate.isdigit() and int(candidate) > 0


def _is_valid_short_max_chars_token(candidate: str) -> bool:
    """Return True when the candidate is a valid explicit `--short` character limit."""
    return candidate.isdigit() and int(candidate) > 7


def _short_uses_attached_value(argv_tokens: list[str]) -> bool:
    """Return True when `--short` was spelled with an attached `=NUMBER` value."""
    return any(token.startswith(("--short=", "-s=")) for token in argv_tokens)


def _resolve_short_max_chars(
    raw_short: bool | str | None,
    *,
    attached_value: bool = False,
) -> int | None:
    """Return the shortening character limit requested by `--short`, or None when disabled."""
    if raw_short is None:
        return None
    if raw_short is True:
        return 500
    if attached_value and isinstance(raw_short, str):
        if _is_valid_short_max_chars_token(raw_short):
            return int(raw_short)
        raise ValueError(
            f"Invalid --short value: {raw_short!r}. Expected digits > 7."
        )
    if isinstance(raw_short, str) and _is_valid_short_max_chars_token(raw_short):
        return int(raw_short)
    return 500


def _warn_only_override(only_flag: str, disabled_flags: list[str]) -> None:
    """Emit a consistent warning when an `--only-*` flag overrides extras."""
    joined = ", ".join(disabled_flags)
    print_warning(f"Warning: {only_flag} overrides {joined}; disabling those options.")


def _normalize_role_visibility_args(args: argparse.Namespace) -> None:
    """Normalize contradictory role visibility flags before building ConversationFlags."""
    only_assistant_disabled = []
    if args.all:
        only_assistant_disabled.append("`--all`")
    if args.thinking:
        only_assistant_disabled.append("`--thinking`")
    if args.tools is not None:
        only_assistant_disabled.append("`--tools`")
    if args.agents:
        only_assistant_disabled.append("`--agents`")
    if args.plans:
        only_assistant_disabled.append("`--plans`")
    if args.only_assistant and only_assistant_disabled:
        _warn_only_override("`--only-assistant`", only_assistant_disabled)
        args.all = False
        args.thinking = None
        args.tools = None
        args.agents = False
        args.plans = False

    only_user_disabled = []
    if args.all:
        only_user_disabled.append("`--all`")
    if args.thinking:
        only_user_disabled.append("`--thinking`")
    if args.tools is not None:
        only_user_disabled.append("`--tools`")
    if args.agents:
        only_user_disabled.append("`--agents`")
    if args.plans:
        only_user_disabled.append("`--plans`")
    if args.only_user and only_user_disabled:
        _warn_only_override("`--only-user`", only_user_disabled)
        args.all = False
        args.thinking = None
        args.tools = None
        args.agents = False
        args.plans = False

    if args.only_user and args.only_assistant:
        print_warning(
            "Warning: `--only-user` and `--only-assistant` are contradictory; "
            "continuing with both filters active."
        )
    if args.only_user and args.no_user:
        print_warning(
            "Warning: `--only-user` and `--no-user` are contradictory; "
            "continuing with both filters active."
        )
    if args.only_assistant and args.no_assistant:
        print_warning(
            "Warning: `--only-assistant` and `--no-assistant` are contradictory; "
            "continuing with both filters active."
        )


def _resolve_message_selection(args: argparse.Namespace) -> MessageSelection:
    """Resolve contradictory role-selection flags into one explicit mode."""
    if args.only_user and args.only_assistant:
        return MessageSelection.NONE
    if args.only_user and args.no_user:
        return MessageSelection.NONE
    if args.only_assistant and args.no_assistant:
        return MessageSelection.NONE
    if args.no_user and args.no_assistant:
        return MessageSelection.NONE
    if args.only_user:
        return MessageSelection.ONLY_USER
    if args.only_assistant:
        return MessageSelection.ONLY_ASSISTANT
    if args.no_user:
        return MessageSelection.NO_USER
    if args.no_assistant:
        return MessageSelection.NO_ASSISTANT
    return MessageSelection.ALL


def _build_parse_flags(args: argparse.Namespace) -> ConversationFlags:
    """Convert normalized parse-mode args into ConversationFlags."""
    show_thinking, shorten_thinking = _resolve_thinking_mode(args.thinking, args.all)
    message_selection = _resolve_message_selection(args)
    shorten_max_chars = _resolve_short_max_chars(
        args.short,
        attached_value=getattr(args, "_short_uses_attached_value", False),
    )
    return ConversationFlags(
        message_selection=message_selection,
        show_thinking=show_thinking,
        show_tools=_resolve_show_tools(args.tools, args.all),
        show_agents=args.agents or args.all,
        show_branches=args.branches or args.all,
        show_plans=args.plans or args.all,
        allow_empty_output=message_selection != MessageSelection.ALL,
        shorten=shorten_max_chars is not None,
        shorten_max_chars=shorten_max_chars or 500,
        shorten_thinking=shorten_thinking,
        color=args.color,
        paging=args.paging,
    )


def _build_fork_flags(args: argparse.Namespace) -> ConversationFlags:
    """Convert fork-mode args into ConversationFlags."""
    show_thinking, shorten_thinking = _resolve_thinking_mode(args.thinking, args.all)
    return ConversationFlags(
        show_thinking=show_thinking,
        show_tools=_resolve_show_tools(args.tools, args.all),
        show_agents=args.agents or args.all,
        show_plans=args.plans or args.all,
        shorten_thinking=shorten_thinking,
        color=False,
        paging=False,
    )


def _resolve_parse_output_mode(args: argparse.Namespace) -> ParseOutputMode:
    """Resolve mutually-exclusive parse output-only flags into one mode."""
    if args.only_id:
        return ParseOutputMode.ONLY_ID
    if args.only_metadata:
        return ParseOutputMode.ONLY_METADATA
    return ParseOutputMode.FULL


def _resolve_search_output_mode(args: argparse.Namespace) -> SearchOutputMode:
    """Resolve mutually-exclusive search output flags into one mode."""
    if args.only_id:
        return SearchOutputMode.ONLY_ID
    if args.list:
        return SearchOutputMode.LIST
    if args.full:
        return SearchOutputMode.FULL
    return SearchOutputMode.MATCHES


def _looks_like_slice(candidate: str) -> bool:
    """Check if candidate is a numeric slice (not a tool filter spec)."""
    parts = candidate.split(":")
    if len(parts) > 2:
        return False
    return all(
        not p or p.isdigit() or (p.startswith("-") and len(p) > 1 and p[1:].isdigit())
        for p in parts
    )


def _looks_like_session_input(candidate: str) -> bool:
    """Check if candidate plausibly names a session/file rather than a tool filter."""
    if os.path.exists(candidate):
        return True
    if candidate.endswith(".jsonl") or "/" in candidate or os.sep in candidate:
        return True
    if is_single_negative_index(candidate):
        return True
    return bool(re.match(r"^[0-9a-f-]{36}$", candidate))


def _add_repaired_slice(args: argparse.Namespace, candidate: str) -> None:
    """Record a slice-like value that argparse swallowed into an optional flag."""
    repaired_slices: list[str] = getattr(args, "_repaired_slices", [])
    repaired_slices.append(candidate)
    args._repaired_slices = repaired_slices


def _repair_visibility_option_positionals(
    args: argparse.Namespace,
    *,
    input_attr: str,
    allow_slice: bool,
) -> None:
    """Undo argparse swallowing positionals into `-T/--thinking` or `-t/--tools`."""
    input_value = getattr(args, input_attr)

    if isinstance(args.thinking, str) and args.thinking not in {"full", "short"}:
        thinking_candidate = args.thinking
        if input_value is None:
            setattr(args, input_attr, thinking_candidate)
            args.thinking = "full"
            input_value = thinking_candidate
        elif allow_slice and _looks_like_slice(thinking_candidate):
            if getattr(args, "slice", None) is None:
                args.slice = thinking_candidate
            else:
                _add_repaired_slice(args, thinking_candidate)
            args.thinking = "full"

    if (
        input_value is None
        and args.tools is not None
        and len(args.tools) == 1
        and isinstance(args.tools[0], str)
    ):
        candidate = args.tools[0]
        if _looks_like_session_input(candidate):
            setattr(args, input_attr, candidate)
            args.tools = [True]
            input_value = candidate

    if (
        allow_slice
        and args.tools is not None
        and len(args.tools) == 1
        and isinstance(args.tools[0], str)
    ):
        candidate = args.tools[0]
        if _looks_like_slice(candidate):
            if getattr(args, "slice", None) is None:
                args.slice = candidate
            else:
                _add_repaired_slice(args, candidate)
            args.tools = [True]


def _repair_short_option_positionals(
    args: argparse.Namespace,
    *,
    input_attr: str,
    allow_slice: bool,
) -> None:
    """Undo argparse swallowing a positional into `-s/--short`."""
    if not isinstance(args.short, str):
        return
    if getattr(args, "_short_uses_attached_value", False):
        return
    if _is_valid_short_max_chars_token(args.short):
        return

    input_value = getattr(args, input_attr)
    if input_value is None:
        setattr(args, input_attr, args.short)
        args.short = True
        return

    if allow_slice and _looks_like_slice(args.short):
        if getattr(args, "slice", None) is None:
            args.slice = args.short
        else:
            _add_repaired_slice(args, args.short)
        args.short = True
        return

    if allow_slice and _looks_like_session_input(args.short) and _looks_like_slice(input_value):
        if getattr(args, "slice", None) is None:
            args.slice = input_value
        else:
            _add_repaired_slice(args, input_value)
        setattr(args, input_attr, args.short)
        args.short = True


def main():
    """Main entry point."""

    def init_module_console_from_color_arg(value: str):
        color = (value == "always") or (value == "auto" and sys.stdout.isatty())
        init_module_console(force_color=color)
        return value

    # Check for subcommands early (before argparse)
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        # Parse search arguments
        parser = argparse.ArgumentParser(prog="ch search")
        parser.add_argument("pattern", nargs="?", help="Pattern to search for")
        parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="List mode - show only paths and metadata",
        )
        parser.add_argument(
            "-ll",
            "--only-id",
            action="store_true",
            help="Show only matching session IDs (implies --color never and --no-paging)",
        )
        parser.add_argument(
            "-f",
            "--full",
            action="store_true",
            help="Show full matching conversations instead of only matching messages",
        )
        parser.add_argument(
            "-r",
            "--raw",
            action="store_true",
            help="Alias for raw markdown search output (implies --no-metadata, --color never, and --no-paging)",
        )
        add_pool_filter_args(
            parser,
            dir_help="Restrict search to conversations in this directory",
            mafter_help="Only conversations modified after DATE (e.g., 2024-12-15, 1d, 2w)",
            cafter_help="Only conversations created after DATE",
            provider_help="Restrict search to sessions from a specific provider",
        )
        parser.add_argument(
            "-T",
            "--thinking",
            nargs="?",
            const="full",
            default=None,
            help="Show thinking tokens (optional: short)",
        )
        parser.add_argument(
            "--only-user",
            action="store_true",
            help="Search only regular user message bodies",
        )
        parser.add_argument(
            "--only-assistant",
            action="store_true",
            help="Search only regular assistant message bodies",
        )
        parser.add_argument(
            "-t",
            "--tools",
            action="append",
            nargs="?",
            const=True,
            default=None,
            help="Show tool use/result details (optional: filter with modifiers, e.g. 'Bash:i', 'Read:o:s', '!Bash')",
        )
        parser.add_argument(
            "-a", "--agents", action="store_true", help="Include agent messages"
        )
        parser.add_argument(
            "-b",
            "--branches",
            action="store_true",
            help="Include messages from abandoned (rewound) branches",
        )
        parser.add_argument(
            "-A",
            "--all",
            action="store_true",
            help="Show everything (thinking, tools, agents, plans)",
        )
        parser.add_argument(
            "--plans",
            action="store_true",
            help="Show plan content (ExitPlanMode)",
        )
        parser.add_argument(
            "-s",
            "--short",
            nargs="?",
            const=True,
            default=None,
            help="Shorten strings in output (optional: max characters)",
        )
        parser.add_argument(
            "--color",
            choices=["always", "never", "auto"],
            default="auto",
            help="Control Rich formatting: always, never, or auto (default: auto)",
            type=init_module_console_from_color_arg,
        )
        parser.add_argument(
            "--paging",
            action="store_true",
            default=None,
            help="Enable paging (default: same as color)",
        )
        parser.add_argument(
            "--no-paging",
            dest="paging",
            action="store_false",
            help="Disable paging",
        )
        parser.add_argument(
            "--no-metadata",
            action="store_true",
            help="Disable outputting metadata frontmatter",
        )

        args, unknown = parser.parse_known_args(sys.argv[2:])
        args._short_uses_attached_value = _short_uses_attached_value(sys.argv[2:])
        if unknown:
            parser.error(f"unrecognized arguments: {' '.join(unknown)}")
        _repair_short_option_positionals(args, input_attr="pattern", allow_slice=False)
        if args.pattern is None:
            parser.error("the following arguments are required: pattern")

        output_mode = _resolve_search_output_mode(args)
        if output_mode == SearchOutputMode.ONLY_ID or args.raw:
            args.paging = False
            args.color = "never"

        args.no_user = False
        args.no_assistant = False
        _normalize_role_visibility_args(args)
        try:
            show_thinking, shorten_thinking = _resolve_thinking_mode(
                args.thinking, args.all
            )
            shorten_max_chars = _resolve_short_max_chars(
                args.short,
                attached_value=getattr(args, "_short_uses_attached_value", False),
            )
            show_tools = _resolve_show_tools(args.tools, args.all)
        except ValueError as exc:
            parser.error(str(exc))
        message_selection = _resolve_message_selection(args)
        flags = ConversationFlags(
            message_selection=message_selection,
            show_thinking=show_thinking,
            show_tools=show_tools,
            show_agents=args.agents or args.all,
            show_branches=args.branches or args.all,
            show_plans=args.plans or args.all,
            shorten=shorten_max_chars is not None,
            shorten_max_chars=shorten_max_chars or 500,
            shorten_thinking=shorten_thinking,
            color=args.color,
            paging=args.paging,
        )
        cmd_search(
            args.pattern,
            flags,
            PoolFilter.from_args(args),
            output_mode=output_mode,
            output_format="raw" if args.raw else "xml",
            emit_metadata=not (args.no_metadata or args.raw),
        )
    elif len(sys.argv) > 1 and sys.argv[1] == "name":
        # Parse name arguments
        parser = argparse.ArgumentParser(
            prog="ch name",
            description="Rename a conversation by updating its display name",
        )
        parser.add_argument(
            "conversation_id",
            help="Conversation/session ID, summary prefix, recent negative index, or file path",
        )
        parser.add_argument(
            "new_name",
            nargs="?",
            default=None,
            help="New display name for the conversation (omit when using --auto)",
        )
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Auto-generate a name using AI via pi (mutually exclusive with new_name)",
        )
        parser.add_argument(
            "-n",
            "--dry-run",
            action="store_true",
            help="Print the resolved/generated name without modifying the session file",
        )

        args = parser.parse_args(sys.argv[2:])

        if not args.new_name and not args.auto:
            parser.error("Either provide a new name or use --auto to generate one.")
        if args.new_name and args.auto:
            parser.error("Cannot specify both a new name and --auto.")

        cmd_name(
            args.conversation_id,
            args.new_name,
            auto=args.auto,
            dry_run=args.dry_run,
        )
    elif len(sys.argv) > 1 and sys.argv[1] == "fork":
        parser = argparse.ArgumentParser(
            prog="ch fork",
            description="Duplicate a supported session into a thinner resumable fork",
        )
        parser.add_argument(
            "session",
            nargs="?",
            help="Conversation/session ID, summary prefix, recent negative index, or file path",
        )
        parser.add_argument(
            "-T",
            "--thinking",
            nargs="?",
            const="full",
            default=None,
            help="Include thinking tokens (optional: short)",
        )
        parser.add_argument(
            "-t",
            "--tools",
            action="append",
            nargs="?",
            const=True,
            default=None,
            help="Include tool use/result details (optional: filter with modifiers, e.g. 'Bash:i', 'Read:o:s', '!Bash')",
        )
        parser.add_argument(
            "-a",
            "--agents",
            action="store_true",
            help="Include agent sidechain messages",
        )
        parser.add_argument(
            "-A",
            "--all",
            action="store_true",
            help="Show everything (thinking, tools, agents, plans)",
        )
        parser.add_argument(
            "--plans",
            action="store_true",
            help="Include plan content (ExitPlanMode)",
        )

        args, _unknown = parser.parse_known_args(sys.argv[2:])
        _repair_visibility_option_positionals(
            args, input_attr="session", allow_slice=False
        )

        if args.session is None:
            parser.error("the following arguments are required: session")

        try:
            flags = _build_fork_flags(args)
        except ValueError as exc:
            parser.error(str(exc))

        commands_module.cmd_fork(args.session, flags)
    elif len(sys.argv) > 1 and sys.argv[1] == "rm":
        # Parse rm arguments
        parser = argparse.ArgumentParser(
            prog="ch rm",
            description="Remove a conversation session and all associated files. "
            "Shows a preview, then prompts for confirmation before removal.",
        )
        parser.add_argument("session", help="Session UUID or file path")
        parser.add_argument(
            "-n",
            "--dry-run",
            action="store_true",
            help="Preview only - show what would be removed without prompting",
        )

        args = parser.parse_args(sys.argv[2:])

        cmd_rm(args.session, dry_run=args.dry_run)
    elif len(sys.argv) > 1 and sys.argv[1] == "catalog":
        # Pass all remaining arguments to catalog command
        # This is a simple passthrough to the shell script
        cmd_catalog(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "info":
        parser = argparse.ArgumentParser(
            prog="ch info",
            description="Show aggregated statistics for a Claude or PI session",
        )
        parser.add_argument(
            "session",
            help="Conversation/session ID, name, recent negative index, or file path",
        )
        parser.add_argument(
            "-f",
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format: text or json (default: text)",
        )
        args = parser.parse_args(sys.argv[2:])
        cmd_info(args.session, output_format=args.format)
    else:
        # Default parse behavior
        parser = argparse.ArgumentParser(
            prog="ch",
            description="Parse and format supported AI CLI conversation histories",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""\
Commands:
  search   Search conversations with regex patterns
  name     Assign a custom display name to a conversation
  fork     Duplicate a session into a thinner resumable copy
  rm       Remove a conversation session and all associated files
  catalog  AI-powered session cataloging
  info     Show aggregated statistics for a Claude or PI session
""",
        )

        parser.add_argument(
            "input",
            nargs="?",
            help="Input file path, conversation/session ID, recent negative index, or use stdin if omitted",
        )
        parser.add_argument(
            "slice",
            nargs="?",
            help='Message selector (1-indexed): "1", "-1", "2:", ":-2", "3:5". '
            "Pass more positional selectors to OR them together. "
            'For negative slices starting with -, use: -- -5: or quote: "-5:"',
        )
        parser.add_argument(
            "-o",
            "--out",
            type=Path,
            help="Output file path (uses Rich display if omitted)",
        )
        parser.add_argument(
            "-l",
            "--only-metadata",
            action="store_true",
            help="Show only session metadata",
        )
        parser.add_argument(
            "-ll",
            "--only-id",
            action="store_true",
            help="Show only the resolved session ID (implies --color never and --no-paging)",
        )
        parser.add_argument(
            "-T",
            "--thinking",
            nargs="?",
            const="full",
            default=None,
            help="Show thinking tokens (optional: short)",
        )
        parser.add_argument(
            "--only-user",
            action="store_true",
            help="Show only regular user messages",
        )
        parser.add_argument(
            "--only-assistant",
            action="store_true",
            help="Show only regular assistant messages",
        )
        parser.add_argument(
            "--no-user",
            action="store_true",
            help="Hide regular user messages",
        )
        parser.add_argument(
            "--no-assistant",
            action="store_true",
            help="Hide regular assistant messages",
        )
        parser.add_argument(
            "-t",
            "--tools",
            action="append",
            nargs="?",
            const=True,
            default=None,
            help="Show tool use/result details (optional: filter with modifiers, e.g. 'Bash:i', 'Read:o:s', '!Bash')",
        )
        add_pool_filter_args(
            parser,
            provider_help="Restrict recent-index resolution to a provider when input is -1, -2, ...",
            dir_help="Restrict recent-index resolution to sessions whose cwd exactly matches this directory",
            mafter_help="Restrict recent-index resolution to sessions modified after DATE",
            cafter_help="Restrict recent-index resolution to sessions created after DATE",
        )
        parser.add_argument(
            "-a", "--agents", action="store_true", help="Include agent messages"
        )
        parser.add_argument(
            "-b",
            "--branches",
            action="store_true",
            help="Include messages from abandoned (rewound) branches",
        )
        parser.add_argument(
            "-A",
            "--all",
            action="store_true",
            help="Show everything (thinking, tools, agents, plans)",
        )
        parser.add_argument(
            "--plans",
            action="store_true",
            help="Show plan content (ExitPlanMode)",
        )
        parser.add_argument(
            "-s",
            "--short",
            nargs="?",
            const=True,
            default=None,
            help="Shorten strings in output (optional: max characters)",
        )
        parser.add_argument(
            "--color",
            choices=["always", "never", "auto"],
            default="auto",
            help="Control Rich formatting: always, never, or auto (default: auto)",
            type=init_module_console_from_color_arg,
        )
        parser.add_argument(
            "-f",
            "--format",
            choices=["xml", "json", "raw"],
            default="xml",
            help="Output format: xml, json, or raw (default: xml)",
        )
        parser.add_argument(
            "-r",
            "--raw",
            action="store_true",
            help="Alias for: -f raw (implies --no-metadata)",
        )
        parser.add_argument(
            "--paging",
            action="store_true",
            default=None,
            help="Enable paging (default: same as color)",
        )
        parser.add_argument(
            "--no-paging",
            dest="paging",
            action="store_false",
            help="Disable paging",
        )
        parser.add_argument(
            "--no-metadata",
            action="store_true",
            help="Disable outputting metadata frontmatter",
        )

        # Handle slices that end up in unknown args due to argparse quirks:
        # 1. Negative slices like "-5:" get interpreted as flags
        # 2. Positional args after --flag=value end up in unknown with nargs='?'
        args, unknown = parser.parse_known_args()
        args._short_uses_attached_value = _short_uses_attached_value(sys.argv[1:])

        _repair_visibility_option_positionals(
            args, input_attr="input", allow_slice=True
        )
        _repair_short_option_positionals(args, input_attr="input", allow_slice=True)

        slice_args = list(getattr(args, "_repaired_slices", []))
        if args.slice is not None:
            slice_args.append(args.slice)

        # Check whether unknown positionals are either a recent-session selector or slices.
        if unknown:
            candidate = unknown[0]
            if (
                args.input is None
                and not slice_args
                and is_single_negative_index(candidate)
                and sys.stdin.isatty()
            ):
                args.input = candidate
                unknown = unknown[1:]

        # Bug: That means a typo like ch session --colro never 1 can silently apply selector 1 instead of surfacing an option error, producing truncated output in a way that is hard to diagnose.
        for candidate in unknown:
            if _looks_like_slice(candidate):
                slice_args.append(candidate)

        output_mode = _resolve_parse_output_mode(args)
        if output_mode == ParseOutputMode.ONLY_ID:
            args.paging = False
            args.color = "never"

        pool_filter = PoolFilter.from_args(args)
        if not pool_filter.is_empty() and not (
            args.input is not None and is_single_negative_index(args.input)
        ):
            print_warning(
                "Warning: pool filters (`--provider`, `--dir`, `--mafter`, `--cafter`) "
                "only apply when parse input is a recent index like `-1`; ignoring them."
            )
            pool_filter = PoolFilter()

        _normalize_role_visibility_args(args)
        try:
            flags = _build_parse_flags(args)
        except ValueError as exc:
            parser.error(str(exc))

        output_format = "raw" if args.raw else args.format
        emit_metadata = not (args.no_metadata or args.raw or output_format == "raw")

        cmd_parse(
            flags,
            args.input,
            slice_str=slice_args,
            output_file=args.out,
            output_format=output_format,
            emit_metadata=emit_metadata,
            pool_filter=pool_filter,
            output_mode=output_mode,
        )
