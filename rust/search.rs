//! The `ch search` argument grammar.
//!
//! Usage and help follow the original argparse layout and are
//! **rewrapped to the terminal width**, so they cannot be
//! static constants — the abandoned branch made exactly that mistake. Wrapping
//! is ported from Python's `textwrap`, including its hyphen rule, which is why
//! `--no-paging` splits after `--no-` at narrow widths.
//!
//! The option *text* is fixed and encoded directly. Only the layout is computed,
//! so this ports the dynamic half of argparse and nothing more.

use crate::visibility::SearchOutputMode;

pub mod parse;
pub mod plan;

/// One row of the help body, and its usage fragment.
struct Action {
    /// How the option appears in the left column of the help body.
    invocation: &'static str,
    help: &'static str,
}

/// A titled block of the help body. Order is argparse's: positionals, then
/// options, then each argument group in the order it was added.
struct Section {
    title: &'static str,
    actions: &'static [Action],
}

const POSITIONALS: &[Action] = &[Action {
    invocation: "pattern",
    help: "Regex or uppercase AND/OR/NOT query (see syntax below)",
}];

const OPTIONS: &[Action] = &[
    Action { invocation: "-h, --help", help: "show this help message and exit" },
    Action { invocation: "-l, --list", help: "List matching sessions and metadata (see Metadata below)" },
    Action {
        invocation: "-ll, --only-id",
        help: "Show only matching session IDs (implies --color never and --no-paging)",
    },
    Action {
        invocation: "-f, --full",
        help: "Show full matching conversations instead of only matching messages",
    },
    Action {
        invocation: "-r, --raw",
        help: "Plain Markdown output, without metadata, color, or paging",
    },
    Action {
        invocation: "-T, --thinking [{full,short}]",
        help: "Search and show full thinking. -T short limits it to 500 characters, replaced by --short if set",
    },
    Action {
        invocation: "--only-user",
        help: "Search and display only user text (see Search scope below)",
    },
    Action {
        invocation: "--only-assistant",
        help: "Search and display only assistant text (see Search scope below)",
    },
    Action {
        invocation: "-t, --tools [TOOLS]",
        help: "Include all tool calls and results, or choose with a filter (below)",
    },
    Action {
        invocation: "-a, --agents",
        help: "Include messages from subagents and other sessions",
    },
    Action {
        invocation: "-b, --branches",
        help: "Include abandoned Claude rewind branches",
    },
    Action {
        invocation: "-A, --all",
        help: "Include thinking, tools, agents, branches, plans, and Pi custom records",
    },
    Action { invocation: "--plans", help: "Show plan content (ExitPlanMode)" },
    Action {
        invocation: "-s, --case-sensitive",
        help: "Match letter case exactly",
    },
    Action {
        invocation: "-i, --case-insensitive",
        help: "Make the default case-insensitive mode explicit",
    },
    Action {
        invocation: "--short [SHORT]",
        help: "Shorten text before matching and display (see Shortening below)",
    },
    Action {
        invocation: "--color {always,never,auto}",
        help: "Formatted terminal display (auto: on in a terminal, off in pipes)",
    },
    Action {
        invocation: "--paging",
        help: "Enable paging (default: same as color)",
    },
    Action { invocation: "--no-paging", help: "Disable paging" },
    Action {
        invocation: "--no-metadata",
        help: "Disable outputting metadata frontmatter",
    },
];

const POOL_FILTERS: &[Action] = &[
    Action {
        invocation: "-d, --dir DIR",
        help: "Match the session working directory exactly (not its subdirectories)",
    },
    Action {
        invocation: "-ma, --mafter DATE",
        help: "Sessions modified on or after DATE",
    },
    Action {
        invocation: "-ca, --cafter DATE",
        help: "Sessions created on or after DATE",
    },
    Action {
        invocation: "-p, --provider {claude,pi,codex}",
        help: "Restrict search to sessions from a specific provider",
    },
];

