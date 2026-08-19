#!/usr/bin/env python3
"""Provider selection for session files outside native storage paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import ConversationFlags, cmd_parse
from chats.model import ParseOutputMode
from chats.parsing import get_jsonl_session_adapter


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write compact JSONL entries to a test session path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_external_pi_session_is_detected_from_its_first_entry(
    tmp_path: Path,
    capsys,
) -> None:
    """A copied Pi session should parse without living under ~/.pi/."""
    session_path = tmp_path / "avidor" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "0f408325-0d79-4781-bdcd-9dccf4acc2d1",
                "timestamp": "2026-08-04T13:56:02.355Z",
                "cwd": "/opt/avidor/workdir",
            },
            {
                "type": "message",
                "id": "user-1",
                "parentId": None,
                "timestamp": "2026-08-04T13:56:03.355Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "external Pi prompt"}],
                    "timestamp": 1785851763355,
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "external Pi prompt" in captured.out, (
        "Expected the external Pi header signature to select the Pi parser. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_external_codex_session_is_detected_from_its_first_entry(
    tmp_path: Path,
    capsys,
) -> None:
    """A copied Codex session should parse without living under ~/.codex/."""
    session_path = tmp_path / "export" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-08-04T13:56:02.355Z",
                "type": "session_meta",
                "payload": {
                    "id": "01961abc-def0-7123-89ab-codexexternal1",
                    "cwd": "/opt/export/workdir",
                },
            },
            {
                "timestamp": "2026-08-04T13:56:03.355Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "external Codex prompt"}
                    ],
                },
            },
        ],
    )

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(session_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    assert "external Codex prompt" in captured.out, (
        "Expected the external Codex header signature to select the Codex parser. "
        f"Got stdout:\n{captured.out}\nstderr:\n{captured.err}"
    )


def test_native_path_takes_precedence_over_first_entry_signature(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A recognized provider path should win over a conflicting content signature."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    session_path = home / ".claude" / "projects" / "demo" / "session.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "session",
                "version": 3,
                "id": "pi-shaped-content",
                "timestamp": "2026-08-04T13:56:02.355Z",
                "cwd": "/tmp/demo",
            }
        ],
    )

    adapter = get_jsonl_session_adapter(session_path)

    assert adapter.name == "claude", (
        "Expected the recognized Claude path to override the conflicting Pi header. "
        f"Got provider: {adapter.name!r}"
    )


def test_canonical_native_roots_keep_provider_precedence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Canonical native roots should keep Codex before Pi before Claude."""
    home = tmp_path / "home"
    shared_root = tmp_path / "shared-sessions"
    shared_root.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    codex_parent = home / ".codex"
    claude_parent = home / ".claude"
    codex_parent.mkdir(parents=True)
    claude_parent.mkdir(parents=True)
    (codex_parent / "sessions").symlink_to(shared_root, target_is_directory=True)
    (home / ".pi").symlink_to(shared_root, target_is_directory=True)
    (claude_parent / "projects").symlink_to(shared_root, target_is_directory=True)

    session_path = shared_root / "session.jsonl"
    _write_jsonl(
        session_path,
        [{"type": "session", "version": 3, "id": "pi-shaped-content"}],
    )

    adapter = get_jsonl_session_adapter(session_path)

    assert adapter.name == "codex", (
        "Expected canonical containment to use Codex before the overlapping Pi "
        f"and Claude roots. Got provider: {adapter.name!r}"
    )


def test_native_symlink_uses_its_canonical_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A native-looking symlink should classify its target, not its link path."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    external_path = tmp_path / "external" / "session.jsonl"
    _write_jsonl(
        external_path,
        [{"type": "session", "version": 3, "id": "external-pi-session"}],
    )
    native_link = home / ".claude" / "projects" / "demo" / "session.jsonl"
    native_link.parent.mkdir(parents=True)
    native_link.symlink_to(external_path)

    adapter = get_jsonl_session_adapter(native_link)

    assert adapter.name == "pi", (
        "Expected a Claude-root symlink targeting an external Pi session to use "
        f"the Pi header fallback. Got provider: {adapter.name!r}"
    )


def test_missing_native_leaf_uses_its_existing_canonical_ancestor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A missing native leaf should classify like Path.resolve(strict=False)."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    (home / ".claude" / "projects").mkdir(parents=True)
    missing_path = home / ".claude" / "projects" / "demo" / "missing.jsonl"

    adapter = get_jsonl_session_adapter(missing_path)

    assert adapter.name == "claude", (
        "Expected the missing leaf below the canonical Claude root to retain its "
        f"native provider. Got provider: {adapter.name!r}"
    )


