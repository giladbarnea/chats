# Cycle 01 native conversion contract

## Baseline

The accepted contract baseline is `67cacb1`. It adds only the accepted cycle map to production baseline `95f1891`.

The real installed launcher is `/Users/giladbarnea/.local/bin/ch`. The checkout launcher is `.venv/bin/ch`.

Both launchers are Python scripts. The accepted large-fixture warm medians were 184.6 ms for JSON-to-XML and 181.6 ms for XML-to-JSON.

Production source stayed unchanged during this contract phase.

## Findings

The previous corpus pinned all 15 JSON-to-XML outputs. Its XML-to-JSON checks only proved self-stability.

The contract now stores exact legacy XML-to-JSON stdout for all 15 fixtures. These new byte oracles total 2,925,365 bytes.

A new command corpus pins help, invalid choices, missing format values, extra arguments, malformed JSON, schema rejection, malformed XML, invalid UTF-8, and missing files.

The command corpus also pins both valid empty cases through files and stdin. `[]` to XML emits no bytes. Empty XML to JSON emits `[]\n`.

A representative fixture pins file and stdin conversion in both directions. It also pins format options before and after the file.

Successful conversion tests require empty stderr. Each non-empty stdout must have exactly one final newline.

Darwin loader traces expose every executable and loaded dynamic library. One trace can reject a Python executable, embedded Python, the PyO3 extension, and a second process callback.

Default session parse, search, and `ch name --dry-run` use controlled fixtures. Their exact bytes stay pinned while loader traces require the private Python legacy route.

The wheel must contain a native public `ch`, the PyO3 extension, and a private Python `ch-legacy` entry. Its RECORD must hash all three assets.

Both installed distributions must record exact hashes and sizes for `ch` and `ch-legacy`. This rejects copied binaries outside package ownership.

The ambiguous tool-input regression now uses only public `ch parse` processes. No test imports the obsolete Python structured JSON decoder.

## Decisions

All public conversion checks invoke the real installed launcher. Package authority checks also invoke `.venv/bin/ch`.

Both installed launchers must resolve to native Mach-O executables. Their installed RECORD hashes must match those exact files.

The built wheel, not an external copy step, must own the native executable. The Python console entry owns only private `ch-legacy`.

Exact conversion must complete under one loader process identifier. Its trace must contain no `python`, `_native`, or `abi3` path.

The contract does not commit the real large performance fixture. The accepted profile kept that potentially private session under `/tmp`.

The performance harness instead pins its three sizes and SHA-256 hashes. It fails if the accepted fixture changes.

The harness pins `TZ=Asia/Jerusalem`, then primes each direction once. It runs seven interleaved conversions per direction and requires both medians at most 60 ms.

## Proof

Legacy parity passed before production work:

```text
uv run pytest tests/test_parse_round_trip.py
40 passed in 16.22s

uv run pytest tests/test_parse_command_contract.py -k 'not one_native_process and not package_ownership'
15 passed, 5 deselected in 6.04s
```

The authority contract is red only at the intended boundary:

```text
uv run pytest tests/test_parse_command_contract.py -k one_native_process
2 failed, 18 deselected
```

Both failures report Python loader entries for the checkout and real installed launchers. Their successful conversion bytes match before the authority assertion.

The package contract is red only at its missing ownership seam:

```text
uv run pytest tests/test_parse_command_contract.py -k package_ownership
3 failed, 17 deselected
```

The wheel lacks a native public script. Both installed distributions lack the private recorded `ch-legacy` entry.

The accepted performance contract is also red:

```text
uv run python tests/benchmark_parse.py
json-to-xml median: 225.6 ms
xml-to-json median: 223.2 ms
AssertionError: expected at most 60 ms
```

The harness verified exact output before recording each timing.

## Remaining risks

The exact failure text includes the accepted 80-column Rich wrapping. The Rust route must reproduce those bytes without keeping Rich or Python authority.

Darwin loader tracing is platform-specific. This product and accepted measurement machine are macOS on Apple silicon.

The full regression suite remains for final acceptance. This checkpoint proves the new conversion boundary before production changes.

## Exact next boundary

Install one wheel-owned Rust `ch` executable at both public launcher paths.

Route only exact `ch parse [FILE] [-f xml|json]` through reusable Rust model and codecs. Do not start, load, embed, call, or fall back to Python.

Route default session parse, search, and unscoped commands through the unchanged private Python entry.

Make the focused behavior, authority, package, and performance contracts green. Remove the obsolete Python conversion handler and decoders.

Then run the full regression suite and package proof.
