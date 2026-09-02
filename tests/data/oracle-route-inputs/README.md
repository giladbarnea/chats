# The two inputs to `dd6ab701` that git cannot hold

**⚠ DO NOT DELETE. These are not stray virtualenv artifacts.**

`tests/oracle_digest.py::oracle_route_digest` pins the Python search oracle. It
digests **three** things:

1. `src/chats/**/*.py` — **in git.**
2. `.venv/bin/ch-legacy` — **not in git.** `.gitignore:13` ignores `.venv`.
3. `chats-*.dist-info/RECORD` — **not in git.**

**So the digest cannot be reproduced from a commit alone.** That is not an
oversight: **the route digest exists precisely BECAUSE a source-only digest is
insufficient** — *"a `git diff` digest cannot see the launcher or the installed
RECORD, so a concurrent `uv sync` moves the oracle invisibly"* (decision 3).
***The property that makes it a good pin is the property that makes it
unrecoverable from a commit.***

These two files are stored so that `sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0`
stays re-derivable **after the Python search authority is deleted.**

    ch-legacy    321 bytes   sha256 c1821a3a86ee9a88…
    RECORD     1,062 bytes   sha256 863d603b8e2c49ed…

## How to re-derive the digest

**`oracle_digest.py` reads the LIVE venv**, so the files alone are not enough —
they must be put back where the recipe looks.

1. `git archive 67d60532bb0d src/chats tests | tar -x -C <dir>`
2. Copy `ch-legacy` from here to `<dir>/.venv/bin/ch-legacy`
3. Copy `RECORD` from here to
   `<dir>/.venv/lib/python3.14/site-packages/chats-0.1.0.dist-info/RECORD`
4. Run `oracle_route_digest()` with `PROJECT_ROOT` at `<dir>`

**Verified by executing exactly that on 2026-09-02 — see the result recorded in
`legacy-selection-baseline.json` and `frozen_reference.json`.**

**The revision is `67d60532bb0d`.** *An earlier stamp said `8cb4c5f79cf6`, which
predates every line of this mission — it was captured by `git rev-parse HEAD`
while the tree was uncommitted, so no revision could have reproduced it. A stale
revision is worse than an absent one: a reader tries it and concludes the record
is wrong.*
