#!/usr/bin/env python3
"""Pi delegation as a reader of `ch` needs it, in parse and in search.

Pi children can copy their parent's history: native `/fork`, `/clone` and `--fork`, a
pi-simple-team `forkContext:true` teammate, and a non-isolated pi-user-agents side chat.
A child's standalone view shows its whole file, copy included. Native forks copy
entries verbatim; pi-user-agents re-appends the snapshot with fresh entry timestamps but
keeps each message's original `message.timestamp`. Either way the copied entries
predate the child's header, which locates the fork point.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from chats import ConversationFlags, parse_jsonl as _parse_jsonl
from chats.formatting import format_to_xml

SESSIONS = Path.home() / ".pi" / "agent" / "sessions" / "--tmp-project--"
PARENT_ID = "30000000-0000-4000-8000-00000000000a"
CHILD_ID = "30000000-0000-4000-8000-00000000000b"
PARENT_FILE = f"2026-10-08T08-00-00-000Z_{PARENT_ID}.jsonl"
CHILD_FILE = f"2026-10-08T09-00-00-000Z_{CHILD_ID}.jsonl"

CH_EXECUTABLE = Path(sys.executable).with_name("ch")


def _milliseconds(iso: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(iso).timestamp() * 1000)


def _text_message(entry_id: str, role: str, text: str, entry_time: str, message_time: str | None = None) -> dict:
    return {
        "type": "message",
        "id": entry_id,
        "timestamp": entry_time,
        "message": {
            "role": role,
            "content": [{"type": "text", "text": text}],
            "timestamp": _milliseconds(message_time or entry_time),
        },
    }


PARENT_ENTRIES = [
    {"type": "session", "version": 3, "id": PARENT_ID, "timestamp": "2026-10-08T08:00:00.000Z", "cwd": "/tmp/project"},
    _text_message("p1", "user", "PARENT_ASK_MARKER", "2026-10-08T08:01:00.000Z"),
    _text_message("p2", "assistant", "PARENT_ANSWER_MARKER", "2026-10-08T08:02:00.000Z"),
]

CHILD_HEADER = {
    "type": "session",
    "version": 3,
    "id": CHILD_ID,
    "timestamp": "2026-10-08T09:00:00.000Z",
    "cwd": "/tmp/project",
    "parentSession": str(SESSIONS / PARENT_FILE),
}
CHILD_OWN_ENTRIES = [
    _text_message("c1", "user", "CHILD_ASK_MARKER", "2026-10-08T09:01:00.000Z"),
    _text_message("c2", "assistant", "CHILD_ANSWER_MARKER", "2026-10-08T09:02:00.000Z"),
]

# Native fork: every parent entry copied verbatim, ids and timestamps included.
NATIVE_FORK_ENTRIES = [CHILD_HEADER, *PARENT_ENTRIES[1:], *CHILD_OWN_ENTRIES]

# pi-user-agents: dispatch record, then the snapshot re-appended at dispatch time.
SIDE_CHAT_ENTRIES = [
    CHILD_HEADER,
    {
        "type": "custom",
        "customType": "pi-user-agents-dispatch",
        "id": "d1",
        "timestamp": "2026-10-08T09:00:00.001Z",
        "data": {"forwardedArgs": [], "task": "CHILD_ASK_MARKER", "isolate": False},
    },
    _text_message("s1", "user", "PARENT_ASK_MARKER", "2026-10-08T09:00:00.010Z", "2026-10-08T08:01:00.000Z"),
    _text_message("s2", "assistant", "PARENT_ANSWER_MARKER", "2026-10-08T09:00:00.011Z", "2026-10-08T08:02:00.000Z"),
    {"type": "model_change", "id": "m1", "timestamp": "2026-10-08T09:00:00.012Z", "provider": "p", "modelId": "m"},
    *CHILD_OWN_ENTRIES,
]

INHERITED_MARKERS = ("PARENT_ASK_MARKER", "PARENT_ANSWER_MARKER")
OWN_MARKERS = ("CHILD_ASK_MARKER", "CHILD_ANSWER_MARKER")


def _jsonl(entries: list[dict]) -> str:
    return "\n".join(json.dumps(entry) for entry in entries)


def _render(entries: list[dict], **flag_values: object) -> str:
    flags = ConversationFlags(color="never", **flag_values)
    return format_to_xml(_parse_jsonl(_jsonl(entries), flags, source_path=SESSIONS / CHILD_FILE), flags)


def test_fork_shows_its_whole_file():
    """A direct fork view retains the copied parent history."""
    for entries in (NATIVE_FORK_ENTRIES, SIDE_CHAT_ENTRIES):
        output = _render(entries)
        for marker in (*INHERITED_MARKERS, *OWN_MARKERS):
            assert marker in output, f"Expected {marker} in the fork's own view. Got:\n{output}"


# ── Search path (native launcher) ─────────────────────────────────────────────


def _write_home(tmp_path: Path, child_entries: list[dict]) -> Path:
    home = tmp_path / "home"
    directory = home / ".pi" / "agent" / "sessions" / "--tmp-project--"
    directory.mkdir(parents=True)
    (directory / PARENT_FILE).write_text(_jsonl(PARENT_ENTRIES) + "\n", encoding="utf-8")
    header = child_entries[0]
    if header.get("parentSession"):
        header = {**header, "parentSession": str(directory / PARENT_FILE)}
    (directory / CHILD_FILE).write_text(_jsonl([header, *child_entries[1:]]) + "\n", encoding="utf-8")
    return home


def _search_ids(home: Path, *arguments: str) -> set[str]:
    result = subprocess.run(
        [str(CH_EXECUTABLE), "search", *arguments, "--only-id"],
        cwd=Path(__file__).parent.parent,
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), f"search failed: {result.stderr!r}"
    return set(result.stdout.split())


def test_search_finds_copied_text_in_parent_and_fork(tmp_path: Path):
    for child_entries in (NATIVE_FORK_ENTRIES, SIDE_CHAT_ENTRIES):
        home = _write_home(tmp_path / child_entries[1]["id"], child_entries)
        for query in (*INHERITED_MARKERS, "."):
            found = _search_ids(home, query)
            assert found == {PARENT_ID, CHILD_ID}, f"Expected parent and fork for {query}. Got {found}."


# ── A teammate's incoming instructions ────────────────────────────────────────
#
# A pi-simple-team teammate receives its briefing and every follow-up from its leader
# as `custom_message` records `from: "main"` addressed `to` it. They are the
# teammate's prompts, as a Claude or Codex child's parent prompt is, so they render
# as user messages by default. Peer messages stay agent content under `--agents`.

TEAMMATE_ID = "30000000-0000-4000-8000-00000000000c"
TEAMMATE_FILE = f"2026-10-08T10-00-00-000Z_{TEAMMATE_ID}.jsonl"


def _team_message(entry_id: str, sender: str, text: str, recipient: str | None, at: str) -> dict:
    details = {"team": "crew", "from": sender, "sentAt": at, "message": text}
    if recipient:
        details["to"] = recipient
    return {
        "type": "custom_message",
        "customType": "pi-simple-team",
        "id": entry_id,
        "timestamp": at,
        "display": True,
        "content": f"[from {sender} on team crew]\n{text}",
        "details": details,
    }


TEAMMATE_ENTRIES = [
    {"type": "session", "version": 3, "id": TEAMMATE_ID, "timestamp": "2026-10-08T10:00:00.000Z", "cwd": "/tmp/project"},
    _team_message("b1", "main", "LEADER_BRIEFING_MARKER", "scout", "2026-10-08T10:00:01.000Z"),
    _text_message("t1", "assistant", "TEAMMATE_REPLY_MARKER", "2026-10-08T10:01:00.000Z"),
    _team_message("b2", "reviewer", "PEER_NOTE_MARKER", "scout", "2026-10-08T10:02:00.000Z"),
    _team_message("b3", "main", "LEADER_FOLLOWUP_MARKER", "scout", "2026-10-08T10:03:00.000Z"),
]


def test_teammate_shows_its_leaders_messages_as_user_messages():
    output = _render(TEAMMATE_ENTRIES)
    for marker in ("LEADER_BRIEFING_MARKER", "LEADER_FOLLOWUP_MARKER"):
        assert f"## User\n\n{marker}" in output, f"Expected {marker} as a default user message. Got:\n{output}"
    assert "[from main" not in output, f"Expected the body without the routing prefix. Got:\n{output}"
    assert "PEER_NOTE_MARKER" not in output, f"Expected peer traffic hidden without --agents. Got:\n{output}"


def test_teammate_peer_messages_stay_agents():
    output = _render(TEAMMATE_ENTRIES, show_agents=True)
    assert "## Agent 'reviewer'\n\n  PEER_NOTE_MARKER" in output, f"Expected the peer note as an agent. Got:\n{output}"
    assert "Agent 'main'" not in output, f"Expected leader messages as user, not agent. Got:\n{output}"


def test_search_finds_leader_messages_by_default(tmp_path: Path):
    home = tmp_path / "home"
    directory = home / ".pi" / "agent" / "sessions" / "--tmp-project--"
    directory.mkdir(parents=True)
    (directory / TEAMMATE_FILE).write_text(_jsonl(TEAMMATE_ENTRIES) + "\n", encoding="utf-8")
    for arguments, expected in (
        (("LEADER_FOLLOWUP_MARKER",), {TEAMMATE_ID}),
        (("LEADER_FOLLOWUP_MARKER", "--only-assistant"), set()),
        (("PEER_NOTE_MARKER",), set()),
        (("PEER_NOTE_MARKER", "--agents"), {TEAMMATE_ID}),
    ):
        found = _search_ids(home, *arguments)
        assert found == expected, f"Expected `search {' '.join(arguments)}` -> {expected}. Got {found}."


# ── Lineage metadata ──────────────────────────────────────────────────────────
#
# The child's own file proves its lineage: `forked_from` names the session whose
# history it copied, `forked_at` when that copy ends in the parent's timeline, and
# `parent_session` the session that spawned it (a side-chat dispatch or a team
# leader's briefing). A native /fork has no spawner.

ISOLATED_SIDE_CHAT_ENTRIES = [
    CHILD_HEADER,
    {**SIDE_CHAT_ENTRIES[1], "data": {"forwardedArgs": [], "task": "CHILD_ASK_MARKER", "isolate": True}},
    *CHILD_OWN_ENTRIES,
]
TEAM_FORK_ENTRIES = [
    CHILD_HEADER,
    *PARENT_ENTRIES[1:],
    _team_message("b1", "main", "LEADER_BRIEFING_MARKER", "scout", "2026-10-08T09:00:01.000Z"),
    *CHILD_OWN_ENTRIES,
]
# The parent's last message, 08:02Z, in Asia/Jerusalem.
FORKED_AT = 'forked_at: "2026-10-08 11:02"'


def _lineage_lines(output: str) -> set[str]:
    return {line for line in output.splitlines() if line.split(":")[0] in {"parent_session", "forked_from", "forked_at"}}


def _metadata_outputs(tmp_path: Path, child_entries: list[dict]) -> tuple[set[str], set[str]]:
    """The child's lineage lines from parse `-l` and from `search -l`."""
    home = _write_home(tmp_path, child_entries)
    environment = {**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"}
    parse = subprocess.run(
        [str(CH_EXECUTABLE), CHILD_ID, "-l", "--color", "never"],
        env=environment, capture_output=True, text=True, check=False,
    )
    search = subprocess.run(
        [str(CH_EXECUTABLE), "search", "-l", "CHILD_ANSWER_MARKER", "--color", "never"],
        env=environment, capture_output=True, text=True, check=False,
    )
    return _lineage_lines(parse.stdout + parse.stderr), _lineage_lines(search.stdout)


def test_lineage_metadata_per_creation_path(tmp_path: Path):
    parent = f"parent_session: {PARENT_ID}"
    forked = f"forked_from: {PARENT_ID}"
    for name, entries, expected in (
        ("native fork", NATIVE_FORK_ENTRIES, {forked, FORKED_AT}),
        ("side chat", SIDE_CHAT_ENTRIES, {parent, forked, FORKED_AT}),
        ("isolated side chat", ISOLATED_SIDE_CHAT_ENTRIES, {parent}),
        ("team fork", TEAM_FORK_ENTRIES, {parent, forked, FORKED_AT}),
        ("no parent", [{**CHILD_HEADER, "parentSession": None}, *CHILD_OWN_ENTRIES], set()),
    ):
        parse_lines, search_lines = _metadata_outputs(tmp_path / name.replace(" ", "-"), entries)
        assert parse_lines == expected, f"{name}: expected parse metadata {expected}. Got {parse_lines}."
        assert search_lines == expected, f"{name}: expected search metadata {expected}. Got {search_lines}."


# ── pi-simple-team tools without the `team_` prefix ───────────────────────────


def _tool_call_entries(name: str, argument: str, result: str) -> list[dict]:
    return [
        {
            "type": "message",
            "id": f"{name}-call",
            "timestamp": "2026-10-08T10:04:00.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "toolCall", "id": f"{name}-id", "name": name, "arguments": {"message": argument}}],
            },
        },
        {
            "type": "message",
            "id": f"{name}-result",
            "timestamp": "2026-10-08T10:04:01.000Z",
            "message": {
                "role": "toolResult",
                "toolCallId": f"{name}-id",
                "toolName": name,
                "content": [{"type": "text", "text": result}],
            },
        },
    ]


