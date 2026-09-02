# M3 — every `saturating_sub` whose Python counterpart is a plain `-`

**STATUS: F18 is fixed and pinned; the sweep is complete.** The three recorded
width reductions were **deliberately left alone**, bounded to a console narrower
than eight columns. **That is a closed decision, not an outstanding task** — a
successor tidying them into a signed-width refactor would be re-opening it.

**Why the sweep exists.** `saturating_sub` is the idiomatic Rust translation of a
Python subtraction and is **only correct where the negative case cannot arise**.
`session_render.rs` ports arithmetic written in a language without unsigned
integers, so the class is systematic rather than incidental. Named by
`slice-reviewer` after finding the first instance.

## Fixed

**F18 — `divide_line`'s remaining-space test.** Rich computes
`remaining_space = width - cell_offset` signed, and a negative value fails
`>= word_length`; a floor at zero **succeeds** for a word measuring zero cells.
A word carries the whitespace to its right, so a word that fits can leave the
cursor past the width, and `\u{200b}` is whitespace to neither language, so it
forms a word of no width at all.

    divide_line("abc   ​", 5)     Rich -> [6]     saturating -> []

Now signed. Pinned by `wrap_tests` against Rich's own answers, with a
falsification that reimplements the floor-at-zero version and requires it to
still disagree — so the case cannot stop reaching the branch it guards.

## Checked and safe, with the reason

**Justify padding** (`Lines.justify`, three sites). Each follows
`truncate(width, overflow)`, which leaves `cell_len <= width` for every overflow
but `Ignore` — and `Ignore` is never set on this surface, because markdown's
overflow is `Fold` throughout.

**`Text.truncate`'s `max_width - 1`.** Reached only under `Ellipsis` overflow,
which the chrome uses and markdown does not. Python at width 0 would pass `-1`
into `set_cell_size`, whose ASCII fast path then drops a character — so the
negative branch is not merely unreached here, it is **wrong in Python too**.

**`LeftRail`'s glyph subtraction.** Python is `max(1, max_width - len(glyph))`,
which clamps the negative itself. Identical for every width.

## Recorded, bounded, not changed

**Three width reductions can go negative in Python and floor at zero here**:
`BlockQuote`'s `max_width - 4`, `ListItem.render_bullet`'s `- 3` and
`render_number`'s `- number_width`.

Python passes the negative into `options.update(width=…)`, where `chop_cells`
receives a negative width, `range(0, len, negative)` is empty, and the fold loop
therefore inserts no breaks. The two routes may then wrap differently.

**Reachability: the panel interior is the console width minus four, so a
blockquote needs a console narrower than eight columns.** The pty differential's
narrowest width is 40 and Rich itself floors a terminal at a usable width. Not
proved unreachable — bounded, and left alone rather than churned into an
unverified signed-width refactor across the module.

**The general rule this leaves:** on this surface, every width that a port
reduces should be read against its Python original, and the question asked each
time is not *can it be negative* but *is the negative branch reachable from
here*. Three of the answers above are "no because of a property of the caller",
not "no because of the type".
