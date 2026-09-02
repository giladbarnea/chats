//! Candidate planning: what to scan, in what order, and what to reject cheaply.
//!
//! This is the assembly layer between the landed machinery and
//! `search_engine::stream_search`. It supplies three of that function's inputs —
//! the scan order, the per-path screen, and the batched probe — and owns none of
//! the logic itself.
//!
//! The economies here are deliberate and each one is invisible to a byte
//! comparison. Probing is lazy per filter and short-circuits; rejection happens
//! before any file is materialised; and the order is newest-first so streaming
//! shows its first hit early.

use std::path::{Path, PathBuf};

use crate::inventory::{Provider, cwd_from_path};
use crate::pool_filter::{PoolFilter, first_timestamp, last_timestamp, parse_date_filter};
use crate::search::parse::SearchPoolFilter;
use crate::scanner::files_contain_ascii_json_strings_impl;
use crate::search_engine::Gated;
use crate::session_pool::SessionPool;

/// Files to scan, newest first, narrowed to one provider when asked.
///
/// Newest-first is by **filesystem mtime**, not by content timestamp. The two
/// disagree on imported and restored sessions, and the ordering follows the
/// filesystem.
pub fn scan_order(pool: &SessionPool, provider: Option<Provider>) -> Vec<PathBuf> {
    pool.scan_order(&pool.candidate_files(provider))
}

/// The cheap per-path screen: date filters, then the directory filter.
///
/// Ordering is load-bearing in two ways. A failed `-ma` check returns before the
/// `-ca` probe, so a rejected file is never opened twice. And the directory
/// probe runs last because it is the only one that opens the file at all.
pub fn screen(filter: &PoolFilter) -> impl FnMut(&Path) -> Gated + '_ {
    move |path: &Path| {
        if filter.has_date_filters() && !filter.passes_path_for_date(path) {
            return Gated::Rejected;
        }
        if filter.needs_content_for_dir() && !filter.passes_cwd(cwd_from_path(path).as_deref()) {
            return Gated::Rejected;
        }
        Gated::Survives
    }
}

