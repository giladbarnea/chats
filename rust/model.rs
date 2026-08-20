use num_bigint::BigInt;
use serde_json::{Map, Number, Value};
use unicode_general_category::{GeneralCategory, get_general_category};

pub const MESSAGE_KEYS: &[&str] = &[
    "type",
    "role",
    "original_index",
    "content",
    "branch",
    "isMeta",
    "sourceToolUserId",
    "agent_id",
    "subagent_type",
    "name",
    "model",
    "custom_type",
    "inherited_context",
    "status",
    "timestamp",
    "native_entry_id",
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MessageType {
    UserMessage,
    UserCommandInput,
    UserCommandOutput,
    Recap,
    Compaction,
    AssistantResponse,
    Agent,
    Custom,
    SessionRename,
}

impl MessageType {
    pub fn from_tag(tag: &str) -> Option<Self> {
        match tag {
            "user-message" => Some(Self::UserMessage),
            "user-command-input" => Some(Self::UserCommandInput),
            "user-command-output" => Some(Self::UserCommandOutput),
            "recap" => Some(Self::Recap),
            "compaction" => Some(Self::Compaction),
            "assistant-response" => Some(Self::AssistantResponse),
            "agent" => Some(Self::Agent),
            "custom" => Some(Self::Custom),
            "session-rename" => Some(Self::SessionRename),
            _ => None,
        }
    }

    pub fn tag(self) -> &'static str {
        match self {
            Self::UserMessage => "user-message",
            Self::UserCommandInput => "user-command-input",
            Self::UserCommandOutput => "user-command-output",
            Self::Recap => "recap",
            Self::Compaction => "compaction",
            Self::AssistantResponse => "assistant-response",
            Self::Agent => "agent",
            Self::Custom => "custom",
            Self::SessionRename => "session-rename",
        }
    }

    pub fn header(self) -> &'static str {
        match self {
            Self::UserMessage => "## User",
            Self::UserCommandInput => "## User Command Input",
            Self::UserCommandOutput => "## User Command Output",
            Self::Recap => "## Recap",
            Self::Compaction => "## Compaction",
            Self::AssistantResponse => "## Assistant",
            Self::Agent => "## Agent",
            Self::Custom => "## Custom",
            Self::SessionRename => "## Renamed Session",
        }
    }

    pub fn default_role(self) -> &'static str {
        match self {
            Self::UserMessage
            | Self::UserCommandInput
            | Self::UserCommandOutput
            | Self::Compaction => "user",
            Self::Custom => "custom",
            Self::SessionRename => "session-rename",
            Self::Recap | Self::AssistantResponse | Self::Agent => "assistant",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Message {
    pub message_type: MessageType,
    pub role: String,
    pub original_index: Number,
    pub text: String,
    pub thinking: Option<String>,
    pub tools: Vec<Tool>,
    pub plan: Option<String>,
    pub subagent_task: Option<String>,
    pub branch: Option<String>,
    pub is_meta: bool,
    pub source_tool_user_id: Option<String>,
    pub agent_id: Option<String>,
    pub subagent_type: Option<String>,
    pub name: Option<String>,
    pub model: Option<String>,
    pub custom_type: Option<String>,
    pub inherited_context: Option<bool>,
    pub status: Option<String>,
    pub timestamp: Option<String>,
    pub native_entry_id: Option<String>,
}

impl Message {
    pub fn new(message_type: MessageType, role: String, original_index: Number) -> Self {
        Self {
            message_type,
            role,
            original_index,
            text: String::new(),
            thinking: None,
            tools: Vec::new(),
            plan: None,
            subagent_task: None,
            branch: None,
            is_meta: false,
            source_tool_user_id: None,
            agent_id: None,
            subagent_type: None,
            name: None,
            model: None,
            custom_type: None,
            inherited_context: None,
            status: None,
            timestamp: None,
            native_entry_id: None,
        }
    }

    pub fn header(&self) -> String {
        if self.message_type != MessageType::Agent {
            return self.message_type.header().to_string();
        }
        if self.subagent_type.as_deref() == Some("fork") {
            return "## Fork".to_string();
        }
        match &self.name {
            Some(name) => format!("## Agent '{name}'"),
            None => "## Agent".to_string(),
        }
    }

    pub fn display_model(&self) -> Option<&str> {
        let model = self.model.as_deref()?;
        if self.custom_type.is_some() {
            return Some(model);
        }
        Some(model.strip_prefix("claude-").unwrap_or(model))
    }

    pub fn contains_only_tool_outputs(&self) -> bool {
        !self.tools.is_empty()
            && self
                .tools
                .iter()
                .all(|tool| matches!(tool, Tool::Result(_)))
    }
}

#[derive(Clone, Debug)]
pub enum Tool {
    Use(ToolUse),
    Result(ToolResult),
}

#[derive(Clone, Debug)]
pub struct ToolUse {
    pub name: String,
    pub input: Value,
    pub id: Option<String>,
    pub native_tool_call_id: Option<String>,
    pub native_content_index: Option<Number>,
}

#[derive(Clone, Debug)]
pub struct ToolResult {
    pub name: Option<String>,
    pub tool_use_id: Option<String>,
    pub native_tool_call_id: Option<String>,
    pub is_error: bool,
    pub content: Option<Value>,
    pub has_content: bool,
}

#[derive(Clone, Copy)]
pub struct ToolSchema {
    pub attribute_keys: &'static [&'static str],
    pub content_key: Option<&'static str>,
    pub content_language: Option<&'static str>,
}

