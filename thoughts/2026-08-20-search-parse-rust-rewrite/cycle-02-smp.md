# Cycle 02 scout, map, and profile result

## Baseline

The accepted changed-system baseline is `b2ce1fd9dea41c033c7cb02321ea37b3764863d8` on `main`.

Cycle 01 moved exact `ch parse [FILE] [-f xml|json]` conversion into the package-owned Rust executable. Default session parse and search remained on the private Python route.

The two installed public launchers are package-owned arm64 Mach-O executables with identical bytes.

No teammate changed production source or tests.

The accepted source views are:

- [Changed product journey scout](cycle-02-scout.md)
- [Changed production authority map](cycle-02-map.md)
- [Changed measured-cost profile](cycle-02-profile.md)

## Findings

### Product use still puts default session parse first

The same local shell history contains 195 direct in-scope calls. This remains directional evidence from one user, not telemetry.

| Journey | Calls | Dominant shape |
| --- | ---: | --- |
| Default session parse | 133 | Exact ID with default rendering, often with visibility flags or slices |
| Search | 62 | Filtered, case-insensitive matches output |
| Conversion | 0 | No direct call appeared |

A corrected count has 102 exact-ID calls and 21 recent-index calls. Cycle 01 had classified two exact-ID calls with `-2` message slices as recent-index calls.

Search still has 51 matches-mode calls. Fifty-four search calls use at least one pool filter.

### Conversion stays complete, native, and fast

Exact `ch parse` still starts and finishes in one Rust process. It loads no Python or PyO3 extension.

Rust owns its argument grammar, input, UTF-8 handling, canonical messages and tools, strict JSON, canonical XML, errors, output bytes, and exits.

Large conversion medians remain 13.5 ms for JSON-to-XML and 14.1 ms for XML-to-JSON. Cycle 01 accepted 13.3 ms and 14.4 ms.

The fixed conversion outputs keep exact byte parity. The route used 13.9 MB maximum resident memory in the changed profile.

### Default session parse and search remain unchanged Python journeys

Every default session and search shape enters the Rust launcher. The launcher then replaces itself with package-owned `ch-legacy`.

Both routes load CPython, `orjson`, Rich, and `chats._native`. Eager package imports also load unrelated commands and NLTK.

An observed `chats.cli` import loaded 30 project modules and 633 total modules. Its cumulative trace took 259.6 ms during this remap.

Interleaved runs against the accepted red launcher showed no material regression. They also showed no performance gain for either unfinished journey.

| Default session shape | Changed warm median |
| --- | ---: |
| Small direct plain XML | 276.4 ms |
| Medium direct plain XML | 295.7 ms |
| Medium last-message slice | 290.2 ms |
| Medium exact ID plain XML | 430.9 ms |
| Large direct plain XML | 347.1 ms |
| Large forced Rich without pager | 532.4 ms |
| Newest Pi recent index, ID only | 636.3 ms |

The last-message slice still costs the same as full output. Python decodes and normalizes the complete session before slicing.

The Python floor consumed about 94% of the small direct journey. Pool discovery consumed 127.8 ms of the exact-ID body.

Recent-index resolution probed 3,330 last timestamps. Those probes consumed 185.9 ms.

### Search remains the largest measured pain

The changed snapshot contains 4,915 main session files and 6.462 GB.

| Search shape | Selected corpus | Changed warm median |
| --- | ---: | ---: |
| Narrow filtered literal miss | 14 files, 26.0 MB | 735 ms |
| Recent broad list | 22 files, 93.8 MB | 1.076 s |
| Broad filtered literal miss | 3,245 files, 5.655 GB | 3.691 s |
| Selective literal, three IDs | 3,245 files, 5.655 GB | 4.456 s |
| Broad filtered regex miss | 3,245 files, 5.655 GB | 23.934 s |

The selective literal printed its first ID after a median 803 ms. Full completion still took 4.456 seconds.

The regex miss bypassed literal gates. Semantic confirmation consumed 22.654 seconds across 3,244 selected files.

`SessionScan` consumed 17.153 seconds inside that regex confirmation. Provider decoding, normalization, visibility, and semantic rendering form the largest search bucket.

### The changed native model creates a real shared seam

`rust/model.rs` and `rust/codecs.rs` now give the native executable a canonical `Message` and `Tool` model plus exact XML and JSON transport.

For one Claude, one Pi, and one Codex session, direct plain XML matched this composition byte for byte:

