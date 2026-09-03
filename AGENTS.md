---
updated: 2026-05-07
---
# Global Instructions

## Ecosystem

You're on a Mac M2 Pro running Tahoe 26.0. In addition to base Unix coreutils and Python 3, you can also leverage the following tools: `rg`, `fd`, `jq`, `yq`, `http`, `uv`, `npx`, `ruff`, and more.

<core-tools>

### Core Tools

<tool-usage>

**1. `rg`**

  Great for searching patterns/regex across a directory or specific files. You can customize the output with its CLI options—for example, show line numbers (`-n`) or list only matching files (`-l`). It’s almost a drop-in replacement for `grep`, so familiar options like `-C` work too.
  *Bottom line: use `rg [-u]` instead of `grep` and the built-in `Search`.*

**2. `fd`**

  Great for finding files.
  *Bottom line: use `fd` instead of `find`.*

**3. Built-in tool: `Read`**

  *Bottom line: **Always read files in full.***

**4. `FORCE_OMZ=1 /usr/bin/env zsh -ic '...'`**

  If some executables aren’t available in `PATH`, try running the command this way. It automatically sources the user’s `.zshrc`, which loads key environment variables and `PATH` entries, making lots of additional commands and tools available.

**5. `gsd`**

  Stands for git structured diff. A superior drop-in replacement for `git diff` that prints the diff in a structured, xml-like format. It's much more readable and guarantees that you understand the diff completely.
  Run it with `gsd [git diff arguments]'`. Like native `git diff`, it should also be used to diff files outside the version control with the `--no-index` flag.
  Drop-in examples: `gsd origin/dev...tommy-log-request-id-VLLM-405 --stat`, `gsd --no-index <(sort -u < requirements.txt) <(sort -u < requirements-dev.txt)`, `gsd --no-index --no-function-context --unified=0 --inter-hunk-context=0 ~/.gemini/GEMINI.md ~/.claude/CLAUDE.md`.
  *Bottom line: use `gsd` instead of `git diff`; use `gsd --no-index` instead of builtin `diff` to diff files outside regardless of version control.*

**6. Avoid pagination and interactive commands**

  Whenever a command might trigger either, use `git --no-pager` for all git commands (e.g., `git --no-pager log`) and the equivalent options for other tools. Pipe to `| cat` liberally to ensure commands behave non-interactively.

**7. Read files in full**

  Always read files in full, even if only parts of them (allegedly) are relevant. Wider context is good.

</tool-usage>

<python>

### Python

- Avoid running bare `python` or `python3` commands. If the current working directory is a project with a `pyproject.toml` file, always use `uv run -p python3` to run Python scripts. If you're not in a project with a `pyproject.toml` file, use `uv run -p python3` to run Python scripts.
- In general, you are encouraged to write temporary Python and shell scripts to disk and run them. This is the best approach for more complex tasks. Python scripts can import any helpful third-party libraries you want, and run with: `uv run -p python3 [--with='dependency1','dependency2'] python3 script.py`. For example, if the script needs `pandas`, `yfinance`, and `rich`, run `uv run -p python3 --with=pandas,yfinance,rich python3 script.py`. Scripts have network access. Just remember to remove the scripts after you no longer need them.
- Never modify global system state: no `brew install`, no `pip install`, etc. Always prefer transient execution with `uvx -p python3`.
- If a library doesn't support python3, adjust `-p python3.*` accordingly. In projects with pyproject.toml or .venv/ directory, just run `uv run ...` without the `-p ...` flag (version already defined at project level).
- For some cleanliness static analysis, you can run `FORCE_OMZ=1 /usr/bin/env zsh -ic 'ruffc dir/or/filepath'`. Take the diagnostics with a big grain of salt, only fix what hints at real problems.

</python>

</core-tools>

---

<tips>

## Tips

**Bash scripts**: When running longer ad-hoc shell scripts, syntax errors are common. To stay on the safe side: 
  - “open up” the code with a sparse, simpler style, rather than doing syntactic acrobatics just to be terse. Boring is better than clever.
  - Write the script to /tmp/<whatever>.sh with a `#!/usr/bin/env zsh -i` shebang and run it. This is safer and more token-economic.
