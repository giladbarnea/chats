---
name: pi-custom-messages
description: Decisions and validation behind Pi custom-message visibility and agent rendering.
date: 2026-08-02
---

# Pi custom messages

The change stays at the Pi adapter boundary in `src/chats/parsing.py`. Generic `custom` records use a dedicated shared wrapper under `--all`. The two known agent record types normalize into existing agent messages under `--agents`, so search and every renderer consume one model.

A plan review caught three important traps. Pi adapter selection depends on a path below `~/.pi`, synthetic error tools normally disappear without `--tools`, and `display:false` user-agent records repeat preceding normal custom records. The tests therefore copy the source fixture into a temporary Pi home, agent errors bypass tool visibility while reusing Bash error rendering, and hidden duplicates never enter the message list.

Agent metadata comes only from `details`; only the response body comes from native content. Error classification uses identity with `False`. The structured transport now carries `custom_type`, `inherited_context`, and `status`, preserving the strict JSON/XML round trip.

`tests/test_pi_custom_messages.py` drives the public CLI through plain, JSON, raw, colored, search, and transport paths. Focused affected tests passed. The full Python suite passed 641 tests and retained one unrelated performance-budget miss already present at baseline.

Useful maps were `README.md` sections “Display Options” and “Conversation File Structure”, plus `ARCHITECTURE.md` sections “Parse”, “Search”, and “Shared Invariants”.
