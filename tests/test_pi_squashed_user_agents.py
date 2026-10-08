#!/usr/bin/env python3
"""A squashed Pi `pi-user-agents` result is a plain user message.

When the user squashes a background agent, the pi-user-agents extension sends
the main agent one `custom_message` (`customType: "pi-user-agents"`,
`details.mainContextState: "squashed"`) whose `content` is the text the main
agent reads. `ch` shows that `content` as it is, as a user message, by default,
whatever `display` says and whether the agent succeeded or failed.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chats import ConversationFlags, parse_jsonl as _parse_jsonl
from chats.formatting import format_to_xml

PI_SOURCE_PATH = Path.home() / ".pi" / "agent" / "sessions" / "project" / "session.jsonl"
SESSION_ID = "01a115bc-0000-7000-8000-000000000002"

SQUASHED_SUCCESS_CONTENT = "\n".join([
    "The user has dispatched a background sub-agent with a task. The sub-agent is done. The following is the back and forth between them:",
    '<user_agent model="provider/model" inherited_context="true">',
    "  <user_message i=1>",
    "  review the migration",
    "  </user_message>",
    "  <assistant_response i=2>",
    "  SQUASHED_SUCCESS_MARKER",
    "  </assistant_response>",
    "</user_agent>",
])
SQUASHED_FAILURE_CONTENT = "\n".join([
    '<user_agent_error command="/agent" model="provider/model" inherited_context="true">',
    "<user_invocation>",
    "/agent review the migration",
    "</user_invocation>",
    "<task>",
    "review the migration",
    "</task>",
    "<error>",
    "SQUASHED_FAILURE_MARKER",
    "</error>",
    "<duration_ms>",
    "1200",
    "</duration_ms>",
    "</user_agent_error>",
])


def _squashed(entry_id: str, content: str, *, ok: bool, display: bool) -> dict:
    return {
        "type": "custom_message",
        "id": entry_id,
        "timestamp": "2026-10-07T11:04:16.706Z",
        "customType": "pi-user-agents",
        "content": content,
        "display": display,
        "details": {
            "agentId": f"agent-{entry_id}",
            "command": "agent",
            "mainContextState": "squashed",
            "inheritedContext": True,
            "model": "provider/model",
            "task": "review the migration",
            "ok": ok,
            **({"responseText": "SQUASHED_SUCCESS_MARKER"} if ok else {"error": "SQUASHED_FAILURE_MARKER"}),
        },
    }


SESSION_ENTRIES = [
    {"type": "session", "version": 3, "id": SESSION_ID, "timestamp": "2026-10-07T11:00:00.000Z", "cwd": "/tmp/project"},
    {
        "type": "message",
        "id": "u1",
        "timestamp": "2026-10-07T11:01:00.000Z",
        "message": {"role": "user", "content": [{"type": "text", "text": "typed by the human"}]},
    },
    _squashed("s1", SQUASHED_SUCCESS_CONTENT, ok=True, display=False),
    _squashed("s2", SQUASHED_FAILURE_CONTENT, ok=False, display=True),
]
CONVERSATION = "\n".join(json.dumps(entry) for entry in SESSION_ENTRIES)


@pytest.mark.parametrize("flag_values", [{}, {"show_agents": True}], ids=["default", "agents"])
def test_squashed_results_render_as_plain_user_messages(flag_values: dict):
    flags = ConversationFlags(color="never", **flag_values)
    output = format_to_xml(_parse_jsonl(CONVERSATION, flags, source_path=PI_SOURCE_PATH), flags)

    for index, content in ((2, SQUASHED_SUCCESS_CONTENT), (3, SQUASHED_FAILURE_CONTENT)):
        expected = f'<user-message i="{index}" date="2026-10-07 14:04">\n## User\n\n{content}\n</user-message>'
        assert expected in output, (
            f"Expected squashed record {index} as a plain user message with its content as it is. "
            f"Expected block:\n{expected}\nGot:\n{output}"
        )
    assert "<agent" not in output, f"Expected no agent block for squashed results. Got:\n{output}"


CH_EXECUTABLE = Path(sys.executable).with_name("ch")


def test_search_finds_squashed_content_by_default(tmp_path: Path):
    home = tmp_path / "home"
    session_path = home / ".pi" / "agent" / "sessions" / "--tmp-project--" / f"2026-10-07T11-00-00-000Z_{SESSION_ID}.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(CONVERSATION + "\n", encoding="utf-8")

    for marker in ("typed by the human", "SQUASHED_SUCCESS_MARKER", "SQUASHED_FAILURE_MARKER", "back and forth between them"):
        result = subprocess.run(
            [str(CH_EXECUTABLE), "search", marker, "--only-id"],
            env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip() == SESSION_ID, (
            f"Expected default search to find {marker!r} in the squashed session. "
            f"stdout: {result.stdout!r}; stderr: {result.stderr!r}."
        )
