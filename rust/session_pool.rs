//! The supported-session inventory for one invocation.
//!
//! Ported from `src/chats/session_pool.py`, narrowed to what search needs:
//! the file list, the provider partition, and the stat-mtime ordering. Identifier
//! resolution lives in the `resolve` route and is deliberately not here.
//!
//! **Two orderings matter and they are not the same one.** `stat_mtime_sorted` is
//! ascending by *filesystem* mtime; search reverses it to scan newest-first. Date
//! *filters* never consult stat mtime as their primary source — that is
//! `pool_filter`'s content probe — because an imported or restored file carries a
//! filesystem time that precedes its content.

use crate::inventory::{self, Provider};
use std::path::{Path, PathBuf};

/// Every provider, in the order `model.PROVIDERS` declares them, so the partition
/// has the same keys even when a provider contributes no sessions.
pub const PROVIDERS: [Provider; 3] = [Provider::Claude, Provider::Pi, Provider::Codex];

#[derive(Debug, Clone, Default)]
pub struct SessionPool {
    /// Discovery order.
    pub files: Vec<PathBuf>,
    /// One entry per provider, always present, possibly empty. A list rather
    /// than a map: there are three providers, and `Provider` is a peer's type
    /// that does not derive `Hash`.
    pub by_provider: Vec<(Provider, Vec<PathBuf>)>,
    /// Ascending by filesystem mtime. Search reverses this for newest-first.
    pub stat_mtime_sorted: Vec<PathBuf>,
}

impl SessionPool {
    /// Build the pool from the current session universe.
    pub fn discover(home: &Path, include_sidechains: bool) -> SessionPool {
        let rows = inventory::discover_session_files_impl(home, include_sidechains)
            .into_iter()
            .map(|(path, provider, mtime)| {
                let resolved = provider
                    .or_else(|| inventory::classify_native_session_path_impl(&path, home))
                    .unwrap_or(Provider::Claude);
                (path, resolved, mtime)
            })
            .collect::<Vec<_>>();
        SessionPool::from_rows(rows)
    }

    /// Build every projection from ordered provider and stat rows.
    fn from_rows(rows: Vec<(PathBuf, Provider, f64)>) -> SessionPool {
        let mut by_provider: Vec<(Provider, Vec<PathBuf>)> =
            PROVIDERS.iter().map(|provider| (*provider, Vec::new())).collect();
        for (path, provider, _) in &rows {
            if let Some(group) = by_provider.iter_mut().find(|(name, _)| name == provider) {
                group.1.push(path.clone());
            }
        }

        let mut ordered = rows.clone();
        // Python sorts by mtime alone with a stable sort, so files sharing an
        // mtime keep discovery order. An unstable sort here would reorder them
        // and change which hit streams first.
        ordered.sort_by(|left, right| {
            left.2.partial_cmp(&right.2).unwrap_or(std::cmp::Ordering::Equal)
        });

        SessionPool {
            files: rows.iter().map(|(path, _, _)| path.clone()).collect(),
            by_provider,
            stat_mtime_sorted: ordered.into_iter().map(|(path, _, _)| path).collect(),
        }
    }

    /// The cheap pre-filter: the provider partition, or everything.
    ///
    /// This reads *discovery* rows, never gate survivors, which is what the
    /// provider-column predicate downstream depends on.
    pub fn candidate_files(&self, provider: Option<Provider>) -> Vec<PathBuf> {
        match provider {
            Some(wanted) => self
                .by_provider
                .iter()
                .find(|(name, _)| *name == wanted)
                .map(|(_, paths)| paths.clone())
                .unwrap_or_default(),
            None => self.files.clone(),
        }
    }

    /// Files to scan, newest first, restricted to `candidates`.
    ///
    /// ```
    /// # use _native::session_pool::SessionPool;
    /// let pool = SessionPool::default();
    /// assert!(pool.scan_order(&[]).is_empty());
    /// ```
    pub fn scan_order(&self, candidates: &[PathBuf]) -> Vec<PathBuf> {
        let wanted: std::collections::HashSet<&PathBuf> = candidates.iter().collect();
        self.stat_mtime_sorted
            .iter()
            .rev()
            .filter(|path| wanted.contains(path))
            .cloned()
            .collect()
    }
}

/// How many path-filter survivors one candidate batch holds.
///
/// Measured, not guessed: 128 / 256 / 512 completed a full scan in 1.422 / 1.188
/// / 1.182 seconds, and 512 bought 6 ms of completion while adding 207 ms to the
/// first barrier. The batch is what makes newest-first streaming visible, so a
/// wider one trades the user's first result for nothing.
///
/// It counts *survivors*, matching `_iter_batched_ascii_literal_hits`, which
/// appends to its window only after the path filters pass.
pub const CANDIDATE_WINDOW: usize = 256;
