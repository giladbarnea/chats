#!/usr/bin/env -S uv run
"""Falsify the colour and cell gates: mutate, require a catch, restore.

These eight ran ad hoc while the modules were being built, which left no durable
record of what the gates were proved able to catch. The mutation list is the
evidence; the tool is just how it is replayed.

Every mutation is a port somebody would plausibly write. `f64::round` is what any
Rust author reaches for; `unicode-width` gives you the no-joiner semantics; a single
hardcoded table is what you get for ignoring `UNICODE_VERSION`.

Usage: falsify_color_and_cells.py   (run from the repository root)
"""

import subprocess
import sys
from pathlib import Path

COLOR = Path("rust/color.rs")
CELLS = Path("rust/cells.rs")

MUTATIONS = [
    (COLOR, "C1 f64::round instead of ties-to-even", "color::",
     "    value.round_ties_even() as i64", "    value.round() as i64"),
    (COLOR, "C2 float redmean instead of integer", "color::",
     "    (((512 + red_mean) * red * red) >> 8) + 4 * green * green + (((767 - red_mean) * blue * blue) >> 8)",
     "    ((((512 + red_mean) as f64 * (red * red) as f64) / 256.0) + 4.0 * (green * green) as f64 + (((767 - red_mean) as f64 * (blue * blue) as f64) / 256.0)) as i64"),
    (CELLS, "L1 no zero-width-joiner path", "cells::",
     "self.joined_cell_len(text)",
     "text.chars().map(|c| self.character_cell_size(c)).sum()"),
    (CELLS, "L2 joiner does not swallow the next character", "cells::",
     "index += if index < characters.len() - 1 { 2 } else { 1 };", "index += 1;"),
    (CELLS, "L3 selector 16 never widens", "cells::",
     "total_width += usize::from(NARROW_TO_WIDE.contains(&previous));", "total_width += 0;"),
    (CELLS, "L4 bytes instead of code points on the fast path", "cells::",
     "return text.chars().count();", "return text.len();"),
    (CELLS, "L5 crop by code points, not cells", "cells::",
     "self.split_text(text, total).0", "text.chars().take(total).collect()"),
    (CELLS, "L7 chop_cells breaks on >= rather than >", "cells::",
     "            if line_size + cell_size > width {",
     "            if line_size + cell_size >= width {"),
    (CELLS, "L8 chop_cells carries the breaking grapheme twice", "cells::",
     "                line_offset = start;\n                line_size = 0;",
     "                line_offset = start;\n                line_size = cell_size;"),
    (CELLS, "L6 one hardcoded table, UNICODE_VERSION ignored", "cells::",
     "widths: WIDTH_TABLES[table_index(unicode_version)],",
     "widths: WIDTH_TABLES[VERSIONS.len() - 1],"),
]


def main() -> None:
    blind = []
    for path, label, filter_expression, old, new in MUTATIONS:
        original = path.read_text()
        if old not in original:
            print(f"  {label:<46} ANCHOR MISSING - result meaningless")
            blind.append(label)
            continue
        try:
            path.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                ["cargo", "test", "--no-default-features", "--lib", filter_expression],
                capture_output=True, text=True)
        finally:
            path.write_text(original)
        blob = result.stdout + result.stderr
        if "error[" in blob:
            print(f"  {label:<46} DID NOT COMPILE - result meaningless")
            blind.append(label)
        elif result.returncode != 0:
            differences = [line.strip() for line in blob.splitlines() if "differ from" in line]
            print(f"  {label:<46} caught  {differences[0] if differences else '(panic)'}")
        else:
            print(f"  {label:<46} NOT CAUGHT")
            blind.append(label)

    if blind:
        print(f"\nFAILED  {len(blind)} mutation(s) not caught or not applied")
        raise SystemExit(1)
    print(f"\nPASS    all {len(MUTATIONS)} mutations caught")


if __name__ == "__main__":
    main()
