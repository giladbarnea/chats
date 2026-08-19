---
date: 2026-08-19
title: Slice two contract
---

# Slice two contract

`get_jsonl_last_timestamp(Path) -> datetime | None` stays the Python interface. It returns the last in-band timestamp as a naive local datetime. If the raw timestamp is absent or invalid, it returns filesystem `st_mtime`. `get_jsonl_timestamps()` keeps returning the same first-and-last tuple.

Rust owns only the raw backward scan. It receives a file path and returns the last raw timestamp string or no value.

The raw scanner must:

1. Read physical lines from newest to oldest in bounded chunks.
2. Handle a line larger than one chunk in linear time.
3. Ignore blank lines, malformed JSON, invalid UTF-8, and objects without a timestamp.
4. Read only top-level `timestamp` and `created_at` values.
5. Apply Python JSON truthiness to `timestamp or created_at`.
6. Give a truthy `timestamp` precedence over `created_at`, even when it is not a string.
7. Return the first selected non-empty string without validating its ISO format.
8. Abort the raw scan on a valid top-level JSON value that is not an object.
9. Preserve Python `json.loads` behavior, including non-finite values, escaped lone surrogates, and the active integer-string digit limit.
10. Return no value on file or scan errors.

Rust owns backward file I/O and linear line assembly. Python keeps JSON line semantics, ISO parsing, UTC or offset conversion to naive local time, and filesystem fallback. The first-timestamp scanner stays Python.

Malformed tail lines must not hide an older timestamp. A newest non-empty but invalid timestamp must hide older timestamps. The Python wrapper then falls back to file mtime. Empty and false `timestamp` values may select `created_at`. A truthy non-string `timestamp` blocks same-entry `created_at`, then the scan continues to an older line.

Acceptance requires exact Rust-versus-Python results on every unchanged live file and on a synthetic edge matrix. It also requires repeated cold and warm end-to-end command measurements. A raw scanner benchmark cannot accept the slice.

All CLI arguments, output, filtering, sorting, metadata, and provider behavior stay unchanged. The production Python backward scanner must be absent after the slice.