/// The batched byte gate over one window of screen survivors.
///
/// Returns **one decision per input path, positionally**. The engine asserts the
/// length, because a mismatch would misalign every decision in the batch rather
/// than failing loudly.
///
/// `pi_session` is per path: a Pi file carrying the joined-agent marker cannot be
/// rejected here, because that record synthesises visible text absent from the
/// raw bytes. Deferring is a correctness requirement, not a missed optimisation.
pub fn probe<'a>(
    needle: &'a [u8],
    is_pi_session: impl Fn(&Path) -> bool + 'a,
) -> impl FnMut(&[PathBuf]) -> Vec<bool> + 'a {
    move |paths: &[PathBuf]| {
        let pi_sessions = paths.iter().map(|path| is_pi_session(path)).collect();
        files_contain_ascii_json_strings_impl(paths.to_vec(), needle, pi_sessions)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write(path: &Path, body: &str) {
        std::fs::create_dir_all(path.parent().expect("parent")).expect("create dir");
        std::fs::write(path, body).expect("write session");
    }

    fn temp_dir(name: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!("ch-plan-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("create temp dir");
        path
    }

    #[test]
    fn the_cwd_probe_stops_at_the_first_entry_carrying_one() {
        let root = temp_dir("cwd");
        let path = root.join("session.jsonl");
        write(
            &path,
            "{\"type\":\"summary\",\"summary\":\"no cwd here\"}\n\
             {\"type\":\"user\",\"cwd\":\"/wanted\"}\n\
             {\"type\":\"user\",\"cwd\":\"/later\"}\n",
        );
        assert_eq!(
            cwd_from_path(&path).as_deref(),
            Some("/wanted"),
            "Expected the first entry with a cwd to win, as the parser does."
        );
    }

    #[test]
    fn an_unreadable_path_has_no_cwd_rather_than_panicking() {
        assert_eq!(
            cwd_from_path(Path::new("/definitely/not/here.jsonl")),
            None,
            "Expected a missing path to yield no cwd."
        );
    }

    // The directory filter must reject without the engine ever seeing the file.
    #[test]
    fn the_screen_rejects_a_directory_mismatch_before_confirmation() {
        let root = temp_dir("dir");
        let matching = root.join("match.jsonl");
        let other = root.join("other.jsonl");
        write(&matching, "{\"type\":\"user\",\"cwd\":\"/wanted\"}\n");
        write(&other, "{\"type\":\"user\",\"cwd\":\"/elsewhere\"}\n");

        let filter = PoolFilter::new(None, Some("/wanted".to_string()), None, None)
            .expect("filter builds");
        let mut screen = screen(&filter);
        assert!(
            matches!(screen(&matching), Gated::Survives),
            "Expected the matching cwd to survive the screen."
        );
        assert!(
            matches!(screen(&other), Gated::Rejected),
            "Expected a different cwd to be rejected without reading the session."
        );
    }

    #[test]
    fn an_empty_filter_lets_everything_through_without_opening_anything() {
        let filter = PoolFilter::new(None, None, None, None).expect("filter builds");
        let mut screen = screen(&filter);
        assert!(
            matches!(screen(Path::new("/definitely/not/here.jsonl")), Gated::Survives),
            "Expected no filters to mean no probes, so even a missing path survives."
        );
    }
}

/// The screen the cutover uses: date filters parsed **per path**, not up front.
///
/// The laziness is load-bearing and is not an optimisation. Python holds the
/// raw strings and resolves them through a `cached_property`, which re-raises on
/// every access because a raising property caches nothing. So an unparseable
/// `-ma notadate` produces one `Invalid date format` error **per candidate
/// file**, then the ordinary no-results hint, exiting 1 — measured, two files
/// giving two errors.
///
/// Parsing once at the cutover would fail once, before the scan. That is
/// arguably better and is not what the product does; `state.md` preserves the
/// per-file shape deliberately, because turning it into a fast failure is a
/// product improvement smuggled into a parity port.
///
/// The message is the **whole** line the user sees. `stream_search` passes it to
/// `HitSink::emit_error` unchanged, so the prefix has to come from here — the
/// screen is what knows the path.
pub fn lazy_screen(filter: &SearchPoolFilter) -> impl FnMut(&Path) -> Gated + '_ {
    move |path: &Path| {
        for (raw, probe) in [
            (filter.modified_after.as_deref(), true),
            (filter.created_after.as_deref(), false),
        ] {
            let Some(raw) = raw else { continue };
            let threshold = match parse_date_filter(Some(raw)) {
                Ok(threshold) => threshold,
                Err(message) => {
                    return Gated::Failed(format!(
                        "Error processing conversation file {}: {message}",
                        path.display()
                    ));
                }
            };
            let Some(threshold) = threshold else { continue };
            let stamp = if probe { last_timestamp(path) } else { first_timestamp(path) };
            match stamp {
                Some(stamp) if stamp >= threshold => {}
                _ => return Gated::Rejected,
            }
        }
        if filter.directory.is_some() {
            let wanted = PoolFilter::new(None, filter.directory.clone(), None, None)
                .expect("no dates supplied, so this cannot fail");
            if !wanted.passes_cwd(cwd_from_path(path).as_deref()) {
                return Gated::Rejected;
            }
        }
        Gated::Survives
    }
}

#[cfg(test)]
mod lazy_screen_tests {
    use super::*;

    fn raw(mafter: Option<&str>, cafter: Option<&str>) -> SearchPoolFilter {
        SearchPoolFilter {
            directory: None,
            modified_after: mafter.map(str::to_string),
            created_after: cafter.map(str::to_string),
            provider: None,
        }
    }

