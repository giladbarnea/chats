//! The coloured search chrome: list rows, the conversation panel frame, and the
//! trailing summary line.
//!
//! Only the search-specific half of the coloured output. Turning one message into
//! styled lines belongs to the session renderer; this module draws the frame
//! around it.
//!
//! Four behaviours here are wrong and are reproduced on purpose. Each one is
//! marked at its definition. A port that repairs any of them looks better and
//! diverges, which is the one direction our byte comparators cannot see.

use crate::cells::CellMetrics;
use crate::search_confirm::SearchHit;
use crate::search_engine::HitSink;
use std::io::Write;
use crate::color::{ColorRendering, ColorTriplet, StyleColor};

/// Replace the home directory prefix with `~` for display.
///
/// **Preserved because it is wrong.** Python matches a string prefix rather than a
/// path boundary, so a sibling directory whose name merely starts with the home
/// directory's name is mangled. A port comparing path components is correct and
/// diverges on every such directory.
///
/// ```
/// use _native::search_views::collapse_home;
/// assert_eq!(collapse_home("/Users/ada/dev/chats", "/Users/ada"), "~/dev/chats");
/// // Wrong on purpose: a prefix match, not a boundary match.
/// assert_eq!(collapse_home("/Users/adaX/dev", "/Users/ada"), "~X/dev");
/// assert_eq!(collapse_home("/Users/ada-backup/x", "/Users/ada"), "~-backup/x");
/// assert_eq!(collapse_home("/opt/tools", "/Users/ada"), "/opt/tools");
/// ```
pub fn collapse_home(path: &str, home: &str) -> String {
    // An empty home would make every path start with it and collapse to `~`,
    // turning a missing environment variable into mangled output on every row.
    // Session roots are `$HOME`-derived, so an absent `HOME` is out of contract.
    if home.is_empty() {
        return path.to_string();
    }
    match path.strip_prefix(home) {
        Some(rest) => format!("~{rest}"),
        None => path.to_string(),
    }
}

/// Units the age label steps through, as `(ceiling, suffix, divisor)` in seconds.
///
/// **Preserved because it is wrong.** A month is exactly 30 days and a year
/// exactly 365, so twelve months is 360 days and an age between 360 and 365 renders
/// `12mo` before jumping to `1y`. Real calendar arithmetic diverges on every age
/// past a month.
const AGE_UNITS: [(f64, &str, f64); 6] = [
    (3600.0, "m", 60.0),
    (86400.0, "h", 3600.0),
    (604800.0, "d", 86400.0),
    (2592000.0, "w", 604800.0),
    (31536000.0, "mo", 2592000.0),
    (f64::INFINITY, "y", 31536000.0),
];

/// Render an age in seconds as a compact token like `24m` or `2w`.
///
/// ```
/// use _native::search_views::humanize_age;
/// assert_eq!(humanize_age(30.0), "now");
/// assert_eq!(humanize_age(24.0 * 60.0), "24m");
/// assert_eq!(humanize_age(3.0 * 3600.0), "3h");
/// assert_eq!(humanize_age(14.0 * 86400.0), "2w");
/// assert_eq!(humanize_age(151.0 * 86400.0), "5mo");
/// // 30-day months: twelve of them is 360 days, so 362 days is still months.
/// assert_eq!(humanize_age(362.0 * 86400.0), "12mo");
/// assert_eq!(humanize_age(365.0 * 86400.0), "1y");
/// ```
pub fn humanize_age(seconds: f64) -> String {
    if seconds < 60.0 {
        return "now".to_string();
    }
    for (ceiling, suffix, divisor) in AGE_UNITS {
        if seconds < ceiling {
            return format!("{}{suffix}", (seconds / divisor).floor() as i64);
        }
    }
    unreachable!("the year bucket has no ceiling")
}

/// The theme style token an age is painted with, brightest for the most recent.
///
/// **Preserved because it is wrong.** These thresholds are *not* the ones
/// [`humanize_age`] uses, and the mismatch is visible in every coloured row: from
/// one day onward the colour is exactly one bucket older than the label reads. A
/// row saying `3d` is painted the week colour, `2w` the month colour, `5mo` the old
/// colour.
///
/// Driving both from one table is the obvious simplification and the single
/// highest-risk change on this mission: the fixtures normalise the label and the
/// comparators normalise the colour, so nothing but `age_pairing_gate.py` checks
/// the pairing. **Do not unify these with [`AGE_UNITS`].**
///
/// ```
/// use _native::search_views::{age_style, humanize_age};
/// // The label and the colour disagree by one bucket, on purpose.
/// assert_eq!(humanize_age(3.0 * 86400.0), "3d");
/// assert_eq!(age_style(3.0 * 86400.0), "search.age.week");
/// assert_eq!(humanize_age(14.0 * 86400.0), "2w");
/// assert_eq!(age_style(14.0 * 86400.0), "search.age.month");
/// assert_eq!(humanize_age(45.0 * 86400.0), "1mo");
/// assert_eq!(age_style(45.0 * 86400.0), "search.age.old");
/// ```
pub fn age_style(seconds: f64) -> &'static str {
    if seconds < 86400.0 {
        "search.age.now"
    } else if seconds < 604800.0 {
        "search.age.week"
    } else if seconds < 2592000.0 {
        "search.age.month"
    } else {
        "search.age.old"
    }
}

/// Where an ellipsis goes when [`elide_to_width`] shortens a string.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Elision {
    Tail,
    Middle,
}

/// Shorten text to `width` on a single line with an ellipsis.
///
/// **Preserved because it is wrong.** The contract says columns and the
/// implementation counts code points, so double-width text returns unchanged and
/// overshoots its budget by 2x. That overshoot never reaches the screen — Rich
/// clips the assembled line again in cells — but a port that measures display width
/// here still diverges, because it elides earlier and produces a *short* line where
/// the product produces a full-width padded one.
///
/// ```
/// use _native::search_views::{elide_to_width, Elision};
/// assert_eq!(elide_to_width("hello world", 20, Elision::Tail), "hello world");
/// assert_eq!(elide_to_width("hello world", 8, Elision::Tail), "hello w…");
/// assert_eq!(elide_to_width("/a/very/long/path/here", 12, Elision::Middle), "/a/ver…/here");
/// // Wrong on purpose: eight code points is sixteen columns, and it fits neither.
/// assert_eq!(elide_to_width("你好你好你好你好", 8, Elision::Tail), "你好你好你好你好");
/// ```
pub fn elide_to_width(text: &str, width: usize, where_to_elide: Elision) -> String {
    let characters: Vec<char> = text.chars().collect();
    if characters.len() <= width {
        return text.to_string();
    }
    if width <= 1 {
        return "…".chars().take(width).collect();
    }
    let available = width - 1;
    match where_to_elide {
        Elision::Tail => characters[..available].iter().collect::<String>() + "…",
        Elision::Middle => {
            let left = available.div_ceil(2);
            let right = available / 2;
            let head: String = characters[..left].iter().collect();
            // Python guards `text[-0:]`, which would otherwise return the whole
            // string rather than nothing.
            let tail: String = characters[characters.len() - right..].iter().collect();
            format!("{head}…{tail}")
        }
    }
}

/// A hyperlink target, carried beside the run it covers.
///
/// Not a field of [`Style`], because a `String` there would cost `Style` its `Copy`,
/// and chrome resolves styles by value everywhere. It rides on the segment instead,
/// so a run and its URL cannot be separated.
///
/// **`id` is Rich's per-render random integer**, not a hash of the URL:
/// `Style._link_id = randint(0, 999999)`. So byte parity on link-bearing content is
/// impossible even for Python against itself, and every comparator over message
/// bodies normalises `id=<digits>` on both sides. Uniqueness per link instance is the
/// property; the value is not.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Link {
    pub url: String,
    pub id: u32,
}

/// One run of text carrying at most one style and at most one link.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Segment {
    pub text: String,
    pub style: Option<Style>,
    /// `None` throughout the chrome; set only by message bodies.
    pub link: Option<Link>,
}

impl Segment {
    pub fn plain(text: impl Into<String>) -> Segment {
        Segment { text: text.into(), style: None, link: None }
    }

    /// Author by theme token. The token resolves **here**, so an unknown one fails
    /// at construction rather than mid-render on user content.
    pub fn styled(text: impl Into<String>, token: &'static str) -> Segment {
        Segment { text: text.into(), style: Some(theme_style(token)), link: None }
    }

    /// Author with a composed style, for content whose styling no token can name.
    pub fn composed(text: impl Into<String>, style: Style) -> Segment {
        Segment { text: text.into(), style: Some(style), link: None }
    }
}

/// A style as Rich composes them: each field is **set, cleared, or inherited**.
///
/// `Option<bool>` rather than `bool` because Rich's styles clear as well as set —
/// `repr.str` specifies `italic=False, bold=False`, so it removes the attributes
/// underneath it rather than adding to them. A struct of plain bools cannot express
/// that difference and silently keeps whatever was there.
///
/// Message bodies compose styles that no token can name — `***both***`, a `**bold**`
/// inside a blockquote, a heading's own style under its inline styles, the search
/// highlight on top of any of them — so a segment carries a resolved `Style` rather
/// than a token name. Chrome still authors by token; the token resolves here, at
/// construction, which also moves the unknown-token panic strictly earlier.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Style {
    pub bold: Option<bool>,
    pub dim: Option<bool>,
    pub italic: Option<bool>,
    pub underline: Option<bool>,
    pub reverse: Option<bool>,
    pub strike: Option<bool>,
    pub foreground: Option<StyleColor>,
    pub background: Option<StyleColor>,
}

impl Style {
    pub const fn colour(foreground: StyleColor) -> Style {
        Style { foreground: Some(foreground), ..Style::inherit() }
    }

    pub const fn inherit() -> Style {
        Style {
            bold: None, dim: None, italic: None, underline: None,
            reverse: None, strike: None, foreground: None, background: None,
        }
    }

    /// Later wins, field by field. Rich's `Style.__add__`.
    pub fn over(self, later: Style) -> Style {
        Style {
            bold: later.bold.or(self.bold),
            dim: later.dim.or(self.dim),
            italic: later.italic.or(self.italic),
            underline: later.underline.or(self.underline),
            reverse: later.reverse.or(self.reverse),
            strike: later.strike.or(self.strike),
            foreground: later.foreground.or(self.foreground),
            background: later.background.or(self.background),
        }
    }

