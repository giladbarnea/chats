//! Codex launch provenance, mirrored by `chats.codex_delegation`.

use serde_json::{Map, Value};

/// A spawner proved by the child header, not an ordinary fork's context source.
///
/// ```
/// use _native::codex_delegation::delegated_parent;
/// let header = serde_json::json!({"thread_source":"agent_forked_thread", "forked_from_id":"parent"});
/// assert_eq!(delegated_parent(header.as_object().unwrap()), Some("parent"));
/// let branch = serde_json::json!({"thread_source":"user", "forked_from_id":"parent"});
/// assert_eq!(delegated_parent(branch.as_object().unwrap()), None);
/// ```
pub fn delegated_parent(header: &Map<String, Value>) -> Option<&str> {
    let field = if header.get("thread_source").and_then(Value::as_str) == Some("agent_forked_thread") {
        "forked_from_id"
    } else {
        "parent_thread_id"
    };
    header.get(field).and_then(Value::as_str).filter(|value| !value.is_empty())
}

/// Join successful Herdr execution events owned by this thread, not inherited events.
///
/// ```
/// use _native::codex_delegation::verified_cli_forks;
/// assert!(verified_cli_forks(&[], "parent").is_empty());
/// ```
pub fn verified_cli_forks(entries: &[Map<String, Value>], writer: &str) -> Vec<(String, String)> {
    let mut commands = Vec::new();
    for entry in entries {
        let Some(payload) = entry.get("payload").and_then(Value::as_object) else { continue };
        if entry.get("type").and_then(Value::as_str) != Some("event_msg")
            || payload.get("thread_id").and_then(Value::as_str) != Some(writer)
            || payload.get("type").and_then(Value::as_str) != Some("item_completed")
        {
            continue;
        }
        let Some(item) = payload.get("item") else { continue };
        if item.get("type").and_then(Value::as_str) != Some("CommandExecution")
            || item.get("status").and_then(Value::as_str) != Some("completed")
            || item.get("exit_code").and_then(Value::as_i64) != Some(0)
        {
            continue;
        }
        let Some(command) = item.get("command").and_then(Value::as_array).and_then(|argv| argv.last()).and_then(Value::as_str) else {
            continue;
        };
        let output = item.get("aggregated_output").and_then(Value::as_str).unwrap_or("");
        commands.push((command, output));
    }
    crate::herdr_launches::verified_herdr_forks(&commands, crate::session::Provider::Codex)
}
