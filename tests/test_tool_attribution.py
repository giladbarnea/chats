"""Tool activity belongs to the assistant, not its provider's transport role."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest


SESSION_ID = "11111111-2222-4333-8444-555555555555"
HUMAN_PROMPT = "HUMAN_PROMPT_MARKER"
HUMAN_FOLLOWUP = "HUMAN_FOLLOWUP_MARKER"
TOOL_INPUT = "TOOL_INPUT_MARKER"
TOOL_RESULT = "TOOL_RESULT_MARKER"


def _write_session(home: Path, provider: str, entries: list[dict[str, object]]) -> Path:
    directories = {
        "claude": home / ".claude/projects/project",
        "pi": home / ".pi/agent/sessions/project",
        "codex": home / ".codex/sessions/2026/10/22",
    }
    path = directories[provider] / f"{SESSION_ID}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
    return path


def _run(executable: Path, home: Path, *arguments: str) -> str:
    environment = {
        **os.environ,
        "HOME": str(home),
        "TERM": "xterm-256color",
        "COLUMNS": "120",
        "TZ": "Asia/Jerusalem",
    }
    environment.pop("NO_COLOR", None)
    result = subprocess.run(
        [str(executable), *arguments, "--no-paging", "--no-metadata"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Expected successful ch output, got {result.stderr!r}"
    return result.stdout


@pytest.fixture(params=["claude", "pi", "codex"])
def tool_session(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    provider = request.param
    entries = {
        "claude": [
            {"type": "user", "message": {"role": "user", "content": HUMAN_PROMPT}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "call-read", "name": "Read", "input": {"file_path": f"/tmp/{TOOL_INPUT}"}},
            ]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": HUMAN_FOLLOWUP},
                {"type": "tool_result", "tool_use_id": "call-read", "content": TOOL_RESULT},
            ]}},
        ],
        "pi": [
            {"type": "session", "version": 3, "id": SESSION_ID},
            {"type": "message", "message": {"role": "user", "content": HUMAN_PROMPT}},
            {"type": "message", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "id": "call-read", "name": "read", "arguments": {"path": f"/tmp/{TOOL_INPUT}"}},
            ]}},
            {"type": "message", "message": {"role": "toolResult", "toolCallId": "call-read", "toolName": "read", "content": [
                {"type": "text", "text": TOOL_RESULT},
            ]}},
            {"type": "message", "message": {"role": "user", "content": HUMAN_FOLLOWUP}},
        ],
        "codex": [
            {"type": "session_meta", "payload": {"id": SESSION_ID}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": HUMAN_PROMPT},
            ]}},
            {"type": "response_item", "payload": {"type": "function_call", "call_id": "call-read", "name": "Read", "arguments": json.dumps({"file_path": f"/tmp/{TOOL_INPUT}"})}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "call-read", "output": TOOL_RESULT}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": HUMAN_FOLLOWUP},
            ]}},
        ],
    }[provider]
    return _write_session(tmp_path, provider, entries)


def test_tool_blocks_have_assistant_owners_without_relabeling_human_text(
    checkout_built_ch: Path, tmp_path: Path, tool_session: Path,
) -> None:
    messages = json.loads(_run(checkout_built_ch, tmp_path, str(tool_session), "-t", "-f", "json"))
    human_content = [message["content"] for message in messages if message.get("role") == "user"]
    assert human_content == [[HUMAN_PROMPT], [HUMAN_FOLLOWUP]], (
        f"Expected only genuine human text under User, got {messages!r}"
    )
    tool_owners = [
        (message.get("role"), message.get("type"), block.get("type"))
        for message in messages
        for block in message["content"]
        if isinstance(block, dict) and block.get("type") in {"tool-input", "tool-output"}
    ]
    assert tool_owners == [
        ("assistant", "assistant-response", "tool-input"),
        ("assistant", "assistant-response", "tool-output"),
    ], f"Expected both tool directions under Assistant, got {tool_owners!r}"


@pytest.mark.parametrize("route", ["parse", "search"])
@pytest.mark.parametrize("output_format", ["xml", "raw", "color"])
def test_readable_output_attributes_tools_to_assistant(
    checkout_built_ch: Path, tmp_path: Path, tool_session: Path,
    route: str, output_format: str,
) -> None:
    arguments = [str(tool_session)] if route == "parse" else ["search", ".", "--full"]
    arguments += ["-t", "--color", "always" if output_format == "color" else "never"]
    if output_format == "raw":
        arguments.append("--raw")
    output = _run(checkout_built_ch, tmp_path, *arguments)
    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    owners: dict[str, str | None] = {}
    owner: str | None = None
    for line in plain.splitlines():
        if heading := re.search(r"\b(User|Assistant)\b", line):
            owner = heading.group(1)
        for marker in (HUMAN_PROMPT, HUMAN_FOLLOWUP, TOOL_INPUT, TOOL_RESULT):
            if marker in line:
                owners[marker] = owner
    assert owners == {
        HUMAN_PROMPT: "User", HUMAN_FOLLOWUP: "User",
        TOOL_INPUT: "Assistant", TOOL_RESULT: "Assistant",
    }, f"Expected human/tool ownership in {route} {output_format}, got {owners!r}:\n{plain}"


@pytest.mark.parametrize("case", ["meta-string", "meta-blocks", "hook", "skill", "team"])
def test_injected_tool_activity_is_not_presented_as_user_action(
    checkout_built_ch: Path, tmp_path: Path, case: str,
) -> None:
    cases = {
        "meta-string": ("claude", [{
            "type": "user", "isMeta": True, "sourceToolUseID": "call-skill",
            "message": {"role": "user", "content": TOOL_RESULT},
        }], "--tools"),
        "meta-blocks": ("claude", [{
            "type": "user", "isMeta": True, "sourceToolUseID": "call-skill",
            "message": {"role": "user", "content": [{"type": "text", "text": TOOL_RESULT}]},
        }], "--tools"),
        "hook": ("claude", [{
            "type": "attachment", "attachment": {
                "type": "hook_additional_context", "hookName": "PostToolUse", "content": [TOOL_RESULT],
            },
        }], "--tools"),
        "skill": ("pi", [
            {"type": "session", "version": 3, "id": SESSION_ID},
            {"type": "message", "id": "skill-entry", "message": {
                "role": "user", "content": f'<skill name="review" location="/tmp/SKILL.md">{TOOL_RESULT}</skill>',
            }},
        ], "--tools"),
        "team": ("pi", [
            {"type": "session", "version": 3, "id": SESSION_ID},
            {"type": "message", "message": {
                "role": "toolResult", "toolName": "team_send_message", "toolCallId": "call-team",
                "content": [{"type": "text", "text": TOOL_RESULT}],
            }},
        ], "--agents"),
    }
    provider, entries, visibility = cases[case]
    path = _write_session(tmp_path, provider, entries)
    output = _run(checkout_built_ch, tmp_path, str(path), visibility, "-f", "json")
    messages = json.loads(output)
    assert TOOL_RESULT in output, f"Expected the tool payload to remain visible, got {output!r}"
    assert [(message.get("role"), message.get("type")) for message in messages] == [
        ("assistant", "assistant-response"),
    ], f"Expected injected tool activity under Assistant, got {messages!r}"

    search = _run(checkout_built_ch, tmp_path, "search", TOOL_RESULT, visibility, "--color", "never")
    assert TOOL_RESULT in search and "<assistant-response " in search and "<user-message " not in search, (
        f"Expected native search to preserve Assistant tool ownership, got {search!r}"
    )


@pytest.mark.parametrize("selection", ["--no-user", "--no-assistant"])
def test_role_filters_do_not_hide_explicit_tool_outputs(
    checkout_built_ch: Path, tmp_path: Path, tool_session: Path, selection: str,
) -> None:
    output = _run(checkout_built_ch, tmp_path, str(tool_session), selection, "-t", "Read:o", "--color", "never")
    assert TOOL_RESULT in output and TOOL_INPUT not in output, (
        f"Expected only tool output with {selection} -t Read:o, got {output!r}"
    )
    assert re.search(r"<assistant-response[^>]*>.*?TOOL_RESULT_MARKER.*?</assistant-response>", output, re.DOTALL), (
        f"Expected explicit tool output under Assistant with {selection}, got {output!r}"
    )


@pytest.mark.parametrize("context_kind", ["meta", "hook", "result"])
def test_subagent_task_survives_leading_tool_context(
    checkout_built_ch: Path, tmp_path: Path, context_kind: str,
) -> None:
    main = _write_session(tmp_path, "claude", [{
        "type": "user", "timestamp": "2026-10-22T10:00:00Z",
        "message": {"role": "user", "content": HUMAN_PROMPT},
    }])
    subagent = main.parent / SESSION_ID / "subagents/agent-scout.jsonl"
    subagent.parent.mkdir(parents=True)
    context = {
        "meta": {"type": "user", "isMeta": True, "sourceToolUseID": "call-skill", "message": {"role": "user", "content": "LOADED_CONTEXT"}},
        "hook": {"type": "attachment", "attachment": {"type": "hook_additional_context", "hookName": "SessionStart", "content": ["LOADED_CONTEXT"]}},
        "result": {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call-skill", "content": "LOADED_CONTEXT"},
        ]}},
    }[context_kind]
    entries = [
        {"type": "user", "message": {"role": "user", "content": "EARLIER_CONTEXT"}},
        context,
        {"type": "user", "message": {"role": "user", "content": "SUBAGENT_TASK_MARKER"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "call-read", "name": "Read", "input": {"file_path": f"/tmp/{TOOL_INPUT}"}},
        ]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call-read", "content": TOOL_RESULT},
        ]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "SUBAGENT_REPLY_MARKER"}]}},
    ]
    subagent.write_text("\n".join(json.dumps({
        **entry, "sessionId": SESSION_ID, "agentId": "scout", "timestamp": f"2026-10-22T10:01:0{index}Z",
    }) for index, entry in enumerate(entries)) + "\n")
    subagent.with_suffix(".meta.json").write_text(json.dumps({"agentType": "general-purpose"}))
    output = _run(checkout_built_ch, tmp_path, str(main), "--agents", "--tools", "-f", "json")
    messages = json.loads(output)
    tasks = [
        block.get("content") for message in messages for block in message["content"]
        if isinstance(block, dict) and block.get("type") == "subagent-task"
    ]
    assert tasks == ["SUBAGENT_TASK_MARKER"], f"Expected the initiating task, not earlier tool context, got {messages!r}"
    tool_owners = [
        message.get("type") for message in messages for block in message["content"]
        if isinstance(block, dict) and block.get("type") in {"tool-input", "tool-output"}
    ]
    assert tool_owners == ["agent", "agent"], f"Expected both tool directions inside the agent block, got {messages!r}"
