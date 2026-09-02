use std::sync::OnceLock;

use indexmap::IndexMap;
use chrono::{
    FixedOffset, Local, NaiveDate, NaiveDateTime, NaiveTime, TimeDelta, TimeZone,
    Weekday,
};
use regex::Regex;
use serde_json::{Map, Number, Value};

use crate::model::{
    Message, MessageType, Tool, ToolResult, ToolUse, canonical_integer,
    canonicalize_json_numbers, messages_from_json, python_repr_string,
    python_value_string, tool_input_needs_wrapper,
    tool_schema, value_is_truthy,
};

const DOCUMENT_SEPARATOR: &str = "\n\n---\n\n";

pub fn json_to_xml(content: &str) -> Result<String, String> {
    if content.starts_with('\u{feff}') {
        return Err(
            "Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)"
                .to_string(),
        );
    }
    validate_json(content)?;
    if content.trim_start().as_bytes().first() != Some(&b'[') {
        return Err("Expected the JSON root to be an array of messages.".to_string());
    }
    let mut value = serde_json::from_str(content).map_err(|error| python_json_error(content, &error))?;
    canonicalize_json_numbers(&mut value)?;
    let messages = messages_from_json(value)?;
    format_xml(&messages)
}

pub fn xml_to_json(content: &str) -> Result<String, String> {
    let messages = messages_from_xml(content.trim_end_matches('\n'))?;
    let value = messages_to_json(&messages);
    serde_json::to_string_pretty(&value).map_err(|error| error.to_string())
}

fn validate_json(content: &str) -> Result<(), String> {
    let mut parser = JsonValidator {
        content,
        bytes: content.as_bytes(),
        index: 0,
    };
    parser.skip_whitespace();
    parser.parse_value()?;
    parser.skip_whitespace();
    if parser.index != parser.bytes.len() {
        return Err(parser.error("Extra data", parser.index));
    }
    Ok(())
}

struct JsonValidator<'content> {
    content: &'content str,
    bytes: &'content [u8],
    index: usize,
}

impl JsonValidator<'_> {
    fn parse_value(&mut self) -> Result<(), String> {
        match self.bytes.get(self.index).copied() {
            Some(b'"') => self.parse_string(),
            Some(b'{') => self.parse_object(),
            Some(b'[') => self.parse_array(),
            Some(b't') if self.consume_literal(b"true") => Ok(()),
            Some(b'f') if self.consume_literal(b"false") => Ok(()),
            Some(b'n') if self.consume_literal(b"null") => Ok(()),
            Some(b'-' | b'0'..=b'9') if self.parse_number() => Ok(()),
            _ => Err(self.error("Expecting value", self.index)),
        }
    }

    fn parse_string(&mut self) -> Result<(), String> {
        let opening_quote = self.index;
        self.index += 1;
        while let Some(byte) = self.bytes.get(self.index).copied() {
            match byte {
                b'"' => {
                    self.index += 1;
                    return Ok(());
                }
                b'\\' => self.parse_escape()?,
                0x00..=0x1f => {
                    return Err(self.error("Invalid control character at", self.index));
                }
                _ => self.index += 1,
            }
        }
        Err(self.error("Unterminated string starting at", opening_quote))
    }

    fn parse_escape(&mut self) -> Result<(), String> {
        let escape = self.index;
        self.index += 1;
        match self.bytes.get(self.index).copied() {
            Some(b'"' | b'\\' | b'/' | b'b' | b'f' | b'n' | b'r' | b't') => {
                self.index += 1;
                Ok(())
            }
            Some(b'u') => {
                let unicode_position = self.index;
                self.index += 1;
                let end = self.index + 4;
                let valid = end <= self.bytes.len()
                    && self.bytes[self.index..end]
                        .iter()
                        .all(u8::is_ascii_hexdigit);
                if !valid {
                    return Err(self.error("Invalid \\uXXXX escape", unicode_position));
                }
                self.index = end;
                Ok(())
            }
            _ => Err(self.error("Invalid \\escape", escape)),
        }
    }

    fn parse_array(&mut self) -> Result<(), String> {
        self.index += 1;
        self.skip_whitespace();
        if self.consume_byte(b']') {
            return Ok(());
        }
        loop {
            self.parse_value()?;
            self.skip_whitespace();
            if self.consume_byte(b']') {
                return Ok(());
            }
            if !self.consume_byte(b',') {
                return Err(self.error("Expecting ',' delimiter", self.index));
            }
            let comma = self.index - 1;
            self.skip_whitespace();
            if self.bytes.get(self.index) == Some(&b']') {
                return Err(self.error("Illegal trailing comma before end of array", comma));
            }
        }
    }

    fn parse_object(&mut self) -> Result<(), String> {
        self.index += 1;
        self.skip_whitespace();
        if self.consume_byte(b'}') {
            return Ok(());
        }
        loop {
            if self.bytes.get(self.index) != Some(&b'"') {
                return Err(self.error(
                    "Expecting property name enclosed in double quotes",
                    self.index,
                ));
            }
            self.parse_string()?;
            self.skip_whitespace();
            if !self.consume_byte(b':') {
                return Err(self.error("Expecting ':' delimiter", self.index));
            }
            self.skip_whitespace();
            self.parse_value()?;
            self.skip_whitespace();
            if self.consume_byte(b'}') {
                return Ok(());
            }
            if !self.consume_byte(b',') {
                return Err(self.error("Expecting ',' delimiter", self.index));
            }
            let comma = self.index - 1;
            self.skip_whitespace();
            if self.bytes.get(self.index) == Some(&b'}') {
                return Err(self.error("Illegal trailing comma before end of object", comma));
            }
        }
    }

    fn parse_number(&mut self) -> bool {
        let start = self.index;
        if self.bytes.get(self.index) == Some(&b'-') {
            self.index += 1;
        }
        match self.bytes.get(self.index).copied() {
            Some(b'0') => self.index += 1,
            Some(b'1'..=b'9') => {
                self.index += 1;
                while self.bytes.get(self.index).is_some_and(u8::is_ascii_digit) {
                    self.index += 1;
                }
            }
            _ => {
                self.index = start;
                return false;
            }
        }
        if self.bytes.get(self.index) == Some(&b'.')
            && self
                .bytes
                .get(self.index + 1)
                .is_some_and(u8::is_ascii_digit)
        {
            self.index += 2;
            while self.bytes.get(self.index).is_some_and(u8::is_ascii_digit) {
                self.index += 1;
            }
        }
        if self.bytes.get(self.index).is_some_and(|byte| matches!(byte, b'e' | b'E')) {
            let exponent = self.index;
            let mut cursor = self.index + 1;
            if self
                .bytes
                .get(cursor)
                .is_some_and(|byte| matches!(byte, b'+' | b'-'))
            {
                cursor += 1;
            }
            if self.bytes.get(cursor).is_some_and(u8::is_ascii_digit) {
                self.index = cursor + 1;
                while self.bytes.get(self.index).is_some_and(u8::is_ascii_digit) {
                    self.index += 1;
                }
            } else {
                self.index = exponent;
            }
        }
        true
    }

    fn consume_literal(&mut self, literal: &[u8]) -> bool {
        if !self.bytes[self.index..].starts_with(literal) {
            return false;
        }
        self.index += literal.len();
        true
    }

    fn consume_byte(&mut self, expected: u8) -> bool {
        if self.bytes.get(self.index) != Some(&expected) {
            return false;
        }
        self.index += 1;
        true
    }

    fn skip_whitespace(&mut self) {
        while self
            .bytes
            .get(self.index)
            .is_some_and(|byte| matches!(byte, b' ' | b'\t' | b'\r' | b'\n'))
        {
            self.index += 1;
        }
    }

    fn error(&self, message: &str, byte_position: usize) -> String {
        let character = self.content[..byte_position].chars().count();
        let preceding = &self.content[..byte_position];
        let line = preceding.bytes().filter(|byte| *byte == b'\n').count() + 1;
        let line_start = preceding.rfind('\n').map_or(0, |index| index + 1);
        let column = self.content[line_start..byte_position].chars().count() + 1;
        format!("{message}: line {line} column {column} (char {character})")
    }
}

