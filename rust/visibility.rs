//! What content is visible, and how short it is rendered.
//!
//! Ported from `MessageSelection`, `SearchOutputMode`, `ParseOutputMode` and
//! `ConversationFlags` in `src/chats/model.py`, at oracle revision `8cb4c5f`.

use crate::shortening::ShortPolicy;
use crate::tool_filter::ToolVisibility;

/// Which regular-message roles are visible.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum MessageSelection {
    #[default]
    All,
    OnlyUser,
    OnlyAssistant,
    NoUser,
    NoAssistant,
    None,
}

impl MessageSelection {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::All => "all",
            Self::OnlyUser => "only-user",
            Self::OnlyAssistant => "only-assistant",
            Self::NoUser => "no-user",
            Self::NoAssistant => "no-assistant",
            Self::None => "none",
        }
    }

    pub fn from_str(value: &str) -> Option<Self> {
        match value {
            "all" => Some(Self::All),
            "only-user" => Some(Self::OnlyUser),
            "only-assistant" => Some(Self::OnlyAssistant),
            "no-user" => Some(Self::NoUser),
            "no-assistant" => Some(Self::NoAssistant),
            "none" => Some(Self::None),
            _ => None,
        }
    }

    pub fn show_user_messages(self) -> bool {
        matches!(self, Self::All | Self::OnlyUser | Self::NoAssistant)
    }

    pub fn show_assistant_messages(self) -> bool {
        matches!(self, Self::All | Self::OnlyAssistant | Self::NoUser)
    }
}

/// Search result output modes.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum SearchOutputMode {
    #[default]
    Matches,
    Full,
    List,
    OnlyId,
}

impl SearchOutputMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Matches => "matches",
            Self::Full => "full",
            Self::List => "list",
            Self::OnlyId => "only-id",
        }
    }
}

/// Special parse output modes.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum ParseOutputMode {
    #[default]
    Full,
    OnlyMetadata,
    OnlyId,
}

impl ParseOutputMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Full => "full",
            Self::OnlyMetadata => "only-metadata",
            Self::OnlyId => "only-id",
        }
    }
}

/// What `--color` asked for. Python accepts a bool or one of three words, and treats
/// them differently — see `ConversationFlags::resolve_color`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ColorChoice {
    Always,
    Never,
    Auto,
    Bool(bool),
}

impl Default for ColorChoice {
    fn default() -> Self {
        Self::Bool(false)
    }
}

/// Flags controlling what content to include.
#[derive(Clone, Debug)]
pub struct ConversationFlags {
    pub message_selection: MessageSelection,
    pub show_thinking: bool,
    pub show_tools: ToolVisibility,
    pub show_agents: bool,
    pub show_custom: bool,
    pub show_branches: bool,
    pub show_plans: bool,
    pub allow_empty_output: bool,
    pub shorten: bool,
    pub shorten_max_chars: i64,
    pub shorten_progressive: bool,
    pub shorten_thinking: bool,
    pub color: bool,
    pub metadata_color: bool,
    pub paging: bool,
}

impl Default for ConversationFlags {
    fn default() -> Self {
        Self {
            message_selection: MessageSelection::All,
            show_thinking: false,
            show_tools: ToolVisibility::All(false),
            show_agents: false,
            show_custom: false,
            show_branches: false,
            show_plans: false,
            allow_empty_output: false,
            shorten: false,
            shorten_max_chars: crate::shortening::DEFAULT_SHORT_MAX_CHARS,
            shorten_progressive: false,
            shorten_thinking: false,
            color: false,
            metadata_color: false,
            paging: false,
        }
    }
}

impl ConversationFlags {
    /// Resolve `--color` into the two independent booleans Python derives.
    ///
    /// Faithful to a quirk worth naming: a **bool** `color` never enables colour,
    /// because Python compares it against the strings `"always"` and `"auto"` and a
    /// bool equals neither. It does still enable `metadata_color`. So
    /// `ConversationFlags(color=True)` yields `color=False, metadata_color=True`.
    ///
    /// ```
    /// use _native::visibility::{ColorChoice, ConversationFlags};
    /// let (colour, metadata) = ConversationFlags::resolve_color(ColorChoice::Bool(true), true);
    /// assert_eq!((colour, metadata), (false, true));
    /// let (colour, metadata) = ConversationFlags::resolve_color(ColorChoice::Auto, true);
    /// assert_eq!((colour, metadata), (true, true));
    /// let (colour, metadata) = ConversationFlags::resolve_color(ColorChoice::Never, true);
    /// assert_eq!((colour, metadata), (false, false));
    /// ```
    pub fn resolve_color(choice: ColorChoice, stdout_is_terminal: bool) -> (bool, bool) {
        let color = matches!(choice, ColorChoice::Always)
            || (matches!(choice, ColorChoice::Auto) && stdout_is_terminal);
        let metadata_color = match choice {
            ColorChoice::Never => false,
            ColorChoice::Always | ColorChoice::Auto => true,
            ColorChoice::Bool(value) => value,
        };
        (color, metadata_color)
    }

