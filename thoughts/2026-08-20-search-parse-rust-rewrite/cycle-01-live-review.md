# Cycle 01 live review

## Baseline

The review baseline is the accepted fleet map at `67cacb1`.

The reviewed red contract is checkpoint `b203317`. It changed only tests, test data, the benchmark, and the contract result.

The review covered every fleet change after `67cacb16f23a757d87b43bf865769be933747816`.

## Findings

The red contract first lacked package ownership proof. It also kept one Python conversion decoder under test.

The contract owner fixed both gaps before checkpoint. The wheel and installed RECORD files became part of acceptance.

The first green implementation passed the stored corpus but missed public behavior outside it. Review found these classes:

1. Valid integers, floats, Python value text, and ISO timestamps differed.
2. JSON, UTF-8, and argument errors differed.
3. TTY error color, Rich wrapping, and broken-pipe behavior differed.
4. Unicode timestamps could panic the Rust process.
5. The architecture document still described the deleted Python conversion route.
6. Overflow numbers converted to XML but could not complete the XML-to-JSON composition.

The implementer fixed every finding without changing the checkpointed contract.

## Decisions

The completed `ch parse` route has one Rust authority.

The package owns the public native `ch` executable. It also owns a private `ch-legacy` Python entry and the existing PyO3 extension.

Only first-argument `parse` stays in Rust. Every uncompleted journey replaces the launcher process with `ch-legacy`.

The reusable Rust model and codecs preserve the accepted Python-visible behavior. This includes numeric limits, ISO timestamps, error bytes, TTY color, and pipe failure output.

The obsolete Python conversion handler and both Python input decoders left production.

## Proof

The focused behavior, package, launcher, and authority suite passes `60` tests.

All 15 JSON fixtures match their XML byte oracles. All 15 XML fixtures match their JSON byte oracles.

The installed legacy differential matches every reviewed case byte for byte. It also matches both complete positive and negative Infinity compositions.

The final full run passed 1,124 non-performance tests with 3 skips. It also passed 4 search performance tests and all 13 shell suites.

Cargo passed 4 unit tests and 1 doctest.

Both `.venv/bin/ch` and `~/.local/bin/ch` are package-owned arm64 Mach-O executables.

Fresh conversion loader traces used one process. They loaded no Python executable, Python library, `_native`, or ABI3 extension.

The accepted large-fixture medians are 13.3 ms for JSON-to-XML and 14.4 ms for XML-to-JSON.

Both results are below the 60 ms limit. They are more than ten times faster than the accepted Python baseline.

## Remaining risks

Default session parse and search still start Python by design. The private legacy route still loads PyO3 for their current native helpers.

The widened differential harness is scratch evidence under `/tmp`. Its cases are recorded in the implementation and integrated cycle results.

## Exact next boundary

Remap conversion, default session parse, and search on the changed installed product.

Use that map to compare the most-used session journey with the highest-cost search journey. Do not select cycle 02 before the remap.
