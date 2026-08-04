# Short Spec Definition

This document is the authoritative contract for global and tool-local shortening values.
Tool selection and short-policy precedence remain defined in [TOOL_SPEC.md](TOOL_SPEC.md).

## Grammar

```text
SHORT_SPEC := N | P | P=N
N          := decimal integer, N >= 8
P          := p | progressive
```

`P` aliases are case-insensitive. `N` alone selects fixed shortening.
`P` selects progressive shortening, and `P=N` sets its final limit.

Reject empty values, unknown components, reversed assignments, repeated
assignments, colon-separated progressive limits, and any `N < 8`. Invalid
examples include `7`, `p=`, `p=7`, `32=p`, `p=32=64`, `32:p`, and `p:32`.

## Global carriers and defaults

Parse mode accepts `--short=SHORT_SPEC`, `--short SHORT_SPEC`, and `-s SHORT_SPEC`.
Search accepts the attached and detached `--short` forms. Search reserves `-s` for case-sensitive matching.

A bare global `--short` or parse-mode `-s` selects fixed `N = 500`.
Global `P` selects progressive `N = 500`. Global `P=N` supplies both fields.
Attached values are strict and fail when they do not match the grammar.

After a parse input, detached `-s 7` and `-s 32:64` retain their legacy meaning:
bare fixed-500 shortening followed by a message selector.

## Tool-local carriers and inheritance

Tool filters accept `-t FILTERS`, `-t:FILTERS`, `--tools FILTERS`, and `--tools=FILTERS`.
Inside one tool spec, use `s[=SHORT_SPEC]` or `short[=SHORT_SPEC]`.

A bare local `s` inherits the complete active global policy. Without one, it uses fixed 500.
Local `s=P` inherits only `N` from the global policy, or 500, and selects progressive mode.
Local `s=N` selects fixed `N`. Local `s=P=N` supplies the complete local policy.
[TOOL_SPEC.md](TOOL_SPEC.md) chooses the winning declaration before this inheritance is resolved.

## Progressive sequence

Build one ordered union of visible messages that have at least one progressive payload.
A message qualifies once, even when several payloads or policies qualify inside it.
Short payloads still qualify when their source length does not require truncation.
Hidden payloads and payloads governed only by fixed policies do not qualify.

Qualifying payloads are message text, shown thinking, shown plans, and visible tool inputs or outputs.
Global and tool-local progressive policies share the same message position and qualifying count.
Each policy applies its own `N` to that shared position.

For `Q > 1` qualifiers and zero-based position `i`, use this endpoint-inclusive limit:

```text
L(i, Q, N) = 8 + floor(i * (N - 8) / (Q - 1))
```

The first qualifier gets 8. The final qualifier gets exactly `N`.
A singleton gets `N`. When `N = 8`, every qualifier gets 8.

Parse assigns positions after agent merging and message-slice selection.
Search assigns positions across all visible session messages before query-match filtering.
Matches-only and full search output preserve those same assigned positions.

Every effective limit applies independently to each string leaf, not to the containing object.
The middle marker counts within the leaf limit. Renderer scaffolding sits outside that limit.
XML, structured JSON, raw, and Rich output use the same resolved limits.
Session metadata and frontmatter never participate in the sequence and are never shortened.
