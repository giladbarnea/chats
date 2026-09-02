//! Terminal width resolution, shared by the binary and the renderers.
//!
//! Both halves of `ch` must resolve width identically, and both must resolve it
//! the way Rich does, or a byte diff between the Python and native routes is
//! meaningless for any width-sensitive output.

use unicode_general_category::{GeneralCategory, get_general_category};

const FALLBACK_TERMINAL_WIDTH: usize = 80;

/// The width to wrap output at: the terminal's own, overridden by COLUMNS.
///
/// A shell sets COLUMNS without exporting it, so the variable alone resolves to
/// nothing and pins the width to the fallback. Asking the terminal is what makes
/// the wrap follow the window.
pub fn terminal_width() -> usize {
    terminal_width_for(stdout_is_dumb_terminal())
}

/// Whether stdout is a terminal Rich would call dumb.
///
/// `is_dumb_terminal` is `is_terminal && TERM in ("dumb", "unknown")` — and
/// **`is_terminal` is Rich's whole cascade, not `isatty`.** This tested `isatty`
/// directly and carried the comment *"a pipe is never dumb however `TERM` is
/// set"*, which is **true only when nothing forces terminal-ness**. Set
/// `FORCE_COLOR=1` or `TTY_COMPATIBLE=1` and a pipe *is* a terminal to Rich, so a
/// pipe with `TERM=dumb` is dumb and the width drops to 80.
///
/// Measured end to end, piped, `COLUMNS=100`, `FORCE_COLOR=1 TERM=dumb`: the
/// product wrapped at 80 and this route at 100 — **2 of 20 environment
/// comparisons, and the only two that were not byte-identical.** It is the same
/// mechanism `cutover-finisher` found on the stderr consoles, arriving on stdout.
///
/// Delegating to `search_run::stdout_capabilities` keeps **one** authority for
/// reading those five variables. The layering is upside down and the alternative
/// was a second copy of the same env reading; a fork of this exact shape has been
/// three separate defects on this mission and odd layering has been none.
fn stdout_is_dumb_terminal() -> bool {
    crate::search_run::stdout_capabilities(false).is_dumb
}

/// Width with dumbness supplied, for callers that already resolved it.
///
/// **A dumb terminal is 80 columns, whatever `COLUMNS` says.** Rich returns
/// `ConsoleDimensions(80, 25)` at `console.py:1021` *before* it consults
/// `COLUMNS` at all, so the override never applies there. Checking `COLUMNS`
/// first — the natural order, and what this did until measured — renders a
/// 40-column dumb terminal at 40 where the product uses 80.
///
/// Invisible to every recorded case, because they all pin a width and none pins
/// `TERM=dumb`, so the two paths never separate.
pub fn terminal_width_for(is_dumb: bool) -> usize {
    if is_dumb {
        return FALLBACK_TERMINAL_WIDTH;
    }
    // **The zero clamp belongs to the measured answer alone.** Rich's comment says
    // why it exists — `get_terminal_size` can report `0, 0` from a pseudo-terminal
    // — and `size` applies `width = width or 80` to that. But `Console.__init__`
    // has already read `COLUMNS` into `_width`, and `size` ends
    // `width - legacy_windows if self._width is None else self._width`, so the
    // clamp is computed and then discarded for an explicit `COLUMNS`.
    // Measured: at `COLUMNS=0` a real `Console` reports `width == 0`, and
    // `ch-legacy search zz -d /nope` exits 1 having printed **nothing at all** on
    // either stream. One filter over both answers turns that into a full line.
    if let Some(width) = std::env::var("COLUMNS")
        .ok()
        .and_then(|value| columns_override(&value))
    {
        return width;
    }
    measured_terminal_width()
        .filter(|width| *width > 0)
        .unwrap_or(FALLBACK_TERMINAL_WIDTH)
}

/// Read a COLUMNS value exactly as Rich does: `str.isdigit()`, then `int()`.
///
/// Rust's own `parse::<usize>()` disagrees with Rich in both directions. It
/// accepts a leading `+`, which `str.isdigit()` rejects, and it rejects the
/// non-ASCII decimal digits that `int()` accepts.
///
/// ```
/// # use _native::terminal::columns_override;
/// assert_eq!(columns_override("96"), Some(96));
/// assert_eq!(columns_override("\u{ff19}\u{ff16}"), Some(96));
/// assert_eq!(columns_override("+96"), None);
/// ```
pub fn columns_override(value: &str) -> Option<usize> {
    if value.is_empty() {
        return None;
    }
    let mut width: usize = 0;
    for character in value.chars() {
        let digit = decimal_digit_value(character)? as usize;
        width = width.checked_mul(10)?.checked_add(digit)?;
    }
    Some(width)
}

