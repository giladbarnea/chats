"""Falsify the gates: break the engine on purpose and prove each gate notices.

A gate that has never failed is not known to work. This applies a named mutation to
the ported engine, reruns every gate, and checks the mutation produces divergences
the baseline did not have. A mutation no gate reports is a blind spot, and the run
fails.

The capstone rule this implements: exhaustive is always exhaustive over a
parameterization, and the parameterization is the assumption. These mutations are
this harness's parameterization, so they are stated by name rather than implied.

Usage:
    uv run python falsify_gates.py <workdir>

`workdir` needs the built cargo project and the probe corpora, as the README lays out.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

# Each mutation names the hazard it stands for. All live in `search_query.rs`,
# the file B3 actually delivers, so the gate is tested against the real artifact.
MUTATIONS: list[dict[str, str]] = [
    {
        "name": "icase_off",
        "hazard": "case-insensitive literal matching",
        "find": "    let lowered_pattern = tolower(pattern_character);",
        "replace": "    return pattern_character == text_character;\n    #[allow(unreachable_code)]\n    let lowered_pattern = tolower(pattern_character);",
    },
    {
        "name": "word_class_ascii_only",
        "hazard": "the `\\w` character-class predicate",
        "find": "            GeneralCategory::UppercaseLetter\n                | GeneralCategory::LowercaseLetter",
        "replace": "            GeneralCategory::UppercaseLetter",
    },
    {
        "name": "dotall_off",
        "hazard": "default compile flags",
        "find": "                dotall: true,",
        "replace": "                dotall: false,",
    },
    {
        "name": "and_binds_looser",
        "hazard": "boolean operator precedence",
        "find": "        let mut operands = vec![self.parse_and()?];",
        "replace": "        let mut operands = vec![self.parse_atom()?];",
    },
    {
        "name": "and_iter_terms_truncated",
        "hazard": "term enumeration feeding highlights and the match set",
        "find": "            Query::And(operands) | Query::Or(operands) => {\n                operands.iter().flat_map(Query::iter_terms).collect()\n            }",
        "replace": "            Query::And(operands) | Query::Or(operands) => {\n                operands.iter().take(1).flat_map(Query::iter_terms).collect()\n            }",
    },
    {
        "name": "budget_answers_silently",
        "hazard": "the step-budget guard reporting instead of guessing",
        "find": "            if vm.exhausted {\n                return Err(StepBudgetExceeded);\n            }",
        "replace": "            if vm.exhausted {\n                return Ok(false);\n            }",
    },
    {
        "name": "prescan_over_rejects",
        "hazard": "soundness of the required-literal prescan",
        "find": "        Node::Repeat { node, min, .. } if *min >= 1 => required_literal(node, ignorecase),",
        "replace": "        Node::Repeat { node, .. } => required_literal(node, ignorecase),",
    },
    {
        "name": "open_group_backref_allowed",
        "hazard": "rejecting a backreference to a group still being defined",
        "find": "                    if number <= self.group_count && !self.open_groups.contains(&number) {",
        "replace": "                    if number <= self.group_count {",
    },
    {
        "name": "noncapturing_consumes_number",
        "hazard": "non-capturing groups not consuming a capture number",
        "find": "                    return Ok(AtomOutcome::Node(Node::NonCapturing(Box::new(inner))));",
        "replace": "                    self.group_count += 1;\n                    return Ok(AtomOutcome::Node(Node::NonCapturing(Box::new(inner))));",
    },
    {
        "name": "flag_dispatch_narrowed",
        "hazard": "routing the ASCII and Unicode mode flags to the flag parser",
        "find": 'other if "imsxau-".contains(other) => {',
        "replace": 'other if "imsx-".contains(other) => {',
    },
    {
        "name": "error_message_drift",
        "hazard": "malformed-query error text, which is user-visible on exit 2",
        "find": "\"Invalid search query: missing closing ')'.\"",
        "replace": "\"Invalid search query: unclosed group.\"",
    },
]

GATES = ("term", "boolean", "predicate", "guard")


def run(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def term_divergences(python: dict, candidate: dict) -> set[str]:
    by_id = {row["id"]: row for row in candidate["results"]}
    keys = set()
    for probe in python["results"]:
        other = by_id.get(probe["id"])
        if other is None:
            continue
        for mode in ("insensitive", "sensitive"):
            if probe[mode]["compiled_as"] != other[mode]["compiled_as"]:
                keys.add(f"{probe['id']}|{mode}|compiled_as")
            if probe[mode]["matches"] != other[mode]["matches"]:
                keys.add(f"{probe['id']}|{mode}|matches")
    return keys


def boolean_divergences(python: dict, candidate: dict) -> set[str]:
    by_id = {row["id"]: row for row in candidate["results"]}
    keys = set()
    for probe in python["results"]:
        other = by_id.get(probe["id"])
        if other is None:
            continue
        for mode in ("insensitive", "sensitive"):
            left, right = probe[mode], other[mode]
            for facet in ("parsed", "error", "shape", "iter_terms", "spans"):
                if facet in left and facet in right and left[facet] != right[facet]:
                    keys.add(f"{probe['id']}|{mode}|{facet}")
    return keys


def predicate_divergence_count(predicates: dict) -> int:
    engine = set()
    for low, high in predicates["word_ranges"]:
        engine.update(range(low, high + 1))
    return sum(
        1
        for code in range(0x110000)
        if (chr(code).isalnum() or chr(code) == "_") != (code in engine)
    )


def measure(work: pathlib.Path, label: str) -> dict[str, object]:
    """Run every gate against the currently built engine."""
    binaries = work / "target" / "release"
    term_keys: set[str] = set()
    batches = ("probes1", "probes2", "probes3", "probes4", "probes5",
               "probes6", "probes7", "gen")
    for batch in (f"{name}.json" for name in batches):
        candidate = run([str(binaries / "branch"), str(work / batch)], work)
        term_keys |= term_divergences(
            json.loads((work / f"py_{batch}").read_text()),
            json.loads(candidate.stdout),
        )
    boolean = run([str(binaries / "boolean"), str(work / "boolcases.json")], work)
    boolean_keys = boolean_divergences(
        json.loads((work / "py_boolcases.json").read_text()),
        json.loads(boolean.stdout),
    )
    predicates = run([str(binaries / "predicates")], work)
    guard = json.loads(run([str(binaries / "guard")], work).stdout)
    return {
        "label": label,
        "term": term_keys,
        "boolean": boolean_keys,
        "predicate": predicate_divergence_count(json.loads(predicates.stdout)),
        # One string per gate failure, so any change is a change in the set.
        "guard": frozenset(
            ([] if guard["guard_fires"] else ["guard-silent"])
            + ([] if guard["prescan_shortcuts"] else ["prescan-not-short-circuiting"])
            + [f"prescan-lost:{pattern}" for pattern in guard["prescan_losses"]]
        ),
    }


def build(work: pathlib.Path) -> bool:
    result = run(
        ["cargo", "build", "--release", "--bin", "branch", "--bin", "boolean",
         "--bin", "predicates", "--bin", "guard"],
        work,
    )
    if result.returncode != 0:
        print(result.stderr[-1500:])
    return result.returncode == 0


def main() -> None:
    work = pathlib.Path(sys.argv[1]).resolve()
    source = work / "src" / "branch" / "search_query.rs"
    backup = work / "search_query.rs.pristine"
    if backup.exists():
        sys.exit(
            f"{backup} exists, so a previous run left the engine mutated. "
            "Restore it before running, or this run measures a poisoned baseline."
        )
    pristine = source.read_text()
    backup.write_text(pristine)

    try:
        outcome = falsify(work, source, pristine)
    finally:
        source.write_text(pristine)
        build(work)
        backup.unlink(missing_ok=True)
    sys.exit(outcome)


def falsify(work: pathlib.Path, source: pathlib.Path, pristine: str) -> int:
    if not build(work):
        return 1
    baseline = measure(work, "baseline")
    print(
        f"baseline: term={len(baseline['term'])} boolean={len(baseline['boolean'])} "
        f"predicate={baseline['predicate']} guard={sorted(baseline['guard'])}\n"
    )

    print(f"{'mutation':<30} {'term':>6} {'bool':>6} {'pred':>8} {'guard':>6}  verdict")
    survivors = []
    for mutation in MUTATIONS:
        if pristine.count(mutation["find"]) != 1:
            found = pristine.count(mutation["find"])
            print(f"{mutation['name']:<30} anchor occurs {found} times in the engine, expected 1 — refusing to guess")
            survivors.append(mutation["name"])
            continue
        source.write_text(pristine.replace(mutation["find"], mutation["replace"], 1))
        if not build(work):
            print(f"{mutation['name']:<30} {'—':>6} {'—':>6} {'—':>8} {'—':>6}  BUILD FAILED")
            survivors.append(mutation["name"])
            continue
        mutated = measure(work, mutation["name"])

        new_term = len(mutated["term"] - baseline["term"])
        new_boolean = len(mutated["boolean"] - baseline["boolean"])
        new_predicate = mutated["predicate"] - baseline["predicate"]
        new_guard = len(mutated["guard"] - baseline["guard"])
        caught = new_term > 0 or new_boolean > 0 or new_predicate != 0 or new_guard > 0
        if not caught:
            survivors.append(mutation["name"])
        print(
            f"{mutation['name']:<30} {new_term:>6} {new_boolean:>6} {new_predicate:>8} "
            f"{new_guard:>6}  {'killed' if caught else 'SURVIVED — gate is blind'}"
        )

    print()
    if survivors:
        print(f"FAIL: {len(survivors)} mutation(s) no gate reported: {', '.join(survivors)}")
        return 1
    print(f"PASS: all {len(MUTATIONS)} mutations were reported by at least one gate")
    return 0


if __name__ == "__main__":
    main()
