---
date: 2026-08-19
title: Slice one baseline
---

# Slice one baseline

The working tree started clean at commit `73a7f7e`.

The functional baseline passed 944 tests and skipped 3 tests in 55.47 seconds. All 13 shell suites passed when run separately.

Two serial performance budgets failed against the live pool:

1. `ch search . -ma 4h --list` took 2,089 ms. Its budget is 1,750 ms.
2. `ch -1 -ma 4h` took 2,096 ms. Its budget is 1,500 ms.

The other two serial performance budgets passed.

The live main-session pool contained 4,838 files across Pi, Codex, and Claude. Python provider classification took about 350 ms per pool pass. Profiling found about 9,800 adapter selections in each failing date flow.

`uv build` failed before this slice. Hatch rejected the tracked absolute `.agents/skills/peer-review` symlink. This known packaging failure is part of the baseline, not a Rust regression.
