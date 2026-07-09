---
date: 2026-07-09
feature: additional-context-color
status: implemented
---

# AdditionalContext now has its own colored-tool accent

The earlier hook-attachment work correctly made `AdditionalContext` obey tool visibility, but the colored renderer still treated it as an ordinary tool call. That made injected context visually blend into Bash/Edit/Read activity, even though it comes from Claude’s hook layer rather than from the assistant’s action stream.

The fix stays at the rendering boundary instead of changing the message model: `src/chats/theme.py` defines a dedicated `tool.additional_context` style, and `src/chats/formatting.py` maps only the `AdditionalContext` tool input to that style. Normal tool calls keep `tool.call`, results keep `tool.result`, and errors keep `tool.error`.

I chose Monokai Pro orange (`#fc9867`) because it is warm, distinct from the existing cyan tool-call rail, and already fits the terminal palette the user pointed at in `/Users/giladbarnea/Downloads/installers-and-assets/Monokai Pro iTerm2/Monokai_Pro.itermcolors`.

The regression test lives in `tests/test_colored_rendering.py` and asserts the public colored output: `AdditionalContext` emits the new orange ANSI color while a neighboring Bash call keeps the existing cyan.

Verification:

1. `uv run pytest tests/test_colored_rendering.py tests/test_hook_additional_context.py tests/test_theme.py -q`
2. `uv run pytest -q`
3. `./tests/test_colors.sh | cat`