fn python_json_error(content: &str, error: &serde_json::Error) -> String {
    let serde_message = error.to_string();
    let line = error.line();
    let column = error.column();
    let line_start = content
        .match_indices('\n')
        .take(line.saturating_sub(1))
        .last()
        .map_or(0, |(index, _)| index + 1);
    let mut character = line_start
        + content[line_start..]
            .char_indices()
            .take(column.saturating_sub(1))
            .last()
            .map_or(0, |(index, value)| index + value.len_utf8());
    let (message, output_column) = if serde_message.starts_with("expected value") {
        ("Expecting value", column.max(1))
    } else if serde_message.starts_with("EOF while parsing a value") {
        character = content.len();
        ("Expecting value", column + 1)
    } else if serde_message.starts_with("EOF while parsing an object")
        || serde_message.starts_with("key must be a string")
    {
        character = content.len().max(character);
        ("Expecting property name enclosed in double quotes", column + 1)
    } else if serde_message.starts_with("EOF while parsing a list") {
        character = content.len();
        ("Expecting value", column + 1)
    } else if serde_message.starts_with("trailing characters") {
        ("Extra data", column)
    } else if serde_message.starts_with("expected `:`") {
        ("Expecting ':' delimiter", column)
    } else if serde_message.starts_with("expected `,` or `}`")
        || serde_message.starts_with("expected `,` or `]`")
    {
        ("Expecting ',' delimiter", column)
    } else {
        let message = serde_message
            .split(" at line ")
            .next()
            .unwrap_or("Expecting value");
        return format!("{message}: line {line} column {column} (char {character})");
    };
    format!("{message}: line {line} column {output_column} (char {character})")
}

pub fn format_xml(messages: &[Message]) -> Result<String, String> {
    let blocks = messages
        .iter()
        .filter_map(|message| format_message_xml(message).transpose())
        .collect::<Result<Vec<_>, _>>()?;
    Ok(blocks.join(DOCUMENT_SEPARATOR))
}

fn format_message_xml(message: &Message) -> Result<Option<String>, String> {
    let (mut content, text_encoding) = render_message_inner_xml(message, true)?;
    if content.is_empty() {
        return Ok(None);
    }
    while content.ends_with('\n') {
        content.pop();
    }
    if content.ends_with(' ') && !content.ends_with("  ") {
        content.pop();
    }
    if message.message_type == MessageType::Agent {
        content = indent_agent_body(&content);
    }
    let attributes = message_attributes(message, text_encoding.as_deref())?;
    Ok(Some(format!(
        "<{} {}>\n{}\n\n{}\n</{}>",
        message.message_type.tag(),
        attributes,
        message.header(),
        content,
        message.message_type.tag()
    )))
}

/// Render one message's inner XML.
///
/// `encode_transport` is the difference between the two readers of this output.
/// `ch parse` needs a document it can decode back, so it escapes delimiters that
/// would otherwise reopen a block. Search matches against the semantic text, so it
/// asks for the same render with the escaping off.
pub fn render_message_inner_xml(
    message: &Message,
    encode_transport: bool,
) -> Result<(String, Option<String>), String> {
    let mut parts = Vec::new();
    let mut text_encoding = None;
    if let Some(task) = message.subagent_task.as_deref().filter(|value| !value.is_empty()) {
        parts.push(render_inner_block("subagent-task", task, &[], encode_transport));
    }
    if !message.text.is_empty() {
        if encode_transport {
            let (text, encoding) = encode_xml_text(&message.text);
            parts.push(text);
            text_encoding = encoding;
        } else {
            parts.push(message.text.clone());
        }
    }
    if let Some(thinking) = message.thinking.as_deref().filter(|value| !value.is_empty()) {
        parts.push(render_inner_block("thinking", thinking, &[], encode_transport));
    }
    if !message.tools.is_empty() {
        parts.push(
            message
                .tools
                .iter()
                .map(|tool| render_tool_xml(tool, encode_transport))
                .collect::<Result<Vec<_>, _>>()?
                .join("\n"),
        );
    }
    if let Some(plan) = message.plan.as_deref().filter(|value| !value.is_empty()) {
        parts.push(render_inner_block(
            "tool-input",
            plan,
            &[("name".to_string(), "ExitPlanMode".to_string())],
            encode_transport,
        ));
    }
    Ok((parts.join("\n\n"), text_encoding))
}

fn encode_xml_text(text: &str) -> (String, Option<String>) {
    if !inner_opening_regex().is_match(text) {
        return (text.to_string(), None);
    }
    (escape_html_text(text), Some("html".to_string()))
}

fn render_tool_xml(tool: &Tool, encode_transport: bool) -> Result<String, String> {
    match tool {
        Tool::Use(tool) => render_tool_use_xml(tool, encode_transport),
        Tool::Result(tool) => Ok(render_tool_result_xml(tool, encode_transport)),
    }
}

/// A tool's attributes and body, which is what **both** consumers need.
///
/// The XML renderers below build a tag from it; `session_render` builds a header and
/// a rail from the same values. Python calls this a `ToolParts`, and computing it
/// twice is how the two routes would drift.
pub struct ToolParts {
    pub attributes: Vec<(String, String)>,
    pub content: Option<String>,
    /// A tool result's body **before** it is fenced, which is what a `Read` result's
    /// line-number gutter reads. `None` for a tool use, exactly as Python's
    /// `ToolParts.output_text` is.
    pub output_text: Option<String>,
}

/// A tool-use's attributes and body.
pub fn tool_use_parts(tool: &ToolUse) -> Result<ToolParts, String> {
    let mut attributes = vec![("name".to_string(), tool.name.clone())];
    if let Some(id) = short_tool_id(tool.id.as_deref()) {
        attributes.push(("id".to_string(), id));
    }
    let mut content = None;
    if let Some(schema) = tool_schema(&tool.name) {
        let input = tool.input.as_object();
        for key in schema.attribute_keys {
            let Some(value) = input.and_then(|values| values.get(*key)) else {
                continue;
            };
            if value_is_truthy(value) {
                attributes.push((key.to_string(), python_value_string(value)));
            }
        }
        if tool.name == "Edit" {
            content = input.map(format_edit_content).filter(|value| !value.is_empty());
        } else if let Some(content_key) = schema.content_key {
            let value = input.and_then(|values| values.get(content_key));
            if value.is_some_and(value_is_truthy) {
                let language = schema.content_language.unwrap_or("");
                content = Some(format!(
                    "```{language}\n{}\n```",
                    python_value_string(value.expect("truthy content exists"))
                ));
            }
        }
    } else if value_is_truthy(&tool.input) {
        content = Some(format!(
            "```json\n{}\n```",
            json_pretty_ensure_ascii(&tool.input)?
        ));
    }
    Ok(ToolParts { attributes, content, output_text: None })
}

