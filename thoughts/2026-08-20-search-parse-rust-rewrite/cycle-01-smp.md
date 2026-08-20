# Cycle 01 scout, map, and profile result

## Baseline

The accepted code baseline is `95f1891` on `main`. No teammate changed production source or tests.

The admiral fixed the product boundary at three public journeys:

1. `ch search ...`
2. Default session parse through `ch [SESSION] [SLICE...] ...`
3. Provider-free conversion through `ch parse [FILE] [-f xml|json]`

The real installed launcher is `/Users/giladbarnea/.local/bin/ch`. It currently starts CPython 3.14 through a uv-generated script.

The installed editable package resolves project imports from this checkout. Cargo builds a PyO3 extension, not a `ch` executable.

The accepted source views are:

- [Product journey scout](cycle-01-scout.md)
- [Production authority map](cycle-01-map.md)
- [Measured-cost profile](cycle-01-profile.md)

## Findings

### Product order and measured cost

The shell history contained 195 direct in-scope invocations. This is directional evidence from one user, not telemetry.

| Journey | Observed uses | Product position | Representative warm cost |
| --- | ---: | --- | ---: |
| Default session parse | 133 | Most used | 182 ms small path, 265 ms exact ID, 384 ms recent Pi ID |
| Search | 62 | Largest measured pain | 481 ms narrow filtered miss, 2.66 s global literal miss, 16.01 s regex miss |
| Conversion | 0 | Smallest enabling boundary | 177 ms small JSON-to-XML, 185 ms large JSON-to-XML |

Exact session IDs accounted for 100 default session calls. Recent indices accounted for 23 calls.

Search used matches mode in 51 calls. Fifty-four search calls used at least one pool filter.

Default session parse is the most-used journey. Search has the largest measured completion cost.

Conversion is neither. Its value is the small complete boundary and the shared code it establishes.

### Shared launcher cost

Importing `chats.cli` loaded 31 project modules and 571 total modules in an observed clean process.

Eager imports load unrelated commands and NLTK. They also load Rich, orjson, and the native extension before routing finishes.

The measured `chats.cli` import cost was 163 ms. Warm `ch parse --help` took 170 ms.

Large conversion added only 11 to 14 ms above that floor. Startup consumed about 92% of the conversion journey.

Small direct session parse spent about 90% of elapsed time before product work. Large plain session parse spent about 71% there.

Another PyO3 helper would keep this cost and would not create a native command authority.

### Default session parse contract

Default session parse accepts a path, exact ID, recent index, title, summary prefix, stdin content, or a piped ID.

It owns input repair, pool filters, resolution, three provider adapters, branch selection, agent merging, visibility, slicing, shortening, metadata, and rendering.

Multiple slice selectors form one ordered union. The parser decodes the full session before it applies any slice.

A medium full output took 189.1 ms. Its last-message slice took 189.7 ms.

Exact ID resolution added about 76 ms over the same direct path. Recent-index ID resolution added about 213 ms above startup.

Forced Rich rendering added about 132 ms on the large direct path.

The public outputs include XML, JSON, raw Markdown, metadata-only, ID-only, file output, and colored terminal panels.

### Search contract and cost centers

Search covers Claude, Pi, and Codex sessions. It scans results newest first by filesystem mtime.

Python query parsing owns regular expressions, Unicode behavior, invalid-regex fallback, and the uppercase boolean grammar.

Search truth covers visible rendered inner XML, all summaries, and the current title. Terms can match different messages or facets.

Visibility flags change both matching truth and output. Candidate gates must remain invisible to ordered result parity.

Rust currently discovers files and performs candidate scans. Python owns filters, provider decoding, semantic confirmation, metadata, rendering, streaming, and exits.

For a selective literal, in-process Python semantic confirmation took 1.95 seconds across 251 files. The native batch scan took 0.61 seconds.

A regex miss bypassed literal gates and took 16.01 seconds. It forced semantic work across the selected corpus.

Narrow filtered searches still inspect the full pool for inventory and timestamps. A 10-file, 11.5 MB selection took 481 ms.

### Conversion contract

`ch parse` does not parse native provider sessions. It reads one UTF-8 file or all stdin.

Its default direction converts strict structured JSON to canonical XML-tagged Markdown. `-f json` converts canonical XML to structured JSON.

The route owns strict schema validation, the canonical message model, tool schemas, transport escaping, output bytes, errors, and exits.

A non-empty success writes one body with one final newline. Every success writes nothing to stderr and uses no metadata, color, or pager.

Empty structured JSON succeeds with no stdout. Empty XML under `-f json` succeeds with `[]\n`.

A dynamic trace confirmed that successful conversion calls no Rust function after import. The loaded extension is unused for this route.

The stored corpus has 15 JSON and XML pairs. They cover three source adapters across five source configurations.

The JSON-to-XML files are exact byte oracles. Current XML-to-JSON tests prove stability but do not pin exact legacy JSON bytes.

### Complete production authority disposition

The detailed symbol and dependency map lives in [cycle-01-map.md](cycle-01-map.md). Its accepted disposition is:

| Current production authority | Required result |
| --- | --- |
| uv Python launcher and `cli.py` routing | A real installed Rust `ch` executable |
| Python resolution, filters, provider adapters, and agent merge | Rust authority for later session and search slices |
| Python canonical model, tool rules, and shortening | One reusable Rust model |
| Python XML, JSON, raw, Rich, and metadata rendering | Rust projections with exact parity |
| Python search grammar and semantic confirmation | Rust search with Python-compatible semantics |
| Rust inventory, timestamps, resolution facets, and candidate scans behind PyO3 | Internal Rust calls without Python callbacks |
| Unrelated Python command imports and NLTK | Leave all three scoped paths |
| Python pager subprocess control | Rust control of the existing `less -r` pager |