pub fn tool_schema(name: &str) -> Option<ToolSchema> {
    let schema = match name {
        "Bash" => ToolSchema {
            attribute_keys: &["workdir", "yield_time_ms", "max_output_tokens"],
            content_key: Some("command"),
            content_language: Some("sh"),
        },
        "Read" => ToolSchema {
            attribute_keys: &["file_path"],
            content_key: None,
            content_language: None,
        },
        "Glob" => ToolSchema {
            attribute_keys: &["pattern", "path"],
            content_key: None,
            content_language: None,
        },
        "Grep" => ToolSchema {
            attribute_keys: &["pattern", "path", "glob", "type", "output_mode"],
            content_key: None,
            content_language: None,
        },
        "Write" => ToolSchema {
            attribute_keys: &["file_path"],
            content_key: Some("content"),
            content_language: None,
        },
        "Edit" => ToolSchema {
            attribute_keys: &["file_path"],
            content_key: None,
            content_language: None,
        },
        "Skill" => ToolSchema {
            attribute_keys: &["skill", "location", "args"],
            content_key: None,
            content_language: None,
        },
        "Task" => ToolSchema {
            attribute_keys: &["subagent_type", "model"],
            content_key: Some("prompt"),
            content_language: None,
        },
        "WebFetch" => ToolSchema {
            attribute_keys: &["url"],
            content_key: Some("prompt"),
            content_language: None,
        },
        "WebSearch" => ToolSchema {
            attribute_keys: &["query"],
            content_key: None,
            content_language: None,
        },
        "Patch" => ToolSchema {
            attribute_keys: &[],
            content_key: Some("input"),
            content_language: Some("diff"),
        },
        "TaskNotification" => ToolSchema {
            attribute_keys: &["tool_use_id", "status", "summary"],
            content_key: Some("result"),
            content_language: None,
        },
        "AdditionalContext" => ToolSchema {
            attribute_keys: &["hook_name"],
            content_key: Some("content"),
            content_language: None,
        },
        _ => return None,
    };
    Some(schema)
}

pub fn optional_string(
    payload: &Map<String, Value>,
    key: &str,
    context: &str,
) -> Result<Option<String>, String> {
    match payload.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => Ok(Some(value.clone())),
        Some(_) => Err(format!("Expected {context}.{key} to be a string.")),
    }
}

