---
date: 2026-07-04
task: tool-spec-short-limits
---

# Tool spec short limits

Implemented explicit numeric limits for tool-local short modifiers, so specs like `Bash:s=10`, `s=80`, and `Read:o:short=120` now carry their own maximum character count.

The main design decision was to treat `--short=N` as setting the global shortening default, not as a separate tier that local bare `:s` can accidentally override. A bare local `:s` now inherits that default, while an explicit tool-local value wins by specificity. That keeps the mental model close to CSS: broad tool specs can set a general tool limit, and a more specific tool spec can override it.

The implementation stayed inside the existing tool-filter boundary: `ToolFilter` now stores an optional local short limit, and `resolve_tool_visibility` chooses the most specific matching short declaration. `Message._iter_visible_tools` and the fork rewrite path both consume that resolved limit.

A small bug surfaced during the first red test: shortening the entire raw tool dict with very small limits corrupted structural fields like `type`, causing known tools to fall back to `Unknown`. The fix was to shorten only tool payload fields while preserving tool metadata.

Docs updated: `TOOL_SPEC.md`, `README.md`, and `CHANGELOG.md`.

Verification: `./tests/run_all.sh` passed.
