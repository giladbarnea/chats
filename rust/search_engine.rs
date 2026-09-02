//! The search scan loop: window, gate, confirm, stream, stop.
//!
//! Ported from `cmd_search` and `_iter_search_hits` in
//! `src/chats/commands/search.py`.
//!
//! Three economies in here are invisible in the output and are the whole reason
//! this loop is shaped the way it is. Removing any of them leaves every byte
//! identical and costs the user seconds:
//!
//! 1. **Early close stops the scan.** When the reader dismisses the pager, or
//!    pipes to `head`, scanning must end. This one is *measured losable*: a
//!    reference native implementation saved -1% on a close-after-one-line
//!    against Python's 92%, so `ch search … | head` cost a full pool scan.
//! 2. **Batches are confirmed serially, in input order, before the next opens.**
//!    That is what makes newest-first streaming visible. Confirming across
//!    batches concurrently finishes no sooner and emits hits out of order.
//! 3. **A gate failure prints at its own scan position**, after every preceding
//!    survivor's hit and before every following one. Python reaches this by
//!    flushing the accumulated window and only then printing, which lands the
//!    error exactly where the failing file sits in scan order.
//!
//! **One loop, two Python paths.** `_iter_search_hits` dispatches between a
//! serial path — path filters, candidate probe and confirm in a single `try` per
//! file — and a batched path that accumulates path-filter survivors to 256,
//! probes those as one batch, then confirms. They differ only in the batch size
//! and in the probe, so they are one loop with two settings. At `batch_size = 1`
//! flush-then-error degenerates to error-at-position, which is exactly what the
//! serial path's single `try` produces.
//!
//! **The batch counts survivors, not scanned files.** A pool where a date filter
//! rejects most files yields batches of `batch_size` survivors gathered across
//! far more scanned paths. Chunking the scan order instead would probe files the
//! path filters had already rejected — I/O Python never does — and would emit the
//! first hit earlier than Python, which is a parity difference even though it
//! favours the reader.

use std::path::{Path, PathBuf};

/// Where confirmed hits go, and whether the reader has stopped reading.
///
/// The engine writes through this and reads `closed`; nothing flows the other
/// way. `Pager` is the production implementation.
pub trait HitSink {
    /// One confirmed hit. **The sink renders it**, because rendering needs the
    /// ordinal — the count of hits emitted so far — which confirmation cannot know.
    /// Python yields a hit and the consumer renders it with `ordinal=found`; a sink
    /// handed finished bytes could not be the thing that made them.
    fn emit(&mut self, hit: &crate::search_confirm::SearchHit);
    /// True once the reader has dismissed the output. Ends the scan.
    fn closed(&self) -> bool;
    /// Per-file failure text, which goes to stderr rather than the pager.
    fn emit_error(&mut self, message: &str);
    /// Called once after the last hit, and **only when the reader is still there**.
    /// The coloured list summary lives here; the plain sinks do nothing.
    ///
    /// The not-closed half of Python's condition is the engine's, because `closed`
    /// belongs to the pager. The mode, colour and found-anything halves are the
    /// sink's own.
    fn finish(&mut self) {}
}

/// What the cheap per-file screen decided about one path.
///
/// A bool cannot express the third arm, and the third arm is the entire subject
/// of the ordering rule: only a *screen* failure can be discovered while earlier
/// survivors are still unconfirmed.
pub enum Gated {
    /// Survives the path filters and joins the pending batch.
    Survives,
    /// Rejected without reading the file's content.
    Rejected,
    /// The screen itself failed — an unreadable path, a directory. The text is
    /// Python's, including its `[Errno N]` shape.
    Failed(String),
}

/// What one file turned out to be.
pub enum Confirmed {
    /// A hit. The sink renders it; see `HitSink::emit`.
    Hit(crate::search_confirm::SearchHit),
    /// Read and rejected.
    Miss,
    /// Failed to process. The text is Python's, including its `[Errno N]` shape.
    Failed(String),
}

