---
name: colored-view-panels-and-tool-blocks
description: Why the colored parse/search views became panels with a left-rail tool language, and the colored-vs-plain split that scoped it.
date: 2026-06-18
---

# Colored view: conversation/message panels and tag-free tool blocks

**One split governs everything.** The colored path and the plain-`xml` path were forked in *intent*, not just appearance: colored output is for a human reading in a pager (orientation, a little delight), while plain `xml` is semi-structured text meant to be piped into an LLM/tool, where the XML tags earn their keep as cheap structure. So every change here gates on `flags.color` and leaves plain `xml` and `raw` byte-identical — the new `ToolParts` fields are colored-only, and the piping/tests that depend on the YAML+tags form keep passing untouched. That intent is invisible at the `if flags.color` branch; it is the reason the branch exists, and the reason `render_message_inner_xml`/`render_tool_xml` were left alone.

**The orientation primitive is a persistent left edge.** A `less` pager cannot pin a sticky header, so the only signal that survives scrolling a multi-screen region is something drawn on *every* line. That one insight unifies all three scopes: conversations are `Panel`s with a border hue that cycles per conversation (`commands/search.py:_render_conversation_panel`), each parse message is a `Panel` whose border/title chip carry the role hue (`build_message_panels`), and tool/thinking blocks get a `▎` rail (`LeftRail`). Headers still name things at the top; the edge keeps you located once they scroll off.

**Tool blocks: `⏺`/`⎿` + rail, by elimination.** The glyphs are borrowed from Claude Code for instant familiarity. The rail was chosen over a labeled-rule header for one concrete reason raised in review: horizontal rules already mean "message/conversation separator," so reusing them for tools muddies the hierarchy. The rail delivers the rule's "where does this block begin and end" legibility, but vertically, where nothing else competes.

**`ToolParts` was XML-shaped and lossy.** It carries a tag, attribute pairs, and a fenced-markdown string — enough for `render_tool_xml`, but it cannot express a diff (Edit) and drops the file path a Read *result* needs to choose a lexer (the path lives on the *input*, a different message). Rather than re-parse the fenced string, `ToolParts` gained colored-only structured fields (populated in `tools.py`), and `_tool_input_by_id` pairs each Read output back to its input by id. `render_tool_rich` moved from `tools.py` (data) into `formatting.py` (rich) so it can reach `LeftRail`/`Syntax` without a circular import — `formatting` already imports `tools`, not the reverse.

**Smaller decisions and traps.** Search match-highlighting re-styles the *rendered* segment stream (`HighlightedMarkdown`) instead of touching Rich's Markdown internals, so it still composes inside a Panel. Theme style names are not `Style.parse`-able — they resolve via `console.get_style` at render time. `LeftRail` trims blank edge lines because Markdown's code-fence padding otherwise emits empty rail segments. Thinking and subagent-task were detagged too (`✻` + rail) for consistency — a judgment call, trivially reverted. One loose end: now that parse renders panels, `render_messages_with_rich` is reachable only through a dead `display_search_result` color branch.

**Useful docs.** ARCHITECTURE.md (MODEL + FORMATTING layer; note 21, streaming search); README "Display Options" and search "Search Features"; the user's terminal screenshots were the visual ground truth at each step.
