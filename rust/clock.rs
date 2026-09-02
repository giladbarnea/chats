//! The instant age rendering measures against.
//!
//! Age is the one search output where identical inputs legitimately produce
//! different bytes on different days, so a byte diff between the Python and
//! native routes is meaningless across it unless both read the same instant.

use chrono::{Local, NaiveDateTime};

pub const NOW_OVERRIDE_VARIABLE: &str = "CH_NOW";
const NOW_OVERRIDE_FORMAT: &str = "%Y-%m-%dT%H:%M:%S";

/// The current instant, overridden by `CH_NOW` when it is set.
///
/// Panics when `CH_NOW` is set but unparseable, rather than silently reverting
/// to the wall clock — a harness that believes it pinned the clock and did not
/// would compare two different instants and call the difference a regression.
pub fn resolved_now() -> NaiveDateTime {
    match std::env::var(NOW_OVERRIDE_VARIABLE) {
        Err(_) => Local::now().naive_local(),
        Ok(override_value) => parse_override(&override_value)
            .unwrap_or_else(|| panic!("{NOW_OVERRIDE_VARIABLE} is not {NOW_OVERRIDE_FORMAT}: {override_value}")),
    }
}

/// Parse a `CH_NOW` value under the one format both routes accept.
///
/// ```
/// # use _native::clock::parse_override;
/// assert!(parse_override("2026-08-20T18:00:00").is_some());
/// assert!(parse_override("2026-08-20").is_none());
/// ```
pub fn parse_override(value: &str) -> Option<NaiveDateTime> {
    NaiveDateTime::parse_from_str(value, NOW_OVERRIDE_FORMAT).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_canonical_format_parses() {
        let parsed = parse_override("2026-08-20T18:00:00").expect("canonical value parses");
        assert_eq!(
            parsed.to_string(),
            "2026-08-20 18:00:00",
            "Expected the pinned format to round-trip to the given instant."
        );
    }

    // Python's `datetime.strptime` with the same format rejects each of these,
    // so the native route must reject them too or a harness value accepted on
    // one route and refused on the other would compare two different clocks.
    #[test]
    fn everything_outside_the_pinned_format_is_rejected() {
        for value in [
            "2026-08-20",
            "2026-08-20T18:00",
            "2026-08-20T18:00:00Z",
            "2026-08-20T18:00:00+03:00",
            "2026-08-20T18:00:00.500",
            "2026-08-20 18:00:00",
            "",
            "now",
        ] {
            assert!(
                parse_override(value).is_none(),
                "Expected {value:?} to be rejected, matching Python strptime."
            );
        }
    }
}
