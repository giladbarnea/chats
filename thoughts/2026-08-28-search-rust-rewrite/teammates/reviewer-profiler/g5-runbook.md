# G5 — final verification runbook

**A G5 a successor can run, not one they must reconstruct.**

Every check below is a command, what it proves, and its status against the current tree. Nothing
here is a description of a check that would need designing; the shapes are proved and the ones
that cannot pass yet say why.

**Preconditions to re-check at run time, not facts.** Each was true when last measured and
each is the kind of thing this runbook exists to stop anyone assuming.

    HEAD                8cb4c5f
    oracle route digest sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
                        via tests/oracle_digest.py::oracle_route_digest
                        unchanged 2026-08-29 -> 2026-09-01 across 38 changed Rust files,
                        which is what "production search is still Python" looks like from
                        the outside
    modified paths      102 on 2026-09-01 (was 82 on 2026-08-29)
    cutover             ⚠ LANDED 2026-09-01, later the same day. `rust/main.rs` routes
                        `search`, and `search_run::run` has callers. The two preconditions
                        above EXPIRED exactly as they were written to. Both original claims
                        are kept because the reasoning is the useful part.
                        **Re-check both before running anything below** — they are still
                        preconditions, not facts, and the next thing to expire is this line.

## Identities to pin before any run

    corpus      ~/.cache/ch-search-corpus/v1
                695 files, 1,183,541,907 bytes
                sha256 de693c35ad4700c5e8c36d453a13460936b6b7b28d453f0866c8b5c4ab284965
                performance_gates.py refuses to run if this moves

    oracle      tests/oracle_digest.py::oracle_route_digest
                digests the whole route, not src/ — a src-only digest reads unchanged
                while a `uv sync` replaces ch-legacy underneath

    routes      hash both subject and reference before and after every run
                a run whose route changed underneath it is void, not noisy

## Proved against the tree, 2026-08-29

    check 1  no PyO3     target/release/ch links libiconv, CoreFoundation, libSystem only,
                         0 undefined Py_ symbols                                    PASS
    check 3  frozen set  0 drifted, 0 new against install 22236c08          PASS
                         **taken at 68 entries**, and real. An earlier version of this
                         line said 76; that was wrong and is the fifth instance of a
                         true statement that quietly stopped being true.
                         Re-taken at 82 on 2026-09-01, fresh process and fresh temp
                         home: 0 drifted, 0 new.
    check 8  scoped diff enumerated; see the precondition block for the current figures

**Between those two runs the file was briefly unverifiable, and the cause is worth knowing
before anyone extends it.** The `[Errno 21]` shapes need a directory where a session file is
expected, and `freeze_references.py` creates it **before** the stderr loops. So every stderr
capture from that freeze onward named a path under the per-run temp home. Six entries were
`{HOME}`-normalised — the ones being added — and twenty-one were not, and those could never
match a fresh run. **All stderr captures are normalised now; 27 entries carry the token and
none carries a raw path.**

**The reason it was invisible: freeze and verify share a temp home *within* a run and differ
*between* runs, so the defect could not show in the run that created it. An artifact that
validates against itself is not validated.** Any future entry naming a filesystem path must be
normalised, and the check is a verify from a separate process — not a second call in the same
one.

**Check 3 is the load-bearing one and its scope matters.** Zero drift across 31 changed Rust
files means the baseline is still a baseline, so divergences after the cutover are the port's
rather than drift nobody noticed. It does not cover the six entries added since, and the first
thing to run when the tree is quiet is a full `--verify` at 82.

## Runnable now — shape proved, re-run at G5

| # | check | command | proves |
| --- | --- | --- | --- |
| 1 | no PyO3 in the shipped binary | `otool -L <ch>` and `nm -u <ch> \| grep -c Py_` | linkage, on the artifact rather than the build flag |
| 2 | corpus identity | `performance_gates.py … ` refuses on mismatch | the budgets belong to this corpus |
| 3 | frozen reference set | `freeze_references.py <ref> <fixtures> --verify frozen_reference.json` | 82 recorded answers still describe the oracle |
| 4 | age pairing | `age_pairing_gate.py <ch> <fixtures>` | label-to-colour pairing across all 7 units; refuses below 5 |
| 5 | ambient inputs, both directions | `ambient_gate.py` and `ambient_gate_piped.py` | 6 known gaps; reverse list empty |
| 6 | colour capability | `colour_capability_sweep.py` | 6 tiers, of which `16 colour` and `8 colour` are byte-identical — Rich maps both to `ColorSystem.STANDARD`, so one of the six proves nothing the other does not |
| 7 | colored width | `colored_width_gate.py` | parity at 60/120/200; 80 is the demonstration, never the gate |
| 8 | scoped diff | `git status --short` against the charter's scope | no unrelated cleanup |