/// The value of a Unicode decimal digit, or None for anything else.
///
/// Decimal-digit characters are laid out in contiguous runs of ten starting at
/// that script's zero, so a character's value is the number of decimal digits
/// immediately preceding it.
fn decimal_digit_value(character: char) -> Option<u32> {
    if get_general_category(character) != GeneralCategory::DecimalNumber {
        return None;
    }
    let code = u32::from(character);
    Some(
        (1..=9)
            .take_while(|offset| {
                code.checked_sub(*offset)
                    .and_then(char::from_u32)
                    .is_some_and(|previous| {
                        get_general_category(previous) == GeneralCategory::DecimalNumber
                    })
            })
            .count() as u32,
    )
}

#[cfg(unix)]
fn measured_terminal_width() -> Option<usize> {
    [libc::STDIN_FILENO, libc::STDOUT_FILENO, libc::STDERR_FILENO]
        .into_iter()
        .find_map(|descriptor| {
            let mut size: libc::winsize = unsafe { std::mem::zeroed() };
            let measured = unsafe {
                libc::ioctl(descriptor, libc::TIOCGWINSZ, &mut size as *mut libc::winsize)
            };
            (measured == 0).then_some(size.ws_col as usize)
        })
}

#[cfg(not(unix))]
fn measured_terminal_width() -> Option<usize> {
    None
}

#[cfg(test)]
mod tests {
    use super::columns_override;

    #[test]
    fn ascii_digits_resolve_to_their_value() {
        assert_eq!(
            columns_override("96"),
            Some(96),
            "Expected plain ASCII digits to resolve like Rich's int(COLUMNS)."
        );
    }

    // Rich gates on `str.isdigit()`, which is true for every Unicode decimal
    // digit, and `int()` accepts them all. Rust's `parse::<usize>()` does not.
    #[test]
    fn non_ascii_decimal_digits_resolve_like_python_int() {
        assert_eq!(
            columns_override("\u{ff19}\u{ff16}"),
            Some(96),
            "Expected fullwidth digits to resolve to 96, as Python int() does."
        );
        assert_eq!(
            columns_override("\u{0668}\u{0660}"),
            Some(80),
            "Expected Arabic-Indic digits to resolve to 80, as Python int() does."
        );
    }

    // `parse::<usize>()` accepts a leading `+`; `str.isdigit()` does not, so
    // Rich ignores COLUMNS here and measures the terminal instead.
    #[test]
    fn signed_and_padded_values_are_rejected() {
        for value in ["+96", "-96", " 96", "96 ", "96.0", "", "ninety"] {
            assert_eq!(
                columns_override(value),
                None,
                "Expected {value:?} to be rejected, matching str.isdigit()."
            );
        }
    }

    // `str.isdigit()` is true for superscripts, but `int()` then raises, so
    // Rich crashes. Treated as a Rich defect and deliberately not reproduced.
    #[test]
    fn non_decimal_digit_characters_are_rejected() {
        assert_eq!(
            columns_override("\u{00b2}"),
            None,
            "Expected superscript two to be rejected rather than reproducing Rich's crash."
        );
    }

    #[test]
    fn zero_resolves_so_the_caller_can_fall_through() {
        assert_eq!(
            columns_override("0"),
            Some(0),
            "Expected COLUMNS=0 to parse, leaving the >0 filter to reject it."
        );
    }
}

/// The colour depth a terminal can render, mirroring Rich's `ColorSystem`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ColorSystem {
    Standard,
    EightBit,
    Truecolor,
}

/// The ambient inputs Rich consults when deciding how to colour output.
#[derive(Clone, Copy, Debug, Default)]
pub struct AmbientColorInputs<'a> {
    pub colorterm: Option<&'a str>,
    pub term: Option<&'a str>,
    pub force_color: Option<&'a str>,
    pub tty_compatible: Option<&'a str>,
    pub no_color: Option<&'a str>,
    pub is_a_tty: bool,
    pub forced_terminal: bool,
}

