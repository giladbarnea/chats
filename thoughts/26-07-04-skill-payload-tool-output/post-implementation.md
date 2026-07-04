---
date: 2026-07-04
feature: classify-skill-payloads-as-tool-outputs
status: implemented
---

# Skill payloads now follow tool-output filtering

The bug was in the message model boundary, not in the renderer: Claude records the loaded skill body as an `isMeta` user text message linked to the `Skill` tool call by `sourceToolUseID`. `ch` preserved that linkage only as wrapper metadata, so `-t:i` still rendered the skill body as normal user text.

The fix keeps the existing tool-filtering pipeline as the single source of truth. During Claude user-entry parsing, an `isMeta` text payload with `sourceToolUseID` is normalized into a `tool_result` for that source id. The existing tool id map then resolves it back to `Skill`, and direction/name filters behave naturally: input-only hides it; output filters show it as a linked tool output.

A peer review caught the main drift from that first pass: `ch fork` has a native JSONL rewrite path and does not reuse parse rendering. I mirrored the same classification there, including the string-form content shape, so input-only forks drop skill bodies and output-only forks keep them as native `tool_result` entries.

I added regression tests in `tests/test_meta_user_messages.py` and `tests/test_fork.py` that exercise behavior rather than parser internals. Documentation was updated in `README.md`, `ARCHITECTURE.md`, and `CHANGELOG.md` because this changes the public classification rule for Claude meta payloads.

Verification:

1. `uv run pytest tests/test_fork.py tests/test_meta_user_messages.py tests/test_tool_filter.py tests/test_task_notifications.py -q`
2. `./tests/run_all.sh | cat`
3. `ch 2a8abe8f-4636-45d0-8e28-af9d0e0c1c67 -t:i | sed -n '256,280p'`
