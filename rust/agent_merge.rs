//! `--agents` merges each delegated child's own transcript into its parent.
//!
//! Ported from `_merge_agent_messages`, `_build_subagent_block` and
//! `_interleave_subagent_blocks` in `src/chats/commands/parse.py`, so search
//! confirms a parent against the same timeline parse prints. Discovery, identity
//! and the records a forked child copied from its parent are per provider, in the
//! three `match`es below; everything else is provider-neutral.

use std::borrow::Cow;
use std::collections::{HashMap, HashSet};
use std::io::BufRead;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

use serde_json::{Map, Number, Value};

use crate::model::{Message, MessageType, Tool};
use crate::session::{self, Provider};
use crate::visibility::ConversationFlags;

type Entries = [Map<String, Value>];

/// Identity of a delegated child, read from its transcript.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct SubagentMetadata {
    pub agent_id: Option<String>,
    pub name: Option<String>,
    pub subagent_type: Option<String>,
}

/// The parent's timeline with every delegated child's block placed at its start.
pub fn merge(
    provider: Provider,
    path: &Path,
    entries: &Entries,
    messages: Vec<Message>,
    flags: &ConversationFlags,
    home: &Path,
) -> Result<Vec<Message>, String> {
    let root_entries = own_entries(provider, entries);
    let mut pending = subagent_transcripts(provider, path, &root_entries, home);
    if pending.is_empty() {
        return Ok(messages);
    }
    pending.reverse();
    let mut visited = HashSet::from([session_identity(provider, path, entries)]);
    let mut visited_paths = HashSet::from([path.canonicalize().map_err(|error| error.to_string())?]);
    let mut blocks = Vec::new();
    while let Some(transcript) = pending.pop() {
        let canonical_path = transcript.canonicalize().map_err(|error| error.to_string())?;
        if !visited_paths.insert(canonical_path) {
            continue;
        }
        let content = crate::python_io::read_text(&transcript)?;
        let entries = session::decode_entries(&content);
        let path_provider = crate::inventory::classify_native_session_path_impl(&transcript, home)
            .map(|provider| crate::search_confirm::ProviderBridge::from(provider).0);
        let provider = session::select_provider(path_provider, entries.first())?;
        if !visited.insert(session_identity(provider, &transcript, &entries)) {
            continue;
        }
        let own = own_entries(provider, &entries);
        pending.extend(subagent_transcripts(provider, &transcript, &own, home).into_iter().rev());
        let messages = parse(provider, &own, flags);
        if !messages.first().is_some_and(|message| message.timestamp.as_deref().is_some_and(|value| !value.is_empty())) {
            continue;
        }
        let block = build_block(messages, subagent_metadata(provider, &transcript, &entries));
        if !block.is_empty() {
            blocks.push(block);
        }
    }
    if blocks.is_empty() {
        return Ok(messages);
    }
    let mut merged = interleave(messages, blocks);
    for (index, message) in merged.iter_mut().enumerate() {
        message.original_index = Number::from(index + 1);
    }
    Ok(merged)
}

fn session_identity(provider: Provider, path: &Path, entries: &Entries) -> (&'static str, String) {
    let identifier = crate::search_confirm::native_session_id(provider, entries.first(), path)
        .unwrap_or_else(|| path.file_stem().unwrap_or_default().to_string_lossy().into_owned());
    (provider.as_str(), identifier)
}

pub fn parse(provider: Provider, entries: &Entries, flags: &ConversationFlags) -> Vec<Message> {
    match provider {
        Provider::Claude => session::parse_claude(entries, flags),
        Provider::Pi => session::parse_pi(entries, flags),
        Provider::Codex => crate::codex::parse_codex(entries, flags),
    }
}

// ----------------------------------------------------------------- per provider

/// The child transcripts delegated from this session. Mirrors Python's
/// `resolve.find_subagent_transcripts`.
fn subagent_transcripts(provider: Provider, path: &Path, entries: &Entries, home: &Path) -> Vec<PathBuf> {
    match provider {
        Provider::Claude => crate::claude_agents::subagent_transcripts(path, entries),
        Provider::Pi => session::pi_delegated_children(path, entries),
        Provider::Codex => codex_children_for(entries, home),
    }
}

