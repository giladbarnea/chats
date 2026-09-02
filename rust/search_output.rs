//! The four uncoloured search output modes, and the sink that writes them.
//!
//! Ported from `_display_hit`, `display_search_result` and `build_metadata_text`
//! in `src/chats/commands/search.py` and `src/chats/formatting.py`.
//!
//! The coloured list row and conversation panel are `views-and-colour`'s. This is
//! everything reached when `flags.color` is false, plus `--only-id`, which has no
//! coloured form at all.
//!
//! **`--raw` is the one mode that buffers.** Every other mode writes each hit as
//! it is confirmed, which is what makes newest-first streaming visible. `--raw`
//! cannot: a single session with exactly one visible message prints the bare body
//! with no header, and "exactly one" is only knowable once the scan has finished.

use crate::cells::CellMetrics;
use crate::color::{ColorRendering, ColorTriplet, StyleColor};
use crate::model::Message;
use crate::search_confirm::{ConfirmError, SearchHit};
use crate::search_query::{Query, SearchTerm};
use crate::search_views::{Segment, Style};
use crate::search_engine::{Confirmed, HitSink};
use crate::session;
use crate::visibility::{ConversationFlags, SearchOutputMode};
use std::io::Write;

/// Bridge between the two `SearchOutputMode` enums this crate carries.
///
/// `search::parse::SearchOutputMode` and `visibility::SearchOutputMode` name the
/// same four modes in different declaration orders. **Both are `search-runtime`'s,
/// and their own two functions disagree about which one they take**:
/// `SearchArguments` carries the `parse` type while `render_no_results_hint` takes
/// the `visibility` one, so anything wiring the two together has to convert.
///
/// This is the second duplicated-enum pair in the tree, after the two `Provider`
/// enums. The ruling there was **do not unify, bridge explicitly**, because the
/// inventory ordering is pinned to the oracle across 5,036 sessions. The same
/// applies here until someone measures whether either ordering is load-bearing,
/// and that measurement has not been done.
pub fn output_mode_of(mode: crate::search::parse::SearchOutputMode) -> SearchOutputMode {
    match mode {
        crate::search::parse::SearchOutputMode::Matches => SearchOutputMode::Matches,
        crate::search::parse::SearchOutputMode::List => SearchOutputMode::List,
        crate::search::parse::SearchOutputMode::Full => SearchOutputMode::Full,
        crate::search::parse::SearchOutputMode::OnlyId => SearchOutputMode::OnlyId,
    }
}

/// Print one error the way Rich's stderr console does: wrapped at the terminal
/// width, one trailing newline — and **nothing at all at zero width.**
///
/// One authority for it. Rich wraps every error it prints, and a per-file error
/// always carries a full path, so a message longer than the terminal is the normal
/// case rather than the exotic one — an unwrapped line disagrees with the product
/// on almost every error it emits.
///
/// **Delegates rather than repeating**, and the three things it inherits are each
/// a divergence this route had on its own:
///
/// - **Colour.** Rich's stderr console highlights these messages, and a bare
///   `eprintln!` emits none — 32 of the 72 failures in the stderr-colour gate.
/// - **Dumbness from stderr, not stdout.** A Rich console returns 80 columns for a
///   dumb terminal *before* consulting `COLUMNS`, and these consoles are built on
///   stderr, so `terminal_width()`'s stdout-derived answer is the wrong one.
/// - **Zero width writes zero bytes.** `COLUMNS=0` survives into the width, Rich
///   renders zero cells as the empty string, and `eprintln!` would still cost one
///   newline per candidate file — 21 on the sweep's fixture pool, 4,947 on the
///   real one.
///
/// `StderrConsole::Error` is built with **no theme**, so its `"red"` stays palette
/// index 31 at every colour tier instead of becoming an RGB triple.
pub fn print_error(message: &str) {
    crate::search_run::print_stderr_wrapped(message, crate::search_views::StderrConsole::Error);
}

/// Turn one confirmation outcome into the scan loop's verdict.
///
/// The two error arms are **not** interchangeable. A per-file failure prints and
/// scanning continues, matching Python's `except Exception` around each file. An
/// undecidable pattern ends the run, because continuing would report "no match"
/// for every later session on a question the engine could not answer — the exact
/// confident wrong answer the step budget exists to prevent.
pub fn confirmed_from(
    path: &std::path::Path,
    outcome: Result<Option<SearchHit>, ConfirmError>,
    undecidable: &mut Option<String>,
) -> Confirmed {
    match outcome {
        Ok(Some(hit)) => Confirmed::Hit(hit),
        Ok(None) => Confirmed::Miss,
        Err(ConfirmError::File(body)) => Confirmed::Failed(format!(
            "Error processing conversation file {}: {body}",
            path.display()
        )),
        Err(ConfirmError::Undecidable(message)) => {
            undecidable.get_or_insert(message);
            Confirmed::Miss
        }
    }
}

/// A horizontal rule with a centred title, as Rich draws it.
///
/// Derived from a recorded table rather than from Rich's source, because the
/// arithmetic is easy to get subtly wrong: `probes/rule-oracle.tsv` holds 99 rows
/// across eleven widths and nine titles, including wide and combining text.
///
/// The title is truncated to `width - 4` cells with an ellipsis, padded with one
/// space each side, and the remaining cells are filled with `─`, the odd cell
/// going to the **right**.
///
/// ```
/// use _native::cells::CellMetrics;
/// use _native::search_output::rule;
/// let metrics = CellMetrics::for_version(None);
/// assert_eq!(rule("f1", 20, &metrics), "──────── f1 ────────");
/// assert_eq!(rule("a", 20, &metrics), "──────── a ─────────");
/// assert_eq!(rule("", 20, &metrics), "────────────────────");
/// ```
pub fn rule(title: &str, width: usize, metrics: &CellMetrics) -> String {
    let parts = rule_parts(title, width, metrics);
    format!("{}{}{}", parts.left, parts.title.unwrap_or_default(), parts.right)
}

