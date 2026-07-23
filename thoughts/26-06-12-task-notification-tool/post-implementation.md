---
name: task-notification-tool-post-implementation
description: How Claude background-task notifications became the synthetic TaskNotification tool.
date: 2026-06-12
---

# TaskNotification post-implementation

Claude Code's background `Agent` runs inject a `type: "user"` entry whose string content is a
`<task-notification>...` payload (plus a duplicate `queue-operation` entry, which the parser already
skipped by virtue of only handling user/assistant/system types). These rendered as ordinary user
prose by default. They are now reclassified as a synthetic `tool_use` named `TaskNotification`:
hidden by default, opted in via `-t`, name-filterable like any tool.

Decisions worth recording:

- **`tool_use`, not `tool_result`.** A result's display name resolves through the tool-id map, and the
  notification's `<tool-use-id>` points at the *original* `Agent` dispatch — resolving through it would
  surface the wrong name. The `ExitPlanMode` plan-as-`tool-input` precedent settled it.
- **No top-level `id` on the synthetic tool.** Reusing the notification's tool-use id would let
  `_build_tool_id_map` clobber the original dispatch's name with "TaskNotification", corrupting the
  dispatch's own `tool-output` label. The shortened id is carried as a plain `tool_use_id` attribute
  instead, preserving the visual chain-link without touching the map.
- **Detection is content-shape-based** (fullmatch in `parsing._parse_task_notification_tool`), like the
  `<command-*>` hiding, rather than keying off the entry-level `origin.kind` field — it works for raw
  stdin that lacks the envelope.
- **Attribute set deliberately small.** Only `tool_use_id` (the linkage anchor), `status`, and `summary`
  survive as attributes; `task_id`, `output_file`, and the `usage` counters were dropped as noise. Trimming
  `_TASK_NOTIFICATION_FIELD_TAGS` (not just the schema) matters because `_tool_use_to_json` splats every
  input key into JSON, so unschema'd fields would otherwise leak there.
- **Attribute double quotes are downgraded to single quotes, not escaped.** No attr in the codebase escapes;
  the `summary` field carries literal `"`, so `_parse_task_notification_tool` swaps them for every attribute
  field (the markdown `result` body keeps its quotes verbatim).

TDD ran five red/green cycles in `tests/test_task_notifications.py`; the filter and JSON cycles were
green on arrival because the behavior falls out of `ToolFilter` and `_tool_use_to_json` once the
payload is a schema-registered tool. README's Conversation File Structure section and ARCHITECTURE.md
were the useful maps.
