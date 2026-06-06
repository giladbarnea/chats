---
name: gotchas
description: A gotcha is fairly confidently signing off on something that later on proved to be at least partially wrong due to wrong assumptions.
---

# GOTCHAS

## 2026-05-04

Assumed sidechain discovery layout didn't have to match fork output layout: in our case, reading Claude agents from `subagents/` while still writing forks to the project root.

Assumed recent-index filtering had to build full metadata for the whole candidate pool before applying the index. In our case, `ch -1 -d ...` loaded timestamps for every candidate session and then reread files for `cwd`, instead of probing incrementally and stopping at the newest matching session.
