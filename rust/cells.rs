//! Terminal cell measurement, following Rich's `rich.cells`.
//!
//! Every chrome line the product emits is wrapped in a Rich `Text` with
//! `overflow="ellipsis"`, which clips the assembled line to the console width in
//! **cells**. That is a second clip on top of `elide_to_width`, which counts code
//! points — two layers, two units, both load-bearing. A port carrying only the
//! first is correct at every ASCII width and wrong on the first wide character.

use crate::cell_tables::{NARROW_TO_WIDE, VERSIONS, WIDTH_TABLES, WidthRange};
use crate::terminal::python_int;

const ZERO_WIDTH_JOINER: char = '\u{200d}';
const VARIATION_SELECTOR_16: char = '\u{fe0f}';

/// Codepoint ranges Rich treats as one cell without consulting a table.
///
/// Non-exhaustive by design — it is Rich's fast path, not a definition — but it
/// covers Latin, Greek, Cyrillic, box drawing and Braille, so the panel frame and
/// every ASCII headline skip the table entirely.
const SINGLE_CELL_RANGES: [(u32, u32); 6] = [
    (0x20, 0x7E),
    (0xA0, 0xAC),
    (0xAE, 0x2FF),
    (0x370, 0x482),
    (0x2500, 0x25FC),
    (0x2800, 0x28FF),
];

/// A resolved cell-width table.
///
/// Rich picks the table from `UNICODE_VERSION` and falls back to the newest it
/// ships. The choice is observable: the same headline at the same width renders
/// 20 characters under `UNICODE_VERSION=9.0.0` and 31 under the default.
#[derive(Clone, Copy, Debug)]
pub struct CellMetrics {
    widths: &'static [WidthRange],
}

impl CellMetrics {
    /// Resolve the table the way Rich's `load("auto")` does.
    pub fn from_environment() -> CellMetrics {
        CellMetrics::for_version(std::env::var("UNICODE_VERSION").ok().as_deref())
    }

    /// Resolve a table from an explicit `UNICODE_VERSION` value.
    ///
    /// An absent or unparseable value takes the newest table. A parseable version
    /// with no exact table takes the newest table **older than** it.
    ///
    /// ```
    /// use _native::cells::CellMetrics;
    /// // '߽' is one cell under Unicode 9 and zero cells from Unicode 14 onward.
    /// assert_eq!(CellMetrics::for_version(Some("9.0.0")).cell_len("A߽B"), 3);
    /// assert_eq!(CellMetrics::for_version(Some("17.0.0")).cell_len("A߽B"), 2);
    /// // No exact table: fall back to the newest older one, which is 9.0.0.
    /// assert_eq!(CellMetrics::for_version(Some("9.5")).cell_len("A߽B"), 3);
    /// // Unparseable falls forward to the newest.
    /// assert_eq!(CellMetrics::for_version(Some("nonsense")).cell_len("A߽B"), 2);
    /// assert_eq!(CellMetrics::for_version(None).cell_len("A߽B"), 2);
    /// ```
    pub fn for_version(unicode_version: Option<&str>) -> CellMetrics {
        CellMetrics {
            widths: WIDTH_TABLES[table_index(unicode_version)],
        }
    }

    /// Cells occupied by one character, or zero for a combining or control character.
    pub fn character_cell_size(&self, character: char) -> usize {
        let codepoint = u32::from(character);
        if (codepoint != 0 && codepoint < 32) || (0x7F..0xA0).contains(&codepoint) {
            return 0;
        }
        let last = self.widths[self.widths.len() - 1];
        if codepoint > last.1 {
            return 1;
        }
        match self
            .widths
            .binary_search_by(|(start, end, _)| match (*start, *end) {
                (start, _) if codepoint < start => std::cmp::Ordering::Greater,
                (_, end) if codepoint > end => std::cmp::Ordering::Less,
                _ => std::cmp::Ordering::Equal,
            }) {
            Ok(index) => usize::from(self.widths[index].2),
            Err(_) => 1,
        }
    }

