# Help coverage audit

The help pages now describe the actual capabilities, including advanced syntax, without treating help as a copy of the README.
Both pages stand alone. Shared tool and shortening syntax appears on each page so search users need no second lookup.

The audit used the argument parsers, session resolver, visibility rules, and [tool](../../TOOL_SPEC.md) and [shortening](../../SHORT_SPEC.md) contracts.
This exposed missing title lookup, boolean search rules, conversion direction, filter forms, and precedence rules.
It also exposed overclaims about `--all`, role filters, and removal across providers.
Catalog work was excluded at the user's request.

The content review showed that complete syntax alone did not teach readers how to combine options.
Examples now come before general rules. The final pass clarified lookup order, content categories, shortening, and flag differences between commands.
The [last Claude review](claude-review-before-search-section.md) preceded the combined help page. The final wording received a direct read-through of both rendered pages.
Bare help now covers search too, so the two common workflows need only one help call. YAML examples make metadata and the distinction between `-l` and `-ll` explicit.

Original search help recordings remain intact. Revised help has a separate reviewed fixture with an explicit source in the manifest.
Width tests compare unusual `COLUMNS` values with Python's resolved numeric width because the old wording no longer applies.

Validation covered documented examples, all shortening value forms, tool-filter forms, copied files, and invalid boolean queries. The help checks cover both pages and terminal widths.
The initial full-suite comparison had 54 baseline failures and 53 final failures. Every final failure also appeared in the baseline.
Verified that global `ch`, the project environment, and the local build show identical help. The editable install points to this checkout.
