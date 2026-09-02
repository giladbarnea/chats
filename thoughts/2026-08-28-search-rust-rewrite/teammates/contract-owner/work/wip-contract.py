r"""Cycle-03 red contract: the complete installed-launcher `ch search` journey.

Every manifest case runs through both package-owned installed launchers and
pins exact stdout bytes, stderr bytes, and exit status against characterized
legacy-search truth. Every covered process also runs under Darwin loader
tracing and must prove single-process native authority with no Python, PyO3,
`_native`, or ABI3 libraries — the intended-red authority seam this contract
exists to enforce before any production code moves the journey.

Engine-strategy ratification (evidence in the accompanying cycle notes): the
query-truth boundary is CPython 3.14 `re` semantics as characterized through
the legacy route, pinned adversarially on both sides:

* Python-valid constructs that naive Rust `regex` ports reject or misread —
  lookarounds, backreferences plus `(?P=w)`, atomic groups `(?>…)`, possessive
  quantifiers `a++`, valid conditionals `(?(1)x|y)` (requires an always
  participating group), `\N{…}` named escapes, empty alternation branches
  (`zznope|` matches every session!), POSIX-class spellings that Python reads
  as ordinary character sets, scoped inline flags `(?i:…)`, `\Z` as absolute
  end (distinct from `$` before a trailing newline), and IGNORECASE folding
  pins including `i`~`İ` (U+0130), `s`~`ſ` (U+017F), and `k`~`K` (U+212A).
* Python-invalid constructs that must take the literal fallback exactly —
  `(?<x>a)`, `\p{L}`, `\x{41}`, `[z-a]`, `a{2,1}`, `\8`, `(?P=name)`,
  `(?(1)x|y)` without a group, `\y`, unmatched `(`, mismatched `[`.

Any implementation that reproduces these pinned bytes satisfies the contract;
one that swaps engines naively fails on the divergence pins above.
"""

from __future__ import annotations

import base64
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "data" / "search-command-fixtures"
MANIFEST = json.loads((FIXTURE_ROOT / "MANIFEST.json").read_text(encoding="utf-8"))["cases"]
MTIMES = json.loads((FIXTURE_ROOT / "MTIMES.json").read_text(encoding="utf-8"))
REAL_INSTALLED_CH = Path.home() / ".local" / "bin" / "ch"
CHECKOUT_INSTALLED_CH = PROJECT_ROOT / ".venv" / "bin" / "ch"
INSTALLED_EXECUTABLES = [
    pytest.param(CHECKOUT_INSTALLED_CH, id="checkout-install"),
    pytest.param(REAL_INSTALLED_CH, id="real-uv-tool-install"),
]
BOTH_INSTALLED_LAUNCHERS = [CHECKOUT_INSTALLED_CH, REAL_INSTALLED_CH]
MACH_O_MAGICS = {
    b"\xca\xfe\xba\xbe",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xbe\xba\xfe\xca",
}
CWD = "/tmp/search-contract"


@pytest.fixture(scope="module")
def contract_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    home = tmp_path_factory.mktemp("search-command-contract") / "home"
    shutil.copytree(FIXTURE_ROOT / "home", home)
    for relative_path, mtime in MTIMES.items():
        os.utime(home / relative_path, (mtime, mtime))
    return home


def _environment(
    home: Path,
    *,
    columns: int = 96,
    color: bool = False,
    loader_trace: bool = False,
    path_prefix: str | None = None,
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
    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}:{environment['PATH']}"
    if loader_trace:
        environment["DYLD_PRINT_LIBRARIES"] = "1"
    return environment


def _normalize(content: bytes, home: Path) -> bytes:
    """Normalize volatile bytes exactly as the fixture generator does: paths,
    warning source roots, and the wall-clock relative age token that colored
    views render from ``humanize_age`` (review F1: ``1d`` decays to ``2d`` at
    the next UTC boundary and would rot the green layer)."""
    normalized = (
        content.replace(str(home).encode(), b"{HOME}")
        .replace(str(PROJECT_ROOT).encode(), b"{PROJECT_ROOT}")
    )
    normalized = re.sub(
        rb"(\x1b\[[0-9;]*m)(\d{1,3}[smhdw]|\?)(\x1b\[0m)",
        rb"\g<1>{AGE}\g<3>",
        normalized,
    )
    return re.sub(rb"\S+search_query\.py", b"{SEARCH_QUERY_SOURCE}", normalized)


