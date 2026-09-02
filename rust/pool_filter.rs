//! Narrowing the session universe by provider, directory, and date.
//!
//! Ported from `src/chats/pool_filter.py` and `src/chats/date_filters.py`.
//!
//! **The probe economy here is contractual, not incidental.** `passes_path_for_date`
//! reads only the timestamp each filter actually needs, and returns early: with
//! `-ma` alone no first timestamp is ever read, and with `-ca` alone no last one
//! is. Both probes are file reads over the whole pool, so collapsing them into
//! one "read both timestamps" call is byte-identical and costs a scan.
//!
//! Confirmed intentional at source: `pool_filter.py`'s docstring says "probes only
//! the timestamp each filter needs", and the two `if` guards are separate rather
//! than combined. Nothing downstream can observe the difference, so no gate here
//! can catch its loss — only reading can.

use crate::clock;
use crate::inventory;
use chrono::{DateTime, Duration, Local, NaiveDate, NaiveDateTime, TimeZone};
use std::io::BufRead;
use std::path::{Path, PathBuf};

/// A relative date suffix and how many days or hours it stands for.
///
/// Months and years are approximated exactly as Python does — 30 and 365 days —
/// so a filter written `3m` means 90 days, not three calendar months.
const RELATIVE_UNITS: &[(char, i64, bool)] = &[
    ('h', 1, true),
    ('d', 1, false),
    ('w', 7, false),
    ('m', 30, false),
    ('y', 365, false),
];

/// ISO shapes accepted for `--mafter` / `--cafter`, most specific first.
///
/// Split by year width on purpose. Python's `strptime` matches `%Y` against
/// exactly four digits, so `24-12-15` falls through to `%y` and means 2024.
/// chrono's `%Y` accepts a short year, which would silently read it as year 24 —
/// a two-thousand-year error on a plausible input.
const FOUR_DIGIT_YEAR_FORMATS: &[&str] =
    &["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"];
const TWO_DIGIT_YEAR_FORMATS: &[&str] =
    &["%y-%m-%dT%H:%M:%S", "%y-%m-%dT%H:%M", "%y-%m-%d"];

/// The formats whose year width matches this input's, or none if it has neither.
fn iso_formats_for(value: &str) -> &'static [&'static str] {
    let year: &str = value.split('-').next().unwrap_or("");
    if year.len() == 4 && year.chars().all(|c| c.is_ascii_digit()) {
        FOUR_DIGIT_YEAR_FORMATS
    } else if year.len() == 2 && year.chars().all(|c| c.is_ascii_digit()) {
        TWO_DIGIT_YEAR_FORMATS
    } else {
        &[]
    }
}

/// Parse a `--mafter` / `--cafter` value.
///
/// `Ok(None)` means no filter was requested. `Err` carries the message Python
/// raises, which the launcher turns into a non-zero exit.
///
/// ```
/// # use _native::pool_filter::parse_date_filter;
/// assert!(parse_date_filter(None).unwrap().is_none());
/// assert!(parse_date_filter(Some("2024-12-15")).unwrap().is_some());
/// assert!(parse_date_filter(Some("bogus-date")).is_err());
/// ```
pub fn parse_date_filter(value: Option<&str>) -> Result<Option<NaiveDateTime>, String> {
    let Some(raw) = value else { return Ok(None) };
    // `python_strip`, not `trim`: Python's `str.strip()` also removes
    // U+001C–U+001F, which Rust's `char::is_whitespace` does not.
    let trimmed = crate::session::python_strip(raw);
    if trimmed.is_empty() {
        return Err("Invalid date format: empty string".to_string());
    }

    if let Some(relative) = parse_relative(trimmed) {
        return Ok(Some(relative));
    }

    // Python normalizes a space separator to `T` before trying the ISO shapes.
    let normalized = trimmed.replace(' ', "T");
    for format in iso_formats_for(&normalized) {
        if let Ok(parsed) = NaiveDateTime::parse_from_str(&normalized, format) {
            return Ok(Some(parsed));
        }
        if let Ok(date) = NaiveDate::parse_from_str(&normalized, format) {
            return Ok(Some(date.and_hms_opt(0, 0, 0).expect("midnight is valid")));
        }
    }
    // Python's `repr`, not Rust's `Debug`: the two disagree on quoting and on
    // escapes, and this string is printed once per candidate file.
    Err(format!(
        "Invalid date format: {}",
        crate::model::python_repr_string(trimmed)
    ))
}