/// The rule's three runs, which Rich styles separately.
///
/// One authority for the arithmetic: `rule` joins these and the 147 recorded rows
/// gate it, so the painted form below cannot drift from the plain one.
struct RuleParts {
    left: String,
    /// `None` when there is no room for a title, where Rich emits one styled run
    /// of filler and no title segment at all.
    title: Option<String>,
    right: String,
}

fn rule_parts(title: &str, width: usize, metrics: &CellMetrics) -> RuleParts {
    let filler = '─';
    let all_filler = || RuleParts {
        left: std::iter::repeat_n(filler, width).collect(),
        title: None,
        right: String::new(),
    };
    if title.is_empty() {
        return all_filler();
    }
    let truncate_width = width.saturating_sub(4);
    if truncate_width == 0 {
        return all_filler();
    }
    let title = metrics.truncate_to_cells(title, truncate_width);
    let padded = metrics.cell_len(&title) + 2;
    let remaining = width.saturating_sub(padded);
    let left = remaining / 2;
    let right = remaining - left;
    RuleParts {
        left: format!("{} ", std::iter::repeat_n(filler, left).collect::<String>()),
        title: Some(title),
        right: format!(" {}", std::iter::repeat_n(filler, right).collect::<String>()),
    }
}

/// `#00ffba`, the rule's filler colour. Authored as RGB, so it downgrades.
const RULE_FILLER: Style = Style {
    bold: None, dim: None, italic: None, underline: None, reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#00ffba"))),
    background: None,
};

/// `[bold white]`, the rule's title. **`white` is a palette colour**, so it stays
/// `1;37` at every colour depth while the filler downgrades around it.
const RULE_TITLE: Style = Style {
    bold: Some(true), dim: None, italic: None, underline: None, reverse: None,
    strike: None, foreground: Some(StyleColor::Palette(7)), background: None,
};

/// The rule as the product actually writes it — **painted even though
/// `flags.color` is false.**
///
/// This is the finding, and it is not what it looks like. `cli.py:343` computes
/// `color` from a plain `sys.stdout.isatty()`, so piped output always takes this
/// plain route and `FORCE_COLOR` never reaches the flag. What it reaches is the
/// **console**: `console.py:98` builds `Console(theme=APP_THEME)` with **no
/// `force_terminal` argument at all** when `color` is falsy, so Rich runs its own
/// cascade and decides it is writing to a terminal.
///
/// Measured, piped, over ten environments: stripping the escapes from a
/// `FORCE_COLOR=1` run gives back the control **byte for byte**, in both list and
/// matches modes. **The route does not change. Only this line's paint does**, and
/// nothing else in the output gains a single escape.
///
/// Gated on `probes/rule-colour-oracle.json`, captured from `ch-legacy` before the
/// deletion slice removes it.
pub fn rule_styled(
    title: &str,
    width: usize,
    metrics: &CellMetrics,
    rendering: ColorRendering,
) -> String {
    let parts = rule_parts(title, width, metrics);
    let paint = |text: &str, style: Style| {
        crate::search_views::render_segment(
            &Segment { text: text.to_string(), style: Some(style), link: None },
            rendering,
        )
    };
    let mut rendered = paint(&parts.left, RULE_FILLER);
    if let Some(title) = &parts.title {
        rendered.push_str(&paint(title, RULE_TITLE));
        rendered.push_str(&paint(&parts.right, RULE_FILLER));
    }
    rendered
}

/// The user-facing session id.
///
/// Claude's is the filename stem. Pi's and Codex's is the in-band id when the file
/// carries one, falling back to the stem. Taken from the entries already decoded
/// during confirmation rather than by reopening the file, which is what Python
/// does — a second read would be a second chance to disagree with the first.
pub fn display_session_id(
    path: &std::path::Path,
    provider: session::Provider,
    native_id: Option<&str>,
) -> String {
    let stem = path
        .file_stem()
        .map(|stem| stem.to_string_lossy().into_owned())
        .unwrap_or_default();
    match provider {
        session::Provider::Claude => stem,
        _ => native_id.map(str::to_string).unwrap_or(stem),
    }
}

/// The YAML frontmatter block, without a trailing newline.
///
/// `include_separator` controls the leading `---`; the trailing one is the
/// caller's, because list mode prints neither and every other mode prints both.
pub fn metadata_block(
    hit: &SearchHit,
    home: &str,
    session_id: &str,
    include_separator: bool,
) -> String {
    let mut lines: Vec<String> = Vec::new();
    if include_separator {
        lines.push("---".to_string());
    }
    lines.push(format!("session_id: {session_id}"));
    lines.push(format!("provider: {}", hit.metadata.provider.as_str()));
    if let Some(forked) = hit.metadata.forked_from.as_deref().filter(|v| !v.is_empty()) {
        lines.push(format!("forked_from: {forked}"));
    }
    if let Some(cwd) = hit.cwd.as_deref().filter(|value| !value.is_empty()) {
        lines.push(format!(
            "directory: {}",
            crate::search_views::collapse_home(cwd, home)
        ));
    }
    lines.push(format!(
        "history_path: {}",
        crate::search_views::collapse_home(&hit.metadata.path.to_string_lossy(), home)
    ));
    if let Some(created) = hit.metadata.ctime {
        lines.push(format!("created: \"{}\"", created.format("%Y-%m-%d %H:%M")));
    }
    if let Some(modified) = hit.metadata.mtime {
        lines.push(format!("modified: \"{}\"", modified.format("%Y-%m-%d %H:%M")));
    }
    lines.push(format!("messages: {}", hit.messages.len()));
    lines.push(format!("matches: {}", hit.match_count()));
    for summary in &hit.matching_summaries {
        lines.push(format!("matched_summary: \"{summary}\""));
    }
    if let Some(title) = hit.last_custom_title.as_deref().filter(|v| !v.is_empty()) {
        lines.push(format!("custom_title: \"{title}\""));
    }
    lines.join("\n")
}

