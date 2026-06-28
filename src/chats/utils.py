from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def truncate_middle(s: str, max_chars: int = 500) -> str:
    """Shorten a string by replacing its middle with an ellipsis block."""
    placeholder = "\n...\n"
    if max_chars < len(placeholder):
        placeholder = "..."[:max_chars]

    if len(s) <= max_chars - len(placeholder):
        return s

    if max_chars <= len(placeholder):
        return placeholder[:max_chars]

    remaining = max_chars - len(placeholder)
    first_half = remaining // 2 + (remaining % 2)
    second_half = remaining // 2

    return s[:first_half] + placeholder + s[-second_half:]


def shorten_data(data: Any, max_chars: int = 500) -> Any:
    """Recursively shorten every string leaf in ``data`` to ``max_chars`` characters.

    The limit is per string, applied to each leaf as the structure is traversed; it
    does not bound the total size of the object (an object with many keys can still
    exceed ``max_chars`` many times over).
    """
    if isinstance(data, dict):
        return {k: shorten_data(v, max_chars) for k, v in data.items()}
    if isinstance(data, list):
        return [shorten_data(item, max_chars) for item in data]
    if isinstance(data, str):
        return truncate_middle(data, max_chars=max_chars)
    return data


def extract_text_from_content(content: Any, strip: bool = False) -> list[str]:
    """
    Extract text strings from a content field.

    Content may be a string, list of content blocks ({"type": "text", "text": "..."}),
    or other. Returns list of text strings (may be empty).
    """
    if isinstance(content, str):
        text = content.strip() if strip else content
        return [text] if text else []

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                text = text.strip() if strip else text
                if text:
                    texts.append(text)
            elif isinstance(item, str):
                text = item.strip() if strip else item
                if text:
                    texts.append(text)
        return texts

    return []


def collapse_home(path_str: str) -> str:
    """Replace home directory path with ~ for display."""
    home = str(Path.home())
    if path_str.startswith(home):
        return "~" + path_str[len(home) :]
    return path_str


def shorten_tool_use_id(tool_use_id: str | None) -> str | None:
    """Normalize tool use IDs to their short printable form."""
    if not tool_use_id:
        return None
    return tool_use_id.removeprefix("toolu_").removeprefix("call_")[:4]


_AGE_UNITS: tuple[tuple[float, str], ...] = (
    (60.0, "now"),
    (3600.0, "m"),
    (86400.0, "h"),
    (7 * 86400.0, "d"),
    (30 * 86400.0, "w"),
    (365 * 86400.0, "mo"),
)


def humanize_age(then: datetime, now: datetime | None = None) -> str:
    """Render the age of ``then`` as a compact token like ``24m`` or ``2w``.

    >>> base = datetime(2026, 6, 15, 12, 0, 0)
    >>> humanize_age(datetime(2026, 6, 15, 11, 59, 30), base)
    'now'
    >>> humanize_age(datetime(2026, 6, 15, 11, 36, 0), base)
    '24m'
    >>> humanize_age(datetime(2026, 6, 15, 9, 0, 0), base)
    '3h'
    >>> humanize_age(datetime(2026, 6, 14, 12, 0, 0), base)
    '1d'
    >>> humanize_age(datetime(2026, 6, 1, 12, 0, 0), base)
    '2w'
    >>> humanize_age(datetime(2026, 1, 15, 12, 0, 0), base)
    '5mo'
    >>> humanize_age(datetime(2024, 6, 15, 12, 0, 0), base)
    '2y'
    """
    seconds = ((now or datetime.now()) - then).total_seconds()
    if seconds < 60:
        return "now"
    divisors = (1, 60, 3600, 86400, 7 * 86400, 30 * 86400)
    for (ceiling, unit), divisor in zip(_AGE_UNITS, divisors):
        if seconds < ceiling:
            return f"{int(seconds // divisor)}{unit}"
    return f"{int(seconds // (365 * 86400))}y"


def age_style(then: datetime, now: datetime | None = None) -> str:
    """Return the theme style token for an age, brightest for the most recent.

    >>> base = datetime(2026, 6, 15, 12, 0, 0)
    >>> age_style(datetime(2026, 6, 15, 9, 0, 0), base)
    'search.age.now'
    >>> age_style(datetime(2026, 6, 12, 12, 0, 0), base)
    'search.age.week'
    >>> age_style(datetime(2026, 5, 20, 12, 0, 0), base)
    'search.age.month'
    >>> age_style(datetime(2025, 6, 15, 12, 0, 0), base)
    'search.age.old'
    """
    seconds = ((now or datetime.now()) - then).total_seconds()
    if seconds < 86400:
        return "search.age.now"
    if seconds < 7 * 86400:
        return "search.age.week"
    if seconds < 30 * 86400:
        return "search.age.month"
    return "search.age.old"


def elide_to_width(text: str, width: int, *, where: str = "tail") -> str:
    """Shorten ``text`` to ``width`` columns on a single line with an ellipsis.

    >>> elide_to_width("hello world", 20)
    'hello world'
    >>> elide_to_width("hello world", 8)
    'hello w…'
    >>> elide_to_width("/a/very/long/path/here", 12, where="middle")
    '/a/ver…/here'
    """
    if len(text) <= width:
        return text
    if width <= 1:
        return "…"[:width]
    available = width - 1
    if where == "middle":
        left = (available + 1) // 2
        right = available // 2
        return text[:left] + "…" + (text[-right:] if right else "")
    return text[:available] + "…"
