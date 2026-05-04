---
name: load-project-context
description: Establish continuity with recent work. Catch up on recent project context and progress. Use when starting a session on an ongoing project or effort, when wider context is helpful, or when user asks to get up to speed.
---

<gather-context>

Check which of these exist in the project, then dive into those that do:

1. **Read All Root Markdown Files** - `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `DEVELOPMENT.md`, `sessions.yaml`, `BUGS.md`. Read these files in full. Follow any context-gathering instructions in them.

2. **Git log** - run `git log --numstat --shortstat --all --graph -10`. If any commit is close in domain or blast radius to your task, read the files involved in it. Mentally build a linear timeline of what happened when. 

The instruction to read files in full is intentional - truly do that.

If the user asks to read the source code as well, read it all, besides `tests/data/*`, which has huge files. 

</gather-context>

<relevancy-gauge>

**Global rule for reading docs, files and gathering context:** always maintain a mental "relevancy" weight for each resource. This is to be able to home in on relevant resources — resources that touch upon the Sphere-Of-Influence(d) of the subject at hand — and not bloat the context window with unequivocally irrelevant resources. Note the language I've used now: The threshold for a resource to qualify as 'relevant' is *low*. Recall has precedence over precision.

**Criteria that make up the 'Relevancy' weight:**
1. **Time**. The older, the less relevant. Code and documentation rot and drift over time. Authoritative timestamp resources:
    a. YAML frontmatter in Markdown files. Isn't always present.
    b. Git: last updated and creation time
2. **File path**. Does it semantically match the current effort?
3. Surgical, **recursive grep matching**. Recursively `grep`ing the codebase to exhaustively climb up and down dependency chains is extremely effective and encouraged to mark relevant files.

Again, *read files that have proven relevant in full.*

</relevancy-gauge>

---

<dev-cycle>

1. Run `./tests/run_all.sh | cat` for baseline.
2. Red/Green TDD: load the `tdd` and `write-tests` skills.
3. Upon completion, run the `post-implementation` Skill.

</dev-cycle>