    /// Cells the whole string occupies in a terminal.
    ///
    /// ```
    /// use _native::cells::CellMetrics;
    /// let metrics = CellMetrics::for_version(None);
    /// assert_eq!(metrics.cell_len("hello"), 5);
    /// assert_eq!(metrics.cell_len("你好"), 4);
    /// // A zero-width joiner sequence measures as its joined parts, not its codepoints.
    /// assert_eq!(metrics.cell_len("\u{1f468}\u{200d}\u{1f4bb}"), 2);
    /// ```
    pub fn cell_len(&self, text: &str) -> usize {
        if is_single_cell_widths(text) {
            return text.chars().count();
        }
        if !text.contains(ZERO_WIDTH_JOINER) && !text.contains(VARIATION_SELECTOR_16) {
            return text
                .chars()
                .map(|character| self.character_cell_size(character))
                .sum();
        }
        self.joined_cell_len(text)
    }

    /// The zero-width-joiner and variation-selector path, which no sum over
    /// characters can reproduce: a joiner swallows the character after it, and
    /// selector 16 widens the character before it.
    fn joined_cell_len(&self, text: &str) -> usize {
        let characters: Vec<char> = text.chars().collect();
        let mut total_width = 0usize;
        let mut last_measured: Option<char> = None;
        let mut index = 0usize;
        while index < characters.len() {
            let character = characters[index];
            if character == ZERO_WIDTH_JOINER {
                index += 1;
            } else if character == VARIATION_SELECTOR_16 {
                if let Some(previous) = last_measured.take() {
                    total_width += usize::from(NARROW_TO_WIDE.contains(&previous));
                }
            } else {
                let width = self.character_cell_size(character);
                if width != 0 {
                    last_measured = Some(character);
                    total_width += width;
                }
            }
            index += 1;
        }
        total_width
    }

    /// Divide the string into graphemes, returning each one's character span and
    /// cell width alongside the total width.
    fn split_graphemes_of(&self, characters: &[char]) -> (Vec<(usize, usize, usize)>, usize) {
        let mut spans: Vec<(usize, usize, usize)> = Vec::new();
        let mut total_width = 0usize;
        let mut last_measured: Option<char> = None;
        let mut index = 0usize;
        while index < characters.len() {
            let character = characters[index];
            if character == ZERO_WIDTH_JOINER || character == VARIATION_SELECTOR_16 {
                if spans.is_empty() {
                    index += 1;
                    spans.push((index - 1, index, 0));
                    continue;
                }
                if character == ZERO_WIDTH_JOINER {
                    index += if index < characters.len() - 1 { 2 } else { 1 };
                    let (start, _end, cell_length) = spans[spans.len() - 1];
                    let last = spans.len() - 1;
                    spans[last] = (start, index, cell_length);
                } else {
                    index += 1;
                    let last = spans.len() - 1;
                    let (start, _end, mut cell_length) = spans[last];
                    if let Some(previous) = last_measured
                        && NARROW_TO_WIDE.contains(&previous)
                    {
                        last_measured = None;
                        cell_length += 1;
                        total_width += 1;
                    }
                    spans[last] = (start, index, cell_length);
                }
                continue;
            }
            let width = self.character_cell_size(character);
            if width != 0 {
                last_measured = Some(character);
                index += 1;
                spans.push((index - 1, index, width));
                total_width += width;
            } else if let Some(last) = spans.len().checked_sub(1) {
                index += 1;
                let (start, _end, cell_length) = spans[last];
                spans[last] = (start, index, cell_length);
            } else {
                index += 1;
                spans.push((index - 1, index, 0));
            }
        }
        (spans, total_width)
    }