const SECTIONS: &[Section] = &[
    Section { title: "positional arguments", actions: POSITIONALS },
    Section { title: "options", actions: OPTIONS },
    Section { title: "session pool filters", actions: POOL_FILTERS },
];

const DESCRIPTION: &str = "Search Claude Code, Codex, and Pi sessions. By default, search the main conversation text, summaries, and latest title. The same options control what search can match and what it displays. For example, -t makes tool calls and results searchable.";

const GUIDE: &str = r#"Query syntax:
  Regex is case-insensitive by default. ^ and $ match line boundaries, and . also matches newlines. If a regex is invalid, ch searches that text literally without reporting the regex error.
  Quote the whole query in the shell so spaces and special characters reach ch unchanged.
  Put patterns starting with a dash after --: ch search -- '-flag'.
  AND / OR combine terms across the whole session, including different messages. AND binds tighter than OR. Parentheses group terms.
  By default, show only matching messages. For 'docker AND timeout', a session must contain both terms, but each displayed message can contain either one. Use -f to show all included messages from that session.
  A NOT B NOT C requires A and excludes sessions containing B or C.
  Mixed queries such as 'docker AND timeout NOT crash' are not supported. NOT cannot mix with AND/OR or boolean grouping parentheses.
  Operators must be uppercase. Without them, the whole query is one regex, including spaces.
  In a boolean query, words do not implicitly combine. 'foo bar AND baz' is an error. Choose between:
    'foo AND bar AND baz'   Require all three terms
    '"foo bar" AND baz'     Require the phrase foo bar and the term baz
  Within a boolean query, also quote any term containing spaces or regex parentheses: '"error (code|status)" AND fix'. Without inner quotes, spaces separate terms and parentheses group boolean expressions.
  Regex terms without spaces or parentheses need no inner quotes:
    ch search 'docker.* AND timeout'

Examples:
  ch search 'docker AND (timeout OR crash)' -l
    List sessions containing docker and either timeout or crash.
  ch search '"hello world" NOT goodbye' -p codex -ma 1w
    Find Codex sessions active in the past week containing hello world but no goodbye.
  ch search 'error' -t e -f
    Search main conversation text and failed tool results. Show all included messages from each matching session.
  ch search '.' -d . -ll
    Print IDs of sessions with searchable content in the current working directory.

Additional content:
  Subagents are agents launched to help the main assistant. -a also includes messages from other sessions and agent work recorded by Pi. Search checks separate Claude subagent transcripts, including /fork conversations that continue from an existing conversation, when -a is enabled.
  Rewind branches are messages abandoned when you rewind and try a different prompt. Include them with -b.
  Pi custom records are extra entries written by Pi extensions. Include them with -A.

Tool filters:
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
  --short=p=200 keeps more detail toward the end of each conversation. Among the messages you include using this mode, limits grow evenly from 8 for the first to 200 for the last. Three messages get 8, 104, and 200. A single message gets 200.
  Search assigns these limits before looking for matches. Text removed by shortening cannot match. Titles and summaries are never shortened.
  Accepted values: N, p, progressive, p=N, progressive=N. N is the character limit. p and progressive mean the same thing and default to a final limit of 500.
  Both --short VALUE and --short=VALUE work. Search reserves -s for case-sensitive matching.

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

Search scope and output:
  A title is the session name set with ch name or the provider's naming command. A summary is a description saved in the session history.
  --only-user/--only-assistant disable thinking, tools, agents, plans, and --all. Titles and summaries can still return a session even when no selected message matches.
  Unlike ch SESSION, search uses -f for full sessions and -s for case-sensitive matching. -f takes no value. Search has no JSON output mode. To export one result, use ch SESSION -f json.

