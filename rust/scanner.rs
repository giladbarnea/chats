//! Candidate-gate scanners: byte-level probes over raw session files that
//! reject a file before anything reads, decodes, or renders it.
//!
//! Lifted unchanged from `python_extension.rs`. The gate is conservative by
//! construction: every uncertainty resolves toward accepting the file, because
//! a false accept costs a wasted parse and a false reject silently loses a
//! user's search result.

use std::io::Read;
use std::path::{Path, PathBuf};

use rayon::prelude::*;

pub const ASCII_CANDIDATE_SCAN_CHUNK_SIZE: usize = 128 * 1024;

// Darwin memmem wins on short needles but regresses long literal misses.
const LIBC_MEMMEM_MAX_NEEDLE_LENGTH: usize = 8;

#[cfg(unix)]
fn contains_exact(haystack: &[u8], needle: &[u8]) -> bool {
    // SAFETY: both pointers stay valid for the supplied slice lengths during this call.
    unsafe {
        !libc::memmem(
            haystack.as_ptr().cast(),
            haystack.len(),
            needle.as_ptr().cast(),
            needle.len(),
        )
        .is_null()
    }
}

#[cfg(not(unix))]
fn contains_exact(haystack: &[u8], needle: &[u8]) -> bool {
    haystack.windows(needle.len()).any(|window| window == needle)
}

struct CandidateMatcher {
    needle: Vec<u8>,
    shifts: [usize; 256],
    case_sensitive: bool,
}

impl CandidateMatcher {
    fn new(needle: &[u8], case_sensitive: bool) -> Self {
        let mut shifts = [needle.len(); 256];
        for (index, byte) in needle[..needle.len().saturating_sub(1)].iter().enumerate() {
            shifts[usize::from(*byte)] = needle.len() - index - 1;
        }
        Self {
            needle: needle.to_vec(),
            shifts,
            case_sensitive,
        }
    }

    fn normalized_haystack_byte(&self, byte: u8) -> u8 {
        if self.case_sensitive {
            byte
        } else {
            byte.to_ascii_lowercase()
        }
    }

    fn contains(&self, haystack: &[u8]) -> bool {
        if self.case_sensitive && self.needle.len() <= LIBC_MEMMEM_MAX_NEEDLE_LENGTH {
            return contains_exact(haystack, &self.needle);
        }
        self.contains_with(haystack.len(), |index| haystack[index])
    }

    fn contains_split(&self, first: &[u8], second: &[u8]) -> bool {
        self.contains_with(first.len() + second.len(), |index| {
            if index < first.len() {
                first[index]
            } else {
                second[index - first.len()]
            }
        })
    }

    fn contains_with(
        &self,
        haystack_length: usize,
        byte_at: impl Fn(usize) -> u8,
    ) -> bool {
        let mut start = 0;
        while start + self.needle.len() <= haystack_length {
            let mut index = self.needle.len();
            while index > 0 {
                index -= 1;
                let actual = self.normalized_haystack_byte(byte_at(start + index));
                if actual != self.needle[index] {
                    break;
                }
            }
            if index == 0
                && self.normalized_haystack_byte(byte_at(start)) == self.needle[0]
            {
                return true;
            }
            let last = self.normalized_haystack_byte(
                byte_at(start + self.needle.len() - 1),
            );
            start += self.shifts[usize::from(last)];
        }
        false
    }
}

const PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS: [char; 20] = [
    '\u{00df}', '\u{0130}', '\u{0131}', '\u{0149}', '\u{017f}', '\u{01f0}', '\u{1e96}',
    '\u{1e97}', '\u{1e98}', '\u{1e99}', '\u{1e9a}', '\u{1e9e}', '\u{212a}', '\u{fb00}',
    '\u{fb01}', '\u{fb02}', '\u{fb03}', '\u{fb04}', '\u{fb05}', '\u{fb06}',
];

/// Tracks `\uXXXX` escapes so a completed scalar that Python folds onto an ASCII
/// byte (e.g. U+212A KELVIN SIGN folding to "k") defers to semantic confirmation.
/// Structurally invalid escapes are ignored: their lines cannot parse, so they
/// carry no decodable content to protect.
#[derive(Default)]
struct EscapedRiskScalarTracker {
    progress: EscapedRiskScalarProgress,
}

#[derive(Default)]
enum EscapedRiskScalarProgress {
    #[default]
    DecodedText,
    AfterBackslash,
    UnicodeHexDigits { value: u16, count: u8 },
}

