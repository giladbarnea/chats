//! Session decoding: format detection, entry decoding, provider selection, and the
//! per-file facets search matches against.
//!
//! Ported from `src/chats/parsing.py` and `src/chats/session_scan.py` at oracle
//! revision `8cb4c5f`.
//!
//! **Three different first-line policies live here, and they disagree by design.**
//! `detect_format` reads the first non-blank line with the *stdlib* JSON parser and
//! requires an object carrying a `type` key. `first_entry` reads it with *orjson* and
//! aborts on anything malformed. `decode_entries` reads every line with orjson and
//! *skips* what it cannot parse. The parsers differ too: a line containing `NaN` is
//! accepted by the first and rejected by the other two, so a file can be classified
//! JSONL and then silently lose that entry. Reproduced, not unified.

use std::sync::OnceLock;

use regex::Regex;
use serde_json::{Map, Value};

use crate::codecs::normalize_python_json_constants;
use crate::model::number_is_integer;

/// Which provider's shape a session file has.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Provider {
    Claude,
    Pi,
    Codex,
}

impl Provider {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Claude => "claude",
            Self::Pi => "pi",
            Self::Codex => "codex",
        }
    }

    pub fn from_str(value: &str) -> Option<Self> {
        match value {
            "claude" => Some(Self::Claude),
            "pi" => Some(Self::Pi),
            "codex" => Some(Self::Codex),
            _ => None,
        }
    }
}

/// Whether content is provider JSONL or a raw CLI transcript.
///
/// The first non-blank line decides, and it must parse as an object carrying a
/// `type` key. Uses the lenient parse, matching Python's stdlib `json` here — which
/// accepts `NaN` and `Infinity` where the decoders below do not.
///
/// ```
/// use _native::session::{detect_format, SessionFormat};
/// assert_eq!(detect_format("{\"type\": \"user\"}"), SessionFormat::Jsonl);
/// assert_eq!(detect_format("> a raw transcript"), SessionFormat::Raw);
/// assert_eq!(detect_format("{\"no\": \"type key\"}"), SessionFormat::Raw);
/// ```
pub fn detect_format(content: &str) -> SessionFormat {
    for line in content.split('\n') {
        let line = python_strip(line);
        if line.is_empty() {
            continue;
        }
        if let Ok(Value::Object(entry)) = serde_json::from_str::<Value>(&detection_lenient(line))
            && entry.contains_key("type")
        {
            return SessionFormat::Jsonl;
        }
        // The first non-blank line decides either way.
        break;
    }
    SessionFormat::Raw
}