/// Everything the plain sink needs that does not change per hit.
pub struct PlainOutput<'a> {
    pub mode: SearchOutputMode,
    pub flags: &'a ConversationFlags,
    pub emit_metadata: bool,
    pub home: &'a str,
    pub width: usize,
    pub metrics: CellMetrics,
}

/// Writes the uncoloured modes straight to stdout.
///
/// **`--only-id` flushes every line individually, and that is not incidental.** It
/// is the whole deliverable of a measured scope: the first id of a piped
/// `ch search … -ll` went from 15.995 s to 0.38 s, with completion time unchanged,
/// purely because Python was block-buffering three short lines into a pipe. A sink
/// that buffers them regresses the product's most visible latency by fifteen
/// seconds and passes every byte comparison we have.
pub struct PlainSink<'a> {
    output: PlainOutput<'a>,
    /// Resolved **once**, here rather than on `PlainOutput`.
    ///
    /// Adding a field to `PlainOutput` would be the symmetric move — the two
    /// coloured sinks carry `rendering` that way — and it breaks `search_run.rs`
    /// the instant it is made, because a struct literal must name every field.
    /// Resolving in this constructor needs no caller change at all.
    ///
    /// `forced_terminal: false` is a fact about the call graph, not a default:
    /// this sink is only reached when `flags.color` is false.
    rendering: ColorRendering,
    closed: bool,
}

impl<'a> PlainSink<'a> {
    pub fn new(output: PlainOutput<'a>) -> PlainSink<'a> {
        PlainSink {
            output,
            rendering: crate::color::rendering(&crate::search_run::stdout_capabilities(false)),
            closed: false,
        }
    }

    /// Render one hit into the bytes this mode produces.
    pub fn render(&self, hit: &SearchHit) -> Result<String, String> {
        let session_id = display_session_id(
            &hit.metadata.path,
            hit.metadata.provider,
            hit.metadata.native_id.as_deref(),
        );
        if self.output.mode == SearchOutputMode::OnlyId {
            return Ok(format!("{session_id}\n"));
        }

        let mut rendered = String::new();
        rendered.push_str(&rule_styled(
            &session_id,
            self.output.width,
            &self.output.metrics,
            self.rendering,
        ));
        rendered.push('\n');

        // List mode prints one `---`-less block; every other mode brackets the
        // frontmatter with a separator above and below.
        let is_list = self.output.mode == SearchOutputMode::List;
        if self.output.emit_metadata {
            rendered.push_str(&metadata_block(
                hit,
                self.output.home,
                &session_id,
                !is_list,
            ));
            rendered.push('\n');
            if !is_list {
                rendered.push_str("---\n");
            }
        }
        if is_list {
            return Ok(rendered);
        }

        let displayed = displayed_messages(hit, self.output.mode);
        if displayed.is_empty() {
            return Ok(rendered);
        }
        let visible: Vec<Message> = displayed
            .iter()
            .map(|index| {
                crate::visibility::visible_message(
                    &hit.messages[*index],
                    self.output.flags,
                    Some(&crate::visibility::build_tool_id_map(&hit.messages)),
                    &hit.progressive,
                    *index,
                )
            })
            .collect();
        rendered.push_str(&crate::codecs::format_xml(&visible)?);
        rendered.push_str("\n\n");
        Ok(rendered)
    }
}

/// Which messages a mode displays: all of them, or only the matched ones.
pub fn displayed_messages(hit: &SearchHit, mode: SearchOutputMode) -> Vec<usize> {
    match mode {
        SearchOutputMode::Full => (0..hit.messages.len()).collect(),
        _ => hit.match_indices.clone(),
    }
}

impl HitSink for PlainSink<'_> {
    fn emit(&mut self, hit: &SearchHit) {
        let rendered = match self.render(hit) {
            Ok(rendered) => rendered,
            Err(error) => {
                self.emit_error(&error);
                return;
            }
        };
        let mut stdout = std::io::stdout();
        if stdout.write_all(rendered.as_bytes()).is_err() {
            self.closed = true;
            return;
        }
        // Per-line flush for id mode only, matching `search.py:350`. The other
        // modes emit whole blocks and match Python's unflushed `print`.
        if self.output.mode == SearchOutputMode::OnlyId && stdout.flush().is_err() {
            self.closed = true;
        }
    }

    fn closed(&self) -> bool {
        self.closed
    }

