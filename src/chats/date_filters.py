from __future__ import annotations

import re
from datetime import datetime, timedelta


def parse_date_filter(value: str | None) -> datetime | None:
    """Parse --mafter/--cafter value to datetime.

    Supports:
    - ISO dates: YYYY-MM-DD or YY-MM-DD
    - With time: ...THH:MM or ... HH:MM (space separator)
    - With seconds: ...THH:MM:SS
    - Relative: Nh (hours), Nd (days), Nw (weeks), Nm (months), Ny (years)

    Returns None if input is None.
    Raises ValueError for invalid formats.
    """
    if value is None:
        return None

    value = value.strip()
    if not value:
        raise ValueError("Invalid date format: empty string")

    # Try relative format first: Nd, Nw, Nh, Nm, Ny
    match = re.match(r"^(\d+)([hdwmy])$", value, re.IGNORECASE)
    if match:
        n, unit = int(match.group(1)), match.group(2).lower()
        now = datetime.now()
        deltas = {
            "h": timedelta(hours=n),
            "d": timedelta(days=n),
            "w": timedelta(weeks=n),
            "m": timedelta(days=n * 30),  # approximate
            "y": timedelta(days=n * 365),  # approximate
        }
        return now - deltas[unit]

    # Normalize: replace space with T for uniform parsing
    normalized = value.replace(" ", "T")

    # Try ISO formats (most specific first)
    formats = [
        "%Y-%m-%dT%H:%M:%S",  # 2024-12-15T14:30:45
        "%Y-%m-%dT%H:%M",  # 2024-12-15T14:30
        "%Y-%m-%d",  # 2024-12-15
        "%y-%m-%dT%H:%M:%S",  # 24-12-15T14:30:45
        "%y-%m-%dT%H:%M",  # 24-12-15T14:30
        "%y-%m-%d",  # 24-12-15
    ]

    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {value!r}")