fn render_tool_use_xml(tool: &ToolUse, encode_transport: bool) -> Result<String, String> {
    let ToolParts { attributes, content, .. } = tool_use_parts(tool)?;
    Ok(match content {
        Some(content) => {
            render_inner_block("tool-input", &content, &attributes, encode_transport)
        }
        None => empty_inner_block("tool-input", &attributes),
    })
}

fn format_edit_content(input: &Map<String, Value>) -> String {
    let mut parts = Vec::new();
    if let Some(value) = input.get("old_string").filter(|value| value_is_truthy(value)) {
        parts.push(format!(
            "old_string:\n```\n{}\n```",
            python_value_string(value)
        ));
    }
    if let Some(value) = input.get("new_string").filter(|value| value_is_truthy(value)) {
        parts.push(format!(
            "new_string:\n```\n{}\n```",
            python_value_string(value)
        ));
    }
    parts.join("\n")
}

/// A tool-result's attributes and body, on the same terms.
pub fn tool_result_parts(tool: &ToolResult) -> ToolParts {
    let mut attributes = Vec::new();
    if let Some(name) = tool.name.as_deref().filter(|value| !value.is_empty()) {
        attributes.push(("name".to_string(), name.to_string()));
    }
    if let Some(id) = short_tool_id(tool.tool_use_id.as_deref()) {
        attributes.push(("id".to_string(), id));
    }
    if tool.is_error {
        attributes.push(("is_error".to_string(), "true".to_string()));
    }
    let content_text = tool
        .content
        .as_ref()
        .map(extract_text_content)
        .unwrap_or_default()
        .join("\n");
    let content = (!content_text.is_empty()).then(|| format!("```\n{content_text}\n```"));
    let output_text = (!content_text.is_empty()).then_some(content_text);
    ToolParts { attributes, content, output_text }
}

fn render_tool_result_xml(tool: &ToolResult, encode_transport: bool) -> String {
    let ToolParts { attributes, content, .. } = tool_result_parts(tool);
    match content {
        Some(content) => {
            render_inner_block("tool-output", &content, &attributes, encode_transport)
        }
        None => empty_inner_block("tool-output", &attributes),
    }
}

