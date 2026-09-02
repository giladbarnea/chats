//! Turning one message into styled lines.
//!
//! `search_views` draws the panel and owns nothing inside it; this module produces
//! the body it draws around — one `Vec<Segment>` per output line, already wrapped,
//! padded and broken.
//!
//! The product renders message bodies with Rich, so this is a port of Rich's
//! render path rather than a look-alike: `Text` and its wrap, `Markdown` and its
//! elements, `Segment.split_and_crop_lines`. Every rule here was read out of the
//! installed Rich source or measured against it, and the gate is a recorded corpus
//! of Rich's own answers at five widths.
//!
//! **Markdown is parsed by the `markdown-it` crate, not by hand.** It is a port of
//! `markdown-it-py`, which is what Rich parses with, so the parse half is provable
//! rather than statistical. Measured at 19,977 of 20,000 real message text blocks
//! identical to `markdown-it-py`'s token stream — see
//! `teammates/message-renderer/M2-parser-equivalence.md` for the five conversion
//! rules that got it there and the two classes that remain.

use crate::cells::CellMetrics;
use crate::color::{ColorTriplet, StyleColor};
use crate::search_views::{Link, Segment, Style};

/// Rich's `JustifyMethod`. `Default` is not `Left`: it pads nothing.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Justify {
    #[default]
    Default,
    Left,
    Center,
    Right,
    Full,
}

/// Rich's `OverflowMethod`.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Overflow {
    #[default]
    Fold,
    Crop,
    Ellipsis,
    Ignore,
}

/// One styled range over a [`RichText`], in **character** offsets.
///
/// Character rather than byte offsets because Rich's are Python string indices, and
/// every offset this module computes — a wrap point, a span boundary — has to agree
/// with the offsets Rich would compute for the same text.
#[derive(Clone, Debug, Eq, PartialEq)]
struct Span {
    start: usize,
    end: usize,
    style: Style,
    /// Rich keeps a hyperlink inside the `Style`; it lives beside it here because a
    /// `String` there would cost `Style` its `Copy`, which the chrome depends on.
    link: Option<Link>,
}

/// Rich's `Text`: a string plus styled ranges over it.
#[derive(Clone, Debug, Default)]
pub struct RichText {
    characters: Vec<char>,
    spans: Vec<Span>,
    style: Style,
    justify: Option<Justify>,
    overflow: Option<Overflow>,
    no_wrap: Option<bool>,
    /// Rich's `Text.end`, which defaults to a newline. It is what makes two
    /// paragraphs two lines rather than one: every block's `Text` closes its own
    /// line before the markdown walk inserts the blank one between blocks.
    end: &'static str,
}

/// Codepoints Rich removes from any text appended to a `Text`.
///
/// Bell, backspace, vertical tab, form feed and carriage return. They are dropped
/// rather than escaped, so a transcript carrying a stray `\r` renders as if it were
/// not there — and a port that keeps them shifts every offset after one.
const STRIPPED_CONTROL_CODES: [char; 5] = ['\u{7}', '\u{8}', '\u{b}', '\u{c}', '\r'];

impl RichText {
    pub fn new() -> RichText {
        RichText { end: "\n", ..RichText::default() }
    }

    pub fn from_str(text: &str, style: Style) -> RichText {
        let mut rich = RichText::new();
        rich.style = style;
        rich.append(text, None);
        rich
    }

    /// Rich's `Text.append`. A no-op on empty text, which is why an empty token
    /// contributes no span and no escape pair.
    pub fn append(&mut self, text: &str, style: Option<Style>) {
        self.append_linked(text, style, None);
    }

    /// Rich's `Text.append_tokens`, which appends to `_text` **directly** and so
    /// does **not** strip control codes.
    ///
    /// `Syntax.highlight` builds its text this way for every fence — including an
    /// unknown language, because `Syntax.default_lexer` is a plain-text lexer and
    /// `Text.append` is therefore unreachable there. So a form feed inside a fenced
    /// block survives in the product and was being dropped here. Markdown normalises
    /// newlines, so a form feed or a vertical tab is the only way in.
    pub fn append_tokens(&mut self, text: &str, style: Option<Style>) {
        if text.is_empty() {
            return;
        }
        let offset = self.characters.len();
        let length = text.chars().count();
        self.characters.extend(text.chars());
        let carries_style = style.is_some_and(|style| style != Style::inherit());
        if carries_style {
            self.spans.push(Span {
                start: offset,
                end: offset + length,
                style: style.unwrap_or_else(Style::inherit),
                link: None,
            });
        }
    }

    /// The same, carrying a hyperlink over the appended run.
    pub fn append_linked(&mut self, text: &str, style: Option<Style>, link: Option<Link>) {
        if text.is_empty() {
            return;
        }
        let sanitized: Vec<char> = text
            .chars()
            .filter(|character| !STRIPPED_CONTROL_CODES.contains(character))
            .collect();
        if sanitized.is_empty() {
            return;
        }
        let offset = self.characters.len();
        let length = sanitized.len();
        self.characters.extend(sanitized);
        // Rich's `if style:` — and an empty `Style` is **falsy**, so it adds no
        // span at all. That is not a tidiness: a span, even an empty one, cuts the
        // text into separate segments, and a paragraph's padding would arrive as
        // its own run rather than inside the text it pads. A `Style` carrying only
        // a link is **not** empty, which is why the link is part of the test.
        let carries_style = style.is_some_and(|style| style != Style::inherit());
        if carries_style || link.is_some() {
            self.spans.push(Span {
                start: offset,
                end: offset + length,
                style: style.unwrap_or_else(Style::inherit),
                link,
            });
        }
    }

    pub fn plain(&self) -> String {
        self.characters.iter().collect()
    }

    pub fn len(&self) -> usize {
        self.characters.len()
    }

    pub fn is_empty(&self) -> bool {
        self.characters.is_empty()
    }

    fn set_plain(&mut self, characters: Vec<char>) {
        self.characters = characters;
    }

    /// Rich's `Text.render`: walk the span boundaries, combining the stack.
    ///
    /// Two adjacent spans carrying the same style stay two segments, and therefore
    /// two escape pairs. That is Rich's behaviour and it is byte-visible, which is
    /// why the token stream has to merge adjacent text nodes before it gets here.
    pub fn render(&self) -> Vec<Segment> {
        if self.spans.is_empty() {
            // Rich yields the segment even when the text is empty, and an empty
            // segment is not nothing: it occupies a line. An empty `Text` is how a
            // horizontal rule produces the blank line after it.
            return vec![styled_segment(self.plain(), self.style, None)];
        }

        // Identifier 0 is the base style, covering the whole text.
        let mut events: Vec<(usize, bool, usize)> = vec![(0, false, 0)];
        for (index, span) in self.spans.iter().enumerate() {
            events.push((span.start, false, index + 1));
        }
        for (index, span) in self.spans.iter().enumerate() {
            events.push((span.end, true, index + 1));
        }
        events.push((self.characters.len(), true, 0));
        events.sort_by_key(|(offset, leaving, _)| (*offset, *leaving));

        let style_at = |identifier: usize| -> Style {
            if identifier == 0 { self.style } else { self.spans[identifier - 1].style }
        };
        let link_at = |identifier: usize| -> Option<Link> {
            if identifier == 0 { None } else { self.spans[identifier - 1].link.clone() }
        };

        let mut stack: Vec<usize> = Vec::new();
        let mut segments: Vec<Segment> = Vec::new();
        for window in events.windows(2) {
            let (offset, leaving, identifier) = window[0];
            let next_offset = window[1].0;
            if leaving {
                if let Some(position) = stack.iter().position(|item| *item == identifier) {
                    stack.remove(position);
                }
            } else {
                stack.push(identifier);
            }
            if next_offset > offset {
                let mut ordered = stack.clone();
                ordered.sort_unstable();
                let combined = ordered
                    .iter()
                    .fold(Style::inherit(), |accumulated, identifier| {
                        accumulated.over(style_at(*identifier))
                    });
                // `Style.__add__` takes the later link when it has one, so the
                // innermost link wins over an enclosing one.
                let link = ordered
                    .iter()
                    .fold(None, |accumulated, identifier| link_at(*identifier).or(accumulated));
                let text: String = self.characters[offset..next_offset].iter().collect();
                segments.push(styled_segment(text, combined, link));
            }
        }
        segments
    }

    /// Rich's `Text.divide`: cut at character offsets, carrying spans across.
    fn divide(&self, offsets: &[usize]) -> Vec<RichText> {
        if offsets.is_empty() {
            return vec![self.clone()];
        }
        let mut boundaries = vec![0usize];
        boundaries.extend_from_slice(offsets);
        boundaries.push(self.characters.len());
        let ranges: Vec<(usize, usize)> = boundaries
            .windows(2)
            .map(|window| (window[0], window[1]))
            .collect();

        let mut lines: Vec<RichText> = ranges
            .iter()
            .map(|(start, end)| RichText {
                characters: self.characters[*start..*end].to_vec(),
                spans: Vec::new(),
                style: self.style,
                justify: self.justify,
                overflow: self.overflow,
                no_wrap: self.no_wrap,
                end: "",
            })
            .collect();

        for span in &self.spans {
            for (index, (start, end)) in ranges.iter().enumerate() {
                let low = span.start.max(*start);
                let high = span.end.min(*end);
                if low < high {
                    lines[index].spans.push(Span {
                        start: low - start,
                        end: high - start,
                        style: span.style,
                        link: span.link.clone(),
                    });
                }
            }
        }
        lines
    }

    /// Rich's `Text.rstrip_end`: drop trailing whitespace only past `size`.
    fn rstrip_end(&mut self, size: usize) {
        let length = self.characters.len();
        if length <= size {
            return;
        }
        let excess = length - size;
        let trailing = self
            .characters
            .iter()
            .rev()
            .take_while(|character| character.is_whitespace())
            .count();
        if trailing == 0 {
            return;
        }
        let cropped = trailing.min(excess);
        self.characters.truncate(length - cropped);
        self.trim_spans();
    }

    fn trim_spans(&mut self) {
        let maximum = self.characters.len();
        self.spans.retain(|span| span.start < maximum);
        for span in &mut self.spans {
            span.end = span.end.min(maximum);
        }
    }

    /// Rich's `Text.truncate`. Padding is applied to the plain text only, so a pad
    /// carries the base style rather than the last span's.
    fn truncate(&mut self, max_width: usize, overflow: Overflow, pad: bool, metrics: &CellMetrics) {
        if overflow == Overflow::Ignore {
            return;
        }
        let plain = self.plain();
        let length = metrics.cell_len(&plain);
        if length > max_width {
            let shortened = if overflow == Overflow::Ellipsis {
                let mut kept = metrics.set_cell_size(&plain, max_width.saturating_sub(1));
                kept.push('…');
                kept
            } else {
                metrics.set_cell_size(&plain, max_width)
            };
            self.set_plain(shortened.chars().collect());
            self.trim_spans();
        } else if pad && length < max_width {
            let spaces = max_width - length;
            self.characters.extend(std::iter::repeat_n(' ', spaces));
        }
    }

    fn pad_left(&mut self, count: usize) {
        if count == 0 {
            return;
        }
        let mut padded: Vec<char> = std::iter::repeat_n(' ', count).collect();
        padded.extend_from_slice(&self.characters);
        self.characters = padded;
        for span in &mut self.spans {
            span.start += count;
            span.end += count;
        }
    }

    fn pad_right(&mut self, count: usize) {
        self.characters.extend(std::iter::repeat_n(' ', count));
    }

    /// Rich's `Text.stylize` over the whole text.
    fn stylize(&mut self, style: Style) {
        if self.characters.is_empty() || style == Style::inherit() {
            return;
        }
        self.spans.push(Span {
            start: 0,
            end: self.characters.len(),
            style,
            link: None,
        });
    }

    /// Rich's `Text.stylize` over the whole text, carrying only a hyperlink.
    fn stylize_link(&mut self, link: Link) {
        if self.characters.is_empty() {
            return;
        }
        self.spans.push(Span {
            start: 0,
            end: self.characters.len(),
            style: Style::inherit(),
            link: Some(link),
        });
    }

    fn rstrip(&mut self) {
        while self.characters.last().is_some_and(|c| c.is_whitespace()) {
            self.characters.pop();
        }
        self.trim_spans();
    }

    /// Rich's `Text.expand_tabs`, which advances to the next multiple of `tab_size`
    /// **in cells**, not in characters.
    fn expand_tabs(&mut self, tab_size: usize, metrics: &CellMetrics) {
        if !self.characters.contains(&'\t') {
            return;
        }
        let mut expanded: Vec<char> = Vec::with_capacity(self.characters.len());
        let mut moves: Vec<(usize, usize)> = Vec::new();
        let mut cell_position = 0usize;
        for (index, character) in self.characters.iter().enumerate() {
            moves.push((index, expanded.len()));
            if *character == '\t' {
                expanded.push(' ');
                cell_position += 1;
                let remainder = cell_position % tab_size;
                if remainder != 0 {
                    let spaces = tab_size - remainder;
                    expanded.extend(std::iter::repeat_n(' ', spaces));
                    cell_position += spaces;
                }
            } else {
                expanded.push(*character);
                cell_position += metrics.character_cell_size(*character);
            }
        }
        let final_offset = expanded.len();
        let translate = |offset: usize| -> usize {
            moves
                .iter()
                .find(|(source, _)| *source == offset)
                .map(|(_, target)| *target)
                .unwrap_or(final_offset)
        };
        for span in &mut self.spans {
            span.start = translate(span.start);
            span.end = translate(span.end);
        }
        self.characters = expanded;
    }

    /// Rich's `Text.split("\n", allow_blank=…)`.
    ///
    /// Divides at **both sides** of every separator and drops the pieces that are
    /// the separator, rather than trimming a newline off each line — the two agree
    /// on plain text and can disagree on where a span lands. `allow_blank` decides
    /// only whether a trailing empty line survives, and it is `false` everywhere
    /// except the wrap path.
    fn split(&self, allow_blank: bool) -> Vec<RichText> {
        let mut offsets: Vec<usize> = Vec::new();
        for (index, character) in self.characters.iter().enumerate() {
            if *character == '\n' {
                offsets.push(index);
                offsets.push(index + 1);
            }
        }
        let mut lines: Vec<RichText> = self
            .divide(&offsets)
            .into_iter()
            .filter(|line| line.characters != ['\n'])
            .collect();
        if !allow_blank && self.characters.last() == Some(&'\n') {
            lines.pop();
        }
        lines
    }

    /// Rich's `Text.wrap`.
    pub fn wrap(
        &self,
        width: usize,
        justify: Justify,
        overflow: Overflow,
        tab_size: usize,
        no_wrap: bool,
        metrics: &CellMetrics,
    ) -> Vec<RichText> {
        // Both arrive already resolved from `to_segments`, which is Python's
        // `justify or self.justify or DEFAULT` with a non-empty left operand.
        let wrap_justify = justify;
        let wrap_overflow = overflow;
        let no_wrap = self.no_wrap.unwrap_or(no_wrap) || overflow == Overflow::Ignore;

        let mut out: Vec<RichText> = Vec::new();
        for line in self.split(true) {
            let mut line = line;
            if line.characters.contains(&'\t') {
                line.expand_tabs(tab_size, metrics);
            }
            let mut new_lines: Vec<RichText> = if no_wrap {
                if overflow == Overflow::Ignore {
                    out.push(line);
                    continue;
                }
                vec![line]
            } else {
                let offsets = divide_line(
                    &line.plain(),
                    width,
                    wrap_overflow == Overflow::Fold,
                    metrics,
                );
                let mut divided = line.divide(&offsets);
                for piece in &mut divided {
                    piece.rstrip_end(width);
                }
                divided
            };
            justify_lines(&mut new_lines, width, wrap_justify, wrap_overflow, metrics);
            for piece in &mut new_lines {
                piece.truncate(width, wrap_overflow, false, metrics);
            }
            out.extend(new_lines);
        }
        out
    }

    /// Rich's `Text.__rich_console__`: wrap, join with newlines, render.
    fn to_segments(&self, width: usize, options: &RenderOptions) -> Vec<Segment> {
        // `justify = self.justify or options.justify or DEFAULT_JUSTIFY` — the
        // text's **own** setting wins, because `"default"` is a truthy string in
        // Python. Markdown never sets `options.justify`, so the two orders agree
        // there and only a table tells them apart: a column is rendered with
        // `justify="left"` while each cell carries its own alignment.
        let justify = self.justify.unwrap_or(options.justify);
        let overflow = self.overflow.unwrap_or(options.overflow);
        let lines = self.wrap(
            width,
            justify,
            overflow,
            options.tab_size,
            options.no_wrap,
            options.metrics,
        );
        let mut joined = RichText::new();
        joined.style = self.style;
        for (index, line) in lines.iter().enumerate() {
            if index > 0 {
                joined.append("\n", None);
            }
            joined.append_text(line);
        }
        let mut segments = joined.render();
        if !self.end.is_empty() {
            segments.push(Segment { text: self.end.to_string(), style: None, link: None });
        }
        segments
    }

    /// Rich's `Text.append_text`: concatenate, shifting the other's spans.
    fn append_text(&mut self, other: &RichText) {
        let offset = self.characters.len();
        self.characters.extend_from_slice(&other.characters);
        for span in &other.spans {
            self.spans.push(Span {
                start: span.start + offset,
                end: span.end + offset,
                style: span.style,
                link: span.link.clone(),
            });
        }
    }
}

/// Rich's `Lines.justify`.
fn justify_lines(
    lines: &mut [RichText],
    width: usize,
    justify: Justify,
    overflow: Overflow,
    metrics: &CellMetrics,
) {
    match justify {
        Justify::Left => {
            for line in lines.iter_mut() {
                line.truncate(width, overflow, true, metrics);
            }
        }
        Justify::Center => {
            for line in lines.iter_mut() {
                line.rstrip();
                line.truncate(width, overflow, false, metrics);
                let used = metrics.cell_len(&line.plain());
                line.pad_left(width.saturating_sub(used) / 2);
                let used = metrics.cell_len(&line.plain());
                line.pad_right(width.saturating_sub(used));
            }
        }
        Justify::Right => {
            for line in lines.iter_mut() {
                line.rstrip();
                line.truncate(width, overflow, false, metrics);
                let used = metrics.cell_len(&line.plain());
                line.pad_left(width.saturating_sub(used));
            }
        }
        // `Full` is unreachable from markdown, which sets only left and center.
        Justify::Full | Justify::Default => {}
    }
}

/// Rich's `_wrap.words`: each word plus the whitespace to its right.
fn words(text: &[char]) -> Vec<(usize, usize, String)> {
    let mut found: Vec<(usize, usize, String)> = Vec::new();
    let mut index = 0usize;
    while index < text.len() {
        let start = index;
        while index < text.len() && text[index].is_whitespace() {
            index += 1;
        }
        if index == text.len() {
            // Trailing whitespace with no word after it is not a match for
            // `\s*\S+\s*`, so Rich yields nothing here.
            break;
        }
        while index < text.len() && !text[index].is_whitespace() {
            index += 1;
        }
        while index < text.len() && text[index].is_whitespace() {
            index += 1;
        }
        found.push((start, index, text[start..index].iter().collect()));
    }
    found
}

/// Rich's `_wrap.divide_line`: the character offsets a line breaks at.
fn divide_line(text: &str, width: usize, fold: bool, metrics: &CellMetrics) -> Vec<usize> {
    let characters: Vec<char> = text.chars().collect();
    let mut breaks: Vec<usize> = Vec::new();
    let mut cell_offset = 0usize;
    for (start, _end, word) in words(&characters) {
        let mut start = start;
        let trimmed: String = word.trim_end().to_string();
        let word_length = metrics.cell_len(&trimmed);
        // **Signed, because Rich's is.** `remaining_space = width - cell_offset` can
        // go negative, and a negative fails `>= word_length` where a floor at zero
        // succeeds for a zero-cell word. `words()` yields `\s*\S+\s*`, so every word
        // has a non-space run — but a run of only zero-width characters measures
        // zero cells, so an overlong unfoldable word followed by one of those breaks
        // differently on the two routes. `saturating_sub` is the idiomatic
        // translation of a Python `-` and is only correct where the negative case
        // cannot arise; here it can.
        let remaining = width as isize - cell_offset as isize;
        if remaining >= word_length as isize {
            cell_offset += metrics.cell_len(&word);
            continue;
        }
        if word_length > width {
            if fold {
                let folded = metrics.chop_cells(&word, width);
                let count = folded.len();
                for (index, piece) in folded.iter().enumerate() {
                    if start > 0 {
                        breaks.push(start);
                    }
                    if index + 1 == count {
                        cell_offset = metrics.cell_len(piece);
                    } else {
                        start += piece.chars().count();
                    }
                }
            } else {
                if start > 0 {
                    breaks.push(start);
                }
                cell_offset = metrics.cell_len(&word);
            }
        } else if cell_offset > 0 && start > 0 {
            breaks.push(start);
            cell_offset = metrics.cell_len(&word);
        }
    }
    breaks
}

fn styled_segment(text: String, style: Style, link: Option<Link>) -> Segment {
    let style = (style != Style::inherit()).then_some(style);
    Segment { text, style, link }
}

/// The console state a renderable is rendered under.
pub struct RenderOptions<'a> {
    pub justify: Justify,
    pub overflow: Overflow,
    pub no_wrap: bool,
    pub tab_size: usize,
    pub metrics: &'a CellMetrics,
}

