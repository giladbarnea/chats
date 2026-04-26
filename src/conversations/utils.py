from __future__ import annotations

from pathlib import Path
from typing import Any


def truncate_middle(s: str, max_len: int = 500) -> str:
    """Shorten a string by replacing its middle with an ellipsis block."""
    placeholder = "\n...\n"
    if max_len < len(placeholder):
        placeholder = "..."[:max_len]

    if len(s) <= max_len - len(placeholder):
        return s

    if max_len <= len(placeholder):
        return placeholder[:max_len]

    remaining = max_len - len(placeholder)
    first_half = remaining // 2 + (remaining % 2)
    second_half = remaining // 2

    return s[:first_half] + placeholder + s[-second_half:]


def shorten_data(data: Any, width: int = 500) -> Any:
    """Recursively traverse data and shorten string values via middle truncation."""
    if isinstance(data, dict):
        return {k: shorten_data(v, width) for k, v in data.items()}
    if isinstance(data, list):
        return [shorten_data(item, width) for item in data]
    if isinstance(data, str):
        return truncate_middle(data, max_len=width)
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
        return "~" + path_str[len(home):]
    return path_str


def shorten_tool_use_id(tool_use_id: str | None) -> str | None:
    """Normalize tool use IDs to their short printable form."""
    if not tool_use_id:
        return None
    return tool_use_id.removeprefix("toolu_").removeprefix("call_")[:4]
