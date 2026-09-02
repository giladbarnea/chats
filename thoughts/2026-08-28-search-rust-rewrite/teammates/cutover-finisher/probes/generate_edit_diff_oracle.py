#!/usr/bin/env -S uv run
"""Freeze CPython's `difflib.unified_diff` answers for the two corpora that grade the
vendored `SequenceMatcher`.

**Both sides are stored.** The inputs and CPython's answers travel together, because a
recorded disagreement with only one side on disk dies the moment the other becomes
unavailable — and the Python route is what the cutover deletes.

**Two corpora, because the first cannot see the defect this grades.**

1. `real-edits` — every `Edit` tool call in the frozen pool. This is what the product
   actually feeds the diff, and almost none of it reaches 200 lines, so it cannot
   exercise the autojunk heuristic at all.
2. `long-bodies` — pairs built from real source files over 200 lines, each carrying
   whether autojunk changes CPython's own answer. This is the corpus that can see it.

Paths are ordered by a hash of the path rather than by a shuffle, so a pool that grows
adds cases at the tail instead of reshuffling every position.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import random
import sys
from pathlib import Path

POOL = Path("/private/tmp/ch-pool-snapshot")
# `registry.TOOL_NAME_ALIASES` maps only Pi's lowercase `edit` onto `Edit`.
EDIT_NAMES = {"edit"}


def hashed_order(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda path: hashlib.sha256(str(path).encode()).hexdigest())


def python_str(value: object) -> str:
    """`str(value)` as CPython renders it, over a JSON-decoded value."""
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, str):
        return value
    return repr(value)


def unified(old: str, new: str, autojunk: bool = True) -> list[str]:
    """The product's call: `difflib.unified_diff(old, new, lineterm="")` at n=2."""
    first, second = old.splitlines(), new.splitlines()
    if autojunk:
        return list(difflib.unified_diff(first, second, lineterm="", n=2))
    matcher = difflib.SequenceMatcher(None, first, second, autojunk=False)
    return list(_unified_from(matcher, first, second, n=2))


def _unified_from(matcher, first, second, n):
    """CPython's `unified_diff` body, with the matcher supplied so autojunk can vary."""
    started = False
    for group in matcher.get_grouped_opcodes(n):
        if not started:
            started = True
            yield "--- "
            yield "+++ "
        head, tail = group[0], group[-1]
        first_range = difflib._format_range_unified(head[1], tail[2])
        second_range = difflib._format_range_unified(head[3], tail[4])
        yield f"@@ -{first_range} +{second_range} @@"
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for line in first[i1:i2]:
                    yield " " + line
                continue
            if tag in {"replace", "delete"}:
                for line in first[i1:i2]:
                    yield "-" + line
            if tag in {"replace", "insert"}:
                for line in second[j1:j2]:
                    yield "+" + line


def harvest_real_edits(limit: int) -> tuple[list[dict], int]:
    """Every `Edit` call in the pool, and how many there are.

    **Both numbers, because a stored sample without its denominator is a claim.** The
    fixture keeps the first `limit` in hashed path order and records the total found,
    so a reader can tell a complete corpus from a capped one.
    """
    cases: list[dict] = []
    found = 0
    for path in hashed_order(list(POOL.rglob("*.jsonl"))):
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        for line in content.split("\n"):
            if '"Edit"' not in line and '"edit"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for block in iter_tool_uses(record):
                name = block.get("name")
                if not isinstance(name, str):
                    continue
                if name != "Edit" and name.lower() not in EDIT_NAMES:
                    continue
                data = block.get("input")
                if not isinstance(data, dict) or not data:
                    continue
                found += 1
                if len(cases) >= limit:
                    continue
                old = python_str(data.get("old_string", ""))
                new = python_str(data.get("new_string", ""))
                cases.append(
                    {
                        "old_string": data.get("old_string", ""),
                        "new_string": data.get("new_string", ""),
                        "expected": unified(old, new),
                    }
                )
    return cases, found


