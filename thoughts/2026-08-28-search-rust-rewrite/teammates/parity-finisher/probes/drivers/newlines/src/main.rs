//! The F1 differential driver: the production read path, then the production scan.
//!
//! Links the crate by path, so it grades the real `python_io::read_text` rather
//! than a copy of it. Reads one session path per line on stdin and emits one JSON
//! row per path: `[[role, text], ...]`, the same shape
//! `make_newline_fixtures.py` prints for Python.
//!
//! The read is `python_io::read_text` on purpose. `session-core`'s render driver
//! uses `std::fs::read_to_string`, which is why 2,436 Claude and 24,367 Pi cases
//! ran at zero mismatches while F1 was live: that driver bypasses the defective
//! function entirely.

use std::io::{self, BufRead, Write};
use std::path::Path;

use _native::search_confirm::scan_session;
use _native::visibility::ConversationFlags;

fn main() {
    let stdin = io::BufReader::new(io::stdin());
    let mut out = io::BufWriter::new(io::stdout());
    let home = std::env::var("HOME").expect("HOME");
    let flags = ConversationFlags::default();
    for line in stdin.lines() {
        let path = line.expect("line");
        let path = path.trim();
        if path.is_empty() {
            continue;
        }
        let rows: Vec<(String, String)> = match _native::python_io::read_text(Path::new(path)) {
            Ok(content) => match scan_session(Path::new(path), &content, &flags, Path::new(&home)) {
                Ok(scan) => scan
                    .messages
                    .iter()
                    .map(|message| (message.role.clone(), message.text.clone()))
                    .collect(),
                Err(error) => vec![("SCAN ERROR".to_string(), error)],
            },
            Err(error) => vec![("READ ERROR".to_string(), error)],
        };
        writeln!(out, "{}", serde_json::to_string(&rows).expect("encode")).expect("write");
    }
}
