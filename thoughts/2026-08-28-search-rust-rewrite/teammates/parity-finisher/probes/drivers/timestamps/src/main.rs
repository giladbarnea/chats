//! The three native answers the timestamp-parity probe compares against Python.
//!
//! Links the crate by path so it grades the production functions rather than a
//! copy. Takes one session path, emits one JSON object whose values are formatted
//! the way Python's `str(...)` formats its own — so the comparison is over the
//! same strings on both sides rather than over two encodings of the same idea.
use std::path::Path;

fn main() {
    let path = std::env::args().nth(1).expect("a session path");
    let path = Path::new(&path);
    // `str(datetime)` in Python: "YYYY-MM-DD HH:MM:SS", dropping a zero
    // microsecond component exactly as Python does.
    let render = |stamp: Option<chrono::NaiveDateTime>| match stamp {
        Some(value) if value.and_utc().timestamp_subsec_micros() == 0 => {
            value.format("%Y-%m-%d %H:%M:%S").to_string()
        }
        Some(value) => value.format("%Y-%m-%d %H:%M:%S%.6f").to_string(),
        None => "None".to_string(),
    };
    let answers = serde_json::json!({
        "first_timestamp": render(_native::pool_filter::first_timestamp(path)),
        "last_timestamp": render(_native::pool_filter::last_timestamp(path)),
        "cwd": _native::inventory::cwd_from_path(path).unwrap_or_else(|| "None".to_string()),
    });
    println!("{answers}");
}
