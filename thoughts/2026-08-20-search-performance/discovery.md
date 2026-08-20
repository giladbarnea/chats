---
date: 2026-08-20
baseline: ce79be1
status: accepted
---

# Search performance discovery

## Decision

The reported search is slow for a specific, avoidable reason. The slash makes the query unsafe for the current raw candidate gate. The command therefore decodes and parses 5.576 GB across 3,234 sessions before it can print three IDs.

The current 16 to 20 second completion time is not inherent to this search class. A subsecond first ID needs only explicit output flushing through the pipe. Low-single-digit warm completion is credible if candidate selection becomes precise and batched. Consistent subsecond completion as the corpus grows needs incremental state or a narrower search pool. A scan-only design must still read the selected bytes.

Do not start with a parser rewrite. The highest-value boundary is candidate selection for default, case-insensitive literal searches. The design must handle JSON escapes locally instead of deferring an entire file. It must also replace the current slow file-at-a-time candidate scan.

## Baseline and method

The repository was clean at `ce79be1`. The installed `ch` launcher used this editable checkout and the live native module. The live main-session corpus changed independently of the repository.

Three sequential installed-launcher runs used a warm filesystem cache. They took 16.65, 16.12, and 16.05 seconds. No measurement claimed a cold cache. Transient runtime instrumentation changed no production file or test.

The exact command was:

```sh
ch search 'CLIENT_ID/CARD' -ca 2m -ll | cat
```

It returned three IDs.

## What the command means

`CLIENT_ID/CARD` is one default case-insensitive Python regular expression. Every character has literal regex meaning here. The shell quotes only protect the pattern from shell interpretation.

`-ca 2m` keeps sessions whose first in-band timestamp is after the relative cutoff. It probes that timestamp for every candidate file before content parsing.

`-ll` changes output to session IDs. It still builds a full `SessionScan` for all 3,234 date-passing files. It then loads conversation metadata for each of the three hits. That metadata work took 0.0006 seconds total. The narrow `search . -ll` projection does not apply with this pattern and date filter.

The pipe does not change search computation. It does change observed latency. Python block-buffers the three short ID lines when stdout is a pipe. Without shell `pipefail`, `cat` also replaces the observable `ch` exit status with its own.

Normal `| cat` showed all IDs at 15.995 seconds and finished at 16.07 seconds. With unbuffered Python, IDs appeared at 0.402, 10.202, and 14.096 seconds. That run finished at 16.52 seconds.

## Exact cost

| Measure | Result |
| --- | ---: |
| Main session files | 4,895 |
| Main corpus bytes | 6.378 GB |
| Files passing `-ca 2m` | 3,234, or 66.1% |
| Bytes passing `-ca 2m` | 5.576 GB, or 87.4% |
| Native candidate-gate calls | 0 |
| Full `SessionScan` calls | 3,234 |
| Visible messages tested | 32,706 |
| Matching IDs | 3 |
| Warm wall time, three runs | 16.05 to 16.65 seconds |
| User CPU time | 14.38 to 14.49 seconds |
| System CPU time | 1.56 to 1.69 seconds |

An instrumented 22.04 second run attributed 0.098 seconds to discovery and 0.889 seconds to date probes. Full text reads took 3.960 seconds. `SessionScan` decoding and parsing took 13.286 seconds. Semantic rendering took 0.039 seconds. Hit metadata took 0.0006 seconds.

A separate `cProfile` run added overhead but found the same shape. Line splitting took 7.70 seconds. `orjson.loads` took 4.64 seconds. Reads took 3.24 seconds. UTF-8 decoding took 1.37 seconds.

The dominant cost is full JSONL decoding and parsing. Discovery, hit metadata, ID formatting, and semantic rendering are not material. The CPU totals nearly equal wall time, so this warm run is mainly single-process CPU work.

The date filter removes one-third of files but only 12.6% of bytes. This explains its limited effect. Without the date filter, the query took 19.43 seconds across 4,895 files and 6.381 GB. The same query with `-p claude` scanned a 382-file, 0.376 GB provider pool in 3.04 seconds. It returned one ID.

The live corpus grew by a few megabytes during discovery. Exact-command attribution used the 5.576 GB snapshot. Later candidate isolation used 5.578 GB.

## Why the candidate gate does not help

Search first parses the query and builds the session pool. It applies provider, date, and directory filters before full parsing. It then uses a native raw candidate gate only when raw absence can safely prove semantic absence.

JSON permits `/` to appear as either `/` or `\/`. A rendered `CLIENT_ID/CARD` match can therefore exist without the raw unescaped needle. `_term_can_change_under_json_decoding` correctly bypasses raw rejection for this query. Every date-passing file reaches full semantic confirmation.