pub fn optional_bool(
    payload: &Map<String, Value>,
    key: &str,
    context: &str,
) -> Result<Option<bool>, String> {
    match payload.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Bool(value)) => Ok(Some(*value)),
        Some(_) => Err(format!("Expected {context}.{key} to be a boolean.")),
    }
}

pub fn canonicalize_json_numbers(value: &mut Value) -> Result<(), String> {
    match value {
        Value::Number(number) => {
            let canonical = if number_is_integer(number) {
                canonical_integer(number.as_str())?
            } else {
                python_float_string(number.as_str())?
            };
            *number = Number::from_string_unchecked(canonical);
        }
        Value::Array(values) => {
            for value in values {
                canonicalize_json_numbers(value)?;
            }
        }
        Value::Object(values) => {
            for value in values.values_mut() {
                canonicalize_json_numbers(value)?;
            }
        }
        Value::Null | Value::Bool(_) | Value::String(_) => {}
    }
    Ok(())
}

pub fn number_is_integer(number: &Number) -> bool {
    !number.as_str().bytes().any(|byte| matches!(byte, b'.' | b'e' | b'E'))
}

pub fn canonical_integer(value: &str) -> Result<String, String> {
    let value = value.trim();
    let mut previous_was_digit = false;
    let mut filtered = String::with_capacity(value.len());
    let mut characters = value.chars().peekable();
    let mut position = 0;
    while let Some(character) = characters.next() {
        if character == '_' {
            let next_is_digit = characters.peek().is_some_and(|next| next.is_ascii_digit());
            if !previous_was_digit || !next_is_digit {
                return Err(format!("invalid literal for int() with base 10: {}", python_repr_string(value)));
            }
            previous_was_digit = false;
            position += 1;
            continue;
        }
        if character.is_ascii_digit() {
            previous_was_digit = true;
            filtered.push(character);
            position += 1;
            continue;
        }
        if position == 0 && matches!(character, '+' | '-') {
            filtered.push(character);
            previous_was_digit = false;
            position += 1;
            continue;
        }
        return Err(format!("invalid literal for int() with base 10: {}", python_repr_string(value)));
    }
    let digit_count = filtered.bytes().filter(|byte| byte.is_ascii_digit()).count();
    if digit_count > 4_300 {
        return Err(format!(
            "Exceeds the limit (4300 digits) for integer string conversion: value has {digit_count} digits; use sys.set_int_max_str_digits() to increase the limit"
        ));
    }
    let integer = filtered.parse::<BigInt>().map_err(|_| {
        format!("invalid literal for int() with base 10: {}", python_repr_string(value))
    })?;
    Ok(integer.to_string())
}

fn python_float_string(value: &str) -> Result<String, String> {
    let value = value.parse::<f64>().map_err(|error| error.to_string())?;
    if value.is_infinite() {
        return Ok(if value.is_sign_negative() {
            "-Infinity".to_string()
        } else {
            "Infinity".to_string()
        });
    }
    let mut buffer = ryu::Buffer::new();
    let rendered = buffer.format_finite(value);
    if let Some((mantissa, exponent)) = rendered.split_once('e') {
        let exponent = exponent.parse::<i32>().expect("Ryū emits an integer exponent");
        return Ok(format!("{mantissa}e{exponent:+03}"));
    }
    if value != 0.0 && value.abs() < 0.0001 {
        let sign = rendered.strip_prefix('-').map_or("", |_| "-");
        let unsigned = rendered.strip_prefix('-').unwrap_or(rendered);
        let fraction = unsigned.strip_prefix("0.").expect("small Ryū float is fractional");
        let first_digit = fraction
            .bytes()
            .position(|byte| byte != b'0')
            .expect("nonzero float has one nonzero digit");
        let digits = &fraction[first_digit..];
        let mantissa = if digits.len() == 1 {
            digits.to_string()
        } else {
            format!("{}.{}", &digits[..1], &digits[1..])
        };
        let exponent = -i32::try_from(first_digit + 1).expect("float exponent fits i32");
        return Ok(format!("{sign}{mantissa}e{exponent:+03}"));
    }
    Ok(rendered.to_string())
}

