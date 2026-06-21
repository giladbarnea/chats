from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from ..console import get_console, print_error
from ..parsing import (
    decode_jsonl_entries,
    extract_latest_custom_title_from_content,
    get_display_session_id,
    get_jsonl_first_timestamp,
    get_jsonl_last_timestamp,
    get_jsonl_session_adapter,
)
from . import resolve

# Providers whose token/cost data `info` knows how to aggregate.
SUPPORTED_INFO_PROVIDERS = ("claude", "pi")

# Per-model (input, output) USD price per 1M tokens for Claude, which does not
# store cost in its session files. Cache reads bill at 0.1x input and cache
# writes (5-minute TTL) at 1.25x input — the standard Anthropic ratios.
_CLAUDE_INPUT_OUTPUT_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-opus-4": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
# Cache reads bill at 0.1x input; cache writes bill per TTL — 1.25x for the
# 5-minute window, 2x for the 1-hour window. Claude records which bucket each
# write landed in, so writes are priced from that split rather than assumed.
_CACHE_READ_PRICE_RATIO = 0.1
_CACHE_WRITE_5M_PRICE_RATIO = 1.25
_CACHE_WRITE_1H_PRICE_RATIO = 2.0


@dataclass
class ModelUsage:
    """Token counts and dollar cost accumulated for one model within a session."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost: float = 0.0

    def add(self, other: ModelUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cost += other.cost

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


@dataclass
class SessionInfo:
    """Aggregated statistics for one session, ready to render."""

    name: str | None
    path: Path
    session_id: str
    provider: str
    wall_duration: timedelta | None
    api_duration: timedelta | None
    usage_by_model: dict[str, ModelUsage]
    user_messages: int
    assistant_messages: int
    tool_calls: int
    tool_results: int
    # PI stores a per-message `totalTokens`; summing the provided field is
    # preferred over recomputing it. None when the provider does not record one.
    reported_total_tokens: int | None = None

    @property
    def total_messages(self) -> int:
        # Tool calls live inside assistant messages, so they are not added; tool
        # results are their own returned messages and are.
        return self.user_messages + self.assistant_messages + self.tool_results

    @property
    def totals(self) -> ModelUsage:
        combined = ModelUsage()
        for usage in self.usage_by_model.values():
            combined.add(usage)
        return combined

    @property
    def total_tokens(self) -> int:
        if self.reported_total_tokens is not None:
            return self.reported_total_tokens
        return self.totals.total_tokens


def _claude_model_cost(model: str, usage: dict) -> float:
    """Compute Claude cost from a usage object, tolerating bare/date-stamped ids.

    Cache writes are priced per TTL bucket from the `cache_creation` breakdown
    Claude records (`ephemeral_1h_input_tokens` at 2x input, `ephemeral_5m_input_tokens`
    at 1.25x). When the breakdown is absent, the aggregate write count is priced at
    the 5-minute rate.
    """
    prices = _lookup_claude_price(model)
    if prices is None:
        return 0.0
    input_price, output_price = prices

    breakdown = usage.get("cache_creation") or {}
    write_1h = breakdown.get("ephemeral_1h_input_tokens", 0)
    write_5m = breakdown.get("ephemeral_5m_input_tokens", 0)
    if not breakdown:
        write_5m = usage.get("cache_creation_input_tokens", 0)

    return (
        usage.get("input_tokens", 0) * input_price
        + usage.get("output_tokens", 0) * output_price
        + usage.get("cache_read_input_tokens", 0) * input_price * _CACHE_READ_PRICE_RATIO
        + write_5m * input_price * _CACHE_WRITE_5M_PRICE_RATIO
        + write_1h * input_price * _CACHE_WRITE_1H_PRICE_RATIO
    ) / 1_000_000


def _lookup_claude_price(model: str) -> tuple[float, float] | None:
    """Match a model id to a price, preferring the longest matching known prefix.

    >>> _lookup_claude_price("claude-opus-4-8")
    (5.0, 25.0)
    >>> _lookup_claude_price("claude-haiku-4-5-20251001")
    (1.0, 5.0)
    >>> _lookup_claude_price("claude-sonnet-4-20250514")
    (3.0, 15.0)
    >>> _lookup_claude_price("<synthetic>") is None
    True
    """
    for key in sorted(_CLAUDE_INPUT_OUTPUT_PRICE_PER_MTOK, key=len, reverse=True):
        if model == key or model.startswith(key + "-") or model.startswith(key + "@"):
            return _CLAUDE_INPUT_OUTPUT_PRICE_PER_MTOK[key]
    return None


def _aggregate_claude(entries: list[dict]) -> dict[str, object]:
    """Aggregate token usage, cost, and message counts from Claude entries.

    Claude writes one assistant API response across several lines (one per
    content block) that repeat the same `message.usage` and `message.id`, so
    usage and assistant-message counts are deduplicated by `message.id`. Cost is
    not stored and is computed from a per-model pricing table.
    """
    usage_by_model: dict[str, ModelUsage] = {}
    seen_message_ids: set[str] = set()
    assistant_ids: set[str] = set()
    tool_call_ids: set[str] = set()
    tool_result_ids: set[str] = set()
    user_messages = 0

    for entry in entries:
        entry_type = entry.get("type")
        if entry_type == "assistant":
            _accumulate_claude_assistant(
                entry, usage_by_model, seen_message_ids, assistant_ids, tool_call_ids
            )
        elif entry_type == "user":
            if _count_claude_user_message(entry, tool_result_ids):
                user_messages += 1

    return {
        "usage_by_model": usage_by_model,
        "user_messages": user_messages,
        "assistant_messages": len(assistant_ids),
        "tool_calls": len(tool_call_ids),
        "tool_results": len(tool_result_ids),
        "api_duration": _claude_api_duration(entries),
        "reported_total_tokens": None,
    }


def _accumulate_claude_assistant(
    entry: dict,
    usage_by_model: dict[str, ModelUsage],
    seen_message_ids: set[str],
    assistant_ids: set[str],
    tool_call_ids: set[str],
) -> None:
    """Fold one Claude assistant line into the running aggregates."""
    message = entry.get("message", {})
    model = message.get("model")
    is_real = model != "<synthetic>" and not entry.get("isApiErrorMessage")

    for block in _content_blocks(message.get("content")):
        if block.get("type") == "tool_use" and block.get("id"):
            tool_call_ids.add(block["id"])

    if not is_real:
        return

    message_id = message.get("id")
    if message_id:
        assistant_ids.add(message_id)
        if message_id in seen_message_ids:
            return
        seen_message_ids.add(message_id)

    usage = message.get("usage") or {}
    usage_by_model.setdefault(model, ModelUsage()).add(
        ModelUsage(
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
            usage.get("cache_read_input_tokens", 0),
            usage.get("cache_creation_input_tokens", 0),
            _claude_model_cost(model, usage),
        )
    )


def _count_claude_user_message(entry: dict, tool_result_ids: set[str]) -> bool:
    """Record tool-result ids and report whether this is a real human message."""
    message = entry.get("message", {})
    for block in _content_blocks(message.get("content")):
        if block.get("type") == "tool_result" and block.get("tool_use_id"):
            tool_result_ids.add(block["tool_use_id"])

    if entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    return _has_visible_text(message.get("content"))


def _claude_api_duration(entries: list[dict]) -> timedelta | None:
    """Sum Claude `turn_duration` system entries; None when none are present.

    These per-turn generation times are the only in-band API-duration signal and
    are emitted only by recent CLI versions, so the field is omitted when absent
    rather than inferred from timestamp gaps.
    """
    total_ms = 0
    found = False
    for entry in entries:
        if entry.get("type") == "system" and entry.get("subtype") == "turn_duration":
            total_ms += entry.get("durationMs", 0)
            found = True
    return timedelta(milliseconds=total_ms) if found else None


def _aggregate_pi(entries: list[dict]) -> dict[str, object]:
    """Aggregate token usage, cost, and message counts from PI entries.

    PI writes one entry per message and stores a fully broken-down `usage.cost`
    on every assistant message, so cost is summed directly with no pricing table.
    """
    usage_by_model: dict[str, ModelUsage] = {}
    user_messages = 0
    assistant_messages = 0
    tool_calls = 0
    tool_results = 0
    reported_total_tokens = 0

    for entry in entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message", {})
        role = message.get("role")

        if role == "user":
            user_messages += 1
        elif role == "assistant":
            assistant_messages += 1
            tool_calls += _pi_assistant_tool_calls(message)
            _accumulate_pi_assistant(message, usage_by_model)
            reported_total_tokens += (message.get("usage") or {}).get("totalTokens", 0)
        elif role == "toolResult":
            tool_results += 1

    return {
        "usage_by_model": usage_by_model,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "api_duration": None,
        "reported_total_tokens": reported_total_tokens,
    }


def _pi_assistant_tool_calls(message: dict) -> int:
    """Count `toolCall` blocks inside a PI assistant message's content."""
    return sum(
        1
        for block in _content_blocks(message.get("content"))
        if block.get("type") == "toolCall"
    )


