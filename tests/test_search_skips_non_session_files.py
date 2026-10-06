from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_render_dependent_search_ignores_files_that_are_not_sessions(
    checkout_built_ch: Path,
    tmp_path: Path,
) -> None:
    """A query the byte gate cannot decide must not report non-session files as errors."""
    home = tmp_path / "home"
    _write_jsonl(
        home / ".codex" / "sessions" / "2026" / "session.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "codex-session-id", "cwd": "/work"}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "<previous-review> marker"}],
                },
            },
        ],
    )
    empty_claude_file = home / ".claude" / "projects" / "-work" / "c1315bb7-7b56-5af5-af5b-23b773edfdbc.jsonl"
    empty_claude_file.parent.mkdir(parents=True)
    empty_claude_file.write_bytes(b"")
    _write_jsonl(
        home / ".codex" / "sessions" / "2025" / "rollout-2025-09-09T14-16-54-ff8721d4-eb57-4aaa-ab06-5969961bb3a5.jsonl",
        [
            {"id": "ff8721d4-eb57-4aaa-ab06-5969961bb3a5", "timestamp": "2025-09-09T11:16:54.769Z", "instructions": None},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<previous-review>"}]},
        ],
    )

    completed = subprocess.run(
        [str(checkout_built_ch), "search", "<previous-review>", "-ll"],
        cwd=PROJECT_ROOT,
        env={**os.environ, "HOME": str(home), "COLUMNS": "96", "NO_COLOR": "1"},
        capture_output=True,
        check=False,
    )

    assert completed.stderr == b"", (
        f"Expected files without a typed first JSON line to be skipped silently. Got stderr {completed.stderr!r}."
    )
    assert (completed.returncode, completed.stdout) == (0, b"codex-session-id\n"), (
        f"Expected only the real session to match. Got exit {completed.returncode}, stdout {completed.stdout!r}."
    )