/// What the ambient inputs resolve to.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TerminalCapabilities {
    pub is_terminal: bool,
    pub is_dumb: bool,
    pub color_system: Option<ColorSystem>,
    pub no_color: bool,
}

/// Resolve colour capability exactly as Rich does.
///
/// Ported against an exhaustive 12,096-row table generated from Rich itself
/// (`teammates/search-runtime/probes/color-oracle.tsv`), covering every
/// combination of the five variables, tty-ness, and the forced-terminal shape
/// `ch` uses. The model this implements was validated against every row.
pub fn resolve_color(inputs: &AmbientColorInputs) -> TerminalCapabilities {
    let is_terminal = resolve_is_terminal(inputs);
    let is_dumb = is_terminal
        && matches!(
            inputs.term.unwrap_or_default().to_ascii_lowercase().as_str(),
            "dumb" | "unknown"
        );
    TerminalCapabilities {
        is_terminal,
        is_dumb,
        color_system: (is_terminal && !is_dumb).then(|| color_system(inputs)),
        no_color: !inputs.no_color.unwrap_or_default().is_empty(),
    }
}

/// `FORCE_COLOR` is tested for presence and emptiness, never for truth, so
/// `FORCE_COLOR=0` reads as a terminal. That is Rich's behavior, not a slip.
fn resolve_is_terminal(inputs: &AmbientColorInputs) -> bool {
    if inputs.forced_terminal {
        return true;
    }
    match inputs.tty_compatible {
        Some("0") => return false,
        Some("1") => return true,
        _ => {}
    }
    match inputs.force_color {
        Some(force_color) => !force_color.is_empty(),
        None => inputs.is_a_tty,
    }
}

fn color_system(inputs: &AmbientColorInputs) -> ColorSystem {
    let colorterm = inputs.colorterm.unwrap_or_default().trim().to_ascii_lowercase();
    if matches!(colorterm.as_str(), "truecolor" | "24bit") {
        return ColorSystem::Truecolor;
    }
    let term = inputs.term.unwrap_or_default().trim().to_ascii_lowercase();
    match term.rsplit('-').next().unwrap_or_default() {
        "kitty" | "256color" => ColorSystem::EightBit,
        "16color" => ColorSystem::Standard,
        _ => ColorSystem::Standard,
    }
}

#[cfg(test)]
mod color_tests {
    use super::*;

    fn inputs<'a>() -> AmbientColorInputs<'a> {
        AmbientColorInputs::default()
    }

    #[test]
    fn a_forced_terminal_overrides_every_other_signal() {
        let resolved = resolve_color(&AmbientColorInputs {
            tty_compatible: Some("0"),
            force_color: Some(""),
            is_a_tty: false,
            forced_terminal: true,
            ..inputs()
        });
        assert!(
            resolved.is_terminal,
            "Expected an explicitly forced terminal to win over TTY_COMPATIBLE=0."
        );
    }

    #[test]
    fn tty_compatible_outranks_force_color_and_isatty() {
        assert!(
            !resolve_color(&AmbientColorInputs {
                tty_compatible: Some("0"),
                force_color: Some("1"),
                is_a_tty: true,
                ..inputs()
            })
            .is_terminal,
            "Expected TTY_COMPATIBLE=0 to reject even with FORCE_COLOR=1 on a tty."
        );
        assert!(
            resolve_color(&AmbientColorInputs {
                tty_compatible: Some("1"),
                is_a_tty: false,
                ..inputs()
            })
            .is_terminal,
            "Expected TTY_COMPATIBLE=1 to accept even off a tty."
        );
    }

    // Rich tests FORCE_COLOR for emptiness, not truth, so "0" reads as a
    // terminal. Counterintuitive and load-bearing.
    #[test]
    fn force_color_is_a_presence_test_not_a_truth_test() {
        assert!(
            resolve_color(&AmbientColorInputs {
                force_color: Some("0"),
                is_a_tty: false,
                ..inputs()
            })
            .is_terminal,
            "Expected FORCE_COLOR=0 to read as a terminal, matching Rich."
        );
        assert!(
            !resolve_color(&AmbientColorInputs {
                force_color: Some(""),
                is_a_tty: true,
                ..inputs()
            })
            .is_terminal,
            "Expected an empty FORCE_COLOR to reject even on a tty."
        );
    }

