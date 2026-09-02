"""Generate the expected colour-downgrade table from Rich, before any Rust is written.

The gate for the native colour downgrade is exhaustive enumeration, not sampling.
This produces the oracle it is checked against, in two parts:

1. Every RGB triple the renderer can actually emit, extracted from the branch
   sources rather than retyped, plus the project theme. This proves today's output.
2. The algorithm-critical inputs. The 6x6x6 cube path is independent per channel,
   so all 256 values per channel is genuinely exhaustive for it; the grayscale
   branch depends jointly on saturation and lightness, so it gets a dense grid.
   This proves the algorithm rather than the palette, which matters because the
   current palette dodges the rounding hazard by luck.

Oracle revision: the Python at 8cb4c5f, via the installed Rich.

Usage: uv run python thoughts/.../probes/colour_downgrade_oracle.py [out.json]
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

from rich.color import Color, ColorSystem, ColorType

BRANCH = "0ffde41"
RENDERER_FILES = ("rust/session_render.rs", "rust/search_views.rs")
TRIPLE_IN_SGR = re.compile(r"(?:38|48);2;(\d{1,3});(\d{1,3});(\d{1,3})")
BARE_TRIPLE = re.compile(r'"(\d{1,3});(\d{1,3});(\d{1,3})"')
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{6})")


def renderer_triples() -> set[tuple[int, int, int]]:
    """Every RGB triple the branch renderer can emit, read from its source."""
    found: set[tuple[int, int, int]] = set()
    for path in RENDERER_FILES:
        source = subprocess.run(
            ["git", "show", f"{BRANCH}:{path}"],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
        for match in TRIPLE_IN_SGR.finditer(source):
            found.add(tuple(int(part) for part in match.groups()))
        # Hue tables hold bare "r;g;b" strings that get interpolated into SGR.
        for match in BARE_TRIPLE.finditer(source):
            triple = tuple(int(part) for part in match.groups())
            if all(component <= 255 for component in triple):
                found.add(triple)
    return found


def theme_triples() -> set[tuple[int, int, int]]:
    """Every colour the Python theme defines."""
    from chats import theme

    source = inspect.getsource(theme)
    return {
        tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
        for value in HEX_COLOUR.findall(source)
    }


def algorithm_critical() -> set[tuple[int, int, int]]:
    """Inputs that exercise the algorithm rather than the palette."""
    found: set[tuple[int, int, int]] = set()
    # The cube path is per-channel independent: all 256 values in each position,
    # against a saturated partner so the grayscale branch does not swallow them.
    for value in range(256):
        found.add((value, 0, 255))
        found.add((0, value, 255))
        found.add((255, 0, value))
    # The grayscale branch is joint in saturation and lightness.
    for level in range(0, 256, 3):
        found.add((level, level, level))
        for delta in (1, 2, 4, 8, 16, 32):
            found.add((min(level + delta, 255), level, max(level - delta, 0)))
    return found


def grayscale_tie_critical(limit: int = 40) -> set[tuple[int, int, int]]:
    """Triples where the grayscale branch's `round(l * 25.0)` lands exactly on a tie.

    Found by `views-and-colour`, who re-derived this table before trusting it. The
    cube path and the grayscale path each round, and the original generator only
    derived rows for the cube one — so the gate caught the rounding hazard on 11 rows
    and would have stopped catching it the moment the cube path was repaired, which is
    the exact next move a red gate invites.

    `l * 25` is `(max + min) * 5 / 102`, so a tie needs `max + min` in
    {51, 153, 255, 357, 459}. Python and Rust actually *disagree* only at 51, 255 and
    459 — at 153 and 357 the nearest even and the away-from-zero answers coincide. Only
    the disagreeing sums are worth rows.
    """
    from colorsys import rgb_to_hls

    disagreeing_sums = {51, 255, 459}
    found: set[tuple[int, int, int]] = set()
    for red in range(256):
        for green in range(256):
            for blue in range(256):
                if (max(red, green, blue) + min(red, green, blue)) not in disagreeing_sums:
                    continue
                _hue, _lightness, saturation = rgb_to_hls(red / 255, green / 255, blue / 255)
                if saturation >= 0.15:
                    continue  # cube branch, already covered
                found.add((red, green, blue))
                if len(found) >= limit:
                    return found
    return found


def standard_critical(limit: int = 48) -> set[tuple[int, int, int]]:
    """Triples where Rich's integer distance and a float port choose different colours.

    The STANDARD downgrade weights its redmean distance with integer `//` and `>>`.
    A float port is wrong roughly once in eleven thousand triples, and when it is
    wrong it picks an entirely different colour, not an adjacent one. Those rows are
    invisible to the palette and to the cube-path grid, so the gate needs them
    explicitly or it cannot see the hazard at all.
    """
    from rich._palettes import STANDARD_PALETTE

    colours = STANDARD_PALETTE._colors

    def argmin(triple: tuple[int, int, int], integer: bool) -> int:
        red, green, blue = triple
        best_distance: float | None = None
        best_index = 0
        for index, (red2, green2, blue2) in enumerate(colours):
            delta_red, delta_green, delta_blue = red - red2, green - green2, blue - blue2
            if integer:
                mean = (red + red2) // 2
                distance = (
                    (((512 + mean) * delta_red * delta_red) >> 8)
                    + 4 * delta_green * delta_green
                    + (((767 - mean) * delta_blue * delta_blue) >> 8)
                )
            else:
                mean = (red + red2) / 2
                distance = (
                    ((512 + mean) * delta_red * delta_red) / 256
                    + 4 * delta_green * delta_green
                    + ((767 - mean) * delta_blue * delta_blue) / 256
                )
            if best_distance is None or distance < best_distance:
                best_distance, best_index = distance, index
        return best_index

    found: set[tuple[int, int, int]] = set()
    for red in range(0, 256, 3):
        for green in range(0, 256, 3):
            for blue in range(0, 256, 3):
                triple = (red, green, blue)
                if argmin(triple, True) != argmin(triple, False):
                    found.add(triple)
                    if len(found) >= limit:
                        return found
    return found


def downgrade(triple: tuple[int, int, int], system: ColorSystem) -> dict:
    colour = Color.from_rgb(*triple)
    reduced = colour.downgrade(system)
    return {
        "type": reduced.type.name,
        "number": reduced.number,
        "triplet": list(reduced.triplet) if reduced.triplet else None,
    }


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("colour_downgrade_oracle.json")

    palette = sorted(renderer_triples() | theme_triples())
    critical = sorted(
        (algorithm_critical() | standard_critical() | grayscale_tie_critical())
        - set(palette)
    )

    table = {
        "oracle_revision": "8cb4c5f",
        "branch_read_for_palette": BRANCH,
        "rich_version": __import__("importlib.metadata", fromlist=["version"]).version("rich"),
        "palette": [
            {
                "rgb": list(triple),
                "eight_bit": downgrade(triple, ColorSystem.EIGHT_BIT),
                "standard": downgrade(triple, ColorSystem.STANDARD),
            }
            for triple in palette
        ],
        "algorithm_critical": [
            {
                "rgb": list(triple),
                "eight_bit": downgrade(triple, ColorSystem.EIGHT_BIT),
                "standard": downgrade(triple, ColorSystem.STANDARD),
            }
            for triple in critical
        ],
    }
    out_path.write_text(json.dumps(table, indent=1), encoding="utf-8")

    print(f"palette triples            {len(palette)}")
    print(f"algorithm-critical triples {len(critical)}")
    print(f"total oracle rows          {len(palette) + len(critical)}")
    print(f"written to                 {out_path}")

    # Report the rounding hazard explicitly, so it is visible rather than latent.
    import math
    from colorsys import rgb_to_hls

    def rust_round(value: float) -> int:
        return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)

    def six(component: int) -> float:
        return component / 95 if component < 95 else 1 + (component - 95) / 40

    hazardous = []
    for triple in palette:
        _hue, lightness, saturation = rgb_to_hls(*[c / 255 for c in triple])
        if saturation < 0.15:
            scaled = lightness * 25.0
            if round(scaled) != rust_round(scaled):
                hazardous.append((triple, "grayscale", scaled))
            continue
        for position, component in enumerate(triple):
            scaled = six(component)
            if round(scaled) != rust_round(scaled):
                hazardous.append((triple, "rgb"[position], scaled))

    print(
        f"\npalette colours where Python and Rust rounding disagree: {len(hazardous)}"
    )
    for item in hazardous:
        print("   ", item)
    print(
        "A zero here means the palette dodges the hazard, not that the algorithm is safe.\n"
        "The algorithm_critical rows are what prove the rounding."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
