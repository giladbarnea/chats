#!/usr/bin/env python3
"""A forked Claude session shows its whole file and names its parent.

`claude --resume <parent> --fork-session` and `/branch` copy the parent's whole
transcript into the child file. Each copied record keeps the snake_case
`session_id` of the session that wrote it, while camelCase `sessionId` is
rewritten to the child. `ch` shows the copied history like any other content,
and the child's metadata names the parent as `forked_from` with `forked_at`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CH_EXECUTABLE = Path(sys.executable).with_name("ch")
PARENT_ID = "11111111-1111-4111-8111-111111111111"
CHILD_ID = "22222222-2222-4222-8222-222222222222"
UNRELATED_ID = "33333333-3333-4333-8333-333333333333"
PROJECT = "-Users-tester-project"


def _record(kind: str, uuid: str, parent_uuid: str | None, text: str, writer: str | None, owner: str) -> dict:
    """One Claude conversation record; `writer` is the snake_case provenance tag."""
    content = text if kind == "user" else [{"type": "text", "text": text}]
    record = {
        "type": kind,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "sessionId": owner,
        "timestamp": f"2026-10-13T10:{int(uuid[-2:]):02d}:00.000Z",
        "message": {"role": kind, "content": content},
    }
    if writer is not None:
        record["session_id"] = writer
    return record


def _parent_records(owner: str) -> list[dict]:
    return [
        _record("user", "u-01", None, "PARENT_PROMPT_MARKER", PARENT_ID, owner),
        _record("assistant", "u-02", "u-01", "PARENT_REPLY_MARKER", PARENT_ID, owner),
        # An untagged inherited record inside the prefix.
        _record("user", "u-03", "u-02", "PARENT_UNTAGGED_MARKER", None, owner),
        _record("assistant", "u-04", "u-03", "PARENT_LAST_REPLY_MARKER", PARENT_ID, owner),
    ]


def _child_records() -> list[dict]:
    inherited = _parent_records(CHILD_ID)
    # Claude writes a recap into the parent while it idles; the fork copies it
    # untagged right after the last tagged parent record.
    recap = {
        "type": "system",
        "subtype": "away_summary",
        "content": "PARENT_RECAP_MARKER",
        "uuid": "u-05",
        "parentUuid": "u-04",
        "sessionId": CHILD_ID,
        "timestamp": "2026-10-13T10:05:00.000Z",
    }
    own = [
        _record("user", "u-06", "u-05", "CHILD_PROMPT_MARKER", None, CHILD_ID),
        _record("assistant", "u-07", "u-06", "CHILD_REPLY_MARKER", CHILD_ID, CHILD_ID),
    ]
    return [*inherited, recap, *own]


def _write(home: Path, session_id: str, records: list[dict]) -> Path:
    path = home / ".claude" / "projects" / PROJECT / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    _write(home, PARENT_ID, _parent_records(PARENT_ID))
    _write(home, CHILD_ID, _child_records())
    return home


def _run(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CH_EXECUTABLE), *arguments],
        cwd=Path(__file__).parent.parent,
        env={**os.environ, "HOME": str(home), "TZ": "Asia/Jerusalem"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_parse_shows_the_whole_fork_file(tmp_path: Path):
    """The copied parent history stays visible: a fork shows its whole file."""
    home = _home(tmp_path)
    output = _run(home, CHILD_ID, "--color", "never", "--no-metadata").stdout

    for marker in ("PARENT_PROMPT_MARKER", "PARENT_LAST_REPLY_MARKER", "CHILD_PROMPT_MARKER", "CHILD_REPLY_MARKER"):
        assert marker in output, f"Expected {marker} in the fork's output. Got:\n{output}"


def test_parse_metadata_names_the_parent(tmp_path: Path):
    home = _home(tmp_path)
    child = _run(home, CHILD_ID, "-l").stdout
    parent = _run(home, PARENT_ID, "-l").stdout

    assert f"forked_from: {PARENT_ID}" in child, f"Expected forked_from in child metadata. Got:\n{child}"
    assert "forked_from" not in parent, f"Expected no forked_from on the parent. Got:\n{parent}"


def test_search_finds_copied_text_in_parent_and_fork(tmp_path: Path):
    home = _home(tmp_path)
    copied = _run(home, "search", "PARENT_REPLY_MARKER", "--only-id")
    own = _run(home, "search", "CHILD_REPLY_MARKER", "--only-id")

    assert sorted(copied.stdout.split()) == sorted([PARENT_ID, CHILD_ID]), (
        f"Expected copied text to match parent and fork. stdout: {copied.stdout!r}; stderr: {copied.stderr!r}."
    )
    assert own.stdout.split() == [CHILD_ID], (
        f"Expected the fork to match its own text. stdout: {own.stdout!r}; stderr: {own.stderr!r}."
    )


def test_search_list_names_the_parent(tmp_path: Path):
    home = _home(tmp_path)
    listing = _run(home, "search", "CHILD_REPLY_MARKER", "-l", "--color", "never").stdout

    assert f"forked_from: {PARENT_ID}" in listing, f"Expected forked_from in the search listing. Got:\n{listing}"


def test_untagged_fork_family_does_not_invent_lineage_from_shared_uuids(tmp_path: Path):
    evidence = json.loads((Path(__file__).parent / "data/claude-delegation-provenance.json").read_text())
    family = evidence["untagged_fork_family"]
    assert len(set(family["child_session_ids"])) == 5
    assert family["parent_session_id"] not in family["child_session_ids"]
    home = tmp_path / "home"
    for identity in [family["parent_session_id"], *family["child_session_ids"]]:
        records = [
            _record("user", "u-01", None, "SHARED_HISTORY_MARKER", None, identity),
            _record("assistant", "u-02", "u-01", "SHARED_REPLY_MARKER", None, identity),
            _record("user", "u-03", "u-02", f"OWN_WORK_{identity}", identity, identity),
        ]
        for record in records:
            record["version"] = family["creation_version"]
            record["timestamp"] = family["created_date"] + "T06:30:14.000Z"
        _write(home, identity, records)
    for child in family["child_session_ids"]:
        metadata = _run(home, child, "--only-metadata").stdout
        assert "forked_from" not in metadata and "parent_session" not in metadata, metadata
        assert "SHARED_HISTORY_MARKER" in _run(home, child, "--raw").stdout
    parent_output = _run(home, family["parent_session_id"], "--agents", "--raw").stdout
    assert not any(f"OWN_WORK_{child}" in parent_output for child in family["child_session_ids"]), parent_output


def test_a_session_quoting_another_session_id_is_not_a_fork(tmp_path: Path):
    """Only the provenance tag counts. Records tagged with their own id stay."""
    home = tmp_path / "home"
    records = [
        _record("user", "u-01", None, f"look at {PARENT_ID}", UNRELATED_ID, UNRELATED_ID),
        _record("assistant", "u-02", "u-01", "UNRELATED_REPLY_MARKER", UNRELATED_ID, UNRELATED_ID),
    ]
    _write(home, UNRELATED_ID, records)
    output = _run(home, UNRELATED_ID, "--color", "never").stdout + _run(home, UNRELATED_ID, "-l").stdout

    assert "UNRELATED_REPLY_MARKER" in output and "forked_from" not in output, (
        f"Expected an ordinary session untouched. Got:\n{output}"
    )


def test_parse_metadata_marks_the_fork_point(tmp_path: Path):
    """`forked_at` is the time of the last copied parent record, in the `created` format."""
    home = _home(tmp_path)
    child = _run(home, CHILD_ID, "-l").stdout

    # u-04 is the last tagged parent record: 2026-10-13T10:04Z, shown in Asia/Jerusalem.
    assert 'forked_at: "2026-10-13 13:04"' in child, f"Expected forked_at in child metadata. Got:\n{child}"
    assert "parent_session" not in child, (
        f"Expected no parent_session: a forked file does not prove who spawned it. Got:\n{child}"
    )


def _write_sidechain(home: Path, name: str, records: list[dict]) -> Path:
    path = home / ".claude" / "projects" / PROJECT / PARENT_ID / "subagents" / f"agent-{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def _sidechain_record(agent_id: str) -> dict:
    return {
        "type": "user",
        "isSidechain": True,
        "agentId": agent_id,
        "sessionId": PARENT_ID,
        "uuid": "s-01",
        "parentUuid": None,
        "timestamp": "2026-10-13T11:00:00.000Z",
        "message": {"role": "user", "content": "SIDECHAIN_TASK_MARKER"},
    }


def test_subagent_metadata_names_its_parent_session(tmp_path: Path):
    """A subagent transcript proves its spawner: the parent session it lives under and names."""
    home = _home(tmp_path)
    agent = _write_sidechain(home, "a0123456789abcdef", [_sidechain_record("a0123456789abcdef")])
    metadata = _run(home, str(agent), "-l").stdout

    assert f"parent_session: {PARENT_ID}" in metadata, f"Expected parent_session. Got:\n{metadata}"
    assert "forked_from" not in metadata, f"Expected a fresh-context subagent not to be a fork. Got:\n{metadata}"


def test_fork_subagent_metadata_names_its_parent_twice(tmp_path: Path):
    """A fork subagent was spawned by its parent and copies its context, so both fields name it."""
    home = _home(tmp_path)
    fork_ref = {
        "type": "fork-context-ref",
        "agentId": "ado-it-0123456789abcdef",
        "parentSessionId": PARENT_ID,
        "parentLastUuid": "u-04",
        "contextLength": 4,
    }
    agent = _write_sidechain(home, "ado-it-0123456789abcdef", [fork_ref, _sidechain_record("ado-it-0123456789abcdef")])
    metadata = _run(home, str(agent), "-l").stdout
    listing = _run(home, "search", "SIDECHAIN_TASK_MARKER", "--agents", "-l", "--color", "never").stdout

    assert f"parent_session: {PARENT_ID}" in metadata and f"forked_from: {PARENT_ID}" in metadata, metadata
    assert f"session_id: {PARENT_ID}" in listing, listing
    assert "agent-ado-it-0123456789abcdef" in listing, listing
