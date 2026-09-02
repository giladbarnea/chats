//! Reading a file the way Python does, and reporting failure the way Python does.
//!
//! `Path.read_text(encoding="utf-8")` opens in **text** mode, so it does two
//! things `std::fs::read` plus a UTF-8 decode does not: it translates line
//! endings, and it fails in Python's two shapes.
//!
//! - `newline=None` is universal-newline mode, so `\r\n` and a lone `\r` both
//!   reach the caller as `\n`. See `universal_newlines`.
//! - the open fails, giving `OSError.__str__` — `[Errno 21] Is a directory: '…'`,
//!   with the path in Python's `repr` quoting rather than Rust's debug quoting;
//! - the bytes are not UTF-8, giving `UnicodeDecodeError`, whose message and
//!   position arithmetic differ between a truncated sequence and an invalid byte.
//!
//! Lifted out of `rust/main.rs` rather than copied, so `ch parse` and `ch search`
//! report a failed read identically. Standing constraint 4: a copy that compiles
//! is not an extraction. The branch already shipped one fork of this shape —
//! `python_extension.rs` trimming on JSON whitespace while `inventory.rs` trimmed
//! on Unicode whitespace, so the same file yielded a timestamp on one route and a
//! filesystem fallback on the other — and the error path is a worse place for it,
//! because nobody looks there until it fires.

use crate::model::python_repr_string;
use std::path::Path;

/// Read a file as Python's `Path.read_text(encoding="utf-8")` does.
///
/// Decode, then translate line endings — that order, because text mode decodes
/// before it translates and `UnicodeDecodeError`'s positions are byte offsets
/// into the undecoded input.
///
/// The error is Python's message body, ready to interpolate into
/// `Error processing conversation file {path}: {error}`.
pub fn read_text(path: &Path) -> Result<String, String> {
    let bytes = std::fs::read(path).map_err(|error| python_io_error(&error, path))?;
    decode_utf8(&bytes).map(universal_newlines)
}

/// Translate line endings the way Python's text mode does.
///
/// `open(..., newline=None)` is universal-newline mode: `\r\n` and a lone `\r`
/// both become `\n` before any caller sees a character. Every product read of a
/// session file is text mode, so this is the only line-ending policy the oracle
/// has.
///
/// It changes two answers downstream. `session::decode_entries` splits on `\n`
/// alone, so a file terminated with lone `\r` is one unparseable line and the
/// session decodes to nothing; and `raw_transcript` neither splits on `\r` nor
/// strips one, so a CRLF transcript keeps a `\r` at the end of every rendered
/// line.
///
/// The guard is an economy, not caution: **0 of 5,061 files in the real pool
/// carry a literal `\r`** (measured 2026-09-01), and the search route reads every
/// candidate, so the common path allocates nothing.
///
/// ```
/// use _native::python_io::universal_newlines;
/// assert_eq!(universal_newlines("a\r\nb".to_string()), "a\nb");
/// assert_eq!(universal_newlines("a\rb".to_string()), "a\nb");
/// assert_eq!(universal_newlines("a\n\rb".to_string()), "a\n\nb");
/// ```
pub fn universal_newlines(content: String) -> String {
    if !content.contains('\r') {
        return content;
    }
    content.replace("\r\n", "\n").replace('\r', "\n")
}

pub fn python_io_error(error: &std::io::Error, path: &Path) -> String {
    let path = path.to_string_lossy();
    match error.raw_os_error() {
        Some(errno) => {
            let rendered = error.to_string();
            let suffix = format!(" (os error {errno})");
            let message = rendered.strip_suffix(&suffix).unwrap_or(&rendered);
            format!(
                "[Errno {errno}] {message}: {}",
                python_repr_string(&path)
            )
        }
        None => format!("{}: {}", error, python_repr_string(&path)),
    }
}

