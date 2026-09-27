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
