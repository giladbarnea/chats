# Remove catalog and copied terminal input

The user removed both features from the product scope. Their command routes, parsers, exports, help, current documentation, dedicated tests, and assets were deleted together.

Catalog was the only runtime consumer of PyYAML. Its runtime dependency was removed. The dataset script declares its own PyYAML dependency, and pre-commit still requires it for development.

Session parsing, naming, and native search now validate JSONL directly. The shared JSONL boundary preserves provider detection and newline handling. Raw Markdown output remains supported. Prefix characters inside valid JSONL remain ordinary message text.

Historical sessions.yaml entries, changelog entries, work records, and immutable rendering recordings remain intact. They preserve user data and the independent test oracles.

The aggregate run exposed a separate terminal capture race. On macOS, closing the last PTY slave before capture discards queued output. A child can also write and exit between a read timeout and an exit check. Two real-process regressions reproduced these losses. The helper now holds its slave open and drains queued output after exit. All 243 terminal checks passed with the original expected bytes.

## Verification

1. The full runner passed: 1,970 Python tests, four performance tests, and all 13 shell suites. Three existing skips remain.
2. Both Rust feature modes passed: 291 library tests, one launcher test, and 54 doctests each.
3. Reinstalled from the canonical checkout and refreshed the project environment. Editable origin and imports point here; installed and local binary hashes match. Nine output checks agree across the local build, installed command, and project command. They cover help, search, JSONL exports, native conversion, rejected removed inputs, and retained raw Markdown output.
4. `gsd --check` passed.

The earlier baseline repairs remain separate in [the test failure report](../2026-09-27-test-failures/post-implementation.md).