def _run_case(
    executable: Path,
    case: dict[str, object],
    home: Path,
    *,
    loader_trace: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    arguments = [
        str(argument).replace("{HOME}", str(home))
        for argument in case["arguments"]
    ]
    return subprocess.run(
        [str(executable), "search", *arguments],
        cwd=PROJECT_ROOT,
        env=_environment(
            home,
            columns=int(case.get("columns", 96)),
            color=bool(case.get("color")),
            loader_trace=loader_trace,
        ),
        input=b"",
        capture_output=True,
        check=False,
        timeout=180,
    )


def _loader_lines(stderr: bytes) -> list[bytes]:
    return [
        line
        for line in stderr.splitlines()
        if re.match(rb"^dyld\[\d+\]:", line)
    ]


def _assert_no_python_authority(
    completed: subprocess.CompletedProcess[bytes],
) -> None:
    loader_lines = _loader_lines(completed.stderr)
    process_ids = {
        match.group(1)
        for line in loader_lines
        if (match := re.match(rb"^dyld\[(\d+)\]:", line))
    }
    forbidden = [
        line
        for line in loader_lines
        if any(
            marker in line.lower()
            for marker in (b"python", b"_native", b"abi3")
        )
    ]

    assert loader_lines, (
        "Expected Darwin loader evidence for the search process. "
        f"stderr tail: {completed.stderr[-1000:]!r}."
    )
    assert len(process_ids) == 1, (
        "Expected exactly one native search process with no exec'd child. "
        f"Observed loader process IDs: {sorted(process_ids)!r}."
    )
    assert not forbidden, (
        "Expected no Python executable, Python library, PyO3 extension, or ABI3 "
        f"authority on the search journey. Forbidden loader entries: {forbidden[:20]!r}."
    )


@pytest.mark.parametrize("case", MANIFEST, ids=lambda case: str(case["id"]))
@pytest.mark.parametrize("executable", INSTALLED_EXECUTABLES)
def test_search_process_matches_characterized_legacy_bytes(
    executable: Path,
    case: dict[str, object],
    contract_home: Path,
) -> None:
    completed = _run_case(executable, case, contract_home)
    expected_stdout = (FIXTURE_ROOT / str(case["expected_stdout"])).read_bytes()
    expected_stderr = (FIXTURE_ROOT / str(case["expected_stderr"])).read_bytes()

    assert completed.returncode == case["exit_status"], (
        f"Expected characterized exit status {case['exit_status']} for "
        f"{case['id']} through {executable}. Got: {completed.returncode}. "
        f"stderr tail: {completed.stderr[-500:]!r}."
    )
    normalized_stdout = _normalize(completed.stdout, contract_home)
    assert normalized_stdout == expected_stdout, (
        f"Expected exact characterized stdout for {case['id']} through "
        f"{executable}. Expected {len(expected_stdout)} bytes; got "
        f"{len(normalized_stdout)} bytes."
    )
    assert _normalize(completed.stderr, contract_home) == expected_stderr, (
        f"Expected exact characterized stderr for {case['id']} through "
        f"{executable}."
    )


@pytest.mark.parametrize("case", MANIFEST, ids=lambda case: str(case["id"]))
@pytest.mark.parametrize("executable", INSTALLED_EXECUTABLES)
def test_every_search_manifest_process_has_no_python_authority(
    executable: Path,
    case: dict[str, object],
    contract_home: Path,
) -> None:
    completed = _run_case(executable, case, contract_home, loader_trace=True)

    assert completed.returncode == case["exit_status"], (
        f"Expected loader tracing not to change {case['id']} exit status. "
        f"Got: {completed.returncode}."
    )
    _assert_no_python_authority(completed)


def _write_claude_session(
    home: Path,
    project: str,
    session_id: str,
    entries: list[dict[str, object]],
    mtime: float,
) -> Path:
    path = home / ".claude/projects" / project / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )
    os.utime(path, (mtime, mtime))
    return path


def _claude_user(text: str, timestamp: str) -> dict[str, object]:
    return {
        "type": "user",
        "uuid": f"u-{timestamp}",
        "timestamp": timestamp,
        "cwd": CWD + "/generated",
        "message": {"role": "user", "content": text},
    }


