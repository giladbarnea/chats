---
date: 2026-07-12
status: implemented
related_files:
  - src/chats/commands/parse.py
  - src/chats/formatting.py
  - src/chats/model.py
  - tests/test_basic.sh
---

# Keep plain parse streams semantically separate

The piped form of `ch` is a data boundary: metadata is useful terminal context, but it corrupts the conversation stream for downstream tools. Plain XML now reserves stdout for conversation content and moves the optional metadata block to stderr.

The key distinction is color intent, not merely the resolved `flags.color` boolean. Automatic color becomes false when stdout is piped, while explicit `--color=never` must still promise ANSI-free output. `ConversationFlags.metadata_color` preserves that intent so metadata is dim on an interactive stderr for ordinary piped use without violating the explicit no-color contract.

`--only-metadata` intentionally remains stdout-only because its entire purpose is data retrieval. JSON, raw output, and colored terminal rendering already omit YAML frontmatter, so they needed no behavioral change.

The first full-suite run exposed parse metadata assertions spread across all session adapters. Those tests now name the channel boundary explicitly, while search metadata remains on its existing output path.

The public behavior is documented in `README.md`, `ARCHITECTURE.md`, and `CHANGELOG.md`. Verification: `./tests/run_all.sh | cat` passed with 578 tests and 3 skips.
