#!/usr/bin/env python3
"""Codex delegation as Codex records it since the `collaboration` tool namespace.

Shapes are taken from Codex 0.153-0.165 rollouts (September-October 2026):

- All `collaboration` function calls and results are agent content under
  `--agents`, never `--tools` alone. Encrypted arguments show as `[encrypted]`.
- Messages between agents are `response_item` payloads of type `agent_message`.
  In a child rollout, a message from its leader is the child's incoming
  instruction and renders as a user message: its plaintext payload, else (the
  usual case, encrypted) its routing header as written. Other deliveries require
  --agents and retain their sender independently of child transcript availability.
- A subagent spawned with inherited context copies the parent's records before
  `session_meta.subagent_history_start_ordinal`. Direct views keep them; merged
  child blocks omit them because the parent's own timeline already contains them.
- A child rollout names its spawner (`parent_thread_id`) and, when forked, its
  context source (`forked_from_id`). Both reach the metadata.

Every claim is made through the public `ch` launcher, once for parse (Python)
and once for search (Rust), so the two paths cannot drift.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CH_EXECUTABLE = Path(sys.executable).with_name("ch")

ROOT_ID = "10000000-0000-4000-8000-000000000001"
CHILD_ID = "10000000-0000-4000-8000-000000000002"
FORK_ID = "10000000-0000-4000-8000-000000000003"
GRANDCHILD_ID = "10000000-0000-4000-8000-000000000004"

CIPHERTEXT = "gAAAAA_SYNTHETIC_ENCRYPTED_ARGUMENT"


def _timestamp(second: int) -> str:
    return f"2026-09-16T09:{40 + second // 60:02d}:{second % 60:02d}.000Z"


def _item(ordinal: int, payload: dict, entry_type: str = "response_item") -> dict:
    return {"timestamp": _timestamp(ordinal), "ordinal": ordinal, "type": entry_type, "payload": payload}


def _user(ordinal: int, text: str) -> dict:
    return _item(ordinal, {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]})


def _assistant(ordinal: int, text: str) -> dict:
    return _item(ordinal, {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]})


def _call(ordinal: int, name: str, call_id: str, arguments: dict) -> dict:
    return _item(ordinal, {
        "type": "function_call",
        "name": name,
        "namespace": "collaboration",
        "arguments": json.dumps(arguments),
        "call_id": call_id,
    })


def _output(ordinal: int, call_id: str, output: str) -> dict:
    return _item(ordinal, {"type": "function_call_output", "call_id": call_id, "output": output})


def _agent_message(ordinal: int, author: str, recipient: str, message_type: str, plaintext: str | None = None) -> dict:
    header = f"Message Type: {message_type}\nTask name: {recipient}\nSender: {author}\nPayload:\n"
    content = (
        [{"type": "input_text", "text": header + plaintext}]
        if plaintext is not None
        else [{"type": "input_text", "text": header}, {"type": "encrypted_content", "encrypted_content": CIPHERTEXT}]
    )
    return _item(ordinal, {"type": "agent_message", "author": author, "recipient": recipient, "content": content})


PLUGIN_NOISE = "<recommended_plugins>\nHere is a list of plugins. PLUGIN_NOISE_MARKER\n</recommended_plugins>"


def _subagent_meta(session_id: str, parent_id: str, agent_path: str, depth: int, **extra: object) -> dict:
    spawn = {"parent_thread_id": parent_id, "depth": depth, "agent_path": agent_path, "agent_nickname": "Kant", "agent_role": "worker"}
    payload = {
        "session_id": ROOT_ID,
        "id": session_id,
        "parent_thread_id": parent_id,
        "timestamp": _timestamp(0),
        "cwd": "/tmp/project",
        "cli_version": "0.163.0",
        "source": {"subagent": {"thread_spawn": spawn}},
        "thread_source": "subagent",
        "agent_nickname": "Kant",
        "agent_path": agent_path,
        "agent_role": "worker",
        **extra,
    }
    return {"timestamp": _timestamp(0), "ordinal": 0, "type": "session_meta", "payload": payload}


ROOT_ROLLOUT = [
    {"timestamp": _timestamp(0), "ordinal": 0, "type": "session_meta", "payload": {
        "session_id": ROOT_ID, "id": ROOT_ID, "timestamp": _timestamp(0), "cwd": "/tmp/project",
        "cli_version": "0.163.0", "source": "cli", "thread_source": "user",
    }},
    _user(1, PLUGIN_NOISE),
    _user(2, "ROOT_USER_MARKER INHERITED_PARENT_MARKER"),
    _assistant(3, "INHERITED_ASSISTANT_MARKER"),
    _call(4, "spawn_agent", "call_spawn", {"task_name": "review", "fork_turns": "none", "message": CIPHERTEXT}),
    _output(5, "call_spawn", '{"task_name":"/root/review"}'),
    _call(6, "wait_agent", "call_wait", {"timeout_ms": 1000}),
    _output(7, "call_wait", '{"message":"Wait completed.","timed_out":false}'),
    _agent_message(8, "/root/review", "/root", "MESSAGE"),
    _agent_message(9, "/root/review", "/root", "FINAL_ANSWER", "CHILD_FINAL_MARKER"),
    _call(10, "followup_task", "call_followup", {"target": "/root/review", "message": CIPHERTEXT}),
    _output(11, "call_followup", ""),
    _call(12, "list_agents", "call_list", {}),
    _output(13, "call_list", "LIST_AGENTS_RESULT_MARKER"),
    _assistant(14, "ROOT_ASSISTANT_MARKER"),
]

CHILD_ROLLOUT = [
    _subagent_meta(CHILD_ID, ROOT_ID, "/root/review", 1),
    _item(1, {"model": "gpt-6.1-sol"}, "turn_context"),
    _user(2, PLUGIN_NOISE),
    _agent_message(3, "/root", "/root/review", "NEW_TASK"),
    _assistant(4, "CHILD_WORK_MARKER"),
    _call(5, "send_message", "call_send", {"target": "/root", "message": CIPHERTEXT}),
    _output(6, "call_send", ""),
    _agent_message(7, "/root", "/root/review", "MESSAGE"),
    _agent_message(8, "/root/other", "/root/review", "MESSAGE", "PEER_MESSAGE_MARKER"),
    _assistant(9, "CHILD_FINAL_MARKER"),
]

FORK_ROLLOUT = [
    _subagent_meta(FORK_ID, ROOT_ID, "/root/forked", 1, forked_from_id=ROOT_ID, subagent_history_start_ordinal=4),
    {**ROOT_ROLLOUT[0], "ordinal": 1},
    {**_user(2, "ROOT_USER_MARKER INHERITED_PARENT_MARKER")},
    {**_assistant(3, "INHERITED_ASSISTANT_MARKER")},
    _agent_message(4, "/root", "/root/forked", "NEW_TASK"),
    _assistant(5, "FORK_OWN_MARKER"),
]

GRANDCHILD_META = _subagent_meta(GRANDCHILD_ID, CHILD_ID, "/root/review/deep", 2)
del GRANDCHILD_META["payload"]["agent_role"]
GRANDCHILD_META["payload"]["source"]["subagent"]["thread_spawn"]["agent_role"] = "explorer"
GRANDCHILD_ROLLOUT = [
    GRANDCHILD_META,
    _agent_message(1, "/root/review", "/root/review/deep", "NEW_TASK"),
    _assistant(2, "GRANDCHILD_MARKER"),
]

ROLLOUTS = {ROOT_ID: ROOT_ROLLOUT, CHILD_ID: CHILD_ROLLOUT, FORK_ID: FORK_ROLLOUT, GRANDCHILD_ID: GRANDCHILD_ROLLOUT}


def _write_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    day = home / ".codex" / "sessions" / "2026" / "09" / "16"
    day.mkdir(parents=True)
    for offset, (session_id, rollout) in enumerate(ROLLOUTS.items()):
        path = day / f"rollout-2026-09-16T12-40-0{offset}-{session_id}.jsonl"
        path.write_text("".join(json.dumps(entry) + "\n" for entry in rollout), encoding="utf-8")
    return home


def _ch(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CH_EXECUTABLE), *arguments, "--color", "never", "--no-paging"],
        cwd=Path(__file__).parent.parent,
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem", "COLUMNS": "200"},
        capture_output=True,
        text=True,
        check=False,
    )


def _parse(home: Path, session_id: str, *arguments: str) -> str:
    result = _ch(home, session_id, *arguments)
    assert result.returncode == 0, f"`ch {session_id} {' '.join(arguments)}` failed: {result.stderr}"
    return result.stdout


def _search_ids(home: Path, pattern: str, *arguments: str) -> set[str]:
    result = _ch(home, "search", pattern, *arguments, "--only-id")
    return set(result.stdout.split())


# ── collaboration controls are agent content ─────────────────────────────────


def test_collaboration_controls_render_only_under_agents(tmp_path: Path):
    home = _write_home(tmp_path)
    for arguments in ((), ("-t",)):
        output = _parse(home, ROOT_ID, *arguments)
        for marker in ("followup_task", "list_agents", "LIST_AGENTS_RESULT_MARKER"):
            assert marker not in output, f"Expected {marker} hidden with {arguments or 'defaults'}. Got:\n{output}"
    output = _parse(home, ROOT_ID, "-a")
    for marker in ("followup_task", "list_agents", "LIST_AGENTS_RESULT_MARKER"):
        assert marker in output, f"Expected {marker} under --agents. Got:\n{output}"
    for control in ("spawn_agent", "wait_agent"):
        assert control in output, f"Expected {control} under --agents, not unconditional suppression."


def test_spawn_failure_remains_visible_without_a_child_file(tmp_path: Path):
    home = _write_home(tmp_path)
    root = next((home / ".codex/sessions").rglob(f"*{ROOT_ID}.jsonl"))
    with root.open("a") as handle:
        handle.write(json.dumps(_call(15, "spawn_agent", "failed_spawn", {"task_name": "missing", "message": "Check."})) + "\n")
        handle.write(json.dumps(_output(16, "failed_spawn", "DELEGATION_FAILED_AT_CAPACITY")) + "\n")
    assert "DELEGATION_FAILED_AT_CAPACITY" in _parse(home, ROOT_ID, "-a")
    assert _search_ids(home, "DELEGATION_FAILED_AT_CAPACITY", "-a") == {ROOT_ID}
    assert _search_ids(home, "DELEGATION_FAILED_AT_CAPACITY", "-t") == set()


def test_collaboration_ciphertext_renders_as_encrypted_marker(tmp_path: Path):
    home = _write_home(tmp_path)
    output = _parse(home, ROOT_ID, "-a", "-t")
    assert "gAAAAA" not in output, f"Expected no ciphertext in the output. Got:\n{output}"
    assert "[encrypted]" in output, f"Expected the encrypted follow-up body marked. Got:\n{output}"


def test_search_finds_collaboration_controls_only_under_agents(tmp_path: Path):
    home = _write_home(tmp_path)
    for arguments, expected in (((), set()), (("-t",), set()), (("-a",), {ROOT_ID})):
        found = _search_ids(home, "LIST_AGENTS_RESULT_MARKER", *arguments)
        assert found == expected, f"Expected search {arguments} to find {expected}. Got: {found}"
    assert _search_ids(home, "gAAAAA", "-a", "-t") == set(), "Expected ciphertext to be unsearchable."


# ── agent messages ────────────────────────────────────────────────────────────


def test_leader_messages_are_the_childs_user_messages(tmp_path: Path):
    home = _write_home(tmp_path)
    output = _parse(home, CHILD_ID)
    for header in ("Message Type: NEW_TASK\nTask name: /root/review\nSender: /root\n", "Message Type: MESSAGE\n"):
        assert header in output, f"Expected the leader's message header {header!r} as a user message. Got:\n{output}"
    assert output.count("<user-message") == 2, f"Expected exactly the two leader messages as user messages. Got:\n{output}"
    assert "PEER_MESSAGE_MARKER" not in output, "Peer messages require --agents."
    peer_output = _parse(home, CHILD_ID, "-a")
    assert 'name="/root/other"' in peer_output and "PEER_MESSAGE_MARKER" in peer_output
    assert _search_ids(home, "Message Type: NEW_TASK") == {CHILD_ID, FORK_ID, GRANDCHILD_ID}, (
        "Expected search to agree with parse."
    )


def test_delivered_child_report_survives_a_missing_child_transcript(tmp_path: Path):
    home = _write_home(tmp_path)
    for path in (home / ".codex/sessions").rglob(f"*{CHILD_ID}.jsonl"):
        path.unlink()
    assert "CHILD_FINAL_MARKER" not in _parse(home, ROOT_ID, "-t")
    output = _parse(home, ROOT_ID, "-a")
    assert 'name="/root/review"' in output and "CHILD_FINAL_MARKER" in output, output
    assert _search_ids(home, "CHILD_FINAL_MARKER", "-a") == {ROOT_ID}


def test_merged_peer_delivery_keeps_its_sender(tmp_path: Path):
    home = _write_home(tmp_path)
    output = _parse(home, ROOT_ID, "-a", "-f", "json")
    peer = [message for message in json.loads(output) if "PEER_MESSAGE_MARKER" in message.get("content", [])]
    assert len(peer) == 1 and peer[0]["name"] == "/root/other", peer
    searched = _ch(home, "search", "PEER_MESSAGE_MARKER", "-a").stdout
    assert 'name="/root/other"' in searched, searched


def test_recommended_plugins_injection_is_not_a_user_message(tmp_path: Path):
    home = _write_home(tmp_path)
    for session_id in (ROOT_ID, CHILD_ID):
        output = _parse(home, session_id)
        assert "PLUGIN_NOISE_MARKER" not in output, f"Expected the harness injection hidden. Got:\n{output}"
    assert _search_ids(home, "PLUGIN_NOISE_MARKER") == set(), "Expected search to agree with parse."


def test_merged_subagent_task_is_the_leaders_task(tmp_path: Path):
    home = _write_home(tmp_path)
    output = _parse(home, ROOT_ID, "-a")
    tasks = [block.split("</subagent-task>", 1)[0] for block in output.split("<subagent-task>")[1:]]
    assert any("Sender: /root\n" in task for task in tasks), (
        f"Expected the leader's task as the child's subagent task. Got:\n{tasks}"
    )
    assert not any("PLUGIN_NOISE_MARKER" in task for task in tasks), f"Expected no harness injection. Got:\n{tasks}"


# ── inherited context ─────────────────────────────────────────────────────────


def test_forked_subagent_shows_its_whole_file(tmp_path: Path):
    """A direct fork view retains copied history as well as the child's own work."""
    home = _write_home(tmp_path)
    output = _parse(home, FORK_ID)
    for marker in ("FORK_OWN_MARKER", "INHERITED_PARENT_MARKER", "INHERITED_ASSISTANT_MARKER"):
        assert marker in output, f"Expected {marker} in the fork's own view. Got:\n{output}"
    assert _search_ids(home, "INHERITED_PARENT_MARKER") == {ROOT_ID, FORK_ID}, "Expected search to agree with parse."


