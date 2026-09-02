"""Cases for the boolean layer and highlight spans.

Hand-written rather than generated: the boolean grammar is small and its
interesting cases are known — precedence, the flat `NOT` form, quoting rules,
and the malformed shapes that exit 2. Span cases pair a query with a haystack
where overlapping and adjacent literals make ordering observable.
"""

import json
import sys

QUERIES = [
    # Single terms, the no-operator path.
    "alpha", "alpha beta", "don't panic", "and or not", "and", "AND",
    # Precedence: AND binds tighter than OR.
    "a AND b", "a OR b", "a OR b AND c", "a AND b OR c", "a AND b AND c",
    "a OR b OR c", "(a OR b) AND c", "a AND (b OR c)", "((a))", "(a OR b)",
    # NOT is a separate flat form and cannot mix with AND/OR.
    "a NOT b", "a NOT b NOT c", "a AND b NOT c", "a NOT b AND c", "a OR b NOT c",
    "NOT a", "NOT", "a NOT", "a NOT (b)", "(a) NOT b",
    # Quoting.
    '"hello world" AND foo', "'hello world' OR foo", '"" AND a', '"a" NOT ""',
    '"unterminated AND a', "mixed 'quote\" AND a", '"a b" NOT "c d"',
    # Operators are uppercase-only.
    "a and b", "a And b", "a Or b", "a nOt b",
    # Malformed shapes that must exit 2.
    "AND", "OR", "AND b", "a AND", "a OR", "(a AND b", "a AND b)", "()",
    "a AND AND b", "a b AND c", "a AND (b", "(", ")",
    # Regex-shaped terms alongside operators.
    "a.* AND b", "[a-z]+ OR c", "(?i)x AND y", "a+ NOT b*",
    # Terms that stay literal versus terms that do not, for highlight selection.
    "alpha AND be.ta", "al.pha AND beta", "al.pha AND be.ta",
    # Folding, where the two span algorithms are most likely to part company:
    # CPython walks an escaped-literal alternation under IGNORECASE, the branch
    # compares character by character through its own equivalence.
    "i", "I", "ı", "s", "K", "k", "ss", "ß", "fi",
    "i AND s", "K OR k", "ss OR ß",
    # Overlapping literals of different lengths, where longest-first matters.
    "a OR ab", "ab OR a", "abc OR ab OR a", "alpha OR alphaalpha",
]

# Haystacks chosen so overlapping and adjacent literals make span order visible.
HAYSTACKS = [
    "alpha beta gamma",
    "ALPHA Beta alphabeta",
    "a b c ab abc",
    "alphaalpha",
    "the quick brown fox",
    "ıI iİ ßss K",
]


def main() -> None:
    cases = []
    for query_index, query in enumerate(QUERIES):
        for haystack_index, haystack in enumerate(HAYSTACKS):
            cases.append({
                "id": f"bool{query_index:03d}_{haystack_index}",
                "query": query,
                "haystack": haystack,
            })
    json.dump(cases, open(sys.argv[1], "w"), ensure_ascii=True)
    print(f"{len(cases)} cases from {len(QUERIES)} queries x {len(HAYSTACKS)} haystacks")


if __name__ == "__main__":
    main()