fn extract_text_content(content: &Value) -> Vec<String> {
    match content {
        Value::String(value) if !value.is_empty() => vec![value.clone()],
        Value::Array(values) => values
            .iter()
            .filter_map(|value| match value {
                Value::String(text) if !text.is_empty() => Some(text.clone()),
                Value::Object(block) if block.get("type").and_then(Value::as_str) == Some("text") => {
                    block.get("text").and_then(Value::as_str).filter(|text| !text.is_empty()).map(str::to_string)
                }
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    }
}

fn short_tool_id(id: Option<&str>) -> Option<String> {
    let id = id?;
    let id = id.strip_prefix("toolu_").unwrap_or(id);
    let id = id.strip_prefix("call_").unwrap_or(id);
    if id.is_empty() {
        return None;
    }
    Some(id.chars().take(4).collect())
}

fn render_inner_block(
    tag: &str,
    body: &str,
    attributes: &[(String, String)],
    encode_transport: bool,
) -> String {
    let mut attributes = attributes.to_vec();
    let body = if encode_transport && body.contains(&format!("</{tag}>")) {
        attributes.push(("encoding".to_string(), "html".to_string()));
        escape_html_text(body)
    } else {
        body.to_string()
    };
    let opening = opening_tag(tag, &attributes);
    format!("{opening}\n{body}\n</{tag}>")
}

fn empty_inner_block(tag: &str, attributes: &[(String, String)]) -> String {
    format!("{}</{tag}>", opening_tag(tag, attributes))
}

fn opening_tag(tag: &str, attributes: &[(String, String)]) -> String {
    if attributes.is_empty() {
        return format!("<{tag}>");
    }
    format!(
        "<{tag} {}>",
        attributes
            .iter()
            .map(|(name, value)| format!(r#"{name}="{value}""#))
            .collect::<Vec<_>>()
            .join(" ")
    )
}

fn message_attributes(message: &Message, text_encoding: Option<&str>) -> Result<String, String> {
    let mut attributes = vec![("i".to_string(), message.original_index.to_string())];
    if let Some(value) = &message.branch {
        attributes.push(("branch".to_string(), value.clone()));
    }
    if message.role == "user" {
        if message.is_meta {
            attributes.push(("isMeta".to_string(), "true".to_string()));
        }
        if let Some(value) = &message.source_tool_user_id {
            attributes.push(("sourceToolUserId".to_string(), value.clone()));
        }
    }
    if let Some(value) = &message.agent_id {
        attributes.push(("agent_id".to_string(), value.clone()));
        if let Some(value) = &message.subagent_type {
            attributes.push(("subagent_type".to_string(), value.clone()));
        }
        if let Some(value) = &message.name {
            attributes.push(("name".to_string(), value.clone()));
        }
    }
    if let Some(value) = message.display_model() {
        attributes.push(("model".to_string(), value.to_string()));
    }
    if let Some(value) = &message.custom_type {
        attributes.push(("custom_type".to_string(), value.clone()));
    }
    if let Some(value) = message.inherited_context {
        attributes.push(("inherited_context".to_string(), value.to_string()));
    }
    if let Some(value) = &message.status {
        attributes.push(("status".to_string(), value.clone()));
    }
    if let Some(value) = text_encoding {
        attributes.push(("text_encoding".to_string(), value.to_string()));
    }
    if let Some(timestamp) = &message.timestamp {
        attributes.push(("date".to_string(), timestamp_to_date(timestamp)?));
    }
    let escape_attributes = message.custom_type.is_some();
    Ok(attributes
        .iter()
        .map(|(name, value)| {
            let value = if escape_attributes {
                escape_html_attribute(value)
            } else {
                value.clone()
            };
            format!(r#"{name}="{value}""#)
        })
        .collect::<Vec<_>>()
        .join(" "))
}

/// A message timestamp as local naive time.
///
/// Both date renderings read from here rather than each parsing the string: the
/// XML attribute wants `%Y-%m-%d %H:%M` and the coloured badge wants
/// `August 20th, 11:01`, and a second parser is a second set of edge cases.
pub fn message_local_datetime(timestamp: &str) -> Result<NaiveDateTime, String> {
    let invalid_isoformat = || {
        format!(
            "Invalid isoformat string: {}",
            python_repr_string(timestamp)
        )
    };
    let normalized = timestamp.replace(',', ".");
    let (datetime, parsed_offset) = split_iso_offset(&normalized);
    let (mut date, time, rolls_to_next_day) = match parse_iso_date_time(datetime) {
        Ok(Some(value)) => value,
        Ok(None) | Err(IsoDateTimeError::Invalid) => return Err(invalid_isoformat()),
        Err(IsoDateTimeError::NonzeroAfterHour24) => {
            return Err(
                "minute, second, and microsecond must be 0 when hour is 24"
                    .to_string(),
            );
        }
    };
    if rolls_to_next_day {
        date = date.succ_opt().ok_or_else(invalid_isoformat)?;
    }
    let naive = NaiveDateTime::new(date, time);
    let Some(parsed_offset) = parsed_offset else {
        // Python's `_message_timestamp_datetime` leaves a naive timestamp naive.
        return Ok(naive);
    };
    let offset = FixedOffset::east_opt(parsed_offset.seconds).ok_or_else(invalid_isoformat)?;
    let value = offset
        .from_local_datetime(&naive)
        .single()
        .ok_or_else(invalid_isoformat)?
        .checked_sub_signed(TimeDelta::microseconds(
            parsed_offset.fractional_microseconds,
        ))
        .ok_or_else(invalid_isoformat)?;
    Ok(value.with_timezone(&Local).naive_local())
}

fn timestamp_to_date(timestamp: &str) -> Result<String, String> {
    Ok(message_local_datetime(timestamp)?
        .format("%Y-%m-%d %H:%M")
        .to_string())
}

#[derive(Clone, Copy)]
struct ParsedIsoOffset {
    seconds: i32,
    fractional_microseconds: i64,
}

fn split_iso_offset(value: &str) -> (&str, Option<ParsedIsoOffset>) {
    if let Some(datetime) = value.strip_suffix('Z') {
        return (
            datetime,
            Some(ParsedIsoOffset {
                seconds: 0,
                fractional_microseconds: 0,
            }),
        );
    }
    let offset_start = value
        .char_indices()
        .rev()
        .find_map(|(index, character)| {
            (index > 10 && matches!(character, '+' | '-')).then_some(index)
        });
    let Some(offset_start) = offset_start else {
        return (value, None);
    };
    let offset = &value[offset_start..];
    match parse_iso_offset(offset) {
        Some(parsed_offset) => (&value[..offset_start], Some(parsed_offset)),
        None => (value, None),
    }
}

fn parse_iso_offset(value: &str) -> Option<ParsedIsoOffset> {
    let sign = match value.as_bytes().first()? {
        b'+' => 1,
        b'-' => -1,
        _ => return None,
    };
    let (whole, fraction) = value[1..]
        .split_once('.')
        .map_or((&value[1..], None), |(whole, fraction)| {
            (whole, Some(fraction))
        });
    let digits = whole.replace(':', "");
    if !digits.is_ascii()
        || !matches!(digits.len(), 2 | 4 | 6)
        || !digits.bytes().all(|byte| byte.is_ascii_digit())
    {
        return None;
    }
    if fraction.is_some() && digits.len() != 6 {
        return None;
    }
    let fractional_microseconds = match fraction {
        Some(fraction) => parse_fractional_microseconds(fraction)?,
        None => 0,
    };
    let hours = digits[0..2].parse::<i32>().ok()?;
    let minutes = digits.get(2..4).unwrap_or("0").parse::<i32>().ok()?;
    let seconds = digits.get(4..6).unwrap_or("0").parse::<i32>().ok()?;
    if hours > 23 || minutes > 59 || seconds > 59 {
        return None;
    }
    Some(ParsedIsoOffset {
        seconds: sign * (hours * 3600 + minutes * 60 + seconds),
        fractional_microseconds: i64::from(sign) * i64::from(fractional_microseconds),
    })
}

#[derive(Clone, Copy)]
enum IsoDateTimeError {
    Invalid,
    NonzeroAfterHour24,
}

fn parse_iso_date_time(
    value: &str,
) -> Result<Option<(NaiveDate, NaiveTime, bool)>, IsoDateTimeError> {
    for date_length in [10, 8, 7] {
        let Some(date_text) = value.get(..date_length) else {
            continue;
        };
        let Some(date) = parse_iso_date(date_text) else {
            continue;
        };
        let remainder = value
            .get(date_length..)
            .ok_or(IsoDateTimeError::Invalid)?;
        if remainder.is_empty() {
            let midnight = NaiveTime::from_hms_opt(0, 0, 0)
                .ok_or(IsoDateTimeError::Invalid)?;
            return Ok(Some((date, midnight, false)));
        }
        let separator_length = remainder
            .chars()
            .next()
            .ok_or(IsoDateTimeError::Invalid)?
            .len_utf8();
        let time_text = remainder
            .get(separator_length..)
            .ok_or(IsoDateTimeError::Invalid)?;
        let (time, rolls_to_next_day) = parse_iso_time(time_text)?;
        return Ok(Some((date, time, rolls_to_next_day)));
    }
    Ok(None)
}

fn parse_iso_date(value: &str) -> Option<NaiveDate> {
    if let Ok(date) = NaiveDate::parse_from_str(value, "%Y-%m-%d") {
        return Some(date);
    }
    if let Ok(date) = NaiveDate::parse_from_str(value, "%Y%m%d") {
        return Some(date);
    }
    let compact = value.replace('-', "");
    if !compact.is_ascii() {
        return None;
    }
    let bytes = compact.as_bytes();
    if bytes.len() < 7 || bytes.get(4) != Some(&b'W') {
        return None;
    }
    let year = compact[0..4].parse::<i32>().ok()?;
    let week = compact[5..7].parse::<u32>().ok()?;
    let day = compact
        .get(7..8)
        .map_or(Ok(1), str::parse::<u32>)
        .ok()?;
    let weekday = match day {
        1 => Weekday::Mon,
        2 => Weekday::Tue,
        3 => Weekday::Wed,
        4 => Weekday::Thu,
        5 => Weekday::Fri,
        6 => Weekday::Sat,
        7 => Weekday::Sun,
        _ => return None,
    };
    NaiveDate::from_isoywd_opt(year, week, weekday)
}

fn parse_iso_time(value: &str) -> Result<(NaiveTime, bool), IsoDateTimeError> {
    let (whole, fraction) = value
        .split_once('.')
        .map_or((value, None), |(whole, fraction)| (whole, Some(fraction)));
    let components = if whole.contains(':') {
        let components = whole.split(':').collect::<Vec<_>>();
        if !matches!(components.len(), 2 | 3)
            || components.iter().any(|component| component.len() != 2)
        {
            return Err(IsoDateTimeError::Invalid);
        }
        components
    } else {
        if !matches!(whole.len(), 2 | 4 | 6) || !whole.is_ascii() {
            return Err(IsoDateTimeError::Invalid);
        }
        whole
            .as_bytes()
            .chunks_exact(2)
            .map(|component| std::str::from_utf8(component).expect("ASCII time component"))
            .collect()
    };
    if components.iter().any(|component| {
        !component.bytes().all(|byte| byte.is_ascii_digit())
    }) {
        return Err(IsoDateTimeError::Invalid);
    }
    if fraction.is_some() && components.len() != 3 {
        return Err(IsoDateTimeError::Invalid);
    }
    let hour = components[0]
        .parse::<u32>()
        .map_err(|_| IsoDateTimeError::Invalid)?;
    let minute = components
        .get(1)
        .map_or(Ok(0), |value| value.parse::<u32>())
        .map_err(|_| IsoDateTimeError::Invalid)?;
    let second = components
        .get(2)
        .map_or(Ok(0), |value| value.parse::<u32>())
        .map_err(|_| IsoDateTimeError::Invalid)?;
    let microsecond = match fraction {
        Some(fraction) => {
            parse_fractional_microseconds(fraction).ok_or(IsoDateTimeError::Invalid)?
        }
        None => 0,
    };
    if hour == 24 {
        if minute == 0 && second == 0 && microsecond == 0 {
            let midnight = NaiveTime::from_hms_opt(0, 0, 0)
                .ok_or(IsoDateTimeError::Invalid)?;
            return Ok((midnight, true));
        }
        return Err(IsoDateTimeError::NonzeroAfterHour24);
    }
    let time = NaiveTime::from_hms_micro_opt(hour, minute, second, microsecond)
        .ok_or(IsoDateTimeError::Invalid)?;
    Ok((time, false))
}

fn parse_fractional_microseconds(value: &str) -> Option<u32> {
    if value.is_empty() || !value.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    let retained = &value[..value.len().min(6)];
    let mut microseconds = retained.parse::<u32>().ok()?;
    for _ in retained.len()..6 {
        microseconds *= 10;
    }
    Some(microseconds)
}

fn indent_agent_body(content: &str) -> String {
    content
        .split_inclusive('\n')
        .map(|line| {
            if line.trim().is_empty() {
                line.to_string()
            } else {
                format!("  {line}")
            }
        })
        .collect()
}

pub fn messages_from_xml(content: &str) -> Result<Vec<Message>, String> {
    let mut messages = Vec::new();
    let mut cursor = 0;
    while cursor < content.len() {
        let position = messages.len() + 1;
        let (message, next_cursor) = parse_document_message(content, cursor, position)?;
        messages.push(message);
        cursor = next_cursor;
    }
    Ok(messages)
}

fn parse_document_message(
    content: &str,
    cursor: usize,
    position: usize,
) -> Result<(Message, usize), String> {
    let remainder = &content[cursor..];
    let opening_end = remainder
        .find("\n")
        .ok_or_else(|| format!("Expected XML-tagged Markdown message {position}."))?;
    let opening = &remainder[..opening_end];
    let opening_match = outer_opening_regex()
        .captures(opening)
        .ok_or_else(|| format!("Expected XML-tagged Markdown message {position}."))?;
    let tag = opening_match.name("tag").expect("outer tag capture").as_str();
    let message_type = MessageType::from_tag(tag)
        .ok_or_else(|| format!("Expected XML-tagged Markdown message {position}."))?;
    let close_marker = format!("\n</{tag}>");
    let search_start = opening_end + 1;
    let mut close_search = search_start;
    let (close_start, _close_end, next_cursor) = loop {
        let relative_close = remainder[close_search..]
            .find(&close_marker)
            .ok_or_else(|| format!("Expected XML-tagged Markdown message {position}."))?;
        let close_start = close_search + relative_close;
        let close_end = close_start + close_marker.len();
        let after = &remainder[close_end..];
        if after.is_empty() {
            break (close_start, close_end, content.len());
        }
        if after.starts_with(DOCUMENT_SEPARATOR) {
            break (
                close_start,
                close_end,
                cursor + close_end + DOCUMENT_SEPARATOR.len(),
            );
        }
        close_search = close_end;
    };
    let inner = &remainder[search_start..close_start];
    let header_end = inner
        .find("\n\n")
        .ok_or_else(|| format!("Expected XML-tagged Markdown message {position}."))?;
    let header = &inner[..header_end];
    let body = &inner[header_end + 2..];
    let raw_attributes = opening_match
        .name("attrs")
        .map_or("", |attributes| attributes.as_str());
    let mut attributes = parse_attributes(raw_attributes, true);
    for name in [
        "branch",
        "sourceToolUserId",
        "agent_id",
        "subagent_type",
        "name",
        "model",
        "custom_type",
        "status",
        "date",
    ] {
        if attributes.get(name).is_some_and(|value| value.is_empty()) {
            attributes.shift_remove(name);
        }
    }
    let expected_header = expected_header(message_type, &attributes);
    if header != expected_header {
        return Err(format!(
            "Expected message {position} header {}.",
            python_repr_string(&expected_header)
        ));
    }
    let original_index = attributes
        .shift_remove("i")
        .ok_or_else(|| format!("Expected message {position} to have an integer i attribute."))
        .and_then(|value| canonical_integer(&value))
        .map(Number::from_string_unchecked)
        .map_err(|_| format!("Expected message {position} to have an integer i attribute."))?;
    let mut message = Message::new(message_type, message_type.default_role().to_string(), original_index);
    let date = attributes.shift_remove("date");
    message.timestamp = date.map(|date| format!("{}:00", date.replace(' ', "T")));
    message.is_meta = attributes.shift_remove("isMeta").as_deref() == Some("true");
    message.source_tool_user_id = attributes.shift_remove("sourceToolUserId");
    message.custom_type = attributes.shift_remove("custom_type");
    message.status = attributes.shift_remove("status");
    let text_encoding = attributes.shift_remove("text_encoding");
    message.inherited_context = match attributes.shift_remove("inherited_context").as_deref() {
        None => None,
        Some("true") => Some(true),
        Some("false") => Some(false),
        Some(_) => {
            return Err(format!(
                "Expected message {position} inherited_context to be true or false."
            ));
        }
    };
    message.agent_id = attributes.shift_remove("agent_id");
    message.subagent_type = attributes.shift_remove("subagent_type");
    message.name = attributes.shift_remove("name");
    message.model = attributes.shift_remove("model");
    message.branch = attributes.shift_remove("branch");
    if !attributes.is_empty() {
        let mut keys = attributes.keys().cloned().collect::<Vec<_>>();
        keys.sort();
        return Err(format!(
            "Unexpected attributes in message {position}: {}.",
            python_string_list(&keys)
        ));
    }
    let body = if message_type == MessageType::Agent {
        unindent_agent_body(body, position)?
    } else {
        body.to_string()
    };
    populate_xml_content(&mut message, &body, position)?;
    message.text = decode_transport_body(&message.text, text_encoding.as_deref())?;
    if message_type == MessageType::Agent {
        if message.subagent_task.is_some() || message.custom_type.is_some() {
            message.role = "agent".to_string();
        } else if message.is_meta
            || message.source_tool_user_id.is_some()
            || message.contains_only_tool_outputs()
        {
            message.role = "user".to_string();
        }
    }
    Ok((message, next_cursor))
}

/// **Deliberately the crate's `\s` and `\w`, not CPython's, and this is the
/// reason.** The two patterns here serve only `parse_document_message` and
/// `find_inner_opening` — the XML-tagged-Markdown → JSON direction, reachable
/// only from `main.rs`. **Python has no counterpart for that direction**:
/// `cmd_parse` reads a session file and formats *to* xml, json or raw, never
/// back. So there is no CPython class behind these to reproduce, and widening
/// them would be a change with nothing behind it.
///
/// `inner_opening_regex` below is the opposite case and does use CPython's.
/// **Do not "finish the set."**
fn outer_opening_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(
            r#"^<(?P<tag>[\w-]+)(?P<attrs>(?:\s+[\w-]+="[^"]*")*)>$"#,
        )
        .expect("outer opening regex")
    })
}

/// See `outer_opening_regex`: same direction, same absent oracle.
fn attribute_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| Regex::new(r#"([\w-]+)="([^"]*)""#).expect("attribute regex"))
}

/// CPython's `\s` and `\w`, because this one has a live oracle.
///
/// It ports `_INNER_XML_BLOCK_OPENING_PATTERN` at `xml_transport.py:15-19`, and
/// `encode_xml_text` uses it to decide whether message text is HTML-escaped —
/// which reaches `render_message_inner_xml`, the string search matches against.
/// The crate's `\s` misses U+001C..U+001F and its `\w` differs from CPython's in
/// **both** directions; `session::PYTHON_SPACE_CLASS` and `PYTHON_WORD_CLASS`
/// carry the measured equivalents.
fn inner_opening_regex() -> &'static Regex {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    REGEX.get_or_init(|| {
        Regex::new(&format!(
            r#"(?m)^<(?P<tag>thinking|tool-input|tool-output|subagent-task)(?P<attrs>(?:[{space}]+[{word}-]+="[^"]*")*)>"#,
            space = crate::session::PYTHON_SPACE_CLASS,
            word = crate::session::PYTHON_WORD_CLASS,
        ))
        .expect("inner opening regex")
    })
}

