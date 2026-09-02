//! The `ch search` argument grammar.
//!
//! Truth is CPython `argparse` as configured in `src/chats/cli.py`. Usage and
//! help are **rewrapped to the terminal width** by argparse, so they cannot be
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
    help: "Pattern to search for",
}];

const OPTIONS: &[Action] = &[
    Action { invocation: "-h, --help", help: "show this help message and exit" },
    Action { invocation: "-l, --list", help: "List mode - show only paths and metadata" },
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
        help: "Alias for raw markdown search output (implies --no-metadata, --color never, and --no-paging)",
    },
    Action {
        invocation: "-T, --thinking [THINKING]",
        help: "Show thinking tokens (optional: short)",
    },
    Action {
        invocation: "--only-user",
        help: "Search only regular user message bodies",
    },
    Action {
        invocation: "--only-assistant",
        help: "Search only regular assistant message bodies",
    },
    Action {
        invocation: "-t, --tools [TOOLS]",
        help: "Show tool use/result details (optional: filter with modifiers, e.g. 'Bash:i', 'Read:o:s', '!Bash')",
    },
    Action {
        invocation: "-a, --agents",
        help: "Include agent messages and Pi agent custom records",
    },
    Action {
        invocation: "-b, --branches",
        help: "Include messages from abandoned (rewound) branches",
    },
    Action {
        invocation: "-A, --all",
        help: "Show everything, including arbitrary Pi custom records",
    },
    Action { invocation: "--plans", help: "Show plan content (ExitPlanMode)" },
    Action {
        invocation: "-s, --case-sensitive",
        help: "Match letter case exactly (default: false)",
    },
    Action {
        invocation: "-i, --case-insensitive",
        help: "Ignore letter case (default: true)",
    },
    Action {
        invocation: "--short [SHORT]",
        help: "Shorten strings in output (optional: SHORT_SPEC, e.g. p=128)",
    },
    Action {
        invocation: "--color {always,never,auto}",
        help: "Control Rich formatting: always, never, or auto (default: auto)",
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
        help: "Restrict search to conversations in this directory",
    },
    Action {
        invocation: "-ma, --mafter DATE",
        help: "Only conversations modified after DATE (e.g., 2024-12-15, 1d, 2w)",
    },
    Action {
        invocation: "-ca, --cafter DATE",
        help: "Only conversations created after DATE",
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
    let mut out = format!("{}\n", format_usage(columns));

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
    out
}

#[cfg(test)]
mod width_parity {
    use super::*;
    use std::path::PathBuf;
    use std::process::Command;

    /// Narrow overflow, the boundaries either side of the longest help line,
    /// and a spread up to wide. The full 20..=200 sweep lives in
    /// `teammates/search-runtime/probes/help_width_sweep.py`.
    const WIDTHS: [usize; 12] = [20, 27, 46, 47, 48, 49, 60, 79, 80, 96, 120, 200];

    fn oracle() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".venv/bin/ch-legacy")
    }

    fn argparse_help(columns: usize) -> String {
        let oracle = oracle();
        assert!(
            oracle.exists(),
            "Expected the Python oracle at {oracle:?}; run `uv sync --dev`."
        );
        let home = std::env::temp_dir().join("ch-help-parity-home");
        std::fs::create_dir_all(&home).expect("create isolated home");
        let output = Command::new(&oracle)
            .args(["search", "--help"])
            .env("HOME", &home)
            .env("COLUMNS", columns.to_string())
            .stdin(std::process::Stdio::null())
            .output()
            .expect("run the Python oracle");
        // Without this the test cannot tell "our formatter diverged" from "the
        // oracle crashed": `ch-legacy` imports from the live `src/` tree, so a
        // peer mid-save makes it exit non-zero with empty stdout, which then
        // compares as a parity failure and blames the wrong file.
        assert!(
            output.status.success(),
            "The Python oracle failed rather than disagreeing. stderr:\n{}",
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8(output.stdout).expect("oracle help is UTF-8")
    }

    // argparse rewraps help to the terminal, so this cannot be a static string.
    // The abandoned branch shipped it as one and passed its own 704-case corpus,
    // because every case in that corpus pinned COLUMNS=96.
    #[test]
    fn help_matches_argparse_at_every_width() {
        for columns in WIDTHS {
            assert_eq!(
                format_help(columns),
                argparse_help(columns),
                "Help output diverged from argparse at COLUMNS={columns}."
            );
        }
    }

    /// A gate that has never been observed to fail is not yet evidence.
    ///
    /// Pinning one width, which is what a width-blind implementation does, must
    /// disagree with argparse at the other widths.
    #[test]
    fn the_parity_test_would_catch_a_width_blind_formatter() {
        let pinned = format_help(96);
        let disagreements = WIDTHS
            .iter()
            .filter(|columns| **columns != 96)
            .filter(|columns| pinned != argparse_help(**columns))
            .count();
        assert_eq!(
            disagreements,
            WIDTHS.len() - 1,
            "Expected a width-blind formatter to disagree with argparse at every \
             other width, which is what makes the parity test above meaningful."
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
    fn help_reproduces_argparse_stdout_byte_for_byte() {
        for columns in [40usize, 60, 96, 140] {
            let (status, stdout, _) = oracle(&["--help"], columns);
            assert_eq!(status, 0, "Expected `--help` to exit 0.");
            assert_eq!(
                render_help(columns).into_bytes(),
                stdout,
                "help stdout diverged at COLUMNS={columns}."
            );
        }
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
