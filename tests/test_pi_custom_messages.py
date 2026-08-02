from __future__ import annotations

import json
import os
import re
import shutil
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
    shutil.copyfile(SOURCE_FIXTURE, session_path)
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
        pytest.param("pi-user-agents", "PARTIAL_USER_AGENT", id="user-agent"),
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


def test_agents_render_successful_pi_user_agents_as_interactions(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_fixture(tmp_path)

    default = _run_ch(
        home,
        str(session_path),
        "--color=never",
        "--no-metadata",
    )
    agents = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--color=never",
        "--no-metadata",
    )

    task = "where's the js/css/html of the visual map?"
    response = "The visual map is one self-contained HTML file:"
    assert default.returncode == 0, default.stderr
    assert task not in default.stdout and response not in default.stdout, (
        "Expected default Pi output to hide user-agent interactions. "
        f"stdout: {default.stdout!r}."
    )
    assert agents.returncode == 0, (
        "Expected `--agents` to parse successful Pi user agents. "
        f"stderr: {agents.stderr!r}."
    )
    assert (
        "<agent " in agents.stdout and 'custom_type="pi-user-agents"' in agents.stdout
    ), (
        "Expected a successful Pi user agent to use the shared agent wrapper. "
        f"stdout: {agents.stdout!r}."
    )
    assert 'model="openai-codex/gpt-5.6-luna (gpt56l)"' in agents.stdout, (
        "Expected the agent model to come from details metadata. "
        f"stdout: {agents.stdout!r}."
    )
    assert 'model="claude-bridge/claude-opus-5 (Claude Opus 5)"' in agents.stdout, (
        "Expected Pi model metadata to stay byte-faithful even with a claude prefix. "
        f"stdout: {agents.stdout!r}."
    )
    assert 'inherited_context="true"' in agents.stdout, (
        "Expected inherited-context details to remain agent metadata. "
        f"stdout: {agents.stdout!r}."
    )
    assert "<subagent-task>" in agents.stdout and task in agents.stdout, (
        "Expected details.task to render with agent-input semantics. "
        f"stdout: {agents.stdout!r}."
    )
    assert response in agents.stdout, (
        "Expected only the response element body to become the agent response. "
        f"stdout: {agents.stdout!r}."
    )
    assert "<user_agent" not in agents.stdout, (
        "Expected the native Pi wrapper to be normalized instead of printed verbatim. "
        f"stdout: {agents.stdout!r}."
    )
    assert "stale_queued_tool_results_dropped" not in agents.stdout, (
        "Expected `--agents` not to expose unrelated custom data. "
        f"stdout: {agents.stdout!r}."
    )


def test_successful_pi_user_agents_use_details_metadata_and_response_content(
    tmp_path: Path,
) -> None:
    def select(entry: dict[str, object]) -> bool:
        return (
            entry.get("type") == "custom"
            and entry.get("customType") == "pi-user-agents"
        )

    def mutate(entry: dict[str, object]) -> None:
        data = entry.get("data")
        assert isinstance(data, dict), f"Expected custom data. Got: {data!r}."
        details = data.get("details")
        content = data.get("content")
        assert isinstance(details, dict), (
            f"Expected details metadata. Got: {details!r}."
        )
        assert isinstance(content, str), (
            f"Expected native agent content. Got: {content!r}."
        )
        details["task"] = "DETAILS_TASK_SENTINEL"
        details["model"] = "DETAILS_MODEL_SENTINEL"
        details["inheritedContext"] = False
        content = re.sub(
            r'model="[^"]*"',
            'model="CONTENT_MODEL_SENTINEL"',
            content,
            count=1,
        )
        content = re.sub(
            r"<task>.*?</task>",
            "<task>CONTENT_TASK_SENTINEL</task>",
            content,
            count=1,
            flags=re.DOTALL,
        )
        data["content"] = re.sub(
            r"<response>.*?</response>",
            "<response>CONTENT_RESPONSE_SENTINEL</response>",
            content,
            count=1,
            flags=re.DOTALL,
        )

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    completed = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--color=never",
        "--no-metadata",
    )

    assert completed.returncode == 0, completed.stderr
    assert "DETAILS_TASK_SENTINEL" in completed.stdout, (
        f"Expected the task from details metadata. stdout: {completed.stdout!r}."
    )
    assert 'model="DETAILS_MODEL_SENTINEL"' in completed.stdout, (
        f"Expected the model from details metadata. stdout: {completed.stdout!r}."
    )
    assert 'inherited_context="false"' in completed.stdout, (
        f"Expected inherited context from details metadata. stdout: {completed.stdout!r}."
    )
    assert "CONTENT_RESPONSE_SENTINEL" in completed.stdout, (
        f"Expected the response element body from native content. stdout: {completed.stdout!r}."
    )
    assert "CONTENT_TASK_SENTINEL" not in completed.stdout, (
        f"Expected native task content to be ignored. stdout: {completed.stdout!r}."
    )
    assert "CONTENT_MODEL_SENTINEL" not in completed.stdout, (
        f"Expected native model attributes to be ignored. stdout: {completed.stdout!r}."
    )