def test_dot_projection_keeps_a_fork_with_only_copied_messages(tmp_path: Path):
    home = _write_home(tmp_path)
    fork = next((home / ".codex/sessions").rglob(f"*{FORK_ID}.jsonl"))
    fork.write_text("".join(json.dumps(entry) + "\n" for entry in FORK_ROLLOUT[:4]))
    assert "INHERITED_PARENT_MARKER" in _parse(home, FORK_ID)
    assert FORK_ID in _search_ids(home, "."), "The default dot projection must keep copied history too."


def test_merged_fork_block_omits_the_history_it_copied(tmp_path: Path):
    """Inside the parent's --agents view the copied records would repeat the parent's own."""
    home = _write_home(tmp_path)
    output = _parse(home, ROOT_ID, "-a")
    assert "FORK_OWN_MARKER" in output, f"Expected the fork's own work merged. Got:\n{output}"
    assert output.count("INHERITED_ASSISTANT_MARKER") == 1, f"Expected the parent's message once. Got:\n{output}"


# ── metadata ──────────────────────────────────────────────────────────────────


def _metadata(home: Path, session_id: str) -> str:
    result = _ch(home, session_id, "-l")
    return result.stdout + result.stderr


OWN_MARKERS = {CHILD_ID: "CHILD_WORK_MARKER", FORK_ID: "FORK_OWN_MARKER"}


