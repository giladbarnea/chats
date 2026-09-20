# `ch search` performance configuration map

> Historical research artifact from September 9, 2026. Later performance commits changed scheduling and costs. Use current code and README for present behavior.

## A flat list cannot be finite

A `ch search` performance configuration is not only a CLI flag set. The query can contain an arbitrarily large Boolean tree or regex program.

Tool filters can also contain an arbitrary number of rules. Corpus outcomes decide which branches run for each file.

The exhaustive map is therefore a product model. **Each legal tuple below is one separate performance configuration.**

```text
Configuration = Query × Visibility × Pool × PathScreen × Output × Environment × Workload
```

This model collapses only spellings that normalize to the same runtime state. It does not collapse branches that only look similar from the CLI.

## 0. Four configurations stop before file scanning

| ID | Representative command | Last work performed |
|---|---|---|
| X1 | `ch search --help` | Parse arguments and render help |
| X2 | `ch search`, an invalid option, or an invalid flag value | Parse arguments and render an argument error |
| X3 | `ch search 'alpha AND'` | Parse arguments, compile the query grammar, and render a query error |
| X4 | `ch search needle -p PROVIDER_WITH_NO_FILES` | Compile the query and discover the full pool, then exit silently |

Invalid regex syntax is not X3. It falls back to a literal and continues through search.

## 1. The query selects the candidate-gate schedule

`rust/search_run.rs:350` makes the top-level scheduling decision.

1. The exact `.` plus eligible `-ll` shape uses the special projection.
2. One eligible term uses a 256-file parallel candidate gate.
3. Every other query uses a one-file serial candidate gate.

### 1.1 Single-term classes

| ID | Representative query | Candidate-gate profile | Confirmation regex profile |
|---|---|---|---|
| Q1 | `ch search "simple string"` | 256-file parallel logical-JSON scan | Literal with a required-literal precheck |
| Q2 | `ch search ''` | 256-file windows, but the empty needle accepts without candidate file I/O | Empty regex can match immediately |
| Q3 | `ch search 'open('` | Invalid regex falls back to a literal, then uses the Q1 gate | Escaped-literal regex |
| Q4 | `ch search -s 'needle'` | One file at a time, using `memmem` for a case-sensitive needle of at most eight bytes | Case-sensitive literal |
| Q5 | `ch search -s 'simple string'` | One file at a time, using the custom skip-table scanner | Case-sensitive literal |
| Q6 | `ch search --only-user 'simple string'` | One file at a time, using the custom skip-table scanner | Literal against user-visible messages plus facets |
| Q7 | `ch search 'a/b'` | Q1 in the default case. It becomes full deferral under `-s` or a role filter | Literal |
| Q8 | `ch search 'say "hi"'` | No candidate file scan. JSON decoding can change the text | Literal |
| Q9 | `ch search 'back\slash'` | No candidate file scan | Regex when valid, otherwise literal fallback |
| Q10 | `ch search '<user-message'` | No candidate file scan. The renderer can generate tag-like text | Literal |
| Q11 | `ch search '```'` | No candidate file scan. The renderer can generate fences | Literal |
| Q12 | `ch search 'café'` | No candidate file scan because the literal is non-ASCII | Unicode literal |
| Q13 | `ch search 'error.*timeout'` | No candidate file scan | Regex VM, with a required-literal precheck |
| Q14 | `ch search 'error|timeout'` | No candidate file scan | Regex VM without a required literal |
| Q15 | `ch search '.'` | No candidate file scan | Regex VM without a required literal |
| Q16 | `ch search '(?:a|a)*b'` | No candidate file scan | Backtracking VM can reach its step budget |

Q1 requires all of these conditions:

1. The query root is one `Term`.
2. The term has a literal candidate.
3. Matching is case-insensitive.
4. The pattern is ASCII.
5. The pattern has no quote, backslash, or control character.
6. The pattern has no render-dependent token.
7. Message selection is unrestricted.
8. Thinking, tools, agents, custom records, branches, and plans are off.
9. Global shortening and thinking shortening are off.