pub fn decode_utf8(bytes: &[u8]) -> Result<String, String> {
    match std::str::from_utf8(bytes) {
        Ok(content) => Ok(content.to_string()),
        Err(error) => {
            let start = error.valid_up_to();
            let byte = bytes.get(start).copied().unwrap_or_default();
            if error.error_len().is_none() {
                let end = bytes.len().saturating_sub(1);
                let subject = if end > start {
                    format!("bytes in position {start}-{end}")
                } else {
                    format!("byte 0x{byte:02x} in position {start}")
                };
                return Err(format!(
                    "'utf-8' codec can't decode {subject}: unexpected end of data"
                ));
            }
            let invalid_length = error.error_len().expect("handled truncated UTF-8");
            let end = start + invalid_length - 1;
            let subject = if end > start {
                format!("bytes in position {start}-{end}")
            } else {
                format!("byte 0x{byte:02x} in position {start}")
            };
            let reason = if matches!(byte, 0xc2..=0xf4) {
                "invalid continuation byte"
            } else {
                "invalid start byte"
            };
            Err(format!(
                "'utf-8' codec can't decode {subject}: {reason}"
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    static TEMPORARY_DIRECTORY_ID: AtomicU64 = AtomicU64::new(0);

    struct TemporaryDirectory(PathBuf);

    impl TemporaryDirectory {
        fn new() -> Self {
            let identifier = TEMPORARY_DIRECTORY_ID.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "chats-native-newline-{}-{identifier}",
                std::process::id()
            ));
            fs::create_dir_all(&path).expect("create temporary directory");
            Self(path)
        }

        fn write(&self, name: &str, bytes: &[u8]) -> PathBuf {
            let path = self.0.join(name);
            fs::write(&path, bytes).expect("write fixture");
            path
        }
    }

    impl Drop for TemporaryDirectory {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).expect("remove temporary directory");
        }
    }

    /// The pre-fix reader, kept so the gate below is proved to catch it.
    ///
    /// This is exactly what `read_text` was before F1: bytes, decode, no
    /// translation.
    fn read_text_without_translation(path: &std::path::Path) -> Result<String, String> {
        let bytes = std::fs::read(path).map_err(|error| python_io_error(&error, path))?;
        decode_utf8(&bytes)
    }

    /// **This gate is authored, not harvested.** 0 of 5,061 `.jsonl` files under
    /// `~/.claude`, `~/.pi` and `~/.codex` carry a literal `\r` (measured
    /// 2026-09-01), so no corpus of any size can grade universal-newline
    /// translation. The expected strings below were transcribed from a run of
    /// `Path.read_text(encoding="utf-8")` at oracle revision `8cb4c5f`, recorded
    /// by `teammates/parity-finisher/probes/make_newline_fixtures.py`.
    #[test]
    fn read_text_translates_both_line_endings_python_translates() {
        let directory = TemporaryDirectory::new();
        let cases: [(&str, &[u8], &str); 6] = [
            ("crlf", b"a\r\nb", "a\nb"),
            ("lone-cr", b"a\rb", "a\nb"),
            ("cr-then-lf-are-two-endings", b"a\n\rb", "a\n\nb"),
            ("no-carriage-return", b"a\nb", "a\nb"),
            ("trailing-cr", b"a\r", "a\n"),
            // Two endings, not three: the `\r\n` pass must run first. Replacing
            // lone `\r` before `\r\n` gives `"\n\n\n"` here and agrees with
            // Python on every other case in this list.
            ("cr-then-crlf", b"\r\r\n", "\n\n"),
        ];
        for (name, bytes, expected) in cases {
            let path = directory.write(name, bytes);
            assert_eq!(
                read_text(&path).expect("read"),
                expected,
                "read_text models Python text mode, which translates \\r\\n and a \
                 lone \\r to \\n before any caller sees a character; case {name:?} \
                 came back untranslated"
            );
        }
    }

    /// The falsifier for the gate above. A reader that skips translation must be
    /// caught, and the two shapes it is caught on are named here so a future
    /// reader can tell **which** mechanism the gate is sensitive to rather than
    /// only that it goes red.
    #[test]
    fn the_gate_catches_a_reader_that_skips_translation() {
        let directory = TemporaryDirectory::new();
        let crlf = directory.write("crlf", b"a\r\nb");
        let lone = directory.write("lone-cr", b"a\rb");

        assert_eq!(
            read_text_without_translation(&crlf).expect("read"),
            "a\r\nb",
            "the falsifier must reproduce the pre-F1 behaviour it stands for: a \
             CRLF file keeps its \\r. If this line fails, the falsifier stopped \
             being wrong and the test below proves nothing."
        );
        assert_eq!(
            read_text_without_translation(&lone).expect("read"),
            "a\rb",
            "the falsifier must reproduce the pre-F1 behaviour it stands for: a \
             lone \\r survives as a character rather than becoming a line break."
        );
        assert_ne!(
            read_text_without_translation(&lone).expect("read"),
            read_text(&lone).expect("read"),
            "the gate is blind: an untranslated read and a translated read agree \
             on a lone-\\r file, so nothing here would catch the F1 regression"
        );
    }

    /// A decode failure reports Python's message and is not reached by
    /// translation, because text mode decodes first.
    #[test]
    fn an_undecodable_file_reports_pythons_message_and_never_reaches_translation() {
        let directory = TemporaryDirectory::new();
        let path = directory.write("invalid", b"a\r\n\xff");
        assert_eq!(
            read_text(&path).expect_err("invalid UTF-8 must fail"),
            "'utf-8' codec can't decode byte 0xff in position 3: invalid start byte",
            "the decode error must be Python's, with byte offsets into the \
             undecoded input — translating first would move position 3"
        );
    }
}