## Blocked on the cutover — cannot pass before it, by construction

| # | check | command | blocked because |
| --- | --- | --- | --- |
| 9 | full suite green | `./tests/run_all.sh \| cat` | the two live-pool budgets are retired and replaced by #2; the suite must be green *including* the fixed-corpus gates and *excluding* those two |
| 10 | no Python on the route | put `ch` alone in an empty directory, no `ch-legacy` sibling, stripped `PATH`; run `search`, then `info --help` | search must render hits; `info` must fail with the private-entry error. **The `info` half is the control** — without it the probe cannot tell the two routes apart. **And the search half must use a shape that reaches the coloured sink** — see the note below |
| 11 | performance | `performance_gates.py <native> --reference <python-route> --falsify` | 4 absolute budgets, 2 ratio gates, 3 memory gates; `--falsify` requires every shape to fail against the reference |
| 12 | memory parity | same command | agent-bearing arm: native delta ≤ Python × 1.05. Claude arm is the control and must stay near zero |
| 13 | allocation slope | `allocation_profile.py <native> <python-route>` | subject slope ≤ 7.36. **This is the queued prediction test**: if `session`'s clone-to-move change was the mechanism, the slope falls from 9.00 toward 7.00 |
| 14 | package ownership | `uv build --wheel` from a **purged** `build/` | one Mach-O `ch`; `entry_points` expose only `ch-legacy`; the extracted binary serves search with no sibling |
| 15 | installed launcher | hash `~/.local/bin/ch` against the wheel's | the shipped artifact is the one measured |

**One behaviour the frozen set pins that nothing else does:** `--color never` on a pty still
emits colour — 841 bytes — because the plain path styles its rule unconditionally. A port
implementing `never` as "the plain path" produces 721 bytes and diverges. It is
preserve-because-wrong, and honouring the flag everywhere would be *more* correct.

## Things that will be got wrong without being told

- **Purge `build/` before the wheel.** setuptools reuses its cache and re-packages modules
  deleted from `src/`. It has already resurrected two deleted files into a wheel once.
- **`exec` replaces the process.** Any no-Python check shaped like "did `ch` spawn a Python
  child" sees nothing and passes for the wrong reason. Absence of a child is not evidence.
- **The loader trace is void.** `DYLD_PRINT_LIBRARIES` reports "842 libraries, 0 python" for
  `ch search` *and* for `ch info --help`, which must use Python. macOS purges `DYLD_*` for a
  hardened interpreter, so the trace stops at the handoff. Use #10 instead.
- **`rg` skips ignored paths.** Any search that must reach `.venv` or site-packages needs `-u`.
  Three confident wrong negatives came from this in one day, including one while verifying a
  correction to the first.
- **Drivers die with their session.** A differential is only re-runnable while its oracle *and*
  its driver exist. Drivers live in `probes/drivers/`; a scratchpad copy is not storage, and a
  stale one will be found first and will look like it worked.
- **Check 10's search shape must reach the coloured sink, or it proves nothing about rendering.**
  The obvious probe is `search <literal> -ll`, and `-ll` never touches the panel renderer. While
  `ch search --full` panicked with exit 101 on a colour terminal — true when written on
  2026-09-01, **FIXED later the same day**: styled tool rendering was built and `Unsupported`
  no longer exists in the crate. **The panic is gone; the reason for this rule is not.**
  A `-ll` probe still never touches the panel renderer, so it **passes the no-Python proof over
  a route whose rendering it never exercised** — The check would be green and the
  product broken. Use a shape that renders: `--full` or `--color always` without `-ll`, and read
  the exit status as well as the output.
- **Name the subject on every number.** "Native ignores X" and "the branch ignores X" are
  different claims and the second is usually the true one.

## The width-parameter question, answered

`search_run::run(arguments, home, width)` takes width as a parameter, which is a shape my
sweeps were not designed against. Measured rather than reasoned:

