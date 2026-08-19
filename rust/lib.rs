use std::collections::HashMap;
use std::ffi::{OsStr, OsString};
use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

use pyo3::prelude::*;

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

#[pyfunction]
fn classify_native_session_path(path: &str, home: &str) -> Option<&'static str> {
    classify_native_session_path_impl(Path::new(path), Path::new(home)).map(Provider::as_str)
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(classify_native_session_path, module)?)
}

#[cfg(test)]
mod tests {
    use super::{classify_native_session_path_impl, provider_for_canonical_path, Provider};
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