def test_every_pi_simple_team_tool_is_agent_content():
    for name in ("send_main_message", "get_context_window_usage"):
        entries = [TEAMMATE_ENTRIES[0], *_tool_call_entries(name, "TOOL_ARGUMENT_MARKER", "TOOL_RESULT_MARKER")]
        for flags, visible in (({}, False), ({"show_tools": True}, False), ({"show_agents": True}, True)):
            output = _render(entries, **flags)
            for marker in ("TOOL_ARGUMENT_MARKER", "TOOL_RESULT_MARKER"):
                assert (marker in output) is visible, f"{name} {flags}: expected {marker} visible={visible}. Got:\n{output}"


def test_search_finds_send_main_message_only_with_agents(tmp_path: Path):
    home = tmp_path / "home"
    directory = home / ".pi" / "agent" / "sessions" / "--tmp-project--"
    directory.mkdir(parents=True)
    entries = [TEAMMATE_ENTRIES[0], *_tool_call_entries("send_main_message", "TOOL_ARGUMENT_MARKER", "TOOL_RESULT_MARKER")]
    (directory / TEAMMATE_FILE).write_text(_jsonl(entries) + "\n", encoding="utf-8")
    for arguments, expected in (((), set()), (("--tools",), set()), (("--agents",), {TEAMMATE_ID})):
        found = _search_ids(home, "TOOL_ARGUMENT_MARKER", *arguments)
        assert found == expected, f"Expected `search {' '.join(arguments)}` -> {expected}. Got {found}."


