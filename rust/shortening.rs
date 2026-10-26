//! Shortening policy and the truncation it applies.
//!
//! Policy and structure-aware allocation mirror `src/chats/shortening.py`.
//! Strings count Unicode code points, not bytes, graphemes, or display columns.

use serde_json::Value;

use crate::model::canonicalize_json_numbers;

pub const DEFAULT_SHORT_MAX_CHARS: i64 = 500;
pub const MIN_SHORT_MAX_CHARS: i64 = 8;

/// Whether a token names the progressive mode, matching Python's set membership.
pub fn is_progressive_component(candidate: &str) -> bool {
    matches!(candidate.to_lowercase().as_str(), "p" | "progressive")
}

/// A complete shortening limit and progression mode.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct ShortPolicy {
    pub max_chars: i64,
    pub progressive: bool,
}

impl ShortPolicy {
    pub fn new(max_chars: i64, progressive: bool) -> Self {
        Self {
            max_chars,
            progressive,
        }
    }

    /// This policy's limit at one progressive sequence position.
    ///
    /// ```
    /// use _native::shortening::ShortPolicy;
    /// assert_eq!(ShortPolicy::new(128, true).effective_max_chars(Some(1), 4), 48);
    /// assert_eq!(ShortPolicy::new(128, true).effective_max_chars(None, 4), 128);
    /// assert_eq!(ShortPolicy::new(128, false).effective_max_chars(Some(1), 4), 128);
    /// ```
    pub fn effective_max_chars(&self, position: Option<usize>, qualifying_count: usize) -> i64 {
        let Some(position) = position else {
            return self.max_chars;
        };
        if !self.progressive || qualifying_count <= 1 {
            return self.max_chars;
        }
        // Python's `//` floors; `div_euclid` matches it for a positive divisor.
        MIN_SHORT_MAX_CHARS
            + (position as i64 * (self.max_chars - MIN_SHORT_MAX_CHARS))
                .div_euclid(qualifying_count as i64 - 1)
    }
}

/// A parsed short spec whose omitted limit can inherit from a policy.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ShortSpec {
    pub max_chars: Option<i64>,
    pub progressive: bool,
}

impl ShortSpec {
    pub fn resolve(&self, default: ShortPolicy) -> ShortPolicy {
        ShortPolicy {
            max_chars: self.max_chars.unwrap_or(default.max_chars),
            progressive: self.progressive,
        }
    }
}

fn invalid_short_spec(candidate: &str) -> String {
    format!(
        "Invalid short value: {}. Expected N, p, progressive, p=N, or progressive=N with N >= 8.",
        crate::model::python_repr_string(candidate)
    )
}

/// Parse the shared global and tool-local short-spec grammar.
///
/// ```
/// use _native::shortening::parse_short_spec;
/// let spec = parse_short_spec("progressive=32").expect("valid");
/// assert_eq!((spec.max_chars, spec.progressive), (Some(32), true));
/// assert_eq!(parse_short_spec("p").expect("valid").max_chars, None);
/// assert!(parse_short_spec("7").is_err());
/// ```
pub fn parse_short_spec(candidate: &str) -> Result<ShortSpec, String> {
    let (progressive_component, separator, maximum_component) = match candidate.find('=') {
        Some(index) => (&candidate[..index], true, &candidate[index + 1..]),
        None => (candidate, false, ""),
    };
    let is_progressive = is_progressive_component(progressive_component);

    if is_progressive && separator {
        let maximum = parse_python_digits(maximum_component)
            .ok_or_else(|| invalid_short_spec(candidate))?;
        if maximum < MIN_SHORT_MAX_CHARS {
            return Err(invalid_short_spec(candidate));
        }
        return Ok(ShortSpec {
            max_chars: Some(maximum),
            progressive: true,
        });
    }

    if is_progressive {
        return Ok(ShortSpec {
            max_chars: None,
            progressive: true,
        });
    }

    if separator {
        return Err(invalid_short_spec(candidate));
    }
    let maximum =
        parse_python_digits(candidate).ok_or_else(|| invalid_short_spec(candidate))?;
    if maximum < MIN_SHORT_MAX_CHARS {
        return Err(invalid_short_spec(candidate));
    }
    Ok(ShortSpec {
        max_chars: Some(maximum),
        progressive: false,
    })
}

