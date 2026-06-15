---
name: fix-claude-codex-agents-detection-and-display
description: Why Claude --agents was broken, how it was fixed, and how subagent display was unified across Claude + Codex.
date: 2026-06-15
---

# Subagent detection & display: Claude fix + Codex parity

**Task.** BUGS.md claimed Claude `--agents` was a no-op. It was — a live bug, not a stale note. The dispatching tool had been renamed Task→Agent, so the timestamp matching inside `_merge_agent_messages` (`commands/parse.py`) never matched and every sidechain was silently dropped. The brief then grew: fix Claude, give Codex (zero subagent support) the same capability, and unify both under one spec — `--agents` shows the full cycle, `--tools` is irrelevant to it, default shows nothing.

**Codex turned out to be a merge, not a synthesis.** First instinct (and an early `fd` miss) was that Codex keeps no subagent transcript, so the block would be synthesized from spawn args + notification. Wrong: subagent rollouts live beside the parent under `~/.codex/sessions`, linked by `session_meta.parent_thread_id`, schema-identical to a normal session. That collapsed the whole design onto the existing Claude merge path — hence the adapter-style `find_subagent_transcripts` / `read_subagent_metadata` dispatchers in `commands/resolve.py` feeding one provider-agnostic `_merge_agent_messages`. A Sonnet subagent verified the on-disk shape first: Codex subagent tool results are `function_call_output`, not the `type:user` quirk Claude uses — so they need no special handling.

**`<subagent-task>` is sourced from the transcript, not the dispatch.** `_build_subagent_block` takes the prompt as the last user-text message before the agent's first reply. This avoids cross-referencing the parent and, crucially, skips Codex's injected developer + AGENTS.md preamble (Claude has neither); `_is_codex_preamble_text` already filters most of that noise. Reframing the prompt as a task block is what kills the "agent prompting itself" reading the raw merge produced.

**Plumbing is abstracted away, not merely gated.** spawn/wait/close + `subagent_notification` (Codex) and the Agent/Task dispatch pair + `TaskNotification` (Claude) never render — the merged block is their sole representation. This deliberately walks back the `TaskNotification`-as-tool design from `thoughts/26-06-12-task-notification-tool/post-implementation.md`. Before committing to lossless suppression we spawned a background haiku agent: it writes the same `subagents/agent-*.jsonl` sidechain (the tmp `tasks/*.output` is just a symlink to it), so the merge captures background tasks too — confirming nothing is lost.

**Gating fell out for free.** No new gating logic: presence is gated because the merge only runs under `show_agents`; agent tools obey `show_tools` because they ride the normal tool path inside merged messages. The only wrinkle — `Message.get_wrapper_type` now checks `agent_id` before `role`, so a subagent's tool-result `user` entries render inside its block rather than as `## User`.

**Challenges.** The live test session was worthless for verification — it is a conversation *about* this feature, full of pasted `ch` output and literal markers — so everything was checked against clean temp fixtures instead. Sharpest bug: the synthetic task message rendered as `## Assistant` because Claude's identity lives on each message while Codex's lives in metadata (Codex masked it). The Claude-specific rendering test in `tests/test_claude_agent_detection.py` caught it; `_build_subagent_block` now resolves `agent_id`/`model` from either source. Cross-provider tests earned their keep.

**Loose ends.** `registry.TOOL_SCHEMAS["TaskNotification"]` and the dict-building half of `_parse_task_notification_tool` are now dead. The Rich (colored) renderer does not yet apply the 2-space agent indent that raw/xml do.

**Useful docs.** README.md "Conversation File Structure"; AGENTS.md; the prior task-notification post-implementation note above.
