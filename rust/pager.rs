//! Incremental paging for streamed search output.
//!
//! This lives beside the search engine rather than with the colored views on
//! purpose. The engine's scan loop constructs the pager, writes each hit through
//! it, and reads `closed` to decide whether to keep scanning — early close is
//! scan control, not rendering. Keeping it here makes the seam one-directional:
//! the engine calls the views, the views return strings, nothing flows back.
//!
//! Behaviour is ported from `chats.console.StreamingPager`, which is the oracle.

use std::io::Write;
use std::process::{Child, ChildStdin, Command, Stdio};

/// Pages output through `less -r`, writing each chunk as it is produced.
///
/// `less` is invoked with `-r` rather than `-R` so wide and ambiguous-width
/// glyphs survive; `-R` keeps screen-width tracking active and mis-handles them.
pub struct Pager {
    stdin: Option<ChildStdin>,
    child: Option<Child>,
    closed: bool,
}

impl Pager {
    /// Spawn the pager, falling back to stdout when `less` is unavailable.
    pub fn spawn() -> Self {
        match Command::new("less")
            .arg("-r")
            .stdin(Stdio::piped())
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .spawn()
        {
            Ok(mut child) => Self {
                stdin: child.stdin.take(),
                child: Some(child),
                closed: false,
            },
            Err(_) => Self {
                stdin: None,
                child: None,
                closed: false,
            },
        }
    }

    /// Whether the reader dismissed the pager, which ends the scan.
    pub fn closed(&self) -> bool {
        self.closed
    }

    /// Write one already-rendered chunk to the pager, flushing immediately.
    ///
    /// The two paths flush differently and both match the oracle. The pager's
    /// stdin **is** flushed per chunk, so hits appear as they are found. The
    /// stdout fallback, taken only when `less` is missing, is **not** flushed,
    /// matching the oracle's bare `sys.stdout.write`.
    ///
    /// Read that narrowly: it is not a rule that this product avoids flushing.
    /// Streamed session ids are flushed individually and deliberately — see
    /// `commands/search.py:350` — and removing that costs seconds of visible
    /// latency while changing no bytes.
    pub fn write(&mut self, chunk: &str) {
        if self.closed || chunk.is_empty() {
            return;
        }
        let Some(stdin) = &mut self.stdin else {
            print!("{chunk}");
            return;
        };
        if stdin.write_all(chunk.as_bytes()).is_err() || stdin.flush().is_err() {
            self.closed = true;
        }
    }

    /// Close the pager's input and wait for the reader to dismiss it.
    pub fn close(&mut self) {
        let Some(mut child) = self.child.take() else {
            return;
        };
        drop(self.stdin.take());
        let _ = child.wait();
    }
}

impl Drop for Pager {
    fn drop(&mut self) {
        self.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn without_pager_process() -> Pager {
        Pager {
            stdin: None,
            child: None,
            closed: false,
        }
    }

    #[test]
    fn closing_without_a_pager_process_does_not_block() {
        let mut pager = without_pager_process();
        pager.close();
        assert!(
            !pager.closed(),
            "Expected closing the stdout fallback to leave the scan-control flag alone."
        );
    }

    // The engine reads `closed` to stop scanning, so a dismissed pager must stay
    // dismissed and must not resurrect on a later write.
    #[test]
    fn a_dismissed_pager_stays_dismissed() {
        let mut pager = without_pager_process();
        pager.closed = true;
        pager.write("ignored");
        assert!(
            pager.closed(),
            "Expected a dismissed pager to remain closed after a further write."
        );
    }

    #[test]
    fn an_empty_chunk_is_not_written() {
        let mut pager = without_pager_process();
        pager.write("");
        assert!(
            !pager.closed(),
            "Expected an empty chunk to be a no-op rather than a write attempt."
        );
    }
}