    fn emit_error(&mut self, message: &str) {
        print_error(message);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every recorded Rich rule reproduces, across eleven widths and nine titles.
    ///
    /// The table is the gate: hand-written expectations for a centring rule with
    /// truncation and wide characters are exactly the kind this project has been
    /// caught writing wrong.
    #[test]
    fn every_recorded_rule_reproduces() {
        let table = include_str!(
            "../thoughts/2026-08-28-search-rust-rewrite/teammates/engine-and-codex/probes/rule-oracle.tsv"
        );
        let metrics = CellMetrics::for_version(None);
        let mut checked = 0usize;
        for line in table.lines().skip(1) {
            let mut columns = line.splitn(3, '\t');
            let width: usize = columns.next().expect("width").parse().expect("numeric width");
            let title = unquote(columns.next().expect("title"));
            let expected = unquote(columns.next().expect("line"));
            assert_eq!(
                rule(&title, width, &metrics),
                expected,
                "rule at width {width} for title {title:?}"
            );
            checked += 1;
        }
        assert_eq!(checked, 99, "the recorded table must be complete");
    }

    /// The rows that separate the two `truncate_to_cells` (F16).
    ///
    /// The 99-row table above is green against **both** implementations, because
    /// its one wide title never truncates inside a double-width character. These
    /// 48 rows do: Rich pads with a space where a wide character cannot fit, so
    /// `你好你好你好` at width 8 is `─ 你 … ─` and not `─ 你… ─`.
    ///
    /// Generated by `probes/rule_oracle_wide.py`, which first regenerates all 99
    /// recorded rows from live Rich and refuses to write unless they reproduce —
    /// so these rows come from the same instrument as the table beside them.
    ///
    /// **Unreachable in production today**: `rule`'s only title is a session id,
    /// and all 4,693 in the pool are ASCII. Gated anyway, because that is a fact
    /// about this corpus and not about the function.
    #[test]
    fn a_wide_title_truncates_the_way_rich_truncates() {
        let table = include_str!(
            "../thoughts/2026-08-28-search-rust-rewrite/teammates/parity-finisher/probes/rule-oracle-wide.tsv"
        );
        let metrics = CellMetrics::for_version(None);
        let mut checked = 0usize;
        for line in table.lines().skip(1) {
            let mut columns = line.splitn(3, '\t');
            let width: usize = columns.next().expect("width").parse().expect("numeric width");
            let title = unquote(columns.next().expect("title"));
            let expected = unquote(columns.next().expect("line"));
            assert_eq!(
                rule(&title, width, &metrics),
                expected,
                "rule at width {width} for wide title {title:?}: Rich truncates \
                 through `set_cell_size`, which pads with a space when a \
                 double-width character cannot fit"
            );
            checked += 1;
        }
        assert_eq!(checked, 48, "the extension table must be complete");
    }

    /// The falsifier for the test above: the un-padding implementation this seat
    /// deleted, run over the same table, must fail on at least one row.
    ///
    /// Without it, a future reader cannot tell the extension table apart from 48
    /// more rows that any implementation would pass.
    #[test]
    fn the_wide_table_catches_a_truncation_that_does_not_pad() {
        fn without_padding(text: &str, limit: usize, metrics: &CellMetrics) -> String {
            if metrics.cell_len(text) <= limit {
                return text.to_string();
            }
            let mut kept = String::new();
            let mut cells = 0usize;
            for character in text.chars() {
                let size = metrics.character_cell_size(character);
                if cells + size > limit.saturating_sub(1) {
                    break;
                }
                cells += size;
                kept.push(character);
            }
            kept.push('…');
            kept
        }

        let metrics = CellMetrics::for_version(None);
        let caught = include_str!(
            "../thoughts/2026-08-28-search-rust-rewrite/teammates/parity-finisher/probes/rule-oracle-wide.tsv"
        )
        .lines()
        .skip(1)
        .filter(|line| {
            let mut columns = line.splitn(3, '\t');
            let width: usize = columns.next().expect("width").parse().expect("numeric width");
            let title = unquote(columns.next().expect("title"));
            let truncate_width = width.saturating_sub(4);
            truncate_width > 0
                && without_padding(&title, truncate_width, &metrics)
                    != metrics.truncate_to_cells(&title, truncate_width)
        })
        .count();
        assert!(
            caught >= 11,
            "the extension table must separate the two implementations on many \
             rows, not one; it caught {caught}, and 11 of the 48 was the figure \
             measured when the table was written. A table that catches nothing is \
             a question about the table, not a pass."
        );
    }

    /// `python_indent` is `textwrap.indent`, and three of these cases separate it
    /// from every `split('\n')` version.
    ///
    /// All 21 expectations were transcribed from a CPython 3.14 run, not reasoned
    /// out. The three that matter:
    ///
    /// - **U+001C, U+001D, U+001E, U+0085, U+2028, U+2029, `\v` and `\f` are line
    ///   boundaries.** A `split('\n')` version indents one line where Python
    ///   indents two.
    /// - **U+001F is whitespace but NOT a boundary**, so `"a\u{1f}b"` stays one
    ///   line. The two sets are not the same set, and this is the case that proves
    ///   it.
    /// - **A whitespace-only line takes no prefix**, and "whitespace" is
    ///   `str.isspace()` — so the middle line of `"a\n\u{1f}\nb"` is skipped where
    ///   Rust's own `trim` would have prefixed it.
    #[test]
    fn python_indent_reproduces_textwrap_indent() {
        for (input, expected) in [
            ("a\nb", "  a\n  b"),
            ("a\n", "  a\n"),
            ("a\n\nb", "  a\n\n  b"),
            ("a\n   \nb", "  a\n   \n  b"),
            ("  \n", "  \n"),
            ("", ""),
            ("a\r\nb", "  a\r\n  b"),
            ("a\rb", "  a\r  b"),
            ("a\u{b}b", "  a\u{b}  b"),
            ("a\u{c}b", "  a\u{c}  b"),
            ("a\u{1c}b", "  a\u{1c}  b"),
            ("a\u{1d}b", "  a\u{1d}  b"),
            ("a\u{1e}b", "  a\u{1e}  b"),
            ("a\u{1f}b", "  a\u{1f}b"),
            ("a\u{85}b", "  a\u{85}  b"),
            ("a\u{2028}b", "  a\u{2028}  b"),
            ("a\u{2029}b", "  a\u{2029}  b"),
            ("\n", "\n"),
            (" \nx", " \n  x"),
            ("a\n\u{1f}\nb", "  a\n\u{1f}\n  b"),
            ("<subagent-task>\nbody\n</subagent-task>\n\ntail", "  <subagent-task>\n  body\n  </subagent-task>\n\n  tail"),
        ] {
            assert_eq!(
                python_indent(input, "  "),
                expected,
                "python_indent({input:?}) must reproduce textwrap.indent at CPython 3.14"
            );
        }
    }

    /// The falsifier: a `split('\n')` indent with a Rust-`trim` predicate must fail
    /// this table on **both** mechanisms, not just one.
    ///
    /// A table that caught only the boundary half would look identical and cover
    /// half as much.
    #[test]
    fn the_indent_table_catches_a_naive_splitter() {
        fn naive_indent(text: &str, prefix: &str) -> String {
            text.split('\n')
                .map(|line| {
                    if line.trim().is_empty() {
                        line.to_string()
                    } else {
                        format!("{prefix}{line}")
                    }
                })
                .collect::<Vec<String>>()
                .join("\n")
        }

        assert_ne!(
            naive_indent("a\u{2028}b", "  "),
            python_indent("a\u{2028}b", "  "),
            "the falsifier must reproduce what it stands for: splitting on \\n alone \
             misses U+2028, so one line is indented where Python indents two"
        );
        assert_ne!(
            naive_indent("a\n\u{1f}\nb", "  "),
            python_indent("a\n\u{1f}\nb", "  "),
            "and the predicate half: Rust's `trim` leaves U+001F, so a line Python \
             calls whitespace takes a prefix here"
        );
    }

    /// Every recorded rule line reproduces, from the environment variables up.
    ///
    /// **The recording is from `ch-legacy` and cannot be re-taken** once the
    /// deletion slice removes it: `probes/rule-colour-oracle.json`, ten
    /// environments × two output shapes, stdout bytes verbatim at `COLUMNS=100`.
    ///
    /// This drives the whole chain rather than the paint alone — the environment
    /// map goes through `terminal::resolve_color`, its answer through
    /// `color::rendering`, and only then into `rule_styled`. **A cascade defect and
    /// a painting defect both land here**, which is the point: the two were
    /// entangled in the original report and only a measurement separated them.
    ///
    /// Four of these rows are findings in their own right:
    /// `FORCE_COLOR=0` still colours, because Rich tests **presence, not truth**;
    /// `TTY_COMPATIBLE=0` beats `FORCE_COLOR=1`, because it is checked first;
    /// `NO_COLOR=1` keeps **bold** and drops colour, which is preserve-because-wrong
    /// item 10 on stdout; and `TERM=dumb` drops the width to 80, so it is 60 bytes
    /// shorter than the control rather than merely unpainted.
    #[test]
    fn every_recorded_rule_colour_reproduces() {
        let recorded = rule_colour_oracle();
        let metrics = CellMetrics::for_version(None);
        let mut checked = 0usize;
        for (shape, rows) in &recorded.rows {
            for (name, first_line) in rows {
                let capabilities = recorded.capabilities(name);
                // `terminal_width_for`'s dumb rule: 80 before `COLUMNS` is read at
                // all. Applied here rather than by mutating the environment,
                // because these tests run in parallel threads.
                let width = if capabilities.is_dumb { 80 } else { recorded.columns };
                assert_eq!(
                    &rule_styled(
                        &recorded.session_id,
                        width,
                        &metrics,
                        crate::color::rendering(&capabilities),
                    ),
                    first_line,
                    "{shape} / {name}: the rule must reproduce ch-legacy byte for byte"
                );
                checked += 1;
            }
        }
        assert_eq!(checked, 20, "the recorded table must be complete");
    }

    /// The falsifier: the plain `rule`, over the same table, must fail every row
    /// that carries an escape and pass every row that does not.
    ///
    /// Without it, a table whose tiers all came out bare would look identical to a
    /// table that proves the paint — which is the failure the capture's own
    /// refusals exist to prevent, checked here from the other side.
    #[test]
    fn the_colour_table_catches_an_unpainted_rule() {
        let recorded = rule_colour_oracle();
        let metrics = CellMetrics::for_version(None);
        let mut caught = 0usize;
        let mut bare = 0usize;
        for rows in recorded.rows.values() {
            for (name, first_line) in rows {
                let capabilities = recorded.capabilities(name);
                let width = if capabilities.is_dumb { 80 } else { recorded.columns };
                let plain = rule(&recorded.session_id, width, &metrics);
                if first_line.contains('\u{1b}') {
                    assert_ne!(&plain, first_line, "{name} carries escapes; plain must differ");
                    caught += 1;
                } else {
                    assert_eq!(&plain, first_line, "{name} carries none; plain must match");
                    bare += 1;
                }
            }
        }
        assert_eq!(caught, 14, "14 of the 20 recorded rows carry colour");
        assert_eq!(bare, 6, "and 6 do not — control, dumb and TTY_COMPATIBLE=0, twice over");
    }

    struct RuleColourOracle {
        columns: usize,
        session_id: String,
        environments: std::collections::BTreeMap<String, std::collections::BTreeMap<String, String>>,
        rows: std::collections::BTreeMap<String, std::collections::BTreeMap<String, String>>,
    }

    impl RuleColourOracle {
        /// The recorded environment, resolved the way the product resolves it:
        /// piped, never forced.
        fn capabilities(&self, name: &str) -> crate::terminal::TerminalCapabilities {
            let environment = &self.environments[name];
            let get = |key: &str| environment.get(key).map(String::as_str);
            crate::terminal::resolve_color(&crate::terminal::AmbientColorInputs {
                colorterm: get("COLORTERM"),
                term: get("TERM"),
                force_color: get("FORCE_COLOR"),
                tty_compatible: get("TTY_COMPATIBLE"),
                no_color: get("NO_COLOR"),
                is_a_tty: false,
                forced_terminal: false,
            })
        }
    }

    fn rule_colour_oracle() -> RuleColourOracle {
        let raw: serde_json::Value = serde_json::from_str(include_str!(
            "../thoughts/2026-08-28-search-rust-rewrite/teammates/parity-finisher/probes/rule-colour-oracle.json"
        ))
        .expect("the recorded table parses");
        let environments = raw["environments"]
            .as_object()
            .expect("environments")
            .iter()
            .map(|(name, values)| {
                (
                    name.clone(),
                    values
                        .as_object()
                        .expect("environment")
                        .iter()
                        .map(|(key, value)| {
                            (key.clone(), value.as_str().expect("string").to_string())
                        })
                        .collect(),
                )
            })
            .collect();
        let rows = raw["recorded"]
            .as_object()
            .expect("recorded")
            .iter()
            .map(|(shape, byname)| {
                (
                    shape.clone(),
                    byname
                        .as_object()
                        .expect("shape")
                        .iter()
                        .map(|(name, encoded)| {
                            let bytes = decode_base64(encoded.as_str().expect("base64"));
                            let text = String::from_utf8(bytes).expect("utf-8 stdout");
                            let first = text.split('\n').next().unwrap_or_default().to_string();
                            (name.clone(), first)
                        })
                        .collect(),
                )
            })
            .collect();
        RuleColourOracle {
            columns: raw["columns"].as_str().expect("columns").parse().expect("numeric"),
            session_id: raw["session_id"].as_str().expect("session id").to_string(),
            environments,
            rows,
        }
    }

    /// Enough base64 to read the recording. The table stores raw stdout bytes, so
    /// it cannot be plain JSON strings.
    fn decode_base64(value: &str) -> Vec<u8> {
        const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        let mut out = Vec::new();
        let mut accumulator = 0u32;
        let mut bits = 0u32;
        for byte in value.bytes().filter(|byte| *byte != b'=') {
            let index = ALPHABET
                .iter()
                .position(|candidate| *candidate == byte)
                .expect("base64 alphabet") as u32;
            accumulator = (accumulator << 6) | index;
            bits += 6;
            if bits >= 8 {
                bits -= 8;
                out.push((accumulator >> bits) as u8);
            }
        }
        out
    }

    /// Python's repr quoting, enough for the recorded table's own escapes.
    fn unquote(value: &str) -> String {
        let trimmed = value.trim();
        let inner = &trimmed[1..trimmed.len() - 1];
        inner.replace("\\'", "'").replace("\\\\", "\\")
    }

    /// A rule narrower than its own padding degrades to a plain line rather than
    /// overflowing, which is what the recorded table shows at the smallest widths.
    #[test]
    fn a_rule_never_exceeds_its_width() {
        let metrics = CellMetrics::for_version(None);
        for width in 0..24 {
            for title in ["", "a", "session-abcdef01", "你好世界"] {
                let line = rule(title, width, &metrics);
                assert!(
                    metrics.cell_len(&line) <= width.max(0),
                    "rule overflowed: width {width}, title {title:?}, got {line:?}"
                );
            }
        }
    }
}

// ------------------------------------------------------------- the entry point

/// Whether one term may use the decoded JSON-string batch gate.
///
/// Ported from `_can_use_logical_json_string_gate`. Every clause is a correctness
/// condition rather than a heuristic: the gate reasons about the file's raw bytes,
/// so any flag that makes the renderer *synthesize* text absent from those bytes
/// has to disable it, or a real hit is rejected without being read.
///
/// **The `.isascii()` clause is the load-bearing one.** `literal_candidate` uses
/// full case folding while matching uses `re.IGNORECASE`, and the two genuinely
/// disagree — for `ß` the candidate is `ss` while the compiled pattern does not
/// match `ss`. ASCII is the only region where they coincide. Widening this to
/// non-ASCII as an optimisation buys the silent loss of a user's result.
pub fn can_use_json_string_gate(term: &SearchTerm, flags: &ConversationFlags) -> bool {
    let Some(candidate) = term.literal_candidate.as_deref() else {
        return false;
    };
    let _ = candidate;
    !term.case_sensitive
        && term.pattern.is_ascii()
        && !term
            .pattern
            .chars()
            .any(|character| matches!(character, '"' | '\\') || (character as u32) < 0x20)
        && !RENDER_DEPENDENT_TOKENS.iter().any(|token| term.pattern.contains(token))
        && flags.message_selection == crate::visibility::MessageSelection::All
        && !flags.show_thinking
        && !tools_requested(flags)
        && !flags.show_agents
        && !flags.show_custom
        && !flags.show_branches
        && !flags.show_plans
        && !flags.shorten
        && !flags.shorten_progressive
        && !flags.shorten_thinking
}

fn tools_requested(flags: &ConversationFlags) -> bool {
    match &flags.show_tools {
        crate::tool_filter::ToolVisibility::All(shown) => *shown,
        crate::tool_filter::ToolVisibility::Filters(filters) => !filters.is_empty(),
    }
}

/// Render messages as plain Markdown, for `--format raw`.
///
/// Ported from `format_to_raw`. A single visible message prints its body with no
/// header at all; two or more get headers and `---` separators. Agent blocks are
/// indented two spaces.
pub fn format_raw(visible: &[Message]) -> Result<String, String> {
    let mut blocks: Vec<(String, bool, String)> = Vec::new();
    for message in visible {
        let (rendered, _) = crate::codecs::render_message_inner_xml(message, false)?;
        if rendered.is_empty() {
            continue;
        }
        blocks.push((
            message.header(),
            message.message_type == crate::model::MessageType::Agent,
            rendered.trim_end().to_string(),
        ));
    }
    if blocks.is_empty() {
        return Ok(String::new());
    }
    // A single visible message returns before the indent, which is why `-r` on a
    // one-message agent result is flush left and the same agent beside a second
    // message is not. Python's early return, reproduced rather than tidied.
    if blocks.len() == 1 {
        return Ok(blocks.into_iter().next().expect("length checked").2);
    }
    Ok(blocks
        .into_iter()
        .map(|(header, is_agent, content)| {
            let content = if is_agent { python_indent(&content, "  ") } else { content };
            if header.is_empty() { content } else { format!("{header}\n\n{content}") }
        })
        .collect::<Vec<String>>()
        .join("\n\n---\n\n"))
}

/// Python's `textwrap.indent(text, prefix)`.
///
/// **Two details a `split('\n')` version gets wrong, and both belong to the class
/// this seat has been chasing all day.** The line boundaries are Python's — `\v`,
/// `\f`, U+001C..U+001E, U+0085, U+2028 and U+2029 as well as `\n` and `\r\n` — so
/// `session_render::python_splitlines` stays the one authority for them instead of
/// a second copy here. And the predicate is `not line.isspace()`, whose whitespace
/// set includes U+001C..U+001F, so `session::python_strip` decides it.
///
/// The separators are carried through verbatim by offset, because `python_splitlines`
/// drops them and `\r\n` must not become `\n`.
fn python_indent(text: &str, prefix: &str) -> String {
    let lines = crate::session_render::python_splitlines(text);
    let mut out = String::with_capacity(text.len() + lines.len() * prefix.len());
    let mut cursor = 0usize;
    for line in lines {
        // Sound: every slice `python_splitlines` returns is a subslice of `text`.
        let start = line.as_ptr() as usize - text.as_ptr() as usize;
        out.push_str(&text[cursor..start]);
        // **Python's predicate runs on the line WITH its ending**, which is what
        // makes this one line rather than two. `splitlines(True)` yields `"\n"`
        // for a blank line, and `"\n".isspace()` is true, so a blank line takes
        // no prefix. Testing the ending-stripped body instead — and reaching for
        // `"".isspace() is False` to justify prefixing it — gives `"  a\n  \n  b"`
        // where Python gives `"  a\n\n  b"`. The recorded table caught exactly
        // that, on the first run.
        if !crate::session::python_strip(line).is_empty() {
            out.push_str(prefix);
        }
        out.push_str(line);
        cursor = start + line.len();
    }
    out.push_str(&text[cursor..]);
    out
}

/// Collects hits instead of writing them, for the one mode that cannot stream.
pub struct BufferingSink {
    pub hits: Vec<SearchHit>,
    closed: bool,
}

impl BufferingSink {
    pub fn new() -> BufferingSink {
        BufferingSink { hits: Vec::new(), closed: false }
    }
}

impl Default for BufferingSink {
    fn default() -> Self {
        BufferingSink::new()
    }
}

impl HitSink for BufferingSink {
    fn emit(&mut self, hit: &SearchHit) {
        self.hits.push(hit.clone());
    }
    fn closed(&self) -> bool {
        self.closed
    }
    fn emit_error(&mut self, message: &str) {
        print_error(message);
    }
}

/// Tokens whose presence means the match depends on the render rather than on
/// the file's bytes, so no byte gate can decide the term.
const RENDER_DEPENDENT_TOKENS: [&str; 5] = ["<", "=\"", "```", "old_string:", "new_string:"];

/// Evidence that a Pi file synthesizes visible text absent from its raw bytes.
const PI_USER_AGENT_EVIDENCE: &[u8] = b"\"pi-user-agents\"";
/// Evidence that a file's JSON escapes could decode into the needle.
const JSON_UNICODE_ESCAPE_EVIDENCE: &[u8] = b"\\u";

/// Whether a file's raw bytes could plausibly satisfy the query.
///
/// Ported from `_search_path_candidate_matches`. This is the **serial** path's
/// probe, used whenever a query is not one term eligible for the batched
/// JSON-string gate. Without it every screen survivor is read and rendered.
///
/// **Every arm that returns `true` early is a correctness requirement, not a
/// missed optimisation.** The gate reasons about bytes on disk; anything that
/// makes the renderer *synthesize* text those bytes do not contain has to defer,
/// or a real hit is rejected without ever being read. That is the asymmetric
/// direction: a false positive costs a read, a false negative costs the user a
/// result they will never know they missed.
pub fn path_candidate_matches(
    path: &std::path::Path,
    query: &Query,
    flags: &ConversationFlags,
    pi_session: bool,
) -> bool {
    if let Query::Term(term) = query
        && can_use_json_string_gate(term, flags)
        && let Some(candidate) = term.literal_candidate.as_deref()
    {
        let evidence: Vec<Vec<Vec<u8>>> = if pi_session {
            vec![vec![PI_USER_AGENT_EVIDENCE.to_vec()]]
        } else {
            Vec::new()
        };
        // Python swallows `OSError` here and answers `true`. An unreadable file
        // then reaches confirmation, which fails to open it too and prints the
        // same `[Errno N]` line at the same scan position.
        return crate::scanner::file_contains_ascii_json_strings_impl(
            path,
            candidate.as_bytes(),
            &evidence,
        )
        .unwrap_or(true);
    }
    // Python raises out of the whole prefilter on the first failure, so exactly
    // one error is printed and the file is skipped. Recording the failure and
    // short-circuiting reproduces that; printing inside the per-term closure does
    // not — an `OR` of two terms would print the same line twice.
    let mut failure: Option<String> = None;
    let survives = evaluate_prefilter(query, &mut |term| {
        if failure.is_some() {
            return false;
        }
        term_path_candidate_matches(path, term, flags, pi_session, &mut failure)
    });
    match failure {
        Some(message) => {
            print_error(&format!(
                "Error processing conversation file {}: {message}",
                path.display()
            ));
            false
        }
        None => survives,
    }
}

/// Boolean evaluation where a `NOT` always passes.
///
/// Ported from `_evaluate_prefilter`. A negated term cannot reject a file: the
/// bytes being absent is exactly what makes `NOT term` true, so treating absence
/// as a rejection would invert the operator.
fn evaluate_prefilter(query: &Query, term_matches: &mut dyn FnMut(&SearchTerm) -> bool) -> bool {
    match query {
        Query::Not(_) => true,
        Query::And(operands) => operands
            .iter()
            .all(|operand| evaluate_prefilter(operand, term_matches)),
        Query::Or(operands) => operands
            .iter()
            .any(|operand| evaluate_prefilter(operand, term_matches)),
        Query::Term(term) => term_matches(term),
    }
}

/// One term against one file's raw bytes.
fn term_path_candidate_matches(
    path: &std::path::Path,
    term: &SearchTerm,
    flags: &ConversationFlags,
    pi_session: bool,
    failure: &mut Option<String>,
) -> bool {
    if term_can_match_generated_marker(term, flags) {
        return true;
    }
    let Some(needle) = ascii_literal_needle(term) else {
        return true;
    };
    // Any of these makes the render carry text the file's bytes do not.
    let gate_bypassed = flags.show_thinking
        || tools_requested(flags)
        || flags.show_agents
        || flags.show_custom
        || flags.show_branches
        || flags.show_plans
        || flags.shorten
        || flags.shorten_progressive
        || flags.shorten_thinking
        || term_can_change_under_json_decoding(term);
    if gate_bypassed {
        return true;
    }

    let mut evidence: Vec<Vec<Vec<u8>>> = vec![vec![JSON_UNICODE_ESCAPE_EVIDENCE.to_vec()]];
    if pi_session {
        evidence.push(vec![PI_USER_AGENT_EVIDENCE.to_vec()]);
    }
    // Python does **not** swallow here, so an unreadable file becomes a per-file
    // error. Answering `true` reaches the same *place* — confirmation opens the
    // same file and fails the same way — but **not the same line**.
    //
    // Measured on a `chmod 000` file:
    //     Python, at this gate      …: Permission denied (os error 13)
    //     native, at confirmation   …: [Errno 13] Permission denied: '/p'
    //
    // The inversion is why it is not obvious. Python's message here comes *from
    // Rust*: `file_contains_ascii_impl` returns an `io::Error` and PyO3 wraps it in
    // a `PermissionError` whose `str()` is Rust's form. `python_io::python_io_error`
    // models `OSError.__str__` faithfully and is therefore **too faithful for this
    // site**, because Python is not raising an `OSError` of its own here.
    //
    // Ruled: the legacy route prints Rust's form at this stage, so the native route
    // must too. The batched arm above is correct and different: that one really does
    // `except OSError: return True`.
    //
    // Printing from inside a predicate looks wrong and mirrors Python exactly — the
    // raise propagates out of `_search_path_candidate_matches`, the per-file handler
    // prints it, and the file is skipped rather than confirmed.
    match crate::scanner::file_contains_ascii_impl(path, &needle, term.case_sensitive, &evidence)
    {
        Ok(found) => found,
        Err(error) => {
            // Recorded, not printed: the caller prints once for the whole file.
            // `error.to_string()` is Rust's form, which is what the legacy route
            // prints here because PyO3 wraps this same `io::Error`.
            *failure = Some(error.to_string());
            false
        }
    }
}

/// The byte needle for a term safe to probe, or `None` to defer.
fn ascii_literal_needle(term: &SearchTerm) -> Option<Vec<u8>> {
    if RENDER_DEPENDENT_TOKENS
        .iter()
        .any(|token| term.pattern.contains(token))
    {
        return None;
    }
    if !term.pattern.is_ascii() {
        return None;
    }
    Some(term.literal_candidate.as_deref()?.as_bytes().to_vec())
}

/// Whether JSON string decoding could *create* the literal, so raw bytes cannot
/// decide it.
fn term_can_change_under_json_decoding(term: &SearchTerm) -> bool {
    term.pattern
        .chars()
        .any(|character| matches!(character, '"' | '\\' | '/') || (character as u32) < 0x20)
}

/// Whether a literal could match text the renderer generates rather than reads.
///
/// The candidate is tested for being **contained in** a marker, not the reverse:
/// searching `too` must defer when `--tools` is on, because `tool-output` is
/// synthesized. `AdditionalContext` is a rendered tool name absent from the raw
/// JSONL, so it needs the same escape hatch.
fn term_can_match_generated_marker(term: &SearchTerm, flags: &ConversationFlags) -> bool {
    let Some(candidate) = term.literal_candidate.as_deref() else {
        return false;
    };
    let mut markers: Vec<&str> = Vec::new();
    if flags.show_thinking {
        markers.push("thinking");
    }
    if tools_requested(flags) || flags.show_plans {
        markers.push("tool-input");
    }
    if tools_requested(flags) {
        markers.push("tool-output");
        markers.push("AdditionalContext");
    }
    if flags.show_plans {
        markers.push("ExitPlanMode");
    }
    markers.iter().any(|marker| {
        if term.case_sensitive {
            marker.contains(candidate)
        } else {
            crate::search_query::python_casefold(marker).contains(candidate)
        }
    })
}
