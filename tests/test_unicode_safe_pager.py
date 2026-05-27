#!/usr/bin/env python3
"""Tests for the unicode-safe Rich pager.

The pager must invoke `less` such that wide / ambiguous-width unicode (⏺, ⎿, box
drawing) survives even when the surrounding shell has a hostile
`LESS=--RAW-CONTROL-CHARS` configured. The pager achieves this by passing
`-r` (--raw-control-chars) on the command line, which overrides any conflicting
raw-mode toggle inherited via the LESS env.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from conversations.console import UnicodeSafePager


HOSTILE_LESS_ENV = "--RAW-CONTROL-CHARS --use-color"
UNICODE_PAYLOAD = (
    "plain: ⏺ ⎿ → ╭─╮\n"
    "\x1b[31mred: ⏺ ⎿ → ╭─╮\x1b[0m\n"
    "wide: 한글 中文 日本語\n"
)


def _install_fake_less(bin_dir: Path, capture_path: Path) -> Path:
    """Install a fake `less` shim on PATH that records argv, env, and stdin."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    less_path = bin_dir / "less"
    less_path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "record = {\n"
        "    'argv': sys.argv[1:],\n"
        "    'env_LESS': os.environ.get('LESS', ''),\n"
        "    'stdin': sys.stdin.buffer.read().decode('utf-8'),\n"
        "}\n"
        f"open({str(capture_path)!r}, 'w', encoding='utf-8').write(json.dumps(record))\n",
        encoding="utf-8",
    )
    less_path.chmod(less_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return less_path


@pytest.fixture
def fake_less(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Place a recording fake `less` first on PATH and return the capture file."""
    bin_dir = tmp_path / "bin"
    capture_path = tmp_path / "capture.json"
    _install_fake_less(bin_dir, capture_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return capture_path


def _read_capture(capture_path: Path) -> dict:
    assert capture_path.exists(), (
        f"Fake less did not produce a capture file at {capture_path}. "
        "The pager likely failed to spawn the shim."
    )
    return json.loads(capture_path.read_text(encoding="utf-8"))


def test_pager_invokes_less_with_lowercase_raw_flag_under_hostile_LESS_env(
    fake_less: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with `LESS=--RAW-CONTROL-CHARS …` inherited, our pager must put
    `less` in lowercase `-r` mode via a command-line argument."""
    monkeypatch.setenv("LESS", HOSTILE_LESS_ENV)

    UnicodeSafePager().show(UNICODE_PAYLOAD)

    capture = _read_capture(fake_less)

    assert capture.get("env_LESS") == HOSTILE_LESS_ENV, (
        "Pager must not mutate the inherited LESS env. "
        f"Expected {HOSTILE_LESS_ENV!r}, got {capture.get('env_LESS')!r}."
    )

    argv = capture.get("argv", [])
    raw_lowercase_flags = {"-r", "--raw-control-chars"}
    has_lowercase_raw = any(arg in raw_lowercase_flags for arg in argv)
    assert has_lowercase_raw, (
        "Pager must invoke `less` with a lowercase raw flag (-r or "
        f"--raw-control-chars) so unicode survives. Got argv={argv!r}."
    )

    raw_uppercase_flags = {"-R", "--RAW-CONTROL-CHARS"}
    has_uppercase_raw = any(arg in raw_uppercase_flags for arg in argv)
    assert not has_uppercase_raw, (
        "Pager must not pass an uppercase raw flag on the CLI; that would "
        f"override our lowercase fix. Got argv={argv!r}."
    )


def test_pager_delivers_content_to_less_byte_faithfully(
    fake_less: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pager must feed `less` exactly the bytes it was given, so unicode
    glyphs reach the renderer intact."""
    monkeypatch.setenv("LESS", HOSTILE_LESS_ENV)

    UnicodeSafePager().show(UNICODE_PAYLOAD)

    capture = _read_capture(fake_less)
    received = capture.get("stdin", "")
    assert received == UNICODE_PAYLOAD, (
        "Content delivered to less must match input exactly. "
        f"Expected {UNICODE_PAYLOAD!r}, got {received!r}."
    )
