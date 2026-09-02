//! Confirmation: read one candidate session and decide it for real.
//!
//! Ported from `_confirm_search_hit` and `_search_conversation_content` in
//! `src/chats/commands/search.py`.
//!
//! **Search truth is three sources, not one.** A term matches a session if it
//! matches any summary, **or** the current custom title, **or** any rendered
//! message. Evaluation is session-wide, so the operands of an `AND` may match in
//! different messages. Nothing else in a session is searchable; a fourth source
//! would be a contract change.
//!
//! **The order before rendering is load-bearing.** Decode, then the tool-id map,
//! then progressive shortening across the *whole* message list, then render each
//! message. Progressive positions depend on which messages qualify, which depends
//! on the flags, so they cannot be computed per message — and they cannot be
//! recomputed over a subset, which is why a hit carries indices rather than a
//! second list of messages.
//!
//! **The renders are deliberately not kept.** Python builds them, matches against
//! them, and drops them when `_search_conversation_content` returns, re-rendering
//! later for display. Holding them would change the memory profile on exactly the
//! large-payload arm the memory gate measures.

use crate::model::Message;
use crate::pool_filter::{self, PoolFilter};
use crate::search_query::{Query, SearchTerm};
use crate::session::{self, SessionFormat};
use crate::visibility::{self, ConversationFlags, ProgressiveAssignment};
use chrono::NaiveDateTime;
use std::path::{Path, PathBuf};

/// Bridge between the two `Provider` enums this crate carries.
///
/// `inventory::Provider` and `session::Provider` name the same three providers in
/// different declaration orders, and the inventory order is **load-bearing**: the
/// provider partition in `session_pool` was proved identical to Python across
/// 5,036 sessions, so that order is pinned to the oracle. Unifying the two would
/// silently adopt one order for both uses and may adopt the wrong one, so the
/// ruling is an explicit conversion here rather than a merge.
impl From<crate::inventory::Provider> for ProviderBridge {
    fn from(provider: crate::inventory::Provider) -> Self {
        ProviderBridge(match provider {
            crate::inventory::Provider::Claude => session::Provider::Claude,
            crate::inventory::Provider::Pi => session::Provider::Pi,
            crate::inventory::Provider::Codex => session::Provider::Codex,
        })
    }
}

/// Newtype so the conversion above can exist without either owner's enum gaining
/// a trait impl that points at the other.
pub struct ProviderBridge(pub session::Provider);

/// Session facts the views read, and nothing else.
///
/// Ported from `ConversationMetadata`, narrowed to what search displays.
#[derive(Clone, Debug)]
pub struct SessionMetadata {
    pub path: PathBuf,
    pub provider: session::Provider,
    /// First in-band timestamp, falling back to filesystem birth time.
    pub ctime: Option<NaiveDateTime>,
    /// Last in-band timestamp, falling back to filesystem mtime.
    pub mtime: Option<NaiveDateTime>,
    /// The provider's own session id, when the file carries one. Claude has none —
    /// its display id is the filename stem.
    pub native_id: Option<String>,
    /// Codex's fork parent. Every other adapter's extractor is `lambda _: None`,
    /// so this is `None` for Claude and Pi by construction rather than by omission.
    pub forked_from: Option<String>,
}

/// One matched conversation, ready for ordered display.
#[derive(Clone, Debug)]
pub struct SearchHit {
    pub metadata: SessionMetadata,
    pub messages: Vec<Message>,
    /// Indices into `messages`, in order. Python holds references to the same
    /// objects; indices are the Rust equivalent, and they preserve each message's
    /// progressive position, which is assigned over the whole list.
    pub match_indices: Vec<usize>,
    pub progressive: ProgressiveAssignment,
    pub cwd: Option<String>,
    pub matching_summaries: Vec<String>,
    pub matching_custom_titles: Vec<String>,
    pub last_custom_title: Option<String>,
}