Metadata:
  Metadata is a YAML record with the session ID, provider, working directory, history file, timestamps, message count, and match count. It can also include a title, fork parent, or matched summary.
  -l lists matching sessions and their metadata. Add --color never to show YAML instead of a formatted list. -ll prints only session IDs, one per line. For one session's metadata alone, use ch -l SESSION.
  Example block (history path abbreviated):
    session_id: 11111111-1111-4111-8111-111111111111
    provider: codex
    directory: ~/work/shop
    history_path: ~/.codex/sessions/.../session.jsonl
    created: "2026-09-27 09:00"
    modified: "2026-09-27 10:30"
    messages: 25
    matches: 2
    custom_title: "Investigate timeouts"
  Optional fields also include forked_from and matched_summary.

Dates and result order:
  Use -ma and -ca to filter by conversation activity. Search lists recently modified files first so results can appear as they are found. Date filters use timestamps inside the transcript, with filesystem times as fallback. Copying or touching a file can therefore change its search position without changing which dates it matches.
  This differs from ch -1, which selects the newest session by its last transcript timestamp.
  -ma and -ca accept YYYY-MM-DD or YY-MM-DD. Add a time with T or a space, for example -ma '2026-09-27 14:30:45'. Seconds are optional.
  Relative ages count back from now: 1h, 2d, 3w, 4m (30-day months), 5y (365-day years).

Exit status:
  0 means matches, 1 means no matches or a runtime error, and 2 means invalid arguments or query syntax.
"#;

/// Usage fragments in argparse's order: optionals first, then positionals.
/// `-d`, `-ma`, `-ca` and `-p` sit where `add_pool_filter_args` inserted them.
const USAGE_ORDER: &[&str] = &[
    "[-h]", "[-l]", "[-ll]", "[-f]", "[-r]",
    "[-d DIR]", "[-ma DATE]", "[-ca DATE]", "[-p {claude,pi,codex}]",
    "[-T [THINKING]]", "[--only-user]", "[--only-assistant]", "[-t [TOOLS]]",
    "[-a]", "[-b]", "[-A]", "[--plans]",
    // A mutually exclusive group stays as separate parts, each carrying its own
    // share of the brackets and pipe, so a line break can fall inside it.
    "[-s |", "-i]",
    "[--short [SHORT]]",
    "[--color {always,never,auto}]", "[--paging]", "[--no-paging]", "[--no-metadata]",
    "[pattern]",
];

pub const PROGRAM: &str = "ch search";
const USAGE_PREFIX: &str = "usage: ";

/// argparse's help column cap (`HelpFormatter.max_help_position`).
const MAX_HELP_POSITION: usize = 24;

/// argparse's `indent_increment`: actions sit one level inside their section.
const SECTION_INDENT: usize = 2;

/// argparse builds its formatter with `width = terminal_columns - 2`.
fn text_width(columns: usize) -> usize {
    columns.saturating_sub(2).max(11)
}

pub mod wrap;
pub use wrap::wrap;

/// Pack `parts` into lines no wider than `width`, argparse's `get_lines`.
///
/// The first line carries `prefix` instead of `indent` when one is given, which
/// is how `usage: ` and the program name share the opening line.
fn get_lines(parts: &[&str], indent: &str, prefix: Option<&str>, width: usize) -> Vec<String> {
    let mut lines: Vec<String> = Vec::new();
    let mut line: Vec<&str> = Vec::new();
    let start = prefix.map_or(indent.len(), str::len);
    let mut line_length = start.saturating_sub(1);
    for part in parts {
        if line_length + 1 + part.len() > width && !line.is_empty() {
            lines.push(format!("{indent}{}", line.join(" ")));
            line.clear();
            line_length = indent.len().saturating_sub(1);
        }
        line.push(part);
        line_length += 1 + part.len();
    }
    if !line.is_empty() {
        lines.push(format!("{indent}{}", line.join(" ")));
    }
    if prefix.is_some() && !lines.is_empty() {
        lines[0] = lines[0][indent.len().min(lines[0].len())..].to_string();
    }
    lines
}