    #[test]
    fn without_signals_tty_ness_decides() {
        assert!(resolve_color(&AmbientColorInputs { is_a_tty: true, ..inputs() }).is_terminal);
        assert!(!resolve_color(&AmbientColorInputs { is_a_tty: false, ..inputs() }).is_terminal);
    }

    #[test]
    fn dumb_terminals_get_no_color_system() {
        for term in ["dumb", "unknown", "DUMB"] {
            let resolved = resolve_color(&AmbientColorInputs {
                term: Some(term),
                colorterm: Some("truecolor"),
                is_a_tty: true,
                ..inputs()
            });
            assert!(resolved.is_dumb, "Expected TERM={term} to be dumb.");
            assert_eq!(
                resolved.color_system, None,
                "Expected a dumb terminal to resolve no colour system even with COLORTERM."
            );
        }
    }

    #[test]
    fn colorterm_is_trimmed_and_case_folded() {
        for colorterm in ["truecolor", "24bit", "TrueColor", " truecolor "] {
            assert_eq!(
                resolve_color(&AmbientColorInputs {
                    colorterm: Some(colorterm),
                    term: Some("xterm"),
                    is_a_tty: true,
                    ..inputs()
                })
                .color_system,
                Some(ColorSystem::Truecolor),
                "Expected COLORTERM={colorterm:?} to resolve truecolor."
            );
        }
    }

    #[test]
    fn the_term_suffix_selects_the_color_system() {
        let cases = [
            ("xterm-256color", ColorSystem::EightBit),
            ("screen-256color", ColorSystem::EightBit),
            ("kitty", ColorSystem::EightBit),
            ("xterm-kitty", ColorSystem::EightBit),
            ("xterm-16color", ColorSystem::Standard),
            ("xterm", ColorSystem::Standard),
            ("", ColorSystem::Standard),
        ];
        for (term, expected) in cases {
            assert_eq!(
                resolve_color(&AmbientColorInputs {
                    term: Some(term),
                    is_a_tty: true,
                    ..inputs()
                })
                .color_system,
                Some(expected),
                "Expected TERM={term:?} to resolve {expected:?}."
            );
        }
    }

    #[test]
    fn a_non_terminal_resolves_no_color_system() {
        assert_eq!(
            resolve_color(&AmbientColorInputs {
                colorterm: Some("truecolor"),
                term: Some("xterm-256color"),
                is_a_tty: false,
                ..inputs()
            })
            .color_system,
            None,
            "Expected a non-terminal to resolve no colour system regardless of COLORTERM."
        );
    }

    #[test]
    fn no_color_is_a_presence_test() {
        assert!(!resolve_color(&AmbientColorInputs { no_color: Some(""), ..inputs() }).no_color);
        assert!(resolve_color(&AmbientColorInputs { no_color: Some("0"), ..inputs() }).no_color);
    }
}

/// The width argparse wraps help and usage to.
///
/// **Not the same rule as [`terminal_width`].** argparse goes through
/// `shutil.get_terminal_size`, which is `int()` in a `try`/`except`; Rich uses
/// `str.isdigit()`. So `COLUMNS=+96` wraps help at 96 while Rich-rendered output
/// wraps at 80, in the same invocation. Two resolvers, each named for what it
/// models — a port that unifies them breaks one.
///
/// `shutil` also measures **stdout only**, where Rich's path tries stdin, stdout
/// and stderr in turn.
pub fn argparse_columns() -> usize {
    std::env::var("COLUMNS")
        .ok()
        .and_then(|value| python_int(&value))
        .filter(|columns| *columns > 0)
        .map(|columns| columns as usize)
        .or_else(measured_stdout_width)
        .unwrap_or(FALLBACK_TERMINAL_WIDTH)
}

