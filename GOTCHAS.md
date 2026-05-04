---
name: gotchas
description: A gotcha is fairly confidently signing off on something that later on proved to be at least partially wrong due to wrong assumptions.
---

# GOTCHAS

## 2026-05-04

Assumed sidechain discovery layout didn't have to match fork output layout: in our case, reading Claude agents from `subagents/` while still writing forks to the project root.