A simple slash whitelist is not sufficient. A native-equivalent safe-literal gate took 9.83 seconds across the 3,234 selected files. It conservatively passed 601 files. Semantic confirmation of those files took another 8.27 seconds and found no hits.

The 601 survivors contain 519 files with raw `\u` evidence, totaling 2.413 GB. They also contain 121 files with the Pi `"pi-user-agents"` marker, totaling 0.333 GB, with overlap. Thirteen more files survived Unicode-risk or invalid-UTF checks. The union is 2.588 GB, or 46.4% of selected bytes.

A Unicode escape can encode any ASCII query character, so the current conservative model parses each whole evidence file. The safe no-hit control `ch search 'PROFILEPROBEQZXWCV' -ca 2m -ll | cat` took 17.47 seconds. The gate first scans selected bytes, then survivors receive another full semantic read and parse.

## Feasibility bound

A transient case-insensitive fixed-string scan searched both `CLIENT_ID/CARD` and `CLIENT_ID\/CARD`. It found 103 of the 3,234 date-passing files. Those files total 148 MB. No file contained the escaped slash form.

Running the existing semantic matcher on those 103 files reproduced the same three IDs in 0.605 seconds. A separate batched `rg` scan of the selected files took 0.26 seconds with a warm cache.

This is a useful bound, not a production prototype. Raw matching does not preserve visible-message, JSON-decoding, Unicode, provider-normalization, or branch semantics. It also misses arbitrary `\u` encodings unless candidate selection decodes or narrows them safely.

The bound still proves large avoidable amplification. Only 3.2% of date-passing files and 2.7% of their bytes contain either observed raw slash form. Only three of those 103 files are semantic hits.

## Search shapes and scaling

| Search shape | Current work | Scaling driver |
| --- | --- | --- |
| This default slash literal | Date gate, then full semantic scan | All date-passing bytes |
| Safe default ASCII literal | Raw scan, then semantic survivors | Selected bytes plus conservative-survivor bytes |
| Regex, non-ASCII, shortening, or render-dependent visibility | Full semantic scan | All filtered bytes and messages |
| Boolean query | Session-wide term evaluation | Positive-term candidates plus semantic survivors |
| `NOT` query | Conservative exclusion confirmation | All facets needed to disprove exclusions |
| Exact `search . -ll` projection | Narrow native projection | Files, with semantic fallbacks |
| Provider or directory constrained search | Early pool reduction or cwd probes | Remaining files and bytes |

Completion cost follows bytes more than file count. The current path processes files serially in newest filesystem-mtime order. Memory scales mainly with the largest file being decoded, not total corpus size.

Matching semantics are broader than raw grep. Search evaluates all summaries, the latest title, and rendered visible messages. Role filters do not remove summaries or titles. Visibility rules hide protocol, tools, thinking, agents, branches, and plans unless requested. Provider normalization can generate searchable rendered text that raw bytes do not contain.

The raw candidate gate is only a conservative rejection step. It can never declare a hit. Every survivor must use the semantic matcher.

## Simplest high-impact opportunities

1. **Flush streamed ID output for first-result UX.** This makes the exact piped command show its first ID near 0.4 seconds. It does not improve search speed or completion time.

2. **Fix candidate amplification before rewriting parsing.** Make common slash literals eligible without losing escaped-slash, `\u`, Unicode case-insensitive, generated-content, or provider parity. Avoid whole-file uncertainty when the uncertain bytes are unrelated to the query.

3. **Batch candidate work.** The current native-equivalent gate took 9.83 seconds. The 0.26 second batched raw scan shows this is not a hardware lower bound. Keep semantic confirmation for survivors and preserve newest-first output.

4. **Reassess the date probe after candidate work.** Its current cost is about one second. It becomes important only after removing the 13-second semantic parse.

5. **Use incremental state only for a strict subsecond completion goal.** A content scan remains proportional to selected bytes. An index adds invalidation and semantic-projection complexity, so first measure the simpler boundary.

Do not prioritize discovery, metadata loading, rendering, or ID formatting. Together they are negligible here. Parallel full parsing also does more work and raises memory pressure before candidate amplification is fixed.

## Constraints for the next team

A response must keep the full semantic matcher authoritative. It must preserve summaries, latest-title behavior, message visibility, branch selection, provider normalization, and newest-first IDs.

Candidate parity must cover raw `/`, escaped `\/`, `\u002F`, escapes in other query characters, and invalid UTF-8. It must also cover Python case-insensitive Unicode risks, default joined Pi-agent evidence, and other generated provider or tool content.

Measure two user outcomes separately. Record first visible ID through the real pipe. Record full completion and exact ID order.

Compare every optimized result with a no-gate semantic reference. Use the exact installed launcher and current live corpus. State cache conditions without calling an unprimed run cold.
