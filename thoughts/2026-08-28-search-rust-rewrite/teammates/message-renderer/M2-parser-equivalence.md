# M2 — the `markdown-it` crate against `markdown-it-py`, measured

**STATUS: this was the condition on ruling L129 and it is satisfied.** The
`markdown-it` crate is adopted, the five conversion rules are implemented in
`session_render.rs`, and the two residual classes stand as recorded. **Not an open
question.**

**The first mate's condition on the L129 ruling.** Two ports of one reference can
drift by version; the whole argument for a crate over a hand-written parser is
that the drift is a **measurable, enumerable list**. Here it is.

## Result

Over 20,000 real transcript text blocks from 800 session files:

    raw text                            19,976 of 20,000 identical   24 differ  (0.12%)
    after the product's tag escaping    19,977 of 20,000 identical   23 differ  (0.115%)

The second row is the one that matters for message bodies:
`_message_content_renderables` escapes tag-like text before a TEXT part reaches
`Markdown`, so the escaped corpus is what the product actually parses.

**The comparison is falsifiable and was observed to fail.** Perturbing one text
token per block turns 1,989 of 2,000 blocks red. The 11 that stay green carry no
text token to perturb — a pure fence or an empty block — which is the correct
answer, not a hole.

`probes/parser_equivalence.py --binary <mdprobe> [--escape-tags] [--falsify]`.

## What is compared, and why that is the right unit

Both sides emit the **flattened** stream `rich.markdown` consumes —
`_flatten_tokens` drops the `inline` wrapper and yields its children, except for
`image` and `fence`. The parser's internal shape decides nothing; that stream
decides every rendered byte.

Fields compared are the ones Rich reads: `type`, `tag`, `content`, and the
attributes it looks up. Three exclusions, each read out of the Rich source rather
than assumed:

1. `info` outside a fence. On `list_item_open` it carries the list marker and
   reaches nothing.
2. `html_block` content. It reaches `UnknownElement`, whose `on_text` is a no-op
   and whose render yields `()`.
3. Trailing whitespace on `fence` and `code_block` content.
   `CodeBlock.__rich_console__` does `str(self.text).rstrip()` first.

## Five differences that are the conversion's job, not the crate's

Found by the comparison and fixed in the AST-to-token conversion. **Each is a
rendered-byte difference, not bookkeeping.**

1. **Adjacent text nodes must be merged.** `markdown-it-py` runs `fragments_join`
   and `text_join`; the crate keeps an escape or an entity as its own node.
   Measured: two same-styled appends emit `\e[1mfoo\e[0m\e[1mbar\e[0m` where one
   emits `\e[1mfoobar\e[0m`. Unstyled runs are unaffected, which is why a plain
   paragraph hides it.
2. **`TextSpecial` is text.** `markdown-it-py` renames `text_special` to `text`
   in `text_join` so it can merge; the crate keeps a distinct node.
3. **A tight list item's paragraph must be restored.** The crate drops the
   paragraph node; `markdown-it-py` keeps it and marks it hidden. **Rich never
   reads `hidden`**, so it builds a `Paragraph` either way — and text arriving in
   a `ListItem` outside a paragraph is text `render_bullet` never renders. It is
   restored per **run** of consecutive inline children: an item holding text
   followed by a nested list must not put the list inside the paragraph.
4. **An empty paragraph, heading or table cell still carries an `inline`
   token**, which survives flattening because it has no children to yield
   instead. It renders nothing but sets the block-separator flag, so it is not
   inert. An empty *list item* carries nothing at all, and a blockquote carries
   no such token either.
5. **Table cell alignment.** The crate holds alignments on the table; Rich reads
   a `style` attribute on each cell, which `TableDataElement.create` turns into a
   justify method.

## The 23 that remain, as two named classes

**Class 1 — an HTML block interrupting a paragraph. Minimal repro:**

    Arguments:
    <SOURCE>
    more

    markdown-it-py   paragraph_open, text, softbreak, html_inline, softbreak, text, paragraph_close
    markdown-it      paragraph_open, text, paragraph_close, html_block

CommonMark type 7 — a complete open tag alone on a line — **may not interrupt a
paragraph**. `<div>` is type 6 and may; `<SOURCE>` is not a known block tag and
may not. The crate starts the block anyway. **The consequence is not cosmetic:
an `html_block` renders as nothing, so the text disappears.**

Its exposure on the TEXT path is small because the product escapes tag-like text
first, and the remaining reach is tool bodies, which are not escaped.

**Class 2 — emphasis delimiter runs in pathological text.** A handful of blocks
of minified JavaScript embedded in JSON, where `_` runs resolve to different
`em` spans. Not reduced to a minimal case; recorded as the residue with its
population, which is 4 blocks in 20,000.

## What this licenses, stated narrowly

The crate reproduces `markdown-it-py`'s stream on **99.88%** of real message text
once the five conversion rules are applied, and the residue is two named classes
rather than an unbounded surprise surface. That is the property a hand-written
parser cannot have at any accuracy, because its divergence set is not
enumerable — which was the argument for the ruling and is now measured rather
than asserted.
