#!/usr/bin/env python3
"""Pi `pi-simple-team` delegation is agent content, not tool content.

The pi-simple-team extension delegates through `team_*` tools (`team_spawn`,
`team_send_message`, `team_status`, ...) and delivers each teammate's reply as a
`custom_message` with `customType: "pi-simple-team"`. Both belong to `--agents`:
hidden by default, shown with `--agents` whether or not `--tools` is set, and
never shown by `--tools` alone.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from chats import ConversationFlags, parse_jsonl as _parse_jsonl
from chats.formatting import format_to_xml
from chats.tool_filter import parse_tool_spec

PI_SOURCE_PATH = Path.home() / ".pi" / "agent" / "sessions" / "project" / "session.jsonl"
SESSION_ID = "01a11a97-0000-7000-8000-000000000001"

SESSION_ENTRIES = [
    {"type": "session", "version": 3, "id": SESSION_ID, "timestamp": "2026-10-08T08:18:34.686Z", "cwd": "/tmp/project"},
    {
        "type": "message",
        "id": "u1",
        "timestamp": "2026-10-08T08:19:00.000Z",
        "message": {"role": "user", "content": [{"type": "text", "text": "typed by the human"}]},
    },
    {
        "type": "message",
        "id": "a1",
        "timestamp": "2026-10-08T08:20:00.000Z",
        "message": {
            "role": "assistant",
            "model": "gpt-test",
            "content": [
                {"type": "text", "text": "assistant reply"},
                {
                    "type": "toolCall",
                    "id": "call-team",
                    "name": "team_send_message",
                    "arguments": {"to": "scout", "message": "OUTGOING_TEAM_MARKER"},
                },
                {"type": "toolCall", "id": "call-zsh", "name": "zsh", "arguments": {"command": "ZSH_INPUT_MARKER"}},
            ],
        },
    },
    {
        "type": "message",
        "id": "r1",
        "timestamp": "2026-10-08T08:20:01.000Z",
        "message": {
            "role": "toolResult",
            "toolCallId": "call-team",
            "toolName": "team_send_message",
            "content": [{"type": "text", "text": "TEAM_RESULT_MARKER"}],
        },
    },
    {
        "type": "message",
        "id": "r2",
        "timestamp": "2026-10-08T08:20:02.000Z",
        "message": {
            "role": "toolResult",
            "toolCallId": "call-zsh",
            "toolName": "zsh",
            "content": [{"type": "text", "text": "ZSH_RESULT_MARKER"}],
        },
    },
    {
        "type": "custom_message",
        "id": "c1",
        "timestamp": "2026-10-08T08:21:00.000Z",
        "customType": "pi-simple-team",
        "content": "[research/scout] INBOUND_TEAM_MARKER",
        "display": True,
        "details": {"team": "research", "from": "scout", "sentAt": "2026-10-08T08:20:59.000Z", "message": "INBOUND_TEAM_MARKER"},
    },
]
CONVERSATION = "\n".join(json.dumps(entry) for entry in SESSION_ENTRIES)

TEAM_MARKERS = ("OUTGOING_TEAM_MARKER", "TEAM_RESULT_MARKER", "INBOUND_TEAM_MARKER")
TOOL_MARKERS = ("ZSH_INPUT_MARKER", "ZSH_RESULT_MARKER")


def _render(**flag_values: object) -> str:
    flags = ConversationFlags(color="never", **flag_values)
    return format_to_xml(_parse_jsonl(CONVERSATION, flags, source_path=PI_SOURCE_PATH), flags)


def test_team_content_is_hidden_by_default():
    output = _render()
    for marker in TEAM_MARKERS:
        assert marker not in output, f"Expected {marker} hidden without --agents. Got:\n{output}"
    assert "typed by the human" in output and "assistant reply" in output, (
        f"Expected the regular conversation untouched. Got:\n{output}"
    )


def test_tools_alone_shows_tools_but_not_team_content():
    output = _render(show_tools=True)
    for marker in TOOL_MARKERS:
        assert marker in output, f"Expected ordinary tool {marker} under --tools. Got:\n{output}"
    for marker in TEAM_MARKERS:
        assert marker not in output, f"Expected {marker} hidden under --tools without --agents. Got:\n{output}"


def test_agents_alone_shows_team_content_without_other_tools():
    output = _render(show_agents=True)
    for marker in TEAM_MARKERS:
        assert marker in output, f"Expected {marker} under --agents without --tools. Got:\n{output}"
    for marker in TOOL_MARKERS:
        assert marker not in output, f"Expected ordinary tool {marker} hidden without --tools. Got:\n{output}"


def test_inbound_team_message_is_an_agent_named_after_its_sender():
    output = _render(show_agents=True)
    assert 'agent_id="scout" name="scout"' in output and "## Agent 'scout'" in output, (
        f"Expected the teammate reply rendered as an agent attributed to 'scout'. Got:\n{output}"
    )
    assert "[research/scout]" not in output, (
        f"Expected the body from details.message, without the routing prefix. Got:\n{output}"
    )


def test_tool_filters_do_not_hide_team_calls_under_agents():
    """A tool-name filter narrows tools; it does not narrow agent content."""
    output = _render(show_agents=True, show_tools=_tool_filters("zsh"))
    for marker in (*TEAM_MARKERS, *TOOL_MARKERS):
        assert marker in output, f"Expected {marker} with --agents -t zsh. Got:\n{output}"


def _tool_filters(spec: str) -> list:
    return [parse_tool_spec(spec)]


# ── Search path (native launcher) ─────────────────────────────────────────────
#
# `ch search` confirms matches through the Rust parser, so the same claims are
# made once more against the launcher.

CH_EXECUTABLE = Path(sys.executable).with_name("ch")


def _write_pi_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    session_path = home / ".pi" / "agent" / "sessions" / "--tmp-project--" / f"2026-10-08T08-18-34-686Z_{SESSION_ID}.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(CONVERSATION + "\n", encoding="utf-8")
    return home


def _search(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CH_EXECUTABLE), "search", *arguments, "--only-id"],
        cwd=Path(__file__).parent.parent,
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_search_finds_team_content_only_with_agents(tmp_path: Path):
    home = _write_pi_home(tmp_path)
    reachable = _search(home, "typed by the human")
    assert reachable.stdout.strip() == SESSION_ID, (
        f"Expected the fixture home to be searchable. stdout: {reachable.stdout!r}; stderr: {reachable.stderr!r}."
    )
    for marker in TEAM_MARKERS:
        for arguments, expected in (((), ""), (("--tools",), ""), (("--agents",), SESSION_ID)):
            result = _search(home, marker, *arguments)
            assert result.stdout.strip() == expected, (
                f"Expected `search {marker} {' '.join(arguments)}` to print {expected!r}. "
                f"stdout: {result.stdout!r}; stderr: {result.stderr!r}."
            )
    for marker in TOOL_MARKERS:
        result = _search(home, marker, "--agents")
        assert not result.stdout.strip(), (
            f"Expected ordinary tool {marker} unsearchable with --agents alone. stdout: {result.stdout!r}."
        )
