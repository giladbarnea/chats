//! Exact Herdr launch-receipt joins, mirrored by `chats.herdr_launches`.

use std::collections::HashMap;
use std::path::Path;

use serde_json::Value;

use crate::session::Provider;

fn herdr_action(command: &str) -> Option<(&str, &str)> {
    let mut command = command.trim();
    for quote in ['\'', '"'] {
        let prefix = format!("zshi -c {quote}");
        if let Some(inner) = command.strip_prefix(&prefix).and_then(|inner| inner.strip_suffix(quote)) {
            command = inner;
            break;
        }
    }
    if command.chars().any(|character| "'\"`;$&|<>\\(){}*?[]\n\r".contains(character)) {
        return None;
    }
    let arguments: Vec<&str> = command.split_whitespace().collect();
    if arguments.len() < 4 || arguments[..2] != ["herdr", "agent"] || !matches!(arguments[2], "start" | "get") {
        return None;
    }
    Some((arguments[2], arguments[3]))
}

fn fork_source(arguments: &[Value], provider: Provider) -> Option<&str> {
    if Path::new(arguments.first()?.as_str()?).file_name()?.to_str()? != provider.as_str() {
        return None;
    }
    if provider == Provider::Claude {
        if !arguments.iter().any(|value| value.as_str() == Some("--fork-session")) {
            return None;
        }
        return arguments.windows(2)
            .filter(|pair| matches!(pair[0].as_str(), Some("--resume") | Some("-r")))
            .find_map(|pair| pair[1].as_str().filter(|value| !value.starts_with('-')));
    }
    let command = &arguments[1..];
    let command = if command.first().and_then(Value::as_str) == Some("exec") {
        &command[1..]
    } else {
        command
    };
    if provider != Provider::Codex || command.first().and_then(Value::as_str) != Some("fork") {
        return None;
    }
    command.get(1)?.as_str().filter(|value| !value.starts_with('-'))
}

/// Join successful starts to exact terminal identities, returning (child, context source).
/// Callers own execution-success and writer checks, and must verify child headers.
///
/// ```
/// use _native::{herdr_launches::verified_herdr_forks, session::Provider};
/// assert!(verified_herdr_forks(&[], Provider::Codex).is_empty());
/// ```
pub fn verified_herdr_forks(commands: &[(&str, &str)], provider: Provider) -> Vec<(String, String)> {
    let mut starts = HashMap::<String, String>::new();
    let mut launches = Vec::new();
    for (command, output) in commands {
        let Some((action, target)) = herdr_action(command) else { continue };
        let Ok(receipt) = serde_json::from_str::<Value>(output) else { continue };
        if receipt.get("id").and_then(Value::as_str) != Some(format!("cli:agent:{action}").as_str()) {
            continue;
        }
        let Some(result) = receipt.get("result") else { continue };
        let Some(agent) = result.get("agent") else { continue };
        let Some(terminal) = agent.get("terminal_id").and_then(Value::as_str).filter(|value| !value.is_empty()) else {
            continue;
        };
        if ![agent.get("name").and_then(Value::as_str), agent.get("pane_id").and_then(Value::as_str), Some(terminal)].contains(&Some(target)) {
            continue;
        }
        let kind = result.get("type").and_then(Value::as_str);
        if kind == Some("agent_started") && action == "start" {
            starts.remove(terminal);
            let source = result.get("argv").and_then(Value::as_array).and_then(|arguments| fork_source(arguments, provider));
            starts.extend(source.map(|source| (terminal.to_string(), source.to_string())));
        }
        let Some(identity) = agent.get("agent_session") else { continue };
        if !matches!(kind, Some("agent_started") | Some("agent_info"))
            || identity.get("agent").and_then(Value::as_str) != Some(provider.as_str())
            || identity.get("kind").and_then(Value::as_str) != Some("id")
        {
            continue;
        }
        let Some(child) = identity.get("value").and_then(Value::as_str).filter(|value| !value.is_empty()) else {
            continue;
        };
        if let Some(source) = starts.remove(terminal) {
            launches.push((child.to_string(), source));
        }
    }
    launches
}