    /// SGR parameters, attributes in ascending code order then foreground then
    /// background — Rich's own order, and the order every recorded gate expects.
    pub fn parameters(self, rendering: ColorRendering) -> String {
        let mut parts: Vec<String> = Vec::new();
        for (set, code) in [
            (self.bold, "1"), (self.dim, "2"), (self.italic, "3"),
            (self.underline, "4"), (self.reverse, "7"), (self.strike, "9"),
        ] {
            if set == Some(true) {
                parts.push(code.to_string());
            }
        }
        if let ColorRendering::Colored(system) = rendering {
            if let Some(foreground) = self.foreground {
                parts.push(foreground.foreground(system));
            }
            if let Some(background) = self.background {
                parts.push(background.background(system));
            }
        }
        parts.join(";")
    }
}

/// Author a theme entry: a hue, optionally bold or italic.
const fn hue(attributes: &'static str, foreground: &str) -> Style {
    let colour = StyleColor::Triplet(ColorTriplet::from_hex(foreground));
    let bytes = attributes.as_bytes();
    Style {
        bold: if bytes.len() == 1 && bytes[0] == b'1' { Some(true) } else { None },
        italic: if bytes.len() == 1 && bytes[0] == b'3' { Some(true) } else { None },
        foreground: Some(colour),
        ..Style::inherit()
    }
}

/// The search half of `src/chats/theme.py`, resolved by token name.
///
/// Held as a table rather than as SGR literals so every colour routes through the
/// downgrade rather than assuming the terminal is truecolor.
pub const THEME: &[(&str, Style)] = &[
    ("search.tick", hue("", "#5cc8a8")),
    ("search.title", hue("1", "#e6e8eb")),
    ("search.title.fallback", hue("3", "#9aa0a6")),
    ("search.dir", hue("", "#5cc8a8")),
    ("search.sep", hue("", "#4a4e54")),
    ("search.count", hue("1", "#c3c7cd")),
    ("search.label", hue("", "#7e8389")),
    ("search.id.head", hue("", "#4f9e86")),
    ("search.id.tail", hue("", "#646a70")),
    ("search.header", hue("", "#7e8389")),
    ("search.empty", hue("", "#878c92")),
    ("search.age.now", hue("", "#a9aeb4")),
    ("search.age.week", hue("", "#878c92")),
    ("search.age.month", hue("", "#6b7076")),
    ("search.age.old", hue("", "#565b61")),
    ("message.meta", hue("", "#646a70")),
    ("search.border.0", hue("", "#5cc8a8")),
    ("search.border.1", hue("", "#9d7cd8")),
    ("search.border.2", hue("", "#d8a657")),
    ("search.border.3", hue("", "#7aa2f7")),
    ("search.match", Style {
        bold: Some(true),
        foreground: Some(StyleColor::Triplet(ColorTriplet::from_hex("#14181d"))),
        background: Some(StyleColor::Triplet(ColorTriplet::from_hex("#e6b450"))),
        ..Style::inherit()
    }),
];

/// Look a theme token up.
///
/// Panics on an unknown token rather than rendering it unstyled: a typo that
/// silently drops colour from one span is exactly the divergence no comparator
/// normalising colour away would catch.
pub fn theme_style(token: &str) -> Style {
    THEME
        .iter()
        .find(|(name, _)| *name == token)
        .map(|(_, style)| *style)
        .unwrap_or_else(|| panic!("unknown theme token {token:?}"))
}

/// Render one styled run to bytes, honouring the terminal's colour capability.
///
/// Under [`ColorRendering::Suppressed`] the text is emitted bare. Under
/// [`ColorRendering::AttributesOnly`] the attributes survive and the colours do
/// not, which is what `NO_COLOR` means and is why bold outlives it.
pub fn render_segment(segment: &Segment, rendering: ColorRendering) -> String {
    // Rich's `Text.append` is a no-op on empty text, so an empty run contributes no
    // escape pair at all. Reached whenever a session id is exactly eight characters.
    if segment.text.is_empty() {
        return String::new();
    }
    // `Style.render` returns the text untouched when there is no colour system —
    // **including the link**, so a dumb terminal emits no OSC-8 either.
    if rendering == ColorRendering::Suppressed {
        return segment.text.clone();
    }

    let styled = match segment.style.map(|style| style.parameters(rendering)) {
        Some(parameters) if !parameters.is_empty() => {
            format!("\x1b[{parameters}m{}\x1b[0m", segment.text)
        }
        _ => segment.text.clone(),
    };

    // OSC-8 wraps **outside** the SGR pair. Measured against Rich rather than read:
    // `\x1b]8;id=N;URL\x1b\\` then `\x1b[4;34m…\x1b[0m` then `\x1b]8;;\x1b\\`.
    // A link on an unstyled run still gets the pair, because `Style.render` wraps
    // whatever it produced, styled or not.
    match &segment.link {
        Some(link) => format!(
            "\x1b]8;id={};{}\x1b\\{styled}\x1b]8;;\x1b\\",
            link.id, link.url
        ),
        None => styled,
    }
}

/// Expand tabs to 8-column stops, splitting the run at each one.
///
/// Rich expands tabs in `Text.wrap`, **at render time and across the assembled
/// line** — the raw text goes into `Text.append` untouched, so this belongs to the
/// line renderer and not to whatever produced the string. The stop is absolute over
/// the whole line, so a tab's width depends on every segment before it.
///
/// **Each tab splits the segment.** Rich emits the padded run and the text after it
/// as separate escape pairs carrying the same style, and never merges them — so a
/// port that pads in place produces identical characters and different bytes.
///
/// ```
/// use _native::search_views::{expand_tabs, Segment};
/// let expanded = expand_tabs(&[Segment::plain("a\tb")]);
/// assert_eq!(expanded.len(), 2);
/// assert_eq!(expanded[0].text, "a       ");   // to column 8
/// assert_eq!(expanded[1].text, "b");
/// ```
pub fn expand_tabs(segments: &[Segment]) -> Vec<Segment> {
    const TAB_STOP: usize = 8;
    if !segments.iter().any(|segment| segment.text.contains('\t')) {
        return segments.to_vec();
    }
    let metrics = CellMetrics::from_environment();
    let mut expanded: Vec<Segment> = Vec::new();
    let mut column = 0usize;
    for segment in segments {
        let mut pieces = segment.text.split('\t').peekable();
        while let Some(piece) = pieces.next() {
            let mut text = piece.to_string();
            column += metrics.cell_len(piece);
            if pieces.peek().is_some() {
                let padding = TAB_STOP - (column % TAB_STOP);
                text.push_str(&" ".repeat(padding));
                column += padding;
            }
            expanded.push(Segment {
                text,
                style: segment.style,
                link: segment.link.clone(),
            });
        }
    }
    expanded
}

/// Render a whole line, clipping it to the console width in cells the way a Rich
/// `Text` with `no_wrap=True, overflow="ellipsis"` does.
///
/// The clip is the second of two, and they count different units: the callers have
/// already elided by code points. Both are load-bearing.
pub fn render_line(
    segments: &[Segment],
    width: usize,
    metrics: &CellMetrics,
    rendering: ColorRendering,
) -> String {
    let expanded = expand_tabs(segments);
    let segments = &expanded[..];
    let plain: String = segments.iter().map(|segment| segment.text.as_str()).collect();
    if metrics.cell_len(&plain) <= width {
        return segments
            .iter()
            .map(|segment| render_segment(segment, rendering))
            .collect();
    }
    let mut rendered = String::new();
    let mut used = 0usize;
    for segment in segments {
        let segment_width = metrics.cell_len(&segment.text);
        if used + segment_width <= width - 1 {
            rendered.push_str(&render_segment(segment, rendering));
            used += segment_width;
            continue;
        }
        let kept = metrics.set_cell_size(&segment.text, width - 1 - used);
        rendered.push_str(&render_segment(
            &Segment {
                text: kept + "…",
                style: segment.style,
                link: segment.link.clone(),
            },
            rendering,
        ));
        return rendered;
    }
    rendered
}

/// Everything one coloured list row displays.
#[derive(Clone, Copy, Debug)]
pub struct ListRow<'a> {
    pub session_id: &'a str,
    pub headline: &'a str,
    pub headline_is_fallback: bool,
    /// The session's working directory, or `None` when it is unknown.
    pub directory: Option<&'a str>,
    pub provider: &'a str,
    pub show_provider: bool,
    pub match_count: usize,
    /// Age in seconds, or `None` when the session carries no modification time.
    pub age_seconds: Option<f64>,
}

fn match_word(count: usize) -> &'static str {
    if count == 1 { "match" } else { "matches" }
}

/// The two styled lines of one list row: a bold headline, then a dim facts line.
///
/// Both budgets count **code points**, because both come from `elide_to_width`.
/// The caller clips the assembled lines again, in cells.
pub fn list_row_lines(row: &ListRow, home: &str, width: usize) -> [Vec<Segment>; 2] {
    let age_label = row
        .age_seconds
        .map(humanize_age)
        .unwrap_or_else(|| "?".to_string());
    let age_token = row.age_seconds.map(age_style).unwrap_or("search.age.old");

    let title_line = vec![
        Segment::styled("▎ ", "search.tick"),
        Segment::styled(
            elide_to_width(row.headline, width.saturating_sub(2).max(8), Elision::Tail),
            if row.headline_is_fallback {
                "search.title.fallback"
            } else {
                "search.title"
            },
        ),
    ];

    let word = match_word(row.match_count);
    let mut reserved = format!(" · {}", row.session_id).chars().count()
        + format!(" · {} {word}", row.match_count).chars().count()
        + format!(" · {age_label}").chars().count();
    if row.show_provider {
        reserved += format!(" · {}", row.provider).chars().count();
    }
    let directory = match row.directory {
        Some(directory) => collapse_home(directory, home),
        None => "(unknown directory)".to_string(),
    };
    let directory = elide_to_width(
        &directory,
        width.saturating_sub(4).saturating_sub(reserved).max(16),
        Elision::Middle,
    );

    let mut facts_line = vec![
        Segment::plain("  "),
        Segment::styled(directory, "search.dir"),
    ];
    if row.show_provider {
        facts_line.push(Segment::styled(" · ", "search.sep"));
        facts_line.push(Segment::styled(row.provider.to_string(), "search.label"));
    }
    facts_line.push(Segment::styled(" · ", "search.sep"));
    facts_line.push(Segment::styled(row.match_count.to_string(), "search.count"));
    facts_line.push(Segment::styled(format!(" {word}"), "search.label"));
    facts_line.push(Segment::styled(" · ", "search.sep"));
    facts_line.push(Segment::styled(age_label, age_token));
    facts_line.push(Segment::styled(" · ", "search.sep"));
    let head: String = row.session_id.chars().take(8).collect();
    let tail: String = row.session_id.chars().skip(8).collect();
    facts_line.push(Segment::styled(head, "search.id.head"));
    facts_line.push(Segment::styled(tail, "search.id.tail"));

    [title_line, facts_line]
}