/// Make a line parseable for *detection only*, matching what stdlib `json` accepts.
///
/// `detect_format` asks one question — is this an object with a `type` key — so the
/// values need only survive parsing, not round-trip. `NaN` becomes `null` on that
/// basis. This deliberately does not extend the codec's
/// `normalize_python_json_constants`, which serves a different contract: its output
/// is re-encoded, so it must map constants to values that survive the trip, and
/// `null` would not.
pub(crate) fn detection_lenient(line: &str) -> String {
    let with_infinities = normalize_python_json_constants(line);
    let mut normalized = String::with_capacity(with_infinities.len());
    let mut in_string = false;
    let mut escaped = false;
    let mut rest = with_infinities.as_str();
    while !rest.is_empty() {
        if !in_string && rest.starts_with("NaN") {
            normalized.push_str("null");
            rest = &rest["NaN".len()..];
            continue;
        }
        let character = rest.chars().next().expect("nonempty remainder");
        normalized.push(character);
        rest = &rest[character.len_utf8()..];
        if !in_string {
            if character == '"' {
                in_string = true;
            }
            continue;
        }
        if escaped {
            escaped = false;
        } else if character == '\\' {
            escaped = true;
        } else if character == '"' {
            in_string = false;
        }
    }
    normalized
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SessionFormat {
    Jsonl,
    Raw,
}

/// Strip the characters Python's `str.strip()` strips.
///
/// Not Rust's `trim`: Python strips every character where `str.isspace()` is true,
/// which includes U+001C..U+001F. Rust's `char::is_whitespace` is the Unicode
/// `White_Space` property, which does not. A line prefixed with U+001C is decoded by
/// Python and would be dropped by `trim`, taking the whole file from JSONL to raw.
pub fn python_strip(value: &str) -> &str {
    value.trim_matches(python_is_space)
}

/// Python's `str.lstrip()`: the same character set, leading side only.
///
/// Kept separate rather than folded into `python_strip` because two call sites
/// use the *length* of what was removed as a byte cursor, where stripping the
/// trailing side too would move the cursor past content.
pub fn python_strip_start(value: &str) -> &str {
    value.trim_start_matches(python_is_space)
}

fn python_is_space(character: char) -> bool {
    character.is_whitespace() || matches!(character, '\u{1c}'..='\u{1f}')
}

/// The body of a character class matching exactly what CPython's `\s` matches.
///
/// The Rust `regex` crate's `\s` is `\p{White_Space}`; CPython's is the
/// `str.isspace()` set, which adds U+001C..U+001F. **Measured, not read off two
/// documents:** every one of the 1,114,112 scalar values was classified by both
/// engines and this class reproduces CPython exactly, in both directions
/// (`probes/character_class_parity.py`).
pub const PYTHON_SPACE_CLASS: &str = r"\s\x{1C}-\x{1F}";

/// The body of a character class matching exactly what CPython's `\w` matches.
///
/// **This one differs in both directions**, so neither engine's class contains
/// the other. Rust's `\w` follows UTS#18 and adds combining marks and
/// `Join_Control` — 2,642 scalars CPython rejects. CPython's is
/// `str.isalnum() or "_"`, which adds `Nl` and `No` numerics such as `½` and
/// `Ⅻ` — 915 scalars Rust rejects. Measured the same way, and exact.
pub const PYTHON_WORD_CLASS: &str = r"\p{L}\p{Nd}\p{Nl}\p{No}_";

/// Decode JSONL content into object entries, skipping every line that is not one.
///
/// Blank lines are skipped, malformed lines are skipped, and non-object values are
/// skipped. This is the *skipping* policy; `first_entry` below is the aborting one.
pub fn decode_entries(content: &str) -> Vec<Map<String, Value>> {
    content
        .split('\n')
        .filter_map(|line| {
            let line = python_strip(line);
            if line.is_empty() {
                return None;
            }
            match serde_json::from_str::<Value>(line) {
                Ok(Value::Object(entry)) => Some(entry),
                _ => None,
            }
        })
        .collect()
}

/// The first object entry, or nothing.
///
/// Blank lines are skipped, then the first non-blank line **decides**: malformed
/// JSON or a valid non-object both yield nothing rather than scanning onward.
pub fn first_entry(content: &str) -> Option<Map<String, Value>> {
    for line in content.split('\n') {
        let line = python_strip(line);
        if line.is_empty() {
            continue;
        }
        return match serde_json::from_str::<Value>(line) {
            Ok(Value::Object(entry)) => Some(entry),
            _ => None,
        };
    }
    None
}

fn entry_type(entry: &Map<String, Value>) -> Option<&str> {
    entry.get("type").and_then(Value::as_str)
}

/// Whether a first entry carries Codex's native session header.
pub fn is_codex_session_header(entry: &Map<String, Value>) -> bool {
    entry_type(entry) == Some("session_meta")
}

/// Whether a first entry carries Pi's native session header.
///
/// Python requires `type(version) is int`, so a float or a string version does not
/// match. `true` does not either, since a bool is not an int under `type(...) is`.
pub fn is_pi_session_header(entry: &Map<String, Value>) -> bool {
    if entry_type(entry) != Some("session") {
        return false;
    }
    matches!(entry.get("version"), Some(Value::Number(number)) if number_is_integer(number))
}

/// Choose the provider for a session, by path classification first and content second.
///
/// `path_provider` is the caller's classification of the file's location — resolved
/// outside this module so there is one authority for it. When it yields nothing, the
/// first entry's signature decides; Codex is tried before Pi, matching the order of
/// Python's adapter list.
pub fn select_provider(
    path_provider: Option<Provider>,
    first: Option<&Map<String, Value>>,
) -> Result<Provider, String> {
    if let Some(provider) = path_provider {
        return Ok(provider);
    }
    if let Some(entry) = first {
        if is_codex_session_header(entry) {
            return Ok(Provider::Codex);
        }
        if is_pi_session_header(entry) {
            return Ok(Provider::Pi);
        }
    }
    Err("Cannot determine JSONL session provider from its path or first entry.".to_string())
}

// -------------------------------------------------------------------- facets

/// Every `summary` value, in file order.
pub fn summaries(entries: &[Map<String, Value>]) -> Vec<String> {
    entries
        .iter()
        .filter(|entry| entry_type(entry) == Some("summary"))
        .filter_map(|entry| entry.get("summary").and_then(Value::as_str))
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .collect()
}

/// The shared custom-title abstraction, from one provider-native entry.
///
/// Three spellings across three providers: Claude's `custom-title`, Pi's
/// `session_info`, and Codex's `event_msg` carrying a `thread_name_updated` payload.
pub fn custom_title_from_entry(entry: &Map<String, Value>) -> Option<String> {
    let raw = match entry_type(entry) {
        Some("custom-title") => entry.get("customTitle"),
        Some("session_info") => entry.get("name"),
        Some("event_msg") => {
            let payload = entry.get("payload")?.as_object()?;
            if payload.get("type").and_then(Value::as_str) != Some("thread_name_updated") {
                return None;
            }
            payload.get("thread_name")
        }
        _ => None,
    }?;
    let title = python_strip(raw.as_str()?);
    (!title.is_empty()).then(|| title.to_string())
}

/// The last custom title in the file, which is the session's current name.
pub fn latest_custom_title(entries: &[Map<String, Value>]) -> Option<String> {
    entries.iter().filter_map(custom_title_from_entry).last()
}

/// Collect Codex message text blocks.
pub fn codex_text_blocks(content: &Value) -> Vec<String> {
    let Some(items) = content.as_array() else {
        return Vec::new();
    };
    items
        .iter()
        .filter_map(Value::as_object)
        .filter(|item| {
            matches!(
                item.get("type").and_then(Value::as_str),
                Some("input_text" | "output_text")
            )
        })
        .filter_map(|item| item.get("text").and_then(Value::as_str))
        .map(python_strip)
        .filter(|text| !text.is_empty())
        .map(str::to_string)
        .collect()
}

fn codex_cwd_from_entry(entry: &Map<String, Value>) -> Option<String> {
    if entry_type(entry) == Some("session_meta") {
        let cwd = entry.get("payload")?.as_object()?.get("cwd")?.as_str()?;
        return (!cwd.is_empty()).then(|| cwd.to_string());
    }
    if entry_type(entry) != Some("response_item") {
        return None;
    }
    let payload = entry.get("payload")?.as_object()?;
    if payload.get("type").and_then(Value::as_str) != Some("message")
        || payload.get("role").and_then(Value::as_str) != Some("user")
    {
        return None;
    }
    for text in codex_text_blocks(payload.get("content").unwrap_or(&Value::Null)) {
        let stripped = python_strip(&text);
        if !stripped.starts_with("<environment_context>") {
            continue;
        }
        let Some(open) = stripped.find("<cwd>") else {
            continue;
        };
        let rest = &stripped[open + "<cwd>".len()..];
        let Some(close) = rest.find("</cwd>") else {
            continue;
        };
        let cwd = python_strip(&rest[..close]);
        if !cwd.is_empty() {
            return Some(cwd.to_string());
        }
    }
    None
}

/// The working directory, from the first entry that carries one.
pub fn cwd(entries: &[Map<String, Value>]) -> Option<String> {
    for entry in entries {
        if let Some(value) = entry.get("cwd").and_then(Value::as_str)
            && !value.is_empty()
        {
            return Some(value.to_string());
        }
        if let Some(value) = codex_cwd_from_entry(entry) {
            return Some(value);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn entries(content: &str) -> Vec<Map<String, Value>> {
        decode_entries(content)
    }

    #[test]
    fn the_first_non_blank_line_decides_the_format() {
        assert_eq!(detect_format("\n\n{\"type\": \"user\"}"), SessionFormat::Jsonl);
        assert_eq!(detect_format("{\"no\": \"type\"}\n{\"type\": \"user\"}"), SessionFormat::Raw);
        assert_eq!(detect_format("not json\n{\"type\": \"user\"}"), SessionFormat::Raw);
        assert_eq!(detect_format(""), SessionFormat::Raw);
    }

    #[test]
    fn detect_format_accepts_what_the_stdlib_parser_accepts() {
        // Python's `detect_format` uses stdlib json, which takes NaN; the decoders
        // use orjson, which does not. So this file is JSONL and loses that entry.
        let content = "{\"type\": \"user\", \"v\": NaN}\n{\"type\": \"user\"}";
        assert_eq!(detect_format(content), SessionFormat::Jsonl);
        assert_eq!(entries(content).len(), 1);
    }

    #[test]
    fn python_strip_removes_the_c0_separators_rust_trim_leaves() {
        let content = "\u{1c}{\"type\": \"user\"}";
        assert_eq!(detect_format(content), SessionFormat::Jsonl);
        assert_eq!(entries(content).len(), 1);
        // Rust's own trim would leave the byte and lose the line entirely.
        assert!(content.trim().starts_with('\u{1c}'));
    }

    /// F1's first consequence, and it decides whether a session exists at all.
    ///
    /// **Authored, not harvested.** 0 of 5,061 `.jsonl` files under `~/.claude`,
    /// `~/.pi` and `~/.codex` carry a literal `\r` (measured 2026-09-01), so no
    /// corpus of any size can grade this. The expected rows were transcribed from
    /// a Python run at oracle revision `8cb4c5f`, recorded by
    /// `teammates/parity-finisher/probes/make_newline_fixtures.py`.
    ///
    /// `detect_format` and `decode_entries` split on `\n` alone. A file whose
    /// lines end with a lone `\r` is therefore one unparseable line: the file is
    /// classified `Raw`, goes to the transcript decoder, and yields **nothing**.
    /// Python's text-mode read turned every `\r` into `\n` before `detect_format`
    /// saw a character, so it decodes the whole session.
    #[test]
    fn every_line_ending_decodes_to_the_same_session_python_decodes() {
        let home = NewlineFixtures::new();
        for (name, expected) in [
            ("jsonl-crlf.jsonl", vec![("user", "alpha question"), ("assistant", "beta answer")]),
            ("jsonl-lone-cr.jsonl", vec![("user", "alpha question"), ("assistant", "beta answer")]),
            (
                "raw-transcript-crlf.jsonl",
                vec![("user", "alpha question"), ("assistant", "\u{23fa} beta answer\ngamma continuation")],
            ),
            (
                "raw-transcript-lone-cr.jsonl",
                vec![("user", "alpha question"), ("assistant", "\u{23fa} beta answer\ngamma continuation")],
            ),
        ] {
            let scanned = home.scan(name);
            let actual: Vec<(&str, &str)> = scanned
                .iter()
                .map(|(role, text)| (role.as_str(), text.as_str()))
                .collect();
            assert_eq!(
                actual, expected,
                "{name} must decode to what Python decodes it to; the read path is \
                 text mode, so the line ending cannot change the answer"
            );
        }
    }

    /// The falsifier for the gate above, naming which two cases carry it.
    ///
    /// A reader that skips translation is caught **only** by the two lone-`\r`
    /// cases, and it is caught differently in each: the JSONL session loses every
    /// message, and the transcript collapses two messages into one. The two CRLF
    /// cases catch nothing here — `python_strip` already removes a trailing `\r`
    /// from a JSONL line, and the transcript's `\r` shows up in the message text
    /// rather than in the shape asserted above. **Recorded because a gate whose
    /// four cases look alike but where only two can fail is a gate half its
    /// apparent size.**
    #[test]
    fn the_gate_catches_a_reader_that_skips_translation() {
        let home = NewlineFixtures::new();

        assert!(
            home.scan_untranslated("jsonl-lone-cr.jsonl").is_empty(),
            "the falsifier must reproduce the pre-F1 behaviour it stands for: a \
             lone-\\r JSONL session is classified Raw and decodes to nothing. If \
             this holds no longer, the gate above proves nothing."
        );
        assert_eq!(
            home.scan_untranslated("raw-transcript-lone-cr.jsonl").len(),
            1,
            "the falsifier must reproduce the pre-F1 behaviour it stands for: a \
             lone-\\r transcript is one line, so its three lines collapse into a \
             single user message"
        );
        assert_eq!(
            home.scan_untranslated("jsonl-crlf.jsonl"),
            home.scan("jsonl-crlf.jsonl"),
            "the CRLF JSONL case is deliberately blind to F1 — `python_strip` \
             already removes the trailing \\r — and must stay recorded as blind \
             rather than counted as coverage"
        );
        assert_ne!(
            home.scan_untranslated("jsonl-lone-cr.jsonl"),
            home.scan("jsonl-lone-cr.jsonl"),
            "the gate is blind: the production read and an untranslated read agree \
             on a lone-\\r session, so nothing above would catch the F1 regression"
        );
    }

    /// The four authored newline fixtures, under a fake home, because both routes
    /// classify a session's provider by its location rather than by its content.
    struct NewlineFixtures(std::path::PathBuf);

    impl NewlineFixtures {
        const CLAUDE: &'static str = concat!(
            r#"{"type": "user", "uuid": "u1", "parentUuid": null, "cwd": "/tmp/newline", "message": {"role": "user", "content": "alpha question"}}"#,
            "\n",
            r#"{"type": "assistant", "uuid": "a1", "parentUuid": "u1", "message": {"role": "assistant", "content": [{"type": "text", "text": "beta answer"}]}}"#,
        );
        const TRANSCRIPT: &'static str =
            "> alpha question\n\u{23fa} beta answer\ngamma continuation";

        fn new() -> Self {
            static IDENTIFIER: std::sync::atomic::AtomicU64 =
                std::sync::atomic::AtomicU64::new(0);
            let home = std::env::temp_dir().join(format!(
                "chats-native-newline-home-{}-{}",
                std::process::id(),
                IDENTIFIER.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
            ));
            let directory = home.join(".claude").join("projects").join("-tmp-newline");
            std::fs::create_dir_all(&directory).expect("create fixture directory");
            for (name, body, terminator) in [
                ("jsonl-crlf.jsonl", Self::CLAUDE, "\r\n"),
                ("jsonl-lone-cr.jsonl", Self::CLAUDE, "\r"),
                ("raw-transcript-crlf.jsonl", Self::TRANSCRIPT, "\r\n"),
                ("raw-transcript-lone-cr.jsonl", Self::TRANSCRIPT, "\r"),
            ] {
                std::fs::write(directory.join(name), body.replace('\n', terminator))
                    .expect("write fixture");
            }
            Self(home)
        }

        fn path(&self, name: &str) -> std::path::PathBuf {
            self.0.join(".claude").join("projects").join("-tmp-newline").join(name)
        }

        /// The production route: the production read, then the production scan.
        fn scan(&self, name: &str) -> Vec<(String, String)> {
            let path = self.path(name);
            let content = crate::python_io::read_text(&path).expect("read fixture");
            self.messages(&path, &content)
        }

        /// The same route with the pre-F1 read spliced in.
        fn scan_untranslated(&self, name: &str) -> Vec<(String, String)> {
            let path = self.path(name);
            let bytes = std::fs::read(&path).expect("read fixture");
            let content = crate::python_io::decode_utf8(&bytes).expect("decode fixture");
            self.messages(&path, &content)
        }

        fn messages(&self, path: &std::path::Path, content: &str) -> Vec<(String, String)> {
            crate::search_confirm::scan_session(
                path,
                content,
                &crate::visibility::ConversationFlags::default(),
                &self.0,
            )
            .expect("scan fixture")
            .messages
            .iter()
            .map(|message| (message.role.clone(), message.text.clone()))
            .collect()
        }
    }

    impl Drop for NewlineFixtures {
        fn drop(&mut self) {
            std::fs::remove_dir_all(&self.0).expect("remove fixture home");
        }
    }

    /// Every regex in this module that stands in for a CPython `\s` or `\w` must
    /// use CPython's class, not the Rust crate's.
    ///
    /// The Rust `regex` crate reads `\s` as `\p{White_Space}` and `\w` by UTS#18.
    /// Neither is CPython's. Each case below is a string CPython's pattern matches
    /// and the crate's bare class does not — or, for the last two, the reverse.
    ///
    /// **Authored, not harvested**, like everything else about this class: not one
    /// of 5,046 real files contains U+001C..U+001F anywhere. The corpus-scale
    /// evidence is `probes/c0_injection_differential.py`, which injects the
    /// separators into the real pool and is proved to catch a reverted
    /// `python_is_space` at 670 of 840 Claude cases, 840 of 840 Pi and 784 of 840
    /// Codex.
    #[test]
    fn the_character_classes_are_pythons_and_not_the_crates() {
        assert!(
            local_command_stdout_regex()
                .is_match("\u{1c}<local-command-stdout>x</local-command-stdout>\u{1f}"),
            "a C0 separator around hidden command output must be absorbed by the \
             leading and trailing class, as CPython's `\\s*` absorbs it; leaving it \
             out makes the block visible to search on one route only"
        );
        assert!(
            task_notification_regex()
                .is_match("\u{1c}<task-notification>x</task-notification>\u{1f}"),
            "same class, and this one decides whether a background-task \
             notification renders at all"
        );
        assert!(
            pi_skill_token_regex().is_match("<skill\u{1c}name=\"x\">"),
            "the separator between the tag name and its attributes is `\\s` in \
             CPython, so this opening tag must still be recognised"
        );
        assert_eq!(
            pi_skill_attribute_regex()
                .captures("\u{bd}=\"x\"")
                .map(|found| found[1].to_string()),
            Some("\u{bd}".to_string()),
            "CPython's `\\w` is `str.isalnum()`, which accepts the `No` numeric \
             U+00BD; the crate's `\\w` rejects it"
        );
        assert!(
            pi_skill_attribute_regex().captures("\u{301}=\"x\"").is_none(),
            "and the difference runs the other way too: the crate's `\\w` accepts a \
             lone combining mark through `\\p{{M}}`, CPython's does not"
        );
        assert!(
            pi_user_agent_prefix_regex()
                .is_match("<user_agent\u{1c}id=\"1\">\n<user_invocation>\n"),
            "the user-agent envelope's attribute separator is `\\s` in CPython; \
             failing it here drops the whole agent response"
        );
    }

    /// The falsifier for the gate above: the crate's bare classes, run on the same
    /// six strings, must disagree with CPython on every one.
    ///
    /// Without this, a future edit that quietly restores `\s` and `\w` would leave
    /// the gate above green on any input that happens to avoid the difference, and
    /// a reader could not tell a covered class from an uncovered one.
    #[test]
    fn the_gate_catches_the_crates_bare_classes() {
        let bare_space = Regex::new(r"(?s)^\s*<local-command-stdout>.*?</local-command-stdout>\s*$")
            .expect("bare space pattern");
        let bare_skill = Regex::new(r"<skill(?:\s[^>]*)?>|</skill>").expect("bare skill pattern");
        let bare_agent = Regex::new(r"^<user_agent(?:\s[^>\r\n]*)?>\r?\n<user_invocation>\r?\n")
            .expect("bare agent pattern");
        let bare_word = Regex::new(r#"([\w-]+)="([^"]*)""#).expect("bare word pattern");

        assert!(
            !bare_space.is_match("\u{1c}<local-command-stdout>x</local-command-stdout>\u{1f}"),
            "the falsifier must reproduce the divergence it stands for: the crate's \
             `\\s` does not absorb U+001C. If this passes, the crate changed and the \
             gate above no longer proves anything."
        );
        assert!(
            !bare_skill.is_match("<skill\u{1c}name=\"x\">"),
            "same, for the Pi skill token"
        );
        assert!(
            !bare_agent.is_match("<user_agent\u{1c}id=\"1\">\n<user_invocation>\n"),
            "same, for the user-agent envelope"
        );
        assert!(
            bare_word.captures("\u{bd}=\"x\"").is_none(),
            "the crate's `\\w` rejects U+00BD where CPython accepts it"
        );
        assert!(
            bare_word.captures("\u{301}=\"x\"").is_some(),
            "and accepts a lone combining mark where CPython rejects it — this is \
             the direction an implementer never checks"
        );
    }

    /// `python_strip_start` is `str.lstrip()`, not `str.strip()`.
    ///
    /// Two call sites use the length of what it removed as a byte cursor, so a
    /// both-ends strip here would move the cursor past content rather than to it.
    #[test]
    fn python_strip_start_leaves_the_trailing_side_alone() {
        assert_eq!(python_strip_start("\u{1c} a \u{1f}"), "a \u{1f}");
        assert_eq!(python_strip("\u{1c} a \u{1f}"), "a");
        assert_eq!(
            "\u{1c} a \u{1f}".trim_start(),
            "\u{1c} a \u{1f}",
            "the falsifier: Rust's own `trim_start` removes nothing here, which is \
             the whole reason the two cursor sites needed a Python variant"
        );
    }

    /// `dedent` is `textwrap.dedent`, and the two rules that make it so are the
    /// two a shortest-indent implementation gets wrong.
    ///
    /// Every expectation was transcribed from a CPython 3.14 run, not reasoned
    /// out. The last case is the one that used to **panic**: the old version took
    /// a byte count from one line and sliced another with it, landing inside
    /// U+2028.
    #[test]
    fn dedent_reproduces_textwrap_dedent() {
        for (input, expected) in [
            (" a\n  b", "a\n b"),
            // A space and a tab share no common prefix, so nothing is removed.
            // A shortest-indent rule removes one character from each and gives
            // "a\nb".
            (" a\n\tb", " a\n\tb"),
            ("\ta\n\tb", "a\nb"),
            ("  a\n  b\n\n  c", "a\nb\n\nc"),
            // A whitespace-only line comes back empty rather than dedented.
            ("  a\n   \n  b", "a\n\nb"),
            // Blank is `str.isspace()`, so a line of C0 separators is blank too.
            ("  a\n\u{1c}\n  b", "a\n\nb"),
            // Only spaces and tabs are margin. Any other whitespace stops it.
            ("\u{a0}a\n\u{a0}b", "\u{a0}a\n\u{a0}b"),
            ("\u{a0}a\n\u{2028}1b", "\u{a0}a\n\u{2028}1b"),
            ("", ""),
            ("\u{1c} \u{1f}", ""),
            ("a\nb", "a\nb"),
            ("  ", ""),
        ] {
            assert_eq!(
                dedent(input),
                expected,
                "dedent({input:?}) must reproduce textwrap.dedent at CPython 3.14"
            );
        }
    }

    /// A `<command-*>` block is protocol content only when the closing tag names
    /// the same command as the opening one.
    ///
    /// Python spells that with the backreference `</(?P=tag)>`. The `regex` crate
    /// has none, so the closing name is captured and compared. **This decides
    /// visibility**: a mismatched pair is ordinary user text that search can
    /// match, and treating it as protocol hides it on one route only.
    #[test]
    fn a_command_block_needs_matching_open_and_close_tags() {
        for (content, hidden) in [
            ("<command-name>x</command-name>", true),
            ("<command-name>x</command-other>", false),
            ("  <command-a>x</command-a>\n  <command-b>y</command-b>", true),
            ("  <command-a>x</command-a>\n  <command-b>y</command-a>", false),
        ] {
            assert_eq!(
                is_hidden_user_command_text(content),
                hidden,
                "{content:?} must be hidden={hidden}, which is what Python's \
                 backreference decides"
            );
        }
    }

    /// The falsifier for the test above: the pattern without the closing capture
    /// accepts a mismatched pair, so the comparison is doing the work.
    #[test]
    fn the_gate_catches_a_pattern_with_no_closing_backreference() {
        let without_backreference = Regex::new(
            r"(?s)^(?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</command-[a-z0-9-]+>[ \t]*$",
        )
        .expect("pattern without the closing capture");
        assert!(
            without_backreference.is_match("<command-name>x</command-other>"),
            "the falsifier must reproduce what it stands for: a pattern that does \
             not compare the two tag names matches a mismatched pair. If this stops \
             holding, the gate above no longer proves the comparison is load-bearing."
        );
    }

    #[test]
    fn first_entry_aborts_where_decode_entries_skips() {
        let content = "not json\n{\"type\": \"user\"}";
        assert!(first_entry(content).is_none());
        assert_eq!(entries(content).len(), 1);
    }

    #[test]
    fn pi_headers_need_an_integer_version() {
        let integer = decode_entries("{\"type\": \"session\", \"version\": 3}");
        assert!(is_pi_session_header(&integer[0]));
        for rejected in [
            "{\"type\": \"session\", \"version\": \"3\"}",
            "{\"type\": \"session\", \"version\": 3.5}",
            "{\"type\": \"session\", \"version\": true}",
            "{\"type\": \"session\"}",
        ] {
            let decoded = decode_entries(rejected);
            assert!(!is_pi_session_header(&decoded[0]), "{rejected}");
        }
    }

    #[test]
    fn provider_selection_prefers_the_path_then_the_header() {
        let codex = decode_entries("{\"type\": \"session_meta\"}");
        assert_eq!(select_provider(None, Some(&codex[0])), Ok(Provider::Codex));
        assert_eq!(
            select_provider(Some(Provider::Claude), Some(&codex[0])),
            Ok(Provider::Claude)
        );
        let unknown = decode_entries("{\"type\": \"user\"}");
        assert!(select_provider(None, Some(&unknown[0])).is_err());
    }

    #[test]
    fn the_latest_custom_title_wins_across_all_three_spellings() {
        let content = concat!(
            "{\"type\": \"custom-title\", \"customTitle\": \"first\"}\n",
            "{\"type\": \"session_info\", \"name\": \"  second  \"}\n",
            "{\"type\": \"event_msg\", \"payload\": {\"type\": \"thread_name_updated\", \"thread_name\": \"third\"}}"
        );
        assert_eq!(latest_custom_title(&entries(content)), Some("third".to_string()));
    }

    #[test]
    fn cwd_comes_from_the_first_entry_that_has_one() {
        let plain = entries("{\"type\": \"user\"}\n{\"type\": \"user\", \"cwd\": \"/repo\"}");
        assert_eq!(cwd(&plain), Some("/repo".to_string()));

        let codex_meta = entries("{\"type\": \"session_meta\", \"payload\": {\"cwd\": \"/from-meta\"}}");
        assert_eq!(cwd(&codex_meta), Some("/from-meta".to_string()));

        let environment = entries(concat!(
            "{\"type\": \"response_item\", \"payload\": {\"type\": \"message\", \"role\": \"user\",",
            " \"content\": [{\"type\": \"input_text\", \"text\": \"<environment_context>\\n<cwd>/from-env</cwd>\\n</environment_context>\"}]}}"
        ));
        assert_eq!(cwd(&environment), Some("/from-env".to_string()));
    }

    #[test]
    fn summaries_keep_file_order_and_drop_empties() {
        let content = concat!(
            "{\"type\": \"summary\", \"summary\": \"one\"}\n",
            "{\"type\": \"summary\", \"summary\": \"\"}\n",
            "{\"type\": \"summary\", \"summary\": \"two\"}"
        );
        assert_eq!(summaries(&entries(content)), vec!["one", "two"]);
    }
}

// ------------------------------------------------------- Claude branch resolution

use std::collections::{HashMap, HashSet};

use indexmap::IndexMap;

fn is_compaction(entry: &Map<String, Value>) -> bool {
    entry_type(entry) == Some("system")
        && entry.get("subtype").and_then(Value::as_str) == Some("compact_boundary")
}

fn uuid_of(entry: &Map<String, Value>) -> Option<&str> {
    entry.get("uuid").and_then(Value::as_str)
}

/// Longest downward chain length per node, memoised in reverse preorder.
fn subtree_depths(
    roots: &[&str],
    children: &HashMap<Option<&str>, Vec<&str>>,
) -> HashMap<String, usize> {
    let mut depth: HashMap<String, usize> = HashMap::new();
    for root in roots {
        let mut order: Vec<&str> = Vec::new();
        let mut stack = vec![*root];
        while let Some(node) = stack.pop() {
            order.push(node);
            if let Some(kids) = children.get(&Some(node)) {
                stack.extend(kids.iter().copied());
            }
        }
        for node in order.into_iter().rev() {
            let deepest = children
                .get(&Some(node))
                .map(|kids| {
                    kids.iter()
                        .map(|kid| depth.get(*kid).copied().unwrap_or(0))
                        .max()
                        .unwrap_or(0)
                })
                .unwrap_or(0);
            depth.insert(node.to_string(), 1 + deepest);
        }
    }
    depth
}

/// Follow the deepest child from `root` to its leaf.
///
/// Python's `max` keeps the **first** maximal element; Rust's `max_by_key` keeps the
/// last. Ties happen whenever two branches are equally long, so this walks explicitly
/// and only replaces on a strictly greater depth.
fn deepest_descendant<'a>(
    root: &'a str,
    children: &HashMap<Option<&'a str>, Vec<&'a str>>,
    depth: &HashMap<String, usize>,
) -> &'a str {
    let mut cursor = root;
    while let Some(kids) = children.get(&Some(cursor)).filter(|kids| !kids.is_empty()) {
        let mut best = kids[0];
        let mut best_depth = depth.get(best).copied().unwrap_or(0);
        for kid in &kids[1..] {
            let kid_depth = depth.get(*kid).copied().unwrap_or(0);
            if kid_depth > best_depth {
                best = kid;
                best_depth = kid_depth;
            }
        }
        cursor = best;
    }
    cursor
}

fn collect_subtree<'a>(root: &'a str, children: &HashMap<Option<&'a str>, Vec<&'a str>>) -> HashSet<&'a str> {
    let mut seen: HashSet<&str> = HashSet::new();
    let mut stack = vec![root];
    while let Some(node) = stack.pop() {
        if !seen.insert(node) {
            continue;
        }
        if let Some(kids) = children.get(&Some(node)) {
            stack.extend(kids.iter().copied());
        }
    }
    seen
}