/// Accept the digit strings Python's `str.isdigit()` accepts and `int()` can convert.
///
/// Python guards these with `isdigit()` and then calls `int()`. The two disagree on
/// characters that are digits without a decimal value — `"²".isdigit()` is true while
/// `int("²")` raises — so Python raises an uncaught `ValueError` there rather than its
/// own message. That shape is unreachable through a valid spec and is not reproduced;
/// it is recorded as a contract gap instead.
fn parse_python_digits(value: &str) -> Option<i64> {
    if value.is_empty() {
        return None;
    }
    let mut total: i64 = 0;
    for character in value.chars() {
        let digit = character.to_digit(10).or_else(|| decimal_digit_value(character))?;
        total = total.checked_mul(10)?.checked_add(digit as i64)?;
    }
    Some(total)
}

/// Decimal value of a non-ASCII Unicode decimal digit (category Nd).
fn decimal_digit_value(character: char) -> Option<u32> {
    use unicode_general_category::{GeneralCategory, get_general_category};
    if get_general_category(character) != GeneralCategory::DecimalNumber {
        return None;
    }
    // Every Nd block is ten consecutive code points starting at its zero.
    let mut zero = character as u32;
    while zero > 0
        && get_general_category(char::from_u32(zero - 1)?) == GeneralCategory::DecimalNumber
        && (character as u32) - (zero - 1) < 10
    {
        zero -= 1;
    }
    Some((character as u32) - zero)
}

#[derive(Clone, Copy, PartialEq)]
enum PayloadContext {
    Value,
    Result,
    Block,
}

fn children(value: &Value, context: PayloadContext) -> Vec<(&Value, PayloadContext)> {
    match value {
        Value::Object(fields) => fields.iter()
            .filter(|(key, _)| !(context == PayloadContext::Block && key.as_str() == "type"))
            .map(|(_, value)| (value, PayloadContext::Value)).collect(),
        Value::Array(items) => items.iter().map(|value| (value,
            if context == PayloadContext::Result { PayloadContext::Block } else { PayloadContext::Value }
        )).collect(),
        _ => Vec::new(),
    }
}

fn payload_cost(value: &Value, context: PayloadContext) -> usize {
    match value {
        Value::String(value) => value.chars().count(),
        Value::Array(_) | Value::Object(_) => children(value, context).into_iter()
            .map(|(value, context)| payload_cost(value, context)).sum(),
        _ => value.to_string().len(),
    }
}

fn minimum_cost(value: &Value, context: PayloadContext) -> usize {
    let cost = payload_cost(value, context);
    match value {
        Value::String(_) => cost.min(2),
        Value::Array(_) | Value::Object(_) => {
            let positive: Vec<usize> = children(value, context).into_iter()
                .map(|(value, context)| minimum_cost(value, context))
                .filter(|cost| *cost != 0).collect();
            cost.min(positive.iter().min().copied().unwrap_or(0) + usize::from(positive.len() > 1))
        }
        _ => cost,
    }
}

fn allocate(costs: &[usize], minimums: &[usize], budget: usize) -> Vec<usize> {
    let mut limits = minimums.to_vec();
    let mut remaining = budget - limits.iter().sum::<usize>();
    let mut count = costs.len();
    let mut indices: Vec<usize> = (0..count).collect();
    indices.sort_by_key(|index| costs[*index] - minimums[*index]);
    for index in indices {
        let extra = (costs[index] - minimums[index]).min(remaining.div_ceil(count));
        limits[index] += extra;
        remaining -= extra;
        count -= 1;
    }
    limits
}