/// The trailing summary line, whose count is known only once the scan ends.
pub fn list_summary_line(count: usize) -> Vec<Segment> {
    let word = if count == 1 { "session" } else { "sessions" };
    vec![
        Segment::styled(format!("{count} {word}"), "search.header"),
        Segment::styled("  ·  newest first", "search.sep"),
    ]
}

/// One coloured list row, ready to write, including the blank line after it.
///
/// Returns a `String` and touches no I/O, so the engine keeps its sink and its
/// early-close check. The seam is one-directional: the engine calls views, views
/// return bytes, nothing flows back.
pub fn list_row(
    row: &ListRow,
    home: &str,
    width: usize,
    metrics: &CellMetrics,
    rendering: ColorRendering,
) -> String {
    let [title, facts] = list_row_lines(row, home, width);
    format!(
        "{}\n{}\n\n",
        render_line(&title, width, metrics, rendering),
        render_line(&facts, width, metrics, rendering)
    )
}

/// The trailing summary line, ready to write.
pub fn list_summary(
    count: usize,
    width: usize,
    metrics: &CellMetrics,
    rendering: ColorRendering,
) -> String {
    format!(
        "{}\n",
        render_line(&list_summary_line(count), width, metrics, rendering)
    )
}

/// The panel's border title: tick, headline, full session id, age.
///
/// The headline's budget subtracts the width of the metadata that follows it, so
/// unlike the list row's budget this one is **not** inert — the headline competes
/// with the id and the age for one box. `width` is the console width, not the
/// panel interior.
pub fn panel_title(row: &ListRow, width: usize) -> Vec<Segment> {
    let age_label = row
        .age_seconds
        .map(humanize_age)
        .unwrap_or_else(|| "?".to_string());
    let age_token = row.age_seconds.map(age_style).unwrap_or("search.age.old");
    let metadata_suffix_width = format!("  ·  {}  ·  {age_label}", row.session_id)
        .chars()
        .count();

    let head: String = row.session_id.chars().take(8).collect();
    let tail: String = row.session_id.chars().skip(8).collect();
    vec![
        Segment::styled("▎ ", "search.tick"),
        Segment::styled(
            elide_to_width(
                row.headline,
                width
                    .saturating_sub(2)
                    .saturating_sub(metadata_suffix_width)
                    .max(8),
                Elision::Tail,
            ),
            if row.headline_is_fallback {
                "search.title.fallback"
            } else {
                "search.title"
            },
        ),
        Segment::styled("  ·  ", "search.sep"),
        Segment::styled(head, "search.id.head"),
        Segment::styled(tail, "search.id.tail"),
        Segment::styled("  ·  ", "search.sep"),
        Segment::styled(age_label, age_token),
    ]
}

/// The facts line inside the panel: directory, provider, match count.
///
/// The directory budget is `width - 28` against a flat 28, where the list row
/// computes its reserve from the text it actually emits. The two are not the same
/// rule and must not be shared.
pub fn panel_facts_line(row: &ListRow, home: &str, width: usize) -> Vec<Segment> {
    let directory = match row.directory {
        Some(directory) => collapse_home(directory, home),
        None => "(unknown directory)".to_string(),
    };
    let word = match_word(row.match_count);
    vec![
        Segment::styled(
            elide_to_width(&directory, width.saturating_sub(28).max(16), Elision::Middle),
            "search.dir",
        ),
        Segment::styled(" · ", "search.sep"),
        Segment::styled(row.provider.to_string(), "search.label"),
        Segment::styled(" · ", "search.sep"),
        Segment::styled(row.match_count.to_string(), "search.count"),
        Segment::styled(format!(" {word}"), "search.label"),
    ]
}

/// Border hues cycled per conversation, so the panel's left edge changes colour at
/// every conversation boundary — the orientation cue that survives scrolling.
pub const BORDER_CYCLE: [&str; 4] = [
    "search.border.0",
    "search.border.1",
    "search.border.2",
    "search.border.3",
];

/// Draw the conversation panel around already-styled body lines.
///
/// Reproduces Rich's `Panel` with `box.ROUNDED`, `title_align="left"` and
/// `padding=(0, 1)`. Each border piece carries its own escape pair rather than
/// being merged with its neighbour, which is what Rich emits and is visible in the
/// bytes.
///
/// `body` lines are rendered as given; this function owns only the frame.
pub fn panel_lines(
    title: &[Segment],
    body: &[Vec<Segment>],
    ordinal: usize,
    width: usize,
    metrics: &CellMetrics,
    rendering: ColorRendering,
) -> Vec<String> {
    let border = BORDER_CYCLE[ordinal % BORDER_CYCLE.len()];
    let paint = |text: &str| render_segment(&Segment::styled(text.to_string(), border), rendering);
    let interior = width.saturating_sub(4);

    let mut lines = vec![top_border(
        title, border, width, metrics, rendering, &paint,
    )];
    for segments in body {
        let rendered = render_line(segments, interior, metrics, rendering);
        let used = metrics.cell_len(&plain_text(segments)).min(interior);
        lines.push(format!(
            "{} {rendered}{} {}",
            paint("│"),
            " ".repeat(interior - used),
            paint("│")
        ));
    }
    lines.push(paint(&format!("╰{}╯", "─".repeat(width.saturating_sub(2)))));
    lines
}

fn plain_text(segments: &[Segment]) -> String {
    segments.iter().map(|segment| segment.text.as_str()).collect()
}

/// The top border, with the title embedded after `╭─ ` and the run of dashes
/// sized to fill what the title leaves.
///
/// A title too long for the box is cut at `width - 5` and the ellipsis takes the
/// style that was active where the cut landed.
fn top_border(
    title: &[Segment],
    border: &'static str,
    width: usize,
    metrics: &CellMetrics,
    rendering: ColorRendering,
    paint: &dyn Fn(&str) -> String,
) -> String {
    let inner = width.saturating_sub(4);
    let title_width = metrics.cell_len(&plain_text(title));
    let dashes = inner.saturating_sub(title_width + 2);

    // Rich assembles the whole strip between the corners — a space, the title,
    // another space, then dashes to fill — and clips *that* to `width - 4` in one
    // pass. There is no separate fits-or-truncates decision, and writing one gets
    // the boundary wrong: a title of exactly `width - 5` overflows, because the
    // trailing space is inside the strip being measured.
    let mut strip = vec![Segment::styled(" ", border)];
    strip.extend(title.iter().cloned());
    strip.push(Segment::styled(" ", border));
    if dashes > 0 {
        strip.push(Segment::styled("─".repeat(dashes), border));
    }
    format!(
        "{}{}{}",
        paint("╭─"),
        render_line(&strip, inner, metrics, rendering),
        paint("─╮")
    )
}

#[cfg(test)]
mod chrome_tests {
    use super::*;
    use crate::terminal::ColorSystem;

    /// The pairing `age_pairing_gate.py` exists to protect. If this ever reads
    /// "same bucket" for every age, someone has unified the two tables.
    #[test]
    fn the_age_label_and_its_colour_disagree_by_one_bucket() {
        let day = 86400.0;
        let pairs = [
            (30.0, "now", "search.age.now"),
            (90.0, "1m", "search.age.now"),
            (3.0 * 3600.0, "3h", "search.age.now"),
            (3.0 * day, "3d", "search.age.week"),
            (5.0 * day, "5d", "search.age.week"),
            (10.0 * day, "1w", "search.age.month"),
            (20.0 * day, "2w", "search.age.month"),
            (45.0 * day, "1mo", "search.age.old"),
            (200.0 * day, "6mo", "search.age.old"),
            (400.0 * day, "1y", "search.age.old"),
        ];
        for (seconds, label, style) in pairs {
            assert_eq!(humanize_age(seconds), label, "at {seconds}s");
            assert_eq!(age_style(seconds), style, "at {seconds}s");
        }
        assert_ne!(
            age_style(3.0 * day),
            "search.age.now",
            "A '3d' row painted with the 'now' colour means the tables were unified."
        );
    }

    #[test]
    fn twelve_thirty_day_months_land_short_of_a_year() {
        assert_eq!(humanize_age(359.0 * 86400.0), "11mo");
        assert_eq!(humanize_age(360.0 * 86400.0), "12mo");
        assert_eq!(humanize_age(364.0 * 86400.0), "12mo");
        assert_eq!(humanize_age(365.0 * 86400.0), "1y");
    }

    #[test]
    fn collapse_home_matches_a_prefix_and_mangles_siblings() {
        assert_eq!(collapse_home("/Users/ada", "/Users/ada"), "~");
        assert_eq!(collapse_home("/Users/adam/dev", "/Users/ada"), "~m/dev");
        assert_eq!(collapse_home("/Users/ad/dev", "/Users/ada"), "/Users/ad/dev");
    }

    #[test]
    fn middle_elision_keeps_the_tail_and_never_returns_the_whole_string() {
        assert_eq!(elide_to_width("abcdefghij", 4, Elision::Middle), "ab…j");
        // available = 1 -> right = 0, and Python guards `text[-0:]` here.
        assert_eq!(elide_to_width("abcdefghij", 2, Elision::Middle), "a…");
        assert_eq!(elide_to_width("abcdefghij", 1, Elision::Tail), "…");
        assert_eq!(elide_to_width("abcdefghij", 0, Elision::Tail), "");
    }

    #[test]
    fn no_color_keeps_the_attribute_and_drops_the_hue() {
        let bold_title = Segment::styled("title", "search.title");
        assert_eq!(
            render_segment(&bold_title, ColorRendering::Colored(ColorSystem::Truecolor)),
            "\x1b[1;38;2;230;232;235mtitle\x1b[0m"
        );
        assert_eq!(
            render_segment(&bold_title, ColorRendering::AttributesOnly),
            "\x1b[1mtitle\x1b[0m"
        );
        assert_eq!(
            render_segment(&bold_title, ColorRendering::Suppressed),
            "title"
        );
    }