def _search_metadata(home: Path, session_id: str) -> str:
    return _ch(home, "search", "-l", "-a", OWN_MARKERS[session_id]).stdout


def test_child_metadata_names_its_spawner(tmp_path: Path):
    home = _write_home(tmp_path)
    for read in (_metadata, _search_metadata):
        metadata = read(home, CHILD_ID)
        assert f"parent_session: {ROOT_ID}" in metadata, f"Expected the spawner via {read.__name__}. Got:\n{metadata}"
        assert "forked_from" not in metadata, f"Expected no fork source for a fresh child. Got:\n{metadata}"


def test_forked_child_metadata_names_its_context_source_and_point(tmp_path: Path):
    home = _write_home(tmp_path)
    for read in (_metadata, _search_metadata):
        metadata = read(home, FORK_ID)
        for line in (f"parent_session: {ROOT_ID}", f"forked_from: {ROOT_ID}", 'forked_at: "2026-09-16 12:40"'):
            assert line in metadata, f"Expected {line!r} via {read.__name__}. Got:\n{metadata}"


def test_root_metadata_has_no_lineage(tmp_path: Path):
    home = _write_home(tmp_path)
    metadata = _metadata(home, ROOT_ID)
    for field in ("parent_session", "forked_from", "forked_at"):
        assert field not in metadata, f"Expected no {field} on a root session. Got:\n{metadata}"