# ── Team calls made inside codemode ───────────────────────────────────────────
#
# Pi records the tools a codemode script ran in its result's `nestedCalls`, with
# their arguments but not their results. Team calls there are delegation like any
# direct team call.

CODEMODE_ENTRIES = [
    TEAMMATE_ENTRIES[0],
    {
        "type": "message",
        "id": "cm-call",
        "timestamp": "2026-10-08T10:05:00.000Z",
        "message": {
            "role": "assistant",
            "content": [{"type": "toolCall", "id": "cm-id", "name": "codemode", "arguments": {"code": "CODEMODE_SOURCE_MARKER"}}],
        },
    },
    {
        "type": "message",
        "id": "cm-result",
        "timestamp": "2026-10-08T10:05:01.000Z",
        "message": {
            "role": "toolResult",
            "toolCallId": "cm-id",
            "toolName": "codemode",
            "content": [{"type": "text", "text": "CODEMODE_RESULT_MARKER"}],
            "nestedCalls": {
                "calls": [
                    {"id": "cm-id/1", "name": "bash", "status": "ok", "arguments": {"command": "NESTED_BASH_MARKER"}},
                    {
                        "id": "cm-id/2",
                        "name": "team_send_message",
                        "status": "ok",
                        "arguments": {"targets": ["scout"], "message": "NESTED_TEAM_MARKER"},
                    },
                ],
                "complete": True,
            },
        },
    },
]


