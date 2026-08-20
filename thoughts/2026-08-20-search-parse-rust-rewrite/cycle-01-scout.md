# Cycle 01 product journey scout

## Baseline

The code baseline is `95f1891` on `main`. The checkout had no tracked source or test changes before this scout.

The accepted product boundary contains three exact journeys:

1. `ch [SESSION] [SLICE...]` resolves and renders native sessions.
2. `ch search ...` searches the native session pool.
3. `ch parse [FILE] [-f xml|json]` converts provider-free transport formats.

The installed product launcher is `/Users/giladbarnea/.local/bin/ch`. It starts CPython through a uv-generated script.

This scout used the public documentation, CLI help, production entry points, tests, controlled homes, the installed launcher, and local shell history.

## Findings

### Product journey order

The shell history contains 195 direct in-scope invocations. This is directional evidence from one user, not product telemetry.

| Journey | Uses | Dominant shape |
| --- | ---: | --- |
| Default session parse | 133 | Exact session ID, default format, often with slices or visibility flags |
| Search | 62 | Filtered, case-insensitive matches output |
| Conversion subcommand | 0 | No direct invocation appeared |

Exact session IDs account for 100 of 133 default session calls. Recent indices account for 23 calls.

Search uses matches mode in 51 of 62 calls. Filters appear in 54 calls. List, ID-only, and raw modes account for eleven calls.

Observed use therefore ranks default session parse first, search second, and conversion third.

### Default session parse contract

Users can supply a native path, exact ID, recent negative index, current title, summary prefix, stdin content, or a piped ID.

Recent indices span Claude, Pi, and Codex. Provider, directory, creation, and modification filters narrow only this resolution shape.

Exact IDs win before title and summary scans. Multiple slice selectors form an ordered union with no duplicate messages.

The default visibility keeps regular user and assistant text. Thinking, tools, plans, agents, abandoned branches, and most protocol records require explicit flags.

The public projections are plain XML, structured JSON, raw Markdown, metadata-only, ID-only, file output, and the colored terminal view.

Plain file-backed XML sends frontmatter to stderr and the message body to stdout. Colored output replaces frontmatter with a session title.

`--color auto` and paging depend on the terminal. ID-only, raw, and JSON routes bypass colored rendering as documented.

Argument repair is public behavior. Bare visibility flags must not steal inputs or slices, and negative indices must not become slices.

Resolution, provider decoding, message ordering, metadata, visibility, shortening, rendering, warnings, errors, and exit status all require parity.

### Search contract

Search covers the same Claude, Pi, and Codex pool. Results stream newest first by filesystem modification time.

A query can match visible rendered message content, any summary, or the current title. Boolean terms can match different facets or messages.

Plain patterns use Python regular-expression semantics. Invalid regular expressions become literals.

Uppercase `AND`, `OR`, and `NOT` enable the boolean grammar. Malformed boolean queries write an error and exit 2.

Visibility flags change both matching truth and rendered output. Role filters still leave summary and current-title facets searchable.

The output modes are matching messages, full conversations, list, ID-only, and raw Markdown. Plain, colored, paged, and metadata-free variants are public.

Non-raw results stream per confirmed session. Each ID flushes immediately. Raw output buffers hits for its single-message special case.

No matches exit 1. ID-only stays silent. Other modes print a hint. A bad session reports an error without stopping later sessions.

Search acceptance must preserve candidate-gate transparency. Every fast path must return the same ordered IDs as full semantic confirmation.

### Conversion contract

`ch parse` is not native-session parsing. It accepts one UTF-8 file or all stdin and discovers no provider.

The default direction converts strict structured JSON into canonical XML-tagged Markdown. `-f json` converts canonical XML in the other direction.

A non-empty success writes one canonical body plus a final newline to stdout. It emits no metadata, color, pager output, or success text on stderr.

An empty structured JSON array is valid. JSON-to-XML exits 0 with empty stdout and stderr. Empty XML-to-JSON emits `[]\n`.

The JSON schema is strict about roots, message fields, content ordering, tool fields, and types. XML parsing is also strict and canonical.

