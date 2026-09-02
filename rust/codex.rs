//! The Codex session decoder, the third and last of the three.
//!
//! Ported from `_parse_codex_jsonl_entries` and the `_*codex*` helpers in
//! `src/chats/parsing.py`. Its own module because `rust/session.rs` holds Claude
//! and Pi and is frozen.
//!
//! **What the corpus does and does not reach.** Measured over all 1,208 Codex
//! sessions on this machine, by payload type:
//!
//! ```text
//! reasoning 50781   function_call 31393   function_call_output 31385
//! message   25043   custom_tool_call 19246   custom_tool_call_output 19244
//! web_search_call 6194   agent_message 2155   ghost_snapshot 1251
//! tool_search_call 30   tool_search_output 30   image_generation_call 2
//! ```
//!
//! The last six have **no arm in Python's loop** and are skipped. That is
//! behaviour, not an omission: a port that grew an arm for `agent_message` would
//! surface 2,155 blocks the product hides.
//!
//! **The generated `exec` script is hot, not exotic.** 16,990 of the 19,246
//! `custom_tool_call` payloads are `exec` with a string body, so
//! `parse_exec_script_tool` runs on the majority of Codex tool calls rather than
//! on a rarity. **788** of those bodies carry more than one call site, which is the
//! only shape `merge_script_tool_calls` exists for — rare, real, and reachable from
//! the corpus, unlike the Pi terminator case.
//!
//! *Corrected: an earlier version of this line said 68, which came from counting
//! the substring `await tools.` rather than the call sites the parser actually
//! finds. A stale figure is worse than a stale stamp, because it says something
//! false with confidence.*
//!
//! **Two shapes here the corpus cannot grade, measured rather than assumed.** An
//! assistant `message` payload carrying more than one visible text block occurs
//! **0** times, and a `reasoning` summary carrying an item that is not
//! `summary_text` occurs **0** times. Both joins are therefore untestable against
//! real data and are pinned by fixtures in `codex-fixtures/` instead. This is the
//! Pi `<duration_ms>` situation twice more: a mutation breaking either caught
//! nothing across 120 sessions, and a corpus of any size would have been as
//! blind.
//!
//! **What this module cannot decide, and what does not belong here.** Eight large
//! Codex rollouts are absent from `search .`, and none of them reaches this file:
//! their first line is an object with no `type` key, so `detect_format` routes
//! them to `raw_transcript`. A decoder made more permissive to "recover" them
//! cannot, and would wrongly surface 36 genuinely trivial sessions instead.

use crate::model::{Message, MessageType, Tool, ToolResult, ToolUse};
use crate::session;
use crate::visibility::ConversationFlags;
use serde_json::{Map, Number, Value};

/// Subagent dispatch is shown as a merged agent block, so the lifecycle calls and
/// their outputs never render.
const AGENT_LIFECYCLE_TOOLS: [&str; 3] = ["spawn_agent", "wait_agent", "close_agent"];

/// Decode Codex JSONL entries into the shared message model.
pub fn parse_codex(entries: &[Map<String, Value>], flags: &ConversationFlags) -> Vec<Message> {
    Decoder::new(flags).run(entries)
}

struct Decoder<'a> {
    flags: &'a ConversationFlags,
    messages: Vec<Message>,
    index: i64,
    current_assistant: Option<Message>,
    /// Call ids whose output must also be suppressed, tracked because the output
    /// arrives as a separate entry that carries no tool name.
    agent_lifecycle_call_ids: Vec<String>,
}

impl<'a> Decoder<'a> {
    fn new(flags: &'a ConversationFlags) -> Self {
        Decoder {
            flags,
            messages: Vec::new(),
            index: 1,
            current_assistant: None,
            agent_lifecycle_call_ids: Vec::new(),
        }
    }

    fn run(mut self, entries: &[Map<String, Value>]) -> Vec<Message> {
        for entry in entries {
            if string_of(entry, "type") != Some("response_item") {
                continue;
            }
            let Some(payload) = entry.get("payload").and_then(Value::as_object) else {
                continue;
            };
            let timestamp = string_of(entry, "timestamp").map(str::to_string);
            self.entry(payload, timestamp);
        }
        self.flush_assistant();
        self.messages
    }

