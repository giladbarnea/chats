# Cycle 02 changed production authority map

## Baseline

The accepted changed-system baseline is `b2ce1fd9dea41c033c7cb02321ea37b3764863d8` on `main`.

This baseline completed exact provider-free conversion through the installed native launcher. No teammate changed production source or tests during this map.

The installed package owns two entries:

1. `ch` is a Mach-O Rust executable.
2. `ch-legacy` is the private Python entry for unfinished and unscoped routes.

## Findings

### Changed launcher authority

The public launcher now splits before Python starts:

```text
~/.local/bin/ch
  ├─ first argument `parse`
  │    -> Rust argument grammar
  │    -> Rust input and UTF-8 handling
  │    -> Rust canonical model and codecs
  │    -> Rust stdout, stderr, and exit
  └─ every other shape
       -> exec package-owned ch-legacy
       -> CPython 3.14
       -> chats.cli and eager package imports
       -> Python default parse, search, or unscoped command
```

A loader trace found no Python or PyO3 library on `ch parse --help`. The same trace found CPython, `orjson`, and `chats._native` on default help and search help.

Importing `chats.cli` now loads 30 project modules and 633 total modules in the observed environment. Default parse and search still pay the eager import graph, including unrelated commands and NLTK.

### Completed native conversion route

Exact `ch parse [FILE] [-f xml|json]` has one production authority:

| Layer | Current authority |
| --- | --- |
| Routing and arguments | `rust/main.rs` |
| File, stdin, UTF-8, newline, errors, exits | `rust/main.rs` |
| Canonical messages and tools | `rust/model.rs` |
| Strict structured JSON | `rust/model.rs`, `rust/codecs.rs` |
| Canonical XML decode and encode | `rust/codecs.rs` |
| Structured JSON projection | `rust/codecs.rs` |
| Installed package asset | `setuptools-rust` wheel and installed RECORD |

The old Python conversion handler, structured JSON decoder, and XML decoder are gone. Python `format_to_xml` and `format_to_json` remain, but only for unfinished default parse and search paths.

### Native reuse is real but incomplete

`rust/model.rs` already represents every canonical message field and tool variant used by conversion. `rust/codecs.rs::format_xml` can project those messages with exact canonical transport behavior.

Default parse and search do not use this model. They still build `src/chats/model.py::Message` and render it with Python.

The native model also does not yet own provider decoding, visibility, tool filters, shortening, slicing, metadata, or terminal rendering. It is a reusable base, not a finished session model.

The scout proved direct plain XML equals `current structured JSON | native ch parse` byte for byte for one Claude, Pi, and Codex session. This proves transport reuse after Python normalization. It does not prove native provider parsing.

The existing Rust session and search helpers are not callable from the no-Python binary. `rust/lib.rs` includes `rust/python_extension.rs` only with Python-binding features, while the packaged `ch` binary builds with `--no-default-features`.

The next native product route must extract the needed portable implementations into normal Rust modules. Thin PyO3 wrappers may call those modules while unfinished Python routes remain. A standalone PyO3 helper cycle would not move a product journey.

### Remaining default session parse authority

Default `ch [SESSION] [SLICE...]` still uses this Python chain:

```text
rust/main.rs legacy dispatch
  -> ch-legacy
  -> cli.py argument grammar and repairs
  -> commands/parse.py
  -> commands/resolve.py and SessionPool
  -> provider adapter and JSONL parsing
  -> Python Message visibility and shortening
  -> slicing, metadata, and rendering
  -> stdout, stderr, file, or less
```

