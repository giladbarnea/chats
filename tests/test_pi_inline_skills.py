"""Pi inline-skill splitting: leading <skill> blocks become Skill tool messages."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CH_EXECUTABLE = Path(sys.executable).with_name("ch")

SKILL_BODY = "SKILL_BODY_SENTINEL follow these skill instructions"
USER_TEXT = "USER_TEXT_SENTINEL hello world"


def _skill_block(
    body: str = SKILL_BODY,
    name: str = "my-skill",
    location: str = "/Users/u/.pi/agent/skills/my-skill/SKILL.md",
) -> str:
    return f'<skill name="{name}" location="{location}">\n{body}\n</skill>'


def _write_pi_session(tmp_path: Path, user_text: str) -> tuple[Path, Path]:
    home = tmp_path / "home"
    session_path = home / ".pi" / "agent" / "sessions" / "project" / "session.jsonl"
    session_path.parent.mkdir(parents=True)
    entries = [
        {
            "type": "session",
            "version": 3,
            "id": "01900000-0000-7000-8000-000000000001",
            "timestamp": "2026-08-01T10:00:00.000Z",
            "cwd": "/tmp/project",
        },
        {
            "type": "message",
            "id": "aaaa0001",
            "parentId": None,
            "timestamp": "2026-08-01T10:00:01.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": user_text}],
                "timestamp": 1785500000000,
            },
        },
    ]
    session_path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return home, session_path


def _run_ch(
    home: Path,
    *arguments: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["TZ"] = "Asia/Jerusalem"
    return subprocess.run(
        [str(CH_EXECUTABLE), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_leading_skill_block_stays_out_of_default_user_text(tmp_path: Path) -> None:
    home, session_path = _write_pi_session(
        tmp_path, f"{_skill_block()}\n\n{USER_TEXT}"
    )

    completed = _run_ch(home, str(session_path), "--color=never", "--no-metadata")

    assert completed.returncode == 0, completed.stderr
    assert USER_TEXT in completed.stdout, (
        "Expected the typed remainder to stay a visible user message. "
        f"stdout: {completed.stdout!r}."
    )
    assert SKILL_BODY not in completed.stdout, (
        "Expected the expanded skill body to leave the default user text. "
        f"stdout: {completed.stdout!r}."
    )


def test_tools_flag_shows_the_skill_as_a_skill_tool_pair(tmp_path: Path) -> None:
    home, session_path = _write_pi_session(
        tmp_path, f"{_skill_block()}\n\n{USER_TEXT}"
    )

    completed = _run_ch(
        home, str(session_path), "-t", "--color=never", "--no-metadata"
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        '<tool-input name="Skill" ' in completed.stdout
        and 'skill="my-skill"' in completed.stdout
        and 'location="/Users/u/.pi/agent/skills/my-skill/SKILL.md"' in completed.stdout
    ), (
        "Expected the inline skill to render as a Skill tool call with its "
        f"name and location. stdout: {completed.stdout!r}."
    )
    assert (
        '<tool-output name="Skill" ' in completed.stdout
        and SKILL_BODY in completed.stdout
    ), (
        "Expected the skill body to render as the Skill tool output. "
        f"stdout: {completed.stdout!r}."
    )
    assert USER_TEXT in completed.stdout, (
        f"Expected the typed remainder to stay visible. stdout: {completed.stdout!r}."
    )


def test_skill_only_message_leaves_no_user_message(tmp_path: Path) -> None:
    home, session_path = _write_pi_session(tmp_path, _skill_block())

    default = _run_ch(home, str(session_path), "--color=never", "--no-metadata")
    tools = _run_ch(home, str(session_path), "-t", "--color=never", "--no-metadata")

    assert default.returncode == 0, default.stderr
    assert "<user-message" not in default.stdout, (
        "Expected no user message when the user typed only a skill command. "
        f"stdout: {default.stdout!r}."
    )
    assert tools.returncode == 0, tools.stderr
    assert (
        '<tool-input name="Skill" ' in tools.stdout and SKILL_BODY in tools.stdout
    ), (
        f"Expected `-t` to still show the Skill pair. stdout: {tools.stdout!r}."
    )
    assert tools.stdout.count("<user-message") == 1, (
        "Expected exactly one message: the Skill pair without an empty "
        f"remainder message. stdout: {tools.stdout!r}."
    )


def test_stacked_skills_split_into_separate_skill_messages(tmp_path: Path) -> None:
    stacked = "\n\n".join(
        [
            _skill_block(body="BODY_ALPHA", name="skill-alpha"),
            _skill_block(body="BODY_BRAVO", name="skill-bravo"),
            USER_TEXT,
        ]
    )
    home, session_path = _write_pi_session(tmp_path, stacked)

    completed = _run_ch(
        home, str(session_path), "-t", "--format=json", "--no-metadata"
    )

    assert completed.returncode == 0, completed.stderr
    messages = json.loads(completed.stdout)
    skill_inputs = [
        block
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict)
        and block.get("type") == "tool-input"
        and block.get("name") == "Skill"
    ]
    assert [block.get("skill") for block in skill_inputs] == [
        "skill-alpha",
        "skill-bravo",
    ], f"Expected one Skill call per stacked block, in order. Got: {messages!r}."
    assert len(messages) == 3, (
        "Expected two skill messages plus the typed user message. "
        f"Got: {messages!r}."
    )
    assert messages[2].get("content") == [USER_TEXT], (
        f"Expected the remainder as the final user message. Got: {messages!r}."
    )


def test_skill_tag_not_at_start_keeps_the_message_untouched(tmp_path: Path) -> None:
    text = f"look at this: {_skill_block()}"
    home, session_path = _write_pi_session(tmp_path, text)

    completed = _run_ch(home, str(session_path), "-t", "--color=never", "--no-metadata")

    assert completed.returncode == 0, completed.stderr
    assert text in completed.stdout, (
        "Expected a message whose skill tag is not the first non-whitespace "
        f"text to stay one verbatim user message. stdout: {completed.stdout!r}."
    )
    assert '<tool-input name="Skill"' not in completed.stdout, (
        f"Expected no Skill tool for a mid-message tag. stdout: {completed.stdout!r}."
    )


def test_unclosed_leading_skill_tag_keeps_the_message_untouched(
    tmp_path: Path,
) -> None:
    text = '<skill name="my-skill" location="/x/SKILL.md">\nfoo bar'
    home, session_path = _write_pi_session(tmp_path, text)

    completed = _run_ch(home, str(session_path), "-t", "--color=never", "--no-metadata")

    assert completed.returncode == 0, completed.stderr
    assert "foo bar" in completed.stdout and "my-skill" in completed.stdout, (
        "Expected an unclosed leading skill tag to stay one verbatim user "
        f"message. stdout: {completed.stdout!r}."
    )
    assert '<tool-input name="Skill"' not in completed.stdout, (
        f"Expected no Skill tool for an unclosed tag. stdout: {completed.stdout!r}."
    )


def test_literal_skill_tags_inside_a_skill_body_stay_body_content(
    tmp_path: Path,
) -> None:
    nested_body = (
        "outer instructions\n"
        '<skill name="red-herring">\nignore me, i am content\n</skill>\n'
        "more outer instructions"
    )
    text = f"{_skill_block(body=nested_body)}\n\n{USER_TEXT}"
    home, session_path = _write_pi_session(tmp_path, text)

    completed = _run_ch(home, str(session_path), "-t", "--format=json", "--no-metadata")

    assert completed.returncode == 0, completed.stderr
    messages = json.loads(completed.stdout)
    skill_outputs = [
        block
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("type") == "tool-output"
    ]
    assert len(skill_outputs) == 1, (
        f"Expected the nested tags to yield exactly one skill. Got: {messages!r}."
    )
    assert skill_outputs[0].get("content") == nested_body, (
        "Expected the balanced inner skill tags to stay inside the outer "
        f"body. Got: {messages!r}."
    )
    assert messages[-1].get("content") == [USER_TEXT], (
        f"Expected the remainder after the outer close. Got: {messages!r}."
    )


def test_pasted_skill_tags_after_the_typed_text_stay_user_text(
    tmp_path: Path,
) -> None:
    pasted_tail = (
        f"{USER_TEXT} here is a pasted transcript:\n"
        '<skill name="pasted-one">\npasted body\n</skill>\n'
        '<skill name="pasted-unclosed">\nnever closes'
    )
    text = f"{_skill_block()}\n\n{pasted_tail}"
    home, session_path = _write_pi_session(tmp_path, text)

    completed = _run_ch(home, str(session_path), "-t", "--format=json", "--no-metadata")

    assert completed.returncode == 0, completed.stderr
    messages = json.loads(completed.stdout)
    skill_inputs = [
        block
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict)
        and block.get("type") == "tool-input"
        and block.get("name") == "Skill"
    ]
    assert [block.get("skill") for block in skill_inputs] == ["my-skill"], (
        "Expected only the leading block as a skill, never the pasted tail. "
        f"Got: {messages!r}."
    )
    assert messages[-1].get("content") == [pasted_tail], (
        "Expected the pasted transcript, unbalanced tags included, to stay "
        f"verbatim user text. Got: {messages!r}."
    )


def test_skill_pair_obeys_tool_name_and_direction_filters(tmp_path: Path) -> None:
    home, session_path = _write_pi_session(
        tmp_path, f"{_skill_block()}\n\n{USER_TEXT}"
    )
    shared = ("--color=never", "--no-metadata")

    by_name = _run_ch(home, str(session_path), "-t", "Skill", *shared)
    output_only = _run_ch(home, str(session_path), "-t", "Skill:o", *shared)
    excluded = _run_ch(home, str(session_path), "-t", "!Skill", *shared)

    assert by_name.returncode == 0, by_name.stderr
    assert (
        '<tool-input name="Skill" ' in by_name.stdout
        and SKILL_BODY in by_name.stdout
    ), f"Expected `-t Skill` to show the pair. stdout: {by_name.stdout!r}."

    assert output_only.returncode == 0, output_only.stderr
    assert (
        '<tool-input name="Skill"' not in output_only.stdout
        and SKILL_BODY in output_only.stdout
    ), (
        "Expected `-t Skill:o` to show only the skill body. "
        f"stdout: {output_only.stdout!r}."
    )

    assert excluded.returncode == 0, excluded.stderr
    assert (
        "Skill" not in excluded.stdout
        and SKILL_BODY not in excluded.stdout
        and USER_TEXT in excluded.stdout
    ), (
        "Expected `-t !Skill` to hide the pair and keep the remainder. "
        f"stdout: {excluded.stdout!r}."
    )