    /// Split the string at a cell offset.
    ///
    /// A split landing inside a double-width character replaces that character
    /// with a space on each side, so both halves keep their exact cell count.
    ///
    /// ```
    /// use _native::cells::CellMetrics;
    /// let metrics = CellMetrics::for_version(None);
    /// assert_eq!(metrics.split_text("hello", 2), ("he".to_string(), "llo".to_string()));
    /// // Splitting inside '好' yields a padding space rather than half a glyph.
    /// assert_eq!(metrics.split_text("你好", 3), ("你 ".to_string(), " ".to_string()));
    /// ```
    pub fn split_text(&self, text: &str, cell_position: usize) -> (String, String) {
        if is_single_cell_widths(text) {
            let characters: Vec<char> = text.chars().collect();
            let cut = cell_position.min(characters.len());
            return (
                characters[..cut].iter().collect(),
                characters[cut..].iter().collect(),
            );
        }
        if cell_position == 0 {
            return (String::new(), text.to_string());
        }
        let characters: Vec<char> = text.chars().collect();
        let (spans, cell_length) = self.split_graphemes_of(&characters);
        let take = |range: std::ops::Range<usize>| -> String { characters[range].iter().collect() };

        let mut offset =
            ((cell_position as f64 / cell_length as f64) * spans.len() as f64) as usize;
        let mut left_size: usize = spans[..offset.min(spans.len())]
            .iter()
            .map(|(_, _, width)| width)
            .sum();
        loop {
            if left_size == cell_position {
                if offset >= spans.len() {
                    return (text.to_string(), String::new());
                }
                let split_index = spans[offset].0;
                return (take(0..split_index), take(split_index..characters.len()));
            }
            if left_size < cell_position {
                let (start, end, cell_size) = spans[offset];
                if left_size + cell_size > cell_position {
                    return (
                        take(0..start) + " ",
                        " ".to_string() + &take(end..characters.len()),
                    );
                }
                offset += 1;
                left_size += cell_size;
            } else {
                let (start, end, cell_size) = spans[offset - 1];
                if left_size - cell_size < cell_position {
                    return (
                        take(0..start) + " ",
                        " ".to_string() + &take(end..characters.len()),
                    );
                }
                offset -= 1;
                left_size -= cell_size;
            }
        }
    }

    /// Divide the string into graphemes: each one's character span and cell width,
    /// with the total width alongside.
    ///
    /// Public because a folding wrapper needs the spans rather than only a total —
    /// a break must land *between* graphemes, and a zero-width joiner sequence is one
    /// grapheme however many code points it spans.
    pub fn split_graphemes(&self, text: &str) -> (Vec<(usize, usize, usize)>, usize) {
        let characters: Vec<char> = text.chars().collect();
        self.split_graphemes_of(&characters)
    }

    /// Fold the string into lines that each fit `width` cells, as Rich's `chop_cells`.
    ///
    /// **The fast path slices by code points, not cells** — a fourth counting unit in
    /// this file, alongside `elide_to_width`'s code points, `truncate_middle`'s code
    /// points and Pi's UTF-16 units. It is Rich's, so it is reproduced rather than
    /// unified; it is only correct because the fast path is taken exactly when every
    /// character is one cell wide.
    ///
    /// Reached only by a word longer than the whole width, so ordinary ASCII prose
    /// never exercises the grapheme branch.
    ///
    /// ```
    /// use _native::cells::CellMetrics;
    /// let metrics = CellMetrics::for_version(None);
    /// assert_eq!(metrics.chop_cells("abcdefgh", 3), ["abc", "def", "gh"]);
    /// // A break lands between graphemes, never inside a wide one.
    /// assert_eq!(metrics.chop_cells("你好你好", 3), ["你", "好", "你", "好"]);
    /// ```
    pub fn chop_cells(&self, text: &str, width: usize) -> Vec<String> {
        if is_single_cell_widths(text) {
            return text
                .chars()
                .collect::<Vec<char>>()
                .chunks(width)
                .map(|chunk| chunk.iter().collect())
                .collect();
        }
        let characters: Vec<char> = text.chars().collect();
        let (spans, _) = self.split_graphemes_of(&characters);
        let take = |range: std::ops::Range<usize>| -> String { characters[range].iter().collect() };

        let mut lines: Vec<String> = Vec::new();
        let mut line_size = 0usize;
        let mut line_offset = 0usize;
        for (start, _end, cell_size) in spans {
            if line_size + cell_size > width {
                lines.push(take(line_offset..start));
                line_offset = start;
                line_size = 0;
            }
            line_size += cell_size;
        }
        if line_size > 0 {
            lines.push(take(line_offset..characters.len()));
        }
        lines
    }