```text
current native session -> current structured JSON -> native ch parse -> canonical XML
```

This proves that the Rust model accepts the current journey's public structured messages. It does not prove native provider decoding, visibility, or metadata.

Default parse and search still build the Python `Message` model. They still use Python visibility, shortening, XML semantics, raw output, metadata, and Rich rendering.

### Useful Rust session and search work is trapped behind PyO3

Rust already implements inventory, provider path classification, timestamp scans, resolution-facet scans, and search candidate scans.

Those implementations live inside `rust/python_extension.rs`. The packaged `ch` binary builds with `--no-default-features`, so it cannot call them.

Timestamp and resolution scans also call Python JSON callbacks. Their native forms still need Rust facet decoding.

The next route must extract only the needed portable cores into ordinary Rust modules. Thin PyO3 wrappers can call those modules while search remains in Python.

### Complete default session parse is the smallest shared product boundary

Default session parse still owns all of these public behaviors:

1. Path, exact ID, recent index, title, summary, stdin, pasted content, and piped-ID input.
2. Provider, directory, creation, and modification filters.
3. Claude, Pi, and Codex decoding, branches, agents, tools, and provider metadata.
4. Role visibility, thinking, plans, custom records, slices, and shortening.
5. XML, structured JSON, raw Markdown, metadata-only, ID-only, file, Rich, and paged output.
6. Argument repair, warnings, errors, final newlines, broken pipes, and exits.

Search needs this provider, model, visibility, shortening, metadata, and presentation core for semantic confirmation.

Search also adds query grammar, Python-compatible regular expressions, candidate planning, result views, ordering, streaming, highlighting, pager cancellation, and no-hit behavior.

A search-first cycle would combine both layers. A complete default-session cycle builds the shared layer first.

### Complete production authority disposition

The detailed symbol map lives in [cycle-02-map.md](cycle-02-map.md). Its accepted disposition is:

| Current production authority | Cycle 02 result |
| --- | --- |
| Native `ch parse` conversion | Keep closed and unchanged |
| Rust `Message`, `Tool`, XML, and JSON codecs | Reuse and extend as the one session model |
| Python default grammar and argument repair | Move every default shape to the Rust launcher |
| PyO3-only inventory, classification, timestamps, and facets | Extract needed portable Rust cores with thin temporary wrappers |
| Python resolution, filters, and three provider adapters | Move to Rust |
| Python branches and agent merging | Move to Rust |
| Python visibility, tool filters, slices, and shortening | Move to Rust |
| Python XML, structured JSON, raw, metadata, and Rich rendering | Move to Rust and reuse the native transport authority |
| Python paging, file output, errors, and exits | Move to Rust while keeping external `less -r` |
| Python search grammar, regex truth, candidate planning, results, and streaming | Keep unchanged on `ch-legacy` during cycle 02 |
| Rust candidate scans behind PyO3 | Keep for legacy search, then extract later as search needs them |
| Unrelated Python commands | Keep on `ch-legacy` |
| NLTK and unrelated eager imports | Leave the completed default-session path |

## Decisions

Cycle 02 will move the complete default `ch [SESSION] [SLICE...] ...` journey to the native executable.

This choice does not deny the search tail. It selects the smaller complete route that builds the largest search prerequisite.

Do not choose an exact-ID-only, plain-only, provider-only, or ID-only production route. Those slices would split one public journey between Python and Rust.

Do not choose standalone core extraction. Extract portable inventory and resolution code only inside the product route.

Do not add another PyO3 semantic helper. It would leave Python on the public path and add temporary authority.

Reuse the cycle 01 Rust model and codecs. A second session-only model or renderer invalidates the reuse evidence.

Keep search and unscoped commands on the private legacy route during cycle 02.

After exact behavior parity, require these changed-system performance gates:

1. Small direct plain output at most 60 ms.
2. Medium exact-ID plain output at most 150 ms.
3. Newest Pi recent-index ID output at most 250 ms.
4. Large forced-Rich output at most 350 ms.

These gates prove that the route removed the Python floor. They do not require conversion-like speed for discovery or terminal rendering.

## Proof

The conversion, package, launcher, round-trip, and authority suite passed 60 tests in 30.12 seconds.

A focused default-session suite passed 113 tests with 1 accepted skip in 33.91 seconds.

A focused search suite passed 138 tests in 0.78 seconds.

Four public shell suites passed. They covered argument repair, XML and JSON output, the real launcher, search ID output, and search date filters.

