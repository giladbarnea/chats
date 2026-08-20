# Cycle 02 changed-system measured-cost profile

## Baseline

The required checkpoint is `b2ce1fd9dea41c033c7cb02321ea37b3764863d8` on `main`.

The profiler changed no production source or test. All harnesses and raw measurements stayed under `/tmp`.

The main real launcher was `/Users/giladbarnea/.local/bin/ch`. The checkout launcher was `.venv/bin/ch`.

Both launchers were package-owned arm64 Mach-O executables. Both had SHA-256 `00bbdb00d48523270c15db97f6c53b4d1e3b53c809cac068b9f6b96b981668bf`.

Measurements ran on an Apple M2 Pro with macOS 26.3.1. Each changed-system timing used the main real launcher after one unmeasured prime.

The accepted cycle 01 red launcher at `b203317` remained available under `/tmp`. Interleaved checks used it only to separate code changes from host timing drift.

## Findings

### Cycle 01 conversion performance holds

The native route still matches the accepted conversion bytes and performance.

| Real-launcher shape | Warm median | Runs | Accepted cycle 01 result |
| --- | ---: | ---: | ---: |
| `ch parse --help` | 6.9 ms | 7 | Not measured after green |
| Large JSON to XML | 13.5 ms | 7 | 13.3 ms |
| Large XML to JSON | 14.1 ms | 7 | 14.4 ms |

The JSON input was 552,693 bytes. The XML input was 327,099 bytes.

JSON-to-XML output matched SHA-256 `9ed12ce8c2d02ce05985d0a053f58fab17f1fc94027872bff427ed2f2f79d47f`.

XML-to-JSON output matched the isolated legacy launcher byte for byte. It contained 412,168 bytes with SHA-256 `b5435c7ef3bc385ea23f529ef434da9e35d43aca0493549ff2685f7266c7d823`.

An interleaved changed-versus-red run measured 14.6 ms versus 280.2 ms for JSON-to-XML. XML-to-JSON measured 16.5 ms versus 277.9 ms.

One native conversion used 13,860,864 bytes of maximum resident memory. Cycle 01 measured 61,227,008 bytes on the Python route.

A fresh loader trace contained no Python, `_native`, or ABI3 loader path. The global and checkout launchers produced identical conversion bytes.

### Default session work still pays the full legacy floor

Every default session shape enters the Rust launcher, replaces itself with `ch-legacy`, and then loads Python.

A real import trace attributed 259.6 ms cumulatively to `chats.cli`. A scratch exit hook observed 30 loaded project modules.

The current absolute timings were higher than cycle 01 because this host ran Python work more slowly during the remap.

An interleaved control removed that ambiguity. The changed launcher took 275.7 ms for the small direct path. The red launcher took 278.9 ms.

The new exec seam therefore caused no material default-session regression. It also gave this unfinished journey no performance gain.

| Real-launcher shape | Warm median | Runs |
| --- | ---: | ---: |
| Small direct path, plain XML | 276.4 ms | 7 |
| Medium direct path, plain XML | 295.7 ms | 7 |
| Medium direct path, last-message slice | 290.2 ms | 7 |
| Medium exact session ID, plain XML | 430.9 ms | 7 |
| Large direct path, plain XML | 347.1 ms | 7 |
| Large direct path, forced Rich without pager | 532.4 ms | 7 |
| Newest Pi recent index, ID only | 636.3 ms | 7 |

The last-message slice still costs the same as full output. The legacy path decodes and normalizes the full session before slicing.

A direct small command body took 16.3 ms after imports. Provider decoding took 4.0 ms, and plain XML projection took 0.3 ms.

The current Python floor therefore consumed about 94% of the small direct journey.

The exact-ID command body took 159.2 ms. Pool discovery consumed 127.8 ms of that body.

The recent-index ID body took 362.7 ms. Pool discovery consumed 113.2 ms, and 3,330 last-timestamp probes consumed 185.9 ms.

Forced Rich added 185.3 ms above the large plain path. One large plain run used 123,109,376 bytes of maximum resident memory.

The global and checkout launchers produced identical small-session bytes.

### Search remains the largest cost

The changed search snapshot contained 4,915 main session files and 6,462,465,063 bytes.

| Provider | Files | Bytes |
| --- | ---: | ---: |
| Claude | 379 | 372,695,497 |
| Pi | 3,330 | 3,752,083,222 |
| Codex | 1,206 | 2,337,686,344 |

The pool grew by eight Pi files and 20.4 MB after the cycle 01 snapshot.

| Real-launcher shape | Selected corpus | Warm median | Runs |
| --- | ---: | ---: | ---: |
| Narrow filtered literal miss | 14 files, 26.0 MB | 735 ms | 3 |
| Recent broad list | 22 files, 93.8 MB | 1.076 s | 3 |
| Broad filtered literal miss | 3,245 files, 5.655 GB | 3.691 s | 3 |
| Selective literal, three IDs | 3,245 files, 5.655 GB | 4.456 s | 3 |
| Broad filtered regex miss | 3,245 files, 5.655 GB | 23.934 s | 3 |

The selective literal printed its first ID after an 803 ms median. Completion still took 4.456 seconds.

The current narrow search took 750.7 ms in an interleaved run. The red launcher took 755.2 ms on the same live corpus.

