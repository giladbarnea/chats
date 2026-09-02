#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Synthesize the Codex shapes the real corpus does not contain, and prove each one bites.

Measured over all 1,208 Codex sessions, two shapes this decoder handles occur **zero**
times:

    assistant `message` payloads with more than one visible text block :  0
    `reasoning` summaries carrying an item that is not `summary_text`  :  0

So a mutation breaking either join catches nothing, and a corpus of any size would be as
blind. That is `session-core`'s Pi `<duration_ms>` result in two more places: 477 of 477
envelopes carried the terminator their code wrongly required, so the corpus could not see
the defect.

Each fixture below is **validated against Python**, not against the port: the script
asserts that Python itself produces the behaviour the fixture is named for. A fixture that
does not reach its own behaviour is malformed, and landing it would create a test that
passes for the wrong reason.

Usage:  uv run make_codex_fixtures.py [output-dir]
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "src"))

from chats.model import ConversationFlags  # noqa: E402
from chats.parsing import _iter_jsonl_entries, _parse_codex_jsonl_entries  # noqa: E402


def header() -> dict:
    """Codex's native session header: `type == "session_meta"` is the whole test."""
    return {
        "type": "session_meta",
        "payload": {"id": "fixture", "cwd": "/tmp/fixture"},
        "timestamp": "2026-07-01T10:00:00.000Z",
    }


def response_item(payload: dict, hour: int) -> dict:
    return {
        "type": "response_item",
        "payload": payload,
        "timestamp": f"2026-07-01T{hour:02d}:00:00.000Z",
    }


def assistant_two_blocks() -> dict:
    return response_item(
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "output_text", "text": "FIRST BLOCK"},
                {"type": "output_text", "text": "SECOND BLOCK"},
            ],
        },
        hour=10,
    )


def reasoning_mixed_summary() -> dict:
    """A reasoning summary whose items are not all `summary_text`.

    Python reads only `summary_text`. A decoder that reads every item would fold the
    other one in, and nothing in the corpus would ever show it.
    """
    return response_item(
        {
            "type": "reasoning",
            "summary": [
                {"type": "summary_text", "text": "KEPT REASONING"},
                {"type": "reasoning_text", "text": "DROPPED REASONING"},
            ],
        },
        hour=11,
    )


def user_two_blocks() -> dict:
    """Two visible user blocks, joined with a blank line. 94 in the corpus, so this
    one is a control: it proves the fixture route agrees with the corpus route."""
    return response_item(
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": "USER ONE"},
                {"type": "input_text", "text": "USER TWO"},
            ],
        },
        hour=9,
    )


FIXTURES: dict[str, tuple[str, list[dict], ConversationFlags, str]] = {
    "assistant-two-text-blocks": (
        "two assistant blocks joined by a blank line — 0 occurrences in the corpus",
        [header(), assistant_two_blocks()],
        ConversationFlags(),
        "FIRST BLOCK\n\nSECOND BLOCK",
    ),
    "reasoning-mixed-summary-items": (
        "a reasoning summary mixing summary_text with another type — 0 in the corpus",
        [header(), reasoning_mixed_summary()],
        ConversationFlags(show_thinking=True),
        "KEPT REASONING",
    ),
    "user-two-text-blocks": (
        "two visible user blocks joined by a blank line — control, 94 in the corpus",
        [header(), user_two_blocks()],
        ConversationFlags(),
        "USER ONE\n\nUSER TWO",
    ),
}


def rendered_fields(messages) -> str:
    """Everything a fixture might assert against, flattened."""
    parts = []
    for message in messages:
        parts.append(message.text or "")
        parts.append(message.thinking or "")
    return "\n".join(parts)


def main() -> int:
    out_dir = (
        pathlib.Path(sys.argv[1])
        if len(sys.argv) > 1
        else pathlib.Path(__file__).resolve().parents[1] / "session-core" / "codex-fixtures"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0

    for name, (description, entries, flags, expected) in FIXTURES.items():
        content = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        (out_dir / f"{name}.jsonl").write_text(content, encoding="utf-8")

        messages = _parse_codex_jsonl_entries(_iter_jsonl_entries(content), flags)
        produced = rendered_fields(messages)
        reaches = expected in produced
        if not reaches:
            failures += 1
        print(f"[{'OK ' if reaches else 'FAIL'}] {name}: {description}")
        print(f"        python yields {len(messages)} message(s); expected {expected!r}")
        if not reaches:
            print(f"        got: {produced!r}")

    # A fixture asserting the dropped half is absent, which the positive assertion
    # above cannot express: `KEPT REASONING` being present says nothing about
    # `DROPPED REASONING` also being present.
    content = (out_dir / "reasoning-mixed-summary-items.jsonl").read_text(encoding="utf-8")
    messages = _parse_codex_jsonl_entries(
        _iter_jsonl_entries(content), ConversationFlags(show_thinking=True)
    )
    leaked = "DROPPED REASONING" in rendered_fields(messages)
    if leaked:
        failures += 1
    print(
        f"[{'FAIL' if leaked else 'OK '}] reasoning-mixed-summary-items: "
        "the non-summary_text item must NOT appear"
    )

    print(f"\nwrote {len(FIXTURES)} fixture session(s) to {out_dir}")
    if failures:
        print(f"{failures} check(s) failed — the fixtures are malformed. Do not land them.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
