from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from typing import TypeVar

T = TypeVar("T")

_SINGLE_NEGATIVE_INDEX = re.compile(r"^-[1-9]\d*$")


def is_single_negative_index(value: str) -> bool:
    """Return True when value is a single negative integer like '-1'."""
    return bool(_SINGLE_NEGATIVE_INDEX.fullmatch(value.strip()))


def sort_by_modified[T](
    items: Iterable[T],
    *,
    modified_at: Callable[[T], datetime | None],
) -> list[T]:
    """Sort items from oldest to newest by modification timestamp."""
    return sorted(items, key=lambda item: modified_at(item) or datetime.min)


def sort_by_modified_descending[T](
    items: Iterable[T],
    *,
    modified_at: Callable[[T], datetime | None],
) -> list[T]:
    """Sort items from newest to oldest by modification timestamp."""
    return sorted(
        items,
        key=lambda item: modified_at(item) or datetime.min,
        reverse=True,
    )


def resolve_negative_index[T](selector: str, ordered_items: Sequence[T]) -> T | None:
    """Resolve a negative index like '-1' against an already ordered sequence."""
    if not is_single_negative_index(selector):
        return None

    try:
        return ordered_items[int(selector)]
    except IndexError:
        return None