The launcher change therefore caused no material search regression. It also gave this unfinished journey no performance gain.

One broad literal command body took 3.419 seconds after imports. Semantic confirmation consumed 2.212 seconds across 159 survivors.

`SessionScan` consumed 1.607 seconds inside that confirmation. The native batch candidate gate consumed 0.732 seconds.

A regex miss bypassed the literal gate. Semantic confirmation consumed 22.654 seconds across 3,244 selected files.

`SessionScan` consumed 17.153 seconds inside the regex confirmation. Discovery and date probes together consumed 0.522 seconds.

One broad literal miss used 651,018,240 bytes of maximum resident memory. It used 7.71 user CPU seconds over 4.16 wall seconds.

### The changed shared-core evidence orders default session before search

Search has the largest measured pain. Its 23.9-second regex tail remains the fleet's largest representative cost.

Default session parse remains the more-used journey in the accepted product evidence. It had 133 observed calls, compared with 62 search calls.

The native conversion model exists, but neither remaining journey uses it. Default parse and search still construct Python `Message` values and use Python rendering.

The largest search bucket is provider decoding, normalization, and rendered semantic confirmation inside `SessionScan`.

A complete native default-session route must build that same provider, model, and presentation core without search-specific behavior.

A complete native search route needs that core plus query semantics, candidate planning, result views, ordering, streaming, and exits.

A partial PyO3 search optimization could attack the largest cost sooner. It would keep Python on the public path and add another temporary authority.

The complete default-session journey is therefore the highest-impact coherent cycle 02 boundary. It removes the common Python floor and builds search's main prerequisite.

## Decisions

Choose the complete default `ch [SESSION] [SLICE...] ...` journey for cycle 02.

Do not choose only direct paths, exact IDs, plain XML, or one provider. Those slices would leave public default-session shapes under two authorities.

Do not choose another PyO3 semantic-search helper. It would improve a component without completing either remaining public journey.

Move existing Rust inventory, classification, timestamp, and resolution work into ordinary Rust modules. The native launcher must call those modules without Python bindings.

Use the cycle 01 Rust canonical model as the one session model. Extend it only for proven default-session behavior.

Keep search and unscoped subcommands on the private legacy route during cycle 02. Search becomes the next product boundary after this shared core lands.

Use these changed-system performance gates after exact parity:

1. Small direct plain output at most 60 ms.
2. Medium exact-ID plain output at most 150 ms.
3. Newest Pi recent-index ID output at most 250 ms.
4. Large forced-Rich output at most 350 ms.

These gates prove removal of the Python floor. They do not assume conversion-like speed for resolution or terminal rendering.

## Proof

The raw timing, component, snapshot, loader, memory, module, and calibration evidence lives under `/tmp/ch-cycle-02-*`.

The conversion timing used the same fixed large fixtures as cycle 01. Their input sizes and hashes remained unchanged.

Default timing reused the fixed small, medium, and large real Pi sessions. Their paths, sizes, and hashes were recorded by the harness.

Search timing used the new 4,915-file snapshot. Relative filters were counted at measurement time.

All timed commands returned their expected status with empty stderr. The selective search returned the same three IDs in the same order.

The isolated `b203317` launcher and the changed launcher ran interleaved. This controlled current host drift for unfinished route comparisons.

The real installed launchers produced identical conversion and default-session output bytes.

No tracked production source or test changed during profiling.

## Remaining risks

Absolute Python and search timings drifted upward during this remap. The same drift affected the isolated red launcher, so it is not a cycle 01 regression.

Future acceptance must use interleaved old-versus-new runs on one recorded corpus. Standalone comparison with cycle 01 wall times would be misleading.

The live corpus changed while the team worked. Recent-index identity and relative-filter counts will continue to move.

The Rust conversion model proves transport reuse, not complete provider-session coverage. Provider adapters and session-only fields still need exact tests.

Rich terminal parity remains a material default-session risk. It covers width, ANSI styling, Markdown, syntax, paging, and broken pipes.

Python regular expressions and Unicode behavior remain the largest later search risk. Cycle 02 must not change search truth while routing it through legacy Python.

## Exact next boundary

Build the complete default `ch [SESSION] [SLICE...] ...` journey in Rust through the installed native launcher.

Before production code, pin process-level behavior for all three providers and every public default-session input class.

Cover direct files, exact IDs, recent indices, title and summary resolution, stdin content, piped IDs, and failures.

Cover selector unions, visibility, agents, branches, plans, shortening, XML, JSON, raw, metadata-only, ID-only, file output, Rich, paging, errors, and exits.

Then implement only the complete default-session route:

1. Route every default-session command shape inside the Rust process.
2. Extract reusable inventory, path, timestamp, and resolution cores from the PyO3-only source.
3. Add the three provider adapters and agent merging around the shared Rust model.
4. Add visibility, slicing, shortening, metadata, and exact output projections.
5. Add terminal rendering and pager control with exact public behavior.
6. Keep search and unscoped subcommands on the unchanged private legacy route.

The completed default-session route must not start, import, embed, call, or fall back to Python. It must not call the PyO3 extension.

Run the fixed direct, exact-ID, recent-index, slice, large plain, and forced-Rich shapes through both installed launchers.

Require exact behavior parity, the four performance gates above, and direct process proof that Python never enters the route.
