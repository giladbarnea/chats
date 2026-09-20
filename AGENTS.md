## Memory

Your memory is OptMem (github.com/giladbarnea/OptMem), scoped to this project:
- The tool is `memo` (on PATH; wrapper at `~/.local/bin/memo`, real file in `~/dev/optmem`)
- Your memories are in `<this repo>/.optmem/memory`

OptMem outlives every session, compaction, model and vendor change.
Without it you do not know who you are, or what was decided and tried.

### At startup: activating OptMem (mandatory)

Run `memo wake` before any other tool call, in every session, and
then do exactly what it prints, to the end of its output.

### While working: register memories (mandatory)

Call `memo note "<1 line, max 280 bytes>"` whenever something worth keeping happens. That covers a lesson worth real effort, a fact or insight the user teaches you, any event of lasting effect.
Do not register redundant memories.
If `memo note` asks a compression: do it before your next action.
Never edit or delete anything under `.optmem/memory`: the tool manages it.

### When you need an old memory: search, or navigate

`memo recall <regex>` searches every memory, word for word.

Your memories also form a binary tree: #0-1, #2-3 ... exist as one-line summaries, pairs of those as #0-3, and so on -- every `#a-b` line wake prints is one node of it.
`memo zoom <a-b>` opens a node into its two halves, down to the raw memories.

### If you are being managed by another AI: perform only read-only memory operations

Only the leader AI is allowed to write or modify memory. Subagents and teammates are strictly limited to read available memory.

### There is a high bar to registering a memory

**A candidate memory should pass:**

1. **Durable:** Useful for many weeks and potentially months, not days.
2. **Behavior-changing:** Knowing it changes future agent conduct or MO.
3. **Repeated and proven:** It applies across tasks, agnostic of implementation details, and already mattered more than once -- or is likely to matter again going forward.
4. **Expensive to relearn:** Forgetting causes meaningful waste, frustration, or risk.
5. **Not stored elsewhere:** Code, documentation, git commit messages or project instructions do not already preserve it.

**Good candidates:**

 - Stable collaboration and transport preferences.
 - A validated recurring failure pattern and its remedy.
 - A durable product principle that guides many unrelated decisions.
 - A user fact that consistently changes how the agent should communicate or work.

**Do not propose:**

- Current task, branch, or commit state.
- Temporary conditions or tuning values.
- Facts already visible in code or documentation.

**Choose the correct home:**

OptMem does _not_ own:
1. Concrete system instructions needed in every session belong in `AGENTS.md`. Updates to `AGENTS.md` are rare (once every few weeks, if at all) and must be confirmed by the user.
2. Current system state knowledge: project documentation (`README.md`, `docs/`, etc).
3. WIP and continuation state: dedicated desks (typically `{thoughts,efforts,desks}/<yyyy-mm-dd>-<mission-slug>/...`).
Note: If `1`, `2` or `3` aren't established in the project, propose the user to set them up minimally. `desks` is preferred to the other two. 

OptMem _does own_:
- Durable tacit wisdom belongs in OptMem, as defined above.
- Explicit user memory requests.

**Note:**

If the user has dictated a different memory policy for the current project, it should of course take precedence over these defaults. A project-specific policy should be memorized outside `OptMem`.

## Memo’s role vs the rest of the project’s documentation

Take the generalized principles from the following specification to fit the current project’s domain.

**The canonical information layer structure should be:**

1. **`README.md`’s own the present truth.**
   They explain what exists, how it works, and how to operate it.

2. **Memo owns project change over time.**
   It records decisions, reversals, incidents, client feedback, major completed milestones, and so on.

3. **`AGENTS.md`’s own operating rules.**  
   They tells agents how to work in this project.

4. **Code owns implementation detail.**  
   No documentation or memory should restate details that the code makes obvious.

### When Memo records a present truth (README overlap) 

The angle must remain different.
A decision can affect both Memo and the README without duplicating their information angle.

> Example's situation: it's 2026-08-23 and the iOS app -> PWA decision and implementation just happened.
**Memo:**

> 2026-08-23: Abandoned the native app because durable Apple distribution required a paid account. We are pivoting to Safari PWA for phone client.

**README:**

> The phone client is a Safari PWA.

Memo owns the change and its reason ("why"). The README owns the resulting current state ("what").

### Memo should record only material changes

Include:

- A product or architecture decision and the reasoning behind it.
- A decision reversal.
- A verified production incident and its cause.
- Client feedback that changes the product.
- A validation that closes an important uncertainty.
- A durable constraint discovered through real use.

Exclude:

- Current commands, URLs, and component descriptions.
- Temporary setup that was removed.
- Routine deployments and successful test runs.
- Facts already owned by a meeting or financial artifact.
- Implementation details recoverable from code.
- General working rules already present in `AGENTS.md`.

## Keep the installed `ch` current

Project-specific exception to the global-state restriction: after each small, verified working step, reinstall `ch` from this repository root:

```bash
uv tool install --force --editable . --reinstall-package chats
```

This keeps the global command aligned with the local project, including its compiled Rust executable. Verify that installed `ch` behaves like the local build.
