//! Claude subagent transcripts: discovery and identity.
//!
//! Every subagent, fork, and teammate transcript lives under
//! `<project>/<session_id>/subagents/agent-<agentId>.jsonl`, with a sibling
//! `.meta.json`. Mirrors Python's `find_agent_files_for_session` and
//! `read_claude_subagent_metadata`.

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};

use regex::Regex;
use serde_json::{Map, Value};
use std::sync::OnceLock;

/// The transcripts that belong to the session stored at `session_file`, sorted by path.
///
/// A transcript belongs when its first line carries the session's `sessionId`, or is a
/// fork's `fork-context-ref` naming it as `parentSessionId`. A transcript that another
/// session's directory links to fails that check and is left out.
pub fn subagent_transcripts(session_file: &Path, entries: &[Map<String, Value>]) -> Vec<PathBuf> {
    let mut children = sidechain_transcripts(session_file);
    children.extend(background_forks(session_file, entries));
    children.extend(herdr_forks(session_file, entries));
    children.sort();
    children.dedup();
    children
}

fn sidechain_transcripts(session_file: &Path) -> Vec<PathBuf> {
    let (Some(parent), Some(session_id)) = (
        session_file.parent(),
        session_file.file_stem().and_then(|stem| stem.to_str()),
    ) else {
        return Vec::new();
    };
    let parent_agent = session_id.strip_prefix("agent-");
    let root_id = if parent_agent.is_some() {
        parent.parent().and_then(|path| path.file_name()).and_then(|name| name.to_str()).unwrap_or_default()
    } else { session_id };
    let directory = if parent_agent.is_some() { parent.to_path_buf() } else { parent.join(session_id).join("subagents") };
    let Ok(listing) = std::fs::read_dir(directory) else {
        return Vec::new();
    };
    let mut transcripts: Vec<PathBuf> = listing
        .filter_map(Result::ok)
        .map(|item| item.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("agent-") && name.ends_with(".jsonl"))
        })
        .filter(|path| first_entry_anchors(path, root_id))
        .filter(|path| {
            let metadata = std::fs::read_to_string(path.with_extension("meta.json")).ok()
                .and_then(|text| serde_json::from_str::<Value>(&text).ok());
            metadata.as_ref().and_then(|value| value.get("parentAgentId")).and_then(Value::as_str) == parent_agent
        })
        .collect();
    transcripts.sort();
    transcripts
}

fn first_entry_anchors(transcript: &Path, session_id: &str) -> bool {
    let Ok(file) = std::fs::File::open(transcript) else {
        return false;
    };
    let mut first_line = String::new();
    if BufReader::new(file).read_line(&mut first_line).is_err() {
        return false;
    }
    let Ok(Value::Object(entry)) = serde_json::from_str::<Value>(first_line.trim()) else {
        return false;
    };
    let field = |key: &str| entry.get(key).and_then(Value::as_str);
    field("sessionId") == Some(session_id)
        || (field("type") == Some("fork-context-ref") && field("parentSessionId") == Some(session_id))
}

fn background_forks(session_file: &Path, entries: &[Map<String, Value>]) -> Vec<PathBuf> {
    static RECEIPT: OnceLock<Regex> = OnceLock::new();
    let receipt = RECEIPT.get_or_init(|| Regex::new(
        r"^<local-command-stdout>session running · .* · ([0-9a-f]{8})</local-command-stdout>$"
    ).expect("background fork receipt"));
    let mut prefixes = Vec::new();
    let mut pending = false;
    for entry in crate::session::claude_own_entries(entries) {
        if entry.get("type").and_then(Value::as_str) != Some("system")
            || entry.get("subtype").and_then(Value::as_str) != Some("local_command") {
            continue;
        }
        let content = entry.get("content").and_then(Value::as_str).unwrap_or_default();
        if content.contains("<command-name>") {
            pending = content.contains("<command-name>/fork</command-name>");
            continue;
        }
        if pending && let Some(captured) = receipt.captures(content) {
            prefixes.push(captured[1].to_string());
        }
        pending = false;
    }
    let Some(directory) = session_file.parent() else { return Vec::new() };
    let session_id = session_file.file_stem().and_then(|stem| stem.to_str());
    let candidates: Vec<_> = std::fs::read_dir(directory).into_iter().flatten()
        .filter_map(Result::ok).map(|entry| entry.path()).collect();
    prefixes.iter().filter_map(|prefix| {
        let matched: Vec<_> = candidates.iter().filter(|path| {
            path.extension().and_then(|value| value.to_str()) == Some("jsonl")
                && path.file_stem().and_then(|value| value.to_str()).is_some_and(|value| value.starts_with(prefix))
        }).collect();
        if matched.len() != 1 || matched[0] == session_file { return None; }
        let child = matched[0];
        let content = crate::python_io::read_text(child).ok()?;
        let child_entries = crate::session::decode_entries(&content);
        (crate::session::claude_forked_from(&child_entries).as_deref() == session_id).then(|| child.clone())
    }).collect()
}