pub fn messages_from_json(value: Value) -> Result<Vec<Message>, String> {
    let Value::Array(payloads) = value else {
        return Err("Expected the JSON root to be an array of messages.".to_string());
    };
    payloads
        .into_iter()
        .enumerate()
        .map(|(index, payload)| message_from_json(payload, index + 1))
        .collect()
}

fn message_from_json(payload: Value, position: usize) -> Result<Message, String> {
    let context = format!("message {position}");
    let Value::Object(payload) = payload else {
        return Err(format!("Expected {context} to be an object."));
    };
    let mut unexpected_keys = payload
        .keys()
        .filter(|key| !MESSAGE_KEYS.contains(&key.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    unexpected_keys.sort();
    if !unexpected_keys.is_empty() {
        return Err(format!(
            "Unexpected keys in {context}: {}.",
            python_string_list(&unexpected_keys)
        ));
    }

    let wrapper_name = payload
        .get("type")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("Expected {context}.type to be a string."))?;
    let message_type = MessageType::from_tag(wrapper_name).ok_or_else(|| {
        format!(
            "Unknown message type in {context}: {}.",
            python_repr_string(wrapper_name)
        )
    })?;
    let role = payload
        .get("role")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("Expected {context}.role to be a string."))?
        .to_string();
    let original_index = match payload.get("original_index") {
        Some(Value::Number(number)) if number_is_integer(number) => number.clone(),
        _ => return Err(format!("Expected {context}.original_index to be an integer.")),
    };
    let content = payload
        .get("content")
        .and_then(Value::as_array)
        .ok_or_else(|| format!("Expected {context}.content to be an array."))?;
    let is_meta = match payload.get("isMeta") {
        None => false,
        Some(Value::Bool(value)) => *value,
        Some(_) => return Err(format!("Expected {context}.isMeta to be a boolean.")),
    };

    let mut message = Message::new(message_type, role, original_index);
    message.agent_id = optional_string(&payload, "agent_id", &context)?;
    message.timestamp = optional_string(&payload, "timestamp", &context)?;
    message.native_entry_id = optional_string(&payload, "native_entry_id", &context)?;
    message.subagent_type = optional_string(&payload, "subagent_type", &context)?;
    message.name = optional_string(&payload, "name", &context)?;
    message.model = optional_string(&payload, "model", &context)?;
    message.custom_type = optional_string(&payload, "custom_type", &context)?;
    message.inherited_context = optional_bool(&payload, "inherited_context", &context)?;
    message.status = optional_string(&payload, "status", &context)?;
    message.is_meta = is_meta;
    message.source_tool_user_id = optional_string(&payload, "sourceToolUserId", &context)?;
    message.branch = optional_string(&payload, "branch", &context)?;
    populate_message_content(&mut message, content, &context)?;
    Ok(message)
}

fn populate_message_content(
    message: &mut Message,
    content: &[Value],
    context: &str,
) -> Result<(), String> {
    let mut text_values = Vec::new();
    let mut text_positions = Vec::new();
    for (index, block) in content.iter().enumerate() {
        let position = index + 1;
        let block_context = format!("{context}.content[{position}]");
        if let Value::String(text) = block {
            text_values.push(text.clone());
            text_positions.push(position);
            continue;
        }
        let Value::Object(block) = block else {
            return Err(format!("Expected {block_context} to be a string or object."));
        };
        match block.get("type").and_then(Value::as_str) {
            Some("thinking") => message.thinking = Some(single_content_string(block, &block_context)?),
            Some("subagent-task") => {
                message.subagent_task = Some(single_content_string(block, &block_context)?)
            }
            Some("tool-input") => append_tool_input(message, block, &block_context)?,
            Some("tool-output") => {
                message.tools.push(Tool::Result(tool_output_from_json(block, &block_context)?))
            }
            block_type => {
                return Err(format!(
                    "Unknown content type in {block_context}: {}.",
                    python_repr_optional_string(block_type)
                ));
            }
        }
    }
    if let (Some(first), Some(last)) = (text_positions.first(), text_positions.last()) {
        if last - first + 1 != text_positions.len() {
            return Err(format!("Text values must be adjacent in {context}.content."));
        }
    }
    message.text = text_values.join("\n\n");
    Ok(())
}

