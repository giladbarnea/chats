//! The native `ch search` route, standing in for the cutover that has not happened.
//!
//! This is the three-arm function `search-runtime` will add to `rust/main.rs`,
//! nothing more, so a byte differential against `ch-legacy search` can run before
//! the route is live. Keeping it out of `main.rs` keeps the charter's rule that
//! there is exactly one cutover moment.
use std::ffi::OsString;
use std::process::ExitCode;

use _native::search::parse::{SearchOutcome, parse_search_arguments};
use _native::search::{render_error, render_help};
use _native::search_run::run;
use _native::terminal::{argparse_columns, terminal_width};

fn main() -> ExitCode {
    let arguments: Vec<OsString> = std::env::args_os().skip(1).collect();
    let parsed = parse_search_arguments(&arguments);
    for warning in &parsed.warnings {
        eprint!("{warning}");
    }
    match parsed.outcome {
        SearchOutcome::Help => {
            print!("{}", render_help(argparse_columns()));
            ExitCode::SUCCESS
        }
        SearchOutcome::Error(message) => {
            eprint!("{}", render_error(&message, argparse_columns()));
            ExitCode::from(2)
        }
        SearchOutcome::Run(args) => {
            let status = run(&args, &home_directory(), terminal_width());
            ExitCode::from(status as u8)
        }
    }
}

/// The session root, resolved exactly as Python's `Path.home()` does.
///
/// **Three branches, because `posixpath.expanduser` distinguishes three states and
/// a `home_dir`-shaped convenience call collapses two of them.** All measured
/// against `ch-legacy search`:
///
/// | `HOME` | legacy | `std::env::home_dir()` |
/// | --- | --- | --- |
/// | a path | that path | that path |
/// | unset | the passwd entry, and search works | the passwd entry |
/// | **empty** | **`/`** | the passwd entry |
///
/// `.expect("HOME")` — what this replaced — **panicked where the product works**,
/// and its message named `main.rs`, which after the cutover is the production file.
///
/// The empty case is Python's `return (userhome + path[i:]) or '/'`: a present but
/// empty `HOME` yields `/`, so legacy searches a root that holds no sessions and
/// returns nothing. A resolver that "corrects" that to the real home returns
/// results where the product returns none.
fn home_directory() -> std::path::PathBuf {
    match std::env::var_os("HOME") {
        Some(value) if !value.is_empty() => std::path::PathBuf::from(value),
        // Present and empty. Python yields `/`, not the passwd entry.
        Some(_) => std::path::PathBuf::from("/"),
        // Absent. Python falls through to `pwd.getpwuid`, which is what
        // `home_dir()` does on Unix.
        None => std::env::home_dir().unwrap_or_else(|| std::path::PathBuf::from("/")),
    }
}