/// The session-start root of the lineage an active leaf belongs to.
///
/// Hops back across compaction boundaries through `logicalParentUuid`, so a leaf in a
/// post-compaction era still resolves to the era that began the session.
fn origin_session_root<'a>(
    start_leaf: &'a str,
    nodes: &HashMap<&'a str, &'a Map<String, Value>>,
    parent: &HashMap<&'a str, Option<&'a str>>,
) -> Option<&'a str> {
    let mut cursor: Option<&'a str> = Some(start_leaf);
    let mut visited: HashSet<&'a str> = HashSet::new();
    while let Some(current) = cursor.filter(|value| nodes.contains_key(value)) {
        if !visited.insert(current) {
            break;
        }
        let mut root = current;
        while let Some(Some(next)) = parent.get(root)
            && nodes.contains_key(next)
        {
            root = next;
        }
        if !is_compaction(nodes[root]) {
            return Some(root);
        }
        cursor = nodes[root].get("logicalParentUuid").and_then(Value::as_str);
    }
    None
}

/// Map each off-main-branch node uuid to a stable branch id.
///
/// A Claude transcript is a forest. Real eras are the session start and each
/// `/compact` boundary; a rewind to the first message adds an abandoned null-parent
/// user root, which is a detour rather than an era. Within each era the active branch
/// is chosen by the latest `last-prompt` leaf and followed *down* to its tip, then up
/// to the root. Nodes off every era's main path are abandoned branches, each
/// identified by its head — the first node that left the main thread — so one detour
/// shares one id. **Ids are numbered by first appearance in file order**, not by
/// traversal order; the two disagree and only file order is correct.
pub fn branch_map(entries: &[Map<String, Value>]) -> HashMap<String, String> {
    // Python builds `nodes` as a dict comprehension, so a repeated uuid keeps its
    // first position and takes the last entry's value — and the graph is then built
    // from `nodes`, not from the entries. Real sessions do carry duplicate uuids, so
    // building from the entries double-counts a node's edges and changes the answer.
    let mut node_map: IndexMap<&str, &Map<String, Value>> = IndexMap::new();
    for entry in entries {
        if let Some(uuid) = uuid_of(entry) {
            node_map.insert(uuid, entry);
        }
    }
    if node_map.is_empty() {
        return HashMap::new();
    }
    let nodes: HashMap<&str, &Map<String, Value>> =
        node_map.iter().map(|(uuid, entry)| (*uuid, *entry)).collect();

    let mut children: HashMap<Option<&str>, Vec<&str>> = HashMap::new();
    let mut parent: HashMap<&str, Option<&str>> = HashMap::new();
    let mut all_roots: Vec<&str> = Vec::new();
    for (uuid, entry) in &node_map {
        let parent_uuid = entry.get("parentUuid").and_then(Value::as_str);
        children.entry(parent_uuid).or_default().push(uuid);
        parent.insert(uuid, parent_uuid);
        if parent_uuid.is_none_or(|value| !node_map.contains_key(value)) {
            all_roots.push(uuid);
        }
    }

    let leaves: Vec<&str> = entries
        .iter()
        .filter(|entry| entry_type(entry) == Some("last-prompt"))
        .filter_map(|entry| entry.get("leafUuid").and_then(Value::as_str))
        .filter(|leaf| nodes.contains_key(leaf))
        .collect();

    let depth = subtree_depths(&all_roots, &children);

    let active_leaf = leaves.last().copied();
    let session_roots: Vec<&str> = all_roots
        .iter()
        .copied()
        .filter(|root| !is_compaction(nodes[root]))
        .collect();
    let compaction_roots: Vec<&str> = all_roots
        .iter()
        .copied()
        .filter(|root| is_compaction(nodes[root]))
        .collect();
    let origin_root = active_leaf.and_then(|leaf| origin_session_root(leaf, &nodes, &parent));

    let mut era_roots = compaction_roots;
    match origin_root {
        Some(root) => era_roots.push(root),
        None => era_roots.extend(session_roots),
    }

    let mut main: HashSet<&str> = HashSet::new();
    for root in &era_roots {
        let members = collect_subtree(root, &children);
        let anchor = leaves
            .iter()
            .rev()
            .find(|leaf| members.contains(*leaf))
            .copied()
            .unwrap_or(root);
        let mut cursor = Some(deepest_descendant(anchor, &children, &depth));
        while let Some(node) = cursor.filter(|value| nodes.contains_key(value)) {
            main.insert(node);
            cursor = parent.get(node).copied().flatten();
        }
    }

    let mut head_ids: HashMap<&str, String> = HashMap::new();
    let mut branch_of: HashMap<String, String> = HashMap::new();
    for entry in entries {
        let Some(uuid) = uuid_of(entry) else { continue };
        if !nodes.contains_key(uuid) || main.contains(uuid) {
            continue;
        }
        // Walk up to the first node that left the main thread.
        let mut head = uuid;
        loop {
            match parent.get(head).copied().flatten() {
                Some(ancestor) if !main.contains(ancestor) => head = ancestor,
                _ => break,
            }
        }
        let next_id = (head_ids.len() + 1).to_string();
        let id = head_ids.entry(head).or_insert(next_id).clone();
        branch_of.insert(uuid.to_string(), id);
    }
    branch_of
}