def _accumulate_pi_assistant(
    message: dict, usage_by_model: dict[str, ModelUsage]
) -> None:
    """Fold one PI assistant message's stored usage and cost into the aggregates."""
    usage = message.get("usage") or {}
    model = message.get("model") or "unknown"
    cost = usage.get("cost") or {}
    usage_by_model.setdefault(model, ModelUsage()).add(
        ModelUsage(
            usage.get("input", 0),
            usage.get("output", 0),
            usage.get("cacheRead", 0),
            usage.get("cacheWrite", 0),
            cost.get("total", 0.0),
        )
    )


def _content_blocks(content: object) -> list[dict]:
    """Return the dict blocks of a message content field, ignoring strings."""
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _has_visible_text(content: object) -> bool:
    """Whether a user message carries real text rather than only tool results."""
    if isinstance(content, str):
        return bool(content.strip())
    for block in _content_blocks(content):
        if block.get("type") == "text" and block.get("text", "").strip():
            return True
    return False


def build_session_info(path: Path) -> SessionInfo:
    """Read a Claude or PI session file and aggregate its statistics."""
    provider = get_jsonl_session_adapter(path).name
    if provider not in SUPPORTED_INFO_PROVIDERS:
        raise ValueError(
            f"`info` supports {' and '.join(SUPPORTED_INFO_PROVIDERS)} sessions; "
            f"{path.name} is a {provider} session."
        )

    content = path.read_text(encoding="utf-8")
    entries = decode_jsonl_entries(content)
    aggregate = _aggregate_claude(entries) if provider == "claude" else _aggregate_pi(entries)

    first = get_jsonl_first_timestamp(path)
    last = get_jsonl_last_timestamp(path)
    wall_duration = last - first if first is not None and last is not None else None

    return SessionInfo(
        name=extract_latest_custom_title_from_content(content),
        path=path,
        session_id=get_display_session_id(path),
        provider=provider,
        wall_duration=wall_duration,
        api_duration=aggregate["api_duration"],
        usage_by_model=aggregate["usage_by_model"],
        user_messages=aggregate["user_messages"],
        assistant_messages=aggregate["assistant_messages"],
        tool_calls=aggregate["tool_calls"],
        tool_results=aggregate["tool_results"],
        reported_total_tokens=aggregate["reported_total_tokens"],
    )


