"""`COLUMNS` swept against `ch search`'s help and error shapes.

**This closes a hole rather than answering a question.** `reviewer-profiler` checked
all eleven existing gates: `COLUMNS` appears only as a fixed `80` in the piped base and
the freeze, never as a swept input, and `pty_harness` actively scrubs it from inherited
environments — the width gate varies the *pty*, not the variable. The one help shape
anywhere is timed rather than byte-compared, so it could not see a rendering difference
if one existed.

**What the hole hides is a real divergence, and it is `preserve-because-wrong` item 9.**
The product resolves terminal width two different ways in one process. argparse reaches
it through `shutil.get_terminal_size`, which is `int(COLUMNS)` inside a `try`, so it
accepts a leading `+`, surrounding whitespace and fullwidth digits. Rich reaches it
through `str.isdigit()` and then `int()`, which accepts none of them. At `COLUMNS=+96`
the help wraps at 96 while Rich-rendered output wraps at 80 — same binary, same
invocation.

**Two resolvers is the correct port and the single most tempting deletion in the
grammar.** `main.rs` keeps `argparse_columns()` for help and errors and
`terminal_width()` for `run`; `terminal.rs` carries a unit test asserting they disagree.
This is the other half: that the *composition* still reproduces `ch-legacy` byte for
byte at every value, including ones the two resolvers read differently.

**The sweep does not stop at `+96`.** A gate built from one known-divergent value proves
that value, not the parameter.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from test_search_command_contract import CHECKOUT_LEGACY

# Absent, empty, ordinary, and then every shape the two parsers read differently: a
# leading sign, surrounding whitespace, a zero, a negative, fullwidth and Arabic-Indic
# digits, a non-number, and a value carrying its own newline.
COLUMNS_VALUES = [
    None,
    "",
    "40",
    "80",
    "96",
    "0",
    "+96",
    " 96",
    "96 ",
    "  120  ",
    "-5",
    "0096",
    "９６",
    "١٢٠",
    "1e3",
    "abc",
    "96\n",
    "9999",
]

# The two shapes that take `argparse_columns()`, plus one that takes
# `terminal_width()` — so a unification in either direction is caught rather than only
# a unification onto Rich.
SHAPES = [
    pytest.param(["search", "--help"], id="help"),
    pytest.param(["search", "--nope"], id="unknown-option"),
    pytest.param(["search", "-ma", "notadate", "x"], id="invalid-date"),
    pytest.param(["search", "zzzz-no-such-term"], id="no-results"),
]


def _run(executable: Path, arguments: list[str], columns: str | None, home: Path):
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"COLUMNS", "NO_COLOR", "FORCE_COLOR", "CLICOLOR", "CLICOLOR_FORCE"}
    }
    environment["HOME"] = str(home)
    # `TERM=dumb` keeps the comparison about width. Colour has its own gates, and a
    # coloured no-results line would drag this one into them.
    environment["TERM"] = "dumb"
    if columns is not None:
        environment["COLUMNS"] = columns
    return subprocess.run(
        [str(executable), *arguments],
        env=environment,
        capture_output=True,
        check=False,
    )


@pytest.fixture(scope="module")
def sweep_home(corpus_homes: dict[str, Path]) -> Path:
    """The contract corpus, so the `run` shape has a pool to answer about.

    An empty pool makes the no-results shape print nothing on both sides, which is a
    comparison that cannot fail.
    """
    return corpus_homes["contract"]


@pytest.mark.parametrize("columns", COLUMNS_VALUES, ids=lambda value: repr(value))
@pytest.mark.parametrize("arguments", SHAPES)
def test_columns_sweep_reproduces_legacy(
    checkout_built_ch: Path,
    sweep_home: Path,
    arguments: list[str],
    columns: str | None,
) -> None:
    native = _run(checkout_built_ch, arguments, columns, sweep_home)
    legacy = _run(CHECKOUT_LEGACY, arguments, columns, sweep_home)

    assert native.returncode == legacy.returncode, (
        f"`ch {' '.join(arguments)}` exits {native.returncode} at COLUMNS={columns!r} "
        f"where `ch-legacy` exits {legacy.returncode}."
    )
    assert native.stdout == legacy.stdout, (
        f"stdout differs at COLUMNS={columns!r} for `ch {' '.join(arguments)}`.\n"
        f"  legacy: {legacy.stdout[:400]!r}\n  native: {native.stdout[:400]!r}"
    )
    assert native.stderr == legacy.stderr, (
        f"stderr differs at COLUMNS={columns!r} for `ch {' '.join(arguments)}`.\n"
        f"  legacy: {legacy.stderr[:400]!r}\n  native: {native.stderr[:400]!r}"
    )


def test_the_sweep_spans_values_argparse_takes_and_values_it_ignores(
    checkout_built_ch: Path, sweep_home: Path
) -> None:
    """The sweep's own discriminating power, measured rather than asserted.

    **Without this the sweep could pass on eighteen values none of which the width
    resolver even reads**, and it would then be a gate about running the binary. The
    check is that the swept set moves the help width for some values and leaves it alone
    for others, so both halves of `int(COLUMNS)`'s behaviour are covered.

    **`+96` must be among the ones argparse takes.** That is the value `terminal.rs`'s
    unit test proves Rich *rejects*, so the pair of tests together says the two
    resolvers disagree and the composition still reproduces legacy.
    """
    default = _run(checkout_built_ch, ["search", "--help"], None, sweep_home)
    default_width = max(
        (len(line) for line in default.stdout.decode().splitlines()), default=0
    )
    taken: list[str] = []
    ignored: list[str] = []
    for columns in COLUMNS_VALUES:
        if columns is None:
            continue
        rendered = _run(checkout_built_ch, ["search", "--help"], columns, sweep_home)
        width = max((len(line) for line in rendered.stdout.decode().splitlines()), default=0)
        (taken if width != default_width else ignored).append(columns)

    assert len(taken) >= 3, (
        f"Only {taken} moved the help width. The sweep is then exercising one branch of "
        "`int(COLUMNS)` and reporting on two."
    )
    assert len(ignored) >= 3, (
        f"Only {ignored} left the help width alone. A sweep of values argparse all "
        "accepts never reaches its rejection path."
    )
    assert "+96" in taken, (
        f"argparse did not take `COLUMNS=+96`, which is the value `terminal.rs` asserts "
        f"Rich rejects. **The two tests are one claim in two places**: without this the "
        f"sweep no longer covers a value the resolvers read differently. Taken: {taken}."
    )
