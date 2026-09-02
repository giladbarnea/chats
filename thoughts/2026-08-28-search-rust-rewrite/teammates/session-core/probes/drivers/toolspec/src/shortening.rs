//! Shortening policy and the truncation it applies.
//!
//! Ported from `src/chats/shortening.py` and `truncate_middle` / `shorten_data` in
//! `src/chats/utils.py`, at oracle revision `8cb4c5f`.
//!
//! Two behaviours here look like defects and are reproduced deliberately. Python
//! counts **code points**, never display columns, so a string of wide characters
//! survives a budget it visibly exceeds. And `truncate_middle` ends with
//! `s[-second_half:]`, which returns the *whole* string when `second_half` is zero,
//! so the result can be longer than the input. See `truncate_middle` below.

use serde_json::Value;

pub const DEFAULT_SHORT_MAX_CHARS: i64 = 500;
pub const MIN_SHORT_MAX_CHARS: i64 = 8;

const PLACEHOLDER: &str = "\n...\n";
const SHORT_PLACEHOLDER: &str = "...";

/// Whether a token names the progressive mode, matching Python's set membership.
pub fn is_progressive_component(candidate: &str) -> bool {
    matches!(candidate.to_lowercase().as_str(), "p" | "progressive")
}

/// A complete shortening limit and progression mode.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
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

/// Shorten a string by replacing its middle with an ellipsis block.
///
/// Counts **code points**, matching Python, so this splits grapheme clusters and
/// ignores display width. It is also normalization-sensitive: the same visible text
/// truncates differently as NFC and NFD.
///
/// The `second_half == 0` case reproduces Python's `s[-0:]`, which is `s[0:]` — the
/// whole string. The result is then *longer* than `max_chars`. Reachable only below
/// the grammar's floor of 8, but reproduced verbatim rather than guarded.
///
/// ```
/// use _native::shortening::truncate_middle;
/// // remaining = 10 - 5 = 5, so three characters of head and two of tail.
/// assert_eq!(truncate_middle("abcdefghij", 10), "abc\n...\nij");
/// assert_eq!(truncate_middle("abcdefghij", 8), "ab\n...\nj");
/// assert_eq!(truncate_middle("abcde", 10), "abcde");
/// assert_eq!(truncate_middle("abcdefghij", 3), "...");
/// ```
pub fn truncate_middle(value: &str, max_chars: i64) -> String {
    let characters: Vec<char> = value.chars().collect();
    let length = characters.len() as i64;

    let placeholder: Vec<char> = if max_chars < PLACEHOLDER.chars().count() as i64 {
        SHORT_PLACEHOLDER
            .chars()
            .take(max_chars.max(0) as usize)
            .collect()
    } else {
        PLACEHOLDER.chars().collect()
    };
    let placeholder_length = placeholder.len() as i64;

    if length <= max_chars - placeholder_length {
        return value.to_string();
    }
    if max_chars <= placeholder_length {
        return placeholder
            .into_iter()
            .take(max_chars.max(0) as usize)
            .collect();
    }

    let remaining = max_chars - placeholder_length;
    let first_half = (remaining / 2 + remaining % 2) as usize;
    let second_half = (remaining / 2) as usize;

    let mut result: String = characters.iter().take(first_half).collect();
    result.extend(placeholder.iter());
    // `s[-0:]` is the whole string, not the empty one.
    let tail_start = if second_half == 0 {
        0
    } else {
        characters.len().saturating_sub(second_half)
    };
    result.extend(characters[tail_start..].iter());
    result
}

/// Recursively shorten every string leaf, preserving object key order.
///
/// The limit is per string leaf, applied as the structure is traversed; it does not
/// bound the total size of the value.
pub fn shorten_data(value: &Value, max_chars: i64) -> Value {
    match value {
        Value::Object(entries) => Value::Object(
            entries
                .iter()
                .map(|(key, nested)| (key.clone(), shorten_data(nested, max_chars)))
                .collect(),
        ),
        Value::Array(items) => {
            Value::Array(items.iter().map(|item| shorten_data(item, max_chars)).collect())
        }
        Value::String(text) => Value::String(truncate_middle(text, max_chars)),
        other => other.clone(),
    }
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
    fn truncation_counts_code_points_not_bytes() {
        // Sixteen code points out, whatever their byte width.
        for sample in ["abcdefghijklmnopqrstuvwxyz", "אבגדהוזחטיכלמנסעפצקרשת", "日本語のテキストです日本語"] {
            let shortened = truncate_middle(sample, 16);
            assert_eq!(
                shortened.chars().count(),
                16,
                "expected 16 code points from {sample:?}, got {shortened:?}"
            );
        }
    }

    #[test]
    fn a_string_shorter_than_the_limit_can_come_back_longer() {
        // Preserved because Python does it: the passthrough test subtracts the
        // placeholder before comparing, so six characters become ten.
        // Distinct characters on purpose — a uniform "xxxxxx" passes this test even
        // if head and tail are swapped, which is exactly the mistake it must catch.
        let shortened = truncate_middle("abcdef", 10);
        assert_eq!(shortened, "abc\n...\nef");
        assert_eq!(shortened.chars().count(), 10);
    }

    #[test]
    fn the_tail_comes_from_the_end_of_the_string() {
        // The head/tail split is the one thing a same-character sample cannot check.
        assert_eq!(truncate_middle("abcdefghij", 10), "abc\n...\nij");
        assert_eq!(truncate_middle("abcdefghij", 8), "ab\n...\nj");
    }

    #[test]
    fn negative_zero_slice_returns_the_whole_string() {
        // `s[-0:]` is `s[0:]`. Reproduced, not guarded.
        assert_eq!(truncate_middle("abcdefghij", 4), "a...abcdefghij");
        assert_eq!(truncate_middle("abcdefghij", 6), "a\n...\nabcdefghij");
    }

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
