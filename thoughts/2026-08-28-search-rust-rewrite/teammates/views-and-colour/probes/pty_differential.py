#!/usr/bin/env -S uv run
"""Byte-differential two `ch search` routes under a real pty, at widths nobody pins.

Built before the native route exists, so that the instrument is ready the moment
there is something to point it at rather than being assembled under pressure at
the final gate.

**What this is for.** The contract suite has 25 coloured cases and every one of
them pins `columns: 96`. Three width defects have already hidden behind that one
unexamined dimension. This drives the same cases at several widths, none of them
96 and none of them 80.

**Why a pty and not a pipe.** Piped, Rich reports 80 columns and a `COLUMNS`-only
helper also returns 80 — the two agree at exactly the width where a width defect
is invisible. And colour is suppressed off a terminal, so the whole subject under
test disappears.

**Six requirements, each bought with somebody's mistake.**

1. The clock is pinned with `CH_NOW` on both sides. Age appears in every list row
   and every panel title; without it any age-bearing diff is meaningless.
2. Two or more widths, none of them 80 — that is Rich's fallback constant, so a
   diff there hides a width defect and a total failure to measure alike.
3. Every `\\r` is stripped, not `\\r\\n` pairs. A pty emits `\\r\\r\\n` when a line
   exactly fills the terminal, so a `.replace("\\r\\n", "\\n")` consumes one pair and
   leaves a stray `\\r`, inventing mismatches at exactly the boundary widths where a
   real wrapping defect would live.
4. Machine-specific paths are normalised, and determinism is proved by capturing
   twice rather than assumed.
5. Nothing is decoded during capture. Universal newlines rewrite carriage returns
   and a pty additionally applies ONLCR, so pty bytes may only be compared with
   pty bytes.
6. The harness ships with its own falsification: `--self-test` requires it to
   catch a deliberately perturbed subject in each dimension it claims to see.

**What running it today does and does not prove.** `rust/main.rs` routes only
`parse` natively and sends `search` to `ch-legacy`, so today both sides are the
same Python. A green run is therefore a calibration of this instrument, **not a
parity result**, and it must not be reported as one.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "reviewer-profiler"),
)
from pty_harness import run_at_width  # noqa: E402


def run_on_two_ptys(
    arguments: list[str], *, columns: int, rows: int = 40, environment: dict[str, str]
) -> tuple[bytes, bytes]:
    """Run a command with stdout and stderr on **separate** ptys, capturing both.

    `pty_harness.run_at_width` sends stderr to `DEVNULL`, which makes an entire
    output stream invisible — and `--color never` leaving stderr coloured lives
    exactly there. Six gates on this desk import that function and none of them can
    see it.

    Two ptys rather than one, because a shared pty interleaves the streams
    nondeterministically, and because the product resolves colour **per stream**:
    stderr's tty-ness decides stderr's colour independently of stdout's. A harness
    putting stderr on a pipe records plain bytes by construction and proves nothing.

    Not a copy of `run_at_width` — a different question. Offered back to
    `reviewer-profiler`, whose gates would gain the same sight.
    """
    import fcntl
    import pty
    import select
    import struct
    import termios

    def sized_pty() -> tuple[int, int]:
        controller, follower = pty.openpty()
        fcntl.ioctl(follower, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
        return controller, follower

    out_controller, out_follower = sized_pty()
    error_controller, error_follower = sized_pty()
    process = subprocess.Popen(
        arguments,
        stdin=subprocess.DEVNULL,
        stdout=out_follower,
        stderr=error_follower,
        env=environment,
        close_fds=True,
    )
    os.close(out_follower)
    os.close(error_follower)

    collected = {out_controller: [], error_controller: []}
    open_descriptors = [out_controller, error_controller]
    try:
        while open_descriptors:
            ready, _, _ = select.select(open_descriptors, [], [], 120)
            if not ready:
                break
            for descriptor in ready:
                try:
                    chunk = os.read(descriptor, 65536)
                except OSError:
                    chunk = b""
                if chunk:
                    collected[descriptor].append(chunk)
                else:
                    open_descriptors.remove(descriptor)
    finally:
        for descriptor in (out_controller, error_controller):
            os.close(descriptor)
        process.wait(timeout=120)
    return b"".join(collected[out_controller]), b"".join(collected[error_controller])

FIXTURES = Path("tests/data/search-contract-fixtures")
# Neither 80 (Rich's fallback) nor 96 (what every recorded coloured case pins).
# 40 is narrow enough to force elision in both the list row and the panel title.
DEFAULT_WIDTHS = (40, 60, 120)
# Chosen by measurement, not convenience. The fixture sessions' content
# timestamps cluster tightly, so most instants put every row in one age bucket.
# This one spans three and includes the label-to-colour disagreement itself:
# `1d` painted week, `22h` painted now, `4mo` painted old.
DEFAULT_NOW = "2027-01-16T12:00:00"

# The clock is a sweep dimension, not a constant. The fixture sessions' content
# timestamps cluster within 600 seconds, so any single instant collapses most rows
# into one age bucket and leaves the age colour barely represented.
#
# Imported rather than copied. Each instant is offset from the corpus's own
# timestamps to land one label unit, so between them they reach all seven. This was
# a hand-kept copy until `reviewer-profiler` moved their `sys.argv` read inside
# `main()` to make it importable — two copies that agree do not fail when they
# drift, so both gates would have kept passing while measuring different instants.
from age_pairing_gate import CLOCK_INSTANTS  # noqa: E402

DEFAULT_CLOCKS = tuple(CLOCK_INSTANTS)

# The contract's 25 coloured cases all search for specific needles, so between
# them they never reach the week age colour. These add the shapes this harness
# owns: every session in both views, so ages span buckets and the border hue
# cycles past its first entry.
# G4's coloured half. The whole-route differential is blind to every one of these
# for two independent reasons — it sets `NO_COLOR=1` *and* it captures through a
# pipe, so `flags.color` resolves false through the isatty cascade either way. Only
# a pty separates them, so these are the modes no other gate on the mission covers.
#
# No `--color` flag: colour must resolve **on** by itself under a terminal, which is
# the condition being tested. `--no-paging` because a real `less` would block.
G4_COLOURED_CASES = [
    {"id": "g4-default-matches", "arguments": ["needle five", "--no-paging"]},
    {"id": "g4-full", "arguments": ["needle five", "--full", "--no-paging"]},
    {"id": "g4-list", "arguments": [".", "-l", "--no-paging"]},
    {"id": "g4-matches-no-metadata", "arguments": ["needle five", "--no-metadata", "--no-paging"]},
    # Two fence rows were added on the captain's requirement that **green must not
    # depend on what the fixture omits**. Every case above renders plain text, so the
    # coloured gate could once have passed while the renderer refused the commonest
    # thing a message body carries.
    #
    # **One survives and is now a real parity row.** Python is a promoted family, so
    # the native route lexes this fence with Pygments' own table and must match
    # `ch-legacy` byte for byte. It was red by design while the table was missing;
    # it is an ordinary parity row now and must actually go green.
    {"id": "g4-fence-covered-later", "arguments": ["Renderfence python", "--no-paging"]},
    #
    # **`g4-fence-never-covered` was removed on 2026-08-30, and removing it is the
    # point rather than a retreat.** By the captain's ruling a language Pygments
    # knows and no table covers renders **plain**, while `ch-legacy` **colours** it.
    # So a byte comparison differs by design, and keeping the row would leave G4
    # carrying a permanently red entry whose redness was expected — the
    # omission-dependent state this gate spent two days removing. Nobody can then
    # tell an expected red from a regression.
    #
    # **Its own subject had also decayed**, which is the second reason. The row's
    # `web` tag covered javascript, html and css on the grounds that none would ever
    # be promoted; **javascript was promoted on 2026-08-30.** An assertion about
    # non-promotion whose subject is one promotion away from moving is a trap, and
    # the Rust side now guards against it mechanically rather than by comment.
    #
    # **The replacement is a behaviour assertion and it is three tests**, all in
    # `session_render::fence_render_oracle_tests`:
    #
    #   the_fallback_subjects_are_still_the_right_ones
    #       derives each subject's membership from `lexer_for_tag` and
    #       `promoted_lexer`, so promoting a language moves the tag instead of
    #       silently invalidating the assertion.
    #   a_fence_in_an_unrecognised_language_renders_plain_as_legacy_does
    #       `mermaid`, `just`, `mdx` — tags reaching no Pygments lexer. Plain output
    #       here is **parity**: `ch-legacy` renders them plain too.
    #   a_fence_in_a_known_but_unported_language_renders_plain_and_diverges
    #       `css`, `html`, `xml`, `yaml` — complete geometry, background and padding,
    #       plain unstyled code, and **never a refusal**, because a refusal panics the
    #       panel sink and truncates a scan that has already printed. This one is the
    #       accepted divergence, asserted so it cannot be mistaken for parity.
    #
    # **Do not restore the row here.** A parity row for a deliberate divergence
    # cannot pass.
]

VIEW_CASES = [
    {"id": "views-list-all", "arguments": [".", "-l", "--color", "always", "--no-paging"]},
    {"id": "views-panels-all", "arguments": [".", "--color", "always", "--no-paging"]},
    {"id": "views-panels-no-metadata",
     "arguments": [".", "--color", "always", "--no-paging", "--no-metadata"]},
]


def fixture_home() -> Path:
    """A private copy of the fixture home with its recorded mtimes restored.

    `copytree` stamps every file with the time of the copy, which would move every
    age in the output and make two runs incomparable.
    """
    home = Path(tempfile.mkdtemp(prefix="ch-pty-diff-")) / "home"
    shutil.copytree(FIXTURES / "home", home)
    for relative, mtime in json.loads((FIXTURES / "MTIMES.json").read_text()).items():
        target = home / relative
        os.utime(target, (mtime, mtime))
    return home


# The colour tier is a swept dimension. A harness pinned at truecolor sees one of
# three renderings: `NO_COLOR` strips colour and **keeps bold**, so a match survives
# as an attribute, and `TERM=dumb` emits no SGR at all, so a search match becomes
# visually indistinguishable from the text around it. A painting defect that appears
# only once colour is stripped is invisible to a truecolor-only gate — the same shape
# as the branch's blocker, which an ASCII-only corpus could not see, one axis over.
# Measured and handed over by `context-curator`.
TIERS: dict[str, dict[str, str]] = {
    "truecolor": {"TERM": "xterm-256color", "COLORTERM": "truecolor"},
    "eight-bit": {"TERM": "xterm-256color"},
    "standard": {"TERM": "xterm-16color"},
    "no-color": {"TERM": "xterm-256color", "COLORTERM": "truecolor", "NO_COLOR": "1"},
    # Width comparisons prove nothing here: `TERM=dumb` pins Rich to 80 columns by a
    # different path than the width fallback. Byte equality still does.
    "dumb": {"TERM": "dumb"},
}


def environment_for(home: Path, now: str, tier: str = "truecolor") -> dict[str, str]:
    """The child environment, pinned in every dimension that moves output."""
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "TZ": "Asia/Jerusalem",
        "CH_NOW": now,
        "LC_ALL": "en_US.UTF-8",
        **TIERS[tier],
    }


def normalise(output: bytes, home: Path) -> bytes:
    """Strip the pty's carriage returns and the machine-specific home path.

    Every `\\r` goes, never `\\r\\n` pairs: a line that exactly fills the terminal
    emits `\\r\\r\\n`, and pair-replacement leaves a stray `\\r` behind that reads as
    a real wrapping defect at exactly the boundary widths.
    """
    return output.replace(b"\r", b"").replace(str(home).encode(), b"$HOME")


G4_ONLY = False


def coloured_cases() -> list[dict]:
    """The contract cases that render colour, which are the ones needing a pty."""
    if G4_ONLY:
        return G4_COLOURED_CASES
    cases = json.loads((FIXTURES / "MANIFEST.json").read_text())["cases"]
    return [case for case in cases if case.get("color")] + VIEW_CASES


# The native route is not wired into `rust/main.rs` yet — `ch search` still falls
# through to `ch-legacy`. `engine-and-codex`'s `searchdriver` is the three-arm
# cutover function as a standalone binary, so a differential can run before the
# route is live. It takes the search arguments directly, with no `search` token.
SUBJECT_TAKES_SEARCH_TOKEN = True


def capture(
    binary: str, case: dict, columns: int, home: Path, now: str, tier: str = "truecolor",
    takes_search_token: bool = True,
) -> bytes:
    """Both streams, concatenated with a marker so a difference names its stream.

    stderr is compared, not discarded: `--color never` leaves it coloured, and a
    native route that routes the colour choice to all four consoles would suppress
    that. Nothing else on this desk would notice.
    """
    arguments = [binary, *(["search"] if takes_search_token else []), *case["arguments"]]
    out, error = run_on_two_ptys(
        arguments, columns=columns, environment=environment_for(home, now, tier)
    )
    return normalise(out, home) + b"\n--- stderr ---\n" + normalise(error, home)


def responsiveness(route: str, home: Path, cases: list[dict], settings, capture_for) -> dict:
    """Per case, how many distinct outputs a route produces across a dimension.

    **Per case, never route-wide.** The earlier version probed a single hardcoded
    case and reported a conclusion about the route — so when a case rendered a form
    that cannot express the dimension at all, it blamed the route for that case's
    silence. That is a claim whose scope is wider than its evidence, in a guard built
    to catch exactly that shape: it could not tell *the subject ignores this input*
    from *this case cannot express this input*.

    A dimension is genuinely swept when **at least one case responds**.
    """
    return {
        case["id"]: len({capture_for(route, case, home, setting) for setting in settings})
        for case in cases
    }


def compare(
    subject: str,
    reference: str,
    widths: tuple[int, ...],
    clocks: tuple[str, ...],
    tiers: tuple[str, ...] = tuple(TIERS),
) -> tuple[int, list[str]]:
    """Compare both routes over every coloured case at every width and clock."""
    cases = coloured_cases()
    home = fixture_home()
    compared = 0
    failures: list[str] = []

    for name, settings, capture_for, label in (
        ("clock", clocks,
         lambda route, case, home, now: capture(route, case, 100, home, now,
                                                takes_search_token=SUBJECT_TAKES_SEARCH_TOKEN
                                                if route == subject else True),
         "CH_NOW"),
        ("tier", tuple(TIERS), 
         lambda route, case, home, tier: capture(route, case, 72, home, clocks[0], tier,
                                                 takes_search_token=SUBJECT_TAKES_SEARCH_TOKEN
                                                 if route == subject else True),
         "the ambient colour inputs"),
    ):
        if len(settings) < 2:
            continue
        per_case = responsiveness(subject, home, cases, settings, capture_for)
        responding = [case_id for case_id, distinct in per_case.items() if distinct > 1]
        if not responding:
            failures.append(
                f"{name.upper()} IGNORED no case responded to {label} across "
                f"{len(settings)} settings. Either the subject does not consult it, or "
                f"every case renders a form that cannot express it — this cannot "
                f"distinguish those, so check a case that should respond."
            )
        else:
            inert = [case_id for case_id, distinct in per_case.items() if distinct == 1]
            if inert:
                print(f"   note: {name} is inert for {len(inert)} of {len(per_case)} cases "
                      f"({', '.join(inert[:3])}) and live for {len(responding)} "
                      f"({', '.join(responding[:3])}) — swept.")

    for tier in tiers:
     for now in clocks:
      for columns in widths:
        for case in cases:
            reference_bytes = capture(reference, case, columns, home, now, tier)

            # Determinism before comparison. A route that differs from itself
            # makes every difference from the other route unattributable.
            again = capture(reference, case, columns, home, now, tier)
            if reference_bytes != again:
                failures.append(
                    f"NONDETERMINISTIC {case['id']} @ {columns}/{now}/{tier}: "
                    f"the reference route differs from itself between two captures"
                )
                continue

            subject_bytes = capture(
                subject, case, columns, home, now, tier, SUBJECT_TAKES_SEARCH_TOKEN
            )
            compared += 1
            if subject_bytes != reference_bytes:
                failures.append(
                    f"DIFFERS {case['id']} @ {columns}/{now}/{tier}\n"
                    f"  reference {reference_bytes[:220]!r}\n"
                    f"  subject   {subject_bytes[:220]!r}"
                )
    return compared, failures


# Each perturbation targets one dimension this harness claims to see. They are
# applied to the *captured bytes*, never through a shell pipe: piping the child's
# stdout would hand it a pipe instead of the pty, which suppresses colour and
# collapses width to 80, so the mutant would differ for a reason that has nothing
# to do with the dimension under test.
#
# Applying them to the capture tests both halves at once. If the capture had
# destroyed a dimension, its pattern would not be present and the perturbation
# would be a no-op -- which is reported as BLIND rather than counted as a pass.
PERTURBATIONS: dict[str, tuple[str, bytes, bytes]] = {
    "age-colour": (
        "repaint the week age bucket as month",
        b"\x1b[38;2;135;140;146m",
        b"\x1b[38;2;107;112;118m",
    ),
    "border-hue": (
        "freeze the second border hue to the first",
        b"\x1b[38;2;157;124;216m",
        b"\x1b[38;2;92;200;168m",
    ),
    "box-width": (
        "shorten every border dash run",
        "\u2500\u2500".encode(),
        "\u2500".encode(),
    ),
    "ellipsis": ("spell the ellipsis as three dots", "\u2026".encode(), b"..."),
    "tick": ("replace the row tick", "\u258e".encode(), b"|"),
    "highlight": (
        "drop the matched-term highlight",
        b"\x1b[1;38;2;20;24;29;48;2;230;180;80m",
        b"\x1b[0m",
    ),
}


def self_test(reference: str, widths: tuple[int, ...], clocks: tuple[str, ...]) -> int:
    """Require the harness to catch a deliberately wrong subject, per dimension.

    A gate that has never been observed to fail is not evidence. The age colour is
    first because every other comparator on this mission normalises it away, so it
    is the one dimension where this harness has to be the thing that sees.
    """
    cases = coloured_cases()
    home = fixture_home()

    # Sensitivity is a property of the whole sweep, not of one width. A narrow
    # width clips the list row before its age token, so measuring only there
    # reports the harness blind to a dimension it sees perfectly at 120.
    captures = [
        capture(reference, case, columns, home, now)
        for now in clocks
        for columns in widths
        for case in cases
    ]
    corpus = b"".join(captures)

    blind: list[str] = []
    for name, (description, pattern, replacement) in PERTURBATIONS.items():
        occurrences = corpus.count(pattern)
        if occurrences == 0:
            print(
                f"  {name:<12} {description:<44} BLIND "
                f"(pattern absent from the capture -- the dimension never reached it)"
            )
            blind.append(name)
            continue
        caught = sum(
            original.replace(pattern, replacement) != original for original in captures
        )
        status = "caught" if caught else "BLIND"
        print(
            f"  {name:<12} {description:<44} {status} "
            f"({caught}/{len(captures)} captures, {occurrences} occurrences)"
        )
        if not caught:
            blind.append(name)

    if blind:
        print(f"\nFAILED  the harness is blind to: {', '.join(blind)}")
        return 1
    print(
        f"\nPASS    every perturbation was caught across widths "
        f"{', '.join(str(w) for w in widths)} and {len(clocks)} clocks"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default=".venv/bin/ch")
    parser.add_argument("--reference", default=".venv/bin/ch-legacy")
    parser.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS))
    parser.add_argument("--clocks", default=",".join(DEFAULT_CLOCKS))
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--g4", action="store_true",
        help="G4's coloured half: the modes that need a terminal, against the native driver.")
    parser.add_argument(
        "--subject-takes-search-token", default="yes", choices=("yes", "no"),
        help="`no` for a driver that takes search arguments directly.")
    options = parser.parse_args()

    global SUBJECT_TAKES_SEARCH_TOKEN
    SUBJECT_TAKES_SEARCH_TOKEN = options.subject_takes_search_token == "yes"
    widths = tuple(int(width) for width in options.widths.split(","))
    clocks = tuple(options.clocks.split(","))
    for forbidden, why in ((80, "Rich's fallback constant"), (96, "what every recorded coloured case pins")):
        if forbidden in widths:
            parser.error(f"width {forbidden} is {why}; a diff there proves nothing")

    global G4_ONLY
    G4_ONLY = options.g4

    if options.self_test:
        print(f"Falsifying the harness against {options.reference} across widths "
              f"{', '.join(str(w) for w in widths)} and {len(clocks)} clocks:")
        return self_test(options.reference, widths, clocks)

    compared, failures = compare(options.subject, options.reference, widths, clocks)
    print(f"{compared} comparisons over {len(coloured_cases())} coloured cases, "
          f"widths {', '.join(str(w) for w in widths)}, {len(clocks)} clocks")
    if failures:
        print(f"\nFAILED  {len(failures)} differences")
        for failure in failures[:10]:
            print(f"   {failure}")
        return 1
    print("PASS    both routes agree byte for byte")
    if Path(options.subject).name == "ch" and Path(options.reference).name == "ch-legacy":
        print(
            "\nNOTE    `ch search` still falls through to `ch-legacy`, so this run\n"
            "        calibrated the instrument and compared Python with Python.\n"
            "        It is not a parity result and must not be reported as one."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