/// The `usage: ...` block, wrapped to `columns`, without its trailing blank line.
pub fn format_usage(columns: usize) -> String {
    let width = text_width(columns);
    let parts: Vec<&str> = USAGE_ORDER.to_vec();
    let single = format!("{PROGRAM} {}", parts.join(" "));
    if USAGE_PREFIX.len() + single.len() <= width {
        return format!("{USAGE_PREFIX}{single}");
    }

    let optionals: Vec<&str> = parts.iter().copied().filter(|p| *p != "[pattern]").collect();
    let positionals: Vec<&str> = vec!["[pattern]"];

    // argparse only aligns under the program name when that leaves room to work
    // with; otherwise it falls back to a flat indent.
    if USAGE_PREFIX.len() + PROGRAM.len() <= (width * 3) / 4 {
        let indent = " ".repeat(USAGE_PREFIX.len() + PROGRAM.len() + 1);
        let mut head: Vec<&str> = vec![PROGRAM];
        head.extend(optionals);
        let mut lines = get_lines(&head, &indent, Some(USAGE_PREFIX), width);
        lines.extend(get_lines(&positionals, &indent, None, width));
        return format!("{USAGE_PREFIX}{}", lines.join("\n"));
    }

    let indent = " ".repeat(USAGE_PREFIX.len());
    let mut lines = vec![PROGRAM.to_string()];
    lines.extend(get_lines(&optionals, &indent, None, width));
    lines.extend(get_lines(&positionals, &indent, None, width));
    let first = lines.remove(0);
    format!("{USAGE_PREFIX}{first}\n{}", lines.join("\n"))
}

/// Where the help column starts.
///
/// argparse caps this against the terminal width as well as its own constant:
/// `min(max_help_position, max(width - 20, indent_increment * 2))`. Without the
/// width term every narrow terminal lays the help body out wrongly.
fn help_position(width: usize) -> usize {
    let action_max_length = SECTIONS
        .iter()
        .flat_map(|section| section.actions.iter())
        .map(|action| action.invocation.len() + SECTION_INDENT)
        .max()
        .unwrap_or(0);
    let cap = MAX_HELP_POSITION.min(width.saturating_sub(20).max(SECTION_INDENT * 2));
    (action_max_length + 2).min(cap)
}

/// The complete `--help` output, wrapped to `columns`.
pub fn format_help(columns: usize) -> String {
    let width = text_width(columns);
    let position = help_position(width);
    let help_width = width.saturating_sub(position).max(11);
    let mut out = format!(
        "usage: {PROGRAM} [options] pattern\n\n{}\n",
        wrap(DESCRIPTION, width).join("\n"),
    );

    for section in SECTIONS {
        out.push_str(&format!("\n{}:\n", section.title));
        // argparse pads the invocation to this width, then two spaces, which is
        // what puts the help text exactly at `position`.
        let action_width = position.saturating_sub(SECTION_INDENT + 2);
        for action in section.actions {
            let indent = " ".repeat(SECTION_INDENT);
            let lines = wrap(action.help, help_width);
            if action.invocation.len() <= action_width {
                let pad = action_width - action.invocation.len();
                out.push_str(&format!(
                    "{indent}{}{}  {}\n",
                    action.invocation,
                    " ".repeat(pad),
                    lines.first().map(String::as_str).unwrap_or("")
                ));
                for line in lines.iter().skip(1) {
                    out.push_str(&format!("{}{line}\n", " ".repeat(position)));
                }
            } else {
                // Too long to share the line: argparse drops the help to the next.
                out.push_str(&format!("{indent}{}\n", action.invocation));
                for line in &lines {
                    out.push_str(&format!("{}{line}\n", " ".repeat(position)));
                }
            }
        }
    }
    out.push('\n');
    for line in GUIDE.lines() {
        let indentation = line.len() - line.trim_start().len();
        let wrapped = crate::terminal::wrap_preserving_spaces(
            line.trim_start(), width.saturating_sub(indentation).max(11),
        );
        if wrapped.is_empty() {
            out.push('\n');
        }
        for line in wrapped.lines() {
            out.push_str(&format!("{}{}\n", " ".repeat(indentation), line.trim_end()));
        }
    }
    out
}