// ------------------------------------------------------------- Claude decoding

use crate::model::{Message, MessageType, Tool, ToolResult, ToolUse};
use crate::visibility::ConversationFlags;

/// Resolve the wrapper type Python's `get_wrapper_type` would pick.
///
/// An explicit override wins, then `agent_id` — so every message belonging to a
/// subagent renders as one block, including its tool-result `user` entries — then role.
fn resolve_message_type(
    override_type: Option<MessageType>,
    agent_id: Option<&str>,
    role: &str,
) -> MessageType {
    if let Some(explicit) = override_type {
        return explicit;
    }
    if agent_id.is_some_and(|value| !value.is_empty()) {
        return MessageType::Agent;
    }
    match role {
        "user" => MessageType::UserMessage,
        "session-rename" => MessageType::SessionRename,
        _ => MessageType::AssistantResponse,
    }
}

fn new_message(index: usize, role: &str, message_type: MessageType) -> Message {
    Message::new(message_type, role.to_string(), index.into())
}

/// Collect text blocks from a message content field.
pub fn extract_text_blocks(content: &Value) -> Vec<String> {
    match content {
        Value::String(text) => {
            if text.is_empty() { Vec::new() } else { vec![text.clone()] }
        }
        Value::Array(items) => items
            .iter()
            .filter_map(Value::as_object)
            .filter_map(|item| item.get("text").and_then(Value::as_str))
            .map(python_strip)
            .filter(|text| !text.is_empty())
            .map(str::to_string)
            .collect(),
        _ => Vec::new(),
    }
}

