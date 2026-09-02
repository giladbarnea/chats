//! Driver for `branch_map_differential.py` (BRANCH_BIN).
//!
//! Reads one JSON-encoded session path per line; emits one JSON object per line, the
//! branch map that `session::branch_map` produces for that file. Links the crate by
//! path so the comparison is against the real code rather than a copy.
use std::io::{self, BufRead, Write};

use _native::session::{branch_map, decode_entries};

fn main() {
    let stdin = io::BufReader::new(io::stdin());
    let mut out = io::BufWriter::new(io::stdout());
    for line in stdin.lines() {
        let path: String = serde_json::from_str(&line.expect("stdin line")).expect("json path");
        let content = std::fs::read_to_string(&path).unwrap_or_default();
        let map = branch_map(&decode_entries(&content));
        writeln!(out, "{}", serde_json::to_string(&map).expect("encode")).expect("write");
    }
}