impl EscapedRiskScalarTracker {
    /// Returns false when a completed risk scalar demands semantic confirmation.
    fn scan(&mut self, chunk: &[u8]) -> bool {
        let mut cursor = 0;
        while cursor < chunk.len() {
            if matches!(
                self.progress,
                EscapedRiskScalarProgress::DecodedText
            ) {
                let Some(relative_backslash) = find_byte(&chunk[cursor..], b'\\') else {
                    return true;
                };
                cursor += relative_backslash;
            }
            if !self.feed(chunk[cursor]) {
                return false;
            }
            cursor += 1;
        }
        true
    }

    fn feed(&mut self, byte: u8) -> bool {
        match &mut self.progress {
            EscapedRiskScalarProgress::DecodedText => {
                if byte == b'\\' {
                    self.progress = EscapedRiskScalarProgress::AfterBackslash;
                }
                true
            }
            EscapedRiskScalarProgress::AfterBackslash => {
                self.progress = if byte == b'u' {
                    EscapedRiskScalarProgress::UnicodeHexDigits {
                        value: 0,
                        count: 0,
                    }
                } else {
                    EscapedRiskScalarProgress::DecodedText
                };
                true
            }
            EscapedRiskScalarProgress::UnicodeHexDigits { value, count } => {
                let Some(digit) = hex_digit(byte) else {
                    self.progress = EscapedRiskScalarProgress::DecodedText;
                    return true;
                };
                *value = *value * 16 + digit;
                *count += 1;
                if *count < 4 {
                    return true;
                }
                let folds_onto_ascii = completed_scalar_folds_onto_ascii(*value);
                self.progress = EscapedRiskScalarProgress::DecodedText;
                !folds_onto_ascii
            }
        }
    }
}

fn completed_scalar_folds_onto_ascii(value: u16) -> bool {
    let Some(scalar) = char::from_u32(u32::from(value)) else {
        return false;
    };
    PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS
        .binary_search(&scalar)
        .is_ok()
}

fn hex_digit(byte: u8) -> Option<u16> {
    match byte {
        b'0'..=b'9' => Some(u16::from(byte - b'0')),
        b'a'..=b'f' => Some(u16::from(byte - b'a' + 10)),
        b'A'..=b'F' => Some(u16::from(byte - b'A' + 10)),
        _ => None,
    }
}

#[cfg(unix)]
fn find_byte(haystack: &[u8], needle: u8) -> Option<usize> {
    // SAFETY: the pointer stays valid for the supplied slice length during this call.
    let pointer = unsafe {
        libc::memchr(
            haystack.as_ptr().cast(),
            i32::from(needle),
            haystack.len(),
        )
    };
    (!pointer.is_null()).then(|| pointer as usize - haystack.as_ptr() as usize)
}

#[cfg(not(unix))]
fn find_byte(haystack: &[u8], needle: u8) -> Option<usize> {
    haystack.iter().position(|byte| *byte == needle)
}

fn regex_hex_scalar(value: u8) -> String {
    format!("{value:04x}")
        .chars()
        .map(|character| match character {
            'a'..='f' => format!("[{character}{}]", character.to_ascii_uppercase()),
            _ => character.to_string(),
        })
        .collect()
}

fn logical_ascii_regex(needle: &[u8], case_sensitive: bool) -> regex::bytes::Regex {
    let pattern = needle
        .iter()
        .map(|byte| {
            let lowercase = byte.to_ascii_lowercase();
            let uppercase = byte.to_ascii_uppercase();
            let raw = if !case_sensitive && lowercase != uppercase {
                format!("[{}{}]", char::from(lowercase), char::from(uppercase))
            } else {
                regex::escape(&char::from(*byte).to_string())
            };
            let mut alternatives = vec![raw];
            if *byte == b'/' {
                alternatives.push(r"\\/".to_string());
            }
            alternatives.push(format!(r"\\u{}", regex_hex_scalar(*byte)));
            if !case_sensitive && lowercase != *byte {
                alternatives.push(format!(r"\\u{}", regex_hex_scalar(lowercase)));
            }
            if !case_sensitive && uppercase != *byte {
                alternatives.push(format!(r"\\u{}", regex_hex_scalar(uppercase)));
            }
            format!("(?:{})", alternatives.join("|"))
        })
        .collect::<String>();
    regex::bytes::Regex::new(&pattern).expect("generated logical ASCII regex")
}

