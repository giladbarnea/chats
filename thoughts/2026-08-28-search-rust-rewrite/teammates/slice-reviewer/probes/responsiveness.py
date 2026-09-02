#!/usr/bin/env -S uv run
"""`reviewer-profiler`'s question 2, answered by computation rather than by argument.

"Does the subject respond to each swept dimension?" is checkable post hoc from the
frozen outputs alone -- no mutation, no re-run. For each ambient INPUT, compare the
recorded bytes at its two settings. If they are identical, that input moved nothing
under that condition, and every row the sweep reports for it is a row that could not
have failed.

FIRST CUT WAS WRONG AND IS RECORDED AS SUCH. I first counted distinct outputs per
dimension and found "13 of 18 members identical" under a pty, which reads as a
finding. Reading the instances killed it: the collapsed group is every input's
*unset* setting, which SHOULD produce the baseline. The question is not whether
members differ from each other, it is whether an input's two settings differ from
EACH OTHER. 22c, on my own aggregate.

Read-only.
"""
import json
from collections import defaultdict
from pathlib import Path

REFERENCE = Path(
    "thoughts/2026-08-28-search-rust-rewrite/teammates/reviewer-profiler/frozen_reference.json"
)


def payload_of(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def main() -> None:
    entries = json.loads(REFERENCE.read_text())["entries"]
    conditions: dict[str, dict[str, dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    other: dict[str, dict[str, str]] = defaultdict(dict)

    for key, value in entries.items():
        dimension, _, member = key.partition("/")
        if "/" in member:
            name, _, setting = member.rpartition("/")
            conditions[dimension][name][setting] = payload_of(value)
        elif member and dimension.startswith(("ambient", "stderr-ambient")):
            name, _, setting = member.rpartition("/")
            conditions[dimension][name or member][setting or "-"] = payload_of(value)
        else:
            other[dimension][member or key] = payload_of(value)

    for dimension in sorted(conditions):
        inputs = conditions[dimension]
        print(f"\n{dimension} — {len(inputs)} inputs")
        for name in sorted(inputs):
            settings = inputs[name]
            if len(settings) < 2:
                print(f"    {name:18s} only one setting recorded — nothing compared")
                continue
            distinct = len(set(settings.values()))
            verdict = "responds" if distinct > 1 else "*** INERT — both settings identical ***"
            print(f"    {name:18s} {len(settings)} settings, {distinct} distinct   {verdict}")

    for dimension in sorted(other):
        members = other[dimension]
        buckets = defaultdict(list)
        for member, payload in members.items():
            buckets[payload].append(member)
        print(f"\n{dimension} — {len(members)} members, {len(buckets)} distinct")
        for payload, group in buckets.items():
            if len(group) > 1:
                print(f"    identical: {' == '.join(sorted(group))}")


if __name__ == "__main__":
    main()