The current functional paths use almost every core Python module. Import initialization also loads unrelated command implementations.

PyO3 must leave every completed scoped path. Useful Rust discovery and scan logic should become normal internal library calls.

Rich, Markdown, Pygments, orjson, argparse, and CPython must leave completed scoped paths. NLTK is import-only ballast.

Legacy `name`, `rm`, `catalog`, and `info` behavior can remain in Python during this fleet. A completed scoped journey must never enter that legacy route.

## Decisions

The first rewrite boundary is exact `ch parse [FILE] [-f xml|json]` through the real installed launcher.

This is enabling work. It is not the most-used journey and does not have the largest direct cost.

The slice is first because it can remove Python from one complete public journey. It also establishes the launcher, package seam, model, and codecs.

The Rust canonical model must be reusable by default session parse and search. A conversion-only duplicate model invalidates this ordering.

Do not add another PyO3 codec. Exact conversion must start and finish in one Rust process with one authority.

The Rust launcher can temporarily route uncompleted scoped journeys and unscoped commands through a private legacy Python entry. It must keep their behavior unchanged.

During this slice, default session parse and search are uncompleted scoped journeys. They intentionally remain on the legacy Python route.

Before production code, add missing exact legacy byte oracles. Self-consistent new output is not sufficient parity.

The large conversion acceptance target is a warm median of at most 60 ms in each direction. This is a threefold improvement over baseline.

After this slice, remap all three journeys. The next decision must compare the most-used session journey with the highest-cost search journey.

## Proof

The full non-performance regression suite passed with `1104 passed, 3 skipped` in 56.02 seconds.

The scout also passed 199 focused tests and eleven in-scope shell scripts. The mapper passed a wider 257-test selected suite.

The installed launcher passed controlled three-provider search, boolean facets, visibility, filters, exact ID, recent index, slices, and structured JSON.

All 15 JSON inputs reproduced their stored XML outputs byte for byte through the public command.

A 257,726-byte stored tool fixture rebuilt XML with SHA-256 `bd5ac9c75d39443eff223db73d3da1148ed93a780d61fbdcde20fc07e6e8cfae`.

The profile used the real launcher with one prime before sequential warm runs. It recorded the corpus, fixture hashes, machine, and native extension hash.

The search snapshot held 4,907 main session files and 6.442 GB. Component attribution used the unchanged command functions and native extension.

The large real conversion fixture contained 648 messages. Its structured JSON was 552,693 bytes, and its XML was 327,099 bytes.

Call traces covered both conversion directions, filtered semantic search, and the special dot ID projection.

No teammate edited production source or tests. Scratch fixtures and measurement harnesses stayed under `/tmp`.

## Remaining risks

The conversion journey had no observed direct shell-history use. Its reuse condition must be checked in the next remap.

The shell history belongs to one developer. It can miss pipelines, scripts, deleted history, and other users.

The current tests do not pin exact XML-to-JSON legacy bytes. The rewrite team must close this gap before code.

No current test proves that scoped launcher use starts no Python. The first slice must add direct process proof.

Native launcher routing can regress legacy commands. Package and real-launcher tests must cover that temporary seam.

Python regular expressions and Unicode case folding remain a large search risk. Rust `regex` alone does not match the full contract.

Rich parity remains a large session and search risk. It covers terminal width, Markdown, syntax, ANSI, paging, and early pager close.

The live session corpus changes during work. Later profiles must record a new snapshot instead of treating these times as permanent.

## Crew convergence

The mapper reviewed the complete draft and both final revisions.

The scout verified the product contract, both valid empty cases, temporary legacy routing, and the exact boundary.

The profiler verified product ordering, cost claims, proof, risks, temporary routing, empty cases, and the performance target.

All three teammates accept this integrated result and the exact first rewrite boundary.

## Exact next boundary

Build a tests-first native `ch parse [FILE] [-f xml|json]` journey through the real installed `ch` executable.

Before production code, add process-level tests that do all of the following:

1. Pin exact legacy XML-to-JSON stdout for all 15 stored XML fixtures.
2. Keep the 15 existing JSON-to-XML byte oracles.
3. Cover file and stdin input in both directions.
4. Pin help, argument order, invalid choices, extra arguments, stderr, and exit status.
5. Pin representative JSON, XML, UTF-8, and file failures byte for byte.
6. Pin `[]` to XML as status 0 with empty stdout and stderr.
7. Pin empty XML to JSON as status 0 with stdout `[]\n` and empty stderr.
8. Prove every successful stderr is empty and every non-empty stdout has exactly one final newline.
9. Prove the installed conversion route starts no Python process.
10. Prove default session parse, search, and legacy commands still route unchanged.

Then implement only the boundary needed for those tests:

1. Install a real Rust executable at the public `ch` path.
2. Route exact `ch parse` to Rust without Python.
3. Implement one reusable canonical message model and the required tool schemas.
4. Implement strict structured JSON decoding and canonical XML decoding.
5. Implement exact XML and structured JSON projections.
6. Preserve exact output, error text, and exit status.
7. Route all other public shapes to a private unchanged legacy entry.

For exact `ch parse`, do not start, import, embed, call, or fall back to Python. Do not keep a second conversion authority.

Run all 15 fixture pairs and the exact failure corpus through the installed launcher.

Use the 552,693-byte JSON and 327,099-byte XML real fixture for performance acceptance. Prime once, then run seven interleaved conversions per direction.

Require exact byte parity and a warm median of at most 60 ms for both large-fixture directions.

After acceptance, remap all three journeys before choosing the next rewrite boundary.