impl<'a> RenderOptions<'a> {
    pub fn new(metrics: &'a CellMetrics) -> RenderOptions<'a> {
        RenderOptions {
            justify: Justify::Default,
            overflow: Overflow::Fold,
            no_wrap: false,
            tab_size: 8,
            metrics,
        }
    }
}

/// Rich's `Segment.adjust_line_length`.
pub fn adjust_line_length(
    line: &[Segment],
    length: usize,
    style: Option<Style>,
    pad: bool,
    metrics: &CellMetrics,
) -> Vec<Segment> {
    let line_length: usize = line.iter().map(|segment| metrics.cell_len(&segment.text)).sum();
    if line_length < length {
        let mut adjusted = line.to_vec();
        if pad {
            adjusted.push(Segment {
                text: " ".repeat(length - line_length),
                style, link: None });
        }
        return adjusted;
    }
    if line_length == length {
        return line.to_vec();
    }
    let mut adjusted: Vec<Segment> = Vec::new();
    let mut used = 0usize;
    for segment in line {
        let segment_length = metrics.cell_len(&segment.text);
        if used + segment_length < length {
            adjusted.push(segment.clone());
            used += segment_length;
            continue;
        }
        adjusted.push(Segment {
            text: metrics.set_cell_size(&segment.text, length - used),
            style: segment.style, link: None });
        break;
    }
    adjusted
}

/// Rich's `Segment.split_and_crop_lines`, without the trailing newline segments.
pub fn split_and_crop_lines(
    segments: &[Segment],
    length: usize,
    style: Option<Style>,
    pad: bool,
    metrics: &CellMetrics,
) -> Vec<Vec<Segment>> {
    let mut lines: Vec<Vec<Segment>> = Vec::new();
    let mut line: Vec<Segment> = Vec::new();
    for segment in segments {
        if !segment.text.contains('\n') {
            line.push(segment.clone());
            continue;
        }
        let mut remainder = segment.text.as_str();
        while !remainder.is_empty() {
            match remainder.split_once('\n') {
                Some((head, tail)) => {
                    if !head.is_empty() {
                        line.push(Segment { text: head.to_string(), style: segment.style, link: None });
                    }
                    lines.push(adjust_line_length(&line, length, style, pad, metrics));
                    line.clear();
                    remainder = tail;
                }
                None => {
                    line.push(Segment { text: remainder.to_string(), style: segment.style, link: None });
                    remainder = "";
                }
            }
        }
    }
    if !line.is_empty() {
        lines.push(adjust_line_length(&line, length, style, pad, metrics));
    }
    lines
}

/// A colour Rich names by palette index rather than by triple.
///
/// Tier-invariant in both directions — `magenta` emits `35` at truecolor, at 256
/// colours and at 16 — measured against live Rich rather than read off a table.
const fn palette(number: u8) -> Option<StyleColor> {
    Some(StyleColor::Palette(number))
}

const fn triplet(hex: &str) -> Option<StyleColor> {
    Some(StyleColor::Triplet(ColorTriplet::from_hex(hex)))
}

const fn markdown_style(
    bold: Option<bool>,
    italic: Option<bool>,
    underline: Option<bool>,
    dim: Option<bool>,
    strike: Option<bool>,
    foreground: Option<StyleColor>,
    background: Option<StyleColor>,
) -> Style {
    Style {
        bold,
        dim,
        italic,
        underline,
        reverse: None,
        strike,
        foreground,
        background,
    }
}

/// Rich's markdown styles as this product's console resolves them.
///
/// Rich's defaults with `theme.APP_THEME` layered over them — `markdown.code` and
/// `dim` are the two the product overrides. Recorded as resolved values rather than
/// as names because the resolution happens once, in Python, at console construction.
pub mod markdown_styles {
    use super::*;

    pub const NONE: Style = Style::inherit();
    pub const EM: Style = markdown_style(None, Some(true), None, None, None, None, None);
    pub const STRONG: Style = markdown_style(Some(true), None, None, None, None, None, None);
    pub const STRIKE: Style = markdown_style(None, None, None, None, Some(true), None, None);
    pub const CODE: Style =
        markdown_style(None, None, None, None, None, triplet("#ee7f4b"), triplet("#3c3c3c"));
    pub const CODE_BLOCK: Style =
        markdown_style(None, None, None, None, None, palette(6), palette(0));
    pub const BLOCK_QUOTE: Style =
        markdown_style(None, None, None, None, None, palette(5), None);
    pub const ITEM_BULLET: Style = markdown_style(Some(true), None, None, None, None, None, None);
    pub const ITEM_NUMBER: Style =
        markdown_style(None, None, None, None, None, palette(6), None);
    pub const HR: Style = markdown_style(None, None, None, Some(true), None, None, None);
    pub const H1: Style =
        markdown_style(Some(true), None, Some(true), None, None, None, None);
    pub const H2: Style =
        markdown_style(None, None, Some(true), None, None, palette(5), None);
    pub const H3: Style = markdown_style(Some(true), None, None, None, None, palette(5), None);
    pub const H4: Style = markdown_style(None, Some(true), None, None, None, palette(5), None);
    pub const H5: Style = markdown_style(None, Some(true), None, None, None, None, None);
    pub const H6: Style = markdown_style(None, None, None, Some(true), None, None, None);
    pub const LINK_URL: Style =
        markdown_style(None, None, Some(true), None, None, palette(4), None);
    /// `bold: Some(false)` **clears** the attribute rather than leaving it alone.
    /// That is the whole reason a style attribute is three-valued.
    pub const TABLE_HEADER: Style =
        markdown_style(Some(false), None, None, None, None, palette(6), None);
    pub const TABLE_BORDER: Style =
        markdown_style(None, None, None, None, None, palette(6), None);

    pub fn heading(tag: &str) -> Style {
        match tag {
            "h1" => H1,
            "h2" => H2,
            "h3" => H3,
            "h4" => H4,
            "h5" => H5,
            _ => H6,
        }
    }
}

// ---------------------------------------------------------------------------
// Markdown
// ---------------------------------------------------------------------------

/// One entry of the flattened token stream `rich.markdown` walks.
///
/// Produced from the `markdown-it` AST rather than from a hand-written parser, and
/// shaped to match `markdown-it-py`'s stream after `_flatten_tokens` — which drops
/// the `inline` wrapper and yields its children, except for `image` and `fence`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Token {
    ParagraphOpen,
    ParagraphClose,
    HeadingOpen(&'static str),
    HeadingClose,
    BlockquoteOpen,
    BlockquoteClose,
    BulletListOpen,
    OrderedListOpen(u32),
    ListClose,
    ListItemOpen,
    ListItemClose,
    TableOpen,
    TableClose,
    TheadOpen,
    TheadClose,
    TbodyOpen,
    TbodyClose,
    RowOpen,
    RowClose,
    CellOpen { header: bool, justify: Justify },
    CellClose,
    Fence { content: String, info: String },
    IndentedCode { content: String },
    HorizontalRule,
    HtmlBlock,
    /// An empty paragraph, heading or table cell still carries this, and it is not
    /// inert: it renders nothing but sets the block separator.
    EmptyInline,
    Text(String),
    Softbreak,
    Hardbreak,
    EmphasisOpen,
    EmphasisClose,
    StrongOpen,
    StrongClose,
    StrikeOpen,
    StrikeClose,
    CodeInline(String),
    HtmlInline(String),
    LinkOpen(String),
    LinkClose,
    Image { alt: String, source: String },
}

mod parse {
    use super::{Justify, Token};
    use markdown_it::MarkdownIt;
    use markdown_it::parser::inline::{Text, TextSpecial};
    use markdown_it::plugins::cmark::block::blockquote::Blockquote;
    use markdown_it::plugins::cmark::block::code::CodeBlock;
    use markdown_it::plugins::cmark::block::fence::CodeFence;
    use markdown_it::plugins::cmark::block::heading::ATXHeading;
    use markdown_it::plugins::cmark::block::hr::ThematicBreak;
    use markdown_it::plugins::cmark::block::lheading::SetextHeader;
    use markdown_it::plugins::cmark::block::list::{BulletList, ListItem, OrderedList};
    use markdown_it::plugins::cmark::block::paragraph::Paragraph;
    use markdown_it::plugins::cmark::inline::autolink::Autolink;
    use markdown_it::plugins::cmark::inline::backticks::CodeInline;
    use markdown_it::plugins::cmark::inline::emphasis::{Em, Strong};
    use markdown_it::plugins::cmark::inline::image::Image;
    use markdown_it::plugins::cmark::inline::link::Link;
    use markdown_it::plugins::cmark::inline::newline::{Hardbreak, Softbreak};
    use markdown_it::plugins::extra::strikethrough::Strikethrough;
    use markdown_it::plugins::extra::tables::{
        ColumnAlignment, Table, TableBody, TableHead, TableRow,
    };
    use markdown_it::plugins::html::html_block::HtmlBlock;
    use markdown_it::plugins::html::html_inline::HtmlInline;
    use markdown_it::Node;

    /// The parser Rich uses: CommonMark plus strikethrough and tables, and nothing
    /// else. The crate's `plugins::extra::add` would additionally enable linkify,
    /// typographer and smartquotes, none of which `markdown-it-py`'s commonmark
    /// preset carries.
    fn parser() -> MarkdownIt {
        let mut markdown = MarkdownIt::new();
        markdown_it::plugins::cmark::add(&mut markdown);
        markdown_it::plugins::html::add(&mut markdown);
        markdown_it::plugins::extra::strikethrough::add(&mut markdown);
        markdown_it::plugins::extra::tables::add(&mut markdown);
        markdown
    }

    fn is_block(node: &Node) -> bool {
        node.is::<Paragraph>()
            || node.is::<ATXHeading>()
            || node.is::<SetextHeader>()
            || node.is::<Blockquote>()
            || node.is::<BulletList>()
            || node.is::<OrderedList>()
            || node.is::<CodeBlock>()
            || node.is::<CodeFence>()
            || node.is::<ThematicBreak>()
            || node.is::<HtmlBlock>()
            || node.is::<Table>()
    }

    fn collect_text(node: &Node) -> String {
        fn walk(node: &Node, out: &mut String) {
            if let Some(text) = node.cast::<Text>() {
                out.push_str(&text.content);
            }
            if let Some(special) = node.cast::<TextSpecial>() {
                out.push_str(&special.content);
            }
            for child in node.children.iter() {
                walk(child, out);
            }
        }
        let mut out = String::new();
        for child in node.children.iter() {
            walk(child, &mut out);
        }
        out
    }

    fn heading_tag(level: u8) -> &'static str {
        match level {
            1 => "h1",
            2 => "h2",
            3 => "h3",
            4 => "h4",
            5 => "h5",
            _ => "h6",
        }
    }

    /// A paragraph, heading or table cell always carries an `inline` token in
    /// `markdown-it-py`, and an empty one survives flattening because it has no
    /// children to yield instead. A blockquote or a list carries none, and an empty
    /// list item carries nothing at all.
    fn emit_inline_children(node: &Node, header: bool, out: &mut Vec<Token>) {
        if node.children.is_empty() {
            out.push(Token::EmptyInline);
            return;
        }
        for child in node.children.iter() {
            emit(child, header, &[], out);
        }
    }

    fn emit_cell(node: &Node, header: bool, alignment: ColumnAlignment, out: &mut Vec<Token>) {
        let justify = match alignment {
            ColumnAlignment::None => Justify::Default,
            ColumnAlignment::Left => Justify::Left,
            ColumnAlignment::Right => Justify::Right,
            ColumnAlignment::Center => Justify::Center,
        };
        out.push(Token::CellOpen { header, justify });
        emit_inline_children(node, header, out);
        out.push(Token::CellClose);
    }

    fn emit(node: &Node, header: bool, alignments: &[ColumnAlignment], out: &mut Vec<Token>) {
        let children = |out: &mut Vec<Token>| {
            for child in node.children.iter() {
                emit(child, header, alignments, out);
            }
        };

        if let Some(table) = node.cast::<Table>() {
            out.push(Token::TableOpen);
            for child in node.children.iter() {
                emit(child, header, &table.alignments, out);
            }
            out.push(Token::TableClose);
        } else if node.is::<TableHead>() {
            out.push(Token::TheadOpen);
            for child in node.children.iter() {
                emit(child, true, alignments, out);
            }
            out.push(Token::TheadClose);
        } else if node.is::<TableBody>() {
            out.push(Token::TbodyOpen);
            for child in node.children.iter() {
                emit(child, false, alignments, out);
            }
            out.push(Token::TbodyClose);
        } else if node.is::<TableRow>() {
            out.push(Token::RowOpen);
            for (column, child) in node.children.iter().enumerate() {
                let alignment = alignments
                    .get(column)
                    .copied()
                    .unwrap_or(ColumnAlignment::None);
                emit_cell(child, header, alignment, out);
            }
            out.push(Token::RowClose);
        } else if node.is::<Paragraph>() {
            out.push(Token::ParagraphOpen);
            emit_inline_children(node, header, out);
            out.push(Token::ParagraphClose);
        } else if let Some(heading) = node.cast::<ATXHeading>() {
            out.push(Token::HeadingOpen(heading_tag(heading.level)));
            emit_inline_children(node, header, out);
            out.push(Token::HeadingClose);
        } else if let Some(heading) = node.cast::<SetextHeader>() {
            out.push(Token::HeadingOpen(heading_tag(heading.level)));
            emit_inline_children(node, header, out);
            out.push(Token::HeadingClose);
        } else if node.is::<Blockquote>() {
            out.push(Token::BlockquoteOpen);
            children(out);
            out.push(Token::BlockquoteClose);
        } else if node.is::<BulletList>() {
            out.push(Token::BulletListOpen);
            children(out);
            out.push(Token::ListClose);
        } else if let Some(list) = node.cast::<OrderedList>() {
            out.push(Token::OrderedListOpen(list.start));
            children(out);
            out.push(Token::ListClose);
        } else if node.is::<ListItem>() {
            // A tight list drops the paragraph node in this crate and keeps it —
            // hidden — in `markdown-it-py`. `rich.markdown` never reads `hidden`, so
            // it builds a `Paragraph` either way, and text arriving in a `ListItem`
            // outside one is text `render_bullet` never renders.
            //
            // Each *run* of inline children gets its own paragraph, not the whole
            // child list: an item holding text followed by a nested list must not
            // put the list inside the paragraph.
            out.push(Token::ListItemOpen);
            let mut index = 0usize;
            while index < node.children.len() {
                if is_block(&node.children[index]) {
                    emit(&node.children[index], header, alignments, out);
                    index += 1;
                    continue;
                }
                out.push(Token::ParagraphOpen);
                while index < node.children.len() && !is_block(&node.children[index]) {
                    emit(&node.children[index], header, alignments, out);
                    index += 1;
                }
                out.push(Token::ParagraphClose);
            }
            out.push(Token::ListItemClose);
        } else if let Some(fence) = node.cast::<CodeFence>() {
            out.push(Token::Fence {
                content: fence.content.clone(),
                info: fence.info.clone(),
            });
        } else if let Some(code) = node.cast::<CodeBlock>() {
            out.push(Token::IndentedCode { content: code.content.clone() });
        } else if node.is::<ThematicBreak>() {
            out.push(Token::HorizontalRule);
        } else if node.is::<HtmlBlock>() {
            out.push(Token::HtmlBlock);
        } else if let Some(html) = node.cast::<HtmlInline>() {
            out.push(Token::HtmlInline(html.content.clone()));
        } else if let Some(special) = node.cast::<TextSpecial>() {
            // `markdown-it-py` renames `text_special` to `text` in `text_join` so it
            // can merge with its neighbours. It has to arrive as text or the merge
            // cannot happen, and the merge is byte-visible inside a styled run.
            out.push(Token::Text(special.content.clone()));
        } else if let Some(text) = node.cast::<Text>() {
            out.push(Token::Text(text.content.clone()));
        } else if node.is::<Softbreak>() {
            out.push(Token::Softbreak);
        } else if node.is::<Hardbreak>() {
            out.push(Token::Hardbreak);
        } else if node.is::<Em>() {
            out.push(Token::EmphasisOpen);
            children(out);
            out.push(Token::EmphasisClose);
        } else if node.is::<Strong>() {
            out.push(Token::StrongOpen);
            children(out);
            out.push(Token::StrongClose);
        } else if node.is::<Strikethrough>() {
            out.push(Token::StrikeOpen);
            children(out);
            out.push(Token::StrikeClose);
        } else if node.is::<CodeInline>() {
            out.push(Token::CodeInline(collect_text(node)));
        } else if let Some(link) = node.cast::<Link>() {
            out.push(Token::LinkOpen(link.url.clone()));
            children(out);
            out.push(Token::LinkClose);
        } else if let Some(link) = node.cast::<Autolink>() {
            out.push(Token::LinkOpen(link.url.clone()));
            children(out);
            out.push(Token::LinkClose);
        } else if let Some(image) = node.cast::<Image>() {
            out.push(Token::Image {
                alt: collect_text(node),
                source: image.url.clone(),
            });
        } else {
            // Nothing else can reach here: the crate's node set is fixed by which
            // plugins are enabled above. Falling through silently would make a new
            // node kind render as absence, which is the failure mode hardest to see.
            panic!("unmapped markdown node {}", node.name());
        }
    }

    /// `markdown-it-py`'s `fragments_join` and `text_join`, which the crate lacks.
    ///
    /// Two same-styled appends emit two escape pairs where one emits one, so this is
    /// a rendered-byte rule rather than token bookkeeping. An empty text token is
    /// dropped because `Text.append` returns early on empty text.
    fn join_text(tokens: Vec<Token>) -> Vec<Token> {
        let mut joined: Vec<Token> = Vec::with_capacity(tokens.len());
        for token in tokens {
            if let Token::Text(text) = &token {
                if let Some(Token::Text(previous)) = joined.last_mut() {
                    previous.push_str(text);
                    continue;
                }
            }
            joined.push(token);
        }
        joined.retain(|token| !matches!(token, Token::Text(text) if text.is_empty()));
        joined
    }

    /// The product's `PaddedInlineCodeMarkdown`, which pads inline code with one
    /// space each side **before** rendering. A port that reimplements Markdown
    /// instead of the subclass loses it silently.
    fn pad_inline_code(tokens: &mut [Token]) {
        for token in tokens.iter_mut() {
            if let Token::CodeInline(content) = token
                && !content.is_empty()
            {
                *content = format!(" {content} ");
            }
        }
    }

    pub fn tokens(markup: &str) -> Vec<Token> {
        let markdown = parser();
        let root = markdown.parse(markup);
        let mut out: Vec<Token> = Vec::new();
        for child in root.children.iter() {
            emit(child, false, &[], &mut out);
        }
        let mut out = join_text(out);
        pad_inline_code(&mut out);
        out
    }
}

pub use parse::tokens as markdown_tokens;

/// One node of Rich's markdown element tree, holding what it needs to render.
#[derive(Clone, Debug)]
enum Element {
    Paragraph { text: RichText },
    Heading { tag: &'static str, text: RichText },
    BlockQuote { style: Style, children: Vec<Element> },
    HorizontalRule,
    List { ordered: bool, start: u32, items: Vec<Element> },
    ListItem { style: Style, children: Vec<Element> },
    Table { header: Vec<RichText>, body: Vec<Vec<RichText>> },
    /// A `thead` or `tbody`, which collects rows and hands them to the table.
    TableSection { header: bool, rows: Vec<Vec<RichText>> },
    TableRow { cells: Vec<RichText> },
    TableCell { text: RichText },
    /// A fenced or indented code block. `lexer` is the display name of a promoted
    /// family, or `None` when the block's language reaches no real lexer and every
    /// character carries Monokai's default foreground.
    CodeBlock { text: RichText, lexer: Option<&'static str> },
    /// An image placeholder: a framed-picture glyph, the alt text, and a space.
    Image { destination: String, link: Option<Link>, text: RichText },
    /// `UnknownElement`: renders nothing, but still moves the block separator.
    Unknown,
}

impl Element {
    /// `MarkdownElement.new_line`, which decides whether a blank line precedes the
    /// next block.
    fn new_line(&self) -> bool {
        !matches!(self, Element::HorizontalRule | Element::Image { .. })
    }

    fn render(&self, width: usize, options: &RenderOptions) -> Vec<Segment> {
        match self {
            Element::Paragraph { text } => {
                let mut text = text.clone();
                text.justify = Some(Justify::Left);
                text.to_segments(width, options)
            }
            Element::Heading { tag, text } => {
                let mut text = text.clone();
                text.justify = Some(if *tag == "h1" { Justify::Center } else { Justify::Left });
                text.to_segments(width, options)
            }
            Element::HorizontalRule => {
                // `Rule` with no title: the character repeated past the width, then
                // truncated and cell-sized back to it. It is followed by an empty
                // `Text`, whose output is one empty segment and a newline — and the
                // empty segment is not nothing, it is the blank line after the rule.
                let mut rule = RichText::new();
                rule.style = markdown_styles::HR;
                rule.append(&"-".repeat(width + 1), None);
                rule.truncate(width, Overflow::Fold, false, options.metrics);
                let sized = options.metrics.set_cell_size(&rule.plain(), width);
                let mut rule_text = RichText::new();
                rule_text.style = markdown_styles::HR;
                rule_text.append(&sized, None);
                let mut segments = rule_text.to_segments(width, options);
                segments.extend(RichText::new().to_segments(width, options));
                segments
            }
            Element::BlockQuote { style, children } => {
                // The prefix is two cells and the width drops by four. Both are
                // Rich's, and they do not have to agree.
                let inner = width.saturating_sub(4);
                let lines = render_lines(children, inner, Some(*style), true, options);
                let mut segments: Vec<Segment> = Vec::new();
                for line in lines {
                    segments.push(Segment { text: "▌ ".to_string(), style: Some(*style), link: None });
                    segments.extend(line);
                    segments.push(Segment { text: "\n".to_string(), style: None, link: None });
                }
                segments
            }
            Element::List { ordered, start, items } => {
                let mut segments: Vec<Segment> = Vec::new();
                if !*ordered {
                    for item in items {
                        segments.extend(item.render_bullet(width, options));
                    }
                    return segments;
                }
                // `last_number` counts one past the final item, so a list of two
                // starting at 1 reserves the width of `3`.
                let last_number = *start as usize + items.len();
                for (index, item) in items.iter().enumerate() {
                    segments.extend(item.render_number(
                        width,
                        *start as usize + index,
                        last_number,
                        options,
                    ));
                }
                segments
            }
            Element::ListItem { .. } => {
                unreachable!("a list item renders through its list's bullet or number")
            }
            Element::Image { destination, link, text } => {
                // `Style(link=self.link or self.destination or None)` — an empty
                // destination and no enclosing link leaves the title unlinked.
                let url = match link {
                    Some(link) => Some(link.url.clone()),
                    None => (!destination.is_empty()).then(|| destination.clone()),
                };
                let mut title = if text.is_empty() {
                    // `self.destination.strip("/").rsplit("/", 1)[-1]`.
                    let trimmed = destination.trim_matches('/');
                    let tail = trimmed.rsplit_once('/').map_or(trimmed, |(_, tail)| tail);
                    RichText::from_str(tail, Style::inherit())
                } else {
                    text.clone()
                };
                if let Some(url) = url {
                    let id = link.as_ref().map_or(0, |link| link.id);
                    title.stylize_link(Link { url, id });
                }
                let mut assembled = RichText::new();
                assembled.end = "";
                assembled.append("🌆 ", None);
                assembled.append_text(&title);
                assembled.append(" ", None);
                assembled.to_segments(width, options)
            }
            Element::CodeBlock { text, lexer } => {
                // `str(self.text).rstrip()` — Python's `rstrip` strips every
                // character its `isspace` accepts, which includes U+001C–U+001F
                // where Rust's `is_whitespace` does not. Same family as the C0 gap
                // the desk already carries for `\s`.
                let plain = text.plain();
                let code = plain.trim_end_matches(|character: char| {
                    character.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&character)
                });
                render_code_block(code, *lexer, width, options)
            }
            Element::Table { header, body } => render_table(
                header,
                body,
                width,
                markdown_styles::TABLE_BORDER,
                options,
            ),
            Element::TableSection { .. } | Element::TableRow { .. } | Element::TableCell { .. } => {
                unreachable!("a table's parts render through the table itself")
            }
            Element::Unknown => Vec::new(),
        }
    }

    fn item_parts(&self) -> (Style, &[Element]) {
        match self {
            Element::ListItem { style, children } => (*style, children.as_slice()),
            _ => unreachable!("a list holds only list items"),
        }
    }

    fn render_bullet(
        &self,
        width: usize,
        options: &RenderOptions,
    ) -> Vec<Segment> {
        let (style, children) = self.item_parts();
        let lines = render_lines(children, width.saturating_sub(3), Some(style), true, options);
        let bullet_style = Some(markdown_styles::ITEM_BULLET);
        let mut segments: Vec<Segment> = Vec::new();
        for (index, line) in lines.into_iter().enumerate() {
            segments.push(Segment {
                text: if index == 0 { " • ".to_string() } else { "   ".to_string() },
                style: bullet_style, link: None });
            segments.extend(line);
            segments.push(Segment { text: "\n".to_string(), style: None, link: None });
        }
        segments
    }

    fn render_number(
        &self,
        width: usize,
        number: usize,
        last_number: usize,
        options: &RenderOptions,
    ) -> Vec<Segment> {
        let (style, children) = self.item_parts();
        let number_width = last_number.to_string().chars().count() + 2;
        let lines = render_lines(
            children,
            width.saturating_sub(number_width),
            Some(style),
            true,
            options,
        );
        let number_style = Some(markdown_styles::ITEM_NUMBER);
        let numeral = format!("{:>width$} ", number, width = number_width - 1);
        let padding = " ".repeat(number_width);
        let mut segments: Vec<Segment> = Vec::new();
        for (index, line) in lines.into_iter().enumerate() {
            segments.push(Segment {
                text: if index == 0 { numeral.clone() } else { padding.clone() },
                style: number_style, link: None });
            segments.extend(line);
            segments.push(Segment { text: "\n".to_string(), style: None, link: None });
        }
        segments
    }
}

/// Rich's `Segment.apply_style`: the given style sits **under** each segment's own.
fn apply_style(segments: Vec<Segment>, style: Style) -> Vec<Segment> {
    segments
        .into_iter()
        .map(|segment| Segment {
            text: segment.text,
            style: Some(match segment.style {
                Some(own) => style.over(own),
                None => style,
            }), link: None })
        .collect()
}

/// Rich's `Console.render_lines` over a sequence of elements.
fn render_lines(
    children: &[Element],
    width: usize,
    style: Option<Style>,
    pad: bool,
    options: &RenderOptions,
) -> Vec<Vec<Segment>> {
    let mut segments: Vec<Segment> = Vec::new();
    for child in children {
        segments.extend(child.render(width, options));
    }
    // `if style:` again: an empty style applies nothing.
    if let Some(style) = style
        && style != Style::inherit()
    {
        segments = apply_style(segments, style);
    }
    split_and_crop_lines(&segments, width, style, pad, options.metrics)
}

/// The style stack `MarkdownContext` keeps, whose top is already the product of
/// everything beneath it.
struct StyleStack {
    entries: Vec<(Style, Option<Link>)>,
}

impl StyleStack {
    fn new(base: Style) -> StyleStack {
        StyleStack { entries: vec![(base, None)] }
    }

