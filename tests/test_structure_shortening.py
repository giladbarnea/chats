from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


CH = Path(sys.executable).with_name("ch")


def write_session(home: Path, content: list[dict[str, object]], role: str = "assistant") -> Path:
    session = home / ".pi/agent/sessions/project/structure-budget.jsonl"
    session.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"type": "session", "version": 3, "id": "structure-budget", "cwd": "/tmp/structure-budget"},
        {"type": "message", "message": {"role": role, "content": content}},
    ]
    session.write_text("\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries))
    return session


def run_ch(home: Path, *arguments: str, source: str | None = None, expected_status: int = 0) -> str:
    result = subprocess.run(
        [str(CH), *arguments], input=source, capture_output=True, text=True, timeout=30,
        env={**os.environ, "HOME": str(home), "COLUMNS": "500", "TZ": "UTC"},
    )
    assert result.returncode == expected_status, result.stderr
    return result.stdout


def test_short_useful_fields_survive_between_long_values(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"description": "A" * 100, "action": "add", "evidence": "B" * 100},
    }])

    output = run_ch(tmp_path, str(session), "-t:i:s=20", "-f", "json")
    tool = json.loads(output)[0]["content"][0]

    assert tool.get("action") == "add", tool
    assert len(tool["description"]) + len(tool["action"]) + len(tool["evidence"]) <= 20, tool
    assert "[…]" in tool["description"] and "[…]" in tool["evidence"], tool
    assert "\n" not in tool["description"] + tool["evidence"], tool


def test_dictionary_only_scalars_fit_without_changing_retained_values(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"left": True, "middle": False, "last": 123},
    }])
    output = run_ch(tmp_path, str(session), "-t:i:s=8", "-f", "json")
    tool = json.loads(output)[0]["content"][0]
    assert {key: tool.get(key) for key in ("left", "middle", "last")} == {"left": True, "middle": "…", "last": 123}, tool
    assert tool["name"] == "Custom" and tool["native_tool_call_id"] == "call-one", tool


def value_characters(value: object) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return sum(value_characters(child) for child in value.values())
    if isinstance(value, list):
        return sum(value_characters(child) for child in value)
    return len(json.dumps(value))


def test_wide_nested_lists_keep_useful_ends_instead_of_empty_value_forests(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"action": "go", "items": [
            {"label": f"{index:03}", "payload": "A" * 100} for index in range(100)
        ]},
    }])
    tool = json.loads(run_ch(tmp_path, str(session), "-t:i:s=40", "-f", "json"))[0]["content"][0]
    items = tool.get("items")
    assert isinstance(items, list), tool
    labels = [item["label"] for item in items if isinstance(item, dict) and "label" in item]
    assert any(label.startswith("0") for label in labels), tool
    assert "" not in labels, tool
    assert len(items) < 100 and any(item in ("…", "[…]") for item in items), tool
    assert tool.get("action") == "go", tool
    assert value_characters({"action": tool["action"], "items": items}) <= 40, tool


@pytest.mark.parametrize(("source", "budget", "expected"), [
    ("first\n" + "\n".join("middle-" + "x" * 100 for _ in range(10)) + "\nlast", 16, "first\n…\nlast"),
    ("x" * 100 + "\nlast", 8, "…\nlast"),
    ("A" * 100 + "\n" + "B" * 100, 8, "AA…A\nB…B"),
    ("abcdefghij", 8, "abc[…]ij"),
    (("long-line-" * 10 + "\n") * 30, 8, "…"),
    ("\n".join("A" * 100 for _ in range(4)), 8, "…"),
    ("first\r\n" + "x" * 100 + "\r\nlast", 16, "first\r\n…\nlast"),
])
def test_line_markers_preserve_source_boundaries(tmp_path: Path, source: str, budget: int, expected: str) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one", "arguments": {"body": source},
    }])
    tool = json.loads(run_ch(tmp_path, str(session), f"-t:i:s={budget}", "-f", "json"))[0]["content"][0]
    assert tool.get("body") == expected, tool
    assert len(expected) <= budget
    for previous, marker, following in zip([None, *expected.splitlines()], expected.splitlines(), [*expected.splitlines()[1:], None]):
        assert marker != "…" or all(line is None or line in source.splitlines() for line in (previous, following)), tool
    xml = run_ch(tmp_path, str(session), f"-t:i:s={budget}", "--color=never", "--no-metadata")
    searched = run_ch(tmp_path, "search", ".", f"-t:i:s={budget}", "--color=never", "--no-metadata")
    assert xml.strip() in searched, searched