    fn entry(&mut self, payload: &Map<String, Value>, timestamp: Option<String>) {
        match string_of(payload, "type") {
            Some("message") => self.message(payload, timestamp),
            Some("reasoning") if self.flags.show_thinking => self.reasoning(payload, timestamp),
            Some("function_call") => self.function_call(payload, timestamp),
            Some("function_call_output") => self.function_call_output(payload, timestamp),
            Some("custom_tool_call") if tools_requested(self.flags) => {
                self.custom_tool_call(payload, timestamp)
            }
            Some("custom_tool_call_output") if tools_requested(self.flags) => {
                let call_id = string_of(payload, "call_id").map(str::to_string);
                let output = parse_tool_output(payload.get("output"));
                self.ensure_assistant(timestamp)
                    .tools
                    .push(tool_result(call_id, output));
            }
            // Every other payload type — web_search_call, agent_message,
            // ghost_snapshot, tool_search_call, image_generation_call — has no arm
            // in Python and contributes nothing.
            _ => {}
        }
    }

    fn message(&mut self, payload: &Map<String, Value>, timestamp: Option<String>) {
        match string_of(payload, "role") {
            Some("user") => {
                let blocks = session::codex_text_blocks(
                    payload.get("content").unwrap_or(&Value::Null),
                );
                let visible = session::filter_hidden_user_text_blocks(
                    blocks
                        .into_iter()
                        .filter(|text| !is_preamble_text(text))
                        .collect(),
                );
                if !self.flags.show_user_messages() || visible.is_empty() {
                    return;
                }
                self.flush_assistant();
                let mut message = Message::new(
                    MessageType::UserMessage,
                    "user".to_string(),
                    Number::from(self.index),
                );
                message.text = visible.join("\n\n");
                message.timestamp = timestamp;
                self.messages.push(message);
                self.index += 1;
            }
            Some("assistant") => {
                if !self.flags.show_assistant_messages() {
                    return;
                }
                let blocks = session::codex_text_blocks(
                    payload.get("content").unwrap_or(&Value::Null),
                );
                let visible: Vec<String> = blocks
                    .into_iter()
                    .filter(|text| !session::python_strip(text).is_empty())
                    .collect();
                if visible.is_empty() {
                    return;
                }
                let joined = visible.join("\n\n");
                let assistant = self.ensure_assistant(timestamp);
                assistant.text = append_block(Some(&assistant.text.clone()), &joined);
            }
            _ => {}
        }
    }

    fn reasoning(&mut self, payload: &Map<String, Value>, timestamp: Option<String>) {
        let thinking = reasoning_text(payload);
        if thinking.is_empty() {
            return;
        }
        let assistant = self.ensure_assistant(timestamp);
        assistant.thinking = Some(append_block(assistant.thinking.as_deref(), &thinking));
    }

    fn function_call(&mut self, payload: &Map<String, Value>, timestamp: Option<String>) {
        let native_name = string_of(payload, "name");
        if native_name.is_some_and(|name| AGENT_LIFECYCLE_TOOLS.contains(&name)) {
            if let Some(call_id) = string_of(payload, "call_id") {
                self.agent_lifecycle_call_ids.push(call_id.to_string());
            }
            return;
        }
        if !tools_requested(self.flags) {
            return;
        }
        let name = crate::model::normalize_tool_name("codex", native_name);
        let input = normalize_tool_input(&name, payload.get("arguments"));
        let call_id = string_of(payload, "call_id").map(str::to_string);
        self.ensure_assistant(timestamp)
            .tools
            .push(tool_use(name, input, call_id));
    }

    fn function_call_output(&mut self, payload: &Map<String, Value>, timestamp: Option<String>) {
        let call_id = string_of(payload, "call_id").map(str::to_string);
        // Suppressed by call id: the output entry carries no tool name, so the
        // only link back to a lifecycle call is the id recorded when it was seen.
        if call_id
            .as_deref()
            .is_some_and(|id| self.agent_lifecycle_call_ids.iter().any(|seen| seen == id))
        {
            return;
        }
        if !tools_requested(self.flags) {
            return;
        }
        let output = parse_tool_output(payload.get("output"));
        self.ensure_assistant(timestamp)
            .tools
            .push(tool_result(call_id, output));
    }

    fn custom_tool_call(&mut self, payload: &Map<String, Value>, timestamp: Option<String>) {
        let (name, input) =
            normalize_custom_tool_call(string_of(payload, "name"), payload.get("input"));
        let call_id = string_of(payload, "call_id").map(str::to_string);
        self.ensure_assistant(timestamp)
            .tools
            .push(tool_use(name, input, call_id));
    }

