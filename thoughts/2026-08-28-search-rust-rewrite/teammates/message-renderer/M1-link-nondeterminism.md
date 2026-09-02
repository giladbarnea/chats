# M1 — the oracle is not byte-deterministic on markdown links

**STATUS: accepted in full, all three consequences.** Normalising `id=<digits>`
in OSC-8 on both sides now applies to **every** comparator that runs over real
message bodies, not only this seat's. No corpus carries a link yet, so nothing
normalises it today — **the first one that does will fail intermittently and look
like a real defect.**

**Status: measured end to end through the shipped product, three times.**
**Consequence: byte parity on link-bearing content is impossible for anyone,
including Python against itself.**

## What was measured

Rich writes a markdown link as an OSC-8 hyperlink carrying a session id:

    \e]8;id=964820;https://example.com\e\  \e[4;34mlabel\e[0m  \e]8;;\e\

`rich.style.Style` sets `_link_id = str(randint(0, 999999))` when a link is
present, so the id is drawn fresh for every `Style` instance. Three consecutive
runs of `ch-legacy search` over one fixture session whose text is
`see [label](https://example.com) here needleword`:

    id=472252
    id=435269
    id=120321
    byte comparison of run 1 against run 2: DIFFERENT

Nothing else in the output moved. The clock was pinned with `CH_NOW`, the pool
was a private `HOME`, and `--color always` was passed.

## How common the shape is

Census over 400 real session files, 12,963 text blocks, parsed with the exact
parser Rich uses (`MarkdownIt().enable("strikethrough").enable("table")`):

    link_open        9,165 occurrences
    code_inline    104,933
    strong          25,510
    hardbreak       25,705
    html_inline     15,770
    em               7,672
    image              196

Links are ordinary content, not a tail. `probes/markdown_structure_census.py`.

## Why no gate has seen it

The G4 coloured cases and the 25 recorded contract cases contain no markdown
link. The pty differential proves determinism by capturing twice and diffing —
**the right check, which passes because the corpus cannot reach the defect.**
Same shape as the branch's ASCII-only highlight corpus: an instrument that
describes itself accurately and cannot see the surface.

## What follows, and what does not

**Does not follow:** that markdown rendering is unprovable. Every other inline
and block construct measured is deterministic. This is one field of one
construct.

**Does follow, and it needs a ruling:**

1. **A byte comparator over real content must normalise `id=<digits>` inside
   OSC-8 sequences, on both sides.** Without it a gate that includes any link
   fails at random. The normalisation belongs in the differential, next to the
   `\r` strip and the `$HOME` substitution, because it is the same class of
   thing: a machine-varying field that is not the subject under test.
2. **The native route reproduces the oracle by emitting an id of the same
   shape.** A fixed id is a smaller divergence than an absent one — terminals
   use the id to join a hyperlink split across lines, so dropping it changes
   behaviour in the terminal, not just in the bytes. Whether the digits are
   random or fixed is then unobservable to any comparator that normalises them,
   and observable to nothing else.
3. **The claim "markdown is deterministic and provable" holds with one stated
   exception.** Recorded here so the exception travels with the claim rather
   than being rediscovered by a red gate.