fn validate_candidate_utf8_chunk(
    chunk: &[u8],
    incomplete_code_point: &mut Vec<u8>,
    case_sensitive: bool,
) -> bool {
    let decoded_text_is_safe = |text: &str| {
        case_sensitive
            || text.chars().all(|character| {
                character.is_ascii()
                    || PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS
                        .binary_search(&character)
                        .is_err()
            })
    };
    let mut cursor = 0;
    while !incomplete_code_point.is_empty() && cursor < chunk.len() {
        incomplete_code_point.push(chunk[cursor]);
        cursor += 1;
        match std::str::from_utf8(incomplete_code_point) {
            Ok(text) => {
                if !decoded_text_is_safe(text) {
                    return false;
                }
                incomplete_code_point.clear();
            }
            Err(error) if error.error_len().is_some() => return false,
            Err(_) => continue,
        }
    }
    if !incomplete_code_point.is_empty() {
        return true;
    }

    match std::str::from_utf8(&chunk[cursor..]) {
        Ok(text) => decoded_text_is_safe(text),
        Err(error) if error.error_len().is_some() => false,
        Err(error) => {
            let valid_length = error.valid_up_to();
            let valid_text = std::str::from_utf8(&chunk[cursor..cursor + valid_length])
                .expect("valid UTF-8 prefix");
            if !decoded_text_is_safe(valid_text) {
                return false;
            }
            incomplete_code_point.extend_from_slice(&chunk[cursor + valid_length..]);
            true
        }
    }
}

pub fn file_contains_ascii_impl(
    path: &Path,
    needle: &[u8],
    case_sensitive: bool,
    evidence_groups: &[Vec<Vec<u8>>],
) -> std::io::Result<bool> {
    if needle.is_empty() {
        return Ok(true);
    }

    let mut file = std::fs::File::open(path)?;
    let overlap_width = evidence_groups
        .iter()
        .flatten()
        .map(|evidence| evidence.len())
        .chain(std::iter::once(needle.len()))
        .max()
        .expect("needle supplies one candidate")
        - 1;
    let needle_matcher = CandidateMatcher::new(needle, case_sensitive);
    let evidence_matchers = evidence_groups
        .iter()
        .map(|group| {
            group
                .iter()
                .map(|evidence| CandidateMatcher::new(evidence, true))
                .collect::<Vec<_>>()
        })
        .collect::<Vec<_>>();
    let mut evidence_matches = evidence_groups
        .iter()
        .map(|group| vec![false; group.len()])
        .collect::<Vec<_>>();
    let mut previous = Vec::new();
    let mut incomplete_code_point = Vec::with_capacity(4);
    let mut block = vec![0; ASCII_CANDIDATE_SCAN_CHUNK_SIZE];

    loop {
        let read_size = file.read(&mut block)?;
        if read_size == 0 {
            break;
        }
        let chunk = &block[..read_size];
        if (!chunk.is_ascii() || !incomplete_code_point.is_empty())
            && !validate_candidate_utf8_chunk(
                chunk,
                &mut incomplete_code_point,
                case_sensitive,
            )
        {
            return Ok(true);
        }

        let boundary_prefix = &chunk[..overlap_width.min(chunk.len())];
        if needle_matcher.contains_split(&previous, boundary_prefix)
            || needle_matcher.contains(chunk)
        {
            return Ok(true);
        }
        for (group_index, group) in evidence_matchers.iter().enumerate() {
            for (evidence_index, evidence) in group.iter().enumerate() {
                if evidence.contains_split(&previous, boundary_prefix)
                    || evidence.contains(chunk)
                {
                    evidence_matches[group_index][evidence_index] = true;
                }
            }
        }
        if overlap_width == 0 {
            continue;
        }
        if chunk.len() >= overlap_width {
            previous.clear();
            previous.extend_from_slice(&chunk[chunk.len() - overlap_width..]);
            continue;
        }
        previous.extend_from_slice(chunk);
        let retained_start = previous.len().saturating_sub(overlap_width);
        previous.drain(..retained_start);
    }

    if !incomplete_code_point.is_empty() {
        return Ok(true);
    }
    Ok(evidence_matches.iter().any(|group| group.iter().all(|found| *found)))
}

pub struct LogicalJsonStringCandidateMatchers {
    logical_matcher: regex::bytes::Regex,
    evidence_matchers: Vec<Vec<regex::bytes::Regex>>,
    overlap_width: usize,
}