    fn current(&self) -> Style {
        self.entries.last().expect("the base style is never popped").0
    }

    /// The hyperlink in force, which Rich keeps inside the style it stacks.
    fn current_link(&self) -> Option<Link> {
        self.entries.last().expect("the base style is never popped").1.clone()
    }

    fn push(&mut self, style: Style) {
        let combined = self.current().over(style);
        let link = self.current_link();
        self.entries.push((combined, link));
    }

    fn push_linked(&mut self, style: Style, link: Link) {
        let combined = self.current().over(style);
        self.entries.push((combined, Some(link)));
    }

    fn pop(&mut self) {
        self.entries.pop();
    }
}

/// Walk the token stream the way `Markdown.__rich_console__` does.
struct Walk<'a, 'b> {
    styles: StyleStack,
    stack: Vec<Element>,
    output: Vec<Segment>,
    new_line: bool,
    link_counter: u32,
    width: usize,
    options: &'a RenderOptions<'b>,
}

impl Walk<'_, '_> {
    fn on_text(&mut self, text: &str) {
        let style = self.styles.current();
        let link = self.styles.current_link();
        match self.stack.last_mut() {
            Some(Element::Paragraph { text: target })
            | Some(Element::Heading { text: target, .. })
            | Some(Element::TableCell { text: target }) => {
                target.append_linked(text, Some(style), link)
            }
            // Every other element's `on_text` is the base class's, which is a no-op.
            _ => {}
        }
    }

    /// One id per link instance.
    ///
    /// Rich draws it from `randint(0, 999999)`, so its output is not reproducible
    /// from one run to the next — proved end to end through `ch-legacy`, three runs,
    /// three ids. **Uniqueness per link is the property; randomness is not**, and
    /// every comparator over real message bodies normalises `id=<digits>` on both
    /// sides. A counter gives the same terminal behaviour and a reproducible gate.
    fn next_link(&mut self, url: &str) -> Link {
        self.link_counter += 1;
        Link { url: url.to_string(), id: self.link_counter }
    }

    /// `should_render`: an element with a collecting parent is stored, not emitted.
    fn close(&mut self, element: Element, suppress_separator: bool) {
        match (self.stack.last_mut(), element) {
            (Some(Element::BlockQuote { children, .. }), element)
            | (Some(Element::ListItem { children, .. }), element) => {
                children.push(element);
                return;
            }
            (Some(Element::List { items, .. }), element) => {
                items.push(element);
                return;
            }
            (
                Some(Element::Table { header, body }),
                Element::TableSection { header: is_header, rows },
            ) => {
                if is_header {
                    // A header carries exactly one row, and its cells become the
                    // columns. Each is stylized with `markdown.table.header`, whose
                    // `bold: false` clears the `table.header` bold under it.
                    *header = rows.into_iter().next().unwrap_or_default();
                    for cell in header.iter_mut() {
                        cell.stylize(markdown_styles::TABLE_HEADER);
                    }
                } else {
                    *body = rows;
                }
                return;
            }
            (Some(Element::TableSection { rows, .. }), Element::TableRow { cells }) => {
                rows.push(cells);
                return;
            }
            (Some(Element::TableRow { cells }), Element::TableCell { text }) => {
                cells.push(text);
                return;
            }
            (_, element) => {
                return self.emit(element, suppress_separator);
            }
        }
    }

    fn emit(&mut self, element: Element, suppress_separator: bool) {
        if self.new_line && !suppress_separator {
            self.output.push(Segment { text: "\n".to_string(), style: None, link: None });
        }
        let segments = element.render(self.width, self.options);
        self.output.extend(segments);

    }
}

/// Render markdown to a flat segment stream, the way `Markdown.__rich_console__`
/// does, including the newlines that separate its blocks.
pub fn markdown_segments(
    markup: &str,
    width: usize,
    options: &RenderOptions,
) -> Vec<Segment> {
    let tokens = markdown_tokens(markup);
    let mut walk = Walk {
        styles: StyleStack::new(Style::inherit()),
        stack: Vec::new(),
        output: Vec::new(),
        new_line: false,
        link_counter: 0,
        width,
        options,
    };

    for token in &tokens {
        match token {
            Token::Text(text) => walk.on_text(text),
            Token::Hardbreak => walk.on_text("\n"),
            Token::Softbreak => walk.on_text(" "),

            // The four inline style tags. `code_inline` is self-closing and carries
            // its own text; the others bracket theirs.
            Token::EmphasisOpen => walk.styles.push(markdown_styles::EM),
            Token::StrongOpen => walk.styles.push(markdown_styles::STRONG),
            Token::StrikeOpen => walk.styles.push(markdown_styles::STRIKE),
            Token::EmphasisClose | Token::StrongClose | Token::StrikeClose => walk.styles.pop(),
            Token::CodeInline(content) => {
                walk.styles.push(markdown_styles::CODE);
                if !content.is_empty() {
                    walk.on_text(content);
                }
                walk.styles.pop();
            }

            Token::ParagraphOpen => {
                walk.styles.push(markdown_styles::NONE);
                let mut text = RichText::new();
                text.justify = Some(Justify::Left);
                walk.stack.push(Element::Paragraph { text });
            }
            Token::ParagraphClose => walk.leave(),

            Token::HeadingOpen(tag) => {
                walk.styles.push(markdown_styles::heading(tag));
                walk.stack.push(Element::Heading { tag, text: RichText::new() });
            }
            Token::HeadingClose => walk.leave(),

            Token::BlockquoteOpen => {
                walk.styles.push(markdown_styles::BLOCK_QUOTE);
                walk.stack.push(Element::BlockQuote {
                    style: walk.styles.current(),
                    children: Vec::new(),
                });
            }
            Token::BlockquoteClose => walk.leave(),

            // `ListElement` is not a `TextElement`, so it pushes no style.
            Token::BulletListOpen => walk.stack.push(Element::List {
                ordered: false,
                start: 1,
                items: Vec::new(),
            }),
            Token::OrderedListOpen(start) => walk.stack.push(Element::List {
                ordered: true,
                start: *start,
                items: Vec::new(),
            }),
            Token::ListClose => walk.leave_without_style(),

            Token::ListItemOpen => {
                walk.styles.push(markdown_styles::NONE);
                walk.stack.push(Element::ListItem {
                    style: walk.styles.current(),
                    children: Vec::new(),
                });
            }
            Token::ListItemClose => walk.leave(),

            Token::HorizontalRule => walk.self_closing(Element::HorizontalRule, false),
            // An `html_block` or an `html_inline` reaches `UnknownElement`, whose
            // `on_text` is a no-op and whose render yields nothing — so its content
            // is dropped, and it still moves the block separator.
            Token::HtmlBlock | Token::HtmlInline(_) => {
                walk.self_closing(Element::Unknown, false)
            }
            // `inline` is the one self-closing token Rich excludes from the
            // separator, by name.
            Token::EmptyInline => walk.self_closing(Element::Unknown, true),

            // A hyperlink is a *style*, not an element: Rich pushes
            // `markdown.link_url` combined with the link and pops it at the close.
            Token::LinkOpen(url) => {
                let link = walk.next_link(url);
                walk.styles.push_linked(markdown_styles::LINK_URL, link);
            }
            Token::LinkClose => walk.styles.pop(),

            Token::Image { alt, source } => {
                // The enclosing link, if the image sits inside one, wins over the
                // image's own source — `self.link or self.destination`.
                let enclosing = walk.styles.current_link();
                walk.styles.push(markdown_styles::NONE);
                let mut text = RichText::new();
                text.justify = Some(Justify::Left);
                text.append(alt, Some(walk.styles.current()));
                walk.self_closing(
                    Element::Image { destination: source.clone(), link: enclosing, text },
                    false,
                );
                walk.styles.pop();
            }

            // None of the table elements is a `TextElement`, so none pushes a
            // style — only the cell does, and it pushes nothing either: a
            // `TableDataElement` stylizes its own text with the current style
            // rather than entering one.
            Token::TableOpen => walk.stack.push(Element::Table {
                header: Vec::new(),
                body: Vec::new(),
            }),
            Token::TableClose => walk.leave_without_style(),
            Token::TheadOpen => walk.stack.push(Element::TableSection {
                header: true,
                rows: Vec::new(),
            }),
            Token::TbodyOpen => walk.stack.push(Element::TableSection {
                header: false,
                rows: Vec::new(),
            }),
            Token::TheadClose | Token::TbodyClose => walk.leave_without_style(),
            Token::RowOpen => walk.stack.push(Element::TableRow { cells: Vec::new() }),
            Token::RowClose => walk.leave_without_style(),
            Token::CellOpen { justify, .. } => {
                let mut text = RichText::new();
                text.justify = Some(*justify);
                walk.stack.push(Element::TableCell { text });
            }
            Token::CellClose => walk.leave_without_style(),

            // `CodeBlock.create` takes the first word of the info string, or
            // `text`. A tag Pygments does not know finds no lexer, and `Syntax`
            // falls back to its plain-text one — the same rendering as `text`, and
            // exact with no lexer written. A tag that reaches a **promoted** family
            // is lexed by that family's table. **Everything else renders plain**,
            // under the ruling recorded on the last arm below.
            Token::Fence { content, info } => {
                let tag = info.split(' ').next().unwrap_or("");
                let tag = if tag.is_empty() { "text" } else { tag };
                let lexer = match crate::syntax_lexers::lexer_for_tag(tag) {
                    None | Some("Text only") => None,
                    Some("JSON") => Some("JSON"),
                    Some(name) if crate::syntax_tables::promoted_lexer(name).is_some() => {
                        Some(name)
                    }
                    // **Ruled, 2026-08-30.** A language Pygments knows and no table
                    // covers renders with **complete fence geometry and plain
                    // unstyled code** — the same treatment as a tag Pygments does
                    // not know. It must never truncate or panic.
                    //
                    // The refusal it replaces was right only while nothing was
                    // wired to it. Once the panel sink existed, refusing produced a
                    // failure strictly worse than the approximation it prevented:
                    // results streamed, then stopped at an arbitrary point with the
                    // panic on stderr, so a redirected run showed a complete-looking
                    // result set that had silently been cut short.
                    //
                    // The accepted divergence is a **range, not a point** — 2.6% to
                    // 11% of fenced blocks, because block exposure is a property of
                    // whose sessions. Session exposure agreed across two corpora at
                    // about one in three.
                    Some(_) => None,
                };
                walk.styles.push(markdown_styles::CODE_BLOCK);
                let mut text = RichText::new();
                text.justify = Some(Justify::Left);
                text.append(content, Some(walk.styles.current()));
                walk.self_closing(Element::CodeBlock { text, lexer }, false);
                walk.styles.pop();
            }
            // An indented block carries no info string, so its lexer is `text`.
            Token::IndentedCode { content } => {
                walk.styles.push(markdown_styles::CODE_BLOCK);
                let mut text = RichText::new();
                text.justify = Some(Justify::Left);
                text.append(content, Some(walk.styles.current()));
                walk.self_closing(Element::CodeBlock { text, lexer: None }, false);
                walk.styles.pop();
            }
        }
    }
    walk.output
}

impl Walk<'_, '_> {
    /// A container closes: pop it, emit or collect it, then leave its style.
    fn leave(&mut self) {
        let element = self.stack.pop().expect("a close follows its open");
        let new_line = element.new_line();
        self.close(element, false);
        self.styles.pop();
        self.new_line = new_line;
    }

    /// The same, for an element whose Rich class is not a `TextElement` and so
    /// pushed no style.
    fn leave_without_style(&mut self) {
        let element = self.stack.pop().expect("a close follows its open");
        let new_line = element.new_line();
        self.close(element, false);
        self.new_line = new_line;
    }

    fn self_closing(
        &mut self,
        element: Element,
        suppress_separator: bool,
    ) {
        let new_line = element.new_line();
        self.close(element, suppress_separator);
        self.new_line = new_line;

    }
}

/// Render markdown to lines, the unit the conversation panel takes.
pub fn markdown_lines(
    markup: &str,
    width: usize,
    metrics: &CellMetrics,
) -> Vec<Vec<Segment>> {
    let options = RenderOptions::new(metrics);
    let segments = markdown_segments(markup, width, &options);
    split_and_crop_lines(&segments, width, None, false, metrics)
}

#[cfg(test)]
mod markdown_oracle_tests {
    use super::*;
    use serde_json::Value;
    use std::path::PathBuf;

    /// Constructs whose rendering is not written yet.
    ///
    /// The set is asserted rather than tolerated: landing one shrinks it and the
    /// test says so, and a construct that starts failing to render cannot hide by
    pub(super) fn oracle() -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/message-renderer/markdown-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("the markdown oracle is missing at {}: {error}", path.display())
        });
        serde_json::from_slice(&bytes).expect("the markdown oracle is valid JSON")
    }

    /// A segment as the oracle records it, so a difference reads as a difference in
    /// style rather than as two unrelated debug dumps.
    pub(super) fn describe(segment: &Segment) -> String {
        // An empty style and no style render identically, and the oracle records
        // both as absent, so the comparison collapses them the same way. A link is
        // recorded by its URL only: the id is random in Rich and normalised by
        // every comparator that meets it.
        let link = segment
            .link
            .as_ref()
            .map(|link| format!(" link={}", link.url))
            .unwrap_or_default();
        let Some(style) = segment.style.filter(|style| *style != Style::inherit()) else {
            if link.is_empty() {
                return format!("{:?}", segment.text);
            }
            return format!("{:?}[{}]", segment.text, link.trim_start());
        };
        let mut parts: Vec<String> = Vec::new();
        for (value, name) in [
            (style.bold, "bold"),
            (style.dim, "dim"),
            (style.italic, "italic"),
            (style.underline, "underline"),
            (style.reverse, "reverse"),
            (style.strike, "strike"),
        ] {
            match value {
                Some(true) => parts.push(name.to_string()),
                Some(false) => parts.push(format!("not-{name}")),
                None => {}
            }
        }
        for (colour, name) in [(style.foreground, "fg"), (style.background, "bg")] {
            match colour {
                Some(StyleColor::Palette(number)) => parts.push(format!("{name}=p{number}")),
                Some(StyleColor::Triplet(triplet)) => parts.push(format!(
                    "{name}=#{:02x}{:02x}{:02x}",
                    triplet.red, triplet.green, triplet.blue
                )),
                None => {}
            }
        }
        format!("{:?}[{}{link}]", segment.text, parts.join(" "))
    }

    pub(super) fn describe_recorded(entry: &Value) -> String {
        let text = entry["t"].as_str().expect("a recorded segment carries text");
        let style = &entry["s"];
        if style.is_null() {
            return format!("{text:?}");
        }
        let mut parts: Vec<String> = Vec::new();
        for name in ["bold", "dim", "italic", "underline", "reverse", "strike"] {
            match style.get(name).and_then(Value::as_bool) {
                Some(true) => parts.push(name.to_string()),
                Some(false) => parts.push(format!("not-{name}")),
                None => {}
            }
        }
        for (key, name) in [("fg", "fg"), ("bg", "bg")] {
            if let Some(colour) = style.get(key) {
                if let Some(number) = colour.get("palette").and_then(Value::as_u64) {
                    parts.push(format!("{name}=p{number}"));
                } else if let Some(rgb) = colour.get("triplet").and_then(Value::as_array) {
                    let channel = |index: usize| rgb[index].as_u64().unwrap_or_default();
                    parts.push(format!(
                        "{name}=#{:02x}{:02x}{:02x}",
                        channel(0),
                        channel(1),
                        channel(2)
                    ));
                }
            }
        }
        if let Some(link) = style.get("link").and_then(Value::as_str) {
            parts.push(format!("link={link}"));
        }
        format!("{text:?}[{}]", parts.join(" "))
    }

    pub(super) fn recorded_lines(case: &Value) -> Vec<Vec<String>> {
        case["lines"]
            .as_array()
            .expect("a recorded case carries lines")
            .iter()
            .map(|line| {
                line.as_array()
                    .expect("a recorded line carries segments")
                    .iter()
                    .map(describe_recorded)
                    .collect()
            })
            .collect()
    }

    struct Comparison {
        compared: usize,
        failures: Vec<String>,
    }

    /// Compare every supported case, optionally against a deliberately wrong
    /// renderer, so the gate's own reach is measurable.
    fn compare(mutate: Option<fn(&mut Vec<Vec<Segment>>)>) -> Comparison {
        let oracle = oracle();
        let metrics = CellMetrics::from_environment();
        let mut comparison = Comparison { compared: 0, failures: Vec::new() };
        for case in oracle["cases"].as_array().expect("the oracle carries cases") {
            let markup = case["markup"].as_str().expect("a case carries markup");
            let width = case["width"].as_u64().expect("a case carries a width") as usize;
            let identifier = case["id"].as_str().unwrap_or("?");
            let mut rendered = markdown_lines(markup, width, &metrics);
            if let Some(mutate) = mutate {
                mutate(&mut rendered);
            }
            comparison.compared += 1;
            let expected = recorded_lines(case);
            let actual: Vec<Vec<String>> = rendered
                .iter()
                .map(|line| line.iter().map(describe).collect())
                .collect();
            if actual == expected {
                continue;
            }
            let mut report = format!("{identifier} @ {width}\n  markup {markup:?}\n");
            for index in 0..expected.len().max(actual.len()) {
                let want = expected.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let got = actual.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let marker = if want == got { "  " } else { "->" };
                report.push_str(&format!("  {marker} rich {want}\n     ours {got}\n"));
            }
            comparison.failures.push(report);
        }
        comparison
    }

    #[test]
    fn every_recorded_rich_render_reproduces() {
        let comparison = compare(None);
        // **Nothing is excluded any more**, so this is a pure corpus floor: every
        // recorded case renders, and a lower count means the recording shrank rather
        // than that a construct started being skipped.
        assert!(
            comparison.compared >= 855,
            "Only {} of the recorded cases were compared, against 855 when every \
             recorded case renders. A shrunken corpus passes vacuously.",
            comparison.compared
        );
        assert!(
            comparison.failures.is_empty(),
            "{} of {} recorded renders differ from Rich:\n\n{}",
            comparison.failures.len(),
            comparison.compared,
            comparison.failures[..comparison.failures.len().min(6)].join("\n")
        );
    }

    /// The gate must fail against a renderer that is wrong in the ways this port
    /// can plausibly be wrong. A gate never observed to fail is not evidence.
    #[test]
    fn the_oracle_rejects_plausible_wrong_renderers() {
        // Padding dropped: the shape of a port that forgets a paragraph is
        // left-justified rather than default-justified.
        fn without_padding(lines: &mut Vec<Vec<Segment>>) {
            for line in lines.iter_mut() {
                if let Some(last) = line.last_mut()
                    && last.text.chars().all(|character| character == ' ')
                {
                    line.pop();
                }
            }
        }
        // Adjacent same-styled runs merged: the shape of a port that joins segments
        // for tidiness, which changes escape structure without changing text.
        fn merged_runs(lines: &mut Vec<Vec<Segment>>) {
            for line in lines.iter_mut() {
                let mut merged: Vec<Segment> = Vec::new();
                for segment in line.drain(..) {
                    match merged.last_mut() {
                        Some(previous) if previous.style == segment.style => {
                            previous.text.push_str(&segment.text);
                        }
                        _ => merged.push(segment),
                    }
                }
                *line = merged;
            }
        }
        // A code block's vertical padding: `Syntax` is built with `padding=1`, so a
        // block that renders only its lines is two lines short. The shape of a port
        // that reads `padding` as horizontal only.
        fn without_vertical_padding(lines: &mut Vec<Vec<Segment>>) {
            let is_blank_run = |line: &Vec<Segment>| {
                line.len() == 1 && line[0].text.chars().all(|character| character == ' ')
            };
            if lines.first().is_some_and(is_blank_run) {
                lines.remove(0);
            }
            if lines.last().is_some_and(is_blank_run) {
                lines.pop();
            }
        }
        // The block's horizontal padding: one column each side, carrying the
        // background. Dropping it is the off-by-two a port makes when it gives the
        // code the panel's whole width.
        fn without_horizontal_padding(lines: &mut Vec<Vec<Segment>>) {
            for line in lines.iter_mut() {
                let single_space = |segment: &Segment| segment.text == " ";
                if line.first().is_some_and(single_space) {
                    line.remove(0);
                }
                if line.last().is_some_and(single_space) {
                    line.pop();
                }
            }
        }
        for (name, mutation) in [
            ("dropped padding", without_padding as fn(&mut Vec<Vec<Segment>>)),
            ("merged runs", merged_runs as fn(&mut Vec<Vec<Segment>>)),
            ("a code block without its vertical padding", without_vertical_padding),
            ("a code block without its horizontal padding", without_horizontal_padding),
        ] {
            let comparison = compare(Some(mutation));
            assert!(
                !comparison.failures.is_empty(),
                "The oracle no longer catches {name}. The gate is blind to it."
            );
        }
    }
}

