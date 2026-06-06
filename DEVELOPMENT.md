# `chats` Development

Current code quality issues, known technical debt, development conventions, and future ideas.

---

## Contributors

1. Read in full every source file, recursively, except `tests/data/*` because the files there are huge.
2. If developing or enhancing a feature, iterate with the user which behaviors should be tested by way of TDD before implementing.
3. Write a minimal, MECE set of tests; implement and iterate against the tests; surgically update docs.

---

## Current Issues

### Code Duplication

- [ ] **Recursive data traversal** in `shorten_data()` and `extract_text_from_content()` (both in `src/chats/utils.py`) uses very similar dict/list/str handling patterns.
  `effort::low`

### Mixed Concerns

- [ ] **`cmd_parse()` (in `src/chats/commands.py`)** currently covers a fairly wide set of responsibilities:
  - Input resolution
  - Content reading
  - Conversation parsing
  - Slice application
  - Metadata printing
  - Output formatting decisions

- [ ] **`main()` (in `src/chats/cli.py`)** sets up four different `argparse` configurations inline, one per subcommand. These might be easier to manage as separate `parse_*_args()` helper functions.

### Other Maintainability

- [ ] **Inconsistent error handling** – a mix of `sys.exit(1)`, silent `continue`, and returning empty collections
  `priority::low`

---

## Known Technical Debt

None currently tracked.

---
## Maintenance Guidelines

Postpone formatting and rendering of structured data as long as possible—ideally to the later stages of the flow. Think of a classic web server: data is turned into HTML *last* on the server, and rendered to the user *even later* in the client browser. This tool should follow the same approach. Formatting and/or rendering data is essentially irreversible, while structured data is malleable.

---


## Random Ideas

Not urgent, not necessarily important. Jotting down to not forget.

1. **Inject CLAUDE.md every 100K tokens** - Periodic reminders from global/local project settings

2. **Link tool inputs to their outputs** - Sometimes the connection isn't clear. Example:
  ```xml
  <tool-input name="Read" file_path="path/to/file.ext"></tool-input>
  </assistant-response>
  <user-message i="28">
  <tool-output>
       1→name: Maintain Documentation
       2→
       3→on:
  ```
  The gap makes it hard to see which output corresponds to which input.
3. **`-u`, `--usage` flag** - Display token usage statistics from conversation file
