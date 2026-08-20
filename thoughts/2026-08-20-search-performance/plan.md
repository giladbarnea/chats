---
date: 2026-08-20
status: proposed
baseline: ce79be1
source: thoughts/2026-08-20-search-performance/discovery.md
---

# Search performance plan

## Goal

Make the reported search fast without changing which sessions match or their order.

The exact command is:

```bash
ch search 'CLIENT_ID/CARD' -ca 2m -ll | cat
```

The accepted warm baseline is 16.05 to 16.65 seconds for three IDs. The current path semantically scans 3,234 files and 5.576 GB.

The plan has one linked scope with two red and green checkpoints. The first checkpoint improves first-ID latency. The second checkpoint fixes completion time.

## Checkpoint 1: Flush streamed IDs

Flush each streamed `-ll` ID at the shared output boundary. This must include the existing dot projection path.

Keep stdout bytes, ID order, exit behavior, and all non-`-ll` output unchanged.

This checkpoint should expose the proven early hit through `| cat`. It does not fix the full 16-second completion time.

## Checkpoint 2: Batch safe candidate selection

Optimize only a single default, unshortened ASCII literal `SearchTerm`. Keep all other search shapes on the current path.

Build fixed, bounded windows in newest-first order. Apply the current date and directory gates before a path enters a window.

Send each window through one native candidate call. Rust may scan the window in parallel, but it must return decisions in input order.

A native decision may reject a file only when rejection is certain. Every candidate or uncertain file must enter the unchanged Python `SessionScan` path.

Confirm survivors sequentially in input order before the next window. This preserves semantic authority, streaming order, and ordered error behavior.

Choose one fixed window size from measurements. Do not add adaptive scheduling or a reorder buffer.

## Native matching boundary

Scan logical JSON string content without parsing JSON objects or building JSON values. Reset the decoder at every string boundary.

Recognize mixed raw and valid JSON-escaped forms of each query character. This includes `/`, `\/`, `\u002F`, and escaped letters or underscores.

Decode a valid high-surrogate and low-surrogate pair as one non-ASCII scalar. Treat malformed or unpaired surrogate sequences as uncertain.

Treat malformed escapes, invalid UTF-8, read uncertainty, and Python 3.14 case-insensitive risk scalars as uncertain.

Retain the current conservative handling for joined Pi content and other generated visible content. These files must still reach semantic confirmation when needed.

Keep quote, backslash, and control-character queries on the old path. Also keep these shapes on the old path:

- regex and boolean queries
- non-ASCII literals
- shortening
- non-default visibility
- any current generated-content bypass

Do not add a public optimization bypass flag. A test-only semantic reference can compare the optimized path with the full confirmation path.

## Tests-first proof

Load `tdd` and `write-tests` before writing tests. Start each checkpoint with a failing behavior test.

Prove these contracts:

1. Piped `-ll` output flushes each ID without changing bytes or order.
2. Raw and mixed JSON escapes cannot cause false rejection.
3. Escapes in any eligible query position work across native chunk boundaries.
4. Valid surrogate pairs decode without broad file deferral.
5. Malformed surrogates, malformed escapes, invalid UTF-8, and read failures defer safely.
6. Python 3.14 case-insensitive risk scalars defer safely.
7. Joined Pi generated content and current visibility rules keep semantic parity.
8. Summaries, current titles, hidden content, and cross-provider fixtures keep current results.
9. Window boundaries and worker completion order cannot change newest-first ID order.
10. Every native survivor still passes through `SessionScan` before it becomes a hit.
11. Ineligible search shapes use the existing path.

Compare optimized IDs and order with a forced full semantic scan. Keep wall-clock limits out of routine CI tests.

## Real-launcher acceptance

Use the installed editable `ch` launcher under Python 3.14. Run one unmeasured priming command before timed warm runs.

Run the exact command three times. Record first-ID time, completion time, selected file count, selected bytes, returned IDs, and cache conditions.

Acceptance requires:

1. IDs and order exactly equal an immediate full semantic reference.
2. Median first visible ID is at most 1.0 second.
3. Median completion is at most 3.0 seconds.
4. No completion run exceeds 4.0 seconds.
5. Median completion is at least four times faster than the immediate semantic reference.

Also measure the accepted no-hit control:

```bash
ch search 'PROFILEPROBEQZXWCV' -ca 2m -ll | cat
```

If the exact command misses the goal, profile the implemented path before adding complexity.

## Rejected scope

Do not add a persistent index or cache. Do not rewrite the semantic parser.

Do not run full semantic parsing in parallel. Do not add an `rg` runtime dependency.

Do not whitelist slash queries or enumerate escape variants. Do not optimize date probes in this effort.

Do not expand batching to regex, boolean, non-ASCII, shortened, or non-default visibility searches.

## Right-sizing checkpoint

The recommended approval is the complete linked scope. Checkpoint 1 must land first inside that scope.

Main may assign only Checkpoint 1 as a smaller scope. Its outcome must state clearly that completion still takes about 16 seconds.

No production work starts until main reads this plan and the accepted discovery report.

## Written outcome

After the assigned scope passes review, write `thoughts/2026-08-20-search-performance/outcome.md`.

Record the assigned scope, behavior proof, exact launcher measurements, remaining costs, and the clean continuation baseline.