impl LogicalJsonStringCandidateMatchers {
    pub fn new(needle: &[u8], evidence_groups: &[Vec<Vec<u8>>]) -> Self {
        let normalized_needle = needle
            .iter()
            .map(|byte| byte.to_ascii_lowercase())
            .collect::<Vec<_>>();
        Self {
            logical_matcher: logical_ascii_regex(&normalized_needle, false),
            evidence_matchers: evidence_groups
                .iter()
                .map(|group| {
                    group
                        .iter()
                        .map(|evidence| logical_ascii_regex(evidence, true))
                        .collect()
                })
                .collect(),
            overlap_width: evidence_groups
                .iter()
                .flatten()
                .map(|evidence| evidence.len() * 6)
                .chain(std::iter::once(normalized_needle.len() * 6))
                .max()
                .expect("needle supplies one candidate")
                .saturating_sub(1),
        }
    }

    pub fn file_contains(
        &self,
        path: &Path,
        block: &mut [u8],
    ) -> std::io::Result<bool> {
        let mut evidence_matches = self
            .evidence_matchers
            .iter()
            .map(|group| vec![false; group.len()])
            .collect::<Vec<_>>();
        let mut previous = Vec::with_capacity(self.overlap_width);
        let mut boundary = Vec::with_capacity(self.overlap_width * 2);
        let mut incomplete_code_point = Vec::with_capacity(4);
        let mut escaped_risk_tracker = EscapedRiskScalarTracker::default();
        let mut file = std::fs::File::open(path)?;

        loop {
            let read_size = file.read(block)?;
            if read_size == 0 {
                break;
            }
            let chunk = &block[..read_size];
            let boundary_prefix = &chunk[..self.overlap_width.min(chunk.len())];
            boundary.clear();
            boundary.extend_from_slice(&previous);
            boundary.extend_from_slice(boundary_prefix);
            if self.logical_matcher.is_match(&boundary)
                || self.logical_matcher.is_match(chunk)
            {
                return Ok(true);
            }
            if (!chunk.is_ascii() || !incomplete_code_point.is_empty())
                && !validate_candidate_utf8_chunk(
                    chunk,
                    &mut incomplete_code_point,
                    false,
                )
            {
                return Ok(true);
            }
            if !escaped_risk_tracker.scan(chunk) {
                return Ok(true);
            }
            for (group_index, group) in self.evidence_matchers.iter().enumerate() {
                for (evidence_index, evidence) in group.iter().enumerate() {
                    if evidence.is_match(&boundary) || evidence.is_match(chunk) {
                        evidence_matches[group_index][evidence_index] = true;
                    }
                }
            }
            if evidence_matches
                .iter()
                .any(|group| group.iter().all(|found| *found))
            {
                return Ok(true);
            }
            if self.overlap_width == 0 {
                continue;
            }
            if chunk.len() >= self.overlap_width {
                previous.clear();
                previous.extend_from_slice(
                    &chunk[chunk.len() - self.overlap_width..],
                );
                continue;
            }
            previous.extend_from_slice(chunk);
            let retained_start = previous.len().saturating_sub(self.overlap_width);
            previous.drain(..retained_start);
        }
        Ok(!incomplete_code_point.is_empty())
    }
}

pub fn file_contains_ascii_json_strings_impl(
    path: &Path,
    needle: &[u8],
    evidence_groups: &[Vec<Vec<u8>>],
) -> std::io::Result<bool> {
    if needle.is_empty() {
        return Ok(true);
    }
    LogicalJsonStringCandidateMatchers::new(needle, evidence_groups).file_contains(
        path,
        &mut vec![0; ASCII_CANDIDATE_SCAN_CHUNK_SIZE],
    )
}

/// Scan one ordered batch in parallel, returning decisions in input order.
///
/// Order is load-bearing: confirmation runs serially over these decisions and
/// that is what preserves newest-first streaming.
pub fn files_contain_ascii_json_strings_impl(
    paths: Vec<PathBuf>,
    needle: &[u8],
    pi_sessions: Vec<bool>,
) -> Vec<bool> {
    if needle.is_empty() {
        return vec![true; paths.len()];
    }
    let matchers = [
        LogicalJsonStringCandidateMatchers::new(needle, &[]),
        LogicalJsonStringCandidateMatchers::new(
            needle,
            &[vec![b"\"pi-user-agents\"".to_vec()]],
        ),
    ];
    paths
        .into_par_iter()
        .zip(pi_sessions)
        .map_init(
            || vec![0; ASCII_CANDIDATE_SCAN_CHUNK_SIZE],
            |block, (path, pi_session)| {
                matchers[usize::from(pi_session)]
                    .file_contains(&path, block)
                    .unwrap_or(true)
            },
        )
        .collect()
}
