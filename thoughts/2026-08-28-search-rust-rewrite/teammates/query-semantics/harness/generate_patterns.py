"""Falsifier 1: generate patterns across CPython's syntax surface and record its verdicts.

The accept/reject boundary is the highest-value contract in the query layer. Search
falls back to an escaped literal when a pattern is invalid, so any disagreement about
validity silently flips a pattern between regex and literal and changes which sessions
match, with no error on either side.

Deterministic: same seed, same corpus.
"""

import json
import random
import re
import sys

# Fragments spanning what CPython accepts and what sits just outside it. The
# near-misses matter more than the valid forms: they are where a reimplementation
# draws its boundary in the wrong place.
ATOMS = [
    "a", "Z", "9", "_", " ", "-", "é", "ı", "ß", "中",
    r"\d", r"\D", r"\w", r"\W", r"\s", r"\S", r"\b", r"\B",
    r"\A", r"\Z", r"\z", r"\n", r"\t", r"\\", r"\.", r"\-",
    r"\x41", r"A", r"\101", r"\0", r"\8", r"\N{BULLET}", r"\N{NOT A NAME}",
    r"\p{L}", r"\q", ".", "^", "$",
]

CLASSES = [
    "[a-z]", "[^a-z]", "[abc]", "[^abc]", "[a-]", "[-a]", "[]a]", "[a\\]]",
    r"[\d]", r"[\w-]", r"[[:alpha:]]", "[[:foo:]]", "[a&&b]", "[a--b]",
    "[h-j]", "[A-Za-z0-9_]", "[", "[z-a]",
]

QUANTIFIERS = [
    "", "*", "+", "?", "*?", "+?", "??", "*+", "++", "?+",
    "{2}", "{2,}", "{,2}", "{2,4}", "{}", "{,}", "{5,x}", "{, 2}", "{4,2}", "{",
]

GROUPS = [
    "({body})", "(?:{body})", "(?P<n>{body})", "(?P<1n>{body})", "(?={body})",
    "(?!{body})", "(?<={body})", "(?<!{body})", "(?>{body})", "(?#{body})",
    "(?i:{body})", "(?-i:{body})", "(?m:{body})", "(?-m:{body})", "(?s:{body})",
    "(?x:{body})", "(?P={body})", "(?({body})a|b)", "(?<{body}>x)", "({body}",
]

LEADING_FLAGS = ["", "(?i)", "(?m)", "(?s)", "(?x)", "(?a)", "(?L)", "(?u)", "(?R)"]

BACKREFS = [r"\1", r"\2", r"\9", r"(?P=n)"]


def build_pattern(rng: random.Random, depth: int = 0) -> str:
    """Assemble one pattern from the fragment grammar."""
    choice = rng.random()
    if depth < 2 and choice < 0.30:
        template = rng.choice(GROUPS)
        return template.format(body=build_pattern(rng, depth + 1)) + rng.choice(QUANTIFIERS)
    if choice < 0.50:
        return rng.choice(CLASSES) + rng.choice(QUANTIFIERS)
    if depth < 2 and choice < 0.62:
        left = build_pattern(rng, depth + 1)
        right = build_pattern(rng, depth + 1)
        return f"{left}|{right}"
    if choice < 0.68:
        return rng.choice(BACKREFS)
    return rng.choice(ATOMS) + rng.choice(QUANTIFIERS)


def build_haystacks(rng: random.Random, pattern: str) -> list[str]:
    """Short haystacks, biased toward text the pattern could plausibly touch."""
    literals = re.findall(r"[A-Za-z0-9_]", pattern)
    seed_text = "".join(literals[:6]) or "az"
    return [
        seed_text,
        seed_text.upper(),
        seed_text + "\n" + seed_text,
        "aZ9_ ß中\n",
        "",
        pattern[:12],
    ]


def main() -> None:
    out_path, count, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rng = random.Random(seed)
    probes, seen = [], set()
    while len(probes) < count:
        pattern = build_pattern(rng)
        # Nested unbounded quantifiers make CPython exponential; the budget
        # question is measured separately and must not stall this corpus.
        if len(pattern) > 60 or re.search(r"[+*]\)?[+*]", pattern):
            continue
        if pattern in seen:
            continue
        seen.add(pattern)
        probes.append({
            "id": f"gen{len(probes):05d}",
            "pattern": pattern,
            "haystacks": build_haystacks(rng, pattern),
        })
    json.dump(probes, open(out_path, "w"), ensure_ascii=True)

    accepted = 0
    for probe in probes:
        try:
            re.compile(probe["pattern"])
            accepted += 1
        except re.error:
            pass
    print(f"{len(probes)} patterns, seed {seed}")
    print(f"  CPython accepts {accepted} ({accepted / len(probes) * 100:.1f}%), "
          f"rejects {len(probes) - accepted}")


if __name__ == "__main__":
    main()
