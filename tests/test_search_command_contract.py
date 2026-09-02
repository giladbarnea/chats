r"""Red acceptance contract for the complete public `ch search` journey.

Five independent proof classes, deliberately kept separate because each one
fails for a different reason. The first three are the spine:

1. Byte lock (green today). Every manifest case runs the public journey through
   a launcher built from this checkout and pins exact exit status, stdout and
   stderr against expectations re-derived from the current Python product. This
   is the parity net; it must never change meaning during the rewrite.
2. Live differential (green today, load-bearing at cutover). The same shapes run
   through `ch-legacy search` and through `ch search`, and the bytes must match.
   Today `ch` hands search to `ch-legacy`, so this compares a process with
   itself and only proves the harness is wired. Once search is native it becomes
   the parity gate that no frozen fixture can rot out from under.
3. Authority proof (red today, by construction). `rust/main.rs` routes every
   non-`parse` command by exec'ing a `ch-legacy` sibling of the running
   executable. Put `ch` alone in a directory and the complete search route must
   still work. It cannot today. That is the single missing Rust authority this
   contract exists to demand, and nothing else in this file may go red for it.

The other two cover dimensions no frozen corpus can hold. The query-validity
differential runs generated patterns through both routes, because an invalid
pattern silently becomes a literal search and a validity disagreement has no
visible trace except a different set of session ids. The terminal differential
drives both routes under a pseudo-terminal at two widths, neither of them 80,
because every corpus case sets COLUMNS and a program that reads only the
variable is otherwise indistinguishable from one that asks the terminal.

The authority proof is a filesystem proof on purpose, and the two alternatives
are ruled out by measurement rather than by taste. On unix the handoff is
`execvp`, which replaces the image in place, so "did `ch` spawn a Python child"
observes nothing. And a `DYLD_PRINT_LIBRARIES` trace is vacuous here: macOS
purges `DYLD_*` for a hardened-runtime interpreter, so the trace stops at the
handoff and reports zero Python libraries for a route that is entirely Python.
Both pass today, for a route that is entirely Python. Only the absence of the
`ch-legacy` file on disk can fail.

Normalization is confessed, not silent. Colored views render an age token and an
age style, both functions of wall clock against a fixed fixture timestamp, so
both are replaced with placeholders in the byte lock. That blinds the byte lock
to the age formatter and its style buckets, so
`test_search_age_token_and_style_track_the_clock` pins that mapping directly.
The unmerged cycle-02 branch normalized the token but not the style, and its
colored expectations silently rotted from green to red in three days.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pty
import re
import shutil
import struct
import subprocess
import termios
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import oracle_provenance
import query_pattern_corpus


PROJECT_ROOT = Path(__file__).parent.parent
ORACLE_SOURCE_ROOT = PROJECT_ROOT / "src" / "chats"


@dataclass(frozen=True)
class Corpus:
    """One fixture pool with its own manifest, timestamps and oracle record.

    There are two, and they are separate on purpose. The contract corpus is
    frozen: the session pool is an input to every broad-pattern case in it, so
    adding a session file there would move a fifth of its expectations —
    invalidation wearing an amendment's clothes. The amendment corpus takes
    post-freeze shapes in a pool of their own, additive by construction.
    """

    name: str
    root: Path

    @property
    def manifest(self) -> list[dict]:
        return json.loads((self.root / "MANIFEST.json").read_text(encoding="utf-8"))["cases"]

    @property
    def mtimes(self) -> dict[str, float]:
        return json.loads((self.root / "MTIMES.json").read_text(encoding="utf-8"))

    @property
    def oracle(self) -> dict[str, str]:
        return json.loads((self.root / "ORACLE.json").read_text(encoding="utf-8"))


CORPORA = (
    Corpus("contract", PROJECT_ROOT / "tests" / "data" / "search-contract-fixtures"),
    Corpus("amendment", PROJECT_ROOT / "tests" / "data" / "search-amendment-fixtures"),
)
FIXTURE_ROOT = CORPORA[0].root
ALL_CASES = [(corpus, case) for corpus in CORPORA for case in corpus.manifest]
ORACLE = CORPORA[0].oracle
CONTRACT_CARGO_TARGET = PROJECT_ROOT / "target" / "contract-suite"
CONTRACT_BUILT_CH = CONTRACT_CARGO_TARGET / "release" / "ch"
VENV_ROOT = PROJECT_ROOT / ".venv"
CHECKOUT_LEGACY = VENV_ROOT / "bin" / "ch-legacy"
# **Imported, never restated.** `tests/deliberate_divergences.py` is the single authority
# for the cases this suite must not assert byte-parity on. A second copy of the list here
# is exactly the defect that produced 21 launcher errors — one fix landing in one of two
# files that held it.
#
# ⚠ **`test_deliberate_divergences.py` used to be named here as the file that asserts what
# each difference IS. It was deleted on 2026-09-02 with the route it ran** — it compared
# `ch` against `ch-legacy` live. **What each difference is, is now asserted against STORED
# bytes**: by `_assert_deliberate_divergence_still_differs` below for this suite, and by
# `_stderr_verdict` in `test_legacy_selection_frozen.py` for the selection recording.
from deliberate_divergences import DELIBERATE  # noqa: E402
# **Probes, not a blacklist.** Each is a production string literal that a release
# build embeds. The guard asserts the binary and the working tree **agree** about every
# one of them, in both directions.
#
# The previous guard was a single forbidden string — `logicalParentUuid`, which the
# unmerged `wip/cycle-02` branch produced and this HEAD did not. **That premise died the
# moment the native `search` arm landed**: the arm links the whole `_native` library into
# `ch` for the first time, so a legitimately fresh build now carries every string in the
# working tree's `session.rs`, that one included. A negative claim about what a fresh
# build "cannot contain" decays every time the tree grows; an agreement between the
# binary and the tree does not.
LAUNCHER_PROVENANCE_PROBES = (
    b"logicalParentUuid",
    b"Search pattern is too expensive to evaluate",
    b"the fence arm maps an unpromoted language to None",
    b"the read table names only promoted families",
    b"a projected tool's input is already valid JSON",
    b"js-delegates",
)
RUST_SOURCE_ROOT = PROJECT_ROOT / "rust"
# Set once the private launcher copy exists. Anything the product prints that
# names the executing script — a traceback's first frame, for one — would
# otherwise carry a per-run temporary path into a byte comparison.
_PRIVATE_LAUNCHER_DIR: Path | None = None

AGE_TOKEN = re.compile(rb"(\x1b\[[0-9;]*m)(\d{1,3}(?:s|m|h|d|w|mo|y)|now|\?)(\x1b\[0m)")
AGE_STYLE_SEQUENCES = (
    b"\x1b[38;2;169;174;180m",
    b"\x1b[38;2;135;140;146m",
    b"\x1b[38;2;107;112;118m",
    b"\x1b[38;2;86;91;97m",
)


def _case_id(pair: tuple[Corpus, dict[str, object]]) -> str:
    corpus, case = pair
    return f"{corpus.name}:{case['id']}"


@pytest.fixture(scope="session", autouse=True)
def oracle_has_not_moved() -> object:
    """Refuse to treat these expectations as evidence for the wrong route.

    ⚠ **This guard changed on 2026-09-02 and it is weaker.** It used to compare
    the corpus's stamp against the LIVE Python route and re-check after the run,
    because the differential ran two processes seconds apart. **The Python search
    authority is deleted, so there is no live route to compare against and no
    second process to race.** What it can still do is refuse a corpus that names
    a route other than the one every frozen artifact here was characterized
    against.

    **What is lost, stated rather than implied:** a source edit that moved the
    oracle under a stored expectation used to fail here. Nothing detects that now.
    The route these 454 files describe is recoverable — `test_oracle_provenance.py`
    proves it re-derives from `67d6053` — but it is not re-runnable.
    """
    oracle_provenance.assert_artifact_names_the_recorded_oracle(
        ORACLE["source_digest"], "the contract corpus"
    )
    yield


def _rust_source_bytes() -> bytes:
    """Every Rust source in the working tree, concatenated."""
    return b"".join(
        path.read_bytes() for path in sorted(RUST_SOURCE_ROOT.rglob("*.rs"))
    )


def _assert_deliberate_divergence_still_differs(case_id: str, ours: bytes, theirs: bytes) -> None:
    """A ruled divergence is exempt from parity here — and must still be a divergence.

    **Not a silent skip.** If the two sides ever agree, the exemption is allowing nothing
    and the id belongs out of `DELIBERATE` — at which point this suite starts asserting
    byte-parity on it again by itself.

    ⚠ **This docstring used to end *"Neither suite can quietly stop meaning anything
    without the other going red"*, naming `test_deliberate_divergences.py` as the other
    suite. That file was deleted on 2026-09-02 with the live route it ran, so the claim
    named one survivor of a pair.** What is true now, and it is narrower:

    **This runs at two call sites against the STORED bytes, so an exemption cannot become
    vacuous** — a case that stops diverging still fails here, and one whose name leaves
    `DELIBERATE` goes back on byte-parity by itself. **Both directions still hold for the
    cases the list NAMES.**

    ***What is gone is completeness.*** The deleted suite ran every recorded case through
    both routes and asserted the differing set was exactly `DELIBERATE`, so a seventh
    divergence appearing was a failure. **Nothing can prove the list is whole any more.**
    """
    assert ours != theirs, (
        f"{case_id} is listed in `DELIBERATE` but now matches `ch-legacy` exactly. "
        "**An exempt case that has stopped diverging is not a pass** — drop it from "
        "`tests/deliberate_divergences.py` and this suite will assert byte-parity on it "
        "again on its own."
    )


def _reject_foreign_launcher(launcher: Path) -> None:
    """Refuse a launcher that disagrees with the working tree about what it contains.

    **A positive freshness proof.** For every probe the binary must carry it if and only
    if the tree does. A stale artifact fails because it is missing what the tree has
    added; a foreign one fails because it carries what the tree has removed.

    Strictly stronger than the forbidden-string guard it replaces, which could only ever
    catch one of those two directions and only for one string.
    """
    if not launcher.is_file():
        return
    tree = _rust_source_bytes()
    in_tree = [probe for probe in LAUNCHER_PROVENANCE_PROBES if probe in tree]
    assert len(in_tree) >= 4, (
        f"Only {len(in_tree)} of {len(LAUNCHER_PROVENANCE_PROBES)} provenance probes "
        "are still in `rust/`. **The guard has decayed into one that cannot prove "
        "freshness**: with too few live probes a stale binary can agree with the tree "
        "about all of them by accident. Choose new probes from current production "
        "string literals."
    )
    launcher_bytes = launcher.read_bytes()
    disagreements = [
        f"{probe.decode()!r}: tree={probe in tree}, launcher={probe in launcher_bytes}"
        for probe in LAUNCHER_PROVENANCE_PROBES
        if (probe in tree) != (probe in launcher_bytes)
    ]
    assert not disagreements, (
        f"Launcher provenance cannot be proven fresh: {launcher} disagrees with "
        f"`rust/` about {disagreements}.\n\n"
        "**This is a real staleness, not a harness quirk.** The launcher was built from "
        "a different tree than the one on disk — a leftover artifact in the build path, "
        "a build from another branch, or a source edit made after the build. Delete the "
        "artifact and let the session fixture rebuild it. If you have just added or "
        "removed one of the probe strings, rebuild before reading this as a failure."
    )


def _place_legacy_sibling(directory: Path) -> None:
    """Give a launcher the private `ch-legacy` sibling its routing expects."""
    assert CHECKOUT_LEGACY.is_file(), (
        f"Expected the checkout virtualenv to own {CHECKOUT_LEGACY} so the built "
        "launcher can route journeys that are still legacy-owned. "
        "Run `uv sync --dev --reinstall-package chats`."
    )
    sibling = directory / "ch-legacy"
    staged = directory / ".ch-legacy.staged"
    staged.unlink(missing_ok=True)
    os.symlink(os.path.relpath(CHECKOUT_LEGACY, directory), staged)
    os.replace(staged, sibling)


@pytest.fixture(scope="session")
def contract_home(corpus_homes: dict[str, Path]) -> Path:
    """The frozen corpus's pool, for the tests that are not corpus-parameterized."""
    return corpus_homes[CORPORA[0].name]


