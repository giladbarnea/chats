#!/usr/bin/env python3
"""Claude's tools for talking to agents are agent content, not ordinary tools.

`SendMessage` (to a teammate or subagent) and `ListAgents` show with `--agents`,
regardless of tool filters, and never with `--tools` alone. Pi's `team_*` tools
follow the same rule.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from chats import ConversationFlags, parse_jsonl
from chats.formatting import format_to_xml
from chats.tool_filter import parse_tool_spec

CLAUDE_SOURCE_PATH = Path.home() / ".claude" / "projects" / "tests" / "session.jsonl"
CH_EXECUTABLE = Path(sys.executable).with_name("ch")
SESSION_ID = "44444444-4444-4444-8444-444444444444"


def _conversation() -> str:
    entries = [
        {"type": "user", "timestamp": "2026-10-14T13:00:00Z", "message": {"role": "user", "content": "ask scout"}},
        {
            "type": "assistant",
            "timestamp": "2026-10-14T13:00:01Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "ASSISTANT_TEXT_MARKER"},
                    {
                        "type": "tool_use",
                        "id": "toolu_send1",
                        "name": "SendMessage",
                        "input": {"to": "scout", "summary": "ask", "message": "SEND_BODY_MARKER"},
                    },
                    {"type": "tool_use", "id": "toolu_bash1", "name": "Bash", "input": {"command": "BASH_MARKER"}},
                ],
            },
        },
        {
            "type": "user",
            "timestamp": "2026-10-14T13:00:02Z",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_send1", "content": "SEND_RESULT_MARKER"},
                    {"type": "tool_result", "tool_use_id": "toolu_bash1", "content": "BASH_RESULT_MARKER"},
                ],
            },
        },
    ]
    return "\n".join(json.dumps(entry) for entry in entries)


def _render(**flag_values) -> str:
    flags = ConversationFlags(color="never", **flag_values)
    return format_to_xml(parse_jsonl(_conversation(), flags, source_path=CLAUDE_SOURCE_PATH), flags)


def test_default_view_hides_agent_messaging():
    output = _render()
    assert "SEND_BODY_MARKER" not in output and "ASSISTANT_TEXT_MARKER" in output, output


def test_tools_alone_do_not_show_agent_messaging():
    output = _render(show_tools=True)
    assert "BASH_MARKER" in output and "BASH_RESULT_MARKER" in output, output
    assert "SEND_BODY_MARKER" not in output and "SEND_RESULT_MARKER" not in output, (
        f"Expected SendMessage to stay hidden under --tools alone. Got:\n{output}"
    )


def test_agents_show_agent_messaging_regardless_of_tool_filters():
    output = _render(show_agents=True, show_tools=[parse_tool_spec("Bash")])
    assert "SEND_BODY_MARKER" in output and "SEND_RESULT_MARKER" in output, (
        f"Expected SendMessage and its result under --agents. Got:\n{output}"
    )


def _search(home: Path, *arguments: str) -> str:
    return subprocess.run(
        [str(CH_EXECUTABLE), "search", *arguments, "--only-id"],
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def test_search_treats_agent_messaging_as_agent_content(tmp_path: Path):
    home = tmp_path / "home"
    path = home / ".claude" / "projects" / "-Users-tester-project" / f"{SESSION_ID}.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(_conversation() + "\n", encoding="utf-8")

    assert _search(home, "ASSISTANT_TEXT_MARKER") == SESSION_ID, "Expected the fixture to be searchable."
    assert _search(home, "SEND_BODY_MARKER") == "", "Expected no default match on agent messaging."
    assert _search(home, "SEND_BODY_MARKER", "--tools") == "", "Expected no --tools match on agent messaging."
    assert _search(home, "SEND_BODY_MARKER", "--agents") == SESSION_ID, "Expected an --agents match."
    assert _search(home, "SEND_RESULT_MARKER", "--agents") == SESSION_ID, "Expected an --agents result match."