#[cfg(test)]
mod width_parity {
    use super::*;

    #[test]
    fn help_fits_narrow_and_wide_terminals() {
        for columns in [40, 60, 80, 96, 120, 200] {
            let help = format_help(columns);
            assert!(
                help.lines().all(|line| line.len() <= columns),
                "Help must fit a {columns}-column terminal:\n{help}"
            );
            assert!(
                help.contains("Query syntax:") && help.contains("Tool filters:"),
                "Advanced syntax must remain available at {columns} columns."
            );
        }
    }

    #[test]
    fn help_uses_the_available_width() {
        let narrow = format_help(60);
        let wide = format_help(120);
        assert!(
            narrow.lines().count() > wide.lines().count(),
            "A wider terminal should need fewer wrapped lines."
        );
        assert!(
            wide.lines().any(|line| line.len() > 60),
            "Wide help must use the available space rather than a fixed narrow layout."
        );
    }
}

/// The bytes `ch search --help` writes to stdout.
pub fn render_help(columns: usize) -> String {
    format_help(columns)
}

/// The bytes argparse writes to stderr before exiting 2.
///
/// argparse prints the usage block, then the error line. Both are wrapped to
/// argparse's own width rule, which is not Rich's — see
/// [`crate::terminal::argparse_columns`].
pub fn render_error(message: &str, columns: usize) -> String {
    format!("{}\n{PROGRAM}: error: {message}\n", format_usage(columns))
}

#[cfg(test)]
mod render_parity {
    use super::*;
    use crate::search::parse::{SearchOutcome, parse_search_arguments};
    use std::ffi::OsString;
    use std::path::PathBuf;
    use std::process::Command;

    const REJECTED: &[&[&str]] = &[
        &[],
        &["needle", "extra"],
        &["needle", "--bogus"],
        &["-s", "-i", "needle"],
        &["--color", "bogus", "needle"],
        &["-p", "bogus", "needle"],
        &["-T", "bogus", "needle"],
    ];

    fn oracle(tokens: &[&str], columns: usize) -> (i32, Vec<u8>, Vec<u8>) {
        let binary = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".venv/bin/ch-legacy");
        assert!(binary.exists(), "Expected the Python oracle at {binary:?}.");
        let home = std::env::temp_dir().join("ch-render-parity-home");
        std::fs::create_dir_all(&home).expect("create isolated home");
        let output = Command::new(&binary)
            .arg("search")
            .args(tokens)
            .env("HOME", &home)
            .env("COLUMNS", columns.to_string())
            .stdin(std::process::Stdio::null())
            .output()
            .expect("run the Python oracle");
        assert_oracle_did_not_crash(&output.stderr);
        (
            output.status.code().unwrap_or(-1),
            output.stdout,
            output.stderr,
        )
    }

    /// The oracle imports `chats` from the live `src/` tree, which other sessions
    /// edit, so a mid-save crash gives an empty stdout and a traceback. That is a
    /// **precondition** failure, not a disagreement — asserting it here makes the
    /// message name the real cause instead of accusing the implementation.
    ///
    /// Deliberately not `status.success()`: a rejected argv legitimately exits 2
    /// and a fruitless search exits 1, so the status is the caller's to compare.
    /// The question here is only whether the oracle ran at all.
    fn assert_oracle_did_not_crash(stderr: &[u8]) {
        let text = String::from_utf8_lossy(stderr);
        assert!(
            !text.contains("Traceback (most recent call last):"),
            "The Python oracle crashed rather than disagreeing. stderr:\n{text}"
        );
    }

    /// Whole stderr, not just the message: the usage block is wrapped by the
    /// same width rule and a wrong one would still produce the right message.
    #[test]
    fn rejected_argv_reproduces_argparse_stderr_byte_for_byte() {
        for columns in [40usize, 60, 96, 140] {
            for tokens in REJECTED {
                let (status, _, stderr) = oracle(tokens, columns);
                assert_eq!(status, 2, "Expected argparse to reject {tokens:?}.");
                let argv: Vec<OsString> = tokens.iter().map(OsString::from).collect();
                let SearchOutcome::Error(message) = parse_search_arguments(&argv).outcome else {
                    panic!("Expected {tokens:?} to be rejected by the native grammar.");
                };
                assert_eq!(
                    render_error(&message, columns).into_bytes(),
                    stderr,
                    "stderr diverged for {tokens:?} at COLUMNS={columns}."
                );
            }
        }
    }

    #[test]
    fn help_matches_the_reviewed_page() {
        assert_eq!(
            render_help(96),
            include_str!("../tests/data/help/search-96.txt"),
            "Help changed from the reviewed page. Review the change before updating the fixture."
        );
    }
}