def test_pi_user_agent_display_false_duplicates_stay_hidden(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_custom_fixture(tmp_path)
    completed = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--color=never",
        "--no-metadata",
    )

    duplicated_task = (
        "turn on deletion protection and disable disk removal with machine."
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count(duplicated_task) == 1, (
        "Expected the normal custom record once and its display=false custom_message "
        f"duplicate to stay hidden. stdout: {completed.stdout!r}."
    )


def test_agents_render_pi_user_agent_failures_as_visible_bash_errors(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_fixture(tmp_path)

    agents = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--color=never",
        "--no-metadata",
    )

    task = (
        "`run 019fb81a-3222-7aec-930e-c3c91e44db09 -t:i:s --thinking > "
        "/tmp/transcription.md`, then read the file in full."
    )
    error = (
        "Codex error: No tool call found for function call output with call_id "
        "toolu_01KVZUheWzuEWjHvfy4xSRhN."
    )
    assert agents.returncode == 0, (
        "Expected `--agents` to parse erroneous Pi user agents. "
        f"stderr: {agents.stderr!r}."
    )
    assert (
        "<agent " in agents.stdout and 'custom_type="pi-user-agents"' in agents.stdout
    ), (
        "Expected an erroneous Pi user agent to remain an agent interaction. "
        f"stdout: {agents.stdout!r}."
    )
    assert task in agents.stdout, (
        "Expected the failed agent input to come from details.task. "
        f"stdout: {agents.stdout!r}."
    )
    assert error in agents.stdout, (
        "Expected the failed agent error to come from details.error. "
        f"stdout: {agents.stdout!r}."
    )
    assert '<tool-output name="Bash" is_error="true">' in agents.stdout, (
        "Expected `--agents` alone to show failures through the shared Bash error path. "
        f"stdout: {agents.stdout!r}."
    )


def test_erroneous_pi_user_agents_ignore_native_task_and_error_content(
    tmp_path: Path,
) -> None:
    def select(entry: dict[str, object]) -> bool:
        if entry.get("type") != "custom_message":
            return False
        if entry.get("customType") != "pi-user-agents":
            return False
        details = entry.get("details")
        return isinstance(details, dict) and details.get("ok") is False

    def mutate(entry: dict[str, object]) -> None:
        details = entry.get("details")
        content = entry.get("content")
        assert isinstance(details, dict), f"Expected error details. Got: {details!r}."
        assert isinstance(content, str), (
            f"Expected native error content. Got: {content!r}."
        )
        details["task"] = "DETAILS_ERROR_TASK_SENTINEL"
        details["error"] = "DETAILS_ERROR_SENTINEL"
        content = re.sub(
            r"<task>.*?</task>",
            "<task>CONTENT_ERROR_TASK_SENTINEL</task>",
            content,
            count=1,
            flags=re.DOTALL,
        )
        entry["content"] = re.sub(
            r"<error>.*?</error>",
            "<error>CONTENT_ERROR_SENTINEL</error>",
            content,
            count=1,
            flags=re.DOTALL,
        )

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    completed = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--color=never",
        "--no-metadata",
    )

    assert completed.returncode == 0, completed.stderr
    assert "DETAILS_ERROR_TASK_SENTINEL" in completed.stdout, (
        f"Expected error input from details.task. stdout: {completed.stdout!r}."
    )
    assert "DETAILS_ERROR_SENTINEL" in completed.stdout, (
        f"Expected error output from details.error. stdout: {completed.stdout!r}."
    )
    assert "CONTENT_ERROR_TASK_SENTINEL" not in completed.stdout, (
        f"Expected native error task content to be ignored. stdout: {completed.stdout!r}."
    )
    assert "CONTENT_ERROR_SENTINEL" not in completed.stdout, (
        f"Expected native error body content to be ignored. stdout: {completed.stdout!r}."
    )


