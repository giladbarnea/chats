from __future__ import annotations

import json
from pathlib import Path

import pytest

from chats import ConversationFlags, cmd_parse

FIXTURES_DIR = Path(__file__).parent / "data" / "json_format"


def _install_fixture(temp_home: Path, provider: str, fixture_name: str) -> Path:
    fixture_content = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")

    if provider == "claude":
        target_path = (
            temp_home
            / ".claude"
            / "projects"
            / "demo-project"
            / fixture_name
        )
    elif provider == "pi":
        target_path = (
            temp_home
            / ".pi"
            / "agent"
            / "sessions"
            / "demo-project"
            / fixture_name
        )
    elif provider == "codex":
        target_path = (
            temp_home
            / ".codex"
            / "sessions"
            / "2026"
            / "05"
            / "12"
            / fixture_name.replace("input-", "rollout-2026-05-12T10-00-00-")
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(fixture_content, encoding="utf-8")
    return target_path


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    ("provider", "fixture_name", "flags", "expected_name"),
    [
        (
            "claude",
            "input-claude-no-tools.jsonl",
            ConversationFlags(color="never"),
            "expected-claude-no-tools.json",
        ),
        (
            "claude",
            "input-claude-with-thinking.jsonl",
            ConversationFlags(show_thinking=True, color="never"),
            "expected-claude-with-thinking.json",
        ),
        (
            "claude",
            "input-claude-with-tools.jsonl",
            ConversationFlags(show_tools=True, color="never"),
            "expected-claude-with-tools.json",
        ),
        (
            "pi",
            "input-pi-no-tools.jsonl",
            ConversationFlags(color="never"),
            "expected-pi-no-tools.json",
        ),
        (
            "pi",
            "input-pi-with-thinking.jsonl",
            ConversationFlags(show_thinking=True, color="never"),
            "expected-pi-with-thinking.json",
        ),
        (
            "pi",
            "input-pi-with-tools.jsonl",
            ConversationFlags(show_tools=True, color="never"),
            "expected-pi-with-tools.json",
        ),
        (
            "codex",
            "input-codex-no-tools.jsonl",
            ConversationFlags(color="never"),
            "expected-codex-no-tools.json",
        ),
        (
            "codex",
            "input-codex-with-thinking.jsonl",
            ConversationFlags(show_thinking=True, color="never"),
            "expected-codex-with-thinking.json",
        ),
        (
            "codex",
            "input-codex-with-tools.jsonl",
            ConversationFlags(show_tools=True, color="never"),
            "expected-codex-with-tools.json",
        ),
    ],
)
def test_json_output_is_fully_structured(
    temp_home: Path,
    capsys: pytest.CaptureFixture[str],
    provider: str,
    fixture_name: str,
    flags: ConversationFlags,
    expected_name: str,
) -> None:
    fixture_path = _install_fixture(temp_home, provider, fixture_name)
    expected = json.loads((FIXTURES_DIR / expected_name).read_text(encoding="utf-8"))

    cmd_parse(
        flags,
        str(fixture_path),
        None,
        None,
        output_format="json",
        emit_metadata=False,
    )

    captured = capsys.readouterr()
    actual = json.loads(captured.out)

    assert actual == expected, (
        f"Expected structured JSON output for {provider}/{fixture_name}.\n"
        f"Expected: {json.dumps(expected, indent=2, ensure_ascii=False)}\n"
        f"Actual: {json.dumps(actual, indent=2, ensure_ascii=False)}\n"
        f"stderr: {captured.err}"
    )
