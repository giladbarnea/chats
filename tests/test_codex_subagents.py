#!/usr/bin/env python3
"""Tests for Codex subagent support: discovery, metadata, merge, and rendering."""

import json
from pathlib import Path

from chats import ConversationFlags, parsing
from chats.commands import _merge_agent_messages
from chats.formatting import format_to_xml


def _merge_codex(parent: Path, flags: ConversationFlags):
    """Parse a parent session and merge subagents, mirroring cmd_parse's --agents gate."""
    messages = parsing.parse_jsonl(parent.read_text(), flags, source_path=parent)
    if flags.show_agents:
        messages = _merge_agent_messages(messages, parent, flags)
    return messages

PARENT_ID = "50000000-0000-4000-8000-000000000001"
PLANCK_ID = "50000000-0000-4000-8000-000000000002"
LEIBNIZ_ID = "50000000-0000-4000-8000-000000000003"


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(e) + "\n" for e in entries),
        encoding="utf-8",
    )


def _subagent_meta(session_id: str, nickname: str, parent: str = PARENT_ID) -> dict:
    """A current subagent header: identity lives in source.subagent.thread_spawn."""
    return {
        "type": "session_meta",
        "payload": {
            "id": session_id,
            "thread_source": "subagent",
            "parent_thread_id": parent,
            "agent_nickname": nickname,
            "agent_role": "default",
            "source": {"subagent": {"thread_spawn": {
                "parent_thread_id": parent,
                "depth": 1,
                "agent_path": f"/root/{nickname.lower()}",
                "agent_nickname": nickname,
                "agent_role": "default",
            }}},
        },
    }


def _codex_sessions_dir(home: Path) -> Path:
    return home / ".codex" / "sessions" / "2026" / "06" / "15"


def _rollout(home: Path, session_id: str) -> Path:
    return _codex_sessions_dir(home) / f"rollout-2026-06-15T12-00-00-{session_id}.jsonl"


def _write_parent(home: Path) -> Path:
    path = _rollout(home, PARENT_ID)
    _write_jsonl(
        path,
        [{"type": "session_meta", "payload": {"id": PARENT_ID, "thread_source": "user"}}],
    )
    return path


def _write_subagent(home: Path, session_id: str, nickname: str, parent: str = PARENT_ID) -> Path:
    path = _rollout(home, session_id)
    _write_jsonl(
        path,
        [_subagent_meta(session_id, nickname, parent)],
    )
    return path


# =============================================================================
# Slice 1: discovery by parent_thread_id
# =============================================================================


def test_finds_codex_subagent_transcripts_by_parent_thread_id(tmp_path, monkeypatch):
    """Codex subagent rollouts are linked to their parent via session_meta.parent_thread_id."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    parent = _write_parent(tmp_path)
    planck = _write_subagent(tmp_path, PLANCK_ID, "Planck")
    leibniz = _write_subagent(tmp_path, LEIBNIZ_ID, "Leibniz")
    # An unrelated subagent belonging to a different parent session.
    _write_subagent(tmp_path, "deadbeef-other", "Stranger", parent="some-other-parent")

    result = parsing.find_codex_subagent_transcripts(parent, PARENT_ID)
    found = sorted(p.name for p in result)
    expected = sorted([planck.name, leibniz.name])
    assert found == expected, (
        f"Expected the two subagents linked to {PARENT_ID}, excluding the stranger. "
        f"Got: {found}"
    )


def test_codex_session_without_subagents_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    parent = _write_parent(tmp_path)

    result = parsing.find_codex_subagent_transcripts(parent, PARENT_ID)
    assert result == [], f"Expected no subagents for a plain session. Got: {result}"


# =============================================================================
# Slice 2: subagent metadata extraction
# =============================================================================


def test_extracts_codex_subagent_metadata(tmp_path, monkeypatch):
    """Name and role come from the spawn record, id from session_meta."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(path, [
        _subagent_meta(LEIBNIZ_ID, "Leibniz"),
        {"type": "turn_context", "payload": {"model": "gpt-5.4-mini"}},
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "do stuff"}],
            },
        },
    ])

    meta = parsing.extract_codex_subagent_metadata(path)
    assert meta.agent_id == LEIBNIZ_ID, f"Expected agent_id from session_meta.id. Got: {meta.agent_id}"
    assert meta.name == "Leibniz", f"Expected nickname 'Leibniz'. Got: {meta.name}"
    assert meta.subagent_type == "default", f"Expected agent_role as subagent_type. Got: {meta.subagent_type}"


# =============================================================================
# Slice 3: adapter-driven merge tags Codex agent messages
# =============================================================================


