---
date: 2026-06-21
task: render Claude isCompactSummary user entries as their own Compaction block
---

# Compaction Messages

Mirrored the existing `RECAP` wrapper precedent end to end, since a post-compaction
summary is the same shape of thing: a system-authored summary that should be visible
by default and labeled as its own block rather than the role that carried it. That
made this a three-touch change (`ContentBlockType.COMPACTION`, a `wrapper_type`
override in `_parse_user_entry`, a `_ROLE_HUE` entry) with everything downstream —
XML tag, `## Compaction` header/badge, JSON `type`, panel border — falling out of the
existing `Message.get_wrapper_type()` routing for free.

Two decisions worth recording. First, the override lives at the *end* of
`_parse_user_entry`, not at `Message` construction: the string-content branch assigns
`wrapper_type` from `_parse_user_string_content`, so an earlier assignment would be
clobbered. Applying it last makes "a compaction entry is a Compaction block" hold
regardless of how the body parsed. Second, `role` stays `"user"` (data fidelity); only
the *displayed* wrapper changes. Because `isCompactSummary` entries never carry
`isMeta`, default `show_user_messages` makes them visible without any flag — the
"shown by default like recap" requirement — while still honoring `--only-assistant`
etc. as a user turn.

The hue `#a21caf` (fuchsia) was chosen by checking it against every value already in
`_ROLE_HUE` and `theme.py`; it is the one clearly-distinct family (blue/violet/teal/
amber/red/green were all taken). The shape was verified against all 38 real
`isCompactSummary` entries under `~/.claude/projects` before coding: every one is
`type:"user"`, string content, no `isMeta` — so no list-content path is needed.

Context docs `README.md` and `CHANGELOG.md` documented the sibling recap behavior, so
both were updated to keep the entry-type reference and changelog in step. Tests pin
the two user-facing surfaces (plain XML via `format_to_xml`, colored badge+hue via
`cmd_parse` against a recording console), matching the recap test rather than asserting
on internals.
