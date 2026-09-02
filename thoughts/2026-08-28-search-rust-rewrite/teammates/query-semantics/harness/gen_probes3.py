"""Third batch: predicted branch-engine defects plus context-curator's trap list."""
import json
import sys

probes = [
    # Predicted defect: invalid pattern falls back to an escaped literal, and the
    # fallback must keep IGNORECASE. Every haystack differs only by letter case.
    {"id": "fallback_icase_paren",  "pattern": "Foo(",      "haystacks": ["foo(", "FOO(", "Foo("]},
    {"id": "fallback_icase_brack",  "pattern": "Bar[",      "haystacks": ["bar[", "BAR[", "Bar["]},
    {"id": "fallback_icase_star",   "pattern": "*Baz",      "haystacks": ["*baz", "*BAZ"]},

    # context-curator trap list.
    {"id": "trap_brace_min0",       "pattern": "a{,2}",     "haystacks": ["aa", "", "a{,2}"]},
    {"id": "trap_brace_open",       "pattern": "a{,}",      "haystacks": ["aaa", "a{,}"]},
    {"id": "trap_brace_empty",      "pattern": "a{}",       "haystacks": ["a{}", "a"]},
    {"id": "trap_verbose_flag",     "pattern": "(?x)a b",   "haystacks": ["ab", "a b"]},
    {"id": "trap_verbose_scoped",   "pattern": "(?x:a b)",  "haystacks": ["ab", "a b"]},
    {"id": "trap_verbose_comment",  "pattern": "(?x)a#c\nb", "haystacks": ["ab", "a#cb"]},
    {"id": "trap_lookbehind_var1",  "pattern": "(?<=ab+)c", "haystacks": ["abbc", "(?<=ab+)c"]},
    {"id": "trap_lookbehind_var2",  "pattern": "(?<=a*)b",  "haystacks": ["aab", "(?<=a*)b"]},
    {"id": "trap_lookbehind_fixed", "pattern": "(?<=ab)c",  "haystacks": ["abc", "xbc"]},
    {"id": "trap_scoped_nomulti",   "pattern": "(?-m:^two$)", "haystacks": ["one\ntwo\nthree", "two"]},
    {"id": "trap_scoped_multi",     "pattern": "(?m:^two$)",  "haystacks": ["one\ntwo\nthree"]},

    # Open items the branch never fixed: malformed intervals inside alternation.
    {"id": "open_interval_alt1",    "pattern": "zzz|a{5,x}", "haystacks": ["zzz", "a{5,x}"]},
    {"id": "open_interval_alt2",    "pattern": "zzz|a{, 2}", "haystacks": ["zzz", "a{, 2}"]},
    {"id": "open_interval_bare",    "pattern": "a{5,x}",     "haystacks": ["a{5,x}", "aaaaa"]},

    # Anchors Python gained recently.
    {"id": "anchor_lower_z",        "pattern": "foo\\z",     "haystacks": ["foo", "foo\n"]},

    # Unicode classes.
    {"id": "digit_arabic_indic",    "pattern": "\\d",        "haystacks": ["٠", "5", "a"]},
    {"id": "digit_devanagari",      "pattern": "\\d",        "haystacks": ["०"]},
    {"id": "word_arabic_indic",     "pattern": "\\w",        "haystacks": ["٠", "中"]},
    {"id": "space_unicode_nbsp",    "pattern": "\\s",        "haystacks": [" ", " ", " "]},

    # Ranges under IGNORECASE with extra-case members.
    {"id": "range_with_extra_i",    "pattern": "[h-j]",      "haystacks": ["ı"]},
    {"id": "range_with_long_s",     "pattern": "[a-z]",      "haystacks": ["ſ", "K"]},
    {"id": "range_micro",           "pattern": "[a-ÿ]", "haystacks": ["μ"]},
    {"id": "class_negated_extra",   "pattern": "[^h-j]",     "haystacks": ["ı"]},
]

json.dump(probes, open(sys.argv[1], "w"), ensure_ascii=True)
print(len(probes), "probes written")
