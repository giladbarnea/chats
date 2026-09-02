use std::ffi::OsString;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::ExitCode;

use _native::codecs::{json_to_xml, xml_to_json};
use _native::model::python_repr_string;
use _native::python_io::{decode_utf8, python_io_error};
use _native::search::parse::{SearchOutcome, parse_search_arguments};
use _native::search::{render_error, render_help};
use _native::search_run::{print_stderr_wrapped, run};
use _native::search_views::StderrConsole;
use _native::terminal::{argparse_columns, terminal_width, wrap_preserving_spaces};

const USAGE: &str = "usage: ch parse [-h] [-f {xml,json}] [input_file]";
const HELP: &str = "usage: ch parse [-h] [-f {xml,json}] [input_file]\n\nConvert between structured ch JSON and XML-tagged Markdown\n\npositional arguments:\n  input_file            Input file (reads stdin when omitted)\n\noptions:\n  -h, --help            show this help message and exit\n  -f, --format {xml,json}\n                        Output format: xml or json (default: xml)\n";

#[derive(Clone, Copy, Eq, PartialEq)]
enum OutputFormat {
    Xml,
    Json,
}

struct ParseArguments {
    input_file: Option<PathBuf>,
    output_format: OutputFormat,
}

enum ArgumentResult {
    Help,
    Parse(ParseArguments),
    Error(String),
}

fn main() -> ExitCode {
    let arguments = std::env::args_os().skip(1).collect::<Vec<_>>();
    if arguments.first().is_some_and(|argument| argument == "parse") {
        return run_parse(&arguments[1..]);
    }
    // `cli.py` dispatches on `sys.argv[1] == "search"` and hands the parser
    // `sys.argv[2:]`, so the subcommand is matched exactly and never abbreviated.
    if arguments.first().is_some_and(|argument| argument == "search") {
        return run_search(&arguments[1..]);
    }
    run_legacy(&arguments)
}

/// The native `ch search` route.
///
/// **Two width resolvers, and they must stay two.** `argparse_columns()` follows
/// `shutil.get_terminal_size`, which is `int(COLUMNS)` inside a `try`; `terminal_width()`
/// follows Rich, which requires `str.isdigit()` first. They disagree on `+96`, on `' 96'`
/// and on `0` — in the same process, in the same run. Help and errors come out of
/// argparse and take the first; everything `run` prints comes out of Rich and takes the
/// second. **Unifying them is the most tempting deletion in this file and it changes
/// output either way**, which is what `terminal.rs`'s disagree-on-`+96` test and the
/// `COLUMNS` sweep in `tests/` are there to stop.
fn run_search(arguments: &[OsString]) -> ExitCode {
    let parsed = parse_search_arguments(arguments);
    // **Wrapped, because `print_warning` is a Rich `Console.print`.** Argparse emits
    // every warning before it decides anything about the arguments, and each one folds
    // at the terminal width. A raw `eprint!` agreed with the product at every width wide
    // enough not to fold — which is every width a developer types, and not the width the
    // contract corpus is recorded at.
    for warning in &parsed.warnings {
        print_stderr_wrapped(warning, StderrConsole::Warning);
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
        SearchOutcome::Run(arguments) => {
            let status = run(&arguments, &home_directory(), terminal_width());
            ExitCode::from(status as u8)
        }
    }
}

/// The session root, resolved exactly as Python's `Path.home()` does.
///
/// **Three branches, because `posixpath.expanduser` distinguishes three states and a
/// `home_dir`-shaped convenience call collapses two of them.** All measured against the
/// live `ch-legacy search` route rather than against an expectation of it:
///
/// | `HOME` | legacy | `std::env::home_dir()` | here |
/// | --- | --- | --- | --- |
/// | a path | that path | that path | that path |
/// | unset | the passwd entry, and search works | the passwd entry | the passwd entry |
/// | **empty** | **`/`** | the passwd entry | **`/`** |
///
/// The empty case is Python's `return (userhome + path[i:]) or '/'`: a present but empty
/// `HOME` yields `/`, so legacy searches a root that holds no sessions and returns
/// nothing. **A resolver that "corrects" that returns results where the product returns
/// none.** `.expect("HOME")` — what this replaced in the rehearsal driver — panicked
/// where the product works.
fn home_directory() -> PathBuf {
    match std::env::var_os("HOME") {
        Some(value) if !value.is_empty() => PathBuf::from(value),
        // Present and empty. Python yields `/`, not the passwd entry.
        Some(_) => PathBuf::from("/"),
        // Absent. Python falls through to `pwd.getpwuid`, which is what `home_dir()`
        // does on Unix.
        None => std::env::home_dir().unwrap_or_else(|| PathBuf::from("/")),
    }
}

