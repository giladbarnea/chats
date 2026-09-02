//! The raw CLI transcript decoder, the fourth session format.
//!
//! Ported from `parse_raw_cli_transcript` in `src/chats/parsing.py`.
//!
//! **This is reached more often than it looks, and never by a transcript.**
//! `SessionScan.from_content` sends anything `detect_format` calls `Raw` here —
//! which is any `.jsonl` file whose first non-blank line is not an object with a
//! `type` key. Measured on the real pool: **9 of 5,039 files**, 8 of them old
//! Codex rollouts whose first line carries `id`/`timestamp`/`instructions`/`git`
//! and no `type`. Every one of the nine produces **zero** messages here.
//!
//! That matters twice over. It is why those 8 Codex sessions are excluded from
//! `search .` — not because the Codex decoder filters them, which is what the
//! Codex handoff originally said. And it means **the real corpus cannot grade
//! this module**: a genuine `> ` / `⏺ ` transcript does not exist anywhere in the
//! pool, so every test here is a synthesized fixture, and a wrong implementation
//! would pass a corpus of any size. The same shape as the Pi `<duration_ms>`
//! defect: 477 of 477 envelopes carried the terminator, so the mutation caught
//! nothing and the code was still wrong.

use crate::model::{Message, MessageType};
use crate::visibility::ConversationFlags;
use serde_json::Number;

/// The assistant response marker, U+23FA BLACK CIRCLE FOR RECORD.
const ASSISTANT_MARKER: &str = "\u{23fa} ";
const USER_MARKER: &str = "> ";

/// Whether a `> ` line is a system notice rather than something the user typed.
///
/// Python's rule exactly, including that it lowercases the whole line before
/// looking — so `> /cmd IS RUNNING` is a system message too.
///
/// ```
/// use _native::raw_transcript::is_system_message;
/// assert!(is_system_message("> /compact is running…"));
/// assert!(is_system_message("> /COMPACT IS RUNNING"));
/// assert!(!is_system_message("> please run the tests"));
/// assert!(!is_system_message("is running"));
/// ```
pub fn is_system_message(line: &str) -> bool {
    line.starts_with(USER_MARKER) && line.to_lowercase().contains("is running")
}

/// Decode a raw CLI transcript into messages.
///
/// `> ` opens a user message unless it is a system notice, `⏺ ` opens an
/// assistant one, and any other line continues whichever is open. A line before
/// the first marker is dropped, because there is no role to attach it to.
///
/// ```
/// use _native::raw_transcript::parse_raw_cli_transcript;
/// use _native::visibility::ConversationFlags;
/// let flags = ConversationFlags::default();
/// let messages = parse_raw_cli_transcript("> hello\n\u{23fa} hi there", &flags);
/// assert_eq!(messages.len(), 2);
/// assert_eq!(messages[0].role, "user");
/// assert_eq!(messages[0].text, "hello");
/// assert_eq!(messages[1].role, "assistant");
/// ```
pub fn parse_raw_cli_transcript(content: &str, flags: &ConversationFlags) -> Vec<Message> {
    let mut messages: Vec<Message> = Vec::new();
    let mut index: i64 = 1;
    let mut current_role: Option<&'static str> = None;
    let mut current_lines: Vec<String> = Vec::new();

    for line in content.split('\n') {
        if let Some(role) = opens(line) {
            if current_role != Some(role) {
                save(&mut messages, &mut index, current_role, &mut current_lines, flags);
                current_role = Some(role);
            }
            // A user line loses its `> `; an assistant line and a system notice
            // keep their marker, which is what Python does and is visible output.
            current_lines.push(match role {
                "user" => line[USER_MARKER.len()..].to_string(),
                _ => line.to_string(),
            });
        } else if current_role.is_some() {
            current_lines.push(line.to_string());
        }
    }
    save(&mut messages, &mut index, current_role, &mut current_lines, flags);
    messages
}

/// Which role a line opens, or `None` when it continues the current one.
fn opens(line: &str) -> Option<&'static str> {
    if line.starts_with(ASSISTANT_MARKER) {
        return Some("assistant");
    }
    if line.starts_with(USER_MARKER) {
        return Some(if is_system_message(line) { "assistant" } else { "user" });
    }
    None
}

