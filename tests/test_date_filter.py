#!/usr/bin/env python3
"""
Unit tests for parse_date_filter function.

Tests date parsing for --mafter/--cafter search filters.
Covers: ISO dates, ISO datetimes, relative formats, edge cases.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from conversations import parse_date_filter


class TestISODateFormats:
    """Test ISO date parsing (YYYY-MM-DD and YY-MM-DD)."""

    def test_full_year_date(self):
        """YYYY-MM-DD format."""
        result = parse_date_filter("2024-12-15")
        assert result == datetime(2024, 12, 15)

    def test_short_year_date(self):
        """YY-MM-DD format (2-digit year)."""
        result = parse_date_filter("24-12-15")
        assert result == datetime(2024, 12, 15)

    def test_short_year_date_2000s(self):
        """YY-MM-DD with year in 2000s."""
        result = parse_date_filter("05-06-20")
        assert result == datetime(2005, 6, 20)


class TestISODatetimeFormats:
    """Test ISO datetime parsing with various separators and precisions."""

    def test_datetime_with_T_no_seconds(self):
        """YYYY-MM-DDTHH:MM format."""
        result = parse_date_filter("2024-12-15T14:30")
        assert result == datetime(2024, 12, 15, 14, 30)

    def test_datetime_with_space_no_seconds(self):
        """YYYY-MM-DD HH:MM format (space separator)."""
        result = parse_date_filter("2024-12-15 14:30")
        assert result == datetime(2024, 12, 15, 14, 30)

    def test_datetime_with_T_and_seconds(self):
        """YYYY-MM-DDTHH:MM:SS format."""
        result = parse_date_filter("2024-12-15T14:30:45")
        assert result == datetime(2024, 12, 15, 14, 30, 45)

    def test_datetime_with_space_and_seconds(self):
        """YYYY-MM-DD HH:MM:SS format."""
        result = parse_date_filter("2024-12-15 14:30:45")
        assert result == datetime(2024, 12, 15, 14, 30, 45)

    def test_short_year_datetime(self):
        """YY-MM-DDTHH:MM format."""
        result = parse_date_filter("24-12-15T14:30")
        assert result == datetime(2024, 12, 15, 14, 30)

    def test_short_year_datetime_with_seconds(self):
        """YY-MM-DDTHH:MM:SS format."""
        result = parse_date_filter("24-12-15T14:30:45")
        assert result == datetime(2024, 12, 15, 14, 30, 45)


class TestRelativeFormats:
    """Test relative date formats (Nh, Nd, Nw, Nm, Ny)."""

    def test_hours(self):
        """Nh format (hours ago)."""
        result = parse_date_filter("3h")
        expected = datetime.now() - timedelta(hours=3)
        # Allow 1 second tolerance for test execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_days(self):
        """Nd format (days ago)."""
        result = parse_date_filter("2d")
        expected = datetime.now() - timedelta(days=2)
        assert abs((result - expected).total_seconds()) < 1

    def test_weeks(self):
        """Nw format (weeks ago)."""
        result = parse_date_filter("1w")
        expected = datetime.now() - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 1

    def test_months(self):
        """Nm format (months ago, approximate 30 days)."""
        result = parse_date_filter("2m")
        expected = datetime.now() - timedelta(days=60)  # 2 * 30
        assert abs((result - expected).total_seconds()) < 1

    def test_years(self):
        """Ny format (years ago, approximate 365 days)."""
        result = parse_date_filter("1y")
        expected = datetime.now() - timedelta(days=365)
        assert abs((result - expected).total_seconds()) < 1

    def test_large_relative(self):
        """Large relative value."""
        result = parse_date_filter("100d")
        expected = datetime.now() - timedelta(days=100)
        assert abs((result - expected).total_seconds()) < 1

    def test_case_insensitive(self):
        """Relative format should be case-insensitive."""
        result_lower = parse_date_filter("1d")
        result_upper = parse_date_filter("1D")
        # Both should be ~1 day ago
        assert abs((result_lower - result_upper).total_seconds()) < 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_none_input(self):
        """None input returns None."""
        result = parse_date_filter(None)
        assert result is None

    def test_invalid_format_raises(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_date_filter("not-a-date")
        assert "Invalid date format" in str(exc_info.value)

    def test_invalid_relative_unit_raises(self):
        """Invalid relative unit raises ValueError."""
        with pytest.raises(ValueError):
            parse_date_filter("5x")  # 'x' is not a valid unit

    def test_empty_string_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_date_filter("")

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace is trimmed."""
        result = parse_date_filter("  2024-12-15  ")
        assert result == datetime(2024, 12, 15)


if __name__ == "__main__":
    import subprocess

    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    sys.exit(result.returncode)