fn herdr_forks(session_file: &Path, entries: &[Map<String, Value>]) -> Vec<PathBuf> {
    let mut calls = std::collections::HashMap::<String, String>::new();
    let mut completed = Vec::new();
    for entry in crate::session::claude_own_entries(entries) {
        let Some(content) = entry.get("message").and_then(|value| value.get("content")).and_then(Value::as_array) else { continue };
        for block in content {
            if entry.get("type").and_then(Value::as_str) == Some("assistant")
                && block.get("type").and_then(Value::as_str) == Some("tool_use")
                && block.get("name").and_then(Value::as_str) == Some("Bash") {
                if let (Some(identity), Some(command)) = (block.get("id").and_then(Value::as_str), block.get("input").and_then(|value| value.get("command")).and_then(Value::as_str)) {
                    calls.insert(identity.to_string(), command.to_string());
                }
            }
            if entry.get("type").and_then(Value::as_str) == Some("user")
                && block.get("type").and_then(Value::as_str) == Some("tool_result")
                && block.get("is_error").and_then(Value::as_bool) != Some(true) {
                if let Some(command) = block.get("tool_use_id").and_then(Value::as_str).and_then(|identity| calls.get(identity)) {
                    let output = crate::session::extract_text_blocks(block.get("content").unwrap_or(&Value::Null)).join("\n");
                    completed.push((command.clone(), output));
                }
            }
        }
    }
    let pairs: Vec<_> = completed.iter().map(|(command, output)| (command.as_str(), output.as_str())).collect();
    let launches = crate::herdr_launches::verified_herdr_forks(&pairs, crate::session::Provider::Claude);
    let Some(projects) = session_file.ancestors().find(|path| {
        path.file_name().and_then(|name| name.to_str()) == Some("projects")
            && path.parent().and_then(Path::file_name).and_then(|name| name.to_str()) == Some(".claude")
    }) else { return Vec::new() };
    let directories: Vec<_> = std::fs::read_dir(projects).into_iter().flatten().filter_map(Result::ok).map(|entry| entry.path()).collect();
    launches.iter().filter_map(|(child_id, source)| {
        if child_id.len() != 36 || !child_id.chars().all(|character| character.is_ascii_hexdigit() || character == '-') { return None; }
        let candidates: Vec<_> = directories.iter().map(|directory| directory.join(format!("{child_id}.jsonl"))).filter(|path| path.is_file()).collect();
        if candidates.len() != 1 || candidates[0] == session_file { return None; }
        let child = &candidates[0];
        let content = crate::python_io::read_text(child).ok()?;
        let records = crate::session::decode_entries(&content);
        (crate::session::claude_forked_from(&records).as_deref() == Some(source)).then(|| child.clone())
    }).collect()
}

/// A transcript's `(agentType, name)` from its `.meta.json` sidecar.
pub fn subagent_type_and_name(transcript: &Path) -> (Option<String>, Option<String>) {
    let meta = std::fs::read_to_string(transcript.with_extension("meta.json"))
        .ok()
        .and_then(|content| serde_json::from_str::<Value>(&content).ok());
    let field = |key: &str| {
        meta.as_ref()
            .and_then(|meta| meta.get(key))
            .and_then(Value::as_str)
            .map(str::to_string)
    };
    (field("agentType"), field("name"))
}
