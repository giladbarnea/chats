---
name: markdown-json-roundtrip-post-implementation
description: Why the bidirectional transport stays provider-free and canonicalizes XML loss.
date: 2026-07-17
status: implemented
handoff: handoff.md
---

# JSON and Markdown Round Trips — Post-Implementation Notes

The decisive simplification was to keep `ch parse` a provider-free, post-visibility transport boundary. The default direction reconstructs `Message` objects from JSON; `-f json` reconstructs them from canonical XML Markdown. Neither repeats provider parsing, visibility filtering, shortening, or agent discovery.

“True inverse” means command interoperability after the XML projection, not recovery of native data that XML never carried. XML dates have minute precision, IDs are shortened, attributes are strings, tool schemas omit irrelevant fields, and outputs are rendered text. `messages_from_xmlmd` preserves those represented semantics, and tests make the canonical losses explicit rather than claiming original-JSON byte identity.

Exact XML stabilization exposed two non-obvious details: separators inside ordinary Markdown cannot be used as naïve message boundaries, and reversing agent indentation must preserve whitespace-only tool-output lines. Agent wrapper roles also require inference from user-only metadata, tool-output content, or a synthetic subagent task.

The 20 static fixtures now run in both directions across every provider and visibility configuration. They prove both `JSON → XML → JSON` and `XML → JSON → XML` stabilize, while focused CLI tests cover stdin, adjacent text normalization, and rejection of ordering the bucketed `Message` model cannot preserve.

Useful context came from [README.md](../../README.md), [ARCHITECTURE.md](../../ARCHITECTURE.md), and the original [handoff](handoff.md). The completed dirty tree passed 49 focused tests and the full project suite, then received independent peer review.
