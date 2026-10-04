"""Tool-spec validation follows the grammar before session work starts."""

from __future__ import annotations

from itertools import permutations
from pathlib import Path
import os
import subprocess

import pytest

from chats.tool_filter import parse_tool_spec


def test_bare_limit_requires_a_short_assignment() -> None:
    with pytest.raises(ValueError, match="s=200"):
        parse_tool_spec("i:200")


@pytest.mark.parametrize("negate", [False, True])
def test_each_slot_can_be_filled_only_once_in_every_order(negate: bool) -> None:
    slots = {
        "name": ("Bash", "Read", "mcp__server__tool"),
        "direction": ("i", "input", "o", "output"),
        "error": ("e", "error"),
        "short": ("s", "short", "s=200", "short=p=200"),
    }
    for length in range(1, 5):
        for order in permutations(slots, length):
            specification = ("!" if negate else "") + ":".join(slots[slot][0] for slot in order)
            parsed = parse_tool_spec(specification)
            assert parsed.negate == negate, specification
            assert parsed.name == ("Bash" if "name" in order else None), specification
            assert parsed.direction == ("input" if "direction" in order else None), specification
            assert parsed.error_only == ("error" in order), specification
            assert parsed.short == ("short" in order), specification
            for filled_slot in order:
                for item in slots[filled_slot]:
                    invalid_specification = f"{specification}:{item}"
                    with pytest.raises(ValueError, match=f"{filled_slot}.*already"):
                        parse_tool_spec(invalid_specification)


@pytest.mark.parametrize(
    ("specification", "reason"),
    [
        ("", "Expected an item"),
        ("!", "Expected an item"),
        ("!!Read", "only once"),
        ("Read!", "only once"),
        ("Read:!o", "only once"),
        (":Read", "empty item"),
        ("Read:", "empty item"),
        ("Read::o", "empty item"),
        ("Read o", "whitespace"),
        ("i=200", "only s or short"),
    ],
)
def test_forbidden_grammar_transitions_report_the_spec_and_reason(
    specification: str,
    reason: str,
) -> None:
    with pytest.raises(ValueError, match=reason) as failure:
        parse_tool_spec(specification)
    assert repr(specification) in str(failure.value), str(failure.value)


@pytest.mark.parametrize("command", [(), ("search",)])
@pytest.mark.parametrize("carrier", ["-t", "-t:", "--tools", "--tools="])
@pytest.mark.parametrize("override", [(), ("--all",), ("--only-user",), ("--only-assistant",)])
def test_invalid_specs_fail_before_session_work_even_with_visibility_overrides(
    checkout_built_ch: Path,
    tmp_path: Path,
    command: tuple[str, ...],
    carrier: str,
    override: tuple[str, ...],
) -> None:
    specification = "i:200"
    tool_arguments = (
        (carrier, specification) if carrier in {"-t", "--tools"}
        else (f"{carrier}{specification}",)
    )
    result = subprocess.run(
        [str(checkout_built_ch), *command, str(tmp_path / "missing.jsonl"),
         *tool_arguments, *override, "--color=never"],
        env={**os.environ, "HOME": str(tmp_path), "COLUMNS": "240"},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert result.stdout == "", result.stdout
    assert "Invalid tool spec: 'i:200'" in result.stderr, result.stderr
    assert "Use s=200" in result.stderr, result.stderr


@pytest.mark.parametrize("command", [(), ("search",)])
@pytest.mark.parametrize(
    "specification",
    ["", "!", "!!Read", ":Read", "Read:", "Read::o", "Read:Bash",
     "i:output", "e:error", "s:short", "i=200"],
)
def test_cli_rejects_each_forbidden_transition(
    checkout_built_ch: Path,
    tmp_path: Path,
    command: tuple[str, ...],
    specification: str,
) -> None:
    result = subprocess.run(
        [str(checkout_built_ch), *command, str(tmp_path / "missing.jsonl"),
         f"--tools={specification}", "--color=never"],
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert result.stdout == "", result.stdout
    assert "Invalid tool spec:" in result.stderr, result.stderr
