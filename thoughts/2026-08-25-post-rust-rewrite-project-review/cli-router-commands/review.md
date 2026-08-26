# Review: cli-router-commands (ac6599cc..3078625)

Scope: argparse router (`src/chats/cli.py`), non-search command implementations, catalog module, registry, ch-legacy plumbing, user-facing flags, negative-index swaps, role-visibility normalization, exit codes, and the native `ch` ↔ `ch-legacy` seam (`rust/main.rs`, `tests/test_cli_seam.sh`, `tests/lib.sh`, `run_all.sh`).

Method: full reads of cli.py (old via `git show ac6599cc` and new), rust/main.rs, commands/{parse,name,rm,info,resolve,common}.py, registry.py, catalog/, lib.sh, test_cli_seam.sh, run_all.sh, test_parse_command_contract.py, fixture MANIFEST + expected bytes, cycle-01 contract docs; empirical differential testing of the old Python router vs the native binary across ~20 argument-handling corners.

## Verified-good (no action)

The seam core is solid. Empirically matched old-argparse byte behavior for: unknown-option wording ("unrecognized arguments"), option-as-format-value (`-f --help` → "expected one argument", exit 2), attached short values (`-fxml`, `-f=xml`), negative-number positionals (`-5`), `--` passthrough, invalid-choice/missing-value messages, empty-output exit 0, conversion-error exit 1. Error-wrap width tracks `COLUMNS` exactly like Rich did. Unix `run_legacy` uses `exec()` so exit codes, signals, env, and non-UTF-8 argv pass through correctly; wheel/package-ownership tests pin the launcher story. The parse-router removal from cli.py is clean (±23 lines, no dead leftovers).

## Findings

### 1. Native argparse emulation misses `--help` abbreviations it claims to own (routing regression, verified)

`rust/main.rs::is_long_format_option` deliberately emulates argparse's long-option abbreviation for `--format` (`--f`, `--fo`, … all accepted; verified `--fo xml` routes like old argparse). But the same emulation was not applied to `--help`: only exact `-h|--help` match. Old behavior vs new:

```console
$ ch parse --h            # pre-rewrite: prints help, exit 0
ch parse: error: unrecognized arguments: --h   # now: exit 2
```
Same for `--he`, `--hel`. Related family gaps: `-hf` (argparse: "argument -f/--format: expected one argument"; native: "unrecognized arguments: -hf") and `--help=foo` (argparse: "ignored explicit argument"; native: unrecognized). None of these are pinned by the fixture corpus, so CI can't catch them. Either complete the abbreviation emulation or accept-and-pin the divergence explicitly.

### 2. Hardcoded broken-pipe traceback cites code this very range deleted, with zero permanent coverage

`rust/main.rs::print_broken_pipe_traceback` fabricates a Python traceback (verified reachable: `ch parse <big>.json | head -c200`) pointing at `src/chats/cli.py:368 → cmd_parse_json(...)`, `src/chats/commands/parse.py:146 → cmd_parse_json`, `resolve.py:405 print(output)`. The first two frames reference symbols deleted by this rewrite (line 368 today sits inside the search parser). The emulation itself is intentional per cycle-01 docs ("preserves … broken-pipe failure output", verified once against a b203317 oracle via a scratch harness) — but unlike every other legacy surface, it never made it into the permanent fixture corpus, so it can drift silently. It also bakes `CARGO_MANIFEST_DIR` build-machine paths into the shipped binary. Pin it with a test or replace with an honest plain message.

### 3. cli.py still advertises `parse` as a subcommand its router no longer routes

After removing the early parse router, `main()`'s epilog keeps listing `parse    Rebuild XML-tagged Markdown…`, but `sys.argv[1] == "parse"` now falls through to the default parser, which treats "parse" as a session identifier. Verified: `ch-legacy parse foo.json` → `Error: Ambiguous conversation/session identifier 'parse' matches multiple sessions:` (varies with the user's session store). Public users can't hit this through native `ch`, but the private entry's help text invites the invocation and then mis-resolves it. Add a one-line guard/error or drop `parse` from the epilog.

### 4. CHANGELOG contradicts the build system and omits the range's biggest change

CHANGELOG.md line 60 still states builds "use Maturin" while `pyproject.toml` switched to setuptools-rust in this range (verified at ac6599cc: `[build-system] requires = ["maturin>=1.14,<2"]`). And no changelog entry covers the headline architectural change itself — public `ch` becoming a Rust launcher that owns only `parse`, everything else exec-ing the private `ch-legacy`. ARCHITECTURE.md documents the seam well; README doesn't mention it at all. Reconcile.

### 5. Contract tests bind to `~/.local/bin/ch`, which here is built from a different source tree than HEAD (cross-scope)

`tests/test_parse_command_contract.py` runs most checks against `REAL_INSTALLED_CH = ~/.local/bin/ch`. On this machine that binary is a **wip/cycle-02 artifact**, not HEAD output:

- Installed binary = 6,528,976 bytes = exactly `/Users/giladbarnea/dev/chats-cycle02-ox/target/release/ch` (worktree of `wip/cycle-02-native-default-pause-20260821`, built Aug 25 00:20).
- It embeds strings absent from HEAD's rust/ ("Cannot determine JSONL session provider", "logicalParentUuid", …) present in that worktree's `rust/session_provider.rs`.
- Its main.rs intercepts more than `parse` (search journey shows **zero** python trace hits vs **34** via `.venv/bin/ch`, identical command+env).

Consequences observed: `test_uncompleted_public_journeys_keep_exact_legacy_behavior` fails today because there genuinely is no Python in the installed route — not because of any HEAD regression. (An initial macOS-26 dyld-silence attribution by legacy-parsing-model was withdrawn after re-running controlled experiments; they independently confirmed all three evidence points above.) This also overturns a teammate's attribution (macOS-26 dyld silence across exec): I measured dyld printing normally for exec'd children here (34 hits through the checkout launcher). The suite needs either a checkout-built launcher target or an install-freshness guard; otherwise green/red signals describe whichever artifact last got installed. (Counter-evidence already sent to legacy-parsing-model.)

## Notes

- Negative-index swaps, role-visibility normalization, and repair heuristics (`_repair_*_positionals`) are unchanged in range and remain covered by shell suites; no new inconsistencies introduced by the router removal.
- Exit-code conventions are consistent across the surface: argparse-style usage errors 2, runtime errors 1, success/empty-output 0 — matching the pinned corpus.