fn parse_attributes(content: &str, decode_html: bool) -> IndexMap<String, String> {
    attribute_regex()
        .captures_iter(content)
        .map(|captures| {
            let name = captures.get(1).expect("attribute name").as_str().to_string();
            let raw_value = captures.get(2).expect("attribute value").as_str();
            let value = if decode_html {
                html_escape::decode_html_entities(raw_value).into_owned()
            } else {
                raw_value.to_string()
            };
            (name, value)
        })
        .collect()
}

fn expected_header(message_type: MessageType, attributes: &IndexMap<String, String>) -> String {
    if message_type != MessageType::Agent {
        return message_type.header().to_string();
    }
    if attributes.get("subagent_type").map(String::as_str) == Some("fork") {
        return "## Fork".to_string();
    }
    match attributes.get("name").map(String::as_str) {
        Some(name) => format!("## Agent '{name}'"),
        None => "## Agent".to_string(),
    }
}

fn unindent_agent_body(body: &str, position: usize) -> Result<String, String> {
    body.split_inclusive('\n')
        .map(|line| {
            if line.trim().is_empty() {
                return Ok(line.to_string());
            }
            line.strip_prefix("  ")
                .map(str::to_string)
                .ok_or_else(|| format!("Expected indented agent content in message {position}."))
        })
        .collect()
}