    /// Open the assistant message, or adopt a timestamp it does not yet have.
    fn ensure_assistant(&mut self, timestamp: Option<String>) -> &mut Message {
        if self.current_assistant.is_none() {
            let mut message = Message::new(
                MessageType::AssistantResponse,
                "assistant".to_string(),
                Number::from(0),
            );
            message.timestamp = timestamp;
            self.current_assistant = Some(message);
        } else if let Some(assistant) = &mut self.current_assistant
            && assistant.timestamp.is_none()
        {
            assistant.timestamp = timestamp;
        }
        self.current_assistant.as_mut().expect("just populated")
    }

    /// Close the open assistant message, dropping it when it has nothing to show.
    ///
    /// The index advances only for a message actually kept, so an assistant turn
    /// that produced only suppressed tool calls does not consume a number.
    ///
    /// **The `has_content` guard is unreachable, and that is a finding rather than
    /// a gap.** All six `ensure_assistant` call sites — here and in Python — add
    /// text, thinking or a tool immediately after opening the message, so no input
    /// can present an empty one at flush time. A mutation removing the guard
    /// therefore catches nothing across the full 1,211-session corpus, and no
    /// fixture can help: there is no shape to synthesize.
    ///
    /// This is a *different* category from the two zero-occurrence shapes in this
    /// module's header. Those are behaviours the corpus never exercises. This is a
    /// branch no input can reach. Kept because Python keeps it and the port
    /// mirrors it, not because anything defends it.
    fn flush_assistant(&mut self) {
        let Some(mut assistant) = self.current_assistant.take() else {
            return;
        };
        if !has_content(&assistant) {
            return;
        }
        assistant.original_index = Number::from(self.index);
        self.messages.push(assistant);
        self.index += 1;
    }
}

/// Whether a message has anything displayable.
///
/// Python is `bool(text or thinking or tools or plan or subagent_task)` —
/// **truthiness**, so `Some("")` is falsy on all three optional fields. This now
/// matches `session.rs:1137`, which had it right.
///
/// **⚠ If this is ever promoted to `Message::has_content()` in `model.rs`, promote
/// `session.rs`'s version — not a copy of some earlier form of this one.** An
/// earlier version here used `is_some()`, which counts `Some("")` as content. That
/// was inert *inside this file*, because every `ensure_assistant` call site adds
/// content immediately, so no corpus could catch it. The exposure was the comment
/// that used to sit here recommending promotion: `parse_assistant_entry` on the
/// Claude path **does** produce `thinking: Some("")`, and `slice-reviewer` measured
/// **12,911 Claude assistant entries** whose only content is an empty or
/// whitespace thinking block. Under the wrong predicate every one is kept — and
/// because `parse_claude` increments its index only for a *kept* message, each
/// resurrected entry shifts the `i` attribute of every message after it.
///
/// Bounded honestly: it needs `show_thinking`, which defaults false.
fn has_content(message: &Message) -> bool {
    !message.text.is_empty()
        || message.thinking.as_deref().is_some_and(|value| !value.is_empty())
        || !message.tools.is_empty()
        || message.plan.as_deref().is_some_and(|value| !value.is_empty())
        || message.subagent_task.as_deref().is_some_and(|value| !value.is_empty())
}

/// Whether the flags ask for tools at all.
///
/// `ToolVisibility::Filters(vec![])` is **falsy**, reproducing Python's empty-list
/// semantics. An empty filter list does not mean "all".
fn tools_requested(flags: &ConversationFlags) -> bool {
    match &flags.show_tools {
        crate::tool_filter::ToolVisibility::All(shown) => *shown,
        crate::tool_filter::ToolVisibility::Filters(filters) => !filters.is_empty(),
    }
}

fn string_of<'a>(map: &'a Map<String, Value>, key: &str) -> Option<&'a str> {
    map.get(key).and_then(Value::as_str)
}

fn tool_use(name: String, input: Value, call_id: Option<String>) -> Tool {
    Tool::Use(ToolUse {
        name,
        input,
        id: call_id,
        native_tool_call_id: None,
        native_content_index: None,
    })
}

