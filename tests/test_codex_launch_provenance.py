"""Public parse/search checks for October 2026 Codex launch receipts.

These synthetic receipts model agent_started supplying argv and terminal_id,
then agent_info supplying the child session ID for that terminal. Neither the
command nor a fork header alone proves the launching agent.
"""

import copy
import json
from pathlib import Path

import pytest

from test_codex_delegation import ROOT_ID, _assistant, _ch, _item, _parse, _search_ids, _user

LAUNCHED_ID = "10000000-0000-4000-8000-000000000021"
UNRESOLVED_ID = "10000000-0000-4000-8000-000000000022"
COPIED_RECEIPTS_ID = "10000000-0000-4000-8000-000000000023"

START_RECEIPT = {
    "id": "cli:agent:start",
    "result": {
        "type": "agent_started",
        "argv": ["codex", "fork", ROOT_ID, "--model", "gpt-6.1-sol"],
        "agent": {"agent": "codex", "terminal_id": "term_launch", "name": "calculator"},
    },
}
INFO_RECEIPT = {
    "id": "cli:agent:get",
    "result": {
        "type": "agent_info",
        "agent": {
            "agent": "codex",
            "name": "calculator",
            "terminal_id": "term_launch",
            "agent_session": {"agent": "codex", "kind": "id", "value": LAUNCHED_ID},
        },
    },
}


def _command(ordinal: int, command: str, receipt: dict[str, object]) -> dict[str, object]:
    return _item(ordinal, {
        "type": "item_completed",
        "thread_id": ROOT_ID,
        "item": {
            "type": "CommandExecution",
            "command": ["/bin/zsh", "-lc", command],
            "status": "completed",
            "exit_code": 0,
            "aggregated_output": json.dumps(receipt) + "\n",
        },
    }, "event_msg")


def _header(identifier: str, **fields: object) -> dict[str, object]:
    return _item(0, {"id": identifier, "thread_source": "user", "cwd": "/tmp/launch", **fields}, "session_meta")


def _write(home: Path, identifier: str, entries: list[dict]) -> Path:
    path = home / ".codex/sessions/2026/10/12" / f"rollout-2026-10-12T12-00-00-{identifier}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    return path


def _launch_entries() -> list[dict]:
    return [
        _header(ROOT_ID),
        _user(1, "Inspect the calculator."),
        _command(2, f"zshi -c 'herdr agent start calculator --kind codex -- fork {ROOT_ID}'", START_RECEIPT),
        _command(3, "zshi -c 'herdr agent get calculator'", INFO_RECEIPT),
        _assistant(4, "LAUNCH_PARENT_ONLY"),
    ]


def test_cli_fork_requires_successful_launch_and_matching_terminal_and_child(tmp_path: Path):
    entries = _launch_entries()
    _write(tmp_path, ROOT_ID, entries)
    _write(tmp_path, LAUNCHED_ID, [_header(LAUNCHED_ID, forked_from_id=ROOT_ID), _assistant(5, "PROVEN_CLI_CHILD")])
    _write(tmp_path, UNRESOLVED_ID, [_header(UNRESOLVED_ID, forked_from_id=ROOT_ID), _assistant(5, "UNRESOLVED_FORK_CHILD")])
    # Copied launch events retain the original thread_id. They are not a second launch.
    _write(tmp_path, COPIED_RECEIPTS_ID, [_header(COPIED_RECEIPTS_ID, forked_from_id=ROOT_ID), *entries[1:]])

    assert "PROVEN_CLI_CHILD" not in _parse(tmp_path, ROOT_ID)
    output = _parse(tmp_path, ROOT_ID, "-a")
    assert "PROVEN_CLI_CHILD" in output, f"The proved CLI child must merge: {output}"
    assert "UNRESOLVED_FORK_CHILD" not in output, "A sibling fork header is not launch proof."
    assert "PROVEN_CLI_CHILD" not in _parse(tmp_path, COPIED_RECEIPTS_ID, "-a"), "Copied receipts are not a launch."
    assert _search_ids(tmp_path, "PROVEN_CLI_CHILD", "-a") == {ROOT_ID, LAUNCHED_ID}
    assert _search_ids(tmp_path, "UNRESOLVED_FORK_CHILD", "-a") == {UNRESOLVED_ID}