#[derive(Clone)]
struct InnerBlock {
    start: usize,
    end: usize,
    tag: String,
    attributes: IndexMap<String, String>,
    body: String,
}

fn populate_xml_content(message: &mut Message, body: &str, position: usize) -> Result<(), String> {
    let blocks = find_inner_blocks(body);
    if blocks.is_empty() {
        message.text = body.to_string();
        return Ok(());
    }
    message.text = body[..blocks[0].start]
        .strip_suffix("\n\n")
        .unwrap_or(&body[..blocks[0].start])
        .to_string();
    let mut cursor = blocks[0].start;
    for (index, block) in blocks.iter().enumerate() {
        let separator = &body[cursor..block.start];
        let previous = index.checked_sub(1).map(|previous| &blocks[previous]);
        if previous.is_some_and(|previous| previous.tag == "subagent-task") {
            message.text = text_between_blocks(separator, position, false)?;
        } else {
            let expected = match previous {
                None => "",
                Some(previous) if previous.tag.starts_with("tool-") => "\n",
                Some(_) => "\n\n",
            };
            if separator != expected {
                return Err(format!("Unexpected content between blocks in message {position}."));
            }
        }
        append_inner_block(message, block, position)?;
        cursor = block.end;
    }
    let trailing = &body[cursor..];
    if blocks.last().is_some_and(|block| block.tag == "subagent-task") && !trailing.is_empty() {
        message.text = text_between_blocks(trailing, position, true)?;
    } else if !trailing.is_empty() {
        return Err(format!("Unexpected content after blocks in message {position}."));
    }
    Ok(())
}

fn find_inner_blocks(body: &str) -> Vec<InnerBlock> {
    let mut blocks = Vec::new();
    let mut scan = 0;
    while scan < body.len() {
        let Some((start, tag, attributes, opening_end)) = find_inner_opening(body, scan) else {
            break;
        };
        let close = format!("</{tag}>");
        let mut close_scan = opening_end;
        let mut matched_close = None;
        while let Some(relative_close) = body[close_scan..].find(&close) {
            let close_start = close_scan + relative_close;
            let close_end = close_start + close.len();
            if close_end == body.len() || body.as_bytes().get(close_end) == Some(&b'\n') {
                matched_close = Some((close_start, close_end));
                break;
            }
            close_scan = close_end;
        }
        let Some((close_start, close_end)) = matched_close else {
            scan = opening_end;
            continue;
        };
        let mut inner_body = body[opening_end..close_start].to_string();
        if inner_body.starts_with('\n') {
            inner_body.remove(0);
        }
        if inner_body.ends_with('\n') {
            inner_body.pop();
        }
        blocks.push(InnerBlock {
            start,
            end: close_end,
            tag,
            attributes,
            body: inner_body,
        });
        scan = close_end;
    }
    blocks
}

fn find_inner_opening(
    body: &str,
    scan: usize,
) -> Option<(usize, String, IndexMap<String, String>, usize)> {
    let captures = inner_opening_regex().captures(&body[scan..])?;
    let complete_match = captures.get(0)?;
    let tag = captures.name("tag")?.as_str().to_string();
    let attributes = captures
        .name("attrs")
        .map_or_else(IndexMap::new, |value| parse_attributes(value.as_str(), false));
    let start = scan + complete_match.start();
    let opening_end = scan + complete_match.end();
    Some((start, tag, attributes, opening_end))
}

fn text_between_blocks(content: &str, position: usize, trailing: bool) -> Result<String, String> {
    let prefix = "\n\n";
    let suffix = if trailing { "" } else { "\n\n" };
    if !content.starts_with(prefix) || !content.ends_with(suffix) {
        return Err(format!("Unexpected content after subagent task in message {position}."));
    }
    let end = content.len() - suffix.len();
    if end <= prefix.len() {
        return Ok(String::new());
    }
    Ok(content[prefix.len()..end].to_string())
}

fn append_inner_block(
    message: &mut Message,
    block: &InnerBlock,
    position: usize,
) -> Result<(), String> {
    let mut attributes = block.attributes.clone();
    let body = decode_transport_body(&block.body, attributes.shift_remove("encoding").as_deref())?;
    match block.tag.as_str() {
        "thinking" => message.thinking = Some(body),
        "subagent-task" => message.subagent_task = Some(body),
        "tool-output" => {
            let name = attributes.shift_remove("name");
            message
                .tools
                .push(Tool::Result(tool_output_from_xml(name, attributes, body, position)?));
        }
        "tool-input" => {
            let name = attributes.shift_remove("name").ok_or_else(|| {
                format!("Expected tool input in message {position} to have a name.")
            })?;
            if name == "ExitPlanMode" {
                message.plan = Some(body);
            } else {
                message.tools.push(Tool::Use(tool_input_from_xml(
                    name,
                    attributes,
                    body,
                    position,
                )?));
            }
        }
        _ => unreachable!("known inner tag"),
    }
    Ok(())
}

