---
name: markdown-json-roundtrip-post-implementation
description: Why the JSON inverse stays provider-free and what exact reversal required.
date: 2026-07-17
status: implemented
handoff: handoff.md
---

# JSON-to-Markdown Round Trip — Post-Implementation Notes

The decisive simplification was to treat structured JSON as a post-visibility transport boundary. Tool selection and shortening, plus agent merging, have already happened before JSON serialization; reversing those choices would have added provider coupling without restoring information. The inverse therefore reconstructs the shared `Message` model and rejoins the existing XML formatter.

Exactness exposed two quiet losses in the forward schema: raw timestamps supply XML `date=` attributes, while optional agent names preserve identity on named agent blocks. Carrying both in JSON was smaller and more truthful than inventing either during reconstruction.

The sharpest schema challenge was a tool input whose own keys look like transport fields. An explicit `input` wrapper is now used only for ambiguous dictionaries, preserving the readable flattened form elsewhere while making the boundary reversible and strictly validatable.

The delivered fixture strategy is the material drift from `handoff.md`: the approved 4×5 matrix uses static JSON/XML pairs rather than rerunning provider discovery inside every test. Its 20 distinct real session IDs still cover every provider and visibility shape while isolating failures to the inverse contract.

Useful context came from `README.md`, `ARCHITECTURE.md`, and the structured JSON history in `CHANGELOG.md`. Independent final verification passed 34 focused tests; the full run passed 613 with 3 skips, including every shell suite.