// ---------------------------------------------------------------------------
// One message, and the group of them inside a conversation panel
// ---------------------------------------------------------------------------

use crate::model::{Message, MessageType, Tool};
use crate::search_query::Regex;
use serde_json::Value;
use std::collections::HashMap;

/// A renderable in the message body's group, mirroring what
/// `_message_content_renderables` builds.
#[derive(Clone, Debug)]
pub enum Renderable {
    /// A markdown body, with the search term painted into it when one is given.
    Markdown { markup: String, highlight: bool },
    Text(RichText),
    /// `LeftRail`: a coloured `▎ ` down the left of a child rendered narrower.
    LeftRail { child: Box<Renderable>, style: Style, glyph: &'static str },
    /// `ToolHeader`: a marker plus a key argument **elided at the width it renders
    /// at**. Panels and rails claim their columns first, so eliding any earlier
    /// fixes the header's width — which then overflows narrow terminals and wastes
    /// wide ones. That was a shipped defect.
    ToolHeader { marker: RichText, argument: String },
    /// A `Read` result's body: source under a line-number gutter, which is geometry
    /// rather than highlighting and is drawn whatever lexer the path resolves to.
    ReadOutput { code: String, lexer: Option<&'static str>, start_line: usize },
}

/// Everything the body render needs that is not a message.
pub struct BodyContext<'a> {
    pub metrics: &'a CellMetrics,
    /// The compiled literal-term regex, or `None` when no term is a plain literal.
    pub highlight: Option<&'a Regex>,
    /// The conversation's short id, restated on every message header.
    pub conversation_tag: Option<&'a str>,
    /// What `collapse_home` shortens a tool's path argument against. Python reads
    /// `Path.home()` inside the helper; it is carried here because a renderer that
    /// reads the environment cannot be gated at two different homes.
    pub home: &'a str,
}

impl Renderable {
    fn render(
        &self,
        width: usize,
        options: &RenderOptions,
        context: &BodyContext,
    ) -> Vec<Segment> {
        match self {
            Renderable::Markdown { markup, highlight } => {
                let segments = markdown_segments(markup, width, options);
                match (highlight, context.highlight) {
                    (true, Some(regex)) => paint_highlight(segments, regex),
                    _ => segments,
                }
            }
            Renderable::Text(text) => text.to_segments(width, options),
            Renderable::ReadOutput { code, lexer, start_line } => {
                render_read_output(code, *lexer, *start_line, width, options)
            }
            // `ToolHeader.__rich_console__`: the budget is what the panel and the
            // rail have left, so the elision happens here rather than at build time.
            Renderable::ToolHeader { marker, argument } => {
                let budget = width
                    .saturating_sub(options.metrics.cell_len(&marker.plain()))
                    .saturating_sub(TOOL_KEY_ARG_SEPARATOR.chars().count());
                let mut line = marker.clone();
                line.append(TOOL_KEY_ARG_SEPARATOR, Some(meta_style()));
                line.append(
                    &crate::search_views::elide_to_width(
                        argument,
                        budget,
                        crate::search_views::Elision::Middle,
                    ),
                    Some(meta_style()),
                );
                line.to_segments(width, options)
            }
            Renderable::LeftRail { child, style, glyph } => {
                // The child renders **narrower** by the glyph's length in code
                // points, and `pad=False`, so its lines are their natural width.
                let inner = width.saturating_sub(glyph.chars().count()).max(1);
                // **Nothing inside a rail is highlighted.** `_text_renderable` is
                // the only thing that builds a `HighlightedMarkdown`, and it is
                // reached from the message text alone — every rail in
                // `formatting.py` is constructed without the regex: thinking, the
                // subagent task, tool content, a `Read` result and an Edit diff.
                //
                // So a search term inside a thinking block is plain in the product,
                // and a port that paints it is *more helpful* and diverges. The rail
                // withholds the regex rather than a comment asking callers not to
                // pass one, so the divergence cannot be reintroduced from outside.
                let unhighlighted = BodyContext {
                    metrics: context.metrics,
                    highlight: None,
                    conversation_tag: context.conversation_tag,
                    home: context.home,
                };
                let segments = child.render(inner, options, &unhighlighted);
                let lines = split_and_crop_lines(&segments, inner, None, false, options.metrics);
                // Blank lines are trimmed from both ends, so a rail marks only the
                // block's real extent.
                let is_blank = |line: &Vec<Segment>| {
                    line.iter().all(|segment| segment.text.trim().is_empty())
                };
                let mut start = 0usize;
                let mut end = lines.len();
                while start < end && is_blank(&lines[start]) {
                    start += 1;
                }
                while end > start && is_blank(&lines[end - 1]) {
                    end -= 1;
                }
                let rail = Segment {
                    text: glyph.to_string(),
                    style: Some(*style),
                    link: None,
                };
                let mut out: Vec<Segment> = Vec::new();
                for line in &lines[start..end] {
                    out.push(rail.clone());
                    out.extend(line.iter().cloned());
                    out.push(Segment { text: "\n".to_string(), style: None, link: None });
                }
                out
            }
        }
    }
}

/// Paint the search highlight onto an already-rendered segment stream.
///
/// **Per segment, and that is preserved because it is wrong.** `HighlightedMarkdown`
/// re-applies the regex to each rendered run, so a term straddling a style boundary
/// is left unpainted: searching `hello` against `**hel**lo` produces `hel` bold and
/// `lo` plain, the regex matches neither, and the rendered line plainly reading
/// `hello` is not highlighted. Its own docstring says so.
///
/// Painting the assembled plain text and mapping offsets back is the obvious
/// implementation, is genuinely more useful, and diverges — and nobody reviews a
/// search term being highlighted as a defect. **It also composes badly with the
/// only way to get the folding right**: the natural version reaches for offsets
/// measured on a lowercased copy, and `İ` grows from two bytes to three while `ﬀ`
/// shrinks from three to two.
///
/// Spans come from the search engine itself, in **character** offsets over the
/// original run, so no string is ever indexed with offsets measured on another.
fn paint_highlight(segments: Vec<Segment>, regex: &Regex) -> Vec<Segment> {
    let highlight = crate::search_views::theme_style("search.match");
    let mut painted: Vec<Segment> = Vec::with_capacity(segments.len());
    for segment in segments {
        if segment.text.is_empty() {
            painted.push(segment);
            continue;
        }
        // A budget trip is not a "no match", and returning one silently is the
        // shape this desk has already ruled against. It is also unreachable:
        // confirmation ran this same pattern over the whole rendered message, which
        // is strictly longer than any run of it, so a run that trips the budget
        // means the budget moved or the pattern did.
        let spans = regex.find_all(&segment.text).unwrap_or_else(|_| {
            panic!(
                "the highlight pattern exhausted its step budget on a rendered run \
                 of {} characters, after matching the whole message during \
                 confirmation. Something upstream changed, and painting nothing \
                 would hide it.",
                segment.text.chars().count()
            )
        });
        if spans.is_empty() {
            painted.push(segment);
            continue;
        }
        let characters: Vec<char> = segment.text.chars().collect();
        let combined = match segment.style {
            Some(style) => style.over(highlight),
            None => highlight,
        };
        let mut cursor = 0usize;
        for (start, end) in spans {
            if start > cursor {
                painted.push(Segment {
                    text: characters[cursor..start].iter().collect(),
                    style: segment.style,
                    link: segment.link.clone(),
                });
            }
            painted.push(Segment {
                text: characters[start..end].iter().collect(),
                style: Some(combined),
                link: segment.link.clone(),
            });
            cursor = end;
        }
        if cursor < characters.len() {
            painted.push(Segment {
                text: characters[cursor..].iter().collect(),
                style: segment.style,
                link: segment.link,
            });
        }
    }
    painted
}

/// One visible content part of a message, in `iter_visible_parts` order.
#[derive(Clone, Debug)]
pub enum Part<'a> {
    SubagentTask(&'a str),
    Text(&'a str),
    Thinking(&'a str),
    Tool(ToolPart<'a>),
}

/// A tool part, which is what a **plan** is too.
///
/// Python has no plan part kind: `iter_visible_parts` emits the plan as a `TOOL`
/// part carrying a synthesized `ToolParts(tag="tool-input", name="ExitPlanMode")`.
/// Modelling it as a fifth `Part` variant is what invites a second tool renderer,
/// so it is a second *constructor* of the one part kind instead.
#[derive(Clone, Debug)]
pub enum ToolPart<'a> {
    Real(&'a Tool),
    ExitPlanMode(&'a str),
}

/// The message's visible parts, in the order that is the single source of truth
/// for content ordering: subagent task, text, thinking, tools, plan.
///
/// The message is already projected — visibility and shortening ran during
/// confirmation — so this reads fields rather than re-applying flags, exactly as
/// `codecs::render_message_inner_xml` does beside it.
pub fn visible_parts(message: &Message) -> Vec<Part<'_>> {
    let mut parts: Vec<Part<'_>> = Vec::new();
    if let Some(task) = message.subagent_task.as_deref().filter(|value| !value.is_empty()) {
        parts.push(Part::SubagentTask(task));
    }
    if !message.text.is_empty() {
        parts.push(Part::Text(&message.text));
    }
    if let Some(thinking) = message.thinking.as_deref().filter(|value| !value.is_empty()) {
        parts.push(Part::Thinking(thinking));
    }
    for tool in &message.tools {
        parts.push(Part::Tool(ToolPart::Real(tool)));
    }
    if let Some(plan) = message.plan.as_deref().filter(|value| !value.is_empty()) {
        parts.push(Part::Tool(ToolPart::ExitPlanMode(plan)));
    }
    parts
}

/// One distinct palette hue per role, from `theme.py` by way of `_ROLE_HUE`.
fn role_hue(message_type: MessageType) -> ColorTriplet {
    let hex = match message_type {
        // The three user-* tags share blue on purpose: they are one actor.
        MessageType::UserMessage
        | MessageType::UserCommandInput
        | MessageType::UserCommandOutput => "#71b9f4",
        MessageType::Recap => "#98c379",
        MessageType::Compaction => "#eac786",
        MessageType::AssistantResponse => "#c88bda",
        MessageType::Agent => "#62bac6",
        MessageType::Custom => "#c9ccd3",
        MessageType::SessionRename => "#e27881",
    };
    ColorTriplet::from_hex(hex)
}

/// Whether the visible user message consists only of `Bash` tool results.
fn is_bash_result_message(message: &Message, parts: &[Part]) -> bool {
    message.message_type == MessageType::UserMessage
        && !parts.is_empty()
        && parts.iter().all(|part| match part {
            Part::Tool(ToolPart::Real(Tool::Result(result))) => {
                result.name.as_deref() == Some("Bash")
            }
            _ => false,
        })
}

/// The message date as the badge shows it: `August 20th, 11:01`.
pub fn display_date(timestamp: Option<&str>) -> Option<String> {
    use chrono::Datelike;
    use chrono::Timelike;
    let parsed = crate::codecs::message_local_datetime(timestamp?).ok()?;
    let day = parsed.day();
    let suffix = match (day % 100, day % 10) {
        (10..=20, _) => "th",
        (_, 1) => "st",
        (_, 2) => "nd",
        (_, 3) => "rd",
        _ => "th",
    };
    let month = [
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December",
    ][parsed.month0() as usize];
    Some(format!(
        "{month} {day}{suffix}, {:02}:{:02}",
        parsed.hour(),
        parsed.minute()
    ))
}

/// The chip's dark ink, drawn over every role hue.
const INK: Style = Style {
    bold: Some(true),
    dim: None,
    italic: None,
    underline: None,
    reverse: None,
    strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#1d1f23"))),
    background: None,
};

fn chip_style(hue: ColorTriplet) -> Style {
    Style { background: Some(StyleColor::Triplet(hue)), ..INK }
}

/// `bold white on #475569` — and `white` is a **palette** colour, so it stays `37`
/// at every colour depth while the slate background downgrades with the terminal.
const BRANCH_CHIP: Style = Style {
    bold: Some(true),
    dim: None,
    italic: None,
    underline: None,
    reverse: None,
    strike: None,
    foreground: Some(StyleColor::Palette(7)),
    background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#475569"))),
};

fn meta_style() -> Style {
    crate::search_views::theme_style("message.meta")
}

/// The role text in a coloured message badge.
fn header_text(message: &Message, parts: &[Part]) -> String {
    if is_bash_result_message(message, parts) {
        return "Bash".to_string();
    }
    let header = message.header();
    // `re.sub(r"^#+\s*", "", header)`.
    let trimmed = header.trim_start_matches('#');
    let trimmed = trimmed.trim_start_matches([' ', '\t', '\n', '\r', '\u{b}', '\u{c}']);
    if !trimmed.is_empty() {
        return trimmed.to_string();
    }
    // Python falls back to `msg.role.title()` only when the header is empty.
    title_case(&message.role)
}

/// Python's `str.title`: the first letter of every run of letters, upper-cased.
fn title_case(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    let mut previous_was_alphabetic = false;
    for character in value.chars() {
        if character.is_alphabetic() && !previous_was_alphabetic {
            out.extend(character.to_uppercase());
        } else if character.is_alphabetic() {
            out.extend(character.to_lowercase());
        } else {
            out.push(character);
        }
        previous_was_alphabetic = character.is_alphabetic();
    }
    out
}

/// A message's role badge: the coloured chip plus its dim metadata suffix.
pub fn header_badge(
    message: &Message,
    parts: &[Part],
    conversation_tag: Option<&str>,
) -> RichText {
    let mut badge = RichText::new();
    if let Some(branch) = message.branch.as_deref().filter(|value| !value.is_empty()) {
        badge.append(&format!(" ⑂{branch} "), Some(BRANCH_CHIP));
    }
    let hue = if is_bash_result_message(message, parts) {
        ColorTriplet::from_hex("#5f7e86")
    } else {
        role_hue(message.message_type)
    };
    badge.append(&format!(" {} ", header_text(message, parts)), Some(chip_style(hue)));

    let mut meta: Vec<String> = Vec::new();
    if let Some(tag) = conversation_tag.filter(|value| !value.is_empty()) {
        meta.push(tag.to_string());
    }
    meta.push(format!("#{}", message.original_index));
    if let Some(model) = message.display_model().filter(|value| !value.is_empty()) {
        meta.push(model.to_string());
    }
    if let Some(date) = display_date(message.timestamp.as_deref()) {
        meta.push(date);
    }
    let meta = meta.join("  ·  ");
    if !meta.is_empty() {
        badge.append(&format!("  ·  {meta}"), Some(meta_style()));
    }
    badge
}

/// Escape tag-like text so Markdown leaves it literal rather than dropping it.
///
/// The product does this to every TEXT part before it reaches `Markdown`, which is
/// why an HTML-shaped parser difference barely reaches this surface.
fn escape_tag_like(text: &str) -> String {
    use std::sync::OnceLock;
    static DETECT: OnceLock<regex::Regex> = OnceLock::new();
    static REPLACE: OnceLock<regex::Regex> = OnceLock::new();
    // **`\s` here is CPython's, not the crate's.** `formatting.py` writes these two
    // patterns with Python's `re`, whose `\s` is the `str.isspace()` set and reaches
    // U+001C through U+001F; the crate's is `\p{White_Space}` and does not. A tag
    // followed by a file separator is escaped by the product and was being left alone
    // here. Measured over all 1,114,112 scalar values, exact in both directions.
    let detect = DETECT.get_or_init(|| {
        regex::Regex::new(&format!(
            r"<[a-zA-Z][a-zA-Z0-9-]*[>{}]",
            crate::session::PYTHON_SPACE_CLASS
        ))
        .expect("a fixed pattern")
    });
    if !detect.is_match(text) {
        return text.to_string();
    }
    let replace = REPLACE.get_or_init(|| {
        regex::Regex::new(&format!(
            r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)([{}]+[^>]*?)?>",
            crate::session::PYTHON_SPACE_CLASS
        ))
        .expect("a fixed pattern")
    });
    replace.replace_all(text, "\\<$1$2$3>").into_owned()
}

fn styled_text(text: &str, style: Style) -> Renderable {
    let mut rich = RichText::new();
    rich.append(text, Some(style));
    Renderable::Text(rich)
}

/// The italic-only style a subagent task's rail carries, and the dim italic a
/// thinking block's does. Neither is a theme token: Rich parses the compound name
/// as attributes, so the theme's own `dim` colour never applies here.
const ITALIC: Style = Style {
    bold: None, dim: None, italic: Some(true), underline: None,
    reverse: None, strike: None, foreground: None, background: None,
};
const DIM_ITALIC: Style = Style {
    bold: None, dim: Some(true), italic: Some(true), underline: None,
    reverse: None, strike: None, foreground: None, background: None,
};

/// The four tool accents from `theme.py`, and the meta colour the key argument uses.
///
/// `tool.call`, `tool.additional_context` and `tool.error` are **bold**; `tool.result`
/// is not. That asymmetry is the theme's, not a slip.
const TOOL_CALL: Style = Style {
    bold: Some(true), dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#78c4ce"))),
    background: None,
};
const TOOL_ADDITIONAL_CONTEXT: Style = Style {
    bold: Some(true), dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#fc9867"))),
    background: None,
};
const TOOL_RESULT: Style = Style {
    bold: None, dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#5f7e86"))),
    background: None,
};
const TOOL_ERROR: Style = Style {
    bold: Some(true), dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e27881"))),
    background: None,
};

/// `diff.add`, `diff.remove` and `dim` from `theme.py`, which are what an `Edit`'s
/// unified diff is painted with.
///
/// **`dim` is a theme *colour* here, not Rich's dim attribute.** The theme defines
/// `"dim": "rgb(80,80,80)"`, so the lookup resolves to a foreground and the attribute
/// is never set — and a port reaching for the attribute renders a context line that
/// inherits its colour instead of taking one.
const DIFF_ADD: Style = Style {
    bold: None, dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#98c379"))),
    background: None,
};
const DIFF_REMOVE: Style = Style {
    bold: None, dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e27881"))),
    background: None,
};
const DIFF_CONTEXT: Style = Style {
    bold: None, dim: None, italic: None, underline: None,
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#505050"))),
    background: None,
};

/// `_TOOL_KEY_ARG_SEPARATOR`.
const TOOL_KEY_ARG_SEPARATOR: &str = "  ·  ";

/// Python's `str.splitlines`, which breaks on eight boundaries `split('\n')` does not
/// and treats `\r\n` as one.
///
/// An `Edit` diff is computed over these lines, so a transcript carrying a form feed
/// or a `U+2028` inside `old_string` splits differently in a port that reaches for
/// `lines()` — and the diff then aligns different text against different text.
///
/// ```
/// use _native::session_render::python_splitlines;
/// assert_eq!(python_splitlines("a\nb"), vec!["a", "b"]);
/// assert_eq!(python_splitlines("a\r\nb"), vec!["a", "b"]);
/// assert_eq!(python_splitlines("a\u{0b}b"), vec!["a", "b"]);
/// assert_eq!(python_splitlines("a\n"), vec!["a"]);
/// assert!(python_splitlines("").is_empty());
/// ```
pub fn python_splitlines(text: &str) -> Vec<&str> {
    const BOUNDARIES: [char; 10] = [
        '\n', '\r', '\u{0b}', '\u{0c}', '\u{1c}', '\u{1d}', '\u{1e}', '\u{85}', '\u{2028}',
        '\u{2029}',
    ];
    let mut lines = Vec::new();
    let mut start = 0usize;
    let mut characters = text.char_indices().peekable();
    while let Some((offset, character)) = characters.next() {
        if !BOUNDARIES.contains(&character) {
            continue;
        }
        lines.push(&text[start..offset]);
        start = offset + character.len_utf8();
        // `\r\n` is one boundary, not two.
        if character == '\r' && characters.peek().is_some_and(|(_, next)| *next == '\n') {
            let (newline_offset, newline) = characters.next().expect("peeked");
            start = newline_offset + newline.len_utf8();
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

pub mod read_lexers;

/// `Syntax.guess_lexer(path, code)`, reduced to the only question that changes bytes:
/// **which promoted family, if any, paints this file**.
///
/// Pygments scores every lexer whose filename globs match, and the winner is the
/// maximum by `(score, is primary, priority, class name)`. Porting every `analyse_text`
/// is unnecessary and was not done: of the globs the seven promoted families claim,
/// all but two have a single candidate, so the filename decides. The two that do not
/// carry their rule by name in the generated table.
///
/// **Measured, not assumed:** over 127 real `Read` results an extension-only answer
/// agreed with `Syntax.guess_lexer` on the promotion decision 121 times, and every
/// disagreement was `*.js` resolving to `js+genshitext`. That is the rule below.
///
/// **`*.sql` is absent on purpose.** `SqlLexer`, `TransactSqlLexer` and `SqlJinjaLexer`
/// all claim it, `SqlLexer` can never score above zero, and the tie-break is the class
/// name — so `TransactSqlLexer` always wins and a `Read` of a `.sql` file renders
/// plain. SQL is promoted for fences and unreachable here.
pub fn read_lexer(path: &str, code: &str) -> Option<&'static str> {
    let name = path.rsplit('/').next().unwrap_or(path);
    read_lexers::READ_PROMOTED_FILENAMES
        .iter()
        .find(|(glob, _, _)| glob_matches(glob, name))
        .and_then(|(_, display, rule)| match *rule {
            "unconditional" => Some(*display),
            // `JavascriptLexer` scores zero and is the primary match, so it wins every
            // tie. A template delegate takes the file only by scoring above zero.
            "js-delegates" => (!javascript_is_delegated(code)).then_some(*display),
            // `SuperColliderLexer` owns `*.sc` unless the content declares Python.
            "python-shebang" => {
                shebang_matches(code, r"pythonw?(3(\.\d)?)?").then_some(*display)
            }
            other => unreachable!("the table carries a rule nothing implements: {other}"),
        })
}

/// `fnmatch.fnmatch` over the shapes the generated table actually uses.
///
/// Only `*` appears, so `?` and `[…]` are not implemented — and the gate asserts no
/// glob uses them, so a regenerated table carrying one fails loudly instead of
/// matching the wrong file.
fn glob_matches(glob: &str, name: &str) -> bool {
    let mut parts = glob.split('*');
    let Some(first) = parts.next() else {
        return false;
    };
    let Some(mut rest) = name.strip_prefix(first) else {
        return false;
    };
    let tail: Vec<&str> = parts.collect();
    if tail.is_empty() {
        return rest.is_empty();
    }
    for (index, part) in tail.iter().enumerate() {
        if index + 1 == tail.len() {
            return rest.ends_with(part);
        }
        match rest.find(part) {
            Some(at) => rest = &rest[at + part.len()..],
            None => return false,
        }
    }
    true
}

fn matches_anywhere(pattern: &'static str, text: &str, ignorecase: bool, dotall: bool) -> bool {
    let compiled = Regex::compile_with_flags(pattern, ignorecase, true, dotall)
        .unwrap_or_else(|_| panic!("the ported Pygments heuristic {pattern:?} compiles"));
    compiled.search(text).unwrap_or(false)
}

/// Whether a `*.js` file is taken from `JavascriptLexer` by a template delegate.
///
/// Five delegates list `*.js` in `alias_filenames`, so each is a non-primary candidate
/// that beats JavaScript only with a score above zero. **Which one wins does not
/// matter** — none of them is a promoted family, so any of them means plain output.
/// The conditions are Pygments' own `analyse_text` bodies, reduced to "can this score
/// at all".
fn javascript_is_delegated(code: &str) -> bool {
    // Django: a block or extends tag, an if tag, or a variable.
    matches_anywhere(r"\{%\s*(block|extends)", code, false, false)
        || matches_anywhere(r"\{%\s*if\s*.*?%\}", code, false, false)
        || matches_anywhere(r"\{\{.*?\}\}", code, false, false)
        // ERB: a substring test in Pygments, not a pattern.
        || (code.contains("<%") && code.contains("%>"))
        // Genshi, through `JavaScript+Genshi Text`, whose score is Genshi's less 0.05.
        // Any one of the three terms clears that.
        || matches_anywhere(r"\$\{.*?\}", code, false, false)
        || matches_anywhere(r#"py:(.*?)=["']"#, code, false, false)
        || looks_like_xml(code)
        // PHP.
        || shebang_matches(code, "php")
        || matches_anywhere(r"<\?(?!xml)", code, false, false)
        // Smarty.
        || matches_anywhere(r"\{if\s+.*?\}.*?\{/if\}", code, false, false)
        || matches_anywhere(r"\{include\s+file=.*?\}", code, false, false)
        || matches_anywhere(r"\{foreach\s+.*?\}.*?\{/foreach\}", code, false, false)
        || matches_anywhere(r"\{\$.*?\}", code, false, false)
}

/// `pygments.util.looks_like_xml`: an XML declaration, a doctype, or a tag pair in the
/// first thousand characters.
fn looks_like_xml(text: &str) -> bool {
    // `xml_decl_re.match`, which is anchored at the start.
    let anchored: Vec<char> = text.chars().collect();
    let declaration = Regex::compile_with_flags(r"\s*<\?xml[^>]*\?>", true, false, false)
        .expect("the xml declaration pattern compiles");
    if declaration.match_at(&anchored, 0).ok().flatten().is_some() {
        return true;
    }
    // `doctype_lookup_re`, written out of its VERBOSE form.
    if matches_anywhere(
        r#"<!DOCTYPE\s+([a-zA-Z_][a-zA-Z0-9]*(?:\s+[a-zA-Z_][a-zA-Z0-9]*\s+"[^"]*")?)[^>]*>"#,
        text,
        false,
        true,
    ) {
        return true;
    }
    // `tag_re.search(text[:1000])` — a thousand **characters**, as Python slices.
    let head: String = text.chars().take(1000).collect();
    matches_anywhere(r"<(.+?)(\s.*?)?>.*?</.+?>", &head, true, true)
}

/// `pygments.util.shebang_matches`: the last path component of a `#!` line, matched
/// whole against `pattern` with an optional Windows executable suffix.
fn shebang_matches(text: &str, pattern: &str) -> bool {
    let first_line = match text.find('\n') {
        Some(index) => &text[..index],
        None => text,
    };
    let lowered = first_line.to_lowercase();
    let Some(body) = lowered.strip_prefix("#!") else {
        return false;
    };
    // `split_path_re` is `[/\\ ]+`, and arguments beginning with `-` are ignored.
    let Some(found) = body
        .trim()
        .split(['/', '\\', ' '])
        .filter(|part| !part.is_empty() && !part.starts_with('-'))
        .next_back()
    else {
        return false;
    };
    let whole = format!(r"^{pattern}(\.(exe|cmd|bat|bin))?$");
    Regex::compile_with_flags(&whole, true, true, true)
        .expect("the shebang pattern compiles")
        .search(found)
        .unwrap_or(false)
}

/// `_strip_read_line_numbers`: drop `Read`'s `<n>\t` gutter and recover the first
/// number, so the highlight starts counting where the file does.
///
/// **The threshold is the rule.** Fewer than half the lines carrying a number means
/// this is not a `Read` gutter at all — a diff, a log, a stack trace — and the text is
/// returned untouched, numbered from 1.
///
/// The pattern is compiled by this crate's own Python-compatible engine rather than
/// hand-matched, because `\s` and `\d` here are Python's: `\s` reaches `U+001C`
/// through `U+001F` and every Unicode space, and `\d` reaches every Unicode decimal
/// digit. A hand-rolled ASCII version strips a line Python leaves alone.
///
/// ```
/// use _native::session_render::strip_read_line_numbers;
/// assert_eq!(strip_read_line_numbers("   12\tab\n   13\tcd"), ("ab\ncd".to_string(), 12));
/// // Fewer than half the lines are numbered, so nothing is stripped. Three of four
/// // unnumbered clears the threshold; two of three does **not**, because the floor is
/// // `len // 2` and integer division rounds down.
/// let mixed = "1\tab\nplain\nplain\nplain";
/// assert_eq!(strip_read_line_numbers(mixed), (mixed.to_string(), 1));
/// assert_eq!(strip_read_line_numbers("1\tab\nplain\nplain"), ("ab\nplain\nplain".to_string(), 1));
/// ```
pub fn strip_read_line_numbers(text: &str) -> (String, usize) {
    static GUTTER: std::sync::LazyLock<Regex> = std::sync::LazyLock::new(|| {
        Regex::compile(r"\s*(\d+)\t(.*)$", false).expect("the gutter pattern compiles")
    });
    let lines: Vec<&str> = text.split('\n').collect();
    let mut stripped: Vec<String> = Vec::with_capacity(lines.len());
    let mut first: Option<usize> = None;
    let mut matched = 0usize;
    for line in &lines {
        let characters: Vec<char> = line.chars().collect();
        let captures = GUTTER.match_at(&characters, 0).ok().flatten();
        let Some(captures) = captures else {
            stripped.push((*line).to_string());
            continue;
        };
        matched += 1;
        if first.is_none()
            && let Some((start, end)) = captures.group(1)
        {
            first = characters[start..end].iter().collect::<String>().parse().ok();
        }
        let body = captures
            .group(2)
            .map(|(start, end)| characters[start..end].iter().collect::<String>())
            .unwrap_or_default();
        stripped.push(body);
    }
    if matched < (lines.len() / 2).max(1) {
        return (text.to_string(), 1);
    }
    (stripped.join("\n"), first.filter(|value| *value != 0).unwrap_or(1))
}

/// `_edit_diff_renderable`: an `Edit` call as a coloured unified diff of `old_string`
/// against `new_string`.
///
/// **`None` when the diff is empty, and that is not the same as falling back.** Python
/// returns this renderable directly from `_tool_body_renderable`, so an `Edit` whose
/// two strings are identical renders its header **with no body at all** — the fenced
/// `old_string`/`new_string` content that every other tool would show is never
/// reached. A port that falls through to the fence on an empty diff is more helpful
/// and diverges.
fn edit_diff_renderable(input: &Value, accent: Style) -> Option<Renderable> {
    let old = crate::model::python_value_string(input.get("old_string").unwrap_or(&Value::Null));
    let new = crate::model::python_value_string(input.get("new_string").unwrap_or(&Value::Null));
    // `input_data.get("old_string", "")` — a **missing** key is the empty string, so
    // an absent key and a JSON `null` are not the same thing.
    let old = if input.get("old_string").is_some() { old } else { String::new() };
    let new = if input.get("new_string").is_some() { new } else { String::new() };
    let mut body = RichText::new();
    let first = python_splitlines(&old);
    let second = python_splitlines(&new);
    // `list(difflib.unified_diff(old, new, lineterm=""))[2:]`, then `@@` skipped. The
    // two dropped lines are the `---` and `+++` headers, which only exist when the
    // diff is non-empty.
    for line in crate::difflib::unified_diff(&first, &second, "", "", "", "", 2, "")
        .into_iter()
        .skip(2)
    {
        if line.starts_with("@@") {
            continue;
        }
        let style = if line.starts_with('+') {
            DIFF_ADD
        } else if line.starts_with('-') {
            DIFF_REMOVE
        } else {
            DIFF_CONTEXT
        };
        body.append(&format!("{line}\n"), Some(style));
    }
    // `LeftRail(body, accent) if body else None` — and an empty `Text` is falsy.
    if body.is_empty() {
        return None;
    }
    Some(Renderable::LeftRail {
        child: Box::new(Renderable::Text(body)),
        style: accent,
        glyph: "▎ ",
    })
}

/// `_tool_key_arg`: the first display-worthy attribute, home-collapsed.
///
/// **`name`, `id` and `is_error` are skipped and the first survivor wins** — not the
/// first *path-like* one. A tool whose schema lists something else first shows that
/// instead, and reproducing the order is the point.
fn tool_key_argument(attributes: &[(String, String)], home: &str) -> Option<String> {
    attributes
        .iter()
        .find(|(key, _)| !matches!(key.as_str(), "name" | "id" | "is_error"))
        .map(|(_, value)| crate::search_views::collapse_home(value, home))
}

/// `_tool_input_by_id`: every tool-use id mapped to its raw input, so a result can
/// find the call it belongs to.
///
/// **Built from the messages being *displayed*, and that is not the same scope the
/// tool *name* is resolved at.** Python builds this inside `build_messages_group`,
/// which receives the display subset, while a result's name comes from
/// `_build_tool_id_map(hit.messages)` over every message in the hit. So under a search
/// that is not `--full`, a `Read` result whose call did not match resolves the name
/// `Read` and finds **no input**, and falls through to its fenced body.
///
/// **That reads as a bug and is the product's behaviour.** A port that builds this map
/// from the whole hit renders a line-numbered gutter where the product renders a
/// fence, which nobody reports because it looks better.
fn tool_input_by_id(messages: &[Message]) -> HashMap<&str, &Value> {
    let mut map = HashMap::new();
    for message in messages {
        for tool in &message.tools {
            if let Tool::Use(use_) = tool
                && let Some(id) = use_.id.as_deref()
            {
                map.insert(id, &use_.input);
            }
        }
    }
    map
}

/// What a tool part carries beyond its attributes and body, which is what the two
/// richer bodies need. Python keeps these on `ToolParts` itself.
struct ToolFacts<'a> {
    name: String,
    attributes: Vec<(String, String)>,
    content: Option<String>,
    is_error: bool,
    is_result: bool,
    /// The raw tool-use input, for `Edit`'s diff. `None` for a result.
    input: Option<&'a Value>,
    /// The result's body before it is fenced, for `Read`'s gutter. `None` for a use.
    output_text: Option<String>,
    tool_use_id: Option<&'a str>,
}

fn tool_facts<'a>(part: &ToolPart<'a>) -> ToolFacts<'a> {
    match part {
        ToolPart::Real(Tool::Use(use_)) => {
            let parts = crate::codecs::tool_use_parts(use_)
                .expect("a projected tool's input is already valid JSON");
            ToolFacts {
                name: use_.name.clone(),
                attributes: parts.attributes,
                content: parts.content,
                is_error: false,
                is_result: false,
                // `input_data if isinstance(input_data, dict) else None`.
                input: use_.input.is_object().then_some(&use_.input),
                output_text: None,
                tool_use_id: use_.id.as_deref(),
            }
        }
        ToolPart::Real(Tool::Result(result)) => {
            let parts = crate::codecs::tool_result_parts(result);
            // `parts.name or <the name attribute> or "Tool"`. **A present-but-empty
            // name is `Tool`, not the empty string** — `name` is falsy, and
            // `tool_result_parts` writes no `name` attribute for it either.
            let name = result
                .name
                .clone()
                .filter(|value| !value.is_empty())
                .unwrap_or_else(|| "Tool".to_string());
            ToolFacts {
                name,
                attributes: parts.attributes,
                content: parts.content,
                is_error: result.is_error,
                is_result: true,
                input: None,
                output_text: parts.output_text,
                tool_use_id: result.tool_use_id.as_deref(),
            }
        }
        // The plan is a tool part carrying a synthesized `ExitPlanMode` input, which
        // is why it has no second renderer.
        ToolPart::ExitPlanMode(plan) => ToolFacts {
            name: "ExitPlanMode".to_string(),
            attributes: vec![("name".to_string(), "ExitPlanMode".to_string())],
            content: Some(plan.to_string()),
            is_error: false,
            is_result: false,
            input: None,
            output_text: None,
            tool_use_id: None,
        },
    }
}

/// `_tool_body_renderable`: the richest body a tool has — an `Edit` diff, a `Read`
/// gutter, or its fenced content.
///
/// **The order is the specification.** `Edit` is decided before anything else and
/// returns whatever the diff gives, including nothing, so an `Edit` whose two strings
/// are equal has no body rather than a fenced one.
fn tool_body_renderable(
    facts: &ToolFacts,
    accent: Style,
    input_by_id: &HashMap<&str, &Value>,
) -> Option<Renderable> {
    if facts.name == "Edit"
        && let Some(input) = facts.input.filter(|value| crate::model::value_is_truthy(value))
    {
        return edit_diff_renderable(input, accent);
    }
    // `_read_output_renderable`, gated on all five conditions Python gates it on. The
    // `file_path` comes from the call this result belongs to, and that lookup is over
    // the **displayed** messages — see `tool_input_by_id`.
    if facts.is_result
        && !facts.is_error
        && facts.name == "Read"
        && let Some(output_text) = facts.output_text.as_deref()
        && let Some(input) = facts.tool_use_id.and_then(|id| input_by_id.get(id))
        && let Some(file_path) = input
            .get("file_path")
            .and_then(Value::as_str)
            .filter(|value| !value.is_empty())
    {
        let (code, start_line) = strip_read_line_numbers(output_text);
        let lexer = read_lexer(file_path, &code);
        return Some(Renderable::LeftRail {
            child: Box::new(Renderable::ReadOutput { code, lexer, start_line }),
            style: accent,
            glyph: "▎ ",
        });
    }
    facts
        .content
        .clone()
        .filter(|value| !value.is_empty())
        .map(|markup| Renderable::LeftRail {
            child: Box::new(Renderable::Markdown { markup, highlight: true }),
            style: accent,
            glyph: "▎ ",
        })
}

/// A tool part as renderables: a header, then a coloured rail around its body.
///
/// `result_label` is `_tool_result_label`'s answer for the message this part belongs
/// to — `"output"` when the whole visible message is `Bash` results, and it replaces
/// the tool's own name in the header rather than sitting beside it.
fn tool_renderables(
    part: &ToolPart,
    home: &str,
    input_by_id: &HashMap<&str, &Value>,
    result_label: Option<&str>,
) -> Vec<Renderable> {
    let facts = tool_facts(part);

    let accent = if facts.is_error {
        TOOL_ERROR
    } else if facts.is_result {
        TOOL_RESULT
    } else if facts.name == "AdditionalContext" {
        TOOL_ADDITIONAL_CONTEXT
    } else {
        TOOL_CALL
    };

    // **The marker keeps `Text`'s default `end`**, so the header closes its own line
    // and the rail starts on the next. Rich's `render_tool_rich` builds a plain
    // `Text()` here, and clearing the end merges the two.
    let mut marker = RichText::new();
    marker.append(if facts.is_result { "⎿ " } else { "⏺ " }, Some(accent));
    let label = match result_label {
        Some(label) if facts.is_result && !label.is_empty() => label,
        _ => &facts.name,
    };
    marker.append(label, Some(accent));
    if facts.is_error {
        marker.append("  ·  error", Some(TOOL_ERROR));
    }

    let mut out: Vec<Renderable> = Vec::new();
    match tool_key_argument(&facts.attributes, home) {
        Some(argument) => out.push(Renderable::ToolHeader { marker, argument }),
        None => out.push(Renderable::Text(marker)),
    }
    out.extend(tool_body_renderable(&facts, accent, input_by_id));
    out
}

/// A message's visible parts as renderables — the body, without its header.
///
/// `home` is what `collapse_home` shortens a tool's path argument against. Python
/// reads `Path.home()` inside the helper; it is a parameter here because a renderer
/// that reads the environment cannot be gated at two different homes.
pub fn message_content_renderables(
    parts: &[Part],
    home: &str,
    input_by_id: &HashMap<&str, &Value>,
    result_label: Option<&str>,
) -> Vec<Renderable> {
    let mut out: Vec<Renderable> = Vec::new();
    for part in parts {
        if !out.is_empty() {
            out.push(Renderable::Text(RichText::new()));
        }
        match part {
            Part::Text(text) => out.push(Renderable::Markdown {
                markup: escape_tag_like(text),
                highlight: true,
            }),
            Part::Thinking(text) => {
                out.push(styled_text("✻ thinking", meta_style()));
                out.push(Renderable::LeftRail {
                    child: Box::new(styled_text(text, DIM_ITALIC)),
                    style: meta_style(),
                    glyph: "▎ ",
                });
            }
            Part::SubagentTask(text) => {
                out.push(styled_text("✻ subagent task", meta_style()));
                out.push(Renderable::LeftRail {
                    child: Box::new(styled_text(text, ITALIC)),
                    style: meta_style(),
                    glyph: "▎ ",
                });
            }
            Part::Tool(tool) => {
                out.extend(tool_renderables(tool, home, input_by_id, result_label))
            }
        }
    }
    out
}

/// The inline body of a conversation panel: every message as a badge over its
/// parts, with a `---` rule between messages.
pub fn messages_group<'a>(
    messages: &'a [Message],
    conversation_tag: Option<&str>,
    home: &str,
) -> Vec<Renderable> {
    // Built once over the messages being displayed, exactly where
    // `build_messages_group` builds it. See `tool_input_by_id` for why that scope is
    // not the one a result's name is resolved at.
    let input_by_id = tool_input_by_id(messages);
    let mut out: Vec<Renderable> = Vec::new();
    for (ordinal, message) in messages.iter().enumerate() {
        let parts = visible_parts(message);
        if parts.is_empty() {
            continue;
        }
        // Python separates on the **enumerate index**, not on whether anything was
        // emitted before, so a first message with no visible parts still leaves the
        // rule above the second.
        if ordinal > 0 {
            out.push(Renderable::Markdown { markup: "---".to_string(), highlight: false });
        }
        let _ = &messages;
        out.push(Renderable::Text(header_badge(message, &parts, conversation_tag)));
        out.push(Renderable::Text(RichText::new()));
        // `_tool_result_label`: a visible message that is only `Bash` results labels
        // every one of them `output` rather than by name.
        let result_label = is_bash_result_message(message, &parts).then_some("output");
        out.extend(message_content_renderables(&parts, home, &input_by_id, result_label));
    }
    out
}

/// The panel's body: one `Vec<Segment>` per line, ready for `panel_lines`.
pub fn message_body_lines(
    messages: &[Message],
    width: usize,
    context: &BodyContext,
) -> Vec<Vec<Segment>> {
    let options = RenderOptions::new(context.metrics);
    let group = messages_group(messages, context.conversation_tag, context.home);
    let mut segments: Vec<Segment> = Vec::new();
    for renderable in &group {
        segments.extend(renderable.render(width, &options, context));
    }
    let lines = split_and_crop_lines(&segments, width, None, false, context.metrics);
    // **The body carries this guarantee explicitly rather than by luck.** Every
    // path here expands tabs before a segment exists — `RichText::wrap` at eight
    // cells for text, `str.expandtabs(4)` in characters for a code block — and the
    // glyphs this module writes directly carry none. `search_views::render_line`
    // expands tabs too, and it would start its column count at zero where a body
    // line actually begins two columns in, after `│ `. So a surviving tab would
    // land its stops two columns off, silently.
    debug_assert!(
        !lines
            .iter()
            .flatten()
            .any(|segment| segment.text.contains('\t')),
        "a tab survived into a rendered body line; the frame would expand it from \
         the wrong column origin"
    );
    lines
}

#[cfg(test)]
mod body_oracle_tests {
    use super::*;
    use crate::search_query::Regex;
    use crate::visibility::ConversationFlags;
    use serde_json::Value;
    use std::collections::BTreeSet;
    use std::path::{Path, PathBuf};

    pub(super) fn oracle() -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/message-renderer/body-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("the body oracle is missing at {}: {error}", path.display())
        });
        serde_json::from_slice(&bytes).expect("the body oracle is valid JSON")
    }

    /// The synthetic pool the recorder used. Neither path has to exist: provider
    /// classification is a pure function of the two.
    pub(super) const HOME: &str = "/tmp/ch-body-oracle-home";
    pub(super) const SESSION: &str =
        "/tmp/ch-body-oracle-home/.claude/projects/bodyproj/aaaaaaaa-1111-4111-8111-aaaaaaaaaa01.jsonl";

    fn flags_from(record: &Value) -> ConversationFlags {
        let mut flags = ConversationFlags::default();
        if record["flags"]["show_thinking"].as_bool() == Some(true) {
            flags.show_thinking = true;
        }
        if record["flags"]["show_tools"].as_bool() == Some(true) {
            flags.show_tools = crate::tool_filter::ToolVisibility::All(true);
        }
        flags
    }

    /// Cases whose difference from Rich is a **body that is not built yet**.
    ///
    /// **It is empty, and both entries left it by being built.** `tool-edit-diff` left
    /// when the vendored `difflib` landed; the two `Read` cases entered it the moment
    /// the recorder was corrected — they had been passing for a reason unrelated to the
    /// gutter, because the recorder passed `tool_id_map=None` and no result could
    /// resolve its name — and `tool-read-result-promoted-extension` left when the
    /// gutter landed.
    ///
    /// **The set is asserted exact.** Building a body makes its case agree and the
    /// test says to remove it; any other case joining is a regression, not a gap.
    const KNOWN_UNBUILT_BODIES: [&str; 0] = [];

    /// Cases where the body **is** built and differs only because the file's language
    /// reaches a Pygments lexer this port does not carry a table for.
    ///
    /// **This is the 2026-08-30 ruling, not a gap.** A language Pygments knows and no
    /// table covers renders with complete geometry and plain unstyled code. Rich still
    /// runs the real lexer, so it emits one run per token where this emits one run for
    /// the whole line — **same text, same style, different segmentation**.
    ///
    /// `tool-read-result-unported-extension` is markdown, which is **37% of real `Read`
    /// calls and the single largest**, and is deliberately outside the seven promoted
    /// families. Half the extension work delivering no colour is the approved outcome.
    ///
    /// **The allowance is not a waiver.** A case here still has to match Rich once
    /// adjacent runs carrying the same style are merged, and it still has to *differ*
    /// before they are — otherwise the allowance is inert and would hide a real
    /// regression.
    const PLAIN_WHERE_THE_LEXER_IS_UNPORTED: [&str; 1] = ["tool-read-result-unported-extension"];

    /// The unported-language relaxation, in the ruling's own terms: **complete
    /// geometry and plain unstyled code**.
    ///
    /// A line is split at the end of the number column. Everything up to there — the
    /// rail glyph, the two-space lead and the number itself — is compared **exactly**,
    /// because it is geometry and it is this port's own. Everything after is compared
    /// by its **text and its background per character**, because Rich still runs the
    /// real lexer there and this renders plain: the block occupies the same cells with
    /// the same ground, and the colours inside it differ.
    ///
    /// **Bold and italic are excluded from the tail too**, and deliberately. Monokai
    /// paints some markdown tokens bold, and "plain unstyled code" gives all of it the
    /// one `Token.Text` style. Including them would fail every heading.
    pub(super) fn relaxed(line: &[Segment], gutter_cells: usize) -> (Vec<String>, String, Vec<Option<StyleColor>>) {
        let mut head: Vec<String> = Vec::new();
        let mut text = String::new();
        let mut grounds: Vec<Option<StyleColor>> = Vec::new();
        let mut consumed = 0usize;
        for segment in line {
            let length = segment.text.chars().count();
            if consumed < gutter_cells {
                head.push(super::markdown_oracle_tests::describe(segment));
                consumed += length;
                continue;
            }
            text.push_str(&segment.text);
            let ground = segment.style.and_then(|style| style.background);
            grounds.extend(std::iter::repeat_n(ground, length));
        }
        (head, text, grounds)
    }

    /// The same shape, read out of a recorded line.
    pub(super) fn relaxed_recorded(
        line: &Value,
        gutter_cells: usize,
    ) -> (Vec<String>, String, Vec<Option<StyleColor>>) {
        let mut head: Vec<String> = Vec::new();
        let mut text = String::new();
        let mut grounds: Vec<Option<StyleColor>> = Vec::new();
        let mut consumed = 0usize;
        for segment in line.as_array().expect("a recorded line carries segments") {
            let body = segment["t"].as_str().unwrap_or_default();
            let length = body.chars().count();
            if consumed < gutter_cells {
                head.push(super::markdown_oracle_tests::describe_recorded(segment));
                consumed += length;
                continue;
            }
            text.push_str(body);
            let ground = segment["s"]["bg"]["triplet"].as_array().map(|values| {
                let channel = |index: usize| values[index].as_u64().unwrap_or(0) as u8;
                StyleColor::Triplet(ColorTriplet {
                    red: channel(0),
                    green: channel(1),
                    blue: channel(2),
                })
            });
            grounds.extend(std::iter::repeat_n(ground, length));
        }
        (head, text, grounds)
    }

    /// How many cells a `Read` body's rail glyph and number column occupy, **read out
    /// of the recording** rather than recomputed.
    ///
    /// Recomputing it here would take the width from the implementation under test, so
    /// a wrong column width would move the split on both sides and cancel itself out.
    /// The number column is found by its colour: `#656660`, the blend
    /// `_get_line_numbers_color` produces, which nothing else in a body carries.
    pub(super) fn recorded_gutter_cells(lines: &Value) -> Option<usize> {
        for line in lines.as_array()? {
            let mut cells = 0usize;
            for segment in line.as_array()? {
                cells += segment["t"].as_str().unwrap_or_default().chars().count();
                let triplet = segment["s"]["fg"]["triplet"].as_array();
                if triplet.is_some_and(|values| {
                    values.iter().map(|value| value.as_u64().unwrap_or(0)).eq([0x65, 0x66, 0x60])
                }) {
                    return Some(cells);
                }
            }
        }
        None
    }

    #[test]
    fn every_recorded_message_body_reproduces() {
        let oracle = oracle();
        let metrics = CellMetrics::from_environment();
        let mut compared = 0usize;
        let mut failures: Vec<(String, String)> = Vec::new();
        let mut inert_allowances: Vec<String> = Vec::new();

        for case in oracle["cases"].as_array().expect("the oracle carries cases") {
            let identifier = case["id"].as_str().unwrap_or("?");
            let width = case["width"].as_u64().expect("a width") as usize;
            let content = case["jsonl"].as_str().expect("a case carries its session");
            let flags = flags_from(case);
            let scanned = crate::search_confirm::scan_session(
                Path::new(SESSION),
                content,
                &flags,
                Path::new(HOME),
            )
            .expect("the recorded session decodes");

            let regex = case["highlight"].as_str().map(|pattern| {
                Regex::compile(pattern, case["ignorecase"].as_bool().unwrap_or(false))
                    .expect("the recorded highlight pattern compiles")
            });
            let context = BodyContext {
                metrics: &metrics,
                highlight: regex.as_ref(),
                conversation_tag: Some("aaaaaaaa"),
                home: HOME,
            };
            // **The product projects before it renders**, and the recorder does the
            // same by handing `iter_visible_parts` the flags and the id map. A gate
            // that renders the raw parse instead sees no shortening and no resolved
            // result name, and four tool behaviours become unreachable at once.
            let tool_id_map = crate::visibility::build_tool_id_map(&scanned.messages);
            let progressive = crate::visibility::ProgressiveAssignment::compute(
                &scanned.messages,
                &flags,
                Some(&tool_id_map),
            );
            let projected: Vec<crate::model::Message> = scanned
                .messages
                .iter()
                .enumerate()
                .map(|(index, message)| {
                    crate::visibility::visible_message(
                        message,
                        &flags,
                        Some(&tool_id_map),
                        &progressive,
                        index,
                    )
                })
                .collect();
            let rendered = message_body_lines(&projected, width, &context);
            compared += 1;

            let expected = super::markdown_oracle_tests::recorded_lines(case);
            let actual: Vec<Vec<String>> = rendered
                .iter()
                .map(|line| line.iter().map(super::markdown_oracle_tests::describe).collect())
                .collect();
            if actual == expected {
                if PLAIN_WHERE_THE_LEXER_IS_UNPORTED.contains(&identifier) {
                    inert_allowances.push(identifier.to_string());
                }
                continue;
            }
            // The ruled relaxation: an unported language keeps the geometry and loses
            // the colours inside the block.
            if PLAIN_WHERE_THE_LEXER_IS_UNPORTED.contains(&identifier) {
                let cells = recorded_gutter_cells(&case["lines"]).unwrap_or_else(|| {
                    panic!(
                        "{identifier} is allowed the unported-language relaxation but \
                         its recording carries no line-number column, so the relaxation \
                         cannot find where geometry ends and colour begins."
                    )
                });
                let recorded = case["lines"].as_array().expect("recorded lines");
                let agrees = rendered.len() == recorded.len()
                    && rendered.iter().zip(recorded).all(|(ours, theirs)| {
                        relaxed(ours, cells) == relaxed_recorded(theirs, cells)
                    });
                if agrees {
                    continue;
                }
            }
            let mut report = format!("{identifier} @ {width}\n");
            if let Some(note) = case["note"].as_str() {
                report.push_str(&format!("  note: {note}\n"));
            }
            for index in 0..expected.len().max(actual.len()) {
                let want = expected.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let got = actual.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let marker = if want == got { "  " } else { "->" };
                report.push_str(&format!("  {marker} rich {want}\n     ours {got}\n"));
            }
            failures.push((identifier.to_string(), report));
        }

        assert!(
            compared >= 60,
            "Only {compared} body cases were compared. A shrunken corpus passes vacuously."
        );
        assert!(
            inert_allowances.is_empty(),
            "{inert_allowances:?} matched Rich exactly, so their entry in \
             PLAIN_WHERE_THE_LEXER_IS_UNPORTED is allowing nothing. **An inert \
             allowance is worse than none**: it reads as a known divergence while \
             hiding whatever divergence appears there next. Drop the name."
        );
        let (known, unexpected): (Vec<_>, Vec<_>) = failures
            .into_iter()
            .partition(|(identifier, _)| KNOWN_UNBUILT_BODIES.contains(&identifier.as_str()));
        assert!(
            unexpected.is_empty(),
            "{} of {compared} recorded message bodies differ from Rich:\n\n{}",
            unexpected.len(),
            unexpected
                .iter()
                .map(|(_, report)| report.as_str())
                .take(4)
                .collect::<Vec<_>>()
                .join("\n")
        );
        let still_differing: BTreeSet<&str> =
            known.iter().map(|(identifier, _)| identifier.as_str()).collect();
        let expected: BTreeSet<&str> = KNOWN_UNBUILT_BODIES.into_iter().collect();
        assert_eq!(
            still_differing, expected,
            "The set of unbuilt bodies moved. **A case that stopped differing means \
             its body is now built** — drop it from KNOWN_UNBUILT_BODIES rather than \
             leaving a name that no longer refers to a gap."
        );
    }

    /// Nothing inside a left rail is highlighted, because no rail in the product
    /// is constructed with the regex. The corpus reaches that case, and this proves
    /// the recording still contains it — a port that paints a term inside a thinking
    /// block is *more helpful* and diverges.
    #[test]
    fn the_corpus_reaches_a_search_term_inside_an_unhighlighted_rail() {
        let oracle = oracle();
        let case = oracle["cases"]
            .as_array()
            .expect("cases")
            .iter()
            .find(|case| case["id"] == "highlight-not-painted-in-a-thinking-rail")
            .expect("the rail case is in the corpus");
        let lines = super::markdown_oracle_tests::recorded_lines(case);
        let painted = |line: &Vec<String>| {
            line.iter()
                .any(|entry| entry.contains("\"needle\"") && entry.contains("bg=#e6b450"))
        };
        let carries_term = |line: &Vec<String>| {
            line.iter().any(|entry| entry.contains("needle"))
        };
        let rail_lines: Vec<&Vec<String>> = lines
            .iter()
            .filter(|line| line.first().is_some_and(|entry| entry.contains("▎ ")))
            .collect();
        assert!(
            lines.iter().any(painted),
            "The visible text must be painted, or the fixture proves nothing."
        );
        assert!(
            rail_lines.iter().any(|line| carries_term(line)),
            "No rail line carries the term any more; the case has stopped reaching \
             the rail and the rule is untested."
        );
        assert!(
            !rail_lines.iter().any(|line| painted(line)),
            "A rail line is painted. `_text_renderable` is the only builder of a \
             `HighlightedMarkdown` and it is reached from the message text alone, so \
             a painted rail is a divergence — and it is one nobody reports, because \
             a visible search term looks like an improvement."
        );
    }

    /// The highlight is painted per rendered segment, so a term straddling a style
    /// boundary is left alone. The corpus reaches that case, and this proves the
    /// gate would catch the improvement.
    #[test]
    fn the_corpus_reaches_a_match_split_across_a_style_boundary() {
        let oracle = oracle();
        let case = oracle["cases"]
            .as_array()
            .expect("cases")
            .iter()
            .find(|case| case["id"] == "highlight-across-style-boundary")
            .expect("the split-match case is in the corpus");
        let recorded: Vec<String> = super::markdown_oracle_tests::recorded_lines(case)
            .into_iter()
            .flatten()
            .collect();
        let painted = |needle: &str| {
            recorded
                .iter()
                .any(|entry| entry.contains(needle) && entry.contains("bg=#e6b450"))
        };
        assert!(
            painted("\"hello\""),
            "The whole occurrence must be painted, or the fixture proves nothing."
        );
        assert!(
            !painted("\"hel\""),
            "The split occurrence must stay unpainted. If this fails the product has \
             changed, or the recording did — and a port that paints it is *better* and \
             diverges."
        );
    }
}