def test_native_search_uses_the_same_structure_preview(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"description": "A" * 100, "action": "add", "evidence": "B" * 100},
    }])
    parsed = run_ch(tmp_path, str(session), "-t:i:s=20", "--color=never", "--no-metadata").strip()
    searched = run_ch(tmp_path, "search", ".", "-t:i:s=20", "--color=never", "--no-metadata")
    start = searched.find("<assistant-response")
    end = searched.rfind("</assistant-response>") + len("</assistant-response>")
    assert start >= 0, searched
    assert searched[start:end] == parsed, searched


@pytest.mark.parametrize(("short", "long", "expected"), [
    ("ok", "abcdefghij", "ab[…]j"),
    ("keep", "abcdefghij", "ab…j"),
    ("ok", "😀אבגדefghij", "😀א[…]j"),
])
def test_inline_markers_use_unicode_character_budgets_without_newlines(
    tmp_path: Path, short: str, long: str, expected: str,
) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"short": short, "long": long},
    }])
    tool = json.loads(run_ch(tmp_path, str(session), "-t:i:s=8", "-f", "json"))[0]["content"][0]
    assert tool.get("short") == short and tool.get("long") == expected, tool
    assert len(short) + len(expected) == 8
    assert "\n" not in expected


@pytest.mark.parametrize("scalar", [10 ** 18, True, False, None])
def test_scalar_heavy_data_never_exceeds_the_payload_budget(tmp_path: Path, scalar: object) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {f"field_{index}": scalar for index in range(30)},
    }])
    tool = json.loads(run_ch(tmp_path, str(session), "-t:i:s=8", "-f", "json"))[0]["content"][0]
    payload = {key: value for key, value in tool.items() if key.startswith("field_")}
    assert 0 < value_characters(payload) <= 8, payload
    assert len(payload) < 30 and any(value in ("…", "[…]") for value in payload.values()), payload
    assert all(value == scalar and type(value) is type(scalar) or value in ("…", "[…]") for value in payload.values()), payload


def test_global_shortening_includes_first_user_and_subagent_task(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{"type": "text", "text": "U" * 100}], role="user")
    side_chat = session.with_name("structure-side-chat.jsonl")
    side_chat.write_text("\n".join(json.dumps(entry) for entry in [
        {"type": "session", "version": 3, "id": "structure-side-chat", "timestamp": "2026-10-08T08:00:00.000Z",
         "cwd": "/tmp/structure-budget", "parentSession": str(session)},
        {"type": "custom", "customType": "pi-user-agents-dispatch", "timestamp": "2026-10-08T08:00:00.001Z",
         "data": {"forwardedArgs": [], "task": "TASK", "isolate": True}},
        {"type": "message", "timestamp": "2026-10-08T08:00:01.000Z",
         "message": {"role": "user", "content": [{"type": "text", "text": "TASK" * 100}]}},
        {"type": "message", "timestamp": "2026-10-08T08:00:02.000Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ANSWER" * 100}]}},
    ]))
    messages = json.loads(run_ch(tmp_path, str(session), "--short=20", "--agents", "-f", "json"))
    assert len(messages) == 3, messages
    assert len(messages[0]["content"][0]) <= 20, messages[0]
    task = next((block["content"] for block in messages[1]["content"] if isinstance(block, dict) and block.get("type") == "subagent-task"), None)
    answer = next((block for block in messages[2]["content"] if isinstance(block, str)), None)
    assert task and len(task) <= 20, messages[1]
    assert answer and len(answer) <= 20, messages[2]
    parsed = run_ch(tmp_path, str(session), "--short=20", "--agents", "--color=never", "--no-metadata")
    searched = run_ch(tmp_path, "search", "U", "--full", "--short=20", "--agents", "--color=never", "--no-metadata")
    assert parsed.strip() in searched, searched


