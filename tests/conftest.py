"""Test-wide fixtures.

`chats.console` caches its `Console` objects in module globals and never
resets them. **Three of them today** — the hint console went with the Python
search authority. A Rich `Console` freezes its world at construction rather than at
use: width from `COLUMNS`, the colour system, and `no_color` are all resolved
once, when the object is built. Nothing cleared those globals between tests, so
the first test in a process to touch a console fixed width, colour and colour
system for every test after it — and a later `monkeypatch.setenv("COLUMNS", …)`
could not move a console that had already read the environment.

That made every width, colour and tty assertion in the in-process test files
order-dependent, which under `-n 8 --dist=loadfile` means dependent on which
worker happened to receive which file. Subprocess-based suites were never
affected; they build a console per child from the environment they are handed.

Found by `reviewer-profiler`.
"""

from __future__ import annotations

import pytest

import chats.console


_CACHED_CONSOLE_ATTRIBUTES = (
    "_console",
    "_error_console",
    "_warning_console",
)


@pytest.fixture(autouse=True)
def reset_cached_consoles() -> None:
    """Give every test a console built from its own environment."""
    for attribute in _CACHED_CONSOLE_ATTRIBUTES:
        setattr(chats.console, attribute, None)
    yield
    for attribute in _CACHED_CONSOLE_ATTRIBUTES:
        setattr(chats.console, attribute, None)


# ── Shared with the frozen-successor module ─────────────────────────────────
#
# Both live here rather than in `test_search_command_contract.py` because two
# modules need them, and two module-local definitions would build the launcher
# twice, materialize both corpora twice, and leave two private launcher
# directories where the normalization only knows about one.

import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import test_search_command_contract as _contract  # noqa: E402

PROJECT_ROOT = _contract.PROJECT_ROOT
CORPORA = _contract.CORPORA
CONTRACT_CARGO_TARGET = _contract.CONTRACT_CARGO_TARGET
CONTRACT_BUILT_CH = _contract.CONTRACT_BUILT_CH
_reject_foreign_launcher = _contract._reject_foreign_launcher
_place_legacy_sibling = _contract._place_legacy_sibling


@pytest.fixture(scope="session")
def checkout_built_ch(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the public launcher, then run every case from a private copy.

    `target/release/` is shared. Another suite's session fixture unlinks and
    rebuilds `ch` there, and several place their own `ch-legacy` sibling beside
    it, so a run that reads that path directly is racing every other process in
    the checkout. Copying once, up front, makes the artifact under test immutable
    for the length of the run: a concurrent rebuild can no longer change what
    this suite measured half way through.
    """
    cargo = shutil.which("cargo")
    assert cargo is not None, "Expected `cargo` on PATH to build the checkout-owned launcher."
    completed = subprocess.run(
        # Mirror [[tool.setuptools-rust.bins]] so the validated artifact matches
        # what the packaging pipeline ships for public `ch`.
        [cargo, "build", "--release", "--bin", "ch", "--no-default-features"],
        cwd=PROJECT_ROOT,
        # Its own target directory, so this suite neither reads nor writes the
        # shared `target/release`. Another suite unlinks and rebuilds `ch` there,
        # and several place their own `ch-legacy` beside it; building into that
        # directory would put this suite back in the contention it exists to be
        # free of. Cached between runs, so only the first build is slow.
        env={**os.environ, "CARGO_TARGET_DIR": str(CONTRACT_CARGO_TARGET)},
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, (
        "Expected `cargo build --release --bin ch --no-default-features` to produce "
        f"the contract-suite launcher. stderr tail: {completed.stderr[-1000:]!r}."
    )
    assert CONTRACT_BUILT_CH.is_file(), (
        f"Expected the release build to produce {CONTRACT_BUILT_CH}."
    )
    _reject_foreign_launcher(CONTRACT_BUILT_CH)

    private = tmp_path_factory.mktemp("contract-launcher") / "ch"
    # Set on the contract module, not here: `_normalize` lives there and reads
    # its own global. A `global` in this file would leave that one None and the
    # per-run launcher path would reach a byte comparison unnormalized.
    _contract._PRIVATE_LAUNCHER_DIR = private.parent
    shutil.copy2(CONTRACT_BUILT_CH, private)
    # Verify the copy rather than predict the space. A full volume truncates the
    # copy silently, and a truncated launcher produces failures that look exactly
    # like regressions — in the suite whose red is supposed to mean something.
    # Checking the result catches a short write whatever caused it; checking free
    # space beforehand only catches the cause we thought of.
    assert private.stat().st_size == CONTRACT_BUILT_CH.stat().st_size, (
        f"The private launcher copy is {private.stat().st_size} bytes against "
        f"{CONTRACT_BUILT_CH.stat().st_size} at source. The copy was truncated — "
        "check free space. Every result in this run would otherwise read as a "
        "regression."
    )
    _reject_foreign_launcher(private)
    _place_legacy_sibling(private.parent)
    return private


@pytest.fixture(scope="session")
def corpus_homes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """One materialized session pool per corpus, timestamps applied."""
    homes: dict[str, Path] = {}
    for corpus in CORPORA:
        home = tmp_path_factory.mktemp(f"search-{corpus.name}") / "home"
        shutil.copytree(corpus.root / "home", home)
        for relative_path, mtime in corpus.mtimes.items():
            os.utime(home / relative_path, (mtime, mtime))
        homes[corpus.name] = home
    return homes


