---
name: adapter-tool-normalization-post-implementation
description: Why current Pi and Codex tools now normalize completely at the provider boundary.
date: 2026-08-18
---

# Provider adapters now protect one tool contract

Each provider adapter must convert native tool envelopes, names, input keys, and result content into canonical dictionaries before shared code runs. `src/chats/registry.py` owns declared aliases, while provider-specific envelope parsing stays in `src/chats/parsing.py`.

The shared model and renderers consume only canonical fields. Results keep content, error state, and an optional canonical name; tool IDs link them to calls without copied input metadata. Unknown native tools stay on generic rendering.

## Claude revealed the intended boundary

Claude already normalized the native `Read` input key `path` to canonical `file_path`. `TOOL_SCHEMAS["Read"]` then fed both `tool_to_parts` plain XML and Rich `ToolParts.attrs`, so both views agreed. [The earlier Claude repair](../26-07-26-claude-read-path/post-implementation.md) records that precedent.

Pi normalized native `read` to `Read` but passed `arguments.path` unchanged, so the shared schema found no `file_path`. Codex normalized the outer `custom_tool_call` name `exec` to Bash before decoding its JavaScript, hiding inner `exec_command` and `apply_patch` data. Latest result arrays also used `input_text`, which the shared extractor ignored. Older direct Codex records still worked, making this provider-schema drift look partial.

## The adapters now finish normalization

Pi now declares `Read.path` as an alias for `file_path` and applies input-key normalization while parsing calls.

Codex now decodes generated custom-call scripts, including one or several `exec_command` calls and `apply_patch`, before applying canonical names and keys. Multiple commands in one outer call remain one Bash call, matching the outer call ID. `input_text` and `output_text` result blocks become canonical `text` blocks. Direct legacy calls remain unchanged, while unknown inner tools retain generic rendering.

We accepted provider-specific parsing inside adapters and declarative aliases for known schemas. We rejected native fallback keys or provider branches downstream, copied call metadata on results, renderer-side JavaScript parsing, and guessed schemas for unknown tools.

The main drift was broader current Codex coverage than the two first failing cases. The implementation also supports several commands in one envelope and preserves generic unknown-tool behavior.

## Verification

The reported Pi session now shows its Read path in plain XML and Rich. The reported Codex slice has zero empty Bash or Patch input/output blocks.

Functional Python tests pass with 968 passed and 3 skipped. All shell suites pass. Two unchanged serial performance budgets still fail locally, matching the pre-change baseline.

Useful durable context: [ARCHITECTURE.md](../../ARCHITECTURE.md), [CHANGELOG.md](../../CHANGELOG.md), and [TOOL_SPEC.md](../../TOOL_SPEC.md).
