"""Author Pi sessions for shapes the real corpus does not contain, and prove they discriminate.

Measured: all 477 joined user-agent envelopes in the corpus carry `<duration_ms>`.
Python's grammar makes it optional, and the prior native port required it — so joined
responses vanished from output through a green suite and an independent review, because
no fixture had the shape. 24,367 green differential cases cannot see that defect.

These fixtures exist so it cannot happen twice.

Run from the repo root:
  uv run python thoughts/.../probes/make_pi_fixtures.py [out_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chats.model import ConversationFlags
from chats.parsing import _parse_pi_jsonl_entries, _iter_jsonl_entries

STAMP = "2026-08-20T{:02d}:00:00.000Z"


def header(version: int = 3) -> dict:
    return {"type": "session", "version": version, "id": "fixture-session"}


def envelope(task: str, response: str, *, duration: bool) -> str:
    tail = (
        "\n<duration_ms>\n1234\n</duration_ms>" if duration else ""
    )
    return (
        "<user_agent>\n<user_invocation>\n"
        f"/agent {task}\n</user_invocation>\n"
        f"<task>\n{task}\n</task>\n"
        f"<response>\n{response}\n</response>"
        f"{tail}\n</user_agent>"
    )


def joined_user_agent(entry_id: str, task: str, response: str, *, duration: bool, hour: int) -> dict:
    return {
        "type": "custom_message",
        "customType": "pi-user-agents",
        "id": entry_id,
        "timestamp": STAMP.format(hour),
        "content": envelope(task, response, duration=duration),
        "details": {
            "task": task,
            "ok": True,
            "mainContextState": "joined",
            "responsePreview": response.split("\n")[0],
        },
    }


def ambiguous_envelope(task: str) -> str:
    """Two producer boundaries for one task, so the candidate set has two members."""
    return (
        "<user_agent>\n<user_invocation>\n"
        f"/agent {task}\n</user_invocation>\n"
        f"<task>\n{task}\n</task>\n"
        # Both candidates open with the SAME first line, so a preview equal to that
        # line matches both. That is what reaches the multiple-match check. An earlier
        # draft omitted the preview entirely, which short-circuits before the check and
        # left the mutation catching nothing.
        "<response>\nshared opening line\nalpha tail\n</response>\n</user_invocation>\n"
        f"<task>\n{task}\n</task>\n"
        "<response>\nshared opening line\nbeta tail\n</response>\n</user_agent>"
    )


def ambiguous_user_agent(entry_id: str, task: str, hour: int) -> dict:
    # responsePreview matches BOTH candidates, so resolution reaches the
    # multiple-match check and Python declines rather than guessing.
    return {
        "type": "custom_message",
        "customType": "pi-user-agents",
        "id": entry_id,
        "timestamp": STAMP.format(hour),
        "content": ambiguous_envelope(task),
        "details": {
            "task": task,
            "ok": True,
            "mainContextState": "joined",
            "responsePreview": "shared opening line",
        },
    }


FIXTURES: dict[str, tuple[str, list[dict]]] = {
    "user-agent-without-duration": (
        "joined user-agent envelope with NO <duration_ms> — the shape the corpus never has",
        [header(), joined_user_agent("ua-1", "summarise the file", "the summary text", duration=False, hour=10)],
    ),
    "user-agent-with-duration": (
        "the same envelope carrying <duration_ms> — CONTROL, this shape is all 477 in the corpus",
        [header(), joined_user_agent("ua-2", "summarise the file", "the summary text", duration=True, hour=11)],
    ),
    "user-agent-ambiguous": (
        "two candidates the preview matches equally — Python DECLINES, yielding no message",
        [header(), ambiguous_user_agent("ua-3", "summarise the file", 12)],
    ),
}

# What Python must produce from each. The fixture is validated against the oracle,
# never against the port — that is what makes it evidence rather than an assertion.
EXPECTED_MESSAGES = {
    "user-agent-without-duration": 1,
    "user-agent-with-duration": 1,
    "user-agent-ambiguous": 0,
}


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pi-fixtures")
    out_dir.mkdir(parents=True, exist_ok=True)
    flags = ConversationFlags(show_agents=True)
    failures = 0

    for name, (description, entries) in FIXTURES.items():
        content = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        (out_dir / f"{name}.jsonl").write_text(content, encoding="utf-8")

        messages = _parse_pi_jsonl_entries(_iter_jsonl_entries(content), flags)
        # The point of the fixture is that the response survives. If Python itself
        # yields nothing here, the fixture is malformed, not the port.
        texts = [message.text for message in messages]
        expected = EXPECTED_MESSAGES[name]
        reaches = len(messages) == expected and (
            expected == 0 or any("candidate" not in text for text in texts)
        )
        status = "OK " if reaches else "FAIL"
        if not reaches:
            failures += 1
        print(f"[{status}] {name}: {description}")
        print(f"        python yields {len(messages)} message(s) (expected {expected}), texts={texts}")

    print(f"\nwrote {len(FIXTURES)} sessions to {out_dir}")
    if failures:
        print(f"{failures} fixture(s) do not reach the behaviour they name — do not land these")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
