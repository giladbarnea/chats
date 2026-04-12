from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .commands import cmd_catalog, cmd_parse, cmd_rename, cmd_rm, cmd_search
from .console import init_module_console, print_warning
from .model import ConversationFlags
from .ordering import is_single_negative_index
from .tool_filter import ToolFilter, parse_tool_spec


def _resolve_thinking_mode(raw_thinking: str | None, show_all: bool) -> tuple[bool, bool]:
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


def _warn_only_override(only_flag: str, disabled_flags: list[str]) -> None:
    """Emit a consistent warning when an `--only-*` flag overrides extras."""
    joined = ", ".join(disabled_flags)
    print_warning(f"Warning: {only_flag} overrides {joined}; disabling those options.")


def _normalize_parse_visibility_args(args: argparse.Namespace) -> None:
    """Normalize contradictory parse-mode visibility flags before building ConversationFlags."""
    only_assistant_disabled = []
    if args.all:
        only_assistant_disabled.append("`--all`")
    if args.thinking:
        only_assistant_disabled.append("`--thinking`")
    if args.tools is not None:
        only_assistant_disabled.append("`--tools`")
    if args.agents:
        only_assistant_disabled.append("`--agents`")
    if args.only_assistant and only_assistant_disabled:
        _warn_only_override("`--only-assistant`", only_assistant_disabled)
        args.all = False
        args.thinking = None
        args.tools = None
        args.agents = False

    only_user_disabled = []
    if args.all:
        only_user_disabled.append("`--all`")
    if args.thinking:
        only_user_disabled.append("`--thinking`")
    if args.tools is not None:
        only_user_disabled.append("`--tools`")
    if args.agents:
        only_user_disabled.append("`--agents`")
    if args.only_user and only_user_disabled:
        _warn_only_override("`--only-user`", only_user_disabled)
        args.all = False
        args.thinking = None
        args.tools = None
        args.agents = False

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


def _build_parse_flags(args: argparse.Namespace) -> ConversationFlags:
    """Convert normalized parse-mode args into ConversationFlags."""
    show_thinking, shorten_thinking = _resolve_thinking_mode(args.thinking, args.all)
    return ConversationFlags(
        show_user_messages=not args.only_assistant and not args.no_user,
        show_assistant_messages=not args.only_user and not args.no_assistant,
        show_thinking=show_thinking,
        show_tools=_resolve_show_tools(args.tools, args.all),
        show_agents=args.agents or args.all,
        show_plans=not args.no_plans,
        allow_empty_output=(
            args.only_user or args.only_assistant or args.no_user or args.no_assistant
        ),
        shorten=args.short,
        shorten_thinking=shorten_thinking,
        color=args.color,
        paging=args.paging,
    )