**Python scripts**: It’s recommended to use the following "frontmatter" at the top of the script to declare dependencies and other metadata:
```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["dependency1", "dependency2"]
# ///
```
Then run the script with `uv run script.py`. No need to specify the Python version or dependencies in the command line.

</tips>

---

<development-rules>

## Development Rules

<tenets>

### Be Bold, Precise and Minimalistic

1. Fail loud and early.
2. Complexity is the enemy.
3. Simplicity is the way to go.
4. Adding a logical branch is unjustified unless proven otherwise.
5. No nested `if` statements.
6. Write declarative, upfront code. The more the source code feels like a high-level configuration rather than an implementation, the better. Just like a Pydantic BaseModel definition is easier to understand than a vanilla class with an implemented `__init__`, manual value and type validation, manual state setting, etc.
7. No squirmy code. Don’t carry over cascading uncertainty via defensive programming. Be straightforward and explicit.

</tenets>

<principles>

1. Do not abbreviate variable, function or class names. Use complete words. Write clean code.
2. Write code that fails early and clearly rather than writing fallbacks to “maybe broken” inputs. Zero “Just in case my inputs are corrupted” code. Fallback-rich code explodes complexity and silently propagates bugs downstream. Good code assumes its inputs are valid and complete—it trusts upstream code to have done its job. This ties closely to separation of concerns. And if something important fails, or an assumption is broken, fail early and clearly. Broken code should be discovered early and loudly and fixed quickly; It should not be tolerated nor worked around.
3. Write highly cohesive, decoupled logic.
4. Utilize existing logic when possible. Do not re-implement anything.
5. Write flat, optimized logical branches. Avoid nested, duplicate-y code. Write DRY and elegant logic.
6. Prefer `import modulename` and call `modulename.function()` rather than `from modulename import function`.
7. Add a doctest example to pure-ish functions (data in, data out).

</principles>

### A Cautious Note About Refactoring

If you hit a design or architecture issue that's causing real friction for you, and reworking it wouldn't be a project in itself, go ahead and refactor it. I'd rather that than you doing acrobatics to work around a past design decision that no longer serves the problem.

</development-rules>

---

<python-type-annotations>

### Python Type Annotations

1. Use modern annotations. <no>`Optional[Dict]`</no>, <yes>`dict | None`</yes>.
2. Parametrize container types until you hit a bottom primitive type. No `list`, yes `list[int]`. No `dict`, no `dict[str, list]`, yes `dict[str, list[int]]`.
3. Try to type annotate to all function arguments, return types, and variables, as long as it makes sense.
4. Don’t use `Any`. If you don’t know the type, that’s a smell — make a small effort to discover it, then annotate accordingly.
5. Prefer capturing the protocol rather than concrete types. For example, if a function only iterates over a passed value, annotate the argument as `Iterable[...]` rather than `list[...]`. Duck typing is good.
6. Use a dataclass or pydantic model for dicts that play a meaningful role in the code.
7. `Literal["foo", "bar"]` can be helpful.
8. `StrEnum: SAME = "SAME"` can also be helpful.

</python-type-annotations>

---

<core-engineering-philosophy>

## Core Engineering Philosophy

1. Avoid increasing complexity without a truly justified reason. Each new line of code or logical branch increases complexity. Complexity is the enemy. In your decision-making, ask yourself how you might **REDUCE complexity**, rather than just solve the immediate problem ad-hoc. Oftentimes, reducing complexity means **REMOVING code**. If done right, removing code is better than writing a solution because it removes the circumstances that give rise to the problem in the first place. It’s like clearing Tetris blocks — it simplifies and creates more space.
2. Prefer declarative code design over imperative approaches. From a variable to an entire system, if it can be declaratively expressed upfront, do so. Make the full picture visible straight up and avoid requiring readers to dive in. Embedding flow and logic in sprawling implementations creates difficulty.
3. Avoid overengineering and excessive abstraction. Abstractions have to be clearly justified. Simplicity and clarity are key.
4. Do not write comments in code unless they are critical for understanding the “why”. Especially, do not write “journaling” comments saying “modified: foo”, “added: bar” or “new implementation”, as if to leave a modification trail.
5. Do NOT fix linter errors unless instructed to do so.
6. Docstrings should be succinct and direct. 1–2 sentences max of what the function does and its role in its larger calling scope. No need to document arguments and return type: use type annotations for that. Do document if it intentionally raises exceptions.

