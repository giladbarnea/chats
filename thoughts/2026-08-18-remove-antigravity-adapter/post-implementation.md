---
date: 2026-08-18
title: Remove the Antigravity adapter
---

# Remove the Antigravity adapter

The project removed the Antigravity adapter completely instead of keeping a compatibility stub or named absence test.

The scope covered project-owned code, provider registration, parsing, search behavior, documentation, direct tests, fixtures, and generated caches. The user explicitly excluded `.antigravity/**`, which stayed byte-for-byte unchanged. Git history and published artifacts also stayed outside the scope.

The work followed a remove, verify, and repeat loop. Historical project documents remained in scope because the acceptance criterion required no current project-owned Antigravity trace.

Verification found traces beyond normal source searches. Opaque transcript fixtures contained adapter text, and deleted SQLite cells retained raw strings until a database vacuum removed them. These findings expanded cleanup without restoring or replacing adapter behavior.

The baseline already contained timing-sensitive performance failures and a Hatch build failure from an external skill symlink. The same failures remained after removal, with no new failure.

Final verification passed 944 tests with 3 skipped tests and passed all 13 shell tests. Runtime providers are now Claude, PI, and Codex, as reflected in `README.md` and `ARCHITECTURE.md`.
