//! Tool filter specs: the `--tools` grammar, matching, and short-policy resolution.
//!
//! Ported from `src/chats/tool_filter.py` at oracle revision `8cb4c5f`.
//!
//! The grammar is order-insensitive and its short modifier can swallow a following
//! token, so the parser walks tokens with an explicit cursor rather than folding.
//! Both are reproduced exactly; the lookahead in particular is easy to simplify into
//! something that behaves differently on `s:8:p`.

use std::collections::HashMap;

use crate::model::normalize_tool_filter_name;
use crate::shortening::{ShortPolicy, is_progressive_component, parse_short_spec};

/// Maps a tool id to the canonical name of the call it belongs to.
pub type ToolIdMap = HashMap<String, String>;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ToolDirection {
    Input,
    Output,
}

/// One tool filter spec. Every field is a criterion, AND'd; `negate` inverts the result.
/// `short` is a display modifier, not a matching criterion.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ToolFilter {
    pub name: Option<String>,
    pub negate: bool,
    pub direction: Option<ToolDirection>,
    pub error_only: bool,
    pub short: bool,
    pub short_max_chars: Option<i64>,
    pub short_progressive: Option<bool>,
}

/// What a tool looks like to the filter: enough to match on, nothing more.
pub struct FilterableTool<'a> {
    pub is_input: bool,
    pub name: Option<&'a str>,
    pub tool_use_id: Option<&'a str>,
    pub is_error: bool,
}

impl ToolFilter {
    pub fn matches(&self, tool: &FilterableTool, id_map: &ToolIdMap) -> bool {
        let hit = self.matches_criteria(tool, id_map);
        if self.negate { !hit } else { hit }
    }

    pub fn matches_criteria(&self, tool: &FilterableTool, id_map: &ToolIdMap) -> bool {
        if self.direction == Some(ToolDirection::Input) && !tool.is_input {
            return false;
        }
        if self.direction == Some(ToolDirection::Output) && tool.is_input {
            return false;
        }
        if self.error_only && !tool.is_error {
            return false;
        }
        let Some(requested) = self.name.as_deref() else {
            return true;
        };
        resolve_tool_names(tool, id_map)
            .iter()
            .any(|actual| tool_names_match(actual, requested))
    }

    fn specificity(&self) -> usize {
        usize::from(self.name.is_some())
            + usize::from(self.direction.is_some())
            + usize::from(self.error_only)
    }

    /// The local limit, falling back to the supplied default.
    ///
    /// Python spells the fallback `short_max_chars or default.max_chars`, which also
    /// falls back on `0`; `unwrap_or` falls back only on `None`. The two therefore
    /// diverge at exactly `Some(0)` — **unreachable by construction**, because both
    /// spec parsers reject anything below `MIN_SHORT_MAX_CHARS`, which is 8. If that
    /// floor is ever relaxed, this line has to move with it.
    fn local_short_policy(&self, default: ShortPolicy) -> Option<ShortPolicy> {
        if !self.short {
            return None;
        }
        Some(ShortPolicy {
            max_chars: self.short_max_chars.unwrap_or(default.max_chars),
            progressive: self.short_progressive.unwrap_or(default.progressive),
        })
    }
}

/// Use an explicit tool name, or resolve a linked result through its call.
///
/// Python also consults a `name_aliases` key here. Nothing in the product ever writes
/// one — it is read at a single site and populated nowhere — so it is not carried.
fn resolve_tool_names<'a>(tool: &FilterableTool<'a>, id_map: &'a ToolIdMap) -> Vec<&'a str> {
    if let Some(name) = tool.name.filter(|value| !value.is_empty()) {
        return vec![name];
    }
    if let Some(linked) = tool
        .tool_use_id
        .and_then(|identifier| id_map.get(identifier))
    {
        return vec![linked.as_str()];
    }
    Vec::new()
}

/// Match exact names, or names sharing a known provider alias.
fn tool_names_match(actual: &str, requested: &str) -> bool {
    actual == requested
        || normalize_tool_filter_name(actual) == normalize_tool_filter_name(requested)
}

/// Whether the filter list shows everything, or a specific set of filters.
#[derive(Clone, Debug)]
pub enum ToolVisibility {
    All(bool),
    Filters(Vec<ToolFilter>),
}