**⚠ EXPIRED 2026-09-01: `run` now HAS callers.** It had none when measured — the only
occurrence was its own definition — **and the arm landed later the same day, so the caller
exists and chooses the width source. It passes `terminal_width()`, the intended one; check 7
after the cutover is the check.** Original reasoning kept: **This expires with the cutover:
`engine-and-codex` landing the three-arm function in `rust/main.rs` makes that caller the first
one, and it chooses the width source.** The intended source is `terminal.rs::terminal_width()`, which reads
`COLUMNS` and falls back to `ioctl`.

**My gates already cover both of those sources** — `colored_width_gate` varies the pty width and
the ambient sweeps vary `COLUMNS` — so the parameter is not currently a gap. It becomes one only
if the wiring passes width from a third source, and `colored_width_gate` would catch the
failure that enables: a route pinned to a constant renders the same width at 60, 120 and 200,
which is exactly what it caught on the branch.

**So the risk lives in the wiring that has not happened yet**, and the check on it is check 7
run after the cutover, not a new gate.

## Held parameters of this runbook itself

`held-parameters.md` is the audit for the eleven gates. The runbook adds two of its own: every
command here runs on **one machine**, warm, with `cwd` inherited rather than set. Directory
*matching* under `-d` is exercised by no gate.

# Check 10 — the recorded "before" state

**For promotion into `g5-runbook.md` beside check 10, by `search-firstmate`. I do
not edit the runbook: it is the specification of the proof I run, and a runner who
can edit it can weaken it. This is evidence for it, not a change to it.**

---

## Measured 2026-09-01T14:3xZ, pre-cutover, by `g5-runner`

**Both halves of check 10 fail identically today. That is the baseline, not a
defect.**

Artifact: `~/.local/share/uv/tools/chats/bin/ch`, `22236c087af33dea`, 3,039,008
bytes, **the Aug 28 install — NOT the Sep 1 build that carries the arm.**

Method: the binary copied alone into an empty directory, **no `ch-legacy`
sibling**, `env -i` with `PATH=/nonexistent`, `HOME` at the contract fixture home.

    search "needle five" --color always --no-paging --no-metadata
        exit 1, stdout 0 bytes
        stderr: Cannot start the private ch legacy entry:
                No such file or directory (os error 2)

    info --help                                       (the control)
        exit 1, byte-identical error

**Why identical: pre-cutover both routes are Python**, so removing the Python
entry removes both. **The control cannot discriminate yet, and that is precisely
why it is worth recording — it will.**

## What the post-cutover run is measured against

**After the flip, `search` must render and exit 0 while `info --help` still fails
with that exact string.** Today's identical pair is the "before" half of that
comparison. **A run that finds both halves still failing has not measured a flipped
route, whatever else it reports.**

## Two things that make this reading safe, and one that would break it

**Safe.** A behavioural test and a structural one agree: the binary links only
libiconv, CoreFoundation and libSystem and carries **0 undefined `Py_` symbols**,
so it holds no interpreter and exec'ing the sibling is the only way it can answer
at all.

**Would break it.** The search half **must use a shape that reaches the coloured
sink** — `--color always`, with or without `--full`, never `-ll`. Both coloured
sinks are gated on the *resolved* `flags.color` (`rust/search_run.rs:125,148`), so
a probe run non-interactively resolves colour off and lands in `PlainSink`. **A
piped `--full` proves nothing about rendering.** Read the exit status as well as
the output.

*Block above written by `g5-runner` 2026-09-01 and promoted verbatim by `search-firstmate`. It is evidence, not criteria: it records what check 10 measured BEFORE the flip so the post-flip run has something to be measured against. No pass condition in this runbook was changed to admit it.*


## Reading check 9's output — added by `search-firstmate` 2026-09-01

**`./tests/run_all.sh` uses `set -e`, so it STOPS at the first pytest failure and never
reaches the perf suite or any of the 13 shell suites.** The command as specified therefore
reports **the first failure only**, and a short failure list is not a small failure count.
**Enumerate the remainder separately before concluding anything about scope.** On the first
post-cutover run this mattered: the specified command showed one failure where the true
figure was 18 failed and 21 errors.

*Evidence, not criteria — no pass condition changed. Placed by `search-firstmate`; the
preconditions above were corrected the same day, marked rather than rewritten, because the
reasoning that expired is the useful part.*
