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


def test_pi_json_output_exposes_stable_native_tool_provenance(
    temp_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_path = (
        temp_home
        / ".pi"
        / "agent"
        / "sessions"
        / "demo-project"
        / "pi-native-provenance.jsonl"
    )
    session_path.parent.mkdir(parents=True)
    native_tool_call_id = "call_01CNfull-native-tool-call-id"
    entries = [
        {"type": "session", "id": "pi-native-provenance"},
        {
            "type": "message",
            "id": "assistant-entry-id",
            "timestamp": "2026-08-03T10:00:00Z",
            "message": {
                "role": "assistant",
                "model": "test/model",
                "content": [
                    {"type": "text", "text": "I will inspect the file."},
                    {"type": "thinking", "thinking": "Choose the right file."},
                    {
                        "type": "toolCall",
                        "id": native_tool_call_id,
                        "name": "read",
                        "arguments": {"file_path": "/tmp/example.txt"},
                    },
                ],
            },
        },
        {
            "type": "message",
            "id": "tool-result-entry-id",
            "timestamp": "2026-08-03T10:00:01Z",
            "message": {
                "role": "toolResult",
                "toolCallId": native_tool_call_id,
                "isError": False,
                "content": [{"type": "text", "text": "contents"}],
            },
        },
    ]
    session_path.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n",
        encoding="utf-8",
    )

    cmd_parse(
        ConversationFlags(show_tools=True, color="never"),
        str(session_path),
        None,
        None,
        output_format="json",
        emit_metadata=False,
    )

    messages = json.loads(capsys.readouterr().out)
    assistant_message, tool_result_message = messages
    tool_input = assistant_message.get("content", [{}])[-1]
    tool_output = tool_result_message.get("content", [{}])[0]

    assert assistant_message.get("native_entry_id") == "assistant-entry-id", (
        f"Expected the assistant's native Pi entry id. Got: {assistant_message!r}."
    )
    assert tool_input.get("id") == "01CN", (
        f"Expected the existing short display id to remain compatible. Got: {tool_input!r}."
    )
    assert tool_input.get("native_tool_call_id") == native_tool_call_id, (
        f"Expected the complete native Pi tool-call id. Got: {tool_input!r}."
    )
    assert tool_input.get("native_content_index") == 2, (
        "Expected the zero-based position in the native message.content array. "
        f"Got: {tool_input!r}."
    )
    assert tool_result_message.get("native_entry_id") == "tool-result-entry-id", (
        f"Expected the tool result's native Pi entry id. Got: {tool_result_message!r}."
    )
    assert tool_output.get("native_tool_call_id") == native_tool_call_id, (
        f"Expected the result to retain its complete paired call id. Got: {tool_output!r}."
    )