fn retained_ends(minimums: &[usize], budget: usize) -> (usize, usize) {
    let mut prefix = vec![0];
    for cost in minimums {
        prefix.push(prefix.last().unwrap() + cost);
    }
    let mut lower = 0;
    let mut upper = minimums.len() - 1;
    while lower < upper {
        let count = (lower + upper).div_ceil(2);
        let (head, tail) = (count.div_ceil(2), count / 2);
        let cost = prefix[head] + prefix[minimums.len()] - prefix[minimums.len() - tail] + 1;
        if cost <= budget {
            lower = count;
        } else {
            upper = count - 1;
        }
    }
    (lower.div_ceil(2), lower / 2)
}

fn empty_payload(value: &Value) -> Value {
    match value {
        Value::Object(_) => Value::Object(Default::default()),
        Value::Array(_) => Value::Array(Vec::new()),
        _ => Value::String(String::new()),
    }
}

fn marker_payload(value: &Value, marker: &str, context: PayloadContext) -> Value {
    match value {
        Value::Object(fields) => fields.keys()
            .find(|key| !(context == PayloadContext::Block && key.as_str() == "type"))
            .map(|key| Value::Object(serde_json::Map::from_iter([(key.clone(), Value::String(marker.to_string()))])))
            .unwrap_or_else(|| Value::String(marker.to_string())),
        Value::Array(_) => Value::Array(vec![Value::String(marker.to_string())]),
        _ => Value::String(marker.to_string()),
    }
}

fn preview_children(
    children: &[(&Value, PayloadContext)], budget: usize, preserve_roots: bool,
) -> std::collections::BTreeMap<usize, Value> {
    let costs: Vec<usize> = children.iter().map(|(value, context)| payload_cost(value, *context)).collect();
    if costs.iter().sum::<usize>() <= budget {
        return children.iter().enumerate().map(|(index, (value, _))| (index, (*value).clone())).collect();
    }
    if budget == 0 {
        return Default::default();
    }
    let minimums: Vec<usize> = children.iter().map(|(value, context)| minimum_cost(value, *context)).collect();
    let mut indices: Vec<usize> = (0..children.len()).collect();
    let mut marker_index = None;
    if minimums.iter().sum::<usize>() > budget {
        let (head, tail) = retained_ends(&minimums, budget);
        marker_index = Some(head);
        indices = (0..head).chain(std::iter::once(head)).chain(children.len() - tail..children.len()).collect();
    }
    let selected_costs: Vec<usize> = indices.iter().map(|index| if Some(*index) == marker_index { 3 } else { costs[*index] }).collect();
    let selected_minimums: Vec<usize> = indices.iter().map(|index| if Some(*index) == marker_index { 1 } else { minimums[*index] }).collect();
    let limits = allocate(&selected_costs, &selected_minimums, budget);
    indices.into_iter().zip(limits).map(|(index, limit)| {
        let (value, context) = children[index];
        if Some(index) != marker_index {
            return (index, shorten_payload(value, limit, context));
        }
        let marker = if limit >= 3 { "[…]" } else { "…" };
        (index, if preserve_roots { marker_payload(value, marker, context) } else { Value::String(marker.to_string()) })
    }).collect()
}

fn shorten_payload(value: &Value, budget: usize, context: PayloadContext) -> Value {
    if payload_cost(value, context) <= budget {
        return value.clone();
    }
    let items = match value {
        Value::String(value) => return Value::String(shorten_string(value, budget)),
        Value::Array(_) | Value::Object(_) => children(value, context),
        _ => return Value::String(if budget >= 3 { "[…]" } else { "…" }.to_string()),
    };
    let previews = preview_children(&items, budget, false);
    match value {
        Value::Array(_) => Value::Array(previews.into_values().collect()),
        Value::Object(fields) => {
            let mut index = 0;
            Value::Object(fields.iter().filter_map(|(key, value)| {
                if context == PayloadContext::Block && key == "type" {
                    return Some((key.clone(), value.clone()));
                }
                let preview = previews.get(&index).map(|value| (key.clone(), value.clone()));
                index += 1;
                preview
            }).collect())
        }
        _ => unreachable!(),
    }
}