    /// Python's own answers for the four display helpers, imported from
    /// `probes/utils-oracle.json` and regenerated by `generate_utils_oracle.py`.
    ///
    /// The unit tests above encode my reading of `utils.py`. This encodes
    /// `utils.py`. Three of these four are preserved because they are wrong, so a
    /// gate that agrees with a careful reading rather than with the product is
    /// exactly the failure this class produces.
    #[test]
    fn every_recorded_python_answer_reproduces() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join("utils-oracle.json");
        let bytes = std::fs::read(&path)
            .unwrap_or_else(|error| panic!("utils oracle missing at {}: {error}", path.display()));
        let oracle: serde_json::Value =
            serde_json::from_slice(&bytes).expect("the utils oracle is valid JSON");

        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();

        for row in oracle["ages"].as_array().expect("recorded ages") {
            let seconds = row["seconds"].as_f64().expect("an age in seconds");
            let label = row["label"].as_str().expect("a recorded label");
            let style = row["style"].as_str().expect("a recorded style");
            compared += 2;
            if humanize_age(seconds) != label {
                mismatches.push(format!(
                    "humanize_age({seconds}): Python {label:?}, got {:?}",
                    humanize_age(seconds)
                ));
            }
            if age_style(seconds) != style {
                mismatches.push(format!(
                    "age_style({seconds}): Python {style:?}, got {:?}",
                    age_style(seconds)
                ));
            }
        }

        for row in oracle["elisions"].as_array().expect("recorded elisions") {
            let text = row["text"].as_str().expect("recorded text");
            let width = row["width"].as_u64().expect("a recorded width") as usize;
            let where_to_elide = match row["where"].as_str().expect("a recorded position") {
                "middle" => Elision::Middle,
                _ => Elision::Tail,
            };
            let expected = row["result"].as_str().expect("a recorded result");
            compared += 1;
            let actual = elide_to_width(text, width, where_to_elide);
            if actual != expected {
                mismatches.push(format!(
                    "elide_to_width({text:?}, {width}, {where_to_elide:?}): \
                     Python {expected:?}, got {actual:?}"
                ));
            }
        }

        for row in oracle["collapse_home"].as_array().expect("recorded paths") {
            let path = row["path"].as_str().expect("a recorded path");
            let home = row["home"].as_str().expect("a recorded home");
            let expected = row["result"].as_str().expect("a recorded result");
            compared += 1;
            let actual = collapse_home(path, home);
            if actual != expected {
                mismatches.push(format!(
                    "collapse_home({path:?}, {home:?}): Python {expected:?}, got {actual:?}"
                ));
            }
        }

        assert!(
            compared > 500,
            "Expected the full recorded corpus, compared only {compared} cases."
        );
        assert!(
            mismatches.is_empty(),
            "{} of {compared} cases differ from Python:\n{}",
            mismatches.len(),
            mismatches.iter().take(10).cloned().collect::<Vec<_>>().join("\n")
        );
    }

    /// The bytes Python's `_build_search_list_row` actually emits, over a grid of
    /// widths, headlines, directories, ages, providers and match counts.
    ///
    /// This is the gate for the whole list view. Everything above it tests a part.
    #[test]
    fn every_recorded_list_row_reproduces_python_byte_for_byte() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join("list-row-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("list row oracle missing at {}: {error}", path.display())
        });
        let oracle: serde_json::Value =
            serde_json::from_slice(&bytes).expect("the list row oracle is valid JSON");
        let home = oracle["home"].as_str().expect("a recorded home");
        let metrics = CellMetrics::for_version(None);
        let rendering = ColorRendering::Colored(ColorSystem::Truecolor);

        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();
        for entry in oracle["rows"].as_array().expect("recorded rows") {
            let width = entry["width"].as_u64().expect("a width") as usize;
            let directory = entry["directory"].as_str();
            let row = ListRow {
                session_id: entry["session_id"].as_str().expect("an id"),
                headline: entry["headline"].as_str().expect("a headline"),
                headline_is_fallback: entry["headline_is_fallback"]
                    .as_bool()
                    .expect("a fallback flag"),
                directory,
                provider: entry["provider"].as_str().expect("a provider"),
                show_provider: entry["show_provider"].as_bool().expect("a provider flag"),
                match_count: entry["match_count"].as_u64().expect("a match count") as usize,
                age_seconds: entry["age_seconds"].as_f64(),
            };
            let [title, facts] = list_row_lines(&row, home, width);
            for (segments, key) in [(title, "title_line"), (facts, "facts_line")] {
                compared += 1;
                let expected = entry[key].as_str().expect("a recorded line");
                let actual = render_line(&segments, width, &metrics, rendering);
                if actual != expected {
                    mismatches.push(format!(
                        "{key} @ width {width}, headline {:?}, dir {:?}, age {:?}:\n  \
                         Python {expected:?}\n  got    {actual:?}",
                        row.headline, directory, row.age_seconds
                    ));
                }
            }
        }
        assert!(
            compared > 40_000,
            "Expected the full recorded grid, compared only {compared} lines."
        );
        assert!(
            mismatches.is_empty(),
            "{} of {compared} rendered lines differ from Python:\n{}",
            mismatches.len(),
            mismatches.iter().take(4).cloned().collect::<Vec<_>>().join("\n")
        );
    }

    /// The headline's `width - 2` budget is **inert**, and this pins that it stays
    /// inert rather than that it is right.
    ///
    /// Falsifying the list-row gate turned up a mutation it could not catch:
    /// changing the budget from `max(8, width - 2)` to `max(8, width)` produces
    /// identical bytes. That is not a thin corpus — measured against Python at
    /// every width from 2 to 129 over seven headline shapes, the two budgets never
    /// differ. The outer cell clip subsumes the inner one, because tail elision
    /// only shortens and both budgets sit at or above `width - 2`.
    ///
    /// So it is kept because Python has it, not because it does anything. If this
    /// test ever fails, the outer clip has changed and the budget has become
    /// load-bearing — at which point it needs a real gate.
    #[test]
    fn the_headline_budget_is_subsumed_by_the_outer_cell_clip() {
        let metrics = CellMetrics::for_version(None);
        let row = ListRow {
            session_id: "0123456789abcdef",
            headline: "a considerably longer session title that will not fit",
            headline_is_fallback: false,
            directory: Some("/Users/ada/dev/chats"),
            provider: "claude",
            show_provider: false,
            match_count: 3,
            age_seconds: Some(3.0 * 86400.0),
        };
        for width in 2..130usize {
            let [product, _] = list_row_lines(&row, "/Users/ada", width);
            let widened = vec![
                Segment::styled("▎ ", "search.tick"),
                Segment::styled(
                    elide_to_width(row.headline, width.max(8), Elision::Tail),
                    "search.title",
                ),
            ];
            assert_eq!(
                render_line(&product, width, &metrics, ColorRendering::Suppressed),
                render_line(&widened, width, &metrics, ColorRendering::Suppressed),
                "at width {width} the headline budget became observable"
            );
        }
    }

    /// The bytes Rich's `Panel` emits for the conversation frame, over widths,
    /// titles, bodies and every border in the cycle.
    #[test]
    fn every_recorded_panel_frame_reproduces_rich_byte_for_byte() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join("panel-oracle.json");
        let bytes = std::fs::read(&path)
            .unwrap_or_else(|error| panic!("panel oracle missing at {}: {error}", path.display()));
        let oracle: serde_json::Value =
            serde_json::from_slice(&bytes).expect("the panel oracle is valid JSON");
        let metrics = CellMetrics::for_version(None);
        let rendering = ColorRendering::Colored(ColorSystem::Truecolor);

        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();
        for entry in oracle["rows"].as_array().expect("recorded panels") {
            let width = entry["width"].as_u64().expect("a width") as usize;
            let ordinal = entry["ordinal"].as_u64().expect("an ordinal") as usize;
            let title: Vec<Segment> = entry["title_parts"]
                .as_array()
                .expect("title parts")
                .iter()
                .map(|part| {
                    let text = part[0].as_str().expect("segment text").to_string();
                    let token = part[1].as_str().expect("a theme token");
                    let token = THEME
                        .iter()
                        .find(|(name, _)| *name == token)
                        .map(|(name, _)| *name)
                        .unwrap_or_else(|| panic!("unknown token {token:?}"));
                    Segment::styled(text, token)
                })
                .collect();
            let body: Vec<Vec<Segment>> = entry["body"]
                .as_array()
                .expect("body lines")
                .iter()
                .map(|line| {
                    let line = line.as_str().expect("a body line");
                    // `\x00` marks a styled body line in the corpus, so the frame's
                    // padding is proved against a styled run rather than only plain.
                    match line.strip_prefix('\u{0}') {
                        Some(styled) => vec![Segment::styled(styled.to_string(), "search.title")],
                        None => vec![Segment::plain(line)],
                    }
                })
                .collect();
            let expected: Vec<&str> = entry["lines"]
                .as_array()
                .expect("recorded lines")
                .iter()
                .map(|line| line.as_str().expect("a rendered line"))
                .collect();
            let actual = panel_lines(&title, &body, ordinal, width, &metrics, rendering);
            compared += expected.len();
            if actual.len() != expected.len() {
                mismatches.push(format!(
                    "panel @ width {width}, title {}, body {}: Rich emitted {} lines, got {}",
                    entry["title"], entry["body_name"], expected.len(), actual.len()
                ));
                continue;
            }
            for (index, (got, want)) in actual.iter().zip(expected.iter()).enumerate() {
                if got != want {
                    mismatches.push(format!(
                        "panel @ width {width}, title {}, body {}, line {index}:\n  \
                         Rich {want:?}\n  got  {got:?}",
                        entry["title"], entry["body_name"]
                    ));
                }
            }
        }
        assert!(
            compared > 2_000,
            "Expected the full recorded panel corpus, compared only {compared} lines."
        );
        assert!(
            mismatches.is_empty(),
            "{} of {compared} panel lines differ from Rich:\n{}",
            mismatches.len(),
            mismatches.iter().take(4).cloned().collect::<Vec<_>>().join("\n")
        );
    }

    /// A whole conversation panel built from Python's own `_panel_title` and
    /// `_panel_facts_line`, inside Rich's own frame.
    #[test]
    fn every_recorded_panel_view_reproduces_python_byte_for_byte() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join("panel-view-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("panel view oracle missing at {}: {error}", path.display())
        });
        let oracle: serde_json::Value =
            serde_json::from_slice(&bytes).expect("the panel view oracle is valid JSON");
        let home = oracle["home"].as_str().expect("a recorded home");
        let metrics = CellMetrics::for_version(None);
        let rendering = ColorRendering::Colored(ColorSystem::Truecolor);

        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();
        for entry in oracle["rows"].as_array().expect("recorded panels") {
            let width = entry["width"].as_u64().expect("a width") as usize;
            let row = ListRow {
                session_id: entry["session_id"].as_str().expect("an id"),
                headline: entry["headline"].as_str().expect("a headline"),
                headline_is_fallback: entry["headline_is_fallback"]
                    .as_bool()
                    .expect("a fallback flag"),
                directory: entry["directory"].as_str(),
                provider: entry["provider"].as_str().expect("a provider"),
                show_provider: false,
                match_count: entry["match_count"].as_u64().expect("a count") as usize,
                age_seconds: entry["age_seconds"].as_f64(),
            };
            let mut body: Vec<Vec<Segment>> = Vec::new();
            if entry["emit_metadata"].as_bool().expect("a metadata flag") {
                body.push(panel_facts_line(&row, home, width));
                body.push(vec![]);
            }
            body.push(vec![Segment::plain("body line")]);

            let expected: Vec<&str> = entry["lines"]
                .as_array()
                .expect("recorded lines")
                .iter()
                .map(|line| line.as_str().expect("a rendered line"))
                .collect();
            let actual = panel_lines(
                &panel_title(&row, width),
                &body,
                entry["ordinal"].as_u64().expect("an ordinal") as usize,
                width,
                &metrics,
                rendering,
            );
            compared += expected.len();
            if actual.len() != expected.len() {
                mismatches.push(format!(
                    "panel @ width {width}: Python emitted {} lines, got {}",
                    expected.len(),
                    actual.len()
                ));
                continue;
            }
            for (index, (got, want)) in actual.iter().zip(expected.iter()).enumerate() {
                if got != want {
                    mismatches.push(format!(
                        "panel @ width {width}, headline {:?}, age {:?}, line {index}:\n  \
                         Python {want:?}\n  got    {got:?}",
                        row.headline, row.age_seconds
                    ));
                }
            }
        }
        assert!(
            compared > 10_000,
            "Expected the full recorded panel corpus, compared only {compared} lines."
        );
        assert!(
            mismatches.is_empty(),
            "{} of {compared} panel lines differ from Python:\n{}",
            mismatches.len(),
            mismatches.iter().take(4).cloned().collect::<Vec<_>>().join("\n")
        );
    }

    #[test]
    fn an_unstyled_token_never_renders_silently() {
        assert!(
            std::panic::catch_unwind(|| theme_style("search.nonexistent")).is_err(),
            "An unknown token must fail loudly, not render unstyled."
        );
    }

    #[test]
    fn a_line_is_clipped_to_the_console_width_in_cells() {
        let metrics = CellMetrics::for_version(None);
        let segments = vec![
            Segment::styled("▎ ", "search.tick"),
            Segment::plain("你好".repeat(18) + "你…"),
        ];
        let rendered = render_line(&segments, 40, &metrics, ColorRendering::Suppressed);
        assert_eq!(metrics.cell_len(&rendered), 40);
        assert!(rendered.ends_with(" …"), "got {rendered:?}");
    }
}

