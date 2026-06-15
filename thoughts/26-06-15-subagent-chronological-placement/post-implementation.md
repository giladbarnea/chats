---
name: subagent-chronological-placement
description: Why merged subagents were buried mid-timeline and how per-block placement fixed it.
date: 2026-06-15
related: ../26-06-15-fix-claude-codex-agents-detection-and-display/post-implementation.md
---

# Subagent placement: each block at its own dispatch time

**Symptom vs. truth.** Reported as "`--agents` shows no agents," with `ch <id> --agents | tail -70` as the repro. Untrue: every sidechain already rendered in both plain/XML and Rich — they were *buried mid-timeline*, so `tail` only reached trailing main messages. The whole fix hinged on distrusting the symptom; the defect was order, not visibility. I spent the first pass chasing a Rich-renderer theory (a real dead end — Rich line-wrapping defeated my fixed-string greps and faked "missing" content) before the index map made placement obvious.

**Root cause was inherited.** `_merge_agent_messages` (`commands/parse.py`) flattened all agents into one list and inserted it at the *earliest* agent's timestamp. Latent since the related effort, whose fixtures ran agents near-simultaneously; a session with one early agent and two late ones (dispatched near the very end) was the first to expose it. The late agents got yanked dozens of messages backward, ahead of main messages that chronologically preceded them — a non-monotonic timeline.

**Why per-block, not a global sort.** A message-level chronological sort would interleave concurrent agents and split each across main messages. The invariant is *one agent = one contiguous block*. `_interleave_subagent_blocks` preserves it: blocks anchored by first timestamp, each flushed just before the first main message that doesn't predate it — deliberately the exact rule the single-agent path already used, so single-agent output is unchanged and only multi-agent-at-different-times shifts. It also retires the old concurrent-agent message interleave for free.

**Edge.** Appending blocks (vs. the prior `.extend`) made `block[0]` reachable in the sort key, so an empty all-user/no-text transcript would `IndexError`; guarded at the append site.

**Useful docs.** ARCHITECTURE.md note 14 (Agent Merge Heuristics — still true, now per-block); the prior note in `related`; README "Agent/Subagent Conversations"; the synthetic fixture lesson (live sessions about this tool are poor fixtures) reused in `tests/test_claude_agent_detection.py::TestSubagentChronologicalPlacement`.