impl SearchHit {
    /// Matched messages plus matched summaries plus matched custom titles.
    ///
    /// A method rather than a field: Python computes it as a property from the
    /// three lists, and a stored field could drift from them.
    pub fn match_count(&self) -> usize {
        self.match_indices.len() + self.matching_summaries.len() + self.matching_custom_titles.len()
    }

    /// The display headline, and whether it is a fallback rather than a real title.
    ///
    /// Four steps, in Python's order. **The first is falsy-sensitive**: an empty
    /// custom title is falsy in Python and must fall through to the fallback, in
    /// the italic fallback style. A `is_some()` check here would paint an empty
    /// headline in the real-title style and pass every view gate, because the view
    /// oracle is fed the pair rather than deriving it.
    ///
    /// ```
    /// # use _native::search_confirm::SearchHit;
    /// # let hit = SearchHit::empty_for_doctest();
    /// assert_eq!(hit.headline(), ("(untitled session)", true));
    /// ```
    pub fn headline(&self) -> (&str, bool) {
        if let Some(title) = self.last_custom_title.as_deref().filter(|t| !t.is_empty()) {
            return (title, false);
        }
        if let Some(summary) = self.matching_summaries.first() {
            return (summary, true);
        }
        for index in &self.match_indices {
            if let Some(line) = first_python_line(session::python_strip(&self.messages[*index].text)) {
                return (line, true);
            }
        }
        ("(untitled session)", true)
    }

    /// Seconds between the session's modification time and `now`.
    ///
    /// The views take this rather than the timestamp, so the clock stays on this
    /// side of the seam and `CH_NOW` remains the single pin for every age-bearing
    /// differential.
    pub fn age_seconds(&self, now: NaiveDateTime) -> Option<f64> {
        let mtime = self.mtime_or_none()?;
        Some((now - mtime).as_seconds_f64())
    }

    fn mtime_or_none(&self) -> Option<NaiveDateTime> {
        self.metadata.mtime
    }

    #[doc(hidden)]
    pub fn empty_for_doctest() -> SearchHit {
        SearchHit {
            metadata: SessionMetadata {
                path: PathBuf::from("x.jsonl"),
                provider: session::Provider::Claude,
                ctime: None,
                mtime: None,
                native_id: None,
                forked_from: None,
            },
            messages: Vec::new(),
            match_indices: Vec::new(),
            progressive: ProgressiveAssignment::default(),
            cwd: None,
            matching_summaries: Vec::new(),
            matching_custom_titles: Vec::new(),
            last_custom_title: None,
        }
    }
}

/// The first line of `text` under Python's `str.splitlines()` boundaries.
///
/// Not `split('\n')`. Python breaks lines on `\v`, `\f`, `\x1c`, `\x1d`, `\x1e`,
/// `\x85`, `\u{2028}` and `\u{2029}` as well, so a headline taken up to the first
/// `\n` would carry a control character into a terminal on any transcript that
/// contains one. Returns `None` for text that is empty after stripping, which is
/// how Python's `if first_line:` falls through to the next candidate.
///
/// ```
/// use _native::search_confirm::first_python_line;
/// assert_eq!(first_python_line("one\ntwo"), Some("one"));
/// assert_eq!(first_python_line("one\u{0b}two"), Some("one"));
/// assert_eq!(first_python_line("one\u{2028}two"), Some("one"));
/// assert_eq!(first_python_line(""), None);
/// ```
pub fn first_python_line(text: &str) -> Option<&str> {
    if text.is_empty() {
        return None;
    }
    let end = text
        .find(PYTHON_LINE_BOUNDARIES)
        .unwrap_or(text.len());
    Some(&text[..end])
}

const PYTHON_LINE_BOUNDARIES: &[char] = &[
    '\n', '\r', '\u{0b}', '\u{0c}', '\u{1c}', '\u{1d}', '\u{1e}', '\u{85}', '\u{2028}', '\u{2029}',
];

