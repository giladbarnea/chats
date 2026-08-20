# Cycle 01 production authority map

## Baseline

The code baseline is `95f1891` on `main`. The checkout had no tracked source or test changes before this map.

The admiral fixed the scope after a product naming ambiguity surfaced. The rewrite covers these three public journeys:

1. `ch search ...`
2. Default session parse through `ch [SESSION] [SLICE...] ...`
3. Provider-free conversion through `ch parse [FILE] [-f xml|json]`

The real installed launcher is `/Users/giladbarnea/.local/bin/ch`. It links to a uv tool script whose shebang starts CPython 3.14.

That script imports `chats.cli:main`. The editable uv install resolves every project module from this checkout.

Cargo currently builds `rust/lib.rs` as `chats._native`. It is a PyO3 extension, not a command binary.

## Findings

### Shared launcher and import authority

All three journeys enter this production chain:

```text
~/.local/bin/ch
  -> uv-generated Python script
  -> CPython 3.14
  -> chats package initialization
  -> chats.cli.main()
  -> Python argparse router
  -> Python command function
```

Importing `chats.cli` loaded 31 project modules and 571 total modules in one observed clean process. Package initialization eagerly loads every command.

The loaded project modules include `info`, `name`, `rm`, and `murmurs`. Those modules do not serve the three selected journeys.

`murmurs` eagerly imports NLTK. `commands/__init__.py` eagerly imports all command implementations.

This makes import-only code part of every current process. A journey rewrite cannot remove Python startup through another PyO3 call.

The native destination needs a real Rust `ch` executable. Each completed scoped journey must not import or start Python.

A Rust launcher can temporarily route uncompleted scoped journeys and unscoped commands to a private legacy Python entry.

### Authority and disposition matrix

| Layer | Current authority | Journeys | Required disposition |
| --- | --- | --- | --- |
| Installed launcher | uv Python script and CPython | All | Replace with a Rust `ch` executable |
| Command routing and argument repair | `cli.py`, `argparse` | All | Move exact public grammar to Rust |
| Session inventory | Rust traversal, then Python `SessionPool` projections | Session parse, search | Consolidate in Rust |
| Provider path classification | Rust canonical containment behind PyO3 | Session parse, search | Keep Rust logic, remove PyO3 |
| Session resolution | `commands/resolve.py`, `session_pool.py`, `ordering.py` | Session parse | Move to Rust |
| Date and directory filters | `pool_filter.py`, `date_filters.py`, Python timestamp conversion | Session parse, search | Move to Rust |
| Provider JSONL decoding | `parsing.py` with `orjson` | Session parse, search | Move all three adapters to Rust |
| Claude branch authority | `_resolve_branch_map()` in `parsing.py` | Session parse, search | Move to Rust |
| Agent discovery and merge | `commands/parse.py` and `commands/resolve.py` | Session parse | Move to Rust |
| Canonical message model | `model.py`, `parts.py`, `registry.py` | All | Move to one Rust model |
| Visibility and shortening | `model.py`, `tool_filter.py`, `shortening.py` | Session parse, search | Move to Rust |
| Tool normalization and projection | `parsing.py`, `tools.py`, `registry.py` | All | Move to Rust |
| Canonical XML transport | `formatting.py`, `xmlmd.py`, `xml_transport.py` | All | Move to Rust |
| Structured JSON transport | `model.py`, `formatting.py` | Session parse, conversion | Move to Rust |
| Search query grammar | `search_query.py` and Python `re` | Search | Move with Python-compatible semantics |
| Candidate gates | Rust scans called through Python | Search | Keep Rust scans, remove Python boundary |
| Semantic search confirmation | `SessionScan`, provider parsers, XML renderer, Python `re` | Search | Move to Rust |
| Result ordering and streaming | `commands/search.py` | Search | Move to Rust |
| Plain and colored rendering | Python `print`, Rich, Markdown, Pygments | Session parse, search | Reproduce in Rust or remove dependencies |
| Paging | Python subprocess control of `less -r` | Session parse, search | Move process control to Rust |
| Errors and exit status | Python exceptions, Rich error output, `sys.exit` | All | Move exact text and status to Rust |

The external `less -r` process is not semantic authority. Rust can keep it as the pager while replacing Python process control.

### Default session parse authority

The default router owns several observable repairs before parsing starts. These include detached short values, tool positionals, negative indices, and multiple slice selectors.

The production sequence is:

```text
cli.py
  -> normalize arguments, visibility, output mode, and pool filters
  -> commands.parse.cmd_parse
  -> commands.resolve input resolution
  -> SessionPool discovery or direct content
  -> provider detection and JSONL decoding
  -> provider adapter message normalization
  -> optional agent merge
  -> tool-id map
  -> ORed slice selection
  -> progressive shortening assignment
  -> metadata and title loading
  -> XML, JSON, raw, or Rich rendering
  -> stdout, stderr, file, or pager
```

