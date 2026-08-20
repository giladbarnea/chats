from __future__ import annotations

import base64
import configparser
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
COMMAND_FIXTURE_ROOT = PROJECT_ROOT / "tests" / "data" / "parse-command-fixtures"
COMMAND_MANIFEST = json.loads(
    (COMMAND_FIXTURE_ROOT / "MANIFEST.json").read_text(encoding="utf-8")
)["cases"]
ROUND_TRIP_ROOT = PROJECT_ROOT / "tests" / "data" / "parse-round-trip-fixtures"
ROUND_TRIP_MANIFEST = json.loads(
    (ROUND_TRIP_ROOT / "MANIFEST.json").read_text(encoding="utf-8")
)["fixtures"]
REAL_INSTALLED_CH = Path.home() / ".local" / "bin" / "ch"
CHECKOUT_INSTALLED_CH = PROJECT_ROOT / ".venv" / "bin" / "ch"
MACH_O_MAGICS = {
    b"\xca\xfe\xba\xbe",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xbe\xba\xfe\xca",
}


def _case_id(case: dict[str, object]) -> str:
    return str(case["id"])


def _environment(*, home: Path | None = None, loader_trace: bool = False) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({"COLUMNS": "80", "NO_COLOR": "1", "TZ": "Asia/Jerusalem"})
    if home is not None:
        environment["HOME"] = str(home)
    if loader_trace:
        environment["DYLD_PRINT_LIBRARIES"] = "1"
    return environment


def _run_ch(
    executable: Path,
    arguments: list[str],
    *,
    input_bytes: bytes | None = None,
    home: Path | None = None,
    loader_trace: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable), *arguments],
        cwd=PROJECT_ROOT,
        env=_environment(home=home, loader_trace=loader_trace),
        input=input_bytes,
        capture_output=True,
        check=False,
    )


def _representative_round_trip_row() -> dict[str, object]:
    return next(
        row
        for row in ROUND_TRIP_MANIFEST
        if row["provider_adapter"] == "codex" and row["configuration"] == "with-tools"
    )


@pytest.mark.parametrize("case", COMMAND_MANIFEST, ids=_case_id)
def test_real_installed_parse_matches_accepted_legacy_command_bytes(
    case: dict[str, object],
) -> None:
    arguments = [str(argument) for argument in case["arguments"]]
    stdin_path = case.get("stdin")
    input_bytes = (
        (PROJECT_ROOT / str(stdin_path)).read_bytes() if stdin_path is not None else None
    )
    completed = _run_ch(REAL_INSTALLED_CH, arguments, input_bytes=input_bytes)
    expected_stdout = (PROJECT_ROOT / str(case["expected_stdout"])).read_bytes()
    expected_stderr = (PROJECT_ROOT / str(case["expected_stderr"])).read_bytes()

    assert completed.returncode == case["exit_status"], (
        f"Expected accepted exit status {case['exit_status']} for {case['id']}. "
        f"Got: {completed.returncode}."
    )
    assert completed.stdout == expected_stdout, (
        f"Expected accepted stdout bytes for {case['id']}. "
        f"Expected: {expected_stdout!r}; got: {completed.stdout!r}."
    )
    assert completed.stderr == expected_stderr, (
        f"Expected accepted stderr bytes for {case['id']}. "
        f"Expected: {expected_stderr!r}; got: {completed.stderr!r}."
    )