fn single_content_string(block: &Map<String, Value>, context: &str) -> Result<String, String> {
    if block.len() == 2 && block.contains_key("type") {
        if let Some(Value::String(content)) = block.get("content") {
            return Ok(content.clone());
        }
    }
    Err(format!(
        "Expected {context} to contain one string content field."
    ))
}

fn append_tool_input(
    message: &mut Message,
    block: &Map<String, Value>,
    context: &str,
) -> Result<(), String> {
    let name = block
        .get("name")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("Expected {context}.name to be a string."))?
        .to_string();
    if name == "ExitPlanMode" {
        if block.len() == 3 && block.contains_key("type") && block.contains_key("name") {
            if let Some(Value::String(plan)) = block.get("plan") {
                message.plan = Some(plan.clone());
                return Ok(());
            }
        }
        return Err(format!("Expected {context}.plan to be a string."));
    }

    let id = optional_string(block, "id", context)?;
    let native_tool_call_id = optional_string(block, "native_tool_call_id", context)?;
    let native_content_index = match block.get("native_content_index") {
        None | Some(Value::Null) => None,
        Some(Value::Number(number)) if number_is_integer(number) && !number.as_str().starts_with('-') => {
            Some(number.clone())
        }
        Some(_) => None,
    };
    if block.contains_key("native_content_index")
        && !matches!(block.get("native_content_index"), None | Some(Value::Null))
        && native_content_index.is_none()
    {
        return Err(format!(
            "Expected {context}.native_content_index to be a non-negative integer."
        ));
    }

    let mut input_fields = Map::new();
    for (key, value) in block {
        if ![
            "type",
            "name",
            "id",
            "native_tool_call_id",
            "native_content_index",
        ]
        .contains(&key.as_str())
        {
            input_fields.insert(key.clone(), value.clone());
        }
    }
    let nested_input = input_fields.get("input");
    let collision_wrapper = input_fields.len() == 1
        && nested_input.is_some_and(Value::is_object)
        && nested_input
            .and_then(Value::as_object)
            .is_some_and(|value| tool_input_needs_wrapper(&name, value));
    let schema_content = tool_schema(&name).is_some_and(|schema| schema.content_key == Some("content"));
    let input = if collision_wrapper {
        nested_input.expect("collision input exists").clone()
    } else if input_fields.len() == 1 && input_fields.contains_key("content") && !schema_content {
        input_fields.remove("content").expect("content input exists")
    } else {
        Value::Object(input_fields)
    };
    message.tools.push(Tool::Use(ToolUse {
        name,
        input,
        id,
        native_tool_call_id,
        native_content_index,
    }));
    Ok(())
}