The render-dependent tokens are `<`, `="`, triple backticks, `old_string:`, and `new_string:`.

The parallel logical-JSON gate supports `/`. The serial byte gate does not, because JSON can store it as `\/`.

An invalid regex can still enter Q1 after literal fallback. A valid regex-shaped pattern has no literal candidate, even when it behaves like a literal.

### 1.2 Boolean query classes

Boolean queries always use one-file candidate windows. Each operand keeps its own term class.

| ID | Representative query | Per-file candidate work |
|---|---|---|
| Q17 | `alpha AND beta` | Scan terms in order until one cannot match |
| Q18 | `alpha OR beta` | Scan terms in order until one can match |
| Q19 | `alpha NOT beta` | Scan only the positive term. The negative term always passes the candidate gate |
| Q20 | `alpha AND beta AND gamma` | Up to three separate file opens and scans |
| Q21 | `alpha OR beta OR gamma` | Between one and three separate file opens and scans |
| Q22 | `(alpha OR beta) AND gamma` | Recursive short-circuiting follows the exact tree |
| Q23 | `alpha AND (beta OR gamma)` | A different short-circuit order from Q22 |
| Q24 | `alpha AND 'error.*timeout'` | The regex term defers. The literal term can still reject |
| Q25 | `'error.*timeout' OR alpha` | The first deferred term makes every file a candidate. The literal gate is never reached |
| Q26 | `alpha OR 'error.*timeout'` | The literal can answer first. The regex term admits every literal miss |

`AND`, `OR`, and `NOT` are syntax only when uppercase. The Boolean tokenizer removes matching quote delimiters around a term.

Without an uppercase operator, quote characters remain part of the regex pattern. An unterminated quote also stays in one term.

The query tree is unbounded. Its exact AST, operand order, and ordered term classes form the complete query configuration.

### 1.3 Special dot projection

The projection runs only when all conditions below hold:

1. The query is exactly `.`.
2. Effective output mode is `OnlyId`.
3. Raw output is off.
4. Visibility is the default.
5. Shortening is off.
6. Directory and date filters are absent.

A provider filter and either case flag are allowed. `--no-metadata`, color flags, paging flags, `-l`, and `-f` are inert after `-ll` wins precedence.

The projection itself has provider-specific branches:

- Claude files always fall back to full confirmation.
- Pi and Codex files scan JSON lines until default-visible content appears.
- A projected Pi or Codex hit rereads and decodes the file to get its native session ID.
- An uncertain or unreadable file falls back to full confirmation.

Adding `-d`, `-ma`, `-ca`, `-a`, `-b`, `-T`, `-t`, `--plans`, `-A`, `--short`, or a role filter disables the projection.

## 2. Visibility forms an independent configuration vector

Use this normalized vector:

```text
V = roles × thinking × tools × agents × branches × custom × plans × globalShort
```

| Component | Runtime states |
|---|---|
| roles | `all`, `only-user`, `only-assistant`, `none` |
| thinking | `off`, `full`, `short` |
| tools | `off`, `all`, ordered filter list |
| agents | `off`, `on` |
| branches | `off`, `on` |
| custom | `off`, `on` |
| plans | `off`, `on` |
| globalShort | `off`, `fixed(N)`, `progressive(N)` |

Every legal combination is separate because it changes parsed content, rendered search text, or both.

The candidate-gate consequences are simpler:

- Default visibility permits Q1 batching.
- A role restriction alone changes Q1 into a serial byte scan.
- Any enabled extra, branch visibility, or shortening makes all terms defer.

`-a` also retains Claude sidechain files in the pool. `-A` enables thinking, all tools, agents, custom records, branches, and plans.

A role-only flag overrides `-T`, `-t`, `-a`, `--plans`, and `-A`. It does not override explicit `-b` or global `--short`.

