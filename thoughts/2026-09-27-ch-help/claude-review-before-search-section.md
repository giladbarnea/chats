Both pages read well overall. The good parts share one trait: each rule comes with an example and one sentence that says why. The weak parts are rules with no example, or one-line option blurbs that assume vocabulary the page never defined.

**The most welcoming sections**

1. **The Examples blocks.** Each command has a plain sentence under it. The search examples teach the idiom `'.' -d . -ll` and the reader gets it at once.
2. **Query syntax's "Choose between" fix list.** It names the error case, shows the two correct forms, and says what each one means. This is the best procedural teaching on either page.
3. **Session lookup.** The lookup order is a plain list. The gotcha "a bare `ch 1` tries to find a session called 1" is exactly the sentence a new user needs.
4. **Additional content.** It defines subagents, rewind branches and Pi custom records in one sentence each before it names the flag.
5. **Search scope and output.** It states the flag collision plainly: search uses `-f` and `-s` differently from `ch SESSION`. Honest and short.
6. **Copied files.** It tells you what to keep in the file and what gets rejected. Actionable.

**The most telegraphic sections**

1. **The options table one-liners.** `--no-user` says "keeping explicitly enabled extras" but "extras" is never defined. `--no-metadata` says "plain XML sends metadata to stderr" and I do not know what plain XML is. `-T short` says "uses --short if set" and I am not sure whether that replaces the 500 or adds to it. The `catalog` command line names `sessions.yaml` and `pi` with no context.
2. **Shortening tools precedence.** "Count the matching filter's conditions. More conditions win. If counts tie, the last filter wins." The rule is complete, but I only trust it after re-reading twice. It is CSS specificity without saying so, and the `s` modifier lives in the same colon grammar as the conditions. That is the one section I would test before I rely on it.
3. **Shortening's "Message selection happens before these limits are assigned."** True, but it does not say why I should care. The reason is that `-- -5:` with progressive mode spreads 8 to N over the five messages, not the whole session. One example would fix it.
4. **Dates and result order in search.** It documents that sort order uses file mtime while date filters use transcript time. I understand it, but it reads as an apology for an inconsistency rather than as guidance. The reader is left asking why.
5. **Session pool filters preamble in `ch --help`.** "Recent indices" is jargon for `-1, -2`. The list of facts is correct but nothing tells me which one I will hit in practice.

**What I am still not confident about after reading**

1. For a boolean query like `docker AND timeout` without `-l` or `-f`, which messages does search show? Messages that match either term, or something else. The page says AND spans the whole session but never says what gets displayed.
2. Whether `-T` in search makes thinking searchable. The intro says all content options widen the scope, but the `-T` blurb only says "Include", which is display vocabulary.
3. Whether a filter that loses precedence still contributes its `:s` value to anything. The rule implies no, but I would run it to be sure.
4. What a "title" is versus a "summary". Summary is defined. Title is only implied by the `name` command.

The pattern is consistent. Wherever the text shows an input, its output and the reason in one place, I am confident. Wherever a constraint stands alone, I am not.