    /// Crop or pad the string so it occupies exactly `total` cells.
    ///
    /// ```
    /// use _native::cells::CellMetrics;
    /// let metrics = CellMetrics::for_version(None);
    /// assert_eq!(metrics.set_cell_size("hi", 5), "hi   ");
    /// assert_eq!(metrics.set_cell_size("hello", 3), "hel");
    /// // A double-width character that cannot fit becomes a padding space.
    /// assert_eq!(metrics.set_cell_size("你好", 3), "你 ");
    /// ```
    pub fn set_cell_size(&self, text: &str, total: usize) -> String {
        if is_single_cell_widths(text) {
            let characters: Vec<char> = text.chars().collect();
            if characters.len() < total {
                return text.to_string() + &" ".repeat(total - characters.len());
            }
            return characters[..total].iter().collect();
        }
        if total == 0 {
            return String::new();
        }
        let cell_size = self.cell_len(text);
        if cell_size == total {
            return text.to_string();
        }
        if cell_size < total {
            return text.to_string() + &" ".repeat(total - cell_size);
        }
        self.split_text(text, total).0
    }

    /// Clip to `max_width` cells the way a Rich `Text` with `overflow="ellipsis"`
    /// does: below the limit the string is returned untouched, above it the last
    /// cell becomes an ellipsis.
    ///
    /// ```
    /// use _native::cells::CellMetrics;
    /// let metrics = CellMetrics::for_version(None);
    /// assert_eq!(metrics.truncate_to_cells("hello world", 8), "hello w…");
    /// assert_eq!(metrics.truncate_to_cells("hello", 8), "hello");
    /// // A cut on a character boundary needs no padding.
    /// assert_eq!(metrics.truncate_to_cells("你好你好", 5), "你好…");
    /// // A cut inside a wide character leaves Rich's pad space in its place.
    /// assert_eq!(metrics.truncate_to_cells("你好你好", 6), "你好 …");
    /// ```
    pub fn truncate_to_cells(&self, text: &str, max_width: usize) -> String {
        if self.cell_len(text) <= max_width {
            return text.to_string();
        }
        self.set_cell_size(text, max_width - 1) + "…"
    }
}

/// Rich's fast-path predicate: every character is one cell.
pub fn is_single_cell_widths(text: &str) -> bool {
    text.chars().all(|character| {
        let codepoint = u32::from(character);
        SINGLE_CELL_RANGES
            .iter()
            .any(|(start, end)| (*start..=*end).contains(&codepoint))
    })
}

/// Rich's version selection: exact match, else the newest table older than the
/// requested version, else the newest table of all.
fn table_index(unicode_version: Option<&str>) -> usize {
    let latest = VERSIONS.len() - 1;
    let Some(requested) = unicode_version else {
        return latest;
    };
    if requested == "latest" {
        return latest;
    }
    let Some(requested) = parse_version(requested) else {
        return latest;
    };
    match VERSIONS.iter().position(|version| *version == requested) {
        Some(index) => index,
        None => VERSIONS
            .iter()
            .position(|version| *version > requested)
            .map(|insert_position| insert_position.saturating_sub(1))
            .unwrap_or(latest),
    }
}

/// Parse a dotted version the way Python's `int()` does, padding to three parts.
///
/// Python's `int()` and not a plain digit parse, because it is `int()` that Rich
/// calls: `" 9 "`, `"+9"` and Unicode decimal digits all resolve.
fn parse_version(value: &str) -> Option<(u32, u32, u32)> {
    let mut parts = [0u32; 3];
    for (position, part) in value.split('.').enumerate() {
        let number = python_int(part)?;
        if position < 3 {
            parts[position] = u32::try_from(number).unwrap_or(0);
        }
    }
    Some((parts[0], parts[1], parts[2]))
}

#[cfg(test)]
mod cell_tests {
    use super::*;