</core-engineering-philosophy>

---

## How To Approach a Task

<how-to-approach-a-task>

The following points are close to my heart:
1. Before starting your task, you must understand all the affected code downstream and all the affecting code upstream. Not only the blast radius, but also whether we’re going to transfer a power plant that a town nearby relies on. Are we going to redirect a water pipe that an adjacent city consumes? How far along the stack does this go? Map out the moving parts and coupling instances before thinking and planning. Use the appropriate agents for that.
2. If you are fixing a bug, nail down the root cause before thinking of a solution.
3. When making changes, be absolutely SURGICAL. Every line of code you add incurs a small debt; this debt compounds over time through increased complexity, maintenance, bugs, and cognitive load. Therefore, make only laser-focused changes.
4. No band-aid fixes. When encountering a problem, first brainstorm what possible root causes may explain it. Band-aid fixes are bad because they increase complexity significantly. Root-cause solutions are good because they reduce complexity.

</how-to-approach-a-task>

---

## Being an Effective AI Agent

<being-an-effective-ai-agent>

1. Know your weaknesses: your eagerness to solve a problem can cause tunnel vision. Avoid tunnel-vision-stemming patterns: Don't fix a problem at the cost of unintentionally breaking something else that was out of your field of view; Don’t deviate from the existing design or from established patterns. The solution is to look around beyond the immediate fix, be aware of (and account for) coupling around the codebase, integrate with the existing design, and periodically refactor.
2. You do your best work when you can verify yourself. With self-verification, you can and should practice continuous trial and error instead of a single shot in the dark.

</being-an-effective-ai-agent>


---

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

Call `memo note "<1 line, max 280 bytes>"` whenever you learn something new, or something worth keeping happens. That covers a lesson worth real effort, a fact or insight the user teaches you, anything you learn about their life (even indirectly), any event of lasting effect.
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
3. **Repeated and proven:** It applies across tasks, agnostic of domain, and has already mattered more than once.
4. **Expensive to relearn:** Forgetting causes meaningful waste, frustration, or risk.
5. **Not stored elsewhere:** Code, documentation, or project instructions do not already preserve it.

**Good candidates:**

 - Stable collaboration and transport preferences.
 - A validated recurring failure pattern and its remedy.
 - A durable product principle that guides many unrelated decisions.
 - A user fact that consistently changes how the agent should communicate or work.

**Do not propose:**

- Current task, branch, or commit state.
- Temporary conditions or tuning values.
- Facts already visible in code or documentation.
- One-off feedback or speculative lessons.

**Choose the correct home:**

OptMem does _not_ own:
- Rules needed in every session belong in `AGENTS.md`. Updates to `AGENTS.md` are rare (once every few weeks, if at all) and must be confirmed by the user.
- System knowledge: project documentation
- WIP and continuation state: dedicated desks (typically `{thoughts/efforts}/<mission-slug>/...`)

OptMem _does own_:
- Durable tacit wisdom belongs in OptMem, as defined above.
- Explicit user memory requests.

**Note:**

If the user has dictated a different memory policy for the current project, it should of course take precedence over these defaults. A project-specific policy should of course be memorized.

## Memo’s role vs the rest of the project’s documentation means 

Take the generalized principles from the following specification to fit the current project’s domain.

**The canonical information layer structure should be:**

1. **Source documents own evidence.**  
   Meeting notes own observations. Financial documents own payment facts.

2. **`README.md`’s own the present truth.**  
   They explain what exists, how it works, and how to operate it.

3. **Memo owns project change over time.**  
   It records decisions, reversals, incidents, client feedback, and material validations.

4. **`AGENTS.md`’s own operating rules.**  
   They tells agents how to work in this project.

5. **Code owns implementation detail.**  
   READMEs should not restate details that the code makes obvious.

### When Memo records a present truth (README overlap) 

The angle must remain different.
A decision can affect both Memo and the README without duplicating their information angle.

**Memo:**

> 2026-08-23: Abandoned the native app because durable Apple distribution required a paid account. The Safari PWA became the phone client.

**README:**

> The phone client is a Safari PWA.

Memo owns the change and its reason. The README owns the resulting current state.

### Memo should record only material changes

Include:

- A product or architecture decision and its reason.
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

