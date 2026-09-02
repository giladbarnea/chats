use std::io::{self, BufRead, Write};
use std::path::Path;
use _native::search_confirm::{rendered_for_search, scan_session};
use _native::tool_filter::ToolVisibility;
use _native::visibility::ConversationFlags;

fn flags_for(name: &str) -> ConversationFlags {
    let mut flags = ConversationFlags::default();
    match name {
        "with-tools" => flags.show_tools = ToolVisibility::All(true),
        "tools-and-agents" => {
            flags.show_tools = ToolVisibility::All(true);
            flags.show_agents = true;
        }
        "thinking" => flags.show_thinking = true,
        "branches" => flags.show_branches = true,
        "shortened" => {
            flags.show_tools = ToolVisibility::All(true);
            flags.shorten = true;
            flags.shorten_max_chars = 120;
        }
        "progressive" => {
            flags.show_tools = ToolVisibility::All(true);
            flags.shorten = true;
            flags.shorten_max_chars = 128;
            flags.shorten_progressive = true;
        }
        _ => {}
    }
    flags
}

fn main() {
    let stdin = io::BufReader::new(io::stdin());
    let mut out = io::BufWriter::new(io::stdout());
    let home = std::env::var("HOME").expect("HOME");
    for line in stdin.lines() {
        let case: serde_json::Value = serde_json::from_str(&line.expect("line")).expect("case");
        let path = case["path"].as_str().expect("path");
        // Content from the snapshot, path from the original: Python classifies
        // providers by location, so a naive snapshot fixes one intermittent
        // failure and creates a systematic one.
        let origin = case["origin"].as_str().unwrap_or(path);
        let flags = flags_for(case["flags"].as_str().expect("flags"));
        let content = std::fs::read_to_string(path).unwrap_or_default();

        // The production pipeline itself, not a re-assembly of its steps. A gate
        // that reimplements what it grades agrees with a wrong implementation for
        // the same reason it agrees with a right one.
        let payload: Vec<String> =
            match scan_session(Path::new(origin), &content, &flags, Path::new(&home)) {
                Ok(scan) => match rendered_for_search(&scan.messages, &flags) {
                    Ok((rendered, _)) => rendered,
                    Err(error) => vec![format!("RENDER ERROR: {error}")],
                },
                Err(error) => vec![format!("SCAN ERROR: {error}")],
            };
        let detail = std::env::var("DETAIL").is_ok();
        let rows: Vec<String> = if detail {
            payload
        } else {
            // Digest per message: the comparison is exact, the rows stay small, and
            // a megabyte-wide line cannot truncate the protocol.
            payload.iter().map(|text| format!("{:016x}", fxhash(text))).collect()
        };
        writeln!(out, "{}", serde_json::to_string(&rows).expect("encode")).expect("write");
    }
}

/// A small, stable, non-cryptographic digest. Only equality matters here.
fn fxhash(value: &str) -> u64 {
    let mut hash: u64 = 0xcbf29ce484222325;
    for byte in value.as_bytes() {
        hash ^= *byte as u64;
        hash = hash.wrapping_mul(0x100000001b3);
    }
    hash
}
