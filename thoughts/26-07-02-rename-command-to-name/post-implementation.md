---
date: 2026-07-02
title: Rename the `rename` command to `name`
---

# Rename the `rename` command to `name`

Renamed the CLI verb `ch rename` to `ch name` and propagated the change across the project.

## Scope decision (the "why")

Three layers of "rename" exist here, and only two were changed. I asked the user to pick the depth; they chose **command + write-path builders**:

1. **Renamed** — the CLI verb, `cmd_name` (was `cmd_rename`), the `commands/name.py` module, and the provider write-path builders in `parsing.py` (`build_name_entries`, `NameEntryBuilder`, `_build_{claude,pi,codex,antigravity}_name_entries`), plus help text, README/ARCHITECTURE/CHANGELOG, and the command's tests.
2. **Kept on purpose** — the rendered `session-rename` concept (`ContentBlockType.SESSION_RENAME`, the `<session-rename>` XML tag, the `## Renamed Session` header, the theme color key, the `session-rename` role in `model.py`). This names the rename *event* in parsed output and is a rendered-output contract covered by golden-file tests; it is orthogonal to the CLI verb.
3. **Must not change** — the `/rename` string written to `~/.claude/history.jsonl` and the `<command-name>/rename</command-name>` record in `parsing.py`. These mirror Claude Code's own native `/rename` slash command; Claude has no `/name` command, so changing them would break that integration.

Action-describing prose ("Rename a conversation…", the success line, error messages) was left as "rename" — it accurately describes the act, and the retained `session-rename` concept keeps "rename" as the project's word for it.

## Approach & notes

TDD tracer bullet: flipped the CLI seam test (`tests/test_name.sh`) to `ch name` first to get a real RED (the verb fell through to parse mode), then implemented until green. This is a symbol rename, so it's one atomic change rather than incremental vertical slices.

The ASCII flow diagrams in `ARCHITECTURE.md` needed width-preserving edits (padding compensates for `cmd_rename`→`cmd_name` losing two chars) to keep the arrow columns aligned.

Left untouched: the `tests/data/rename_fixtures/` directory (session-with-renames test data, not the command) and all historical CHANGELOG/`sessions.yaml` entries.

Full suite green: 561 passed, 3 skipped.