/// `Nh`, `Nd`, `Nw`, `Nm`, `Ny`, case-insensitive, measured back from now.
fn parse_relative(value: &str) -> Option<NaiveDateTime> {
    let (digits, suffix) = value.split_at(value.len().checked_sub(1)?);
    let unit = suffix.chars().next()?.to_ascii_lowercase();
    if digits.is_empty() || !digits.chars().all(|character| character.is_ascii_digit()) {
        return None;
    }
    let count: i64 = digits.parse().ok()?;
    let (_, size, is_hours) = RELATIVE_UNITS.iter().find(|(name, _, _)| *name == unit)?;
    let delta = if *is_hours {
        Duration::hours(count * size)
    } else {
        Duration::days(count * size)
    };
    Some(clock::resolved_now() - delta)
}

/// Narrows the supported-session universe before resolution or search.
#[derive(Debug, Clone, Default)]
pub struct PoolFilter {
    pub provider: Option<String>,
    pub dir: Option<String>,
    mafter: Option<NaiveDateTime>,
    cafter: Option<NaiveDateTime>,
}

impl PoolFilter {
    /// Build from raw argument strings, resolving both date filters once.
    pub fn new(
        provider: Option<String>,
        dir: Option<String>,
        mafter: Option<&str>,
        cafter: Option<&str>,
    ) -> Result<PoolFilter, String> {
        Ok(PoolFilter {
            provider,
            dir,
            mafter: parse_date_filter(mafter)?,
            cafter: parse_date_filter(cafter)?,
        })
    }

    pub fn is_empty(&self) -> bool {
        self.provider.is_none()
            && self.dir.is_none()
            && self.mafter.is_none()
            && self.cafter.is_none()
    }

    pub fn has_date_filters(&self) -> bool {
        self.mafter.is_some() || self.cafter.is_some()
    }

    pub fn needs_content_for_dir(&self) -> bool {
        self.dir.is_some()
    }

    /// Per-path date check that probes only the timestamp each filter needs.
    ///
    /// The two guards stay separate and the first returns early on purpose. See
    /// this module's header: merging them is invisible and costs a scan.
    pub fn passes_path_for_date(&self, path: &Path) -> bool {
        if let Some(threshold) = self.mafter {
            match last_timestamp(path) {
                Some(stamp) if stamp >= threshold => {}
                _ => return false,
            }
        }
        if let Some(threshold) = self.cafter {
            match first_timestamp(path) {
                Some(stamp) if stamp >= threshold => {}
                _ => return false,
            }
        }
        true
    }

    /// Check a session's cwd against the directory filter.
    pub fn passes_cwd(&self, cwd: Option<&str>) -> bool {
        let Some(wanted) = &self.dir else { return true };
        let Some(actual) = cwd else { return false };
        resolve(Path::new(actual)) == resolve(Path::new(wanted))
    }
}

/// Python's `Path.resolve()`: absolute, with symlinks followed where possible.
fn resolve(path: &Path) -> PathBuf {
    std::fs::canonicalize(path).unwrap_or_else(|_| {
        std::env::current_dir()
            .map(|cwd| cwd.join(path))
            .unwrap_or_else(|_| path.to_path_buf())
    })
}

/// Last in-band timestamp, falling back to filesystem mtime.
///
/// The content probe comes first and the filesystem is only a fallback. A prior
/// team shipped an mtime *short circuit* here and withdrew it permanently:
/// imports, copies preserving foreign clocks, `touch -t` and restore tools all
/// produce files whose mtime precedes their content, so it silently dropped hits.
pub fn last_timestamp(path: &Path) -> Option<NaiveDateTime> {
    if let Some(parsed) = inventory::last_timestamp(path).as_deref().and_then(parse_iso) {
        return Some(parsed);
    }
    filesystem_mtime(path)
}

/// First in-band timestamp, falling back to filesystem birth time.
pub fn first_timestamp(path: &Path) -> Option<NaiveDateTime> {
    if let Some(parsed) = first_in_band_timestamp(path).as_deref().and_then(parse_iso) {
        return Some(parsed);
    }
    filesystem_birthtime(path)
}

/// Read forward for the first in-band timestamp, stopping at the first hit.
///
/// Stopping early is the point: a session file can be megabytes and the first
/// timestamp is almost always on line one.
fn first_in_band_timestamp(path: &Path) -> Option<String> {
    let file = std::fs::File::open(path).ok()?;
    for line in std::io::BufReader::new(file).lines() {
        // **A decode failure stops the scan rather than skipping the line.** Python
        // reads the file as text inside a bare `except Exception: pass`, so invalid
        // UTF-8 aborts the whole probe — and it aborts it *lazily*, after any earlier
        // line has already answered, which is why this stays line by line.
        let Ok(line) = line else { return None };
        let trimmed = crate::session::python_strip(&line);
        if trimmed.is_empty() {
            continue;
        }
        if let Some(stamp) = entry_timestamp(trimmed) {
            return Some(stamp);
        }
    }
    None
}