// ---------------------------------------------------------------- the sink

/// Everything the coloured list sink needs that does not come from a hit.
pub struct ColouredListOutput<'a> {
    pub home: &'a str,
    pub width: usize,
    pub metrics: CellMetrics,
    pub rendering: ColorRendering,
    /// Whether rows carry a provider column. The engine computes this from the
    /// **discovery** rows rather than from gate survivors, so it is passed in.
    pub show_provider: bool,
    pub now: chrono::NaiveDateTime,
    /// `flags.paging`. Colour is implied — this sink only exists on the coloured path.
    pub paging: bool,
}

/// The coloured `--list` view: two styled lines per hit, then a summary.
///
/// **Only the list mode.** The conversation panel needs a session renderer that
/// turns one message into styled lines, and no such thing exists in the tree yet.
/// A sink covering panels would be a half-implementation whose output nobody could
/// check, so this one is named for what it does.
///
/// The pager lives here because Python's does: `use_pager` is
/// `color and paging and mode != ONLY_ID`, so it exists only on paths this sink
/// serves. `closed()` reports it, and the engine reads that to stop scanning —
/// **quitting `less` must stop the work behind it.** A sink that keeps accepting
/// hits after the reader has gone produces identical output, none, while burning
/// the rest of the corpus.
pub struct ColouredListSink<'a> {
    output: ColouredListOutput<'a>,
    pager: Option<crate::pager::Pager>,
    found: usize,
    closed: bool,
}

impl<'a> ColouredListSink<'a> {
    pub fn new(output: ColouredListOutput<'a>) -> ColouredListSink<'a> {
        let pager = output.paging.then(crate::pager::Pager::spawn);
        ColouredListSink { output, pager, found: 0, closed: false }
    }

    /// Project a hit onto the row this view draws.
    ///
    /// `ListRow` is deliberately not the engine's type: views borrows the few
    /// fields it displays so it does not depend on the shape of a search hit.
    fn row<'hit>(&self, hit: &'hit SearchHit, session_id: &'hit str) -> ListRow<'hit> {
        let (headline, headline_is_fallback) = hit.headline();
        ListRow {
            session_id,
            headline,
            headline_is_fallback,
            directory: hit.cwd.as_deref(),
            provider: hit.metadata.provider.as_str(),
            show_provider: self.output.show_provider,
            match_count: hit.match_count(),
            age_seconds: hit.age_seconds(self.output.now),
        }
    }

    fn write(&mut self, chunk: &str) {
        match &mut self.pager {
            Some(pager) => {
                pager.write(chunk);
                if pager.closed() {
                    self.closed = true;
                }
            }
            None => {
                let mut stdout = std::io::stdout();
                if stdout.write_all(chunk.as_bytes()).is_err() {
                    self.closed = true;
                }
            }
        }
    }

    /// Hand the pager back so the caller can wait for the reader to dismiss it.
    pub fn into_pager(self) -> Option<crate::pager::Pager> {
        self.pager
    }
}

impl ColouredListSink<'_> {
    /// The bytes one hit produces, with no I/O — the seam the gate compares.
    pub fn render(&self, hit: &SearchHit) -> String {
        let session_id = crate::search_output::display_session_id(
            &hit.metadata.path,
            hit.metadata.provider,
            hit.metadata.native_id.as_deref(),
        );
        list_row(
            &self.row(hit, &session_id),
            self.output.home,
            self.output.width,
            &self.output.metrics,
            self.output.rendering,
        )
    }

    /// The trailing summary, or nothing when no hit was emitted.
    pub fn render_summary(&self) -> Option<String> {
        (self.found > 0).then(|| {
            list_summary(
                self.found,
                self.output.width,
                &self.output.metrics,
                self.output.rendering,
            )
        })
    }

    pub fn found(&self) -> usize {
        self.found
    }
}

impl HitSink for ColouredListSink<'_> {
    fn emit(&mut self, hit: &SearchHit) {
        let rendered = self.render(hit);
        self.write(&rendered);
        self.found += 1;
    }

    fn closed(&self) -> bool {
        self.closed
    }

    fn emit_error(&mut self, message: &str) {
        // **The gap this comment used to describe is closed.** Python's stderr
        // consoles colour whenever stderr is a tty regardless of `--color`, and that
        // is now reproduced in one place — `print_stderr_wrapped` carries the colour,
        // the stderr-derived dumbness and the zero-width return together, so every
        // sink and every direct site answer the same way. Gated on 240 bytes frozen
        // from `ch-legacy` in `tests/data/stderr-colour/`.
        crate::search_run::print_stderr_wrapped(message, StderrConsole::Error);
    }

    fn finish(&mut self) {
        // Python's condition is `mode == LIST and color and found and not closed`.
        // The engine holds the not-closed half because it belongs to the pager;
        // mode and colour are settled by this sink existing at all; `found` is mine.
        if let Some(summary) = self.render_summary() {
            self.write(&summary);
        }
    }
}

#[cfg(test)]
mod sink_tests {
    use super::*;
    use crate::search_confirm::{SearchHit, SessionMetadata};
    use crate::session;
    use chrono::NaiveDateTime;
    use std::path::PathBuf;

    fn now() -> NaiveDateTime {
        NaiveDateTime::parse_from_str("2026-06-15T12:00:00", "%Y-%m-%dT%H:%M:%S").expect("a fixed clock")
    }

    /// A hit shaped to produce a given row, so the projection is what is tested.
    fn hit_for(
        session_id: &str,
        headline: &str,
        is_fallback: bool,
        directory: Option<&str>,
        match_count: usize,
        age_seconds: Option<f64>,
    ) -> SearchHit {
        SearchHit {
            metadata: SessionMetadata {
                path: PathBuf::from(format!("{session_id}.jsonl")),
                provider: session::Provider::Claude,
                ctime: None,
                mtime: age_seconds.map(|age| now() - chrono::Duration::milliseconds((age * 1000.0) as i64)),
                native_id: None,
                forked_from: None,
            },
            messages: Vec::new(),
            match_indices: Vec::new(),
            progressive: Default::default(),
            cwd: directory.map(str::to_string),
            matching_summaries: Vec::new(),
            // Contributes to `match_count` and never to `headline`, so the count
            // can be set without disturbing the headline under test.
            matching_custom_titles: vec![String::new(); match_count],
            last_custom_title: (!is_fallback).then(|| headline.to_string()),
        }
    }

