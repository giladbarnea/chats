# Cycle 01 measured-cost profile

## Baseline

The code baseline is `95f1891bc5bc` on `main`. No tracked production or test file had changes before profiling.

The real launcher was `/Users/giladbarnea/.local/bin/ch`. It entered the editable checkout through CPython 3.14.7 and `chats.cli`.

The native extension SHA-256 was `3cdb85fe2acec4e6cc5e728bbe630c677aa41116333cd813268910eeb4b39499`. Measurements ran on an Apple M2 Pro with macOS 26.3.1.

Every timing used the real launcher. Each shape had one unmeasured priming run before sequential warm-cache measurements.

The machine also hosted the scout and mapper processes. Absolute startup time varied under contention, so ordering uses interleaved medians and component attribution.

The accepted scope contains three exact journeys:

1. `ch search ...`
2. Default session parse through `ch [SESSION] [SLICE...] ...`
3. Provider-free conversion through `ch parse [FILE] [-f xml|json]`

## Repeatable inputs

The search snapshot contained 4,907 main session files and 6,442,031,239 bytes.

| Provider | Files | Bytes |
| --- | ---: | ---: |
| Claude | 379 | 372,695,497 |
| Pi | 3,322 | 3,731,661,157 |
| Codex | 1,206 | 2,337,674,585 |

The profile created three transport inputs from real Pi sessions for this checkout. The export command was `ch "$SOURCE" -t:s --agents -f json`.

| Label | Session ID | Native JSONL | Structured JSON | Messages | XML | Structured JSON SHA-256 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Small | `01a0150d-56f1-7343-bd96-4c19685af1de` | 624,908 B | 179,436 B | 218 | 100,527 B | `036bd028341a4a6c91e92a7021f6a16a2e210a3a2e020e532fd4859cc197037d` |
| Medium | `01a01de3-021a-7f83-8e5e-8cc187093788` | 1,270,658 B | 152,561 B | 133 | 84,006 B | `7b5caeaf8933f7518c4eafb12928b08567cee606f6cdb9ef44c135f7b9f5b194` |
| Large | `019ef3f8-272e-7c18-bfd9-d4aac7f3c976` | 4,566,311 B | 552,693 B | 648 | 327,099 B | `be0bfacf29e2d0fdc29a27bd55c713ca6dd3d121987b18578fd453967223e76e` |

The small, medium, and large sources were near the 10th, 50th, and 99th raw-size percentiles in the then-current checkout Pi set.

## Findings

### Product use orders default session parse first

The scout found 195 in-scope direct invocations in the local shell history. This is one-user directional evidence, not telemetry.

Default session parse accounted for 133 calls. Search accounted for 62 calls, and 54 search calls used a pool filter.

Search used matches mode in 51 calls. Exact `ch parse` conversion had no observed direct call.

This use evidence orders default session parse first, filtered search second, and conversion third.

### Python startup dominates short parse journeys

An exact import-time trace attributed 163 ms to `chats.cli`. The trace loaded 571 modules, including NLTK through unrelated command imports.

| Exact real-launcher shape | Warm median | Runs | Result |
| --- | ---: | ---: | --- |
| `ch parse --help` | 170.3 ms | 11 | Status 0 |
| Small JSON file to XML | 177.0 ms | 11 | Status 0 |
| Large JSON file to XML | 184.6 ms | 11 | Status 0 |
| Large XML file to JSON | 181.6 ms | 11 | Status 0 |

The large conversions added only 11 to 14 ms above the launcher floor. Startup therefore consumed about 92% of their elapsed time.

A paired file-versus-stdin run found no material input-channel difference. Both paths remained launcher-bound.

One `/usr/bin/time -l` large JSON-to-XML run used 61,227,008 bytes of maximum resident memory.

### Default session parse is frequent and also launcher-bound

| Exact real-launcher shape | Warm median | Runs |
| --- | ---: | ---: |
| Small direct path to plain XML | 182.0 ms | 7 |
| Large direct path to plain XML | 229.7 ms | 7 |
| Large direct path with forced Rich and no pager | 361.5 ms | 7 |
| Medium direct path to plain XML | 189.1 ms | 9 |
| Medium direct path, last-message slice | 189.7 ms | 9 |
| Medium exact session ID to plain XML | 265.4 ms | 7 |
| Newest Pi recent index, ID only | 383.5 ms | 7 |

A direct-path small session spent about 90% of elapsed time before product work. The large plain journey still spent about 71% there.

Exact ID resolution added about 76 ms over the same direct-path session. Recent-index ID resolution added about 213 ms above the launcher floor.

The last-message slice cost the same as full output. The parser decodes and normalizes the whole session before it applies slices.

Forced Rich rendering added 132 ms to the large direct-path journey. Terminal rendering becomes material after startup and decoding for larger output.

One large plain run used 120,635,392 bytes of maximum resident memory.

### Search has the largest measured pain

The history-shaped command was `ch search sluggish -ca 3h`. At measurement time, its former hit had left the relative window.

The command still describes the common product shape. It uses a case-insensitive ASCII literal, a creation filter, and matches output.