    #[test]
    fn the_generated_tables_cover_every_version_rich_ships() {
        assert_eq!(VERSIONS.len(), WIDTH_TABLES.len());
        assert_eq!(VERSIONS.len(), 21);
        assert!(
            VERSIONS.windows(2).all(|pair| pair[0] < pair[1]),
            "The version list must be ascending; the fallback search relies on it."
        );
    }

    /// `UNICODE_VERSION` is a sixth ambient input, alongside the five the mission
    /// already tracks. It changes rendered width, so it changes rendered bytes.
    #[test]
    fn the_unicode_version_changes_measured_width() {
        let old = CellMetrics::for_version(Some("9.0.0"));
        let new = CellMetrics::for_version(Some("17.0.0"));
        let probe = "A\u{07fd}B";
        assert_eq!(old.cell_len(probe), 3);
        assert_eq!(new.cell_len(probe), 2);
        assert_ne!(
            old.truncate_to_cells(&probe.repeat(20), 20),
            new.truncate_to_cells(&probe.repeat(20), 20),
            "If these agree the version seam has stopped being observable."
        );
    }

    #[test]
    fn an_unknown_version_falls_back_to_the_newest_older_table() {
        let exact = CellMetrics::for_version(Some("9.0.0"));
        let between = CellMetrics::for_version(Some("9.5.0"));
        let probe = "A\u{07fd}B";
        assert_eq!(between.cell_len(probe), exact.cell_len(probe));
        let ancient = CellMetrics::for_version(Some("1.0.0"));
        assert_eq!(ancient.cell_len(probe), 3);
    }

    #[test]
    fn a_split_inside_a_wide_character_pads_both_halves() {
        let metrics = CellMetrics::for_version(None);
        let (left, right) = metrics.split_text("你好", 3);
        assert_eq!(metrics.cell_len(&left), 3);
        assert_eq!(left, "你 ");
        assert_eq!(right, " ");
    }

    /// The exact shape the product emits, and the reason views needs this module:
    /// `elide_to_width` leaves 75 cells and Rich clips the result to the console
    /// width, padding because it cannot split a double-width character.
    #[test]
    fn the_product_shape_from_the_double_truncation_finding() {
        let metrics = CellMetrics::for_version(None);
        let after_elide_to_width = format!("▎ {}…", "你好".repeat(18) + "你");
        assert_eq!(metrics.cell_len(&after_elide_to_width), 77);
        let on_screen = metrics.truncate_to_cells(&after_elide_to_width, 40);
        assert_eq!(metrics.cell_len(&on_screen), 40);
        assert!(
            on_screen.ends_with(" …"),
            "Expected Rich's pad space before the ellipsis, got {on_screen:?}"
        );
    }

