//! One recorded table over **both** wrap implementations.
//!
//! # What this gate covers, and what it does not
//!
//! Rich's word splitter (`_wrap.words`, `re_word = r"\s*\S+\s*"`) and its
//! `Text.rstrip_end` each exist **twice** in this tree: once in `terminal.rs`, for
//! the error-message wrap, and once in `session_render.rs`, for the markdown wrap.
//! Neither is wrong and both are needed. The unification was deliberately deferred
//! past the cutover, and this gate is what makes deferring safe: a copy goes stale
//! silently, and one table over both catches the drift without paying for the
//! refactor.
//!
//! **The two copies are not covered to the same depth, and the difference is
//! stated here rather than buried:**
//!
//! - `terminal.rs` is gated **directly**. `wrap_preserving_spaces` is the whole
//!   path, so every row exercises its `rich_words` and its `rstrip_end`.
//! - `session_render.rs` is gated **composed**, through the public `RichText::wrap`.
//!   Its `words` and `rstrip_end` are private and this seat does not edit that
//!   file, so they are reached the way a caller reaches them and not in isolation.
//!   A defect that `RichText::wrap` masks would not show here.
//!
//! # The table
//!
//! `wrap-oracle.tsv`, 235 rows over five widths, recorded from live Rich by
//! `engine-and-codex`. Its corpus is built so the wrap boundary lands in every
//! position relative to a space, which is the case hand-reasoning gets wrong: three
//! wrong fixes preceded it, and only the recorded table settled which was right.
//!
//! The 30 wide-character rows in `wrap-oracle-cjk.tsv` are this seat's addition for
//! F17, where the two `chop_cells` disagree. The ASCII table cannot see that
//! difference — it needs a grapheme wider than the whole line.

use crate::cells::CellMetrics;
use crate::search_views::Style;
use crate::session_render::{Justify, Overflow, RichText};
use crate::terminal::wrap_preserving_spaces;

const ASCII_TABLE: &str = include_str!(
    "../thoughts/2026-08-28-search-rust-rewrite/teammates/engine-and-codex/probes/wrap-oracle.tsv"
);
const CJK_TABLE: &str = include_str!(
    "../thoughts/2026-08-28-search-rust-rewrite/teammates/parity-finisher/probes/wrap-oracle-cjk.tsv"
);

/// One recorded row: a width, the message, and Rich's wrapped answer.
struct Row {
    width: usize,
    message: String,
    wrapped: String,
}

fn rows(table: &str) -> Vec<Row> {
    table
        .lines()
        .skip(1)
        .filter(|line| !line.is_empty())
        .map(|line| {
            let mut columns = line.splitn(3, '\t');
            Row {
                width: columns.next().expect("width").parse().expect("numeric width"),
                message: unquote(columns.next().expect("message")),
                wrapped: unquote(columns.next().expect("wrapped")),
            }
        })
        .collect()
}

/// Python `repr` quoting, as the recorded tables use it.
fn unquote(value: &str) -> String {
    let inner = &value[1..value.len() - 1];
    let mut out = String::with_capacity(inner.len());
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
            Some(other) => out.push(other),
            None => out.push('\\'),
        }
    }
    out
}

/// The markdown copy, reached the only way a caller can reach it.
fn markdown_wrap(message: &str, width: usize, metrics: &CellMetrics) -> String {
    RichText::from_str(message, Style::default())
        .wrap(width, Justify::Default, Overflow::Fold, 8, false, metrics)
        .iter()
        .map(RichText::plain)
        .collect::<Vec<String>>()
        .join("\n")
}

#[test]
fn the_error_wrap_reproduces_every_recorded_row() {
    let rows = rows(ASCII_TABLE);
    assert_eq!(rows.len(), 235, "the recorded table must be complete");
    for row in &rows {
        assert_eq!(
            wrap_preserving_spaces(&row.message, row.width),
            row.wrapped,
            "terminal.rs wrap at width {} for {:?}",
            row.width,
            row.message
        );
    }
}

#[test]
fn the_markdown_wrap_reproduces_every_recorded_row() {
    let metrics = CellMetrics::for_version(None);
    for row in &rows(ASCII_TABLE) {
        assert_eq!(
            markdown_wrap(&row.message, row.width, &metrics),
            row.wrapped,
            "session_render.rs wrap at width {} for {:?} — the two copies of \
             Rich's word splitter and rstrip_end have drifted, which is the whole \
             reason deferring their unification was safe",
            row.width,
            row.message
        );
    }
}

/// The wide-character rows, where `chop_cells` decides the answer.
#[test]
fn both_wraps_reproduce_the_recorded_wide_character_rows() {
    let metrics = CellMetrics::for_version(None);
    let rows = rows(CJK_TABLE);
    assert_eq!(rows.len(), 30, "the wide-character table must be complete");
    for row in &rows {
        assert_eq!(
            wrap_preserving_spaces(&row.message, row.width),
            row.wrapped,
            "terminal.rs wrap at width {} for {:?}",
            row.width,
            row.message
        );
        assert_eq!(
            markdown_wrap(&row.message, row.width, &metrics),
            row.wrapped,
            "session_render.rs wrap at width {} for {:?}",
            row.width,
            row.message
        );
    }
}

/// Both sides of the F17 disagreement, so the recorded table's power is stated
/// rather than assumed.
///
/// The implementation deleted from `terminal.rs` carried an extra
/// `&& !line.is_empty()` guard, so it never emitted the leading empty piece Rich
/// emits when the very first grapheme already exceeds the width. The ASCII table
/// cannot see that — it needs a grapheme wider than the whole line — which is why
/// 235 green rows were not evidence that the two `chop_cells` agreed.
///
/// **Attributed by measurement, not by reasoning.** Restoring the deleted
/// `chop_cells` while keeping every other change leaves the wide table red at
/// width 1 for `"a 你好 b"`: it produced `"a\n \n \n \nb"` where Rich produces
/// `"a\n\n \n \n \nb"`. That pair is asserted below, so the gate pins the wrong
/// answer as well as the right one.
#[test]
fn the_wide_table_catches_the_chop_cells_that_never_emits_a_leading_empty_piece() {
    assert_ne!(
        wrap_preserving_spaces("a 你好 b", 1),
        "a\n \n \n \nb",
        "the production wrap has returned the answer the deleted `chop_cells` \
         gave: the leading empty piece is missing again, and the recorded row \
         above is the only thing that would have caught it"
    );

    fn chop_cells_without_leading_empty(
        text: &str,
        width: usize,
        metrics: &CellMetrics,
    ) -> Vec<String> {
        let mut lines: Vec<String> = Vec::new();
        let mut line = String::new();
        let mut size = 0usize;
        for character in text.chars() {
            let cell = metrics.character_cell_size(character);
            if size + cell > width && !line.is_empty() {
                lines.push(std::mem::take(&mut line));
                size = 0;
            }
            line.push(character);
            size += cell;
        }
        if !line.is_empty() {
            lines.push(line);
        }
        lines
    }

    let metrics = CellMetrics::for_version(None);
    let caught = rows(CJK_TABLE)
        .iter()
        .filter(|row| {
            row.message.split_whitespace().any(|word| {
                chop_cells_without_leading_empty(word, row.width, &metrics)
                    != metrics.chop_cells(word, row.width)
            })
        })
        .count();
    assert!(
        caught >= 5,
        "the wide table must separate the two chop_cells on several rows, not one; \
         it caught {caught}, and 5 of the 30 was the figure measured when the table \
         was written. A mutation that catches nothing is a question about the \
         corpus, not a pass."
    );
}