/// Why the scan ended, which decides the exit status.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Outcome {
    /// At least one hit was emitted.
    Hits,
    /// The pool held candidates but none matched.
    NoHits,
    /// No candidate files at all. Exits 1 silently, without the no-results hint.
    EmptyPool,
}

impl Outcome {
    /// `0` for hits, `1` for a fruitless search and for an empty pool.
    pub fn exit_status(self) -> i32 {
        match self {
            Outcome::Hits => 0,
            Outcome::NoHits | Outcome::EmptyPool => 1,
        }
    }

    /// Whether the caller should print the "no sessions match" hint.
    ///
    /// An empty pool exits 1 *silently*; a search that found nothing explains
    /// itself. Collapsing the two is a one-line simplification that changes
    /// observable output.
    pub fn wants_no_results_hint(self) -> bool {
        matches!(self, Outcome::NoHits)
    }
}

/// Scan `scan_order`, streaming confirmed hits until the reader stops.
///
/// `screen` applies the cheap per-file path filters in scan order. Survivors
/// accumulate until `batch_size` of them exist, then `probe` decides the whole
/// batch at once and must return **one decision per input path, positionally** —
/// a length mismatch would silently misalign every decision in the batch, so it
/// is asserted rather than tolerated. `confirm` reads a candidate and decides it
/// for real.
///
/// Use `batch_size = crate::session_pool::CANDIDATE_WINDOW` with the batched byte
/// gate, or `batch_size = 1` with a per-file probe for the serial path.
pub fn stream_search<S: HitSink>(
    scan_order: &[PathBuf],
    sink: &mut S,
    batch_size: usize,
    mut screen: impl FnMut(&Path) -> Gated,
    mut probe: impl FnMut(&[PathBuf]) -> Vec<bool>,
    mut confirm: impl FnMut(&Path) -> Confirmed,
) -> Outcome {
    assert!(batch_size > 0, "batch_size must be at least 1");
    if scan_order.is_empty() {
        return Outcome::EmptyPool;
    }

    let mut found = false;
    let mut pending: Vec<PathBuf> = Vec::with_capacity(batch_size);

    for path in scan_order {
        if sink.closed() {
            return outcome(found);
        }
        match screen(path) {
            Gated::Rejected => {}
            Gated::Failed(message) => {
                // Python flushes the accumulated batch and only then prints, which
                // lands the error after every preceding survivor's hit and before
                // every following one. Holding it to the end of the batch instead
                // looks equivalent and is not: the two differ whenever a failure
                // precedes a survivor, which is the common case.
                if flush(&mut pending, sink, &mut probe, &mut confirm, &mut found) {
                    return outcome(found);
                }
                sink.emit_error(&message);
            }
            Gated::Survives => {
                pending.push(path.clone());
                if pending.len() == batch_size
                    && flush(&mut pending, sink, &mut probe, &mut confirm, &mut found)
                {
                    return outcome(found);
                }
            }
        }
    }
    flush(&mut pending, sink, &mut probe, &mut confirm, &mut found);
    if !sink.closed() {
        sink.finish();
    }
    outcome(found)
}

/// Probe one accumulated batch and confirm its candidates, in input order.
///
/// Returns whether the reader stopped, which ends the scan. Leaves `pending`
/// empty either way, so a caller cannot flush the same batch twice.
fn flush<S: HitSink>(
    pending: &mut Vec<PathBuf>,
    sink: &mut S,
    probe: &mut impl FnMut(&[PathBuf]) -> Vec<bool>,
    confirm: &mut impl FnMut(&Path) -> Confirmed,
    found: &mut bool,
) -> bool {
    if pending.is_empty() {
        return false;
    }
    let decisions = probe(pending);
    assert_eq!(
        decisions.len(),
        pending.len(),
        "probe returned {} decisions for {} paths; decisions must be positional",
        decisions.len(),
        pending.len()
    );

    for (path, candidate) in pending.iter().zip(decisions) {
        if !candidate {
            continue;
        }
        match confirm(path) {
            Confirmed::Hit(hit) => {
                sink.emit(&hit);
                *found = true;
                if sink.closed() {
                    pending.clear();
                    return true;
                }
            }
            Confirmed::Miss => {}
            Confirmed::Failed(message) => sink.emit_error(&message),
        }
    }
    pending.clear();
    false
}