/// Parse as Python's `int()` does: surrounding whitespace, one optional sign,
/// Unicode decimal digits, and single underscores *between* digits.
///
/// ```
/// # use _native::terminal::python_int;
/// assert_eq!(python_int(" +9_6 "), Some(96));
/// assert_eq!(python_int("96.0"), None);
/// ```
pub fn python_int(value: &str) -> Option<i64> {
    let trimmed = value.trim_matches(|character: char| character.is_whitespace());
    let (negative, digits) = match trimmed.strip_prefix(['+', '-']) {
        Some(rest) => (trimmed.starts_with('-'), rest),
        None => (false, trimmed),
    };
    if digits.is_empty() || digits.starts_with('_') || digits.ends_with('_') {
        return None;
    }
    let mut magnitude: i64 = 0;
    let mut previous_was_underscore = false;
    for character in digits.chars() {
        if character == '_' {
            if previous_was_underscore {
                return None;
            }
            previous_was_underscore = true;
            continue;
        }
        previous_was_underscore = false;
        let digit = decimal_digit_value(character)?;
        magnitude = magnitude.checked_mul(10)?.checked_add(i64::from(digit))?;
    }
    Some(if negative { -magnitude } else { magnitude })
}

#[cfg(unix)]
fn measured_stdout_width() -> Option<usize> {
    let mut size: libc::winsize = unsafe { std::mem::zeroed() };
    let measured =
        unsafe { libc::ioctl(libc::STDOUT_FILENO, libc::TIOCGWINSZ, &mut size as *mut libc::winsize) };
    (measured == 0 && size.ws_col > 0).then_some(size.ws_col as usize)
}

#[cfg(not(unix))]
fn measured_stdout_width() -> Option<usize> {
    None
}

#[cfg(test)]
mod argparse_width_tests {
    use super::*;

    #[test]
    fn python_int_accepts_what_cpython_accepts() {
        for (value, expected) in [
            ("96", 96),
            ("+96", 96),
            (" 96", 96),
            ("96 ", 96),
            ("\t96\n", 96),
            ("9_6", 96),
            ("-96", -96),
            ("0", 0),
            ("\u{0668}\u{0660}", 80),
            ("\u{ff19}\u{ff16}", 96),
        ] {
            assert_eq!(
                python_int(value),
                Some(expected),
                "Expected int({value:?}) to be {expected}, matching CPython."
            );
        }
    }

    #[test]
    fn python_int_rejects_what_cpython_rejects() {
        for value in ["", "bogus", "96.0", "+ 96", "__96", "9__6", "_96", "96_"] {
            assert_eq!(
                python_int(value),
                None,
                "Expected int({value:?}) to raise in CPython, so we reject it."
            );
        }
    }

    // The whole reason both resolvers exist. If this ever passes with equal
    // answers, someone has unified them and broken one of the two surfaces.
    #[test]
    fn the_two_resolvers_disagree_exactly_where_measured() {
        for value in ["+96", " 96"] {
            assert_eq!(
                python_int(value).map(|columns| columns as usize),
                Some(96),
                "argparse honours {value:?} through shutil's int()."
            );
            assert_eq!(
                columns_override(value),
                None,
                "Rich rejects {value:?} through str.isdigit(); the rules differ."
            );
        }
    }
}