Tool filters add an unbounded ordered subconfiguration. Relevant states include:

1. All tools through bare `-t`.
2. A positive allowlist.
3. A negative-only blocklist.
4. Mixed positive and negative filters.
5. Name, direction, and error criteria.
6. Fixed local shortening.
7. Progressive local shortening.
8. Multiple matching short rules, where specificity and order select the policy.

All tool-requested states parse provider tool payloads before applying the display filter. Codex also parses generated tool-call scripts.

## 3. Pool and path-screen configurations

The provider scope has four states:

```text
P0 = all providers
P1 = Claude
P2 = Pi
P3 = Codex
```

Provider filtering happens after full inventory discovery. It narrows the scan list, but it does not avoid walking all provider roots.

The path screen has eight valid structural states:

| ID | Flags | Per-path order |
|---|---|---|
| F0 | none | No path file I/O |
| F1 | `-d DIR` | Read forward until `cwd` |
| F2 | `-ma DATE` | Parse the date and scan backward for the last timestamp |
| F3 | `-ma DATE -d DIR` | Modified-time probe, then `cwd` on survivors |
| F4 | `-ca DATE` | Parse the date and scan forward for the first timestamp |
| F5 | `-ca DATE -d DIR` | Created-time probe, then `cwd` on survivors |
| F6 | `-ma DATE -ca DATE` | Modified-time probe, then created-time probe on survivors |
| F7 | `-ma DATE -ca DATE -d DIR` | Modified time, created time, then `cwd` |

`P0..P3 × F0..F7` gives **32 separate pool and path-screen configurations**. Each combines with every query, visibility, and output configuration.

Date parsing occurs once per reached path. An invalid date therefore adds error configurations:

- Invalid `-ma` fails at every reached path.
- Invalid `-ca` fails at every path that reaches it.
- A rejecting valid `-ma` prevents `-ca` parsing.
- An empty date is invalid, although no-results wording treats it as an empty filter.

Threshold selectivity changes how many files reach later nodes. That selectivity belongs to the workload state.

## 4. Confirmation has four decoder profiles

Every candidate that reaches confirmation pays a complete file read and format detection.

| ID | Content profile | Decoder |
|---|---|---|
| D1 | Claude JSONL | `session::parse_claude` |
| D2 | Pi JSONL | `session::parse_pi` |
| D3 | Codex JSONL | `codex::parse_codex` |
| D4 | First nonblank line lacks a typed JSON object | `raw_transcript::parse_raw_cli_transcript` |

All JSONL profiles first decode every valid JSON object into memory.

Claude always computes the branch map, even when branches stay hidden. Pi has inline-skill and custom-agent paths.

Codex coalesces assistant records. Tool visibility activates function-call and generated-script parsing.

After provider decoding, confirmation always performs these steps:

1. Build a tool ID map.
2. Compute progressive positions over all messages.
3. Clone each visible message projection.
4. Render every projected message to semantic inner XML.
5. Evaluate the query over summaries, the current title, and rendered messages.
6. If matched, run a second positive-term pass to collect displayed matches.
7. If matched, reopen the file for first and last timestamp metadata.

`-l`, `-ll`, and `--no-metadata` do not skip these steps. Only the special dot projection bypasses normal confirmation.

## 5. Output has twenty normalized profiles

The output mode precedence is `-ll`, then `-l`, then `-f`, then matches.

Raw output branches before the ordinary sinks. Therefore, `-r -l` and `-r -ll` render matching bodies like bare `-r`.

