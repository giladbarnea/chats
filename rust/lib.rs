use std::borrow::Cow;
use std::collections::HashMap;
use std::ffi::{OsStr, OsString};
use std::io::{ErrorKind, Read, Seek, SeekFrom};
use std::path::{Component, Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

#[cfg(unix)]
use std::os::unix::ffi::{OsStrExt, OsStringExt};
#[cfg(unix)]
use std::os::unix::fs::MetadataExt;
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3::types::PyBytes;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Provider {
    Codex,
    Pi,
    Claude,
}

impl Provider {
    fn as_str(self) -> &'static str {
        match self {
            Self::Codex => "codex",
            Self::Pi => "pi",
            Self::Claude => "claude",
        }
    }
}

fn provider_for_canonical_path(
    canonical_path: &Path,
    canonical_roots: &[(Provider, PathBuf)],
) -> Option<Provider> {
    canonical_roots
        .iter()
        .find_map(|(provider, root)| canonical_path.starts_with(root).then_some(*provider))
}

const MAX_DANGLING_SYMLINKS: usize = 40;

fn permits_strict_false_resolution(error: &std::io::Error) -> bool {
    let missing_path = matches!(error.kind(), ErrorKind::NotFound | ErrorKind::NotADirectory);
    #[cfg(unix)]
    let symlink_loop = error.raw_os_error() == Some(libc::ELOOP);
    #[cfg(not(unix))]
    let symlink_loop = false;
    missing_path || symlink_loop
}

fn resolve_missing_tail(
    mut canonical_path: PathBuf,
    missing_components: &[OsString],
    remaining_symlinks: usize,
) -> Option<PathBuf> {
    for component in missing_components.iter().rev() {
        if component == OsStr::new(".") {
            continue;
        }
        if component == OsStr::new("..") {
            canonical_path.pop();
            continue;
        }

        canonical_path.push(component);
        match canonical_path.canonicalize() {
            Ok(resolved_path) => canonical_path = resolved_path,
            Err(error) if permits_strict_false_resolution(&error) => {
                let Ok(metadata) = std::fs::symlink_metadata(&canonical_path) else {
                    continue;
                };
                if !metadata.file_type().is_symlink() {
                    continue;
                }
                if remaining_symlinks == 0 {
                    return Some(canonical_path);
                }
                let link_target = std::fs::read_link(&canonical_path).ok()?;
                let link_parent = canonical_path.parent()?;
                let target_path = if link_target.is_absolute() {
                    link_target
                } else {
                    link_parent.join(link_target)
                };
                canonical_path = canonicalize_allow_missing_with_limit(
                    &target_path,
                    remaining_symlinks - 1,
                )?;
            }
            Err(_) => return None,
        }
    }
    Some(canonical_path)
}

fn canonicalize_allow_missing_with_limit(
    path: &Path,
    remaining_symlinks: usize,
) -> Option<PathBuf> {
    let mut current = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir().ok()?.join(path)
    };
    let mut missing_components = Vec::new();

    loop {
        match current.canonicalize() {
            Ok(canonical_path) => {
                return resolve_missing_tail(
                    canonical_path,
                    &missing_components,
                    remaining_symlinks,
                );
            }
            Err(error) if permits_strict_false_resolution(&error) => {
                let parent = current.parent()?;
                let missing_component = current.strip_prefix(parent).ok()?;
                missing_components.push(missing_component.as_os_str().to_os_string());
                current = parent.to_path_buf();
            }
            Err(_) => return None,
        }
    }
}

fn canonicalize_allow_missing(path: &Path) -> Option<PathBuf> {
    canonicalize_allow_missing_with_limit(path, MAX_DANGLING_SYMLINKS)
}

type CanonicalProviderRoots = Arc<[(Provider, PathBuf)]>;

static PROVIDER_ROOTS_BY_HOME: OnceLock<Mutex<HashMap<OsString, CanonicalProviderRoots>>> =
    OnceLock::new();