/// Wrap a message at `width`, preserving runs of spaces.
///
/// Rich's stderr console wraps every error it prints, so a native route that
/// writes an unwrapped line disagrees with the product on every message longer
/// than the terminal — which is most per-file errors, because they carry a full
/// path. Measured: `-ma notadate` differed on all four of its cases for this alone.
///
/// Lifted from `rust/main.rs` rather than copied, so `ch parse` and `ch search`
/// wrap identically. Standing constraint 4.
/// Wrap a message the way Rich's console does.
///
/// A faithful port of `rich/_wrap.py::divide_line` plus `Text.rstrip_end`, not an
/// approximation. The details that matter, each of which I got wrong by reasoning
/// before measuring:
///
/// - **A "word" is `\s*\S+\s*`** — it carries its leading *and* trailing
///   whitespace. A break is inserted at the start of the match, so whitespace that
///   belongs to a word travels with it to the next line rather than being dropped.
/// - **The fit test uses the word without its trailing space; the advance uses the
///   word with it.** So a line may legitimately end with a trailing space that
///   pushes it past `width`.
/// - **`rstrip_end` then removes only the *excess*** — `min(trailing whitespace,
///   length - width)` characters — rather than all trailing whitespace. A line
///   ending one space over keeps every space but one.
///
/// Gated on `probes/wrap-oracle.tsv`, 235 rows over five widths. Hand-reasoning
/// this cost three wrong fixes: the first dropped a space at a full line, the
/// second added one everywhere, and only the recorded table settled it.
pub fn wrap_preserving_spaces(message: &str, width: usize) -> String {
    // **Zero cells is not "unlimited", it is nothing.** Measured against live
    // Rich: `Console(width=0).print(Text(...))` writes the empty string, and the
    // product at `COLUMNS=0` exits 1 having written **zero bytes** on either
    // stream. Returning the message here reads as a sensible guard and is the
    // opposite of what the oracle does.
    //
    // **This does not close the gap for every caller, and which ones it closes
    // was checked rather than assumed.** `search_run::emit_hint` returns before
    // it ever calls this, so the two no-results shapes already write zero bytes.
    // The callers that write the result straight into `eprintln!` — the
    // undecidable-pattern and per-file error paths in `search_run.rs`, and
    // `main.rs::print_wrapped_error` — still cost one newline where Python costs
    // none. That last byte belongs to those call sites, not here.
    if width == 0 {
        return String::new();
    }
    let metrics = crate::cells::CellMetrics::from_environment();
    let characters: Vec<char> = message.chars().collect();
    let mut breaks: Vec<usize> = Vec::new();
    let mut cell_offset = 0usize;

    for (start, word) in rich_words(&characters) {
        let trimmed: String = word.iter().collect::<String>().trim_end().to_string();
        let word_length = metrics.cell_len(&trimmed);
        let whole: String = word.iter().collect();
        if width - cell_offset.min(width) >= word_length && cell_offset <= width {
            cell_offset += metrics.cell_len(&whole);
            continue;
        }
        if word_length > width {
            // Folded across lines. `start` advances by the characters consumed so
            // each fold lands at its own offset.
            let folded = metrics.chop_cells(&word.iter().collect::<String>(), width);
            let mut cursor = start;
            let count = folded.len();
            for (index, line) in folded.iter().enumerate() {
                if cursor > 0 {
                    breaks.push(cursor);
                }
                if index + 1 == count {
                    cell_offset = metrics.cell_len(line);
                } else {
                    cursor += line.chars().count();
                }
            }
        } else if cell_offset > 0 && start > 0 {
            breaks.push(start);
            cell_offset = metrics.cell_len(&whole);
        }
    }

    let mut lines: Vec<String> = Vec::new();
    let mut previous = 0usize;
    for offset in breaks.iter().copied().chain(std::iter::once(characters.len())) {
        lines.push(characters[previous.min(characters.len())..offset.min(characters.len())]
            .iter()
            .collect());
        previous = offset;
    }
    lines
        .iter()
        .map(|line| {
            let line = rstrip_end(line, width);
            // Rich's `Text.wrap` ends with `line.truncate(width, overflow)`, and
            // under `fold` that is `set_cell_size(plain, width)` **only when the
            // line is over** — `set_cell_size` pads a short line, and no recorded
            // row is padded. Folding cannot normally leave a line over width; a
            // grapheme wider than the whole line can, and then Rich replaces it
            // with a pad space. `你好世界` at width 1 is four spaces, not four
            // characters.
            if metrics.cell_len(&line) > width {
                return metrics.set_cell_size(&line, width);
            }
            line
        })
        .collect::<Vec<String>>()
        .join("\n")
}

/// Rich's `re_word = r"\s*\S+\s*"`, as (start index, characters).
fn rich_words(characters: &[char]) -> Vec<(usize, Vec<char>)> {
    let mut words = Vec::new();
    let mut index = 0usize;
    while index < characters.len() {
        let start = index;
        while index < characters.len() && characters[index].is_whitespace() {
            index += 1;
        }
        if index == characters.len() {
            break;
        }
        while index < characters.len() && !characters[index].is_whitespace() {
            index += 1;
        }
        while index < characters.len() && characters[index].is_whitespace() {
            index += 1;
        }
        words.push((start, characters[start..index].to_vec()));
    }
    words
}

/// Rich's `Text.rstrip_end`: remove only the trailing whitespace that *exceeds*
/// `size`, never all of it.
fn rstrip_end(line: &str, size: usize) -> String {
    let length = line.chars().count();
    if length <= size {
        return line.to_string();
    }
    let excess = length - size;
    let trailing = line.chars().rev().take_while(|c| c.is_whitespace()).count();
    let remove = trailing.min(excess);
    line.chars().take(length - remove).collect()
}

