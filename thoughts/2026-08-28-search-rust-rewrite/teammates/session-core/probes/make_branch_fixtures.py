"""Author six minimal Claude sessions, one per branch-resolution shape, and prove each trips its path.

A synthesized fixture that does not actually reach the logic it names is a fixture
that passes forever while proving nothing. So every session here is asserted twice:
the structural precondition it is built to contain, and the exact branch map
`_resolve_branch_map` produces from it.

Writes JSONL to the directory given as argv[1] (default: ./branch-fixtures).

Run from the repo root:
  uv run python thoughts/.../probes/make_branch_fixtures.py [out_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from chats.parsing import _resolve_branch_map

STAMP = "2026-08-20T10:{:02d}:00.000Z"


def user(uuid: str, parent: str | None, text: str, minute: int) -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "parentUuid": parent,
        "timestamp": STAMP.format(minute),
        "message": {"role": "user", "content": text},
    }


def assistant(uuid: str, parent: str | None, text: str, minute: int) -> dict:
    return {
        "type": "assistant",
        "uuid": uuid,
        "parentUuid": parent,
        "timestamp": STAMP.format(minute),
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def compaction(uuid: str, logical_parent: str, minute: int) -> dict:
    return {
        "type": "system",
        "subtype": "compact_boundary",
        "uuid": uuid,
        "parentUuid": None,
        "logicalParentUuid": logical_parent,
        "timestamp": STAMP.format(minute),
    }


def last_prompt(leaf: str) -> dict:
    return {"type": "last-prompt", "leafUuid": leaf}


# --------------------------------------------------------------- the six shapes

FIXTURES: dict[str, tuple[str, list[dict], dict[str, str]]] = {}

# 1. Truncated head: the root's parent is not in this file.
FIXTURES["truncated-head"] = (
    "root parentUuid points outside the file; one abandoned reply below it",
    [
        user("u1", "ancestor-not-in-this-file", "resumed from a trimmed transcript", 0),
        assistant("a1", "u1", "continuing", 1),
        user("u2", "a1", "kept question", 2),
        assistant("a2", "u2", "kept answer", 3),
        user("u3", "a1", "abandoned question", 4),
    ],
    {"u3": "1"},
)

# 2. Compaction boundary, with the logicalParentUuid hop back into the earlier era.
FIXTURES["compaction-boundary"] = (
    "a compact_boundary root whose logicalParentUuid reaches the pre-compaction era",
    [
        user("u1", None, "before compaction", 0),
        assistant("a1", "u1", "answer before compaction", 1),
        compaction("c1", "a1", 2),
        user("u2", "c1", "after compaction", 3),
        assistant("a2", "u2", "answer after compaction", 4),
        user("u3", "c1", "abandoned after compaction", 5),
        last_prompt("a2"),
    ],
    {"u3": "1"},
)

# 3. Rewind to the first message: two null-parent roots, only one holds the leaf.
FIXTURES["rewind-to-first"] = (
    "two null-parent roots; the one without the active leaf is a detour, not an era",
    [
        user("u1", None, "abandoned opening", 0),
        assistant("a1", "u1", "abandoned reply", 1),
        user("u2", None, "real opening", 2),
        assistant("a2", "u2", "real reply", 3),
        last_prompt("a2"),
    ],
    {"u1": "1", "a1": "1"},
)

# 4. No recorded leaf: resolution falls to the longest continuation.
FIXTURES["no-recorded-leaf"] = (
    "no last-prompt entry, so the longest downward chain wins the main thread",
    [
        user("u1", None, "opening", 0),
        assistant("a1", "u1", "reply", 1),
        user("u2", "a1", "kept follow-up", 2),
        assistant("a2", "u2", "kept answer", 3),
        assistant("a3", "a2", "kept continuation", 4),
        user("u3", "a1", "abandoned follow-up", 5),
    ],
    {"u3": "1"},
)

# 5. The hard combination: compaction + rewind-to-first + a recorded leaf + branches in both eras.
FIXTURES["combined-eras"] = (
    "compaction era and a rewound session root together, each with its own abandoned branch",
    [
        user("u1", None, "abandoned opening", 0),
        assistant("a1", "u1", "abandoned reply", 1),
        user("u2", None, "real opening", 2),
        assistant("a2", "u2", "real reply", 3),
        compaction("c1", "a2", 4),
        user("u3", "c1", "after compaction", 5),
        assistant("a3", "u3", "answer after compaction", 6),
        user("u4", "c1", "abandoned after compaction", 7),
        last_prompt("a3"),
    ],
    {"u1": "1", "a1": "1", "u4": "2"},
)

# 6. Numbering stress: branch heads appear in the file in the exact reverse of
#    traversal order, so file-order numbering and traversal-order numbering
#    produce reversed id sequences.
#    A depth-first walk that descends the main chain first meets the branch heads
#    deepest-attachment-first. So the file must list them shallowest-first to make
#    the two orders disagree. `discriminates()` below enforces that; my first draft
#    listed them deepest-first and produced identical numbering under both rules,
#    which is a fixture that can never fail.
FIXTURES["numbering-order"] = (
    "four branch heads whose file order is the exact reverse of a root-first traversal",
    [
        user("u1", None, "turn 1", 0),
        assistant("a1", "u1", "reply 1", 1),
        user("u2", "a1", "turn 2", 2),
        assistant("a2", "u2", "reply 2", 3),
        user("u3", "a2", "turn 3", 4),
        assistant("a3", "u3", "reply 3", 5),
        user("u4", "a3", "turn 4", 6),
        assistant("a4", "u4", "reply 4", 7),
        # Branch heads, shallowest attachment first in the file.
        user("bA", "u1", "branch off turn 1", 8),
        user("bB", "a1", "branch off turn 2", 9),
        user("bC", "a2", "branch off turn 3", 10),
        user("bD", "a3", "branch off turn 4", 11),
        last_prompt("a4"),
    ],
    {"bA": "1", "bB": "2", "bC": "3", "bD": "4"},
)


# 7. Equal-depth fork: two children of one node with identical subtree depth.
#    Python's `max` keeps the FIRST maximal element; Rust's `max_by_key` keeps the
#    last. Nothing in 347 real sessions produces a tie where the choice is
#    observable, so without this fixture that divergence cannot be seen at all.
FIXTURES["equal-depth-fork"] = (
    "two branches of identical depth from one node, so the tie-break decides the main thread",
    [
        user("u1", None, "opening", 0),
        assistant("a1", "u1", "reply", 1),
        user("b1", "a1", "first continuation", 2),
        user("b2", "a1", "second continuation", 3),
    ],
    {"b2": "1"},
)

# ------------------------------------------------------- structural preconditions

def preconditions(entries: list[dict]) -> dict[str, bool]:
    nodes = {entry["uuid"]: entry for entry in entries if "uuid" in entry}
    null_roots = [u for u, n in nodes.items() if n.get("parentUuid") is None]
    external_roots = [
        u
        for u, n in nodes.items()
        if n.get("parentUuid") is not None and n.get("parentUuid") not in nodes
    ]
    compactions = [
        u
        for u, n in nodes.items()
        if n.get("type") == "system" and n.get("subtype") == "compact_boundary"
    ]
    leaves = [e["leafUuid"] for e in entries if e.get("type") == "last-prompt"]
    return {
        "external_parent_root": bool(external_roots),
        "compaction_boundary": bool(compactions),
        "multiple_null_roots": len(null_roots) > 1,
        "recorded_leaf": bool(leaves),
        "logical_parent_hop": any(
            nodes[u].get("logicalParentUuid") in nodes for u in compactions
        ),
    }


REQUIRED: dict[str, list[str]] = {
    "truncated-head": ["external_parent_root"],
    "compaction-boundary": ["compaction_boundary", "logical_parent_hop", "recorded_leaf"],
    "rewind-to-first": ["multiple_null_roots", "recorded_leaf"],
    "no-recorded-leaf": [],
    "combined-eras": [
        "compaction_boundary",
        "logical_parent_hop",
        "multiple_null_roots",
        "recorded_leaf",
    ],
    "numbering-order": ["recorded_leaf"],
    "equal-depth-fork": [],
}


# Give every session its own hour, so no two share a last in-band timestamp.
# Newest-first ordering is a stable sort, so a tie falls through to pool discovery
# order, which is lexical by filename — deterministic, but it would silently invert
# if a fixture were ever renamed. Distinct hours remove that coupling entirely.
for _hour, (_name, (_description, _entries, _expected)) in enumerate(FIXTURES.items(), start=10):
    for _entry in _entries:
        if "timestamp" in _entry:
            _entry["timestamp"] = _entry["timestamp"].replace("T10:", f"T{_hour:02d}:")


def discriminates(entries: list[dict], actual: dict[str, str]) -> bool | None:
    """Would numbering by a root-first traversal give a different answer than file order?

    Returns None when the session has fewer than two branches, where the question
    does not arise. A fixture whose whole purpose is to separate the two numbering
    rules must return True, or it can never fail against the wrong implementation.
    """
    if len(set(actual.values())) < 2:
        return None

    nodes = {entry["uuid"]: entry for entry in entries if "uuid" in entry}
    children: dict[str | None, list[str]] = {}
    for uuid, node in nodes.items():
        children.setdefault(node.get("parentUuid"), []).append(uuid)

    roots = [
        uuid
        for uuid, node in nodes.items()
        if node.get("parentUuid") is None or node.get("parentUuid") not in nodes
    ]
    visited: list[str] = []

    def walk(uuid: str) -> None:
        visited.append(uuid)
        for child in children.get(uuid, []):
            walk(child)

    for root in roots:
        walk(root)

    file_order_heads: dict[str, str] = {}
    for uuid, branch in actual.items():
        file_order_heads.setdefault(branch, uuid)

    seen_branches: set[str] = set()
    traversal_heads: list[str] = []
    for uuid in visited:
        branch = actual.get(uuid)
        if branch is not None and branch not in seen_branches:
            seen_branches.add(branch)
            traversal_heads.append(uuid)

    traversal_numbering = {
        head: str(position + 1) for position, head in enumerate(traversal_heads)
    }
    file_numbering = {uuid: branch for branch, uuid in file_order_heads.items()}
    return traversal_numbering != file_numbering


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("branch-fixtures")
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for name, (description, entries, expected) in FIXTURES.items():
        checks = preconditions(entries)
        missing = [item for item in REQUIRED[name] if not checks[item]]
        if name == "no-recorded-leaf" and checks["recorded_leaf"]:
            missing.append("must NOT have a recorded leaf")

        actual = _resolve_branch_map(entries)
        map_ok = actual == expected
        precondition_ok = not missing

        separates = discriminates(entries, actual)
        if name == "numbering-order" and separates is not True:
            missing.append("file order and traversal order must disagree")
            precondition_ok = False

        content = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        (out_dir / f"{name}.jsonl").write_text(content, encoding="utf-8")

        status = "OK " if (map_ok and precondition_ok) else "FAIL"
        if not (map_ok and precondition_ok):
            failures += 1
        print(f"[{status}] {name}: {description}")
        print(f"        entries={len(entries)} reaches={[k for k, v in checks.items() if v]}")
        if missing:
            print(f"        MISSING PRECONDITION: {missing}")
        if not map_ok:
            print(f"        expected branch map {expected}")
            print(f"        actual   branch map {actual}")
        else:
            print(f"        branch map {actual}")
        if separates is not None:
            verdict = "yes" if separates else "NO — cannot fail a traversal-order port"
            print(f"        separates file order from traversal order: {verdict}")

    print(f"\nwrote {len(FIXTURES)} sessions to {out_dir}")
    if failures:
        print(f"{failures} fixture(s) do not trip their path — do not land these")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
