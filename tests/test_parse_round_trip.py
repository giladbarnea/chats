from __future__ import annotations

from collections.abc import Iterator
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from chats.formatting import format_to_json, format_to_xml
from chats.model import ConversationFlags, Message, messages_from_json_data

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "data" / "parse-round-trip-fixtures"
MANIFEST_PATH = FIXTURE_ROOT / "MANIFEST.json"
CH_EXECUTABLE = Path(sys.executable).with_name("ch")

PROVIDERS = {"claude", "pi", "codex", "antigravitycli"}
CONFIGURATION_ARGUMENTS = {
    "bare": [],
    "with-tools": ["-t"],
    "tools-shortened": ["-t:s"],
    "with-agents": ["--agents"],
    "tools-and-agents": ["-t", "--agents"],
}
CONFIGURATION_COMMAND_TOKENS = {
    "bare": ["{session_id}"],
    "with-tools": ["{session_id}", "-t"],
    "tools-shortened": ["-t:s", "{session_id}"],
    "with-agents": ["{session_id}", "--agents"],
    "tools-and-agents": ["{session_id}", "-t", "--agents"],
}
MANIFEST_ROWS = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["fixtures"]


def _fixture_id(row: dict[str, object]) -> str:
    return f"{row['provider_adapter']}-{row['configuration']}"


def _byte_summary(content: bytes) -> str:
    return f"{len(content)} bytes, sha256={hashlib.sha256(content).hexdigest()}"


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for nested in value.values():
            yield from _nested_values(nested)
    if isinstance(value, list):
        for nested in value:
            yield from _nested_values(nested)


def test_static_fixtures_cover_the_exact_adapter_configuration_matrix() -> None:
    actual_matrix = {
        (row["provider_adapter"], row["configuration"]) for row in MANIFEST_ROWS
    }
    expected_matrix = set(itertools.product(PROVIDERS, CONFIGURATION_ARGUMENTS))
    session_ids = [row["session_id"] for row in MANIFEST_ROWS]

    assert actual_matrix == expected_matrix, (
        "Expected one stored fixture pair for every adapter/configuration combination. "
        f"Missing: {expected_matrix - actual_matrix!r}; "
        f"unexpected: {actual_matrix - expected_matrix!r}."
    )
    assert len(MANIFEST_ROWS) == 20, (
        f"Expected the 4-adapter x 5-configuration corpus to contain 20 rows. "
        f"Got: {len(MANIFEST_ROWS)}."
    )
    assert len(set(session_ids)) == 20, (
        "Expected every stored fixture row to come from a globally distinct session. "
        f"Got session IDs: {session_ids!r}."
    )

    native_sessions = list(FIXTURE_ROOT.rglob("*.jsonl"))
    assert not native_sessions, (
        "Expected the static corpus to contain only stored `ch` JSON/XML outputs, "
        f"never provider-native JSONL sessions. Got: {native_sessions!r}."
    )

    for row in MANIFEST_ROWS:
        configuration = row["configuration"]
        assert row["arguments"] == CONFIGURATION_ARGUMENTS[configuration], (
            f"Expected {configuration!r} to record its exact source CLI arguments. "
            f"Got: {row['arguments']!r}."
        )
        expected_xml_command = [
            "ch",
            *[
                row["session_id"] if token == "{session_id}" else token
                for token in CONFIGURATION_COMMAND_TOKENS[configuration]
            ],
        ]
        assert row["xml_command"] == expected_xml_command, (
            f"Expected the exact source command for {_fixture_id(row)}. "
            f"Expected: {expected_xml_command!r}; got: {row['xml_command']!r}."
        )
        assert row["json_command"] == [*expected_xml_command, "-f", "json"], (
            "Expected each stored input to use that exact source command plus "
            f"`-f json`. Got: {row['json_command']!r}."
        )

        input_path = (PROJECT_ROOT / row["input_json"]).resolve()
        expected_path = (PROJECT_ROOT / row["expected_xml"]).resolve()
        assert input_path.is_relative_to(FIXTURE_ROOT.resolve()), (
            f"Expected manifest input paths to stay inside the static corpus. "
            f"Got: {input_path}."
        )
        assert expected_path.is_relative_to(FIXTURE_ROOT.resolve()), (
            f"Expected manifest oracle paths to stay inside the static corpus. "
            f"Got: {expected_path}."
        )
        assert input_path.is_file() and input_path.suffix == ".json", (
            f"Expected a stored `ch ... -f json` input file. Got: {input_path}."
        )
        assert expected_path.is_file() and expected_path.suffix == ".xml", (
            f"Expected a stored plain XML-tagged Markdown file. Got: {expected_path}."
        )
        assert expected_path.read_bytes(), (
            f"Expected a substantive stored Markdown oracle. Got empty: {expected_path}."
        )
        for fixture_path in (input_path, expected_path):
            assert b"sk-or-v1-" not in fixture_path.read_bytes(), (
                "Expected committed round-trip fixtures to redact OpenRouter credentials. "
                f"Found a credential prefix in: {fixture_path}."
            )

        stored_json = json.loads(input_path.read_text(encoding="utf-8"))
        assert isinstance(stored_json, list) and stored_json, (
            f"Expected {input_path} to contain a non-empty JSON array, exactly as "
            "`ch ... -f json` emits."
        )
        nested_values = list(_nested_values(stored_json))
        typed_tool_blocks = [
            value
            for value in nested_values
            if isinstance(value, dict)
            and value.get("type") in {"tool-input", "tool-output"}
        ]
        if any(argument.startswith("-t") for argument in row["arguments"]):
            assert typed_tool_blocks, (
                f"Expected tool-enabled fixture {_fixture_id(row)} to contain a typed "
                "tool block."
            )
        if configuration == "tools-shortened":
            assert any(
                isinstance(value, str) and "\n...\n" in value
                for tool_block in typed_tool_blocks
                for value in _nested_values(tool_block)
            ), (
                f"Expected shortened fixture {_fixture_id(row)} to contain an actual "
                "recursively shortened string inside a typed tool block."
            )
        if row["provider_adapter"] == "claude" and "--agents" in row["arguments"]:
            assert any(
                isinstance(message, dict) and message.get("type") == "agent"
                for message in stored_json
            ), (
                f"Expected Claude agent fixture {_fixture_id(row)} to contain a "
                "top-level agent message."
            )