def test_real_installed_parse_accepts_file_and_stdin_in_both_argument_orders() -> None:
    row = _representative_round_trip_row()
    input_json_path = PROJECT_ROOT / str(row["input_json"])
    expected_xml_path = PROJECT_ROOT / str(row["expected_xml"])
    expected_json_path = PROJECT_ROOT / str(row["expected_json"])
    input_json = input_json_path.read_bytes()
    expected_xml = expected_xml_path.read_bytes()
    expected_json = expected_json_path.read_bytes()
    cases = [
        ("json-file-format-after", ["parse", str(input_json_path), "-f", "xml"], None, expected_xml),
        ("json-file-format-before", ["parse", "-f", "xml", str(input_json_path)], None, expected_xml),
        ("json-file-long-format", ["parse", "--format=xml", str(input_json_path)], None, expected_xml),
        ("json-stdin", ["parse"], input_json, expected_xml),
        ("xml-file-format-after", ["parse", str(expected_xml_path), "-f", "json"], None, expected_json),
        ("xml-file-format-before", ["parse", "-f", "json", str(expected_xml_path)], None, expected_json),
        ("xml-file-long-format", ["parse", "--format=json", str(expected_xml_path)], None, expected_json),
        ("xml-stdin", ["parse", "-f", "json"], expected_xml, expected_json),
    ]

    for case_id, arguments, input_bytes, expected_stdout in cases:
        completed = _run_ch(REAL_INSTALLED_CH, arguments, input_bytes=input_bytes)
        assert completed.returncode == 0, (
            f"Expected {case_id} conversion to succeed. "
            f"Exit status: {completed.returncode}; stderr: {completed.stderr[:500]!r}."
        )
        assert completed.stdout == expected_stdout, (
            f"Expected {case_id} conversion to match its legacy byte oracle. "
            f"Expected {len(expected_stdout)} bytes; got {len(completed.stdout)} bytes."
        )
        assert completed.stderr == b"", (
            f"Expected {case_id} success to keep stderr empty. "
            f"Got: {completed.stderr[:500]!r}."
        )
        assert completed.stdout.endswith(b"\n") and not completed.stdout.endswith(b"\n\n"), (
            f"Expected {case_id} non-empty stdout to have exactly one final newline. "
            f"Got tail: {completed.stdout[-20:]!r}."
        )