| Observable responsibility | Python authority | Native dependency or required result |
| --- | --- | --- |
| Public grammar and argument repairs | `cli.py` | Move the complete default grammar to the Rust launcher. |
| Path, pasted content, stdin, and piped-ID distinction | `commands/resolve.py` | Move input classification and exact errors to Rust. |
| Inventory and provider partition | `session_pool.py`, `parsing._discover_session_file_rows` | Extract Rust discovery and classification from the PyO3-only source. |
| Exact path, filename, stem, and native-ID resolution | `session_pool.py`, provider ID readers in `parsing.py` | Consolidate on a Rust session inventory. |
| Recent negative-index resolution | `commands/resolve.py`, `ordering.py` | Move in-band timestamp ordering and sidechain exclusion to Rust. |
| Title substring and summary-prefix fallback | `commands/resolve.py`, `parsing.extract_resolution_facets_from_jsonl` | Replace the Python callback used by the current Rust scanner. |
| Provider, directory, creation, and modification filters | `pool_filter.py`, `date_filters.py`, timestamp helpers in `parsing.py` | Move filter grammar, local-time policy, and probes to Rust. |
| Provider detection | `parsing._select_jsonl_session_adapter` | Reuse extracted native path classification, then preserve first-entry fallback. |
| JSONL decode | `parsing._iter_jsonl_entries`, `orjson` | Replace `orjson` with Rust JSONL decoding. |
| Claude messages and branches | `_parse_default_jsonl_entries`, `_resolve_branch_map` | Move forest, compaction-era, visibility, protocol, hook, and tool rules to Rust. |
| Pi messages and custom records | `_parse_pi_jsonl_entries` and Pi helpers | Move message, tool, inline-skill, compaction, and joined-agent rules to Rust. |
| Codex messages and tools | `_parse_codex_jsonl_entries` and Codex helpers | Move preamble, reasoning, tool-script, lifecycle, and metadata rules to Rust. |
| Claude and Codex agent discovery and merge | `commands/resolve.py`, `commands/parse.py` | Move transcript discovery, identity, block construction, and timeline merge to Rust. |
| Canonical session model | `model.py`, `parts.py`, `registry.py`, `tools.py` | Extend and use the existing Rust `Message` and `Tool` model. |
| Visibility and tool filtering | `model.py`, `tool_filter.py` | Move role, thinking, tools, agents, branches, plans, and custom visibility to Rust. |
| Slices and ordered unions | `commands/parse.py` | Move argument repair, bounds, OR union, empty results, and exits to Rust. |
| Shortening | `shortening.py`, `model.py`, `utils.py` | Move global, local tool, thinking, and progressive policies to Rust. |
| XML, JSON, and raw output | `formatting.py`, `tools.py`, `xml_transport.py` | Reuse the Rust model and XML codec, then add exact visible JSON and raw projections. |
| Session metadata and identifiers | `formatting.py`, `parsing.py`, `commands/resolve.py` | Move provider IDs, cwd, fork parent, title, timestamps, frontmatter, and title projection. |
| Colored output | `formatting.py`, `theme.py`, Rich, Markdown, Pygments | Reproduce panels, Markdown, syntax, diffs, widths, ANSI, and terminal detection in Rust. |
| Paging and output destinations | `console.py`, `commands/resolve.py` | Move stdout, stderr, file output, `less -r`, early close, and broken pipes to Rust. |

### Remaining search authority

Search still uses the same Python provider and presentation core as default parse. It adds these search-specific authorities:

| Observable responsibility | Python authority | Native dependency or required result |
| --- | --- | --- |
| Search grammar and option normalization | `cli.py` | Move the complete public grammar to Rust. |
| Regex-or-literal fallback | `search_query.py`, Python `re` | Match Python regular expressions, flags, invalid-pattern fallback, and Unicode behavior. |
| Uppercase boolean grammar | `search_query.py` | Move tokenization, precedence, errors, and session-wide evaluation to Rust. |
| Candidate pool and newest-first order | `commands/search.py`, `SessionPool` | Use the shared native inventory and preserve filesystem-mtime order. |
| Date, directory, and provider gates | `pool_filter.py`, `commands/search.py` | Reuse native session filters without changing ordered results. |
| Dot/ID projection | `_project_default_dot_match` and provider helpers | Fold this duplicate visibility logic into the native provider core. |
| Literal candidate planning | `commands/search.py` | Preserve all conservative bypass and evidence rules. |
| Candidate byte scans | Rust through PyO3 | Extract byte and decoded-JSON-string scans into ordinary Rust modules. |
| Semantic confirmation | `SessionScan`, provider parsers, `render_message_inner_xml`, Python `re` | Reuse native adapters, visibility, shortening, and semantic XML from the session route. |
| Search facets | `SessionScan`, parsing facet helpers | Move summaries, current title, cwd, and message truth to Rust. |
| Hit metadata and counts | `SearchHit`, `commands/resolve.py` | Move match lists, counts, provider, fork parent, and timestamps to Rust. |
| Result modes | `commands/search.py`, `formatting.py` | Move ID, list, matches, full, raw, plain, and colored output. |
| Streaming and exits | `commands/search.py`, `console.py` | Preserve per-hit flush, raw buffering, pager early close, per-file errors, no-hit text, and exits. |
| Match highlighting | Python `re`, Rich Markdown | Preserve literal-only highlights, case behavior, and ANSI presentation. |

### Shared remaining runtime dependencies

| Dependency | Current use | Required disposition |
| --- | --- | --- |
| CPython 3.14 and standard library | All unfinished routes | Leave each completed scoped route. |
| `argparse` | Default parse and search grammar | Replace with exact Rust grammar. |
| `orjson` | Provider JSONL decode | Replace with Rust JSON decoding. |
| Rich, Markdown-It, and Pygments | Colored default parse and search | Reproduce observable output in Rust. |
| PyO3 and `chats._native` | Session inventory, timestamps, facets, candidate scans | Remove from completed routes. Keep thin wrappers only for unfinished Python callers. |
| NLTK and its import graph | Eager import ballast | Leave scoped routes. Do not port it. |
| Python `re` | Search truth and several provider grammars | Port provider grammars normally. Prove search regex compatibility separately. |
| External `less -r` | Paging | Keep the pager, but move process control to Rust. |
| Rust `serde_json`, `regex`, Rayon, `libc`, and `chrono` | Native conversion and current helpers | Keep internal where behavior matches the contract. |