/// Decide whether a tool is visible, and which local short policy governs it.
///
/// Negative filters are a blocklist AND'd first: any negative whose criteria match
/// excludes the tool. Positive filters are an allowlist OR'd. Among matching positive
/// filters that declare a short limit, the most specific wins, and a tie goes to the
/// one that appears **later** in the list.
pub fn resolve_tool_visibility(
    tool: &FilterableTool,
    visibility: &ToolVisibility,
    id_map: &ToolIdMap,
    default_short_max_chars: i64,
    default_short_progressive: bool,
) -> (bool, Option<ShortPolicy>) {
    let filters = match visibility {
        ToolVisibility::All(shown) => return (*shown, None),
        ToolVisibility::Filters(filters) => filters,
    };

    for filter in filters {
        if filter.negate && filter.matches_criteria(tool, id_map) {
            return (false, None);
        }
    }

    let positive: Vec<&ToolFilter> = filters.iter().filter(|filter| !filter.negate).collect();
    if positive.is_empty() {
        return (true, None);
    }

    let matching: Vec<&ToolFilter> = positive
        .into_iter()
        .filter(|filter| filter.matches_criteria(tool, id_map))
        .collect();
    if matching.is_empty() {
        return (false, None);
    }

    let matching_short: Vec<&ToolFilter> =
        matching.into_iter().filter(|filter| filter.short).collect();
    if matching_short.is_empty() {
        return (true, None);
    }

    // `max` over (specificity, index) — on a tie the later filter wins, matching
    // Python's `max(enumerate(...), key=...)`, which keeps the last maximum.
    let selected = matching_short
        .iter()
        .enumerate()
        .max_by_key(|(index, filter)| (filter.specificity(), *index))
        .map(|(_, filter)| *filter)
        .expect("non-empty");

    (
        true,
        selected.local_short_policy(ShortPolicy::new(
            default_short_max_chars,
            default_short_progressive,
        )),
    )
}

fn is_short_component(candidate: &str) -> bool {
    (!candidate.is_empty() && candidate.chars().all(|character| character.is_ascii_digit()))
        || is_progressive_component(candidate)
}

/// Parse one tool filter spec.
///
/// Syntax: `[!][Name][:modifier[:modifier...]]`, modifiers `i`/`input`, `o`/`output`,
/// `e`/`error`, `s`/`short`, and `s=SPEC`. Token order does not matter.
///
/// ```
/// use _native::tool_filter::{parse_tool_spec, ToolDirection};
/// let filter = parse_tool_spec("!Bash:o:e").expect("valid");
/// assert!(filter.negate);
/// assert_eq!(filter.name.as_deref(), Some("Bash"));
/// assert_eq!(filter.direction, Some(ToolDirection::Output));
/// assert!(filter.error_only);
/// ```
pub fn parse_tool_spec(spec: &str) -> Result<ToolFilter, String> {
    let negate = spec.starts_with('!');
    let body = if negate { &spec[1..] } else { spec };

    let mut filter = ToolFilter {
        negate,
        ..ToolFilter::default()
    };
    let tokens: Vec<&str> = body.split(':').collect();
    let mut position = 0usize;
    let mut parsed_short_value: Option<String> = None;

    while position < tokens.len() {
        let token = tokens[position];
        if token.is_empty() {
            position += 1;
            continue;
        }
        let (keyword, separator, value) = match token.find('=') {
            Some(index) => (&token[..index], true, &token[index + 1..]),
            None => (token, false, ""),
        };
        let keyword_lower = keyword.to_lowercase();

        if matches!(keyword_lower.as_str(), "s" | "short") {
            let (consumed, short_value) =
                apply_short_modifier(&mut filter, &tokens, position, separator, value)?;
            parsed_short_value = short_value;
            position += consumed;
            continue;
        }

        match token.to_lowercase().as_str() {
            "i" | "input" => filter.direction = Some(ToolDirection::Input),
            "o" | "output" => filter.direction = Some(ToolDirection::Output),
            "e" | "error" => filter.error_only = true,
            _ => {
                if filter.name.is_none() || !filter.short {
                    filter.name = Some(token.to_string());
                } else {
                    let reported = match &parsed_short_value {
                        Some(previous) => format!("{previous}:{token}"),
                        None => token.to_string(),
                    };
                    return Err(format!(
                        "Invalid tool short value: {}.",
                        crate::model::python_repr_string(&reported)
                    ));
                }
            }
        }
        position += 1;
    }
    Ok(filter)
}

fn apply_short_modifier(
    filter: &mut ToolFilter,
    tokens: &[&str],
    position: usize,
    separator: bool,
    value: &str,
) -> Result<(usize, Option<String>), String> {
    if filter.short {
        return Err("Invalid tool short value: repeated short modifier.".to_string());
    }
    filter.short = true;
    if !separator {
        return Ok((1, None));
    }

    let (candidate, additional) = tool_short_value(tokens, position, value);
    let spec = parse_short_spec(&candidate)?;
    filter.short_max_chars = spec.max_chars;
    filter.short_progressive = Some(spec.progressive);
    Ok((additional + 1, Some(candidate)))
}

