from __future__ import annotations

import argparse
import os
import re
import sys
import textwrap
from pathlib import Path

from .commands import (
    cmd_catalog,
    cmd_info,
    cmd_name,
    cmd_parse,
    cmd_rm,
)
from .console import init_module_console, print_warning
from .model import (
    ConversationFlags,
    MessageSelection,
    ParseOutputMode,
)
from .ordering import is_single_negative_index
from .pool_filter import PoolFilter, add_pool_filter_args
from .shortening import (
    DEFAULT_SHORT_POLICY,
    ShortPolicy,
    looks_like_short_spec,
    parse_short_spec,
)
from .tool_filter import ToolFilter, parse_tool_spec


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _fill_text(self, text: str, width: int, indent: str) -> str:
        r"""Wrap section lines without losing their indentation.

        >>> HelpFormatter("ch")._fill_text("  first second", 10, "")
        '  first\n  second'
        """
        return "\n".join(
            textwrap.fill(
                line,
                width,
                initial_indent=indent,
                subsequent_indent=indent + line[: len(line) - len(line.lstrip())],
            )
            for line in text.splitlines()
        )


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
    """Return True when `--short` was spelled with an attached `=SHORT_SPEC` value."""
    return any(token.startswith(("--short=", "-s=")) for token in argv_tokens)


def _resolve_short_policy(raw_short: bool | str | None) -> ShortPolicy | None:
    """Return the complete shortening policy requested by `--short`."""
    if raw_short is None:
        return None
    if raw_short is True:
        return DEFAULT_SHORT_POLICY
    return parse_short_spec(raw_short).resolve(DEFAULT_SHORT_POLICY)


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
    short_policy = _resolve_short_policy(args.short)
    return ConversationFlags(
        message_selection=message_selection,
        show_thinking=show_thinking,
        show_tools=_resolve_show_tools(args.tools, args.all),
        show_agents=args.agents or args.all,
        show_custom=args.all,
        show_branches=args.branches or args.all,
        show_plans=args.plans or args.all,
        allow_empty_output=message_selection != MessageSelection.ALL,
        shorten=short_policy is not None,
        shorten_max_chars=(short_policy or DEFAULT_SHORT_POLICY).max_chars,
        shorten_progressive=(short_policy or DEFAULT_SHORT_POLICY).progressive,
        shorten_thinking=shorten_thinking,
        color=args.color,
        paging=args.paging,
    )


