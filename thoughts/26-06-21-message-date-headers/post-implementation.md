---
date: 2026-06-21
task: message dates in XML attributes and Rich panel titles
---

# Message Date Headers

Added message-level dates at the `Message` boundary because both affected display
paths already depend on `Message` for wrapper metadata. This kept the change out
of command orchestration and avoided separate parse/search formatting rules.

Plain XML now emits a `date` wrapper attribute only when the message has a
timestamp. That preserves raw transcript behavior for messages without source
timestamps while adding the requested `YYYY-MM-DD` value for normal session
JSONL messages.

Rich titles reuse the same parsed timestamp but format it as a compact calendar
label with an ordinal day. The date is appended after the existing model suffix,
so the existing title scan order remains role, index, model, then date.

The relevant context docs were `README.md` and `ARCHITECTURE.md`, especially the
recent colored-view split: plain XML is the piping format, colored output is the
tag-free panel format. Tests were added at both user-facing surfaces rather than
only at the helper level.
