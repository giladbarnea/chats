---
date: 2026-08-20
title: Slice Five contract
---

# Slice Five contract

`_file_contains_ascii(Path, bytes, *, case_sensitive: bool, evidence_groups: tuple[tuple[bytes, ...], ...]) -> bool` stays the Python interface used by search orchestration. CLI arguments, results, ordering, output, and exit codes stay unchanged.

Rust owns the raw candidate file scan. The scan must preserve these rules:

1. An empty needle returns `True` without opening the path.
2. A needle match may cross a read-chunk boundary.
3. Evidence bytes match exactly and case-sensitively in both modes, including across chunk boundaries.
4. Production evidence groups contain only non-empty ASCII members. One group passes only when every member appears somewhere in the file. Any complete group passes the candidate.
5. A needle match returns `True` immediately. Evidence-only success is decided after the scan.
6. Case-sensitive search compares the ASCII needle exactly.
7. Valid UTF-8 non-ASCII text does not force case-sensitive search to defer. Rust continues the exact byte scan.
8. Invalid or incomplete UTF-8 makes the case-sensitive gate return `True`. The existing decoded confirmation path then preserves its error behavior.
9. Case-insensitive search keeps the current conservative rule. Any non-ASCII byte returns `True` because Unicode case folding can create an ASCII match.
10. ASCII-only case-insensitive search lowercases only the haystack bytes. The caller supplies the already-normalized ASCII needle.
11. Open and read errors propagate as `OSError` rather than becoming a match or miss.
12. Paths with surrogate-escaped filesystem bytes remain representable.
13. Reads use the current 1 MiB chunk size. Memory stays bounded by one chunk, the maximum candidate overlap, the evidence match state, and at most one incomplete UTF-8 code point.

The raw scan remains only a conservative candidate optimization. A `True` result still enters the existing decoded-content and rendered-message confirmation path. Query parsing, boolean evaluation, generated-marker bypasses, Pi normalization evidence construction, semantic matching, and display stay Python-owned.

Rust becomes the only production file loop for this behavior. The replaced Python loop, its Python scan constant, and any production fallback must be absent.

Acceptance requires parity against a transient refined Python reference for the intended candidate contract. It must not use the old conservative gate as the direct oracle. End-to-end semantic results must also match on stable live files. The synthetic matrix must cover both case modes, valid and invalid UTF-8, split multibyte code points, needle and evidence boundaries, complete and incomplete evidence groups, empty needles, file errors, and surrogate-escaped paths.

Acceptance also requires a stale-artifact-free native rebuild, the exact real launcher, and repeated unprimed and primed end-to-end measurements for no-hit and real-hit searches. A direct scanner benchmark cannot accept the slice.