/// Close the open message, dropping it when its role is not visible.
///
/// The index advances only for a message actually kept, so hiding one role
/// renumbers the rest — Python's behaviour, and the reason this cannot be a
/// filter applied afterwards.
fn save(
    messages: &mut Vec<Message>,
    index: &mut i64,
    role: Option<&str>,
    lines: &mut Vec<String>,
    flags: &ConversationFlags,
) {
    let Some(role) = role.filter(|_| !lines.is_empty()) else {
        lines.clear();
        return;
    };
    let visible = match role {
        "user" => flags.show_user_messages(),
        _ => flags.show_assistant_messages(),
    };
    if !visible {
        lines.clear();
        return;
    }
    let message_type = match role {
        "user" => MessageType::UserMessage,
        _ => MessageType::AssistantResponse,
    };
    let mut message = Message::new(message_type, role.to_string(), Number::from(*index));
    message.text = lines.join("\n");
    messages.push(message);
    *index += 1;
    lines.clear();
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::visibility::MessageSelection;

    fn shape(messages: &[Message]) -> Vec<(String, String)> {
        messages
            .iter()
            .map(|message| (message.role.clone(), message.text.clone()))
            .collect()
    }

    /// Every real raw-format file in the pool decodes to nothing, because its
    /// lines are JSON objects rather than transcript markers. This is the case
    /// that actually ships, and the reason 8 Codex sessions are excluded from
    /// `search .`.
    #[test]
    fn json_lines_without_a_type_key_decode_to_nothing() {
        let content = "{\"id\":\"x\",\"timestamp\":\"2025-09-02T14:19:45Z\"}\n{\"record_type\":\"state\"}";
        let messages = parse_raw_cli_transcript(content, &ConversationFlags::default());
        assert!(
            messages.is_empty(),
            "a rollout with no transcript markers must decode to nothing, got {:?}",
            shape(&messages)
        );
    }

    /// A continuation line joins the open message rather than starting one.
    #[test]
    fn continuation_lines_join_the_open_message() {
        let content = "> first\nsecond\nthird";
        let messages = parse_raw_cli_transcript(content, &ConversationFlags::default());
        assert_eq!(shape(&messages), vec![("user".into(), "first\nsecond\nthird".into())]);
    }

    /// Text before any marker has no role to attach to and is dropped.
    #[test]
    fn text_before_the_first_marker_is_dropped() {
        let content = "orphan preamble\n> a question";
        let messages = parse_raw_cli_transcript(content, &ConversationFlags::default());
        assert_eq!(shape(&messages), vec![("user".into(), "a question".into())]);
    }

    /// A `> ` system notice belongs to the assistant, keeps its marker, and does
    /// not break an assistant run in two.
    #[test]
    fn a_system_notice_joins_the_assistant_rather_than_the_user() {
        let content = "\u{23fa} working\n> /compact is running\nstill working";
        let messages = parse_raw_cli_transcript(content, &ConversationFlags::default());
        assert_eq!(
            shape(&messages),
            vec![(
                "assistant".into(),
                "\u{23fa} working\n> /compact is running\nstill working".into()
            )],
            "a system notice must not split the assistant message or lose its marker"
        );
    }

    /// Consecutive same-role markers stay one message; a role change closes it.
    #[test]
    fn a_role_change_closes_the_open_message() {
        let content = "> one\n> two\n\u{23fa} reply\n> three";
        let messages = parse_raw_cli_transcript(content, &ConversationFlags::default());
        assert_eq!(
            shape(&messages),
            vec![
                ("user".into(), "one\ntwo".into()),
                ("assistant".into(), "\u{23fa} reply".into()),
                ("user".into(), "three".into()),
            ]
        );
    }

    /// Hiding a role renumbers the rest, because the index advances only for a
    /// message that is kept. A filter applied after decoding would not do this.
    #[test]
    fn hiding_a_role_renumbers_the_messages_that_remain() {
        let content = "> one\n\u{23fa} reply\n> two";
        let flags = ConversationFlags {
            message_selection: MessageSelection::OnlyAssistant,
            ..ConversationFlags::default()
        };
        let messages = parse_raw_cli_transcript(content, &flags);
        assert_eq!(shape(&messages), vec![("assistant".into(), "\u{23fa} reply".into())]);
        assert_eq!(
            messages[0].original_index,
            Number::from(1),
            "the surviving message must take index 1, not the index it would have had"
        );
    }

    /// This decoder has no line-ending policy of its own, and must not grow one.
    ///
    /// Python's `parse_raw_cli_transcript` splits on `"\n"` and nothing else, so
    /// both sides depend entirely on the caller having read the file in text
    /// mode. `python_io::read_text` does that (F1). This test stores the other
    /// side of that dependency: a carriage return arriving here is an **ordinary
    /// character**, not a line break and not whitespace to strip.
    ///
    /// **Authored, not harvested, twice over.** No `> ` / `⏺ ` transcript exists
    /// anywhere in the pool, and 0 of 5,061 files carry a literal `\r` (measured
    /// 2026-09-01). Both halves of this case are unreachable by any corpus.
    ///
    /// If someone removes the translation at the read site, the composed gate in
    /// `session.rs` goes red and this test says why: two lines become one, and a
    /// `\r` reaches rendered output.
    #[test]
    fn a_carriage_return_is_an_ordinary_character_here() {
        let flags = ConversationFlags::default();

        let lone = parse_raw_cli_transcript("> one\r\u{23fa} reply", &flags);
        assert_eq!(
            shape(&lone),
            vec![("user".into(), "one\r\u{23fa} reply".into())],
            "a lone \\r must not split a line here; the read path translates it \
             to \\n before this decoder sees it, and that is the only reason two \
             messages come out of a lone-\\r transcript"
        );

        let crlf = parse_raw_cli_transcript("> one\r\n\u{23fa} reply\r\n", &flags);
        assert_eq!(
            shape(&crlf),
            vec![
                ("user".into(), "one\r".into()),
                ("assistant".into(), "\u{23fa} reply\r\n".into()),
            ],
            "a \\r left by an untranslated read survives into message text and \
             into rendered output; nothing downstream removes it"
        );
    }

    /// Only the `> ` prefix is stripped, and only from user lines.
    #[test]
    fn only_the_user_marker_is_stripped() {
        let content = "> \u{23fa} not an assistant line";
        let messages = parse_raw_cli_transcript(content, &ConversationFlags::default());
        assert_eq!(shape(&messages), vec![("user".into(), "\u{23fa} not an assistant line".into())]);
    }
}