| Exact real-launcher shape | Selected corpus | Warm median | Runs | Result |
| --- | ---: | ---: | ---: | --- |
| `ch search sluggish -ca 3h` | 10 files, 11.5 MB | 481 ms | 5 | No match |
| `ch search . -ma 4h --list --color never --no-metadata` | 28 files, 154.1 MB | 859 ms | 5 | Match |
| `ch search search -d /Users/giladbarnea/dev/chats --color never --no-metadata` | 130 files, 195.5 MB | 1.370 s | 5 | Match |
| `ch search PROFILEPROBEQZXWCV -ca 2m -ll` | 3,241 files, 5.637 GB | 2.663 s | 3 | No match |
| `ch search CLIENT_ID/CARD -ca 2m -ll` | 3,241 files, 5.637 GB | 3.229 s | 3 | Three IDs |
| `ch search 'PROFILEPROBEQZXWC[V]' -ca 2m -ll` | 3,241 files, 5.637 GB | 16.014 s | 3 | No match |

The selective literal printed its first ID after a 461 ms median. Completion remained 3.229 seconds.

The 481 ms narrow search selected only 11.5 MB for candidate work. Import, inventory, and timestamp probes over the full 4,907-file pool dominated it.

The regex spelling bypassed the literal gate and forced semantic confirmation. Its 16-second completion is the largest measured product cost.

A one-run component trace excluded import time and discarded output. It found these inclusive costs:

| Component | Literal miss | Selective literal |
| --- | ---: | ---: |
| Command body | 2.462 s | 2.841 s |
| Python semantic confirmation | 1.520 s across 165 files | 1.953 s across 251 files |
| `SessionScan` inside confirmation | 1.119 s | 1.482 s |
| Native batch candidate gate | 0.627 s | 0.607 s |
| Date probes | 0.224 s | 0.194 s |
| Pool discovery | 0.079 s | 0.075 s |
| Hit metadata | None | 0.001 s for three hits |

Conservative survivors now make Python semantic confirmation the largest eligible-literal bucket. Regex searches semantically confirm every selected file.

One literal-miss run used 662,863,872 bytes of maximum resident memory. Its 5.89 user CPU seconds exceeded 3.00 wall seconds because the Rust candidate gate uses Rayon.

## Decisions

Search is the largest direct cost. Default session parse is the most-used journey.

Exact conversion is neither. Its first-slice value comes from architectural coherence, not observed frequency or absolute pain.

Accept exact `ch parse` conversion as the first rewrite slice only because it establishes two shared assets:

1. The real native `ch` launcher and package seam.
2. The single Rust canonical message model and transport codecs that later session and search work reuse.

Another PyO3 helper would not satisfy this decision. A conversion-only model that later paths cannot reuse would also invalidate the ordering.

After conversion, the next remap must compare two candidates. Default session parse has greater observed use, while search has much greater tail cost.

The measured search order is clear. Remove Python semantic confirmation before tuning metadata or result formatting.

The measured default-parse order is also clear. Remove startup first, then resolution and full-session decoding, then large Rich rendering.

## Proof

The timing harness invoked `/Users/giladbarnea/.local/bin/ch` directly. Output went to a pipe or `/dev/null`, except forced-Rich runs.

Search first-result timing read the real launcher pipe one line at a time. The three selective runs returned identical ID order and empty stderr.

`PYTHONPROFILEIMPORTTIME=1` measured the exact launcher import chain. A separate `cProfile` diagnostic confirmed imports dominated both large parse paths.

In-memory wrappers measured search components without changing tracked files. They preserved the real command functions and current native extension.

All scratch fixtures, profiles, and harnesses stayed under `/tmp/ch-cycle-01-profile` or `/tmp`. Profiling changed no production source or test.

No measurement claims a cold filesystem cache. Relative date filters and the live session corpus will change, so a rerun must record its new corpus snapshot.

## Remaining risks

The conversion-first slice has no observed shell-history demand. It must earn its place through reuse in the next two journeys.

The local history belongs to one user. Pipelines, scripts, or removed history can change the true use mix.

The live corpus grew during team work. The final snapshot and filter counts anchor the reported search timings.

Plain redirected output does not measure interactive pager wait time. Forced Rich measured rendering without `less` or user reading time.

Python regular-expression parity remains a large later search risk. The 16-second control proves cost, not a safe partial rewrite boundary.

Native launcher routing can regress legacy commands outside this fleet. Package and real-launcher tests must cover that temporary routing seam.

## Exact next boundary

Build a tests-first native `ch parse [FILE] [-f xml|json]` journey through the real installed `ch` executable.

The boundary includes the Rust launcher, exact arguments, file and stdin input, the shared canonical model, tool schemas, both codecs, output, errors, and exits.

Before production code, pin exact legacy XML-to-JSON stdout for all 15 stored XML fixtures. Keep the 15 JSON-to-XML outputs as byte oracles.

Also pin exact stdout, stderr, and exit status for malformed inputs and argument errors.

The installed `ch parse` process must not start, import, embed, call, or fall back to Python. It must not call a second conversion authority.

Keep default session parse and search behavior unchanged through a private legacy route during this slice.

Use the three real fixture sizes above for acceptance. After one prime, run seven interleaved real-launcher conversions in each direction.

Require exact output parity and a warm median of at most 60 ms for the large fixture in both directions. This is a threefold improvement over baseline.

Then remap all three journeys. Choose between default session parse and search from the new use, cost, and shared-model evidence.