    fn list_sink(width: usize, show_provider: bool) -> ColouredListSink<'static> {
        ColouredListSink::new(ColouredListOutput {
            home: "/Users/ada",
            width,
            metrics: CellMetrics::for_version(None),
            rendering: ColorRendering::Colored(crate::terminal::ColorSystem::Truecolor),
            show_provider,
            now: now(),
            // No pager: spawning `less` in a unit test would block on a reader.
            paging: false,
        })
    }

    /// The sink's bytes against Python's, driven from a `SearchHit` rather than a
    /// pre-built row — so this gates the **projection** that the row oracle cannot.
    #[test]
    fn the_sink_reproduces_pythons_bytes_from_a_hit() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join("list-row-oracle.json");
        let oracle: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&path).expect("the list row oracle")).expect("valid JSON");

        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();
        for entry in oracle["rows"].as_array().expect("rows") {
            let width = entry["width"].as_u64().expect("a width") as usize;
            let session_id = entry["session_id"].as_str().expect("an id");
            let hit = hit_for(
                session_id,
                entry["headline"].as_str().expect("a headline"),
                entry["headline_is_fallback"].as_bool().expect("a flag"),
                entry["directory"].as_str(),
                entry["match_count"].as_u64().expect("a count") as usize,
                entry["age_seconds"].as_f64(),
            );
            let expected = format!(
                "{}\n{}\n\n",
                entry["title_line"].as_str().expect("a title line"),
                entry["facts_line"].as_str().expect("a facts line")
            );
            let actual = list_sink(width, entry["show_provider"].as_bool().expect("a flag")).render(&hit);
            compared += 1;
            if actual != expected {
                mismatches.push(format!(
                    "@ width {width}, headline {:?}:\n  Python {expected:?}\n  got    {actual:?}",
                    entry["headline"]
                ));
            }
        }
        assert!(compared > 20_000, "Expected the full grid, compared {compared}.");
        assert!(
            mismatches.is_empty(),
            "{} of {compared} rendered hits differ from Python:\n{}",
            mismatches.len(),
            mismatches.iter().take(3).cloned().collect::<Vec<_>>().join("\n")
        );
    }

    /// Python emits no summary when nothing was found, and the count is the hits
    /// emitted rather than anything the engine passes in.
    #[test]
    fn the_summary_counts_emitted_hits_and_is_absent_at_zero() {
        let mut sink = list_sink(60, false);
        assert_eq!(sink.render_summary(), None, "no hits must produce no summary");

        let hit = hit_for("0123456789ab", "a title", false, Some("/Users/ada/dev"), 1, Some(30.0));
        for _ in 0..3 {
            let rendered = sink.render(&hit);
            assert!(!rendered.is_empty());
            sink.found += 1;
        }
        assert_eq!(sink.found(), 3);
        let summary = sink.render_summary().expect("three hits produce a summary");
        assert!(summary.contains("3 sessions"), "got {summary:?}");
        assert!(summary.contains("newest first"), "got {summary:?}");

        let mut single = list_sink(60, false);
        single.found = 1;
        assert!(
            single.render_summary().expect("one hit").contains("1 session"),
            "the singular form is not 'sessions'"
        );
    }

    /// An empty custom title is falsy in Python and must reach the fallback style.
    #[test]
    fn an_empty_custom_title_falls_through_to_the_fallback_style() {
        let hit = SearchHit {
            last_custom_title: Some(String::new()),
            ..hit_for("0123456789ab", "unused", true, None, 1, Some(30.0))
        };
        let rendered = list_sink(60, false).render(&hit);
        assert!(
            rendered.contains("(untitled session)"),
            "an empty title must fall through, got {rendered:?}"
        );
        // The italic fallback style, not the bold real-title one.
        assert!(rendered.contains("\x1b[3;38;2;154;160;166m"), "got {rendered:?}");
    }
}

// ------------------------------------------------------------ stderr consoles

/// Which of the product's stderr consoles a message goes to.
///
/// **`--color` reaches none of them.** It is passed to `init_module_console` for
/// stdout only, so stderr colour follows stderr's own tty-ness and
/// `ch search nomatch --color never 2>/dev/tty` is coloured. Preserved, not
/// repaired: a port resolving the colour choice once and applying it to all four
/// consoles is more correct and diverges on every no-results search run in a
/// terminal.
///
/// A fourth console, `formatting.py:698`, *does* honour the flag — so the correct
/// pattern sits one file from these three, and a reader who finds it will be
/// tempted to bring these into line. That is the change this comment exists to
/// stop.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StderrConsole {
    /// `print_hint`. **Themed**, so its grey is an RGB triple that downgrades.
    Hint,
    /// `print_error`. Built with **no theme**, so `"red"` is the palette index and
    /// stays `31` at every colour tier rather than becoming a triple.
    Error,
    /// `print_warning`. No theme either; `"yellow"` is palette index 3.
    Warning,
}

impl StderrConsole {
    fn base(self) -> Style {
        match self {
            StderrConsole::Hint => Style::colour(StyleColor::Triplet(
                ColorTriplet::from_hex("#878c92"),
            )),
            StderrConsole::Error => Style::colour(StyleColor::Palette(1)),
            StderrConsole::Warning => Style::colour(StyleColor::Palette(3)),
        }
    }
}

/// The subset of Rich's `ReprHighlighter` the product's stderr messages reach.
///
/// Not the whole highlighter: measured against every message shape the product
/// emits, only these five rules ever fire. The tag and attribute rules need `<` or
/// `=`, which none of them contain.
///
/// **A port that applies the base style and stops is wrong on every hint**, because
/// every no-results hint carries a quoted search term and `repr.str` paints it.
fn highlight_spans(message: &str) -> Vec<(usize, usize, Style)> {
    let bold = Style { bold: Some(true), ..Style::inherit() };
    let mut spans: Vec<(usize, usize, Style)> = Vec::new();

    // Rule order is Rich's: the brace rule is its own regex applied first, then
    // the combined alternation layers on top.
    for (offset, character) in message.char_indices() {
        if matches!(character, '[' | ']' | '{' | '}' | '(' | ')') {
            spans.push((offset, offset + character.len_utf8(), bold));
        }
    }

    // **One alternation, not a pattern per rule.** Rich combines these into a
    // single regex, so scanning is leftmost-first and an earlier alternative
    // *consumes* the region an later one would have matched inside. That is not a
    // detail: `path` swallows `/x/1.jsonl` whole, which is the only reason
    // `number` does not fire on the `1.` in a filename. Applying the rules
    // independently paints a bold cyan `1.` inside every session filename.
    for found in COMBINED_PATTERN.captures_iter(message) {
        for (name, style) in [
            ("uuid", Style::colour(StyleColor::Palette(11))),
            ("number", Style { foreground: Some(StyleColor::Palette(6)), bold: Some(true), ..Style::inherit() }),
            ("path", Style::colour(StyleColor::Palette(5))),
            ("filename", Style::colour(StyleColor::Palette(13))),
            // `repr.str` sets italic and bold to false, so it clears them.
            ("str", Style { foreground: Some(StyleColor::Palette(2)), bold: Some(false), italic: Some(false), ..Style::inherit() }),
        ] {
            let Some(region) = found.name(name) else { continue };
            if region.as_str().is_empty() {
                continue;
            }
            // Rich guards `number` with a `(?<!\w)` lookbehind, which this crate
            // has no equivalent for. Checked after the fact instead.
            if name == "number" && preceded_by_word_character(message, region.start()) {
                continue;
            }
            spans.push((region.start(), region.end(), style));
        }
    }
    spans
}

fn preceded_by_word_character(message: &str, position: usize) -> bool {
    message[..position]
        .chars()
        .next_back()
        .is_some_and(|character| character.is_alphanumeric() || character == '_')
}

static COMBINED_PATTERN: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| {
    // **`\w` here is CPython's, not the crate's, and the two differ in both
    // directions.** Rich writes `ReprHighlighter`'s path pattern with Python's `re`,
    // whose `\w` is `str.isalnum() or "_"`. The crate's follows UTS#18: it adds 2,642
    // scalars CPython rejects — combining marks and `Join_Control` — and misses 915 it
    // accepts, the `Nl` and `No` numerics such as `½` and `Ⅻ`. Either direction moves
    // where a path span ends. Measured over all 1,114,112 scalar values, exact.
    regex::Regex::new(&format!(
        concat!(
            r"(?P<uuid>[a-fA-F0-9]{{8}}-[a-fA-F0-9]{{4}}-[a-fA-F0-9]{{4}}-[a-fA-F0-9]{{4}}-[a-fA-F0-9]{{12}})",
            r"|(?P<number>-?[0-9]+\.?[0-9]*)",
            r"|(?P<path>(?:/[-{word}._+]+)*/)(?P<filename>[-{word}._+]*)?",
            r#"|(?P<str>b?"[^"]*"|b?'[^']*')"#,
        ),
        word = crate::session::PYTHON_WORD_CLASS
    ))
    .expect("a valid combined highlighter pattern")
});

/// Render one stderr message the way the product's consoles do.
///
/// Base style for the console, Rich's repr highlighting layered on top, wrapped at
/// the terminal width. Returns the bytes including the trailing newline.
pub fn render_stderr_message(
    message: &str,
    console: StderrConsole,
    rendering: ColorRendering,
    width: usize,
) -> String {
    let wrapped = crate::terminal::wrap_preserving_spaces(message, width);

    // Styles are resolved on the unwrapped text and walked in lockstep, because
    // wrapping only replaces a space with a newline and never adds or drops
    // characters — so positions stay aligned.
    let spans = highlight_spans(message);
    let base = console.base();
    let mut rendered = String::new();
    for line in wrapped.split('\n') {
        rendered.push_str(&render_styled_run(line, message, &spans, base, rendering));
        rendered.push('\n');
    }
    rendered
}

/// Group one line into runs of equal resolved style and emit them.
fn render_styled_run(
    line: &str,
    message: &str,
    spans: &[(usize, usize, Style)],
    base: Style,
    rendering: ColorRendering,
) -> String {
    let offset = message.find(line).unwrap_or(0);
    let style_at = |position: usize| {
        spans
            .iter()
            .filter(|(start, end, _)| position >= *start && position < *end)
            .fold(base, |resolved, (_, _, style)| resolved.over(*style))
    };

    let mut rendered = String::new();
    let mut run = String::new();
    let mut run_style: Option<Style> = None;
    for (index, character) in line.char_indices() {
        let style = style_at(offset + index);
        if run_style != Some(style) && !run.is_empty() {
            rendered.push_str(&emit_run(&run, run_style.unwrap_or(base), rendering));
            run.clear();
        }
        run_style = Some(style);
        run.push(character);
    }
    if !run.is_empty() {
        rendered.push_str(&emit_run(&run, run_style.unwrap_or(base), rendering));
    }
    rendered
}

fn emit_run(text: &str, style: Style, rendering: ColorRendering) -> String {
    if rendering == ColorRendering::Suppressed {
        return text.to_string();
    }
    let parameters = style.parameters(rendering);
    if parameters.is_empty() {
        return text.to_string();
    }
    format!("\x1b[{parameters}m{text}\x1b[0m")
}

#[cfg(test)]
mod stderr_tests {
    use super::*;
    use crate::terminal::ColorSystem;

