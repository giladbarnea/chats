---
date: 2026-08-20
status: ready-for-review
baseline: ce79be1
scope: 1
---

# Search performance Scope 1 outcome

## Result

Scope 1 preserves the exact three IDs and newest-first order. The exact piped command now shows its first ID in about 0.38 seconds and finishes in about 7.15 seconds.

This is a material improvement from the accepted 16.05 to 16.65-second baseline. It does not reach the full plan’s 3-second completion goal because main excluded multi-file batching from Scope 1.

## Implemented scope

Search now flushes each streamed `-ll` ID at one shared output boundary. The normal search path and the dot projection use that boundary. Output bytes, ID order, and exit behavior stay unchanged.

One default, unshortened, case-insensitive ASCII literal can now use a single-file native logical JSON-string gate. Rust recognizes raw characters, short escaped slash, and mixed `\uXXXX` forms without building JSON objects. It validates JSON escapes, UTF-8, surrogate pairs, and Python 3.14 case-insensitive risk scalars conservatively. Joined-Pi evidence uses the same logical escape matching, so an escaped `pi-user-agents` marker still reaches semantic confirmation.

Every survivor still enters the unchanged Python `SessionScan` path. Regex, boolean, non-ASCII, case-sensitive, shortened, control-character, and non-default visibility searches keep their prior path. The control boundary covers every character from U+0000 through U+001F.

Scope 1 adds no multi-file call, window, parallel scan, cache, index, parser rewrite, or date-probe change.

## Behavior proof

Tests cover per-ID flushing through normal search and dot projection. Native boundary tests cover raw `/`, `\/`, `\u002F`, mixed escaped query characters, native read boundaries, valid and invalid surrogates, malformed escapes, invalid UTF-8, Unicode risks, read errors, and JSON string boundaries.

End-to-end parity tests compare optimized IDs with forced full semantic scans across providers. They prove that hidden-only raw candidates do not become hits and that an escaped joined-Pi marker preserves generated `Bash` content. A complete U+0000 through U+001F matrix proves that every control-character query bypasses both native gates. A public-path regression proves that native read uncertainty keeps Python `Path.read_text` error text, stdout, and exit status unchanged.

The final full runner passed 1,100 Python unit tests with 3 skips, all four performance tests, and every shell suite. Cargo test and release check also passed.

## Exact launcher measurements

The installed editable `ch` launcher used Python 3.14 and the source-built ABI3 module. Measurements used the live corpus and a warm filesystem cache after one unmeasured priming run.

The final measured snapshot contained 4,897 pool files. The `-ca 2m` filter selected 3,234 files and 5,605,967,285 bytes. The native gate retained 244 files and 558,724,416 bytes for semantic confirmation.

The immediate full semantic reference was:

```sh
ch search 'CLIENT_ID[/]CARD' -ca 2m -ll | cat
```

It completed in 15.504 seconds. It returned these IDs:

```text
01a0161d-7a2f-7254-8adf-9289ea48805f
bac1d6c8-0bc4-4b62-8891-77f9f3b01fb3
019f7f45-ff38-7312-852b-351902ef5454
```

The exact command returned the same bytes and order in all three runs:

| Run | First ID | Completion |
| --- | ---: | ---: |
| 1 | 0.381 s | 7.145 s |
| 2 | 0.376 s | 7.125 s |
| 3 | 0.380 s | 7.154 s |
| **Median** | **0.380 s** | **7.145 s** |

The measured no-hit control enabled shell `pipefail` explicitly:

```sh
/bin/zsh -o pipefail -c "ch search 'PROFILEPROBEQZXWCV' -ca 2m -ll | cat"
```

It completed in 7.04 seconds with empty stdout and status 1. Direct `ch search 'PROFILEPROBEQZXWCV' -ca 2m -ll` also returns 1. The same `| cat` pipeline without `pipefail` returns 0 because `cat` supplies the pipeline status.

## Continuation baseline

Scope 1 removes the semantic amplification from unrelated `\u` evidence. Completion now spends most of its time making 3,234 serial native file calls over 5.606 GB.

Scope 2 should batch this same gate across fixed newest-first windows. It should keep sequential `SessionScan` confirmation and the new flushed output boundary. No parser or date-probe work is justified before measuring that batch boundary.