def test_codemode_team_calls_are_agent_content():
    for flags, team_visible, tools_visible in (
        ({}, False, False),
        ({"show_tools": True}, False, True),
        ({"show_agents": True}, True, False),
    ):
        output = _render(CODEMODE_ENTRIES, **flags)
        assert ("NESTED_TEAM_MARKER" in output) is team_visible, f"{flags}: nested team call visible={team_visible}. Got:\n{output}"
        assert ("CODEMODE_RESULT_MARKER" in output) is tools_visible, f"{flags}: codemode visible={tools_visible}. Got:\n{output}"
        assert "NESTED_BASH_MARKER" not in output, f"{flags}: expected nested non-team calls not duplicated. Got:\n{output}"


def test_search_finds_codemode_team_calls_with_agents(tmp_path: Path):
    home = tmp_path / "home"
    directory = home / ".pi" / "agent" / "sessions" / "--tmp-project--"
    directory.mkdir(parents=True)
    (directory / TEAMMATE_FILE).write_text(_jsonl(CODEMODE_ENTRIES) + "\n", encoding="utf-8")
    for arguments, expected in (((), set()), (("--agents",), {TEAMMATE_ID})):
        found = _search_ids(home, "NESTED_TEAM_MARKER", *arguments)
        assert found == expected, f"Expected `search {' '.join(arguments)}` -> {expected}. Got {found}."


