from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
from typing import Literal

DEFAULT_SHORT_MAX_CHARS = 500
MIN_SHORT_MAX_CHARS = 8
PROGRESSIVE_SHORT_COMPONENTS = frozenset({"p", "progressive"})


@dataclass(frozen=True)
class ShortPolicy:
    """A complete shortening limit and progression mode."""

    max_chars: int
    progressive: bool

    def effective_max_chars(
        self,
        position: int | None,
        qualifying_count: int,
    ) -> int:
        """Return this policy's limit at one progressive sequence position.

        >>> ShortPolicy(128, True).effective_max_chars(1, 4)
        48
        """
        if not self.progressive or position is None or qualifying_count <= 1:
            return self.max_chars
        return MIN_SHORT_MAX_CHARS + (
            position * (self.max_chars - MIN_SHORT_MAX_CHARS)
            // (qualifying_count - 1)
        )


@dataclass(frozen=True)
class ShortSpec:
    """A parsed short spec whose omitted fields can inherit a policy."""

    max_chars: int | None
    progressive: bool

    def resolve(self, default: ShortPolicy) -> ShortPolicy:
        """Fill this spec's omitted limit from the supplied policy."""
        return ShortPolicy(
            max_chars=self.max_chars or default.max_chars,
            progressive=self.progressive,
        )


DEFAULT_SHORT_POLICY = ShortPolicy(DEFAULT_SHORT_MAX_CHARS, False)


def shorten_string(value: str, max_chars: int) -> str:
    """Keep a string's head and tail within its character allowance.

    >>> shorten_string("abcdefghij", 7)
    'ab[…]ij'
    """
    if len(value) <= max_chars:
        return value
    if max_chars == 0:
        return ""
    if "\n" in value:
        return _shorten_lines(value, max_chars)
    marker = "[…]" if max_chars >= 5 else "…"
    remaining = max_chars - len(marker)
    head = (remaining + 1) // 2
    tail = remaining // 2
    return value[:head] + marker + (value[-tail:] if tail else "")


def _shorten_lines(value: str, budget: int) -> str:
    pieces = value.split("\n")
    lines = [piece + "\n" for piece in pieces[:-1]]
    if pieces[-1]:
        lines.append(pieces[-1])
    head = tail = head_cost = tail_cost = 0
    progress = True
    while progress and head + tail < len(lines) - 1:
        progress = False
        for from_head in (True, False):
            if head + tail >= len(lines) - 1:
                break
            index = head if from_head else len(lines) - tail - 1
            candidate_tail = tail + (not from_head)
            cost = head_cost + tail_cost + len(lines[index]) + 1 + bool(candidate_tail)
            if cost > budget:
                continue
            head += from_head
            tail += not from_head
            head_cost += len(lines[index]) if from_head else 0
            tail_cost += len(lines[index]) if not from_head else 0
            progress = True
    if head or tail:
        return "".join(lines[:head]) + "…" + ("\n" + "".join(lines[-tail:]) if tail else "")
    endings = ["\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else "" for line in lines]
    bodies = [line[:-len(ending)] if ending else line for line, ending in zip(lines, endings)]
    remaining = budget - sum(map(len, endings))
    minimums = [min(len(body), 2) for body in bodies]
    if sum(minimums) > remaining:
        return "…"
    limits = _allocate(list(map(len, bodies)), minimums, remaining)
    return "".join(shorten_string(body, limit) + ending for body, ending, limit in zip(bodies, endings, limits))


PayloadContext = Literal["value", "result", "block"]


def payload_cost(value: object, context: PayloadContext = "value") -> int:
    """Count payload characters, excluding syntax and result-block discriminators.

    >>> payload_cost({"label": "ok", "enabled": True, "count": 123})
    9
    """
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (dict, list)):
        return sum(payload_cost(child, child_context) for _, child, child_context in _children(value, context))
    return len(json.dumps(value, ensure_ascii=False))


def _children(value: object, context: PayloadContext) -> list[tuple[str | int, object, PayloadContext]]:
    if isinstance(value, dict):
        return [(key, child, "value") for key, child in value.items() if not (context == "block" and key == "type")]
    if isinstance(value, list):
        return [(index, child, "block" if context == "result" else "value") for index, child in enumerate(value)]
    return []


def _minimum_cost(value: object, context: PayloadContext) -> int:
    cost = payload_cost(value, context)
    if isinstance(value, str):
        return min(cost, 2)
    if not isinstance(value, (dict, list)):
        return cost
    minimums = [_minimum_cost(child, child_context) for _, child, child_context in _children(value, context)]
    positive = [minimum for minimum in minimums if minimum]
    return min(cost, min(positive, default=0) + (len(positive) > 1))