@pytest.mark.parametrize("short_arguments", [
    ("--short=32", "-t"), ("--short=p=32", "-t:s"),
    ("-t:i:s=32",), ("--tools=i:short=progressive=32",),
])
def test_structure_previews_agree_across_formats_and_round_trips(tmp_path: Path, short_arguments: tuple[str, ...]) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"action": "add", "records": [{"value": f"item-{index}", "body": "X" * 80} for index in range(30)]},
    }])
    structured = run_ch(tmp_path, str(session), *short_arguments, "-f", "json")
    tool = json.loads(structured)[0]["content"][0]
    assert tool.get("action") == "add", tool
    assert value_characters({"action": tool["action"], "records": tool["records"]}) <= 32, tool
    xml = run_ch(tmp_path, str(session), *short_arguments, "--color=never", "--no-metadata")
    assert run_ch(tmp_path, "parse", source=structured) == xml
    canonical = run_ch(tmp_path, "parse", "-f", "json", source=xml)
    assert run_ch(tmp_path, "parse", source=canonical) == xml
    assert run_ch(tmp_path, "search", "item-15", "-t", "--only-id") == "structure-budget\n"
    assert run_ch(tmp_path, "search", "item-15", *short_arguments, "--only-id", expected_status=1) == ""
    for arguments in [("-f", "raw"), ("--color=always", "--no-paging")]:
        rendered = run_ch(tmp_path, str(session), *short_arguments, *arguments, "--no-metadata")
        assert "add" in rendered and "X" * 20 not in rendered, rendered
    for arguments in [("--raw",), ("--color=always", "--no-paging")]:
        rendered = run_ch(tmp_path, "search", ".", *short_arguments, *arguments, "--no-metadata")
        assert "add" in rendered and "X" * 20 not in rendered, rendered


def test_fitting_values_and_deep_structure_remain_unchanged(tmp_path: Path) -> None:
    nested: object = "😀אבגד"
    for _ in range(20):
        nested = {"nested": nested}
    original = {"ok": "yes", "tree": nested}
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one", "arguments": original,
    }])
    tool = json.loads(run_ch(tmp_path, str(session), "-t:i:s=8", "-f", "json"))[0]["content"][0]
    assert {"ok": tool.get("ok"), "tree": tool.get("tree")} == original, tool


def test_tool_output_blocks_keep_transport_types_and_share_a_budget(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{"type": "toolCall", "name": "Custom", "id": "call-one", "arguments": {}}])
    with session.open("a") as stream:
        stream.write("\n" + json.dumps({"type": "message", "message": {
            "role": "toolResult", "toolCallId": "call-one", "toolName": "Custom",
            "content": [{"type": "text", "text": "א" * 40}, {"type": "text", "text": "ב" * 40}],
        }}))
    structured = run_ch(tmp_path, str(session), "-t:o:s=20", "-f", "json")
    tool = json.loads(structured)[0]["content"][0]
    assert tool["type"] == "tool-output" and tool["name"] == "Custom", tool
    assert all(block["type"] == "text" for block in tool["content"]), tool
    assert sum(len(block["text"]) for block in tool["content"]) <= 20, tool
    assert all(block["text"] for block in tool["content"]), tool
    xml = run_ch(tmp_path, str(session), "-t:o:s=20", "--color=never", "--no-metadata")
    assert run_ch(tmp_path, "parse", source=structured) == xml
    assert xml.strip() in run_ch(tmp_path, "search", ".", "-t:o:s=20", "--color=never", "--no-metadata")