# ── --agents merges the sessions this session delegated to ────────────────────
#
# Delegation started from session S: a teammate S's agent spawned (fresh or forked)
# and a side chat S's user dispatched (inheriting or isolated). Each child's own
# transcript merges into S's `--agents` view as an agent block; a copied prefix is
# S's own history and is not merged again. A native fork of S is branching, not
# delegation, and never merges.

DELEGATING_ID = "30000000-0000-4000-8000-0000000000d0"
FRESH_TEAMMATE_ID = "30000000-0000-4000-8000-0000000000d1"
SIDE_CHAT_ID = "30000000-0000-4000-8000-0000000000d2"
BRANCH_ID = "30000000-0000-4000-8000-0000000000d3"


def _session_path(home: Path, session_id: str, stamp: str) -> Path:
    return home / ".pi" / "agent" / "sessions" / "--tmp-project--" / f"{stamp}_{session_id}.jsonl"


def _write_delegation_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    teammate = _session_path(home, FRESH_TEAMMATE_ID, "2026-10-08T08-10-00-000Z")
    side_chat = _session_path(home, SIDE_CHAT_ID, "2026-10-08T08-20-00-000Z")
    branch = _session_path(home, BRANCH_ID, "2026-10-08T08-30-00-000Z")
    parent.parent.mkdir(parents=True)
    parent_history = [
        _text_message("p1", "user", "PARENT_ASK_MARKER", "2026-10-08T08:01:00.000Z"),
        _text_message("p2", "assistant", "PARENT_ANSWER_MARKER", "2026-10-08T08:02:00.000Z"),
    ]
    spawn_receipt = {
        "type": "message",
        "id": "p3",
        "timestamp": "2026-10-08T08:09:59.000Z",
        "message": {
            "role": "toolResult",
            "toolCallId": "spawn",
            "toolName": "team_spawn",
            "content": [{"type": "text", "text": "spawned"}],
            "details": {"teamName": "crew", "teammates": [{"name": "scout", "teammateId": FRESH_TEAMMATE_ID, "sessionFile": str(teammate)}]},
        },
    }
    late = _text_message("p4", "assistant", "PARENT_LATE_MARKER", "2026-10-08T08:40:00.000Z")
    parent_entries = [
        {"type": "session", "version": 3, "id": DELEGATING_ID, "timestamp": "2026-10-08T08:00:00.000Z", "cwd": "/tmp/project"},
        *parent_history,
        spawn_receipt,
        late,
    ]

    def child_header(session_id: str, at: str, with_parent: bool) -> dict:
        header = {"type": "session", "version": 3, "id": session_id, "timestamp": at, "cwd": "/tmp/project"}
        return {**header, "parentSession": str(parent)} if with_parent else header

    teammate_entries = [
        child_header(FRESH_TEAMMATE_ID, "2026-10-08T08:10:00.000Z", with_parent=False),
        _team_message("t1", "main", "TEAMMATE_BRIEFING_MARKER", "scout", "2026-10-08T08:10:01.000Z"),
        _text_message("t2", "assistant", "TEAMMATE_WORK_MARKER", "2026-10-08T08:11:00.000Z"),
    ]
    side_chat_entries = [
        child_header(SIDE_CHAT_ID, "2026-10-08T08:20:00.000Z", with_parent=True),
        {"type": "custom", "customType": "pi-user-agents-dispatch", "id": "d1", "timestamp": "2026-10-08T08:20:00.001Z",
         "data": {"forwardedArgs": [], "task": "SIDE_CHAT_TASK_MARKER", "isolate": False}},
        *[{**entry, "timestamp": "2026-10-08T08:20:00.010Z"} for entry in parent_history],
        _text_message("s1", "user", "SIDE_CHAT_TASK_MARKER", "2026-10-08T08:20:01.000Z"),
        _text_message("s2", "assistant", "SIDE_CHAT_ANSWER_MARKER", "2026-10-08T08:21:00.000Z"),
    ]
    branch_entries = [
        child_header(BRANCH_ID, "2026-10-08T08:30:00.000Z", with_parent=True),
        *parent_history,
        _text_message("f1", "user", "BRANCH_MARKER", "2026-10-08T08:31:00.000Z"),
    ]
    for path, entries in ((parent, parent_entries), (teammate, teammate_entries), (side_chat, side_chat_entries), (branch, branch_entries)):
        path.write_text(_jsonl(entries) + "\n", encoding="utf-8")
    return home


