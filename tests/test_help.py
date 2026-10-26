import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("command", [[], ["search"]], ids=["session", "search"])
@pytest.mark.parametrize("columns", [60, 80, 120])
def test_help_fits_the_terminal(
    checkout_built_ch: Path, command: list[str], columns: int
) -> None:
    completed = subprocess.run(
        [str(checkout_built_ch), *command, "--help"],
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": str(columns), "NO_COLOR": "1"},
        check=True,
    )
    overflowing = [line for line in completed.stdout.splitlines() if len(line) > columns]
    assert not overflowing, f"Help exceeds the {columns}-column terminal: {overflowing!r}"
    assert completed.stderr == "", completed.stderr


@pytest.mark.parametrize("command", [[], ["search"]], ids=["session", "search"])
def test_help_describes_shared_payload_budgets(checkout_built_ch: Path, command: list[str]) -> None:
    completed = subprocess.run(
        [str(checkout_built_ch), *command, "--help"], capture_output=True, text=True,
        env={**os.environ, "COLUMNS": "120", "NO_COLOR": "1"}, check=True,
    )
    help_text = " ".join(completed.stdout.split())
    assert "one shared payload budget per message" in help_text, help_text
    assert "Numbers, booleans, null, and omission markers count" in help_text, help_text
    assert "Different policies keep separate budgets" in help_text, help_text
    assert "No message is exempt" in help_text, help_text
    assert "each get their own limit" not in help_text, help_text
    assert "Limit each Read output text value" not in help_text, help_text
