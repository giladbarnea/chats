"""Search patterns for the product differential suite.

`contract-owner` runs the public journey twice over one fixture corpus and compares
emitted session ids byte for byte. That differential is the oracle, so nothing here
knows what CPython says — this module only supplies patterns.

Two entry points:

    generate_patterns(seed, count) -> list[str]
    DEFECT_PATTERNS: dict[str, str]

`generate_patterns` is deterministic for a seed. Keep the generator live in the suite
rather than freezing a dump: three of the ten known defect classes came out of it and
none would have been written by hand.

Every pattern this module yields is backtracking-safe. A catastrophic pattern wedges a
differential suite instead of failing it, because CPython does not finish.

>>> generate_patterns(1, 3) == generate_patterns(1, 3)
True
>>> all(is_backtracking_safe(p) for p in generate_patterns(7, 200))
True
"""

from __future__ import annotations

import random
import re

# Fragments spanning what CPython accepts and the near-misses just outside it. The
# near-misses matter more: they are where a reimplementation draws its validity
# boundary in the wrong place, which silently flips a pattern between regex and
# literal and changes which sessions match.
ATOMS = [
    "a", "Z", "9", "_", " ", "-", "é", "ı", "ß", "中",
    r"\d", r"\D", r"\w", r"\W", r"\s", r"\S", r"\b", r"\B",
    r"\A", r"\Z", r"\z", r"\n", r"\t", r"\\", r"\.", r"\-",
    r"\x41", "A", r"\101", r"\0", r"\8", r"\N{BULLET}", r"\N{NOT A NAME}",
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

BACKREFERENCES = [r"\1", r"\2", r"\9", "(?P=n)"]

_QUANTIFIER_START = frozenset("*+?{")

# A `?` directly after `(` opens a group form, it does not quantify anything.
# Consuming the whole prefix keeps `(?:ab)+c` out of the catastrophic bucket.
_GROUP_PREFIX = re.compile(
    r"\(\?(?:P<[^>]*>|P=[^)]*\)|<[=!]|[=!>#]|[aiLmsux]*(?:-[aiLmsux]+)?[:)])"
)

# One pattern per known defect class, pinned by name so a seed change cannot
# silently drop coverage. Verdicts live with the engine owner, not here.
DEFECT_PATTERNS: dict[str, str] = {
    "fallback_drops_ignorecase": "Foo(",
    "fallback_drops_ignorecase_bracket": "Bar[",
    "digit_escape_is_unicode": r"\d",
    "range_ignores_extra_cases": "[a-z]",
    "range_ignores_extra_cases_narrow": "[h-j]",
    "negated_range_extra_cases": "[^h-j]",
    "lower_z_anchor": r"foo\z",
    "malformed_interval_in_alternation": "zzz|a{5,x}",
    "malformed_interval_spaced": "zzz|a{, 2}",
    "posix_class_future_warning": "[[:alpha:]]",
    "quantified_word_boundary": r"\B{2}",
    "quantified_caret": "^{2}a",
    "invalid_group_name_digit": "(?P<1n>a)",
    "invalid_group_name_dash": "(?P<n-x>a)",
    "ascii_flag": r"(?a)\w",
    "unicode_flag": r"(?u)\w",
    "word_escape_over_matches": r"\w",
    "empty_alternation_matches_all": "zznope|",
}


def is_backtracking_safe(pattern: str) -> bool:
    """Reject patterns whose match time can blow up exponentially.

    A quantified group whose body itself repeats, or which alternates, is the
    classic catastrophic shape. CPython does not finish on those, so a product
    differential hangs rather than diverging.

    >>> is_backtracking_safe("(a+)+b")
    False
    >>> is_backtracking_safe("(a|a)*b")
    False
    >>> is_backtracking_safe("(?:ab)+c")
    True
    """
    depth_has_quantifier: list[bool] = []
    depth_has_alternation: list[bool] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\":
            index += 2
            continue
        if character == "(":
            depth_has_quantifier.append(False)
            depth_has_alternation.append(False)
            prefix = _GROUP_PREFIX.match(pattern, index)
            if prefix is None:
                index += 1
                continue
            # Forms like `(?i)` and `(?P=n)` close inside their own prefix.
            if prefix.group().endswith(")"):
                depth_has_quantifier.pop()
                depth_has_alternation.pop()
            index = prefix.end()
            continue
        if character == ")" and depth_has_quantifier:
            body_repeats = depth_has_quantifier.pop()
            body_alternates = depth_has_alternation.pop()
            following = pattern[index + 1 : index + 2]
            if following in _QUANTIFIER_START and (body_repeats or body_alternates):
                return False
            if following in _QUANTIFIER_START:
                for stack in (depth_has_quantifier,):
                    if stack:
                        stack[-1] = True
            index += 1
            continue
        if character == "|" and depth_has_alternation:
            depth_has_alternation[-1] = True
        if character in _QUANTIFIER_START and depth_has_quantifier:
            depth_has_quantifier[-1] = True
        index += 1
    return True


def _build(rng: random.Random, depth: int = 0) -> str:
    """Assemble one pattern from the fragment grammar."""
    choice = rng.random()
    if depth < 2 and choice < 0.30:
        template = rng.choice(GROUPS)
        return template.format(body=_build(rng, depth + 1)) + rng.choice(QUANTIFIERS)
    if choice < 0.50:
        return rng.choice(CLASSES) + rng.choice(QUANTIFIERS)
    if depth < 2 and choice < 0.62:
        return f"{_build(rng, depth + 1)}|{_build(rng, depth + 1)}"
    if choice < 0.68:
        return rng.choice(BACKREFERENCES)
    return rng.choice(ATOMS) + rng.choice(QUANTIFIERS)


def generate_patterns(seed: int, count: int) -> list[str]:
    """Return `count` distinct backtracking-safe patterns, deterministic for `seed`.

    >>> len(generate_patterns(3, 50))
    50
    """
    rng = random.Random(seed)
    patterns: list[str] = []
    seen: set[str] = set()
    while len(patterns) < count:
        pattern = _build(rng)
        if len(pattern) > 60 or pattern in seen or not is_backtracking_safe(pattern):
            continue
        seen.add(pattern)
        patterns.append(pattern)
    return patterns


def adversarial_haystacks(pattern: str) -> list[str]:
    """Short texts biased toward what `pattern` could plausibly touch."""
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
