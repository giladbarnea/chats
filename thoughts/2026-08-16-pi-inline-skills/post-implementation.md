---
name: pi-inline-skills-post-implementation
description: How the Pi inline-skill splitting feature was designed and built.
date: 2026-08-16
---

# Pi inline-skill splitting

Pi expands `/skill` invocations by prepending the skill body into the same user text block as the typed prompt, so transcripts showed giant skill bodies as user text. Now `_parse_pi_message_entry` (parsing.py) splits the leading run of `<skill ...>` blocks into synthetic `Skill` tool-pair messages plus the typed remainder.

Decisions and why:

- **Claude-shaped tool pair over a solo tool_result.** Research showed only Claude has a native `Skill` tool, and this codebase's tool *name filter* resolves a result's name only through the tool_use id map. Emitting a `tool_use`+`tool_result` pair made `-t Skill` and friends work with zero core changes; a solo result would have needed a filter-layer fix.
- **Peel-from-start, never scan the tail.** A survey of all ~3,160 real Pi sessions found one message with unbalanced literal `<skill` tags in a pasted transcript after the typed text. Whole-message depth tracking mis-slices there; peeling blocks from the front and stopping at the first non-skill text sidesteps it and was correct on every observed message. Same survey: ~13% of skill-expanded messages stack 2+ sibling blocks (max 8), separators vary (`\n\n` or a space), and the closing tag is always the literal `</skill>`.
- **Grammar relaxed beyond the wild.** Observed openings are always `<skill name="..." location="...">`, but the pattern accepts bare `<skill>` and arbitrary attributes per user request. An unclosed leading tag means "not a skill expansion" — message kept verbatim.
- **Shared `Skill` schema in registry.py.** Renders `skill`/`location`/`args` as attributes. Deliberate side effect: Claude Skill calls stopped rendering fenced-JSON bodies; three golden fixtures were regenerated after verifying (via subagent) that every diff hunk was exclusively this change or the intended split.

Challenges: none structural. The Pi entry loop needed `_parse_pi_message_entry` to return `list[Message]` with index assignment moved to the loop. Codex peer review (fresh context, full repo rules) found no issues.

Useful references: AGENTS.md, ARCHITECTURE.md notes 25–27, tests/test_pi_custom_messages.py for the fixture/subprocess test pattern, tests/data/parse-round-trip-fixtures/MANIFEST.json for golden regeneration.