/// The "no sessions match" hint, or `None` when the mode suppresses it.
///
/// The tail of the `Run` arm. Port of `_emit_no_results`: the hint goes to
/// stderr and is suppressed under `--only-id`, whose whole contract is that
/// stdout carries session ids and nothing else.
///
/// `filter_is_empty` is the *filter's* emptiness, not "a filter is active" —
/// the suffix appears when the filter is **not** empty, and inverting that
/// silently swaps the two messages.
///
/// An empty pool prints nothing at all and still exits 1. That case does not
/// reach here: `Outcome::wants_no_results_hint` is false for `EmptyPool`, and
/// collapsing the two is a one-line simplification that changes observable
/// output.
pub fn render_no_results_hint(
    pattern: &str,
    filter_is_empty: bool,
    output_mode: SearchOutputMode,
) -> Option<String> {
    if output_mode == SearchOutputMode::OnlyId {
        return None;
    }
    let suffix = if filter_is_empty {
        ""
    } else {
        " with the current filters"
    };
    Some(format!("No sessions match \"{pattern}\"{suffix}.\n"))
}

#[cfg(test)]
mod no_results_tests {
    use super::*;

    // Both forms are recorded in probes/grammar-oracle.json, captured from
    // `ch-legacy`: a bare miss and a miss under `-ma 1d`.
    #[test]
    fn the_two_hint_forms_match_the_recorded_oracle() {
        assert_eq!(
            render_no_results_hint("needle", true, SearchOutputMode::Matches).as_deref(),
            Some("No sessions match \"needle\".\n"),
            "Expected the unfiltered hint to match the recorded oracle bytes."
        );
        assert_eq!(
            render_no_results_hint("needle", false, SearchOutputMode::Matches).as_deref(),
            Some("No sessions match \"needle\" with the current filters.\n"),
            "Expected the filtered hint to match the recorded oracle bytes."
        );
    }

    #[test]
    fn a_lone_dash_pattern_is_quoted_verbatim() {
        assert_eq!(
            render_no_results_hint("-", true, SearchOutputMode::Matches).as_deref(),
            Some("No sessions match \"-\".\n"),
            "Expected the pattern to be interpolated as-is, matching the oracle."
        );
    }

    /// `--only-id` promises stdout carries ids and nothing else, and the hint
    /// would be the one thing on stderr that a caller piping ids does not want.
    #[test]
    fn only_id_suppresses_the_hint_but_not_the_exit_status() {
        assert_eq!(
            render_no_results_hint("needle", true, SearchOutputMode::OnlyId),
            None,
            "Expected `--only-id` to suppress the hint."
        );
    }

    #[test]
    fn every_other_mode_prints_it() {
        for mode in [
            SearchOutputMode::Matches,
            SearchOutputMode::Full,
            SearchOutputMode::List,
        ] {
            assert!(
                render_no_results_hint("needle", true, mode).is_some(),
                "Expected {mode:?} to print the hint; only `--only-id` suppresses it."
            );
        }
    }
}