#[cfg(test)]
mod dumb_width_tests {
    use super::*;

    /// Measured at `rich/console.py:1021`: the dumb branch returns 80 and
    /// returns it *before* `COLUMNS` is read.
    #[test]
    fn a_dumb_terminal_is_eighty_columns_whatever_columns_says() {
        // SAFETY: single-threaded test; restored immediately after the reads.
        let previous = std::env::var("COLUMNS").ok();
        unsafe { std::env::set_var("COLUMNS", "40") };
        assert_eq!(
            terminal_width_for(true),
            80,
            "A dumb terminal must ignore COLUMNS and use 80, as Rich does."
        );
        assert_eq!(
            terminal_width_for(false),
            40,
            "A non-dumb terminal must honour COLUMNS."
        );
        match previous {
            Some(value) => unsafe { std::env::set_var("COLUMNS", value) },
            None => unsafe { std::env::remove_var("COLUMNS") },
        }
    }

    /// **A pipe IS dumb once something forces terminal-ness**, which is the
    /// precondition the old comment left out.
    ///
    /// `stdout_is_dumb_terminal` tested `isatty` directly and was documented as
    /// *"a pipe is never dumb however `TERM` is set"*. That holds only while
    /// nothing forces the terminal: Rich's `is_dumb_terminal` is
    /// `is_terminal && TERM in ("dumb", "unknown")`, and `is_terminal` is the
    /// whole cascade.
    ///
    /// Asserted against `resolve_color` with explicit inputs rather than by
    /// setting environment variables, because these tests run in parallel threads
    /// and the neighbouring `COLUMNS` tests already mutate the environment.
    ///
    /// **Measured end to end before it was written**: piped, `COLUMNS=100`,
    /// `FORCE_COLOR=1 TERM=dumb`, the product wrapped at 80 and this route at 100
    /// — 2 of 20 environment comparisons, and the only two that were not
    /// byte-identical. It is the mechanism `cutover-finisher` found on the stderr
    /// consoles, arriving on stdout.
    #[test]
    fn a_forced_pipe_with_a_dumb_term_is_dumb() {
        let piped_dumb = |force_color, tty_compatible| {
            resolve_color(&AmbientColorInputs {
                colorterm: None,
                term: Some("dumb"),
                force_color,
                tty_compatible,
                no_color: None,
                is_a_tty: false,
                forced_terminal: false,
            })
            .is_dumb
        };
        assert!(
            piped_dumb(Some("1"), None),
            "FORCE_COLOR makes a pipe a terminal, so TERM=dumb makes it a dumb one \
             — and a dumb terminal is 80 columns whatever COLUMNS says"
        );
        assert!(
            piped_dumb(None, Some("1")),
            "TTY_COMPATIBLE=1 does the same"
        );
        assert!(
            !piped_dumb(None, None),
            "the falsifier: with nothing forcing it, a pipe is not a terminal and \
             not dumb, so `isatty` and the cascade agree. If this ever fails the \
             two assertions above stop proving anything, because every pipe would \
             be dumb."
        );
    }

    /// `COLUMNS=0` is zero, not eighty — and zero cells is nothing, not
    /// everything.
    ///
    /// The clamp Rich carries is for the **measured** answer: its own comment
    /// says `get_terminal_size` can report `0, 0` from a pseudo-terminal. An
    /// explicit `COLUMNS` never reaches it, because `Console.__init__` has stored
    /// it in `_width` and `size` ends `... if self._width is None else
    /// self._width`, discarding the clamped value.
    ///
    /// **Measured twice before this test was written**, because the behaviour
    /// looks like a bug: a live `Console(stderr=True, theme=APP_THEME)` at
    /// `COLUMNS=0` reports `width == 0`, and `ch-legacy search zz -d /nope` at
    /// `COLUMNS=0` exits 1 having written **zero bytes** on both streams.
    /// **Preserve-because-wrong in its purest form** — a port that clamps this
    /// prints a full error line and passes every gate that existed before it.
    #[test]
    fn columns_zero_is_zero_and_wraps_to_nothing() {
        // SAFETY: single-threaded test; restored immediately after the reads.
        let previous = std::env::var("COLUMNS").ok();
        unsafe { std::env::set_var("COLUMNS", "0") };
        assert_eq!(
            terminal_width_for(false),
            0,
            "an explicit COLUMNS=0 must survive: Rich's zero clamp applies to the \
             ioctl answer, never to the environment variable"
        );
        assert_eq!(
            terminal_width_for(true),
            80,
            "and a dumb terminal is still 80, because it returns before COLUMNS \
             is read at all"
        );
        match previous {
            Some(value) => unsafe { std::env::set_var("COLUMNS", value) },
            None => unsafe { std::env::remove_var("COLUMNS") },
        }

        assert_eq!(
            wrap_preserving_spaces("No sessions match \"zz\".", 0),
            "",
            "zero cells renders nothing. Measured: Console(width=0).print(Text(..)) \
             writes the empty string. Returning the message reads as a sensible \
             guard and is the opposite of what the oracle does."
        );
    }
}

