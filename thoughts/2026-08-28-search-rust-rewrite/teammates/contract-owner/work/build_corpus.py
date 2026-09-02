#!/usr/bin/env python3
"""Build the deterministic `ch search` contract corpus under a fixture HOME."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# Fixed epochs, newest last. Ordering in search output is newest-first by stat mtime.
BASE_EPOCH = 1_760_000_000


def _write(path: Path, entries: list[dict], *, mtime_rank: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )
    stamp = BASE_EPOCH + mtime_rank
    os.utime(path, (stamp, stamp))
    return path


def claude_user(text: str, *, cwd: str, timestamp: str = "2025-10-09T00:00:00Z") -> dict:
    return {
        "type": "user",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "user", "content": text},
    }


def claude_assistant_text(text: str, *, cwd: str) -> dict:
    return {
        "type": "assistant",
        "timestamp": "2025-10-09T00:01:00Z",
        "cwd": cwd,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def build(home: Path) -> None:
    if home.exists():
        shutil.rmtree(home)

    claude = home / ".claude" / "projects"
    pi = home / ".pi" / "agent" / "sessions"
    codex = home / ".codex" / "sessions"

    alpha_cwd = "/tmp/ch-contract/alpha"
    beta_cwd = "/tmp/ch-contract/beta"

    # 1. Oldest: plain claude session with a summary facet.
    _write(
        claude / "alpha" / "aaaa0001-summary-and-body.jsonl",
        [
            {"type": "summary", "summary": "Alpha summary mentions needle", "leafUuid": "leaf-a"},
            claude_user("plain alpha body", cwd=alpha_cwd),
            claude_assistant_text("alpha assistant reply", cwd=alpha_cwd),
        ],
        mtime_rank=10,
    )

    # 2. Custom title facet only.
    _write(
        claude / "alpha" / "aaaa0002-custom-title.jsonl",
        [
            {"type": "custom-title", "customTitle": "Titled needle session"},
            claude_user("unrelated words here", cwd=alpha_cwd),
        ],
        mtime_rank=20,
    )

    # 3. Hidden-by-default content: thinking, tool use, plan.
    _write(
        claude / "beta" / "aaaa0003-hidden-facets.jsonl",
        [
            claude_user("visible beta prompt", cwd=beta_cwd),
            {
                "type": "assistant",
                "timestamp": "2025-10-09T00:02:00Z",
                "cwd": beta_cwd,
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "thinkingonlyneedle appears here"},
                        {
                            "type": "tool_use",
                            "id": "toolu_c1",
                            "name": "Bash",
                            "input": {"command": "echo toolonlyneedle"},
                        },
                    ],
                },
            },
            {
                "type": "user",
                "timestamp": "2025-10-09T00:03:00Z",
                "cwd": beta_cwd,
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_c1",
                            "content": "tooloutputneedle printed",
                        }
                    ],
                },
            },
        ],
        mtime_rank=30,
    )

    # 4. Regex-hostile literal text and unicode.
    _write(
        claude / "beta" / "aaaa0004-regex-and-unicode.jsonl",
        [
            claude_user("literal a.b*c pattern and ünïcodé ⚙ text", cwd=beta_cwd),
        ],
        mtime_rank=40,
    )

    # 5. Pi session.
    _write(
        pi / "proj" / "pi-0005.jsonl",
        [
            {"type": "session", "id": "pi-0005-id", "cwd": "/tmp/ch-contract/pi"},
            {
                "type": "message",
                "message": {"role": "user", "content": [{"type": "text", "text": "pi body needle"}]},
            },
        ],
        mtime_rank=50,
    )

    # 6. Codex session.
    _write(
        codex / "2026" / "01" / "01" / "codex-0006.jsonl",
        [
            {"type": "session_meta", "payload": {"id": "codex-0006-id", "cwd": "/tmp/ch-contract/codex"}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "codex body needle"}],
                },
            },
        ],
        mtime_rank=60,
    )

    # 7. Newest: two terms in different messages, for AND/OR/NOT truth.
    _write(
        claude / "alpha" / "aaaa0007-boolean-terms.jsonl",
        [
            claude_user("first term is booleanalpha", cwd=alpha_cwd),
            claude_assistant_text("second term is booleanbeta", cwd=alpha_cwd),
        ],
        mtime_rank=70,
    )


if __name__ == "__main__":
    build(Path(sys.argv[1]))
    print(f"built corpus at {sys.argv[1]}")
