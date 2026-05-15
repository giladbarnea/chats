from __future__ import annotations

from dataclasses import dataclass

import nltk
import nltk.tokenize

TOKENIZER = nltk.tokenize.TreebankWordTokenizer()
SUBORDINATE_MARKERS = frozenset({"because", "if", "since", "so", "until", "while"})
QUICK_CHECK_MARKERS = frozenset({"check", "sanity"})


@dataclass(frozen=True)
class MurmurFeatures:
    text: str
    tokens: tuple[str, ...]
    pos_tags: tuple[tuple[str, str], ...]
    token_count: int
    starts_with_now: bool
    starts_with_quick: bool
    starts_with_done: bool
    starts_with_progressive_verb: bool
    starts_with_code_target: bool
    starts_with_build_status: bool
    has_question: bool
    has_markdown_structure: bool
    has_subordinate_marker: bool
    is_short: bool


def analyze_murmur(text: str) -> MurmurFeatures:
    """Extract POS-backed features for cheap murmur detection.

    >>> features = analyze_murmur("Now verifying the build.")
    >>> features.starts_with_progressive_verb
    True
    >>> features.pos_tags[1]
    ('verifying', 'VBG')
    """
    stripped_text = text.strip()
    tokens = tuple(TOKENIZER.tokenize(stripped_text))
    pos_tags = tuple(nltk.pos_tag(list(tokens))) if tokens else ()
    lowered_tokens = tuple(token.lower() for token in tokens)

    starts_with_now = lowered_tokens[:1] == ("now",)
    starts_with_quick = lowered_tokens[:1] == ("quick",)
    starts_with_done = lowered_tokens[:1] == ("done",)

    head_index = 1 if starts_with_now and len(pos_tags) > 1 else 0
    starts_with_progressive_verb = bool(pos_tags) and pos_tags[head_index][1] == "VBG"

    starts_with_code_target = any(
        marker in token for token in tokens[1:3] for marker in ("`", ".", "/")
    )

    return MurmurFeatures(
        text=stripped_text,
        tokens=tokens,
        pos_tags=pos_tags,
        token_count=len(tokens),
        starts_with_now=starts_with_now,
        starts_with_quick=starts_with_quick,
        starts_with_done=starts_with_done,
        starts_with_progressive_verb=starts_with_progressive_verb,
        starts_with_code_target=starts_with_code_target,
        starts_with_build_status=stripped_text.lower().startswith("build green."),
        has_question="?" in stripped_text,
        has_markdown_structure=(
            "\n\n" in stripped_text
            or stripped_text.startswith("#")
            or "\n- " in stripped_text
            or "\n1. " in stripped_text
        ),
        has_subordinate_marker=bool(SUBORDINATE_MARKERS.intersection(lowered_tokens)),
        is_short=len(stripped_text) <= 140 and len(tokens) <= 24,
    )


def is_murmur(text: str) -> bool:
    """Return True when text looks like a terse assistant self-murmur.

    >>> is_murmur("Implementing now.")
    True
    >>> is_murmur("Holding off on coding until I've mapped the surfaces. Researching now.")
    False
    """
    features = analyze_murmur(text)
    if not features.tokens:
        return False
    if features.has_question or features.has_markdown_structure or not features.is_short:
        return False
    if features.starts_with_done and features.token_count <= 3:
        return True
    if features.starts_with_build_status and "quick check" in features.text.lower():
        return True
    if features.starts_with_quick and QUICK_CHECK_MARKERS.intersection(
        token.lower() for token in features.tokens[1:4]
    ):
        return True
    if features.has_subordinate_marker:
        return False
    if features.starts_with_now:
        if features.starts_with_progressive_verb or features.starts_with_code_target:
            return True
        if len(features.pos_tags) > 1 and features.pos_tags[1][1].startswith("VB"):
            if len(features.tokens) > 2 and features.tokens[2].lower() in {"a", "an", "the"} and "—" in features.text:
                return False
            return True
        return False
    return features.starts_with_progressive_verb