def test_distinct_policies_keep_separate_shared_message_budgets(tmp_path: Path) -> None:
    session = write_session(tmp_path, [
        {"type": "text", "text": "TEXT" * 40},
        {"type": "toolCall", "name": "Bash", "id": "call-one", "arguments": {"command": "FIRST" * 40}},
        {"type": "toolCall", "name": "Bash", "id": "call-two", "arguments": {"command": "LAST" * 40}},
    ])
    message = json.loads(run_ch(tmp_path, str(session), "--short=20", "-t:Bash:s=10", "-f", "json"))[0]
    text = next(block for block in message["content"] if isinstance(block, str))
    tools = [block for block in message["content"] if isinstance(block, dict)]
    assert len(text) == 20, message
    assert sum(len(tool["command"]) for tool in tools) == 10, message
    assert all(tool["command"] for tool in tools), message


def test_global_budget_covers_text_thinking_tools_and_plan(tmp_path: Path) -> None:
    session = write_session(tmp_path, [
        {"type": "text", "text": "TEXT" * 40},
        {"type": "thinking", "thinking": "THOUGHT" * 40},
        {"type": "toolCall", "name": "Bash", "id": "call-one", "arguments": {"command": "COMMAND" * 40}},
        {"type": "toolCall", "name": "ExitPlanMode", "id": "call-two", "arguments": {"plan": "PLAN" * 40}},
    ])
    message = json.loads(run_ch(tmp_path, str(session), "--short=20", "-A", "-f", "json"))[0]
    values = [block if isinstance(block, str) else next(block[key] for key in ("content", "command", "plan") if key in block) for block in message["content"]]
    assert len(values) == 4 and all(values), message
    assert sum(map(len, values)) <= 20, message


def test_more_tools_than_characters_keeps_identity_without_overflow(tmp_path: Path) -> None:
    session = write_session(tmp_path, [
        {"type": "toolCall", "name": "Bash", "id": f"call-{index}", "arguments": {"command": "COMMAND" * 40}}
        for index in range(30)
    ])
    message = json.loads(run_ch(tmp_path, str(session), "-t:i:s=8", "-f", "json"))[0]
    tools = message["content"]
    assert len(tools) == 30, message
    assert [tool["native_tool_call_id"] for tool in tools] == [f"call-{index}" for index in range(30)], message
    assert sum(len(tool.get("command", "")) for tool in tools) <= 8, message
    assert any(tool.get("command") in ("…", "[…]") for tool in tools), message


def test_json_previews_show_markers_without_decoding_literal_backslash_u(tmp_path: Path) -> None:
    session = write_session(tmp_path, [{
        "type": "toolCall", "name": "Custom", "id": "call-one",
        "arguments": {"literal": r"\u2026", "unicode": "א😀", "body": "abcdefghijklmnopqrst" * 10},
    }])
    outputs = [
        run_ch(tmp_path, str(session), "-t:i:s=32", "--color=never", "--no-metadata"),
        run_ch(tmp_path, str(session), "-t:i:s=32", "-f", "raw"),
        run_ch(tmp_path, "search", ".", "-t:i:s=32", "--color=never", "--no-metadata"),
        run_ch(tmp_path, "search", ".", "-t:i:s=32", "--raw"),
    ]
    for output in outputs:
        assert "[…]" in output, output
        assert r'"literal": "\\u2026"' in output, output
        assert r'"unicode": "\u05d0\ud83d\ude00"' in output, output
        assert "א" not in output and "😀" not in output, output
    structured = run_ch(tmp_path, str(session), "-t:i:s=32", "-f", "json")
    assert run_ch(tmp_path, "parse", source=structured) == outputs[0]
    canonical = run_ch(tmp_path, "parse", "-f", "json", source=outputs[0])
    tool = json.loads(canonical)[0]["content"][0]
    assert tool["literal"] == r"\u2026" and tool["unicode"] == "א😀", tool
    assert run_ch(tmp_path, "parse", source=canonical) == outputs[0]