#[cfg(test)]
mod highlight_falsification_tests {
    use super::*;
    use crate::search_query::Regex;
    use crate::visibility::ConversationFlags;
    use std::path::Path;

    /// The named mutation for preserve-because-wrong item ten: paint the highlight
    /// over a line's **assembled** text and split the runs back out afterwards.
    ///
    /// This is the implementation everyone reaches for, it is genuinely more useful,
    /// and it diverges — a term straddling a style boundary becomes painted where the
    /// product leaves it alone. A fixture built from unformatted text cannot tell the
    /// two apart, so this proves the corpus reaches formatted text.
    fn paint_over_assembled(lines: &mut Vec<Vec<Segment>>, regex: &Regex) {
        let highlight = crate::search_views::theme_style("search.match");
        for line in lines.iter_mut() {
            let assembled: String = line.iter().map(|segment| segment.text.as_str()).collect();
            let Ok(spans) = regex.find_all(&assembled) else {
                continue;
            };
            if spans.is_empty() {
                continue;
            }
            let mut painted: Vec<Segment> = Vec::new();
            let mut offset = 0usize;
            for segment in line.drain(..) {
                let characters: Vec<char> = segment.text.chars().collect();
                let start = offset;
                offset += characters.len();
                let mut cursor = 0usize;
                for (span_start, span_end) in &spans {
                    let low = (*span_start).max(start).saturating_sub(start);
                    let high = (*span_end).min(offset).saturating_sub(start);
                    if *span_start >= offset || *span_end <= start || low >= high {
                        continue;
                    }
                    if low > cursor {
                        painted.push(Segment {
                            text: characters[cursor..low].iter().collect(),
                            style: segment.style,
                            link: segment.link.clone(),
                        });
                    }
                    painted.push(Segment {
                        text: characters[low..high].iter().collect(),
                        style: Some(match segment.style {
                            Some(style) => style.over(highlight),
                            None => highlight,
                        }),
                        link: segment.link.clone(),
                    });
                    cursor = high;
                }
                if cursor < characters.len() {
                    painted.push(Segment {
                        text: characters[cursor..].iter().collect(),
                        style: segment.style,
                        link: segment.link.clone(),
                    });
                }
            }
            *line = painted;
        }
    }

