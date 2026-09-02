//! Dump every scalar value the Rust `regex` crate matches for each candidate class.
//!
//! Compared against CPython's answer by `../../character_class_parity.py`.
//! Measured rather than inferred: the crate documents `\s` as `\p{White_Space}`
//! and `\w` by UTS#18, CPython documents neither in those terms, so the only
//! honest comparison is two dumps.
//!
//! Columns: code, `\s`, `\w`, candidate-space, candidate-word.
use regex::Regex;

fn main() {
    let patterns = [
        r"^\s$",
        r"^\w$",
        r"^[\s\x{1C}-\x{1F}]$",
        r"^[\p{L}\p{Nd}\p{Nl}\p{No}_]$",
    ];
    let compiled: Vec<Regex> = patterns
        .iter()
        .map(|pattern| Regex::new(pattern).expect("pattern"))
        .collect();
    let mut buffer = [0u8; 4];
    for code in 0u32..=0x10FFFF {
        let Some(character) = char::from_u32(code) else {
            continue;
        };
        let text = character.encode_utf8(&mut buffer);
        let flags: Vec<u8> = compiled.iter().map(|r| r.is_match(text) as u8).collect();
        if flags.iter().any(|flag| *flag == 1) {
            println!(
                "{code}\t{}\t{}\t{}\t{}",
                flags[0], flags[1], flags[2], flags[3]
            );
        }
    }
}
