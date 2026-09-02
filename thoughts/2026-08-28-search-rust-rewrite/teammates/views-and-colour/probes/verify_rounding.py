"""Locate every input where Python's round() and Rust's f64::round() disagree
inside Rich 14.3.3's TRUECOLOR -> EIGHT_BIT downgrade.

Control: the same code with Python's own round must reproduce the oracle exactly.
A control that fails means the algorithm model is wrong, not the rounding.
"""
import json
from colorsys import rgb_to_hls
from math import floor

ORACLE = "thoughts/2026-08-28-search-rust-rewrite/teammates/session-core/colour-downgrade-oracle.json"


def away_from_zero(x: float) -> int:
    """Rust f64::round semantics: ties away from zero."""
    return int(floor(x + 0.5)) if x >= 0 else -int(-floor(-x + 0.5))


def eight_bit(rgb, rounder):
    red, green, blue = rgb
    _h, lightness, saturation = rgb_to_hls(red / 255.0, green / 255.0, blue / 255.0)
    if saturation < 0.15:
        gray = rounder(lightness * 25.0)
        if gray == 0:
            return 16
        if gray == 25:
            return 231
        return 231 + gray
    six = [c / 95 if c < 95 else 1 + (c - 95) / 40 for c in (red, green, blue)]
    return 16 + 36 * rounder(six[0]) + 6 * rounder(six[1]) + rounder(six[2])


oracle = json.load(open(ORACLE))
for section in ("palette", "algorithm_critical"):
    rows = oracle[section]
    control = sum(eight_bit(tuple(r["rgb"]), round) != r["eight_bit"]["number"] for r in rows)
    naive = [r["rgb"] for r in rows if eight_bit(tuple(r["rgb"]), away_from_zero) != r["eight_bit"]["number"]]
    print(f"{section}: {len(rows)} rows | control(round) wrong on {control} | f64::round wrong on {len(naive)}")
    for rgb in naive:
        print("   ", rgb)

print("\n--- exhaustive: which inputs can differ at all ---")
cube_ties = [c for c in range(256) if (c / 95 if c < 95 else 1 + (c - 95) / 40) % 1 == 0.5]
print("channel bytes landing exactly on x.5 in the cube path:", cube_ties)
print("  of those, where the two roundings DISAGREE:",
      [c for c in cube_ties
       if round((c / 95 if c < 95 else 1 + (c - 95) / 40))
       != away_from_zero(c / 95 if c < 95 else 1 + (c - 95) / 40)])

gray_ties = []
for red in range(256):
    for green in range(256):
        for blue in range(256):
            pass
        break
    break
# The grayscale branch depends on max+min only; enumerate that instead.
disagreeing_sums = []
for total in range(0, 511):
    lightness = (total / 2.0) / 255.0
    if round(lightness * 25.0) != away_from_zero(lightness * 25.0):
        disagreeing_sums.append(total)
print("grayscale branch: max+min sums where the two roundings disagree:", disagreeing_sums)
