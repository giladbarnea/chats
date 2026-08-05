---
updated: 2026-08-05
---
# External session provider detection

The change removes an unsafe assumption: an unknown JSONL file is no longer treated as Claude merely because no path matcher claimed it.

Native paths still win because they carry stronger provider intent than copied content. External Codex and PI files use stable first-entry signatures confirmed across the local session corpus. Claude remains path-only because recent Claude sessions have no stable first entry.

Failing closed made an old test-suite assumption visible. Many Claude fixtures lived outside `~/.claude/projects/` and silently depended on the fallback. The tests now give those fixtures explicit Claude paths. Stdin seam tests use PI content because pathless Claude content is intentionally unresolvable.

The shell harness now copies only declared Claude fixtures into an isolated native path. It does not recreate the removed fallback by treating every JSONL fixture as Claude.

The real Avidor transcript now resolves to its header ID and renders all 86 messages with `--all`. A peer-review follow-up also made `ch name` and `ch rm` report unknown providers cleanly instead of exposing tracebacks. `./tests/run_all.sh` passes, including unit, performance, and shell tests.

Useful references were `ARCHITECTURE.md` and `/Users/giladbarnea/.pi/agent/skills/jsonl-toolkit/references/pi-session-jsonl.md`.