fn run_parse(arguments: &[OsString]) -> ExitCode {
    match parse_arguments(arguments) {
        ArgumentResult::Help => {
            print!("{HELP}");
            ExitCode::SUCCESS
        }
        ArgumentResult::Error(error) => {
            eprintln!("{USAGE}\nch parse: error: {error}");
            ExitCode::from(2)
        }
        ArgumentResult::Parse(arguments) => convert(arguments),
    }
}

fn parse_arguments(arguments: &[OsString]) -> ArgumentResult {
    let mut output_format = OutputFormat::Xml;
    let mut input_file = None;
    let mut unknown = Vec::new();
    let mut options_enabled = true;
    let mut index = 0;
    while index < arguments.len() {
        let argument = arguments[index].to_string_lossy();
        if options_enabled && argument == "--" {
            options_enabled = false;
            index += 1;
            continue;
        }
        if options_enabled && matches!(argument.as_ref(), "-h" | "--help") {
            return ArgumentResult::Help;
        }
        if options_enabled && is_long_format_option(&argument) {
            let value = if let Some((_, value)) = argument.split_once('=') {
                value.to_string()
            } else {
                index += 1;
                match required_option_value(arguments.get(index)) {
                    Ok(value) => value,
                    Err(error) => return ArgumentResult::Error(error),
                }
            };
            match parse_output_format(&value) {
                Ok(value) => output_format = value,
                Err(error) => return ArgumentResult::Error(error),
            }
            index += 1;
            continue;
        }
        if options_enabled && argument.starts_with("-f") {
            let value = if argument == "-f" {
                index += 1;
                match required_option_value(arguments.get(index)) {
                    Ok(value) => value,
                    Err(error) => return ArgumentResult::Error(error),
                }
            } else {
                argument[2..]
                    .strip_prefix('=')
                    .unwrap_or(&argument[2..])
                    .to_string()
            };
            match parse_output_format(&value) {
                Ok(value) => output_format = value,
                Err(error) => return ArgumentResult::Error(error),
            }
            index += 1;
            continue;
        }
        if options_enabled && looks_like_option(&argument) {
            unknown.push(argument.into_owned());
            index += 1;
            continue;
        }
        if input_file.is_none() {
            input_file = Some(PathBuf::from(&arguments[index]));
        } else {
            unknown.push(argument.into_owned());
        }
        index += 1;
    }
    if !unknown.is_empty() {
        return ArgumentResult::Error(format!(
            "unrecognized arguments: {}",
            unknown.join(" ")
        ));
    }
    ArgumentResult::Parse(ParseArguments {
        input_file,
        output_format,
    })
}

fn required_option_value(value: Option<&OsString>) -> Result<String, String> {
    let value = value
        .ok_or_else(|| "argument -f/--format: expected one argument".to_string())?
        .to_string_lossy();
    if looks_like_option(&value) {
        return Err("argument -f/--format: expected one argument".to_string());
    }
    Ok(value.into_owned())
}

fn looks_like_option(argument: &str) -> bool {
    argument.starts_with('-') && argument != "-" && !looks_like_negative_number(argument)
}

fn looks_like_negative_number(argument: &str) -> bool {
    let Some(unsigned) = argument.strip_prefix('-') else {
        return false;
    };
    if !unsigned.is_empty() && unsigned.bytes().all(|byte| byte.is_ascii_digit()) {
        return true;
    }
    let Some((whole, fraction)) = unsigned.split_once('.') else {
        return false;
    };
    (whole.is_empty() || whole.bytes().all(|byte| byte.is_ascii_digit()))
        && !fraction.is_empty()
        && fraction.bytes().all(|byte| byte.is_ascii_digit())
}

fn is_long_format_option(argument: &str) -> bool {
    let option = argument.split_once('=').map_or(argument, |(option, _)| option);
    matches!(option, "--f" | "--fo" | "--for" | "--form" | "--forma" | "--format")
}

fn parse_output_format(value: &str) -> Result<OutputFormat, String> {
    match value {
        "xml" => Ok(OutputFormat::Xml),
        "json" => Ok(OutputFormat::Json),
        _ => Err(format!(
            "argument -f/--format: invalid choice: {} (choose from 'xml', 'json')",
            python_repr_string(value)
        )),
    }
}

