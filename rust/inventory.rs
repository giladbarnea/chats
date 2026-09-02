//! Session inventory: provider classification, filesystem discovery, and the
//! JSONL line scanning the date filters and hit metadata read.
//!
//! Lifted unchanged from `python_extension.rs`, which compiled only under the
//! PyO3 features and was therefore invisible to the `ch` binary. The PyO3
//! wrappers now call this module rather than carrying their own copies.

use std::collections::HashMap;
use std::ffi::{OsStr, OsString};
use std::io::{ErrorKind, Read, Seek, SeekFrom};
use std::path::{Component, Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

#[cfg(unix)]
use std::os::unix::ffi::OsStrExt;
#[cfg(unix)]
use std::os::unix::fs::MetadataExt;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Provider {
    Codex,
    Pi,
    Claude,
}

impl Provider {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Codex => "codex",
            Self::Pi => "pi",
            Self::Claude => "claude",
        }
    }
}

pub fn provider_for_canonical_path(
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

pub fn classify_native_session_path_impl(path: &Path, home: &Path) -> Option<Provider> {
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
pub fn os_string_bytes(value: &OsStr) -> &[u8] {
    value.as_bytes()
}

#[cfg(not(unix))]
pub fn os_string_bytes(value: &OsStr) -> &[u8] {
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

pub fn python_filesystem_path_key(path: &Path) -> Vec<Vec<u32>> {
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
pub fn stat_mtime(path: &Path) -> f64 {
    let Ok(metadata) = std::fs::metadata(path) else {
        return f64::NEG_INFINITY;
    };
    metadata.mtime() as f64 + metadata.mtime_nsec() as f64 / 1_000_000_000.0
}

#[cfg(not(unix))]
pub fn stat_mtime(path: &Path) -> f64 {
    use std::time::UNIX_EPOCH;

    let Ok(modified) = std::fs::metadata(path).and_then(|metadata| metadata.modified()) else {
        return f64::NEG_INFINITY;
    };
    match modified.duration_since(UNIX_EPOCH) {
        Ok(duration) => duration.as_secs_f64(),
        Err(error) => -error.duration().as_secs_f64(),
    }
}

pub fn discover_session_files_impl(
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

pub const JSONL_SCAN_CHUNK_SIZE: usize = 4096;

pub fn trim_python_byte_whitespace(line: &[u8]) -> &[u8] {
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

/// What a line handler decides about one assembled line.
pub enum LineVerdict<T> {
    Found(T),
    Continue,
    Abort,
}

/// Walk a file's lines from the end toward the start, in fixed chunks.
///
/// The handler receives raw line bytes and does its own trimming. That is
/// deliberate: the byte layer wants Python's four-byte JSON whitespace set and
/// the `str` layer wants Python's `isspace()` set, and those differ in both
/// directions — Rust's own `trim` strips U+00A0 that the byte layer must keep,
/// and leaves U+001C..U+001F that the `str` layer must strip. A trim inside the
/// walk would silently impose one policy on both callers.
pub fn for_each_line_backward<T>(
    path: &Path,
    mut handle: impl FnMut(&[u8]) -> LineVerdict<T>,
) -> Option<T> {
    let mut file = std::fs::File::open(path).ok()?;
    let mut remaining_bytes = file.seek(SeekFrom::End(0)).ok()?;
    let mut later_fragments: Vec<Vec<u8>> = Vec::new();
    let mut assembled = Vec::new();

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
            assemble_line(&block[newline_index + 1..line_end], &later_fragments, &mut assembled);
            match handle(&assembled) {
                LineVerdict::Found(found) => return Some(found),
                LineVerdict::Abort => return None,
                LineVerdict::Continue => {}
            }
            later_fragments.clear();
            line_end = newline_index;
        }

        if line_end > 0 {
            later_fragments.push(block[..line_end].to_vec());
        }
    }

    assemble_line(&[], &later_fragments, &mut assembled);
    match handle(&assembled) {
        LineVerdict::Found(found) => Some(found),
        LineVerdict::Continue | LineVerdict::Abort => None,
    }
}

fn assemble_line(earlier: &[u8], later_fragments: &[Vec<u8>], assembled: &mut Vec<u8>) {
    assembled.clear();
    assembled.extend_from_slice(earlier);
    for fragment in later_fragments.iter().rev() {
        assembled.extend_from_slice(fragment);
    }
}

/// The last in-band timestamp in a JSONL file, scanning backward.
pub fn last_timestamp(path: &Path) -> Option<String> {
    for_each_line_backward(path, |line| {
        // **The byte trim is right here and must stay.** `get_jsonl_last_timestamp`
        // calls the Rust `find_last_jsonl_timestamp`, so on this one path the trim
        // is already Rust's and *is* the oracle. Widening it to `str.strip()` would
        // move the oracle rather than match it. The parse is the half that is
        // Python's — `_jsonl_line_timestamp` uses stdlib `json.loads`, which takes
        // `NaN` and `Infinity` where `serde_json` refuses and skips the line.
        let line = trim_python_byte_whitespace(line);
        if line.is_empty() {
            return LineVerdict::Continue;
        }
        let Ok(text) = std::str::from_utf8(line) else {
            return LineVerdict::Continue;
        };
        let lenient = crate::session::detection_lenient(text);
        match serde_json::from_str::<serde_json::Value>(&lenient) {
            Ok(entry) => match entry_timestamp(&entry) {
                Some(timestamp) => LineVerdict::Found(timestamp),
                None => LineVerdict::Continue,
            },
            Err(_) => LineVerdict::Continue,
        }
    })
}

/// The `timestamp` field, falling back to `created_at`, as Python reads it.
fn entry_timestamp(entry: &serde_json::Value) -> Option<String> {
    entry
        .get("timestamp")
        .or_else(|| entry.get("created_at"))
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

#[cfg(test)]
mod tests {
    use super::{
        Provider, classify_native_session_path_impl, provider_for_canonical_path,
        python_filesystem_path_key,
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

/// The session's working directory, read by streaming rather than parsing.
///
/// The `-d` filter runs in the *path* stage, before anything reads a file for
/// real, so this must not decode the whole session. It stops at the first entry
/// carrying a `cwd`, which is the same entry `session::cwd` would pick.
///
/// **No caller, today, and that is the only reason the gaps below are not
/// defects.** `ch search`'s `-d` reaches cwd through `session::cwd(&entries)` at
/// `search_confirm.rs`, not through here. This function is the port of Python's
/// `extract_cwd_from_jsonl_file`, which serves `pool_filter.passes_path_for_index`
/// — the `ch -1 -d` index path, which has not been ported.
///
/// **Two gaps remain, left rather than fixed because nothing reaches them, and
/// written down because the moment someone wires up `ch -1 -d` they become live:**
///
/// - Python requires a **truthy** cwd — `isinstance(cwd, str) and cwd` — so an
///   empty string falls through to the next check. This returns `Some("")`.
/// - Python then falls back to `_extract_cwd_from_codex_entry`, reading `cwd` out
///   of a Codex `<environment_context>` block. This has no such fallback, so a
///   Codex session yields nothing here.
///
/// A third, shared with every other line reader in this file: Python opens in
/// **text** mode, so a lone `\r` is a line separator to it and not to
/// `BufRead::read_line`. See `python_io::universal_newlines`.
pub fn cwd_from_path(path: &Path) -> Option<String> {
    let file = std::fs::File::open(path).ok()?;
    let mut reader = std::io::BufReader::new(file);
    let mut line = String::new();
    loop {
        line.clear();
        if std::io::BufRead::read_line(&mut reader, &mut line).ok()? == 0 {
            return None;
        }
        // Unlike `last_timestamp` above, this one's oracle is **pure CPython**:
        // `extract_cwd_from_jsonl_file` strips the *decoded* line with
        // `str.strip()` and parses with stdlib `json.loads`. The byte helper is
        // wrong on both counts here — it misses U+001C..U+001F and every
        // non-ASCII space, and `serde_json` refuses `NaN`.
        let trimmed = crate::session::python_strip(&line);
        if trimmed.is_empty() {
            continue;
        }
        let lenient = crate::session::detection_lenient(trimmed);
        let Ok(entry) = serde_json::from_str::<serde_json::Value>(&lenient) else {
            continue;
        };
        if let Some(cwd) = entry.get("cwd").and_then(serde_json::Value::as_str) {
            return Some(cwd.to_string());
        }
    }
}