    #[test]
    fn the_body_corpus_catches_highlighting_over_assembled_text() {
        let oracle = super::body_oracle_tests::oracle();
        let metrics = CellMetrics::from_environment();
        let mut caught = 0usize;
        let mut highlighted_cases = 0usize;

        for case in oracle["cases"].as_array().expect("cases") {
            let Some(pattern) = case["highlight"].as_str() else {
                continue;
            };
            highlighted_cases += 1;
            let width = case["width"].as_u64().expect("a width") as usize;
            let content = case["jsonl"].as_str().expect("a session");
            let mut flags = ConversationFlags::default();
            if case["flags"]["show_thinking"].as_bool() == Some(true) {
                flags.show_thinking = true;
            }
            let scanned = crate::search_confirm::scan_session(
                Path::new(super::body_oracle_tests::SESSION),
                content,
                &flags,
                Path::new(super::body_oracle_tests::HOME),
            )
            .expect("the recorded session decodes");
            let regex = Regex::compile(pattern, case["ignorecase"].as_bool().unwrap_or(false))
                .expect("the recorded pattern compiles");
            let context = BodyContext {
                metrics: &metrics,
                highlight: Some(&regex),
                conversation_tag: Some("aaaaaaaa"),
                home: super::body_oracle_tests::HOME,
            };
            let mut rendered = message_body_lines(&scanned.messages, width, &context);
            let faithful: Vec<Vec<String>> = rendered
                .iter()
                .map(|line| line.iter().map(super::markdown_oracle_tests::describe).collect())
                .collect();
            paint_over_assembled(&mut rendered, &regex);
            let mutated: Vec<Vec<String>> = rendered
                .iter()
                .map(|line| line.iter().map(super::markdown_oracle_tests::describe).collect())
                .collect();
            if mutated != faithful {
                caught += 1;
            }
        }

        assert!(
            highlighted_cases >= 8,
            "Only {highlighted_cases} highlighted cases are recorded; the corpus is too \
             thin to say anything about the painter."
        );
        assert!(
            caught > 0,
            "The corpus no longer separates per-segment painting from painting over \
             assembled text. That means no recorded case has a match straddling a style \
             boundary any more — and the wrong-and-preserved behaviour is untested."
        );
    }
}

#[cfg(test)]
mod wrap_tests {
    use super::*;

    /// `divide_line`'s remaining-space test is **signed**, and the negative case is
    /// reachable. Answers taken from `rich._wrap.divide_line` directly.
    ///
    /// A word carries the whitespace to its right, so a word that fits can still
    /// leave the cursor past the width. The next word then sees a negative
    /// remaining space — which fails `>= word_length` — where a floor at zero
    /// succeeds for a word measuring zero cells. `\u{200b}` is not whitespace to
    /// either language, so it forms a word of no width at all.
    #[test]
    fn a_zero_width_word_after_an_overhanging_one_breaks_where_rich_breaks() {
        let metrics = CellMetrics::for_version(None);
        assert_eq!(divide_line("abc   \u{200b}", 5, true, &metrics), vec![6]);
        assert_eq!(divide_line("abc   \u{200b}\u{200b}", 5, true, &metrics), vec![6]);
        assert_eq!(divide_line("ab \u{200b} cd", 3, true, &metrics), vec![5]);
    }

    /// The falsification for the above: the floor-at-zero version must disagree, or
    /// the case has stopped reaching the branch it was written for.
    #[test]
    fn the_saturating_version_still_gets_it_wrong() {
        fn saturating_divide_line(
            text: &str,
            width: usize,
            metrics: &CellMetrics,
        ) -> Vec<usize> {
            let characters: Vec<char> = text.chars().collect();
            let mut breaks: Vec<usize> = Vec::new();
            let mut cell_offset = 0usize;
            for (start, _end, word) in words(&characters) {
                let trimmed: String = word.trim_end().to_string();
                let word_length = metrics.cell_len(&trimmed);
                if width.saturating_sub(cell_offset) >= word_length {
                    cell_offset += metrics.cell_len(&word);
                    continue;
                }
                if word_length <= width && cell_offset > 0 && start > 0 {
                    breaks.push(start);
                    cell_offset = metrics.cell_len(&word);
                }
            }
            breaks
        }
        let metrics = CellMetrics::for_version(None);
        assert_eq!(saturating_divide_line("abc   \u{200b}", 5, &metrics), Vec::<usize>::new());
        assert_eq!(divide_line("abc   \u{200b}", 5, true, &metrics), vec![6]);
    }
}

// ---------------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------------

/// Rich's `Measurement`: the narrowest and widest a renderable wants to be.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Measurement {
    minimum: usize,
    maximum: usize,
}

impl Measurement {
    fn with_maximum(self, width: usize) -> Measurement {
        Measurement {
            minimum: self.minimum.min(width),
            maximum: self.maximum.min(width),
        }
    }

    fn normalize(self) -> Measurement {
        let minimum = self.minimum.min(self.maximum);
        Measurement { minimum, maximum: minimum.max(self.maximum) }
    }
}

/// Rich's `Text.__rich_measure__`: widest line, and widest single word.
fn measure_text(text: &RichText, metrics: &CellMetrics) -> Measurement {
    let plain = text.plain();
    let lines: Vec<&str> = plain.lines().collect();
    let maximum = lines
        .iter()
        .map(|line| metrics.cell_len(line))
        .max()
        .unwrap_or(0);
    let minimum = plain
        .split_whitespace()
        .map(|word| metrics.cell_len(word))
        .max()
        .unwrap_or(maximum);
    Measurement { minimum, maximum }
}

/// The padding a markdown table's cell carries, in cells.
///
/// `padding=(0, 1)` with `collapse_padding` and without `pad_edge` reduces to: no
/// left padding anywhere, one column of right padding except on the last column,
/// and no vertical padding at all. Derived from `_get_padding_width` rather than
/// assumed, because the collapse reads the **already-zeroed** left value when it
/// computes the right one.
fn table_padding_width(column_index: usize, column_count: usize) -> usize {
    if column_index + 1 == column_count { 0 } else { 1 }
}

/// `Measurement.get` over one padded cell.
fn measure_cell(
    text: &RichText,
    padding_width: usize,
    max_width: usize,
    metrics: &CellMetrics,
) -> Measurement {
    if max_width < 1 || max_width.saturating_sub(padding_width) < 1 {
        return Measurement { minimum: 0, maximum: 0 };
    }
    let inner = measure_text(text, metrics)
        .with_maximum(max_width - padding_width)
        .normalize();
    Measurement {
        minimum: inner.minimum + padding_width,
        maximum: inner.maximum + padding_width,
    }
    .with_maximum(max_width)
    .normalize()
}

/// Rich's `_measure_column` for a flexible column with no width constraints.
fn measure_column(
    cells: &[&RichText],
    padding_width: usize,
    max_width: usize,
    metrics: &CellMetrics,
) -> Measurement {
    if max_width < 1 {
        return Measurement { minimum: 0, maximum: 0 };
    }
    let mut minimums: Vec<usize> = Vec::new();
    let mut maximums: Vec<usize> = Vec::new();
    for text in cells {
        let measured = measure_cell(text, padding_width, max_width, metrics);
        minimums.push(measured.minimum);
        maximums.push(measured.maximum);
    }
    Measurement {
        minimum: minimums.iter().copied().max().unwrap_or(1),
        maximum: maximums.iter().copied().max().unwrap_or(max_width),
    }
    .with_maximum(max_width)
}

/// Rich's `_ratio.ratio_reduce`.
fn ratio_reduce(total: usize, ratios: &[usize], maximums: &[usize], values: &[usize]) -> Vec<usize> {
    let ratios: Vec<usize> = ratios
        .iter()
        .zip(maximums)
        .map(|(ratio, maximum)| if *maximum > 0 { *ratio } else { 0 })
        .collect();
    let mut total_ratio: usize = ratios.iter().sum();
    if total_ratio == 0 {
        return values.to_vec();
    }
    let mut total_remaining = total as i64;
    let mut result: Vec<usize> = Vec::with_capacity(values.len());
    for ((ratio, maximum), value) in ratios.iter().zip(maximums).zip(values) {
        if *ratio > 0 && total_ratio > 0 {
            // Python's `round` breaks ties to even, and the division is float.
            let share = (*ratio as f64) * (total_remaining as f64) / (total_ratio as f64);
            let distributed = (*maximum as i64).min(share.round_ties_even() as i64);
            result.push((*value as i64 - distributed).max(0) as usize);
            total_remaining -= distributed;
            total_ratio -= ratio;
        } else {
            result.push(*value);
        }
    }
    result
}

/// Rich's `Table._collapse_widths`: shave the widest wrapable column repeatedly.
fn collapse_widths(mut widths: Vec<usize>, wrapable: &[bool], max_width: usize) -> Vec<usize> {
    let mut total_width: usize = widths.iter().sum();
    let mut excess_width = total_width as i64 - max_width as i64;
    if !wrapable.iter().any(|allow| *allow) {
        return widths;
    }
    while total_width > 0 && excess_width > 0 {
        let max_column = widths
            .iter()
            .zip(wrapable)
            .filter(|(_, allow)| **allow)
            .map(|(width, _)| *width)
            .max()
            .unwrap_or(0);
        let second_max_column = widths
            .iter()
            .zip(wrapable)
            .map(|(width, allow)| if *allow && *width != max_column { *width } else { 0 })
            .max()
            .unwrap_or(0);
        let column_difference = max_column - second_max_column;
        let ratios: Vec<usize> = widths
            .iter()
            .zip(wrapable)
            .map(|(width, allow)| usize::from(*width == max_column && *allow))
            .collect();
        if !ratios.iter().any(|ratio| *ratio > 0) || column_difference == 0 {
            break;
        }
        let max_reduce = vec![(excess_width as usize).min(column_difference); widths.len()];
        widths = ratio_reduce(excess_width as usize, &ratios, &max_reduce, &widths);
        total_width = widths.iter().sum();
        excess_width = total_width as i64 - max_width as i64;
    }
    widths
}

