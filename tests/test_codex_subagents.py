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

PARENT_ID = "019eca84-83bd-7900-a142-04833f5ae1c6"
PLANCK_ID = "019ecaa3-3e57-7150-bb03-2c582bede7ba"
LEIBNIZ_ID = "019ecaa9-37d5-7822-9338-bbf5dbfcf5a1"


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(e) + "\n" for e in entries),
        encoding="utf-8",
    )


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
        [{
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "thread_source": "subagent",
                "parent_thread_id": parent,
                "agent_nickname": nickname,
                "agent_role": "default",
            },
        }],
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
    """Name, role, id come from session_meta; model from the turn_context entry."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = _rollout(tmp_path, LEIBNIZ_ID)
    _write_jsonl(path, [
        {
            "type": "session_meta",
            "payload": {
                "id": LEIBNIZ_ID,
                "thread_source": "subagent",
                "parent_thread_id": PARENT_ID,
                "agent_nickname": "Leibniz",
                "agent_role": "default",
            },
        },
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
    assert meta.model == "gpt-5.4-mini", f"Expected model from turn_context. Got: {meta.model}"


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
        {
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "thread_source": "subagent",
                "parent_thread_id": PARENT_ID,
                "agent_nickname": nickname,
                "agent_role": "default",
            },
        },
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
    assert all(m.model == "gpt-5.4-mini" for m in agent_messages), (
        f"Expected model='gpt-5.4-mini'. Got: {[m.model for m in agent_messages]}"
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
    """A parent that spawns/waits/closes an agent and receives a notification."""
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
                "call_id": "call_spawn",
                "arguments": '{"model":"gpt-5.4-mini","message":"do the thing"}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:06Z",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_spawn",
                "output": '{"agent_id":"019ecaa9","nickname":"Leibniz"}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:07Z",
            "payload": {
                "type": "function_call",
                "name": "wait_agent",
                "call_id": "call_wait",
                "arguments": '{"targets":["019ecaa9"]}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:08Z",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_wait",
                "output": '{"status":{"019ecaa9":{"completed":"did the thing"}}}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:09Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": '<subagent_notification>\n{"agent_path":"019ecaa9","status":{"completed":"did the thing"}}\n</subagent_notification>',
                }],
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:10Z",
            "payload": {
                "type": "function_call",
                "name": "close_agent",
                "call_id": "call_close",
                "arguments": '{"target":"019ecaa9"}',
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-06-15T12:00:11Z",
            "payload": {"type": "function_call_output", "call_id": "call_close", "output": "{}"},
        },
    ]


def test_codex_agent_plumbing_suppressed(tmp_path, monkeypatch):
    """spawn/wait/close calls and the subagent_notification never render, even with --tools."""
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

    for plumbing in ("spawn_agent", "wait_agent", "close_agent", "subagent_notification"):
        assert plumbing not in output, (
            f"Expected '{plumbing}' to be abstracted away by the agent block. Got:\n{output}"
        )


# =============================================================================
# Slice 7: gating matrix
# =============================================================================


def _codex_subagent_rollout_with_tool(session_id: str, nickname: str, prompt: str) -> list[dict]:
    return [
        {
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "thread_source": "subagent",
                "parent_thread_id": PARENT_ID,
                "agent_nickname": nickname,
                "agent_role": "default",
            },
        },
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