def _environment(
    home: Path, *, columns: int, color: bool, isolated_path: bool = False
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        "HOME": str(home),
        "TZ": "Asia/Jerusalem",
        "COLUMNS": str(columns),
        "LINES": "40",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "NO_COLOR": "1",
    })
    if color:
        environment.pop("NO_COLOR", None)
    if isolated_path:
        # A `ch-legacy` reachable through PATH would let the route survive for a
        # reason the authority proof is not allowed to accept.
        environment["PATH"] = "/usr/bin:/bin"
    return environment


def _normalize(content: bytes, home: Path) -> bytes:
    """Replace the bytes that no fixed corpus can own: paths and wall-clock age."""
    normalized = (
        content.replace(str(home).encode(), b"{HOME}")
        .replace(str(CONTRACT_BUILT_CH.parent).encode(), b"{LAUNCHER_DIR}")
        .replace(str(PROJECT_ROOT).encode(), b"{PROJECT_ROOT}")
    )
    if _PRIVATE_LAUNCHER_DIR is not None:
        normalized = normalized.replace(str(_PRIVATE_LAUNCHER_DIR).encode(), b"{LAUNCHER_DIR}")
    # Token first. The style substitution rewrites the SGR introducer that
    # AGE_TOKEN anchors on, so the reverse order silently disables the token
    # replacement and leaves a wall-clock value in the corpus.
    normalized = AGE_TOKEN.sub(rb"\g<1>{AGE}\g<3>", normalized)
    for style in AGE_STYLE_SEQUENCES:
        normalized = normalized.replace(style, b"\x1b[{AGE_STYLE}m")
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", normalized)


