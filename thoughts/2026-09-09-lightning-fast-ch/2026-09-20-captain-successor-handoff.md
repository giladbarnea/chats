# Captain successor handoff

Refreshed directly on **September 21, 2026, 00:39 Israel time**.
This replaces the previous contradictory, append-only handoff. Older Captain notes and teammate prompts are historical.

## 1. Start here

You are the new Astra Captain. Gilad wants autonomous work toward near-instant `ch`, with simple effective decisions and little narration.

**Main and installed `ch` are current and verified. No production change is unfinished.**
The original interactive search now completes in roughly **1.9 seconds**, versus roughly 17 seconds initially, on the fixed corpus.
The 250 ms completion and 100 ms first-output goals remain unmet.

All delivery crews are now **dormant, unclaimed, not live, and not active**, verified with `team_list` during this refresh.
The earlier capacity pause no longer blocks work: `aiuse` now reports a fresh weekly window and ample capacity.
I did not resume engineering while preparing this handoff. The successor can continue under Gilad's standing instruction.

First actions:

1. Run mandatory `memo wake`, then read current `AGENTS.md` and the applicable interaction skills.
2. Check current quota before dispatch. Do not obey an old 95%-used snapshot or wait for its old reset date.
3. Choose a bounded next investigation of remaining within-file work. No next production optimization has been selected.
4. Use a small fresh Sol worker/adversary pair. Recover an old agent only for a missing fact.
5. Restore 30-minute oversight and roughly hourly quota checks during active work.

## 2. Live state verified during this refresh

| Item | Current value |
|---|---|
| Main repository | `/Users/giladbarnea/dev/chats` |
| Main HEAD | `f44f60779449390b7af90e57ea115f9d1670125f` |
| Main tree | `ba15d7692779af77898c32e9cbc401615c480efd` |
| Main branch | `main` |
| Selection worktree | `/Users/giladbarnea/dev/chats-lightning-file-selection` |
| Selection branch / HEAD | `lightning/list-window-eight` / same `f44f607` |
| Historical processing worktree | `/Users/giladbarnea/dev/chats-lightning-session-processing`, `9651e21` |
| Public executable | `/Users/giladbarnea/.local/bin/ch` |
| Resolved executable | `/Users/giladbarnea/.local/share/uv/tools/chats/bin/ch` |
| Installed and main `target/release/ch` SHA-256 | `684c855676dd5a54861e95d8f3b4c212ee3e9b9d6b5655ce22a38c31694727f5` |
| Live uv editable origin | `/Users/giladbarnea/dev/chats` |

The installed/local hashes and live uv receipt were read again during this refresh. No benchmark was rerun.
The prior independent release review also matched the qualified candidate hash and public help output.

Current unrelated dirty state, which must remain intact:

- `.optmem/memory/LOG.txt`
- `.optmem/memory/TREE/2`, `TREE/4`, `TREE/8`
- `AGENTS.md`
- `thoughts/2026-08-19-rust-rewrite/slice-02-backward-timestamp-scanner/decisions.md`
- Untracked `thoughts/2026-09-09-lightning-fast-ch/`

Do not broadly stash, reset, clean, or commit that state. Nothing was pushed in this effort.
Use scoped Git operations. The shared hook rewrites unrelated skill symlinks, so use per-command `git -c core.hooksPath=/dev/null` for scoped commits/integration.

## 3. Quota recovered; the old pause snapshot is obsolete

Fresh `aiuse` result at approximately **00:39 September 21**:

- CODEX weekly used: **2%**, remaining **98%**.
- Burn rate: **0.3329**.
- Target burn rate (`target_rate`): **1.0426**.
- Session-window data: `null`.
- Reported window start: **September 20, 14:33:32 Israel**.
- Reported next reset: **September 27, 14:33:32 Israel**.

This differs from the former 95%-used window and its September 21 reset forecast. Use live data, not an explanation guessed for the reset.
The standing resume condition, target rate >=0.8 with actual capacity, is currently satisfied.

```bash
aiuse -f json | jq '.providers[] | select(.name == "CODEX") | {name, windows}'
```

Watch actual remaining capacity and recent hourly consumption, not only window-average rates.
Soft-pause at target rate <=0.2, or earlier when the remaining budget cannot safely fund work before the next check.
Commit scoped work at a safe boundary. Do not change providers to evade a cap.
After a capacity pause, the standing policy is a 24-hour recheck and resume only at >=0.8 with actual capacity.

The old session scheduled a recheck for **September 21 at about 14:11 Israel**. It may not transfer to a new session.
Do not wait for that stale reminder now that live quota has recovered. Avoid duplicate reminder loops.

## 4. What reached main

The original command is `ch search 'lightweight AND Terminal' -l`, including its default terminal/color route.
Measurements use an immutable 5,077-file, 7.986 GB corpus. They do not guarantee every query or today's larger live corpus.

