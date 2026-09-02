use regex::RegexBuilder;
use serde_json::{json, Value};
use std::fs;

/// Mirror of Python `compile_search_term`: try the pattern as a regex, fall back
/// to an escaped literal when the engine rejects it.
fn authority(pattern: &str, haystacks: &[String], case_sensitive: bool) -> Value {
    let build = |source: &str| {
        RegexBuilder::new(source)
            .multi_line(true)
            .dot_matches_new_line(true)
            .case_insensitive(!case_sensitive)
            .size_limit(usize::MAX >> 4)
            .build()
    };
    let (regex, compiled_as, error) = match build(pattern) {
        Ok(regex) => (regex, "regex", Value::Null),
        Err(err) => {
            let message = err.to_string();
            let escaped = regex::escape(pattern);
            (
                build(&escaped).expect("escaped literal must compile"),
                "literal-fallback",
                Value::String(message.lines().next().unwrap_or("").to_string()),
            )
        }
    };
    json!({
        "compiled_as": compiled_as,
        "compile_error": error,
        "matches": haystacks.iter().map(|h| regex.is_match(h)).collect::<Vec<bool>>(),
    })
}

fn main() {
    let path = std::env::args().nth(1).expect("probe file argument");
    let probes: Vec<Value> = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
    let mut out = Vec::new();
    for probe in &probes {
        let pattern = probe["pattern"].as_str().unwrap();
        let haystacks: Vec<String> = probe["haystacks"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().to_string())
            .collect();
        out.push(json!({
            "id": probe["id"],
            "insensitive": authority(pattern, &haystacks, false),
            "sensitive": authority(pattern, &haystacks, true),
        }));
    }
    println!("{}", serde_json::to_string_pretty(&json!({"results": out})).unwrap());
}