/// Share one message budget across recursive payloads, preserving short values.
///
/// ```
/// use _native::shortening::shorten_payloads;
/// use serde_json::json;
/// let payload = json!({"left": true, "middle": false, "last": 123});
/// assert_eq!(shorten_payloads(vec![(payload, false)], 8), vec![json!({"left": true, "middle": "…", "last": 123})]);
/// ```
pub fn shorten_payloads(mut values: Vec<(Value, bool)>, max_chars: i64) -> Vec<Value> {
    for (value, _) in &mut values {
        canonicalize_json_numbers(value).expect("parsed payload numbers have valid JSON spellings");
    }
    let children: Vec<(&Value, PayloadContext)> = values.iter().map(|(value, result)| (value,
        if *result { PayloadContext::Result } else { PayloadContext::Value }
    )).collect();
    let previews = preview_children(&children, max_chars as usize, true);
    values.iter().enumerate().map(|(index, (value, _))| previews.get(&index).cloned().unwrap_or_else(|| empty_payload(value))).collect()
}

fn shorten_string(value: &str, budget: usize) -> String {
    let length = value.chars().count();
    if length <= budget {
        return value.to_string();
    }
    if budget == 0 {
        return String::new();
    }
    if value.contains('\n') {
        return shorten_lines(value, budget);
    }
    let marker = if budget >= 5 { "[…]" } else { "…" };
    let remaining = budget - marker.chars().count();
    let (head, tail) = (remaining.div_ceil(2), remaining / 2);
    let mut shortened: String = value.chars().take(head).collect();
    shortened.push_str(marker);
    shortened.extend(value.chars().skip(length - tail));
    shortened
}

fn shorten_lines(value: &str, budget: usize) -> String {
    let lines: Vec<&str> = value.split_inclusive('\n').collect();
    let lengths: Vec<usize> = lines.iter().map(|line| line.chars().count()).collect();
    let (mut head, mut tail, mut head_cost, mut tail_cost) = (0, 0, 0, 0);
    let mut progress = true;
    while progress && head + tail < lines.len() - 1 {
        progress = false;
        for from_head in [true, false] {
            if head + tail >= lines.len() - 1 {
                break;
            }
            let index = if from_head { head } else { lines.len() - tail - 1 };
            let candidate_tail = tail + usize::from(!from_head);
            let cost = head_cost + tail_cost + lengths[index] + 1 + usize::from(candidate_tail > 0);
            if cost > budget {
                continue;
            }
            head += usize::from(from_head);
            tail += usize::from(!from_head);
            head_cost += if from_head { lengths[index] } else { 0 };
            tail_cost += if from_head { 0 } else { lengths[index] };
            progress = true;
        }
    }
    if head > 0 || tail > 0 {
        return format!("{}…{}", lines[..head].concat(),
            if tail > 0 { format!("\n{}", lines[lines.len() - tail..].concat()) } else { String::new() });
    }
    let endings: Vec<&str> = lines.iter().map(|line| if line.ends_with("\r\n") { "\r\n" } else if line.ends_with('\n') { "\n" } else { "" }).collect();
    let bodies: Vec<&str> = lines.iter().zip(&endings).map(|(line, ending)| &line[..line.len() - ending.len()]).collect();
    let minimums: Vec<usize> = bodies.iter().map(|body| body.chars().count().min(2)).collect();
    let ending_cost: usize = endings.iter().map(|ending| ending.len()).sum();
    if ending_cost + minimums.iter().sum::<usize>() > budget {
        return "…".to_string();
    }
    let costs: Vec<usize> = bodies.iter().map(|body| body.chars().count()).collect();
    let limits = allocate(&costs, &minimums, budget - ending_cost);
    bodies.into_iter().zip(endings).zip(limits).map(|((body, ending), limit)| format!("{}{ending}", shorten_string(body, limit))).collect()
}

