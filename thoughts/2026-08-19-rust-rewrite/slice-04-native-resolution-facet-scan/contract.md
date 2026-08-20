---
date: 2026-08-20
title: Slice Four contract
---

# Slice Four contract

`extract_resolution_facets_from_jsonl(Path) -> tuple[str | None, list[str]]` stays the Python interface. It returns the latest valid current title and every valid summary in file order.

Rust owns buffered forward file reads, physical-line framing, UTF-8 validation, the raw facet-marker gate, and result accumulation. A Python line callback keeps `json.loads` and provider title extraction authoritative.

The scan must preserve these rules:

1. Scan physical lines from start to end. Do not stop after finding a title or summary.
2. Preserve Python text-mode universal newline behavior for LF, CRLF, and lone CR separators.
3. Validate UTF-8 before rejecting a line through the raw marker gate.
4. Ignore blank lines and lines whose stripped text does not start with `{`.
5. JSON-parse only lines containing `"summary"`, `"custom-title"`, `"session_info"`, or `"thread_name_updated"`.
6. Ignore malformed JSON and valid top-level JSON values that are not objects.
7. Preserve Python `json.loads` behavior, including non-finite values, lone surrogates, and the active integer-string digit limit.
8. Collect a summary only when `type == "summary"` and `summary` is a non-empty string. Preserve its text without stripping.
9. Extract titles through the shared provider rules for Claude `custom-title`, Pi `session_info`, and Codex `thread_name_updated` records.
10. Strip a title string and accept it only when the stripped result is non-empty.
11. Let each later valid title replace the prior title. A blank or invalid later title does not clear it.
12. Preserve ordered duplicate summaries.
13. Return `(None, [])` for open and read errors, discarding partial results.
14. Propagate invalid UTF-8 and non-JSON callback errors as the Python implementation does.
15. Handle a missing final newline, marker and newline chunk boundaries, and a physical line larger than one chunk in linear time.
16. Keep memory bounded by one physical line, one fixed read chunk, and the accumulated facet results.
17. Preserve filesystem paths with surrogate-escaped bytes.

The raw marker gate is an optimization only. Marker-like text in an unrelated object must not create a facet, and a marker line must still use the complete Python semantic callback.

Rust becomes the only production forward file loop for this behavior. The replaced Python loop and any production fallback must be absent.

Resolution keeps its current path and exact-identifier fast paths. Title substring matching still takes precedence over summary prefix matching. Ambiguity results, miss fallback, CLI arguments, output, and provider behavior stay unchanged.

Acceptance requires exact Rust-versus-Python results on every stable live file and on a synthetic edge matrix. It also requires a stale-artifact-free rebuild, the exact real launcher, and repeated quiet unprimed and primed end-to-end measurements. A direct scanner benchmark cannot accept the slice.
