"""Bucket divergences by the construct that most likely causes them.

A raw divergence list from a generated corpus is unusable — hundreds of rows, a
handful of causes. This groups them so each bucket is one fix.
"""

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

SIGNATURES = [
    ("malformed interval {5,x} / {, 2}", r"\{\s*\d*\s*,\s*[^0-9}]"),
    ("open-min interval {,N}", r"\{,\d"),
    ("empty interval {}", r"\{\}"),
    ("bare brace {", r"\{(?![^}]*\})"),
    ("\\z anchor", r"\\z"),
    ("\\N{...} named escape", r"\\N\{"),
    ("\\p{...} unicode property", r"\\p\{"),
    ("POSIX class [[:...:]]", r"\[\[:"),
    ("possessive quantifier", r"[*+?]\+"),
    ("atomic group (?>", r"\(\?>"),
    ("conditional (?(...)", r"\(\?\("),
    ("lookbehind", r"\(\?<[=!]"),
    ("lookahead", r"\(\?[=!]"),
    ("named group / backref", r"\(\?P"),
    ("numeric backreference", r"\\[1-9]"),
    ("octal escape", r"\\0|\\[1-9]\d\d"),
    ("scoped flags (?i: (?-m:", r"\(\?-?[imsxa]+:"),
    ("global flags (?i)", r"\(\?[imsxaLuR]\)"),
    ("inline comment (?#", r"\(\?#"),
    ("class set ops && --", r"\[[^\]]*(&&|--)"),
    ("unicode literal in class/range", r"[^\x00-\x7f]"),
]


def classify(pattern: str) -> str:
    for label, signature in SIGNATURES:
        if re.search(signature, pattern):
            return label
    return "other"


def main() -> None:
    python = json.loads(pathlib.Path(sys.argv[1]).read_text())
    candidate = json.loads(pathlib.Path(sys.argv[2]).read_text())
    by_id = {row["id"]: row for row in candidate["results"]}

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    kinds: Counter = Counter()
    for probe in python["results"]:
        other = by_id[probe["id"]]
        for mode in ("insensitive", "sensitive"):
            left, right = probe[mode], other[mode]
            if left["compiled_as"] == right["compiled_as"] and left["matches"] == right["matches"]:
                continue
            kind = ("ACCEPT-BOUNDARY" if left["compiled_as"] != right["compiled_as"]
                    else "MATCH-SEMANTICS")
            kinds[kind] += 1
            buckets[(classify(probe["pattern"]), kind)].append({
                "pattern": probe["pattern"],
                "python": left["compiled_as"],
                "candidate": right["compiled_as"],
                "haystacks": probe["haystacks"],
                "python_matches": left["matches"],
                "candidate_matches": right["matches"],
            })

    total = sum(kinds.values())
    print(f"divergent (probe,mode) pairs: {total}")
    for kind, count in kinds.most_common():
        print(f"   {kind}: {count}")
    print()
    print(f"{'construct':<36} {'kind':<17} {'count':>6}  example")
    for (label, kind), rows in sorted(buckets.items(), key=lambda item: -len(item[1])):
        example = rows[0]["pattern"]
        print(f"{label:<36} {kind:<17} {len(rows):>6}  {example!r}")


if __name__ == "__main__":
    main()