fn tool_result(call_id: Option<String>, content: Value) -> Tool {
    Tool::Result(ToolResult {
        name: None,
        tool_use_id: call_id,
        native_tool_call_id: None,
        is_error: false,
        content: Some(content),
        // Python always sets the key, so the block always counts as carrying one.
        has_content: true,
    })
}

/// Join a new block onto an existing one with paragraph spacing.
///
/// An empty existing block is replaced rather than joined, matching Python's
/// falsy check — otherwise every first block gains a leading blank line.
///
/// ```
/// use _native::codex::append_block;
/// assert_eq!(append_block(None, "b"), "b");
/// assert_eq!(append_block(Some(""), "b"), "b");
/// assert_eq!(append_block(Some("a"), "b"), "a\n\nb");
/// ```
pub fn append_block(existing: Option<&str>, new_text: &str) -> String {
    match existing.filter(|value| !value.is_empty()) {
        Some(value) => format!("{value}\n\n{new_text}"),
        None => new_text.to_string(),
    }
}

/// Whether a Codex user text block is protocol noise rather than something typed.
///
/// ```
/// use _native::codex::is_preamble_text;
/// assert!(is_preamble_text("   "));
/// assert!(is_preamble_text("<environment_context>\n<cwd>/x</cwd>"));
/// assert!(is_preamble_text("# AGENTS.md instructions for /x"));
/// assert!(!is_preamble_text("please run the tests"));
/// ```
pub fn is_preamble_text(text: &str) -> bool {
    let stripped = session::python_strip(text);
    stripped.is_empty()
        || stripped.starts_with("# AGENTS.md instructions for ")
        || stripped.starts_with("<environment_context>")
        || stripped.starts_with("<subagent_notification>")
        || stripped.starts_with("<skill>")
}

/// The visible summary text of a reasoning payload.
fn reasoning_text(payload: &Map<String, Value>) -> String {
    let Some(summary) = payload.get("summary").and_then(Value::as_array) else {
        return String::new();
    };
    summary
        .iter()
        .filter_map(Value::as_object)
        .filter(|item| string_of(item, "type") == Some("summary_text"))
        .filter_map(|item| {
            let text = session::python_strip(string_of(item, "text").unwrap_or_default());
            (!text.is_empty()).then(|| text.to_string())
        })
        .collect::<Vec<String>>()
        .join("\n\n")
}

/// Normalize a Codex tool output into shared text content.
fn parse_tool_output(raw: Option<&Value>) -> Value {
    let raw = raw.unwrap_or(&Value::Null);
    if let Some(blocks) = raw.as_array() {
        return Value::Array(
            blocks
                .iter()
                .map(|block| match block.as_object() {
                    Some(object)
                        if matches!(
                            string_of(object, "type"),
                            Some("input_text") | Some("output_text")
                        ) =>
                    {
                        let mut rewritten = object.clone();
                        rewritten.insert("type".to_string(), Value::String("text".to_string()));
                        Value::Object(rewritten)
                    }
                    _ => block.clone(),
                })
                .collect(),
        );
    }
    let Some(text) = raw.as_str() else {
        return raw.clone();
    };
    if !session::python_strip(text).starts_with('{') {
        return raw.clone();
    }
    let Ok(Value::Object(parsed)) = serde_json::from_str::<Value>(session::python_strip(text))
    else {
        return raw.clone();
    };
    for key in ["output", "content", "text"] {
        if let Some(value) = parsed.get(key).and_then(Value::as_str) {
            return Value::String(value.to_string());
        }
    }
    raw.clone()
}

/// Normalize Codex tool input into an object for the shared tool renderer.
fn parse_tool_input(raw: Option<&Value>) -> Value {
    let raw = raw.unwrap_or(&Value::Null);
    if raw.is_object() {
        return raw.clone();
    }
    if raw.is_array() {
        return wrapped(raw.clone());
    }
    let Some(text) = raw.as_str() else {
        return Value::Object(Map::new());
    };
    let stripped = session::python_strip(text);
    if stripped.is_empty() {
        return Value::Object(Map::new());
    }
    if !(stripped.starts_with('{') || stripped.starts_with('[')) {
        return wrapped(raw.clone());
    }
    match serde_json::from_str::<Value>(stripped) {
        Ok(Value::Object(object)) => Value::Object(object),
        Ok(other) => wrapped(other),
        Err(_) => wrapped(raw.clone()),
    }
}

