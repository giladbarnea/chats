"""Pin Python `truncate_middle` behavior at the boundaries a Rust port is likely to miss.

Python slices by code point. A Rust port slicing by byte diverges on any non-ASCII
payload and panics on a non-boundary index. The placeholder branches below 5 chars
are the other trap: the function swaps its placeholder and can return a bare prefix
of "...".

Run from the repo root: uv run python thoughts/.../probes/shortening_boundaries.py
"""

from chats.shortening import MIN_SHORT_MAX_CHARS, ShortPolicy
from chats.utils import truncate_middle

SAMPLES = {
    "ascii": "abcdefghijklmnopqrstuvwxyz0123456789",
    "hebrew": "אבגדהוזחטיכלמנסעפצקרשת" * 2,
    "cjk": "日本語のテキストです" * 4,
    "astral": "𝔘𝔫𝔦𝔠𝔬𝔡𝔢" * 6,
    "emoji_zwj": "👨‍👩‍👧‍👦" * 10,
    "combining": "é" * 40,  # e + U+0301, two code points per glyph
}

print("=== truncate_middle: code-point semantics ===")
for name, sample in SAMPLES.items():
    print(f"\n{name}: {len(sample)} code points, {len(sample.encode('utf-8'))} utf-8 bytes")
    for limit in (0, 1, 2, 3, 4, 5, 8, 16, 40):
        result = truncate_middle(sample, max_chars=limit)
        print(
            f"  limit={limit:3} -> {len(result):3} code points, "
            f"{len(result.encode('utf-8')):3} bytes  {result[:28]!r}"
        )

print("\n=== the placeholder branches below len('\\n...\\n') == 5 ===")
for limit in range(0, 7):
    print(f"  limit={limit} -> {truncate_middle('abcdefghij', max_chars=limit)!r}")

print("\n=== short-of-limit passthrough boundary ===")
# `len(s) <= max_chars - len(placeholder)` returns s untouched.
for length in range(1, 12):
    sample = "x" * length
    result = truncate_middle(sample, max_chars=10)
    print(f"  len={length:2} limit=10 -> untouched={result == sample!s:5} {result!r}")

print("\n=== ShortPolicy.effective_max_chars progression ===")
policy = ShortPolicy(128, True)
print(f"  MIN_SHORT_MAX_CHARS={MIN_SHORT_MAX_CHARS}")
for count in (1, 2, 4):
    row = [policy.effective_max_chars(position, count) for position in range(count)]
    print(f"  qualifying_count={count} -> {row}")
print(f"  position=None      -> {policy.effective_max_chars(None, 4)}")
print(f"  non-progressive    -> {ShortPolicy(128, False).effective_max_chars(1, 4)}")