| Commit | Kept change | Measured result or purpose |
|---|---|---|
| `8a3444a` | Ordered six-path computation through existing gates/parsers. Net 97 runtime lines. | Actual terminal median roughly 17.3 → 8.5 seconds. |
| `607439d` | Existing regex library inside the existing streaming candidate scanner. Net 90 runtime lines. | Roughly 8.6 → 5.4 seconds, exact outputs, lower CPU. |
| `5547237` | Simplified continuous List admission with compact completed rows. Net 224 runtime lines. | Interactive median 2.274 seconds, p95 2.318 seconds on that revision. |
| `9743092` | Three-line ASCII comparison guard, exact patch from `02250b3`. | Roughly 2.18 seconds median. Five pairs per mode, no p95 claim. |
| `826a99d` | Native Codex directory correction, runtime +8/-1. | Restores valid filtered sessions. Fixed no-match Codex directory check 14.335 → 0.265 seconds median. |
| `706ad26` | Reuse validated owned input buffer. Runtime +3/-1. | List 2.183 → 2.094 seconds median; RSS 1.737 → 1.295 GB. |
| `a8a9078` | Borrow supplied nonempty tool maps; hoist PlainSink map construction. Runtime +10/-8. | List neutral. Exact recorded tool-heavy output 5.904 → 2.951 seconds median; CPU 13.825 → 7.786 seconds. |
| `f44f607` | Eight active List tasks only. Other per-file modes remain six. | Interactive median 2.116 → 1.902 seconds; plain 2.105 → 1.880 seconds. |

README-only commits `f7cb3df` and `c446943` document earlier scheduling changes.
**Documentation follow-up:** the last README scheduling edit described six active List tasks. `f44f607` changed only Rust. Check and correct that sentence to eight.

Latest eight-task qualification used four balanced pairs per mode, all retained, no retry or exclusion:

- Every pair improved completion; all output/status/stderr remained exact.
- Interactive CPU median increased 12.16%; plain increased 12.25%.
- Maximum RSS was 1,552,220,160 bytes interactive and 1,484,046,336 bytes plain, below 2 GiB.
- First-output medians were 149.50 ms interactive and 145.64 ms plain.
- The first interactive pair was cold for both arms and stayed in the results. Candidate completion range was 1.876–2.522 seconds.
- This four-pair final check makes **no p95 claim**. Older revision p95 values must not be presented as current p95.

The changes preserved output except the explicitly user-approved Codex directory correction.
Correctness tests and independent reviews passed for the changed behavior. Known old rendering/retired-oracle failures remain baseline drift; the whole legacy suite is not claimed green.

## 5. Current behavior and contracts

- Continuous admission applies to per-file **List** routes, including the original colored terminal command.
- Up to eight tasks are outstanding. Other per-file output modes retain six-file windows.
- Eligible single-literal batching and the dot/Only-ID special path remain unchanged.
- Existing per-file gate, confirmation, and timestamp rereads remain. This is **not** the rejected one-body subsystem.
- Results, file errors, and first Undecidable commit in original scan order.
- Completed List hits become compact rendered rows, rather than retaining full message graphs.
- Closure stops new admission and drains admitted work. Reads cannot cancel synchronously. Wider speculative read-ahead is an accepted tradeoff.
- There is no whole-corpus snapshot or hard memory-byte guarantee from a task-count limit.
- UTF-8 validation occurs before newline normalization. Exact invalid-UTF-8 errors and the borrowed decoder API are preserved.
- Shared nonempty tool maps are borrowed. Empty/None map behavior, off-screen names, and session-wide progressive positions remain unchanged.

## 6. Installation is required after each verified step

Gilad explicitly reversed the initial installation restriction. Current `AGENTS.md` requires:

```bash
cd /Users/giladbarnea/dev/chats
uv tool install --force --editable . --reinstall-package chats
```

Integrate the scoped change into the **original main checkout first**. Then reinstall from that root and verify installed provenance and behavior.
Do not install from the selection worktree. A previous release did exactly that: its binary matched, but main lacked the commits and Python imports pointed at the wrong checkout.
That error was corrected before acceptance. **Binary equality does not prove editable origin or main ancestry.**
No unrelated global package/configuration changes or remote pushes are authorized.

## 7. What to do next, and what is already closed

Gilad's standing instruction is to continue performance work autonomously. The next production change is not preselected.

The remaining completion cost is mostly within-file screening/confirmation work. More coordinator machinery is not justified by current evidence.
Use current-source measurements and total change cost before choosing another implementation. Old serial profiles are composition clues, not current wall-time attribution.
A maintained-library opportunity or smaller representation may be worth investigating, but no private decoder, new dependency, or parser rewrite has been authorized or proved.

**Closed check: do not repeat it.** Clean all-ASCII chunks with no incomplete UTF-8 carry already bypass raw UTF-8/risk-character checking in both scanners.
The logical JSON-string scanner still checks ASCII `\\uXXXX` escapes because they can encode a case-fold-risk scalar. Its backslash search already returns quickly when absent.

Other discarded work must not be revived mechanically:

