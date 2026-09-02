# Branch `0ffde41` vs. the session-core boundary I drew

Owner: `session-core`. Read `session-core-map.md` first — this amends it.
Method: read-only, through `git show`. No branch switch, no production edit.
Rule applied throughout: the branch is prior art. Python on `main` is the oracle.

## 1. Bottom line

The branch converges with my boundary on the two seams that matter most, and diverges on one
that matters just as much. The colored renderer is real and complete, which prices the
mission's largest unpriced item — but it is priced as a hand-written reimplementation of two
third-party libraries, and that changes what "parity" can mean there (§5).

Most important single finding: **the parity defect I confirmed against Python before I ever
saw this branch is present on the branch, unchanged, and its green suite did not catch it**
(§4). That is the concrete case for treating it as prior art rather than as an answer.

## 2. Where it converges — adopt

**`codecs.rs`.** I proposed renaming `render_message_content` to `render_message_inner_xml`
and threading an `encode_transport: bool` through the render tree. The branch did exactly
that, with the same name and the same signature, down to which call sites take the flag. Two
independent derivations reaching the same seam is the strongest evidence available that the
seam is right. Adopt it as written.

**`model.rs`.** I predicted `Message` needs exactly one new field, `tools_always_visible`.
The branch adds exactly that field and nothing else structural, plus a `has_content()` method
that mirrors Python's. Adopt both.

I was wrong about one prediction: I expected `ToolUse` to need `name_aliases` for tool-filter
matching. The branch does not add it. I have not yet found where Python populates
`name_aliases`, so I may have priced a dead field. Open item, mine to close.

**`session_provider.rs`.** This is my proposed `decode.rs` + `claude.rs` + `pi.rs` +
`codex.rs` collapsed into one 1989-line file, with the same internal shape — `branch_map`,
`collect_subtree`, `subtree_depths`, `deepest_descendant`, `origin_root`,
`suppress_agent_dispatch`, `split_pi_skills`, `parse_codex_script`. I prefer one file per
provider; I concede to theirs. The split is a preference, the content is the work, and
re-cutting it now buys nothing.

It also carries a `CwdPeek` fast path with an `assert_fidelity` harness that checks the cheap
projection against the full parse on a real fixture pool. That pattern is better than
anything I had planned and I would keep it.

## 3. Where it diverges — I defend mine

**`session.rs` is not a session core.** It is the complete default-session command: argv
normalization, long/short option specs, positional repair, identifier resolution, recent
lookup, slice notation, the pager, error printing. Welded into that same file is the layer my
scope owns and search needs — `project_message`, `visible_tool_policies`,
`resolve_tool_policy`, `tool_filter_matches`, `effective_limit`, `truncate_middle`,
`shorten_tool`, `shorten_value`.

Two reasons I defend my boundary over it:

1. **Two consumers need that layer.** Search confirmation and default parse both apply
   visibility, shortening and tool filters before rendering. On the branch, search cannot
   reach them without dragging in a command driver.
2. **Our charter excludes the rest of that file.** Default session parsing and unscoped
   commands stay on `ch-legacy` this mission. The branch went further than our scope, so
   `session.rs`'s command shell is not something we are entitled to adopt — only the layer
   trapped inside it.

Concrete consequence for the DAG: extracting the visibility/shortening/tool-filter layer out
of `session.rs` into a core module is a prerequisite for reusing any of this, and it is my
work, not a merge.

**`session_render.rs` mixes three renderers in one 3749-line file**: the semantic XML/raw
passthrough, the metadata and title text, and the colored ANSI renderer. I would split the
colored renderer out. It is the only surface here whose parity is statistical rather than
provable (§5), so it needs to be independently gateable and independently revertible. This
matches the decision to make colored output its own slice.

**Agent transcript merging comes along for the ride.** `session_provider.rs` carries
`claude_agent_paths`, `codex_agent_paths`, `agent_metadata`, `build_agent_block`. Search
never merges agent transcripts — `_merge_agent_messages` is parse-command-only. It should not
cross into the native search route.

## 4. The falsifier that survives on the branch

Before reading the branch I confirmed a live parity divergence in `ch parse` on `main`:

```
text:  "<thinking is my hobby\nand a second line"

ch parse -f xml       -> <user-message i="1" text_encoding="html">
                         &lt;thinking is my hobby
Python format_to_xml  -> <user-message i="1">
                         <thinking is my hobby
```

`codecs.rs::has_inner_opening_tag` accepts `<tag` followed by `>` **or a space**. Python's
`_INNER_XML_BLOCK_OPENING_PATTERN` requires a complete opening tag,
`^<tag(\s+[\w-]+="[^"]*")*>`. Rust over-escapes.

**On branch `0ffde41`, `has_inner_opening_tag` is unchanged.** The branch inherits the defect,
and its recorded green full suite plus eight performance gates did not surface it. Its
round-trip fixtures pass because `ch parse` decodes its own escaping faithfully — round-trip
fidelity is not cross-implementation parity, and no fixture covers this shape.