`--only-id` resolves a file without reading its session body. `--only-metadata` requires file-backed input.

Recent indices use in-band last timestamps. They apply provider, directory, creation, and modification filters.

Exact identifiers use file names and native session IDs. Title substring and summary prefix scans form the fallback authority.

Claude parsing resolves a forest of branches and compaction eras. Pi and Codex each have separate message and tool envelopes.

Default visibility suppresses protocol text, hidden tools, thinking, plans, agents, custom records, and abandoned branches.

Agent mode changes both content and discovery. It merges file-backed Claude and Codex agent transcripts into the main timeline.

The functional Python path uses these modules:

```text
cli.py
commands/parse.py, commands/resolve.py, commands/common.py
console.py, date_filters.py, formatting.py, model.py, ordering.py
parsing.py, parts.py, pool_filter.py, registry.py, session_pool.py
shortening.py, theme.py, tool_filter.py, tools.py, utils.py
xml_transport.py
rust/lib.rs through chats._native
```

### Conversion subcommand authority

`ch parse` is separate from default session parse. It does not discover or decode native provider sessions.

Its complete successful sequence is:

```text
cli.py argparse
  -> read one UTF-8 file or all stdin
  -> json.loads plus messages_from_json_data
     OR messages_from_xmlmd
  -> strict canonical Message reconstruction
  -> build tool-id map
  -> format_to_xml or format_to_json
  -> plain stdout only
```

The command supports only an optional file and `-f xml|json`. It emits no session metadata and uses no pager.

JSON input is strict about root shape, keys, field types, content ordering, tool fields, and provenance fields.

XML input is strict about wrapper headers, attributes, separators, indentation, tool schemas, and transport escaping.

Both directions canonicalize through the shared `Message` model. Non-empty successful output ends with one newline.

Empty structured JSON succeeds with no stdout. Empty XML under `-f json` succeeds with `[]\n`.

Errors cover file I/O, JSON decoding, schema validation, and XML validation. They write a red error to stderr and exit 1.

A dynamic trace confirmed that exact conversion calls no Rust function after import. The loaded native extension is unused ballast for this journey.

The functional codec uses these modules:

```text
cli.py
commands/parse.py, commands/common.py, commands/resolve.py
model.py, formatting.py, xmlmd.py, xml_transport.py
parts.py, registry.py, tools.py, tool_filter.py, shortening.py, utils.py
console.py for errors
```

Import coupling also loads provider parsing, Rich, orjson, the Rust extension, and NLTK. None own successful conversion behavior.

### Search authority

Search first parses a query with Python `re.MULTILINE | re.DOTALL`. Invalid regular expressions become escaped literal terms.

Uppercase `AND`, `OR`, and `NOT` create a session-wide query tree. Malformed boolean queries exit 2.

Rust discovers Claude, Pi, and Codex files under the current home. Python partitions the rows and scans them newest first by filesystem mtime.

Provider filters narrow the pool first. Date and directory filters run before full semantic confirmation.

Search has three execution shapes:

1. Narrow `search . -ll` projects visible content directly for Pi and Codex. Claude falls back to full semantic confirmation.
2. Eligible case-insensitive ASCII literals use Rust batch gates in windows of 256 paths.
3. Other queries use per-file conservative gates or go directly to full confirmation.

The Rust gates are candidate authority, not semantic authority. Surviving files still enter Python semantic confirmation.

Full confirmation reads the complete UTF-8 file. `SessionScan` decodes it once into provider, directory, summaries, current title, and visible messages.

Search renders each visible message to semantic inner XML before matching. This makes rendering rules part of search truth.

Boolean terms can match different messages or facets. Current titles and summaries remain searchable under role filters.

A confirmed hit loads provider, fork parent, creation time, and modification time. Results keep newest-first scan order.

ID, list, matches, full, raw, plain, colored, paged, and non-paged modes have separate emit paths.

Non-raw results stream as each file confirms. Raw results buffer all hits for the one-message output special case.

The pager starts `less -r` before streaming. An early pager close stops later scanning.

No matches exit 1. Per-file read or parse failures print an error and let later files continue.

The functional search path uses these modules:

```text
cli.py
commands/search.py, commands/common.py, commands/resolve.py
console.py, date_filters.py, formatting.py, model.py, parsing.py
parts.py, pool_filter.py, registry.py, search_query.py
session_pool.py, session_scan.py, shortening.py, theme.py
tool_filter.py, tools.py, utils.py, xml_transport.py
rust/lib.rs through chats._native
```

### Existing Rust authority

`rust/lib.rs` exports seven PyO3 functions. All seven affect a selected session or search journey.