/// Parse pure `<command-*>` lines, preserving their relative indentation.
///
/// Returns nothing unless *every* non-blank line is a complete command tag, which is
/// what makes this a reliable test for hidden protocol content.
fn command_tag_lines(content: &str) -> Option<Vec<(usize, String, String)>> {
    let pattern = command_tag_regex();
    let mut parsed = Vec::new();
    for raw_line in content.lines() {
        if python_strip(raw_line).is_empty() {
            continue;
        }
        let captures = pattern.captures(raw_line)?;
        if captures.get(0)?.as_str() != raw_line {
            return None;
        }
        // Python's pattern closes with the backreference `</(?P=tag)>`, which the
        // `regex` crate has no equivalent for, so the closing name is captured and
        // compared here instead. Without it `<command-a>x</command-b>` is protocol
        // content on this route and ordinary user text on Python's, which decides
        // whether search can see the block at all.
        if captures.name("close")?.as_str() != captures.name("tag")?.as_str() {
            return None;
        }
        let indent = captures
            .name("indent")
            .map(|m| expand_tabs(m.as_str()))
            .unwrap_or(0);
        let key = captures.name("tag")?.as_str().trim_start_matches("command-");
        let value = normalize_command_tag_value(captures.name("value")?.as_str());
        parsed.push((indent, key.to_string(), value));
    }
    (!parsed.is_empty()).then_some(parsed)
}

fn expand_tabs(indent: &str) -> usize {
    indent.chars().map(|c| if c == '\t' { 4 } else { 1 }).sum()
}

fn normalize_command_tag_value(raw: &str) -> String {
    let stripped = python_strip(raw);
    if !stripped.contains('\n') {
        return stripped.to_string();
    }
    python_strip(&dedent(stripped)).to_string()
}

/// `textwrap.dedent`, CPython 3.14's implementation.
///
/// The margin is the common prefix of the lexicographically **smallest and
/// largest** non-blank lines, stopped at the first character that is not a space
/// or a tab. It is not the shortest indent, which is what the previous version
/// computed: `" a\n\tb"` dedents to itself here and to `"a\nb"` under a
/// shortest-indent rule, because a space and a tab share no common prefix.
///
/// Blank means `str.isspace()`, so U+001C..U+001F count, and a blank line comes
/// back **empty** rather than keeping its whitespace.
fn dedent(value: &str) -> String {
    fn is_blank(line: &str) -> bool {
        !line.is_empty() && line.chars().all(python_is_space)
    }
    let lines: Vec<&str> = value.split('\n').collect();
    let non_blank: Vec<&str> = lines
        .iter()
        .copied()
        .filter(|line| !line.is_empty() && !is_blank(line))
        .collect();
    let margin = match (non_blank.iter().min(), non_blank.iter().max()) {
        (Some(low), Some(high)) => low
            .chars()
            .zip(high.chars())
            .take_while(|(left, right)| left == right && matches!(left, ' ' | '\t'))
            .count(),
        _ => 0,
    };
    lines
        .iter()
        .copied()
        .map(|line| {
            if is_blank(line) {
                return "";
            }
            // The margin is spaces and tabs only, and every non-blank line shares
            // it with the lexicographic extremes, so this offset always lands on a
            // character boundary and never past the end. The previous version
            // sliced at a byte count taken from a different line and panicked on
            // `"\u{a0}a\n\u{2028}b"`.
            let offset: usize = line.chars().take(margin).map(char::len_utf8).sum();
            &line[offset..]
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn command_tag_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(
            r"(?s)^(?P<indent>[ \t]*)<(?P<tag>command-[a-z0-9-]+)>(?P<value>.*?)</(?P<close>command-[a-z0-9-]+)>[ \t]*$",
        )
        .expect("command tag regex")
    })
}

fn local_command_stdout_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(&format!(
            r"(?s)^[{0}]*<local-command-stdout>.*?</local-command-stdout>[{0}]*$",
            PYTHON_SPACE_CLASS
        ))
        .expect("local command stdout regex")
    })
}

/// Whether a user text block is protocol command I/O that stays hidden.
pub fn is_hidden_user_command_text(content: &str) -> bool {
    if local_command_stdout_regex().is_match(content) {
        return true;
    }
    command_tag_lines(content).is_some()
}

/// Drop user text blocks representing hidden command protocol content.
pub fn filter_hidden_user_text_blocks(blocks: Vec<String>) -> Vec<String> {
    blocks
        .into_iter()
        .filter(|block| !is_hidden_user_command_text(block))
        .collect()
}

fn task_notification_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(&format!(
            r"(?s)^[{0}]*<task-notification>(?P<body>.*)</task-notification>[{0}]*$",
            PYTHON_SPACE_CLASS
        ))
        .expect("task notification regex")
    })
}

/// Whether a user string is a background-task notification.
///
/// Python converts it into a synthetic `TaskNotification` tool so it classifies and
/// filters as a tool; the message itself then renders nothing.
fn is_task_notification(content: &str) -> bool {
    task_notification_regex().is_match(content)
}

fn agent_id_of(entry: &Map<String, Value>) -> Option<&str> {
    entry.get("agentId").and_then(Value::as_str)
}

fn timestamp_of(entry: &Map<String, Value>) -> Option<String> {
    entry
        .get("timestamp")
        .and_then(Value::as_str)
        .map(str::to_string)
}

fn source_tool_use_id(entry: &Map<String, Value>) -> Option<&str> {
    ["sourceToolUseID", "sourceToolUseId", "sourceToolUserId"]
        .iter()
        .find_map(|key| entry.get(*key).and_then(Value::as_str))
        .filter(|value| !value.is_empty())
}

/// Shorten a tool id the way Python's `shorten_tool_use_id` does.
///
/// Note this differs from `codecs::short_tool_id` at exactly one input: an id that is
/// only a prefix, such as `"toolu_"`, yields `Some("")` here and `None` there. The
/// render path treats both as absent because it tests truthiness, so they agree where
/// it matters; this one feeds a tool payload, where the empty string is what Python
/// stores.
fn shorten_tool_use_id(value: Option<&str>) -> Option<String> {
    let value = value.filter(|text| !text.is_empty())?;
    let trimmed = value
        .strip_prefix("toolu_")
        .or_else(|| value.strip_prefix("call_"))
        .unwrap_or(value);
    Some(trimmed.chars().take(4).collect())
}