fn convert(arguments: ParseArguments) -> ExitCode {
    let input_description = if arguments.output_format == OutputFormat::Xml {
        "structured JSON"
    } else {
        "XML-tagged Markdown"
    };
    let bytes = match read_input(arguments.input_file.as_ref()) {
        Ok(bytes) => bytes,
        Err(error) => {
            print_wrapped_error(&format!("Error parsing {input_description}: {error}"));
            return ExitCode::FAILURE;
        }
    };
    let content = match decode_utf8(&bytes) {
        Ok(content) => normalize_newlines(content),
        Err(error) => {
            print_wrapped_error(&format!("Error parsing {input_description}: {error}"));
            return ExitCode::FAILURE;
        }
    };
    let result = if arguments.output_format == OutputFormat::Xml {
        json_to_xml(&content)
    } else {
        xml_to_json(&content)
    };
    let output = match result {
        Ok(output) => output,
        Err(error) => {
            print_wrapped_error(&format!("Error parsing {input_description}: {error}"));
            return ExitCode::FAILURE;
        }
    };
    if output.is_empty() {
        return ExitCode::SUCCESS;
    }
    let mut stdout = std::io::stdout().lock();
    if let Err(error) = writeln!(stdout, "{output}") {
        let mut stderr = std::io::stderr().lock();
        return handle_output_write_error(&error, &mut stderr);
    }
    ExitCode::SUCCESS
}

fn handle_output_write_error(error: &std::io::Error, error_output: &mut impl Write) -> ExitCode {
    if error.kind() == std::io::ErrorKind::BrokenPipe {
        return ExitCode::SUCCESS;
    }
    let _ = writeln!(error_output, "{error}");
    ExitCode::FAILURE
}

fn read_input(path: Option<&PathBuf>) -> Result<Vec<u8>, String> {
    if let Some(path) = path {
        return std::fs::read(path).map_err(|error| python_io_error(&error, path));
    }
    let mut bytes = Vec::new();
    std::io::stdin()
        .lock()
        .read_to_end(&mut bytes)
        .map_err(|error| error.to_string())?;
    Ok(bytes)
}

fn normalize_newlines(content: String) -> String {
    content.replace("\r\n", "\n").replace('\r', "\n")
}

fn print_wrapped_error(message: &str) {
    let wrapped = wrap_preserving_spaces(message, terminal_width());
    if error_color_enabled() {
        for line in wrapped.lines() {
            eprintln!("\x1b[31m{line}\x1b[0m");
        }
        return;
    }
    eprintln!("{wrapped}");
}

#[cfg(unix)]
fn error_color_enabled() -> bool {
    let terminal_supports_color = std::env::var("TERM").as_deref() != Ok("dumb");
    let color_allowed = std::env::var_os("NO_COLOR").is_none();
    let is_terminal = unsafe { libc::isatty(libc::STDERR_FILENO) == 1 };
    terminal_supports_color && color_allowed && is_terminal
}

#[cfg(not(unix))]
fn error_color_enabled() -> bool {
    false
}

fn run_legacy(arguments: &[OsString]) -> ExitCode {
    use std::os::unix::process::CommandExt;

    let executable = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|parent| parent.join("ch-legacy")));
    let Some(executable) = executable else {
        eprintln!("Error: Cannot locate the private ch legacy entry.");
        return ExitCode::FAILURE;
    };
    let error = std::process::Command::new(executable).args(arguments).exec();
    eprintln!("Error: Cannot start the private ch legacy entry: {error}");
    ExitCode::FAILURE
}

#[cfg(not(unix))]
fn run_legacy(arguments: &[OsString]) -> ExitCode {
    let executable = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|parent| parent.join("ch-legacy")));
    let Some(executable) = executable else {
        eprintln!("Error: Cannot locate the private ch legacy entry.");
        return ExitCode::FAILURE;
    };
    match std::process::Command::new(executable).args(arguments).status() {
        Ok(status) => ExitCode::from(status.code().unwrap_or(1) as u8),
        Err(error) => {
            eprintln!("Error: Cannot start the private ch legacy entry: {error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn broken_pipe_exits_successfully_without_error_output() {
        let error = std::io::Error::new(std::io::ErrorKind::BrokenPipe, "closed pipe");
        let mut error_output = Vec::new();

        let exit_code = handle_output_write_error(&error, &mut error_output);

        assert_eq!(
            exit_code,
            ExitCode::SUCCESS,
            "Broken pipe handling must exit successfully"
        );
        assert_eq!(
            error_output,
            Vec::<u8>::new(),
            "Broken pipe handling must not write stderr"
        );
    }
}
