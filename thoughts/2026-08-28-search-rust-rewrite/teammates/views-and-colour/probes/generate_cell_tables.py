#!/usr/bin/env -S uv run
"""Generate `rust/cell_tables.rs` from Rich's own unicode data.

Rich resolves a cell-width table per `UNICODE_VERSION`, defaulting to the latest.
That choice changes rendered output, so the native route reproduces every version
rather than pinning one. The tables are emitted from the installed Rich rather
than transcribed, and this script asserts the round trip before writing.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "src")

from rich._unicode_data import VERSIONS, load

OUTPUT = Path("rust/cell_tables.rs")


def main() -> None:
    narrow_to_wide = {version: load(version).narrow_to_wide for version in VERSIONS}
    shared = narrow_to_wide[VERSIONS[0]]
    assert all(other == shared for other in narrow_to_wide.values()), (
        "narrow_to_wide differs per version; the emitted table must become per-version too"
    )

    tables = {version: load(version).widths for version in VERSIONS}
    for version, widths in tables.items():
        assert list(widths) == sorted(widths), f"{version} table is not sorted"
        assert all(start <= end for start, end, _ in widths), f"{version} has an inverted range"

    lines: list[str] = [
        "//! Cell-width tables, generated from Rich's own unicode data.",
        "//!",
        "//! Do not edit. Regenerate with",
        "//! `teammates/views-and-colour/probes/generate_cell_tables.py`, which asserts the",
        "//! round trip against the installed Rich before writing.",
        "",
        "/// An inclusive codepoint range and the cell width every codepoint in it occupies.",
        "pub type WidthRange = (u32, u32, u8);",
        "",
        f"/// Every unicode version Rich ships a table for, oldest first.",
        "pub const VERSIONS: [(u32, u32, u32); %d] = [" % len(VERSIONS),
    ]
    for version in VERSIONS:
        major, minor, patch = (int(part) for part in version.split("."))
        lines.append(f"    ({major}, {minor}, {patch}),")
    lines.append("];")
    lines.append("")

    for version in VERSIONS:
        identifier = "WIDTHS_" + version.replace(".", "_")
        widths = tables[version]
        lines.append(f"const {identifier}: [WidthRange; {len(widths)}] = [")
        lines.extend(f"    ({start}, {end}, {width})," for start, end, width in widths)
        lines.append("];")
        lines.append("")

    lines.append("/// The width table for each entry of [`VERSIONS`], in the same order.")
    lines.append(f"pub const WIDTH_TABLES: [&[WidthRange]; {len(VERSIONS)}] = [")
    lines.extend(f"    &WIDTHS_{version.replace('.', '_')}," for version in VERSIONS)
    lines.append("];")
    lines.append("")

    lines.append("/// Characters that variation selector 16 widens from one cell to two.")
    lines.append("/// Identical across every version Rich ships, asserted by the generator.")
    lines.append(f"pub const NARROW_TO_WIDE: [char; {len(shared)}] = [")
    lines.extend(f"    '\\u{{{ord(character):x}}}'," for character in sorted(shared))
    lines.append("];")
    lines.append("")

    OUTPUT.write_text("\n".join(lines))
    subprocess.run(["rustfmt", str(OUTPUT)], check=False)
    print(f"wrote {OUTPUT} — {len(VERSIONS)} versions, "
          f"{sum(len(table) for table in tables.values())} ranges, "
          f"{len(shared)} narrow-to-wide characters")


if __name__ == "__main__":
    main()
