from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from chats.formatting import format_to_json, format_to_xml
from chats.model import ConversationFlags, Message
from chats.tool_filter import parse_tool_spec


def test_tool_input_values_share_one_message_budget() -> None:
    message = Message(
        role="assistant",
        tools=[
            {
                "type": "tool_use",
                "name": "Custom",
                "id": "first-call",
                "input": {"first": "A" * 40, "nested": ["B" * 40, "C" * 40]},
            },
            {
                "type": "tool_use",
                "name": "Custom",
                "id": "last-call",
                "input": {"last": "D" * 40},
            },
        ],
    )
    flags = ConversationFlags(show_tools=[parse_tool_spec("i:s=20")])

    content = json.loads(format_to_json([message], flags))[0]["content"]

    assert content[0]["first"] == "A" * 8 + "\n...\n", content
    assert content[0]["nested"] == ["", ""], content
    assert content[1]["last"] == "D" * 7, content
    assert content[0]["name"] == content[1]["name"] == "Custom"


@pytest.mark.parametrize("budget", [8, 20, 100])
def test_many_short_values_cannot_multiply_the_budget(budget: int) -> None:
    message = Message(role="assistant", tools=[{
        "type": "tool_use", "name": "Custom",
        "input": {"values": [f"{index:03}" for index in range(100)]},
    }])
    flags = ConversationFlags(show_tools=[parse_tool_spec(f"i:s={budget}")])
    values = json.loads(format_to_json([message], flags))[0]["content"][0]["values"]

    assert sum(map(len, values)) == budget, values
    assert len(values) == 100, "Shortening must preserve the original array shape."
    assert values[0].startswith("0") and values[-1].endswith("9"), values
    assert values[50] == "", values


def test_global_budget_spans_text_thinking_tools_and_plan() -> None:
    message = Message(
        role="assistant", text="A" * 40, thinking="B" * 40, plan="D" * 40,
        tools=[{"type": "tool_use", "name": "Bash", "input": {"command": "C" * 40}}],
    )
    flags = ConversationFlags(
        show_tools=True, show_thinking=True, show_plans=True,
        shorten=True, shorten_max_chars=20,
    )
    content = json.loads(format_to_json([message], flags))[0]["content"]

    assert content == [
        "AAAAAAAA\n...\n",
        {"type": "tool-input", "name": "Bash", "command": ""},
        {"type": "tool-input", "name": "ExitPlanMode", "plan": "DDDDDDD"},
    ], content
    assert message.text == "A" * 40, "Rendering must not shorten the source message."
    assert message.tools[0]["input"]["command"] == "C" * 40


def test_tool_result_block_types_survive_shared_shortening() -> None:
    message = Message(role="assistant", tools=[{
        "type": "tool_result", "name": "Read", "tool_use_id": "result-1",
        "content": [{"type": "text", "text": "א" * 40}, {"type": "text", "text": "ב" * 40}],
    }])
    flags = ConversationFlags(show_tools=[parse_tool_spec("o:s=20")])
    content = json.loads(format_to_json([message], flags))[0]["content"][0]["content"]

    assert content == [
        {"type": "text", "text": "א" * 8 + "\n...\n"},
        {"type": "text", "text": "ב" * 7},
    ], content
    xml = format_to_xml([message], flags)
    assert "א" * 8 in xml and "ב" * 7 in xml, xml


def test_distinct_policies_keep_independent_message_budgets() -> None:
    message = Message(role="assistant", text="A" * 40, tools=[
        {"type": "tool_use", "name": "Bash", "input": {"command": "B" * 40}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "C" * 40}},
    ])
    flags = ConversationFlags(
        shorten=True, shorten_max_chars=20,
        show_tools=[parse_tool_spec("Bash:s=10")],
    )
    content = json.loads(format_to_json([message], flags))[0]["content"]

    assert content[0] == "AAAAAAAA\n...\nAAAAAAA", content
    assert content[1]["command"] == "BBB\n...\n", content
    assert content[2]["command"] == "CC", content


@pytest.mark.parametrize("short_arguments", [
    ("--short=20", "-t"),
    ("--short=p=20", "-t:s"),
    ("-t:i:s=20",),
    ("--tools=i:short=progressive=20",),
])
def test_shared_budget_matches_parse_search_renderers_and_conversion(
    tmp_path: Path, checkout_built_ch: Path, short_arguments: tuple[str, ...],
) -> None:
    session = tmp_path / ".pi/agent/sessions/project/budget.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text("\n".join(json.dumps(entry, ensure_ascii=False) for entry in [
        {"type": "session", "version": 3, "id": "budget", "cwd": "/tmp/budget"},
        {"type": "message", "timestamp": "2026-10-26T09:00:00Z", "message": {
            "role": "assistant", "content": [
                {"type": "toolCall", "id": "call-one", "name": "Custom", "arguments": {
                    "first": "א" * 40, "nested": ["ב" * 40 + "MIDDLE_SHOULD_DISAPPEAR", "ג" * 40],
                }},
                {"type": "toolCall", "id": "call-two", "name": "Custom", "arguments": {"last": "ד" * 40}},
            ],
        }},
    ]))
    environment = {**os.environ, "HOME": str(tmp_path), "COLUMNS": "500", "TZ": "UTC"}

    def run(*arguments: str, source: str | None = None, expected_status: int = 0) -> str:
        result = subprocess.run(
            [str(checkout_built_ch), *arguments], input=source, text=True,
            capture_output=True, env=environment, timeout=30,
        )
        assert result.returncode == expected_status, result.stderr
        return result.stdout

    xml = run(str(session), *short_arguments, "--color=never", "--no-metadata")
    structured = run(str(session), *short_arguments, "-f", "json")
    outputs = [xml, structured]
    for render_arguments in [("-f", "raw"), ("--color=always", "--no-paging")]:
        outputs.append(run(str(session), *short_arguments, *render_arguments, "--no-metadata"))
    for render_arguments in [("--color=never",), ("--raw",), ("--color=always", "--no-paging")]:
        outputs.append(run("search", ".", *short_arguments, *render_arguments, "--no-metadata"))

    for output in outputs:
        assert output.count("א") + output.count(r"\u05d0") == 8, output
        assert output.count("ד") + output.count(r"\u05d3") == 7, output
        assert all(symbol not in output for symbol in ("ב", "ג", r"\u05d1", r"\u05d2")), output
    search_xml = outputs[4]
    assert re.search(r"<assistant-response.*?</assistant-response>", search_xml, re.S)[0] == xml.strip()
    assert run("parse", source=structured) == xml
    canonical = run("parse", "-f", "json", source=xml)
    assert run("parse", source=canonical) == xml
    assert run("search", "MIDDLE_SHOULD_DISAPPEAR", "-t", "--only-id") == "budget\n"
    assert run("search", "MIDDLE_SHOULD_DISAPPEAR", *short_arguments, "--only-id", expected_status=1) == ""
