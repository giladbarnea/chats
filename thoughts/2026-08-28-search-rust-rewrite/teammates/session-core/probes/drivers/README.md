# Differential drivers

The probes in `../` shell out to these. They lived in a session scratchpad, which does
not survive; they are here so the instruments outlast the sessions that built them.

## `render/` — the route driver (`RENDER_BIN`, also `BRANCH_BIN`)

Serves `claude_render_differential.py` and `branch_map_differential.py`. Depends on the
crate by path, so it links the real code rather than a copy — both sides of every
comparison compute fresh, and no PyO3 exposure is needed.

```
cd render
CARGO_TARGET_DIR=$PWD/target cargo build --release
RENDER_BIN=$PWD/target/release/branchcheck uv run python ../../claude_render_differential.py
```

Reads one JSON case per line on stdin: `{"path", "origin", "flags", "provider"}`.
Emits one JSON row per case — a digest per message, or the rendered text when `DETAIL`
is set. **Adding a provider is one arm in its `match provider`.**

Its output protocol matters: rows are digests so a megabyte-wide rendered message cannot
truncate a line. If you change that, change both sides — comparing a digest against raw
text reads as total failure, which cost me a run.

## `branchmap/` — the branch-map driver (`BRANCH_BIN`)

Serves `branch_map_differential.py`. **Rebuilt after the original was lost:** I had
repurposed the crate that produced it into the render driver, so for a while the 355-case
branch result was correct and unreproducible. Rebuilt from the recipe by its original
author rather than reconstructed by a reader, so the number keeps its identity.

```
cd branchmap
CARGO_TARGET_DIR=$PWD/target cargo build --release
BRANCH_BIN=$PWD/target/release/branchmap uv run python ../../branch_map_differential.py
```

Reads one JSON-encoded session path per line, emits one branch map per line.

**The session count moves between runs and that is expected** — the Claude corpus grows
while the team works. It was 355 when first proved and 360 on the rebuild, both at zero
mismatches. Quote the count with the date it was taken.

## `toolspec/`, `shortening/` — grammar and truncation drivers
**These two need their modules copied in before they build** — they were built as
standalone crates rather than linking the real one:
```
ROOT=$(git rev-parse --show-toplevel)
cp $ROOT/rust/{model,shortening,tool_filter}.rs toolspec/src/
printf 'pub mod model;\npub mod shortening;\npub mod tool_filter;\n' > toolspec/src/lib.rs
# shortening/ needs model.rs and shortening.rs only, plus a two-line lib.rs.
# Every recipe here was run verbatim from this file and builds; the earlier version
# was off by one directory and its driver did not compile.
```
`render/` needs none of that: it links the crate by path, which is the better shape and
the one to copy if you build another.


`toolspec.rs` serves `tool_spec_differential.py` (`TOOLSPEC_BIN`); `diff.rs` serves
`shortening_differential.py` (`DIFF_BIN`). Both are self-contained: they copy the module
under test rather than linking the crate, which is why they need a `Cargo.toml` of their
own.

## `../mutate_pi.py` — the falsification pattern

Applies deliberately wrong ports and reports **ANCHOR MISSING — mutation not applied,
result meaningless** rather than a number, because a mutation that was never applied and
a mutation that nothing caught both print zero.
