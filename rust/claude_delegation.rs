//! Delivered Claude agent reports retain their originating dispatch attribution.

use std::collections::HashSet;
use std::sync::OnceLock;
use regex::Regex;
use serde_json::{Map, Number, Value};
use crate::model::{Message, MessageType};

#[derive(Default)]
pub struct AgentOrigins {
    calls: HashSet<String>,
    tasks: HashSet<String>,
    user_forks: HashSet<(String, String)>,
}

pub fn agent_origins(entries: &[Map<String, Value>]) -> AgentOrigins {
    let calls: HashSet<String> = entries.iter()
        .filter(|entry| entry.get("type").and_then(Value::as_str) == Some("assistant"))
        .filter_map(|entry| entry.get("message")?.get("content")?.as_array())
        .flatten()
        .filter(|block| block.get("type").and_then(Value::as_str) == Some("tool_use")
            && block.get("name").and_then(Value::as_str) == Some("Agent"))
        .filter_map(|block| block.get("id")?.as_str().map(str::to_string)).collect();
    let mut origins = AgentOrigins { calls, ..AgentOrigins::default() };
    let mut pending = false;
    static FORK: OnceLock<Regex> = OnceLock::new();
    let fork = FORK.get_or_init(|| Regex::new(r"^<local-command-stdout>⑂ forked (.+) \(([0-9a-f]{4})\)</local-command-stdout>$").expect("user fork receipt"));
    for entry in entries {
        if entry.get("type").and_then(Value::as_str) == Some("user") {
            let linked = entry.get("message").and_then(|value| value.get("content")).and_then(Value::as_array)
                .is_some_and(|blocks| blocks.iter().any(|block|
                    block.get("type").and_then(Value::as_str) == Some("tool_result")
                    && block.get("tool_use_id").and_then(Value::as_str).is_some_and(|identity| origins.calls.contains(identity))
                    && block.get("is_error").and_then(Value::as_bool) != Some(true)));
            if linked && let Some(task) = entry.get("toolUseResult").and_then(|value| value.get("agentId")).and_then(Value::as_str) {
                origins.tasks.insert(task.to_string());
            }
        }
        if entry.get("type").and_then(Value::as_str) != Some("system")
            || entry.get("subtype").and_then(Value::as_str) != Some("local_command") { continue; }
        let content = entry.get("content").and_then(Value::as_str).unwrap_or_default();
        if content.contains("<command-name>") {
            pending = ["/subtask", "/btw", "/fork"].iter().any(|name| content.contains(&format!("<command-name>{name}</command-name>")));
            continue;
        }
        if pending && let Some(captured) = fork.captures(content) {
            origins.user_forks.insert((captured[1].to_string(), captured[2].to_string()));
        }
        pending = false;
    }
    origins
}

fn field<'a>(body: &'a str, name: &str) -> &'a str {
    body.split_once(&format!("<{name}>"))
        .and_then(|(_, tail)| tail.split_once(&format!("</{name}>")))
        .map(|(value, _)| crate::session::python_strip(value)).unwrap_or_default()
}

pub fn notification_messages(entry: &Map<String, Value>, origins: &AgentOrigins, index: usize) -> Vec<Message> {
    if entry.get("origin").and_then(|value| value.get("kind")).and_then(Value::as_str) != Some("task-notification") {
        return Vec::new();
    }
    let Some(content) = entry.get("message").and_then(|value| value.get("content")).and_then(Value::as_str) else {
        return Vec::new();
    };
    static BLOCK: OnceLock<Regex> = OnceLock::new();
    let block = BLOCK.get_or_init(|| Regex::new(r"(?s)<task-notification>(.*?)</task-notification>").expect("task notification blocks"));
    block.captures_iter(content).filter_map(|captured| {
        let body = &captured[1];
        let task = field(body, "task-id");
        let user_fork = task.strip_prefix('a').unwrap_or(task).rsplit_once('-').is_some_and(|(slug, suffix)| {
            let ending: String = suffix.chars().rev().take(4).collect::<String>().chars().rev().collect();
            origins.user_forks.contains(&(slug.to_string(), ending))
        });
        let proven = origins.calls.contains(field(body, "tool-use-id")) || origins.tasks.contains(task) || user_fork;
        let result = field(body, "result");
        let text = if result.is_empty() { field(body, "summary") } else { result };
        if !proven || task.is_empty() || text.is_empty() { return None; }
        let mut message = Message::new(MessageType::Agent, "agent".to_string(), Number::from(index));
        message.agent_id = Some(task.to_string());
        message.text = text.to_string();
        message.timestamp = entry.get("timestamp").and_then(Value::as_str).map(str::to_string);
        let status = field(body, "status");
        message.status = (!status.is_empty()).then(|| status.to_string());
        Some(message)
    }).collect()
}