/// `table.header` — Rich's default header style, applied to the whole header cell
/// including its padding. The heading text carries `markdown.table.header` on top,
/// whose `bold: false` **clears** this one over the text but not over the padding.
const TABLE_HEADER_CELL: Style = Style {
    bold: Some(true), dim: None, italic: None, underline: None,
    reverse: None, strike: None, foreground: None, background: None,
};

/// One row of `box.SIMPLE`, whose only non-blank characters are the header rule.
fn simple_box_row(widths: &[usize], head_rule: bool) -> String {
    let (horizontal, cross) = if head_rule { ('─', '─') } else { (' ', ' ') };
    let mut row = String::from(" ");
    for (index, width) in widths.iter().enumerate() {
        row.extend(std::iter::repeat_n(horizontal, *width));
        if index + 1 != widths.len() {
            row.push(cross);
        }
    }
    row.push(' ');
    row
}

/// One padded table cell, rendered to lines at its column's width.
fn render_table_cell(
    text: &RichText,
    width: usize,
    padding_width: usize,
    cell_style: Style,
    column_justify: Justify,
    options: &RenderOptions,
) -> Vec<Vec<Segment>> {
    // `Padding` expands to the width it is given, so the child renders at the
    // column width less the padding and is padded to it.
    let inner = width.saturating_sub(padding_width);
    let child_options = RenderOptions {
        justify: column_justify,
        overflow: Overflow::Ellipsis,
        no_wrap: options.no_wrap,
        tab_size: options.tab_size,
        metrics: options.metrics,
    };
    let mut segments: Vec<Segment> = Vec::new();
    if inner >= 1 {
        let child = text.to_segments(inner, &child_options);
        for line in split_and_crop_lines(&child, inner, None, true, options.metrics) {
            segments.extend(line);
            if padding_width > 0 {
                segments.push(Segment {
                    text: " ".repeat(padding_width),
                    style: None,
                    link: None,
                });
            }
            segments.push(Segment { text: "\n".to_string(), style: None, link: None });
        }
    }
    let styled = if cell_style == Style::inherit() {
        segments
    } else {
        apply_style(segments, cell_style)
    };
    let style = (cell_style != Style::inherit()).then_some(cell_style);
    split_and_crop_lines(&styled, width, style, true, options.metrics)
}

/// Rich's `Segment.set_shape`, plus the vertical alignment a table row applies.
fn shape_cell(
    mut lines: Vec<Vec<Segment>>,
    width: usize,
    height: usize,
    style: Option<Style>,
    align_bottom: bool,
    metrics: &CellMetrics,
) -> Vec<Vec<Segment>> {
    let blank = || {
        vec![Segment { text: " ".repeat(width), style, link: None }]
    };
    while lines.len() < height {
        if align_bottom {
            lines.insert(0, blank());
        } else {
            lines.push(blank());
        }
    }
    lines
        .into_iter()
        .take(height)
        .map(|line| adjust_line_length(&line, width, style, true, metrics))
        .collect()
}

/// Rich's `Table`, as `TableElement` configures it: `box.SIMPLE`, no edge padding,
/// collapsed padding, a header and no footer.
fn render_table(
    header: &[RichText],
    body: &[Vec<RichText>],
    width: usize,
    border: Style,
    options: &RenderOptions,
) -> Vec<Segment> {
    let column_count = header.len();
    if column_count == 0 {
        return vec![Segment { text: "\n".to_string(), style: None, link: None }];
    }
    let metrics = options.metrics;
    // `show_edge` contributes two columns and each divider one more.
    let extra_width = 2 + column_count - 1;
    let measure_width = width.saturating_sub(extra_width);

    let empty = RichText::new();
    let column_cells = |index: usize| -> Vec<&RichText> {
        let mut cells: Vec<&RichText> = vec![&header[index]];
        for row in body {
            cells.push(row.get(index).unwrap_or(&empty));
        }
        cells
    };

    let mut widths: Vec<usize> = (0..column_count)
        .map(|index| {
            let padding = table_padding_width(index, column_count);
            // `widths = [_range.maximum or 1 ...]` — a zero maximum becomes one.
            let maximum = measure_column(&column_cells(index), padding, measure_width, metrics)
                .maximum;
            if maximum == 0 { 1 } else { maximum }
        })
        .collect();

    let mut table_width: usize = widths.iter().sum();
    if table_width > measure_width {
        widths = collapse_widths(widths, &vec![true; column_count], measure_width);
        table_width = widths.iter().sum();
        if table_width > measure_width {
            let excess = table_width - measure_width;
            widths = ratio_reduce(excess, &vec![1; column_count], &widths.clone(), &widths);
        }
        // Re-measure at the reduced widths, and this time a zero maximum stays zero.
        widths = (0..column_count)
            .map(|index| {
                let padding = table_padding_width(index, column_count);
                measure_column(&column_cells(index), padding, widths[index], metrics).maximum
            })
            .collect();
    }

    let rows: Vec<(bool, Vec<&RichText>)> = std::iter::once((true, header.iter().collect()))
        .chain(body.iter().map(|row| {
            (
                false,
                (0..column_count)
                    .map(|index| row.get(index).unwrap_or(&empty))
                    .collect::<Vec<&RichText>>(),
            )
        }))
        .collect();

    let paint = |text: String| Segment { text, style: Some(border), link: None };
    let new_line = || Segment { text: "\n".to_string(), style: None, link: None };

    let mut out: Vec<Segment> = vec![paint(simple_box_row(&widths, false)), new_line()];

    for (row_index, (is_header, cells)) in rows.iter().enumerate() {
        let cell_style = if *is_header { TABLE_HEADER_CELL } else { Style::inherit() };
        let rendered: Vec<Vec<Vec<Segment>>> = cells
            .iter()
            .enumerate()
            .map(|(index, text)| {
                render_table_cell(
                    text,
                    widths[index],
                    table_padding_width(index, column_count),
                    cell_style,
                    Justify::Left,
                    options,
                )
            })
            .collect();
        let max_height = rendered.iter().map(Vec::len).max().unwrap_or(1).max(1);
        let style = (cell_style != Style::inherit()).then_some(cell_style);
        let shaped: Vec<Vec<Vec<Segment>>> = rendered
            .into_iter()
            .enumerate()
            .map(|(index, cell)| {
                shape_cell(cell, widths[index], max_height, style, *is_header, metrics)
            })
            .collect();

        for line_index in 0..max_height {
            out.push(paint(" ".to_string()));
            for (index, cell) in shaped.iter().enumerate() {
                out.extend(cell[line_index].iter().cloned());
                if index + 1 != column_count {
                    out.push(paint(" ".to_string()));
                }
            }
            out.push(paint(" ".to_string()));
            out.push(new_line());
        }
        if row_index == 0 {
            out.push(paint(simple_box_row(&widths, true)));
            out.push(new_line());
        }
    }

    out.push(paint(simple_box_row(&widths, false)));
    out.push(new_line());
    out
}

#[cfg(test)]
mod table_width_tests {
    use super::*;

    /// Both width algorithms against Rich's own answers.
    ///
    /// A corpus of tables that all fit gates the box drawing and nothing else, so
    /// these are pinned directly as well as being reached by the over-wide cases in
    /// the recorded corpus.
    #[test]
    fn the_width_algorithms_reproduce_richs_answers() {
        assert_eq!(collapse_widths(vec![10, 20, 30], &[true; 3], 40), vec![10, 15, 15]);
        assert_eq!(collapse_widths(vec![10, 20, 30], &[true; 3], 15), vec![5, 5, 5]);
        assert_eq!(collapse_widths(vec![5, 5, 5], &[true; 3], 6), vec![2, 2, 2]);
        assert_eq!(collapse_widths(vec![30, 3, 3], &[true; 3], 20), vec![14, 3, 3]);
        assert_eq!(collapse_widths(vec![12, 12], &[true; 2], 10), vec![5, 5]);
        assert_eq!(collapse_widths(vec![100], &[true], 7), vec![7]);

        assert_eq!(
            ratio_reduce(5, &[1, 1, 1], &[5, 5, 5], &[10, 20, 30]),
            vec![8, 18, 29]
        );
        assert_eq!(
            ratio_reduce(7, &[1, 0, 1], &[3, 3, 3], &[10, 20, 30]),
            vec![7, 20, 27]
        );
        assert_eq!(ratio_reduce(4, &[1, 1], &[2, 2], &[6, 6]), vec![4, 4]);
    }

    /// The recorded corpus must actually reach the collapse branch, or the table
    /// cases gate the box and the padding and leave both width algorithms untested.
    #[test]
    fn the_recorded_corpus_reaches_a_table_that_must_be_narrowed() {
        let oracle = super::markdown_oracle_tests::oracle();
        let metrics = CellMetrics::for_version(None);
        let mut narrowed = 0usize;
        for case in oracle["cases"].as_array().expect("cases") {
            let markup = case["markup"].as_str().expect("markup");
            let width = case["width"].as_u64().expect("a width") as usize;
            let tokens = markdown_tokens(markup);
            if !tokens.iter().any(|token| matches!(token, Token::TableOpen)) {
                continue;
            }
            // One column's widest cell alone exceeding the console is the cheapest
            // sufficient condition, and it needs no second copy of the algorithm.
            let widest = markup
                .lines()
                .filter(|line| line.starts_with('|'))
                .map(|line| metrics.cell_len(line))
                .max()
                .unwrap_or(0);
            if widest > width {
                narrowed += 1;
            }
        }
        assert!(
            narrowed >= 10,
            "Only {narrowed} recorded table records are wider than their console. \
             Below that the corpus exercises the box drawing and leaves \
             `collapse_widths` and `ratio_reduce` unreached."
        );
    }
}

// ---------------------------------------------------------------------------
// Fenced and indented code: the block's geometry
// ---------------------------------------------------------------------------

/// Monokai's background, which `Syntax` uses as its base style and as the style of
/// every pad it adds.
const SYNTAX_BACKGROUND: Style = Style {
    bold: None, dim: None, italic: None, underline: None, reverse: None, strike: None,
    foreground: None,
    background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
};

/// Monokai's `Token.Text`, which is every character of a block that reaches no
/// real lexer.
///
/// The three attributes are set to **false** rather than left unset, because
/// `PygmentsSyntaxTheme` builds every token style from the full Pygments dict. They
/// clear rather than inherit, which is invisible inside a fence and is the reason a
/// style attribute is three-valued.
const SYNTAX_TEXT: Style = Style {
    bold: Some(false), dim: None, italic: Some(false), underline: Some(false),
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#f8f8f2"))),
    background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
};

/// Python's `str.expandtabs`, which counts **characters** and resets at a line
/// break.
///
/// Not `Text.expand_tabs`, which counts cells: `Syntax._process_code` calls the
/// string method before any `Text` exists. Two tab expansions with different
/// counting units, in one render path.
fn expand_tabs_by_characters(text: &str, tab_size: usize) -> String {
    let mut out = String::with_capacity(text.len());
    let mut column = 0usize;
    for character in text.chars() {
        match character {
            '\t' => {
                let spaces = if tab_size == 0 { 0 } else { tab_size - column % tab_size };
                out.extend(std::iter::repeat_n(' ', spaces));
                column += spaces;
            }
            '\n' | '\r' => {
                out.push(character);
                column = 0;
            }
            _ => {
                out.push(character);
                column += 1;
            }
        }
    }
    out
}

/// Rich's `Padding`, expanded to the width it is given.
fn render_padding(
    child: Vec<Segment>,
    width: usize,
    pad: (usize, usize, usize, usize),
    style: Style,
    options: &RenderOptions,
) -> Vec<Segment> {
    let (top, right, bottom, left) = pad;
    let inner = width.saturating_sub(left + right);
    let lines = split_and_crop_lines(&child, inner, Some(style), true, options.metrics);
    let blank = || Segment {
        text: format!("{}\n", " ".repeat(width)),
        style: Some(style),
        link: None,
    };
    let mut out: Vec<Segment> = Vec::new();
    for _ in 0..top {
        out.push(blank());
    }
    for line in lines {
        if left > 0 {
            out.push(Segment { text: " ".repeat(left), style: Some(style), link: None });
        }
        out.extend(line);
        if right > 0 {
            out.push(Segment { text: " ".repeat(right), style: Some(style), link: None });
        }
        out.push(Segment { text: "\n".to_string(), style: None, link: None });
    }
    for _ in 0..bottom {
        out.push(blank());
    }
    out
}

/// A code block: geometry, background, and one foreground per token.
///
/// `CodeBlock` builds `Syntax(code, lexer, theme="monokai", word_wrap=True,
/// padding=1)`. When Pygments knows no such language, `Syntax` falls back to its
/// plain-text lexer, which emits the whole block as one `Token.Text` — so the
/// rendering is exact with no lexer written at all. Measured over 3,000 real fenced
/// blocks: 22.3% of them, and 39.6% of fenced characters.
///
/// **A promoted family changes only which token each run carries.** The geometry
/// below — the padding, the background on every cell, the character-counted tab
/// expansion and the `width - 2` wrap — is the same either way, which is why
/// promoting a table cannot move a line.
fn render_code_block(
    code: &str,
    lexer: Option<&'static str>,
    width: usize,
    options: &RenderOptions,
) -> Vec<Segment> {
    // `_process_code`: the block always ends in a newline, then tabs expand at four.
    let processed = expand_tabs_by_characters(&format!("{code}\n"), 4);
    let mut text = RichText::new();
    text.style = SYNTAX_BACKGROUND;
    text.justify = Some(Justify::Left);
    // **Two arms because the reference has two kinds of lexer.** Every promoted
    // family but one is a `RegexLexer` table that `syntax_lexer` runs; `JsonLexer` is
    // a hand-written character scanner with no table at all, so it is its own port.
    // Folding them behind one interface would hide the difference that decides how
    // each is gated.
    let tokens: Vec<(String, String)> = match lexer {
        None => {
            text.append_tokens(&processed, Some(SYNTAX_TEXT));
            Vec::new()
        }
        Some("JSON") => crate::syntax_json::tokenize(&processed),
        Some(name) => match crate::syntax_tables::promoted_lexer(name) {
            // **Still unreachable, and now by a different guarantee.** The fence
            // arm maps a language with no table to `None` before this is called, so
            // the plain render happens once, in one place. Reaching here would mean
            // the two had drifted apart.
            None => unreachable!("the fence arm maps an unpromoted language to None: {name}"),
            // `Syntax.highlight` appends one run per token, with the style the theme
            // resolves for that token's type.
            // **A fence that exhausts the step budget renders plain**, with the same
            // geometry every other block gets. Python's `re` has no step budget, so
            // there is no behaviour to reproduce either way — but the two answers are
            // not equally wrong. Refusing used to mean a typed error; once the panel
            // sink existed it meant a truncated scan and exit 101, which is worse than
            // a block that is uncoloured. Identical in structure to an unported
            // language, and strictly rarer.
            Some(lexer) => match crate::syntax_lexer::tokenize(lexer, &processed, &["root"]) {
                Ok(tokens) => tokens,
                Err(crate::search_query::StepBudgetExceeded) => {
                    text.append_tokens(&processed, Some(SYNTAX_TEXT));
                    Vec::new()
                }
            },
        },
    };
    for (path, value) in tokens {
        text.append_tokens(&value, Some(crate::syntax_styles::token_style(&path)));
    }

    // Horizontal padding is taken out of the code's width before it wraps.
    let code_width = width.saturating_sub(2);
    let mut body: Vec<Segment> = Vec::new();
    // `allow_blank` is `ends_on_nl`, which is false: the caller has already
    // rstripped the code, so the newline added above is not the author's.
    for line in text.split(false) {
        let segments = line.to_segments(code_width, options);
        for wrapped in split_and_crop_lines(
            &segments,
            code_width,
            Some(SYNTAX_BACKGROUND),
            true,
            options.metrics,
        ) {
            body.extend(wrapped);
            body.push(Segment { text: "\n".to_string(), style: None, link: None });
        }
    }
    render_padding(body, width, (1, 1, 1, 1), SYNTAX_BACKGROUND, options)
}

/// The two styles `Syntax` paints its line-number column with.
///
/// **`NUMBER_GUTTER` is the blended colour** `_get_line_numbers_color` computes: 30% of
/// the way from Monokai's background `#272822` to its `Token.Text` foreground
/// `#f8f8f2`, which lands on `#656660`. It is a computed constant rather than a theme
/// entry, so it is written out here.
///
/// **`NUMBER_LEAD` styles the two leading spaces and is the *highlight* style**, at 90%
/// blend and bold. Nothing is highlighted in a `Read` result, so its foreground never
/// shows — but the bold attribute and the background do, and they are byte-visible.
const NUMBER_GUTTER: Style = Style {
    bold: Some(false), dim: None, italic: Some(false), underline: Some(false),
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#656660"))),
    background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
};
const NUMBER_LEAD: Style = Style {
    bold: Some(true), dim: None, italic: Some(false), underline: Some(false),
    reverse: None, strike: None,
    foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e3e3dd"))),
    background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#272822"))),
};

/// `_read_output_renderable`'s body: a `Read` result as source with a line-number
/// gutter.
///
/// **The gutter is unconditional geometry, not highlighting.** It is drawn whatever
/// lexer the file resolves to, and over 2,497 real `Read` calls with a path only 48.3%
/// reach a promoted family — markdown alone is 37% and is deliberately outside the
/// seven. **Half the extension work delivering no colour is the approved outcome.**
///
/// `Syntax` here is built with `line_numbers=True` and **no padding**, where a fenced
/// block is built with `padding=1` and no numbers. So this is not `render_code_block`
/// with a column added: the two geometries differ at their edges as well as in the
/// middle.
fn render_read_output(
    code: &str,
    lexer: Option<&'static str>,
    start_line: usize,
    width: usize,
    options: &RenderOptions,
) -> Vec<Segment> {
    // `_numbers_column_width`: the widest number this block will show, plus two.
    // Counted over the **unprocessed** code, which is what `Syntax` holds.
    let last_number = start_line + code.matches('\n').count();
    let numbers_column_width = last_number.to_string().chars().count() + 2;
    let code_width = width.saturating_sub(numbers_column_width + 1);

    let ends_on_newline = code.ends_with('\n');
    let processed = expand_tabs_by_characters(
        &if ends_on_newline { code.to_string() } else { format!("{code}\n") },
        4,
    );
    let mut text = RichText::new();
    text.style = SYNTAX_BACKGROUND;
    text.justify = Some(Justify::Left);
    let tokens: Vec<(String, String)> = match lexer {
        None => {
            text.append_tokens(&processed, Some(SYNTAX_TEXT));
            Vec::new()
        }
        Some("JSON") => crate::syntax_json::tokenize(&processed),
        Some(name) => match crate::syntax_tables::promoted_lexer(name) {
            None => unreachable!("the read table names only promoted families: {name}"),
            Some(lexer) => match crate::syntax_lexer::tokenize(lexer, &processed, &["root"]) {
                Ok(tokens) => tokens,
                // The same ruling as a fence: exhausting the budget renders plain.
                Err(crate::search_query::StepBudgetExceeded) => {
                    text.append_tokens(&processed, Some(SYNTAX_TEXT));
                    Vec::new()
                }
            },
        },
    };
    for (path, value) in tokens {
        text.append_tokens(&value, Some(crate::syntax_styles::token_style(&path)));
    }

    let continuation = format!("{} ", " ".repeat(numbers_column_width));
    let mut out: Vec<Segment> = Vec::new();
    for (offset, line) in text.split(ends_on_newline).into_iter().enumerate() {
        let segments = line.to_segments(code_width, options);
        let wrapped = split_and_crop_lines(
            &segments,
            code_width,
            Some(SYNTAX_BACKGROUND),
            true,
            options.metrics,
        );
        for (index, wrapped_line) in wrapped.into_iter().enumerate() {
            if index == 0 {
                let number = (start_line + offset).to_string();
                let padding = numbers_column_width
                    .saturating_sub(2)
                    .saturating_sub(number.chars().count());
                out.push(Segment {
                    text: "  ".to_string(),
                    style: Some(NUMBER_LEAD),
                    link: None,
                });
                out.push(Segment {
                    text: format!("{}{number} ", " ".repeat(padding)),
                    style: Some(NUMBER_GUTTER),
                    link: None,
                });
            } else {
                out.push(Segment {
                    text: continuation.clone(),
                    style: Some(SYNTAX_BACKGROUND),
                    link: None,
                });
            }
            out.extend(wrapped_line);
            out.push(Segment { text: "\n".to_string(), style: None, link: None });
        }
    }
    out
}

/// The rendered block for each **promoted** family, end to end against Rich.
///
/// The token-stream gate in `syntax_table_gates` proves the table; this proves what
/// the block looks like once the geometry closes around it. They are separate
/// because a correct stream laid out wrongly and a wrong stream laid out correctly
/// fail in the same place, and only one of them is this seat's.
#[cfg(test)]
mod fence_render_oracle_tests {
    use super::markdown_oracle_tests::{describe, recorded_lines};
    use super::*;
    use serde_json::Value;
    use std::path::PathBuf;

    /// Every promoted family has one of these, and each is recorded from the token
    /// oracle already on disk, so both regenerate identically from a checkout.
    const FAMILIES: [&str; 7] =
        ["typescript", "tsx", "bash", "python", "javascript", "json", "sql"];