fn wrapped(value: Value) -> Value {
    let mut object = Map::new();
    object.insert("input".to_string(), value);
    Value::Object(object)
}

fn normalize_tool_input(tool_name: &str, raw: Option<&Value>) -> Value {
    crate::model::normalize_tool_input_keys("codex", tool_name, &parse_tool_input(raw))
}

/// Normalize a direct custom call, or Codex's generated `exec` envelope.
fn normalize_custom_tool_call(native_name: Option<&str>, raw: Option<&Value>) -> (String, Value) {
    let script = (native_name == Some("exec"))
        .then(|| raw.and_then(Value::as_str))
        .flatten()
        .and_then(parse_exec_script_tool);

    match script {
        Some((name, input)) => {
            let canonical = crate::model::normalize_tool_name("codex", Some(&name));
            let normalized =
                crate::model::normalize_tool_input_keys("codex", &canonical, &input);
            (canonical, normalized)
        }
        None => {
            let canonical = crate::model::normalize_tool_name("codex", native_name);
            let normalized = normalize_tool_input(&canonical, raw);
            (canonical, normalized)
        }
    }
}

// ------------------------------------------------------- the generated script

/// Extract the native tool calls from Codex's generated `exec` script.
///
/// This runs on 16,990 of the corpus's 19,246 `custom_tool_call` payloads, so it
/// is the common path rather than an edge case.
///
/// ```
/// use _native::codex::parse_exec_script_tool;
/// let (name, input) = parse_exec_script_tool(r#"await tools.exec_command({cmd: "pwd"});"#).unwrap();
/// assert_eq!(name, "exec_command");
/// assert_eq!(input["cmd"], "pwd");
/// ```
pub fn parse_exec_script_tool(script: &str) -> Option<(String, Value)> {
    let bindings = string_bindings(script);
    let mut calls: Vec<(String, Value)> = Vec::new();
    for (name, open) in script_call_sites(script) {
        calls.push(parse_script_call(script, &name, open, &bindings)?);
    }
    if calls.is_empty() {
        return None;
    }
    merge_script_tool_calls(calls)
}

/// Every `tools.<name>(` site, as a name and the index of its opening paren.
///
/// Hand-scanned rather than compiled, because the crate's regex engine is not the
/// one this product's search semantics run on and pulling it in here would put a
/// second regex dialect in the decode path.
fn script_call_sites(script: &str) -> Vec<(String, usize)> {
    const MARKER: &str = "tools.";
    let bytes = script.as_bytes();
    let mut sites = Vec::new();
    let mut cursor = 0;
    while let Some(found) = script[cursor..].find(MARKER) {
        let start = cursor + found;
        cursor = start + MARKER.len();
        // `\b` before `tools`: the preceding character must not be a word one.
        if start > 0
            && bytes
                .get(start - 1)
                .is_some_and(|byte| byte.is_ascii_alphanumeric() || *byte == b'_')
        {
            continue;
        }
        let name_start = start + MARKER.len();
        let name: String = script[name_start..]
            .chars()
            .take_while(|character| character.is_ascii_alphanumeric() || *character == '_')
            .collect();
        if name.is_empty() || name.starts_with(|c: char| c.is_ascii_digit()) {
            continue;
        }
        let after_name = name_start + name.len();
        let open = script[after_name..]
            .char_indices()
            .find(|(_, character)| !character.is_whitespace())
            .filter(|(_, character)| *character == '(')
            .map(|(offset, _)| after_name + offset);
        if let Some(open) = open {
            sites.push((name, open));
            cursor = open + 1;
        }
    }
    sites
}