def _allocate(costs: Sequence[int], minimums: Sequence[int], budget: int) -> list[int]:
    """Reserve useful previews, then share spare characters across unfinished children.

    >>> _allocate([3, 100, 100], [2, 2, 2], 8)
    [3, 3, 2]
    """
    limits = list(minimums)
    remaining = budget - sum(limits)
    count = len(costs)
    for index in sorted(range(count), key=lambda index: costs[index] - minimums[index]):
        extra = min(costs[index] - minimums[index], (remaining + count - 1) // count)
        limits[index] += extra
        remaining -= extra
        count -= 1
    return limits


def _retained_ends(minimums: Sequence[int], budget: int) -> tuple[int, int]:
    """Keep balanced container ends while reserving one character for an omission.

    >>> _retained_ends([4, 5, 3], 8)
    (1, 1)
    """
    prefix = [0]
    for cost in minimums:
        prefix.append(prefix[-1] + cost)
    lower, upper = 0, len(minimums) - 1
    while lower < upper:
        count = (lower + upper + 1) // 2
        head, tail = (count + 1) // 2, count // 2
        cost = prefix[head] + prefix[-1] - prefix[len(minimums) - tail] + 1
        if cost <= budget:
            lower = count
        else:
            upper = count - 1
    return (lower + 1) // 2, lower // 2


def _empty_payload(value: object) -> object:
    if isinstance(value, dict):
        return {}
    if isinstance(value, list):
        return []
    return ""


def _marker_payload(value: object, marker: str, context: PayloadContext) -> object:
    children = _children(value, context)
    if isinstance(value, dict) and children:
        return {children[0][0]: marker}
    if isinstance(value, list):
        return [marker]
    return marker


def _preview_children(
    children: Sequence[tuple[object, PayloadContext]], budget: int, *, preserve_roots: bool = False,
) -> dict[int, object]:
    costs = [payload_cost(value, context) for value, context in children]
    if sum(costs) <= budget:
        return {index: value for index, (value, _) in enumerate(children)}
    if budget == 0:
        return {}
    minimums = [_minimum_cost(value, context) for value, context in children]
    indices = list(range(len(children)))
    marker_index: int | None = None
    if sum(minimums) > budget:
        head, tail = _retained_ends(minimums, budget)
        marker_index = head
        indices = [*range(head), marker_index, *range(len(children) - tail, len(children))]
    selected_costs = [3 if index == marker_index else costs[index] for index in indices]
    selected_minimums = [1 if index == marker_index else minimums[index] for index in indices]
    limits = _allocate(selected_costs, selected_minimums, budget)
    previews: dict[int, object] = {}
    for index, limit in zip(indices, limits):
        value, context = children[index]
        if index != marker_index:
            previews[index] = _shorten_payload(value, limit, context)
            continue
        marker = "[…]" if limit >= 3 else "…"
        previews[index] = _marker_payload(value, marker, context) if preserve_roots else marker
    return previews


def _shorten_payload(value: object, budget: int, context: PayloadContext) -> object:
    if payload_cost(value, context) <= budget:
        return value
    if isinstance(value, str):
        return shorten_string(value, budget)
    if not isinstance(value, (dict, list)):
        return "[…]" if budget >= 3 else "…"
    children = _children(value, context)
    previews = _preview_children([(child, child_context) for _, child, child_context in children], budget)
    if isinstance(value, list):
        return list(previews.values())
    replacements = {children[index][0]: preview for index, preview in previews.items()}
    return {key: replacements[key] if key in replacements else child
            for key, child in value.items() if key in replacements or context == "block" and key == "type"}


def shorten_payloads(values: Sequence[tuple[object, bool]], max_chars: int) -> list[object]:
    """Share a message budget across recursive payloads while preserving tool identity.

    >>> shorten_payloads([({"a": "aa", "b": "bb", "c": "cc", "d": "dd", "e": "ee"}, False)], 5)
    [{'a': 'aa', 'b': '…', 'e': 'ee'}]
    """
    children = [(value, "result" if result else "value") for value, result in values]
    previews = _preview_children(children, max_chars, preserve_roots=True)
    return [previews.get(index, _empty_payload(value)) for index, (value, _) in enumerate(values)]


def parse_short_spec(candidate: str) -> ShortSpec:
    """Parse the shared global and tool-local short-spec grammar.

    >>> parse_short_spec("progressive=32")
    ShortSpec(max_chars=32, progressive=True)
    """
    progressive_component, separator, maximum_component = candidate.partition("=")
    is_progressive = (
        progressive_component.lower() in PROGRESSIVE_SHORT_COMPONENTS
    )
    progressive_with_limit = is_progressive and bool(separator)

    if progressive_with_limit and not maximum_component.isdigit():
        raise _invalid_short_spec(candidate)
    if progressive_with_limit and int(maximum_component) < MIN_SHORT_MAX_CHARS:
        raise _invalid_short_spec(candidate)
    if progressive_with_limit:
        return ShortSpec(max_chars=int(maximum_component), progressive=True)

    if is_progressive:
        return ShortSpec(max_chars=None, progressive=True)
    if separator or not candidate.isdigit():
        raise _invalid_short_spec(candidate)

    maximum = int(candidate)
    if maximum < MIN_SHORT_MAX_CHARS:
        raise _invalid_short_spec(candidate)
    return ShortSpec(max_chars=maximum, progressive=False)


def looks_like_short_spec(candidate: str) -> bool:
    """Return whether a detached token should stay attached to `--short`."""
    components = candidate.split(":")
    incomplete_numeric_spec = (
        len(components) == 2
        and components[0].isdigit()
        and int(components[0]) >= MIN_SHORT_MAX_CHARS
        and not components[1]
    )
    progressive_component = candidate.partition("=")[0]
    return not candidate or incomplete_numeric_spec or any(
        component.lower() in PROGRESSIVE_SHORT_COMPONENTS
        for component in components
    ) or progressive_component.lower() in PROGRESSIVE_SHORT_COMPONENTS


def _invalid_short_spec(candidate: str) -> ValueError:
    return ValueError(
        f"Invalid short value: {candidate!r}. Expected N, p, progressive, "
        "p=N, or progressive=N with N >= 8."
    )
