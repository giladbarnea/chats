# Slices One and Two review findings

## 1. High: the package still targets Python 3.13 and later

The current requirement is Python 3.14 only. The shipped metadata still allows Python 3.13 and all later versions:

- `.python-version:1` selects 3.13.
- `pyproject.toml:9` declares `requires-python = ">=3.13"`.
- `Cargo.toml:14` selects `pyo3/abi3-py313`.
- `uv.lock:3`, `README.md:598`, `ARCHITECTURE.md:15`, and `CHANGELOG.md:19` repeat that support range.

This is functional packaging behavior, not stale wording alone. A fresh `uv build` produced `chats-0.1.0-cp313-abi3-...whl`, and the project test environment still selected Python 3.13. Make the package accept only the Python 3.14 minor series. Align the PyO3 ABI floor, the lock, the local interpreter selector, tests, and current documentation.

Keep the launcher fact precise during this change. The real global launcher worked after the user ran `uv tool install -e .`. Do not claim that `setup.sh` created that global editable installation.

## 2. Medium: Slice One records a contradicted launcher result

`slice-01-provider-path-classification/outcome.md:12` says normal setup made the global launcher work without a global tool reinstall. `slice-02-backward-timestamp-scanner/baseline.md:34` later marks the opposite as authoritative. The launcher worked only after the user ran `uv tool install -e .`.

Correct the Slice One outcome so future reviews do not restore the disproved setup claim. The current uv receipt confirms the user-established editable install. Slice Two already records this accurately.

## 3. Medium: the durable scanner tests omit several explicit parity rules

`slice-02-backward-timestamp-scanner/contract.md:14-27` makes `created_at`, Python truthiness, non-string precedence, invalid UTF-8, and chunk boundaries part of the accepted behavior. `tests/test_timestamp_scanner.py` does not retain cases for those rules. The reported 36-case acceptance matrix was transient, so later scanner changes can break accepted parity while the committed suite stays green.

Retain a small focused matrix that proves:

1. `created_at` is selected when `timestamp` is missing, empty, or false.
2. A truthy non-string `timestamp` blocks same-line `created_at`, then scanning continues.
3. An invalid UTF-8 tail line does not hide an older timestamp.
4. Newlines and timestamp lines at the 4,096-byte boundaries preserve newest-first scanning.

## Verification

The Rust implementations otherwise matched the reviewed contracts. I found zero mismatches in 9,000 Python 3.14 path-classification cases and 2,000 scanner cases under each Python version. Python 3.14 passed 963 tests with 3 skips. The Rust test, check, and release build passed. All 13 shell suites passed, including the existing real launcher. Wheel and source builds passed.

The accepted cold search budget remained the only full-run failure at 2,557 ms against 1,750 ms. This review does not treat it as a new finding.
