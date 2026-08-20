---
date: 2026-08-20
status: accepted
baseline: 06c8471
scope: 2
---

# Search performance Scope 2 outcome

## Result

Scope 2 replaces 3,235 serial native candidate calls with fixed 256-file newest-first windows. Independent exact-launcher acceptance preserved the three reference IDs and order. Median piped first ID was 0.438 seconds, and median completion was 2.996 seconds.

The immediate full semantic reference completed in 15.470 seconds. Scope 2 was 5.16 times faster. The slowest optimized completion was 3.008 seconds.

## Implementation

The eligible gate remains the default, unshortened, case-insensitive ASCII literal gate from Scope 1. Date and directory checks run before a path enters a window. Each window makes one native call with aligned per-path Pi evidence.

Rayon scans candidate files concurrently and returns decisions in input order. Native read uncertainty stays a survivor. Python confirms survivors sequentially through the unchanged `read_text`, `SessionScan`, semantic match, and metadata path before it starts the next window.

A path-filter error first drains the preceding window. This keeps errors in the unchanged serial order. Every ineligible query and visibility shape keeps the Scope 1 path.

Scope 2 adds no adaptive scheduling, reorder buffer, cache, index, parser rewrite, semantic parallelism, runtime `rg`, date-probe change, or broader query support.

## Fixed boundary

Process-parallel live-corpus probes measured 128, 256, and 512-file windows at 1.422, 1.188, and 1.182 seconds. Their first barriers were 0.402, 0.462, and 0.669 seconds. The 256-file window is the measured knee. The 512-file window saved 0.006 seconds but added 0.207 seconds to the first barrier.

A fixed 128 KiB native read buffer produced the best measured completion. Trials at 64 KiB, 256 KiB, and 1 MiB were slower.

## Behavior and regression proof

The focused search suite passed 150 tests. It proves ordered native decisions, exact per-path Pi evidence, fixed newest-first windows, sequential semantic confirmation, output flushing, and cross-provider semantic parity.

Independent review found one ordered-error defect. A later directory-filter decode error passed an earlier semantic read error. The public optimized-versus-semantic regression failed first, then passed after the window barrier fix.

The full runner passed 1,104 Python tests with 3 skips, all 4 performance tests, and all 13 shell suites. Cargo passed 4 unit tests, the all-target all-feature check, and the release build.

Fresh `cp314-abi3` wheel and source packages built. Fresh isolated Python 3.14 installs from both packages passed the native import and export, site-package origin, catalog asset, installed `ch --help`, and Pi fixture parse.

## Clean native build and exact launcher

Independent acceptance removed the source native module and every target native artifact. `cargo clean` removed 379 files and 115.8 MiB. No native binary remained before `uv sync --dev --reinstall-package chats` rebuilt the project.

The rebuild created exactly one `src/chats/_native.abi3.so` and no interpreter-tagged source module. The artifact is 2,569,856 bytes. Its SHA-256 is `3cdb85fe2acec4e6cc5e728bbe630c677aa41116333cd813268910eeb4b39499`.

Project Python and the uv-tool Python are Python 3.14.7. Both import this checkout and the same rebuilt artifact. The artifact exports `files_contain_ascii_json_strings`.

The exact launcher remains `~/.local/bin/ch`, linked to the editable tool environment that the user established with `uv tool install -e .`. Its metadata still marks this checkout as editable. Acceptance did not change global tool state. The launcher passed `--help` and a Pi fixture parse.

## Accepted exact-launcher measurements

Measurements used the exact launcher through `| cat` with shell `pipefail`. One unmeasured priming run preceded the timed runs. The filesystem cache was warm.

An independent post-timing inventory contained 4,901 pool files. The `-ca 2m` filter selected 3,235 files and 5,610,265,748 bytes across 13 windows. The native gate retained 248 files.

The immediate full semantic reference was:

```sh
ch search 'CLIENT_ID[/]CARD' -ca 2m -ll | cat
```

It completed in 15.470 seconds. The exact command returned identical stdout bytes, empty stderr, status 0, and these newest-first IDs in every run:

```text
01a0161d-7a2f-7254-8adf-9289ea48805f
bac1d6c8-0bc4-4b62-8891-77f9f3b01fb3
019f7f45-ff38-7312-852b-351902ef5454
```

| Run | First ID | Completion |
| --- | ---: | ---: |
| 1 | 0.434 s | 2.990 s |
| 2 | 0.454 s | 3.008 s |
| 3 | 0.438 s | 2.996 s |
| **Median** | **0.438 s** | **2.996 s** |

The median first ID is below 1.0 second. The median completion is below 3.0 seconds. No completion exceeds 4.0 seconds. The median completion is 5.16 times faster than the immediate semantic reference.

The no-hit semantic reference was `PROFILEPROBEQZXWC[V]`. It completed in 15.686 seconds with status 1 and empty stdout and stderr. The accepted `PROFILEPROBEQZXWCV` control completed in 2.644, 2.610, and 2.621 seconds. Its median was 2.621 seconds. All three runs kept status 1 and empty stdout and stderr.

## Continuation baseline

The independently accepted tree contains only the Scope 2 implementation, tests, dependency lock changes, and this outcome. It is ready for one clean Scope 2 commit on top of `06c8471`. No later search scope has started.
