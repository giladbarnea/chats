# Date-filter gate

Differential for `pool_filter::parse_date_filter` against `chats.date_filters.parse_date_filter`.

36 cases spanning the accepted shapes and the near-misses: both year widths, all
five relative units in both cases, whitespace, and malformed input. **36/36 agree**
on accept/reject and on the parsed value.

Pin the clock on both sides (`CH_NOW=2026-08-28T12:00:00`) or the relative units
are uncomparable.

## Falsification — five mutations, all caught

| mutation | hazard | disagreements |
| --- | --- | --- |
| `year_width_ignored` | `%Y` must match exactly four digits | 2 |
| `month_is_calendar` | a month is 30 days, not a calendar month | 2 |
| `year_is_366` | a year is 365 days | 2 |
| `empty_accepted` | an empty value is an error, not "no filter" | 2 |
| `case_sensitive_units` | `1D` means the same as `1d` | 5 |

Baseline is 0. Any mutation moving it off 0 is caught.

## The defect this gate found

chrono's `%Y` accepts a two-digit year where CPython's `strptime` requires exactly
four. So `-ma 24-12-15` parsed as **year 24** natively and **2024** in Python — a
two-thousand-year error on a plausible input, silently narrowing or widening the
filter. Fixed by selecting the format set from the year token's width.