/// Whether a detached token should stay attached to `--short`.
///
/// Ported from `looks_like_short_spec`. Used by argument repair to decide whether a
/// token argparse swallowed belongs to `--short` or is a positional.
///
/// ```
/// use _native::shortening::looks_like_short_spec;
/// assert!(looks_like_short_spec(""));
/// assert!(looks_like_short_spec("p"));
/// assert!(looks_like_short_spec("8:"));
/// assert!(!looks_like_short_spec("8"));
/// ```
pub fn looks_like_short_spec(candidate: &str) -> bool {
    if candidate.is_empty() {
        return true;
    }
    let components: Vec<&str> = candidate.split(':').collect();
    let incomplete_numeric_spec = components.len() == 2
        && parse_python_digits(components[0]).is_some_and(|value| value >= MIN_SHORT_MAX_CHARS)
        && components[1].is_empty();
    if incomplete_numeric_spec {
        return true;
    }
    if components.iter().any(|component| is_progressive_component(component)) {
        return true;
    }
    let progressive_component = candidate.split('=').next().unwrap_or(candidate);
    is_progressive_component(progressive_component)
}

/// Whether a token is a positive base-10 integer, as `--short` repair asks.
///
/// Python spells this `candidate.isdigit() and int(candidate) > 0`, whose two halves
/// disagree on digits with no decimal value. See `parse_python_digits`.
pub fn looks_like_positive_integer(candidate: &str) -> bool {
    parse_python_digits(candidate).is_some_and(|value| value > 0)
}

/// Whether a token is a valid explicit `--short` character limit.
pub fn is_valid_short_max_chars_token(candidate: &str) -> bool {
    parse_python_digits(candidate).is_some_and(|value| value > 7)
}

/// Resolve the policy `--short` asked for: absent, bare, or an explicit spec.
pub fn resolve_short_policy(raw: Option<&str>, bare: bool) -> Result<Option<ShortPolicy>, String> {
    if bare {
        return Ok(Some(default_short_policy()));
    }
    let Some(raw) = raw else { return Ok(None) };
    Ok(Some(parse_short_spec(raw)?.resolve(default_short_policy())))
}

/// The default policy, matching `DEFAULT_SHORT_POLICY`.
pub fn default_short_policy() -> ShortPolicy {
    ShortPolicy::new(DEFAULT_SHORT_MAX_CHARS, false)
}

/// Whether `--short` was spelled with an attached `=SHORT_SPEC` value.
///
/// Ported from `_short_uses_attached_value` in `cli.py`. The positional-repair path
/// branches on this: it decides whether `--short 128 needle` reads `128` as the spec
/// or as the pattern.
///
/// ```
/// use _native::shortening::short_uses_attached_value;
/// assert!(short_uses_attached_value(&["--short=128", "needle"]));
/// assert!(short_uses_attached_value(&["-s=p"]));
/// assert!(!short_uses_attached_value(&["--short", "128"]));
/// ```
pub fn short_uses_attached_value<S: AsRef<str>>(argv_tokens: &[S]) -> bool {
    argv_tokens.iter().any(|token| {
        let token = token.as_ref();
        token.starts_with("--short=") || token.starts_with("-s=")
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn progressive_positions_match_the_python_progression() {
        let policy = ShortPolicy::new(128, true);
        let row: Vec<i64> = (0..4).map(|position| policy.effective_max_chars(Some(position), 4)).collect();
        assert_eq!(row, vec![8, 48, 88, 128]);
        assert_eq!(policy.effective_max_chars(Some(0), 1), 128);
    }

    #[test]
    fn spec_grammar_matches_python() {
        assert_eq!(
            parse_short_spec("progressive=32").expect("valid"),
            ShortSpec { max_chars: Some(32), progressive: true }
        );
        assert_eq!(
            parse_short_spec("p").expect("valid"),
            ShortSpec { max_chars: None, progressive: true }
        );
        assert_eq!(
            parse_short_spec("500").expect("valid"),
            ShortSpec { max_chars: Some(500), progressive: false }
        );
        for rejected in ["7", "p=7", "abc", "=32", "12abc", ""] {
            assert!(parse_short_spec(rejected).is_err(), "expected {rejected:?} to be rejected");
        }
    }

    #[test]
    fn unicode_decimal_digits_are_accepted_like_python_int() {
        // Python: "５００".isdigit() is true and int("５００") is 500.
        assert_eq!(
            parse_short_spec("５００").expect("valid").max_chars,
            Some(500)
        );
    }
}