def _codex_parent_rollout() -> list[dict]:
    return [
        {"type": "session_meta", "payload": {"id": PARENT_ID, "thread_source": "user"}},
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:00Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "please spawn leibniz"}],
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:05Z",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "spawning now"}],
            },
        },
    ]


def _codex_subagent_rollout(session_id: str, nickname: str, prompt: str, reply: str) -> list[dict]:
    return [
        _subagent_meta(session_id, nickname, PARENT_ID),
        {"type": "turn_context", "payload": {"model": "gpt-5.4-mini"}},
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:42:30Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:42:35Z",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": reply}],
            },
        },
    ]


def test_codex_subagent_merge_tags_agent_messages(tmp_path, monkeypatch):
    """Merging pulls the Codex subagent transcript in and stamps identity onto its messages."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    parent = _rollout(tmp_path, PARENT_ID)
    _write_jsonl(parent, _codex_parent_rollout())
    leibniz = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(
        leibniz,
        _codex_subagent_rollout(LEIBNIZ_ID, "Leibniz", "do the thing", "did the thing"),
    )

    flags = ConversationFlags(show_agents=True, color="never")
    messages = parsing.parse_jsonl(parent.read_text(), flags, source_path=parent)
    merged = _merge_agent_messages(messages, parent, flags)

    agent_messages = [m for m in merged if m.agent_id == LEIBNIZ_ID]
    assert agent_messages, (
        f"Expected merged Leibniz messages tagged with agent_id={LEIBNIZ_ID}. "
        f"Got: {[(m.role, m.agent_id) for m in merged]}"
    )
    assert all(m.subagent_type == "default" for m in agent_messages), (
        f"Expected subagent_type='default'. Got: {[m.subagent_type for m in agent_messages]}"
    )
    assert all(m.name == "Leibniz" for m in agent_messages), (
        f"Expected name='Leibniz'. Got: {[m.name for m in agent_messages]}"
    )
    rendered = format_to_xml(merged, flags)
    assert "gpt-5.4-mini" not in rendered, (
        f"Expected the merged agent to carry no model id from turn_context. Got:\n{rendered}"
    )
    assert any("did the thing" in (m.text or "") for m in agent_messages), (
        "Expected the agent's reply text to survive the merge."
    )


# =============================================================================
# Slice 4: the initiating prompt renders as an always-on <subagent-task> block
# =============================================================================


def test_subagent_task_block_rendered_once_regardless_of_tools(tmp_path, monkeypatch):
    """The prompt given to the subagent renders as <subagent-task>, never as a bare
    agent line, and is present with or without --tools."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    parent = _rollout(tmp_path, PARENT_ID)
    _write_jsonl(parent, _codex_parent_rollout())
    leibniz = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(
        leibniz,
        _codex_subagent_rollout(
            LEIBNIZ_ID, "Leibniz", "exercise the filesystem tools", "did the thing"
        ),
    )

    for show_tools in (False, True):
        flags = ConversationFlags(show_agents=True, show_tools=show_tools, color="never")
        output = format_to_xml(_merge_codex(parent, flags), flags)

        assert "<subagent-task>" in output, (
            f"Expected a <subagent-task> block (show_tools={show_tools}). Got:\n{output}"
        )
        assert "exercise the filesystem tools" in output, (
            f"Expected the prompt inside the task block (show_tools={show_tools}). Got:\n{output}"
        )
        assert output.count("exercise the filesystem tools") == 1, (
            "Expected the prompt to appear exactly once (only inside <subagent-task>), "
            f"never duplicated as a bare agent line (show_tools={show_tools}). Got:\n{output}"
        )


# =============================================================================
# Slice 5: agent block presentation (name attr, named header, 2-space indent)
# =============================================================================