/// `const name = "value";` bindings, so an `apply_patch` body passed by reference
/// can be resolved.
///
/// **The trailing `;` is required, and dropping it silently truncates a patch.**
/// Python's pattern ends `(?P<value>"(?:\\.|[^"\\])*")\s*;`, so a binding built by
/// concatenation — `const patch = "line one\n" +\n"line two\n";`, which is how
/// Codex emits any multi-line patch — matches **nothing**. The call then has no
/// binding to resolve, `apply_patch` stays unparsed, and the envelope keeps the
/// name `exec`, which normalises to `Bash`.
///
/// Accepting the first fragment instead produces a tool named `Patch` carrying a
/// patch body truncated to its first line. Measured: 4 mismatches across the
/// 1,211-session differential, in the four tool-bearing configurations.
///
/// This is the second place in this file where being *more permissive* than the
/// oracle was the defect. Both came from implementing what the Python appears to
/// intend rather than what it literally accepts.
fn string_bindings(script: &str) -> Vec<(String, String)> {
    let mut bindings = Vec::new();
    let mut cursor = 0;
    while let Some(found) = script[cursor..].find("const ") {
        let keyword = cursor + found;
        let start = keyword + "const ".len();
        cursor = start;
        // `\b` before `const`: the preceding character must not be a word one.
        if keyword > 0
            && script[..keyword]
                .chars()
                .next_back()
                .is_some_and(|c| c.is_ascii_alphanumeric() || c == '_')
        {
            continue;
        }
        let name: String = script[start..]
            .chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
            .collect();
        if name.is_empty() || name.starts_with(|c: char| c.is_ascii_digit()) {
            continue;
        }
        let rest = session::python_strip_start(&script[start + name.len()..]);
        let Some(rest) = rest.strip_prefix('=') else {
            continue;
        };
        let rest = session::python_strip_start(rest);
        if !rest.starts_with('"') {
            continue;
        }
        let offset = script.len() - rest.len();
        let Some(end) = quoted_string_end(script, offset) else {
            continue;
        };
        // The literal must be the whole value, terminated by `;`. A `+` here means
        // a concatenation, which Python's pattern does not match at all.
        if !session::python_strip_start(&script[end + 1..]).starts_with(';') {
            continue;
        }
        if let Ok(Value::String(value)) = serde_json::from_str::<Value>(&script[offset..=end]) {
            bindings.push((name, value));
        }
    }
    bindings
}

/// The index of the closing quote of the string starting at `open`.
fn quoted_string_end(script: &str, open: usize) -> Option<usize> {
    let mut escaped = false;
    for (offset, character) in script[open + 1..].char_indices() {
        if escaped {
            escaped = false;
        } else if character == '\\' {
            escaped = true;
        } else if character == '"' {
            return Some(open + 1 + offset);
        }
    }
    None
}

/// The matching close paren for the call opened at `open`, ignoring quoted text.
fn script_call_end(script: &str, open: usize) -> Option<usize> {
    let mut depth = 1usize;
    let mut quote: Option<char> = None;
    let mut escaped = false;
    for (offset, character) in script[open + 1..].char_indices() {
        let index = open + 1 + offset;
        if let Some(open_quote) = quote {
            if escaped {
                escaped = false;
            } else if character == '\\' {
                escaped = true;
            } else if character == open_quote {
                quote = None;
            }
            continue;
        }
        match character {
            '"' | '\'' | '`' => quote = Some(character),
            '(' => depth += 1,
            ')' => {
                depth -= 1;
                if depth == 0 {
                    return Some(index);
                }
            }
            _ => {}
        }
    }
    None
}

fn parse_script_call(
    script: &str,
    name: &str,
    open: usize,
    bindings: &[(String, String)],
) -> Option<(String, Value)> {
    let close = script_call_end(script, open)?;
    let argument = session::python_strip(&script[open + 1..close]);
    if let Some(input) = parse_script_object(argument) {
        return Some((name.to_string(), input));
    }
    if name != "apply_patch" {
        return None;
    }
    let patch = bindings
        .iter()
        .find(|(binding, _)| binding == argument)
        .map(|(_, value)| value.clone())
        .or_else(|| match serde_json::from_str::<Value>(argument) {
            Ok(Value::String(value)) => Some(value),
            _ => None,
        })?;
    Some((name.to_string(), wrapped(Value::String(patch))))
}

