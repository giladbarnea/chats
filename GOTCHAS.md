---
name: gotchas
description: A gotcha is fairly confidently signing off on something that later on proved to be at least partially wrong due to wrong assumptions.
---

# GOTCHAS

## 2026-05-04

Assumed a selection must fully materialize every candidate before filtering. When a query needs only a few fields and can short-circuit, eager full materialization is the trap: probe the minimal facets the predicate needs, push the filter to the scan, and stop at the first match. In our case, `ch -1 -d ...` loaded full metadata and reread files for `cwd` instead of streaming `cwd` newest-first and stopping.

Assumed an input was already ordered the way a short-circuit depended on. Optimizing a scan to stop early silently makes correctness depend on iteration order — a dependency the eager version never had. In our case, the dir fast path did `reversed(files)` assuming stat-mtime order, but the list was discovery-ordered, so it matched the wrong session.