CHILD_WORK_MARKERS = ("TEAMMATE_WORK_MARKER", "SIDE_CHAT_ANSWER_MARKER")


def _parse_with_ch(home: Path, *arguments: str, session_id: str = DELEGATING_ID) -> str:
    result = subprocess.run(
        [str(CH_EXECUTABLE), session_id, "--color", "never", "--no-metadata", *arguments],
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_agents_merges_every_delegated_child_and_no_branch(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    output = _parse_with_ch(home, "--agents")
    for marker in CHILD_WORK_MARKERS:
        assert marker in output, f"Expected delegated child work {marker} under --agents. Got:\n{output}"
    assert "BRANCH_MARKER" not in output, f"Expected the native fork not merged. Got:\n{output}"
    assert output.count("PARENT_ASK_MARKER") == 1, f"Expected the side chat's copied prefix not merged again. Got:\n{output}"
    assert 'name="scout"' in output, f"Expected the teammate block named after the teammate. Got:\n{output}"
    assert output.index("TEAMMATE_WORK_MARKER") < output.index("SIDE_CHAT_ANSWER_MARKER") < output.index("PARENT_LATE_MARKER"), (
        f"Expected each block at its own start time. Got:\n{output}"
    )


def test_children_stay_out_of_the_default_view(tmp_path: Path):
    output = _parse_with_ch(_write_delegation_home(tmp_path))
    for marker in (*CHILD_WORK_MARKERS, "BRANCH_MARKER"):
        assert marker not in output, f"Expected {marker} absent without --agents. Got:\n{output}"


def test_agents_search_finds_parent_through_child_work(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    for query, child in (("TEAMMATE_WORK_MARKER", FRESH_TEAMMATE_ID), ("SIDE_CHAT_ANSWER_MARKER", SIDE_CHAT_ID)):
        assert _search_ids(home, query) == {child}
        assert _search_ids(home, query, "--agents") == {DELEGATING_ID, child}
    assert _search_ids(home, "BRANCH_MARKER", "--agents") == {BRANCH_ID}


def test_a_copied_dispatch_does_not_turn_a_branch_into_delegation(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    branch = _session_path(home, BRANCH_ID, "2026-10-08T08-30-00-000Z")
    entries = [json.loads(line) for line in branch.read_text().splitlines()]
    entries.insert(1, {
        "type": "custom", "customType": "pi-user-agents-dispatch", "id": "old-dispatch",
        "timestamp": "2026-10-07T08:00:00.001Z", "data": {"task": "OLD_TASK", "isolate": False},
    })
    branch.write_text(_jsonl(entries))
    assert "BRANCH_MARKER" not in _parse_with_ch(home, "--agents")
    assert _search_ids(home, "BRANCH_MARKER", "--agents") == {BRANCH_ID}


def test_nested_spawn_receipts_do_not_claim_unrelated_printed_files(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    branch = _session_path(home, BRANCH_ID, "2026-10-08T08-30-00-000Z")
    entries = [json.loads(line) for line in parent.read_text().splitlines()]
    receipt = entries[3]["message"]
    printed = {**receipt.pop("details"), "teamId": f"{DELEGATING_ID}-crew"}
    receipt["toolName"] = "codemode"
    receipt["nestedCalls"] = {"complete": True, "calls": [
        {"id": "spawn/1", "name": "team_spawn", "status": "ok", "arguments": {"teamName": "crew"}},
    ]}
    receipt["content"] = [{"type": "text", "text": (
        "Script completed\n==> text 1/2 <==\n" + json.dumps(printed, indent=2)
        + "\n==> text 2/2 <==\n" + json.dumps({"sessionFile": str(branch)})
    )}]
    parent.write_text(_jsonl(entries))
    output = _parse_with_ch(home, "--agents")
    assert "TEAMMATE_WORK_MARKER" in output
    assert "BRANCH_MARKER" not in output
    assert _search_ids(home, "TEAMMATE_WORK_MARKER", "--agents") == {DELEGATING_ID, FRESH_TEAMMATE_ID}
    assert _search_ids(home, "BRANCH_MARKER", "--agents") == {BRANCH_ID}


def test_inherited_spawn_receipts_do_not_attach_ancestors_children(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    entries = [json.loads(line) for line in parent.read_text().splitlines()]
    branch = _session_path(home, BRANCH_ID, "2026-10-08T08-30-00-000Z")
    branch_entries = [json.loads(line) for line in branch.read_text().splitlines()]
    branch_entries.insert(3, entries[3])
    branch.write_text(_jsonl(branch_entries))
    output = _parse_with_ch(home, "--agents", session_id=BRANCH_ID)
    assert "TEAMMATE_WORK_MARKER" not in output
    assert "SIDE_CHAT_ANSWER_MARKER" not in output
    assert BRANCH_ID not in _search_ids(home, "TEAMMATE_WORK_MARKER", "--agents")


def test_repeated_spawn_and_resume_receipts_merge_each_child_once(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    entries = [json.loads(line) for line in parent.read_text().splitlines()]
    repeated = entries[3]
    resume = {**repeated, "id": "resume", "message": {**repeated["message"], "toolName": "team_resume"}}
    entries.extend([repeated, resume])
    parent.write_text(_jsonl(entries))
    output = _parse_with_ch(home, "--agents")
    assert output.count("TEAMMATE_WORK_MARKER") == 1
    searched = subprocess.run(
        [str(CH_EXECUTABLE), "search", "TEAMMATE_WORK_MARKER", "--agents", "--color", "never"],
        env={**os.environ, "HOME": str(home)}, capture_output=True, text=True, check=True,
    )
    assert searched.stdout.count("TEAMMATE_WORK_MARKER") == 2, searched.stdout


def test_a_resume_receipt_does_not_claim_creation(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    entries = [json.loads(line) for line in parent.read_text().splitlines()]
    entries[3]["message"]["toolName"] = "team_resume"
    parent.write_text(_jsonl(entries))
    assert "TEAMMATE_WORK_MARKER" not in _parse_with_ch(home, "--agents")
    assert _search_ids(home, "TEAMMATE_WORK_MARKER", "--agents") == {FRESH_TEAMMATE_ID}


def test_recursive_delegation_deduplicates_aliases_and_cycles(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    teammate = _session_path(home, FRESH_TEAMMATE_ID, "2026-10-08T08-10-00-000Z")
    grandchild_id = "30000000-0000-4000-8000-0000000000d4"
    grandchild = _session_path(home, grandchild_id, "2026-10-08T08-12-00-000Z")
    grandchild.write_text(_jsonl([
        {"type": "session", "version": 3, "id": grandchild_id, "timestamp": "2026-10-08T08:12:00.000Z", "cwd": "/tmp/project"},
        _team_message("g1", "main", "GRANDCHILD_TASK", "nested-scout", "2026-10-08T08:12:01.000Z"),
        _text_message("g2", "assistant", "GRANDCHILD_WORK_MARKER", "2026-10-08T08:13:00.000Z"),
    ]))
    alias = grandchild.with_name("grandchild-alias.jsonl")
    alias.symlink_to(grandchild)
    receipt = {
        "type": "message", "id": "nested-spawn", "timestamp": "2026-10-08T08:12:00.000Z",
        "message": {"role": "toolResult", "toolName": "team_spawn", "toolCallId": "nested-spawn",
                    "content": [{"type": "text", "text": "spawned"}],
                    "details": {"teammates": [{"sessionFile": str(path)} for path in (grandchild, alias, parent)]}},
    }
    with teammate.open("a") as stream:
        stream.write(_jsonl([receipt]) + "\n")
    output = _parse_with_ch(home, "--agents")
    assert output.count("GRANDCHILD_WORK_MARKER") == 1
    records = json.loads(_parse_with_ch(home, "--agents", "-f", "json"))
    grandchildren = [record for record in records if record.get("agent_id") == grandchild_id]
    assert grandchildren and all(record.get("name") == "nested-scout" for record in grandchildren)
    assert output.count("PARENT_ASK_MARKER") == 1
    assert _search_ids(home, "GRANDCHILD_WORK_MARKER", "--agents") == {DELEGATING_ID, FRESH_TEAMMATE_ID, grandchild_id}


def test_user_isolation_and_team_inheritance_do_not_change_delegation(tmp_path: Path):
    home = _write_delegation_home(tmp_path)
    parent = _session_path(home, DELEGATING_ID, "2026-10-08T08-00-00-000Z")
    parent_entries = [json.loads(line) for line in parent.read_text().splitlines()]
    teammate = _session_path(home, FRESH_TEAMMATE_ID, "2026-10-08T08-10-00-000Z")
    team_entries = [json.loads(line) for line in teammate.read_text().splitlines()]
    team_entries[0]["parentSession"] = str(parent)
    team_entries[1:1] = parent_entries[1:3]
    teammate.write_text(_jsonl(team_entries))
    # Discover a fork-context teammate from its own file, without a parent receipt.
    parent.write_text(_jsonl([*parent_entries[:3], parent_entries[-1]]))
    side_chat = _session_path(home, SIDE_CHAT_ID, "2026-10-08T08-20-00-000Z")
    side_entries = [json.loads(line) for line in side_chat.read_text().splitlines()]
    side_entries[1]["data"]["isolate"] = True
    del side_entries[2:4]
    side_chat.write_text(_jsonl(side_entries))
    output = _parse_with_ch(home, "--agents")
    for marker in CHILD_WORK_MARKERS:
        assert marker in output
    assert output.count("PARENT_ASK_MARKER") == 1
    assert _search_ids(home, "TEAMMATE_WORK_MARKER", "--agents") == {DELEGATING_ID, FRESH_TEAMMATE_ID}
    assert _search_ids(home, "SIDE_CHAT_ANSWER_MARKER", "--agents") == {DELEGATING_ID, SIDE_CHAT_ID}