def main():
    """Main entry point."""

    def init_module_console_from_color_arg(value: str):
        color = (value == "always") or (value == "auto" and sys.stdout.isatty())
        init_module_console(force_color=color)
        return value

    # Check for subcommands early (before argparse)
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        # Parse search arguments
        parser = argparse.ArgumentParser(prog="ccc search")
        parser.add_argument("pattern", help="Pattern to search for")
        parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="List mode - show only paths and metadata",
        )
        parser.add_argument(
            "-d",
            "--dir",
            type=str,
            default=None,
            help="Restrict search to conversations in this directory",
        )
        parser.add_argument(
            "-ma",
            "--mafter",
            type=str,
            default=None,
            metavar="DATE",
            help="Only conversations modified after DATE (e.g., 2024-12-15, 1d, 2w)",
        )
        parser.add_argument(
            "-ca",
            "--cafter",
            type=str,
            default=None,
            metavar="DATE",
            help="Only conversations created after DATE",
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
            "-A",
            "--all",
            action="store_true",
            help="Show everything (thinking, tools, agents)",
        )
        parser.add_argument(
            "-s", "--short", action="store_true", help="Shorten strings in output"
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
            "--no-plans",
            action="store_true",
            help="Hide plan content (ExitPlanMode)",
        )
        parser.add_argument(
            "--no-metadata",
            action="store_true",
            help="Disable outputting metadata frontmatter",
        )

        args = parser.parse_args(sys.argv[2:])

        try:
            show_thinking, shorten_thinking = _resolve_thinking_mode(args.thinking, args.all)
        except ValueError as exc:
            parser.error(str(exc))
        flags = ConversationFlags(
            show_thinking=show_thinking,
            show_tools=_resolve_show_tools(args.tools, args.all),
            show_agents=args.agents or args.all,
            show_plans=not args.no_plans,
            shorten=args.short,
            shorten_thinking=shorten_thinking,
            color=args.color,
            paging=args.paging,
        )
        cmd_search(
            args.pattern,
            flags,
            args.list,
            args.dir,
            args.mafter,
            args.cafter,
            emit_metadata=not args.no_metadata,
        )
    elif len(sys.argv) > 1 and sys.argv[1] == "rename":
        # Parse rename arguments
        parser = argparse.ArgumentParser(
            prog="ccc rename",
            description="Rename a conversation by updating its display name",
        )
        parser.add_argument(
            "conversation_id",
            help="Conversation/session ID, summary prefix, recent negative index, or file path",
        )
        parser.add_argument("new_name", help="New display name for the conversation")

        args = parser.parse_args(sys.argv[2:])

        cmd_rename(args.conversation_id, args.new_name)
    elif len(sys.argv) > 1 and sys.argv[1] == "rm":
        # Parse rm arguments
        parser = argparse.ArgumentParser(
            prog="ccc rm",
            description="Remove a conversation session and all associated files. "
                        "Shows a preview, then prompts for confirmation before removal.",
        )
        parser.add_argument(
            "session", help="Session UUID or file path"
        )
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
    else:
        # Default parse behavior
        parser = argparse.ArgumentParser(
            prog="ccc",
            description="Parse and format supported AI CLI conversation histories",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        parser.add_argument(
            "input",
            nargs="?",
            help="Input file path, conversation/session ID, recent negative index, or use stdin if omitted",
        )
        parser.add_argument(
            "slice",
            nargs="?",
            help='Message slice (1-indexed): "1", "-1", "2:", ":-2", "3:5". '
            'For negative slices starting with -, use: -- -5: or quote: "-5:"',
        )
        parser.add_argument(
            "-o",
            "--out",
            type=Path,
            help="Output file path (uses Rich display if omitted)",
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
        parser.add_argument(
            "-a", "--agents", action="store_true", help="Include agent messages"
        )
        parser.add_argument(
            "-A",
            "--all",
            action="store_true",
            help="Show everything (thinking, tools, agents)",
        )
        parser.add_argument(
            "-s", "--short", action="store_true", help="Shorten strings in output"
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
            "--no-plans",
            action="store_true",
            help="Hide plan content (ExitPlanMode)",
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

        if args.input is None and isinstance(args.thinking, str):
            if args.thinking in {"full", "short"}:
                pass
            else:
                args.input = args.thinking
                args.thinking = "full"

        def _looks_like_slice(candidate: str) -> bool:
            """Check if candidate is a numeric slice (not a tool filter spec).

            Valid slices: "1", "-1", "2:", ":-2", "2:5", "-5:".
            NOT slices: "Bash:i", "Read:o:s" (contain non-numeric parts).
            """
            parts = candidate.split(":")
            if len(parts) > 2:
                return False
            return all(
                not p or p.isdigit() or (p.startswith("-") and len(p) > 1 and p[1:].isdigit())
                for p in parts
            )

        # Check if unknown[0] is either a recent-session selector or a slice.
        if unknown:
            candidate = unknown[0]
            if (
                args.input is None
                and args.slice is None
                and is_single_negative_index(candidate)
                and sys.stdin.isatty()
            ):
                args.input = candidate
            elif args.slice is None and _looks_like_slice(candidate):
                args.slice = candidate

        # Fix for nargs='?' consuming positional arg:
        # With action="append", args.tools is None or a list.
        # If args.tools has a single string that looks like a file/session ID, swap it.
        if (
            args.input is None
            and args.tools is not None
            and len(args.tools) == 1
            and isinstance(args.tools[0], str)
        ):
            candidate = args.tools[0]
            should_swap = False
            if os.path.exists(candidate):
                should_swap = True
            elif candidate.endswith(".jsonl") or "/" in candidate or os.sep in candidate:
                should_swap = True
            elif is_single_negative_index(candidate):
                should_swap = True
            elif re.match(r"^[0-9a-f-]{36}$", candidate):
                should_swap = True

            if should_swap:
                args.input = candidate
                args.tools = [True]

        # Fix for nargs='?' consuming slice argument:
        if (
            args.slice is None
            and args.tools is not None
            and len(args.tools) == 1
            and isinstance(args.tools[0], str)
        ):
            candidate = args.tools[0]
            if _looks_like_slice(candidate):
                args.slice = candidate
                args.tools = [True]

        _normalize_parse_visibility_args(args)
        try:
            flags = _build_parse_flags(args)
        except ValueError as exc:
            parser.error(str(exc))

        output_format = "raw" if args.raw else args.format
        emit_metadata = not (args.no_metadata or args.raw or output_format == "raw")

        cmd_parse(
            flags,
            args.input,
            slice_str=args.slice,
            output_file=args.out,
            output_format=output_format,
            emit_metadata=emit_metadata,
        )
