# Test failures, 2026-09-27

The baseline had 57 Python failures and two Rust failures. Serial checks also exposed two timing controls that passed under parallel test load.

The 53 frozen rendering failures came from session ages changing with the real date. Longer age labels changed column allocation before normalization. The shared test helpers now use the recording date. The seven age cases derive their timestamps from that same date. All 720 related cases passed with an external clock set to 2035, without changing their expected output.

Four help checks failed because the reviewed fixture missed the committed Shortening guidance. The correction updates that fixture. The earlier [help audit](../2026-09-27-ch-help/post-implementation.md) supplied the context.

The Rust checks still invoked Python search after that command had been removed. They now use the original grammar recording and its [provenance](../../tests/data/search-grammar/grammar-oracle.provenance.json), copied byte-for-byte. This keeps the expected behavior independent of the current Rust parser. Deliberate error-text and wrapping changes each failed the intended check before restoration.

The timing checks mixed first-launch overhead with scan time. The copied launcher initially took 325–475 ms, then 10–14 ms. A help invocation now warms it before measurement. Larger synthetic corpora restore measurable full-scan controls. The original timing thresholds and ratios remain unchanged. Three serial repeats passed both controls and ratios.

## Verification

1. The full runner passed: 1,976 Python tests, four performance tests, and all 13 shell suites. Three existing skips remain.
2. Both Rust feature modes passed: 299 library tests, one launcher test, and 56 doctests each.
3. Reinstalled from `/Users/giladbarnea/dev/chats`. The installed editable origin and Python source path point to this checkout. Binary hashes match. Help, search help, colored search, session parsing, JSON output, and native conversion match the local build byte-for-byte.