@pytest.mark.parametrize(
    ("case_name", "ok_value", "remove_ok"),
    [
        pytest.param("true", True, False, id="true"),
        pytest.param("zero", 0, False, id="zero"),
        pytest.param("null", None, False, id="null"),
        pytest.param("missing", None, True, id="missing"),
    ],
)
def test_pi_user_agent_error_detection_requires_the_false_singleton(
    tmp_path: Path,
    case_name: str,
    ok_value: bool | int | None,
    remove_ok: bool,
) -> None:
    task = f"IDENTITY_TASK_{case_name}"
    response = f"IDENTITY_RESPONSE_{case_name}"
    error = f"IDENTITY_ERROR_{case_name}"

    def select(entry: dict[str, object]) -> bool:
        if entry.get("type") != "custom_message":
            return False
        if entry.get("customType") != "pi-user-agents":
            return False
        details = entry.get("details")
        return (
            entry.get("display") is True
            and isinstance(details, dict)
            and details.get("ok") is True
        )

    def mutate(entry: dict[str, object]) -> None:
        details = entry.get("details")
        content = entry.get("content")
        assert isinstance(details, dict), f"Expected success details. Got: {details!r}."
        assert isinstance(content, str), f"Expected success content. Got: {content!r}."
        if remove_ok:
            details.pop("ok", None)
        else:
            details["ok"] = ok_value
        details["task"] = task
        details["error"] = error
        entry["content"] = re.sub(
            r"<response>.*?</response>",
            f"<response>{response}</response>",
            content,
            count=1,
            flags=re.DOTALL,
        )

    home, session_path = _derive_pi_fixture(tmp_path, select, mutate)
    completed = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--format=json",
    )

    assert completed.returncode == 0, (
        f"Expected ok={case_name} to parse as a successful interaction. "
        f"stderr: {completed.stderr!r}."
    )
    messages = json.loads(completed.stdout)
    interaction = next(
        message
        for message in messages
        if any(
            isinstance(block, dict)
            and block.get("type") == "subagent-task"
            and block.get("content") == task
            for block in message.get("content", [])
        )
    )
    assert response in interaction.get("content", []), (
        f"Expected ok={case_name} to use its response body. Got: {interaction!r}."
    )
    assert not any(
        isinstance(block, dict)
        and block.get("type") == "tool-output"
        and block.get("is_error") is True
        for block in interaction.get("content", [])
    ), f"Expected only the False singleton to mark an error. Got: {interaction!r}."
    assert error not in completed.stdout, (
        f"Expected ok={case_name} not to expose details.error. "
        f"stdout: {completed.stdout!r}."
    )