fn canonical_provider_roots(home: &Path) -> CanonicalProviderRoots {
    let cache = PROVIDER_ROOTS_BY_HOME.get_or_init(|| Mutex::new(HashMap::new()));
    let mut roots_by_home = cache.lock().expect("provider root cache mutex poisoned");
    if let Some(roots) = roots_by_home.get(home.as_os_str()) {
        return Arc::clone(roots);
    }

    let provider_roots = [
        (Provider::Codex, home.join(".codex").join("sessions")),
        (Provider::Pi, home.join(".pi")),
        (Provider::Claude, home.join(".claude").join("projects")),
    ];
    let canonical_roots = provider_roots
        .into_iter()
        .filter_map(|(provider, root)| {
            canonicalize_allow_missing(&root).map(|root| (provider, root))
        })
        .collect::<Vec<_>>()
        .into();
    roots_by_home.insert(home.as_os_str().to_os_string(), Arc::clone(&canonical_roots));
    canonical_roots
}

fn classify_native_session_path_impl(path: &Path, home: &Path) -> Option<Provider> {
    let canonical_path = canonicalize_allow_missing(path)?;
    let canonical_roots = canonical_provider_roots(home);
    provider_for_canonical_path(&canonical_path, canonical_roots.as_ref())
}

fn filename_ends_with(path: &Path, suffix: &[u8]) -> bool {
    path.file_name()
        .map(os_string_bytes)
        .is_some_and(|filename| filename.ends_with(suffix))
}

fn filename_starts_with(path: &Path, prefix: &[u8]) -> bool {
    path.file_name()
        .map(os_string_bytes)
        .is_some_and(|filename| filename.starts_with(prefix))
}

#[cfg(unix)]
fn os_string_bytes(value: &OsStr) -> &[u8] {
    value.as_bytes()
}

#[cfg(not(unix))]
fn os_string_bytes(value: &OsStr) -> &[u8] {
    value.to_str().unwrap_or_default().as_bytes()
}

fn python_filesystem_codepoints(value: &OsStr) -> Vec<u32> {
    let mut bytes = os_string_bytes(value);
    let mut codepoints = Vec::new();
    while !bytes.is_empty() {
        match std::str::from_utf8(bytes) {
            Ok(text) => {
                codepoints.extend(text.chars().map(u32::from));
                break;
            }
            Err(error) => {
                let valid_length = error.valid_up_to();
                let valid_text = std::str::from_utf8(&bytes[..valid_length])
                    .expect("valid UTF-8 prefix");
                codepoints.extend(valid_text.chars().map(u32::from));
                let invalid_length = error
                    .error_len()
                    .unwrap_or(bytes.len() - valid_length);
                codepoints.extend(
                    bytes[valid_length..valid_length + invalid_length]
                        .iter()
                        .map(|byte| 0xdc00 + u32::from(*byte)),
                );
                bytes = &bytes[valid_length + invalid_length..];
            }
        }
    }
    codepoints
}

fn python_filesystem_component_codepoints(component: Component<'_>) -> Vec<u32> {
    match component {
        Component::Prefix(prefix) => python_filesystem_codepoints(prefix.as_os_str()),
        Component::RootDir => {
            python_filesystem_codepoints(OsStr::new(std::path::MAIN_SEPARATOR_STR))
        }
        Component::CurDir => vec![u32::from('.')],
        Component::ParentDir => vec![u32::from('.'), u32::from('.')],
        Component::Normal(value) => python_filesystem_codepoints(value),
    }
}

fn python_filesystem_path_key(path: &Path) -> Vec<Vec<u32>> {
    path.components()
        .map(python_filesystem_component_codepoints)
        .collect()
}

fn read_recursive_jsonl_paths(root: &Path, paths: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if filename_ends_with(&path, b".jsonl") {
            paths.push(path.clone());
        }
        if entry.file_type().is_ok_and(|file_type| file_type.is_dir()) {
            read_recursive_jsonl_paths(&path, paths);
        }
    }
}

