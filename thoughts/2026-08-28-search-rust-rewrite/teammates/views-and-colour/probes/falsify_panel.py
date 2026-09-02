import subprocess, sys
from pathlib import Path
SRC = Path("rust/search_views.rs")
MUTATIONS = [
    ("P1 one dash too few",
     'let dashes = inner.saturating_sub(title_width + 2);',
     'let dashes = inner.saturating_sub(title_width + 3);'),
    ("P2 inner strip is width - 3",
     'let inner = width.saturating_sub(4);',
     'let inner = width.saturating_sub(3);'),
    ("P3 border does not cycle",
     'let border = BORDER_CYCLE[ordinal % BORDER_CYCLE.len()];',
     'let border = BORDER_CYCLE[0];'),
    ("P4 bottom border one short",
     'paint(&format!("╰{}╯", "─".repeat(width.saturating_sub(2))))',
     'paint(&format!("╰{}╯", "─".repeat(width.saturating_sub(3))))'),
    ("P5 the strip's leading space loses its own escape",
     'let mut strip = vec![Segment::styled(" ", border)];',
     'let mut strip = vec![Segment::plain(" ")];'),
    ("P6 interior padding uses width - 2",
     'let interior = width.saturating_sub(4);',
     'let interior = width.saturating_sub(2);'),
]
def main() -> None:
    # The file itself is the original; no backup argument to get wrong.
    original = SRC.read_text()
    for label, old, new in MUTATIONS:
        if old not in original:
            print(f"{label:<44} ANCHOR MISSING - result meaningless"); continue
        SRC.write_text(original.replace(old, new, 1))
        result = subprocess.run(
            ["cargo", "test", "--no-default-features", "--lib",
             "search_views::chrome_tests::every_recorded_panel"],
            capture_output=True, text=True)
        blob = result.stdout + result.stderr
        hit = [l for l in blob.splitlines() if "panel lines differ from Rich" in l]
        if hit:
            print(f"{label:<44} {hit[0].strip()}")
        elif "error[" in blob:
            print(f"{label:<44} DID NOT COMPILE - result meaningless")
        elif result.returncode != 0:
            print(f"{label:<44} caught (panic, exit {result.returncode})")
        else:
            print(f"{label:<44} NOT CAUGHT")
    SRC.write_text(original)

if __name__ == "__main__":
    main()