| ID | Representative suffix | Sink and output work |
|---|---|---|
| O1 | `--color never` | Plain matching messages, metadata on, streamed |
| O2 | `--color never --no-metadata` | Plain matching messages, metadata off, streamed |
| O3 | `-f --color never` | Plain full conversations, metadata on, streamed |
| O4 | `-f --color never --no-metadata` | Plain full conversations, metadata off, streamed |
| O5 | `-l --color never` | Plain rule plus metadata, streamed |
| O6 | `-l --color never --no-metadata` | Plain rule only, streamed |
| O7 | `-ll` | Plain ID lines with per-line flushes |
| O8 | `--color always --no-paging` | Colored matching panels, metadata on, direct stream |
| O9 | `--color always --no-paging --no-metadata` | Colored matching panels, metadata off, direct stream |
| O10 | `--color always` | Colored matching panels, metadata on, pager stream |
| O11 | `--color always --no-metadata` | Colored matching panels, metadata off, pager stream |
| O12 | `-f --color always --no-paging` | Colored full panels, metadata on, direct stream |
| O13 | `-f --color always --no-paging --no-metadata` | Colored full panels, metadata off, direct stream |
| O14 | `-f --color always` | Colored full panels, metadata on, pager stream |
| O15 | `-f --color always --no-metadata` | Colored full panels, metadata off, pager stream |
| O16 | `-l --color always --no-paging` | Colored list rows and trailing summary, direct stream |
| O17 | `-l --color always` | Colored list rows and trailing summary, pager stream |
| O18 | `-r` or `-r -l` | Matching-message raw output, all hits cloned and buffered |
| O19 | `-r -f` | Full-conversation raw output, all hits cloned and buffered |
| O20 | `-r -ll` | The O18 body path, but an empty result suppresses the no-results hint |

`--no-metadata` is inert in colored list mode, ID mode, and raw mode. It does not stop timestamp metadata reads during confirmation.

`--color auto` maps to a colored profile on a stdout terminal. It maps to a plain profile when stdout is redirected.

Paging only changes colored list and panel profiles. `--paging` is inert on a plain profile.

Colored panel output adds Markdown parsing, wrapping, cell measurement, query highlighting, and optional syntax highlighting. Full mode repeats this work for every visible message.

Colored list output does not render message bodies. It still pays the same confirmation work before the sink.

## 6. Environment and consumer states remain separate

The same CLI arguments can select different output profiles through ambient state.

```text
E = stdoutTTY × pagerAvailable × consumerBehavior × width × colorTier × unicodeWidthTable
```

Relevant states are:

- Stdout terminal versus pipe under `--color auto`.
- Pager available versus stdout fallback.
- Consumer reads all output versus closes early.
- Terminal width and `COLUMNS`.
- Suppressed, attributes-only, 16-color, 256-color, and truecolor rendering.
- The selected `UNICODE_VERSION` width table.

A pager quit or broken output pipe stops the scan. Completion measurements must state whether the consumer read all results.

## 7. Corpus outcomes are dynamic configurations

Arguments alone do not determine the executed call graph. Each file takes one terminal edge.

| ID | Per-file terminal edge |
|---|---|
| W0 | The selected provider partition is empty, so scanning never starts |
| W1 | Provider partition excludes the file |
| W2 | Modified-time screen rejects it |
| W3 | Created-time screen rejects it |
| W4 | Directory screen rejects it |
| W5 | Candidate gate rejects after a full miss scan |
| W6 | Candidate gate accepts after an early raw hit |
| W7 | Candidate gate defers because of a case-risk scalar, JSON escape evidence, invalid UTF-8, or Pi-agent evidence |
| W8 | Confirmation decodes and rejects the session |
| W9 | Confirmation finds one or more summary matches |
| W10 | Confirmation finds a current-title match |
| W11 | Confirmation finds one or more message matches |
| W12 | File processing fails and emits an error |
| W13 | Regex evaluation exhausts its step budget |

W9, W10, and W11 can occur together for one hit. A complete workload state records file counts and bytes on each edge. It also records term position, hit position, session size, and rendered-message volume.

The same command can be candidate-gate-bound, decode-bound, regex-bound, or output-bound under different workload states.

## 8. Ordered configuration spine

