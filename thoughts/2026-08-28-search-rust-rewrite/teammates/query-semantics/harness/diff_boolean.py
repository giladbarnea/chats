"""Report boolean-layer and span disagreements, grouped by which facet diverged."""

import json
import pathlib
import sys
from collections import Counter

FACETS = ("parsed", "error", "shape", "iter_terms", "spans")


def main() -> None:
    python = json.loads(pathlib.Path(sys.argv[1]).read_text())
    candidate = json.loads(pathlib.Path(sys.argv[2]).read_text())
    by_id = {row["id"]: row for row in candidate["results"]}

    counts: Counter = Counter()
    shown: Counter = Counter()
    total = 0
    for probe in python["results"]:
        other = by_id[probe["id"]]
        for mode in ("insensitive", "sensitive"):
            left, right = probe[mode], other[mode]
            diverged = [
                facet for facet in FACETS
                if facet in left and facet in right and left[facet] != right[facet]
            ]
            # A parse-failure message wording difference is reported separately
            # from a parse-outcome difference: only the latter changes results.
            if not diverged:
                continue
            total += 1
            key = ",".join(diverged)
            counts[key] += 1
            if shown[key] < 2:
                shown[key] += 1
                print(f"[{key}] {probe['id']} ({mode})  query={probe['query']!r}")
                print(f"   haystack={probe['haystack']!r}")
                for facet in diverged:
                    print(f"   python.{facet:<14} = {left[facet]!r}")
                    print(f"   branch.{facet:<14} = {right[facet]!r}")
                print()

    print(f"divergent (case,mode) pairs: {total} of {len(python['results']) * 2}")
    for key, count in counts.most_common():
        print(f"   {key}: {count}")


if __name__ == "__main__":
    main()
