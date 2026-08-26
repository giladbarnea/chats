use std::ffi::OsString;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::ExitCode;

use _native::codecs::{json_to_xml, xml_to_json};
use _native::model::python_repr_string;

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
    run_legacy(&arguments)
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

fn python_io_error(error: &std::io::Error, path: &PathBuf) -> String {
    let path = path.to_string_lossy();
    match error.raw_os_error() {
        Some(errno) => {
            let rendered = error.to_string();
            let suffix = format!(" (os error {errno})");
            let message = rendered.strip_suffix(&suffix).unwrap_or(&rendered);
            format!(
                "[Errno {errno}] {message}: {}",
                python_repr_string(&path)
            )
        }
        None => format!("{}: {}", error, python_repr_string(&path)),
    }
}

fn decode_utf8(bytes: &[u8]) -> Result<String, String> {
    match std::str::from_utf8(bytes) {
        Ok(content) => Ok(content.to_string()),
        Err(error) => {
            let start = error.valid_up_to();
            let byte = bytes.get(start).copied().unwrap_or_default();
            if error.error_len().is_none() {
                let end = bytes.len().saturating_sub(1);
                let subject = if end > start {
                    format!("bytes in position {start}-{end}")
                } else {
                    format!("byte 0x{byte:02x} in position {start}")
                };
                return Err(format!(
                    "'utf-8' codec can't decode {subject}: unexpected end of data"
                ));
            }
            let invalid_length = error.error_len().expect("handled truncated UTF-8");
            let end = start + invalid_length - 1;
            let subject = if end > start {
                format!("bytes in position {start}-{end}")
            } else {
                format!("byte 0x{byte:02x} in position {start}")
            };
            let reason = if matches!(byte, 0xc2..=0xf4) {
                "invalid continuation byte"
            } else {
                "invalid start byte"
            };
            Err(format!(
                "'utf-8' codec can't decode {subject}: {reason}"
            ))
        }
    }
}

fn normalize_newlines(content: String) -> String {
    content.replace("\r\n", "\n").replace('\r', "\n")
}

fn print_wrapped_error(message: &str) {
    let width = std::env::var("COLUMNS")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(80);
    let wrapped = wrap_preserving_spaces(message, width);
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

fn wrap_preserving_spaces(message: &str, width: usize) -> String {
    let mut output = String::new();
    let mut line_width = 0;
    let mut word = String::new();
    let flush_word = |word: &mut String, output: &mut String, line_width: &mut usize| {
        if word.is_empty() {
            return;
        }
        let word_width = word.chars().count();
        if *line_width > 0 && *line_width + word_width > width {
            output.push('\n');
            *line_width = 0;
        }
        for character in word.chars() {
            if *line_width == width {
                output.push('\n');
                *line_width = 0;
            }
            output.push(character);
            *line_width += 1;
        }
        word.clear();
    };
    for character in message.chars() {
        if character != ' ' {
            word.push(character);
            continue;
        }
        flush_word(&mut word, &mut output, &mut line_width);
        if line_width == width {
            output.push('\n');
            line_width = 0;
            continue;
        }
        output.push(' ');
        line_width += 1;
    }
    flush_word(&mut word, &mut output, &mut line_width);
    output
}

#[cfg(unix)]
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
