#!/usr/bin/env python3
"""Tests for metadata timestamps shown in parse/search output."""

import json
import os
import shutil
from pathlib import Path

import pytest

from conversations import ConversationFlags, cmd_parse, cmd_search


FIXTURES_DIR = Path(__file__).parent / "data" / "rename_fixtures"


@pytest.fixture
def temp_claude_home(tmp_path, monkeypatch):
    """Create a temporary .claude directory structure and patch Path.home()."""
    temp_home = tmp_path / "home"
    temp_projects = temp_home / ".claude" / "projects"

    shutil.copytree(FIXTURES_DIR / "projects", temp_projects)
    monkeypatch.setattr(Path, "home", lambda: temp_home)

    return temp_home


def test_cmd_parse_metadata_prefers_jsonl_timestamps_over_file_stat(tmp_path, capsys):
    """Parse metadata should show conversation timestamps, not stale file mtimes."""
    conversation_path = tmp_path / "timestamped.jsonl"
    conversation_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "summary",
                        "summary": "Timestamp test",
                        "leafUuid": "leaf-1",
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2025-02-03T04:05:06.000Z",
                        "cwd": "/tmp/project",
                        "message": {"role": "user", "content": "hello"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(conversation_path, (1_704_067_200, 1_704_067_200))  # 2024-01-02 00:00

    cmd_parse(
        ConversationFlags(color="never", paging=False),
        str(conversation_path),
        slice_str=None,
        output_file=None,
        output_format="xml",
        emit_metadata=True,
    )

    captured = capsys.readouterr()
    assert 'modified: "2025-02-03 04:05"' in captured.out, (
        "Expected parse metadata to use the conversation timestamp for "
        f"modified time. Got output:\n{captured.out}\n{captured.err}"
    )
    assert 'modified: "2024-01-02 00:00"' not in captured.out, (
        "Expected parse metadata not to fall back to the stale filesystem "
        f"mtime when JSONL timestamps are available. Got output:\n{captured.out}"
    )


def test_cmd_search_metadata_prefers_jsonl_timestamps_over_file_stat(
    temp_claude_home, capsys
):
    """Search metadata should use the same timestamp source as search ordering."""
    conversation_path = (
        temp_claude_home
        / ".claude"
        / "projects"
        / "test-project"
        / "recent-by-content.jsonl"
    )
    conversation_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "summary",
                        "summary": "Timestamp search test",
                        "leafUuid": "leaf-search",
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "timestamp": "2025-03-04T05:06:07.000Z",
                        "cwd": "/tmp/project",
                        "message": {"role": "user", "content": "search needle"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(conversation_path, (1_704_067_200, 1_704_067_200))  # 2024-01-02 00:00

    with pytest.raises(SystemExit) as exc_info:
        cmd_search(
            "search needle",
            ConversationFlags(color="never", paging=False),
            list_only=True,
            emit_metadata=True,
        )

    assert exc_info.value.code == 0, (
        f"Expected cmd_search to succeed. Got exit code: {exc_info.value.code}"
    )

    captured = capsys.readouterr()
    assert 'modified: "2025-03-04 05:06"' in captured.out, (
        "Expected search metadata to use the conversation timestamp for "
        f"modified time. Got output:\n{captured.out}\n{captured.err}"
    )
    assert 'modified: "2024-01-02 00:00"' not in captured.out, (
        "Expected search metadata not to show the stale filesystem mtime "
        f"when JSONL timestamps are available. Got output:\n{captured.out}"
    )