    fn rendering_for(tier: &str) -> ColorRendering {
        match tier {
            "truecolor" => ColorRendering::Colored(ColorSystem::Truecolor),
            "eight-bit" => ColorRendering::Colored(ColorSystem::EightBit),
            "standard" => ColorRendering::Colored(ColorSystem::Standard),
            "no-color" => ColorRendering::AttributesOnly,
            _ => ColorRendering::Suppressed,
        }
    }

    /// Every recorded byte the product's stderr consoles emit, across five colour
    /// tiers and three widths.
    #[test]
    fn every_recorded_stderr_message_reproduces() {
        let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/views-and-colour/probes")
            .join("stderr-oracle.json");
        let oracle: serde_json::Value =
            serde_json::from_slice(&std::fs::read(&path).expect("the stderr oracle")).expect("valid JSON");

        let mut compared = 0usize;
        let mut mismatches: Vec<String> = Vec::new();
        for row in oracle["rows"].as_array().expect("rows") {
            let tier = row["tier"].as_str().expect("a tier");
            let message = row["message"].as_str().expect("a message");
            let console = match row["kind"].as_str().expect("a kind") {
                "hint" => StderrConsole::Hint,
                "warning" => StderrConsole::Warning,
                _ => StderrConsole::Error,
            };
            // **A dumb terminal is 80 columns, whatever the pty says.** Rich
            // returns `ConsoleDimensions(80, 25)` before it even consults
            // `COLUMNS` (`console.py:1021`). Resolving that is width resolution's
            // job and `terminal::terminal_width` does not do it — reported. This
            // gate owns rendering, so it is handed the width Rich would have used.
            let width = if tier == "dumb" {
                80
            } else {
                row["columns"].as_u64().expect("a width") as usize
            };
            let expected = String::from_utf8(
                base64_decode(row["bytes"].as_str().expect("recorded bytes")),
            )
            .expect("recorded bytes are utf-8");
            let actual = render_stderr_message(message, console, rendering_for(tier), width);
            compared += 1;
            if actual != expected {
                mismatches.push(format!(
                    "{tier} @ {width}, {message:?}:\n  Python {expected:?}\n  got    {actual:?}"
                ));
            }
        }
        assert!(
            compared > 130,
            "Expected all 135 recorded cases, compared {compared}. Nothing is excluded \
             any more -- a lower count means a filter crept back in."
        );
        assert!(
            mismatches.is_empty(),
            "{} of {compared} stderr messages differ from Python:\n{}",
            mismatches.len(),
            mismatches.iter().take(30).cloned().collect::<Vec<_>>().join("\n")
        );
    }

    fn base64_decode(encoded: &str) -> Vec<u8> {
        const TABLE: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        let mut output = Vec::new();
        let mut accumulator = 0u32;
        let mut bits = 0u32;
        for byte in encoded.bytes().filter(|b| *b != b'=' && !b.is_ascii_whitespace()) {
            let value = TABLE.iter().position(|c| *c == byte).expect("base64 alphabet") as u32;
            accumulator = (accumulator << 6) | value;
            bits += 6;
            if bits >= 8 {
                bits -= 8;
                output.push((accumulator >> bits) as u8);
            }
        }
        output
    }
}

// -------------------------------------------------------- the panel sink

/// Everything the coloured panel sink needs that does not come from a hit.
pub struct ColouredPanelOutput<'a> {
    pub home: &'a str,
    /// What the body is projected against. **The panel sink used to render `hit`'s
    /// raw messages**, which parse-time visibility had already filtered but which
    /// nothing had shortened and whose tool results still carried no resolved name —
    /// so a `Bash` result's header read `Tool` instead of `output`. The plain sink
    /// projects at `search_output.rs`; this one has to project the same way, from the
    /// same function, or there are two answers to what a message shows.
    pub flags: &'a crate::visibility::ConversationFlags,
    pub width: usize,
    pub metrics: CellMetrics,
    pub rendering: ColorRendering,
    pub now: chrono::NaiveDateTime,
    /// `flags.paging`. Colour is implied — this sink only exists on the coloured path.
    pub paging: bool,
    /// `--full` renders every message in the session; the default renders only the
    /// ones that matched.
    pub full: bool,
    /// `--no-metadata` drops the facts line **and** the blank line under it.
    pub emit_metadata: bool,
    /// The compiled literal-term regex, or `None` when no term is a plain literal.
    pub highlight: Option<crate::search_query::Regex>,
}

/// One regex over the query's plain-literal terms, or `None` when it has none.
///
/// Ported from `_build_highlight_regex`. **Only literal terms are highlighted** —
/// a regex term is skipped so a greedy span cannot paint half a message — and
/// longer literals come first so the alternation prefers the most specific match.
///
/// Python sorts a **set**, whose iteration order is arbitrary, so the order among
/// equal-length literals is unspecified there. It is also unobservable: two
/// distinct literals of the same length cannot both match at one position. The tie
/// is broken by the literal here, to keep this deterministic.
///
/// ```
/// use _native::search_query::parse_search_query;
/// use _native::search_views::highlight_regex;
/// let query = parse_search_query("cat OR catalogue", true).expect("a valid query");
/// let regex = highlight_regex(&query).expect("two literal terms");
/// // The longer literal is preferred, so `catalogue` matches whole.
/// assert_eq!(regex.find_all("catalogue").expect("within budget"), vec![(0, 9)]);
/// // A regex term contributes nothing to the highlight.
/// let pattern = parse_search_query("ca.", true).expect("a valid query");
/// assert!(highlight_regex(&pattern).is_none());
/// ```
pub fn highlight_regex(query: &crate::search_query::Query) -> Option<crate::search_query::Regex> {
    let terms = query.iter_terms();
    let mut literals: Vec<&str> = terms
        .iter()
        .filter(|term| term.literal_candidate.is_some() && !term.pattern.is_empty())
        .map(|term| term.pattern.as_str())
        .collect();
    literals.sort_unstable();
    literals.dedup();
    literals.sort_by(|left, right| {
        right
            .chars()
            .count()
            .cmp(&left.chars().count())
            .then_with(|| left.cmp(right))
    });
    if literals.is_empty() {
        return None;
    }
    let ignorecase = !terms.iter().all(|term| term.case_sensitive);
    let pattern = literals
        .iter()
        .map(|literal| crate::search_query::python_regex_escape(literal))
        .collect::<Vec<_>>()
        .join("|");
    crate::search_query::Regex::compile(&pattern, ignorecase).ok()
}

/// The coloured default and `--full` views: one bordered panel per hit.
///
/// The panel's *frame* is `panel_lines` and its *body* is
/// [`session_render::message_body_lines`](crate::session_render::message_body_lines).
/// This joins them and owns the pager, exactly as [`ColouredListSink`] does for
/// rows — including that quitting `less` stops the scan behind it.
///
/// **No trailing summary.** `_display_list_summary` is called from the list branch
/// alone, so the panel path ends with its last panel.
pub struct ColouredPanelSink<'a> {
    output: ColouredPanelOutput<'a>,
    pager: Option<crate::pager::Pager>,
    found: usize,
    closed: bool,
    /// How much narrower the body is than the console: two border columns and two
    /// of padding. A field only so the gate can perturb it; production never
    /// changes it.
    body_width_offset: usize,
}

impl<'a> ColouredPanelSink<'a> {
    pub fn new(output: ColouredPanelOutput<'a>) -> ColouredPanelSink<'a> {
        let pager = output.paging.then(crate::pager::Pager::spawn);
        ColouredPanelSink { output, pager, found: 0, closed: false, body_width_offset: 4 }
    }

    fn write(&mut self, chunk: &str) {
        match &mut self.pager {
            Some(pager) => {
                pager.write(chunk);
                if pager.closed() {
                    self.closed = true;
                }
            }
            None => {
                let mut stdout = std::io::stdout();
                if stdout.write_all(chunk.as_bytes()).is_err() {
                    self.closed = true;
                }
            }
        }
    }

    /// Hand the pager back so the caller can wait for the reader to dismiss it.
    pub fn into_pager(self) -> Option<crate::pager::Pager> {
        self.pager
    }

    pub fn found(&self) -> usize {
        self.found
    }

    /// Perturb the metadata flag, for the gate's own falsification.
    #[cfg(test)]
    pub(crate) fn set_emit_metadata_for_test(&mut self, emit_metadata: bool) {
        self.output.emit_metadata = emit_metadata;
    }

    /// Perturb how much the body's width is reduced from the console's, for the
    /// gate's own falsification. Four in production: two borders and two of padding.
    #[cfg(test)]
    pub(crate) fn set_body_width_offset_for_test(&mut self, offset: usize) {
        self.body_width_offset = offset;
    }

    /// The bytes one hit produces, with no I/O — the seam the gate compares.
    ///
    /// **It cannot fail.** Every construct renders: a fence in a language with no
    /// promoted table, and a fence whose lexer exhausts its step budget, both render
    /// plain with complete geometry. There is no refusal left to hand back, which is
    /// why this returns a `String` rather than a `Result` — the panel sink used to
    /// panic on one and could truncate a scan it had already started printing.
    pub fn render(&self, hit: &SearchHit, ordinal: usize) -> String {
        let session_id = crate::search_output::display_session_id(
            &hit.metadata.path,
            hit.metadata.provider,
            hit.metadata.native_id.as_deref(),
        );
        let (headline, headline_is_fallback) = hit.headline();
        let row = ListRow {
            session_id: &session_id,
            headline,
            headline_is_fallback,
            directory: hit.cwd.as_deref(),
            provider: hit.metadata.provider.as_str(),
            // The panel's facts line always carries the provider; only the list
            // row's is conditional.
            show_provider: true,
            match_count: hit.match_count(),
            age_seconds: hit.age_seconds(self.output.now),
        };

        let title = panel_title(&row, self.output.width);
        let mut body: Vec<Vec<Segment>> = Vec::new();
        if self.output.emit_metadata {
            body.push(panel_facts_line(&row, self.output.home, self.output.width));
            // `Text("")` renders as one empty line.
            body.push(Vec::new());
        }

        // `_display_messages_for_hit`: everything under `--full`, the matches
        // otherwise. The indices preserve each message's progressive position,
        // which is assigned over the whole list.
        let displayed: Vec<usize> = if self.output.full {
            (0..hit.messages.len()).collect()
        } else {
            hit.match_indices.clone()
        };
        // **The id map is built over every message in the hit, not over the displayed
        // ones.** That is `_render_conversation_panel`'s shape, and it is why a `Read`
        // result can resolve its name from a call that is not on screen.
        let tool_id_map = crate::visibility::build_tool_id_map(&hit.messages);
        let messages: Vec<crate::model::Message> = displayed
            .iter()
            .map(|index| {
                crate::visibility::visible_message(
                    &hit.messages[*index],
                    self.output.flags,
                    Some(&tool_id_map),
                    &hit.progressive,
                    *index,
                )
            })
            .collect();
        let tag: String = session_id.chars().take(8).collect();
        let context = crate::session_render::BodyContext {
            metrics: &self.output.metrics,
            highlight: self.output.highlight.as_ref(),
            conversation_tag: Some(&tag),
            home: &self.output.home,
        };
        // The body is laid out at the panel's interior, which is the console width
        // less two border columns and two of padding.
        let interior = self.output.width.saturating_sub(self.body_width_offset);
        body.extend(crate::session_render::message_body_lines(
            &messages, interior, &context,
        ));

        let lines = panel_lines(
            &title,
            &body,
            ordinal,
            self.output.width,
            &self.output.metrics,
            self.output.rendering,
        );
        lines.join("\n") + "\n"
    }
}

impl HitSink for ColouredPanelSink<'_> {
    fn emit(&mut self, hit: &SearchHit) {
        // The border hue cycles per conversation, so the ordinal is the count of
        // panels already drawn.
        let ordinal = self.found;
        let rendered = self.render(hit, ordinal);
        self.write(&rendered);
        self.found += 1;
    }