fn tool_input_from_xml(
    name: String,
    mut attributes: IndexMap<String, String>,
    body: String,
    position: usize,
) -> Result<ToolUse, String> {
    let id = attributes.shift_remove("id");
    let input = if let Some(schema) = tool_schema(&name) {
        let mut input = attributes
            .into_iter()
            .map(|(key, value)| (key, Value::String(value)))
            .collect::<Map<_, _>>();
        if name == "Edit" && !body.is_empty() {
            input.extend(edit_input_from_body(&body, position)?.into_iter());
        } else if let Some(content_key) = schema.content_key {
            if !body.is_empty() {
                input.insert(content_key.to_string(), Value::String(unfence(&body)));
            }
        }
        Value::Object(input)
    } else if body.is_empty() {
        Value::Object(
            attributes
                .into_iter()
                .map(|(key, value)| (key, Value::String(value)))
                .collect(),
        )
    } else {
        parse_embedded_python_json(&unfence(&body))?
    };
    Ok(ToolUse {
        name,
        input,
        id,
        native_tool_call_id: None,
        native_content_index: None,
    })
}

fn parse_embedded_python_json(content: &str) -> Result<Value, String> {
    let normalized = normalize_python_json_constants(content);
    validate_json(&normalized)?;
    let mut value = serde_json::from_str(&normalized)
        .map_err(|error| python_json_error(&normalized, &error))?;
    canonicalize_json_numbers(&mut value)?;
    Ok(value)
}

pub(crate) fn normalize_python_json_constants(content: &str) -> String {
    let mut normalized = String::with_capacity(content.len());
    let mut index = 0;
    let mut in_string = false;
    let mut escaped = false;
    while index < content.len() {
        let remainder = &content[index..];
        if !in_string && remainder.starts_with("-Infinity") {
            normalized.push_str("-1e999999");
            index += "-Infinity".len();
            continue;
        }
        if !in_string && remainder.starts_with("Infinity") {
            normalized.push_str("1e999999");
            index += "Infinity".len();
            continue;
        }
        let character = remainder
            .chars()
            .next()
            .expect("nonempty JSON remainder has one character");
        normalized.push(character);
        index += character.len_utf8();
        if !in_string {
            if character == '"' {
                in_string = true;
            }
            continue;
        }
        if escaped {
            escaped = false;
            continue;
        }
        if character == '\\' {
            escaped = true;
            continue;
        }
        if character == '"' {
            in_string = false;
        }
    }
    normalized
}

fn tool_output_from_xml(
    name: Option<String>,
    mut attributes: IndexMap<String, String>,
    body: String,
    position: usize,
) -> Result<ToolResult, String> {
    let mut unexpected = attributes
        .keys()
        .filter(|key| !["id", "is_error"].contains(&key.as_str()))
        .cloned()
        .collect::<Vec<_>>();
    unexpected.sort();
    if !unexpected.is_empty() {
        return Err(format!(
            "Unexpected tool output attributes in message {position}: {}.",
            python_string_list(&unexpected)
        ));
    }
    let tool_use_id = attributes.shift_remove("id");
    let is_error = attributes.shift_remove("is_error").as_deref() == Some("true");
    let has_content = !body.is_empty();
    Ok(ToolResult {
        name,
        tool_use_id,
        native_tool_call_id: None,
        is_error,
        content: has_content.then(|| Value::String(unfence(&body))),
        has_content,
    })
}

fn unfence(body: &str) -> String {
    let Some(after_open) = body.strip_prefix("```") else {
        return body.to_string();
    };
    let Some(first_newline) = after_open.find('\n') else {
        return body.to_string();
    };
    let content = &after_open[first_newline + 1..];
    content
        .strip_suffix("\n```")
        .unwrap_or(body)
        .to_string()
}

fn edit_input_from_body(body: &str, position: usize) -> Result<Map<String, Value>, String> {
    static REGEX: OnceLock<Regex> = OnceLock::new();
    let captures = REGEX
        .get_or_init(|| {
            Regex::new(
                r"(?s)^(?:old_string:\n```\n(?P<old>.*?)\n```)?(?:\n?new_string:\n```\n(?P<new>.*?)\n```)?$",
            )
            .expect("edit body regex")
        })
        .captures(body)
        .ok_or_else(|| format!("Expected canonical Edit body in message {position}."))?;
    let mut input = Map::new();
    if let Some(value) = captures.name("old") {
        input.insert("old_string".to_string(), Value::String(value.as_str().to_string()));
    }
    if let Some(value) = captures.name("new") {
        input.insert("new_string".to_string(), Value::String(value.as_str().to_string()));
    }
    Ok(input)
}

fn decode_transport_body(body: &str, encoding: Option<&str>) -> Result<String, String> {
    match encoding {
        None => Ok(body.to_string()),
        Some("html") => Ok(html_escape::decode_html_entities(body).into_owned()),
        Some(encoding) => Err(format!(
            "Unsupported XML transport encoding: {}.",
            python_repr_string(encoding)
        )),
    }
}

pub fn messages_to_json(messages: &[Message]) -> Value {
    Value::Array(messages.iter().filter_map(message_to_json).collect())
}

fn message_to_json(message: &Message) -> Option<Value> {
    let content = message_json_content(message);
    if content.is_empty() {
        return None;
    }
    let mut payload = Map::new();
    payload.insert("type".to_string(), Value::String(message.message_type.tag().to_string()));
    payload.insert("role".to_string(), Value::String(message.role.clone()));
    payload.insert("original_index".to_string(), Value::Number(message.original_index.clone()));
    payload.insert("content".to_string(), Value::Array(content));
    if let Some(value) = &message.branch {
        payload.insert("branch".to_string(), Value::String(value.clone()));
    }
    if message.role == "user" {
        if message.is_meta {
            payload.insert("isMeta".to_string(), Value::Bool(true));
        }
        if let Some(value) = &message.source_tool_user_id {
            payload.insert("sourceToolUserId".to_string(), Value::String(value.clone()));
        }
    }
    if let Some(value) = &message.agent_id {
        payload.insert("agent_id".to_string(), Value::String(value.clone()));
        if let Some(value) = &message.subagent_type {
            payload.insert("subagent_type".to_string(), Value::String(value.clone()));
        }
        if let Some(value) = &message.name {
            payload.insert("name".to_string(), Value::String(value.clone()));
        }
    }
    if let Some(value) = message.display_model() {
        payload.insert("model".to_string(), Value::String(value.to_string()));
    }
    if let Some(value) = &message.custom_type {
        payload.insert("custom_type".to_string(), Value::String(value.clone()));
    }
    if let Some(value) = message.inherited_context {
        payload.insert("inherited_context".to_string(), Value::Bool(value));
    }
    if let Some(value) = &message.status {
        payload.insert("status".to_string(), Value::String(value.clone()));
    }
    if let Some(value) = &message.timestamp {
        payload.insert("timestamp".to_string(), Value::String(value.clone()));
    }
    if let Some(value) = &message.native_entry_id {
        payload.insert("native_entry_id".to_string(), Value::String(value.clone()));
    }
    Some(Value::Object(payload))
}