Both directions preserve all represented data. XML intentionally cannot recover native precision or fields that its transport discarded.

Schema, decode, XML, UTF-8, and file errors write a prefixed error to stderr and exit 1. CLI grammar errors exit 2.

The stored corpus covers three source adapters across five source configurations. The converter itself remains provider-free.

### Shared parity surfaces

The three journeys share command routing, the canonical message model, tool normalization, XML transport, output bytes, and package installation.

Default session parse and search also share inventory, providers, filters, visibility, shortening, semantic XML rendering, metadata, color, and paging.

Search truth depends on rendered inner XML. A renderer change can change both visible output and which sessions match.

The real installed launcher is part of every contract. Passing an internal Rust or Python test alone does not prove product parity.

## Decisions

Use frequency alone would start with exact-ID default session parse. That boundary still includes provider discovery, three adapters, and terminal rendering.

The accepted first slice is exact `ch parse`. It is the smallest complete public journey and creates shared model and codec authority.

This choice is enabling work, not a claim that conversion has the most direct use. The next remap must return to the higher-use journeys.

Do not add another PyO3 helper. The completed conversion invocation must start and finish in the native executable without Python.

Keep the three journey names exact in later artifacts. Do not use “parse” alone for both session rendering and transport conversion.

## Proof

The full non-performance regression suite passed with `1104 passed, 3 skipped` in 56.02 seconds.

The focused search and parse suite passed `199` tests. Eleven in-scope shell scripts also passed.

The shell scripts covered stdin, files, slices, argument repair, visibility, tools, formats, metadata, raw output, colors, search dates, and ID-only output.

The installed launcher passed a controlled three-provider search. It returned `codex-journey`, `pi-journey`, then `claude-journey` in pinned newest-first order.

The same launcher passed boolean facet matching, hidden-thinking visibility, provider and directory filters, and exit codes 1 and 2.

The installed launcher resolved an exact ID with a slice, a provider-filtered recent index, and a Pi session to structured JSON.

The installed launcher converted a 257,726-byte tool fixture through file and stdin routes. Rebuilt XML matched SHA-256 `bd5ac9c75d39443eff223db73d3da1148ed93a780d61fbdcde20fc07e6e8cfae`.

All 15 stored JSON inputs already reproduce their stored XML outputs byte for byte through the public command.

## Remaining risks

The shell history reflects one developer and includes development work. It does not measure other users, abandoned commands, or automated invocations.

Current XML-to-JSON tests prove round-trip stability but do not pin exact legacy JSON bytes. A rewrite could change canonical JSON and remain self-consistent.

Most tests run the checkout launcher through `uv run`. Only a narrow seam test uses the installed uv tool launcher.

No current acceptance test proves that a scoped invocation starts no Python process. The native package boundary needs direct process proof.

Rich behavior spans terminal width, Markdown, syntax highlighting, ANSI styling, pager timing, and early pager close. Current coverage cannot remove visual review risk.

Python regular expressions include Unicode and syntax behavior that Rust `regex` does not fully reproduce.

## Exact next boundary

Build a tests-first native `ch parse [FILE] [-f xml|json]` journey through the installed `ch` executable.

Before implementation, pin these process-level contracts:

1. Store exact legacy XML-to-JSON stdout for all 15 XML fixtures.
2. Keep the 15 existing JSON-to-XML byte oracles.
3. Cover file and stdin input in both directions.
4. Pin help, argument order, invalid choices, extra arguments, stderr, and exit status.
5. Pin representative JSON, XML, UTF-8, and file failures byte for byte.
6. Prove successful stderr is empty. Pin empty and non-empty output termination separately.
7. Prove `[]` JSON-to-XML emits no bytes, while empty XML-to-JSON emits `[]\n`.
8. Prove the installed conversion route starts no Python process.
9. Prove default session parse, search, and legacy commands still route unchanged.

Then implement the Rust launcher, strict canonical message model, tool schemas, both codecs, output, and errors for this exact subcommand.

For `ch parse`, do not import, embed, call, or fall back to Python. Route all other commands to a private legacy entry until later slices replace them.
