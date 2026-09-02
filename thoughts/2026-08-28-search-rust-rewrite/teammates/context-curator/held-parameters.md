---
date: 2026-08-28
author: context-curator
method: reviewer-profiler's — enumerate what the harness HOLDS, not what it varies, then ask of each whether you chose it
subject: tests/data/search-content-fuzz/fuzz_harness.py::run_under_pty
---

# Held parameters — my pty harness

Every result I have reported from this harness inherits every row below. `reviewer-profiler`'s tell: a **chosen** held parameter is usually documented somewhere; an **inherited** one is invisible in every downstream artifact, and the helper's docstring can be accurate the whole time.

Mine was. It says stdout and stderr share the pty "as they would in a terminal", which is true and says nothing about the six things below it.

| Held | Value | Chosen? | Exposure |
| --- | --- | --- | --- |
| `columns` | varied, 4 values | **varied** | — |
| colour tier | varied, 4 tiers | **varied** (since L22) | — |
| output mode | varied, 5 modes | **varied** | — |
| `rows` / `LINES` | 40 | **no** | Pager behaviour is height-dependent. Nothing I ran could see a paging boundary. |
| `cwd` | `PROJECT_ROOT` | **no** | **Directory filters resolve against cwd.** `-d .` means something different per directory and my corpus never moved. |
| stdin | the pty — always a tty | **no** | The product has a piped-stdin input path and a piped-ID path. Neither is reachable from this harness. |
| stdout/stderr | merged on one pty | half — I reasoned about it | Correct model of a terminal; means I **cannot attribute a finding to a stream**. `views-and-colour`'s two-pty runner is the better instrument. |
| environment base | `os.environ.copy()` | **no** | Everything in my shell leaks in. A variable set here and not there changes results with no record of it. |
| `timeout` | 120 s | **no** | A hang looks like a truncated capture rather than a failure. |
| `TZ` | `Asia/Jerusalem` | **yes** | Matches the contract corpus deliberately. |
| `COLUMNS` | popped | **yes** | The point of the harness — let the terminal decide. |

## Six inherited, three chosen

The exposure is `rows`, `cwd`, stdin-is-a-tty, environment completeness, `timeout`, and stream merging. **I chose none of them.** They are the defaults of the function I wrote on the first attempt, and every subsequent result inherited them without the question being asked again.

The two I would close first:

1. **`cwd`** — because directory filtering is a real product feature that resolves against it, and "no invariant violations" over a corpus that never left one directory says nothing about `-d`.
2. **stdin-is-a-tty** — because piped stdin is a documented input path and this harness cannot reach it at all.

## The pattern across three instruments today

Mine held colour and the five above. `reviewer-profiler`'s held the stream, the width, and environment completeness. `views-and-colour`'s inherited `stderr=DEVNULL` through a shared helper.

**Nine held parameters between three harnesses, and not one was chosen.** Every one arrived as the default of something written for a different purpose.

That is the argument for enumerating rather than remembering: the parameters you would think to list are the ones you chose, and those are exactly the ones that are safe.