    /// Apply a colour choice, and default paging to the resolved colour when unset.
    pub fn with_color(
        mut self,
        choice: ColorChoice,
        stdout_is_terminal: bool,
        paging: Option<bool>,
    ) -> Self {
        let (color, metadata_color) = Self::resolve_color(choice, stdout_is_terminal);
        self.color = color;
        self.metadata_color = metadata_color;
        self.paging = paging.unwrap_or(color);
        self
    }

    pub fn show_user_messages(&self) -> bool {
        self.message_selection.show_user_messages()
    }

    pub fn show_assistant_messages(&self) -> bool {
        self.message_selection.show_assistant_messages()
    }

    /// Whether every content class is shown. Note `show_tools` counts as shown when it
    /// is anything other than an explicit `false`, matching Python's truthiness on a
    /// bool-or-list field: a non-empty filter list is truthy.
    pub fn show_all(&self) -> bool {
        let tools_shown = match &self.show_tools {
            ToolVisibility::All(shown) => *shown,
            ToolVisibility::Filters(filters) => !filters.is_empty(),
        };
        self.show_thinking
            && tools_shown
            && self.show_agents
            && self.show_custom
            && self.show_branches
            && self.show_plans
    }

    /// The active global short policy, if shortening is enabled.
    pub fn global_short_policy(&self) -> Option<ShortPolicy> {
        if !self.shorten {
            return None;
        }
        Some(ShortPolicy::new(
            self.shorten_max_chars,
            self.shorten_progressive,
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn role_selection_matches_python() {
        for (selection, user, assistant) in [
            (MessageSelection::All, true, true),
            (MessageSelection::OnlyUser, true, false),
            (MessageSelection::OnlyAssistant, false, true),
            (MessageSelection::NoUser, false, true),
            (MessageSelection::NoAssistant, true, false),
            (MessageSelection::None, false, false),
        ] {
            assert_eq!(selection.show_user_messages(), user, "{selection:?} user");
            assert_eq!(
                selection.show_assistant_messages(),
                assistant,
                "{selection:?} assistant"
            );
        }
    }

    #[test]
    fn selection_names_round_trip() {
        for selection in [
            MessageSelection::All,
            MessageSelection::OnlyUser,
            MessageSelection::OnlyAssistant,
            MessageSelection::NoUser,
            MessageSelection::NoAssistant,
            MessageSelection::None,
        ] {
            assert_eq!(MessageSelection::from_str(selection.as_str()), Some(selection));
        }
    }

    #[test]
    fn a_bool_color_never_enables_colour_but_does_enable_metadata() {
        // Python compares the flag against "always" and "auto"; a bool equals neither.
        assert_eq!(
            ConversationFlags::resolve_color(ColorChoice::Bool(true), true),
            (false, true)
        );
        assert_eq!(
            ConversationFlags::resolve_color(ColorChoice::Bool(false), true),
            (false, false)
        );
    }

    #[test]
    fn auto_colour_follows_the_terminal() {
        assert_eq!(
            ConversationFlags::resolve_color(ColorChoice::Auto, true),
            (true, true)
        );
        assert_eq!(
            ConversationFlags::resolve_color(ColorChoice::Auto, false),
            (false, true)
        );
    }

    #[test]
    fn paging_defaults_to_the_resolved_colour() {
        let flags = ConversationFlags::default().with_color(ColorChoice::Always, false, None);
        assert!(flags.color);
        assert!(flags.paging);
        let explicit =
            ConversationFlags::default().with_color(ColorChoice::Always, false, Some(false));
        assert!(explicit.color);
        assert!(!explicit.paging);
    }

    #[test]
    fn global_short_policy_is_absent_until_shortening_is_on() {
        let mut flags = ConversationFlags::default();
        assert!(flags.global_short_policy().is_none());
        flags.shorten = true;
        flags.shorten_max_chars = 128;
        flags.shorten_progressive = true;
        assert_eq!(
            flags.global_short_policy(),
            Some(ShortPolicy::new(128, true))
        );
    }
}

// ---------------------------------------------------------------- visible content

use crate::model::{Message, Tool};
use crate::shortening::{shorten_data, truncate_middle};
use crate::tool_filter::{FilterableTool, ToolIdMap, resolve_tool_visibility};

/// Map every tool id to the canonical name of the call it belongs to.
///
/// Ported from `_build_tool_id_map` in `commands/common.py`.
pub fn build_tool_id_map(messages: &[Message]) -> ToolIdMap {
    let mut map = ToolIdMap::new();
    for message in messages {
        for tool in &message.tools {
            if let Tool::Use(use_tool) = tool
                && let Some(identifier) = &use_tool.id
            {
                map.insert(identifier.clone(), use_tool.name.clone());
            }
        }
    }
    map
}

fn filterable(tool: &Tool) -> FilterableTool<'_> {
    match tool {
        Tool::Use(use_tool) => FilterableTool {
            is_input: true,
            name: Some(&use_tool.name),
            tool_use_id: None,
            is_error: false,
        },
        Tool::Result(result) => FilterableTool {
            is_input: false,
            name: result.name.as_deref(),
            tool_use_id: result.tool_use_id.as_deref(),
            is_error: result.is_error,
        },
    }
}

/// Build a tool id map locally only when the filters need one and none was supplied.
///
/// Ported from `Message._tool_name_id_map`: a caller-supplied map always wins, and a
/// local one is built only for a named filter list.
fn tool_name_id_map(
    message: &Message,
    visibility: &ToolVisibility,
    supplied: Option<&ToolIdMap>,
) -> ToolIdMap {
    if let Some(map) = supplied.filter(|map| !map.is_empty()) {
        return map.clone();
    }
    let needs_local = match visibility {
        ToolVisibility::Filters(filters) => filters.iter().any(|filter| filter.name.is_some()),
        ToolVisibility::All(_) => false,
    };
    if !needs_local {
        return supplied.cloned().unwrap_or_default();
    }
    let mut map = supplied.cloned().unwrap_or_default();
    for tool in &message.tools {
        if let Tool::Use(use_tool) = tool
            && let Some(identifier) = &use_tool.id
        {
            map.insert(identifier.clone(), use_tool.name.clone());
        }
    }
    map
}

/// Fill in a tool result's name from the call it belongs to.
///
/// Python resolves this at render time, inside `tool_to_parts(tool, id_map)`. Doing it
/// here instead keeps the renderer taking only a `Message`, and matches Python's rule
/// exactly: the lookup happens **only when the result carries no `name` key at all**.
/// A present-but-empty name stays empty rather than being resolved.
fn resolve_result_name(tool: Tool, id_map: &ToolIdMap) -> Tool {
    let Tool::Result(mut result) = tool else {
        return tool;
    };
    if result.name.is_none()
        && let Some(id) = result.tool_use_id.as_deref()
        && let Some(name) = id_map.get(id)
    {
        result.name = Some(name.clone());
    }
    Tool::Result(result)
}

fn shorten_tool_payload(tool: &Tool, max_chars: i64) -> Tool {
    match tool {
        Tool::Use(use_tool) => {
            let mut shortened = use_tool.clone();
            shortened.input = shorten_data(&use_tool.input, max_chars);
            Tool::Use(shortened)
        }
        Tool::Result(result) => {
            let mut shortened = result.clone();
            shortened.content = result
                .content
                .as_ref()
                .map(|content| shorten_data(content, max_chars));
            Tool::Result(shortened)
        }
    }
}

/// Which messages take a progressive short position, and how many there are.
///
/// Python assigns these by mutating each message. Computing them alongside keeps
/// `Message` free of render-time state, which matters because `ch parse` shares it.
#[derive(Clone, Debug, Default)]
pub struct ProgressiveAssignment {
    positions: Vec<Option<usize>>,
    qualifying_count: usize,
}

impl ProgressiveAssignment {
    pub fn compute(
        messages: &[Message],
        flags: &ConversationFlags,
        tool_id_map: Option<&ToolIdMap>,
    ) -> Self {
        let mut positions = vec![None; messages.len()];
        let mut next = 0usize;
        for (index, message) in messages.iter().enumerate() {
            if has_progressive_payload(message, flags, tool_id_map) {
                positions[index] = Some(next);
                next += 1;
            }
        }
        Self {
            positions,
            qualifying_count: next,
        }
    }

    pub fn position(&self, index: usize) -> Option<usize> {
        self.positions.get(index).copied().flatten()
    }

    pub fn qualifying_count(&self) -> usize {
        self.qualifying_count
    }
}

fn tools_are_visible(message: &Message, flags: &ConversationFlags) -> bool {
    let requested = match &flags.show_tools {
        ToolVisibility::All(shown) => *shown,
        ToolVisibility::Filters(filters) => !filters.is_empty(),
    };
    (requested || message.tools_always_visible) && !message.tools.is_empty()
}

fn effective_visibility(message: &Message, flags: &ConversationFlags) -> ToolVisibility {
    if message.tools_always_visible {
        ToolVisibility::All(true)
    } else {
        flags.show_tools.clone()
    }
}

/// Whether one visible payload of this message uses a progressive short policy.
pub fn has_progressive_payload(
    message: &Message,
    flags: &ConversationFlags,
    tool_id_map: Option<&ToolIdMap>,
) -> bool {
    let global = flags.global_short_policy();
    let global_payload_visible = !message.text.is_empty()
        || (flags.show_thinking && message.thinking.as_deref().is_some_and(|v| !v.is_empty()))
        || (flags.show_plans && message.plan.as_deref().is_some_and(|v| !v.is_empty()));
    if global.is_some_and(|policy| policy.progressive) && global_payload_visible {
        return true;
    }
    if !tools_are_visible(message, flags) {
        return false;
    }
    let visibility = effective_visibility(message, flags);
    let id_map = tool_name_id_map(message, &visibility, tool_id_map);
    message.tools.iter().any(|tool| {
        let (show, local) = resolve_tool_visibility(
            &filterable(tool),
            &visibility,
            &id_map,
            flags.shorten_max_chars,
            flags.shorten && flags.shorten_progressive,
        );
        show && local.or(global).is_some_and(|policy| policy.progressive)
    })
}

/// Project a message down to what the flags make visible, shortened at the source.
///
/// Returns a `Message` rather than a parts list so the proved renderer in `codecs`
/// stays the only renderer. Shortening happens here, once per payload, exactly as
/// Python shortens before building any view.
pub fn visible_message(
    message: &Message,
    flags: &ConversationFlags,
    tool_id_map: Option<&ToolIdMap>,
    progressive: &ProgressiveAssignment,
    index: usize,
) -> Message {
    let position = progressive.position(index);
    let count = progressive.qualifying_count();
    let global_limit = ShortPolicy::new(flags.shorten_max_chars, flags.shorten_progressive)
        .effective_max_chars(position, count);

    let mut visible = message.clone();

    if !message.text.is_empty() && flags.shorten {
        visible.text = truncate_middle(&message.text, global_limit);
    }

    visible.thinking = match message.thinking.as_deref().filter(|value| !value.is_empty()) {
        Some(thinking) if flags.show_thinking => {
            if flags.shorten || flags.shorten_thinking {
                let limit = if flags.shorten { global_limit } else { flags.shorten_max_chars };
                Some(truncate_middle(thinking, limit))
            } else {
                Some(thinking.to_string())
            }
        }
        _ => None,
    };

    visible.plan = match message.plan.as_deref().filter(|value| !value.is_empty()) {
        Some(plan) if flags.show_plans => Some(if flags.shorten {
            truncate_middle(plan, global_limit)
        } else {
            plan.to_string()
        }),
        _ => None,
    };

    visible.tools = if tools_are_visible(message, flags) {
        let visibility = effective_visibility(message, flags);
        let id_map = tool_name_id_map(message, &visibility, tool_id_map);
        message
            .tools
            .iter()
            .filter_map(|tool| {
                let (show, local) = resolve_tool_visibility(
                    &filterable(tool),
                    &visibility,
                    &id_map,
                    flags.shorten_max_chars,
                    flags.shorten && flags.shorten_progressive,
                );
                if !show {
                    return None;
                }
                let shortened = match local.or_else(|| flags.global_short_policy()) {
                    Some(policy) => {
                        shorten_tool_payload(tool, policy.effective_max_chars(position, count))
                    }
                    None => tool.clone(),
                };
                Some(resolve_result_name(shortened, &id_map))
            })
            .collect()
    } else {
        Vec::new()
    };

    visible
}
