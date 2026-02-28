from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any


def shorten_data(data: Any, width: int = 120, placeholder: str = "[...]") -> Any:
    """Recursively traverse data and shorten string values."""
    if isinstance(data, dict):
        return {k: shorten_data(v, width, placeholder) for k, v in data.items()}
    if isinstance(data, list):
        return [shorten_data(item, width, placeholder) for item in data]
    if isinstance(data, str):
        return textwrap.shorten(data, width=width, placeholder=placeholder)
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

