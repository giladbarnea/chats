"""Census the Claude corpus for the branch-resolution shapes `_resolve_branch_map` handles.

Its docstring names four structural cases. This asks which of them real transcripts
actually contain, so the contract knows whether a fixture exists or must be authored.

Run from the repo root: uv run python thoughts/.../probes/branch_shapes.py
"""

from __future__ import annotations

from collections import Counter, defaultdict

from chats.parsing import (
    _iter_jsonl_entries,
    _resolve_branch_map,
    find_all_supported_session_files,
    get_jsonl_session_adapter,
)

shapes: Counter = Counter()
examples: dict[str, str] = {}
branch_counts: Counter = Counter()


def note(shape: str, path: str) -> None:
    shapes[shape] += 1
    examples.setdefault(shape, path)


for session in find_all_supported_session_files():
    try:
        if get_jsonl_session_adapter(session).name != "claude":
            continue
        entries = _iter_jsonl_entries(session.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        shapes["unreadable"] += 1
        continue

    nodes = {entry["uuid"]: entry for entry in entries if "uuid" in entry}
    if not nodes:
        continue
    shapes["claude_sessions"] += 1

    children: dict[str | None, list[str]] = defaultdict(list)
    for node_uuid, node in nodes.items():
        children[node.get("parentUuid")].append(node_uuid)

    null_parent_roots = [u for u, n in nodes.items() if n.get("parentUuid") is None]
    external_parent_roots = [
        u
        for u, n in nodes.items()
        if n.get("parentUuid") is not None and n.get("parentUuid") not in nodes
    ]
    compaction_roots = [
        u
        for u in nodes
        if nodes[u].get("type") == "system"
        and nodes[u].get("subtype") == "compact_boundary"
    ]
    leaves = [
        entry["leafUuid"]
        for entry in entries
        if entry.get("type") == "last-prompt" and entry.get("leafUuid") in nodes
    ]
    forks = [u for u, kids in children.items() if u is not None and len(kids) > 1]

    branch_of = _resolve_branch_map(entries)
    distinct = len(set(branch_of.values()))
    branch_counts[distinct] += 1

    path = str(session)
    if branch_of:
        note("has_off_main_branch", path)
    if distinct > 1:
        note("multiple_distinct_branches", path)
    if compaction_roots:
        note("compaction_boundary", path)
    if len(null_parent_roots) > 1:
        note("multiple_null_parent_roots__rewind_to_first", path)
    if external_parent_roots:
        note("truncated_head__parent_outside_file", path)
    if not leaves:
        note("no_recorded_last_prompt_leaf", path)
    if len(leaves) > 1:
        note("multiple_last_prompt_leaves", path)
    if forks:
        note("forking_node", path)
    if compaction_roots and branch_of:
        note("COMBO_compaction_plus_branch", path)
    if len(null_parent_roots) > 1 and leaves:
        note("COMBO_rewind_first_with_leaf", path)
    if compaction_roots and len(null_parent_roots) > 1:
        note("COMBO_compaction_plus_rewind_first", path)

print("=== Claude branch-shape census ===")
for shape, count in shapes.most_common():
    print(f"{count:6}  {shape}")

print("\n=== distinct branch ids per session ===")
for distinct, count in sorted(branch_counts.items()):
    print(f"  {distinct} branch ids: {count} sessions")

print("\n=== one example path per shape ===")
for shape in sorted(examples):
    print(f"  {shape}\n      {examples[shape]}")