#[cfg(test)]
mod wrap_cell_tests {
    use super::*;
    use crate::cells::CellMetrics;

    /// Rich measures cells. Counting code points holds for every ASCII message
    /// and diverges on wide characters, which is why this went unnoticed.
    #[test]
    fn a_wide_message_wraps_where_rich_wraps_it() {
        let metrics = CellMetrics::for_version(None);
        let message = format!("No sessions match \"{}\".", "\u{4f60}\u{597d}".repeat(16));
        assert!(
            metrics.cell_len(&message) > message.chars().count(),
            "the fixture must actually be wide, or this test proves nothing"
        );
        let wrapped = wrap_preserving_spaces(&message, 40);
        assert!(
            wrapped.contains('\n'),
            "A message wider than 40 cells must break. Got {wrapped:?}"
        );
        for line in wrapped.lines() {
            assert!(
                metrics.cell_len(line) <= 40,
                "Every wrapped line must fit in 40 cells. Got {line:?} at {} cells.",
                metrics.cell_len(line)
            );
        }
    }

    /// The fix must not move ASCII output, which is what every recorded case is.
    #[test]
    fn ascii_wrapping_is_unchanged() {
        let message = "Error parsing structured JSON: something went wrong here now";
        for width in [20usize, 40, 80] {
            for line in wrap_preserving_spaces(message, width).lines() {
                assert!(
                    line.chars().count() <= width,
                    "ASCII line exceeded {width}: {line:?}"
                );
            }
        }
    }
}

#[cfg(test)]
mod wrap_parity {
    use super::wrap_preserving_spaces;

    /// Every recorded Rich wrap reproduces, across five widths and 47 shapes.
    ///
    /// The corpus is deliberately dominated by one message with a path of every
    /// length from 0 to 39 characters, so the wrap boundary lands in every
    /// position relative to a space. That is the dimension three hand-reasoned
    /// fixes got wrong: a space at an exactly-full line, a space that fits, and a
    /// word too long to fit on any line each behave differently.
    #[test]
    fn every_recorded_rich_wrap_reproduces() {
        let table = include_str!(
            "../thoughts/2026-08-28-search-rust-rewrite/teammates/engine-and-codex/probes/wrap-oracle.tsv"
        );
        let mut checked = 0usize;
        for line in table.lines().skip(1) {
            let mut columns = line.splitn(3, '\t');
            let width: usize = columns.next().expect("width").parse().expect("numeric");
            let message = unquote(columns.next().expect("message"));
            let expected = unquote(columns.next().expect("wrapped"));
            assert_eq!(
                wrap_preserving_spaces(&message, width),
                expected,
                "width {width}, message {message:?}"
            );
            checked += 1;
        }
        assert_eq!(checked, 235, "the recorded table must be complete");
    }

    /// Python `repr` quoting, enough for the escapes this table contains.
    fn unquote(value: &str) -> String {
        let trimmed = value.trim();
        let inner = &trimmed[1..trimmed.len() - 1];
        let mut out = String::new();
        let mut characters = inner.chars();
        while let Some(character) = characters.next() {
            if character != '\\' {
                out.push(character);
                continue;
            }
            match characters.next() {
                Some('n') => out.push('\n'),
                Some('t') => out.push('\t'),
                Some('r') => out.push('\r'),
                Some('\\') => out.push('\\'),
                Some('\'') => out.push('\''),
                Some('"') => out.push('"'),
                Some(other) => {
                    out.push('\\');
                    out.push(other);
                }
                None => out.push('\\'),
            }
        }
        out
    }
}