fn tools_requested(flags: &ConversationFlags) -> bool {
    match &flags.show_tools {
        crate::tool_filter::ToolVisibility::All(shown) => *shown,
        crate::tool_filter::ToolVisibility::Filters(filters) => !filters.is_empty(),
    }
}

/// Build a `Tool` from a raw provider content block.
fn tool_from_json(item: &Map<String, Value>, provider: &str) -> Option<Tool> {
    match item.get("type").and_then(Value::as_str) {
        Some("tool_use") => {
            let name = crate::model::normalize_tool_name(
                provider,
                item.get("name").and_then(Value::as_str),
            );
            let input = item.get("input").cloned().unwrap_or(Value::Null);
            Some(Tool::Use(ToolUse {
                input: crate::model::normalize_tool_input_keys(provider, &name, &input),
                name,
                id: item.get("id").and_then(Value::as_str).map(str::to_string),
                native_tool_call_id: None,
                native_content_index: None,
            }))
        }
        Some("tool_result") => Some(Tool::Result(ToolResult {
            name: item.get("name").and_then(Value::as_str).map(str::to_string),
            tool_use_id: item
                .get("tool_use_id")
                .and_then(Value::as_str)
                .map(str::to_string),
            native_tool_call_id: None,
            is_error: item.get("is_error").and_then(Value::as_bool).unwrap_or(false),
            content: item.get("content").cloned(),
            has_content: item.contains_key("content"),
        })),
        _ => None,
    }
}

/// Classify `isMeta` payload text linked to a tool call as that tool's output.
fn append_meta_source_tool_result(
    message: &mut Message,
    source: Option<&str>,
    text_blocks: &[String],
    flags: &ConversationFlags,
) -> bool {
    if !(tools_requested(flags) && message.is_meta && source.is_some() && !text_blocks.is_empty()) {
        return false;
    }
    message.tools.push(Tool::Result(ToolResult {
        name: None,
        tool_use_id: source.map(str::to_string),
        native_tool_call_id: None,
        is_error: false,
        content: Some(Value::String(text_blocks.join("\n\n"))),
        has_content: true,
    }));
    true
}

fn parse_user_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Option<Message> {
    let message_data = entry.get("message")?.as_object()?;
    if message_data.get("role").and_then(Value::as_str) != Some("user") {
        return None;
    }
    let source = source_tool_use_id(entry);
    let is_meta = entry.get("isMeta").and_then(Value::as_bool) == Some(true);
    let mut message = new_message(index, "user", MessageType::UserMessage);
    message.timestamp = timestamp_of(entry);
    message.is_meta = is_meta;
    message.source_tool_user_id = shorten_tool_use_id(source);

    let content = message_data.get("content").unwrap_or(&Value::Null);

    // A background-task notification renders nothing; the merged agent block is its
    // representation.
    if let Value::String(text) = content
        && is_task_notification(text)
    {
        return Some(message);
    }

    let show_user_text = flags.show_user_messages() && (!is_meta || tools_requested(flags));

    match content {
        Value::String(text) => {
            let blocks = vec![text.clone()];
            if append_meta_source_tool_result(&mut message, source, &blocks, flags) {
                return Some(message);
            }
            if show_user_text && !is_hidden_user_command_text(text) {
                message.text = text.clone();
            }
        }
        Value::Array(items) => {
            let blocks = filter_hidden_user_text_blocks(extract_text_blocks(content));
            if tools_requested(flags) {
                for item in items.iter().filter_map(Value::as_object) {
                    if item.get("type").and_then(Value::as_str) == Some("tool_result")
                        && let Some(tool) = tool_from_json(item, "claude")
                    {
                        message.tools.push(tool);
                    }
                }
            }
            if append_meta_source_tool_result(&mut message, source, &blocks, flags) {
                return Some(message);
            }
            if !blocks.is_empty() && show_user_text {
                message.text = blocks.join("\n\n");
            }
        }
        _ => {}
    }

    // A post-compaction summary arrives as a user turn but is its own block.
    if entry.get("isCompactSummary").and_then(Value::as_bool) == Some(true) {
        message.message_type = MessageType::Compaction;
    }
    Some(message)
}

fn parse_assistant_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Option<Message> {
    let message_data = entry.get("message")?.as_object()?;
    if message_data.get("role").and_then(Value::as_str) != Some("assistant") {
        return None;
    }
    let agent_id = agent_id_of(entry).filter(|value| !value.is_empty());
    if agent_id.is_some() && !flags.show_agents {
        return None;
    }
    let show_message_text = if agent_id.is_some() {
        flags.show_agents
    } else {
        flags.show_assistant_messages()
    };
    let items = message_data.get("content")?.as_array()?;

    let mut message = new_message(
        index,
        "assistant",
        resolve_message_type(None, agent_id, "assistant"),
    );
    message.agent_id = agent_id.map(str::to_string);
    message.timestamp = timestamp_of(entry);
    message.model = message_data
        .get("model")
        .and_then(Value::as_str)
        .map(str::to_string);

    let mut text_blocks: Vec<String> = Vec::new();
    for item in items.iter().filter_map(Value::as_object) {
        match item.get("type").and_then(Value::as_str) {
            Some("text") => {
                if let Some(text) = item.get("text").and_then(Value::as_str)
                    && !python_strip(text).is_empty()
                {
                    text_blocks.push(python_strip(text).to_string());
                }
            }
            Some("thinking") if flags.show_thinking => {
                message.thinking = Some(
                    python_strip(
                        item.get("thinking").and_then(Value::as_str).unwrap_or_default(),
                    )
                    .to_string(),
                );
            }
            Some("tool_use") => {
                let name = item.get("name").and_then(Value::as_str).unwrap_or_default();
                if name == "ExitPlanMode" {
                    if show_message_text
                        && let Some(plan) = item
                            .get("input")
                            .and_then(Value::as_object)
                            .and_then(|input| input.get("plan"))
                            .and_then(Value::as_str)
                        && !plan.is_empty()
                    {
                        message.plan = Some(plan.to_string());
                    }
                } else if tools_requested(flags)
                    && let Some(tool) = tool_from_json(item, "claude")
                {
                    message.tools.push(tool);
                }
            }
            _ => {}
        }
    }

    if !text_blocks.is_empty() && show_message_text {
        message.text = text_blocks.join("\n\n");
    }
    Some(message)
}

fn parse_system_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Option<Message> {
    if !flags.show_assistant_messages() {
        return None;
    }
    if entry.get("subtype").and_then(Value::as_str) != Some("away_summary") {
        return None;
    }
    let content = entry.get("content")?.as_str()?;
    let recap = python_strip(
        content
            .strip_suffix(" (disable recaps in /config)")
            .unwrap_or(content),
    );
    if recap.is_empty() {
        return None;
    }
    let mut message = new_message(index, "assistant", MessageType::Recap);
    message.text = recap.to_string();
    message.timestamp = timestamp_of(entry);
    Some(message)
}

/// Represent a hook's injected additional context as an `AdditionalContext` tool, so
/// it obeys the shared `--tools` visibility policy.
fn parse_hook_additional_context_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Option<Message> {
    if !tools_requested(flags) {
        return None;
    }
    let attachment = entry.get("attachment")?.as_object()?;
    if attachment.get("type").and_then(Value::as_str) != Some("hook_additional_context") {
        return None;
    }
    let blocks = attachment.get("content")?.as_array()?;
    let text = blocks
        .iter()
        .filter_map(Value::as_str)
        .filter(|block| !python_strip(block).is_empty())
        .collect::<Vec<_>>()
        .join("\n\n");
    if text.is_empty() {
        return None;
    }
    let mut message = new_message(index, "user", MessageType::UserMessage);
    message.timestamp = timestamp_of(entry);
    let hook_name = attachment
        .get("hookName")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let mut input = Map::new();
    input.insert("hook_name".to_string(), Value::String(hook_name.to_string()));
    input.insert("content".to_string(), Value::String(text));
    message.tools.push(Tool::Use(ToolUse {
        name: "AdditionalContext".to_string(),
        input: Value::Object(input),
        id: None,
        native_tool_call_id: None,
        native_content_index: None,
    }));
    Some(message)
}

/// Drop the Agent/Task dispatch `tool_use` and its paired `tool_result`.
///
/// The merged agent block and its `<subagent-task>` are their representation, so the
/// raw dispatch pair is plumbing.
fn suppress_agent_dispatch(messages: &mut [Message]) {
    let dispatch_ids: HashSet<String> = messages
        .iter()
        .flat_map(|message| &message.tools)
        .filter_map(|tool| match tool {
            Tool::Use(use_tool) if matches!(use_tool.name.as_str(), "Agent" | "Task") => {
                use_tool.id.clone()
            }
            _ => None,
        })
        .collect();
    for message in messages {
        message.tools.retain(|tool| match tool {
            Tool::Use(use_tool) => !matches!(use_tool.name.as_str(), "Agent" | "Task"),
            Tool::Result(result) => !result
                .tool_use_id
                .as_ref()
                .is_some_and(|id| dispatch_ids.contains(id)),
        });
    }
}

fn has_content(message: &Message) -> bool {
    !message.text.is_empty()
        || message.thinking.as_deref().is_some_and(|v| !v.is_empty())
        || !message.tools.is_empty()
        || message.plan.as_deref().is_some_and(|v| !v.is_empty())
        || message.subagent_task.as_deref().is_some_and(|v| !v.is_empty())
}