# ── merged descendants ────────────────────────────────────────────────────────


def test_search_agents_matches_a_parent_through_its_merged_descendants(tmp_path: Path):
    home = _write_home(tmp_path)
    assert _search_ids(home, "GRANDCHILD_MARKER") == {GRANDCHILD_ID}, "Expected only the child's own file without -a."
    assert _search_ids(home, "GRANDCHILD_MARKER", "-a") == {ROOT_ID, CHILD_ID, GRANDCHILD_ID}, (
        "Expected every ancestor to match through its merged block under -a."
    )
    assert _search_ids(home, "INHERITED_ASSISTANT_MARKER", "-a") == {ROOT_ID, FORK_ID}, (
        "Expected the merged fork block not to repeat the copied history."
    )


def test_search_agents_renders_the_same_merged_timeline_as_parse(tmp_path: Path):
    home = _write_home(tmp_path)
    parse_output = _parse(home, ROOT_ID, "-a", "--no-metadata")
    search_output = _ch(home, "search", "ROOT_ASSISTANT_MARKER", "-a", "-f", "--no-metadata").stdout
    for marker in ("<subagent-task>", "GRANDCHILD_MARKER", "FORK_OWN_MARKER", "CHILD_WORK_MARKER", 'name="Kant"'):
        assert parse_output.count(marker) == search_output.count(marker), (
            f"Expected parse and search -f to agree on {marker!r}.\nparse:\n{parse_output}\nsearch:\n{search_output}"
        )


