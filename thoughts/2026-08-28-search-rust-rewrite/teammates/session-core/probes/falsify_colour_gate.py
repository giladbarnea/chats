"""Prove the colour oracle discriminates each hazard, by writing the wrong port on purpose.

A gate is only worth the wrong implementations it can reject. Three hazards were
identified in Rich's downgrade; each gets a plausible-but-wrong version here, and
the oracle must catch every one. A hazard the oracle cannot catch is a hazard the
oracle does not cover, and the table needs extending rather than trusting.

Run from the repo root: uv run python thoughts/.../probes/falsify_colour_gate.py
"""

from __future__ import annotations

import json
import math
from colorsys import rgb_to_hls
from pathlib import Path

from rich.palette import Palette
from rich._palettes import STANDARD_PALETTE

ORACLE = Path(__file__).resolve().parent.parent / "colour-downgrade-oracle.json"
TABLE = json.loads(ORACLE.read_text(encoding="utf-8"))
ROWS = [(row, "palette") for row in TABLE["palette"]] + [
    (row, "algorithm_critical") for row in TABLE["algorithm_critical"]
]


def six(component: int) -> float:
    return component / 95 if component < 95 else 1 + (component - 95) / 40


def rust_round(value: float) -> int:
    """Rust's f64::round — half away from zero."""
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


# --------------------------------------------------------------- correct baseline

def correct_eight_bit(red: int, green: int, blue: int) -> int:
    _hue, lightness, saturation = rgb_to_hls(red / 255, green / 255, blue / 255)
    if saturation < 0.15:
        gray = round(lightness * 25.0)
        return 16 if gray == 0 else (231 if gray == 25 else 231 + gray)
    return 16 + 36 * round(six(red)) + 6 * round(six(green)) + round(six(blue))


def correct_standard(red: int, green: int, blue: int) -> int:
    return STANDARD_PALETTE.match((red, green, blue))


# ------------------------------------------------------------- wrong ports

def wrong_rounding(red: int, green: int, blue: int) -> int:
    """Hazard 1: Rust's f64::round instead of Python's round-half-to-even."""
    _hue, lightness, saturation = rgb_to_hls(red / 255, green / 255, blue / 255)
    if saturation < 0.15:
        gray = rust_round(lightness * 25.0)
        return 16 if gray == 0 else (231 if gray == 25 else 231 + gray)
    return 16 + 36 * rust_round(six(red)) + 6 * rust_round(six(green)) + rust_round(six(blue))


def hsv_saturation(red: int, green: int, blue: int) -> tuple[float, float]:
    """A plausible wrong rgb_to_hls: HSV saturation, (max-min)/max, not the HLS branch."""
    r, g, b = red / 255, green / 255, blue / 255
    high, low = max(r, g, b), min(r, g, b)
    lightness = (high + low) / 2.0
    saturation = 0.0 if high == 0 else (high - low) / high
    return lightness, saturation


def wrong_hls(red: int, green: int, blue: int) -> int:
    """Hazard 2: rgb_to_hls not matching colorsys branch for branch."""
    lightness, saturation = hsv_saturation(red, green, blue)
    if saturation < 0.15:
        gray = round(lightness * 25.0)
        return 16 if gray == 0 else (231 if gray == 25 else 231 + gray)
    return 16 + 36 * round(six(red)) + 6 * round(six(green)) + round(six(blue))


def wrong_standard_float(red: int, green: int, blue: int) -> int:
    """Hazard 3: float arithmetic where Rich uses integer // and >>."""
    colours = STANDARD_PALETTE._colors

    def distance(index: int) -> float:
        red2, green2, blue2 = colours[index]
        red_mean = (red + red2) / 2  # Rich uses //
        delta_red = red - red2
        delta_green = green - green2
        delta_blue = blue - blue2
        return math.sqrt(
            ((512 + red_mean) * delta_red * delta_red) / 256  # Rich uses >> 8
            + 4 * delta_green * delta_green
            + ((767 - red_mean) * delta_blue * delta_blue) / 256
        )

    return min(range(len(colours)), key=distance)


HAZARDS = [
    ("rounding: f64::round vs half-to-even", "eight_bit", correct_eight_bit, wrong_rounding),
    ("rgb_to_hls: HSV saturation vs HLS branch", "eight_bit", correct_eight_bit, wrong_hls),
    ("STANDARD: float arithmetic vs // and >>", "standard", correct_standard, wrong_standard_float),
]


def main() -> int:
    print(f"oracle rows: {len(ROWS)}  (palette {len(TABLE['palette'])}, "
          f"critical {len(TABLE['algorithm_critical'])})\n")

    undetected = 0
    for label, field, correct, wrong in HAZARDS:
        # First confirm the "correct" reference actually reproduces the oracle.
        reference_mismatches = [
            row["rgb"] for row, _ in ROWS if correct(*row["rgb"]) != row[field]["number"]
        ]
        caught = [
            (row["rgb"], row[field]["number"], wrong(*row["rgb"]), section)
            for row, section in ROWS
            if wrong(*row["rgb"]) != row[field]["number"]
        ]
        in_palette = sum(1 for *_, section in caught if section == "palette")

        print(f"--- {label}")
        if reference_mismatches:
            print(f"    REFERENCE DISAGREES WITH ORACLE on {len(reference_mismatches)} rows"
                  f" — the baseline is wrong, not the hazard")
        print(f"    caught on {len(caught)} rows  (palette {in_palette}, "
              f"critical {len(caught) - in_palette})")
        if caught:
            for rgb, expected, actual, section in caught[:3]:
                print(f"      {tuple(rgb)} expected {expected} got {actual}  [{section}]")
        else:
            undetected += 1
            print("      *** ORACLE CANNOT SEE THIS HAZARD — extend the table ***")
        print()

    print("gate verdict:",
          "complete — every hazard is discriminated"
          if not undetected
          else f"INCOMPLETE — {undetected} hazard(s) invisible to the oracle")
    return 1 if undetected else 0


if __name__ == "__main__":
    raise SystemExit(main())
