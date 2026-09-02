#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Falsify the Codex render differential: break the decoder, prove the gate notices.

The differential over 1,208 real Codex sessions returning zero is not evidence the
decoder is right. It is evidence of nothing at all until the gate has been shown to
fail. Each mutation below is a wrong port a competent implementer could plausibly
have written, named for the hazard it stands for — the mutation set **is** this
harness's parameterization, and an unnamed set is an unexamined assumption.

**A mutation that catches zero is a question, not a result.** When one survives, the
next step is to measure whether the shape it breaks occurs in the corpus at all,
never to conclude the decoder is right. `session-core` reintroduced the previous
team's exact Pi defect and it caught nothing across 400 sessions — because all 477
joined envelopes in the corpus carry the terminator their code wrongly required. The
corpus was blind, not clean.

**Nothing here touches the shared checkout.** The crate is synced to a private
directory and mutated there, with a private driver pointing at it. `mutate_pi.py`
mutates in place and restores in a `finally`, which is correct and still left me
reading a transiently mutated file and publishing a wrong finding from it.

Usage:  uv run falsify_codex.py [--sessions N]
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path("/Users/giladbarnea/dev/chats")
WORK = pathlib.Path("/private/tmp/ch-falsify-codex")
PROBE = (
    REPO
    / "thoughts/2026-08-28-search-rust-rewrite/teammates/session-core/probes/claude_render_differential.py"
)
TARGET = "rust/codex.rs"

MUTATIONS: list[dict[str, str]] = [
    {
        "name": "preamble_blocks_kept",
        "hazard": "hiding protocol noise from Codex user turns",
        "find": "    let stripped = session::python_strip(text);\n    stripped.is_empty()",
        "replace": "    let stripped = session::python_strip(text);\n    #[allow(unused)]\n    let _ = &stripped;\n    return false;\n    #[allow(unreachable_code)]\n    stripped.is_empty()",
    },
    {
        "name": "assistant_blocks_joined_singly",
        "hazard": "paragraph spacing between assistant content blocks",
        "find": '                let joined = visible.join("\\n\\n");',
        "replace": '                let joined = visible.join("\\n");',
    },
    {
        "name": "append_block_always_joins",
        "hazard": "the falsy check that stops a first block gaining a blank line",
        "find": "    match existing.filter(|value| !value.is_empty()) {",
        "replace": "    match existing {",
    },
    {
        "name": "lifecycle_calls_rendered",
        "hazard": "suppressing spawn_agent / wait_agent / close_agent",
        "find": "        if native_name.is_some_and(|name| AGENT_LIFECYCLE_TOOLS.contains(&name)) {",
        "replace": "        if false {",
    },
    {
        "name": "lifecycle_outputs_rendered",
        "hazard": "suppressing a lifecycle call's output, which carries no tool name",
        "find": "        if call_id\n            .as_deref()\n            .is_some_and(|id| self.agent_lifecycle_call_ids.iter().any(|seen| seen == id))\n        {\n            return;\n        }",
        "replace": "",
    },
    {
        "name": "reasoning_accepts_any_item",
        "hazard": "reading only summary_text items from a reasoning payload",
        "find": '        .filter(|item| string_of(item, "type") == Some("summary_text"))',
        "replace": "",
    },
    {
        "name": "script_calls_never_merged",
        "hazard": "one exec envelope rendering as one canonical call",
        "find": "    if calls.len() == 1 {\n        return calls.into_iter().next();\n    }",
        "replace": "    return calls.into_iter().next();\n    #[allow(unreachable_code)]\n    if calls.len() == 1 {\n        return calls.into_iter().next();\n    }",
    },
    {
        "name": "script_object_json_only",
        "hazard": "parsing the JavaScript object form with bare keys",
        "find": "    let mut object = Map::new();\n    for item in split_script_items(&stripped[1..stripped.len() - 1]) {",
        "replace": "    return None;\n    #[allow(unreachable_code)]\n    let mut object = Map::new();\n    for item in split_script_items(&stripped[1..stripped.len() - 1]) {",
    },
    {
        "name": "tool_output_never_unwrapped",
        "hazard": "lifting output/content/text out of a JSON tool result",
        "find": '    for key in ["output", "content", "text"] {',
        "replace": '    for key in [] as [&str; 0] {',
    },
    {
        "name": "empty_assistant_turns_kept",
        "hazard": "dropping an assistant turn that produced nothing displayable",
        "find": "        if !has_content(&assistant) {\n            return;\n        }",
        "replace": "",
    },
    {
        "name": "user_text_not_paragraph_joined",
        "hazard": "paragraph spacing between a user turn's visible blocks",
        "find": '                message.text = visible.join("\\n\\n");',
        "replace": '                message.text = visible.join("\\n");',
    },
]

MISMATCHES = re.compile(r"mismatches:\s*(\d+)")