    /// Measured against `ch-legacy`: two files in the pool give two errors.
    #[test]
    fn an_unparseable_date_fails_once_per_path_rather_than_once_overall() {
        let filter = raw(Some("notadate"), None);
        let mut screen = lazy_screen(&filter);
        for path in [Path::new("/a.jsonl"), Path::new("/b.jsonl")] {
            match screen(path) {
                Gated::Failed(message) => assert!(
                    message.contains("Invalid date format") && message.contains(&*path.to_string_lossy()),
                    "Expected the whole Python line naming this path. Got: {message}"
                ),
                _ => panic!("Expected {path:?} to fail on the unparseable date."),
            }
        }
    }

    /// The eager `PoolFilter::passes_path_for_date` and this lazy screen must not
    /// drift: same verdict for every valid filter, on a path with no timestamps.
    #[test]
    fn the_lazy_screen_agrees_with_the_eager_filter_on_valid_dates() {
        let missing = Path::new("/definitely/not/here.jsonl");
        for (mafter, cafter) in [(None, None), (Some("1d"), None), (None, Some("1d")), (Some("1d"), Some("2d"))] {
            let eager = PoolFilter::new(None, None, mafter, cafter).expect("valid dates");
            let expected = eager.passes_path_for_date(missing);
            let filter = raw(mafter, cafter);
            let actual = matches!(lazy_screen(&filter)(missing), Gated::Survives);
            assert_eq!(
                actual, expected,
                "Lazy and eager date screening disagreed for {mafter:?}/{cafter:?}."
            );
        }
    }
    /// **Timing economy 2: a failed `-ma` returns before the `-ca` probe**, so a
    /// rejected file is never opened twice.
    ///
    /// This test exists because **no other instrument can ever reach it.** The cost
    /// is one file open rather than measurable wall time, and the tools that count
    /// opens are SIP-restricted on this machine, so `economy_probe` cannot see it.
    /// A stored-rule unit test is the only available guard, and it is durable past
    /// cutover because it compares against a rule rather than against a live peer.
    ///
    /// **It asserts the ordering, not the outcome.** A test checking that a
    /// rejected file yields no hit passes with the two probes swapped, which is
    /// exactly the mutation this defends against. The trick is an **invalid** `-ca`
    /// beside a rejecting `-ma`: in the right order the `-ca` string is never even
    /// parsed, so the verdict is `Rejected`; swap them and parsing it first turns
    /// the same case into `Failed`.
    ///
    /// Named mutation: `cafter_probed_before_mafter`.
    #[test]
    fn a_failed_mafter_returns_before_the_cafter_probe() {
        // No file exists at this path, so `last_timestamp` finds neither an in-band
        // stamp nor a filesystem one and the `-ma` check rejects.
        let missing = Path::new("/definitely/not/here.jsonl");
        let filter = raw(Some("2099-01-01"), Some("bogus-date"));

        match lazy_screen(&filter)(missing) {
            Gated::Rejected => {}
            Gated::Failed(message) => panic!(
                "The `-ca` value was parsed even though `-ma` had already rejected \
                 the path, so the probes run in the wrong order. Got: {message}"
            ),
            Gated::Survives => panic!("Expected the `-ma` check to reject this path."),
        }
    }

    /// The control: with `-ma` absent there is nothing to return early from, so the
    /// same invalid `-ca` *is* reached and does fail. Without this, the test above
    /// would pass against a screen that never looked at `-ca` at all.
    #[test]
    fn the_cafter_value_is_reached_when_mafter_does_not_reject_first() {
        let missing = Path::new("/definitely/not/here.jsonl");
        let filter = raw(None, Some("bogus-date"));
        match lazy_screen(&filter)(missing) {
            Gated::Failed(message) => assert!(
                message.contains("Invalid date format"),
                "Expected the `-ca` parse failure. Got: {message}"
            ),
            other => panic!(
                "Expected the invalid `-ca` to be reached and to fail, got {}",
                match other {
                    Gated::Rejected => "Rejected",
                    Gated::Survives => "Survives",
                    Gated::Failed(_) => unreachable!(),
                }
            ),
        }
    }
}
