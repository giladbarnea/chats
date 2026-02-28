from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .commands import cmd_catalog, cmd_parse, cmd_rename, cmd_rm, cmd_search
from .console import init_module_console
from .model import ConversationFlags


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
            "-T", "--thinking", action="store_true", help="Show thinking tokens"
        )
        parser.add_argument(
            "-t",
            "--tools",
            nargs="?",
            const=True,
            default=False,
            help="Show tool use/result details (optional: filter by name, e.g. 'Bash' or '!Bash')",
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

        flags = ConversationFlags(
            show_thinking=args.thinking or args.all,
            show_tools=args.tools or args.all,
            show_agents=args.agents or args.all,
            show_plans=not args.no_plans,
            shorten=args.short,
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
            "conversation_id", help="Conversation UUID, summary prefix, or file path"
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
            description="Parse and format Claude Code conversations",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        parser.add_argument(
            "input",
            nargs="?",
            help="Input file path, conversation ID, or use stdin if omitted",
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
            "-T", "--thinking", action="store_true", help="Show thinking tokens"
        )
        parser.add_argument(
            "-t",
            "--tools",
            nargs="?",
            const=True,
            default=False,
            help="Show tool use/result details (optional: filter by name, e.g. 'Bash' or '!Bash')",
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

        def _looks_like_slice(candidate: str) -> bool:
            return (
                candidate.isdigit()  # "0", "1", "2"
                or (candidate.startswith("-") and candidate[1:].isdigit())  # "-1", "-5"
                or ":" in candidate  # "2:", ":-2", "4:-7", "-5:"
            )

        # Check if unknown[0] looks like a slice and args.slice wasn't set
        if unknown and args.slice is None:
            candidate = unknown[0]
            # Valid slice patterns: "0", "-1", "2:", ":-2", "4:-7", "-5:", etc.
            if _looks_like_slice(candidate):
                args.slice = candidate

        # Fix for nargs='?' consuming positional arg:
        # If args.tools is a string (value consumed) but args.input is None,
        # check if args.tools looks like a file/session ID. If so, swap them.
        if args.input is None and isinstance(args.tools, str):
            candidate = args.tools
            should_swap = False
            # Check existence if it looks like a path
            if os.path.exists(candidate):
                should_swap = True
            # Check for common extensions or path separators
            elif candidate.endswith(".jsonl") or "/" in candidate or os.sep in candidate:
                should_swap = True
            # Check for UUID-like (session ID)
            elif re.match(r"^[0-9a-f-]{36}$", candidate):
                should_swap = True

            if should_swap:
                args.input = candidate
                # Restore default boolean behavior for -t
                args.tools = True
        # Fix for nargs='?' consuming slice argument:
        # If args.tools is a string that looks like a slice, restore slice.
        if args.slice is None and isinstance(args.tools, str):
            candidate = args.tools
            if _looks_like_slice(candidate):
                args.slice = candidate
                args.tools = True

        flags = ConversationFlags(
            show_thinking=args.thinking or args.all,
            show_tools=args.tools or args.all,
            show_agents=args.agents or args.all,
            show_plans=not args.no_plans,
            shorten=args.short,
            color=args.color,
            paging=args.paging,
        )

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
