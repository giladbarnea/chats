from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_codex_session_meta_payload_cwd_passes_directory_filter(
    checkout_built_ch: Path,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    session = home / ".codex" / "sessions" / "2026" / "session.jsonl"
    session.parent.mkdir(parents=True)
    entries = [
        {
            "type": "session_meta",
            "payload": {"id": "codex-directory-id", "cwd": "/wanted"},
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "directory-filter-marker"}
                ],
            },
        },
    ]
    session.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )

    for directory, expected_status, expected_stdout in (
        ("/wanted", 0, b"codex-directory-id\n"),
        ("/other", 1, b""),
    ):
        completed = subprocess.run(
            [
                str(checkout_built_ch),
                "search",
                "directory-filter-marker",
                "-p",
                "codex",
                "-d",
                directory,
                "-ll",
            ],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "HOME": str(home),
                "COLUMNS": "96",
                "NO_COLOR": "1",
                "TZ": "Asia/Jerusalem",
            },
            capture_output=True,
            check=False,
        )

        assert completed.returncode == expected_status, (
            f"Expected directory {directory!r} to exit {expected_status}. "
            f"Got exit {completed.returncode}, stderr {completed.stderr!r}."
        )
        assert completed.stdout == expected_stdout, (
            f"Expected directory {directory!r} to emit {expected_stdout!r}. "
            f"Got stdout {completed.stdout!r}."
        )
        assert completed.stderr == b"", (
            f"Expected no error for directory {directory!r}. Got {completed.stderr!r}."
        )
