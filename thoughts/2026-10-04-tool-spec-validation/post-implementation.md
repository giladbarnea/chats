---
date: 2026-10-04
---

# Tool-spec validation

`-t:i:200` silently selected a tool named `200`. Decimal integers now require
an explicit short assignment. Invalid inputs fail without changing the input.

[TOOL_SPEC.md](../../TOOL_SPEC.md) already defined unique slots and strict
separators. Both parsers now enforce that contract. The carrier colon in `-t:`
stays outside the spec grammar, so stricter separators preserve this carrier.

Validation happens before visibility overrides because those overrides could
discard malformed specs. Unknown nonnumeric names still match exactly.

Regression tests cover every partial slot order, slot reuse, forbidden grammar
transitions, all four carriers, both commands, and visibility overrides.
The focused suite passed 419 tests. Rust passed 292 library tests, one binary
test, and 54 doctests. The full suite passed 2,031 tests with three skips and
only the two baseline color failures. Installed/local parity and editable
checkout origin were verified after installation finished.
The frozen two-name search case now records the required syntax error, with its
revised contract named in the manifest. Its session corpus remains unchanged.
