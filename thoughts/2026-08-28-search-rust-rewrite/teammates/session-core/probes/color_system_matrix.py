"""Characterize Rich's colour-system detection and downsampling, which the native colored renderer must reproduce.

The native branch hard-codes 24-bit `38;2;R;G;B` SGR everywhere. Rich picks a colour
system from COLORTERM and TERM, then downsamples every style to it. On any terminal
that is not truecolor, every coloured byte differs.

Run from the repo root: uv run python thoughts/.../probes/color_system_matrix.py
"""

from rich.color import Color
from rich.console import Console
from rich.style import Style

DETECTION_CASES = [
    ("COLORTERM=truecolor  TERM=xterm-256color", {"COLORTERM": "truecolor", "TERM": "xterm-256color"}),
    ("COLORTERM=24bit      TERM=xterm", {"COLORTERM": "24bit", "TERM": "xterm"}),
    ("COLORTERM=TrueColor  (mixed case)", {"COLORTERM": "TrueColor", "TERM": "xterm"}),
    ("COLORTERM=' truecolor ' (padded)", {"COLORTERM": " truecolor ", "TERM": "xterm"}),
    ("COLORTERM=yes        (unknown value)", {"COLORTERM": "yes", "TERM": "xterm"}),
    ("COLORTERM unset      TERM=xterm-256color", {"TERM": "xterm-256color"}),
    ("COLORTERM unset      TERM=screen-256color", {"TERM": "screen-256color"}),
    ("COLORTERM unset      TERM=xterm-kitty", {"TERM": "xterm-kitty"}),
    ("COLORTERM unset      TERM=xterm-16color", {"TERM": "xterm-16color"}),
    ("COLORTERM unset      TERM=xterm", {"TERM": "xterm"}),
]

print("=== Rich colour-system detection ===")
for label, environ in DETECTION_CASES:
    console = Console(force_terminal=True, _environ=environ)
    print(f"  {label:42} -> {console.color_system}")

print("\n=== the same style, rendered under each system ===")
# The search match highlight and a representative role hue.
SAMPLES = {
    "match highlight": Style.parse("bold #14181d on #e6b450"),
    "assistant hue": Style.parse("#c88bda"),
    "agent hue": Style.parse("#62bac6"),
}
SYSTEMS = {
    "truecolor": {"COLORTERM": "truecolor", "TERM": "xterm-256color"},
    "256": {"TERM": "xterm-256color"},
    "standard": {"TERM": "xterm"},
}

for name, style in SAMPLES.items():
    print(f"\n  {name}")
    for system, environ in SYSTEMS.items():
        console = Console(force_terminal=True, _environ=environ)
        with console.capture() as capture:
            console.print("X", style=style, end="")
        print(f"    {system:10} -> {capture.get()!r}")

print("\n=== downsample of one colour, directly ===")
color = Color.parse("#e6b450")
for system in ("TRUECOLOR", "EIGHT_BIT", "STANDARD"):
    from rich.color import ColorSystem

    target = getattr(ColorSystem, system)
    downgraded = color.downgrade(target)
    print(f"  {system:10} -> {downgraded!r}")