def _run_search(
    executable: Path,
    case: dict[str, object],
    home: Path,
    *,
    isolated_path: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    arguments = [
        str(argument).replace("{HOME}", str(home)) for argument in case["arguments"]
    ]
    return subprocess.run(
        [str(executable), "search", *arguments],
        cwd=PROJECT_ROOT,
        env=_environment(
            home,
            columns=int(case.get("columns", 96)),
            color=bool(case.get("color")),
            isolated_path=isolated_path,
        ),
        capture_output=True,
        check=False,
    )


# ── 1. Byte lock against the characterized Python product ────────────────────


@pytest.mark.parametrize("pair", ALL_CASES, ids=_case_id)
def test_search_journey_matches_characterized_legacy_bytes(
    checkout_built_ch: Path,
    corpus_homes: dict[str, Path],
    pair: tuple[Corpus, dict[str, object]],
) -> None:
    """The public journey must reproduce the characterized product byte for byte."""
    corpus, case = pair
    contract_home = corpus_homes[corpus.name]
    completed = _run_search(checkout_built_ch, case, contract_home)
    expected_stdout = (corpus.root / str(case["expected_stdout"])).read_bytes()
    expected_stderr = (corpus.root / str(case["expected_stderr"])).read_bytes()

    assert completed.returncode == case["exit_status"], (
        f"Expected exit status {case['exit_status']} for {case['id']}. "
        f"Got: {completed.returncode}. stderr: {completed.stderr[-600:]!r}"
    )
    if str(case["id"]) in DELIBERATE:
        _assert_deliberate_divergence_still_differs(
            str(case["id"]),
            _normalize(completed.stdout, contract_home) + _normalize(completed.stderr, contract_home),
            expected_stdout + expected_stderr,
        )
        return
    assert _normalize(completed.stdout, contract_home) == expected_stdout, (
        f"Expected characterized stdout bytes for {case['id']}. "
        f"Expected: {expected_stdout[:600]!r}; got: "
        f"{_normalize(completed.stdout, contract_home)[:600]!r}."
    )
    assert _normalize(completed.stderr, contract_home) == expected_stderr, (
        f"Expected characterized stderr bytes for {case['id']}. "
        f"Expected: {expected_stderr[:600]!r}; got: "
        f"{_normalize(completed.stderr, contract_home)[:600]!r}."
    )


# ── 2. Live differential against the Python implementation ───────────────────


# ── 3. Native authority: the intended red ────────────────────────────────────


@pytest.fixture(scope="session")
def solitary_launcher(checkout_built_ch: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of the public launcher with no `ch-legacy` sibling to fall back on."""
    directory = tmp_path_factory.mktemp("solitary-launcher")
    solitary = directory / "ch"
    shutil.copy2(checkout_built_ch, solitary)
    assert not (directory / "ch-legacy").exists(), (
        "Expected the solitary launcher directory to hold no private legacy entry."
    )
    return solitary


def test_solitary_launcher_harness_is_sound(solitary_launcher: Path, contract_home: Path) -> None:
    """A command that is already native must work with no `ch-legacy` sibling.

    Without this control, the solitary-launcher proof below could pass for the
    wrong reason once `ch parse` regresses, or fail for a reason unrelated to
    search.
    """
    completed = subprocess.run(
        [str(solitary_launcher), "parse", "--help"],
        cwd=PROJECT_ROOT,
        env=_environment(contract_home, columns=96, color=False),
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, (
        "Expected the already-native `ch parse` route to succeed without a "
        f"`ch-legacy` sibling. Got exit {completed.returncode}, "
        f"stderr: {completed.stderr!r}."
    )


@pytest.mark.parametrize("pair", ALL_CASES, ids=_case_id)
def test_search_journey_needs_no_private_legacy_entry(
    solitary_launcher: Path,
    corpus_homes: dict[str, Path],
    pair: tuple[Corpus, dict[str, object]],
) -> None:
    """Every search shape must run with no `ch-legacy` sibling on disk.

    `rust/main.rs::run_legacy` resolves `ch-legacy` beside the running
    executable, so a launcher standing alone cannot delegate. This is red until
    the search route is genuinely native, and it is the only reason this file is
    allowed to be red.
    """
    corpus, case = pair
    contract_home = corpus_homes[corpus.name]
    completed = _run_search(solitary_launcher, case, contract_home, isolated_path=True)
    expected_stdout = (corpus.root / str(case["expected_stdout"])).read_bytes()
    expected_stderr = (corpus.root / str(case["expected_stderr"])).read_bytes()

    assert b"Cannot start the private ch legacy entry" not in completed.stderr, (
        f"Expected `ch search` to serve {case['id']} natively. It tried to hand the "
        "journey to the private legacy entry, which is the missing Rust authority."
    )
    assert completed.returncode == case["exit_status"], (
        f"Expected exit status {case['exit_status']} for {case['id']} with no legacy "
        f"sibling. Got: {completed.returncode}."
    )
    if str(case["id"]) in DELIBERATE:
        _assert_deliberate_divergence_still_differs(
            str(case["id"]),
            _normalize(completed.stdout, contract_home) + _normalize(completed.stderr, contract_home),
            expected_stdout + expected_stderr,
        )
        return
    assert _normalize(completed.stdout, contract_home) == expected_stdout, (
        f"Expected identical stdout for {case['id']} with no legacy sibling."
    )
    assert _normalize(completed.stderr, contract_home) == expected_stderr, (
        f"Expected identical stderr for {case['id']} with no legacy sibling."
    )


def test_solitary_launcher_still_refuses_a_legacy_owned_command(
    solitary_launcher: Path,
    contract_home: Path,
) -> None:
    """A command that is still legacy-owned must fail without its private entry.

    This is the other half of the harness control. Together with
    `test_solitary_launcher_harness_is_sound` it proves the solitary directory
    discriminates: already-native routes work in it, legacy-owned routes cannot.
    A no-Python proof that cannot fail for a legacy-owned command is measuring
    nothing.
    """
    completed = subprocess.run(
        [str(solitary_launcher), "info", "--help"],
        cwd=PROJECT_ROOT,
        env=_environment(contract_home, columns=96, color=False),
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0, (
        "Expected the legacy-owned `ch info` route to fail with no `ch-legacy` "
        "sibling. It succeeded, so the solitary directory is not isolating anything."
    )
    assert b"Cannot start the private ch legacy entry" in completed.stderr, (
        "Expected the private-entry error to name the missing legacy sibling. "
        f"Got stderr: {completed.stderr!r}."
    )


# ── Query validity: the divergence with no visible trace ─────────────────────


# `compile_search_term` catches `re.error` and recompiles the escaped pattern,
# so an invalid pattern silently becomes a literal search. The set of patterns
# CPython *accepts* is therefore part of the public contract: a validator that
# accepts a different set flips a pattern between regex and literal, changing
# which sessions match, with no error raised on either side. Nothing except a
# product differential can see it. `query-semantics` measured this directly —
# over 4,000 generated patterns, all 994 engine divergences were accept-or-
# reject and none were match semantics.
GENERATED_PATTERN_SEED = 20260828
GENERATED_PATTERN_COUNT = 60
# Width is a generated dimension, not a constant, because a colored diff taken
# at one width cannot see a width defect. None of these is 80.
GENERATED_PATTERN_WIDTHS = (52, 96, 110, 140)


# ── Colored output on a real terminal ────────────────────────────────────────


def _run_search_on_terminal(
    executable: Path,
    arguments: list[str],
    home: Path,
    *,
    columns: int,
    rows: int = 40,
) -> tuple[int, bytes]:
    """Run a search on a pseudo-terminal of a given size and return its raw bytes.

    `COLUMNS` and `LINES` are removed on purpose. Every fixture case sets them,
    which makes the whole interactive-width dimension invisible: a program that
    reads only the variable is indistinguishable from one that asks the
    terminal. This is the only place the difference can be seen.
    """
    controller, terminal = pty.openpty()
    fcntl.ioctl(terminal, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    environment = os.environ.copy()
    environment.pop("COLUMNS", None)
    environment.pop("LINES", None)
    environment.pop("NO_COLOR", None)
    environment.update({
        "HOME": str(home),
        "TZ": "Asia/Jerusalem",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
    })
    process = subprocess.Popen(
        [str(executable), "search", *arguments],
        stdin=terminal,
        stdout=terminal,
        stderr=terminal,
        env=environment,
    )
    os.close(terminal)
    chunks: list[bytes] = []
    while True:
        try:
            data = os.read(controller, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    process.wait()
    os.close(controller)
    return process.returncode, b"".join(chunks)


# Neither width is 80. Eighty is `main`'s own fallback constant and the one
# point where a width-aware renderer and a hard-coded one agree, so a diff taken
# there proves nothing. The narrow width is chosen to force elision in list rows
# and panel titles, which `test_narrow_terminal_actually_elides` verifies rather
# than assumes.
TERMINAL_WIDTHS = (52, 110)
TERMINAL_SHAPES = (
    ("list-rows", ["needle", "-l", "--no-paging"]),
    ("matches-panels", ["needle five", "--no-paging", "--no-metadata"]),
    ("full-panel-fences", ["Renderfence shell", "-f", "--no-paging", "--no-metadata"]),
    ("wide-glyphs", ["Renderwide", "-f", "--no-paging", "--no-metadata"]),
    ("long-wrapped-lines", ["Renderwrap", "-f", "--no-paging", "--no-metadata"]),
)


def test_narrow_terminal_actually_elides(
    checkout_built_ch: Path,
    contract_home: Path,
) -> None:
    """The narrow width must really be narrow enough to exercise elision.

    Without this, `TERMINAL_WIDTHS` could drift wide and the width dimension
    would quietly stop being tested while both parameterized cases still passed.
    """
    narrow, wide = TERMINAL_WIDTHS
    _, narrow_output = _run_search_on_terminal(
        checkout_built_ch, ["needle", "-l", "--no-paging"], contract_home, columns=narrow
    )
    _, wide_output = _run_search_on_terminal(
        checkout_built_ch, ["needle", "-l", "--no-paging"], contract_home, columns=wide
    )

    assert "…".encode() in narrow_output, (
        f"Expected {narrow} columns to force elision in the colored list rows, so "
        "that the narrow parameterization exercises the width path at all."
    )
    assert narrow_output != wide_output, (
        f"Expected {narrow} and {wide} columns to render differently. Identical "
        "output means the renderer is not reading the terminal."
    )


# ── A right behaviour whose absence looks right ──────────────────────────────


STREAM_MARKER = "streammarker"
# `|` is a regex metacharacter, so this pattern has no literal candidate and the
# fast byte gate is bypassed. Every file then gets a full semantic scan, which is
# what makes the scan long enough to separate from interpreter startup.
STREAM_PATTERN = f"{STREAM_MARKER}|zzznope"
STREAM_DECOY_COUNT = 800
STREAM_DECOY_BODY = "unrelated filler content " * 400


def _build_streaming_home(home: Path, *, match_newest: bool) -> str:
    """One matching session among many decoys, placed newest or oldest."""
    projects = home / ".claude" / "projects" / "stream"
    projects.mkdir(parents=True)
    base = 1_800_030_000.0
    for index in range(STREAM_DECOY_COUNT):
        path = projects / f"decoy-{index:04d}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "type": "user",
                    "timestamp": "2026-08-20T10:00:00.000Z",
                    "cwd": "/tmp/stream",
                    "message": {"role": "user", "content": f"{STREAM_DECOY_BODY} {index}"},
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        os.utime(path, (base + index, base + index))

    match = projects / "match-session.jsonl"
    match.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": "2026-08-20T11:00:00.000Z",
                "cwd": "/tmp/stream",
                "message": {"role": "user", "content": f"{STREAM_MARKER} lives here"},
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    stamp = base + STREAM_DECOY_COUNT + 1 if match_newest else base - 1
    os.utime(match, (stamp, stamp))
    return match.stem


def _time_to_first_id(executable: Path, home: Path) -> tuple[float, float, str]:
    """Run an id-only search through a real pipe; time the first line and the exit."""
    environment = _environment(home, columns=96, color=False)
    start = time.perf_counter()
    process = subprocess.Popen(
        [str(executable), "search", STREAM_PATTERN, "-ll"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        cwd=PROJECT_ROOT,
    )
    first_line = process.stdout.readline()
    first_at = time.perf_counter() - start
    process.stdout.read()
    process.wait()
    return first_at, time.perf_counter() - start, first_line.decode().strip()


def test_first_session_id_reaches_a_pipe_before_the_scan_finishes(
    checkout_built_ch: Path,
    tmp_path: Path,
) -> None:
    """Streamed ids must reach a pipe as they are found, not at exit.

    `commands/search.py` flushes each id individually, and that flush is the
    entire deliverable of a measured scope: the first id of a real query went
    from 15.995 s to 0.38 s with completion time unchanged, purely because Python
    was block-buffering three short lines into a pipe.

    **No byte gate can see this.** An implementation that buffers produces
    identical bytes in identical order with the same exit status, and gives back
    the most visible latency in the product. It is a timing property, and time to
    first id through a real pipe is the only shape of test that fails on it.

    Measured as a pair rather than against a budget: the same corpus with the
    match placed newest and then oldest. Both runs pay identical interpreter
    startup, so the difference between their first-id times is scan time and
    nothing else. If output were held until exit, both would equal the total and
    the difference would vanish.
    """
    newest_home = tmp_path / "newest"
    oldest_home = tmp_path / "oldest"
    expected_id = _build_streaming_home(newest_home, match_newest=True)
    assert _build_streaming_home(oldest_home, match_newest=False) == expected_id

    newest_first_at, newest_total, newest_id = _time_to_first_id(checkout_built_ch, newest_home)
    oldest_first_at, _oldest_total, oldest_id = _time_to_first_id(checkout_built_ch, oldest_home)

    assert newest_id == expected_id and oldest_id == expected_id, (
        f"Expected both runs to find {expected_id!r}. Got {newest_id!r} and {oldest_id!r}."
    )
    # Control: the corpus must really take time to scan, or the comparison below
    # is measuring noise and would pass on any implementation.
    assert oldest_first_at - newest_first_at > 0.15, (
        "Expected a scan long enough for streaming to matter. The first id "
        f"appeared after {newest_first_at * 1000:.0f} ms with the match newest and "
        f"{oldest_first_at * 1000:.0f} ms with it oldest, a difference too small to "
        "distinguish streaming from buffering. Raise STREAM_DECOY_COUNT."
    )
    assert newest_first_at < oldest_first_at * 0.85, (
        "Expected the first session id to reach the pipe when it was found, not "
        f"when the scan finished. Newest match: first id at {newest_first_at * 1000:.0f} ms "
        f"of {newest_total * 1000:.0f} ms total. Oldest match: first id at "
        f"{oldest_first_at * 1000:.0f} ms. Two similar times mean output is being "
        "held until exit, which is byte-identical and much slower to first result."
    )


EARLY_CLOSE_MARKER = "closemarker"
EARLY_CLOSE_PATTERN = f"{EARLY_CLOSE_MARKER}|zzznope"
# Raised from 800 after the cutover. The same corpus took 557 ms through the
# Python route and 153 ms through the native one, which fell under this
# test's own 400 ms floor — so the control refused to report a ratio it
# could no longer measure. **A corpus adjustment, not a relaxed
# expectation:** the floor and the 0.7 ratio are unchanged; only the amount
# of work is, so that the comparison stays measurable against a faster
# implementation.
EARLY_CLOSE_SESSION_COUNT = 3000


def _build_early_close_home(home: Path) -> None:
    """A pool where *every* session matches.

    Deliberate. With a single match there is nothing left to write after the
    first line, so no write ever reaches the closed pipe and the process runs to
    completion whether or not it handles early close. A corpus that cannot
    distinguish the two is worse than no gate at all.
    """
    projects = home / ".claude" / "projects" / "close"
    projects.mkdir(parents=True)
    base = 1_800_040_000.0
    body = "unrelated filler content " * 400
    for index in range(EARLY_CLOSE_SESSION_COUNT):
        path = projects / f"match-{index:04d}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "type": "user",
                    "timestamp": "2026-08-20T10:00:00.000Z",
                    "cwd": "/tmp/close",
                    "message": {
                        "role": "user",
                        "content": f"{EARLY_CLOSE_MARKER} {body} {index}",
                    },
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        os.utime(path, (base + index, base + index))


def _time_until_exit(executable: Path, home: Path, *, close_after_first: bool) -> tuple[float, int]:
    """Run an id-only search through a pipe; optionally stop reading after one line."""
    environment = _environment(home, columns=96, color=False)
    start = time.perf_counter()
    process = subprocess.Popen(
        [str(executable), "search", EARLY_CLOSE_PATTERN, "-ll"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        cwd=PROJECT_ROOT,
    )
    lines = 1 if process.stdout.readline() else 0
    if not close_after_first:
        while process.stdout.readline():
            lines += 1
    process.stdout.close()
    process.wait()
    return time.perf_counter() - start, lines


def test_a_closed_reader_stops_the_scan(
    checkout_built_ch: Path,
    tmp_path: Path,
) -> None:
    """When the consumer stops reading, the scan must stop.

    `ch search … | head`, or quitting the pager on the first screen, must not
    leave the scan running to completion. Measured against the abandoned
    branch's native binary, this economy was lost entirely: it saved 92% in
    Python and -1% natively, confirmed independently through `head -1`. Total
    output was well inside a pipe buffer, so it was not back-pressure.

    Measured as a pair on one corpus — closed after one line, versus read to the
    end — so both runs pay identical interpreter startup and the difference is
    scan time alone. The same shape as the streaming gate, for the same reason:
    an absolute budget here would measure process startup.
    """
    home = tmp_path / "home"
    _build_early_close_home(home)

    full_elapsed, full_lines = _time_until_exit(
        checkout_built_ch, home, close_after_first=False
    )
    closed_elapsed, _ = _time_until_exit(checkout_built_ch, home, close_after_first=True)

    assert full_lines == EARLY_CLOSE_SESSION_COUNT, (
        f"Expected every session to match so that writes keep reaching the pipe. "
        f"Got {full_lines} of {EARLY_CLOSE_SESSION_COUNT} ids."
    )
    # Control: the full scan must be long enough for an early exit to be visible,
    # or the comparison below is measuring noise and passes on anything.
    assert full_elapsed > 0.4, (
        f"Expected the full scan to take long enough to measure. It took "
        f"{full_elapsed * 1000:.0f} ms. Raise EARLY_CLOSE_SESSION_COUNT."
    )
    assert closed_elapsed < full_elapsed * 0.7, (
        "Expected a closed reader to stop the scan. Reading one line and closing "
        f"took {closed_elapsed * 1000:.0f} ms against {full_elapsed * 1000:.0f} ms "
        "for the whole scan. Times this close mean the scan ran to completion with "
        "nobody listening."
    )


# ── The normalizations must actually fire ────────────────────────────────────


# Every placeholder `_normalize` can emit, and whether the corpus should contain
# it. A substitution that fires nowhere is indistinguishable from one that is
# unnecessary, so absence has to be a recorded decision rather than an accident.
NORMALIZATION_PLACEHOLDERS: dict[bytes, str | None] = {
    b"{AGE}": None,
    b"{AGE_STYLE}": None,
    b"{SEARCH_QUERY_SOURCE}": None,
    b"{HOME}": "Session paths are rendered `~`-collapsed, so the fixture home's "
    "absolute path never reaches output. Kept as a guard for a future case that "
    "prints one.",
    b"{PROJECT_ROOT}": "Only ever appeared inside a traceback, and the one case "
    "that produced one was removed — a traceback cannot be a golden.",
    b"{LAUNCHER_DIR}": "Same: only a traceback's first frame names the executing "
    "script. Kept because the next uncaught error would carry a per-run path.",
}


def test_every_normalization_placeholder_is_accounted_for() -> None:
    """No placeholder may exist without a decision about whether it should appear."""
    emitted = {
        placeholder
        for placeholder in (b"{AGE}", b"{AGE_STYLE}", b"{HOME}", b"{PROJECT_ROOT}", b"{LAUNCHER_DIR}", b"{SEARCH_QUERY_SOURCE}")
    }
    assert emitted == set(NORMALIZATION_PLACEHOLDERS), (
        "A placeholder was added to or removed from `_normalize` without a "
        "corresponding entry saying whether the corpus should contain it. "
        f"Emitted: {sorted(emitted)}; declared: {sorted(NORMALIZATION_PLACEHOLDERS)}."
    )


@pytest.mark.parametrize(
    "placeholder",
    [p for p, absent_because in NORMALIZATION_PLACEHOLDERS.items() if absent_because is None],
    ids=lambda p: p.decode(),
)
def test_declared_normalizations_appear_in_the_corpus(placeholder: bytes) -> None:
    """Every declared placeholder must appear somewhere, or its substitution is dead.

    This exists because one of them was dead for a day and nothing noticed. The
    colour substitution rewrites the SGR introducer that `AGE_TOKEN` anchors on,
    so running it first silently disabled the token replacement, and seventeen
    expectations carried a live wall-clock value instead. **A normalization that
    quietly no-ops is invisible in exactly the same way as one that is
    unnecessary** — the corpus looks the same either way — so the only thing that
    separates them is asking whether the placeholder is there at all.

    The pair is also why order matters: the contract promises to normalize the
    age token and its colour together, and half of that promise was being kept.
    """
    # Both streams: the warning-source placeholder only ever lands on stderr,
    # and globbing stdout alone made this gate report a live substitution dead.
    found = [
        path.name
        for corpus in CORPORA
        for path in sorted((corpus.root / "expected").glob("*"))
        if path.suffix in (".stdout", ".stderr") and placeholder in path.read_bytes()
    ]
    assert found, (
        f"No expectation contains {placeholder.decode()}, so its substitution "
        "never fires and whatever it was meant to replace is still in the corpus. "
        "Check the order of the replacements in `_normalize`."
    )


def test_normalization_substitutes_escapes_rather_than_stripping_them() -> None:
    """A structure-only difference must survive normalization.

    Two defects found elsewhere on this mission were **identical text with
    different segment structure**: an empty segment emitting an escape pair Rich
    omits, and an empty span cutting a run Rich leaves whole. Both are invisible
    to any comparator over visible characters.

    `_normalize` is safe from them because of the *shape* of the transform, not
    the care of its author: it substitutes one escape sequence for one
    placeholder and rewrites a token's payload between two preserved sequences.
    It never strips, inserts, merges or splits. Byte count and boundary
    positions survive, so structure does.

    **The common design — strip ANSI, compare text — hides all three shapes
    below.** This test exists so that a future rewrite into that shape fails
    here rather than silently becoming blind to a defect class.
    """
    age_colour = AGE_STYLE_SEQUENCES[1]
    reset = b"\x1b[0m"
    home = Path("/nonexistent-home-for-this-check")
    structure_only = {
        "a run split in two versus left whole": (
            age_colour + b"foo" + reset + age_colour + b"bar" + reset,
            age_colour + b"foobar" + reset,
        ),
        "an extra empty escape pair": (
            age_colour + reset + age_colour + b"x" + reset,
            age_colour + b"x" + reset,
        ),
        "an empty span cutting a run": (
            age_colour + b"ab" + reset + reset + age_colour + b"cd" + reset,
            age_colour + b"abcd" + reset,
        ),
    }

    hidden = [
        name
        for name, (left, right) in structure_only.items()
        if _normalize(left, home) == _normalize(right, home)
    ]
    assert not hidden, (
        f"Normalization now hides structure-only differences: {hidden}. Something "
        "has started removing escape sequences rather than substituting them, and "
        "the suite is blind to a defect class that produces identical visible text."
    )

    # The declared blindness, asserted here too so its scope stays visible beside
    # the property that bounds it: colour among the four age buckets, nothing else.
    assert _normalize(age_colour + b"2w" + reset, home) == _normalize(
        AGE_STYLE_SEQUENCES[2] + b"2w" + reset, home
    ), "Expected the four age colours to normalize alike — the declared blindness."


def test_no_expectation_carries_a_raw_age_token() -> None:
    """The bytes the age normalization exists to remove must be gone.

    The positive check above proves the placeholder appears somewhere; this
    proves the thing it replaces appears nowhere. Both are needed: a substitution
    can fire on some rows and miss others, which is exactly what a partially
    matching pattern does.
    """
    raw = re.compile(rb"\{AGE_STYLE\}m(\d{1,3}(?:s|m|h|d|w|mo|y)|now)\x1b")
    offenders = {
        path.name: match.group(1).decode()
        for corpus in CORPORA
        for path in sorted((corpus.root / "expected").glob("*.stdout"))
        for match in raw.finditer(path.read_bytes())
    }
    assert not offenders, (
        "Expectations still carry a wall-clock age token next to a normalized "
        f"age colour, so they rot as the fixtures age: {offenders}."
    )


# ── What the byte lock's normalization hides ─────────────────────────────────


def _write_claude_session(path: Path, *, text: str, timestamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = timestamp.astimezone().isoformat(timespec="milliseconds")
    path.write_text(
        json.dumps(
            {
                "type": "user",
                "timestamp": stamp,
                "cwd": "/tmp/ch-age-contract",
                "message": {"role": "user", "content": text},
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


AGE_NOW = b"\x1b[38;2;169;174;180m"
AGE_WEEK = b"\x1b[38;2;135;140;146m"
AGE_MONTH = b"\x1b[38;2;107;112;118m"
AGE_OLD = b"\x1b[38;2;86;91;97m"


# Every pair below is preserved *because* it is wrong. `humanize_age` and
# `age_style` carry separate, unaligned thresholds, so the colour is
# consistently one bucket older than the label it paints: a row reading `3d`
# wears the week colour, `2w` wears month, `1mo` wears old. A native
# implementation driving both from one table — the obvious simplification, and
# the one any reviewer would ask for — repaints every coloured result row.
#
# Do not "fix" these expectations. If a future change aligns the thresholds, the
# behaviour has moved and this is the test that is supposed to say so.
#
# The last pair is the same class in the units: months are 30 days and years are
# 365, so ages between 360 and 365 days render `12mo` before jumping to `1y`.
@pytest.mark.parametrize(
    ("age", "expected_token", "expected_style"),
    [
        (timedelta(hours=3), "3h", AGE_NOW),
        (timedelta(days=3), "3d", AGE_WEEK),
        (timedelta(days=12), "1w", AGE_MONTH),
        (timedelta(days=14), "2w", AGE_MONTH),
        (timedelta(days=31), "1mo", AGE_OLD),
        (timedelta(days=362), "12mo", AGE_OLD),
        (timedelta(days=400), "1y", AGE_OLD),
    ],
    ids=["hours", "days", "weeks", "two-weeks", "one-month", "twelve-months", "years"],
)
def test_search_age_token_and_style_track_the_clock(
    checkout_built_ch: Path,
    tmp_path: Path,
    age: timedelta,
    expected_token: str,
    expected_style: bytes,
) -> None:
    """Pin the age rendering that the byte lock replaces with placeholders.

    The colored list row renders a relative age token and picks its colour from
    an age bucket. Both are wall-clock functions, so the byte lock cannot own
    them; without this test the placeholders would hide an entire parity class.
    """
    home = tmp_path / "home"
    session = home / ".claude" / "projects" / "age" / "age-session.jsonl"
    _write_claude_session(session, text="agecontract body", timestamp=datetime.now() - age)

    case = {
        "id": "age",
        "arguments": ["agecontract", "-l", "--color", "always", "--no-paging"],
        "columns": 96,
        "color": True,
    }
    completed = _run_search(checkout_built_ch, case, home)

    assert completed.returncode == 0, (
        f"Expected the age fixture to match. stderr: {completed.stderr!r}"
    )
    assert expected_token.encode() in completed.stdout, (
        f"Expected the colored list row to render age token {expected_token!r} for an "
        f"age of {age}. Got: {completed.stdout!r}"
    )
    assert expected_style in completed.stdout, (
        f"Expected the colored list row to style an age of {age} with "
        f"{expected_style!r}. Got: {completed.stdout!r}"
    )