def test_missing_native_tail_normalizes_parent_components(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A missing tail should preserve parent components until normalization."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    (home / ".claude" / "projects").mkdir(parents=True)
    missing_path = (
        home
        / ".claude"
        / "projects"
        / "missing"
        / ".."
        / "demo"
        / "session.jsonl"
    )

    adapter = get_jsonl_session_adapter(missing_path)

    assert adapter.name == "claude", (
        "Expected the normalized missing tail to stay below the Claude root. "
        f"Got provider: {adapter.name!r}"
    )


@pytest.mark.parametrize("target_exists", [True, False])
def test_normalized_missing_tail_follows_a_later_symlink(
    tmp_path: Path,
    monkeypatch,
    target_exists: bool,
) -> None:
    """Strict-false resolution should follow symlinks reached after `..`."""
    home = tmp_path / "home"
    native_root = home / ".claude" / "projects"
    external_root = tmp_path / "external"
    native_root.mkdir(parents=True)
    external_root.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    (native_root / "link").symlink_to(external_root, target_is_directory=True)
    session_path = native_root / "missing" / ".." / "link" / "session.jsonl"

    if target_exists:
        _write_jsonl(
            external_root / "session.jsonl",
            [{"type": "session", "version": 3, "id": "external-pi-session"}],
        )

    with pytest.raises(ValueError, match="Cannot determine JSONL session provider"):
        get_jsonl_session_adapter(session_path)


@pytest.mark.parametrize(
    "tail_parts",
    [("link", "session.jsonl"), ("link", "..", "session.jsonl")],
)
def test_dangling_native_symlink_resolves_its_external_target(
    tmp_path: Path,
    monkeypatch,
    tail_parts: tuple[str, ...],
) -> None:
    """Strict-false resolution should follow a symlink to a missing target."""
    home = tmp_path / "home"
    native_root = home / ".claude" / "projects"
    native_root.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    (native_root / "link").symlink_to(
        tmp_path / "missing-external-directory",
        target_is_directory=True,
    )
    session_path = native_root.joinpath(*tail_parts)

    with pytest.raises(ValueError, match="Cannot determine JSONL session provider"):
        get_jsonl_session_adapter(session_path)


def test_native_symlink_loop_preserves_unresolved_native_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Bounded loop handling should match Python 3.13 strict-false resolution."""
    home = tmp_path / "home"
    native_root = home / ".claude" / "projects"
    native_root.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    (native_root / "a").symlink_to("b", target_is_directory=True)
    (native_root / "b").symlink_to("a", target_is_directory=True)

    adapter = get_jsonl_session_adapter(native_root / "a" / "session.jsonl")

    assert adapter.name == "claude", (
        "Expected bounded loop resolution to preserve the unresolved native path. "
        f"Got provider: {adapter.name!r}"
    )


def test_missing_tail_below_a_symlinked_native_root_keeps_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Missing tails should append after resolving a symlinked native root."""
    home = tmp_path / "home"
    shared_root = tmp_path / "shared-claude-projects"
    shared_root.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    claude_parent = home / ".claude"
    claude_parent.mkdir(parents=True)
    (claude_parent / "projects").symlink_to(shared_root, target_is_directory=True)
    missing_path = claude_parent / "projects" / "demo" / "missing.jsonl"

    adapter = get_jsonl_session_adapter(missing_path)

    assert adapter.name == "claude", (
        "Expected the missing tail below the symlinked Claude root to retain its "
        f"native provider. Got provider: {adapter.name!r}"
    )


def test_pi_signature_requires_an_integer_version(tmp_path: Path) -> None:
    """A Pi-shaped header with a string version should remain unrecognized."""
    session_path = tmp_path / "pi-string-version" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [{"type": "session", "version": "3", "id": "not-an-exact-pi-header"}],
    )

    with pytest.raises(ValueError, match="Cannot determine JSONL session provider"):
        get_jsonl_session_adapter(session_path)


def test_unknown_external_jsonl_exits_instead_of_assuming_claude(
    tmp_path: Path,
    capsys,
) -> None:
    """An unrecognized path and first entry should fail without a Claude fallback."""
    session_path = tmp_path / "unknown" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [
            {
                "type": "user",
                "sessionId": "external-claude-shaped-session",
                "message": {"role": "user", "content": "unknown provider prompt"},
            }
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        cmd_parse(
            ConversationFlags(color="never", paging=False),
            str(session_path),
            slice_str=None,
            output_file=None,
            output_format="xml",
            emit_metadata=False,
        )

    captured = capsys.readouterr()
    assert exit_info.value.code == 1, (
        "Expected an unknown JSONL provider to exit with status 1. "
        f"Got: {exit_info.value.code!r}"
    )
    assert "Cannot determine JSONL session provider" in captured.err, (
        "Expected the error to explain that provider resolution failed. "
        f"Got stderr:\n{captured.err}"
    )
    assert captured.out == "", (
        "Expected unknown JSONL input not to produce transcript output. "
        f"Got stdout:\n{captured.out}"
    )


def test_unknown_external_jsonl_only_id_exits_cleanly(
    tmp_path: Path,
    capsys,
) -> None:
    """Provider rejection should also apply before the id-only fast path returns."""
    session_path = tmp_path / "unknown-id" / "transcript.jsonl"
    _write_jsonl(
        session_path,
        [{"type": "user", "sessionId": "unknown", "message": {"role": "user"}}],
    )

    with pytest.raises(SystemExit) as exit_info:
        cmd_parse(
            ConversationFlags(color="never", paging=False),
            str(session_path),
            slice_str=None,
            output_file=None,
            output_format="xml",
            emit_metadata=False,
            output_mode=ParseOutputMode.ONLY_ID,
        )

    captured = capsys.readouterr()
    assert exit_info.value.code == 1, (
        f"Expected unknown id-only JSONL to exit 1. Got: {exit_info.value.code!r}"
    )
    assert "Cannot determine JSONL session provider" in captured.err, (
        "Expected id-only provider rejection without a traceback. "
        f"Got stderr:\n{captured.err}"
    )