## Decisions

The completed conversion route remains closed. Do not reintroduce Python, PyO3, or a second conversion authority.

Do not make shared-core extraction its own cycle. Extract only the portable Rust inventory, classification, timestamp, facet, or scan code required by the selected public route.

The next boundary is the complete default session parse journey. It is the smallest remaining route that can cross the public launcher without creating a second helper boundary.

The corrected product sample contains 133 default session calls and 62 search calls. Exact IDs account for 102 default calls. Recent indices account for 21.

Search retains the largest measured tail at 23.934 seconds. However, its largest bucket is provider normalization and rendered semantic confirmation. The default session route establishes that shared core without search-only regex, candidate planning, streaming, and result views.

A narrow `--only-id`, exact-ID, plain-only, or provider-only native branch would leave one public journey split between Python and Rust. That can be useful red-contract staging inside the cycle, but it is not the accepted green boundary.

## Proof

1. `git rev-parse HEAD` returned the accepted baseline `b2ce1fd9dea41c033c7cb02321ea37b3764863d8`.
2. Both installed public launchers are package-owned arm64 Mach-O executables.
3. The installed RECORD owns the native `ch` binary and private `ch-legacy` entry.
4. Loader traces proved exact conversion help loads no Python, while default and search help load CPython, `orjson`, and `chats._native`.
5. A clean `chats.cli` import recorded 30 project modules and 633 total modules.
6. Static reading covered the full Rust launcher, model, codecs, PyO3 extension, default parse, resolution, provider adapters, shared model, rendering, filters, and search path.
7. The accepted cycle 01 suite already pins native conversion and one unchanged legacy case for default parse and search.
8. The scout passed 60 conversion/package tests, 113 default-session tests with 1 skip, 138 search tests, and four shell suites.
9. The profiler used an interleaved red control to prove default parse and search received no material regression or gain from the launcher seam.
10. This map changed only this Markdown artifact.

## Remaining risks

The current tests strongly cover Python units and command functions. They do not yet pin the full default session journey as installed-launcher byte oracles.

Colored Rich parity remains the largest default-session presentation risk. Terminal width, Markdown, syntax highlighting, diffs, ANSI, paging, and broken pipes need real process fixtures.

Provider parsing is the largest shared semantic body. Claude branches, Pi custom and joined-agent records, Codex generated tool scripts, and merged agents need cross-provider process-level parity.

The Rust conversion model proves canonical transport, not provider-to-model normalization. Extending it without creating session-only duplicate fields needs careful contract tests.

Python regular-expression and Unicode compatibility remains the largest search-only architecture risk. Rust `regex` does not implement the full Python contract.

During default-session migration, search can keep Python and PyO3. Shared portable Rust cores must keep thin wrappers until search leaves that route.

## Exact next boundary

Build a tests-first, fully native default `ch [SESSION] [SLICE...]` journey through both installed `ch` launchers.

Before production code, add installed-launcher byte oracles for:

1. The complete default argument grammar, repairs, help, warnings, errors, and exits.
2. Path, exact ID, recent index, title, summary, pasted content, stdin content, and piped ID resolution.
3. Claude, Pi, and Codex default output plus branches, agents, thinking, tools, plans, custom records, and role filters.
4. Multiple slice unions, empty slices, global shortening, tool-local shortening, and progressive shortening.
5. XML, structured JSON, raw Markdown, metadata-only, ID-only, file output, and metadata controls.
6. Provider, directory, creation, and modification filters with in-band timestamp ordering.
7. Colored terminal output at fixed widths, pager behavior, early pager close, Unicode, and broken pipes.
8. Exact stdout, stderr, final newlines, streaming or file timing where observable, and exit status.
9. No Python executable, embedded Python, PyO3 extension, callback, fallback, or parallel authority on every covered default-session process. This includes help and all argument, resolution, input, rendering, output, and broken-pipe failures.
10. Unchanged native conversion, search, and unscoped legacy routes.

Then implement only that journey:

1. Route every default session shape in `rust/main.rs` without starting Python.
2. Extract needed portable inventory, path classification, timestamps, and resolution facets from the PyO3-only source.
3. Extend the existing Rust canonical model instead of creating another message model.
4. Implement all three provider adapters, branch selection, agent merging, visibility, filters, slices, and shortening.
5. Reuse the Rust XML transport authority. Add exact structured JSON, raw, metadata, and colored projections.
6. Move terminal detection, file output, stderr, exits, and `less -r` control to Rust.
7. Remove the Python default parse authority after all route shapes pass.
8. Keep search and unscoped commands on the private legacy entry until later cycles.

Require exact behavior before performance. Then require warm medians of at most 60 ms for small direct plain output, 150 ms for medium exact-ID plain output, 250 ms for newest Pi recent-index ID output, and 350 ms for large forced-Rich output.

The green boundary is complete only when installed default session parse preserves behavior and starts no Python for every supported shape.