def iter_tool_uses(record: object):
    """Every `tool_use` block anywhere in a decoded transcript record."""
    stack = [record]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if item.get("type") == "tool_use":
                yield item
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def mutate(lines: list[str], seed: int) -> list[str]:
    """A realistic edit, at four intensities.

    **Intensity is the point.** A one-line change over a 300-line body barely reaches
    the autojunk heuristic, because the match that anchors the diff is nowhere near a
    popular line. Moving and duplicating blocks is what makes the purge decide
    something, which is what this corpus exists to grade.
    """
    rng = random.Random(seed)
    out = list(lines)
    shape = seed % 4
    if shape == 0:
        for _ in range(rng.randint(1, 6)):
            if not out:
                break
            index = rng.randrange(len(out))
            kind = rng.choice(("delete", "insert", "replace"))
            if kind == "delete":
                del out[index : index + rng.randint(1, 4)]
            elif kind == "insert":
                out[index:index] = [
                    f"    # inserted {rng.randrange(1000)}" for _ in range(rng.randint(1, 4))
                ]
            else:
                out[index] = out[index].replace("    ", "  ", 1) + "  # changed"
    elif shape == 1:
        # A block moved somewhere else, which is where anchoring on a popular line
        # changes the answer.
        start = rng.randrange(max(1, len(out) - 40))
        block = out[start : start + 30]
        del out[start : start + 30]
        out[rng.randrange(len(out) or 1) : 0] = []
        target = rng.randrange(len(out) or 1)
        out[target:target] = block
    elif shape == 2:
        # A block duplicated, so an element's position count crosses the 1% threshold.
        start = rng.randrange(max(1, len(out) - 30))
        out[start:start] = out[start : start + 25]
    else:
        # Many scattered small changes at once.
        for index in range(0, len(out), rng.randint(7, 15)):
            out[index] = out[index] + f"  # {rng.randrange(100)}"
    return out


def harvest_long_bodies(limit: int, body_lines: int, readable: int = 40) -> list[dict]:
    roots = [Path("src"), Path("rust"), Path("tests"), Path("scripts"), Path("thoughts")]
    sources: list[Path] = []
    for root in roots:
        if root.is_dir():
            sources.extend(path for path in root.rglob("*") if path.is_file())
    cases: list[dict] = []
    seed = 0
    for path in hashed_order(sources):
        try:
            body = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        lines = body.splitlines()
        if len(lines) < 200:
            continue
        # **Capped, because the fixture has to be committable.** Two hundred lines is
        # where CPython's `autojunk` engages at all, so a longer body buys reach the
        # gate does not need and megabytes it cannot afford.
        lines = lines[:body_lines]
        for _ in range(4):
            seed += 1
            changed = mutate(lines, seed)
            old, new = "\n".join(lines), "\n".join(changed)
            expected = unified(old, new)
            case = {
                "old_string": old,
                "new_string": new,
                # **A digest rather than the text, and only here.** Storing 900 whole
                # diffs over 900 whole bodies is 75 MB of fixture. A digest still
                # answers this corpus's only question — byte-identical or not — for as
                # long as the fixture lives, which outlives the Python route that
                # produced it. What it cannot do is show a reader *how* a failure
                # differs, so the first cases keep their full text for that.
                "expected_digest": hashlib.sha256("\n".join(expected).encode()).hexdigest(),
                "autojunk_matters": expected != unified(old, new, autojunk=False),
            }
            if len(cases) < readable:
                case["expected"] = expected
            cases.append(case)
            if len(cases) >= limit:
                return cases
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--real-edit-limit", type=int, default=3000)
    parser.add_argument("--long-body-limit", type=int, default=900)
    parser.add_argument("--body-lines", type=int, default=240)
    options = parser.parse_args()

    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)

    real, found = harvest_real_edits(options.real_edit_limit)
    over_200 = sum(1 for case in real if len(python_str(case["old_string"]).splitlines()) >= 200)
    (out / "real-edits.json").write_text(
        json.dumps(
            {"cases": real, "over_200_lines": over_200, "found_in_pool": found},
            ensure_ascii=False,
        )
    )
    print(f"real-edits: {len(real)} of {found} found, {over_200} reaching 200 lines")

    long_bodies = harvest_long_bodies(options.long_body_limit, options.body_lines)
    matters = sum(1 for case in long_bodies if case["autojunk_matters"])
    (out / "long-bodies.json").write_text(
        json.dumps({"cases": long_bodies, "autojunk_matters": matters}, ensure_ascii=False)
    )
    share = 100.0 * matters / len(long_bodies) if long_bodies else 0.0
    print(f"long-bodies: {len(long_bodies)} pairs, autojunk changes {matters} ({share:.1f}%)")


if __name__ == "__main__":
    main()
