---
updated: 2026-07-12
related_files:
  - src/chats/parsing.py
  - pyproject.toml
  - uv.lock
---

# Accelerate the central JSONL decoder with orjson

The change deliberately targets only `_iter_jsonl_entries`, the shared full-content decode boundary used by parse and `SessionScan`. Keeping the standard library for serialization and lightweight metadata probes avoids output compatibility work where the benchmark showed little benefit.

This scope follows the real-session benchmark rather than library microbenchmarks alone. Across a 358 MB sample, decoding improved by 36%, full session scanning by 25%, and a broad end-to-end search by 14%. Prefiltered searches remain largely unaffected because they already avoid decoding rejected files.

`orjson.JSONDecodeError` is handled at the same boundary as before, preserving the policy that malformed JSONL records are skipped. The existing behavioral suite passed without test changes: 578 tests passed and 3 were skipped.

The repository's shell baseline still has the pre-existing golden XML mismatch found before this implementation: `tests/data/golden_xml_output.txt` expects date-only message attributes while current output includes the recently added time. It was left untouched because it is unrelated to decoding.