fn outcome(found: bool) -> Outcome {
    if found { Outcome::Hits } else { Outcome::NoHits }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::rc::Rc;

    const BATCH: usize = crate::session_pool::CANDIDATE_WINDOW;

    /// Records hits and errors in **one interleaved log**, so a test can assert
    /// their relative order. Two separate lists would let an error overtake a hit
    /// without any assertion noticing.
    #[derive(Default)]
    struct Recorder {
        events: Vec<String>,
        close_after: Option<usize>,
        /// Closes once this many files have been screened, modelling a reader that
        /// quits while the engine is rejecting rather than after a hit.
        close_after_screens: Option<usize>,
        screens: Rc<std::cell::Cell<usize>>,
        /// Counted rather than logged, so the ordering assertions stay about the
        /// relative order of hits and errors and nothing else.
        finishes: usize,
    }

    impl Recorder {
        fn emitted(&self) -> Vec<&str> {
            self.events
                .iter()
                .filter_map(|event| event.strip_prefix("hit:"))
                .collect()
        }
        fn errors(&self) -> Vec<&str> {
            self.events
                .iter()
                .filter_map(|event| event.strip_prefix("err:"))
                .collect()
        }
    }

    impl HitSink for Recorder {
        fn emit(&mut self, hit: &crate::search_confirm::SearchHit) {
            self.events.push(format!("hit:{}", name(&hit.metadata.path)));
        }
        fn closed(&self) -> bool {
            let by_hits = self
                .close_after
                .is_some_and(|limit| self.emitted().len() >= limit);
            let by_screens = self
                .close_after_screens
                .is_some_and(|limit| self.screens.get() >= limit);
            by_hits || by_screens
        }
        fn emit_error(&mut self, message: &str) {
            self.events.push(format!("err:{message}"));
        }
        fn finish(&mut self) {
            self.finishes += 1;
        }
    }

    fn paths(count: usize) -> Vec<PathBuf> {
        (0..count).map(|index| PathBuf::from(index.to_string())).collect()
    }

    fn name(path: &Path) -> String {
        path.display().to_string()
    }

    /// A hit carrying only the path, which is all these ordering tests assert on.
    fn hit_for(path: &Path) -> crate::search_confirm::SearchHit {
        let mut hit = crate::search_confirm::SearchHit::empty_for_doctest();
        hit.metadata.path = path.to_path_buf();
        hit
    }

    /// Every path survives the screen.
    fn survives(_path: &Path) -> Gated {
        Gated::Survives
    }

    /// Every probed path is a candidate.
    fn all_candidates(batch: &[PathBuf]) -> Vec<bool> {
        vec![true; batch.len()]
    }

    // ---------------------------------------------------------------- batching

    /// The batch counts **survivors**, not scanned files. Chunking the scan order
    /// instead would hand the probe files the screen already rejected, and would
    /// reach the first hit sooner than Python does.
    #[test]
    fn batches_fill_with_survivors_not_with_scanned_files() {
        let files = paths(1_000);
        let mut sink = Recorder::default();
        let batch_sizes: Rc<RefCell<Vec<usize>>> = Rc::new(RefCell::new(Vec::new()));
        let seen: Rc<RefCell<Vec<String>>> = Rc::new(RefCell::new(Vec::new()));
        let recorded_sizes = batch_sizes.clone();
        let recorded_paths = seen.clone();

        stream_search(
            &files,
            &mut sink,
            32,
            // Only every tenth path survives: 100 survivors across 1,000 files.
            |path| {
                if name(path).parse::<usize>().expect("test path is numeric") % 10 == 0 {
                    Gated::Survives
                } else {
                    Gated::Rejected
                }
            },
            |batch| {
                recorded_sizes.borrow_mut().push(batch.len());
                recorded_paths.borrow_mut().extend(batch.iter().map(|p| name(p)));
                all_candidates(batch)
            },
            |_| Confirmed::Miss,
        );

        assert_eq!(
            *batch_sizes.borrow(),
            vec![32, 32, 32, 4],
            "batches must fill to 32 survivors each; got {:?}. Chunking the scan \
             order into 32s would give 32 batches of 1 survivor instead.",
            batch_sizes.borrow()
        );
        assert_eq!(
            seen.borrow().len(),
            100,
            "the probe must see every survivor exactly once"
        );
    }

    /// A file the screen rejected must never reach the probe. Probing it would be
    /// I/O Python never performs.
    #[test]
    fn a_rejected_file_is_never_probed() {
        let files = paths(10);
        let mut sink = Recorder::default();
        let probed: Rc<RefCell<Vec<String>>> = Rc::new(RefCell::new(Vec::new()));
        let recorded = probed.clone();

        stream_search(
            &files,
            &mut sink,
            BATCH,
            |path| {
                if name(path) == "4" { Gated::Rejected } else { Gated::Survives }
            },
            |batch| {
                recorded.borrow_mut().extend(batch.iter().map(|p| name(p)));
                all_candidates(batch)
            },
            |_| Confirmed::Miss,
        );

        assert!(
            !probed.borrow().iter().any(|path| path == "4"),
            "a screen-rejected file reached the probe: {:?}",
            probed.borrow()
        );
        assert_eq!(probed.borrow().len(), 9, "every other file must be probed");
    }

    /// A probe returning `false` is a rejection, so the file is never read.
    #[test]
    fn a_probe_rejection_is_never_confirmed() {
        let files = paths(6);
        let mut sink = Recorder::default();
        let mut confirmed: Vec<String> = Vec::new();

        stream_search(
            &files,
            &mut sink,
            BATCH,
            survives,
            |batch| batch.iter().map(|path| name(path) != "3").collect(),
            |path| {
                confirmed.push(name(path));
                Confirmed::Miss
            },
        );

        assert_eq!(
            confirmed,
            vec!["0", "1", "2", "4", "5"],
            "a probe rejection must skip confirmation entirely"
        );
    }

    // ------------------------------------------------------------ early close

    /// The economy measured as losable: a reader that stops must stop the scan,
    /// at the hit rather than at the end of the batch.
    #[test]
    fn early_close_stops_scanning() {
        let files = paths(2_000);
        let mut sink = Recorder { close_after: Some(1), ..Default::default() };
        let mut visited = 0usize;
        stream_search(&files, &mut sink, BATCH, survives, all_candidates, |path| {
            visited += 1;
            Confirmed::Hit(hit_for(path))
        });
        assert_eq!(sink.emitted().len(), 1, "one hit should have been emitted");
        // Exact, not `< files.len()`. A loop that stopped only at the next batch
        // boundary would confirm 256 files and still satisfy a bound of 2,000.
        assert_eq!(
            visited, 1,
            "the scan must stop at the hit, not at the end of the batch"
        );
    }

    /// Without an early close the whole pool is scanned, so the test above is
    /// measuring the close rather than some unrelated stopping condition.
    #[test]
    fn without_early_close_the_whole_pool_is_scanned() {
        let files = paths(600);
        let mut sink = Recorder::default();
        let mut visited = 0usize;
        let outcome =
            stream_search(&files, &mut sink, BATCH, survives, all_candidates, |_| {
                visited += 1;
                Confirmed::Miss
            });
        assert_eq!(visited, 600);
        assert_eq!(outcome, Outcome::NoHits);
    }

    /// A reader that quits while every file is being rejected, with no hit to
    /// trigger the check inside the batch, must still stop the scan.
    #[test]
    fn early_close_without_any_hit_stops_scanning() {
        let files = paths(2_000);
        let screens = Rc::new(std::cell::Cell::new(0usize));
        let mut sink = Recorder {
            close_after_screens: Some(1),
            screens: screens.clone(),
            ..Default::default()
        };
        stream_search(
            &files,
            &mut sink,
            BATCH,
            |_| {
                screens.set(screens.get() + 1);
                Gated::Rejected
            },
            all_candidates,
            |_| Confirmed::Miss,
        );
        assert_eq!(screens.get(), 1, "scanning continued past an early close");
    }

    // --------------------------------------------------------------- ordering

    /// Hits arrive in scan order across batch boundaries.
    #[test]
    fn hits_stream_in_scan_order() {
        let files = paths(600);
        let mut sink = Recorder::default();
        stream_search(&files, &mut sink, BATCH, survives, all_candidates, |path| {
            Confirmed::Hit(hit_for(path))
        });
        let expected: Vec<String> = files.iter().map(|path| name(path)).collect();
        assert_eq!(sink.emitted(), expected);
    }

    /// A confirmation failure must not print above a hit that precedes it.
    #[test]
    fn an_error_never_overtakes_an_earlier_hit() {
        let files = paths(3);
        let mut sink = Recorder::default();
        stream_search(&files, &mut sink, BATCH, survives, all_candidates, |path| {
            if name(path) == "1" {
                Confirmed::Failed("[Errno 21] Is a directory: '1'".to_string())
            } else {
                Confirmed::Hit(hit_for(path))
            }
        });
        assert_eq!(sink.emitted(), vec!["0", "2"]);
        assert_eq!(sink.errors().len(), 1);
        assert_eq!(
            sink.events,
            vec![
                "hit:0".to_string(),
                "err:[Errno 21] Is a directory: '1'".to_string(),
                "hit:2".to_string(),
            ],
            "an error overtook an earlier hit"
        );
    }

    /// A screen failure lands at its own scan position: after the hits that
    /// precede it, before the hits that follow. Pinning both directions matters —
    /// a rule that holds failures until the batch ends agrees with this one only
    /// when the failure happens to be last.
    #[test]
    fn a_screen_failure_prints_at_its_own_scan_position() {
        let files = paths(5);
        let mut sink = Recorder::default();
        stream_search(
            &files,
            &mut sink,
            BATCH,
            |path| {
                if name(path) == "2" {
                    Gated::Failed("[Errno 21] Is a directory: '2'".to_string())
                } else {
                    Gated::Survives
                }
            },
            all_candidates,
            |path| Confirmed::Hit(hit_for(path)),
        );
        assert_eq!(
            sink.events,
            vec![
                "hit:0".to_string(),
                "hit:1".to_string(),
                "err:[Errno 21] Is a directory: '2'".to_string(),
                "hit:3".to_string(),
                "hit:4".to_string(),
            ],
            "a screen failure must print where the failing file sits in scan order"
        );
    }

    /// The failure-last case, kept because it is the one both candidate rules
    /// agree on and so proves the test above is not simply inverted.
    #[test]
    fn a_screen_failure_never_overtakes_an_earlier_hit() {
        let files = paths(3);
        let mut sink = Recorder::default();
        stream_search(
            &files,
            &mut sink,
            BATCH,
            |path| {
                if name(path) == "2" {
                    Gated::Failed("[Errno 21] Is a directory: '2'".to_string())
                } else {
                    Gated::Survives
                }
            },
            all_candidates,
            |path| Confirmed::Hit(hit_for(path)),
        );
        assert_eq!(
            sink.events,
            vec![
                "hit:0".to_string(),
                "hit:1".to_string(),
                "err:[Errno 21] Is a directory: '2'".to_string(),
            ],
            "a screen failure printed above a hit that precedes it in scan order"
        );
    }

    /// At `batch_size = 1` the loop is Python's serial path, where filters, probe
    /// and confirm sit in one `try` per file — so flush-then-error is exactly
    /// error-at-position, and no hit ever waits on a later file.
    #[test]
    fn a_batch_size_of_one_is_the_serial_path() {
        let files = paths(4);
        let mut sink = Recorder::default();
        stream_search(
            &files,
            &mut sink,
            1,
            |path| {
                if name(path) == "1" {
                    Gated::Failed("Error processing conversation file 1".to_string())
                } else {
                    Gated::Survives
                }
            },
            all_candidates,
            |path| Confirmed::Hit(hit_for(path)),
        );
        assert_eq!(
            sink.events,
            vec![
                "hit:0".to_string(),
                "err:Error processing conversation file 1".to_string(),
                "hit:2".to_string(),
                "hit:3".to_string(),
            ],
            "serial mode must emit every outcome at its own scan position"
        );
    }

    // ----------------------------------------------------------------- outcome

    /// `finish` runs once after the last hit, so the coloured list summary can be
    /// written where Python writes it.
    #[test]
    fn finish_runs_once_after_the_last_hit() {
        let mut sink = Recorder::default();
        stream_search(&paths(5), &mut sink, BATCH, survives, all_candidates, |path| {
            Confirmed::Hit(hit_for(path))
        });
        assert_eq!(sink.finishes, 1, "finish must run exactly once");
        assert_eq!(sink.emitted().len(), 5, "and only after every hit");
    }

    /// A reader who has gone gets no summary. This half of Python's condition is
    /// the engine's, because `closed` belongs to the pager and not to the sink.
    #[test]
    fn finish_is_skipped_when_the_reader_has_stopped() {
        let mut sink = Recorder { close_after: Some(1), ..Default::default() };
        stream_search(&paths(50), &mut sink, BATCH, survives, all_candidates, |path| {
            Confirmed::Hit(hit_for(path))
        });
        assert_eq!(
            sink.finishes, 0,
            "a dismissed reader must not be sent a trailing summary"
        );
    }

    /// An empty pool returns before the loop, so nothing is finished either.
    #[test]
    fn finish_is_skipped_for_an_empty_pool() {
        let mut sink = Recorder::default();
        stream_search(&[], &mut sink, BATCH, survives, all_candidates, |_| Confirmed::Miss);
        assert_eq!(sink.finishes, 0);
    }

    #[test]
    fn an_empty_pool_is_distinct_from_a_fruitless_search() {
        let mut sink = Recorder::default();
        let empty =
            stream_search(&[], &mut sink, BATCH, survives, all_candidates, |_| Confirmed::Miss);
        assert_eq!(empty, Outcome::EmptyPool);
        assert_eq!(empty.exit_status(), 1);
        assert!(!empty.wants_no_results_hint(), "an empty pool exits silently");

        let fruitless = stream_search(
            &paths(4),
            &mut sink,
            BATCH,
            survives,
            all_candidates,
            |_| Confirmed::Miss,
        );
        assert_eq!(fruitless, Outcome::NoHits);
        assert_eq!(fruitless.exit_status(), 1);
        assert!(fruitless.wants_no_results_hint(), "a fruitless search explains itself");
    }

    /// A pool whose every file is rejected by the screen is still a *fruitless
    /// search*, not an empty pool: Python exits 1 silently only when the candidate
    /// list itself is empty, before any scanning happens.
    #[test]
    fn a_fully_rejected_pool_is_a_fruitless_search_not_an_empty_pool() {
        let mut sink = Recorder::default();
        let outcome = stream_search(
            &paths(50),
            &mut sink,
            BATCH,
            |_| Gated::Rejected,
            all_candidates,
            |_| Confirmed::Miss,
        );
        assert_eq!(outcome, Outcome::NoHits);
        assert!(outcome.wants_no_results_hint());
    }
}