@pytest.mark.parametrize("number", ["1e-7", "0.000001", "0.00001", "1e+20", "1.00e+20", "1.0", "-0.0", "2.5e-08", "1.25E+2"])
def test_float_spelling_uses_the_same_budget_in_parse_and_search(tmp_path: Path, number: str) -> None:
    session = write_session(tmp_path, [])
    header = json.dumps({"type": "session", "version": 3, "id": "structure-budget", "cwd": "/tmp/structure-budget"})
    session.write_text(header + '\n{"type":"message","message":{"role":"assistant","content":'
                       '[{"type":"toolCall","name":"Custom","id":"call-one","arguments":'
                       '{"number":' + number + ',"body":"abcdefghijklmnopqrst"}}]}}')
    structured = run_ch(tmp_path, str(session), "-t:i:s=8", "-f", "json")
    tool = json.loads(structured)[0]["content"][0]
    assert tool.get("number") == json.loads(number) and isinstance(tool.get("number"), float), tool
    assert value_characters({"number": tool["number"], "body": tool["body"]}) <= 8, tool
    xml = run_ch(tmp_path, str(session), "-t:i:s=8", "--color=never", "--no-metadata")
    searched = run_ch(tmp_path, "search", ".", "-t:i:s=8", "--color=never", "--no-metadata")
    assert xml.strip() in searched, searched
    assert run_ch(tmp_path, "parse", source=structured) == xml


@pytest.mark.parametrize("budget", [8, 17, 64])
def test_nested_payload_corpus_stays_within_budget_and_matches_native_search(tmp_path: Path, budget: int) -> None:
    payloads = [
        {"action": "go", "rows": [{"label": f"row-{index}", "values": [False, None, 12345, "😀אבגד" * 20]} for index in range(40)]},
        {"type": "payload-type", "name": "payload-name", "id": "payload-id", "body": "content" * 100},
        {"empty": "", "empty_dict": {}, "empty_list": [], "items": [str(index) for index in range(100)]},
        {"numbers": [10 ** 18, -12345, 1e-7, True, False, None] * 20},
        {"lines": "start\n" + ("long line " * 40 + "\n") * 30 + "end"},
        {"input": {"nested": {"inner": ["long" * 50] * 50}}},
    ]
    session = write_session(tmp_path, [{"type": "toolCall", "name": "Custom", "id": "call-0", "arguments": payloads[0]}])
    with session.open("a") as stream:
        for index, payload in enumerate(payloads[1:], 1):
            stream.write("\n" + json.dumps({"type": "message", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "name": "Custom", "id": f"call-{index}", "arguments": payload},
            ]}}))
    structured = run_ch(tmp_path, str(session), f"-t:i:s={budget}", "-f", "json")
    messages = json.loads(structured)
    assert len(messages) == len(payloads), messages
    metadata = {"type", "name", "id", "native_content_index", "native_tool_call_id"}
    for message in messages:
        tool = message["content"][0]
        payload = {key: value for key, value in tool.items() if key not in metadata}
        assert value_characters(payload) <= budget, (budget, tool)
        assert tool["name"] == "Custom" and tool["native_tool_call_id"].startswith("call-"), tool
    xml = run_ch(tmp_path, str(session), f"-t:i:s={budget}", "--color=never", "--no-metadata")
    assert run_ch(tmp_path, "parse", source=structured) == xml
    searched = run_ch(tmp_path, "search", ".", f"-t:i:s={budget}", "--color=never", "--no-metadata")
    assert xml.strip() in searched, searched