def sync() -> pathlib.Path:
    """Refresh the private crate and driver. Never the shared checkout."""
    WORK.mkdir(parents=True, exist_ok=True)
    crate = WORK / "crate"
    if crate.exists():
        shutil.rmtree(crate)
    crate.mkdir()
    for name in ("Cargo.toml", "Cargo.lock", "build.rs"):
        if (REPO / name).exists():
            shutil.copy2(REPO / name, crate / name)
    shutil.copytree(REPO / "rust", crate / "rust")
    # The recorded oracle tables are `include_str!`d by tests in `search_output.rs`
    # and `terminal.rs`, so a crate copy without them does not compile. A falsifier
    # that cannot build is a falsifier that cannot run.
    probes = "thoughts/2026-08-28-search-rust-rewrite/teammates/engine-and-codex/probes"
    (crate / probes).mkdir(parents=True, exist_ok=True)
    for table in (REPO / probes).glob("*.tsv"):
        shutil.copy2(table, crate / probes / table.name)

    driver = WORK / "driver"
    (driver / "src").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        REPO
        / "thoughts/2026-08-28-search-rust-rewrite/teammates/session-core/probes/drivers/render/src/main.rs",
        driver / "src" / "main.rs",
    )
    (driver / "Cargo.toml").write_text(
        "[package]\n"
        'name = "branchcheck"\n'
        'version = "0.0.0"\n'
        'edition = "2024"\n'
        "[dependencies]\n"
        f'chats-native = {{ path = "{crate}", default-features = false }}\n'
        'serde_json = { version = "1", features = ["arbitrary_precision", "preserve_order"] }\n'
    )
    return crate


def build(driver: pathlib.Path) -> bool:
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=driver,
        capture_output=True,
        env={**os.environ, "CARGO_TARGET_DIR": str(driver / "target")},
    )
    output = result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
    return "error[" not in output and "error:" not in output


def differential(driver: pathlib.Path, sessions: int) -> int | None:
    """Mismatch count over `sessions` Codex sessions, or None when the run refused."""
    result = subprocess.run(
        ["uv", "run", "-p", "python3", "python3", str(PROBE), str(sessions)],
        cwd=REPO,
        capture_output=True,
        env={**os.environ, "PROVIDER": "codex", "RENDER_BIN": str(driver / "target/release/branchcheck")},
    )
    output = result.stdout.decode("utf-8", "replace")
    found = MISMATCHES.search(output)
    return int(found.group(1)) if found else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=200)
    arguments = parser.parse_args()

    crate = sync()
    driver = WORK / "driver"
    target = crate / TARGET
    pristine = target.read_text()

    if not build(driver):
        print("FAIL: the private driver does not build against an unmutated crate")
        return 1
    baseline = differential(driver, arguments.sessions)
    if baseline is None:
        print("FAIL: the differential refused to report; nothing below would mean anything")
        return 1
    if baseline != 0:
        print(f"FAIL: baseline is {baseline} mismatches, not 0. Fix the decoder before falsifying.")
        return 1
    covered = "the whole corpus" if arguments.sessions == 0 else f"{arguments.sessions} sessions"
    print(f"baseline: 0 mismatches over {covered}\n")

    print(f"{'mutation':<32} {'verdict':<10} detail")
    survivors: list[str] = []
    for mutation in MUTATIONS:
        occurrences = pristine.count(mutation["find"])
        if occurrences != 1:
            print(
                f"{mutation['name']:<32} {'REFUSED':<10} "
                f"ANCHOR MATCHES {occurrences} TIMES, EXPECTED 1 — "
                "mutation not applied, result meaningless"
            )
            survivors.append(mutation["name"])
            continue

        target.write_text(pristine.replace(mutation["find"], mutation["replace"], 1))
        try:
            if not build(driver):
                # A mutation the compiler rejects is still a mutation nothing shipped.
                print(f"{mutation['name']:<32} {'killed':<10} rejected by the compiler")
                continue
            count = differential(driver, arguments.sessions)
        finally:
            target.write_text(pristine)

        if count is None:
            print(f"{mutation['name']:<32} {'REFUSED':<10} differential did not report")
            survivors.append(mutation["name"])
        elif count == 0:
            survivors.append(mutation["name"])
            print(
                f"{mutation['name']:<32} {'SURVIVED':<10} "
                f"0 new mismatches — MEASURE whether the corpus contains: {mutation['hazard']}"
            )
        else:
            print(f"{mutation['name']:<32} {'killed':<10} {count} mismatches")

    build(driver)
    print()
    if survivors:
        print(
            f"{len(survivors)} mutation(s) the corpus did not catch: {', '.join(survivors)}\n"
            "Each is a question about whether that shape occurs, not a clean bill of health."
        )
        return 1
    print(f"PASS: all {len(MUTATIONS)} mutations produced mismatches the differential reported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
