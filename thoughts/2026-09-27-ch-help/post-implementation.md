# CLI help audit

Bare help covers session display and search because both are common workflows. Dedicated search help remains self-contained.
YAML examples make structured metadata discoverable and explain the choice between metadata records (`-l`) and IDs (`-ll`).
Catalog was excluded because the user plans to retire it.

## Complete syntax also needs procedural guidance

The audit compared help with the argument parsers, resolver, visibility rules, and [tool](../../TOOL_SPEC.md) and [shortening](../../SHORT_SPEC.md) contracts.
Correct syntax alone left readers unsure how to combine options. Reviewers trusted commands paired with an expected result and a reason.
Concrete examples clarified lookup order, boolean search output, content selection, flag meanings across commands, and which shortening filter wins.
The remaining wording fixes defined titles versus summaries, explained thinking limits, and distinguished transcript dates from file ordering.

Claude's last independent review said both pages “read well overall.” It preceded the Search section in bare help and the metadata examples.
The final pass used direct reading of the rendered pages and help tests. The review's actionable findings were addressed, except catalog's excluded wording.

## Verification preserved the original evidence

Original search help recordings remain intact. Revised help uses a separate fixture with an explicit source in the manifest.
Width checks compare unusual `COLUMNS` values with Python's resolved numeric width because the original wording no longer applies.
Validation covered documented examples, all shortening value forms, tool filters, copied files, invalid boolean queries, and terminal widths. The final help checks passed.
The initial full-suite comparison had 54 baseline failures and 53 final failures. Every final failure also appeared in the baseline.
Global `ch`, the project environment, and the local build produced identical help. The editable install pointed to this checkout.