/// Decode Claude-shaped JSONL entries into the shared message model.
pub fn parse_claude(entries: &[Map<String, Value>], flags: &ConversationFlags) -> Vec<Message> {
    let branch_of = branch_map(entries);
    let mut messages = Vec::new();
    let mut index = 1usize;

    for entry in entries {
        let branch_id = uuid_of(entry).and_then(|uuid| branch_of.get(uuid));
        if branch_id.is_some() && !flags.show_branches {
            continue; // abandoned rewind branch, hidden unless --branches
        }
        let message = match entry_type(entry) {
            Some("user") => parse_user_entry(entry, index, flags),
            Some("assistant") => parse_assistant_entry(entry, index, flags),
            Some("system") => parse_system_entry(entry, index, flags),
            Some("attachment") => parse_hook_additional_context_entry(entry, index, flags),
            _ => None,
        };
        if let Some(mut message) = message
            && has_content(&message)
        {
            message.branch = branch_id.cloned();
            messages.push(message);
            index += 1;
        }
    }

    suppress_agent_dispatch(&mut messages);
    messages
}

// ---------------------------------------------------------------- Pi decoding

/// One expanded inline skill peeled from the front of a Pi user message.
struct PiInlineSkill {
    input: Map<String, Value>,
    body: String,
}

fn pi_skill_token_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(&format!(r"<skill(?:[{PYTHON_SPACE_CLASS}][^>]*)?>|</skill>"))
            .expect("pi skill token")
    })
}

fn pi_skill_attribute_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(&format!(r#"([{PYTHON_WORD_CLASS}-]+)="([^"]*)""#))
            .expect("pi skill attribute")
    })
}

/// Map a skill opening tag's attributes to `Skill` tool input keys — `name` becomes `skill`.
fn parse_pi_skill_attributes(opening: &str) -> Map<String, Value> {
    let mut input = Map::new();
    for captures in pi_skill_attribute_regex().captures_iter(opening) {
        let key = &captures[1];
        let key = if key == "name" { "skill" } else { key };
        input.insert(key.to_string(), Value::String(captures[2].to_string()));
    }
    input
}

/// Split the **leading run** of inline-skill blocks from the typed user text.
///
/// Only the leading run counts: the first non-skill text ends the scan, so a literal
/// `<skill>` pasted later stays user text. An unclosed leading block means the message
/// is not a skill expansion and is returned untouched.
fn split_pi_inline_skills(text: &str) -> (Vec<PiInlineSkill>, String) {
    let mut skills = Vec::new();
    let mut cursor = text.len() - python_strip_start(text).len();

    loop {
        let Some(opening) = pi_skill_token_regex().find_at(text, cursor) else {
            break;
        };
        if opening.start() != cursor || opening.as_str() == "</skill>" {
            break;
        }
        let mut depth = 1i32;
        let mut close_end: Option<usize> = None;
        for token in pi_skill_token_regex().find_iter(&text[opening.end()..]) {
            let start = opening.end() + token.start();
            let end = opening.end() + token.end();
            depth += if token.as_str() == "</skill>" { -1 } else { 1 };
            if depth == 0 {
                skills.push(PiInlineSkill {
                    input: parse_pi_skill_attributes(opening.as_str()),
                    body: python_strip(&text[opening.end()..start]).to_string(),
                });
                close_end = Some(end);
                break;
            }
        }
        let Some(close_end) = close_end else {
            return (Vec::new(), text.to_string());
        };
        let tail = &text[close_end..];
        cursor = close_end + tail.len() - python_strip_start(tail).len();
    }

    if skills.is_empty() {
        return (Vec::new(), text.to_string());
    }
    (skills, text[cursor..].to_string())
}

/// Represent one expanded inline skill as a synthetic `Skill` tool pair.
fn pi_inline_skill_message(
    entry: &Map<String, Value>,
    skill: &PiInlineSkill,
    ordinal: usize,
) -> Message {
    use sha1::{Digest, Sha1};
    let native_id = pi_native_entry_id(entry);
    let seed = format!("{}:{ordinal}", native_id.as_deref().unwrap_or("None"));
    let digest = Sha1::digest(seed.as_bytes());
    let tool_use_id: String = format!("{digest:x}").chars().take(12).collect();

    let mut message = new_message(0, "user", MessageType::UserMessage);
    message.timestamp = timestamp_of(entry);
    message.native_entry_id = native_id;
    message.tools = vec![
        Tool::Use(ToolUse {
            name: "Skill".to_string(),
            input: Value::Object(skill.input.clone()),
            id: Some(tool_use_id.clone()),
            native_tool_call_id: None,
            native_content_index: None,
        }),
        Tool::Result(ToolResult {
            name: None,
            tool_use_id: Some(tool_use_id),
            native_tool_call_id: None,
            is_error: false,
            content: Some(Value::String(skill.body.clone())),
            has_content: true,
        }),
    ];
    message
}

/// A Pi entry's stable native id, when it has one.
fn pi_native_entry_id(entry: &Map<String, Value>) -> Option<String> {
    entry
        .get("id")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

fn pi_normalize_tool_name(name: Option<&str>) -> String {
    crate::model::normalize_tool_name("pi", name)
}

/// Whether a Pi custom envelope is hidden duplicate plumbing.
fn is_hidden_pi_custom_entry(entry: &Map<String, Value>) -> bool {
    !is_joined_pi_user_agent_custom_message(entry)
        && (entry.get("customType").and_then(Value::as_str) == Some("subagent-notification")
            || entry.get("display") == Some(&Value::Bool(false))
            || entry_type(entry) == Some("custom_message"))
}

/// Whether Pi joined this user-agent response into the main context.
fn is_joined_pi_user_agent_custom_message(entry: &Map<String, Value>) -> bool {
    entry_type(entry) == Some("custom_message")
        && entry.get("customType").and_then(Value::as_str) == Some("pi-user-agents")
        && entry
            .get("details")
            .and_then(Value::as_object)
            .and_then(|details| details.get("mainContextState"))
            .and_then(Value::as_str)
            == Some("joined")
}

fn parse_pi_compaction_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Option<Message> {
    let summary = entry.get("summary")?.as_str()?;
    if !flags.show_user_messages() || python_strip(summary).is_empty() {
        return None;
    }
    let mut message = new_message(index, "user", MessageType::Compaction);
    message.text = summary.to_string();
    message.native_entry_id = pi_native_entry_id(entry);
    message.timestamp = timestamp_of(entry);
    Some(message)
}

/// Whether a response starts with Pi's structured preview.
///
/// The truncated form is measured in **UTF-16 code units**, not code points and not
/// bytes — a third counting unit, and it must not be unified with the others.
fn pi_response_matches_preview(response: &str, preview: Option<&str>) -> bool {
    let Some(preview) = preview else {
        return false;
    };
    let first_line = response
        .split('\n')
        .map(python_strip)
        .find(|line| !line.is_empty())
        .unwrap_or("");
    if first_line == preview {
        return true;
    }
    if !preview.ends_with('\u{2026}') {
        return false;
    }
    let utf16_length = preview.chars().map(char::len_utf16).sum::<usize>();
    let without_ellipsis = &preview[..preview.len() - '\u{2026}'.len_utf8()];
    utf16_length == 500 && first_line.starts_with(without_ellipsis)
}

fn pi_user_agent_prefix_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(&format!(
            r"^<user_agent(?:[{PYTHON_SPACE_CLASS}][^>\r\n]*)?>\r?\n<user_invocation>\r?\n"
        ))
        .expect("pi user agent prefix")
    })
}

fn pi_user_agent_ending_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        // `<duration_ms>` is OPTIONAL. The prior native port required it and joined
        // user-agent responses vanished from output through a green suite and a review.
        Regex::new(
            r"(?s)^(?P<before>.*)\r?\n</response>(?:\r?\n<duration_ms>\r?\n.*\r?\n</duration_ms>)?\r?\n</user_agent>$",
        )
        .expect("pi user agent ending")
    })
}

/// Extract the response from Pi's structured user-agent envelope.
///
/// Conservative by construction: one candidate wins outright, otherwise
/// `responsePreview` must resolve to exactly one, otherwise **nothing**. Ambiguity
/// yields no response rather than a guess.
fn extract_pi_user_agent_response(
    content: Option<&str>,
    task: &str,
    preview: Option<&str>,
) -> Option<String> {
    let stripped = python_strip(content?);
    let prefix = pi_user_agent_prefix_regex().find(stripped)?;
    let ending = pi_user_agent_ending_regex().captures(stripped)?;
    let before = ending.name("before")?.as_str();

    let boundary = Regex::new(&format!(
        r"\r?\n</user_invocation>\r?\n<task>\r?\n{}\r?\n</task>\r?\n<response>\r?\n",
        regex::escape(task)
    ))
    .ok()?;

    let search_from = prefix.end().min(before.len());
    let candidates: Vec<String> = boundary
        .find_iter(&before[search_from..])
        .map(|found| python_strip(&before[search_from + found.end()..]).to_string())
        .collect();

    if candidates.len() == 1 {
        return candidates.into_iter().next().filter(|value| !value.is_empty());
    }
    let mut matching = candidates
        .into_iter()
        .filter(|candidate| pi_response_matches_preview(candidate, preview));
    let first = matching.next()?;
    if matching.next().is_some() {
        return None;
    }
    (!first.is_empty()).then_some(first)
}

