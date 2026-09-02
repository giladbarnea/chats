# Fully native `ch search` rewrite charter

## Mission

Move every public `ch search` shape into the package-owned Rust executable. The completed route must preserve public behavior and must not start, import, embed, call, or fall back to Python or PyO3.

Baseline: clean `main` at `9bf1e06`. The post-review fixes are committed at `47b3db9`.

Default session parsing and unscoped commands remain on `ch-legacy`. Build the shared provider/session core as ordinary reusable Rust modules so default session parsing can use it later.

## Complete dependency cone

1. Claude, Pi, and Codex JSONL decoding.
2. Message normalization, branches, agents, tools, metadata, and searchable facets.
3. Visibility, role/tool filters, and shortening.
4. Semantic inner-XML rendering, which defines search truth.
5. Query grammar, Python-compatible regex behavior, literals, and boolean evaluation.
6. Inventory, pool filters, candidate planning, confirmation, ordering, result modes, highlighting, streaming, paging, errors, and exits.
7. Native launcher routing, package proof, and direct no-Python process proof.

Do not ship an intermediate Python→Rust→Python production path. Keep production search fully Python until the full native route passes, then cut over once.

## Work culture

- Define 1–2 falsification probes and 1–2 positive definitions of done before implementation.
- Treat the current Python product as the behavioral oracle.
- Build red process contracts before production code.
- Work in small internal slices, but accept only one complete public green boundary.
- Follow evidence. If a falsifier disproves the plan, change the plan.
- Keep edits surgical. No unrelated cleanup, defensive fallbacks, or parallel production authorities.
- Direct shared checkout. Coordinate ownership before touching overlapping files.
- Workers do not commit independently. The first mate may create accepted checkpoint commits.
- **Desk policy (2026-08-28, captain).** Only `search-firstmate` writes team-level
  files directly under `thoughts/2026-08-28-search-rust-rewrite/`. Every teammate
  works only inside `teammates/<name>/` — throwaway material, temporary scripts,
  WIP notes, and draft artifacts. `search-firstmate` uses its own subdirectory for
  scratch work too. When a teammate has something ready, it messages
  `search-firstmate` with the path and asks for promotion. The first mate reviews
  and promotes accepted material to the shared desk.
  **This supersedes every role prompt in `prompts/` that tells a worker to write a
  shared document.** Read `write X.md` in a role prompt as `write
  teammates/<your-name>/X.md and ask for promotion`.
- **Memory policy (2026-08-28, captain).** Only `search-firstmate` may run `memo`
  or write under `.optmem/`. No other teammate touches either.
- **Pause policy (2026-08-28, admiral).** If the shared Claude usage or session
  limit is reached, or is close enough to stop work, pause the effort. Do not
  switch models, do not spawn replacements, and do not attempt recovery. Leave
  work in progress in `teammates/<name>/` and stop cleanly. The effort resumes
  later.
  **Therefore every teammate keeps `teammates/<name>/RESUME.md` current**: what
  is half-done, what comes next, and which production files carry uncommitted
  edits. A pause can arrive without warning, so the note is written as work
  proceeds rather than when stopping.
- Current source, tests, and installed-launcher evidence outrank `thoughts/`. Historical notes are untrusted until the context curator classifies them.

## Social dynamics

Roster: `search-firstmate`, `context-curator`, `contract-owner`, `session-core`, `query-semantics`, `search-runtime`, and `reviewer-profiler`.

`search-firstmate` owns the whole mission and edits no production code or tests. Every teammate communicates directly with the first mate through Claude Code native messaging.

Teammates own their scopes end to end. They message peers only for material cross-scope findings, blockers, or a genuine “1+1” connection. Do not redo a peer’s work.

Send the first mate short updates at milestones, when a falsifier changes the plan, when blocked, and before context gets low. Write durable results under this desk instead of reconstructing history in messages.

## Phases

1. Context relevance, current authority map, red contract, and performance baseline.
2. First-mate acceptance of boundaries and task DAG.
3. Implementation by scope owners with continuous differential proof.
4. Independent review and repairs.
5. Exact full suite, package/launcher/no-Python proof, fixed-corpus performance proof, scoped diff check, and final change log.

## Completion

Done means every supported `ch search` shape preserves behavior and uses one Rust authority. Every falsifier has been attempted, every definition of done proved, `./tests/run_all.sh | cat` is green, package and installed-launcher proof is green, and representative performance gates pass on a recorded corpus.