/// Why one candidate produced no hit.
pub enum ConfirmError {
    /// Printed to stderr, and scanning continues. The text is Python's message
    /// body, ready to interpolate into
    /// `Error processing conversation file {path}: {body}`.
    File(String),
    /// The pattern was too expensive to decide. This ends the run with a non-zero
    /// exit rather than continuing.
    ///
    /// Python has no step budget — it hangs instead — so there is no oracle for
    /// what happens next. This is the documented deliberate divergence, and
    /// stopping at once is the only answer that never reports a confidently wrong
    /// result. Answering "no match" is precisely what the guard exists to prevent.
    Undecidable(String),
}

/// The invariant half of confirmation: everything that does not change per file.
///
/// **It takes a directory, not a `PoolFilter`, and that is deliberate.**
/// Confirmation applies exactly one filter — the cwd check — and never reads a
/// date. But `PoolFilter::new` parses both dates eagerly and returns `Err` on a
/// bad one, so a caller who passed the date strings through here would make
/// `-ma notadate` fail **once, before the scan**, where the product fails **once
/// per candidate file** and then prints the ordinary no-results hint.
///
/// That divergence would be invisible to every gate on this mission: the eager
/// and lazy date filters agree on every *valid* value, and the only case that
/// separates them is the one a fast failure deletes from the scan entirely. No
/// byte comparator can diff an error that never happens.
///
/// Accepting only the directory removes the class. The dates belong to
/// `search::plan::lazy_screen`, which parses them per path and reports
/// `Gated::Failed` with Python's whole line.
pub struct Confirmation<'a> {
    query: &'a Query,
    flags: &'a ConversationFlags,
    /// Built here from the directory alone. Never handed in.
    filter: PoolFilter,
    home: &'a Path,
}

impl<'a> Confirmation<'a> {
    /// `directory` is `--dir`, or `None`. Date filters are not accepted, by design.
    pub fn new(
        query: &'a Query,
        flags: &'a ConversationFlags,
        directory: Option<String>,
        home: &'a Path,
    ) -> Confirmation<'a> {
        Confirmation {
            query,
            flags,
            // Cannot fail: the only fallible part of `PoolFilter::new` is parsing
            // the two date strings, and neither is supplied.
            filter: PoolFilter::new(None, directory, None, None)
                .expect("a filter with no date strings cannot fail to parse"),
            home,
        }
    }
}

impl Confirmation<'_> {
    /// Read one candidate and decide it.
    pub fn hit(&self, path: &Path) -> Result<Option<SearchHit>, ConfirmError> {
        let content = crate::python_io::read_text(path).map_err(ConfirmError::File)?;
        self.hit_from_content(path, &content)
    }

    /// Decide one candidate from content already read.
    ///
    /// Split here because Python splits here: `_search_conversation_content` takes
    /// content, which keeps every decision below testable without a filesystem.
    pub fn hit_from_content(
        &self,
        path: &Path,
        content: &str,
    ) -> Result<Option<SearchHit>, ConfirmError> {
        let scan = self.scan(path, content)?;

        if !self.filter.passes_cwd(scan.cwd.as_deref()) {
            return Ok(None);
        }

        let (rendered, progressive) =
            rendered_for_search(&scan.messages, self.flags).map_err(ConfirmError::File)?;

        let mut search = TermSearch::default();
        let matched = self
            .query
            .evaluate(&mut |term| search.matches_session(term, &scan, &rendered));
        // Checked before the result is trusted. An undecidable term answers
        // `false` transiently, which is only safe because the answer is discarded.
        search.into_result()?;
        if !matched {
            return Ok(None);
        }

        let terms = self.query.iter_terms();
        let mut search = TermSearch::default();
        let matching_summaries: Vec<String> = scan
            .summaries
            .iter()
            .filter(|summary| terms.iter().any(|term| search.matches(term, summary)))
            .cloned()
            .collect();
        let matching_custom_titles: Vec<String> = scan
            .custom_title
            .iter()
            .filter(|title| terms.iter().any(|term| search.matches(term, title)))
            .cloned()
            .collect();
        let match_indices: Vec<usize> = rendered
            .iter()
            .enumerate()
            .filter(|(_, text)| terms.iter().any(|term| search.matches(term, text)))
            .map(|(index, _)| index)
            .collect();
        search.into_result()?;

        // A session can satisfy the query through a `NOT` while matching nothing
        // positively. Python drops those, so a hit always has something to show.
        if match_indices.is_empty()
            && matching_summaries.is_empty()
            && matching_custom_titles.is_empty()
        {
            return Ok(None);
        }

        Ok(Some(SearchHit {
            metadata: SessionMetadata {
                path: path.to_path_buf(),
                provider: scan.provider,
                ctime: pool_filter::first_timestamp(path),
                mtime: pool_filter::last_timestamp(path),
                native_id: scan.native_id,
                forked_from: scan.forked_from,
            },
            messages: scan.messages,
            match_indices,
            progressive,
            cwd: scan.cwd,
            matching_summaries,
            matching_custom_titles,
            last_custom_title: scan.custom_title,
        }))
    }

    fn scan(&self, path: &Path, content: &str) -> Result<Scanned, ConfirmError> {
        scan_session(path, content, self.flags, self.home).map_err(ConfirmError::File)
    }
}