This is the cleanest available demonstration that the branch's evidence is not a substitute
for a differential against Python. It also tells us where its evidence is thinnest: shapes
the round-trip corpus never contained.

## 5. Colored output: priced, but priced as a library reimplementation

The claim that the branch prices colored search is **true**. `search_views::conversation_panel`
builds its body from `session_render::rich_message_lines`, which routes message text through
`markdown_lines` and tool results through `read_syntax_lines`. Both are real.

What they are, concretely: `session_render.rs` hand-writes a Rich Markdown renderer
(`parse_markdown_blocks`, `render_markdown_heading`, `render_markdown_list`,
`wrap_segments`) and a Pygments clone with per-language lexers — `python_tokens_with_state`
with f-string expansion, `shell_tokens_with_state` with heredoc and arithmetic handling,
plus HTML, CSS, JavaScript, JSON and Markdown lexers — emitting hard-coded Monokai truecolor
SGR constants.

That is roughly 2500 lines reproducing two third-party libraries. It is written, and on the
corpus it was tuned against it presumably matches. But its input is arbitrary user code
pasted into transcripts, in any language and frequently malformed. A fixed-corpus byte diff
can demonstrate parity on that corpus; it cannot bound divergence off it, because the space
of inputs is the space of all code.

So colored parity here is statistical, not provable. That is not an argument against shipping
it — it is an argument for naming the standard before we build to it.

**My recommendation, for the first mate's call, not mine:** accept best-effort colored parity
behind a fixed-corpus byte-diff gate, and state plainly in the change log that colored
highlighting is a reimplementation whose fidelity is corpus-bounded. The alternative worth
weighing is keeping colored output on Python for this mission and cutting over only the
uncolored route, which loses the "no Python on the completed route" property for exactly one
output mode. I lean to the first, because the second fails the charter's completion bar.

I also agree the three tests in `test_colored_rendering.py` cannot be the gate. They assert
substrings and SGR codes, and this project has already shipped a width bug that survived every
one of them because they all pinned a single console width.

## 6. Reconciliation items against a moved `main`

1. **Empty optionals — sized, and I had the direction backwards.** I first wrote that the
   branch changed `optional_string` and that `main` fixed the same defect differently. Wrong.
   `main` changed it, at `47b3db9` on 2026-08-26, and the branch simply predates the fix.

   `47b3db9` touches both files I own, in both directions of the codec:
   - `model.rs::optional_string` went from `Some(value.clone())` to
     `(!value.is_empty()).then(...)`, so an empty string in the input normalizes to absent.
   - `codecs.rs::parse_document_message` gained a strip of nine empty attributes —
     `branch`, `sourceToolUserId`, `agent_id`, `subagent_type`, `name`, `model`,
     `custom_type`, `status`, `date` — on the XML-to-JSON side.

   The branch has **neither**. Verified: its `optional_string` is the pre-fix body, and its
   `codecs.rs` has no such strip. So it would render `branch="" status="" agent_id=""` where
   `main` renders nothing. Accepted behavior on `main`, confirmed by running the fixture that
   commit added:

   ```
   ch parse -f xml tests/data/parse-command-fixtures/inputs/empty-optionals.json
   -> <user-message i="1">        # no branch, status or agent_id attributes
   ```

   This matches Python, where `get_wrapper_attrs` and `to_json_dict` both gate on truthiness.

   **Consequence for how I adopt branch code:** the branch is the stale side in both of my
   files, not a peer with a competing fix. Anything I take from its `model.rs` or `codecs.rs`
   gets rebased onto `main`'s versions. It is not a merge and not a comparison of equals.
2. **Terminal width.** `main` moved terminal-width resolution to `ioctl` across fds 0/1/2 on
   2026-08-27. The branch predates that and its renderer computes its own width. Every
   width-dependent byte in the colored output depends on which resolution wins.
3. The branch deletes `src/chats/session_scan.py` and rewrites `commands/search.py`,
   `cli.py`, `formatting.py`. Under our charter, production search stays Python until one
   cutover, so none of those deletions can land early.

## 7. What I need at G2

- **`rust/codecs.rs` and `rust/model.rs` assigned to me.** Both need my changes and both are
  shared with `ch parse`.
- **A ruling on `session.rs`.** Its visibility/shortening/tool-filter layer is mine; its
  command shell is out of charter. If anyone plans to lift that file wholesale, we collide.
- **The colored-renderer standard decided before that slice opens** (§5).
- Confirmation that agent transcript merging stays out (§3).

Unchanged from my map: I take `Option<Provider>` rather than a path, so the lifted core is a
dependency of the route and not of my slices. `scan_resolution_facets` is mine but off the
native search route, so I am not writing a native decoder for it this mission.
