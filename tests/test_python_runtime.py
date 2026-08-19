from __future__ import annotations

import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
PYTHON_VERSION = "3.14"
REQUIRES_PYTHON = "==3.14.*"


def test_project_targets_only_python_314() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    cargo = tomllib.loads((PROJECT_ROOT / "Cargo.toml").read_text())
    uv_lock = tomllib.loads((PROJECT_ROOT / "uv.lock").read_text())

    assert sys.version_info[:2] == (3, 14), (
        "Expected the project test interpreter to use Python 3.14. "
        f"Got: {sys.version_info[:2]!r}"
    )
    assert (PROJECT_ROOT / ".python-version").read_text().strip() == PYTHON_VERSION, (
        "Expected the local interpreter selector to require Python 3.14."
    )
    assert pyproject["project"]["requires-python"] == REQUIRES_PYTHON, (
        "Expected package metadata to accept only the Python 3.14 minor series."
    )
    assert uv_lock["requires-python"] == REQUIRES_PYTHON, (
        "Expected the lock to match the package Python requirement."
    )
    assert cargo["features"]["extension-module"] == [
        "pyo3/abi3-py314",
        "pyo3/extension-module",
    ], "Expected the native extension stable ABI floor to be Python 3.14."
