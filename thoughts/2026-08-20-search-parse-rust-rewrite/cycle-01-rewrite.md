# Cycle 01 native conversion rewrite

## Baseline

The accepted map baseline is `67cacb1`. The production source beneath that map is `95f1891`.

The reviewed red contract is checkpoint `b203317`.

Before this cycle, both installed `ch` launchers started Python. Large conversion medians were 184.6 ms and 181.6 ms.

The accepted inputs are:

- [Cycle 01 contract](cycle-01-contract.md)
- [Cycle 01 implementation](cycle-01-implementation.md)
- [Cycle 01 live review](cycle-01-live-review.md)

## Findings

Maturin did not put the mixed-package Rust executable in its wheel.

`setuptools-rust` puts the executable and PyO3 extension in one wheel. It also keeps a private Python entry for unfinished routes.

The stored 15-pair corpus covered the main conversion data. Independent review found additional public parity surfaces.

Those surfaces included Python numeric limits, ISO timestamps, malformed input, UTF-8, argument order, terminal errors, and broken pipes.

The native implementation now covers those surfaces. It also preserves both complete Infinity round trips produced by valid exponent overflow.

## Decisions

The wheel owns one public Rust `ch` executable.

Exact `ch parse [FILE] [-f xml|json]` starts and finishes in that Rust process.

The route does not start, embed, import, call, or fall back to Python. It does not load the PyO3 extension.

One reusable Rust `Message` and `Tool` model owns conversion. Rust codecs own strict JSON, canonical XML, tool schemas, transport escaping, and projections.

The Python conversion handler and Python input decoders were removed.

Default session parse, search, and unscoped commands remain unchanged. The Rust launcher replaces itself with the package-owned `ch-legacy` entry for those shapes.

The package change from Maturin to `setuptools-rust` is accepted. Wheel and installed RECORD proof make the executable a package asset, not a copied build artifact.

## Proof

The contract stores exact legacy XML-to-JSON stdout for all 15 XML fixtures. The existing 15 JSON-to-XML byte oracles remain authoritative.

The focused behavior, package, launcher, and authority suite passes `60` tests.

The public route covers file and stdin input in both directions. It pins help, argument order, errors, empty cases, stderr, exits, and final newlines.

The independent differential matches legacy bytes across the widened valid-input and failure matrix.

It covers 4,300 and 4,301 digit boundaries, finite and overflow exponents, broad Python 3.14 ISO forms, and Unicode timestamp safety.

It also covers BOM errors, multibyte UTF-8 failures, Rich hard wrapping, red TTY errors, argument parsing, and broken pipes.

Both `1e309 → Infinity XML → JSON` and `-1e309 → -Infinity XML → JSON` match legacy bytes through the complete composition.

The final full run passed 1,124 non-performance tests with 3 skips. It passed 4 search performance tests and all 13 shell suites.

Cargo passed 4 unit tests and 1 doctest.

The built wheel owns these assets:

1. The native `.data/scripts/ch` executable.
2. The `chats._native` ABI3 extension.
3. The private `ch-legacy` console entry.

Both `.venv/bin/ch` and `~/.local/bin/ch` are package-owned arm64 Mach-O executables.

Fresh conversion traces show one process identifier. They contain no Python, `_native`, or ABI3 loader path.

The accepted large-fixture medians are 13.3 ms for JSON-to-XML and 14.4 ms for XML-to-JSON.

The target was at most 60 ms in each direction. Both directions exceed the required threefold improvement.

## Remaining risks

Default session parse and search still use Python. Their current legacy processes still load the PyO3 extension.

The conversion boundary had no direct use in the original shell-history sample. The changed-system remap must test whether its Rust model creates the expected reuse.

The widened differential remains a scratch harness. Its exact case classes are preserved in the accepted implementation and review results.

## Crew convergence

The contract owner independently verified the final focused suite, package authority, benchmark, and widened differential.

The implementer reran the final full suite after all review fixes.

The reviewer verified every fleet change since `67cacb1`. All reported findings were fixed and rechecked.

All three owners accept this cycle.

## Exact next boundary

Remap conversion, default session parse, and search on the changed installed product.

Measure the new launcher, package, model reuse, and remaining Python authority.

Then compare the most-used default session journey with the highest-cost search journey. Select cycle 02 only from that changed-system evidence.