fn message_json_content(message: &Message) -> Vec<Value> {
    let mut content = Vec::new();
    if let Some(value) = message.subagent_task.as_ref().filter(|value| !value.is_empty()) {
        content.push(typed_content("subagent-task", value));
    }
    if !message.text.is_empty() {
        content.push(Value::String(message.text.clone()));
    }
    if let Some(value) = message.thinking.as_ref().filter(|value| !value.is_empty()) {
        content.push(typed_content("thinking", value));
    }
    content.extend(message.tools.iter().map(tool_to_json));
    if let Some(value) = message.plan.as_ref().filter(|value| !value.is_empty()) {
        let mut block = Map::new();
        block.insert("type".to_string(), Value::String("tool-input".to_string()));
        block.insert("name".to_string(), Value::String("ExitPlanMode".to_string()));
        block.insert("plan".to_string(), Value::String(value.clone()));
        content.push(Value::Object(block));
    }
    content
}

fn typed_content(block_type: &str, content: &str) -> Value {
    let mut block = Map::new();
    block.insert("type".to_string(), Value::String(block_type.to_string()));
    block.insert("content".to_string(), Value::String(content.to_string()));
    Value::Object(block)
}

fn tool_to_json(tool: &Tool) -> Value {
    match tool {
        Tool::Use(tool) => tool_use_to_json(tool),
        Tool::Result(tool) => tool_result_to_json(tool),
    }
}

fn tool_use_to_json(tool: &ToolUse) -> Value {
    let mut payload = Map::new();
    payload.insert("type".to_string(), Value::String("tool-input".to_string()));
    payload.insert("name".to_string(), Value::String(tool.name.clone()));
    if let Some(value) = short_tool_id(tool.id.as_deref()) {
        payload.insert("id".to_string(), Value::String(value));
    }
    if let Some(value) = &tool.native_tool_call_id {
        payload.insert("native_tool_call_id".to_string(), Value::String(value.clone()));
    }
    if let Some(value) = &tool.native_content_index {
        payload.insert("native_content_index".to_string(), Value::Number(value.clone()));
    }
    if !value_is_truthy(&tool.input) {
        return Value::Object(payload);
    }
    let Some(input) = tool.input.as_object() else {
        payload.insert("content".to_string(), tool.input.clone());
        return Value::Object(payload);
    };
    if tool_input_needs_wrapper(&tool.name, input) {
        payload.insert("input".to_string(), tool.input.clone());
        return Value::Object(payload);
    }
    for (key, value) in input {
        payload.insert(key.clone(), value.clone());
    }
    Value::Object(payload)
}

fn tool_result_to_json(tool: &ToolResult) -> Value {
    let mut payload = Map::new();
    payload.insert("type".to_string(), Value::String("tool-output".to_string()));
    if let Some(value) = tool.name.as_ref().filter(|value| !value.is_empty()) {
        payload.insert("name".to_string(), Value::String(value.clone()));
    }
    if let Some(value) = short_tool_id(tool.tool_use_id.as_deref()) {
        payload.insert("id".to_string(), Value::String(value));
    }
    if let Some(value) = &tool.native_tool_call_id {
        payload.insert("native_tool_call_id".to_string(), Value::String(value.clone()));
    }
    if tool.is_error {
        payload.insert("is_error".to_string(), Value::Bool(true));
    }
    if tool.has_content {
        payload.insert("content".to_string(), tool.content.clone().unwrap_or(Value::Null));
    }
    Value::Object(payload)
}

fn json_pretty_ensure_ascii(value: &Value) -> Result<String, String> {
    let serialized = serde_json::to_string_pretty(value).map_err(|error| error.to_string())?;
    let mut output = String::with_capacity(serialized.len());
    for character in serialized.chars() {
        if character.is_ascii() {
            output.push(character);
            continue;
        }
        let scalar = u32::from(character);
        if scalar <= 0xffff {
            output.push_str(&format!("\\u{scalar:04x}"));
            continue;
        }
        let adjusted = scalar - 0x10000;
        let high = 0xd800 + (adjusted >> 10);
        let low = 0xdc00 + (adjusted & 0x3ff);
        output.push_str(&format!("\\u{high:04x}\\u{low:04x}"));
    }
    Ok(output)
}

fn escape_html_text(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn escape_html_attribute(value: &str) -> String {
    escape_html_text(value)
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
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

#[cfg(test)]
mod inner_block_class_tests {
    use super::*;

    /// `encode_xml_text` must use CPython's character classes, not the crate's.
    ///
    /// It decides whether message text is HTML-escaped, and the escaped form is
    /// what `render_message_inner_xml` emits — **the string search matches
    /// against** — so a class difference here changes which sessions a query
    /// finds.
    ///
    /// **Authored, not harvested.** Every expectation was transcribed from a run
    /// of `chats.xml_transport.encode_xml_text` at oracle revision `8cb4c5f`; no
    /// file in the real pool carries U+001C..U+001F at all.
    #[test]
    fn encode_xml_text_uses_pythons_character_classes() {
        for (text, expected) in [
            ("<thinking>x</thinking>", Some("html")),
            (r#"<thinking id="1">x"#, Some("html")),
            // CPython's `\s` matches U+001C; the crate's does not.
            ("<thinking\u{1c}id=\"1\">x", Some("html")),
            // CPython's `\w` is `str.isalnum()`, which accepts the `No` numeric
            // U+00BD; the crate's `\w` rejects it.
            ("<thinking \u{bd}=\"1\">x", Some("html")),
            // And the other direction, which is the one an implementer never
            // checks: the crate's `\w` accepts a lone combining mark through
            // `\p{M}`, CPython's does not, so Python leaves this text alone.
            ("<thinking \u{301}=\"1\">x", None),
            ("plain text", None),
        ] {
            assert_eq!(
                encode_xml_text(text).1.as_deref(),
                expected,
                "encode_xml_text({text:?}) must agree with Python about whether \
                 this opens a canonical inner block"
            );
        }
    }

    /// The falsifier: the crate's bare classes, on the same six inputs, must
    /// disagree with Python on three of them — and in both directions.
    #[test]
    fn the_gate_catches_the_crates_bare_classes() {
        let bare = Regex::new(
            r#"(?m)^<(?P<tag>thinking|tool-input|tool-output|subagent-task)(?P<attrs>(?:\s+[\w-]+="[^"]*")*)>"#,
        )
        .expect("the pre-fix pattern");

        assert!(
            !bare.is_match("<thinking\u{1c}id=\"1\">x"),
            "the falsifier must reproduce what it stands for: the crate's `\\s` \
             does not match U+001C, so this text escaped HTML-escaping"
        );
        assert!(
            !bare.is_match("<thinking \u{bd}=\"1\">x"),
            "same, for the crate's `\\w` rejecting the `No` numeric U+00BD"
        );
        assert!(
            bare.is_match("<thinking \u{301}=\"1\">x"),
            "and the reverse: the crate's `\\w` accepts a lone combining mark, so \
             this text was escaped where Python leaves it alone. If this stops \
             holding, the class difference has gone one-directional and the gate \
             above no longer covers both."
        );
    }
}
