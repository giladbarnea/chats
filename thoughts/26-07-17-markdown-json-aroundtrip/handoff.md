---
status: implemented
updated: 2026-07-17 17:01 +03:00
post_implementation: post-implementation.md
---

# Handoff: JSON-to-Markdown round trip

## Completed outcome

`ch parse` now converts both provider-free transport representations. Its default output reconstructs plain XML-tagged Markdown from structured JSON; `ch parse -f json` reconstructs canonical structured JSON from that XML. Either input can come from a file or stdin, and both command compositions stabilize byte-for-byte after XML's represented information is canonicalized.

The structured JSON contract retains raw timestamps and optional agent names. Ambiguous tool-input dictionaries use an explicit `input` wrapper, while existing unambiguous dictionaries remain flattened. XML-to-JSON intentionally preserves only what XML carries: minute-precision dates, shortened IDs, string attributes, schema-visible inputs, and rendered tool-output strings. Malformed input in either grammar fails clearly.

## Fixture clarification

The interim handoff incorrectly recommended copying provider-native JSONL sessions and regenerating outputs during tests. The user clarified that fixtures should be static outputs generated with `ch <real-session-id> [args] -f json`; no native transcripts belong in the test corpus.

The final corpus contains generated JSON/XML pairs from 20 globally distinct real sessions: four provider adapters across bare, tools, shortened tools, agents, and tools-plus-agents configurations. Sensitive customer sessions discovered during curation were replaced before the fixture checkpoint commit `d807ce0`.

## Verification

The focused round-trip suite passes 49 tests. The full `./tests/run_all.sh | cat` run passes 637 tests with 3 skips, including every shell suite. Independent peer review found no remaining material issue.

See [post-implementation.md](post-implementation.md) for the decisions, surprises, and implementation drift that are not obvious from the source.