def _resolve_parse_output_mode(args: argparse.Namespace) -> ParseOutputMode:
    """Resolve mutually-exclusive parse output-only flags into one mode."""
    if args.only_id:
        return ParseOutputMode.ONLY_ID
    if args.only_metadata:
        return ParseOutputMode.ONLY_METADATA
    return ParseOutputMode.FULL


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
    if looks_like_short_spec(args.short):
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
    if len(sys.argv) > 1 and sys.argv[1] == "name":
        # Parse name arguments
        parser = argparse.ArgumentParser(
            prog="ch name",
            description="Set the current title of a Claude Code, Codex, or Pi session.",
        )
        parser.add_argument(
            "conversation_id",
            help="Session ID, current title substring, summary prefix, recent index (-1, -2, ...), or file path",
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
            help="Print the title without writing it (--auto still calls pi)",
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
    elif len(sys.argv) > 1 and sys.argv[1] == "rm":
        # Parse rm arguments
        parser = argparse.ArgumentParser(
            prog="ch rm",
            description="Preview a session, then ask for confirmation before removal. "
            "Claude removal includes associated files and history entries. "
            "Codex and Pi removal deletes the session file only.",
        )
        parser.add_argument(
            "session",
            help="Session ID, current title substring, summary prefix, recent index (-1, -2, ...), or file path",
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
    elif len(sys.argv) > 1 and sys.argv[1] == "info":
        parser = argparse.ArgumentParser(
            prog="ch info",
            description="Show token usage, cost, durations, and message counts for a Claude or Pi session. "
            "Codex is not supported.",
        )
        parser.add_argument(
            "session",
            help="Session ID, current title substring, summary prefix, recent index (-1, -2, ...), or file path",
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
            usage="ch [options] [input] [selector ...]\n       ch COMMAND [options] ...",
            description="""\
Read and manage Claude Code, Codex, and Pi session histories.
Without a command, display a session or export it as XML, JSON, or Markdown.
By default, show the main conversation text. Add -t for tool calls and results, -T for thinking, or -a for messages from subagents and other sessions.

Commands:
  search   Find sessions by regex or AND/OR/NOT queries
  parse    Convert ch JSON exports to tagged Markdown, or back (-f json)
  name     Set a session title, or generate one with AI (--auto)
  rm       Preview and remove a session, with confirmation
  catalog  Catalog the first supplied session in sessions.yaml via pi
  info     Show tokens, cost, durations, and counts (Claude and Pi)

Search:
  ch search [options] PATTERN
  Search conversation text, current titles, and saved summaries across Claude, Codex, and Pi sessions.

  ch search 'docker AND timeout' -l
    List sessions containing both terms, even in different messages.
  ch search '.' -d . -ll
    Print IDs of sessions with searchable content in this directory.
  ch search 'error' -t e -f
    Search conversation text and failed tool results. Show the full matching sessions with the selected content options.

  Choose the search output:
    -l, --list             List matching sessions and metadata
    -ll, --only-id         Print only session IDs, without color or paging
    -f, --full             Show all included messages from matching sessions
    -r, --raw              Plain Markdown without metadata, color, or paging
  By default, show only matching messages. For 'docker AND timeout', a session must contain both terms, but each displayed message can contain either one.
  Search -f takes no format value. To export a result as JSON, use ch SESSION -f json.

  Write a query:
    Quote the whole query in the shell. Without boolean operators, it is one regex, including spaces. ^ and $ match line boundaries, and . also matches newlines. Invalid regex is searched literally without reporting the regex error.
    -s, --case-sensitive    Match letter case exactly
    -i, --case-insensitive  Make the default case-insensitive mode explicit
    Choose either -s or -i. In search, use --short for shortening, not -s.
    Uppercase AND / OR combine terms across the session. AND binds tighter. Use parentheses to group terms: 'docker AND (timeout OR crash)'.
    'docker NOT crash NOT timeout' requires docker and excludes sessions containing either excluded term. NOT cannot mix with AND/OR or boolean grouping parentheses.
    Within a boolean query, quote phrases and regex parentheses: '"error (code|status)" AND fix'. Unquoted words do not implicitly combine:
      'foo AND bar AND baz'   Require all three terms
      '"foo bar" AND baz'     Require the phrase foo bar and the term baz
    'foo bar AND baz' is an error. 'docker.* AND timeout' needs no inner quotes. For a pattern starting with a dash, use ch search -- '-flag'.

  Narrow the search:
    -d DIR matches the session's working directory exactly. -p chooses claude, pi, or codex. -ma DATE filters by last activity, and -ca DATE by creation. For example, -d . -p codex -ma 1w finds Codex sessions active here in the past week.
    The content options below also control what can match: -T makes thinking searchable, -t includes tools, and -a includes agents. -b and --plans include abandoned branches and plans. -A includes all these plus Pi custom records.
    --only-user/--only-assistant select user/assistant text and disable those additions. Titles and summaries can still match. --short changes the text before matching, so removed text cannot match. Progressive limits are assigned within each session before choosing matching messages.
    Search also accepts --color, --paging, --no-paging, and --no-metadata. See the shared content, tool-filter, shortening, and date explanations below.

  Results list recently modified files first. Date filters use timestamps inside the transcript, with filesystem times as fallback. File copies can therefore affect result order without changing the activity dates.
  Exit status: 0 means matches, 1 means no matches or a runtime error, and 2 means invalid arguments or query syntax.

  ch search --help shows search on its own.

Session display and export:
  The positional arguments and options below apply to ch SESSION.""",
            formatter_class=HelpFormatter,
            epilog="""\
Metadata:
  Metadata is a YAML record with the session ID, provider, working directory, history file, timestamps, and message count. It can also include a title or fork parent.
  ch -l -1 prints only this record for the newest session. ch -ll -1 prints only its ID. In search, -l lists matching sessions and their metadata, while -ll prints one ID per line. Use --color never for search metadata as YAML instead of a formatted list.
  Example record (history path abbreviated):
    session_id: 11111111-1111-4111-8111-111111111111
    provider: codex
    directory: ~/work/shop
    history_path: ~/.codex/sessions/.../session.jsonl
    created: "2026-09-27 09:00"
    modified: "2026-09-27 10:30"
    messages: 25
    custom_title: "Investigate timeouts"
  Search also reports matches and, when applicable, matched_summary. Fork ancestry appears as forked_from when available.

Examples:
  ch -p codex -d . -1
    Read the newest Codex session in this directory.
  ch -1 -t:s -- -5:
    Read the last five messages, with shortened tools.
  ch -1 -f json -o session.json
    Export the newest session as structured JSON.
  ch parse session.json
    Turn that JSON export into readable, XML-tagged Markdown.

Session lookup and message selection:
  Put the session first, then the message selectors: ch -1 1 shows the first message of the newest session. Recent sessions use negative numbers (-1, -2, ...). A bare ch 1 tries to find a session called 1.
  For other input, ch tries an existing file path, an exact session ID or filename, a current title substring, then a summary prefix. A title is the session name set with ch name or the provider's naming command. A summary is a description saved in the session history.
  Title and summary matching ignore case. Only the latest title is used. If several sessions match, use a more specific name or a session ID.
  The -- separator ends option parsing. In ch -1 -- -5:, this makes -5: a message range instead of an option.

Additional content:
  Subagents are agents launched to help the main assistant. -a also includes messages from other sessions and agent work recorded by Pi. Claude /fork conversations, which continue from an existing conversation, are included too.
  Rewind branches are messages abandoned when you rewind and try a different prompt. Include them with -b.
  Pi custom records are extra entries written by Pi extensions. Include them with -A.

Tool filters (also available in search):
  Bare -t includes all tool calls and results, alongside the main conversation text.
  Add a filter to choose which tools to include:
    -t Bash        Include Bash calls and results
    -t Bash:i      Include Bash calls only
    -t Read:o      Include Read results only
    -t e           Include failed results from any tool
    -t Bash:e      Include failed Bash results only
    -t '!Bash'     Include every tool except Bash
  Within one filter, all colon-separated conditions must match (AND). Between filters, any match is enough (OR).
  For example, -t Read:o -t Bash:i includes Read results and Bash calls. You can also write -t 'Read:o Bash:i'.
  Put ! first to exclude matches. Exclusions take priority over inclusions.
  Use i/input for calls, o/output for results, and e/error for failures. Order is flexible: Read:o and o:Read mean the same thing.
  Names match exactly, with known aliases: Codex exec_command also matches Bash.
  Equivalent forms: -t FILTER, -t:FILTER, --tools FILTER, --tools=FILTER.
  --all ignores tool filters and includes all tools.

Shortening:
  Shortening is a powerful means to understand what a session of potentially hundreds of messages is about while keeping the token cost of consuming it low. It is the recommended approach to start with when looking up content across and within sessions to pin down where, in that large search space, to zoom in without shortening (it's recall first, precision later). The shortening API is optimized to enable effective and efficient searches of vague purposes over a large data space without costing the searching agent its entire context window.
  --short limits each message body, thinking block, plan, and tool text value to a default of 500 characters. A tool's command and output each get their own limit. This is not a total output budget.
  Shortened text is truncated in the middle. This because the start and end of a message typically has the more important information.
  --short=200 limits each to 200 characters.
  Bare --short uses a fixed limit of 500. Numeric limits must be at least 8.
  --short=p=200 keeps more detail toward the end of the conversation. Among the messages you include using this mode, limits grow evenly from 8 for the first to 200 for the last. Three messages get 8, 104, and 200. A single message gets 200.
  Message selection happens first. For example, ch -1 --short=p=200 -- -5: spreads the limits from 8 to 200 across the last five messages, rather than the whole conversation. Metadata is never shortened.
  Accepted values: N, p, progressive, p=N, progressive=N. N is the character limit. p and progressive mean the same thing and default to a final limit of 500.
  Both --short VALUE and --short=VALUE work, as does -s. With =, the value unambiguously belongs to --short. For example:
    ch -1 -s=200 -- 3
      Show message 3 of the newest session, with a 200-character limit.

Shortening tools:
  Use -t s to shorten tools alone to 500 characters. You can attach the value to the option as -t:s. A --short setting changes this default.
  Add s or short to any tool filter. Both accept the same values as --short:
    -t Read:o:s=80       Limit each Read output text value to 80 characters
    -t Read:o:short=p=80 Grow Read output limits from 8 to 80
  Bare :s copies both the limit and mode from --short. :s=p copies only the limit and switches to progressive mode:
    --short=200 -t Read:o:s=p
      Grow Read output limits from 8 to 200. Other text stays fixed at 200.
  To give one tool more room than the rest:
    -t:s=80 -t Bash:s=200
      Give Bash a limit of 200 and other tools 80. The Bash filter wins because it adds a tool-name condition.
  Count one condition for a tool name, one for input/output, and one for error. s and short do not count. More conditions win. If counts tie, the last filter wins. Only the winning filter controls shortening. Limits are never added or combined.

Dates:
  -ma and -ca accept YYYY-MM-DD or YY-MM-DD. Add a time with T or a space, for example -ma '2026-09-27 14:30:45'. Seconds are optional.
  Relative ages count back from now: 1h, 2d, 3w, 4m (30-day months), 5y (365-day years).

Copied files and pasted transcripts:
  A raw CLI transcript is copied terminal text: user messages start with > and assistant replies with ⏺. Save it to a file or pipe it into ch.
  You can read a copied Codex or Pi JSONL file from any directory. Keep its first JSON record: type=session_meta for Codex, or type=session with an integer version for Pi. This identifies the provider.
  Claude files have no such identifying record. Read them from ~/.claude/projects instead. A copied Claude file, or external JSONL without a recognized first record, is rejected.
""",
        )

        parser.add_argument(
            "input",
            nargs="?",
            help="Session ID, file path, or -1 for newest (see Session lookup). "
            "Omit to read content or a session ID from stdin.",
        )
        parser.add_argument(
            "slice",
            nargs="?",
            metavar="selector",
            help="Message index or range: 1 = first, -1 = last, 2:5 = messages 2 through 4. "
            "Open ranges: 2:, :-2, -5:. Repeat to combine selections without duplicates. "
            "Put negative ranges after --.",
        )
        parser.add_argument(
            "-o",
            "--out",
            type=Path,
            help="Write plain output to a file (default: stdout)",
        )
        parser.add_argument(
            "-l",
            "--only-metadata",
            action="store_true",
            help="Print only YAML metadata (requires a session or file)",
        )
        parser.add_argument(
            "-ll",
            "--only-id",
            action="store_true",
            help="Show only the resolved session ID, without color or paging",
        )
        parser.add_argument(
            "-T",
            "--thinking",
            nargs="?",
            const="full",
            default=None,
            metavar="{full,short}",
            help="Include full thinking. -T short limits it to 500 characters, replaced by --short if set",
        )
        parser.add_argument(
            "--only-user",
            action="store_true",
            help="Only user text. Overrides -T, -t, -a, --plans, and -A",
        )
        parser.add_argument(
            "--only-assistant",
            action="store_true",
            help="Only assistant text. Overrides -T, -t, -a, --plans, and -A",
        )
        parser.add_argument(
            "--no-user",
            action="store_true",
            help="Hide main user text, keeping enabled tools and agents",
        )
        parser.add_argument(
            "--no-assistant",
            action="store_true",
            help="Hide main assistant text, keeping enabled thinking, tools, and agents",
        )
        parser.add_argument(
            "-t",
            "--tools",
            action="append",
            nargs="?",
            const=True,
            default=None,
            help="Include all tool calls and results, or choose with a filter (below)",
        )
        add_pool_filter_args(
            parser,
            description="For ch -1, -2, ... these filters choose which sessions to count. For example, ch -p codex -1 selects the newest Codex session. Other input forms ignore these filters.\n"
            "Newest uses the last timestamp inside the transcript. If none is readable, use the file's modification time.\n"
            "These session lookups exclude separate Claude subagent files.",
            provider_help="Choose a provider before selecting -1, -2, ...",
            dir_help="Match the working directory before selecting -1, -2, ...",
            mafter_help="Sessions modified on or after DATE",
            cafter_help="Sessions created on or after DATE",
        )
        parser.add_argument(
            "-a",
            "--agents",
            action="store_true",
            help="Include messages from subagents and other sessions",
        )
        parser.add_argument(
            "-b",
            "--branches",
            action="store_true",
            help="Include abandoned Claude rewind branches",
        )
        parser.add_argument(
            "-A",
            "--all",
            action="store_true",
            help="Include thinking, tools, agents, branches, plans, and Pi custom records",
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
            help="Shorten message and tool text (see Shortening below)",
        )
        parser.add_argument(
            "--color",
            choices=["always", "never", "auto"],
            default="auto",
            help="Formatted terminal display (auto: on in a terminal, off in pipes)",
            type=init_module_console_from_color_arg,
        )
        parser.add_argument(
            "-f",
            "--format",
            choices=["xml", "json", "raw"],
            default="xml",
            help="xml (default), structured json, or raw Markdown",
        )
        parser.add_argument(
            "-r",
            "--raw",
            action="store_true",
            help="Plain Markdown without metadata (same as -f raw)",
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
            help="Hide session metadata (XML with --color never sends it to stderr)",
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
