from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SOURCE_FIXTURE = PROJECT_ROOT / "tests" / "data" / "pi-custom-message.jsonl"
CH_EXECUTABLE = Path(sys.executable).with_name("ch")


def _copy_pi_fixture(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    session_path = home / ".pi" / "agent" / "sessions" / "project" / SOURCE_FIXTURE.name
    session_path.parent.mkdir(parents=True)
    with SOURCE_FIXTURE.open(encoding="utf-8") as source, session_path.open(
        "w", encoding="utf-8"
    ) as target:
        target.write(source.read())
    return home, session_path


def _copy_pi_custom_fixture(tmp_path: Path) -> tuple[Path, Path]:
    home, session_path = _copy_pi_fixture(tmp_path)
    with (
        SOURCE_FIXTURE.open(encoding="utf-8") as source,
        session_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            entry = json.loads(line)
            if entry.get("type") in {"session", "custom", "custom_message"}:
                target.write(line)
    return home, session_path


def _derive_pi_fixture(
    tmp_path: Path,
    selector: Callable[[dict[str, object]], bool],
    mutate: Callable[[dict[str, object]], None],
) -> tuple[Path, Path]:
    home, session_path = _copy_pi_fixture(tmp_path)
    matched = False
    with (
        SOURCE_FIXTURE.open(encoding="utf-8") as source,
        session_path.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            entry: dict[str, object] = json.loads(line)
            if entry.get("type") == "session":
                target.write(line)
                continue
            if matched or not selector(entry):
                continue
            mutate(entry)
            target.write(json.dumps(entry, ensure_ascii=False) + "\n")
            matched = True
    assert matched, "Expected to derive one matching record from the Pi fixture."
    return home, session_path


def _run_ch(
    home: Path,
    *arguments: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if "--color=always" in arguments:
        environment.pop("NO_COLOR", None)
        environment["TERM"] = "xterm-256color"
    environment["HOME"] = str(home)
    environment["TZ"] = "Asia/Jerusalem"
    environment["COLORTERM"] = "truecolor"
    return subprocess.run(
        [str(CH_EXECUTABLE), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_unsquashed_pi_user_agent_custom_messages_stay_hidden(
    tmp_path: Path,
) -> None:
    task = "UNSQUASHED_AGENT_TASK"
    response = "UNSQUASHED_AGENT_RESPONSE"

    def select(entry: dict[str, object]) -> bool:
        return (
            entry.get("type") == "custom_message"
            and entry.get("customType") == "pi-user-agents"
        )

    def mutate(entry: dict[str, object]) -> None:
        details = entry.get("details")
        assert isinstance(details, dict), f"Expected agent details. Got: {details!r}."
        entry["content"] = f"{task}\n{response}"
        details["task"] = task
        details["mainContextState"] = "separate"

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    completed = _run_ch(
        home,
        str(session_path),
        "--color=never",
        "--no-metadata",
    )

    assert completed.returncode == 0, completed.stderr
    assert task not in completed.stdout and response not in completed.stdout, (
        "Expected an unsquashed Pi user-agent message to stay out of default output. "
        f"stdout: {completed.stdout!r}."
    )


def test_generic_pi_custom_messages_are_hidden_by_default_and_shown_by_all(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_fixture(tmp_path)

    default = _run_ch(
        home,
        str(session_path),
        "--color=never",
        "--no-metadata",
    )
    show_all = _run_ch(
        home,
        str(session_path),
        "--all",
        "--color=never",
        "--no-metadata",
    )

    assert default.returncode == 0, (
        "Expected the public CLI to parse the Pi fixture with default visibility. "
        f"stderr: {default.stderr!r}."
    )
    assert "stale_queued_tool_results_dropped" not in default.stdout, (
        "Expected default Pi output to hide arbitrary custom data. "
        f"stdout: {default.stdout!r}."
    )
    assert show_all.returncode == 0, (
        f"Expected `--all` to parse the Pi fixture. stderr: {show_all.stderr!r}."
    )
    assert 'custom_type="claude-bridge-integrity"' in show_all.stdout, (
        "Expected `--all` to identify the arbitrary Pi custom type. "
        f"stdout: {show_all.stdout!r}."
    )
    assert '"label": "stale_queued_tool_results_dropped"' in show_all.stdout, (
        "Expected `--all` to render arbitrary Pi custom data without a fixed schema. "
        f"stdout: {show_all.stdout!r}."
    )


@pytest.mark.parametrize(
    ("custom_type", "sentinel"),
    [
        pytest.param(
            "subagents:record", "PARTIAL_SUBAGENT_RECORD", id="subagent-record"
        ),
    ],
)
def test_all_renders_partial_special_pi_custom_records_as_generic_data(
    tmp_path: Path,
    custom_type: str,
    sentinel: str,
) -> None:
    def select(entry: dict[str, object]) -> bool:
        return entry.get("type") == "custom" and entry.get("customType") == custom_type

    def mutate(entry: dict[str, object]) -> None:
        entry["data"] = {"unexpected": sentinel}

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    completed = _run_ch(
        home,
        str(session_path),
        "--all",
        "--color=never",
        "--no-metadata",
    )

    assert completed.returncode == 0, (
        f"Expected `--all` to preserve a partial {custom_type} record. "
        f"stderr: {completed.stderr!r}."
    )
    assert f'custom_type="{custom_type}"' in completed.stdout, (
        f"Expected generic output for the partial {custom_type} record. "
        f"stdout: {completed.stdout!r}."
    )
    assert sentinel in completed.stdout, (
        f"Expected generic output to retain arbitrary {custom_type} data. "
        f"stdout: {completed.stdout!r}."
    )


def test_generic_pi_custom_type_round_trips_xml_attribute_characters(
    tmp_path: Path,
) -> None:
    custom_type = 'custom "quoted" & <angled>'

    def select(entry: dict[str, object]) -> bool:
        return (
            entry.get("type") == "custom"
            and entry.get("customType") == "claude-bridge-integrity"
        )

    def mutate(entry: dict[str, object]) -> None:
        entry["customType"] = custom_type
        entry["data"] = {"sentinel": "ESCAPED_CUSTOM_TYPE"}

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    native_xml = _run_ch(
        home,
        str(session_path),
        "--all",
        "--color=never",
        "--no-metadata",
    )

    assert native_xml.returncode == 0, native_xml.stderr
    assert (
        'custom_type="custom &quot;quoted&quot; &amp; &lt;angled&gt;"'
        in native_xml.stdout
    ), (
        f"Expected the arbitrary custom type to be XML-safe. stdout: {native_xml.stdout!r}."
    )

    canonical_json = _run_ch(
        home,
        "parse",
        "--format=json",
        input_text=native_xml.stdout,
    )
    assert canonical_json.returncode == 0, canonical_json.stderr
    messages = json.loads(canonical_json.stdout)
    assert messages[0].get("custom_type") == custom_type, (
        f"Expected XML parsing to restore the custom type. Got: {messages!r}."
    )

    rebuilt_xml = _run_ch(home, "parse", input_text=canonical_json.stdout)
    assert rebuilt_xml.returncode == 0, rebuilt_xml.stderr
    assert rebuilt_xml.stdout == native_xml.stdout, (
        "Expected the escaped custom type to stabilize across the public transport path."
    )


def test_pi_agent_metadata_round_trips_xml_attribute_characters(
    tmp_path: Path,
) -> None:
    metadata_value = 'metadata "quoted" & <angled>'

    def select(entry: dict[str, object]) -> bool:
        return entry.get("customType") == "pi-simple-team"

    def mutate(entry: dict[str, object]) -> None:
        details = entry.get("details")
        assert isinstance(details, dict), f"Expected team details. Got: {details!r}."
        details["from"] = metadata_value

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    native_xml = _run_ch(home, str(session_path), "--agents", "--color=never", "--no-metadata")

    assert native_xml.returncode == 0, native_xml.stderr
    escaped_value = "metadata &quot;quoted&quot; &amp; &lt;angled&gt;"
    assert f'name="{escaped_value}"' in native_xml.stdout, (
        f"Expected an XML-safe agent name. stdout: {native_xml.stdout!r}."
    )

    canonical_json = _run_ch(home, "parse", "--format=json", input_text=native_xml.stdout)
    assert canonical_json.returncode == 0, canonical_json.stderr
    messages = json.loads(canonical_json.stdout)
    assert len(messages) == 1, f"Expected one agent message. Got: {messages!r}."
    assert messages[0].get("name") == metadata_value, (
        f"Expected XML parsing to restore the agent name. Got: {messages!r}."
    )

    rebuilt_xml = _run_ch(home, "parse", input_text=canonical_json.stdout)
    assert rebuilt_xml.returncode == 0, rebuilt_xml.stderr
    assert rebuilt_xml.stdout == native_xml.stdout, "Expected the escaped agent name to stabilize."


def test_retired_subagent_extension_records_are_generic_custom_data(
    tmp_path: Path,
) -> None:
    """Retired extension records remain generic custom data, not current agent deliveries."""
    home, session_path = _copy_pi_fixture(tmp_path)
    hidden_display_sentinel = "CUSTOM_ENVELOPE_DISPLAY_FALSE_SENTINEL"
    with session_path.open("a", encoding="utf-8") as target:
        target.write(json.dumps({
            "type": "custom",
            "customType": "duplicate-record",
            "display": False,
            "data": {"sentinel": hidden_display_sentinel},
        }) + "\n")

    agents = _run_ch(home, str(session_path), "--agents", "--color=never", "--no-metadata")
    show_all = _run_ch(home, str(session_path), "--all", "--color=never", "--no-metadata")

    assert agents.returncode == show_all.returncode == 0, agents.stderr + show_all.stderr
    assert 'custom_type="subagents:record"' not in agents.stdout, (
        f"Expected no subagents:record agent under --agents. stdout: {agents.stdout!r}."
    )
    assert '<custom i=' in show_all.stdout and 'custom_type="subagents:record"' in show_all.stdout, (
        f"Expected --all to show the record as generic custom data. stdout: {show_all.stdout!r}."
    )
    for completed in (agents, show_all):
        assert 'custom_type="subagent-notification"' not in completed.stdout, completed.stdout
        assert hidden_display_sentinel not in completed.stdout, completed.stdout


def test_agents_emit_structured_pi_custom_messages_as_agent_data(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_fixture(tmp_path)

    completed = _run_ch(home, str(session_path), "--agents", "--format=json", "--no-metadata")

    assert completed.returncode == 0, completed.stderr
    messages = json.loads(completed.stdout)
    record = next(message for message in messages if message.get("agent_id") == "scout")
    assert record.get("custom_type") == "pi-simple-team", f"Got: {record!r}."
    assert record.get("native_entry_id") == "a0000006", (
        f"Expected the source Pi entry id. Got: {record!r}."
    )


def test_pi_agent_text_inner_blocks_round_trip_as_text(
    tmp_path: Path,
) -> None:
    literal_text = "<thinking>\nLITERAL_AGENT_TEXT\n</thinking>"
    custom_type = "pi-simple-team"

    def select(entry: dict[str, object]) -> bool:
        return entry.get("customType") == custom_type

    def mutate(entry: dict[str, object]) -> None:
        details = entry.get("details")
        assert isinstance(details, dict), f"Expected team details. Got: {details!r}."
        details["message"] = literal_text

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    native_xml = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--color=never",
        "--no-metadata",
    )
    native_raw = _run_ch(home, str(session_path), "--agents", "--raw")
    assert native_xml.returncode == 0, native_xml.stderr
    assert native_raw.returncode == 0, native_raw.stderr
    assert "&lt;thinking&gt;" in native_xml.stdout, (
        f"Expected plain XML to encode colliding text. stdout: {native_xml.stdout!r}."
    )
    assert literal_text in native_raw.stdout, (
        f"Expected raw output to preserve the agent text. stdout: {native_raw.stdout!r}."
    )
    assert "&lt;thinking&gt;" not in native_raw.stdout, (
        f"Expected XML transport entities to stay out of raw output. stdout: {native_raw.stdout!r}."
    )

    canonical_json = _run_ch(
        home,
        "parse",
        "--format=json",
        input_text=native_xml.stdout,
    )
    assert canonical_json.returncode == 0, canonical_json.stderr
    messages = json.loads(canonical_json.stdout)
    interaction = next(
        (
            message
            for message in messages
            if message.get("custom_type") == custom_type
        ),
        {},
    )
    text_blocks = [
        block for block in interaction.get("content", []) if isinstance(block, str)
    ]
    assert text_blocks == [literal_text], (
        f"Expected the canonical inner block to remain agent text. Got: {messages!r}."
    )
    assert not any(
        isinstance(block, dict) and block.get("type") == "thinking"
        for block in interaction.get("content", [])
    ), f"Expected XML parsing not to reclassify agent text. Got: {messages!r}."

    rebuilt_xml = _run_ch(home, "parse", input_text=canonical_json.stdout)
    assert rebuilt_xml.returncode == 0, rebuilt_xml.stderr
    assert rebuilt_xml.stdout == native_xml.stdout, (
        "Expected colliding agent text to stabilize across XML and JSON."
    )


def test_pi_agent_text_unmatched_inner_opening_round_trips_before_thinking(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    literal_text = "TEXT_BEFORE\n<thinking>\nUNMATCHED_OPENING"
    thinking = "STRUCTURAL_THINKING"
    structured_messages = [
        {
            "type": "agent",
            "role": "agent",
            "original_index": 1,
            "custom_type": "pi-user-agents",
            "content": [
                {"type": "subagent-task", "content": "ROUND_TRIP_TASK"},
                literal_text,
                {"type": "thinking", "content": thinking},
            ],
        }
    ]

    native_xml = _run_ch(
        home,
        "parse",
        input_text=json.dumps(structured_messages),
    )
    assert native_xml.returncode == 0, native_xml.stderr
    assert 'text_encoding="html"' in native_xml.stdout, (
        "Expected an unmatched text opening delimiter to use XML transport encoding. "
        f"stdout: {native_xml.stdout!r}."
    )

    canonical_json = _run_ch(
        home,
        "parse",
        "--format=json",
        input_text=native_xml.stdout,
    )
    assert canonical_json.returncode == 0, canonical_json.stderr
    messages = json.loads(canonical_json.stdout)
    interaction = messages[0] if messages else {}
    text_blocks = [
        block for block in interaction.get("content", []) if isinstance(block, str)
    ]
    thinking_blocks = [
        block
        for block in interaction.get("content", [])
        if isinstance(block, dict) and block.get("type") == "thinking"
    ]
    assert text_blocks == [literal_text], (
        f"Expected the unmatched opening to remain text. Got: {messages!r}."
    )
    assert [block.get("content") for block in thinking_blocks] == [thinking], (
        f"Expected the following thinking block to remain structural. Got: {messages!r}."
    )

    rebuilt_xml = _run_ch(home, "parse", input_text=canonical_json.stdout)
    assert rebuilt_xml.returncode == 0, rebuilt_xml.stderr
    assert rebuilt_xml.stdout == native_xml.stdout, (
        "Expected unmatched-opening XML transport to stabilize."
    )


def test_pi_custom_message_json_and_xml_round_trips_stabilize(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_custom_fixture(tmp_path)
    shared_arguments = (
        str(session_path),
        "--all",
        "--color=never",
        "--no-metadata",
    )

    native_xml = _run_ch(home, *shared_arguments)
    native_json = _run_ch(home, *shared_arguments, "--format=json")
    rebuilt_xml = _run_ch(home, "parse", input_text=native_json.stdout)

    assert native_xml.returncode == native_json.returncode == 0, (
        "Expected both native Pi transport formats to succeed. "
        f"XML stderr: {native_xml.stderr!r}; JSON stderr: {native_json.stderr!r}."
    )
    assert rebuilt_xml.returncode == 0, (
        "Expected public `ch parse` to accept Pi custom-message JSON. "
        f"stderr: {rebuilt_xml.stderr!r}."
    )
    assert rebuilt_xml.stdout == native_xml.stdout, (
        "Expected structured Pi custom-message JSON to rebuild the native XML output. "
        f"stderr: {rebuilt_xml.stderr!r}."
    )

    canonical_json = _run_ch(
        home,
        "parse",
        "--format=json",
        input_text=rebuilt_xml.stdout,
    )
    stabilized_xml = _run_ch(home, "parse", input_text=canonical_json.stdout)
    stabilized_json = _run_ch(
        home,
        "parse",
        "--format=json",
        input_text=stabilized_xml.stdout,
    )

    assert canonical_json.returncode == stabilized_xml.returncode == 0, (
        "Expected Pi custom-message XML and JSON conversions to succeed. "
        f"JSON stderr: {canonical_json.stderr!r}; XML stderr: {stabilized_xml.stderr!r}."
    )
    assert stabilized_json.returncode == 0, stabilized_json.stderr
    assert stabilized_xml.stdout == rebuilt_xml.stdout, (
        "Expected Pi custom-message XML to stabilize after canonical JSON conversion."
    )
    assert stabilized_json.stdout == canonical_json.stdout, (
        "Expected Pi custom-message JSON to stabilize after canonical XML conversion."
    )


def test_raw_output_preserves_normalized_pi_agent_interactions(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_custom_fixture(tmp_path)

    completed = _run_ch(home, str(session_path), "--all", "--raw")

    assert completed.returncode == 0, (
        f"Expected raw Pi agent output to succeed. stderr: {completed.stderr!r}."
    )
    assert "## Agent" in completed.stdout, (
        f"Expected raw output to identify agent messages. stdout: {completed.stdout!r}."
    )
    assert "# Synthetic teammate report" in completed.stdout, (
        f"Expected raw output to retain teammate messages. stdout: {completed.stdout!r}."
    )
    assert "## Custom" in completed.stdout, (
        f"Expected `--all` raw output to identify generic custom records. stdout: {completed.stdout!r}."
    )
    assert "stale_queued_tool_results_dropped" in completed.stdout, (
        f"Expected `--all` raw output to retain generic custom data. stdout: {completed.stdout!r}."
    )


@pytest.mark.parametrize("terminal", ["dumb", "xterm-256color"])
def test_colored_output_uses_agent_panels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
) -> None:
    monkeypatch.setenv("TERM", terminal)
    home, session_path = _copy_pi_custom_fixture(tmp_path)

    completed = _run_ch(
        home,
        str(session_path),
        "--all",
        "--color=always",
        "--no-paging",
        "--no-metadata",
    )
    plain = re.sub(r"\x1b\[[0-9;]*m", "", completed.stdout)

    assert completed.returncode == 0, (
        f"Expected colored Pi agent output to succeed. stderr: {completed.stderr!r}."
    )
    assert "\x1b[" in completed.stdout, (
        f"Expected `--color=always` to emit ANSI styles. stdout: {completed.stdout!r}."
    )
    assert "Agent" in plain, f"Expected shared agent panels. stdout: {plain!r}."
    assert "Synthetic teammate report" in plain, (
        f"Expected colored output to retain teammate messages. stdout: {plain!r}."
    )
    assert "Custom" in plain and "stale_queued_tool_results_dropped" in plain, (
        f"Expected `--all` color output to render generic custom records. stdout: {plain!r}."
    )
    assert (
        "<agent" not in plain and "<tool-output" not in plain and "<custom" not in plain
    ), f"Expected colored output to remain tag-free. stdout: {plain!r}."


def test_search_uses_pi_custom_message_visibility_flags(
    tmp_path: Path,
) -> None:
    home, _session_path = _copy_pi_custom_fixture(tmp_path)
    agent_needle = "Synthetic teammate report"
    custom_needle = "stale_queued_tool_results_dropped"

    hidden_agent = _run_ch(
        home,
        "search",
        agent_needle,
        "--provider=pi",
        "--only-id",
    )
    shown_agent = _run_ch(
        home,
        "search",
        agent_needle,
        "--provider=pi",
        "--only-id",
        "--agents",
    )
    hidden_custom = _run_ch(
        home,
        "search",
        custom_needle,
        "--provider=pi",
        "--only-id",
    )
    shown_custom = _run_ch(
        home,
        "search",
        custom_needle,
        "--provider=pi",
        "--only-id",
        "--all",
    )

    assert hidden_agent.returncode == 1 and not hidden_agent.stdout, (
        "Expected default search to ignore hidden Pi agent content. "
        f"stdout: {hidden_agent.stdout!r}; stderr: {hidden_agent.stderr!r}."
    )
    assert shown_agent.returncode == 0, (
        "Expected `--agents` search to find Pi teammate messages. "
        f"stderr: {shown_agent.stderr!r}."
    )
    assert shown_agent.stdout.strip() == "00000000-0000-4000-8000-000000000001", (
        f"Expected the source fixture session id. stdout: {shown_agent.stdout!r}."
    )
    assert hidden_custom.returncode == 1 and not hidden_custom.stdout, (
        "Expected default search to ignore arbitrary Pi custom data. "
        f"stdout: {hidden_custom.stdout!r}; stderr: {hidden_custom.stderr!r}."
    )
    assert shown_custom.returncode == 0, (
        "Expected `--all` search to find arbitrary Pi custom data. "
        f"stderr: {shown_custom.stderr!r}."
    )
    assert shown_custom.stdout.strip() == "00000000-0000-4000-8000-000000000001", (
        f"Expected the source fixture session id. stdout: {shown_custom.stdout!r}."
    )


def test_search_confirms_text_generated_by_pi_custom_normalization(
    tmp_path: Path,
) -> None:
    custom_home, _session_path = _copy_pi_custom_fixture(tmp_path / "custom")
    pretty_json = _run_ch(
        custom_home,
        "search",
        '"label": "stale_queued_tool_results_dropped"',
        "--provider=pi",
        "--only-id",
        "--all",
        "--case-sensitive",
    )

    expected_session_id = "00000000-0000-4000-8000-000000000001"
    assert pretty_json.returncode == 0, (
        "Expected search to inspect pretty-printed Pi custom JSON after raw gates. "
        f"stderr: {pretty_json.stderr!r}."
    )
    assert pretty_json.stdout.strip() == expected_session_id, (
        f"Expected the Pi custom JSON session. stdout: {pretty_json.stdout!r}."
    )