    fn closed(&self) -> bool {
        self.closed
    }

    fn emit_error(&mut self, message: &str) {
        // The same one authority as the list sink's, for the same reason: two sinks
        // answering the colour question separately is how they drift apart.
        crate::search_run::print_stderr_wrapped(message, StderrConsole::Error);
    }
}

#[cfg(test)]
pub(crate) mod panel_sink_tests {
    use super::*;
    use crate::search_confirm::{SearchHit, SessionMetadata};
    use crate::session::Provider;
    use crate::visibility::{ConversationFlags, ProgressiveAssignment};
    use serde_json::Value;
    use std::path::{Path, PathBuf};

    const SESSION: &str =
        "/tmp/ch-panel-sink/.claude/projects/panelproj/aaaaaaaa-1111-4111-8111-aaaaaaaaaa01.jsonl";
    const HOME: &str = "/tmp/ch-panel-sink";

    pub(crate) fn oracle() -> Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/data/message-renderer/panel-sink-oracle.json");
        let bytes = std::fs::read(&path).unwrap_or_else(|error| {
            panic!("the panel sink oracle is missing at {}: {error}", path.display())
        });
        serde_json::from_slice(&bytes).expect("the panel sink oracle is valid JSON")
    }

    pub(crate) fn hit_from(record: &Value, now: chrono::NaiveDateTime) -> SearchHit {
        let content = record["jsonl"].as_str().expect("a recorded session");
        let flags = ConversationFlags::default();
        let scanned = crate::search_confirm::scan_session(
            Path::new(SESSION),
            content,
            &flags,
            Path::new(HOME),
        )
        .expect("the recorded session decodes");
        let match_indices: Vec<usize> = record["match_indices"]
            .as_array()
            .expect("recorded match indices")
            .iter()
            .map(|index| index.as_u64().expect("an index") as usize)
            .collect();
        let progressive = ProgressiveAssignment::compute(&scanned.messages, &flags, None);
        SearchHit {
            metadata: SessionMetadata {
                path: PathBuf::from(SESSION),
                provider: Provider::Claude,
                ctime: None,
                mtime: Some(now),
                native_id: None,
                forked_from: None,
            },
            messages: scanned.messages,
            match_indices,
            progressive,
            cwd: Some("/tmp/panelproj".to_string()),
            matching_summaries: Vec::new(),
            matching_custom_titles: Vec::new(),
            last_custom_title: Some("a recorded panel".to_string()),
        }
    }

    /// **The recorder used default flags for every case**, so this corpus cannot see
    /// the projection at all: nothing is shortened, no tool is filtered, and no
    /// result name is resolved from a call. It is a stated limit of this gate rather
    /// than an assertion that flags do not reach the panel — the body oracle carries
    /// the flagged cases.
    static RECORDED_FLAGS: std::sync::LazyLock<crate::visibility::ConversationFlags> =
        std::sync::LazyLock::new(crate::visibility::ConversationFlags::default);

    pub(crate) fn sink_for(record: &Value, now: chrono::NaiveDateTime) -> ColouredPanelSink<'static> {
        let highlight = record["highlight"].as_str().map(|pattern| {
            crate::search_query::Regex::compile(pattern, false)
                .expect("the recorded highlight pattern compiles")
        });
        ColouredPanelSink::new(ColouredPanelOutput {
            // The recorder's `HOME`, not `/tmp` — `collapse_home` matches a string
            // prefix rather than a path boundary, so a home of `/tmp` would turn the
            // recorded `/tmp/panelproj` into `~/panelproj`. The behaviour is wrong
            // and preserved; the test has to supply the same home the recording did.
            home: HOME,
            flags: &RECORDED_FLAGS,
            width: record["width"].as_u64().expect("a width") as usize,
            metrics: CellMetrics::from_environment(),
            rendering: ColorRendering::Colored(crate::terminal::ColorSystem::Truecolor),
            now,
            // No pager: the gate compares bytes, and spawning `less` from a test
            // would block on a reader that never arrives.
            paging: false,
            full: record["full"].as_bool().expect("a full flag"),
            emit_metadata: record["emit_metadata"].as_bool().expect("a metadata flag"),
            highlight,
        })
    }

    #[test]
    fn every_recorded_panel_reproduces() {
        let oracle = oracle();
        let now = chrono::NaiveDateTime::parse_from_str(
            oracle["now"].as_str().expect("a recorded clock"),
            "%Y-%m-%dT%H:%M:%S",
        )
        .expect("the recorded clock parses");

        let mut compared = 0usize;
        let mut failures: Vec<String> = Vec::new();
        for record in oracle["cases"].as_array().expect("recorded panels") {
            let hit = hit_from(record, now);
            let sink = sink_for(record, now);
            let ordinal = record["ordinal"].as_u64().expect("an ordinal") as usize;
            let rendered = sink.render(&hit, ordinal);
            compared += 1;

            let expected: Vec<String> = record["lines"]
                .as_array()
                .expect("recorded lines")
                .iter()
                .map(|line| line.as_str().expect("a line").to_string())
                .collect();
            let actual: Vec<String> =
                rendered.trim_end_matches('\n').split('\n').map(str::to_string).collect();
            if actual == expected {
                continue;
            }
            let identifier = record["id"].as_str().unwrap_or("?");
            let width = record["width"].as_u64().unwrap_or(0);
            let mut report = format!(
                "{identifier} @ {width} metadata={} full={} highlight={}\n",
                record["emit_metadata"], record["full"], record["highlight"]
            );
            for index in 0..expected.len().max(actual.len()) {
                let want = expected.get(index).cloned().unwrap_or_default();
                let got = actual.get(index).cloned().unwrap_or_default();
                let marker = if want == got { "  " } else { "->" };
                report.push_str(&format!(
                    "  {marker} rich {}\n     ours {}\n",
                    want.replace('\u{1b}', "\\e"),
                    got.replace('\u{1b}', "\\e")
                ));
            }
            failures.push(report);
        }

        assert!(
            compared >= 160,
            "Only {compared} panels were compared. A shrunken corpus passes vacuously."
        );
        assert!(
            failures.is_empty(),
            "{} of {compared} recorded panels differ from Rich:\n\n{}",
            failures.len(),
            failures[..failures.len().min(2)].join("\n")
        );
    }
}

#[cfg(test)]
mod panel_sink_falsification_tests {
    use super::panel_sink_tests::{hit_from, oracle, sink_for};

    /// The gate must fail against the three errors a panel sink can plausibly make.
    /// A gate never observed to fail is not evidence, and a sink never observed to
    /// render is not evidence either — this is the second half of that.
    #[test]
    fn the_panel_gate_catches_plausible_wrong_sinks() {
        let oracle = oracle();
        let now = chrono::NaiveDateTime::parse_from_str(
            oracle["now"].as_str().expect("a recorded clock"),
            "%Y-%m-%dT%H:%M:%S",
        )
        .expect("the recorded clock parses");
        let records = oracle["cases"].as_array().expect("recorded panels");

        let mut ordinal_ignored = 0usize;
        let mut metadata_ignored = 0usize;
        let mut body_at_full_width = 0usize;

        for record in records {
            let hit = hit_from(record, now);
            let sink = sink_for(record, now);
            let ordinal = record["ordinal"].as_u64().expect("an ordinal") as usize;
            let faithful = sink.render(&hit, ordinal);

            // 1. The border hue cycles per conversation. A sink that draws every
            //    panel with the first hue loses the orientation cue that survives
            //    scrolling, and looks correct in any single-hit fixture.
            if sink.render(&hit, 0) != faithful {
                ordinal_ignored += 1;
            }

            // 2. `--no-metadata` drops the facts line *and* the blank under it. A
            //    sink that always emits them passes every default-flag fixture.
            let mut always_metadata = sink_for(record, now);
            always_metadata.set_emit_metadata_for_test(true);
            if always_metadata.render(&hit, ordinal) != faithful {
                metadata_ignored += 1;
            }

            // 3. The body is laid out at the panel's *interior* — the console width
            //    less two borders and two of padding. Laying it out at the console
            //    width is the natural off-by-four, and it only shows once a line is
            //    long enough to wrap differently.
            let mut full_width = sink_for(record, now);
            full_width.set_body_width_offset_for_test(0);
            if full_width.render(&hit, ordinal) != faithful {
                body_at_full_width += 1;
            }
        }

        assert!(
            ordinal_ignored >= 30,
            "Only {ordinal_ignored} recorded panels notice a sink that never cycles \
             the border hue. The corpus has stopped spanning the cycle."
        );
        assert!(
            metadata_ignored >= 30,
            "Only {metadata_ignored} recorded panels notice a sink that ignores \
             `--no-metadata`. The corpus has stopped covering both settings."
        );
        assert!(
            body_at_full_width >= 10,
            "Only {body_at_full_width} recorded panels notice a body laid out at the \
             console width rather than the interior. The corpus has stopped carrying \
             a line long enough to wrap differently."
        );
    }
}
