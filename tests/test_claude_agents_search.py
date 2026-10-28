#!/usr/bin/env python3
"""`ch search --agents` reads a Claude session the way `ch <session> --agents` does.

Parse merges each subagent, fork, and teammate transcript into its parent's
timeline as an agent block. Search does the same: a match inside a child is a
match in the parent session. The child file also remains separately searchable.
"""

import json
import os
import subprocess
import sys

import pytest
from pathlib import Path

CH_EXECUTABLE = Path(sys.executable).with_name("ch")
PARENT_ID = "55555555-5555-4555-8555-555555555555"
AGENT_ID = "a0123456789abcdef"
PROJECT = "-Users-tester-project"


def _write(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    project = home / ".claude" / "projects" / PROJECT
    _write(project / f"{PARENT_ID}.jsonl", [
        {"type": "user", "sessionId": PARENT_ID, "timestamp": "2026-10-20T10:00:00Z",
         "message": {"role": "user", "content": "PARENT_PROMPT_MARKER"}},
        {"type": "assistant", "sessionId": PARENT_ID, "timestamp": "2026-10-20T10:05:00Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "PARENT_REPLY_MARKER"}]}},
    ])
    agent = project / PARENT_ID / "subagents" / f"agent-{AGENT_ID}.jsonl"
    _write(agent, [
        {"type": "user", "isSidechain": True, "agentId": AGENT_ID, "sessionId": PARENT_ID,
         "timestamp": "2026-10-20T10:01:00Z", "message": {"role": "user", "content": "CHILD_TASK_MARKER"}},
        {"type": "assistant", "isSidechain": True, "agentId": AGENT_ID, "sessionId": PARENT_ID,
         "timestamp": "2026-10-20T10:02:00Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "CHILD_REPLY_MARKER"}]}},
    ])
    agent.with_name(f"agent-{AGENT_ID}.meta.json").write_text(
        json.dumps({"agentType": "general-purpose", "name": "scout"}), encoding="utf-8"
    )
    return home


def _run(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CH_EXECUTABLE), *arguments],
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_agents_search_finds_child_text_in_the_parent(tmp_path: Path):
    home = _home(tmp_path)
    for marker in ("CHILD_REPLY_MARKER", "CHILD_TASK_MARKER"):
        hit = _run(home, "search", marker, "--agents", "--only-id")
        assert set(hit.stdout.split()) == {PARENT_ID, f"agent-{AGENT_ID}"}, (
            f"Expected {marker} to match the parent and child sessions. stdout: {hit.stdout!r}; stderr: {hit.stderr!r}."
        )


def test_merged_child_keeps_peer_sender_and_leader_followup(tmp_path: Path):
    home = _home(tmp_path)
    transcript = home / ".claude" / "projects" / PROJECT / PARENT_ID / "subagents" / f"agent-{AGENT_ID}.jsonl"
    with transcript.open("a", encoding="utf-8") as handle:
        for sender, body in (("closer", "PEER_REPORT_MARKER"), ("team-lead", "FOLLOWUP_TASK_MARKER")):
            record = {
                "type": "user", "agentId": AGENT_ID, "sessionId": PARENT_ID,
                "timestamp": "2026-10-20T10:03:00Z",
                "message": {"role": "user", "content": f'<teammate-message teammate_id="{sender}">{body}</teammate-message>'},
            }
            handle.write(json.dumps(record) + "\n")
    parsed = json.loads(_run(home, PARENT_ID, "--agents", "--format", "json").stdout)
    peer = next(message for message in parsed if "PEER_REPORT_MARKER" in message["content"])
    assert peer["name"] == "closer" and peer["agent_id"] == "closer", peer
    tasks = [block["content"] for message in parsed for block in message["content"]
             if isinstance(block, dict) and block.get("type") == "subagent-task"]
    assert "FOLLOWUP_TASK_MARKER" in tasks, tasks
    searched = _run(home, "search", "PEER_REPORT_MARKER", "--agents", "--full", "--raw").stdout
    assert "Agent 'closer'" in searched, searched


def _background_fork(home: Path, *, launch_kind: str = "system", copied_receipt: bool = False) -> str:
    project = home / ".claude" / "projects" / PROJECT
    child_id = "66666666-6666-4666-8666-666666666666"
    origin = "77777777-7777-4777-8777-777777777777" if copied_receipt else PARENT_ID
    prefix = {"type": "user", "uuid": "source-user", "sessionId": PARENT_ID, "session_id": origin,
              "timestamp": "2026-10-20T10:00:00Z", "message": {"role": "user", "content": "COPIED_PARENT_MARKER"}}
    command = {"type": launch_kind, "subtype": "local_command", "sessionId": PARENT_ID,
               "timestamp": "2026-10-20T10:01:00Z", "content": "<command-name>/fork</command-name><command-args>research</command-args>"}
    receipt = {"type": launch_kind, "subtype": "local_command", "sessionId": PARENT_ID,
               "timestamp": "2026-10-20T10:01:01Z", "content": f"<local-command-stdout>session running · research · {child_id[:8]}</local-command-stdout>"}
    parent_records = [prefix, command, receipt]
    if copied_receipt:
        parent_records.append({**prefix, "uuid": "source-reply", "message": {"role": "user", "content": "old"}})
    parent_records.append({**prefix, "uuid": "own-user", "session_id": PARENT_ID,
                           "message": {"role": "user", "content": "CURRENT_PARENT_MARKER"}})
    _write(project / f"{PARENT_ID}.jsonl", parent_records)
    _write(project / f"{child_id}.jsonl", [
        {**prefix, "sessionId": child_id},
        {"type": "user", "sessionId": child_id, "session_id": child_id,
         "timestamp": "2026-10-20T10:02:00Z", "message": {"role": "user", "content": "BACKGROUND_TASK_MARKER"}},
        {"type": "assistant", "sessionId": child_id, "session_id": child_id,
         "timestamp": "2026-10-20T10:03:00Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "BACKGROUND_REPLY_MARKER"}]}},
    ])
    return child_id


def test_user_background_fork_is_delegation_in_parse_and_search(tmp_path: Path):
    home = _home(tmp_path)
    child_id = _background_fork(home)
    parsed = _run(home, PARENT_ID, "--agents", "--format", "json").stdout
    assert "BACKGROUND_REPLY_MARKER" in parsed, parsed
    assert parsed.count("COPIED_PARENT_MARKER") == 1, parsed
    assert any(message.get("agent_id") == child_id for message in json.loads(parsed)), parsed
    found = _run(home, "search", "BACKGROUND_REPLY_MARKER", "--agents", "--only-id").stdout.split()
    assert set(found) == {PARENT_ID, child_id}, found
    direct = _run(home, child_id, "--raw").stdout
    assert "COPIED_PARENT_MARKER" in direct, direct


@pytest.mark.parametrize("launch_kind,copied_receipt", [("user", False), ("system", True)])
def test_no_delegation_from_quoted_or_inherited_launches(tmp_path: Path, launch_kind: str, copied_receipt: bool):
    home = _home(tmp_path)
    child_id = _background_fork(home, launch_kind=launch_kind, copied_receipt=copied_receipt)
    parsed = _run(home, PARENT_ID, "--agents", "--format", "json").stdout
    assert "BACKGROUND_REPLY_MARKER" not in parsed, parsed
    found = _run(home, "search", "BACKGROUND_REPLY_MARKER", "--agents", "--only-id").stdout.split()
    assert found == [child_id], found


def _herdr_fork(home: Path, *, invalid: str | None = None) -> str:
    project = home / ".claude" / "projects" / PROJECT
    child_id = "88888888-8888-4888-8888-888888888888"
    source_id = "99999999-9999-4999-8999-999999999999"
    child_source = PARENT_ID if invalid == "unrelated" else source_id
    parent_path = project / f"{PARENT_ID}.jsonl"
    started = {"id": "cli:agent:start", "result": {"type": "agent_started",
               "argv": ["claude", "--fork-session", "--resume", source_id],
               "agent": {"name": "helper", "terminal_id": "terminal-new", "pane_id": "pane-new"}}}
    observed = {"id": "cli:agent:get", "result": {"type": "agent_info", "agent": {
        "terminal_id": "terminal-wrong" if invalid == "terminal" else "terminal-new", "pane_id": "pane-new",
        "agent_session": {"agent": "claude", "kind": "id", "value": child_id}}}}
    records = []
    for number, (command, receipt) in enumerate((
        (f"herdr agent start helper --kind claude --pane pane-new -- --fork-session --resume {source_id}", started),
        ("herdr agent get pane-new", observed),
    )):
        if invalid == "documentation":
            command = "printf '%s' '" + command + "'"
        records.extend([
            {"type": "assistant", "sessionId": PARENT_ID, "session_id": PARENT_ID,
             "timestamp": f"2026-10-20T10:0{number + 1}:00Z", "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "id": f"launch-{number}", "name": "Bash", "input": {"command": command}}]}},
            {"type": "user", "sessionId": PARENT_ID, "session_id": PARENT_ID,
             "timestamp": f"2026-10-20T10:0{number + 1}:01Z", "message": {"role": "user", "content": [
                 {"type": "tool_result", "tool_use_id": f"launch-{number}", "is_error": invalid == "failed",
                  "content": json.dumps(receipt)}]}},
        ])
    with parent_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(map(json.dumps, records)) + "\n")
    _write(project / f"{child_id}.jsonl", [
        {"type": "user", "sessionId": child_id, "session_id": child_source,
         "timestamp": "2026-10-20T09:00:00Z", "message": {"role": "user", "content": "OTHER_CONTEXT_MARKER"}},
        {"type": "user", "sessionId": child_id, "session_id": child_id,
         "timestamp": "2026-10-20T10:04:00Z", "message": {"role": "user", "content": "HERDR_TASK_MARKER"}},
        {"type": "assistant", "sessionId": child_id, "session_id": child_id,
         "timestamp": "2026-10-20T10:05:00Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "HERDR_REPLY_MARKER"}]}},
    ])
    return child_id


def test_proven_agent_cli_fork_can_copy_another_sessions_context(tmp_path: Path):
    home = _home(tmp_path)
    child_id = _herdr_fork(home)
    output = _run(home, PARENT_ID, "--agents", "--format", "json").stdout
    assert "HERDR_REPLY_MARKER" in output and "OTHER_CONTEXT_MARKER" not in output, output
    found = _run(home, "search", "HERDR_REPLY_MARKER", "--agents", "--only-id").stdout.split()
    assert set(found) == {PARENT_ID, child_id}, found


@pytest.mark.parametrize("invalid", ["documentation", "failed", "unrelated", "terminal"])
def test_cli_fork_requires_executed_successful_receipts_and_matching_child(tmp_path: Path, invalid: str):
    home = _home(tmp_path)
    child_id = _herdr_fork(home, invalid=invalid)
    output = _run(home, PARENT_ID, "--agents", "--format", "json").stdout
    assert "HERDR_REPLY_MARKER" not in output, output
    found = _run(home, "search", "HERDR_REPLY_MARKER", "--agents", "--only-id").stdout.split()
    assert found == [child_id], found


def test_nested_claude_sidechain_keeps_its_identity(tmp_path: Path):
    home = _home(tmp_path)
    directory = home / ".claude" / "projects" / PROJECT / PARENT_ID / "subagents"
    grandchild_id = "a9999999999999999"
    transcript = directory / f"agent-{grandchild_id}.jsonl"
    _write(transcript, [
        {"type": "user", "agentId": grandchild_id, "sessionId": PARENT_ID, "timestamp": "2026-10-20T10:02:30Z",
         "message": {"role": "user", "content": "NESTED_TASK_MARKER"}},
        {"type": "assistant", "agentId": grandchild_id, "sessionId": PARENT_ID, "timestamp": "2026-10-20T10:03:00Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "NESTED_REPLY_MARKER"}]}},
    ])
    transcript.with_suffix(".meta.json").write_text(json.dumps({"parentAgentId": AGENT_ID, "name": "nested"}), encoding="utf-8")
    messages = json.loads(_run(home, PARENT_ID, "--agents", "--format", "json").stdout)
    replies = [message for message in messages if "NESTED_REPLY_MARKER" in message["content"]]
    assert len(replies) == 1 and replies[0]["agent_id"] == grandchild_id, replies
    found = _run(home, "search", "NESTED_REPLY_MARKER", "--agents", "--only-id").stdout.split()
    assert set(found) == {PARENT_ID, f"agent-{AGENT_ID}", f"agent-{grandchild_id}"}, found


def test_delivered_reply_and_private_child_work_both_survive(tmp_path: Path):
    home = _home(tmp_path)
    parent = home / ".claude" / "projects" / PROJECT / f"{PARENT_ID}.jsonl"
    records = [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Agent", "id": "dispatch", "input": {"prompt": "research"}}]}},
        {"type": "user", "origin": {"kind": "task-notification"}, "message": {"role": "user", "content":
         f"<task-notification><task-id>{AGENT_ID}</task-id><tool-use-id>dispatch</tool-use-id><status>completed</status><result>DELIVERED_REPORT_MARKER</result></task-notification>"}},
    ]
    with parent.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(map(json.dumps, records)) + "\n")
    parsed = _run(home, PARENT_ID, "--agents", "--format", "json").stdout
    assert "CHILD_REPLY_MARKER" in parsed and "DELIVERED_REPORT_MARKER" in parsed, parsed
    delivered = next(message for message in json.loads(parsed) if "DELIVERED_REPORT_MARKER" in message["content"])
    assert delivered["agent_id"] == AGENT_ID and delivered["status"] == "completed", delivered
    search = _run(home, "search", "DELIVERED_REPORT_MARKER", "--agents", "--full", "--raw").stdout
    assert "CHILD_REPLY_MARKER" in search and "DELIVERED_REPORT_MARKER" in search, search


def test_orphan_sidechain_stays_searchable(tmp_path: Path):
    home = _home(tmp_path)
    (home / ".claude" / "projects" / PROJECT / f"{PARENT_ID}.jsonl").unlink()
    found = _run(home, "search", "CHILD_REPLY_MARKER", "--agents", "--only-id").stdout.split()
    assert found == [f"agent-{AGENT_ID}"], found


def test_child_directory_filter_does_not_require_parent_match(tmp_path: Path):
    home = _home(tmp_path)
    project = home / ".claude" / "projects" / PROJECT
    for path, directory in ((project / f"{PARENT_ID}.jsonl", "/parent"),
                            (project / PARENT_ID / "subagents" / f"agent-{AGENT_ID}.jsonl", "/child")):
        records = [dict(json.loads(line), cwd=directory) for line in path.read_text().splitlines()]
        _write(path, records)
    found = _run(home, "search", "CHILD_REPLY_MARKER", "--agents", "--dir", "/child", "--only-id").stdout.split()
    assert found == [f"agent-{AGENT_ID}"], found


def test_default_search_ignores_child_text(tmp_path: Path):
    home = _home(tmp_path)
    hit = _run(home, "search", "CHILD_REPLY_MARKER", "--only-id")
    assert hit.returncode == 1 and not hit.stdout, f"Expected no default match. stdout: {hit.stdout!r}."


def test_agents_search_shows_the_child_as_parse_does(tmp_path: Path):
    home = _home(tmp_path)
    searched = _run(home, "search", "CHILD_REPLY_MARKER", "--agents", "--full", "--raw").stdout
    parsed = _run(home, PARENT_ID, "--agents", "--raw").stdout

    for output in (searched, parsed):
        assert "Agent 'scout'" in output and "CHILD_REPLY_MARKER" in output and "PARENT_REPLY_MARKER" in output, (
            f"Expected the merged agent block beside the parent's messages. Got:\n{output}"
        )