    fn oracle(family: &str) -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join(format!("tests/data/lexer-tables/{family}-render-oracle.json"));
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("the {family} fence render oracle is missing at {}: {error}", path.display())
        });
        serde_json::from_slice(&bytes).expect("the fence render oracle is valid JSON")
    }

    #[test]
    fn every_recorded_fence_in_a_promoted_language_renders_exactly() {
        for family in FAMILIES {
            renders_exactly(family);
        }
    }

    fn renders_exactly(family: &str) {
        let oracle = oracle(family);
        let metrics = CellMetrics::from_environment();
        let mut compared = 0usize;
        let mut failures: Vec<String> = Vec::new();
        for case in oracle["cases"].as_array().expect("the oracle carries cases") {
            let markup = case["markup"].as_str().expect("a case carries markup");
            let width = case["width"].as_u64().expect("a case carries a width") as usize;
            let identifier = case["id"].as_str().unwrap_or("?");
            let rendered = markdown_lines(markup, width, &metrics);
            compared += 1;
            let expected = recorded_lines(case);
            let actual: Vec<Vec<String>> = rendered
                .iter()
                .map(|line| line.iter().map(describe).collect())
                .collect();
            if actual == expected {
                continue;
            }
            let mut report = format!("{identifier} @ {width}\n");
            for index in 0..expected.len().max(actual.len()) {
                let want = expected.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let got = actual.get(index).map(|line| line.join(" ")).unwrap_or_default();
                if want == got {
                    continue;
                }
                report.push_str(&format!("  rich {want}\n  ours {got}\n"));
            }
            failures.push(report);
        }
        assert!(
            compared >= 200,
            "Only {compared} rendered {family} fences were compared, against 200 or \
             more when the corpus is whole. A shrunken corpus passes vacuously."
        );
        assert!(
            failures.is_empty(),
            "{} of {compared} rendered {family} fences differ from Rich:\n\n{}",
            failures.len(),
            failures[..failures.len().min(3)].join("\n")
        );
    }

    /// Content a lexer will certainly colour, so the fallback assertions cannot pass
    /// because the sample happened to be default-coloured.
    ///
    /// **The first version of this test used the word `placeholder`**, which every
    /// lexer scans as a plain name and Monokai paints in the default foreground — so
    /// a fence in a *promoted* language rendered byte-identically to an untagged one
    /// and the assertion passed for the wrong reason. `sql` was in its subject list
    /// after SQL was promoted, and nothing went red.
    const DISCRIMINATING: &str = "\"text\" 42";

    /// A tag Pygments does not know. **Rendering plain here is parity with
    /// `ch-legacy`, which also renders it plain**, and these are the measured
    /// commonest: 401 blocks, 1.1% of all fenced blocks, across 29 tags.
    const NO_LEXER_AT_ALL: [&str; 3] = ["mermaid", "just", "mdx"];

    /// A tag Pygments knows and no promoted table covers. **Rendering plain here is
    /// a deliberate divergence** — `ch-legacy` colours all of these — accepted by the
    /// 2026-08-30 ruling because the alternative is refusing, which panics the panel
    /// sink and truncates a scan that has already printed.
    const KNOWN_BUT_UNPORTED: [&str; 4] = ["css", "html", "xml", "yaml"];

    fn fenced(tag: &str, metrics: &CellMetrics) -> Vec<Vec<Segment>> {
        let markup = format!("```{tag}\n{DISCRIMINATING}\n```");
        markdown_lines(&markup, 72, metrics)
    }

    /// **The subjects, checked rather than commented.** Both lists decay the moment a
    /// family is promoted — `javascript` was in one of them and turned it red the day
    /// JavaScript landed — so each tag's membership is derived from
    /// `lexer_for_tag` and `promoted_lexer` instead of being asserted in prose.
    #[test]
    fn the_fallback_subjects_are_still_the_right_ones() {
        for tag in NO_LEXER_AT_ALL {
            assert_eq!(
                crate::syntax_lexers::lexer_for_tag(tag),
                None,
                "`{tag}` now reaches a Pygments lexer, so it is no longer a parity \
                 subject. Move it to KNOWN_BUT_UNPORTED and pick another tag that \
                 reaches none."
            );
        }
        for tag in KNOWN_BUT_UNPORTED {
            let name = crate::syntax_lexers::lexer_for_tag(tag).unwrap_or_else(|| {
                panic!("`{tag}` reaches no Pygments lexer, so it is a parity subject \
                        rather than a divergence one")
            });
            assert!(
                crate::syntax_tables::promoted_lexer(name).is_none() && name != "JSON",
                "`{tag}` reaches {name}, which is now promoted, so it no longer \
                 diverges. Drop it and pick another unported language."
            );
        }
    }

    /// **The control that makes the two tests below mean something.** If the sample
    /// content is not coloured by a promoted family either, plain output proves
    /// nothing.
    #[test]
    fn the_fallback_sample_is_coloured_by_a_promoted_family() {
        let metrics = CellMetrics::from_environment();
        assert_ne!(
            fenced("python", &metrics),
            fenced("", &metrics),
            "the sample must render differently under a promoted family than \
             untagged, or every assertion about plain output passes vacuously"
        );
    }

    /// **Parity.** A tag reaching no lexer renders plain in the product and plain in
    /// `ch-legacy`, so this is agreement rather than divergence.
    #[test]
    fn a_fence_in_an_unrecognised_language_renders_plain_as_legacy_does() {
        let metrics = CellMetrics::from_environment();
        let untagged = fenced("", &metrics);
        for tag in NO_LEXER_AT_ALL {
            assert_eq!(
                fenced(tag, &metrics),
                untagged,
                "`{tag}` reaches no Pygments lexer, so both routes render it as an \
                 untagged fence. This is the one place plain output is parity."
            );
        }
    }

    /// **The accepted divergence, asserted so it cannot be mistaken for parity.**
    #[test]
    fn a_fence_in_a_known_but_unported_language_renders_plain_and_diverges() {
        let metrics = CellMetrics::from_environment();
        let untagged = fenced("", &metrics);
        for tag in KNOWN_BUT_UNPORTED {
            assert_eq!(
                fenced(tag, &metrics),
                untagged,
                "`{tag}` reaches a Pygments lexer and no promoted table, so by the \
                 2026-08-30 ruling it renders exactly as an untagged fence: complete \
                 geometry, background and padding, plain unstyled code. **It \
                 deliberately does not match `ch-legacy`, which colours it** — that is \
                 the accepted divergence, not a defect."
            );
        }
    }

    /// **The colours have to be the lexer's, not one colour over the block.** A port
    /// that wired the geometry and forgot the tokens would pass every geometry test
    /// in this file, so the gate says outright that the recorded render carries more
    /// than one foreground.
    #[test]
    fn a_recorded_fence_carries_more_than_one_foreground() {
        for family in FAMILIES {
            let oracle = oracle(family);
            let mut foregrounds: std::collections::BTreeSet<String> = Default::default();
            for case in oracle["cases"].as_array().expect("cases") {
                for line in case["lines"].as_array().expect("lines") {
                    for segment in line.as_array().expect("segments") {
                        if let Some(colour) = segment["s"].get("fg") {
                            foregrounds.insert(colour.to_string());
                        }
                    }
                }
            }
            assert!(
                foregrounds.len() >= 6,
                "The recorded {family} renders carry {} distinct foregrounds. A \
                 promoted table paints keywords, strings, numbers, comments and names \
                 differently, so this corpus cannot tell a highlighted block from a \
                 plain one.",
                foregrounds.len()
            );
        }
    }
}

#[cfg(test)]
mod code_block_geometry_tests {
    use super::*;

    /// `Syntax._process_code` calls Python's `str.expandtabs`, which counts
    /// **characters**. `Text.expand_tabs`, used on the markdown path, counts
    /// **cells**. Both run in one render, and only a wide character separates them.
    /// Answers taken from CPython.
    #[test]
    fn tabs_in_a_code_block_expand_by_characters_not_cells() {
        assert_eq!(expand_tabs_by_characters("a\tb\tc", 4), "a   b   c");
        assert_eq!(expand_tabs_by_characters("ab\tcd", 4), "ab  cd");
        assert_eq!(expand_tabs_by_characters("abc\tx", 4), "abc x");
        assert_eq!(expand_tabs_by_characters("\t\ta", 4), "        a");
        // The discriminating case: `你好` is two characters and four cells.
        assert_eq!(expand_tabs_by_characters("你好\tx", 4), "你好  x");
    }

    /// The falsification: a cell-counting expansion must still disagree, or the
    /// case above has stopped reaching the difference it was written for.
    #[test]
    fn a_cell_counting_expansion_still_gets_the_wide_case_wrong() {
        fn by_cells(text: &str, tab_size: usize, metrics: &CellMetrics) -> String {
            let mut out = String::new();
            let mut column = 0usize;
            for character in text.chars() {
                if character == '\t' {
                    let spaces = tab_size - column % tab_size;
                    out.extend(std::iter::repeat_n(' ', spaces));
                    column += spaces;
                } else {
                    out.push(character);
                    column += metrics.character_cell_size(character);
                }
            }
            out
        }
        let metrics = CellMetrics::for_version(None);
        assert_eq!(by_cells("你好\tx", 4, &metrics), "你好    x");
        assert_ne!(
            by_cells("你好\tx", 4, &metrics),
            expand_tabs_by_characters("你好\tx", 4),
            "The two counting units must still differ here, or this guard is inert."
        );
    }

    /// The recorded corpus must reach the plain-lexer path, or the geometry gate is
    /// asserting nothing about code blocks.
    #[test]
    fn the_recorded_corpus_reaches_code_blocks_that_render() {
        let oracle = super::markdown_oracle_tests::oracle();
        let mut rendered = 0usize;
        for case in oracle["cases"].as_array().expect("cases") {
            let markup = case["markup"].as_str().expect("markup");
            let tokens = markdown_tokens(markup);
            let has_block = tokens.iter().any(|token| {
                matches!(token, Token::Fence { .. } | Token::IndentedCode { .. })
            });
            if !has_block {
                continue;
            }
            let width = case["width"].as_u64().expect("a width") as usize;
            let metrics = CellMetrics::from_environment();
            if !markdown_lines(markup, width, &metrics).is_empty() {
                rendered += 1;
            }
        }
        assert!(
            rendered >= 60,
            "Only {rendered} recorded code-block records render. Below that the \
             geometry gate is measuring the corpus rather than the renderer."
        );
    }
}

/// A fence whose lexer exhausts the step budget renders **plain**, with complete
/// geometry, and never refuses.
///
/// **No corpus can reach this.** The budget is twenty million steps, and a 147 KB
/// pathological Python fence — long unterminated strings, eighty-deep nesting,
/// repeated four hundred times — rendered fine. So the gate shrinks the real limit
/// inside the real VM and lets the exhaustion travel the real path, rather than
/// fabricating the symptom and asserting its own stub.
#[cfg(test)]
mod fence_budget_exhaustion_tests {
    use super::*;
    use crate::search_query::ShrunkStepBudget;

    /// Long enough that the first rule's first match cannot be free, and in a
    /// promoted family, so the lexer is genuinely entered.
    const CODE: &str = "def add(a, b):\n    \"\"\"a docstring\"\"\"\n    return a + b\n";
    const WIDTH: usize = 40;

    fn render(lexer: Option<&'static str>) -> Vec<Segment> {
        let metrics = CellMetrics::for_version(None);
        let options = RenderOptions::new(&metrics);
        render_code_block(CODE, lexer, WIDTH, &options)
    }

    fn describe(segments: &[Segment]) -> Vec<String> {
        segments.iter().map(super::markdown_oracle_tests::describe).collect()
    }

    /// What the gate accepts, factored out so the two deliberately wrong renders
    /// below can be run through the same judgement.
    fn disagreement(actual: &[Segment], plain: &[Segment]) -> Option<String> {
        if describe(actual) == describe(plain) {
            return None;
        }
        Some(format!(
            "the exhausted render is not the plain one:\n  plain {:?}\n  ours  {:?}",
            describe(plain),
            describe(actual)
        ))
    }

    #[test]
    fn a_fence_that_exhausts_the_step_budget_renders_plain() {
        let plain = render(None);
        let exhausted = {
            let _shrunk = ShrunkStepBudget::to(1);
            render(Some("Python"))
        };
        assert!(
            disagreement(&exhausted, &plain).is_none(),
            "{}",
            disagreement(&exhausted, &plain).unwrap_or_default()
        );
    }

    /// The control. Without it the gate above passes on a lexer that was never
    /// entered, and it would be measuring nothing — the shape this mission has been
    /// caught by repeatedly.
    #[test]
    fn the_same_fence_is_coloured_when_the_budget_is_whole() {
        let plain = render(None);
        let lexed = render(Some("Python"));
        assert_ne!(
            describe(&lexed),
            describe(&plain),
            "A whole budget must colour this fence. If it does not, the exhaustion \
             gate beside this one is comparing plain against plain and proves nothing."
        );
    }

    /// **The falsification, run as part of the gate.** Two deliberately wrong
    /// fallbacks — a refusal, which is what the panel sink used to panic on, and a
    /// truncation, which is what refusing actually produced once the sink existed.
    /// Both must be rejected, or the judgement above has stopped catching anything.
    #[test]
    fn the_gate_rejects_a_refusal_and_a_truncation() {
        let plain = render(None);

        let refuses: Vec<Segment> = Vec::new();
        assert!(
            disagreement(&refuses, &plain).is_some(),
            "A fallback that renders nothing must fail this gate. That is the shape a \
             refusal took at the sink: a panel that printed its frame and no body."
        );

        let mut truncates = plain.clone();
        truncates.truncate(plain.len().saturating_sub(2));
        assert!(
            disagreement(&truncates, &plain).is_some(),
            "A fallback that drops the tail of the block must fail this gate. That is \
             what refusing produced once the sink existed: output already printed, \
             then cut short."
        );
    }

    /// End to end through the real markdown route, so the claim is about `ch search`
    /// rather than about one private function.
    #[test]
    fn the_whole_markdown_route_survives_an_exhausted_budget() {
        let metrics = CellMetrics::for_version(None);
        let markup = format!("```python\n{CODE}```");
        let plain = markdown_lines(&format!("```mermaid\n{CODE}```"), WIDTH, &metrics);
        let exhausted = {
            let _shrunk = ShrunkStepBudget::to(1);
            markdown_lines(&markup, WIDTH, &metrics)
        };
        assert!(
            !exhausted.is_empty(),
            "An exhausted fence must still render a block. An empty body is the \
             failure the refusal produced."
        );
        let lines = |rendered: &Vec<Vec<Segment>>| -> Vec<Vec<String>> {
            rendered.iter().map(|line| describe(line)).collect()
        };
        assert_eq!(
            lines(&exhausted),
            lines(&plain),
            "Through the whole markdown route an exhausted fence must render exactly \
             as an unported one does. **`mermaid` reaches no lexer at all**, which is \
             the right subject for this comparison; a promoted family would be the \
             wrong one, because it would be compared against itself."
        );
    }
}

/// The `Read` gutter against Rich, over real `Read` results from the frozen pool.
///
/// **The body oracle carries two synthetic `Read` cases; this carries the real ones.**
/// Both are needed and they answer different questions: the synthetic pair pins the
/// gutter inside a whole message body, and this pins it against the file names and
/// content the product actually meets — 72 cases drawn from 2,676 real results, at two
/// widths.
#[cfg(test)]
mod read_gutter_oracle_tests {
    use super::body_oracle_tests::{recorded_gutter_cells, relaxed, relaxed_recorded};
    use super::markdown_oracle_tests::{describe, recorded_lines};
    use super::*;
    use serde_json::Value;
    use std::collections::BTreeSet;
    use std::path::PathBuf;

    fn oracle() -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/read-gutter/read-gutter-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!(
                "the Read-gutter oracle is missing at {}: {error}. Rebuild it with \
                 `teammates/cutover-finisher/probes/generate_read_gutter_oracle.py`.",
                path.display()
            )
        });
        serde_json::from_slice(&bytes).expect("the Read-gutter oracle is valid JSON")
    }

    /// The rail Python builds around the syntax, so this compares the same renderable
    /// the product does rather than the geometry alone.
    fn render(case: &Value, metrics: &CellMetrics) -> Vec<Vec<Segment>> {
        let output_text = case["output_text"].as_str().expect("a recorded result");
        let file_path = case["file_path"].as_str().expect("a recorded path");
        let width = case["width"].as_u64().expect("a recorded width") as usize;
        let (code, start_line) = strip_read_line_numbers(output_text);
        let lexer = read_lexer(file_path, &code);
        let rail = Renderable::LeftRail {
            child: Box::new(Renderable::ReadOutput { code, lexer, start_line }),
            style: theme_style_for_result(),
            glyph: "▎ ",
        };
        let options = RenderOptions::new(metrics);
        let context = BodyContext {
            metrics,
            highlight: None,
            conversation_tag: None,
            home: "/tmp/ch-read-gutter-home",
        };
        let segments = rail.render(width, &options, &context);
        split_and_crop_lines(&segments, width, None, false, metrics)
    }

    fn theme_style_for_result() -> Style {
        TOOL_RESULT
    }

    #[test]
    fn every_recorded_read_result_reproduces() {
        let oracle = oracle();
        let metrics = CellMetrics::from_environment();
        let cases = oracle["cases"].as_array().expect("recorded results");
        let mut compared = 0usize;
        let mut exact = 0usize;
        let mut relaxed_cases: BTreeSet<String> = BTreeSet::new();
        let mut failures: Vec<String> = Vec::new();

        for case in cases {
            let output_text = case["output_text"].as_str().expect("a recorded result");
            let file_path = case["file_path"].as_str().expect("a recorded path");
            let (code, _) = strip_read_line_numbers(output_text);
            // **Which family Rich chose, taken from the recording rather than from this
            // port.** Deciding it with `read_lexer` would let a wrong resolution grant
            // itself the relaxation and hide the very defect this gate exists for.
            let recorded_alias = case["lexer"].as_str().expect("a recorded lexer");
            let promoted = crate::syntax_lexers::lexer_for_tag(recorded_alias).filter(|name| {
                *name == "JSON" || crate::syntax_tables::promoted_lexer(name).is_some()
            });
            assert_eq!(
                read_lexer(file_path, &code),
                promoted,
                "`read_lexer` disagrees with `Syntax.guess_lexer` about {file_path}, \
                 which Rich resolved to {recorded_alias:?}. **That decides whether the \
                 block is coloured at all**, so a disagreement here is a rendering \
                 divergence rather than a naming one."
            );
            let rendered = render(case, &metrics);
            compared += 1;
            let expected = recorded_lines(case);
            let actual: Vec<Vec<String>> = rendered
                .iter()
                .map(|line| line.iter().map(describe).collect())
                .collect();
            if actual == expected {
                exact += 1;
                continue;
            }
            // The 2026-08-30 ruling: an unported language keeps the geometry and loses
            // the colours inside the block. A **promoted** family gets no relaxation at
            // all, so a regression there is caught by the exact comparison above.
            if promoted.is_none()
                && let Some(cells) = recorded_gutter_cells(&case["lines"])
            {
                let recorded = case["lines"].as_array().expect("recorded lines");
                let agrees = rendered.len() == recorded.len()
                    && rendered.iter().zip(recorded).all(|(ours, theirs)| {
                        relaxed(ours, cells) == relaxed_recorded(theirs, cells)
                    });
                if agrees {
                    relaxed_cases.insert(case["lexer"].as_str().unwrap_or("?").to_string());
                    continue;
                }
            }
            let path = case["file_path"].as_str().unwrap_or("?");
            let width = case["width"].as_u64().unwrap_or(0);
            let mut report = format!("{path} @ {width} ({})\n", case["lexer"]);
            for index in 0..expected.len().max(actual.len()) {
                let want = expected.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let got = actual.get(index).map(|line| line.join(" ")).unwrap_or_default();
                let marker = if want == got { "  " } else { "->" };
                report.push_str(&format!("  {marker} rich {want}\n     ours {got}\n"));
            }
            failures.push(report);
        }

        assert!(
            compared >= 120,
            "Only {compared} recorded Read results were compared. A shrunken corpus \
             passes vacuously."
        );
        assert!(
            failures.is_empty(),
            "{} of {compared} recorded Read results differ from Rich by more than \
             where their runs are cut:\n\n{}",
            failures.len(),
            failures[..failures.len().min(3)].join("\n")
        );
        // **The corpus must reach both sides of the ruling**, or it is measuring one
        // path and reporting on two.
        assert!(
            exact >= 40,
            "Only {exact} of {compared} recorded Read results matched Rich exactly. \
             Below that the corpus has stopped reaching the promoted families and this \
             gate is proving the plain fallback alone."
        );
        assert!(
            !relaxed_cases.is_empty(),
            "No recorded Read result took the unported-language path. **Markdown is 37% \
             of real Read calls and is deliberately not promoted**, so a corpus that \
             never reaches it is not the corpus this gate was built for."
        );
        assert!(
            relaxed_cases.contains("markdown"),
            "The relaxation was taken by {relaxed_cases:?} and **not by markdown**, \
             which is 37% of real `Read` calls and the single largest unported \
             language. A corpus that stopped reaching it has stopped measuring the \
             case this gate was built around."
        );
    }

    /// `read_lexer` against `Syntax.guess_lexer`, wide and cheap.
    ///
    /// **The render oracle could not grade this on its own.** It carries whole rendered
    /// blocks, so it is expensive per case and thin in the tail — and a mutation that
    /// disabled the `*.js` delegation test survived it, because a 144-record corpus
    /// happened to hold no delegated `.js` file. This holds 353 paths and bodies,
    /// including five that Pygments hands to a template delegate.
    #[test]
    fn read_lexer_agrees_with_guess_lexer_on_every_recorded_path() {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/read-gutter/read-lexer-oracle.json");
        let bytes = std::fs::read(&path).expect("the Read-lexer oracle is present");
        let oracle: Value = serde_json::from_slice(&bytes).expect("valid JSON");
        let cases = oracle["cases"].as_array().expect("recorded paths");
        let mut failures: Vec<String> = Vec::new();
        let mut delegated = 0usize;
        for case in cases {
            let file_path = case["file_path"].as_str().expect("a path");
            let code = case["code"].as_str().expect("a body");
            let alias = case["lexer"].as_str().expect("an alias");
            let expected = crate::syntax_lexers::lexer_for_tag(alias).filter(|name| {
                *name == "JSON" || crate::syntax_tables::promoted_lexer(name).is_some()
            });
            if alias.contains('+') {
                delegated += 1;
            }
            let ours = read_lexer(file_path, code);
            if ours != expected {
                failures.push(format!("{file_path}: rich {alias:?} -> {expected:?}, ours {ours:?}"));
            }
        }
        assert!(
            cases.len() >= 300,
            "Only {} recorded paths. A shrunken corpus passes vacuously.",
            cases.len()
        );
        assert!(
            failures.is_empty(),
            "{} of {} recorded Read paths resolve to a different family than \
             `Syntax.guess_lexer` chose:\n  {}",
            failures.len(),
            cases.len(),
            failures[..failures.len().min(6)].join("\n  ")
        );
        // **Without this the delegation test is untested.** A `.js` file Pygments hands
        // to a template delegate renders plain; one it keeps renders JavaScript. A
        // corpus with no delegated file lets a resolver that ignores content pass.
        assert!(
            delegated >= 3,
            "Only {delegated} recorded paths resolve to a delegating lexer. The \
             `js-delegates` rule is then asserted by nothing, and a resolver that \
             answered from the extension alone would pass this gate."
        );
    }

    /// The gutter is drawn whatever the file is, which is the whole claim behind
    /// "line numbers are unconditional geometry, not highlighting".
    #[test]
    fn every_recorded_read_result_carries_a_line_number_column() {
        let oracle = oracle();
        let metrics = CellMetrics::from_environment();
        let mut without = Vec::new();
        for case in oracle["cases"].as_array().expect("cases") {
            let rendered = render(case, &metrics);
            let numbered = rendered.iter().any(|line| {
                line.iter().any(|segment| {
                    segment.style == Some(NUMBER_GUTTER)
                        && segment.text.trim().chars().all(|c| c.is_ascii_digit())
                        && !segment.text.trim().is_empty()
                })
            });
            if !numbered {
                without.push(case["file_path"].as_str().unwrap_or("?").to_string());
            }
        }
        assert!(
            without.is_empty(),
            "{} recorded Read results rendered with no line-number column, including \
             {:?}. The gutter is geometry rather than highlighting: an unported \
             language loses its colours and keeps its numbers.",
            without.len(),
            &without[..without.len().min(3)]
        );
    }
}