def test_equal_mtimes_enumerate_in_reverse_discovery_order(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    session_ids = [
        f"tie{index}0000-0000-4000-8000-00000000000{index}" for index in range(6)
    ]
    for index, session_id in enumerate(session_ids):
        _write_claude_session(
            home,
            "ties",
            session_id,
            [_claude_user(f"tieorder body {index}", "2026-08-20T10:00:00Z")],
            mtime=1_900_000_000,
        )
    completed = subprocess.run(
        [str(CHECKOUT_INSTALLED_CH), "search", "tieorder", "-ll"],
        cwd=PROJECT_ROOT,
        env=_environment(home),
        input=b"",
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    assert completed.stdout.decode().splitlines() == list(reversed(session_ids)), (
        "Expected equal-mtime ties to enumerate in reverse discovery "
        "(creation) order through the stable ascending sort followed by "
        "reversal."
    )


def test_literal_candidate_gate_crosses_the_256_file_batch_window(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    marked_ids = {}
    total = 257
    for index in range(total):
        marker = f"windowmarker{index}"
        session_id = f"win{index:04d}000-0000-4000-8000-{index:012d}"
        _write_claude_session(
            home,
            "windows",
            session_id,
            [_claude_user(f"filler {index} {marker}", "2026-08-20T10:00:00Z")],
            mtime=2_000_000_000 - index,
        )
        if index in (0, 130, 256):
            marked_ids[marker] = session_id
    query = "windowmarker0 OR windowmarker130 OR windowmarker256"
    completed = subprocess.run(
        [str(CHECKOUT_INSTALLED_CH), "search", query, "-ll"],
        cwd=PROJECT_ROOT,
        env=_environment(home),
        input=b"",
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr[-500:]
    observed = completed.stdout.decode().splitlines()
    assert observed == [
        marked_ids["windowmarker0"],
        marked_ids["windowmarker130"],
        marked_ids["windowmarker256"],
    ], (
        "Expected candidates in the first window, across the 256 boundary, "
        "and in the final partial window to confirm identically."
    )


def test_malformed_pool_files_report_errors_and_keep_streaming_hits(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    shutil.copytree(FIXTURE_ROOT / "home", home)
    for relative_path, mtime in MTIMES.items():
        os.utime(home / relative_path, (mtime, mtime))
    broken = home / ".claude/projects/broken"
    broken.mkdir(parents=True)
    bad_utf8 = broken / "badutf8.jsonl"
    bad_utf8.write_bytes(
        b'{"type":"user","message":{"role":"user","content":"\xff\xfe bad"}}\n'
    )
    malformed = broken / "malformed.jsonl"
    malformed.write_text('{"type":"user", broken\n', encoding="utf-8")
    empty = broken / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    newest = 2_100_000_000.0
    for path in (bad_utf8, malformed, empty):
        os.utime(path, (newest, newest))

    def run(arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [str(CHECKOUT_INSTALLED_CH), "search", *arguments],
            cwd=PROJECT_ROOT,
            env=_environment(home),
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )

    matches_mode = run(["needle five", "--no-metadata", "--color", "never"])
    only_id_mode = run(["zzbrokenmarker", "-ll"])
    mixed_mode = run(['"needle five" OR bad', "-ll"])

    for label, completed in (
        ("matches", matches_mode),
        ("only-id", only_id_mode),
        ("mixed", mixed_mode),
    ):
        stderr = _normalize(completed.stderr, home)
        assert b"Error processing conversation file" in stderr, (
            f"Expected per-file error reporting for {label} mode."
        )
        assert b"'utf-8' codec can't decode" in stderr, (
            f"Expected the invalid-UTF-8 decode error for {label} mode."
        )
    assert matches_mode.returncode == 0, (
        "Expected valid hits to keep streaming despite malformed pool files."
    )
    assert b"88888888-8888-4888-8888-888888888888" in matches_mode.stdout
    assert only_id_mode.returncode == 1, (
        "Expected a no-hit search over only-broken candidates to exit 1 after "
        "reporting the per-file errors."
    )
    assert mixed_mode.returncode == 0
    assert set(mixed_mode.stdout.decode().split()) == {
        "88888888-8888-4888-8888-888888888888",
        "44444444-4444-4444-8444-444444444444",
    }, "Expected only valid hits; broken pool files contribute nothing."


def test_empty_pool_exits_silently_in_every_mode(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    for label, arguments in (
        ("matches", ["anything", "--color", "never"]),
        ("list", ["anything", "-l", "--color", "never"]),
        ("full", ["anything", "-f", "--color", "never"]),
        ("raw", ["anything", "-r"]),
        ("only-id", ["anything", "-ll"]),
        ("dot-only-id", [".", "-ll"]),
    ):
        completed = subprocess.run(
            [str(CHECKOUT_INSTALLED_CH), "search", *arguments],
            cwd=PROJECT_ROOT,
            env=_environment(home),
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )
        assert completed.returncode == 1, (
            f"Expected the empty pool to exit 1 in {label} mode."
        )
        assert completed.stdout == b"", (
            f"Expected no stdout in {label} mode over an empty pool."
        )
        assert completed.stderr == b"", (
            f"Expected the empty-pool exit to stay silent in {label} mode; "
            f"got {completed.stderr!r}."
        )


def _install_contract_fake_less(bin_directory: Path) -> Path:
    """Install a fake less that logs each chunk and can stop after N chunks."""
    bin_directory.mkdir(parents=True, exist_ok=True)
    marker_source = bin_directory / "less-marker.c"
    marker_library = bin_directory / "libch_search_contract_less_marker.dylib"
    marker_source.write_text("void ch_search_contract_less_marker(void) {}\n")
    marker_compile = subprocess.run(
        [
            "/usr/bin/clang",
            "-dynamiclib",
            str(marker_source),
            "-o",
            str(marker_library),
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert marker_compile.returncode == 0, (
        f"Expected the fake less identity library to compile. {marker_compile.stderr!r}"
    )
    source = bin_directory / "less.c"
    executable = bin_directory / "less"
    source.write_text(
        r'''#include <stdio.h>
#include <stdlib.h>
extern void ch_search_contract_less_marker(void);
int main(int argc, char **argv) {
    ch_search_contract_less_marker();
    FILE *arguments = fopen(getenv("CH_PAGER_ARGUMENTS"), "wb");
    for (int index = 1; index < argc; index++) {
        fputs(argv[index], arguments);
        fputc('\n', arguments);
    }
    fclose(arguments);
    if (getenv("CH_PAGER_EARLY_EXIT")) return 0;
    const char *max_chunks = getenv("CH_PAGER_MAX_CHUNKS");
    int delivered = 0;
    int limit = max_chunks ? atoi(max_chunks) : 0;
    FILE *log = fopen(getenv("CH_PAGER_CHUNK_LOG"), "ab");
    unsigned char buffer[4096];
    size_t count;
    while ((count = fread(buffer, 1, sizeof(buffer), stdin)) > 0) {
        fwrite(buffer, 1, count, log);
        fflush(log);
        delivered += 1;
        if (limit && delivered >= limit) break;
    }
    fclose(log);
    return 0;
}
''',
        encoding="utf-8",
    )
    compile_result = subprocess.run(
        [
            "/usr/bin/clang",
            "-O2",
            str(source),
            "-L",
            str(bin_directory),
            "-lch_search_contract_less_marker",
            f"-Wl,-rpath,{bin_directory}",
            "-o",
            str(executable),
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert compile_result.returncode == 0, (
        f"Expected the fake less harness to compile. {compile_result.stderr!r}"
    )
    return executable


def _write_big_session(home: Path, session_id: str, megabytes: int, mtime: float) -> None:
    filler = "F" * (megabytes * 1024 * 1024 - len(session_id) - 40)
    _write_claude_session(
        home,
        "big",
        session_id,
        [{
            "type": "user",
            "uuid": "u-big",
            "timestamp": "2026-08-20T10:00:00Z",
            "cwd": CWD + "/big",
            "message": {"role": "user", "content": f"bigsessionmark {filler} bigtail"},
        }],
        mtime=mtime,
    )


def test_pager_receives_hits_incrementally_in_newest_first_order(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    newest_id = "aaa00000-0000-4000-8000-000000000001"
    oldest_id = "bbb00000-0000-4000-8000-000000000002"
    big_id = "ccc00000-0000-4000-8000-000000000003"
    _write_claude_session(
        home,
        "stream",
        newest_id,
        [_claude_user("streamfirstmark hit body", "2026-08-20T10:00:00Z")],
        mtime=2_200_000_003,
    )
    _write_big_session(home, big_id, megabytes=6, mtime=2_200_000_002)
    _write_claude_session(
        home,
        "stream",
        oldest_id,
        [_claude_user("streamlastmark hit body", "2026-08-20T09:00:00Z")],
        mtime=2_200_000_001,
    )
    fake_bin = tmp_path / "bin"
    _install_contract_fake_less(fake_bin)
    chunk_log = tmp_path / "chunks.log"
    arguments_path = tmp_path / "pager-arguments"
    environment = _environment(home, color=True, path_prefix=str(fake_bin))
    environment.update({
        "CH_PAGER_CHUNK_LOG": str(chunk_log),
        "CH_PAGER_ARGUMENTS": str(arguments_path),
        "LESS": "--RAW-CONTROL-CHARS --use-color",
    })
    process = subprocess.Popen(
        [
            str(CHECKOUT_INSTALLED_CH),
            "search",
            "streamfirstmark|bigsessionmark|streamlastmark",
            "--color",
            "always",
            "--no-metadata",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 60
        saw_incremental_delivery = False
        while time.monotonic() < deadline:
            if chunk_log.exists() and b"streamfirstmark" in chunk_log.read_bytes():
                if process.poll() is None:
                    saw_incremental_delivery = True
                break
            time.sleep(0.01)
        assert saw_incremental_delivery, (
            "Expected the first hit to reach the pager while the search "
            "process was still scanning the remaining pool."
        )
        stdout, stderr = process.communicate(timeout=120)
    finally:
        if process.poll() is None:
            process.kill()

    assert process.returncode == 0, stderr[-500:]
    assert stderr == b""
    pager_stream = chunk_log.read_bytes()
    first_offset = pager_stream.index(b"streamfirstmark")
    big_offset = pager_stream.index(b"bigsessionmark")
    last_offset = pager_stream.index(b"streamlastmark")
    assert first_offset < big_offset < last_offset, (
        "Expected per-hit delivery to the pager in newest-first order."
    )
    assert b"streamfirstmark" not in stdout and b"bigsessionmark" not in stdout, (
        "Expected the engaged pager to receive the hits instead of stdout."
    )


def test_pager_cancellation_after_first_chunk_skips_remaining_hits(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    newest_id = "ddd00000-0000-4000-8000-000000000001"
    oldest_id = "eee00000-0000-4000-8000-000000000002"
    big_id = "fff00000-0000-4000-8000-000000000003"
    _write_claude_session(
        home,
        "cancel",
        newest_id,
        [_claude_user("cancelfirstmark hit body", "2026-08-20T10:00:00Z")],
        mtime=2_300_000_003,
    )
    _write_big_session(home, big_id, megabytes=6, mtime=2_300_000_002)
    _write_claude_session(
        home,
        "cancel",
        oldest_id,
        [_claude_user("cancellastmark hit body", "2026-08-20T09:00:00Z")],
        mtime=2_300_000_001,
    )
    fake_bin = tmp_path / "bin"
    _install_contract_fake_less(fake_bin)
    chunk_log = tmp_path / "cancel-chunks.log"
    arguments_path = tmp_path / "cancel-pager-arguments"
    environment = _environment(home, color=True, path_prefix=str(fake_bin))
    environment.update({
        "CH_PAGER_CHUNK_LOG": str(chunk_log),
        "CH_PAGER_ARGUMENTS": str(arguments_path),
        "CH_PAGER_MAX_CHUNKS": "1",
        "LESS": "--RAW-CONTROL-CHARS --use-color",
    })
    completed = subprocess.run(
        [
            str(CHECKOUT_INSTALLED_CH),
            "search",
            "cancelfirstmark|bigsessionmark|cancellastmark",
            "--color",
            "always",
            "--no-metadata",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        input=b"",
        capture_output=True,
        check=False,
        timeout=240,
    )

    assert completed.returncode == 0, completed.stderr[-500:]
    assert completed.stderr == b""
    pager_stream = chunk_log.read_bytes() if chunk_log.exists() else b""
    assert b"cancelfirstmark" in pager_stream, (
        "Expected the newest hit to be delivered to the pager before cancellation."
    )
    assert b"cancellastmark" not in pager_stream, (
        "Expected the hit loop to stop writing after the pager went away."
    )


def test_missing_less_falls_back_to_stdout_with_single_final_newline(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    shutil.copytree(FIXTURE_ROOT / "home", home)
    for relative_path, mtime in MTIMES.items():
        os.utime(home / relative_path, (mtime, mtime))
    environment = _environment(home, color=True)
    environment["PATH"] = "/nonexistent"
    arguments = [
        "search",
        "needle five",
        "--color",
        "always",
        "--paging",
        "--no-metadata",
    ]
    completed = subprocess.run(
        [str(CHECKOUT_INSTALLED_CH), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        input=b"",
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr[-500:]
    assert completed.stderr == b""
    assert completed.stdout.endswith(b"\n"), (
        "Expected the missing-less fallback output to end with exactly one "
        "final newline."
    )
    assert not completed.stdout.endswith(b"\n\n"), (
        "Expected no doubled final newline in the missing-less fallback."
    )


def test_missing_less_fallback_has_no_python_authority(tmp_path: Path) -> None:
    home = tmp_path / "home"
    shutil.copytree(FIXTURE_ROOT / "home", home)
    for relative_path, mtime in MTIMES.items():
        os.utime(home / relative_path, (mtime, mtime))
    environment = _environment(home, color=True, loader_trace=True)
    environment["PATH"] = "/nonexistent"
    completed = subprocess.run(
        [
            str(CHECKOUT_INSTALLED_CH),
            "search",
            "needle five",
            "--color",
            "always",
            "--paging",
            "--no-metadata",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        input=b"",
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr[-500:]
    _assert_no_python_authority(completed)


def test_broken_stdout_pipe_matches_exact_exit_and_stderr(
    contract_home: Path,
) -> None:
    """Full-pool plain XML exceeds the 64KB pipe buffer, so closing stdout
    after the first bytes guarantees a mid-write EPIPE regardless of timing."""

    def run(loader_trace: bool) -> tuple[int, bytes]:
        environment = _environment(
            contract_home,
            loader_trace=loader_trace,
        )
        # Review F4 root cause: under DYLD_PRINT_LIBRARIES the child emits
        # ~266KB of loader logging into a 16KB stderr pipe before main(). With
        # stderr on PIPE the child blocks in dyld while this parent blocks on
        # stdout.read(50) — a mutual deadlock the watchdog then reports as a
        # confusing `assert 0 == 50`. A real file absorbs any volume, keeps
        # captured stderr byte-exact, and needs no drain thread.
        with tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(
                [
                    str(CHECKOUT_INSTALLED_CH),
                    "search",
                    ".",
                    "-f",
                    "--no-metadata",
                    "--color",
                    "never",
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
            )
            # Review F4: a wedged early-startup process must never hang pytest.
            watchdog = threading.Timer(120.0, process.kill)
            watchdog.daemon = True
            watchdog.start()
            try:
                assert process.stdout is not None
                first_bytes = process.stdout.read(50)
                process.stdout.close()
                exit_status = process.wait(timeout=60)
                stderr_file.seek(0)
                stderr = stderr_file.read()
            finally:
                watchdog.cancel()
        assert len(first_bytes) == 50
        return exit_status, stderr

    exit_status, stderr = run(loader_trace=False)

    assert exit_status == 1, (
        f"Expected the legacy broken-pipe exit status 1. Got: {exit_status}."
    )
    assert stderr == b"", f"Expected empty broken-pipe stderr. Got: {stderr!r}."

    traced_status, traced_stderr = run(loader_trace=True)
    traced = subprocess.CompletedProcess([], traced_status, b"", traced_stderr)

    assert traced_status == exit_status
    # Loader tracing legitimately floods stderr with dyld lines; pin that the
    # search process itself still contributes nothing but those lines.
    own_traced_stderr = b"".join(
        line + b"\n"
        for line in traced_stderr.splitlines()
        if not re.match(rb"^dyld\[\d+\]:", line)
    )
    assert own_traced_stderr == stderr
    _assert_no_python_authority(traced)


def test_native_journeys_keep_their_closed_routes_and_bytes(
    contract_home: Path,
) -> None:
    """Sentinel: default help, parse conversion, and direct XML stay native."""
    alpha_path = (
        contract_home
        / ".claude/projects/alpha/11111111-1111-4111-8111-111111111111.jsonl"
    )
    for executable in BOTH_INSTALLED_LAUNCHERS:
        help_process = subprocess.run(
            [str(executable), "--help"],
            cwd=PROJECT_ROOT,
            env=_environment(contract_home),
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )
        assert help_process.returncode == 0
        assert help_process.stdout.startswith(b"usage: ch [-h]")
        assert help_process.stderr == b""

        conversion = subprocess.run(
            [str(executable), "parse"],
            cwd=PROJECT_ROOT,
            env=_environment(contract_home),
            input=b"[]",
            capture_output=True,
            check=False,
            timeout=120,
        )
        assert conversion.returncode == 0
        assert conversion.stdout == b""
        assert conversion.stderr == b""

        direct = subprocess.run(
            [str(executable), str(alpha_path), "-t:s"],
            cwd=PROJECT_ROOT,
            env=_environment(contract_home),
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )
        structured = subprocess.run(
            [str(executable), str(alpha_path), "-t:s", "-f", "json"],
            cwd=PROJECT_ROOT,
            env=_environment(contract_home),
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )
        rebuilt = subprocess.run(
            [str(executable), "parse"],
            cwd=PROJECT_ROOT,
            env=_environment(contract_home),
            input=structured.stdout,
            capture_output=True,
            check=False,
            timeout=120,
        )
        assert direct.returncode == structured.returncode == rebuilt.returncode == 0
        assert rebuilt.stdout == direct.stdout, (
            "Expected direct default XML to equal structured JSON through the "
            "native conversion authority byte for byte."
        )


def test_unscoped_commands_stay_on_the_python_legacy_route(
    contract_home: Path,
) -> None:
    """Tripwire: name/info keep their accepted legacy authority by design."""
    for executable in BOTH_INSTALLED_LAUNCHERS:
        completed = subprocess.run(
            [str(executable), "info", "--help"],
            cwd=PROJECT_ROOT,
            env=_environment(contract_home),
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )
        traced_environment = _environment(contract_home, loader_trace=True)
        traced = subprocess.run(
            [str(executable), "info", "--help"],
            cwd=PROJECT_ROOT,
            env=traced_environment,
            input=b"",
            capture_output=True,
            check=False,
            timeout=120,
        )
        loader_lines = _loader_lines(traced.stderr)

        assert completed.returncode == traced.returncode == 0
        assert completed.stdout == traced.stdout
        assert any(b"python" in line.lower() for line in loader_lines), (
            "Expected unscoped commands to remain on the Python legacy route "
            "by design after the search journey moves."
        )


def _record_hash(content: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
    return f"sha256={digest.decode()}"


def _record_rows(content: str) -> dict[str, tuple[str, str]]:
    import csv
    import io

    return {
        path: (hash_value, size)
        for path, hash_value, size in csv.reader(io.StringIO(content))
    }


def test_built_wheel_and_both_installs_own_identical_native_search_route(
    tmp_path: Path,
    contract_home: Path,
) -> None:
    completed = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        timeout=240,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert completed.returncode == 0 and len(wheels) == 1, (
        "Expected one built wheel for package-route proof. "
        f"Exit status: {completed.returncode}; wheels: {wheels!r}."
    )

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        public_scripts = [name for name in names if name.endswith(".data/scripts/ch")]
        entry_points_files = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        assert len(public_scripts) == 1
        script_bytes = wheel.read(public_scripts[0])
        assert script_bytes[:4] in MACH_O_MAGICS
        entry_points = configparser.ConfigParser()
        entry_points.read_string(wheel.read(entry_points_files[0]).decode())
        scripts = entry_points["console_scripts"]
        assert "ch" not in scripts and scripts.get("ch-legacy", "").startswith("chats.")

    for executable in BOTH_INSTALLED_LAUNCHERS:
        assert executable.resolve().read_bytes() == script_bytes, (
            "Expected built wheel and both installed public launchers to "
            f"contain identical route bytes. Mismatch: {executable}."
        )

    extracted = tmp_path / "standalone-wheel-ch"
    extracted.write_bytes(script_bytes)
    extracted.chmod(0o755)
    help_case = next(case for case in MANIFEST if case["id"] == "help-long")
    wheel_process = _run_case(
        extracted,
        help_case,
        contract_home,
        loader_trace=True,
    )
    expected_stdout = (FIXTURE_ROOT / str(help_case["expected_stdout"])).read_bytes()
    assert wheel_process.returncode == 0, (
        "Expected the standalone wheel asset to own search help without a "
        f"sibling legacy entry. Got: {wheel_process.returncode}; "
        f"{wheel_process.stderr[-1000:]!r}."
    )
    assert wheel_process.stdout == expected_stdout
    _assert_no_python_authority(wheel_process)
