"""Second probe batch: classes, ranges, anchors, boundaries, whitespace escapes."""
import json
import sys

probes = [
    {"id": "class_with_i",     "pattern": "[i]",     "haystacks": ["ı", "I", "i"]},
    {"id": "range_h_j",        "pattern": "[h-j]",   "haystacks": ["ı", "I", "i"]},
    {"id": "range_a_z",        "pattern": "[a-z]",   "haystacks": ["ı", "ſ", "K", "A"]},
    {"id": "negated_class_i",  "pattern": "[^i]",    "haystacks": ["ı", "I", "x"]},
    {"id": "dot_any",          "pattern": ".",       "haystacks": ["\n", "ı"]},
    {"id": "word_class",       "pattern": "\\w",     "haystacks": ["ı", "中", "_", "-"]},
    {"id": "alt_literal_i",    "pattern": "i|q",     "haystacks": ["ı", "q"]},
    {"id": "multichar_with_i", "pattern": "kim",     "haystacks": ["kım", "KIM", "kim"]},
    {"id": "boundary_turkish", "pattern": "\\bi\\b", "haystacks": ["a ı b", "a i b"]},
    {"id": "anchor_dollar_nl", "pattern": "x$",      "haystacks": ["x\n", "x\ny", "ax"]},
    {"id": "anchor_caret_nl",  "pattern": "^x",      "haystacks": ["y\nx", "yx"]},
    {"id": "crlf_dollar",      "pattern": "x$",      "haystacks": ["x\r\n"]},
    {"id": "dotall_dot_nl",    "pattern": "a.b",     "haystacks": ["a\nb", "a\r\nb"]},
    {"id": "empty_alt",        "pattern": "a|",      "haystacks": ["z"]},
    {"id": "tab_literal",      "pattern": "a\tb",    "haystacks": ["a\tb", "a b"]},
    {"id": "astral_class",     "pattern": "[\U0001f600-\U0001f60f]", "haystacks": ["\U0001f600"]},
    {"id": "backslash_A_mid",  "pattern": "a\\Ab",   "haystacks": ["ab"]},
    {"id": "nongreedy",        "pattern": "a+?b",    "haystacks": ["aab"]},
    {"id": "whitespace_class", "pattern": "a\\sb",   "haystacks": ["a\tb", "a b", "ab", "a b"]},
    {"id": "control_literal",  "pattern": "a\x01b",  "haystacks": ["a\x01b"]},
    {"id": "escaped_dot",      "pattern": "a\\.b",   "haystacks": ["a.b", "axb"]},
    {"id": "hex_escape",       "pattern": "\\x41",   "haystacks": ["A", "x41"]},
    {"id": "unicode_escape",   "pattern": "\\u0041", "haystacks": ["A", "u0041"]},
    {"id": "named_unicode",    "pattern": "\\N{BULLET}", "haystacks": ["•", "N{BULLET}"]},
]

json.dump(probes, open(sys.argv[1], "w"), ensure_ascii=True)
print(len(probes), "probes written")