The installed command contract reproduced accepted default-session and search bytes. Loader traces confirmed both still use Python by design.

The same contract reproduced the conversion command corpus and all 15 stored conversion pairs. It also proved package ownership and no Python on exact conversion.

The three-provider composition check proved direct XML parity through the changed native conversion model.

The profile used the real installed launcher after one prime. It recorded machine, fixtures, hashes, the search snapshot, memory, and component attribution.

Interleaved changed-versus-red runs controlled for host timing drift. The live Python paths were slower than cycle 01, but the red launcher drifted with them.

No teammate edited production source or tests. Scratch fixtures and harnesses stayed under the system temporary directory.

## Remaining risks

The shell history belongs to one developer. It can miss scripts, removed history, failed commands, and other users.

The current tests strongly cover Python units and command functions. They do not yet pin the full installed default-session journey as exact process oracles.

The Rust conversion model proves transport compatibility only after Python has normalized provider records. Native adapters can expose missing session-only fields or ordering rules.

Provider parsing is the largest semantic body. Claude branches, Pi custom and joined-agent records, Codex generated tool scripts, and merged agents need exact parity.

Rich terminal parity remains the largest presentation risk. It includes widths, Markdown, syntax highlighting, diffs, ANSI, paging, Unicode, and broken pipes.

Search keeps the 23.934-second tail after cycle 02. The shared native session core must remain reusable without moving search truth in this cycle.

Python regular expressions and Unicode behavior remain the largest later search architecture risk.

The live corpus changes during work. Later acceptance must record a fresh snapshot and use interleaved controls.

## Crew convergence

The mapper integrated all three source artifacts and revised the draft after both independent reviews.

The scout verified the product contract, launcher evidence, corrected use counts, success-and-failure authority proof, exact colored output, risks, and boundary.

The profiler verified every cost claim, host-drift control, performance gate, proof item, risk, and boundary.

Both requested revisions were applied. All three teammates accept this result and the complete native default-session boundary.

## Exact next boundary

Build a tests-first, complete native default `ch [SESSION] [SLICE...] ...` journey through both installed `ch` executables.

Before production code, add process-level byte oracles that do all of the following:

1. Pin the complete default argument grammar, help, option order, detached optional values, negative inputs, negative slices, warnings, errors, and exits.
2. Pin path, exact ID, recent index, title, summary prefix, pasted content, stdin content, and piped-ID resolution.
3. Pin provider, directory, creation, and modification filters with in-band timestamp ordering.
4. Cover Claude, Pi, and Codex default output, branches, agents, Pi agent records, tools, plans, custom records, and role filters.
5. Pin multiple ordered-union slices, empty slices, global shortening, tool-local shortening, thinking shortening, and progressive shortening.
6. Pin XML, structured JSON, raw Markdown, metadata-only, ID-only, file output, metadata controls, stdout, stderr, and final newlines.
7. Pin colored terminal output at fixed widths, pager launch and cancellation, TTY errors, Unicode, and broken pipes.
8. Prove direct XML equals `structured JSON | ch parse` across the accepted three-provider corpus.
9. Prove every covered default-session process starts, loads, embeds, and calls no Python or PyO3 authority. This includes help and all argument, resolution, input, rendering, output, and broken-pipe failures.
10. Prove native conversion stays unchanged while search and unscoped commands keep accepted legacy behavior.
11. Prove both package-owned launchers and the built wheel contain the same native route.

Then implement only that complete route:

1. Route every default session shape inside `rust/main.rs` without starting Python.
2. Extract needed portable inventory, classification, timestamp, and resolution-facet cores from the PyO3-only source.
3. Implement all three provider adapters, branch selection, and agent merging against the existing Rust model.
4. Implement visibility, tool filters, filters, slices, shortening, metadata, and every public projection in Rust.
5. Reuse the native XML and structured JSON transport authority.
6. Move terminal detection, exact colored terminal output, file output, stderr, exits, and `less -r` control to Rust.
7. Remove the Python default-session production authority after every public shape passes.
8. Keep search and unscoped commands on the unchanged private legacy entry.

Run the full regression suite, all process oracles, package verification, both installed launchers, and the fixed performance shapes.

Require exact behavior first. Then require warm medians of at most 60 ms for small direct plain output, 150 ms for medium exact-ID plain output, 250 ms for newest Pi recent-index ID output, and 350 ms for large forced-Rich output without a pager.

The green boundary is complete only when every default session shape preserves behavior and starts no Python.