/// One pass over the content: provider, facets and messages.
///
/// Ported from `SessionScan.from_content`.
pub fn scan_session(
    path: &Path,
    content: &str,
    flags: &ConversationFlags,
    home: &Path,
) -> Result<Scanned, String> {
    if session::detect_format(content) == SessionFormat::Raw {
        // Raw carries no facets at all — not merely none found. This is why eight
        // large Codex rollouts are absent from `search .`: their first line is an
        // object with no `type` key, so they never reach a decoder.
        return Ok(Scanned {
            provider: session::Provider::Claude,
            native_id: None,
            forked_from: None,
            cwd: None,
            summaries: Vec::new(),
            custom_title: None,
            messages: crate::raw_transcript::parse_raw_cli_transcript(content, flags),
        });
    }

    let entries = session::decode_entries(content);
    let path_provider = crate::inventory::classify_native_session_path_impl(path, home)
        .map(|provider| ProviderBridge::from(provider).0);
    // Python raises here rather than defaulting to Claude: the Claude adapter has
    // no first-entry matcher, so only path classification can select it. Mapping
    // this to Claude would decode files Python refuses, surfacing sessions the
    // product excludes.
    let provider = session::select_provider(path_provider, entries.first())?;

    let messages = match provider {
        session::Provider::Claude => session::parse_claude(&entries, flags),
        session::Provider::Pi => session::parse_pi(&entries, flags),
        session::Provider::Codex => crate::codex::parse_codex(&entries, flags),
    };

    Ok(Scanned {
        provider,
        native_id: native_session_id(provider, entries.first(), path),
        forked_from: codex_meta_field(provider, entries.first(), "forked_from_id"),
        cwd: session::cwd(&entries),
        summaries: session::summaries(&entries),
        custom_title: session::latest_custom_title(&entries),
        messages,
    })
}

/// The provider's own session id, read from the first entry.
///
/// Python's extractors open the file and stop at the **first decodable entry**, so
/// nothing later in the file can supply one. Taking it from the entries already
/// decoded costs no extra read and removes a second chance to disagree.
///
/// Pi falls back to the filename stem's suffix after the last `_`, which is
/// Python's `rpartition` and yields `None` when either half is empty.
pub(crate) fn native_session_id(
    provider: session::Provider,
    first: Option<&serde_json::Map<String, serde_json::Value>>,
    path: &Path,
) -> Option<String> {
    match provider {
        session::Provider::Claude => None,
        session::Provider::Codex => codex_meta_field(provider, first, "id"),
        session::Provider::Pi => {
            let from_entry = first
                .filter(|entry| entry.get("type").and_then(serde_json::Value::as_str) == Some("session"))
                .and_then(|entry| entry.get("id"))
                .and_then(serde_json::Value::as_str)
                .filter(|value| !value.is_empty())
                .map(str::to_string);
            from_entry.or_else(|| {
                let stem = path.file_stem()?.to_string_lossy().into_owned();
                let (prefix, suffix) = stem.rsplit_once('_')?;
                (!prefix.is_empty() && !suffix.is_empty()).then(|| suffix.to_string())
            })
        }
    }
}

