# Global Instructions

## Ecosystem
You're on a Mac M4 Pro running Tahoe 26.0. In addition to base Unix coreutils and Python 3, you can also leverage the following tools: `rg`, `fd`, `jq`, `yq`, `http`, `uv`, `npx`, `ruff`, and more.

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

<web-fetching>
### Fetching Web Pages & Files
Use the `rf` tool (stands for robust fetch) to fetch and convert web content or documents to Markdown.
Usage: `rf [-h] [--cache] [--timeout N_SEC (default 30)] [-s,--scraper {playwright,firecrawl,markitdown}] URL`
</web-fetching>
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

<using-sub-agents>

## Using (Sub-)Agents
Dispatch an agent whenever you need to either:
a) explore a particular system or a major domain within the codebase (`codebase-analyzer:single-subsystem`); or
b) explore multiple systems or domains up to and including the entire codebase (`codebase-analyzer:multiple-subsystems`); or
c) find where a feature or functionality is used or implemented (`codebase-locator`).

<subagents-positive-impact>
Delegating exploration and research tasks to agents leads to improved results and is context-efficient. It keeps the main conversation’s context window from ballooning and your mind clear of noise.
</subagents-positive-impact>

**A few goto agents:**
- `codebase-locator` to find *where* something is in the codebase.
- `codebase-analyzer:single-subsystem` to get a deep report on *how* a particular system or domain works.
- `codebase-analyzer:multiple-subsystems` when you need in-depth research across *multiple systems* and domains, plus an excellent *synthesis* of their connected flows, how they’re coupled, and so on.

#### Common agent-driven workflows

1) **Understanding the codebase-wide reach of a particular aspect, concept, feature, functionality, etc.:**
  codebase-locator("Find all contexts in the codebase that have to do with {thin lead}")    // Will provide a list of contexts.
  → codebase-analyzer:multiple-subsystems("Investigate {list of contexts}")

2) **Wide understanding of an entire codebase or any arbitrarily large scope:**
  codebase-analyzer:multiple-subsystems("Investigate the {large scope}")    // Handles any compound set of domains, no matter how large or complex, by automatically creating as many `single-subsystem` agents as the scope requires.
  
3) **Deep understanding of a particular system or domain:**
  codebase-analyzer:single-subsystem("Investigate the {system or domain}")    // Deep, narrow and thorough exploration of a system or domain.

#### How to prompt an agent

Be generous in giving the agent wider context—understanding *why* it's performing the task will boost its performance. Don't micromanage nor over-instruct it. The agent already has a highly detailed system prompt. It is also highly intelligent, just like you, and is able to navigate around uncertainties well. Avoid prescribing instructions or giving it "how-to" examples; Avoid prescribing it which files or symbols to look at; just declare what kind of *understanding* you're seeking.
Sharing only why it's been dispatched, and what you hope to achieve by the time the agent completes its task directly frees it up to find the best way to achieve *your* goal.

</using-sub-agents>

---

<development-rules>
  
## Development Rules

### Be Bold, Precise and Minimalistic
1. Fail loud and early.
2. Complexity is the enemy.
3. Simplicity is the way to go.
4. Adding a logical branch is unjustified unless proven otherwise.
5. No nested `if` statements.
6. Write declarative, upfront code. The more the source code feels like a high-level configuration rather than an implementation, the better. Thought experiement: what’s more easy to understand: a Pydantic BaseModel definition, or a manually-written class with an `__init__`, value and type validation, manual state setting, etc.?
7. No squirmy code. Don’t carry over cascading uncertainty via defensive programming. Be straightforward and explicit.

### A Cautious Note About Refactoring

If throughout the development cycle you encounter some aspect of the software design or architecture that is a meaningful annoyance increasing the friction between you and solving the problem, and it could be relatively easily redesigned to significantly relieve that friction without requiring so much change that it constitutes an adventure of its own, please go ahead and make this refactor. I prefer that over you needing to do acrobatics to overcome a past, now irrelevant design decision.

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
