---
date: 2026-08-28
author: context-curator
role: G3 structural review (the half that reads the change and checks a property survived)
oracle_route_digest: sha256:dd6ab701e9b8450ed2a1e45bb46998065155436752f4d251389020bdbbadcee0
scope: landed slices — inventory, scanner, python_extension lift, terminal, pool_filter
verdict: no structural defects found; one watch item; one nuance worth stating so nobody fixes it
---

# G3 structural review 01 — the extraction and reconciliation surfaces

Reviewed against `g3-review-criteria.md`, written before any slice landed. Started where the reconciliation is thickest, per the brief: the two commits `main` gained after the branch forked, and the extraction that the branch got wrong.

Method: read the change, check whether the property survived. Not a measurement and not a corpus sweep — those halves are `reviewer-profiler`'s and my own respectively.

---

## 1. No fork of a scan — **pass**, with one watch item

The branch's version of this extraction left a live fork: `python_extension.rs` kept its own `find_last_jsonl_timestamp_impl` and `scan_resolution_facets_impl` while `inventory.rs` separately grew `last_timestamp` and `resolution_facets`, and the two already disagreed on which whitespace they stripped.

**That has not happened here.** `python_extension.rs` fell from 1,399 lines to 301, and three of the four scans are now thin wrappers over one implementation:

| PyO3 function | Body |
| --- | --- |
| `classify_native_session_path` | delegates to `inventory::classify_native_session_path_impl` |
| `find_last_jsonl_timestamp` | delegates to `inventory::for_each_line_backward` |
| `discover_session_files` | delegates to `discover_session_files_impl` |
| `scan_resolution_facets` | **own body**, `python_extension.rs:95` |

**Watch item, not a defect.** The facet scanner is the one that was not extracted. There is no second copy, so this is not a fork — it is un-extracted. But resolution fallback needs facets, so when the native route reaches them, this is exactly where a second implementation gets written and the branch's defect reproduces. The fork does not exist; the conditions for it do.

Cheapest guard: extract it in the same change that first needs it natively, rather than writing a native one beside this one.

## 2. The two trim layers stay two, on the right semantics — **pass**

`trim_python_byte_whitespace` is defined **once**, at `inventory.rs:349`, and imported by `python_extension.rs:14`. Both callers in `inventory.rs` (lines 431, 609) use it.

The branch's divergence — Python's four-byte JSON whitespace set on one side and Rust's `.trim()`, which strips the full Unicode `White_Space` property, on the other — is gone. A line beginning `\u{00A0}` now behaves identically on both routes.

## 3. Terminal width, the thickest reconciliation point — **pass**

`main` moved here after the branch forked (`a51f32c`), and the branch was COLUMNS-only defaulting to 80. Two things had to survive:

**The original is deleted.** `main.rs` no longer defines `terminal_width`; it imports `_native::terminal::terminal_width` at line 9. One authority, extraction complete. This is the criterion the branch failed and this slice passes.

**The measurement matches.** `terminal.rs::measured_terminal_width` iterates `[STDIN_FILENO, STDOUT_FILENO, STDERR_FILENO]` with `find_map` — structurally identical to the oracle at `a51f32c:311`.

**Unasked-for, and the reason I would hold this slice up as the standard:** `terminal.rs` reproduces Rich's `COLUMNS` parsing exactly — `str.isdigit()` then `int()` — including a test asserting that Arabic-Indic digits resolve to 80 as Python's `int()` does. And it keeps **two** resolvers deliberately, because `COLUMNS=+96` wraps help at 96 while Rich-rendered output wraps at 80 *in the same invocation*: argparse's `int()` accepts the leading `+`, Rich's `str.isdigit()` does not.

That is a preserve-because-wrong behaviour found and preserved without it being on my list. The comment names each resolver for what it is rather than unifying them.

## 4. Date verdicts are content-only in every arm — **pass**

The branch shipped an mtime short circuit here, and it silently dropped hits on any file whose mtime precedes its content — imports, copies, `touch -t`, restore tools. Worse, its pager arm used a different predicate, so the binary disagreed with itself.

`pool_filter.rs::passes_path_for_date` (line 153) consults content timestamps only. No stat pre-filter in any arm.

And `pool_filter.rs:189–191` carries a comment recording *why* it is absent, citing the prior team's withdrawal and the reason. A future reader reaching for that optimization meets the argument against it at the point of temptation, which is the only place it works.

## 5. Timing economy 2 survives — **pass**

Holding the other three per the brief, since they live in the engine still being wired. This one is in a landed slice, so it is reviewable now.

`passes_path_for_date` preserves both economies:

- Each probe runs **only if its own filter is active** — `if let Some(threshold) = self.mafter`, then separately for `cafter`.
- A failed `mafter` check `return false`s **before** the `cafter` probe runs.

So `-ma` alone never reads a first timestamp, and a file rejected by `-ma` is never opened twice. Byte-invisible, cost-unmeasured, and intact.

## 6. Paths as bytes — **correct, and worth stating so nobody "fixes" it**

`classify_native_session_path(path: &str, home: &str)` and `find_last_jsonl_timestamp(path: &str, ...)` still take `&str` at the PyO3 boundary, where every sibling takes `PyBytes`. That is the asymmetry that raises `UnicodeEncodeError` on a session path containing invalid UTF-8.

**This is not a port defect.** The native side takes `&Path` — `inventory::classify_native_session_path_impl(path: &Path, home: &Path)` — which is byte-safe on Unix. The lossy conversion lives only in the legacy wrapper, and that wrapper dies at cutover, which removes the defect for free.

Stating it because it reads like an unfixed bug in a diff, and because a well-meaning fix to the PyO3 signature now is work on code scheduled for deletion.

---

## Verdict

**No structural defects.** Every criterion that applies to a landed slice passes, including the two the branch demonstrably failed — the forked scan and the mtime short circuit.

One watch item: the facet scanner is the last un-extracted scan, and therefore the one place the branch's fork can still reproduce.

## What this review did not cover

- **Timing economies 1, 3 and 4** — held per the brief; three of four live in the engine being wired now.
- **The measured surface** — `reviewer-profiler`'s half, by the split agreed directly.
- **Corpus sweeps** — mine, but a separate pass.
- `color.rs`, `cells.rs`, `rust/search/` grammar, `plan.rs`, `python_io`, `codex.rs`, `session.rs` — landed and not yet read. This pass took the reconciliation-thickest surfaces first; those are next.