def test_codex_agent_block_named_and_indented(tmp_path, monkeypatch):
    """The agent block carries the nickname (attr + header) and indents its inner content."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    parent = _rollout(tmp_path, PARENT_ID)
    _write_jsonl(parent, _codex_parent_rollout())
    leibniz = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(
        leibniz,
        _codex_subagent_rollout(LEIBNIZ_ID, "Leibniz", "do the thing", "did the thing"),
    )

    flags = ConversationFlags(show_agents=True, color="never")
    output = format_to_xml(_merge_codex(parent, flags), flags)

    assert 'name="Leibniz"' in output, f"Expected name attribute on the agent tag. Got:\n{output}"
    assert "## Agent 'Leibniz'" in output, f"Expected the nickname in the header. Got:\n{output}"
    assert "\n  <subagent-task>" in output, (
        f"Expected the subagent-task block indented 2 spaces inside the agent block. Got:\n{output}"
    )
    assert "\n  did the thing" in output, (
        f"Expected the agent's reply text indented 2 spaces. Got:\n{output}"
    )


# =============================================================================
# Slice 6: agent-lifecycle plumbing is abstracted away
# =============================================================================


def _codex_parent_rollout_with_plumbing() -> list[dict]:
    """A parent that spawns and waits on an agent, then receives its final answer."""
    return [
        {"type": "session_meta", "payload": {"id": PARENT_ID, "thread_source": "user"}},
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:00Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "please spawn leibniz"}],
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:05Z",
            "payload": {
                "type": "function_call",
                "name": "spawn_agent",
                "namespace": "collaboration",
                "call_id": "call_spawn",
                "arguments": '{"task_name":"leibniz","fork_turns":"none","message":"gAAAAABcipher"}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:06Z",
            "payload": {"type": "function_call_output", "call_id": "call_spawn", "output": '{"task_name":"/root/leibniz"}'},
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:07Z",
            "payload": {
                "type": "function_call",
                "name": "wait_agent",
                "namespace": "collaboration",
                "call_id": "call_wait",
                "arguments": '{"timeout_ms":1000}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:08Z",
            "payload": {"type": "function_call_output", "call_id": "call_wait", "output": '{"message":"Wait completed.","timed_out":false}'},
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:09Z",
            "payload": {
                "type": "agent_message",
                "author": "/root/leibniz",
                "recipient": "/root",
                "content": [{"type": "input_text", "text": "Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/leibniz\nPayload:\nFINAL_ANSWER_MARKER"}],
            },
        },
    ]


def test_codex_agent_controls_and_delivered_reports_are_visible(tmp_path, monkeypatch):
    """The parent retains delivered reports independently of the merged child transcript."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    parent = _rollout(tmp_path, PARENT_ID)
    _write_jsonl(parent, _codex_parent_rollout_with_plumbing())
    leibniz = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(
        leibniz,
        _codex_subagent_rollout(LEIBNIZ_ID, "Leibniz", "do the thing", "did the thing"),
    )

    flags = ConversationFlags(show_agents=True, show_tools=True, color="never")
    output = format_to_xml(_merge_codex(parent, flags), flags)

    assert output.count("did the thing") == 1, f"Expected the child's reply once, in its block. Got:\n{output}"
    assert "FINAL_ANSWER_MARKER" in output, "A delivered report must survive independently of child merging."
    for control in ("spawn_agent", "wait_agent"):
        assert control in output, f"Expected '{control}' with --agents. Got:\n{output}"


# =============================================================================
# Slice 7: gating matrix
# =============================================================================


def _codex_subagent_rollout_with_tool(session_id: str, nickname: str, prompt: str) -> list[dict]:
    return [
        _subagent_meta(session_id, nickname, PARENT_ID),
        {"type": "turn_context", "payload": {"model": "gpt-5.4-mini"}},
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:42:30Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:42:33Z",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "running a command"}],
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:42:34Z",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "call_bash",
                "arguments": '{"cmd":"echo hello-from-leibniz"}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:42:35Z",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_bash",
                "output": "hello-from-leibniz",
            },
        },
    ]


def test_codex_gating_matrix(tmp_path, monkeypatch):
    """tools never gate agent presence; --agents shows the cycle; -t adds the agent's tools."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    parent = _rollout(tmp_path, PARENT_ID)
    _write_jsonl(parent, _codex_parent_rollout_with_plumbing())
    leibniz = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(leibniz, _codex_subagent_rollout_with_tool(LEIBNIZ_ID, "Leibniz", "do the thing"))

    def render(**flag_kwargs: bool) -> str:
        flags = ConversationFlags(color="never", **flag_kwargs)
        return format_to_xml(_merge_codex(parent, flags), flags)

    default = render()
    assert "## Agent" not in default and "<subagent-task>" not in default, (
        f"default: expected no agents at all. Got:\n{default}"
    )

    tools_only = render(show_tools=True)
    assert "## Agent" not in tools_only, f"-t only: expected no agents. Got:\n{tools_only}"
    assert "spawn_agent" not in tools_only, f"-t only: plumbing must stay hidden. Got:\n{tools_only}"

    agents_only = render(show_agents=True)
    assert "## Agent 'Leibniz'" in agents_only and "<subagent-task>" in agents_only, (
        f"--agents: expected the agent block and its task. Got:\n{agents_only}"
    )
    assert 'tool-input name="Bash"' not in agents_only, (
        f"--agents without -t must NOT show the agent's tools. Got:\n{agents_only}"
    )

    agents_tools = render(show_agents=True, show_tools=True)
    assert 'tool-input name="Bash"' in agents_tools and "hello-from-leibniz" in agents_tools, (
        f"--agents -t must show the agent's tools, filtered like main. Got:\n{agents_tools}"
    )