- The roughly 900-runtime-line one-body subsystem (`55767af`, `36a7375`) missed the default colored terminal route. It was not integrated.
- The custom selective decoder saved too little time for its complexity. Two-pass projection was about twice as slow.
- Required-literal precheck `4a00843` failed its 100 ms stage gate at about 109 ms. Its roughly 200 ms CPU-stage saving did not justify pursuing that local target. It is different from the admitted three-line ASCII guard.
- Filter borrowing and direct Message construction added no useful measured value. They were omitted from the lean copy-removal changes.
- Ten active List tasks were less consistent and cost more CPU/RSS than eight. Do not continue tuning the task count without a new reason.
- Scratch continuous prototype `43a16df` was not shipped. Production `5547237` removed instrumentation and redundant coordination.

Decisions that mattered:

1. Judge the **whole feature** and the actual user route, not the latest tiny patch or a convenient piped benchmark.
2. Rejecting an added prefilter did not reject replacing an existing expensive scanner. The baseline changed the economics.
3. Approximately 898 pending paths were mostly tiny completed misses, not hundreds of message graphs. Falsifying that assumption enabled continuous admission.
4. Preserve exact evidence and report limits. Do not demand a perfectly idle laptop or grow a benchmark framework to avoid making a decision.

## 8. Evidence to read selectively

Most artifacts are ignored under:
`/Users/giladbarnea/dev/chats-lightning-file-selection/target/`

| Directory | Purpose |
|---|---|
| `list-window-final-v1/REPORT.md` | Latest eight-task source, tests, exact timings and resources. |
| `list-window-scratch-v1/` | Six/eight/ten comparison; ten rejected. |
| `processing-input-reuse-step-v1/` | Owned-buffer production evidence. |
| `processing-map-borrow-step-v1/` | Map borrowing/hoist production evidence. |
| `processing-current-main-feasibility-v1/` | Component comparison and lean design choice. |
| `continuous-admission-list-v1/REPORT.md` | Simplified continuous List qualification. |
| `streaming-regex-matcher-production-qualification-v1/REPORT.md` | Scanner qualification. |
| `main-path-six-production-qualification-v1/REPORT.md` | First retained concurrency qualification. |
| `ascii-literal-guard-v1/five-pair-measurement-v1/` | Three-line comparison. |
| `codex-cwd-delivery-v1/` | Directory correction and narrowly scoped timing claim. |
| `current-main-free-running-memory-model-v1/` | Corrected backlog/active-memory model. |

Main-side evidence:

- `target/list-window-eight-release-v1/`: final main/install/qualified identity and smoke.
- `target/processing-release-correction-v1/`: corrected main ancestry and editable origin.

The preserved corpus is `target/selection-bench/home` in the selection worktree, with sibling manifest/environment files.
Keep its exact path and pinned environment when comparing old evidence. Path relocation once invalidated an event digest because it included absolute paths.

No existing qualified benchmark needs rerunning merely for this handoff. If an artifact is missing, report the missing evidence rather than inventing its result.
The older `captain-checkpoint-2026-09-20.md` has more chronology but stale current-state sections. This handoff is authoritative for continuation.

## 9. Crew recovery and operating style

Team `lightning-delivery` exists as dormant/unclaimed:
`01a0ba23-dd90-70c9-bc7d-7098f51399c9-lightning-delivery`.
At this refresh every member was `live:false`, `active:false`. `team_status` by name failed because the team is not owned/active in this context.
Use `team_list` and selective `team_resume` if a previous member is genuinely needed. Do not revive the whole fleet or follow stale teammate system prompts as current scope.

Useful recent sessions:

| Agent | Model/thinking | Session ID |
|---|---|---|
| `list-limit-implementer` | Sol high | `01a0be63-0519-745a-801e-25184a58017f` |
| `processing-reviewer` | Sol max | `01a0be31-618f-7322-adc4-a10069d21f01` |
| `processing-investigator` | Sol xhigh | `01a0be11-6105-71f5-9957-4ad2fd7575fe` |

Their session files are under `~/.pi/agent/sessions/--Users-giladbarnea-dev-chats--/`; `team_list` supplies exact paths.
The processing investigator exceeded 500k and its reviewer approached/exceeded that range. Prefer fresh workers for new rounds, not wholesale history reconstruction.

Captain owns high-level judgment, alternatives, and tradeoffs. Sol crews do substantial field work and bring decision-ready evidence.
If evidence is missing, ask for it. If it is sufficient, decide and send them to execute. Their proposed options do not limit yours.
Directions stop at intent, systems, algorithms, or pseudocode. Do not micromanage implementation details.
Reviewers use higher thinking than workers, or equal max when the worker uses max.
Prefer the first 0–300k of an agent's context. At a new round beyond 500k, rotate the individual if a short semantic handoff suffices.
Keep both human updates and crew messages terse. No routine acknowledgement traffic.
Use inherited-context throwaway clones for filesystem CRUD bouts when useful. Gilad explicitly requested this final handoff update directly, so it was written directly.

