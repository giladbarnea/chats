from __future__ import annotations

import os
from pathlib import Path

import chats._native as native
import chats.parsing as parsing_module
import chats.session_pool as session_pool_module
from chats.parsing import find_all_supported_session_files
from chats.session_pool import SessionPool


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")


def test_native_inventory_returns_ordered_provider_rows_and_mtimes(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    claude_later = home / ".claude" / "projects" / "z-project" / "z.jsonl"
    claude_earlier = home / ".claude" / "projects" / "a-project" / "a.jsonl"
    claude_agent = (
        home
        / ".claude"
        / "projects"
        / "a-project"
        / "session"
        / "subagents"
        / "agent-a.jsonl"
    )
    codex = home / ".codex" / "sessions" / "2026" / "08" / "codex.jsonl"
    pi = home / ".pi" / "agent" / "sessions" / "project" / "pi.jsonl"
    expected_paths = [claude_earlier, claude_agent, claude_later, codex, pi]

    for ordinal, path in enumerate(expected_paths, start=1):
        _write(path)
        timestamp_ns = 1_700_000_000_000_000_000 + ordinal
        os.utime(path, ns=(timestamp_ns, timestamp_ns))

    rows = native.discover_session_files(os.fsencode(home), True)

    actual_paths = [Path(os.fsdecode(raw_path)) for raw_path, _, _ in rows]
    actual_providers = [provider for _, provider, _ in rows]
    actual_mtimes = [mtime for _, _, mtime in rows]
    expected_mtimes = [path.stat().st_mtime for path in expected_paths]

    assert actual_paths == expected_paths, (
        "Expected native inventory rows in Claude, Codex, Pi group order with "
        f"lexical order inside each group. Got: {actual_paths!r}"
    )
    assert actual_providers == ["claude", "claude", "claude", "codex", "pi"], (
        "Expected every native path to carry its canonical provider. "
        f"Got: {actual_providers!r}"
    )
    assert actual_mtimes == expected_mtimes, (
        "Expected native rows to carry Python-compatible stat mtimes. "
        f"Got: {actual_mtimes!r}"
    )


def test_native_inventory_matches_hidden_names_and_case_sensitive_suffixes(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    sessions = home / ".codex" / "sessions"
    hidden = sessions / ".hidden.jsonl"
    unicode_name = sessions / "é.jsonl"
    wrong_case = sessions / "ignored.JSONL"
    for path in (hidden, unicode_name, wrong_case):
        _write(path)

    rows = native.discover_session_files(os.fsencode(home), True)
    actual_paths = [Path(os.fsdecode(raw_path)) for raw_path, _, _ in rows]
    expected_paths = sorted([hidden, unicode_name])

    assert actual_paths == expected_paths, (
        "Expected hidden names to match and the JSONL suffix to stay "
        f"case-sensitive. Got: {actual_paths!r}"
    )


def test_public_inventory_orders_prefix_related_sibling_components_like_pathlib(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    sessions = home / ".codex" / "sessions"
    shorter_component = sessions / "agents" / "z.jsonl"
    longer_component = sessions / "agents-plugins" / "a.jsonl"
    for path in (shorter_component, longer_component):
        _write(path)
    monkeypatch.setattr(Path, "home", lambda: home)

    actual = find_all_supported_session_files()

    assert actual == [shorter_component, longer_component], (
        "Expected pathlib component-tuple order, where 'agents' sorts before its "
        f"'agents-plugins' sibling regardless of the following separator. Got: {actual!r}"
    )


def test_native_inventory_accepts_surrogate_escaped_home_bytes() -> None:
    rows = native.discover_session_files(b"/missing-home-\x80", True)

    assert rows == [], (
        "Expected a non-UTF-8 missing home to stay representable and produce no rows. "
        f"Got: {rows!r}"
    )


def test_public_inventory_preserves_surrogate_escaped_native_row(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw_path = os.fsencode(tmp_path) + b"/session-\xff.jsonl"

    monkeypatch.setattr(
        parsing_module,
        "discover_session_files",
        lambda _home, _include_sidechains: [(raw_path, "pi", 0.0)],
    )

    actual = find_all_supported_session_files()

    assert len(actual) == 1 and isinstance(actual[0], Path), (
        "Expected the native bytes row to project through the public Path interface. "
        f"Got: {actual!r}"
    )
    assert os.fsencode(actual[0]) == raw_path, (
        "Expected os.fsdecode and Path construction to preserve every native path byte. "
        f"Got: {os.fsencode(actual[0])!r}"
    )


def test_public_inventory_does_not_use_python_glob_traversal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    session = home / ".pi" / "agent" / "sessions" / "project" / "pi.jsonl"
    _write(session)
    monkeypatch.setattr(Path, "home", lambda: home)

    def reject_python_traversal(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Python glob traversal must not own production inventory.")

    monkeypatch.setattr(Path, "glob", reject_python_traversal)
    monkeypatch.setattr(Path, "rglob", reject_python_traversal)

    actual = find_all_supported_session_files()

    assert actual == [session], (
        "Expected the public Path interface to project the native inventory. "
        f"Got: {actual!r}"
    )


def test_session_pool_consumes_native_provider_and_mtime_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    claude = home / ".claude" / "projects" / "project" / "duplicate.jsonl"
    codex = home / ".codex" / "sessions" / "duplicate.jsonl"
    pi = home / ".pi" / "agent" / "sessions" / "project" / "duplicate.jsonl"
    for path in (claude, codex, pi):
        _write(path)
    for path, timestamp in ((claude, 3), (codex, 1), (pi, 2)):
        os.utime(path, (timestamp, timestamp))
    monkeypatch.setattr(Path, "home", lambda: home)

    def reject_reclassification(_path: Path) -> None:
        raise AssertionError("SessionPool.discover must consume native provider rows.")

    monkeypatch.setattr(
        session_pool_module,
        "get_jsonl_session_adapter",
        reject_reclassification,
    )

    pool = SessionPool.discover()

    assert pool.files == (claude, codex, pi), (
        f"Expected original provider-group order in pool.files. Got: {pool.files!r}"
    )
    assert pool.by_provider == {
        "claude": (claude,),
        "pi": (pi,),
        "codex": (codex,),
    }, f"Expected native provider partitions. Got: {pool.by_provider!r}"
    assert pool.stat_mtime_sorted == (codex, pi, claude), (
        "Expected SessionPool to sort by native mtimes. "
        f"Got: {pool.stat_mtime_sorted!r}"
    )
    assert pool.by_stem["duplicate"] == pi, (
        "Expected duplicate stems to keep last-in-inventory overwrite behavior. "
        f"Got: {pool.by_stem!r}"
    )
    assert pool.by_filename["duplicate.jsonl"] == pi, (
        "Expected duplicate filenames to keep last-in-inventory overwrite behavior. "
        f"Got: {pool.by_filename!r}"
    )


def test_native_inventory_preserves_fixed_and_recursive_symlink_rules(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    external_project = tmp_path / "external-project"
    external_main = external_project / "main.jsonl"
    _write(external_main)
    claude_projects = home / ".claude" / "projects"
    claude_projects.mkdir(parents=True)
    linked_project = claude_projects / "linked-project"
    linked_project.symlink_to(external_project, target_is_directory=True)
    linked_main = linked_project / "main.jsonl"

    external_session = tmp_path / "external-session"
    external_agent = external_session / "subagents" / "agent-linked.jsonl"
    _write(external_agent)
    real_project = claude_projects / "real-project"
    real_project.mkdir()
    linked_session = real_project / "linked-session"
    linked_session.symlink_to(external_session, target_is_directory=True)
    linked_agent = linked_session / "subagents" / "agent-linked.jsonl"

    codex_root = home / ".codex" / "sessions"
    external_codex = tmp_path / "external-codex"
    external_codex_file = external_codex / "not-followed.jsonl"
    _write(external_codex_file)
    codex_root.mkdir(parents=True)
    (codex_root / "linked-directory").symlink_to(
        external_codex,
        target_is_directory=True,
    )
    matching_directory = codex_root / "matching-directory.jsonl"
    matching_directory.mkdir()
    matching_symlink = codex_root / "matching-symlink.jsonl"
    matching_symlink.symlink_to(external_codex_file)

    rows = native.discover_session_files(os.fsencode(home), True)
    actual_paths = [Path(os.fsdecode(raw_path)) for raw_path, _, _ in rows]
    expected_paths = [
        *sorted([linked_main, linked_agent]),
        *sorted([matching_directory, matching_symlink]),
    ]

    assert actual_paths == expected_paths, (
        "Expected fixed Claude segments to follow directory symlinks, recursive "
        "Codex traversal not to enter directory symlinks, and matching directory "
        f"or symlink entries to remain. Got: {actual_paths!r}"
    )
    assert external_codex_file not in actual_paths, (
        "Expected recursive traversal not to replace a lexical symlink entry with "
        f"its external target. Got: {actual_paths!r}"
    )


def test_sidechain_filter_uses_canonical_provider_then_python_header_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    project = home / ".claude" / "projects" / "project"
    agent_named_main = project / "agent-main.jsonl"
    normal_main = project / "normal.jsonl"
    native_agent = project / "session" / "subagents" / "agent-native.jsonl"
    for path in (agent_named_main, normal_main, native_agent):
        _write(path)

    external_pi = tmp_path / "external-pi.jsonl"
    external_pi.write_text(
        '{"type":"session","version":3,"id":"external-pi"}\n',
        encoding="utf-8",
    )
    external_agent = (
        project / "session" / "subagents" / "agent-external-pi.jsonl"
    )
    external_agent.symlink_to(external_pi)
    monkeypatch.setattr(Path, "home", lambda: home)

    with_sidechains = find_all_supported_session_files(include_sidechains=True)
    without_sidechains = find_all_supported_session_files(include_sidechains=False)
    pool = SessionPool.discover(include_sidechains=False)

    assert with_sidechains == sorted(
        [agent_named_main, normal_main, external_agent, native_agent]
    ), f"Expected every matching Claude entry with sidechains enabled. Got: {with_sidechains!r}"
    assert without_sidechains == [normal_main, external_agent], (
        "Expected canonical Claude agent names to be excluded, while a Claude-shaped "
        "symlink with external Pi content uses Python header detection and remains. "
        f"Got: {without_sidechains!r}"
    )
    assert pool.by_provider["pi"] == (external_agent,), (
        "Expected SessionPool to group the no-native-match symlink by its Pi header. "
        f"Got: {pool.by_provider!r}"
    )


def test_stat_failures_sort_first_and_equal_mtimes_keep_inventory_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    project = home / ".claude" / "projects" / "project"
    broken = project / "broken.jsonl"
    broken.parent.mkdir(parents=True)
    broken.symlink_to("broken.jsonl")
    claude = project / "equal.jsonl"
    codex = home / ".codex" / "sessions" / "equal.jsonl"
    pi = home / ".pi" / "agent" / "sessions" / "project" / "equal.jsonl"
    for path in (claude, codex, pi):
        _write(path)
        os.utime(path, (100, 100))
    monkeypatch.setattr(Path, "home", lambda: home)

    rows = native.discover_session_files(os.fsencode(home), True)
    row_by_path = {
        Path(os.fsdecode(raw_path)): (provider, mtime)
        for raw_path, provider, mtime in rows
    }
    pool = SessionPool.discover()

    assert row_by_path[broken] == ("claude", float("-inf")), (
        "Expected a matching stat-failing symlink to retain its canonical provider "
        f"and negative-infinity sentinel. Got: {row_by_path!r}"
    )
    assert pool.stat_mtime_sorted == (broken, claude, codex, pi), (
        "Expected stat failures first and equal mtimes stable in Claude, Codex, Pi "
        f"inventory order. Got: {pool.stat_mtime_sorted!r}"
    )