/// `timestamp`, or `created_at` when the first is absent or empty.
fn entry_timestamp(line: &str) -> Option<String> {
    // **`json.loads`, not orjson.** `_find_first_timestamp` uses the stdlib parser,
    // which accepts `NaN` and `Infinity` where `serde_json` refuses them — so a
    // session whose first line carries a `NaN` had its timestamp skipped here and the
    // probe fell through to the next line, or to the filesystem clock. That moves
    // `created:` and it moves which sessions a `-ca` filter returns.
    let entry: serde_json::Map<String, serde_json::Value> =
        serde_json::from_str(&crate::session::detection_lenient(line)).ok()?;
    for key in ["timestamp", "created_at"] {
        if let Some(serde_json::Value::String(value)) = entry.get(key) {
            if !value.is_empty() {
                return Some(value.clone());
            }
        }
    }
    None
}

/// Parse a JSONL timestamp to naive **local** time.
///
/// Session timestamps are usually UTC with a trailing `Z`. Python converts them
/// to local time so they compare correctly against relative filters, which are
/// measured from local now. Comparing a UTC stamp against a local threshold
/// would shift every date filter by the machine's offset.
fn parse_iso(value: &str) -> Option<NaiveDateTime> {
    if value.is_empty() {
        return None;
    }
    // **A lowercase `z` must fail, and it is preserved because it is wrong.**
    // `_parse_iso_timestamp` rewrites only an uppercase `Z`, and `fromisoformat` then
    // raises on the lowercase one — so the caller falls back to the **filesystem**
    // clock, and such a session sorts by a different clock, filters differently under
    // `-ma` and `-ca`, and renders a different date. `chrono`'s RFC-3339 parser accepts
    // both cases, so a port that simply reaches for it is *more correct* and moves the
    // session. Measured: two files with identical content timestamps render seven
    // months apart on the uppercase/lowercase difference alone.
    if value.ends_with('z') {
        return None;
    }
    let normalized = match value.strip_suffix('Z') {
        Some(head) => format!("{head}+00:00"),
        None => value.to_string(),
    };
    if let Ok(aware) = DateTime::parse_from_rfc3339(&normalized) {
        return Some(aware.with_timezone(&Local).naive_local());
    }
    for format in ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"] {
        if let Ok(naive) = NaiveDateTime::parse_from_str(&normalized, format) {
            return Some(naive);
        }
    }
    NaiveDate::parse_from_str(&normalized, "%Y-%m-%d")
        .ok()
        .and_then(|date| date.and_hms_opt(0, 0, 0))
}

fn filesystem_mtime(path: &Path) -> Option<NaiveDateTime> {
    let seconds = inventory::stat_mtime(path);
    if !seconds.is_finite() {
        return None;
    }
    local_from_unix_seconds(seconds)
}

fn filesystem_birthtime(path: &Path) -> Option<NaiveDateTime> {
    let created = std::fs::metadata(path).and_then(|metadata| metadata.created()).ok()?;
    local_from_unix_seconds(created.duration_since(std::time::UNIX_EPOCH).ok()?.as_secs_f64())
}

/// `datetime.fromtimestamp`, **microseconds and all**.
///
/// **Truncating to whole seconds changes newest-first ordering.** `st_mtime` is a float
/// carrying sub-second precision, and two files written inside the same second order by
/// the fraction — which is the ordering this product is built on. Measured: one fixture
/// rendered `…:55` here against Python's `…:55.004794`.
///
/// **CPython rounds the fraction to microseconds with banker's rounding**, then carries.
/// Rust's `f64::round` is half-away-from-zero, so it is not a substitute: the two
/// disagree on every exact half-microsecond, and the carry at 1,000,000 has to be
/// reproduced rather than assumed unreachable.
fn local_from_unix_seconds(seconds: f64) -> Option<NaiveDateTime> {
    let mut whole = seconds.trunc() as i64;
    let mut microseconds = round_half_even((seconds - seconds.trunc()) * 1e6);
    if microseconds >= 1_000_000 {
        whole += 1;
        microseconds -= 1_000_000;
    } else if microseconds < 0 {
        whole -= 1;
        microseconds += 1_000_000;
    }
    Local
        .timestamp_opt(whole, (microseconds as u32) * 1_000)
        .single()
        .map(|moment| moment.naive_local())
}

/// Python's `round()` on a float: ties go to the even neighbour.
fn round_half_even(value: f64) -> i64 {
    let floor = value.floor();
    let fraction = value - floor;
    let rounded = if fraction > 0.5 {
        floor + 1.0
    } else if fraction < 0.5 {
        floor
    } else if (floor as i64) % 2 == 0 {
        floor
    } else {
        floor + 1.0
    };
    rounded as i64
}