    /// Rich's own answers over an adversarial corpus, at four unicode versions.
    ///
    /// The corpus is imported from `teammates/views-and-colour/probes/` rather
    /// than copied in, and it is regenerated by `generate_cell_oracle.py`. Unit
    /// tests cannot reach the grapheme walk; only Rich can say what it produces.
    #[test]
    fn every_recorded_rich_measurement_reproduces() {
        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();
        for version in ["latest", "13.0.0", "9.0.0", "4.1.0"] {
            let oracle = load_cell_oracle(version);
            let metrics = CellMetrics::for_version(Some(version));
            for row in oracle["rows"].as_array().expect("the oracle has rows") {
                let text = row["text"].as_str().expect("each row carries its text");
                compared += 1;
                let expected_len = row["cell_len"].as_u64().expect("a recorded cell_len") as usize;
                if metrics.cell_len(text) != expected_len {
                    mismatches.push(format!(
                        "cell_len({text:?}) @ {version}: Rich {expected_len}, got {}",
                        metrics.cell_len(text)
                    ));
                }
                for (width, expected) in row["set_cell_size"]
                    .as_object()
                    .expect("recorded set_cell_size answers")
                {
                    let width: usize = width.parse().expect("a numeric width key");
                    let expected = expected.as_str().expect("a recorded string");
                    compared += 1;
                    let actual = metrics.set_cell_size(text, width);
                    if actual != expected {
                        mismatches.push(format!(
                            "set_cell_size({text:?}, {width}) @ {version}: \
                             Rich {expected:?}, got {actual:?}"
                        ));
                    }
                }
                for (width, expected) in
                    row["chop_cells"].as_object().expect("recorded chop_cells answers")
                {
                    let width: usize = width.parse().expect("a numeric width key");
                    let expected: Vec<&str> = expected
                        .as_array()
                        .expect("a recorded line list")
                        .iter()
                        .map(|line| line.as_str().expect("a line"))
                        .collect();
                    compared += 1;
                    let actual = metrics.chop_cells(text, width);
                    if actual != expected {
                        mismatches.push(format!(
                            "chop_cells({text:?}, {width}) @ {version}: \
                             Rich {expected:?}, got {actual:?}"
                        ));
                    }
                }
                for (width, expected) in
                    row["split_text"].as_object().expect("recorded split_text answers")
                {
                    let width: usize = width.parse().expect("a numeric width key");
                    let expected = expected.as_array().expect("a recorded pair");
                    compared += 1;
                    let (left, right) = metrics.split_text(text, width);
                    let expected_left = expected[0].as_str().expect("a left half");
                    let expected_right = expected[1].as_str().expect("a right half");
                    if left != expected_left || right != expected_right {
                        mismatches.push(format!(
                            "split_text({text:?}, {width}) @ {version}: \
                             Rich ({expected_left:?}, {expected_right:?}), got ({left:?}, {right:?})"
                        ));
                    }
                }
            }
        }
        assert!(
            compared > 10_000,
            "Expected the full recorded corpus, compared only {compared} cases."
        );
        assert!(
            mismatches.is_empty(),
            "{} of {compared} cases differ from Rich:\n{}",
            mismatches.len(),
            mismatches
                .iter()
                .take(10)
                .cloned()
                .collect::<Vec<_>>()
                .join("\n")
        );
    }

    fn load_cell_oracle(version: &str) -> serde_json::Value {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join(format!("cell-oracle-{version}.json"));
        let bytes = std::fs::read(&path)
            .unwrap_or_else(|error| panic!("cell oracle missing at {}: {error}", path.display()));
        serde_json::from_slice(&bytes).expect("the cell oracle is valid JSON")
    }

    /// **The fast path is an optimisation, not a behavioural branch — and that is
    /// provable rather than corpus-dependent.**
    ///
    /// Removing it entirely and always walking graphemes changes nothing on the
    /// 20,056-case corpus. That could mean the corpus is thin, so this checks the
    /// world instead: every codepoint in Rich's fast-path ranges is exactly one cell
    /// in **all 21 shipped tables**, so code-point slicing and cell-based walking
    /// agree by construction.
    ///
    /// If this ever fails, `chop_cells` and `set_cell_size` have acquired a real
    /// second behaviour and every gate over them needs a case that reaches it.
    #[test]
    fn the_fast_path_ranges_are_one_cell_in_every_shipped_table() {
        let mut violations = Vec::new();
        for table in WIDTH_TABLES {
            let metrics = CellMetrics { widths: table };
            for (start, end) in SINGLE_CELL_RANGES {
                for codepoint in start..=end {
                    let Some(character) = char::from_u32(codepoint) else { continue };
                    if metrics.character_cell_size(character) != 1 {
                        violations.push((codepoint, table[0]));
                    }
                }
            }
        }
        assert!(
            violations.is_empty(),
            "{} codepoints in the fast-path ranges are not one cell, so the fast path \
             and the grapheme walk can disagree: {:?}",
            violations.len(),
            &violations[..violations.len().min(6)]
        );
    }

    #[test]
    fn ascii_takes_the_single_cell_fast_path() {
        let metrics = CellMetrics::for_version(None);
        assert!(is_single_cell_widths("╭─ hello ─╮"));
        assert!(!is_single_cell_widths("你好"));
        assert_eq!(metrics.set_cell_size("abc", 6), "abc   ");
        assert_eq!(metrics.set_cell_size("abcdef", 3), "abc");
    }
}