fn read_claude_jsonl_paths(root: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let Ok(projects) = std::fs::read_dir(root) else {
        return paths;
    };
    for project in projects.flatten() {
        let project_path = project.path();
        if !project_path.is_dir() {
            continue;
        }
        let Ok(children) = std::fs::read_dir(&project_path) else {
            continue;
        };
        for child in children.flatten() {
            let child_path = child.path();
            if filename_ends_with(&child_path, b".jsonl") {
                paths.push(child_path.clone());
            }
            if !child_path.is_dir() {
                continue;
            }
            let Ok(agents) = std::fs::read_dir(child_path.join("subagents")) else {
                continue;
            };
            for agent in agents.flatten() {
                let agent_path = agent.path();
                if filename_starts_with(&agent_path, b"agent-")
                    && filename_ends_with(&agent_path, b".jsonl")
                {
                    paths.push(agent_path);
                }
            }
        }
    }
    paths.sort_by_cached_key(|path| python_filesystem_path_key(path));
    paths
}

fn read_recursive_provider_paths(root: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    read_recursive_jsonl_paths(root, &mut paths);
    paths.sort_by_cached_key(|path| python_filesystem_path_key(path));
    paths
}

#[cfg(unix)]
fn stat_mtime(path: &Path) -> f64 {
    let Ok(metadata) = std::fs::metadata(path) else {
        return f64::NEG_INFINITY;
    };
    metadata.mtime() as f64 + metadata.mtime_nsec() as f64 / 1_000_000_000.0
}

#[cfg(not(unix))]
fn stat_mtime(path: &Path) -> f64 {
    use std::time::UNIX_EPOCH;

    let Ok(modified) = std::fs::metadata(path).and_then(|metadata| metadata.modified()) else {
        return f64::NEG_INFINITY;
    };
    match modified.duration_since(UNIX_EPOCH) {
        Ok(duration) => duration.as_secs_f64(),
        Err(error) => -error.duration().as_secs_f64(),
    }
}

fn discover_session_files_impl(
    home: &Path,
    include_sidechains: bool,
) -> Vec<(PathBuf, Option<Provider>, f64)> {
    let groups = [
        read_claude_jsonl_paths(&home.join(".claude").join("projects")),
        read_recursive_provider_paths(&home.join(".codex").join("sessions")),
        read_recursive_provider_paths(
            &home.join(".pi").join("agent").join("sessions"),
        ),
    ];
    groups
        .into_iter()
        .flatten()
        .filter_map(|path| {
            let provider = classify_native_session_path_impl(&path, home);
            let excluded_sidechain = !include_sidechains
                && provider == Some(Provider::Claude)
                && filename_starts_with(&path, b"agent-");
            (!excluded_sidechain).then(|| {
                let mtime = stat_mtime(&path);
                (path, provider, mtime)
            })
        })
        .collect()
}

const JSONL_SCAN_CHUNK_SIZE: usize = 4096;

enum TimestampLine {
    Found(Py<PyAny>),
    Continue,
    Abort,
}

fn trim_python_byte_whitespace(line: &[u8]) -> &[u8] {
    let start = line
        .iter()
        .position(|byte| !matches!(*byte, b'\t' | b'\n' | 0x0b | 0x0c | b'\r' | b' '))
        .unwrap_or(line.len());
    let end = line
        .iter()
        .rposition(|byte| !matches!(*byte, b'\t' | b'\n' | 0x0b | 0x0c | b'\r' | b' '))
        .map(|index| index + 1)
        .unwrap_or(start);
    &line[start..end]
}