def test_agents_render_subagent_records_once_and_hide_notifications(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_fixture(tmp_path)

    agents = _run_ch(
        home,
        str(session_path),
        "--agents",
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

    record_id = "2ceaec18-6ba7-4c9"
    description = "Verify GIL-10 live"
    result_heading = "# The live cloud confirms GIL-10"
    for mode, completed in (("--agents", agents), ("--all", show_all)):
        assert completed.returncode == 0, (
            f"Expected {mode} to parse Pi subagent records. stderr: {completed.stderr!r}."
        )
        assert f'agent_id="{record_id}"' in completed.stdout, (
            f"Expected {mode} to preserve the subagent record id. "
            f"stdout: {completed.stdout!r}."
        )
        assert 'subagent_type="general-purpose"' in completed.stdout, (
            f"Expected {mode} to preserve the subagent type. "
            f"stdout: {completed.stdout!r}."
        )
        assert 'status="completed"' in completed.stdout, (
            f"Expected {mode} to preserve the subagent status. "
            f"stdout: {completed.stdout!r}."
        )
        assert description in completed.stdout and result_heading in completed.stdout, (
            f"Expected {mode} to render the subagent input and result. "
            f"stdout: {completed.stdout!r}."
        )
        assert 'custom_type="subagent-notification"' not in completed.stdout, (
            f"Expected {mode} to hide the duplicate subagent notification. "
            f"stdout: {completed.stdout!r}."
        )
        assert "resultPreview" not in completed.stdout, (
            f"Expected {mode} not to render notification-only data. "
            f"stdout: {completed.stdout!r}."
        )

    assert agents.stdout.count(result_heading) == 1, (
        "Expected `--agents` to show the subagent result only through its record. "
        f"stdout: {agents.stdout!r}."
    )


def test_agents_emit_structured_pi_custom_messages_as_agent_data(
    tmp_path: Path,
) -> None:
    home, session_path = _copy_pi_fixture(tmp_path)

    completed = _run_ch(
        home,
        str(session_path),
        "--agents",
        "--format=json",
        "--no-metadata",
    )

    assert completed.returncode == 0, (
        f"Expected structured Pi agent output to succeed. stderr: {completed.stderr!r}."
    )
    messages = json.loads(completed.stdout)
    success_task = "where's the js/css/html of the visual map?"
    success = next(
        message
        for message in messages
        if any(
            block.get("type") == "subagent-task"
            and block.get("content") == success_task
            for block in message.get("content", [])
            if isinstance(block, dict)
        )
    )
    assert success.get("type") == "agent", (
        f"Expected a structured agent wrapper. Got: {success!r}."
    )
    assert success.get("custom_type") == "pi-user-agents", (
        f"Expected the native custom type as metadata. Got: {success!r}."
    )
    assert success.get("inherited_context") is True, (
        f"Expected inherited context to remain a JSON boolean. Got: {success!r}."
    )
    assert success.get("model") == "openai-codex/gpt-5.6-luna (gpt56l)", (
        f"Expected the details model in structured output. Got: {success!r}."
    )
    assert any(
        isinstance(block, str)
        and block.startswith("The visual map is one self-contained HTML file:")
        for block in success.get("content", [])
    ), f"Expected the extracted response as agent text. Got: {success!r}."

    failed = next(
        message
        for message in messages
        if any(
            isinstance(block, dict)
            and block.get("type") == "tool-output"
            and block.get("is_error") is True
            for block in message.get("content", [])
        )
    )
    error_block = next(
        block
        for block in failed["content"]
        if isinstance(block, dict) and block.get("type") == "tool-output"
    )
    assert error_block.get("name") == "Bash", (
        f"Expected structured errors to use shared Bash semantics. Got: {error_block!r}."
    )
    assert str(error_block.get("content", "")).startswith("Codex error:"), (
        f"Expected details.error as structured error content. Got: {error_block!r}."
    )

    record = next(
        message
        for message in messages
        if message.get("agent_id") == "2ceaec18-6ba7-4c9"
    )
    assert record.get("subagent_type") == "general-purpose", (
        f"Expected the structured subagent type. Got: {record!r}."
    )
    assert record.get("status") == "completed", (
        f"Expected the structured subagent status. Got: {record!r}."
    )
    assert not any(
        message.get("custom_type") == "subagent-notification" for message in messages
    ), f"Expected notification duplicates to stay absent. Got: {messages!r}."


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
    assert "<subagent-task>" in completed.stdout, (
        f"Expected raw output to retain agent inputs. stdout: {completed.stdout!r}."
    )
    assert "The visual map is one self-contained HTML file:" in completed.stdout, (
        f"Expected raw output to retain extracted agent responses. stdout: {completed.stdout!r}."
    )
    assert '<tool-output name="Bash" is_error="true">' in completed.stdout, (
        f"Expected raw output to retain agent failure semantics. stdout: {completed.stdout!r}."
    )
    assert "## Custom" in completed.stdout, (
        f"Expected `--all` raw output to identify generic custom records. stdout: {completed.stdout!r}."
    )
    assert "stale_queued_tool_results_dropped" in completed.stdout, (
        f"Expected `--all` raw output to retain generic custom data. stdout: {completed.stdout!r}."
    )


def test_colored_output_uses_agent_panels_and_shared_error_styling(
    tmp_path: Path,
) -> None:
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
    assert "Agent" in plain and "✻ subagent task" in plain, (
        f"Expected shared agent panels and input markers. stdout: {plain!r}."
    )
    assert "The visual map is one self-contained HTML file:" in plain, (
        f"Expected colored output to retain extracted responses. stdout: {plain!r}."
    )
    assert "⎿ Bash" in plain and "·  error" in plain, (
        f"Expected the shared Bash error marker for agent failures. stdout: {plain!r}."
    )
    assert "38;2;226;120;129" in completed.stdout, (
        "Expected the same red error style that regular Bash failures use. "
        f"stdout: {completed.stdout!r}."
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
    agent_needle = "The visual map is one self-contained HTML file"
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
        "Expected `--agents` search to find Pi user-agent responses. "
        f"stderr: {shown_agent.stderr!r}."
    )
    assert shown_agent.stdout.strip() == "019fb81a-3222-7aec-930e-c3c91e44db09", (
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
    assert shown_custom.stdout.strip() == "019fb81a-3222-7aec-930e-c3c91e44db09", (
        f"Expected the source fixture session id. stdout: {shown_custom.stdout!r}."
    )
