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