def test_agents_merge_nested_subagents_with_their_role(tmp_path: Path):
    home = _write_home(tmp_path)
    output = _parse(home, ROOT_ID, "-a")
    assert "GRANDCHILD_MARKER" in output, f"Expected the depth-2 subagent merged into the root. Got:\n{output}"
    assert f'agent_id="{GRANDCHILD_ID}" subagent_type="explorer"' in output, (
        f"Expected the role from source.subagent.thread_spawn. Got:\n{output}"
    )


def test_recursive_merge_deduplicates_identity_and_stops_a_cycle(tmp_path: Path):
    home = _write_home(tmp_path)
    directory = home / ".codex/sessions/2026/09/16"
    child = next(directory.glob(f"*{CHILD_ID}.jsonl"))
    (directory / "duplicate-child.jsonl").write_text(child.read_text())
    root = next(directory.glob(f"*{ROOT_ID}.jsonl"))
    entries = [json.loads(line) for line in root.read_text().splitlines()]
    entries[0]["payload"]["parent_thread_id"] = GRANDCHILD_ID
    root.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    output = _parse(home, ROOT_ID, "-a")
    assert output.count("ROOT_ASSISTANT_MARKER") == 1, "A cyclic return must not append the root again."
    assert output.count("CHILD_WORK_MARKER") == 1, "Two files with one child ID must merge once."
    assert output.count("GRANDCHILD_MARKER") == 1
    result = _ch(home, "search", "GRANDCHILD_MARKER", "-a", "--only-id")
    assert result.returncode == 0 and ROOT_ID in result.stdout, result.stderr


def test_merged_follow_up_from_the_leader_is_a_subagent_task(tmp_path: Path):
    """A later instruction to a merged child is a task given to it, not the child speaking."""
    home = _write_home(tmp_path)
    output = _parse(home, ROOT_ID, "-a")
    tasks = [block.split("</subagent-task>", 1)[0] for block in output.split("<subagent-task>")[1:]]
    assert any("Message Type: MESSAGE" in task for task in tasks), (
        f"Expected the leader's follow-up inside a <subagent-task> block. Got:\n{output}"
    )
    assert sum("Message Type: MESSAGE" in task for task in tasks) == 1, (
        f"Expected the leader's follow-up as one task, distinct from incoming child messages. Got:\n{output}"
    )