fn pi_user_agent_payload(entry: &Map<String, Value>) -> (Option<&Value>, Option<&Value>) {
    if entry_type(entry) != Some("custom") {
        return (entry.get("content"), entry.get("details"));
    }
    match entry.get("data").and_then(Value::as_object) {
        Some(data) => (data.get("content"), data.get("details")),
        None => (None, None),
    }
}

fn parse_pi_user_agent_entry(entry: &Map<String, Value>, index: usize) -> Option<Message> {
    let (content, details) = pi_user_agent_payload(entry);
    let details = details?.as_object()?;
    let task = details.get("task")?.as_str()?;
    let is_error = details.get("ok") == Some(&Value::Bool(false));
    if !is_error && python_strip(task).is_empty() {
        return None;
    }

    let agent_id = pi_native_entry_id(entry);
    let mut message = new_message(index, "agent", MessageType::Agent);
    message.agent_id = agent_id.clone();
    message.native_entry_id = agent_id;
    message.timestamp = timestamp_of(entry);
    message.subagent_task = Some(task.to_string());
    message.model = details.get("model").and_then(Value::as_str).map(str::to_string);
    message.custom_type = Some("pi-user-agents".to_string());
    message.inherited_context = match details.get("inheritedContext") {
        Some(Value::Bool(value)) => Some(*value),
        _ => None,
    };

    let error = details.get("error").and_then(Value::as_str);
    if is_error {
        let error = error.filter(|value| !value.is_empty())?;
        message.tools = vec![Tool::Result(ToolResult {
            name: Some("Bash".to_string()),
            tool_use_id: None,
            native_tool_call_id: None,
            is_error: true,
            content: Some(Value::String(error.to_string())),
            has_content: true,
        })];
        message.tools_always_visible = true;
        return Some(message);
    }

    message.text = extract_pi_user_agent_response(
        content.and_then(Value::as_str),
        task,
        details.get("responsePreview").and_then(Value::as_str),
    )?;
    Some(message)
}

fn parse_pi_subagent_record(entry: &Map<String, Value>, index: usize) -> Option<Message> {
    let data = entry.get("data")?.as_object()?;
    let field = |key: &str| {
        data.get(key)
            .and_then(Value::as_str)
            .filter(|value| !value.is_empty())
    };
    let (agent_id, subagent_type, description, status, result) = (
        field("id")?,
        field("type")?,
        field("description")?,
        field("status")?,
        field("result")?,
    );

    let mut message = new_message(index, "agent", MessageType::Agent);
    message.text = result.to_string();
    message.agent_id = Some(agent_id.to_string());
    message.native_entry_id = pi_native_entry_id(entry);
    message.timestamp = timestamp_of(entry);
    message.subagent_type = Some(subagent_type.to_string());
    message.subagent_task = Some(description.to_string());
    message.custom_type = Some("subagents:record".to_string());
    message.status = Some(status.to_string());
    Some(message)
}

fn parse_pi_custom_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Option<Message> {
    let custom_type = entry.get("customType")?.as_str()?;
    let special = match custom_type {
        "pi-user-agents" if flags.show_agents => parse_pi_user_agent_entry(entry, index),
        "subagents:record" if flags.show_agents => parse_pi_subagent_record(entry, index),
        _ => None,
    };
    if special.is_some() {
        return special;
    }
    if !flags.show_custom {
        return None;
    }
    let data = serde_json::to_string_pretty(entry.get("data").unwrap_or(&Value::Null)).ok()?;
    let mut message = new_message(index, "custom", MessageType::Custom);
    message.text = format!("```json\n{data}\n```");
    message.native_entry_id = pi_native_entry_id(entry);
    message.timestamp = timestamp_of(entry);
    message.custom_type = Some(custom_type.to_string());
    Some(message)
}

/// Parse a Pi `type=message` entry into its visible messages.
///
/// A user entry whose text starts with expanded inline-skill blocks splits into one
/// synthetic `Skill` message per block plus the typed remainder.
fn parse_pi_message_entry(
    entry: &Map<String, Value>,
    index: usize,
    flags: &ConversationFlags,
) -> Vec<Message> {
    let Some(message_data) = entry.get("message").and_then(Value::as_object) else {
        return Vec::new();
    };
    let role = message_data.get("role").and_then(Value::as_str).unwrap_or("");
    let native_entry_id = pi_native_entry_id(entry);

    if role == "toolResult" {
        if !tools_requested(flags) {
            return Vec::new();
        }
        let native_tool_call_id = message_data
            .get("toolCallId")
            .and_then(Value::as_str)
            .map(str::to_string);
        let mut message = new_message(index, "user", MessageType::UserMessage);
        message.timestamp = timestamp_of(entry);
        message.native_entry_id = native_entry_id;
        let is_error = message_data.get("isError").and_then(Value::as_bool) == Some(true)
            || message_data
                .get("details")
                .and_then(Value::as_object)
                .and_then(|details| details.get("error"))
                .is_some_and(crate::model::value_is_truthy);
        let name = message_data
            .get("toolName")
            .and_then(Value::as_str)
            .filter(|value| !value.is_empty())
            .map(|value| pi_normalize_tool_name(Some(value)));
        message.tools.push(Tool::Result(ToolResult {
            name,
            tool_use_id: native_tool_call_id.clone(),
            native_tool_call_id,
            is_error,
            content: message_data.get("content").cloned(),
            has_content: message_data.contains_key("content"),
        }));
        return vec![message];
    }

    if role != "user" && role != "assistant" {
        return Vec::new();
    }

    let mut message = new_message(
        index,
        role,
        if role == "user" { MessageType::UserMessage } else { MessageType::AssistantResponse },
    );
    message.timestamp = timestamp_of(entry);
    message.native_entry_id = native_entry_id;
    if role == "assistant" {
        message.model = message_data
            .get("model")
            .and_then(Value::as_str)
            .map(str::to_string);
    }

    let content_items = message_data.get("content").cloned().unwrap_or(Value::Null);
    let text_blocks = extract_text_blocks(&content_items);

    if role == "user" {
        let blocks = filter_hidden_user_text_blocks(text_blocks);
        let (skills, remainder) = split_pi_inline_skills(&blocks.join("\n\n"));
        if !remainder.is_empty() && flags.show_user_messages() {
            message.text = remainder;
        }
        let mut output: Vec<Message> = if tools_requested(flags) {
            skills
                .iter()
                .enumerate()
                .map(|(ordinal, skill)| pi_inline_skill_message(entry, skill, ordinal))
                .collect()
        } else {
            Vec::new()
        };
        output.push(message);
        return output;
    }

    if !text_blocks.is_empty() && flags.show_assistant_messages() {
        message.text = text_blocks.join("\n\n");
    }

    if let Some(items) = content_items.as_array() {
        let mut thinking_blocks: Vec<String> = Vec::new();
        for (native_content_index, item) in items.iter().enumerate() {
            let Some(item) = item.as_object() else { continue };
            match item.get("type").and_then(Value::as_str) {
                Some("thinking") if flags.show_thinking => {
                    if let Some(thinking) = item.get("thinking").and_then(Value::as_str)
                        && !python_strip(thinking).is_empty()
                    {
                        thinking_blocks.push(python_strip(thinking).to_string());
                    }
                }
                Some("toolCall") if tools_requested(flags) => {
                    let native_tool_call_id =
                        item.get("id").and_then(Value::as_str).map(str::to_string);
                    let name = pi_normalize_tool_name(item.get("name").and_then(Value::as_str));
                    let arguments = item.get("arguments").cloned().unwrap_or(Value::Null);
                    message.tools.push(Tool::Use(ToolUse {
                        input: crate::model::normalize_tool_input_keys("pi", &name, &arguments),
                        name,
                        id: native_tool_call_id.clone(),
                        native_tool_call_id,
                        native_content_index: Some(native_content_index.into()),
                    }));
                }
                _ => {}
            }
        }
        if !thinking_blocks.is_empty() {
            message.thinking = Some(thinking_blocks.join("\n\n"));
        }
    }

    vec![message]
}

/// Decode Pi-shaped JSONL entries into the shared message model.
///
/// Covers every entry type Python's Pi adapter handles: `message` (user, assistant and
/// toolResult, including inline-skill expansion), `compaction`, `custom` (including the
/// user-agent and subagent-record specialisations) and `custom_message`. Anything else
/// is ignored, exactly as Python ignores it.
pub fn parse_pi(entries: &[Map<String, Value>], flags: &ConversationFlags) -> Vec<Message> {
    let mut messages: Vec<Message> = Vec::new();
    let mut index = 1usize;

    for entry in entries {
        let kind = entry_type(entry);
        if matches!(kind, Some("custom" | "custom_message")) && is_hidden_pi_custom_entry(entry) {
            continue;
        }
        let parsed: Vec<Message> = match kind {
            Some("message") => parse_pi_message_entry(entry, index, flags),
            Some("compaction") => parse_pi_compaction_entry(entry, index, flags)
                .into_iter()
                .collect(),
            Some("custom") => parse_pi_custom_entry(entry, index, flags).into_iter().collect(),
            Some("custom_message") => {
                if is_joined_pi_user_agent_custom_message(entry) {
                    parse_pi_user_agent_entry(entry, index).into_iter().collect()
                } else {
                    Vec::new()
                }
            }
            _ => Vec::new(),
        };
        for mut message in parsed {
            if has_content(&message) {
                message.original_index = index.into();
                messages.push(message);
                index += 1;
            }
        }
    }
    messages
}