def _humanize_tokens(count: int) -> str:
    """Render a token count with a k/m suffix.

    >>> [_humanize_tokens(n) for n in (842, 3300, 2255360)]
    ['842', '3.3k', '2.3m']
    """
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}m"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def _humanize_duration(duration: timedelta) -> str:
    """Render a duration as compact `Xh Ym Zs`, dropping leading zero units.

    >>> _humanize_duration(timedelta(seconds=1766))
    '29m 26s'
    >>> _humanize_duration(timedelta(seconds=45))
    '45s'
    >>> _humanize_duration(timedelta(seconds=3723))
    '1h 02m 03s'
    """
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _model_usage_line(model: str, usage: ModelUsage) -> str:
    """Render one `Usage by model` line for a model."""
    return (
        f"    {model}:  "
        f"{_humanize_tokens(usage.input_tokens)} input, "
        f"{_humanize_tokens(usage.output_tokens)} output, "
        f"{_humanize_tokens(usage.cache_read_tokens)} cache read, "
        f"{_humanize_tokens(usage.cache_write_tokens)} cache write "
        f"(${usage.cost:.2f})"
    )


def render_session_info(info: SessionInfo) -> str:
    """Render a SessionInfo as the plain-text report block."""
    totals = info.totals
    lines = [
        "Session Info",
        "",
        f" Name: {info.name or '(untitled)'}",
        f" File: {info.path}",
        f" ID: {info.session_id}",
    ]
    if info.api_duration is not None:
        lines.append(f" Total duration (API):  {_humanize_duration(info.api_duration)}")
    if info.wall_duration is not None:
        lines.append(f" Total duration (wall): {_humanize_duration(info.wall_duration)}")

    lines.append(" Usage by model:")
    for model in sorted(info.usage_by_model):
        lines.append(_model_usage_line(model, info.usage_by_model[model]))

    lines += [
        "",
        "Messages",
        f" User: {info.user_messages}",
        f" Assistant: {info.assistant_messages}",
        f" Tool Calls: {info.tool_calls}",
        f" Tool Results: {info.tool_results}",
        f" Total: {info.total_messages}",
        "",
        "Tokens",
        f" Input: {totals.input_tokens:,}",
        f" Output: {totals.output_tokens:,}",
        f" Cache Read: {totals.cache_read_tokens:,}",
        f" Cache Write: {totals.cache_write_tokens:,}",
        f" Total: {info.total_tokens:,}",
        "",
        "Cost",
        f" Total: {totals.cost:.4f}",
    ]
    return "\n".join(lines)


def cmd_info(session: str) -> None:
    """Resolve a session identifier and print its aggregated statistics."""
    path = resolve.resolve_conversation_file(session)
    try:
        info = build_session_info(path)
    except ValueError as error:
        print_error(str(error))
        sys.exit(1)
    get_console().print(render_session_info(info), soft_wrap=True)