This is a readable walk through the product space. It is not a replacement for the tuple product above.

1. `ch search 'simple string'`
2. `ch search 'simple string' -l`
3. `ch search 'simple string' -ll`
4. `ch search 'simple string' -f`
5. `ch search 'simple string' -r`
6. `ch search -s 'simple string'`
7. `ch search 'café'`
8. `ch search 'error.*timeout'`
9. `ch search 'error|timeout'`
10. `ch search 'open('`
11. `ch search '.' -ll`
12. `ch search '.' -ll -d DIR`
13. `ch search 'alpha AND beta'`
14. `ch search 'alpha AND beta' -l`
15. `ch search 'alpha OR beta' -l`
16. `ch search 'alpha NOT beta' -l`
17. `ch search '(alpha OR beta) AND gamma' -l`
18. `ch search 'simple string' --only-user`
19. `ch search 'simple string' --only-assistant`
20. `ch search 'simple string' --only-user --only-assistant`
21. `ch search 'simple string' -T`
22. `ch search 'simple string' -T short`
23. `ch search 'simple string' -t`
24. `ch search 'simple string' -t 'Read:o:s=p=80'`
25. `ch search 'simple string' -a`
26. `ch search 'simple string' -b`
27. `ch search 'simple string' --plans`
28. `ch search 'simple string' -A`
29. `ch search 'simple string' --short=128`
30. `ch search 'simple string' --short=p=128`
31. `ch search 'simple string' -p claude`
32. `ch search 'simple string' -p pi`
33. `ch search 'simple string' -p codex`
34. `ch search 'simple string' -ma 1d`
35. `ch search 'simple string' -ca 1w`
36. `ch search 'simple string' -ma 1d -ca 1w`
37. `ch search 'simple string' -d DIR`
38. `ch search 'simple string' -p pi -ma 1d -ca 1w -d DIR`
39. `ch search 'simple string' --color always --no-paging`
40. `ch search 'simple string' -f -t -a --short=p=128 --color always`

For exhaustive enumeration, replace each item with its full legal cross-product across the other dimensions.

## 9. The earlier measured command

`ch search 'lightweight AND Terminal' -l` has this signature on an ordinary interactive terminal:

```text
Query       = Q17, two case-insensitive ASCII literal terms
Visibility  = default
Pool        = all providers, main sessions only
PathScreen  = F0
Output      = O17 when paging stays enabled, or O16 when paging is disabled
Environment = terminal-dependent
Workload    = the measured live-corpus edge distribution
```

Its `AND` root disables the 256-file gate. Each path uses up to two serial candidate file scans before confirmation.

The `-l` flag changes only the output sink. It does not reduce confirmation work.

## 10. Source anchors and validation

- Argument normalization: `rust/search/parse.rs:444-532`
- Search assembly and sink selection: `rust/search_run.rs:25-215`
- Batch decision: `rust/search_run.rs:349-358`
- Dot projection: `rust/search_run.rs:449-594`
- Term and regex compilation: `rust/search_query.rs:111-170`, `rust/search_query.rs:1790-2041`
- Query AST parsing: `rust/search_query.rs:2042-2200`
- Candidate-gate eligibility: `rust/search_output.rs:836-866`
- Boolean candidate evaluation: `rust/search_output.rs:991-1140`
- Path screens: `rust/search/plan.rs:142-190`
- Scan loop: `rust/search_engine.rs:117-220`
- Confirmation: `rust/search_confirm.rs:252-336`
- Session decoding: `rust/search_confirm.rs:343-390`
- Semantic rendering: `rust/search_confirm.rs:446-472`
- Output sinks: `rust/search_output.rs`, `rust/search_views.rs`

A focused probe confirmed two non-obvious normalizations:

1. `-r`, `-r -l`, and `-r -ll` produced identical matching-body output on the contract fixture.
2. Colored `-l` produced identical output with and without `--no-metadata`.