/// Collect the short-spec components without consuming tool modifiers.
fn tool_short_value(tokens: &[&str], position: usize, first: &str) -> (String, usize) {
    let next_position = position + 1;
    if next_position >= tokens.len() {
        return (first.to_string(), 0);
    }
    let next = tokens[next_position];
    let continues = is_short_component(first) && (next.is_empty() || is_short_component(next));
    if !continues {
        return (first.to_string(), 0);
    }
    let mut candidate = format!("{first}:{next}");
    let following = next_position + 1;
    if following < tokens.len() && tokens[following].is_empty() {
        candidate.push(':');
    }
    (candidate, 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn use_tool(name: &str) -> FilterableTool<'_> {
        FilterableTool { is_input: true, name: Some(name), tool_use_id: None, is_error: false }
    }

    fn result_tool<'a>(name: Option<&'a str>, id: Option<&'a str>, error: bool) -> FilterableTool<'a> {
        FilterableTool { is_input: false, name, tool_use_id: id, is_error: error }
    }

    #[test]
    fn direction_and_error_criteria() {
        let map = ToolIdMap::new();
        let output_errors = parse_tool_spec("o:e").expect("valid");
        assert!(output_errors.matches(&result_tool(Some("Bash"), None, true), &map));
        assert!(!output_errors.matches(&result_tool(Some("Bash"), None, false), &map));
        assert!(!output_errors.matches(&use_tool("Bash"), &map));
    }

    #[test]
    fn provider_aliases_match_across_names() {
        let map = ToolIdMap::new();
        let patch = parse_tool_spec("Patch").expect("valid");
        assert!(patch.matches(&use_tool("apply_patch"), &map));
        let bash = parse_tool_spec("Bash").expect("valid");
        assert!(bash.matches(&use_tool("shell_command"), &map));
    }

    #[test]
    fn a_result_without_a_name_resolves_through_its_call() {
        let mut map = ToolIdMap::new();
        map.insert("toolu_1".to_string(), "Read".to_string());
        let read = parse_tool_spec("Read").expect("valid");
        assert!(read.matches(&result_tool(None, Some("toolu_1"), false), &map));
        assert!(read.matches(&result_tool(Some(""), Some("toolu_1"), false), &map));
        assert!(!read.matches(&result_tool(None, Some("toolu_2"), false), &map));
    }

    #[test]
    fn specificity_ties_go_to_the_later_filter() {
        let map = ToolIdMap::new();
        // Two matching short filters of equal specificity: the later limit wins.
        let filters = ToolVisibility::Filters(vec![
            parse_tool_spec("Bash:s=100").expect("valid"),
            parse_tool_spec("Bash:s=200").expect("valid"),
        ]);
        let (shown, policy) =
            resolve_tool_visibility(&use_tool("Bash"), &filters, &map, 500, false);
        assert!(shown);
        assert_eq!(policy.expect("policy").max_chars, 200);
    }

    #[test]
    fn a_more_specific_filter_beats_an_earlier_general_one() {
        let map = ToolIdMap::new();
        let filters = ToolVisibility::Filters(vec![
            parse_tool_spec("Bash:i:s=100").expect("valid"),
            parse_tool_spec("s=200").expect("valid"),
        ]);
        let (_, policy) = resolve_tool_visibility(&use_tool("Bash"), &filters, &map, 500, false);
        assert_eq!(policy.expect("policy").max_chars, 100);
    }

    #[test]
    fn negative_filters_are_a_blocklist_checked_first() {
        let map = ToolIdMap::new();
        let filters = ToolVisibility::Filters(vec![
            parse_tool_spec("!Bash").expect("valid"),
            parse_tool_spec("Bash:s=100").expect("valid"),
        ]);
        let (shown, policy) = resolve_tool_visibility(&use_tool("Bash"), &filters, &map, 500, false);
        assert!(!shown);
        assert!(policy.is_none());
    }

    #[test]
    fn only_negative_filters_show_everything_else() {
        let map = ToolIdMap::new();
        let filters = ToolVisibility::Filters(vec![parse_tool_spec("!Bash").expect("valid")]);
        let (shown, _) = resolve_tool_visibility(&use_tool("Read"), &filters, &map, 500, false);
        assert!(shown);
    }

    #[test]
    fn the_short_modifier_takes_its_spec_after_the_equals_sign() {
        let filter = parse_tool_spec("Bash:s=p=128").expect("valid");
        assert!(filter.short);
        assert_eq!(filter.short_max_chars, Some(128));
        assert_eq!(filter.short_progressive, Some(true));

        let plain = parse_tool_spec("Bash:s=8").expect("valid");
        assert_eq!(plain.short_max_chars, Some(8));
        assert_eq!(plain.short_progressive, Some(false));

        let bare = parse_tool_spec("Bash:s").expect("valid");
        assert!(bare.short);
        assert_eq!(bare.short_max_chars, None);
        assert_eq!(bare.short_progressive, None);
    }

    #[test]
    fn the_lookahead_gathers_a_colon_separated_spec_and_then_rejects_it() {
        // `_tool_short_value` joins the next token when both look like short
        // components, and `parse_short_spec` then refuses the colon form. So these
        // are errors in Python too — the lookahead exists to name the whole value in
        // the message, not to accept it. Verified against the oracle.
        for rejected in ["Bash:s=p:128", "Bash:s=8:p", "Bash:s=8:"] {
            assert!(
                parse_tool_spec(rejected).is_err(),
                "expected {rejected:?} to be rejected"
            );
        }
    }

    #[test]
    fn a_repeated_short_modifier_is_rejected() {
        assert!(parse_tool_spec("Bash:s:s").is_err());
    }

    #[test]
    fn a_later_bare_token_overwrites_the_name_when_short_is_absent() {
        // Python assigns unconditionally while `not tf.short`, so the last one wins.
        let filter = parse_tool_spec("Bash:Read").expect("valid");
        assert_eq!(filter.name.as_deref(), Some("Read"));
    }
}
