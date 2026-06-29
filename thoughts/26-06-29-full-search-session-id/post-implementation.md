---
updated: 2026-06-29
---

# Full search session id in colored output

This was a deliberately small rendering fix. The plain and id-only paths already exposed complete session identifiers; the gap was only the colored search Panel title, which still used the old short-id convention.

The change keeps the existing visual split between the first eight characters and the dim tail, but it no longer drops the tail. To preserve the title layout, the headline now yields width to the full id and age instead of reserving space for a fixed eight-character id.

The regression test lives in `tests/test_colored_rendering.py` because this is observable Rich output through `cmd_search`, not a formatting helper contract. The implementation is in `src/chats/commands/search.py`.

Relevant context came from `README.md` and `ARCHITECTURE.md`, especially the colored search rendering path around `SearchHit`, `_render_conversation_panel`, and `_panel_title`.