/// A string field of Codex's `session_meta` payload, from the first entry only.
fn codex_meta_field(
    provider: session::Provider,
    first: Option<&serde_json::Map<String, serde_json::Value>>,
    field: &str,
) -> Option<String> {
    if provider != session::Provider::Codex {
        return None;
    }
    first
        .filter(|entry| {
            entry.get("type").and_then(serde_json::Value::as_str) == Some("session_meta")
        })?
        .get("payload")?
        .as_object()?
        .get(field)?
        .as_str()
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

/// The exact strings search matches a session against.
///
/// Decode order is load-bearing and lives here, once: the tool-id map, then
/// progressive shortening over the **whole** message list, then the visible
/// projection and render per message. `encode_transport` is `false`, because
/// transport escaping belongs to `ch parse` and would escape the delimiters a
/// user's pattern is trying to match.
///
/// Public so the render differential grades this function rather than its own
/// copy of these four steps.
pub fn rendered_for_search(
    messages: &[Message],
    flags: &ConversationFlags,
) -> Result<(Vec<String>, ProgressiveAssignment), String> {
    let tool_id_map = visibility::build_tool_id_map(messages);
    let progressive = ProgressiveAssignment::compute(messages, flags, Some(&tool_id_map));
    let rendered = messages
        .iter()
        .enumerate()
        .map(|(index, message)| {
            let visible =
                visibility::visible_message(message, flags, Some(&tool_id_map), &progressive, index);
            crate::codecs::render_message_inner_xml(&visible, false).map(|(text, _)| text)
        })
        .collect::<Result<Vec<String>, String>>()?;
    Ok((rendered, progressive))
}

/// One session's decoded facets and messages.
///
/// Public because the render differential grades **this** pipeline rather than a
/// re-assembly of the same steps. A gate that reimplements what it grades is
/// grading itself: it would agree with a confirmation that had the steps in the
/// wrong order, because it would have them in the wrong order too.
pub struct Scanned {
    pub provider: session::Provider,
    /// From the first entry, which is the only place Python looks for either.
    pub native_id: Option<String>,
    pub forked_from: Option<String>,
    pub cwd: Option<String>,
    pub summaries: Vec<String>,
    pub custom_title: Option<String>,
    pub messages: Vec<Message>,
}

/// Runs terms against text, remembering an undecidable pattern rather than
/// answering `false` for it.
///
/// `Query::evaluate` returns a bare `bool`, so a `StepBudgetExceeded` cannot
/// propagate out of the closure. It is recorded here and checked by the caller
/// **before** the evaluation's answer is used.
#[derive(Default)]
struct TermSearch {
    undecidable: Option<String>,
}

impl TermSearch {
    fn matches(&mut self, term: &SearchTerm, text: &str) -> bool {
        match term.engine.search(text) {
            Ok(found) => found,
            Err(exceeded) => {
                self.undecidable.get_or_insert_with(|| exceeded.to_string());
                false
            }
        }
    }

    fn matches_session(&mut self, term: &SearchTerm, scan: &Scanned, rendered: &[String]) -> bool {
        scan.summaries.iter().any(|summary| self.matches(term, summary))
            || scan
                .custom_title
                .as_deref()
                .is_some_and(|title| self.matches(term, title))
            || rendered.iter().any(|text| self.matches(term, text))
    }

    fn into_result(self) -> Result<(), ConfirmError> {
        match self.undecidable {
            Some(message) => Err(ConfirmError::Undecidable(message)),
            None => Ok(()),
        }
    }
}
