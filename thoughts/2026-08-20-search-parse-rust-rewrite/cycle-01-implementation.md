# Cycle 01 native conversion implementation

## Baseline

The reviewed red contract is `b203317`. Production started from accepted map commit `67cacb1`.

Both public launchers were Python scripts. Conversion used Python models and codecs, and large-fixture medians exceeded 180 ms.

## Findings

Maturin can build the Rust executable, but its mixed Python and Rust wheel omits that executable.

`setuptools-rust` can own the Rust executable and the existing PyO3 extension in one wheel. Optional PyO3 features keep Python outside the executable.

A line-by-line inner XML scan met parity but missed the performance target. One multiline Rust regex brought both conversion medians far below 60 ms.

Adversarial review found gaps beyond the stored corpus. They covered Python integer limits, exponent overflow composition, float and value text, broad ISO timestamps, Unicode panic safety, JSON and UTF-8 errors, argparse order, TTY color, Rich wrapping, and broken pipes.

## Decisions

The wheel now owns a native `ch` executable and a private `ch-legacy` Python entry.

Only first-argument `parse` routes to native Rust. Every other command replaces its process with the private legacy entry.

One reusable Rust `Message` and `Tool` model owns strict structured JSON, arbitrary integers, Python-compatible number and value text, canonical XML, tool schemas, transport escaping, and both projections.

A native JSON validator preserves the accepted Python error categories and positions. The launcher also preserves sequential argparse behavior, red TTY errors, and broken-pipe failure output.

The Python conversion router and both Python decoders left production. Uncompleted session parse, search, and legacy commands keep their prior Python authority.

## Proof

All 15 JSON inputs match their XML byte oracles. All 15 XML inputs match their accepted JSON byte oracles.

The focused command, round-trip, authority, and package suite passes with `60 passed`.

A scratch differential harness matches the isolated `b203317` Python command byte for byte across valid inputs, Python numeric limits, the ISO matrix, JSON and UTF-8 failures, CLI order, TTY color, Rich wrapping, and normalized broken pipes.

The harness also proves complete `1e309 → Infinity XML → JSON` and `-1e309 → -Infinity XML → JSON` compositions byte for byte.

The full suite passes with 1,124 non-performance tests, 3 skips, 4 search performance tests, and all 13 shell suites.

Cargo passes four unit tests. Both no-Python and PyO3 library builds pass.

The installed `.venv/bin/ch` and `~/.local/bin/ch` files are package-owned Mach-O executables. Their conversion loader traces contain no Python or PyO3 extension.

`ARCHITECTURE.md` now shows the native launcher, Rust model and codecs, wheel seam, and temporary private legacy route.

The final independent accepted-fixture run produced 13.3 ms JSON-to-XML and 14.4 ms XML-to-JSON warm medians. Both beat the 60 ms limit.

## Remaining risks

Default session parse and search still start Python by design. Their native boundaries require the mandated changed-system remap.

The source keeps PyO3 for those legacy journeys until later rewrite cycles remove their Python authority.

## Exact next boundary

Remap conversion, default session parse, and search on the changed installed product.

Then compare the most-used session journey with the highest-cost search journey before selecting cycle 02.