/// A child's identity. Mirrors Python's `resolve.read_subagent_metadata`.
fn subagent_metadata(provider: Provider, transcript: &Path, entries: &Entries) -> SubagentMetadata {
    match provider {
        Provider::Claude => {
            let is_sidechain = transcript.file_name().and_then(|name| name.to_str())
                .is_some_and(|name| name.starts_with("agent-"));
            if !is_sidechain {
                return SubagentMetadata {
                    agent_id: transcript.file_stem().and_then(|name| name.to_str()).map(str::to_string),
                    subagent_type: Some("fork".to_string()),
                    ..SubagentMetadata::default()
                };
            }
            let (subagent_type, name) = crate::claude_agents::subagent_type_and_name(transcript);
            SubagentMetadata {
                agent_id: transcript.file_stem().and_then(|name| name.to_str())
                    .map(|name| name.trim_start_matches("agent-").to_string()),
                subagent_type, name, ..SubagentMetadata::default()
            }
        }
        Provider::Pi => {
            let identity = session::pi_child_identity(entries);
            SubagentMetadata {
                agent_id: identity.agent_id,
                name: identity.name,
                subagent_type: Some(identity.subagent_type.to_string()),
            }
        }
        Provider::Codex => codex_metadata(entries),
    }
}

/// The child's records without those it copied from its parent, which the
/// parent's own timeline already shows. Mirrors the adapters' `own_entries`.
fn own_entries(provider: Provider, entries: &Entries) -> Cow<'_, Entries> {
    match provider {
        Provider::Claude => Cow::Borrowed(session::claude_own_entries(entries)),
        Provider::Pi if session::pi_inherited_prefix_end(entries) > 0 => Cow::Owned(session::pi_own_entries(entries)),
        Provider::Codex => {
            let thread = crate::codex::Thread::from_header(entries.first());
            if thread.first_own_ordinal == 0 {
                return Cow::Borrowed(entries);
            }
            Cow::Owned(entries
                .iter()
                .take(1)
                .chain(entries.iter().skip(1).filter(|entry| !thread.is_inherited(entry)))
                .cloned()
                .collect())
        }
        _ => Cow::Borrowed(entries),
    }
}

// --------------------------------------------------------------------- Codex arm

/// Header-proven edges and the identities needed to validate parent-side receipts.
#[derive(Default)]
struct CodexChildren {
    children: HashMap<String, Vec<(PathBuf, String)>>,
    sessions: HashMap<String, (PathBuf, Option<String>)>,
}

fn codex_children(home: &Path) -> Arc<CodexChildren> {
    static INDEX: OnceLock<Mutex<HashMap<PathBuf, Arc<CodexChildren>>>> = OnceLock::new();
    let mut indexes = INDEX.get_or_init(Default::default).lock().expect("index lock");
    indexes
        .entry(home.to_path_buf())
        .or_insert_with(|| Arc::new(build_codex_children(home)))
        .clone()
}

fn build_codex_children(home: &Path) -> CodexChildren {
    let mut index = CodexChildren::default();
    for path in crate::inventory::read_recursive_provider_paths(&home.join(".codex").join("sessions")) {
        let Some(header) = codex_session_meta(&path) else { continue };
        let Some(id) = header.get("id").and_then(Value::as_str) else { continue };
        let context_source = header.get("forked_from_id").and_then(Value::as_str).map(str::to_string);
        index.sessions.insert(id.to_string(), (path.clone(), context_source));
        let Some(parent) = crate::codex_delegation::delegated_parent(&header) else { continue };
        index.children.entry(parent.to_string()).or_default().push((path, id.to_string()));
    }
    index
}

/// The payload of the file's first decodable entry when it is a `session_meta`.
/// Mirrors Python's `_read_codex_session_meta`.
fn codex_session_meta(path: &Path) -> Option<Map<String, Value>> {
    let reader = std::io::BufReader::new(std::fs::File::open(path).ok()?);
    for line in reader.lines() {
        let line = line.ok()?;
        let stripped = session::python_strip(&line);
        if stripped.is_empty() {
            continue;
        }
        let Ok(Value::Object(entry)) = serde_json::from_str::<Value>(stripped) else {
            continue;
        };
        if entry.get("type").and_then(Value::as_str) != Some("session_meta") {
            return None;
        }
        return entry.get("payload").and_then(Value::as_object).cloned();
    }
    None
}

/// Direct children from native headers and parent-owned CLI launch receipts.
fn codex_children_for(entries: &Entries, home: &Path) -> Vec<PathBuf> {
    let Some(session_id) = codex_header(entries).and_then(|header| header.get("id")).and_then(Value::as_str) else {
        return Vec::new();
    };
    let index = codex_children(home);
    let mut proven: Vec<PathBuf> = index.children.get(session_id).into_iter().flatten()
        .map(|(path, _)| path.clone()).collect();
    for (child_id, source) in crate::codex_delegation::verified_cli_forks(entries, session_id) {
        let Some((child_path, context_source)) = index.sessions.get(&child_id) else { continue };
        if context_source.as_deref() == Some(source.as_str()) {
            proven.push(child_path.clone());
        }
    }
    proven
}

