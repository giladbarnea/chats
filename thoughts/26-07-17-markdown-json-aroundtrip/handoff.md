---
status: implemented
updated: 2026-07-17 17:01 +03:00
post_implementation: post-implementation.md
---

# Handoff: JSON-to-Markdown round trip

## Completed outcome

`ch parse <json-file>` now reconstructs the plain XML-tagged Markdown body from JSON emitted by `ch <session> ... -f json`. It reuses the shared `Message` model and XML formatter; provider discovery, visibility filtering, shortening, and agent merging do not run again.

The structured JSON contract now retains raw timestamps and optional agent names. Ambiguous tool-input dictionaries use an explicit `input` wrapper, while existing unambiguous dictionaries remain flattened. Malformed structured input fails cleanly, legacy unambiguous JSON remains accepted, and an empty array produces zero stdout bytes.

## Fixture clarification

The interim handoff incorrectly recommended copying provider-native JSONL sessions and regenerating outputs during tests. The user clarified that fixtures should be static outputs generated with `ch <real-session-id> [args] -f json`; no native transcripts belong in the test corpus.

The final corpus contains generated JSON/XML pairs from 20 globally distinct real sessions: four provider adapters across bare, tools, shortened tools, agents, and tools-plus-agents configurations. Sensitive customer sessions discovered during curation were replaced before the fixture checkpoint commit `d807ce0`.

## Verification

The focused round-trip and structured-JSON suite passes 34 tests. The full `./tests/run_all.sh | cat` run passes 613 tests with 3 skips, including every shell suite. Independent adversarial review also exercised 224 tool schema/key/id combinations and found no remaining material issue.

See [post-implementation.md](post-implementation.md) for the decisions, surprises, and implementation drift that are not obvious from the source.
