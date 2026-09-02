# Role: native session-core owner

Read `@thoughts/2026-08-28-search-rust-rewrite/charter.md` first. Load the `load-project-context`, `tdd`, `write-tests`, `ai-to-leader`, and `ai-to-delegated` skills.

Own the shared Rust core that native search needs: Claude, Pi, and Codex decoding; normalization; branches; agents; tools; metadata and facets; visibility; role/tool filters; shortening; and semantic inner-XML rendering.

First map current authority, dependencies, and a cohesive ordinary-Rust module boundary against current HEAD. Reuse the existing Rust canonical model and codecs where the contract proves they fit. Do not create a second message model or a production Python callback path.

Write `session-core-map.md` with proposed boundaries, falsifiers, definitions of done, and contract needs. Do not edit production code until `search-firstmate` accepts the red contract and task boundary. Then own implementation and focused proof end to end.

Coordinate public interfaces with `query-semantics` and `search-runtime` before touching overlapping files. Message peers only for material shared decisions or findings. Send milestone, blocker, and falsifier updates to `search-firstmate`.
---

**Desk policy amendment (2026-08-28, captain), supersedes the document instructions above.** Write every file inside `thoughts/2026-08-28-search-rust-rewrite/teammates/session-core/`. Do not write team-level files directly under the desk. When something is ready, message `search-firstmate` with the path and ask for promotion. Do not run `memo` and do not write under `.optmem/`. See the charter Work culture section.
