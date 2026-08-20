# Cycle 02 changed-system product journey scout

## Baseline

The changed-system baseline is `b2ce1fd9dea41c033c7cb02321ea37b3764863d8` on `main`. The checkout had no tracked source or test changes before this scout.

Cycle 01 moved exact `ch parse [FILE] [-f xml|json]` conversion into the package-owned Rust executable. Default session parse and search intentionally remained on the private Python route.

This scout rechecked the three public journeys through the real installed launcher at `/Users/giladbarnea/.local/bin/ch`. It also compared the checkout launcher at `.venv/bin/ch`.

## Findings

### Product use still orders default session parse first

The same local shell history contains 195 direct in-scope calls. It remains directional evidence from one user, not product telemetry.

| Journey | Calls | Dominant shape |
| --- | ---: | --- |
| Default session parse | 133 | Exact session ID with default rendering, often with visibility flags or slices |
| Search | 62 | Filtered, case-insensitive matches output |
| Conversion | 0 | No direct call appeared |

A corrected shape count has 102 exact-ID calls and 21 recent-index calls. Cycle 01 classified two exact-ID calls with a trailing `-2` message slice as recent-index calls. This correction strengthens exact-ID use without changing the journey order.

Search still has 51 default matches-mode calls. Fifty-four calls use at least one pool filter. Eleven calls select list, ID-only, or raw output.

### Native conversion is complete and isolated

Both installed public launchers are package-owned arm64 Mach-O executables. Their bytes share SHA-256 `00bbdb00d48523270c15db97f6c53b4d1e3b53c809cac068b9f6b96b981668bf`.

Exact `ch parse` now owns its arguments, UTF-8 input, strict schema, canonical model, XML and JSON projection, errors, output bytes, and exits in Rust.

The route starts no Python process and loads no PyO3 extension. Its public contract remains file or stdin input in either direction, exact output bytes, empty cases, errors, and one final newline for non-empty success.

### Default session parse remains one complete Python journey

Every default shape first enters the native launcher, which replaces itself with `ch-legacy`. The journey still loads Python and the PyO3 extension.

The public journey remains unchanged. It resolves paths, exact IDs, recent indices, titles, summary prefixes, stdin content, and piped IDs across Claude, Pi, and Codex.

It then owns provider decoding, branches, agents, visibility, tool filters, ordered union slices, shortening, metadata, XML, structured JSON, raw Markdown, ID-only, metadata-only, files, colored panels, paging, warnings, errors, and exits.

A partial native route for only exact IDs, plain XML, or one provider would split this one public journey across two authorities. Argument repair, terminal detection, and resolution fallbacks also make a partial launcher split hard to classify before product work starts.

### Search remains the broader Python journey

Every `ch search` shape also replaces the native launcher with `ch-legacy`. Python still owns query grammar, Python-compatible regular expressions, semantic confirmation, visibility-dependent truth, metadata, rendering, streaming, and exits.

Rust still helps through the loaded PyO3 extension. It supplies inventory, timestamp and resolution probes, and conservative candidate scans. These helpers do not make search a native executable route.

Search still spans three providers, newest-first filesystem ordering, summary and current-title facets, uppercase boolean operators, invalid-regex literal fallback, visibility-sensitive matches, five output shapes, early result streaming, and pager cancellation.

Search therefore adds query planning, regular-expression parity, candidate transparency, streaming, and search-specific views on top of the provider and presentation work that default session parse also needs.

### The cycle 01 model is reusable at the public seam

For one Claude, one Pi, and one Codex session, direct plain XML matched this composition byte for byte:

```text
native session → current structured JSON → native ch parse → canonical XML
```

All six session and conversion processes exited 0. Every stderr was empty.

| Provider | Direct XML | Structured JSON | Composition parity |
| --- | ---: | ---: | --- |
| Claude | 167 bytes | 260 bytes | Exact |
| Pi | 10,838 bytes | 14,548 bytes | Exact |
| Codex | 26,974 bytes | 28,014 bytes | Exact |

This proves that the Rust model and codecs accept the current journey's public structured messages. It does not mean default session parse or search uses that model today.

## Decisions

Cycle 02 should move the complete default session parse journey to the native executable.

Default session parse remains the most-used journey. It is also the smallest complete remaining route that can establish shared native provider decoding, visibility, slicing, shortening, metadata, and presentation.

