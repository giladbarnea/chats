"""Fourth batch: constructs isolated from the generated corpus's divergence buckets."""
import json
import sys

probes = [
    # Quantified zero-width assertions. CPython allows repeating an assertion.
    {"id": "quant_word_boundary", "pattern": "\\B{2}",   "haystacks": ["ab", "a b"]},
    {"id": "quant_boundary_b",    "pattern": "\\b{2}",   "haystacks": ["ab", "a b"]},
    {"id": "quant_caret",         "pattern": "^{2}a",    "haystacks": ["a", "ba"]},
    {"id": "quant_lookahead",     "pattern": "(?=a){2}", "haystacks": ["a", "b"]},

    # Reversed interval bounds.
    {"id": "interval_reversed",   "pattern": "a{4,2}",   "haystacks": ["aaaa", "a{4,2}"]},
    {"id": "interval_rev_alt",    "pattern": "zz|a{4,2}", "haystacks": ["zz"]},

    # Group-name validity.
    {"id": "group_name_digit",    "pattern": "(?P<1n>a)", "haystacks": ["a", "(?P<1n>a)"]},
    {"id": "group_name_valid",    "pattern": "(?P<n1>a)", "haystacks": ["a"]},
    {"id": "group_name_dash",     "pattern": "(?P<n-x>a)", "haystacks": ["a", "(?P<n-x>a)"]},

    # Backreference to a group that does not exist.
    {"id": "backref_undefined",   "pattern": "\\1",       "haystacks": ["a", "\\1"]},
    {"id": "backref_defined",     "pattern": "(a)\\1",    "haystacks": ["aa", "ab"]},
    {"id": "named_backref_undef", "pattern": "(?P=nope)", "haystacks": ["a"]},

    # Octal versus group reference.
    {"id": "escape_zero",         "pattern": "\\0",       "haystacks": ["\x00", "0"]},
    {"id": "escape_8",            "pattern": "\\8",       "haystacks": ["8", "\\8"]},
    {"id": "escape_377",          "pattern": "\\377",     "haystacks": ["ÿ"]},
    {"id": "escape_400",          "pattern": "\\400",     "haystacks": ["x"]},

    # Flag spellings CPython knows.
    {"id": "flag_ascii",          "pattern": "(?a)\\w",   "haystacks": ["é", "a"]},
    {"id": "flag_unicode",        "pattern": "(?u)\\w",   "haystacks": ["é", "a"]},
    {"id": "flag_locale",         "pattern": "(?L)\\w",   "haystacks": ["a"]},

    # Empty and degenerate forms.
    {"id": "empty_alt_trailing",  "pattern": "zznope|",   "haystacks": ["unrelated text"]},
    {"id": "empty_group",         "pattern": "()",        "haystacks": ["x"]},
    {"id": "nested_empty_alt",    "pattern": "(|)",       "haystacks": ["x"]},
]

json.dump(probes, open(sys.argv[1], "w"), ensure_ascii=True)
print(len(probes), "probes written")
