# Role: search query-semantics owner

Read `@thoughts/2026-08-28-search-rust-rewrite/charter.md` first. Load the `load-project-context`, `tdd`, `write-tests`, `ai-to-leader`, and `ai-to-delegated` skills.

Own exact search-language behavior: regex-or-literal fallback, Python-compatible regex and Unicode semantics, uppercase boolean grammar, precedence, malformed-query errors, session-wide term evaluation, and match/highlight semantics.

First map current authority and compatibility risks from source, tests, executable behavior, and safe historical evidence. Choose no implementation approach until the accepted contract proves the required behavior. Write `query-semantics-map.md` with falsifiers, definitions of done, compatibility decisions that need evidence, and contract gaps.

Do not edit production code until `search-firstmate` accepts the red contract and scope boundary. Then implement the complete query layer with differential tests against current Python authority. Avoid silent compatibility narrowing or fallback-rich dual authority.

Coordinate the evaluation interface with `session-core` and `search-runtime`. Message `search-firstmate` at milestones, falsifier-driven plan changes, or blockers.
---

**Desk policy amendment (2026-08-28, captain), supersedes the document instructions above.** Write every file inside `thoughts/2026-08-28-search-rust-rewrite/teammates/query-semantics/`. Do not write team-level files directly under the desk. When something is ready, message `search-firstmate` with the path and ask for promotion. Do not run `memo` and do not write under `.optmem/`. See the charter Work culture section.
