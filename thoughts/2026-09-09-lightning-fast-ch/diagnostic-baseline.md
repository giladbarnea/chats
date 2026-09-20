# Search diagnostic baseline

Source: sole read-only investigator `5782fa1f-ce40-4da`, gpt-5.6-sol at max thinking, September 9, 2026. This is the Captain's evidence summary, not independent remeasurement. Full returned report is in the Captain session.

## Scope

Investigated installed `ch search 'lightweight AND Terminal' -l` and diagnostic variations, not all search configurations or other commands. No production or installation changes. Installed native Rust executable matched repository binaries, SHA-256 `1f76081cd87a2808e0f6eed0407b98149e0e7212c4b4cedd7f16c529bd8e512f`. It linked no Python library, contained no Python symbols, and a standalone copy searched a synthetic session without ch-legacy or a valid PATH.

## Measurements

Three warm installed runs completed in 18.00, 18.18 and 18.94 seconds. Repeated warm runs reported zero block-input operations, about 15.7 seconds user CPU and 1.75 seconds system CPU, with peak RSS 1.16–1.25 GB.

One coherent phase-profiler run took 19.09 seconds:

| Stage | Seconds |
|---|---:|
| Candidate gate | 11.38 |
| Candidate reads | 2.03 |
| Session decoding | 4.80 |
| Semantic matching and match collection | 0.73 |
| Inventory | 0.084 |
| Visible-text rendering | 0.017 |
| Hit timestamp probes | 0.003 |

JSON decoding accounted for 3.95 seconds and 606,547 JSON objects. A second run measured the gate at 12.51 seconds and confirmation at 8.09 seconds. The custom regex engine consumed about 0.65 seconds.

One coherent corpus had 5,049 files and 7.92 GB. The gate admitted 1,567 files totaling 5.29 GB; 29 became real hits. By provider: Claude 160 files / 119 candidates / 0 hits / 0.18 seconds gate; Pi 3,624 / 831 / 11 / 9.65 seconds; Codex 1,265 / 617 / 18 / 1.55 seconds. Candidate confirmation rendered 39.8 MB of searchable text from 37,641 messages.

Median file size was 155 KB. The 161 files at least 10 MB totaled 4.78 GB; 50 files at least 30 MB totaled 2.92 GB; maximum was 242 MB.

## Causal findings and exploratory experiments

`search_run.rs:350-353` permits batching only for eligible `Query::Term`. The measured `Query::And` uses one-file batches. Each positive term can separately open and scan a file through `search_output.rs:1058-1111` and `scanner.rs:326`. Confirmation is serial at `search_engine.rs:201-205`.

A missing literal took 2.97 seconds. Repeating that literal as `term AND term` took 26.53 seconds; both returned no hits. An isolated experiment changed only candidate predicate scheduling: serial 11.907 seconds versus ten-worker 4.995 and 4.852 seconds. Candidate decisions and order matched. This is an exploratory measurement, not a serious final optimization attempt, target, performance ceiling or chosen solution.

Only 855 files contained both raw terms. Conservative evidence admitted another 712 files. Deferral evidence includes raw Unicode escapes, the Pi custom-agent marker, and twenty Unicode case-matching risk characters. The evidence categories predicted the production candidate counts exactly.

At least 826 raw-both files failed semantic confirmation. Examples included the term in hidden developer/skill content, a hidden attachment and a hidden tool result. One 187 MB Pi session contained no raw lightweight; one Unicode escape forced confirmation. Default search correctly excludes the hidden records.

Confirmation rereads candidates at `search_confirm.rs:254-255`, then decodes JSON lines through `scan_session` and `session::decode_entries`. Output reduction did not eliminate the cost: `-ll` took 17.35 seconds and `-l --no-metadata` 17.37 seconds. Reversing operands did not materially improve totals.

## Limits

The corpus changed during investigation, with hits varying from 29 to 32. The coherent phase and category runs both used 5,049 files and matched candidate counts. Candidate byte totals are file sizes, not exact bytes read before early exits. Allocation attribution and cold-cache behavior were not measured.

One installed PTY run with --no-paging emitted first output at 99.9 ms and completed at 20.58 seconds. The first hit was the active diagnostic conversation, which already contained the query. This does not establish the original command's first-hit latency.

The investigator reported baseline 1,961 passes, 3 skips and 2 PTY-color flakes. The affected file subsequently passed all 241 tests serially. Treat these as baseline observations, not permission to ignore a future failing test.