/// Parse the object literal generated for a tool call.
///
/// Tries strict JSON first, then the JavaScript form with bare keys.
///
/// **An empty object is `None`, not `Some({})`, and the difference is visible in
/// shipped output.** Python's caller tests the result with `if input_data :=`,
/// and `{}` is falsy, so an empty literal means "not parsed" — the call falls
/// through, the envelope keeps the name `exec`, and `exec` normalises to `Bash`.
/// Returning `Some({})` here instead renders
/// `const t = await tools.clock__curr_time({}); text(t);` as
/// `name="clock__curr_time"` where the product renders `name="Bash"`.
///
/// Measured: this exact defect produced 56 mismatches across 14 sessions in the
/// 1,208-session differential, and only in the four tool-bearing configurations.
///
/// ```
/// use _native::codex::parse_exec_script_tool;
/// // An empty argument list is not a parsed call, so the envelope stays `exec`.
/// assert!(parse_exec_script_tool("const t = await tools.clock__curr_time({}); text(t);").is_none());
/// ```
fn parse_script_object(argument: &str) -> Option<Value> {
    let stripped = session::python_strip(argument);
    if !(stripped.starts_with('{') && stripped.ends_with('}')) {
        return None;
    }
    if let Ok(Value::Object(parsed)) = serde_json::from_str::<Value>(stripped) {
        return (!parsed.is_empty()).then_some(Value::Object(parsed));
    }
    let mut object = Map::new();
    for item in split_script_items(&stripped[1..stripped.len() - 1]) {
        let (key, value) = item.split_once(':')?;
        let key = session::python_strip(key);
        if key.is_empty()
            || !key.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
            || key.starts_with(|c: char| c.is_ascii_digit())
        {
            return None;
        }
        object.insert(key.to_string(), parse_script_scalar(value));
    }
    (!object.is_empty()).then_some(Value::Object(object))
}

/// Split comma-separated items without splitting nested values or quoted text.
fn split_script_items(source: &str) -> Vec<String> {
    let mut items = Vec::new();
    let mut start = 0usize;
    let mut depth = 0i64;
    let mut quote: Option<char> = None;
    let mut escaped = false;
    for (index, character) in source.char_indices() {
        if let Some(open_quote) = quote {
            if escaped {
                escaped = false;
            } else if character == '\\' {
                escaped = true;
            } else if character == open_quote {
                quote = None;
            }
            continue;
        }
        match character {
            '"' | '\'' | '`' => quote = Some(character),
            '(' | '[' | '{' => depth += 1,
            ')' | ']' | '}' => depth -= 1,
            ',' if depth == 0 => {
                items.push(session::python_strip(&source[start..index]).to_string());
                start = index + 1;
            }
            _ => {}
        }
    }
    items.push(session::python_strip(&source[start..]).to_string());
    items.into_iter().filter(|item| !item.is_empty()).collect()
}

/// Parse a generated scalar, keeping a dynamic expression visible as its source.
fn parse_script_scalar(value: &str) -> Value {
    let stripped = session::python_strip(value);
    if let Ok(parsed) = serde_json::from_str::<Value>(stripped) {
        return parsed;
    }
    if stripped.len() >= 2 && stripped.starts_with('`') && stripped.ends_with('`') {
        return Value::String(stripped[1..stripped.len() - 1].to_string());
    }
    Value::String(stripped.to_string())
}

/// Represent one outer `exec` envelope as one canonical tool call.
///
/// Only two multi-call shapes merge — all `apply_patch`, or all `exec_command`.
/// Anything else returns `None`, which sends the caller back to the unparsed
/// envelope rather than inventing a combined call.
fn merge_script_tool_calls(calls: Vec<(String, Value)>) -> Option<(String, Value)> {
    if calls.len() == 1 {
        return calls.into_iter().next();
    }
    let names: Vec<&str> = calls.iter().map(|(name, _)| name.as_str()).collect();

    if names.iter().all(|name| *name == "apply_patch") {
        let mut patches = Vec::new();
        for (_, input) in &calls {
            patches.push(input.get("input").and_then(Value::as_str)?.to_string());
        }
        return Some(("apply_patch".to_string(), wrapped(Value::String(patches.join("\n\n")))));
    }
    if !names.iter().all(|name| *name == "exec_command") {
        return None;
    }

    let mut commands = Vec::new();
    for (_, input) in &calls {
        commands.push(input.get("cmd").and_then(Value::as_str)?.to_string());
    }
    let mut merged = Map::new();
    merged.insert("cmd".to_string(), Value::String(commands.join("\n\n")));
    // A shared key survives the merge only when every call agrees on it.
    for key in ["workdir", "yield_time_ms", "max_output_tokens"] {
        let values: Vec<Option<&Value>> = calls.iter().map(|(_, input)| input.get(key)).collect();
        let Some(first) = values[0] else { continue };
        if values.iter().all(|value| *value == Some(first)) {
            merged.insert(key.to_string(), first.clone());
        }
    }
    Some(("exec_command".to_string(), Value::Object(merged)))
}