fn tool_output_from_json(
    block: &Map<String, Value>,
    context: &str,
) -> Result<ToolResult, String> {
    let allowed_keys = [
        "type",
        "name",
        "id",
        "native_tool_call_id",
        "is_error",
        "content",
    ];
    let mut unexpected_keys = block
        .keys()
        .filter(|key| !allowed_keys.contains(&key.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    unexpected_keys.sort();
    if !unexpected_keys.is_empty() {
        return Err(format!(
            "Unexpected keys in {context}: {}.",
            python_string_list(&unexpected_keys)
        ));
    }
    let tool_use_id = optional_string(block, "id", context)?;
    let native_tool_call_id = optional_string(block, "native_tool_call_id", context)?;
    let name = optional_string(block, "name", context)?;
    let is_error = match block.get("is_error") {
        None => false,
        Some(Value::Bool(value)) => *value,
        Some(_) => return Err(format!("Expected {context}.is_error to be a boolean.")),
    };
    Ok(ToolResult {
        name,
        tool_use_id,
        native_tool_call_id,
        is_error,
        content: block.get("content").cloned(),
        has_content: block.contains_key("content"),
    })
}

/// Returns whether flattening a tool-input object would make its transport ambiguous.
///
/// ```
/// use serde_json::{Map, Value};
/// use _native::model::tool_input_needs_wrapper;
///
/// let input = Map::from_iter([("content".to_string(), Value::String("value".to_string()))]);
/// assert!(tool_input_needs_wrapper("Unknown", &input));
/// ```
pub fn tool_input_needs_wrapper(name: &str, input: &Map<String, Value>) -> bool {
    let schema_content = tool_schema(name).is_some_and(|schema| schema.content_key == Some("content"));
    input.keys().any(|key| ["type", "name", "id"].contains(&key.as_str()))
        || (input.len() == 1 && input.contains_key("content") && !schema_content)
        || (input.len() == 1 && input.get("input").is_some_and(Value::is_object))
}

pub fn value_is_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(value) => value.as_f64() != Some(0.0),
        Value::String(value) => !value.is_empty(),
        Value::Array(value) => !value.is_empty(),
        Value::Object(value) => !value.is_empty(),
    }
}

pub fn python_value_string(value: &Value) -> String {
    match value {
        Value::Null => "None".to_string(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Number(number) => match number.as_str() {
            "Infinity" => "inf".to_string(),
            "-Infinity" => "-inf".to_string(),
            value => value.to_string(),
        },
        Value::String(value) => value.clone(),
        Value::Array(values) => format!(
            "[{}]",
            values
                .iter()
                .map(python_value_repr)
                .collect::<Vec<_>>()
                .join(", ")
        ),
        Value::Object(values) => format!(
            "{{{}}}",
            values
                .iter()
                .map(|(key, value)| format!(
                    "{}: {}",
                    python_repr_string(key),
                    python_value_repr(value)
                ))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    }
}

fn python_value_repr(value: &Value) -> String {
    match value {
        Value::String(value) => python_repr_string(value),
        _ => python_value_string(value),
    }
}

pub fn python_repr_string(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut escaped = String::new();
    for character in value.chars() {
        match character {
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            character if character == quote => {
                escaped.push('\\');
                escaped.push(character);
            }
            character if !python_character_is_printable(character) && u32::from(character) <= 0xff => {
                escaped.push_str(&format!("\\x{:02x}", u32::from(character)));
            }
            character if !python_character_is_printable(character) && u32::from(character) <= 0xffff => {
                escaped.push_str(&format!("\\u{:04x}", u32::from(character)));
            }
            character if !python_character_is_printable(character) => {
                escaped.push_str(&format!("\\U{:08x}", u32::from(character)));
            }
            character => escaped.push(character),
        }
    }
    format!("{quote}{escaped}{quote}")
}

fn python_character_is_printable(character: char) -> bool {
    if character == ' ' {
        return true;
    }
    !matches!(
        get_general_category(character),
        GeneralCategory::Control
            | GeneralCategory::Format
            | GeneralCategory::LineSeparator
            | GeneralCategory::ParagraphSeparator
            | GeneralCategory::PrivateUse
            | GeneralCategory::SpaceSeparator
            | GeneralCategory::Surrogate
            | GeneralCategory::Unassigned
    )
}

fn python_repr_optional_string(value: Option<&str>) -> String {
    value.map_or_else(|| "None".to_string(), python_repr_string)
}

fn python_string_list(values: &[String]) -> String {
    format!(
        "[{}]",
        values
            .iter()
            .map(|value| python_repr_string(value))
            .collect::<Vec<_>>()
            .join(", ")
    )
}