def _record_hash(content: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
    return f"sha256={digest.decode()}"


def _record_rows(content: str) -> dict[str, tuple[str, str]]:
    return {
        path: (hash_value, size)
        for path, hash_value, size in csv.reader(io.StringIO(content))
    }


def test_package_ownership_built_wheel_contains_all_runtime_assets(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert completed.returncode == 0 and len(wheels) == 1, (
        "Expected one built distribution for package ownership proof. "
        f"Exit status: {completed.returncode}; wheels: {wheels!r}; "
        f"stderr: {completed.stderr[-1000:]!r}."
    )

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        public_scripts = [name for name in names if name.endswith(".data/scripts/ch")]
        extensions = [name for name in names if name.endswith("chats/_native.abi3.so")]
        entry_points_files = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        record_files = [name for name in names if name.endswith(".dist-info/RECORD")]
        assert len(public_scripts) == 1, (
            "Expected the wheel to own one public native `ch` script. "
            f"Wheel scripts: {[name for name in names if '.data/scripts/' in name]!r}."
        )
        assert len(extensions) == 1, (
            "Expected the wheel to own the existing PyO3 extension. "
            f"Native package files: {[name for name in names if name.endswith('.so')]!r}."
        )
        assert len(entry_points_files) == 1 and len(record_files) == 1, (
            "Expected one entry-point declaration and one wheel RECORD. "
            f"Entry points: {entry_points_files!r}; RECORDs: {record_files!r}."
        )

        public_script = public_scripts[0]
        extension = extensions[0]
        entry_points_file = entry_points_files[0]
        public_script_bytes = wheel.read(public_script)
        extension_bytes = wheel.read(extension)
        assert public_script_bytes[:4] in MACH_O_MAGICS, (
            "Expected the wheel-owned public `ch` script to be a native Mach-O binary."
        )
        assert extension_bytes[:4] in MACH_O_MAGICS, (
            "Expected the wheel-owned PyO3 extension to be a native Mach-O library."
        )
        script_mode = wheel.getinfo(public_script).external_attr >> 16
        assert script_mode & 0o111, (
            f"Expected the wheel-owned public `ch` script to be executable. Mode: {script_mode:o}."
        )

        entry_points = configparser.ConfigParser()
        entry_points.read_string(wheel.read(entry_points_file).decode())
        console_scripts = entry_points["console_scripts"]
        assert "ch-legacy" in console_scripts and console_scripts["ch-legacy"].startswith(
            "chats."
        ), (
            "Expected the wheel to own the private Python `ch-legacy` entry. "
            f"Console scripts: {dict(console_scripts)!r}."
        )
        assert "ch" not in console_scripts, (
            "Expected the native wheel script, not a Python console entry, to own public `ch`. "
            f"Console scripts: {dict(console_scripts)!r}."
        )

        record_rows = _record_rows(wheel.read(record_files[0]).decode())
        for owned_path in (public_script, extension, entry_points_file):
            hash_value, size = record_rows.get(owned_path, ("", ""))
            assert hash_value.startswith("sha256=") and size == str(
                len(wheel.read(owned_path))
            ), (
                f"Expected the wheel RECORD to hash and size {owned_path}. "
                f"Got: {(hash_value, size)!r}."
            )


@pytest.mark.parametrize(
    "executable",
    [
        pytest.param(CHECKOUT_INSTALLED_CH, id="checkout-install"),
        pytest.param(REAL_INSTALLED_CH, id="real-uv-tool-install"),
    ],
)
def test_package_ownership_installed_record_hashes_public_and_private_launchers(
    executable: Path,
) -> None:
    resolved_executable = executable.resolve()
    environment_root = resolved_executable.parent.parent
    records = list(
        environment_root.glob("lib/python*/site-packages/chats-*.dist-info/RECORD")
    )
    assert len(records) == 1, (
        f"Expected one installed chats distribution RECORD under {environment_root}. "
        f"Got: {records!r}."
    )
    site_packages = records[0].parent.parent
    record_rows = _record_rows(records[0].read_text(encoding="utf-8"))
    owned_paths = {
        (site_packages / record_path).resolve(): values
        for record_path, values in record_rows.items()
    }
    private_legacy = environment_root / "bin" / "ch-legacy"

    for installed_path in (resolved_executable, private_legacy):
        assert installed_path.is_file() and os.access(installed_path, os.X_OK), (
            f"Expected the installed distribution to provide executable {installed_path}."
        )
        hash_value, size = owned_paths.get(installed_path.resolve(), ("", ""))
        content = installed_path.read_bytes()
        assert hash_value == _record_hash(content) and size == str(len(content)), (
            "Expected the installed RECORD to own the exact launcher bytes. "
            f"Path: {installed_path}; recorded: {(hash_value, size)!r}; "
            f"actual: {(_record_hash(content), str(len(content)))!r}."
        )

    assert resolved_executable.read_bytes()[:4] in MACH_O_MAGICS, (
        "Expected the RECORD-owned public launcher to be the native Mach-O binary. "
        f"Got: {resolved_executable}."
    )


@pytest.mark.parametrize(
    "executable",
    [
        pytest.param(CHECKOUT_INSTALLED_CH, id="checkout-install"),
        pytest.param(REAL_INSTALLED_CH, id="real-uv-tool-install"),
    ],
)
def test_installed_parse_is_one_native_process_with_no_python_authority(
    executable: Path,
) -> None:
    row = _representative_round_trip_row()
    input_json = (PROJECT_ROOT / str(row["input_json"])).read_bytes()
    expected_xml = (PROJECT_ROOT / str(row["expected_xml"])).read_bytes()
    expected_json = (PROJECT_ROOT / str(row["expected_json"])).read_bytes()
    directions = [
        ("json-to-xml", ["parse"], input_json, expected_xml),
        ("xml-to-json", ["parse", "-f", "json"], expected_xml, expected_json),
    ]

    assert executable.is_file() and os.access(executable, os.X_OK), (
        f"Expected an installed executable at {executable}."
    )
    resolved_executable = executable.resolve()
    for direction_name, arguments, input_bytes, expected_stdout in directions:
        completed = _run_ch(
            executable,
            arguments,
            input_bytes=input_bytes,
            loader_trace=True,
        )
        loader_trace = completed.stderr.lower()
        process_ids = set(
            re.findall(rb"^dyld\[(\d+)\]:", completed.stderr, re.MULTILINE)
        )

        assert completed.returncode == 0, (
            f"Expected traced {direction_name} through {executable} to succeed. "
            f"Exit status: {completed.returncode}; trace tail: {completed.stderr[-500:]!r}."
        )
        assert completed.stdout == expected_stdout, (
            f"Expected traced {direction_name} through {executable} to preserve stdout. "
            f"Expected {len(expected_stdout)} bytes; got {len(completed.stdout)} bytes."
        )
        assert process_ids and len(process_ids) == 1, (
            "Expected conversion to start and finish in one native process without a callback. "
            f"Observed loader process IDs: {sorted(process_ids)!r}."
        )
        assert b"python" not in loader_trace, (
            "Expected conversion to start no Python executable and load no embedded Python. "
            f"Python loader entries: {[line for line in completed.stderr.splitlines() if b'python' in line.lower()][:10]!r}."
        )
        assert b"_native" not in loader_trace and b"abi3" not in loader_trace, (
            "Expected completed conversion to bypass the legacy PyO3 extension authority. "
            f"Extension loader entries: {[line for line in completed.stderr.splitlines() if b'_native' in line.lower() or b'abi3' in line.lower()][:10]!r}."
        )

    assert resolved_executable.read_bytes()[:4] in MACH_O_MAGICS, (
        "Expected the public installed launcher to resolve to a native Mach-O executable. "
        f"Got: {resolved_executable}."
    )


def _controlled_legacy_session(home: Path) -> Path:
    session_directory = home / ".claude" / "projects" / "contract"
    session_directory.mkdir(parents=True)
    source = PROJECT_ROOT / "tests" / "data" / "a6f25fb8-e7a8-4411-b378-ad0f20e552d1.jsonl"
    destination = session_directory / source.name
    shutil.copyfile(source, destination)
    return destination


def test_uncompleted_public_journeys_keep_exact_legacy_behavior(tmp_path: Path) -> None:
    session_path = _controlled_legacy_session(tmp_path)
    cases = [
        (
            "default-session-parse",
            [str(session_path), "--color", "never", "--no-metadata"],
            "legacy-default-parse",
        ),
        (
            "search",
            ["search", "I.ll export the current", "--color", "never", "--no-metadata"],
            "legacy-search",
        ),
        (
            "legacy-name",
            ["name", "a6f25fb8-e7a8-4411-b378-ad0f20e552d1", "Contract Name", "-n"],
            "legacy-name",
        ),
    ]

    for case_id, arguments, expected_name in cases:
        expected_stdout = (
            COMMAND_FIXTURE_ROOT / "expected" / f"{expected_name}.stdout"
        ).read_bytes()
        expected_stderr = (
            COMMAND_FIXTURE_ROOT / "expected" / f"{expected_name}.stderr"
        ).read_bytes()
        completed = _run_ch(REAL_INSTALLED_CH, arguments, home=tmp_path)
        assert completed.returncode == 0, (
            f"Expected unchanged {case_id} route to succeed. "
            f"Exit status: {completed.returncode}; stderr: {completed.stderr[:500]!r}."
        )
        assert completed.stdout == expected_stdout, (
            f"Expected unchanged {case_id} stdout. "
            f"Expected: {expected_stdout!r}; got: {completed.stdout!r}."
        )
        assert completed.stderr == expected_stderr, (
            f"Expected unchanged {case_id} stderr. "
            f"Expected: {expected_stderr!r}; got: {completed.stderr!r}."
        )

        traced = _run_ch(
            REAL_INSTALLED_CH,
            arguments,
            home=tmp_path,
            loader_trace=True,
        )
        assert traced.returncode == 0 and traced.stdout == expected_stdout, (
            f"Expected traced {case_id} route to keep its behavior. "
            f"Exit status: {traced.returncode}; stdout: {traced.stdout[:500]!r}."
        )
        assert b"python" in traced.stderr.lower(), (
            f"Expected uncompleted {case_id} to remain on the private Python legacy route. "
            f"Loader trace tail: {traced.stderr[-500:]!r}."
        )