fn timestamp_from_jsonl_line(
    py: Python<'_>,
    line: &[u8],
    line_timestamp: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> TimestampLine {
    let line = trim_python_byte_whitespace(line);
    if line.is_empty() {
        return TimestampLine::Continue;
    }
    let Ok(decoded_line) = std::str::from_utf8(line) else {
        return TimestampLine::Continue;
    };
    let timestamp = match line_timestamp.call1((decoded_line,)) {
        Ok(timestamp) => timestamp,
        Err(error) if error.is_instance(py, json_decode_error) => {
            return TimestampLine::Continue;
        }
        Err(_) => return TimestampLine::Abort,
    };
    if timestamp.is_none() {
        return TimestampLine::Continue;
    }
    TimestampLine::Found(timestamp.unbind())
}

fn timestamp_from_fragmented_line(
    py: Python<'_>,
    earlier_fragment: &[u8],
    later_fragments: &[Vec<u8>],
    line_timestamp: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> TimestampLine {
    let line = if later_fragments.is_empty() {
        Cow::Borrowed(earlier_fragment)
    } else {
        let line_length =
            earlier_fragment.len() + later_fragments.iter().map(Vec::len).sum::<usize>();
        let mut line = Vec::with_capacity(line_length);
        line.extend_from_slice(earlier_fragment);
        for fragment in later_fragments.iter().rev() {
            line.extend_from_slice(fragment);
        }
        Cow::Owned(line)
    };
    timestamp_from_jsonl_line(py, &line, line_timestamp, json_decode_error)
}

fn find_last_jsonl_timestamp_impl(
    py: Python<'_>,
    path: &Path,
    line_timestamp: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> Option<Py<PyAny>> {
    let mut file = std::fs::File::open(path).ok()?;
    let mut remaining_bytes = file.seek(SeekFrom::End(0)).ok()?;
    let mut later_fragments: Vec<Vec<u8>> = Vec::new();

    while remaining_bytes > 0 {
        let read_size = JSONL_SCAN_CHUNK_SIZE.min(remaining_bytes as usize);
        remaining_bytes -= read_size as u64;
        file.seek(SeekFrom::Start(remaining_bytes)).ok()?;
        let mut block = vec![0; read_size];
        file.read_exact(&mut block).ok()?;

        let mut line_end = block.len();
        while let Some(newline_index) = block[..line_end]
            .iter()
            .rposition(|byte| *byte == b'\n')
        {
            match timestamp_from_fragmented_line(
                py,
                &block[newline_index + 1..line_end],
                &later_fragments,
                line_timestamp,
                json_decode_error,
            ) {
                TimestampLine::Found(timestamp) => return Some(timestamp),
                TimestampLine::Abort => return None,
                TimestampLine::Continue => {}
            }
            later_fragments.clear();
            line_end = newline_index;
        }

        if line_end > 0 {
            later_fragments.push(block[..line_end].to_vec());
        }
    }

    match timestamp_from_fragmented_line(
        py,
        &[],
        &later_fragments,
        line_timestamp,
        json_decode_error,
    ) {
        TimestampLine::Found(timestamp) => Some(timestamp),
        TimestampLine::Continue | TimestampLine::Abort => None,
    }
}

const ASCII_CANDIDATE_SCAN_CHUNK_SIZE: usize = 1024 * 1024;

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

#[derive(Clone, Copy)]
enum JsonEscapeState {
    Plain,
    AfterBackslash,
    Unicode { value: u16, digits: u8 },
    ExpectLowBackslash { high: u16 },
    ExpectLowU { high: u16 },
    LowUnicode { high: u16, value: u16, digits: u8 },
}

struct JsonEscapeValidator {
    state: JsonEscapeState,
}

impl JsonEscapeValidator {
    fn new() -> Self {
        Self {
            state: JsonEscapeState::Plain,
        }
    }

    fn push(&mut self, byte: u8) -> bool {
        match self.state {
            JsonEscapeState::Plain => {
                if byte == b'\\' {
                    self.state = JsonEscapeState::AfterBackslash;
                }
                true
            }
            JsonEscapeState::AfterBackslash => {
                self.state = JsonEscapeState::Plain;
                match byte {
                    b'"' | b'\\' | b'/' | b'b' | b'f' | b'n' | b'r' | b't' => true,
                    b'u' => {
                        self.state = JsonEscapeState::Unicode {
                            value: 0,
                            digits: 0,
                        };
                        true
                    }
                    _ => false,
                }
            }
            JsonEscapeState::Unicode { value, digits } => {
                let Some(digit) = hex_digit(byte) else {
                    return false;
                };
                let value = value * 16 + digit;
                let digits = digits + 1;
                if digits < 4 {
                    self.state = JsonEscapeState::Unicode { value, digits };
                    return true;
                }
                self.state = JsonEscapeState::Plain;
                if (0xd800..=0xdbff).contains(&value) {
                    self.state = JsonEscapeState::ExpectLowBackslash { high: value };
                    return true;
                }
                if (0xdc00..=0xdfff).contains(&value) {
                    return false;
                }
                let character = char::from_u32(u32::from(value))
                    .expect("non-surrogate BMP scalar");
                PYTHON_CASE_INSENSITIVE_ASCII_RISK_CHARACTERS
                    .binary_search(&character)
                    .is_err()
            }
            JsonEscapeState::ExpectLowBackslash { high } => {
                if byte != b'\\' {
                    return false;
                }
                self.state = JsonEscapeState::ExpectLowU { high };
                true
            }
            JsonEscapeState::ExpectLowU { high } => {
                if byte != b'u' {
                    return false;
                }
                self.state = JsonEscapeState::LowUnicode {
                    high,
                    value: 0,
                    digits: 0,
                };
                true
            }
            JsonEscapeState::LowUnicode {
                high,
                value,
                digits,
            } => {
                let Some(digit) = hex_digit(byte) else {
                    return false;
                };
                let value = value * 16 + digit;
                let digits = digits + 1;
                if digits < 4 {
                    self.state = JsonEscapeState::LowUnicode {
                        high,
                        value,
                        digits,
                    };
                    return true;
                }
                if !(0xdc00..=0xdfff).contains(&value) {
                    return false;
                }
                self.state = JsonEscapeState::Plain;
                true
            }
        }
    }

    fn is_incomplete(&self) -> bool {
        !matches!(self.state, JsonEscapeState::Plain)
    }
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

fn validate_json_escapes_chunk(
    chunk: &[u8],
    validator: &mut JsonEscapeValidator,
) -> bool {
    let mut cursor = 0;
    while cursor < chunk.len() {
        if matches!(validator.state, JsonEscapeState::Plain) {
            let Some(relative_backslash) = find_byte(&chunk[cursor..], b'\\') else {
                return true;
            };
            cursor += relative_backslash;
        }
        if !validator.push(chunk[cursor]) {
            return false;
        }
        cursor += 1;
    }
    true
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

fn file_contains_ascii_impl(
    path: &Path,
    needle: &[u8],
    case_sensitive: bool,
    evidence_groups: &[Vec<PyBackedBytes>],
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

fn file_contains_ascii_json_strings_impl(
    path: &Path,
    needle: &[u8],
    evidence_groups: &[Vec<PyBackedBytes>],
) -> std::io::Result<bool> {
    if needle.is_empty() {
        return Ok(true);
    }

    let normalized_needle = needle
        .iter()
        .map(|byte| byte.to_ascii_lowercase())
        .collect::<Vec<_>>();
    let logical_matcher = logical_ascii_regex(&normalized_needle, false);
    let evidence_matchers = evidence_groups
        .iter()
        .map(|group| {
            group
                .iter()
                .map(|evidence| logical_ascii_regex(evidence, true))
                .collect::<Vec<_>>()
        })
        .collect::<Vec<_>>();
    let mut evidence_matches = evidence_groups
        .iter()
        .map(|group| vec![false; group.len()])
        .collect::<Vec<_>>();
    let overlap_width = evidence_groups
        .iter()
        .flatten()
        .map(|evidence| evidence.len() * 6)
        .chain(std::iter::once(normalized_needle.len() * 6))
        .max()
        .expect("needle supplies one candidate")
        .saturating_sub(1);
    let mut previous = Vec::new();
    let mut incomplete_code_point = Vec::with_capacity(4);
    let mut escape_validator = JsonEscapeValidator::new();
    let mut block = vec![0; ASCII_CANDIDATE_SCAN_CHUNK_SIZE];
    let mut file = std::fs::File::open(path)?;

    loop {
        let read_size = file.read(&mut block)?;
        if read_size == 0 {
            break;
        }
        let chunk = &block[..read_size];
        let boundary_prefix = &chunk[..overlap_width.min(chunk.len())];
        let mut boundary = Vec::with_capacity(previous.len() + boundary_prefix.len());
        boundary.extend_from_slice(&previous);
        boundary.extend_from_slice(boundary_prefix);
        if logical_matcher.is_match(&boundary) || logical_matcher.is_match(chunk) {
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
        if !validate_json_escapes_chunk(chunk, &mut escape_validator) {
            return Ok(true);
        }
        for (group_index, group) in evidence_matchers.iter().enumerate() {
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

    Ok(
        !incomplete_code_point.is_empty()
            || escape_validator.is_incomplete()
    )
}

const RESOLUTION_FACET_MARKERS: [&str; 4] = [
    "\"summary\"",
    "\"custom-title\"",
    "\"session_info\"",
    "\"thread_name_updated\"",
];

fn accumulate_resolution_line(
    py: Python<'_>,
    line: &[u8],
    line_facets: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
    latest_title: &mut Option<Py<PyAny>>,
    summaries: &mut Vec<Py<PyAny>>,
) -> PyResult<()> {
    let decoded_line = match std::str::from_utf8(line) {
        Ok(decoded_line) => decoded_line,
        Err(_) => {
            PyBytes::new(py, line).call_method1("decode", ("utf-8",))?;
            unreachable!("invalid UTF-8 decode must raise")
        }
    };
    if !RESOLUTION_FACET_MARKERS
        .iter()
        .any(|marker| decoded_line.contains(marker))
    {
        return Ok(());
    }

    let facets = match line_facets.call1((decoded_line,)) {
        Ok(facets) => facets,
        Err(error) if error.is_instance(py, json_decode_error) => return Ok(()),
        Err(error) => return Err(error),
    };
    let (title, summary): (Option<Py<PyAny>>, Option<Py<PyAny>>) = facets.extract()?;
    if title.is_some() {
        *latest_title = title;
    }
    if let Some(summary) = summary {
        summaries.push(summary);
    }
    Ok(())
}

fn scan_resolution_facets_impl(
    py: Python<'_>,
    path: &Path,
    line_facets: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> PyResult<(Option<Py<PyAny>>, Vec<Py<PyAny>>)> {
    let mut file = match std::fs::File::open(path) {
        Ok(file) => file,
        Err(_) => return Ok((None, Vec::new())),
    };
    let mut latest_title = None;
    let mut summaries = Vec::new();
    let mut line = Vec::new();
    let mut block = [0; JSONL_SCAN_CHUNK_SIZE];
    let mut skip_leading_line_feed = false;

    loop {
        let read_size = match file.read(&mut block) {
            Ok(read_size) => read_size,
            Err(_) => return Ok((None, Vec::new())),
        };
        if read_size == 0 {
            break;
        }

        let mut cursor = usize::from(skip_leading_line_feed && block[0] == b'\n');
        skip_leading_line_feed = false;
        while cursor < read_size {
            let Some(relative_delimiter) = block[cursor..read_size]
                .iter()
                .position(|byte| matches!(*byte, b'\r' | b'\n'))
            else {
                line.extend_from_slice(&block[cursor..read_size]);
                break;
            };
            let delimiter = cursor + relative_delimiter;
            line.extend_from_slice(&block[cursor..delimiter]);
            accumulate_resolution_line(
                py,
                &line,
                line_facets,
                json_decode_error,
                &mut latest_title,
                &mut summaries,
            )?;
            line.clear();

            cursor = delimiter + 1;
            if block[delimiter] != b'\r' {
                continue;
            }
            if cursor == read_size {
                skip_leading_line_feed = true;
                continue;
            }
            if block[cursor] == b'\n' {
                cursor += 1;
            }
        }
    }

    if !line.is_empty() {
        accumulate_resolution_line(
            py,
            &line,
            line_facets,
            json_decode_error,
            &mut latest_title,
            &mut summaries,
        )?;
    }
    Ok((latest_title, summaries))
}

#[pyfunction]
fn file_contains_ascii(
    path: PyBackedBytes,
    needle: PyBackedBytes,
    case_sensitive: bool,
    evidence_groups: Vec<Vec<PyBackedBytes>>,
) -> PyResult<bool> {
    #[cfg(unix)]
    let path = PathBuf::from(OsString::from_vec(path.as_ref().to_vec()));
    #[cfg(not(unix))]
    let path = PathBuf::from(String::from_utf8_lossy(path.as_ref()).into_owned());

    Ok(file_contains_ascii_impl(
        &path,
        needle.as_ref(),
        case_sensitive,
        &evidence_groups,
    )?)
}

#[pyfunction]
fn file_contains_ascii_json_strings(
    path: PyBackedBytes,
    needle: PyBackedBytes,
    evidence_groups: Vec<Vec<PyBackedBytes>>,
) -> PyResult<bool> {
    #[cfg(unix)]
    let path = PathBuf::from(OsString::from_vec(path.as_ref().to_vec()));
    #[cfg(not(unix))]
    let path = PathBuf::from(String::from_utf8_lossy(path.as_ref()).into_owned());

    Ok(file_contains_ascii_json_strings_impl(
        &path,
        needle.as_ref(),
        &evidence_groups,
    )?)
}

#[pyfunction]
fn classify_native_session_path(path: &str, home: &str) -> Option<&'static str> {
    classify_native_session_path_impl(Path::new(path), Path::new(home)).map(Provider::as_str)
}

#[pyfunction]
fn find_last_jsonl_timestamp(
    py: Python<'_>,
    path: &str,
    line_timestamp: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> Option<Py<PyAny>> {
    find_last_jsonl_timestamp_impl(
        py,
        Path::new(path),
        line_timestamp,
        json_decode_error,
    )
}

#[pyfunction]
fn scan_resolution_facets(
    py: Python<'_>,
    path: &Bound<'_, PyBytes>,
    line_facets: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> PyResult<(Option<Py<PyAny>>, Vec<Py<PyAny>>)> {
    #[cfg(unix)]
    let path = PathBuf::from(OsString::from_vec(path.as_bytes().to_vec()));
    #[cfg(not(unix))]
    let path = PathBuf::from(String::from_utf8_lossy(path.as_bytes()).into_owned());

    scan_resolution_facets_impl(py, &path, line_facets, json_decode_error)
}

#[pyfunction]
fn discover_session_files(
    py: Python<'_>,
    home: &Bound<'_, PyBytes>,
    include_sidechains: bool,
) -> Vec<(Py<PyBytes>, Option<&'static str>, f64)> {
    #[cfg(unix)]
    let home = PathBuf::from(OsString::from_vec(home.as_bytes().to_vec()));
    #[cfg(not(unix))]
    let home = PathBuf::from(String::from_utf8_lossy(home.as_bytes()).into_owned());

    discover_session_files_impl(&home, include_sidechains)
        .into_iter()
        .map(|(path, provider, mtime)| {
            let path = PyBytes::new(py, os_string_bytes(path.as_os_str())).unbind();
            (path, provider.map(Provider::as_str), mtime)
        })
        .collect()
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(file_contains_ascii, module)?)?;
    module.add_function(wrap_pyfunction!(file_contains_ascii_json_strings, module)?)?;
    module.add_function(wrap_pyfunction!(classify_native_session_path, module)?)?;
    module.add_function(wrap_pyfunction!(find_last_jsonl_timestamp, module)?)?;
    module.add_function(wrap_pyfunction!(scan_resolution_facets, module)?)?;
    module.add_function(wrap_pyfunction!(discover_session_files, module)?)
}

#[cfg(test)]
mod tests {
    use super::{
        classify_native_session_path_impl, provider_for_canonical_path,
        python_filesystem_path_key, Provider,
    };
    use std::fs;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    static TEMPORARY_DIRECTORY_ID: AtomicU64 = AtomicU64::new(0);

    struct TemporaryDirectory(PathBuf);

    impl TemporaryDirectory {
        fn new() -> Self {
            let identifier = TEMPORARY_DIRECTORY_ID.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "chats-native-test-{}-{identifier}",
                std::process::id()
            ));
            fs::create_dir_all(&path).expect("create temporary directory");
            Self(path)
        }
    }

    impl Drop for TemporaryDirectory {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).expect("remove temporary directory");
        }
    }

    #[cfg(unix)]
    #[test]
    fn filesystem_path_order_matches_python_surrogate_escape_order() {
        use std::cmp::Ordering;
        use std::ffi::OsString;
        use std::os::unix::ffi::OsStringExt;

        let unicode_path = PathBuf::from("é.jsonl");
        let surrogate_escaped_path = PathBuf::from(OsString::from_vec(b"\x80.jsonl".to_vec()));

        assert_eq!(
            python_filesystem_path_key(&surrogate_escaped_path)
                .cmp(&python_filesystem_path_key(&unicode_path)),
            Ordering::Greater,
            "Python orders U+00E9 before the surrogate-escaped U+DC80.",
        );
        assert_eq!(
            python_filesystem_path_key(Path::new("/root/agents/z.jsonl")).cmp(
                &python_filesystem_path_key(Path::new("/root/agents-plugins/a.jsonl")),
            ),
            Ordering::Less,
            "Python compares path components before later separators.",
        );
    }

    #[test]
    fn canonical_containment_uses_provider_precedence() {
        let roots = [
            (Provider::Codex, PathBuf::from("/native/shared")),
            (Provider::Pi, PathBuf::from("/native/shared")),
            (Provider::Claude, PathBuf::from("/native/claude")),
        ];

        assert_eq!(
            provider_for_canonical_path(Path::new("/native/shared/session.jsonl"), &roots),
            Some(Provider::Codex),
            "Expected the first containing provider root to win."
        );
        assert_eq!(
            provider_for_canonical_path(Path::new("/native/shared-sibling/session.jsonl"), &roots),
            None,
            "Expected path-component containment not to match a sibling prefix."
        );
    }

    #[cfg(unix)]
    #[test]
    fn exhausted_symlink_replay_preserves_the_unresolved_path() {
        use std::ffi::OsString;
        use std::os::unix::fs::symlink;

        let temporary_directory = TemporaryDirectory::new();
        let canonical_root = temporary_directory
            .0
            .canonicalize()
            .expect("canonical temporary directory");
        symlink(
            temporary_directory.0.join("missing-target"),
            temporary_directory.0.join("link"),
        )
        .expect("create dangling symlink");

        let unresolved_link = canonical_root.join("link");
        assert_eq!(
            super::resolve_missing_tail(
                canonical_root,
                &[OsString::from("link")],
                0,
            ),
            Some(unresolved_link),
            "Expected exhausted symlink replay to preserve the unresolved path."
        );
    }

    #[test]
    fn native_paths_map_to_their_provider_roots() {
        let temporary_directory = TemporaryDirectory::new();
        let home = temporary_directory.0.join("home");
        let cases = [
            (".codex/sessions/2026/session.jsonl", Provider::Codex),
            (".pi/agent/sessions/project/session.jsonl", Provider::Pi),
            (".claude/projects/project/session.jsonl", Provider::Claude),
        ];

        for (relative_path, expected_provider) in cases {
            let session_path = home.join(relative_path);
            fs::create_dir_all(session_path.parent().expect("session parent"))
                .expect("create provider root");
            fs::write(&session_path, "{}\n").expect("write session");
            assert_eq!(
                classify_native_session_path_impl(&session_path, &home),
                Some(expected_provider),
                "Expected {session_path:?} to map to {expected_provider:?}."
            );
        }

        let outside_path = temporary_directory.0.join("outside/session.jsonl");
        fs::create_dir_all(outside_path.parent().expect("outside parent"))
            .expect("create outside directory");
        fs::write(&outside_path, "{}\n").expect("write outside session");
        assert_eq!(
            classify_native_session_path_impl(&outside_path, &home),
            None,
            "Expected a path outside all native roots to remain unclassified."
        );
    }
}
