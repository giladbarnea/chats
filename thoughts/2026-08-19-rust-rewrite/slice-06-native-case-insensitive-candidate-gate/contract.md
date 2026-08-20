---
date: 2026-08-20
title: Slice Six contract
---

# Slice Six contract

`_file_contains_ascii(Path, bytes, *, case_sensitive: bool, evidence_groups: tuple[tuple[bytes, ...], ...]) -> bool` stays the Python scanner interface. Search CLI arguments, results, ordering, output, and exit codes stay unchanged.

Rust remains the sole raw file scanner. Slice Six changes only default-visibility, unshortened, case-insensitive plain ASCII literal candidates. Case-sensitive scanning keeps the accepted Slice Five behavior.

The strict Python caller gate must preserve these rules:

1. Bypass native rejection when thinking, tools, agents, custom records, branches, plans, or any shortening mode is active.
2. Bypass native rejection when JSON decoding can create a query character absent from raw JSON text.
3. Keep the existing render-dependent and generated-marker bypasses.
4. Add raw `b"\\u"` as an unconditional OR evidence group for eligible terms. JSON Unicode escapes must reach semantic confirmation.
5. For every eligible Pi file, add raw `b'"pi-user-agents"'` as an unconditional OR evidence group. Default joined Pi agent records can generate visible text absent from raw values.
6. Preserve boolean prefilter behavior. Positive `AND` and `OR` terms use the gate independently. A `NOT` term never rejects a file.
7. Preserve evidence semantics. Every member of one group must occur, and any complete group passes the candidate.
8. Delete the decoded-content candidate gate. `SessionScan` and the existing rendered regex path become the sole semantic confirmation after the native path gate.

The case-insensitive native scanner must preserve these rules:

1. Continue ASCII needle matching with ASCII-only haystack lowering.
2. Validate UTF-8 incrementally across 1 MiB read boundaries.
3. Treat every safe valid non-ASCII scalar as an ASCII-match separator and continue scanning.
4. Defer on invalid or incomplete UTF-8.
5. Defer on the 20 Python 3.14 risk scalars. Nineteen have a casefold containing ASCII. U+0131 is the additional ASCII `i` equivalent under Python `re.IGNORECASE`.
6. The risk set is U+00DF, U+0130, U+0131, U+0149, U+017F, U+01F0, U+1E96, U+1E97, U+1E98, U+1E99, U+1E9A, U+1E9E, U+212A, and U+FB00 through U+FB06.
7. Preserve cross-chunk needle and evidence matches, empty-needle behavior, bounded memory, byte-preserving paths, read errors, and early needle success.

The native gate remains conservative. `True` means semantic confirmation is required. It does not mean the session matches.

Acceptance requires differential parity against the proved Python 3.14 reference across exhaustive Unicode classification, seeded chunk and semantic cases, the stable live pool, and public end-to-end searches. It also requires a stale-artifact-free native rebuild, the exact real launcher, and repeated unprimed and primed measurements for a no-hit and a real-hit query. A direct scanner benchmark cannot accept the slice.