Search has the larger tail cost, but it needs those shared capabilities plus search-only grammar, regular expressions, candidate planning, streaming, and result views. Starting with search would combine both layers in one boundary.

Do not choose a standalone core-extraction cycle. Extract portable Rust inventory, resolution, and scan cores only as enabling work inside the default session route.

Do not choose an exact-ID-only, plain-only, or provider-only production route. These slices leave one public journey under parallel Rust and Python authorities.

Reuse the cycle 01 Rust `Message` and `Tool` model and its codecs. A second session-only model or renderer would invalidate the reuse evidence and make later search migration harder.

## Proof

The exact conversion, package, launcher, round-trip, and authority suite passed `60` tests in 30.12 seconds.

A focused default session suite passed `113` tests with `1` accepted skip in 33.91 seconds. It covered output modes, visibility, slices, provider filters, provider detection, and Pi and Codex adapters.

A focused search suite passed `138` tests in 0.78 seconds. It covered arguments, boolean operators, orchestration, output modes, visibility, case behavior, and searchable facets.

Four public shell suites passed. They covered CLI argument repair, XML and structured JSON output, real installed launcher loading, search ID-only output, and search date filters.

The installed command contract reproduced accepted bytes for the controlled default session and search routes. Loader traces confirmed that both still use Python by design.

The same contract reproduced the accepted conversion command corpus, all 15 stored conversion pairs, package RECORD ownership, and no-Python loader traces.

The three-provider composition check independently proved exact direct-XML parity through the changed native conversion model.

No scout command changed production source or tests. Temporary files stayed under the system temporary directory.

## Remaining risks

The shell history belongs to one developer. It can miss scripts, removed history, failed calls, and other users.

Complete default session parse is much broader than conversion. Rich terminal layout, pager behavior, early pipe close, argument repair, and three provider adapters need process-level acceptance, not only Rust unit tests.

The Rust model currently proves transport compatibility only after Python has already decoded providers and applied visibility. Native provider adapters can still expose missing model fields or ordering rules.

Search keeps the largest measured tail and remains fully on Python after this boundary. Cycle 02 must build shared cores that search can reuse without making search part of the same production change.

The live session pool changes during the work. Performance and recent-index evidence must record a fresh corpus snapshot.

## Exact next boundary

Build a tests-first, complete native default session parse journey through both installed `ch` executables.

Before production code, add process-level byte oracles for all of these public surfaces:

1. Resolve a path, exact ID, recent index, title, summary prefix, stdin content, and piped ID.
2. Cover Claude, Pi, and Codex, including branches, file-backed agents, and normalized Pi agent records.
3. Pin provider, directory, creation, and modification filters for recent indices.
4. Pin multiple ordered-union slices, empty slices, shortening, role selection, visibility overrides, and tool filters.
5. Pin XML, structured JSON, raw Markdown, metadata-only, ID-only, file output, stdout, stderr, newlines, errors, and exits.
6. Pin help, option order, detached optional values, negative indices, negative slices, unknown options, and argument-repair warnings.
7. Pin colored terminal panels at fixed widths, pager launch and cancellation, TTY errors, and broken pipes.
8. Prove direct XML equals `structured JSON | ch parse` across the accepted three-provider corpus.
9. Prove every completed default session process starts, loads, embeds, and calls no Python or PyO3 authority.
10. Prove native conversion stays unchanged, while search and unscoped commands keep their accepted legacy behavior.
11. Prove both package-owned installed launchers and the built wheel contain the same native route.

Then implement only that complete route:

1. Route every default session parse shape inside the Rust executable.
2. Separate the needed inventory and resolution cores from their thin PyO3 wrappers.
3. Implement the three provider adapters against the existing reusable Rust model.
4. Implement visibility, agents, branches, slicing, shortening, metadata, and all public projections once in Rust.
5. Keep the exact conversion route on its existing model and codecs.
6. Keep search and unscoped commands on the private legacy route for this cycle.

For default session parse, do not start, import, embed, call, or fall back to Python. Do not retain a second Python production authority for any default shape.

Run the full regression suite, every process oracle, package verification, real-launcher proof, and the changed-system performance contract. After acceptance, remap all three journeys before selecting cycle 03.