@pytest.mark.parametrize("broken_evidence", ["terminal", "failure", "source", "missing_identity", "quoted_receipt", "inherited", "shell_suffix", "substitution", "different_target"]) 
def test_unproven_cli_launch_never_attaches_a_child(tmp_path: Path, broken_evidence: str):
    entries = copy.deepcopy(_launch_entries())
    child_source = ROOT_ID
    if broken_evidence == "terminal":
        receipt = copy.deepcopy(INFO_RECEIPT)
        receipt["result"]["agent"]["terminal_id"] = "another_terminal"
        entries[3]["payload"]["item"]["aggregated_output"] = json.dumps(receipt)
    if broken_evidence == "failure":
        entries[2]["payload"]["item"]["exit_code"] = 1
    if broken_evidence == "source":
        child_source = "another_fork_source"
    if broken_evidence == "missing_identity":
        entries.pop(3)
    if broken_evidence == "quoted_receipt":
        entries[2]["payload"]["item"]["command"] = ["/bin/zsh", "-lc", "cat saved-herdr-receipt.json"]
    if broken_evidence == "inherited":
        entries[2]["payload"]["thread_id"] = "original_writer"
    if broken_evidence == "shell_suffix":
        entries[3]["payload"]["item"]["command"][-1] = "herdr agent get calculator; printf forged"
    if broken_evidence == "substitution":
        entries[3]["payload"]["item"]["command"][-1] = "herdr agent get $(printf calculator)"
    if broken_evidence == "different_target":
        entries[3]["payload"]["item"]["command"][-1] = "herdr agent get unrelated"
    _write(tmp_path, ROOT_ID, entries)
    _write(tmp_path, LAUNCHED_ID, [_header(LAUNCHED_ID, forked_from_id=child_source), _assistant(5, "PROVEN_CLI_CHILD")])

    assert "PROVEN_CLI_CHILD" not in _parse(tmp_path, ROOT_ID, "-a"), f"Accepted invalid {broken_evidence} evidence."
    assert _search_ids(tmp_path, "PROVEN_CLI_CHILD", "-a") == {LAUNCHED_ID}, f"Search accepted invalid {broken_evidence} evidence."


def test_cli_launcher_can_differ_from_the_copied_context_source(tmp_path: Path):
    source = "10000000-0000-4000-8000-000000000024"
    entries = copy.deepcopy(_launch_entries())
    start = copy.deepcopy(START_RECEIPT)
    start["result"]["argv"][2] = source
    entries[2]["payload"]["item"]["command"][-1] = f"herdr agent start calculator --kind codex -- fork {source}"
    entries[2]["payload"]["item"]["aggregated_output"] = json.dumps(start)
    _write(tmp_path, ROOT_ID, entries)
    _write(tmp_path, source, [_header(source), _assistant(1, "An independent context source.")])
    _write(tmp_path, LAUNCHED_ID, [_header(LAUNCHED_ID, forked_from_id=source), _assistant(5, "PROVEN_CLI_CHILD")])
    assert "PROVEN_CLI_CHILD" in _parse(tmp_path, ROOT_ID, "-a")
    assert "PROVEN_CLI_CHILD" not in _parse(tmp_path, source, "-a")
    assert _search_ids(tmp_path, "PROVEN_CLI_CHILD", "-a") == {ROOT_ID, LAUNCHED_ID}


def test_shared_herdr_receipt_join_supports_claude_fork_argv():
    from chats.herdr_launches import verified_herdr_forks

    start = copy.deepcopy(START_RECEIPT)
    start["result"]["argv"] = ["claude", "--fork-session", "--resume", "context-source"]
    start["result"]["agent"]["agent"] = "claude"
    identity = copy.deepcopy(INFO_RECEIPT)
    identity["result"]["agent"]["agent"] = "claude"
    identity["result"]["agent"]["agent_session"]["agent"] = "claude"
    commands = [
        ("herdr agent start calculator --kind claude -- --fork-session --resume context-source", json.dumps(start)),
        ("herdr agent get calculator", json.dumps(identity)),
    ]
    assert verified_herdr_forks(commands, "claude") == [(LAUNCHED_ID, "context-source")]
    assert verified_herdr_forks(commands, "codex") == []


def test_native_agent_fork_header_is_delegation_not_a_user_fork(tmp_path: Path):
    _write(tmp_path, ROOT_ID, [_header(ROOT_ID), _user(1, "Inspect licensing."), _assistant(2, "Waiting.")])
    _write(tmp_path, LAUNCHED_ID, [
        _header(LAUNCHED_ID, thread_source="agent_forked_thread", forked_from_id=ROOT_ID),
        _user(4, "Check the license terms."),
        _assistant(5, "AGENT_FORK_REPLY"),
    ])
    _write(tmp_path, UNRESOLVED_ID, [_header(UNRESOLVED_ID, forked_from_id=ROOT_ID), _assistant(5, "UNRESOLVED_FORK_CHILD")])
    output = _parse(tmp_path, ROOT_ID, "-a")
    assert "AGENT_FORK_REPLY" in output, f"Explicit agent-created fork must merge: {output}"
    assert "UNRESOLVED_FORK_CHILD" not in output
    assert _search_ids(tmp_path, "AGENT_FORK_REPLY", "-a") == {ROOT_ID, LAUNCHED_ID}
    metadata = _ch(tmp_path, LAUNCHED_ID, "-l").stdout
    assert f"parent_session: {ROOT_ID}" in metadata