1. `discover_session_files`
2. `classify_native_session_path`
3. `find_last_jsonl_timestamp`
4. `scan_resolution_facets`
5. `file_contains_ascii`
6. `file_contains_ascii_json_strings`
7. `files_contain_ascii_json_strings`

The timestamp and resolution scans still call Python JSON callbacks. Inventory and candidate scans are otherwise native.

The crate uses `libc` for Darwin byte scans and `ELOOP`, Rayon for batched search, and Rust regex for logical ASCII gates.

PyO3 must leave the three completed paths. The useful Rust implementations should become normal internal library calls.

### Runtime dependencies that must move or leave

The three paths currently depend on CPython 3.14 and its standard library. That runtime must leave each completed scoped journey.

Rich and its Markdown and Pygments stack own colored session and search output. Their behavior must move to Rust.

`orjson` owns native JSONL decoding for session parse and search. A Rust JSON decoder must replace it.

NLTK is import-only ballast. It must leave the path, not move.

PyYAML is installed as a direct package dependency but did not load during `chats.cli` import. It already sits outside these functional paths.

PyO3 owns every current Rust boundary. It must leave completed scoped paths.

Rust `regex`, Rayon, and `libc` can remain internal Rust dependencies where their behavior still applies.

Python `re` is public search behavior. Rust regex alone does not support all Python regular-expression constructs, so compatibility needs explicit proof.

### Packaging authority

`pyproject.toml` defines `ch = "chats.cli:main"`. Maturin builds only the extension module.

The completed product needs an installed native executable at the same `ch` path. An alternate developer-only binary does not satisfy the launcher contract.

Package tests must cover `.venv/bin/ch` and the real uv tool launcher. They must prove completed scoped journeys do not start Python.

Uncompleted scoped journeys and unscoped commands can keep Python during this fleet. Their modules must not load on a completed scoped journey.

## Decisions

The production authority is Python despite existing Rust hot paths. Rust currently accelerates discovery and candidate work but does not own command semantics.

The rewrite must converge on one Rust canonical message model. Session parsing, conversion, and search rendering all depend on it.

The first slice should cross a public command boundary. Another Python-to-Rust-to-Python helper would repeat the function-first failure.

From the dependency view, provider-free conversion is the smallest end-to-end slice. It establishes the canonical model and both transport projections without provider or terminal complexity.

This slice also forces the native launcher and package seam early. Later session and search work can reuse its model, tools, XML transport, and JSON projection.

## Proof

The following evidence anchors this map:

1. `git rev-parse HEAD` returned `95f1891`.
2. The real `ch` resolved to a uv Python script and imported source from this checkout.
3. `Cargo.toml`, `pyproject.toml`, and the installed launcher confirmed the PyO3-only package shape.
4. A clean import probe recorded 31 project modules and 571 total loaded modules.
5. JSON-to-XML and XML-to-JSON call traces recorded every invoked project function.
6. A controlled three-provider home confirmed the `search . -ll` projection and Claude fallback paths.
7. Static reading covered the complete transitive source path and all 1,451 Rust lines.
8. The selected behavior baseline passed 257 tests in 34.64 seconds.

The test command covered conversion, session output modes, visibility, resolution, search semantics, rendering, metadata, and unified provider space.

## Remaining risks

Python regular-expression compatibility is the largest search semantics risk. Unicode case folding and unsupported constructs can change results silently.

Rich output is a large product surface. Exact color, wrapping, markdown, syntax highlighting, pager timing, and terminal detection need launcher-level fixtures.

Provider parsing is large and stateful. Claude branches, Pi custom records, Codex tool scripts, and agent timelines need independent parity proof.

Current timestamps mix Rust scans, Python callbacks, local-time conversion, birth-time fallback, and filesystem mtime. A native type policy must preserve exact output.

A native launcher must preserve every route while removing Python from each completed scoped journey. Package installation is part of the first slice, not cleanup.

The conversion journey had no direct uses in the observed shell-history sample. Its first-slice value comes from coherent shared authority, not observed frequency.

## Exact next boundary

Build a tests-first native `ch parse [FILE] [-f xml|json]` journey through the real installed `ch` executable.

The boundary includes the Rust launcher, exact argument grammar, UTF-8 file and stdin input, the canonical message model, tool schemas, both codecs, output, errors, and exit status.

Before production code, pin exact legacy XML-to-JSON stdout for all 15 stored XML fixtures. The current tests prove self-stability but not exact legacy JSON bytes.

Keep the 15 JSON-to-XML files as byte oracles. Also pin exact stdout, stderr, and exit status for malformed input and argparse errors.

Pin both valid empty cases. `[]` to XML emits nothing, while empty XML to JSON emits `[]\n`. Both exit 0 with empty stderr.

For exact `ch parse`, the real installed Rust process must not import, embed, call, or fall back to Python.

Keep all other command behavior unchanged during this slice. Route uncompleted scoped journeys and unscoped commands through a private legacy entry.
