"""Record CPython's verdict for the boolean layer and for highlight spans.

Two gaps the term-level harness could not see:

1. The boolean grammar — `AND`/`OR`/`NOT` tokenizing, precedence, the flat `NOT`
   form, malformed-query errors — which is public, documented, and exits 2.
2. Match spans. Highlighting is built from spans and is visible on every colored
   hit, so a span divergence with identical boolean verdicts is invisible to a
   harness that compares only "did it match".

Tree shape plus `iter_terms` fully determines `evaluate`, so serializing both is a
complete characterization without needing a truth table over short-circuiting calls.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "src")

from chats.commands.search import _build_highlight_regex  # noqa: E402
from chats.search_query import (  # noqa: E402
    AndQuery,
    NotQuery,
    OrQuery,
    SearchQueryError,
    SearchTerm,
    parse_search_query,
)


def shape(query) -> str:
    """Canonical serialization of a parsed query tree.

    >>> shape(parse_search_query("a AND b"))
    'AND(T:a,T:b)'
    >>> shape(parse_search_query("a NOT b"))
    'AND(T:a,NOT(T:b))'
    """
    if isinstance(query, SearchTerm):
        return f"T:{query.pattern}"
    if isinstance(query, AndQuery):
        return "AND(" + ",".join(shape(operand) for operand in query.operands) + ")"
    if isinstance(query, OrQuery):
        return "OR(" + ",".join(shape(operand) for operand in query.operands) + ")"
    if isinstance(query, NotQuery):
        return f"NOT({shape(query.operand)})"
    raise TypeError(f"unexpected node {query!r}")


def characterize(pattern_arg: str, case_sensitive: bool, haystack: str) -> dict:
    try:
        query = parse_search_query(pattern_arg, case_sensitive=case_sensitive)
    except SearchQueryError as error:
        return {"parsed": False, "error": str(error)}

    highlight = _build_highlight_regex(query)
    spans = (
        [[match.start(), match.end(), match.group()] for match in highlight.finditer(haystack)]
        if highlight is not None
        else []
    )
    return {
        "parsed": True,
        "error": None,
        "shape": shape(query),
        # Excludes negated terms by design: `NotQuery.iter_terms` yields nothing.
        # This list drives both highlighting and the displayed match set.
        "iter_terms": [term.pattern for term in query.iter_terms()],
        "highlight_pattern": highlight.pattern if highlight is not None else None,
        "highlight_ignorecase": bool(highlight.flags & 2) if highlight is not None else None,
        "spans": spans,
    }


def main() -> None:
    cases = json.loads(pathlib.Path(sys.argv[1]).read_text())
    results = []
    for case in cases:
        results.append({
            "id": case["id"],
            "query": case["query"],
            "haystack": case["haystack"],
            "insensitive": characterize(case["query"], False, case["haystack"]),
            "sensitive": characterize(case["query"], True, case["haystack"]),
        })
    print(json.dumps({"results": results}, ensure_ascii=True, indent=1))


if __name__ == "__main__":
    main()