fn codex_header(entries: &Entries) -> Option<&Map<String, Value>> {
    entries
        .first()
        .filter(|entry| entry.get("type").and_then(Value::as_str) == Some("session_meta"))?
        .get("payload")?
        .as_object()
}

/// Identity from the spawn record.
/// Mirrors Python's `extract_codex_subagent_metadata`.
fn codex_metadata(entries: &Entries) -> SubagentMetadata {
    let header = codex_header(entries);
    let spawn = header
        .and_then(|header| header.get("source"))
        .and_then(Value::as_object)
        .and_then(|source| source.get("subagent"))
        .and_then(Value::as_object)
        .and_then(|subagent| subagent.get("thread_spawn"))
        .and_then(Value::as_object);
    let text = |map: Option<&Map<String, Value>>, key: &str| {
        map.and_then(|map| map.get(key)).and_then(Value::as_str).filter(|value| !value.is_empty()).map(str::to_string)
    };
    SubagentMetadata {
        agent_id: header.and_then(|header| header.get("id")).and_then(Value::as_str).map(str::to_string),
        name: text(spawn, "agent_nickname"),
        subagent_type: text(spawn, "agent_role"),
    }
}

// ------------------------------------------------------------ provider-neutral

/// Reframe a child transcript for display. Mirrors `_build_subagent_block`.
///
/// The initiating prompt (the last user text before the child's first reply)
/// becomes a `<subagent-task>` head, the leading prompt and context messages are
/// dropped, every later user message (an instruction given to the child) becomes
/// a `<subagent-task>` too, and every message is stamped with the child's identity.
fn build_block(messages: Vec<Message>, metadata: SubagentMetadata) -> Vec<Message> {
    let first_reply = messages.iter().position(is_reply).unwrap_or(messages.len());
    let agent_id = metadata
        .agent_id
        .or_else(|| messages.iter().find_map(|message| message.agent_id.clone()));
    let mut messages = messages;
    let rest = messages.split_off(first_reply);
    let leading = messages;

    let mut block = Vec::new();
    if let Some(task) = leading.iter().rev().map(|message| &message.text).find(|text| !text.is_empty()) {
        block.push(task_message(task.clone(), leading[0].timestamp.clone()));
    }
    block.extend(rest.into_iter().map(|message| {
        if message.role == "user" && !message.text.is_empty() {
            task_message(message.text, message.timestamp)
        } else {
            message
        }
    }));

    for message in &mut block {
        if message.role == "agent" && message.agent_id.is_some() && message.agent_id != agent_id {
            continue;
        }
        message.agent_id = agent_id.clone();
        message.name = metadata.name.clone();
        message.subagent_type = metadata.subagent_type.clone();
        // Python derives the wrapper from `agent_id` unless one was set explicitly,
        // which only the user and assistant defaults were not.
        if agent_id.as_deref().is_some_and(|id| !id.is_empty())
            && matches!(message.message_type, MessageType::UserMessage | MessageType::AssistantResponse)
        {
            message.message_type = MessageType::Agent;
        }
    }
    block
}

fn is_reply(message: &Message) -> bool {
    message.role != "user"
        && (!message.text.is_empty()
            || message.thinking.as_deref().is_some_and(|value| !value.is_empty())
            || message.plan.as_deref().is_some_and(|value| !value.is_empty())
            || message
                .tools
                .iter()
                .any(|tool| matches!(tool, Tool::Use(tool_use) if tool_use.name != "AdditionalContext")))
}

fn task_message(task: String, timestamp: Option<String>) -> Message {
    let mut message = Message::new(MessageType::AssistantResponse, "agent".to_string(), Number::from(0));
    message.subagent_task = Some(task);
    message.timestamp = timestamp;
    message
}

/// Place each block before the first parent message that does not predate it.
/// Mirrors `_interleave_subagent_blocks`.
fn interleave(messages: Vec<Message>, mut blocks: Vec<Vec<Message>>) -> Vec<Message> {
    let start = |block: &Vec<Message>| block[0].timestamp.clone().unwrap_or_default();
    blocks.sort_by_key(start);
    let mut pending = blocks.into_iter().peekable();
    let mut merged = Vec::new();
    for message in messages {
        if let Some(timestamp) = message.timestamp.as_deref().filter(|value| !value.is_empty()) {
            while pending.peek().is_some_and(|block| start(block).as_str() <= timestamp) {
                merged.extend(pending.next().expect("peeked"));
            }
        }
        merged.push(message);
    }
    merged.extend(pending.flatten());
    merged
}
