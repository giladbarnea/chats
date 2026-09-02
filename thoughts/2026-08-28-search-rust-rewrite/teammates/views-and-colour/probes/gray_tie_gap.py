"""Does the 1,459-row colour oracle contain any row that exercises the
grayscale branch's rounding tie? If not, the gate is blind to a port that
repairs the cube path and leaves the grayscale path on f64::round.
"""
import json
from colorsys import rgb_to_hls
from math import floor

ORACLE = "thoughts/2026-08-28-search-rust-rewrite/teammates/session-core/colour-downgrade-oracle.json"
away = lambda x: int(floor(x + 0.5))


def branch_and_tie(rgb):
    red, green, blue = rgb
    _h, lightness, saturation = rgb_to_hls(red / 255.0, green / 255.0, blue / 255.0)
    if saturation >= 0.15:
        return "cube", False
    return "gray", round(lightness * 25.0) != away(lightness * 25.0)


oracle = json.load(open(ORACLE))
rows = oracle["palette"] + oracle["algorithm_critical"]
gray_rows = [r["rgb"] for r in rows if branch_and_tie(tuple(r["rgb"]))[0] == "gray"]
gray_tie_rows = [r["rgb"] for r in rows if branch_and_tie(tuple(r["rgb"])) == ("gray", True)]
print(f"rows total {len(rows)} | grayscale-branch rows {len(gray_rows)} | of those, rounding ties {len(gray_tie_rows)}")
print("tie rows in oracle:", gray_tie_rows)

# Do such triples exist at all, and what do they resolve to?
print("\nreal triples that hit the grayscale tie (first 6):")
found = 0
for red in range(256):
    for green in range(256):
        for blue in range(256):
            if red + green + blue == 0:
                continue
            if max(red, green, blue) + min(red, green, blue) not in (51, 255, 459):
                continue
            branch, tie = branch_and_tie((red, green, blue))
            if branch == "gray" and tie:
                _h, l, _s = rgb_to_hls(red / 255.0, green / 255.0, blue / 255.0)
                print(f"  ({red},{green},{blue}) l*25={l*25.0!r} rich->{231+round(l*25.0)} f64::round->{231+away(l*25.0)}")
                found += 1
                if found >= 6:
                    raise SystemExit(0)
