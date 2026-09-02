"""The six places `ch search` deliberately differs from `ch-legacy`, asserted exactly.

**An expected red is indistinguishable from a regression.** This desk spent two days
removing the last row that was allowed to fail, so these six are not left red: each is an
**asserted exact difference**, the way `KNOWN_UNBUILT_BODIES` works. The set is exact,
the shape of each difference is pinned, and **anything else fails** — a geometry change, a
byte outside the named blocks, a seventh case joining, or a case quietly agreeing.

**Two classes, both ruled.**

**Four fence rows carry a language the seven-family list does not cover.** L247 closed
that list at seven on the captain's approval; `render-fence-web` carries `css`, `html`
and `javascript`, and `render-fence-data` carries `diff`, `json` and `markdown`. The
promoted halves render plain-identically — **`render-fence-shell` and `render-fence-python`
are byte-identical at both widths, which is what proves the divergence is the language
list and not the renderer.** Promoting four languages to turn four fixtures green would
reopen a settled decision to satisfy a fixture.

**Two warning rows want CPython's `warnings` decoration.** The warning text, the stream
and the ordering are all reproduced; what is absent is the source path, the line number
and the echoed line of Python. **Reproducing them means emitting a path to
`search_query.py:96` and echoing a line the cutover deletes** — the fabricated-traceback
pattern this project already fixed once, when a prior team faked a broken-pipe traceback
and baked build paths into the binary. Ruled against reproduction explicitly.

**`rebless_oracle.py` must not be reached for.** It replays through the built launcher,
which is now Rust, so a re-bless would stamp the native answer as the expectation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_search_command_contract import CHECKOUT_LEGACY, CORPORA

SGR = re.compile(rb"\x1b\[[0-9;]*m")
#: Monokai's fence background. Every style that only legacy emits carries it, which is
#: what places the whole difference inside fenced code blocks.
FENCE_BACKGROUND = b"48;2;39;40;34"

# **Imported, not restated.** `tests/deliberate_divergences.py` is the single authority;
# the contract suite reads the same names to know what it must not assert parity on.
from deliberate_divergences import (  # noqa: E402
    DELIBERATE,
    FENCE_CONTROLS,
    FENCE_DIVERGENCES,
    WARNING_DIVERGENCES,
    WARNING_PREFIX,
    WARNING_SOURCE_ECHO,
)


def _normalize_source_path(content: bytes) -> bytes:
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", content)


@pytest.fixture(scope="module")
def corpora(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[Path, list[dict]]]:
    out: dict[str, tuple[Path, list[dict]]] = {}
    for corpus in CORPORA:
        home = tmp_path_factory.mktemp(f"divergence-{corpus.name}") / "home"
        shutil.copytree(corpus.root / "home", home)
        for relative_path, mtime in corpus.mtimes.items():
            path = home / relative_path
            if path.exists():
                os.utime(path, (mtime, mtime))
        out[corpus.name] = (home, corpus.manifest)
    return out


def _run(executable: Path, case: dict, home: Path) -> subprocess.CompletedProcess[bytes]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"NO_COLOR", "FORCE_COLOR", "CLICOLOR", "CLICOLOR_FORCE"}
    }
    environment["HOME"] = str(home)
    environment["COLUMNS"] = str(case["columns"])
    environment["TERM"] = "xterm-256color"
    return subprocess.run(
        [str(executable), "search", *case["arguments"]],
        env=environment,
        capture_output=True,
        check=False,
    )


def _case(corpora: dict, identifier: str) -> tuple[Path, dict]:
    for home, manifest in corpora.values():
        for case in manifest:
            if case["id"] == identifier:
                return home, case
    raise AssertionError(f"{identifier} is not in either manifest any more.")


@pytest.mark.parametrize("identifier", FENCE_DIVERGENCES)
def test_a_fence_divergence_is_only_the_missing_syntax_colours(
    checkout_built_ch: Path, corpora: dict, identifier: str
) -> None:
    home, case = _case(corpora, identifier)
    native = _run(checkout_built_ch, case, home)
    legacy = _run(CHECKOUT_LEGACY, case, home)

    assert (native.returncode, native.stderr) == (legacy.returncode, legacy.stderr), (
        f"{identifier} differs on stderr or exit status. The accepted divergence is "
        "colour inside a fenced block on stdout and nothing else."
    )
    assert native.stdout != legacy.stdout, (
        f"{identifier} now matches `ch-legacy` exactly, so its entry here is allowing "
        "nothing. **An inert allowance is worse than none** — it reads as a known "
        "divergence while hiding whatever appears there next. Drop the name."
    )
    assert SGR.sub(b"", native.stdout) == SGR.sub(b"", legacy.stdout), (
        f"{identifier} differs in its **text**, not only its colour. The ruling covers "
        "an unported language rendering plain with complete geometry; a text or layout "
        "difference is a defect."
    )
    native_styles = set(SGR.findall(native.stdout))
    legacy_styles = set(SGR.findall(legacy.stdout))
    assert native_styles <= legacy_styles, (
        f"{identifier} emits styling `ch-legacy` does not: "
        f"{sorted(native_styles - legacy_styles)}. Rendering an unported language plain "
        "may only ever *omit* colour."
    )
    only_legacy = sorted(legacy_styles - native_styles)
    assert only_legacy, f"{identifier} is missing no styles, so nothing is diverging."
    assert all(FENCE_BACKGROUND in style for style in only_legacy), (
        f"{identifier} is missing styling from **outside** a fenced code block: "
        f"{[s for s in only_legacy if FENCE_BACKGROUND not in s]}. Every accepted "
        "difference carries Monokai's fence background, which is what confines this "
        "divergence to the code blocks the language list does not cover."
    )


@pytest.mark.parametrize("identifier", FENCE_CONTROLS)
def test_a_promoted_fence_is_byte_identical(
    checkout_built_ch: Path, corpora: dict, identifier: str
) -> None:
    """The control that makes the four above mean what they say.

    Without it, "the renderer drops colour on some fences" and "the language list does
    not cover four tags" are the same observation.
    """
    home, case = _case(corpora, identifier)
    native = _run(checkout_built_ch, case, home)
    legacy = _run(CHECKOUT_LEGACY, case, home)
    assert (native.stdout, native.stderr, native.returncode) == (
        legacy.stdout,
        legacy.stderr,
        legacy.returncode,
    ), (
        f"{identifier} carries only promoted languages and must reproduce `ch-legacy` "
        "byte for byte. If this fails, the fence divergence beside it is the renderer "
        "rather than the language list, and the four allowances are hiding a defect."
    )


@pytest.mark.parametrize("identifier", WARNING_DIVERGENCES)
def test_a_warning_divergence_is_only_the_missing_decoration(
    checkout_built_ch: Path, corpora: dict, identifier: str
) -> None:
    home, case = _case(corpora, identifier)
    native = _run(checkout_built_ch, case, home)
    legacy = _run(CHECKOUT_LEGACY, case, home)

    assert (native.stdout, native.returncode) == (legacy.stdout, legacy.returncode), (
        f"{identifier} differs on stdout or exit status. The accepted divergence is "
        "CPython's warning decoration on stderr and nothing else."
    )
    assert native.stderr != legacy.stderr, (
        f"{identifier} now matches `ch-legacy` exactly. Drop the name rather than leave "
        "an allowance that allows nothing."
    )
    # **Spelled out, so a change to the warning text itself still fails.** The only
    # accepted difference is the prefix `warnings` adds and the line of source it echoes.
    assert _normalize_source_path(legacy.stderr) == (
        WARNING_PREFIX + native.stderr + WARNING_SOURCE_ECHO
    ), (
        f"{identifier}'s difference is no longer exactly CPython's warning decoration.\n"
        f"  legacy: {_normalize_source_path(legacy.stderr)!r}\n"
        f"  native: {native.stderr!r}\n"
        "Reproducing the decoration is ruled against — it means emitting a path to "
        "`search_query.py:96` and echoing a line of Python the cutover deletes, which is "
        "the fabricated-traceback pattern this project already removed once. But the "
        "warning **text**, its stream and its ordering are not covered by that ruling, "
        "and this says one of them has moved."
    )


def test_the_set_of_deliberate_divergences_is_exact(
    checkout_built_ch: Path, corpora: dict
) -> None:
    """Every other recorded case reproduces `ch-legacy` byte for byte.

    **This is the assertion that keeps the six honest.** Without it they are six names
    beside a suite that could be diverging anywhere else.
    """
    differing: set[str] = set()
    compared = 0
    for home, manifest in corpora.values():
        for case in manifest:
            native = _run(checkout_built_ch, case, home)
            legacy = _run(CHECKOUT_LEGACY, case, home)
            compared += 1
            if (native.stdout, native.stderr, native.returncode) != (
                legacy.stdout,
                legacy.stderr,
                legacy.returncode,
            ):
                differing.add(case["id"])
    assert compared >= 250, (
        f"Only {compared} recorded cases were compared. A shrunken corpus passes "
        "vacuously."
    )
    assert differing == set(DELIBERATE), (
        f"The deliberate-divergence set moved.\n"
        f"  joined: {sorted(differing - DELIBERATE)}\n"
        f"  left:   {sorted(DELIBERATE - differing)}\n"
        "**A case that joined is a regression, not a gap** — nothing else is allowed to "
        "differ from `ch-legacy`. A case that left has stopped diverging and its name "
        "should go rather than stay pointing at nothing."
    )