@pytest.mark.parametrize("row", MANIFEST_ROWS, ids=_fixture_id)
def test_parse_reconstructs_stored_markdown_byte_for_byte(
    row: dict[str, object],
    tmp_path: Path,
) -> None:
    input_path = (PROJECT_ROOT / row["input_json"]).resolve()
    expected_path = (PROJECT_ROOT / row["expected_xml"]).resolve()
    assert CH_EXECUTABLE.is_file(), (
        f"Expected the installed public `ch` executable beside pytest's Python. "
        f"Got: {CH_EXECUTABLE}."
    )
    assert input_path.is_file() and expected_path.is_file(), (
        f"Expected committed static fixture files for {_fixture_id(row)}. "
        f"Input exists: {input_path.is_file()}; expected exists: {expected_path.is_file()}."
    )

    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path)
    environment["TZ"] = "Asia/Jerusalem"
    completed = subprocess.run(
        [str(CH_EXECUTABLE), "parse", str(input_path)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
    )
    expected = expected_path.read_bytes()

    assert completed.returncode == 0, (
        f"Expected public `ch parse <json-file>` to succeed for {_fixture_id(row)}. "
        f"Exit code: {completed.returncode}; stdout: {completed.stdout[:500]!r}; "
        f"stderr: {completed.stderr[:500]!r}."
    )
    assert completed.stdout == expected, (
        f"Expected `ch parse {input_path}` stdout to equal the stored plain Markdown "
        f"conversation byte-for-byte for {_fixture_id(row)}. "
        f"Expected {_byte_summary(expected)}; got {_byte_summary(completed.stdout)}. "
        f"stderr: {completed.stderr[:500]!r}."
    )


def test_json_messages_preserve_metadata_required_to_rebuild_xml_wrappers() -> None:
    flags = ConversationFlags(color="never", paging=False)
    message = Message(
        role="assistant",
        index=7,
        text="Named agent response",
        agent_id="019ecaa3-3e57-7150-bb03-2c582bede7ba",
        subagent_type="default",
        name="Planck",
        model="gpt-5.4-mini",
        timestamp="2026-06-15T09:35:42.123Z",
    )

    actual = json.loads(format_to_json([message], flags))

    assert actual == [
        {
            "type": "agent",
            "role": "assistant",
            "original_index": 7,
            "content": ["Named agent response"],
            "agent_id": "019ecaa3-3e57-7150-bb03-2c582bede7ba",
            "subagent_type": "default",
            "name": "Planck",
            "model": "gpt-5.4-mini",
            "timestamp": "2026-06-15T09:35:42.123Z",
        }
    ], (
        "Expected structured JSON to retain the raw message timestamp and agent name "
        "needed to reconstruct XML `date=`, `name=`, and named-agent headers. "
        f"Got: {actual!r}."
    )


@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        pytest.param(
            "Unknown", {"content": "value"}, id="unknown-content-field"
        ),
        pytest.param(
            "Patch", {"input": {"type": "inner"}}, id="nested-input-field"
        ),
        pytest.param(
            "Unknown", {"id": "inner-id"}, id="body-id-without-tool-id"
        ),
    ],
)
def test_structured_json_round_trip_preserves_ambiguous_tool_input_dicts(
    tool_name: str,
    tool_input: dict[str, object],
) -> None:
    flags = ConversationFlags(show_tools=True, color="never", paging=False)
    message = Message(
        role="assistant",
        index=1,
        tools=[{"type": "tool_use", "name": tool_name, "input": tool_input}],
    )
    expected_xml = format_to_xml([message], flags)

    json_data = json.loads(format_to_json([message], flags))
    assert json_data == [
        {
            "type": "assistant-response",
            "role": "assistant",
            "original_index": 1,
            "content": [
                {
                    "type": "tool-input",
                    "name": tool_name,
                    "input": tool_input,
                }
            ],
        }
    ], (
        "Expected ambiguous tool-input dictionaries to use an explicit nested input "
        f"wrapper. Input: {tool_input!r}; serialized: {json_data!r}."
    )

    reconstructed = messages_from_json_data(json_data)
    actual_xml = format_to_xml(reconstructed, flags)

    assert actual_xml == expected_xml, (
        "Expected structured JSON serialization and inversion to preserve the complete "
        f"tool-input dictionary. Input: {tool_input!r}; serialized: {json_data!r}; "
        f"expected XML: {expected_xml!r}; actual XML: {actual_xml!r}."
    )
